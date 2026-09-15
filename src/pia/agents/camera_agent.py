"""
Camera layer agent.

Every CAMERA_LIST_REFRESH_MIN it asks each provider for its camera list and upserts
the rows into `sensors`. It never downloads pictures; the API's snapshot proxy does
that on demand. Providers that need the US relay are skipped unless RELAY_URL is set.
"""
import json
import os
import random
import socket
from datetime import datetime, timezone

import requests
from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.sensors.http import get, relay_url
from pia.sensors.providers import ALL_PROVIDERS


class CameraAgent(BaseAgent):
    LIST_REFRESH_MIN = int(os.getenv("CAMERA_LIST_REFRESH_MIN", "60"))
    PROBE_SAMPLE_PCT = float(os.getenv("CAMERA_PROBE_SAMPLE_PCT", "2"))

    def setup(self):
        self.db = DatabaseManager()
        enabled = os.getenv("CAMERA_PROVIDERS", "").strip()
        wanted = {p.strip() for p in enabled.split(",") if p.strip()} if enabled else None
        self.providers = [P() for P in ALL_PROVIDERS if (wanted is None or P.provider_id in wanted)]
        self.last_refresh = None
        self.hostname = socket.gethostname()
        logger.info(f"{self.name}: providers = {[p.provider_id for p in self.providers]}; relay = {'yes' if relay_url() else 'no'}")

    def poll(self):
        now = datetime.now(timezone.utc)
        if self.last_refresh is None or (now - self.last_refresh).total_seconds() >= self.LIST_REFRESH_MIN * 60:
            self.refresh_lists()
            self.last_refresh = now
        self.probe_sample()

    def refresh_lists(self):
        for provider in self.providers:
            if provider.requires_relay and not relay_url():
                logger.info(f"{provider.provider_id}: needs the US relay (RELAY_URL unset) — skipped")
                continue
            try:
                cams = provider.list_cameras()
            except Exception as e:
                logger.error(f"{provider.provider_id}: list failed: {e}")
                continue
            if not cams:
                logger.warning(f"{provider.provider_id}: empty list; keeping existing rows")
                continue
            self.upsert(provider, cams)

    def upsert(self, provider, cams):
        rows = [(
            'cameras', provider.provider_id, c.external_id, c.name, c.lon, c.lat, c.city, c.country_code,
            c.media_kind, c.media_url, c.video_url, c.refresh_seconds or provider.default_refresh_seconds,
            provider.attribution, provider.cost_class, provider.requires_relay, json.dumps(c.metadata or {}),
        ) for c in cams]
        self.db.execute_values("""
                    INSERT INTO sensors (layer_id, provider, external_id, name, geo, city, country_code,
                                         media_kind, media_url, video_url, refresh_seconds,
                                         attribution, cost_class, requires_relay, metadata, last_seen)
                    VALUES %s
                    ON CONFLICT (provider, external_id) DO UPDATE SET
                        name = EXCLUDED.name, geo = EXCLUDED.geo, city = EXCLUDED.city,
                        media_kind = EXCLUDED.media_kind, media_url = EXCLUDED.media_url,
                        video_url = EXCLUDED.video_url, refresh_seconds = EXCLUDED.refresh_seconds,
                        attribution = EXCLUDED.attribution, cost_class = EXCLUDED.cost_class,
                        requires_relay = EXCLUDED.requires_relay, metadata = EXCLUDED.metadata,
                        last_seen = NOW(),
                        status = CASE WHEN sensors.status = 'OFFLINE' THEN 'UNKNOWN' ELSE sensors.status END
            """, rows, template="(%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())")
        # Cameras the provider stopped listing go OFFLINE
        self.db.execute_query("""
            UPDATE sensors SET status = 'OFFLINE'
            WHERE provider = %s AND (last_seen IS NULL OR last_seen < NOW() - INTERVAL '5 minutes')
        """, (provider.provider_id,))
        logger.success(f"{provider.provider_id}: {len(rows)} cameras upserted")

    def probe_sample(self):
        """Fetches a small random sample of snapshots per provider to keep status honest."""
        for provider in self.providers:
            if provider.requires_relay and not relay_url():
                continue
            rows = self.db.execute_query(
                "SELECT sensor_id, media_url, media_kind FROM sensors WHERE provider = %s AND status <> 'OFFLINE'",
                (provider.provider_id,), fetch=True) or []
            if not rows:
                continue
            k = max(1, int(len(rows) * self.PROBE_SAMPLE_PCT / 100))
            for row in random.sample(rows, min(k, len(rows))):
                ok = False
                try:
                    if row['media_kind'] == 'SNAPSHOT' and '#camera_id=' not in row['media_url']:
                        r = get(row['media_url'], via_relay=provider.requires_relay, timeout=15, stream=True)
                        ok = r.status_code == 200 and r.headers.get('content-type', '').startswith('image')
                        r.close()
                    else:
                        ok = True  # rotating-URL or stream sources are checked by the proxy on use
                except requests.RequestException:
                    ok = False
                self.db.execute_query(
                    "UPDATE sensors SET status = %s, last_ok = CASE WHEN %s THEN NOW() ELSE last_ok END WHERE sensor_id = %s",
                    ('ONLINE' if ok else 'OFFLINE', ok, row['sensor_id']))

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    agent = CameraAgent(name="camera_layer_v1", interval_sec=600)
    agent.run()
