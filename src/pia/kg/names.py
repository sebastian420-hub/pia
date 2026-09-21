"""
Self-maintaining names: the resolver's review queue decides its clear cases itself.

Every name the resolver could not place waits as NEEDS_REVIEW. Most of them are not new things:
  1. a collective of a known thing — "Chinese Foreign Ministry", "Houthi militia", "South Korean
     government", "US embassy" → the country / the group it belongs to (as government bodies already do)
  2. the same place or organisation spelt a little differently — "Bab al-Mandab Strait" vs the known
     "Bab-el-Mandeb" (places and organisations only; two people can have near-identical names)
  3. a demonym filed as a person — "Palestinian", "Iranians" → not an entity
  4. a name seen once and never again in 14 days → kept quietly as LOCAL, out of the queue
Review keeps the rest. Everything decided here is logged in ai_feedback (by = 'names'), reversible.
"""
import json
import re
from typing import Dict, List, Optional

from loguru import logger

from pia.kg import wikidata
from pia.kg.normalize import normalize

# words that make a phrase "the X of something" rather than a thing of its own
COLLECTIVE = {"government", "delegation", "officials", "authorities", "regime", "leadership", "ministry", "army",
              "military", "forces", "police", "navy", "parliament", "militia", "group", "fighters", "rebels",
              "movement", "embassy", "media", "troops", "administration", "cabinet", "junta", "side", "team",
              "state", "command", "council", "spokesperson", "spokesman", "spokeswoman", "officers", "guards", "soldiers"}
# qualifiers that may sit between the head and the collective word
QUALIFIER = {"foreign", "health", "defence", "defense", "commerce", "riot", "interior", "national", "central", "supreme",
             "revolutionary", "run", "backed", "led", "armed", "security", "federal", "royal", "state", "civil", "coast"}
COLLECTIVE_KINDS = {"COUNTRY", "ORG"}

SIMILAR_MIN = 0.9          # trigram similarity for a spelling variant (places / organisations)
QUIET_DAYS = 14


def merge(db, loser_id: str, keeper_id: str, alias: Optional[str], why: str):
    """Re-points mentions and events from a local entity to the keeper, keeps the name as an alias, removes it."""
    # a report that already mentions the keeper keeps that row (mentions are unique per report and entity)
    db.execute_query("""
        DELETE FROM mentions l WHERE l.entity_id = %s
          AND EXISTS (SELECT 1 FROM mentions k WHERE k.entity_id = %s AND k.report_uid = l.report_uid)
    """, (loser_id, keeper_id))
    db.execute_query("UPDATE mentions SET entity_id = %s WHERE entity_id = %s", (keeper_id, loser_id))
    for col in ("actor_id", "target_id", "location_id"):
        db.execute_query(f"UPDATE events SET {col} = %s WHERE {col} = %s", (keeper_id, loser_id))
    db.execute_query("UPDATE external_ids SET entity_id = %s WHERE entity_id = %s", (keeper_id, loser_id))
    if alias and normalize(alias):
        db.execute_query("INSERT INTO entity_aliases (entity_id, alias, alias_norm, source) VALUES (%s, %s, %s, 'auto') ON CONFLICT DO NOTHING",
                         (keeper_id, alias[:200], normalize(alias)))
    # relations (facts, Wikidata links): the keeper's own row wins where both have one; the rest move over
    db.execute_query("""
        DELETE FROM relations l WHERE (l.a_id = %s OR l.b_id = %s) AND (l.a_id = %s OR l.b_id = %s
           OR EXISTS (SELECT 1 FROM relations k WHERE k.kind = l.kind AND k.source = l.source
                      AND k.a_id = CASE WHEN l.a_id = %s THEN %s ELSE l.a_id END
                      AND k.b_id = CASE WHEN l.b_id = %s THEN %s ELSE l.b_id END))
    """, (loser_id, loser_id, keeper_id, keeper_id, loser_id, keeper_id, loser_id, keeper_id))
    db.execute_query("UPDATE relations SET a_id = %s WHERE a_id = %s", (keeper_id, loser_id))
    db.execute_query("UPDATE relations SET b_id = %s WHERE b_id = %s", (keeper_id, loser_id))
    db.execute_query("INSERT INTO entity_aliases (entity_id, alias, alias_norm, source) SELECT %s, alias, alias_norm, source FROM entity_aliases WHERE entity_id = %s ON CONFLICT DO NOTHING",
                     (keeper_id, loser_id))
    db.execute_query("""
        UPDATE entities k SET mention_count = (SELECT COUNT(*) FROM mentions m WHERE m.entity_id = k.entity_id),
               last_seen = GREATEST(k.last_seen, l.last_seen),
               listings = (SELECT COALESCE(jsonb_agg(DISTINCT x), '[]'::jsonb) FROM jsonb_array_elements(COALESCE(k.listings, '[]'::jsonb) || COALESCE(l.listings, '[]'::jsonb)) x),
               properties = COALESCE(l.properties, '{}'::jsonb) || COALESCE(k.properties, '{}'::jsonb),
               description = COALESCE(k.description, l.description), country_qid = COALESCE(k.country_qid, l.country_qid)
        FROM entities l WHERE k.entity_id = %s AND l.entity_id = %s
    """, (keeper_id, loser_id))
    db.execute_query("DELETE FROM entities WHERE entity_id = %s", (loser_id,))
    db.execute_query("INSERT INTO ai_feedback (entity_id, feedback_type, human_correction) VALUES (%s, 'MERGED', %s)",
                     (keeper_id, json.dumps({"from": str(loser_id), "name": alias, "by": "names", "why": why})))


class NameKeeper:
    def __init__(self, db):
        self.db = db
        self._demonyms: Optional[Dict[str, str]] = None    # demonym (normalised) → country entity_id

    # ── demonyms (Wikidata P1549), cached on the country rows ──
    def demonyms(self) -> Dict[str, str]:
        if self._demonyms is not None:
            return self._demonyms
        q = """SELECT entity_id, qid, sitelinks, metadata->'demonyms' AS d, metadata ? 'iso3' AS current
               FROM entities WHERE kind = 'COUNTRY' AND resolution = 'RESOLVED' AND qid IS NOT NULL"""
        rows = self.db.execute_query(q, fetch=True) or []
        missing = [r for r in rows if r["d"] is None]
        for i in range(0, len(missing), 50):
            self._fetch_demonyms(missing[i:i + 50])
        if missing:
            rows = self.db.execute_query(q, fetch=True) or []
        # "Russian" names Russia, not the Russian Empire; "Chinese" the PRC, not the Republic of China:
        # a state with an ISO code (a current one) wins, then the better-known one
        out: Dict[str, str] = {}
        best: Dict[str, tuple] = {}
        self._current: Dict[str, bool] = {}
        for r in rows:
            d = r["d"]
            d = json.loads(d) if isinstance(d, str) else (d or [])
            rank = (bool(r["current"]), r["sitelinks"] or 0)
            for w in d:
                k = normalize(w)
                if k not in best or rank > best[k]:
                    best[k] = rank
                    out[k] = str(r["entity_id"])
                    self._current[k] = bool(r["current"])
        self._demonyms = out
        return out

    DEMONYM_SUFFIXES = ("ian", "ean", "ese", "ish", "i", "an", "n", "ic")

    def country_by_adjective(self, head: str) -> Optional[str]:
        """'iraqi' → Iraq, 'israeli' → Israel when Wikidata lists no English demonym: the stem must be a
        current country's exact alias, so 'chin' or 'fren' never match anything."""
        for suf in self.DEMONYM_SUFFIXES:
            if head.endswith(suf) and len(head) > len(suf) + 2:
                rows = self.db.execute_query("""
                    SELECT e.entity_id FROM entity_aliases a JOIN entities e ON e.entity_id = a.entity_id
                    WHERE e.kind = 'COUNTRY' AND e.resolution = 'RESOLVED' AND e.metadata ? 'iso3' AND a.alias_norm = %s
                    ORDER BY e.mention_count DESC, e.sitelinks DESC LIMIT 1
                """, (head[:-len(suf)],), fetch=True)
                if rows:
                    return str(rows[0]["entity_id"])
        return None

    def _fetch_demonyms(self, rows: List[Dict]):
        try:
            ents = wikidata.get_entities([r["qid"] for r in rows], raw=True)
        except Exception as e:
            logger.warning(f"demonyms: wikidata unavailable ({e})")
            return
        for r in rows:
            ent = ents.get(r["qid"]) or {}
            words = []
            for v, _ in wikidata._claim_values(ent, "P1549"):
                if isinstance(v, dict) and v.get("language", "").startswith("en") and v.get("text"):
                    words.append(v["text"])
            # "Iranian" → also "Iranians"; the label itself covers "Iran government"
            plural = [w + "s" for w in words if not w.endswith("s")]
            self.db.execute_query("UPDATE entities SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb WHERE entity_id = %s",
                                  (json.dumps({"demonyms": sorted(set(words + plural))}), r["entity_id"]))

    # ── rule 1: a collective of a known thing ──
    def head_of(self, name: str) -> Optional[str]:
        """'Chinese Foreign Ministry' → 'chinese'; 'Houthi militia' → 'houthi'; 'Jacob Wulfson' → None."""
        toks = normalize(name).replace("-", " ").split()
        if len(toks) < 2 or toks[-1] not in COLLECTIVE:
            return None
        while len(toks) > 1 and (toks[-1] in COLLECTIVE or toks[-1] in QUALIFIER):
            toks.pop()
        head = " ".join(toks)
        return head if head and head not in COLLECTIVE and head not in QUALIFIER else None

    def owner_of(self, head: str) -> Optional[Dict]:
        """The resolved COUNTRY/ORG the head names: by demonym, by alias, or by the alias' plural / prefix."""
        dem = self.demonyms().get(head)
        if dem and self._current.get(head):
            return {"entity_id": dem, "how": "demonym"}
        adj = self.country_by_adjective(head)
        if adj:
            return {"entity_id": adj, "how": "adjective"}
        if dem:
            return {"entity_id": dem, "how": "demonym"}
        rows = self.db.execute_query("""
            SELECT e.entity_id, e.kind, e.sitelinks, e.mention_count, a.alias_norm
            FROM entity_aliases a JOIN entities e ON e.entity_id = a.entity_id
            WHERE e.resolution = 'RESOLVED' AND e.kind = ANY(%s)
              AND (a.alias_norm = %s OR a.alias_norm = %s OR a.alias_norm LIKE %s)
            ORDER BY (a.alias_norm = %s) DESC, (e.kind = 'COUNTRY') DESC, e.mention_count DESC, e.sitelinks DESC
        """, (list(COLLECTIVE_KINDS), head, head + "s", head + " %", head), fetch=True) or []
        # a prefix hit ("houthi rebels" for "houthi") only counts when every hit is the same entity
        if rows and (rows[0]["alias_norm"] in (head, head + "s") or len({r["entity_id"] for r in rows}) == 1):
            return {"entity_id": str(rows[0]["entity_id"]), "how": "alias"}
        return None

    # ── rule 2: a spelling variant of a known place / organisation ──
    def variant_of(self, name: str, kind: str) -> Optional[Dict]:
        if kind not in ("PLACE", "ORG"):
            return None
        rows = self.db.execute_query("""
            SELECT e.entity_id, a.alias, similarity(a.alias_norm, %s) AS s
            FROM entity_aliases a JOIN entities e ON e.entity_id = a.entity_id
            WHERE e.resolution = 'RESOLVED' AND e.kind = %s AND a.alias_norm %% %s
            ORDER BY s DESC, e.mention_count DESC LIMIT 2
        """, (normalize(name), kind, normalize(name)), fetch=True) or []
        if rows and rows[0]["s"] >= SIMILAR_MIN and (len(rows) == 1 or rows[1]["s"] < rows[0]["s"] or rows[1]["entity_id"] == rows[0]["entity_id"]):
            return {"entity_id": str(rows[0]["entity_id"]), "alias": rows[0]["alias"], "s": float(rows[0]["s"])}
        return None

    # ── the pass ──
    def run(self, limit: int = 200) -> Dict[str, int]:
        stats = {"collective": 0, "variant": 0, "demonym_person": 0, "quiet": 0, "kept": 0}
        rows = self.db.execute_query("""
            SELECT entity_id, name, kind, mention_count, last_seen, created_at, (metadata->>'names_checked') IS NOT NULL AS checked
            FROM entities WHERE resolution = 'NEEDS_REVIEW'
            ORDER BY (metadata->>'names_checked') IS NULL DESC, mention_count DESC LIMIT %s
        """, (limit,), fetch=True) or []
        dem = self.demonyms()
        for r in rows:
            eid, name, kind = str(r["entity_id"]), r["name"], r["kind"]
            norm = normalize(name)
            if kind == "PERSON" and norm in dem:
                self.db.execute_query("UPDATE entities SET resolution = 'REJECTED', updated_at = NOW() WHERE entity_id = %s", (eid,))
                self.db.execute_query("DELETE FROM mentions WHERE entity_id = %s", (eid,))
                self.db.execute_query("INSERT INTO ai_feedback (entity_id, feedback_type, human_correction) VALUES (%s, 'REJECTED_HALLUCINATION', %s)",
                                      (eid, json.dumps({"name": name, "by": "names", "why": "demonym as person"})))
                stats["demonym_person"] += 1
                continue
            head = self.head_of(name)
            owner = self.owner_of(head) if head else None
            if owner and owner["entity_id"] != eid:
                merge(self.db, eid, owner["entity_id"], name, f"collective of {head} ({owner['how']})")
                stats["collective"] += 1
                continue
            var = self.variant_of(name, kind)
            if var and var["entity_id"] != eid:
                merge(self.db, eid, var["entity_id"], name, f"spelling of {var['alias']} ({var['s']:.2f})")
                stats["variant"] += 1
                continue
            if not r["checked"]:
                self.db.execute_query("UPDATE entities SET metadata = COALESCE(metadata, '{}'::jsonb) || '{\"names_checked\": true}' WHERE entity_id = %s", (eid,))
                stats["kept"] += 1
        # rule 4: quiet names leave the queue
        quiet = self.db.execute_query("""
            UPDATE entities SET resolution = 'LOCAL', watch_status = 'PASSIVE', updated_at = NOW(),
                   metadata = COALESCE(metadata, '{}'::jsonb) || '{"quiet": true}'
            WHERE resolution = 'NEEDS_REVIEW' AND mention_count <= 1 AND last_seen < NOW() - make_interval(days => %s)
            RETURNING 1
        """, (QUIET_DAYS,), fetch=True) or []
        stats["quiet"] = len(quiet)
        if any(v for k, v in stats.items() if k != "kept"):
            logger.success(f"names: {stats}")
        return stats
