"""
GDELT 2.0 event ingester: every 15 minutes, the latest export file (~1,400 events, already
geocoded and CAMEO-coded). No LLM. Actors are resolved against the local alias table only.

Kept: events with NumMentions ≥ GDELT_MIN_MENTIONS or |Goldstein| ≥ GDELT_MIN_ABS_GOLDSTEIN,
with a geocoded action location and at least one resolvable actor.
"""
import csv
import hashlib
import io
import os
import zipfile
from datetime import datetime, timezone

import requests
from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.ingest.article import outlet_from_url
from pia.kg.ontology import ACTIONS, CAMEO_ROOT_TO_ACTION
from pia.kg.resolver import Resolver

LASTUPDATE = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
COL = dict(id=0, day=1, a1name=6, a1cc=7, a2name=16, a2cc=17, root=28, goldstein=30, mentions=31,
           sources=32, tone=34, geo_name=52, geo_cc=53, lat=56, lon=57, added=59, url=60)


DIRECTED_ACTIONS = {"ATTACK", "ACCUSE", "THREATEN", "SANCTION", "COERCE", "ARREST", "AID", "AGREE", "MEET",
                    "COOPERATE", "APPEAL", "REJECT"}


class GdeltAgent(BaseAgent):
    MIN_MENTIONS = int(os.getenv("GDELT_MIN_MENTIONS", "3"))
    MIN_MENTIONS_SOLO = int(os.getenv("GDELT_MIN_MENTIONS_SOLO", "10"))
    MIN_ABS_GOLDSTEIN = float(os.getenv("GDELT_MIN_ABS_GOLDSTEIN", "5"))

    def setup(self):
        self.db = DatabaseManager()
        self.resolver = Resolver(self.db)
        self.last_file = None
        self.iso3 = {r['iso3']: r['qid'] for r in (self.db.execute_query(
            "SELECT metadata->>'iso3' AS iso3, qid FROM entities WHERE kind = 'COUNTRY' AND metadata ? 'iso3'", fetch=True) or [])}
        logger.info(f"{self.name} ready (min mentions {self.MIN_MENTIONS}, |goldstein| ≥ {self.MIN_ABS_GOLDSTEIN})")

    def poll(self):
        r = requests.get(LASTUPDATE, timeout=20)
        r.raise_for_status()
        export_line = next((ln for ln in r.text.splitlines() if ln.endswith(".export.CSV.zip")), None)
        if not export_line:
            return
        url = export_line.split()[-1]
        if url == self.last_file:
            return
        z = requests.get(url, timeout=60)
        z.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(z.content)) as zf:
            name = zf.namelist()[0]
            text = zf.read(name).decode("utf-8", "replace")
        kept = self.ingest(text, url)
        self.last_file = url
        logger.success(f"GDELT {name}: {kept} events kept")

    @staticmethod
    def _title(name: str) -> str:
        return " ".join(w.capitalize() for w in (name or "").lower().split())

    def _actor(self, name: str, cc: str):
        if not name:
            return None
        ctx = {"country_qid": self.iso3.get((cc or "").upper())}
        ent = self.resolver.resolve(self._title(name), role="ACTOR", context=ctx, local_only=True)
        if ent and ent['resolution'] == 'RESOLVED':
            return ent
        return None

    def ingest(self, text: str, file_url: str) -> int:
        kept = 0
        seen_urls = {}
        for row in csv.reader(io.StringIO(text), delimiter="\t"):
            if len(row) < 61:
                continue
            try:
                mentions = int(row[COL['mentions']] or 0)
                goldstein = float(row[COL['goldstein']] or 0)
                lat, lon = float(row[COL['lat']]), float(row[COL['lon']])
            except ValueError:
                continue
            if mentions < self.MIN_MENTIONS and abs(goldstein) < self.MIN_ABS_GOLDSTEIN:
                continue
            action = CAMEO_ROOT_TO_ACTION.get(row[COL['root']].zfill(2))
            if not action:
                continue
            actor = self._actor(row[COL['a1name']], row[COL['a1cc']])
            target = self._actor(row[COL['a2name']], row[COL['a2cc']])
            if not actor and not target:
                continue
            if not actor:                      # GDELT sometimes only names actor2; keep the pair meaningful
                actor, target = target, None
            if target and target['entity_id'] == actor['entity_id']:
                target = None                  # "United States attacks United States": a domestic story, no pair
            if target is None:
                if action in DIRECTED_ACTIONS:
                    continue                   # an attack/accusation with no known counterpart is noise here
                if mentions < self.MIN_MENTIONS_SOLO:
                    continue
            src_url = row[COL['url']].strip()
            outlet = outlet_from_url(src_url) if src_url.startswith("http") else "gdelt"
            when = datetime.strptime(row[COL['day']], "%Y%m%d").replace(tzinfo=timezone.utc)

            report_uid = seen_urls.get(src_url)
            if report_uid is None and src_url.startswith("http"):
                report_uid = self._report(src_url, outlet, row, lat, lon, goldstein, when)
                seen_urls[src_url] = report_uid

            dedup = hashlib.sha1(f"gdelt|{actor['entity_id']}|{target['entity_id'] if target else ''}|{action}|{when.date()}|{outlet}".encode()).hexdigest()
            self.db.execute_query("""
                INSERT INTO events (event_time, time_precision, action, actor_id, target_id, geo, report_uid, source_id,
                                    origin, quote, confidence, tone, external_id, dedup_key)
                VALUES (%s, 'day', %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, 'gdelt', 'gdelt', %s, %s, %s, %s, %s)
                ON CONFLICT (dedup_key, event_time) DO NOTHING
            """, (when, action, actor['entity_id'], target['entity_id'] if target else None, lon, lat, report_uid,
                  f"{row[COL['a1name']].title()} {action.lower()} {row[COL['a2name']].title()} — {row[COL['geo_name']]}".strip(),
                  min(0.9, 0.45 + 0.05 * min(mentions, 9)), goldstein, row[COL['id']], dedup))
            for ent in (actor, target):
                if ent:
                    self.db.execute_query("UPDATE entities SET mention_count = mention_count + 1, last_seen = NOW() WHERE entity_id = %s", (ent['entity_id'],))
            kept += 1
        return kept

    def _report(self, url, outlet, row, lat, lon, goldstein, when):
        """One lightweight report per source URL (no body, no LLM), so events link to something clickable."""
        existing = self.db.execute_query("SELECT uid FROM intelligence_records WHERE source_url = %s", (url,), fetch=True)
        if existing:
            return existing[0]['uid']
        self.db.execute_query("INSERT INTO sources (source_id, label, kind, trust) VALUES (%s, %s, 'NEWS', 0.5) ON CONFLICT DO NOTHING", (outlet, outlet))
        headline = f"{self._title(row[COL['a1name']]) or 'Unknown actor'} — {ACTIONS and CAMEO_ROOT_TO_ACTION.get(row[COL['root']].zfill(2), 'event').lower()} — {row[COL['geo_name']] or ''}".strip(" —")
        priority = 'HIGH' if goldstein <= -7 else 'NORMAL'
        domain = 'MILITARY' if row[COL['root']].zfill(2) in ('18', '19', '20') else 'POLITICAL'
        rows = self.db.execute_query("""
            INSERT INTO intelligence_records (source_type, source_id, source_agent, source_name, source_url, published_at,
                                              content_hash, content_headline, body_status, domain, priority, confidence,
                                              geo, geo_precision, geo_source, metadata)
            VALUES ('OSINT', %s, %s, %s, %s, %s, %s, %s, 'NONE', %s, %s, 0.5,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326), 'city', 'gdelt', '{"skip_analysis": true, "via": "gdelt"}'::jsonb)
            ON CONFLICT (content_hash) DO NOTHING RETURNING uid
        """, (outlet, self.name, outlet, url, when, hashlib.sha256(url.encode()).hexdigest(), headline[:300], domain, priority, lon, lat), fetch=True)
        if rows:
            return rows[0]['uid']
        again = self.db.execute_query("SELECT uid FROM intelligence_records WHERE source_url = %s", (url,), fetch=True)
        return again[0]['uid'] if again else None

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    agent = GdeltAgent(name="gdelt_events_v1", interval_sec=900)
    agent.run()
