"""
The reader: GDELT finds the articles, PIA reads them.

Every few minutes it takes the wire reports (created by the GDELT agent with no body and
skip_analysis) that stand behind the strongest pairs, fetches the article body, and hands the
report to the analysts — the same extraction that reads the RSS feeds. What the analyst finds
becomes verified events (origin llm, with quotes); the wire events stay as hints.

Budget: READER_DAILY_BUDGET articles per day (default 400 ≈ $0.35/day at gpt-4o-mini).
"""
import os
from datetime import datetime, timezone

from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.agents.gdelt_agent import page_title
from pia.ingest.article import fetch_body


class ReaderAgent(BaseAgent):
    DAILY_BUDGET = int(os.getenv("READER_DAILY_BUDGET", "400"))
    MIN_STORY_DAYS = int(os.getenv("READER_MIN_STORY_DAYS", "3"))
    BATCH = int(os.getenv("READER_BATCH", "12"))

    def setup(self):
        self.db = DatabaseManager()
        logger.info(f"{self.name} ready (budget {self.DAILY_BUDGET}/day, pairs with ≥ {self.MIN_STORY_DAYS} story-days)")

    def read_today(self) -> int:
        row = self.db.execute_query("""
            SELECT COUNT(*) AS n FROM intelligence_records
            WHERE source_agent = %s AND body_fetched_at > date_trunc('day', NOW())
        """, (self.name,), fetch=True)
        return int(row[0]["n"]) if row else 0

    def candidates(self, limit: int):
        """Wire reports behind pairs that would become lines, strongest pair first, unread only."""
        return self.db.execute_query("""
            WITH pairs AS (
                SELECT LEAST(actor_id, target_id) AS a, GREATEST(actor_id, target_id) AS b,
                       COUNT(DISTINCT (action, event_time::date)) AS story_days
                FROM events
                WHERE origin = 'gdelt' AND target_id IS NOT NULL
                  AND COALESCE(weight_class, 'material') = 'material'
                  AND event_time > NOW() - INTERVAL '7 days'
                GROUP BY 1, 2
                HAVING COUNT(DISTINCT (action, event_time::date)) >= %s
            ), urls AS (
                SELECT ev.report_uid, MAX(p.story_days) AS strength
                FROM events ev JOIN pairs p ON p.a = LEAST(ev.actor_id, ev.target_id) AND p.b = GREATEST(ev.actor_id, ev.target_id)
                WHERE ev.origin = 'gdelt' AND ev.report_uid IS NOT NULL
                GROUP BY ev.report_uid
            )
            SELECT r.uid, r.source_url, r.source_id, u.strength
            FROM urls u JOIN intelligence_records r ON r.uid = u.report_uid
            WHERE r.body_status = 'NONE' AND r.metadata->>'via' = 'gdelt' AND NOT (r.metadata ? 'read_attempt')
            ORDER BY u.strength DESC, r.published_at DESC
            LIMIT %s
        """, (self.MIN_STORY_DAYS, limit), fetch=True) or []

    def poll(self):
        done = self.read_today()
        room = self.DAILY_BUDGET - done
        if room <= 0:
            return
        rows = self.candidates(min(self.BATCH, room))
        if not rows:
            return
        read = 0
        for r in rows:
            body, status = fetch_body(r["source_url"])
            now = datetime.now(timezone.utc)
            if body:
                title = page_title(r["source_url"], timeout=6) or _title_from(body)
                self.db.execute_query("""
                    UPDATE intelligence_records
                    SET content_raw = %s, body_status = 'OK', body_fetched_at = %s, source_agent = %s,
                        content_headline = CASE WHEN content_headline LIKE '%% — %%' THEN %s ELSE content_headline END,
                        confidence = 0.7,
                        metadata = metadata - 'skip_analysis' || jsonb_build_object('read_attempt', %s, 'read_by', %s)
                    WHERE uid = %s
                """, (body, now, self.name, title, now.isoformat(), self.name, r["uid"]))
                self.db.execute_query("""
                    INSERT INTO analysis_queue (uir_uid, trigger_type, priority, status)
                    SELECT %s, 'READ', 'NORMAL', 'PENDING'
                    WHERE NOT EXISTS (SELECT 1 FROM analysis_queue WHERE uir_uid = %s AND status IN ('PENDING', 'PROCESSING'))
                """, (r["uid"], r["uid"]))
                read += 1
            else:
                self.db.execute_query("""
                    UPDATE intelligence_records
                    SET body_status = %s, body_fetched_at = %s,
                        metadata = metadata || jsonb_build_object('read_attempt', %s, 'read_by', %s)
                    WHERE uid = %s
                """, (status, now, now.isoformat(), self.name, r["uid"]))
        logger.success(f"read {read}/{len(rows)} articles ({done + read}/{self.DAILY_BUDGET} today)")

    def stop(self):
        self.db.close()


def _title_from(body: str) -> str:
    """First sentence of the body as a headline when the wire gave us only 'A — code — B'."""
    first = body.split(". ")[0].strip()
    return (first[:140] + "…") if len(first) > 140 else first


if __name__ == "__main__":
    ReaderAgent(name="gdelt_reader_v1", interval_sec=180).run()
