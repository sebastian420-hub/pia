"""
Knowledge-web maintenance agent (runs every 5 minutes):
  1. resolves pending Wikidata relation targets for entities people actually mention
  2. refreshes Wikidata items older than 30 days
  3. retries NEEDS_REVIEW entities once (Wikidata may have caught up) after 6 hours
  4. rebuilds relations (hourly)
  5. verifies article-read events that could draw a line (independent model call, budgeted)
  6. keeps the verb catalogue's embeddings filled
"""
import json
import os
import time

from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.kg import relations, wikidata
from pia.kg.resolver import Resolver
from pia.kg.verbs import VerbCatalogue
from pia.kg.verifier import Verifier


class EnrichmentAgent(BaseAgent):
    RELATIONS_EVERY_SEC = int(os.getenv("RELATIONS_REBUILD_SEC", "3600"))
    VERIFIER_DAILY_BUDGET = int(os.getenv("VERIFIER_DAILY_BUDGET", "800"))
    VERIFIER_BATCH = int(os.getenv("VERIFIER_BATCH", "40"))

    def setup(self):
        self.db = DatabaseManager()
        self.resolver = Resolver(self.db)
        self._last_rebuild = 0.0
        self.verifier = None
        self.verbs = None
        if os.getenv("OPENROUTER_API_KEY"):
            from pia.core.nlp import NLPManager
            nlp = NLPManager()
            self.verifier = Verifier(self.db, nlp.client)
            self.verbs = VerbCatalogue(self.db, embed=nlp.generate_embedding)
        logger.info(f"{self.name} ready (verifier: {'on' if self.verifier else 'off'})")

    def verify_pending(self):
        if not self.verifier:
            return
        done_today = self.db.execute_query(
            "SELECT COUNT(*) AS n FROM events WHERE verified_at > date_trunc('day', NOW())", fetch=True)[0]["n"]
        room = self.VERIFIER_DAILY_BUDGET - int(done_today)
        if room > 0:
            self.verifier.run(min(self.VERIFIER_BATCH, room))

    def embed_verbs(self):
        if self.verbs:
            self.verbs.embed_missing(limit=50)

    def poll(self):
        # each step independently: a Wikidata hiccup must not stop the relations rebuild
        for step in (self.fill_pending_relations, self.refresh_stale, self.verify_pending, self.embed_verbs):
            try:
                step()
            except Exception as e:
                logger.warning(f"{step.__name__}: {e}")
        if time.time() - self._last_rebuild > self.RELATIONS_EVERY_SEC:
            relations.rebuild(self.db)
            self._last_rebuild = time.time()

    def fill_pending_relations(self, limit: int = 40):
        rows = self.db.execute_query("""
            SELECT entity_id, qid, metadata->'pending_relations' AS pend
            FROM entities WHERE metadata ? 'pending_relations' AND mention_count > 0
            ORDER BY mention_count DESC LIMIT %s
        """, (limit,), fetch=True) or []
        targets = sorted({q for r in rows for q in (r['pend'] or [])})[:200]
        if not targets:
            return
        existing = {r['qid'] for r in self.db.execute_query("SELECT qid FROM entities WHERE qid = ANY(%s)", (targets,), fetch=True) or []}
        missing = [q for q in targets if q not in existing]
        if missing:
            try:
                for p in wikidata.get_entities(missing[:100]).values():
                    self.resolver.upsert_wikidata(p)
            except Exception as e:
                logger.warning(f"pending targets fetch: {e}")
                return
        for r in rows:
            fetched = wikidata.get_entities([r['qid']]) if r['qid'] else {}
            if r['qid'] in fetched:
                self.resolver._store_static_relations(r['entity_id'], fetched[r['qid']].get('relations', []))
            self.db.execute_query("UPDATE entities SET metadata = metadata - 'pending_relations' WHERE entity_id = %s", (r['entity_id'],))
        logger.info(f"linked static relations for {len(rows)} entities")

    def refresh_stale(self, limit: int = 20):
        rows = self.db.execute_query("""
            SELECT qid FROM entities WHERE qid IS NOT NULL AND mention_count > 0
              AND wikidata_synced_at < NOW() - INTERVAL '30 days' ORDER BY mention_count DESC LIMIT %s
        """, (limit,), fetch=True) or []
        if rows:
            try:
                for p in wikidata.get_entities([r['qid'] for r in rows]).values():
                    self.resolver.upsert_wikidata(p)
            except Exception as e:
                logger.warning(f"refresh: {e}")
        # second chance: lookups that failed (rate limit / outage) soon; other review items after 6 hours
        retry = self.db.execute_query("""
            SELECT entity_id, name, kind FROM entities
            WHERE resolution = 'NEEDS_REVIEW' AND (metadata->>'retried') IS NULL
              AND ((metadata->>'note' = 'lookup failed' AND created_at < NOW() - INTERVAL '2 minutes')
                   OR created_at < NOW() - INTERVAL '6 hours')
            ORDER BY mention_count DESC LIMIT 10
        """, fetch=True) or []
        for r in retry:
            ent = self.resolver.resolve(r['name'], kind_hint=r['kind'])
            self.db.execute_query("UPDATE entities SET metadata = COALESCE(metadata,'{}'::jsonb) || '{\"retried\": true}' WHERE entity_id = %s", (r['entity_id'],))
            if ent and ent['resolution'] == 'RESOLVED' and ent['entity_id'] != r['entity_id']:
                self.merge(r['entity_id'], ent['entity_id'])

    def merge(self, loser_id, keeper_id):
        """Re-points mentions/events from a local entity to a resolved one, then removes it."""
        self.db.execute_query("UPDATE mentions SET entity_id = %s WHERE entity_id = %s", (keeper_id, loser_id))
        for col in ("actor_id", "target_id", "location_id"):
            self.db.execute_query(f"UPDATE events SET {col} = %s WHERE {col} = %s", (keeper_id, loser_id))
        self.db.execute_query("""
            UPDATE entities k SET mention_count = k.mention_count + l.mention_count
            FROM entities l WHERE k.entity_id = %s AND l.entity_id = %s
        """, (keeper_id, loser_id))
        self.db.execute_query("DELETE FROM entities WHERE entity_id = %s", (loser_id,))
        self.db.execute_query("INSERT INTO ai_feedback (entity_id, feedback_type, human_correction) VALUES (%s, 'MERGED', %s)",
                              (keeper_id, json.dumps({"from": str(loser_id), "by": "enrichment_agent"})))
        logger.info(f"merged {loser_id} → {keeper_id}")

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    agent = EnrichmentAgent(name="kg_maintenance_v2", interval_sec=300)
    agent.run()
