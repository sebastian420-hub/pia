"""
GDELT 2.0 event ingester: every 15 minutes, the latest export file (~1,400 events, already
geocoded and CAMEO-coded). No LLM. Actors are resolved against the local alias table only.

Precision rules (see docs/design/graph_accuracy_implementation_plan.md, part A):
  - the full CAMEO code decides the action and topic ("051" → PRAISE / diplomacy), not the root
  - a country is an actor only when GDELT typed it as the state (GOV, MIL, LEG, SPY, JUD), used a
    government seat, or the story is country-to-country with ≥ 2 sources; an untyped "UNITED
    STATES" alone is a story *about* America and yields a report but no event
  - regions (EUR, AFR …) and places are never actors or targets
  - the event carries no quote: the evidence is the source page's title, outlet and URL, plus the
    CAMEO code; the event location is kept only when it lies in one of the two actors' countries
  - symmetric actions (MEET, AGREE …) dedup on the unordered pair
  - a story is counted once: the same (pair, action, day) from thirty outlets is one event whose
    `outlets` list grows; `is_root` and `weight_class` (verbal / material) are kept so the
    relations job can refuse to draw a line from "somebody said something"
"""
import csv
import hashlib
import io
import json
import os
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests
from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.ingest.article import outlet_from_url
from pia.kg.geo_codes import fips_to_iso2
from pia.kg.normalize import normalize
from pia.kg.ontology import (ACTIONS, CONTINENT_QIDS, GDELT_GENERIC_ACTORS, GDELT_KNOWN_GROUPS,
                             GDELT_REGION_CODES, GOVERNMENT_SEATS, STATE_ACTOR_TYPES, SYMMETRIC_ACTIONS,
                             cameo_action, weight_class)
from pia.kg.resolver import Resolver

LASTUPDATE = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
COL = dict(id=0, day=1, a1name=6, a1cc=7, a1kg=8, a1type=12, a2name=16, a2cc=17, a2kg=18, a2type=22,
           isroot=25, code=26, root=28, quad=29, goldstein=30, mentions=31, sources=32, tone=34,
           geo_name=52, geo_cc=53, lat=56, lon=57, added=59, url=60)

DIRECTED_ACTIONS = {"ATTACK", "ACCUSE", "THREATEN", "SANCTION", "COERCE", "ARREST", "AID", "AGREE", "MEET",
                    "COOPERATE", "APPEAL", "REJECT"} | {a for a in ACTIONS if a not in (
                        "STATEMENT", "PROTEST", "DEPLOY", "DISASTER", "OTHER", "ELECT", "RESIGN", "APPOINT",
                        "MILITARY_POSTURE")}
ACTOR_KINDS = {"COUNTRY", "ORG", "PERSON", "VESSEL"}      # places are locations, never actors
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
TITLE_UA = {"User-Agent": "PIA-gdelt-agent/1.0 (+https://github.com/sebastian420-hub/pia)"}


def page_title(url: str, timeout: float = 5.0) -> str:
    """Best-effort <title> of a source page (first 64 KB). Empty string on any failure."""
    try:
        with requests.get(url, headers=TITLE_UA, timeout=timeout, stream=True) as r:
            if r.status_code != 200:
                return ""
            chunk = r.raw.read(65536, decode_content=True)
        m = TITLE_RE.search(chunk.decode("utf-8", "replace"))
        if not m:
            return ""
        import html as _html
        return _html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()[:300]
    except Exception:
        return ""


def fetch_export(url: str, attempts: int = 3) -> str:
    """Download and unzip one export file. A flaky link gets a few quick retries; 404 raises at once."""
    last = None
    for i in range(attempts):
        try:
            z = requests.get(url, timeout=25)
            z.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
                return zf.read(zf.namelist()[0]).decode("utf-8", "replace")
        except requests.exceptions.HTTPError:
            raise
        except Exception as e:                    # connection reset, SSL EOF, timeout, bad zip
            last = e
            time.sleep(2 * (i + 1))
    raise last  # type: ignore[misc]


class GdeltAgent(BaseAgent):
    MIN_MENTIONS = int(os.getenv("GDELT_MIN_MENTIONS", "3"))
    MIN_MENTIONS_SOLO = int(os.getenv("GDELT_MIN_MENTIONS_SOLO", "10"))
    MIN_ABS_GOLDSTEIN = float(os.getenv("GDELT_MIN_ABS_GOLDSTEIN", "5"))
    MIN_SOURCES_UNTYPED = int(os.getenv("GDELT_MIN_SOURCES_UNTYPED", "2"))
    FETCH_TITLES = os.getenv("GDELT_FETCH_TITLES", "1") == "1"

    def setup(self):
        self.db = DatabaseManager()
        self.resolver = Resolver(self.db)
        self.last_file = None
        self.load_countries()
        logger.info(f"{self.name} ready (min mentions {self.MIN_MENTIONS}, |goldstein| ≥ {self.MIN_ABS_GOLDSTEIN}, "
                    f"{len(self.iso3)} country codes)")

    def load_countries(self):
        rows = self.db.execute_query("""
            SELECT e.entity_id, e.qid, e.metadata->>'iso3' AS iso3, e.metadata->>'iso2' AS iso2,
                   array_agg(a.alias_norm) AS aliases
            FROM entities e LEFT JOIN entity_aliases a USING (entity_id)
            WHERE e.kind = 'COUNTRY' AND e.metadata ? 'iso3'
            GROUP BY 1, 2, 3, 4
        """, fetch=True) or []
        self.iso3 = {r['iso3']: r['qid'] for r in rows}
        self.country_iso2 = {r['qid']: (r['iso2'] or "").upper() for r in rows}
        self.country_aliases = {r['qid']: set(r['aliases'] or []) for r in rows}

    # ── polling ──────────────────────────────────────────────────────────────

    def poll(self):
        r = requests.get(LASTUPDATE, timeout=20)
        r.raise_for_status()
        export_line = next((ln for ln in r.text.splitlines() if ln.endswith(".export.CSV.zip")), None)
        if not export_line:
            return
        url = export_line.split()[-1]
        if url == self.last_file:
            return
        kept = self.ingest_url(url)
        self.last_file = url
        logger.success(f"GDELT {url.rsplit('/', 1)[-1]}: {kept} events kept")

    def ingest_url(self, url: str) -> int:
        return self.ingest(fetch_export(url), url)

    # ── actors ───────────────────────────────────────────────────────────────

    def _actor(self, name: str, cc: str, kg: str, atype: str, other_is_state: bool, sources: int):
        """
        -> (entity | None, is_state, strong). Country-level actors follow part A3; everything else
        goes through the local alias table (never Wikidata) with the country as context.
        `strong` = the row named the thing itself (country name, seat, known group, resolved
        org/person) rather than a typed placeholder ("ORLANDO"/USA/GOV) — only strong actors may
        carry an event on their own (no target).
        """
        name, cc, kg, atype = (name or "").strip(), (cc or "").strip().upper(), (kg or "").strip().upper(), (atype or "").strip().upper()
        if kg in GDELT_KNOWN_GROUPS:
            ent = self.resolver.ensure_qid(GDELT_KNOWN_GROUPS[kg])
            return (ent, True, True) if ent else (None, False, False)
        if cc in GDELT_REGION_CODES:
            return None, False, False
        qid = self.iso3.get(cc)
        norm = normalize(self._title(name)) if name else ""
        if qid:
            is_country_name = norm in self.country_aliases.get(qid, ()) or GOVERNMENT_SEATS.get(norm) == qid
            typed_state = atype in STATE_ACTOR_TYPES
            if typed_state or GOVERNMENT_SEATS.get(norm) == qid:
                return self.resolver.ensure_qid(qid), True, is_country_name
            if is_country_name:
                # untyped "UNITED STATES": only as one side of a country-to-country story with corroboration
                if other_is_state and sources >= self.MIN_SOURCES_UNTYPED:
                    return self.resolver.ensure_qid(qid), True, False
                return None, False, None      # None = "untyped country name": may be retried once the other side is known
        if not name or norm in GDELT_GENERIC_ACTORS:
            return None, False, False          # "CITIZEN", "AIR FORCE", "PRINCE": a role, not a thing
        ent = self.resolver.resolve(self._title(name), role="ACTOR", context={"country_qid": qid}, local_only=True)
        if ent and ent.get('event_entity'):
            ent = ent['event_entity']            # "State Department" → United States
        if not ent or ent['resolution'] != 'RESOLVED' or ent['kind'] not in ACTOR_KINDS or ent['qid'] in CONTINENT_QIDS:
            return None, False, False
        # a wire name must match the thing's own label, not a loose Wikidata alias
        # ("Arizona" is an alias of the University of Arizona; "Missouri" of a battleship)
        if ent['kind'] != 'COUNTRY' and normalize(ent['name']) != norm and ent.get('role') != 'GOVERNMENT':
            return None, False, False
        return ent, ent['kind'] == 'COUNTRY', True

    @staticmethod
    def _title(name: str) -> str:
        return " ".join(w.capitalize() for w in (name or "").lower().split())

    def _country_iso2_of(self, ent) -> str:
        if not ent:
            return ""
        if ent.get('kind') == 'COUNTRY':
            return self.country_iso2.get(ent['qid'], "")
        cq = ent.get('country_qid')
        return self.country_iso2.get(cq, "") if cq else ""

    # ── ingest ───────────────────────────────────────────────────────────────

    def ingest(self, text: str, file_url: str) -> int:
        candidates = []
        for row in csv.reader(io.StringIO(text), delimiter="\t"):
            if len(row) < 61:
                continue
            try:
                mentions = int(row[COL['mentions']] or 0)
                sources = int(row[COL['sources']] or 0)
                goldstein = float(row[COL['goldstein']] or 0)
                lat, lon = float(row[COL['lat']]), float(row[COL['lon']])
            except ValueError:
                continue
            if mentions < self.MIN_MENTIONS and abs(goldstein) < self.MIN_ABS_GOLDSTEIN:
                continue
            coded = cameo_action(row[COL['code']] or row[COL['root']])
            if not coded:
                continue
            action, topic, code_label = coded

            # resolve the typed / seated side first so the untyped side can lean on it
            a1 = (row[COL['a1name']], row[COL['a1cc']], row[COL['a1kg']], row[COL['a1type']])
            a2 = (row[COL['a2name']], row[COL['a2cc']], row[COL['a2kg']], row[COL['a2type']])
            actor, actor_state, actor_strong = self._actor(*a1, other_is_state=False, sources=sources)
            target, target_state, target_strong = self._actor(*a2, other_is_state=actor_state, sources=sources)
            a1_untyped_country, a2_untyped_country = actor_strong is None, target_strong is None
            if actor is None and a1_untyped_country and (target_state or a2_untyped_country):
                actor, actor_state, actor_strong = self._actor(*a1, other_is_state=True, sources=sources)
            if target is None and a2_untyped_country and actor_state:
                target, target_state, target_strong = self._actor(*a2, other_is_state=True, sources=sources)
            actor_strong, target_strong = bool(actor_strong), bool(target_strong)
            if not actor and not target:
                continue
            if not actor:                      # GDELT sometimes only names actor2; keep the pair meaningful
                actor, target, actor_strong = target, None, target_strong
            if target and target['entity_id'] == actor['entity_id']:
                target = None                  # "United States attacks United States": a domestic story, no pair
            if target is None:
                if action in DIRECTED_ACTIONS or not actor_strong:
                    continue                   # an attack with no counterpart, or a typed placeholder alone, is noise
                if mentions < self.MIN_MENTIONS_SOLO:
                    continue

            # the action location is kept only when it lies in one of the two actors' countries
            geo_iso2 = fips_to_iso2(row[COL['geo_cc']])
            in_actor_country = geo_iso2 and geo_iso2 in {self._country_iso2_of(actor), self._country_iso2_of(target)}
            src_url = row[COL['url']].strip()
            when = datetime.strptime(row[COL['day']], "%Y%m%d").replace(tzinfo=timezone.utc)
            candidates.append(dict(row=row, action=action, topic=topic, code=(row[COL['code']] or row[COL['root']]).strip(),
                                   code_label=code_label, actor=actor, target=target, lat=lat, lon=lon,
                                   event_geo=bool(in_actor_country), url=src_url, when=when,
                                   goldstein=goldstein, sources=sources, is_root=(row[COL['isroot']].strip() == "1")))

        # one lightweight report per source URL; titles fetched in parallel, best effort
        urls = sorted({c['url'] for c in candidates if c['url'].startswith("http")})
        titles = self._titles(urls)
        report_uids = {}
        for c in candidates:
            if c['url'].startswith("http") and c['url'] not in report_uids:
                report_uids[c['url']] = self._report(c, titles.get(c['url'], ""))

        kept = 0
        for c in candidates:
            actor, target, action, when = c['actor'], c['target'], c['action'], c['when']
            outlet = outlet_from_url(c['url']) if c['url'].startswith("http") else "gdelt"
            a_id, t_id = actor['entity_id'], target['entity_id'] if target else ''
            pair = tuple(sorted((a_id, t_id))) if (target and action in SYMMETRIC_ACTIONS) else (a_id, t_id)
            # one event per story-day: the outlet is NOT part of the key; copies add to `outlets`
            dedup = hashlib.sha1(f"gdelt|{pair[0]}|{pair[1]}|{action}|{when.date()}".encode()).hexdigest()
            confidence = round(min(0.9, 0.4 + 0.1 * min(c['sources'], 5)), 2)
            self.db.execute_query("""
                INSERT INTO events (event_time, time_precision, action, kind, actor_id, target_id, geo, report_uid, source_id,
                                    origin, quote, confidence, tone, external_id, topic, code, is_root, weight_class, outlets, dedup_key)
                VALUES (%s, 'day', %s, %s, %s, %s,
                        CASE WHEN %s THEN ST_SetSRID(ST_MakePoint(%s, %s), 4326) END,
                        %s, 'gdelt', 'gdelt', NULL, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (dedup_key, event_time) DO UPDATE SET
                    outlets = CASE WHEN events.outlets ? %s THEN events.outlets ELSE events.outlets || %s::jsonb END,
                    confidence = LEAST(0.9, GREATEST(events.confidence, EXCLUDED.confidence) + 0.05),
                    is_root = events.is_root OR EXCLUDED.is_root
            """, (when, action, ACTIONS[action][1], a_id, t_id or None, c['event_geo'], c['lon'], c['lat'],
                  report_uids.get(c['url']), confidence, c['goldstein'], c['row'][COL['id']], c['topic'], c['code'],
                  c['is_root'], weight_class(c['code']), json.dumps([outlet]), dedup,
                  outlet, json.dumps([outlet])))
            for ent in (actor, target):
                if ent:
                    self.db.execute_query("UPDATE entities SET mention_count = mention_count + 1, last_seen = NOW() WHERE entity_id = %s", (ent['entity_id'],))
            kept += 1
        return kept

    def _titles(self, urls):
        if not urls or not self.FETCH_TITLES:
            return {}
        known = self.db.execute_query(
            "SELECT source_url, content_headline FROM intelligence_records WHERE source_url = ANY(%s)", (urls,), fetch=True) or []
        titles = {r['source_url']: r['content_headline'] for r in known}
        todo = [u for u in urls if u not in titles]
        if todo:
            with ThreadPoolExecutor(max_workers=8) as pool:
                for u, t in zip(todo, pool.map(page_title, todo)):
                    titles[u] = t
        return titles

    def _report(self, c, title: str):
        """One lightweight report per source URL (no body, no LLM), so events link to something clickable."""
        url = c['url']
        existing = self.db.execute_query("SELECT uid FROM intelligence_records WHERE source_url = %s", (url,), fetch=True)
        if existing:
            return existing[0]['uid']
        outlet = outlet_from_url(url)
        self.db.execute_query("INSERT INTO sources (source_id, label, kind, trust) VALUES (%s, %s, 'NEWS', 0.5) ON CONFLICT DO NOTHING", (outlet, outlet))
        row = c['row']
        actor_name, target_name = c['actor']['name'], (c['target']['name'] if c['target'] else "")
        fallback = f"{actor_name} — {c['code_label']}" + (f" — {target_name}" if target_name else "")
        headline = title or fallback
        priority = 'HIGH' if c['goldstein'] <= -7 else 'NORMAL'
        domain = 'MILITARY' if c['code'][:2] in ('18', '19', '20') else 'POLITICAL'
        rows = self.db.execute_query("""
            INSERT INTO intelligence_records (source_type, source_id, source_agent, source_name, source_url, published_at,
                                              content_hash, content_headline, content_summary, body_status, domain, priority, confidence,
                                              geo, geo_precision, geo_source, metadata)
            VALUES ('OSINT', %s, %s, %s, %s, %s, %s, %s, %s, 'NONE', %s, %s, 0.5,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326), 'city', 'gdelt-dateline', %s::jsonb)
            ON CONFLICT (content_hash) DO NOTHING RETURNING uid
        """, (outlet, self.name, outlet, url, c['when'], hashlib.sha256(url.encode()).hexdigest(), headline[:300],
              f"GDELT {c['code']} — {c['code_label']}: {fallback}. Dateline: {row[COL['geo_name']] or 'n/a'}.",
              domain, priority, c['lon'], c['lat'],
              '{"skip_analysis": true, "via": "gdelt", "cameo": "%s"}' % c['code']), fetch=True)
        if rows:
            return rows[0]['uid']
        again = self.db.execute_query("SELECT uid FROM intelligence_records WHERE source_url = %s", (url,), fetch=True)
        return again[0]['uid'] if again else None

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    agent = GdeltAgent(name="gdelt_events_v1", interval_sec=900)
    agent.run()
