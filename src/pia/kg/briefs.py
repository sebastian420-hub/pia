"""
Entity briefs: 3–5 sentences of "what is happening", written from verified quotes only.

Regenerated when the set of verified events changes (hash of event ids). Budgeted; the card
shows the brief first, the connections with their words under it.
"""
import hashlib
import os
from typing import Optional

from loguru import logger

PROMPT = """You write a short intelligence brief about ONE entity from the quotes below and nothing else.
Rules: 3–5 sentences, plain English, present tense for this week, past tense for older. Every sentence must
rest on a quote; name the outlet in brackets after the sentence, e.g. (bbc.co.uk). No speculation, no
adjectives of your own, no "reportedly" unless the quote is a claim. If the quotes contradict, say so.
Start with the most consequential fact. Output the brief only."""


def _hash(ids) -> str:
    return hashlib.sha1("|".join(sorted(ids)).encode()).hexdigest()


class BriefWriter:
    def __init__(self, db, client, model: Optional[str] = None):
        self.db = db
        self.client = client
        self.model = model or os.getenv("BRIEF_MODEL") or os.getenv("LLM_MODEL") or "openai/gpt-4o-mini"

    def candidates(self, limit: int):
        """Entities with ≥ 2 verified events in 14 days whose brief is missing or stale, most active first."""
        return self.db.execute_query("""
            WITH act AS (
                SELECT e.entity_id, array_agg(ev.event_id::text ORDER BY ev.event_id) AS ids, COUNT(*) AS n
                FROM events ev JOIN entities e ON e.entity_id IN (ev.actor_id, ev.target_id)
                WHERE ev.origin = 'llm' AND ev.verifier_verdict = 'yes' AND ev.event_time > NOW() - INTERVAL '14 days'
                GROUP BY e.entity_id HAVING COUNT(*) >= 2
            )
            SELECT a.entity_id, a.ids, a.n, b.events_hash
            FROM act a LEFT JOIN entity_briefs b ON b.entity_id = a.entity_id
            ORDER BY (b.events_hash IS NULL) DESC, a.n DESC
            LIMIT %s
        """, (limit,), fetch=True) or []

    def write(self, entity_id, ids) -> Optional[str]:
        h = _hash(ids)
        row = self.db.execute_query("SELECT events_hash FROM entity_briefs WHERE entity_id = %s", (entity_id,), fetch=True)
        if row and row[0]["events_hash"] == h:
            return None
        name = self.db.execute_query("SELECT name, kind, description FROM entities WHERE entity_id = %s", (entity_id,), fetch=True)[0]
        evs = self.db.execute_query("""
            SELECT ev.event_time::date AS d, a.name AS actor, t.name AS target, COALESCE(ev.predicate, ev.action) AS pred,
                   ev.modality, ev.quote, COALESCE(ev.source_id, 'unknown') AS outlet
            FROM events ev JOIN entities a ON a.entity_id = ev.actor_id LEFT JOIN entities t ON t.entity_id = ev.target_id
            WHERE ev.event_id::text = ANY(%s) ORDER BY ev.event_time DESC LIMIT 25
        """, (list(ids),), fetch=True) or []
        lines = "\n".join(f"- {e['d']}: {e['actor']} — {e['pred']} — {e['target'] or ''} [{e['modality'] or 'asserted'}] ({e['outlet']}): \"{(e['quote'] or '')[:300]}\"" for e in evs)
        user = f"ENTITY: {name['name']} ({name['kind']}; {name['description'] or ''})\nTODAY: (this week)\n\nQUOTES:\n{lines}"
        try:
            r = self.client.chat.completions.create(model=self.model, temperature=0.2, max_tokens=260,
                                                    messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": user}])
            text = (r.choices[0].message.content or "").strip()
        except Exception as e:
            logger.warning(f"brief failed for {name['name']}: {e}")
            return None
        if not text:
            return None
        self.db.execute_query("""
            INSERT INTO entity_briefs (entity_id, text, events_hash, model, generated_at) VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (entity_id) DO UPDATE SET text = EXCLUDED.text, events_hash = EXCLUDED.events_hash,
                model = EXCLUDED.model, generated_at = NOW()
        """, (entity_id, text, h, self.model))
        return text

    def run(self, budget: int) -> int:
        n = 0
        for c in self.candidates(budget):
            if c["events_hash"] and c["events_hash"] == _hash(c["ids"]):
                continue
            if self.write(c["entity_id"], c["ids"]):
                n += 1
        if n:
            logger.success(f"briefs: {n} written ({self.model})")
        return n
