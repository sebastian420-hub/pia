"""
Missions: collect broadly, look narrowly.

A mission is a collection plan — area, countries, feeds/sources, watchlist, topics, alert rules,
default view. Broad collection never stops; for each active mission this module computes a
**relevance** score (0–1) for reports, entities and events of the last 30 days, and raises
**alerts** (as HIGH/CRITICAL reports, so the feed, the alert lane and the globe show them) when
the mission's rules fire — once per thing, remembered in mission_memory.

Relevance, highest rule wins:
  1.0  a watchlist entity is involved
  0.8  the thing is inside the mission area
  0.6  an involved entity belongs to one of the mission's countries
  0.4  the topic / domain matches
  0.1  nothing matches (still stored, so "show all" is cheap)
"""
import hashlib
import json
import re
from typing import Dict, List, Optional

from loguru import logger

TOPIC_TO_DOMAIN = {"military": "MILITARY", "security": "MILITARY", "nuclear": "MILITARY", "economy": "FINANCIAL",
                   "trade": "FINANCIAL", "sanctions": "FINANCIAL", "cyber": "CYBER", "technology": "CYBER",
                   "elections": "POLITICAL", "diplomacy": "POLITICAL", "human_rights": "POLITICAL",
                   "migration": "POLITICAL", "detention": "POLITICAL", "territory": "MILITARY",
                   "energy": "INFRASTRUCTURE", "environment": "NATURAL", "health": "NATURAL", "crime": "POLITICAL",
                   "humanitarian": "POLITICAL", "other": None}


def active_missions(db) -> List[Dict]:
    rows = db.execute_query("""
        SELECT mission_id, name, is_active, ST_AsText(area) AS area_wkt, area IS NOT NULL AS has_area, countries, languages,
               feeds, sources, watchlist::text[] AS watchlist, topics, alert_rules, default_view, model
        FROM missions WHERE is_active = TRUE OR cardinality(watchlist) > 0 OR cardinality(countries) > 0 OR area IS NOT NULL
    """, fetch=True) or []
    out = []
    for r in rows:
        d = dict(r)
        d["alert_rules"] = json.loads(d["alert_rules"]) if isinstance(d["alert_rules"], str) else (d["alert_rules"] or {})
        d["watchlist"] = [str(x) for x in (d["watchlist"] or [])]
        out.append(d)
    return out


def is_general(m: Dict) -> bool:
    return not (m["watchlist"] or m["countries"] or m["has_area"] or m["topics"])


# ── relevance ─────────────────────────────────────────────────────────────────

def compute_relevance(db, mission: Dict, days: int = 30) -> Dict[str, int]:
    """Recompute report / entity / event relevance for one mission over the last `days`."""
    if is_general(mission):
        return {"reports": 0, "entities": 0, "events": 0}
    mid = mission["mission_id"]
    watch = mission["watchlist"] or ["00000000-0000-0000-0000-000000000000"]
    countries = mission["countries"] or ["Q0"]
    domains = [d for d in {TOPIC_TO_DOMAIN.get(t) for t in (mission["topics"] or [])} if d] or ["NONE"]
    topics = mission["topics"] or ["none"]
    has_area = bool(mission["has_area"])
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mission_relevance WHERE mission_id = %s", (mid,))
            # events
            cur.execute("""
                INSERT INTO mission_relevance (mission_id, kind, ref_id, score, reasons)
                SELECT %s, 'event', ev.event_id,
                       GREATEST(
                         CASE WHEN ev.actor_id = ANY(%s::uuid[]) OR ev.target_id = ANY(%s::uuid[]) THEN 1.0 ELSE 0 END,
                         CASE WHEN %s AND ev.geo IS NOT NULL AND ST_Intersects(ev.geo, (SELECT area FROM missions WHERE mission_id = %s)) THEN 0.8 ELSE 0 END,
                         CASE WHEN a.country_qid = ANY(%s) OR a.qid = ANY(%s) OR t.country_qid = ANY(%s) OR t.qid = ANY(%s) THEN 0.6 ELSE 0 END,
                         CASE WHEN ev.topic = ANY(%s) THEN 0.4 ELSE 0 END,
                         0.1),
                       ARRAY_REMOVE(ARRAY[
                         CASE WHEN ev.actor_id = ANY(%s::uuid[]) OR ev.target_id = ANY(%s::uuid[]) THEN 'watchlist' END,
                         CASE WHEN %s AND ev.geo IS NOT NULL AND ST_Intersects(ev.geo, (SELECT area FROM missions WHERE mission_id = %s)) THEN 'area' END,
                         CASE WHEN a.country_qid = ANY(%s) OR a.qid = ANY(%s) OR t.country_qid = ANY(%s) OR t.qid = ANY(%s) THEN 'country' END,
                         CASE WHEN ev.topic = ANY(%s) THEN 'topic' END], NULL)
                FROM events ev JOIN entities a ON a.entity_id = ev.actor_id LEFT JOIN entities t ON t.entity_id = ev.target_id
                WHERE ev.event_time > NOW() - make_interval(days => %s)
                ON CONFLICT (mission_id, kind, ref_id) DO UPDATE SET score = EXCLUDED.score, reasons = EXCLUDED.reasons, computed_at = NOW()
            """, (mid, watch, watch, has_area, mid, countries, countries, countries, countries, topics,
                  watch, watch, has_area, mid, countries, countries, countries, countries, topics, days))
            n_events = cur.rowcount
            # reports: from their mentions, their position, their domain
            cur.execute("""
                INSERT INTO mission_relevance (mission_id, kind, ref_id, score, reasons)
                SELECT %s, 'report', u.uid,
                       GREATEST(
                         CASE WHEN EXISTS (SELECT 1 FROM mentions m WHERE m.report_uid = u.uid AND m.entity_id = ANY(%s::uuid[])) THEN 1.0 ELSE 0 END,
                         CASE WHEN %s AND u.geo IS NOT NULL AND ST_Intersects(u.geo, (SELECT area FROM missions WHERE mission_id = %s)) THEN 0.8 ELSE 0 END,
                         CASE WHEN EXISTS (SELECT 1 FROM mentions m JOIN entities e ON e.entity_id = m.entity_id
                                           WHERE m.report_uid = u.uid AND (e.country_qid = ANY(%s) OR e.qid = ANY(%s))) THEN 0.6 ELSE 0 END,
                         CASE WHEN u.domain = ANY(%s) THEN 0.4 ELSE 0 END,
                         0.1),
                       ARRAY_REMOVE(ARRAY[
                         CASE WHEN EXISTS (SELECT 1 FROM mentions m WHERE m.report_uid = u.uid AND m.entity_id = ANY(%s::uuid[])) THEN 'watchlist' END,
                         CASE WHEN %s AND u.geo IS NOT NULL AND ST_Intersects(u.geo, (SELECT area FROM missions WHERE mission_id = %s)) THEN 'area' END,
                         CASE WHEN EXISTS (SELECT 1 FROM mentions m JOIN entities e ON e.entity_id = m.entity_id
                                           WHERE m.report_uid = u.uid AND (e.country_qid = ANY(%s) OR e.qid = ANY(%s))) THEN 'country' END,
                         CASE WHEN u.domain = ANY(%s) THEN 'domain' END], NULL)
                FROM intelligence_records u
                WHERE u.created_at > NOW() - make_interval(days => %s)
                ON CONFLICT (mission_id, kind, ref_id) DO UPDATE SET score = EXCLUDED.score, reasons = EXCLUDED.reasons, computed_at = NOW()
            """, (mid, watch, has_area, mid, countries, countries, domains, watch, has_area, mid, countries, countries, domains, days))
            n_reports = cur.rowcount
            # entities: watchlist = 1; else the best of their events (one pass over the scored events); countries 0.6
            cur.execute("""
                WITH ev_best AS (
                    SELECT x.entity_id, MAX(r.score) AS score
                    FROM mission_relevance r
                    JOIN events ev ON ev.event_id = r.ref_id AND ev.event_time > NOW() - make_interval(days => %s)
                    CROSS JOIN LATERAL (VALUES (ev.actor_id), (ev.target_id)) AS x(entity_id)
                    WHERE r.mission_id = %s AND r.kind = 'event' AND x.entity_id IS NOT NULL
                    GROUP BY x.entity_id
                )
                INSERT INTO mission_relevance (mission_id, kind, ref_id, score, reasons)
                SELECT %s, 'entity', e.entity_id,
                       GREATEST(
                         CASE WHEN e.entity_id = ANY(%s::uuid[]) THEN 1.0 ELSE 0 END,
                         CASE WHEN %s AND e.primary_geo IS NOT NULL AND ST_Intersects(e.primary_geo, (SELECT area FROM missions WHERE mission_id = %s)) THEN 0.8 ELSE 0 END,
                         COALESCE(b.score, 0),
                         CASE WHEN e.country_qid = ANY(%s) OR e.qid = ANY(%s) THEN 0.6 ELSE 0 END,
                         0.1),
                       ARRAY_REMOVE(ARRAY[CASE WHEN e.entity_id = ANY(%s::uuid[]) THEN 'watchlist' END,
                                          CASE WHEN %s AND e.primary_geo IS NOT NULL AND ST_Intersects(e.primary_geo, (SELECT area FROM missions WHERE mission_id = %s)) THEN 'area' END,
                                          CASE WHEN e.country_qid = ANY(%s) OR e.qid = ANY(%s) THEN 'country' END,
                                          CASE WHEN b.score >= 0.4 THEN 'events' END], NULL)
                FROM entities e LEFT JOIN ev_best b ON b.entity_id = e.entity_id
                WHERE e.last_seen > NOW() - make_interval(days => %s) AND e.mention_count > 0
                ON CONFLICT (mission_id, kind, ref_id) DO UPDATE SET score = EXCLUDED.score, reasons = EXCLUDED.reasons, computed_at = NOW()
            """, (days, mid, mid, watch, has_area, mid, countries, countries, watch, has_area, mid, countries, countries, days))
            n_entities = cur.rowcount
        conn.commit()
    return {"reports": n_reports, "entities": n_entities, "events": n_events}


# ── alerts ────────────────────────────────────────────────────────────────────

def raise_alerts(db, mission: Dict) -> int:
    """Alerts become HIGH/CRITICAL reports (source_agent = mission_alerts) so every screen shows them; each fires once."""
    if is_general(mission):
        return 0
    mid, rules, watch = mission["mission_id"], mission["alert_rules"] or {}, mission["watchlist"]
    fired = 0
    if rules.get("watchlist_hostile") and watch:
        rows = db.execute_query("""
            SELECT ev.event_id, ev.event_time, ev.stance, a.name AS actor, t.name AS target, COALESCE(ev.predicate, lower(replace(ev.action, '_', ' '))) AS pred,
                   ev.quote, ev.source_id, ST_Y(ev.geo) AS lat, ST_X(ev.geo) AS lon, ev.report_uid,
                   ev.actor_id::text || '>' || COALESCE(ev.target_id::text, '') || '|' || COALESCE(ev.verb_id::text, ev.action) || '|' || ev.event_time::date AS key
            FROM events ev JOIN entities a ON a.entity_id = ev.actor_id LEFT JOIN entities t ON t.entity_id = ev.target_id
            WHERE ev.origin = 'llm' AND ev.verifier_verdict = 'yes' AND ev.kind = 'HOSTILE'
              AND (ev.actor_id = ANY(%s::uuid[]) OR ev.target_id = ANY(%s::uuid[]))
              AND ev.event_time > NOW() - INTERVAL '7 days'
              AND NOT EXISTS (SELECT 1 FROM mission_memory mm WHERE mm.mission_id = %s
                              AND mm.key = 'hostile:' || ev.actor_id::text || '>' || COALESCE(ev.target_id::text, '') || '|' || COALESCE(ev.verb_id::text, ev.action) || '|' || ev.event_time::date)
            ORDER BY ev.event_time DESC LIMIT 20
        """, (watch, watch, mid), fetch=True) or []
        seen_keys = set()
        for r in rows:                       # one alert per actor › target · verb · day
            if r["key"] in seen_keys:
                continue
            seen_keys.add(r["key"])
            head = f"ALERT · {mission['name']}: {r['actor']} {r['pred']} {r['target'] or ''}".strip()
            _alert_report(db, mission, head, r["quote"] or "", "CRITICAL" if (r["stance"] or 0) <= -3 else "HIGH",
                          r["lat"], r["lon"], r["report_uid"], f"hostile:{r['key']}")
            fired += 1
    if rules.get("watchlist_pair") and len(watch) > 1:
        rows = db.execute_query("""
            SELECT ev.event_id, a.name AS actor, t.name AS target, COALESCE(ev.predicate, lower(replace(ev.action, '_', ' '))) AS pred, ev.quote,
                   ST_Y(ev.geo) AS lat, ST_X(ev.geo) AS lon, ev.report_uid,
                   LEAST(ev.actor_id, ev.target_id)::text || '|' || GREATEST(ev.actor_id, ev.target_id)::text AS pair
            FROM events ev JOIN entities a ON a.entity_id = ev.actor_id JOIN entities t ON t.entity_id = ev.target_id
            WHERE ev.origin = 'llm' AND ev.verifier_verdict = 'yes'
              AND ev.actor_id = ANY(%s::uuid[]) AND ev.target_id = ANY(%s::uuid[]) AND ev.actor_id <> ev.target_id
              AND NOT EXISTS (SELECT 1 FROM mission_memory mm WHERE mm.mission_id = %s
                              AND mm.key = 'pair:' || LEAST(ev.actor_id, ev.target_id)::text || '|' || GREATEST(ev.actor_id, ev.target_id)::text)
            ORDER BY ev.event_time DESC LIMIT 20
        """, (watch, watch, mid), fetch=True) or []
        seen = set()
        for r in rows:
            if r["pair"] in seen:
                continue
            seen.add(r["pair"])
            head = f"ALERT · {mission['name']}: first verified link {r['actor']} ↔ {r['target']} ({r['pred']})"
            _alert_report(db, mission, head, r["quote"] or "", "HIGH", r["lat"], r["lon"], r["report_uid"], f"pair:{r['pair']}")
            fired += 1
    n_new = int(rules.get("new_entity_in_area") or 0)
    if n_new and (mission["has_area"] or mission["countries"]):
        # "new" = first seen after the mission was created; "in theatre" = its own country / the area,
        # never just because it acted on someone there (the US is not new to the Gulf); countries excluded
        rows = db.execute_query("""
            SELECT e.entity_id, e.name, e.kind, COUNT(ev.event_id) AS n
            FROM entities e JOIN events ev ON e.entity_id IN (ev.actor_id, ev.target_id)
            JOIN mission_relevance r ON r.mission_id = %s AND r.kind = 'entity' AND r.ref_id = e.entity_id
            WHERE e.kind <> 'COUNTRY' AND ('country' = ANY(r.reasons) OR 'area' = ANY(r.reasons))
              AND e.first_seen > (SELECT created_at FROM missions WHERE mission_id = %s)
              AND e.first_seen > NOW() - INTERVAL '7 days' AND ev.origin = 'llm' AND ev.verifier_verdict = 'yes'
              AND NOT EXISTS (SELECT 1 FROM mission_memory mm WHERE mm.mission_id = %s AND mm.key = 'entity:' || e.entity_id::text)
            GROUP BY e.entity_id, e.name, e.kind HAVING COUNT(ev.event_id) >= %s LIMIT 20
        """, (mid, mid, mid, n_new), fetch=True) or []
        for r in rows:
            head = f"ALERT · {mission['name']}: new {r['kind'].lower()} in theatre — {r['name']} ({r['n']} verified events)"
            _alert_report(db, mission, head, "", "HIGH", None, None, None, f"entity:{r['entity_id']}")
            fired += 1
    if fired:
        logger.success(f"mission {mission['name']}: {fired} alerts")
    return fired


def _alert_report(db, mission, headline, summary, priority, lat, lon, report_uid, key):
    db.execute_query("INSERT INTO sources (source_id, label, kind, trust) VALUES ('pia', 'PIA missions', 'SYSTEM', 1.0) ON CONFLICT DO NOTHING")
    h = hashlib.sha256(f"alert|{mission['mission_id']}|{key}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_id, source_agent, source_name, content_hash, content_headline,
                                          content_summary, body_status, domain, priority, confidence, mission_id, geo, geo_precision, geo_source, metadata)
        VALUES ('OSINT', 'pia', 'mission_alerts', 'PIA', %s, %s, %s, 'NONE', 'POLITICAL', %s, 0.9, %s,
                CASE WHEN %s IS NOT NULL THEN ST_SetSRID(ST_MakePoint(%s, %s), 4326) END, 'city', 'mission',
                %s::jsonb)
        ON CONFLICT (content_hash) DO NOTHING
    """, (h, headline[:300], summary[:600], priority, mission["mission_id"], lon, lon, lat,
          json.dumps({"skip_analysis": True, "alert": True, "source_report": str(report_uid) if report_uid else None, "key": key})))
    db.execute_query("INSERT INTO mission_memory (mission_id, key, note) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                     (mission["mission_id"], key, headline[:300]))


# ── collection hooks ──────────────────────────────────────────────────────────

def mission_feeds(db) -> List[str]:
    rows = db.execute_query("SELECT feeds FROM missions WHERE cardinality(feeds) > 0", fetch=True) or []
    return sorted({u for r in rows for u in (r["feeds"] or []) if u})


def watch_names(db) -> Dict[str, "re.Pattern"]:
    """mission_id → one regex over the names + aliases of its watchlist, matched at a word start
    ("Iran", "Iranian" — not "Miranda"), for tagging reports at collection time."""
    rows = db.execute_query("""
        SELECT m.mission_id::text AS mid, lower(a.alias) AS alias
        FROM missions m JOIN entity_aliases a ON a.entity_id = ANY(m.watchlist)
        WHERE cardinality(m.watchlist) > 0 AND length(a.alias) >= 4
    """, fetch=True) or []
    names: Dict[str, List[str]] = {}
    for r in rows:
        names.setdefault(r["mid"], []).append(re.escape(r["alias"]))
    return {mid: re.compile(r"\b(?:" + "|".join(sorted(set(v), key=len, reverse=True)) + ")") for mid, v in names.items()}


def tag_report(patterns: Dict[str, "re.Pattern"], text_lower: str) -> Optional[str]:
    """The first mission whose watchlist name appears in the text, else None."""
    for mid, pat in patterns.items():
        if pat.search(text_lower):
            return mid
    return None
