"""
Relations are computed, never written by the LLM.

  events       → HOSTILE / COOPERATIVE / ROLE / OWNERSHIP between actor and target, weighted by
                 confidence and recency (90-day half-life-ish decay), with first/last seen
  co-mentions  → MENTIONED_WITH (weak) for entities appearing in the same report
  wikidata     → static facts, written by the resolver when items are loaded

Run hourly (enrichment agent) or on demand.
"""
from loguru import logger

from pia.kg.ontology import ACTIONS

ACTION_KIND_SQL = "CASE action " + " ".join(
    f"WHEN '{a}' THEN '{k}'" for a, (_, k, _) in ACTIONS.items() if k) + " ELSE NULL END"


def rebuild(db, days: int = 365):
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # 1. from events
            cur.execute(f"""
                WITH agg AS (
                    SELECT LEAST(actor_id, target_id) AS a_id, GREATEST(actor_id, target_id) AS b_id,
                           {ACTION_KIND_SQL} AS kind,
                           MIN(event_time) AS first_seen, MAX(event_time) AS last_seen,
                           COUNT(*) AS event_count,
                           SUM(confidence * exp(-EXTRACT(EPOCH FROM (NOW() - event_time)) / 86400.0 / 90.0)) AS weight,
                           (array_agg(action ORDER BY event_time DESC))[1] AS latest_action,
                           bool_or(origin <> 'gdelt') AS has_non_gdelt,
                           COUNT(DISTINCT source_id) AS outlets
                    FROM events
                    WHERE actor_id IS NOT NULL AND target_id IS NOT NULL AND actor_id <> target_id
                      AND event_time > NOW() - make_interval(days => %s)
                    GROUP BY 1, 2, 3
                )
                INSERT INTO relations (a_id, b_id, kind, source, label, directed, first_seen, last_seen, event_count, weight, updated_at)
                SELECT a_id, b_id, kind, 'events', lower(latest_action), FALSE, first_seen, last_seen, event_count, weight, NOW()
                FROM agg
                WHERE kind IS NOT NULL
                  -- noise bar: a pair seen only through GDELT needs several wire stories from more than one outlet
                  AND (has_non_gdelt OR event_count >= 3 OR outlets >= 2)
                ON CONFLICT (a_id, b_id, kind, source) DO UPDATE SET
                    label = EXCLUDED.label, first_seen = EXCLUDED.first_seen, last_seen = EXCLUDED.last_seen,
                    event_count = EXCLUDED.event_count, weight = EXCLUDED.weight, updated_at = NOW()
            """, (days,))
            # 2. co-mentions (only between resolved entities, capped so the web stays readable)
            cur.execute("""
                WITH pairs AS (
                    SELECT LEAST(m1.entity_id, m2.entity_id) AS a_id, GREATEST(m1.entity_id, m2.entity_id) AS b_id,
                           COUNT(DISTINCT m1.report_uid) AS n, MIN(m1.created_at) AS first_seen, MAX(m1.created_at) AS last_seen
                    FROM mentions m1
                    JOIN mentions m2 ON m1.report_uid = m2.report_uid AND m1.entity_id < m2.entity_id
                    JOIN entities e1 ON e1.entity_id = m1.entity_id AND e1.resolution = 'RESOLVED' AND e1.kind <> 'PLACE'
                    JOIN entities e2 ON e2.entity_id = m2.entity_id AND e2.resolution = 'RESOLVED' AND e2.kind <> 'PLACE'
                    WHERE m1.created_at > NOW() - INTERVAL '90 days'
                    GROUP BY 1, 2 HAVING COUNT(DISTINCT m1.report_uid) >= 2
                )
                INSERT INTO relations (a_id, b_id, kind, source, label, directed, first_seen, last_seen, event_count, weight, updated_at)
                SELECT a_id, b_id, 'MENTIONED_WITH', 'cooccurrence', 'mentioned together', FALSE, first_seen, last_seen, n, LEAST(1.0, n / 10.0), NOW()
                FROM pairs
                ON CONFLICT (a_id, b_id, kind, source) DO UPDATE SET
                    first_seen = EXCLUDED.first_seen, last_seen = EXCLUDED.last_seen,
                    event_count = EXCLUDED.event_count, weight = EXCLUDED.weight, updated_at = NOW()
            """)
            # 3. prune event/co-mention relations this run did not refresh (fell below the bar or decayed away)
            cur.execute("""
                DELETE FROM relations WHERE source IN ('events','cooccurrence')
                  AND updated_at < (SELECT COALESCE(max(updated_at), NOW()) FROM relations WHERE source IN ('events','cooccurrence')) - INTERVAL '10 seconds'
            """)
        conn.commit()
    logger.success("relations rebuilt")
