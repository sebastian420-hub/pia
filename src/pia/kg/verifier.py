"""
The verifier: nothing draws a line unchecked.

For an article-read event that would feed a line, a second, independent model call gets the
quote, the surrounding paragraph and the structured claim, and answers whether the text really
states that ACTOR did PREDICATE to TARGET in that direction, with what stance and modality.
Disagreement means the event stays on the card as "unverified" and draws no line.
"""
import json
import os
from typing import Dict, Optional

from loguru import logger

from pia.core.nlp import parse_llm_json

PROMPT = """You check one claim extracted from a news article. Answer ONLY a JSON object:
{"verdict": "yes|partly|no", "stance": -3..3, "modality": "asserted|intended|claimed|hypothetical|denied", "note": "≤ 20 words"}

"yes"    = the text states that ACTOR did PREDICATE to TARGET, in this direction, as described.
"partly" = the act is there but the direction, the target, the stance or whether it actually happened is different.
"no"     = the text does not say this (another actor did it, it is about a third party, or it is invented).
STANCE is the effect on the TARGET: -3 attack, -2 sanction/boycott/arrest/threat of force, -1 accuse/condemn/reject,
0 neutral, +1 praise/support/meet, +2 agreement/aid, +3 alliance/rescue.
MODALITY: asserted = happened; intended = announced/planned/threatened; claimed = a third party says so;
hypothetical = if/could; denied = the actor denies it."""


def _window(body: Optional[str], quote: str, radius: int = 400) -> str:
    """The quote with ±radius characters of the article around it (or just the quote)."""
    if not body or not quote:
        return quote or ""
    i = body.find(quote[:60])
    if i < 0:
        return quote
    return body[max(0, i - radius): i + len(quote) + radius]


class Verifier:
    def __init__(self, db, client, model: Optional[str] = None):
        self.db = db
        self.client = client
        self.model = model or os.getenv("VERIFIER_MODEL") or os.getenv("LLM_MODEL") or "openai/gpt-4o-mini"

    def pending(self, limit: int):
        """Asserted article-read events, not yet judged, whose pair could become a line — strongest pairs first."""
        return self.db.execute_query("""
            WITH pairs AS (
                SELECT LEAST(actor_id, target_id) AS a, GREATEST(actor_id, target_id) AS b, COUNT(*) AS n
                FROM events WHERE origin = 'llm' AND target_id IS NOT NULL AND actor_id <> target_id
                  AND COALESCE(modality, 'asserted') = 'asserted' AND COALESCE(polarity, TRUE)
                  AND event_time > NOW() - INTERVAL '90 days'
                GROUP BY 1, 2
            )
            SELECT ev.event_id, ev.event_time, ev.quote, ev.predicate, ev.action, ev.stance, ev.modality,
                   a.name AS actor, t.name AS target, r.content_raw AS body, p.n AS pair_n
            FROM events ev
            JOIN entities a ON a.entity_id = ev.actor_id
            JOIN entities t ON t.entity_id = ev.target_id
            JOIN pairs p ON p.a = LEAST(ev.actor_id, ev.target_id) AND p.b = GREATEST(ev.actor_id, ev.target_id)
            LEFT JOIN intelligence_records r ON r.uid = ev.report_uid
            WHERE ev.origin = 'llm' AND ev.verifier_verdict IS NULL
              AND COALESCE(ev.modality, 'asserted') = 'asserted' AND COALESCE(ev.polarity, TRUE)
            ORDER BY p.n DESC, ev.event_time DESC
            LIMIT %s
        """, (limit,), fetch=True) or []

    def judge(self, row: Dict) -> Optional[Dict]:
        predicate = row["predicate"] or (row["action"] or "").lower().replace("_", " ")
        claim = f"ACTOR: {row['actor']}\nPREDICATE: {predicate}\nTARGET: {row['target']}\nEXTRACTED STANCE: {row['stance']}\n"
        text = _window(row["body"], row["quote"] or "")
        try:
            r = self.client.chat.completions.create(
                model=self.model, temperature=0, max_tokens=120,
                messages=[{"role": "system", "content": PROMPT},
                          {"role": "user", "content": f"{claim}\nQUOTE: {row['quote']}\n\nTEXT:\n{text[:3000]}"}])
            data = parse_llm_json(r.choices[0].message.content)
        except Exception as e:
            logger.warning(f"verifier call failed: {e}")
            return None
        verdict = str(data.get("verdict") or "").lower()
        if verdict not in ("yes", "partly", "no"):
            return None
        try:
            stance = max(-3, min(3, int(round(float(data.get("stance"))))))
        except (TypeError, ValueError):
            stance = None
        return {"verdict": verdict, "stance": stance, "note": str(data.get("note") or "")[:200]}

    def run(self, budget: int) -> int:
        rows = self.pending(budget)
        done = 0
        for row in rows:
            out = self.judge(row)
            if not out:
                continue
            self.db.execute_query("""
                UPDATE events SET verifier_verdict = %s, verifier_stance = %s, verified_at = NOW(),
                       verifier_note = %s
                WHERE event_id = %s AND event_time = %s
            """, (out["verdict"], out["stance"], out["note"], row["event_id"], row["event_time"]))
            done += 1
        if done:
            logger.success(f"verifier: {done} events judged ({self.model})")
        return done
