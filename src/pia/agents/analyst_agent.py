"""
Analyst: turns one report into knowledge.

    claim job → summary + embedding + situation
              → extract mentions/events (full article)
              → resolve every mention to an identity (Wikidata Q-id, local, or review)
              → store mentions, events (with quotes), geocode the report
              → DONE / FAILED (retried)

Relations are never written here; kg.relations computes them from events.
"""
import hashlib
import os
import socket
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.core.nlp import ExtractionError, NLPManager
from pia.kg.normalize import normalize
from pia.kg.ontology import ACTIONS, LLM_ACTIONS, TOPICS
from pia.kg.verbs import MODALITIES, VerbCatalogue, guard_family, kind_for_stance
from pia.kg.resolver import Resolver


def _legacy_action(family: str, stance) -> str:
    """The old 23-verb code for grouping and GDELT parity, from the family."""
    head, sub = family.split("·")
    return {"force": "ATTACK", "coercion": "COERCE", "sanction": "SANCTION", "accusation": "ACCUSE", "threat": "THREATEN",
            "agreement": "AGREE", "aid": "AID", "support": "COOPERATE", "meeting": "MEET",
            "role": "APPOINT", "ownership": "ACQUIRE", "statement": "STATEMENT"}.get(sub, "OTHER")


class AnalystAgent(BaseAgent):
    STALE_MINUTES = int(os.getenv("ANALYST_STALE_MINUTES", "10"))
    MAX_RETRIES = int(os.getenv("ANALYST_MAX_RETRIES", "3"))
    RETRY_DELAY_MINUTES = int(os.getenv("ANALYST_RETRY_DELAY_MINUTES", "5"))
    MIN_EVENT_CONFIDENCE = float(os.getenv("MIN_EVENT_CONFIDENCE", "0.5"))

    def setup(self):
        self.db = DatabaseManager()
        self.nlp = NLPManager()
        self.resolver = Resolver(self.db, llm_choose=self.nlp.choose_candidate)
        self.verbs = VerbCatalogue(self.db, embed=self.nlp.generate_embedding)
        self.nlp.set_catalogue(self.verbs.prompt_block())
        self._catalogue_at = time.time()
        self.name = f"analyst_{socket.gethostname()}"
        logger.info(f"{self.name} ready (event extraction + Wikidata resolution)")

    # ── queue ─────────────────────────────────────────────────────────────────

    def poll(self):
        if time.time() - self._catalogue_at > 600:      # new verbs from any analyst reach every prompt within 10 min
            self.verbs.reload()
            self.nlp.set_catalogue(self.verbs.prompt_block())
            self._catalogue_at = time.time()
        while self.running:
            if not self.process_one_job():
                return
            self.heartbeat("OK", {"interval_sec": self.interval_sec})

    def claim_job(self) -> Optional[Dict]:
        rows = self.db.execute_query("""
            UPDATE analysis_queue
            SET status = 'PROCESSING', processed_at = NOW(), assigned_at = NOW(), assigned_agent = %s
            WHERE queue_id = (
                SELECT q.queue_id FROM analysis_queue q
                WHERE q.status = 'PENDING'
                   OR (q.status = 'PROCESSING' AND q.processed_at < NOW() - make_interval(mins => %s))
                   OR (q.status = 'FAILED' AND q.retry_count < %s AND q.processed_at < NOW() - make_interval(mins => %s))
                ORDER BY q.priority = 'CRITICAL' DESC, q.created_at ASC
                FOR UPDATE SKIP LOCKED LIMIT 1)
            RETURNING queue_id, uir_uid, retry_count
        """, (self.name, self.STALE_MINUTES, self.MAX_RETRIES, self.RETRY_DELAY_MINUTES), fetch=True)
        return rows[0] if rows else None

    def fail_job(self, job_id, message: str, retryable: bool = True):
        self.db.execute_query("""
            UPDATE analysis_queue SET status = 'FAILED', error_message = %s,
                retry_count = CASE WHEN %s THEN retry_count + 1 ELSE %s END
            WHERE queue_id = %s
        """, (str(message)[:2000], retryable, self.MAX_RETRIES, job_id))

    def process_one_job(self) -> bool:
        claimed = self.claim_job()
        if not claimed:
            return False
        job_id, uid = claimed['queue_id'], claimed['uir_uid']

        rows = self.db.execute_query("""
            SELECT u.uid, u.geo, u.domain, u.priority, u.content_headline, u.content_summary, u.content_raw,
                   u.published_at, u.created_at, u.source_id, u.source_type, u.client_id, u.mission_id,
                   COALESCE(s.trust, 0.5) AS source_trust, s.country_qid AS source_country,
                   (SELECT ARRAY_AGG(e.name) FROM entities e WHERE e.entity_id = ANY(m.watchlist)) AS mission_keywords
            FROM intelligence_records u
            LEFT JOIN sources s ON s.source_id = u.source_id
            LEFT JOIN missions m ON m.mission_id = u.mission_id
            WHERE u.uid = %s
        """, (uid,), fetch=True)
        if not rows:
            self.fail_job(job_id, "report missing", retryable=False)
            return True
        report = rows[0]
        logger.info(f"claimed {job_id} [{report['source_id']}] {str(report['content_headline'])[:60]}")

        try:
            text = report['content_raw'] or report['content_summary'] or report['content_headline'] or ""
            summary_vec = self.nlp.generate_embedding((report['content_summary'] or report['content_headline'] or "").lower())
            cluster_id = self.correlate_and_cluster(report, summary_vec)

            if report['source_type'] in ('GEOINT', 'SIGINT') or len(text) < 80:
                # sensor readings and tiny blurbs: no LLM extraction, just bookkeeping
                self.finish(job_id, uid, cluster_id, summary_vec, None, [])
                return True

            extraction = self.nlp.extract_events(
                text, headline=report['content_headline'] or "", outlet=report['source_id'] or "",
                published=(report['published_at'] or report['created_at']).date().isoformat(),
                mission_keywords=report.get('mission_keywords'))

            context = {
                "headline": report['content_headline'], "country_context": extraction.get("country_context"),
                "country_qid": self._country_qid(extraction.get("country_context")) or report.get('source_country'),
            }
            resolved = self.store_mentions(uid, extraction.get("mentions", []), context)
            self.store_events(report, extraction.get("events", []), resolved, context)
            self.geocode_report(report, resolved)

            names = sorted({e['name'] for e in resolved.values() if e and e['resolution'] == 'RESOLVED'})
            self.finish(job_id, uid, cluster_id, summary_vec, extraction.get("summary"), names)
        except ExtractionError as e:
            logger.error(f"extraction failed {job_id}: {e}")
            self.fail_job(job_id, f"extraction: {e}")
        except Exception as e:
            logger.exception(f"job {job_id} failed")
            self.fail_job(job_id, str(e))
        return True

    def finish(self, job_id, uid, cluster_id, vec, summary, names):
        summary = summary.strip() if isinstance(summary, str) and summary.strip() else None
        self.db.execute_query("""
            UPDATE intelligence_records
            SET cluster_id = %s, entities = %s, embedding = COALESCE(%s::vector, embedding),
                content_summary = COALESCE(%s, content_summary)
            WHERE uid = %s
        """, (cluster_id, names, vec or None, summary, uid))
        self.db.execute_query(
            "UPDATE analysis_queue SET status = 'DONE', error_message = NULL, result_cluster = %s WHERE queue_id = %s",
            (cluster_id, job_id))
        logger.success(f"done {uid}: {len(names)} entities")

    # ── identity ──────────────────────────────────────────────────────────────

    def _country_qid(self, country_name: Optional[str]) -> Optional[str]:
        if not country_name:
            return None
        row = self.db.execute_query("""
            SELECT e.qid FROM entity_aliases a JOIN entities e ON e.entity_id = a.entity_id
            WHERE a.alias_norm = %s AND e.kind = 'COUNTRY' AND e.qid IS NOT NULL LIMIT 1
        """, (normalize(country_name),), fetch=True)
        return row[0]['qid'] if row else None

    def store_mentions(self, uid, mentions: List[Dict], context: dict) -> Dict[str, Optional[dict]]:
        """surface → entity (or None when rejected). Writes the mentions table."""
        resolved: Dict[str, Optional[dict]] = {}
        for m in mentions:
            surface = str(m.get("surface", "")).strip()
            if not surface or surface in resolved:
                continue
            kind = str(m.get("kind", "UNKNOWN")).upper()
            role = str(m.get("role", "MENTIONED")).upper()
            if role not in ("ACTOR", "TARGET", "LOCATION", "MENTIONED"):
                role = "MENTIONED"
            ent = self.resolver.resolve(surface, kind_hint=kind, role=role, context=context)
            resolved[surface] = ent
            if not ent:
                continue
            role_out = ent.get("role") or role
            self.db.execute_query("""
                INSERT INTO mentions (report_uid, entity_id, surface, role, confidence)
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, (uid, ent['entity_id'], surface, role_out, 0.9 if ent['resolution'] == 'RESOLVED' else 0.5))
            self.db.execute_query(
                "UPDATE entities SET mention_count = mention_count + 1, last_seen = NOW() WHERE entity_id = %s",
                (ent['entity_id'],))
        return resolved

    # ── events ────────────────────────────────────────────────────────────────

    def store_events(self, report, events: List[Dict], resolved: Dict[str, Optional[dict]], context: dict):
        trust = float(report['source_trust'] or 0.5)
        published = report['published_at'] or report['created_at']
        for ev in events:
            # ── the event's own judgement (prompt v3); old-style "action" answers still accepted ──
            predicate = str(ev.get("predicate") or ev.get("verb") or ev.get("action") or "").strip()
            verb_choice = str(ev.get("verb") or "").strip()
            try:
                stance = max(-3, min(3, int(round(float(ev.get("stance"))))))
            except (TypeError, ValueError):
                stance = None
            family = guard_family(ev.get("family"), stance)
            modality = str(ev.get("modality") or "asserted").lower().strip()
            if modality not in MODALITIES:
                modality = "asserted"
            polarity = ev.get("polarity")
            polarity = True if polarity is None else bool(polarity) and str(polarity).lower() not in ("false", "0", "no")
            action = str(ev.get("action", "")).upper()
            if action not in LLM_ACTIONS:
                action = _legacy_action(family, stance)
            topic = str(ev.get("topic") or "other").lower().strip()
            if topic not in TOPICS:
                topic = "other"
            actor = self._lookup(ev.get("actor"), resolved, "ACTOR", context)
            if not actor or actor['resolution'] != 'RESOLVED':
                continue  # strict: no event without a known actor
            target = self._lookup(ev.get("target"), resolved, "TARGET", context)
            if target and target['resolution'] != 'RESOLVED':
                target = None
            location = self._lookup(ev.get("location"), resolved, "LOCATION", context)
            conf = min(1.0, max(0.0, float(ev.get("confidence") or 0.6))) * (0.6 + 0.4 * trust)
            if conf < self.MIN_EVENT_CONFIDENCE:
                continue
            quote = str(ev.get("quote") or "")[:1000]
            # the catalogue: the model's pick when it named one, else its own words
            chosen = verb_choice if verb_choice and verb_choice.upper() != "NEW" else predicate
            verb_id, verb, is_new = self.verbs.canonical(chosen or predicate, family, stance, quote=quote)
            if predicate and predicate.lower() != verb:
                self.verbs.alias(predicate, verb_id)                 # the article's phrasing points at the same verb
            kind = kind_for_stance(stance, family)
            when, precision = self._event_time(ev.get("date"), ev.get("precision"), published)
            geo = self._entity_geo(location) if location else None
            dedup = hashlib.sha1(f"{actor['entity_id']}|{target['entity_id'] if target else ''}|{verb}|{when.date()}|{report['source_id']}".encode()).hexdigest()
            self.db.execute_query("""
                INSERT INTO events (event_time, time_precision, action, kind, actor_id, target_id, location_id, geo,
                                    report_uid, source_id, origin, quote, confidence, tone, topic, weight_class,
                                    predicate, verb_id, family, stance, modality, polarity, dedup_key)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::geometry, %s, %s, 'llm', %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dedup_key, event_time) DO NOTHING
            """, (when, precision, action, kind, actor['entity_id'], target['entity_id'] if target else None,
                  location['entity_id'] if location else None, geo, report['uid'], report['source_id'],
                  quote, round(conf, 3), float(stance * 3) if stance is not None else ACTIONS[action][2], topic,
                  "material" if modality == "asserted" else "verbal",
                  (predicate or verb)[:80], verb_id, family, stance, modality, polarity, dedup))

    def _lookup(self, surface, resolved, role, context) -> Optional[dict]:
        if not surface:
            return None
        surface = str(surface).strip()
        if surface not in resolved:
            resolved[surface] = self.resolver.resolve(surface, role=role, context=context)
        ent = resolved[surface]
        # a ministry / armed force / agency / place acts as its country in events (the mention keeps the body);
        # a place with no country ("West Asia") is no party to an event at all
        if ent and role in ("ACTOR", "TARGET") and "event_entity" in ent:
            return ent["event_entity"]
        return ent

    @staticmethod
    def _event_time(date_str, precision, published) -> Tuple[datetime, str]:
        if date_str:
            try:
                d = datetime.fromisoformat(str(date_str)[:10]).replace(tzinfo=timezone.utc)
                return d, ("month" if precision == "month" else "day")
            except ValueError:
                pass
        return published.astimezone(timezone.utc), "day"

    def _entity_geo(self, ent: Optional[dict]) -> Optional[str]:
        if not ent:
            return None
        row = self.db.execute_query("SELECT ST_AsEWKT(primary_geo) AS g FROM entities WHERE entity_id = %s", (ent['entity_id'],), fetch=True)
        return row[0]['g'] if row and row[0]['g'] else None

    def geocode_report(self, report, resolved: Dict[str, Optional[dict]]):
        """Reports without a position take the position of their location / country mention."""
        if report['geo']:
            return
        for preference in ("PLACE", "COUNTRY"):
            for ent in resolved.values():
                if ent and ent['kind'] == preference and ent['resolution'] == 'RESOLVED':
                    g = self._entity_geo(ent)
                    if g:
                        self.db.execute_query("""
                            UPDATE intelligence_records SET geo = %s::geometry, geo_precision = %s, geo_source = %s WHERE uid = %s
                        """, (g, 'city' if preference == 'PLACE' else 'country', f"entity:{ent['qid'] or ent['entity_id']}", report['uid']))
                        return

    # ── situations ────────────────────────────────────────────────────────────

    def correlate_and_cluster(self, report, vec) -> Optional[str]:
        """Same area (50 km) + same domain + similar meaning (> 0.6) within 3 days → same situation."""
        geo, domain = report['geo'], report['domain']
        if not geo or not vec:
            return None
        hit = self.db.execute_query("""
            SELECT cluster_id FROM intelligence_clusters
            WHERE status = 'ACTIVE' AND domain = %s AND client_id = %s
              AND updated_at > NOW() - INTERVAL '3 days'
              AND ST_DWithin(geo_centroid::geography, %s::geography, 50000)
              AND semantic_dna IS NOT NULL AND (1 - (semantic_dna <=> %s::vector)) > 0.6
            ORDER BY semantic_dna <=> %s::vector LIMIT 1
        """, (domain, report['client_id'], geo, vec, vec), fetch=True)
        if hit:
            cid = hit[0]['cluster_id']
            self.db.execute_query("UPDATE intelligence_clusters SET updated_at = NOW(), uir_count = uir_count + 1 WHERE cluster_id = %s", (cid,))
            return cid
        # Only start a situation when a second report agrees: a lone report stays unclustered
        near = self.db.execute_query("""
            SELECT uid FROM intelligence_records
            WHERE uid <> %s AND domain = %s AND cluster_id IS NULL AND embedding IS NOT NULL
              AND created_at > NOW() - INTERVAL '3 days' AND geo IS NOT NULL
              AND ST_DWithin(geo::geography, %s::geography, 50000)
              AND (1 - (embedding <=> %s::vector)) > 0.6
            LIMIT 1
        """, (report['uid'], domain, geo, vec), fetch=True)
        if not near:
            return None
        title = f"{str(domain).title()} situation: {str(report['content_headline'])[:80]}"
        row = self.db.execute_query("""
            INSERT INTO intelligence_clusters (title, domain, status, priority, confidence, geo_centroid, uir_count, semantic_dna, client_id, event_start)
            VALUES (%s, %s, 'ACTIVE', %s, 0.6, %s, 2, %s::vector, %s, NOW()) RETURNING cluster_id
        """, (title, domain, report['priority'], geo, vec, report['client_id']), fetch=True)
        cid = row[0]['cluster_id']
        self.db.execute_query("UPDATE intelligence_records SET cluster_id = %s WHERE uid = %s", (cid, near[0]['uid']))
        return cid

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    agent = AnalystAgent(name="heartbeat_analyst_v2", interval_sec=10)
    agent.run()
