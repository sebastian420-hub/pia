"""
Relations are computed, never written by the LLM.

  events       → HOSTILE / COOPERATIVE / ROLE / OWNERSHIP between actor and target, weighted by
                 confidence and recency (90-day half-life-ish decay), with first/last seen.
                 Two ledgers: verified (an article said it, origin llm, quote) and wire (GDELT).
                 A relation exists when ≥ 1 verified event, or ≥ 5 wire deeds from ≥ 3 outlets.
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
            # 1. from events. Two ledgers per (pair, kind): what an article said (origin llm, with a
            #    quote) and what the wire guessed (origin gdelt). Weight comes from the verified
            #    ledger; wire deeds add a faint tenth so a strong wire-only pair still surfaces.
            cur.execute(f"""
                WITH ev AS (
                    SELECT LEAST(actor_id, target_id) AS a_id, GREATEST(actor_id, target_id) AS b_id,
                           COALESCE(events.kind, {ACTION_KIND_SQL}) AS kind, COALESCE(topic, 'other') AS topic,
                           event_time, action, confidence, events.source_id, outlets,
                           -- an article-read event counts as verified once the verifier agreed; events
                           -- from before prompt v3 (no stance) keep counting until they are judged
                           -- a structured row (connector, human report) is not verified by a model: it counts
                           -- when its source is trusted enough (a direct/indirect reporter, a dataset), never hearsay
                           ((origin NOT IN ('gdelt', 'connector') AND COALESCE(modality, 'asserted') = 'asserted' AND COALESCE(polarity, TRUE)
                             AND (verifier_verdict = 'yes' OR (verifier_verdict IS NULL AND stance IS NULL)))
                            OR (origin = 'connector' AND COALESCE(s.trust, 0.9) >= 0.5)) AS verified,
                           (origin = 'gdelt' AND COALESCE(weight_class, 'material') = 'material' AND COALESCE(is_root, TRUE)) AS wire_deed,
                           exp(-EXTRACT(EPOCH FROM (NOW() - event_time)) / 86400.0 / 90.0) AS decay
                    FROM events LEFT JOIN sources s ON s.source_id = events.source_id
                    WHERE actor_id IS NOT NULL AND target_id IS NOT NULL AND actor_id <> target_id
                      AND event_time > NOW() - make_interval(days => %s)
                ), per_topic AS (
                    SELECT a_id, b_id, kind, topic,
                           COUNT(*) AS n, COUNT(*) FILTER (WHERE verified) AS n_verified
                    FROM ev WHERE kind IS NOT NULL GROUP BY 1, 2, 3, 4
                ), agg AS (
                    SELECT a_id, b_id, kind,
                           MIN(event_time) AS first_seen, MAX(event_time) AS last_seen,
                           COUNT(*) AS event_count,
                           COUNT(*) FILTER (WHERE verified) AS verified_count,
                           COUNT(*) FILTER (WHERE NOT verified) AS wire_count,
                           COUNT(*) FILTER (WHERE wire_deed) AS wire_deeds,
                           SUM(CASE WHEN verified THEN confidence * decay WHEN wire_deed THEN 0.1 * confidence * decay ELSE 0 END) AS weight,
                           (array_agg(action ORDER BY verified DESC, event_time DESC))[1] AS latest_action,
                           (SELECT COUNT(DISTINCT o) FROM (
                                SELECT source_id AS o FROM ev e2 WHERE e2.a_id = ev.a_id AND e2.b_id = ev.b_id AND e2.kind = ev.kind
                                UNION SELECT jsonb_array_elements_text(outlets) FROM ev e3 WHERE e3.a_id = ev.a_id AND e3.b_id = ev.b_id AND e3.kind = ev.kind) oo
                            WHERE o IS NOT NULL) AS outlets
                    FROM ev WHERE kind IS NOT NULL
                    GROUP BY 1, 2, 3
                ), topics AS (
                    SELECT a_id, b_id, kind,
                           jsonb_object_agg(topic, n) AS topics,
                           COALESCE(jsonb_object_agg(topic, n_verified) FILTER (WHERE n_verified > 0), '{{}}'::jsonb) AS verified_topics,
                           (array_agg(topic ORDER BY n_verified DESC, n DESC))[1] AS top_topic
                    FROM per_topic GROUP BY 1, 2, 3
                )
                INSERT INTO relations (a_id, b_id, kind, source, label, directed, first_seen, last_seen, event_count, weight,
                                       topics, verified_count, wire_count, verified_topics, updated_at)
                SELECT g.a_id, g.b_id, g.kind, 'events', t.top_topic, FALSE, g.first_seen, g.last_seen, g.event_count, g.weight,
                       t.topics, g.verified_count, g.wire_count, t.verified_topics, NOW()
                FROM agg g JOIN topics t USING (a_id, b_id, kind)
                  -- a line needs something an article said, or a strong wire signal of deeds from several outlets
                WHERE g.verified_count >= 1 OR (g.wire_deeds >= 5 AND g.outlets >= 3)
                ON CONFLICT (a_id, b_id, kind, source) DO UPDATE SET
                    label = EXCLUDED.label, first_seen = EXCLUDED.first_seen, last_seen = EXCLUDED.last_seen,
                    event_count = EXCLUDED.event_count, weight = EXCLUDED.weight, topics = EXCLUDED.topics,
                    verified_count = EXCLUDED.verified_count, wire_count = EXCLUDED.wire_count,
                    verified_topics = EXCLUDED.verified_topics, updated_at = NOW()
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
