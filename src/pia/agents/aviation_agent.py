"""
Aviation Sentinel v2 — Real ADS-B via OpenSky Network (anonymous, free, no key needed).

Polls the OpenSky REST API every 60 s.  Only aircraft that meet at least one of the
following criteria create a UIR (Universal Intelligence Record) so the analyst queue
is not flooded with routine commercial traffic:

  * Special squawk: 7700 (emergency), 7600 (comms failure), 7500 (hijack/unlawful)
  * US military ICAO24 prefix: AE…, AF… (Air Force/Army/Navy)
  * NATO military prefixes: 43… (France), 43C… (France mil), 3E… (Germany), etc.

Everything else goes to Layer 1 telemetry only.
"""
import hashlib
import os
from datetime import datetime, timezone

import requests
from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

# ── OpenSky API ───────────────────────────────────────────────────────────────
OPENSKY_URL = "https://opensky-network.org/api/states/all"
# State vector field indices (from the OpenSky docs)
_F_ICAO24   = 0
_F_CALLSIGN = 1
_F_LON      = 5
_F_LAT      = 6
_F_BARO_ALT = 7   # metres
_F_ON_GROUND= 8
_F_VELOCITY = 9   # m/s
_F_HEADING  = 10
_F_SQUAWK   = 14

# ── Interesting squawks ───────────────────────────────────────────────────────
_SQUAWK_PRIORITY: dict[str, str] = {
    "7700": "CRITICAL",   # general emergency
    "7600": "HIGH",       # radio failure
    "7500": "CRITICAL",   # unlawful interference / hijack
}
_SQUAWK_LABEL: dict[str, str] = {
    "7700": "⚠️ EMERGENCY DECLARED",
    "7600": "📡 COMMS FAILURE",
    "7500": "🚨 HIJACK TRANSPONDER",
}

# ── Military ICAO24 prefixes (first 2 hex chars, lower-case) ──────────────────
# US DoD block: AE0000–AFFFFF  (Air Force, Army, Navy, Marines)
# French military: 3A (partial), NATO/Eurocontrol flags vary widely.
# This conservative list captures the well-known US block.
_MILITARY_PREFIXES = frozenset({"ae", "af"})


class AviationAgent(BaseAgent):
    """Real ADS-B sentinel — OpenSky Network anonymous feed."""

    SOURCE_NAME = "OpenSky Network (ADS-B)"

    def setup(self):
        # Optional credentials for a higher rate limit
        user = os.getenv("OPENSKY_USERNAME", "").strip()
        pwd  = os.getenv("OPENSKY_PASSWORD", "").strip()
        self._auth = (user, pwd) if user and pwd else None
        if self._auth:
            logger.info(f"{self.name}: using authenticated OpenSky access (60s interval).")
        else:
            # Anonymous: OpenSky allows ~10 requests/min across the whole IP.
            # We back off to every 5 minutes to stay within limits reliably.
            self.interval_sec = 300
            logger.info(f"{self.name}: anonymous OpenSky access — polling every 5 min to respect rate limits.")
            logger.info(f"{self.name}: register at https://opensky-network.org to unlock 60s polling.")
        self.db = DatabaseManager()

    def poll(self):
        logger.debug(f"{self.name} polling OpenSky Network…")
        try:
            resp = requests.get(
                OPENSKY_URL,
                auth=self._auth,
                timeout=30,
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning(f"{self.name}: OpenSky request failed — {exc}")
            return

        states = resp.json().get("states") or []
        logger.info(f"{self.name}: {len(states):,} aircraft in feed.")

        telemetry_count = 0
        uir_count = 0
        for s in states:
            try:
                inserted_uir = self._process_state(s)
                telemetry_count += 1
                if inserted_uir:
                    uir_count += 1
            except Exception as exc:
                logger.debug(f"state skip: {exc}")

        logger.info(f"{self.name}: {telemetry_count:,} telemetry rows, {uir_count} UIRs created.")

    def _process_state(self, s: list) -> bool:
        """Ingest one ADS-B state vector.  Returns True if a UIR was also created."""
        icao24   = (s[_F_ICAO24]   or "").strip().lower()
        callsign = (s[_F_CALLSIGN] or "").strip()
        lon      = s[_F_LON]
        lat      = s[_F_LAT]
        baro_alt = s[_F_BARO_ALT]
        on_ground= s[_F_ON_GROUND]
        speed_ms = s[_F_VELOCITY]
        heading  = s[_F_HEADING]
        squawk   = (s[_F_SQUAWK]   or "").strip()

        # Skip aircraft with no valid position
        if lat is None or lon is None:
            return False
        # Skip ground traffic that isn't squawking something interesting
        if on_ground and squawk not in _SQUAWK_PRIORITY:
            return False

        alt_ft    = int(baro_alt * 3.28084) if baro_alt else 0
        speed_kts = int(speed_ms * 1.94384) if speed_ms else 0
        now       = datetime.now(timezone.utc)

        # ── Layer 1: raw telemetry (always) ──────────────────────────────────
        self.db.execute_query(
            """
            INSERT INTO flight_tracks
                (time, icao24, callsign, position, altitude_ft, speed_kts, heading, squawk)
            VALUES (%s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s)
            ON CONFLICT (time, icao24) DO NOTHING
            """,
            (now, icao24, callsign or icao24, lon, lat, alt_ft, speed_kts, heading, squawk or None),
        )

        # ── Decide whether this aircraft warrants a UIR ───────────────────────
        is_special_squawk = squawk in _SQUAWK_PRIORITY
        is_military       = len(icao24) >= 2 and icao24[:2] in _MILITARY_PREFIXES

        if not is_special_squawk and not is_military:
            return False   # telemetry only; don't touch the analyst queue

        # ── Layer 2: Universal Intelligence Record ────────────────────────────
        priority = _SQUAWK_PRIORITY.get(squawk, "HIGH" if is_military else "NORMAL")
        ident    = callsign or icao24.upper()

        if is_special_squawk:
            headline = f"{_SQUAWK_LABEL[squawk]}: {ident} squawking {squawk}"
        else:
            headline = f"Military aircraft: {ident} (ICAO {icao24.upper()}) at {alt_ft:,} ft"

        summary = (
            f"ADS-B data from OpenSky Network. Aircraft {ident} (ICAO24: {icao24.upper()}) "
            f"at {alt_ft:,} ft, {speed_kts} kts. "
            f"Position: {lat:.4f}°N, {lon:.4f}°E. Squawk: {squawk or 'none'}."
        )
        # Hash per aircraft per hour — prevents spamming UIRs for the same flight
        content_hash = hashlib.sha256(
            f"adsb:{icao24}:{squawk}:{now.strftime('%Y%m%d%H')}".encode()
        ).hexdigest()

        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_id, source_agent, source_name, content_hash,
                content_headline, content_summary, domain, priority,
                geo, geo_precision, geo_source, confidence
            ) VALUES (
                'SIGINT', 'opensky', %s, %s, %s,
                %s, %s, 'AVIATION', %s,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326), 'exact', 'sensor', 0.85
            ) ON CONFLICT (content_hash) DO NOTHING
            """,
            (self.name, self.SOURCE_NAME, content_hash,
             headline, summary, priority, lon, lat),
        )
        logger.info(f"UIR created: {headline}")
        return True

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    agent = AviationAgent(name="aviation_sentinel_v2", interval_sec=60)
    agent.run()
