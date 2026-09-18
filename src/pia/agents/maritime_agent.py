"""
Maritime Sentinel v2 — Real AIS via AISHub free API.

AISHub (https://www.aishub.net) provides live AIS vessel positions.
Registration is free, no credit card required.
Set the environment variable AISHUB_USERNAME to your account username.

If AISHUB_USERNAME is not set, the agent logs a warning and skips the poll
(no simulated data, no noise).  All vessel positions go to Layer 1 telemetry.
Only military vessels and large tankers create UIRs to avoid flooding the
analyst queue with routine commercial shipping.

AIS vessel type codes used for filtering:
  35        → Military ops
  80-89     → Tankers (crude, chemical, LNG, LPG, etc.)
"""
import hashlib
import os
from datetime import datetime, timezone

import requests
from loguru import logger

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

# ── AISHub API ────────────────────────────────────────────────────────────────
AISHUB_URL = "https://data.aishub.net/ws.php"

# AIS vessel type codes (ITU-R M.1371)
_MILITARY_TYPES = frozenset({35})
_TANKER_TYPES   = frozenset({80, 81, 82, 83, 84, 85, 86, 87, 88, 89})
_HIGH_INTEREST  = _MILITARY_TYPES | _TANKER_TYPES

# AISHub response field names
_F_MMSI    = "MMSI"
_F_NAME    = "NAME"
_F_LAT     = "LATITUDE"
_F_LON     = "LONGITUDE"
_F_TYPE    = "TYPE"
_F_SPEED   = "SPEED"
_F_HEADING = "HEADING"
_F_COUNTRY = "COUNTRY"


class MaritimeAgent(BaseAgent):
    """Real AIS sentinel — AISHub free API."""

    SOURCE_NAME = "AISHub (Live AIS)"

    def setup(self):
        self._username = os.getenv("AISHUB_USERNAME", "").strip()
        if not self._username:
            logger.warning(
                f"{self.name}: AISHUB_USERNAME is not set. "
                "Register free at https://www.aishub.net/join and add "
                "AISHUB_USERNAME=<your_username> to pia/.env. "
                "The agent will skip polls until the variable is configured."
            )
        self.db = DatabaseManager()
        logger.info(f"{self.name} initialized — AISHub real AIS feed.")

    def poll(self):
        if not self._username:
            logger.debug(f"{self.name}: skipping poll — AISHUB_USERNAME not configured.")
            return

        logger.debug(f"{self.name} polling AISHub…")
        try:
            resp = requests.get(
                AISHUB_URL,
                params={
                    "username": self._username,
                    "format":   "1",
                    "output":   "json",
                    "compress": "0",
                },
                timeout=30,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning(f"{self.name}: AISHub request failed — {exc}")
            return

        data = resp.json()
        # AISHub wraps the response: [[header_dict], [vessel, vessel, ...]]
        if not isinstance(data, list) or len(data) < 2:
            logger.warning(f"{self.name}: unexpected AISHub response: {str(data)[:120]}")
            return

        header = data[0] if isinstance(data[0], dict) else {}
        vessels = data[1] if isinstance(data[1], list) else []
        logger.info(
            f"{self.name}: {len(vessels):,} vessels in feed "
            f"(AISHub msg: {header.get('ERROR', 'ok')})."
        )

        telemetry_count = 0
        uir_count = 0
        for v in vessels:
            try:
                inserted_uir = self._process_vessel(v)
                telemetry_count += 1
                if inserted_uir:
                    uir_count += 1
            except Exception as exc:
                logger.debug(f"vessel skip: {exc}")

        logger.info(f"{self.name}: {telemetry_count:,} telemetry rows, {uir_count} UIRs created.")

    def _process_vessel(self, v: dict) -> bool:
        """Ingest one AIS position report.  Returns True if a UIR was also created."""
        mmsi         = str(v.get(_F_MMSI, "")).strip()
        name         = (v.get(_F_NAME) or "").strip()
        lat          = v.get(_F_LAT)
        lon          = v.get(_F_LON)
        vessel_type  = int(v.get(_F_TYPE) or 0)
        speed_kts    = float(v.get(_F_SPEED) or 0)
        heading      = v.get(_F_HEADING)
        flag         = (v.get(_F_COUNTRY) or "").strip()

        if not mmsi or lat is None or lon is None:
            return False

        now = datetime.now(timezone.utc)
        display_name = name or mmsi

        # ── Layer 1: raw telemetry (always) ──────────────────────────────────
        self.db.execute_query(
            """
            INSERT INTO vessel_positions
                (time, mmsi, name, vessel_type, flag, position, speed_kts, heading)
            VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)
            ON CONFLICT (time, mmsi) DO NOTHING
            """,
            (now, mmsi, display_name, str(vessel_type), flag, lon, lat, speed_kts, heading),
        )

        # ── Decide whether this vessel warrants a UIR ─────────────────────────
        is_military = vessel_type in _MILITARY_TYPES
        is_tanker   = vessel_type in _TANKER_TYPES

        if not is_military and not is_tanker:
            return False   # routine vessel — telemetry only

        # ── Layer 2: Universal Intelligence Record ────────────────────────────
        kind     = "MILITARY VESSEL" if is_military else "TANKER"
        priority = "HIGH" if is_military else "NORMAL"

        headline = (
            f"AIS: {kind} {display_name} (MMSI {mmsi}) "
            f"at {lat:.3f}°N, {lon:.3f}°E"
        )
        summary = (
            f"Live AIS position from AISHub. {kind}: {display_name} (MMSI {mmsi}), "
            f"flag: {flag or 'unknown'}, AIS type code: {vessel_type}, "
            f"speed: {speed_kts:.1f} kts. "
            f"Position: {lat:.4f}°N, {lon:.4f}°E."
        )
        # One UIR per vessel per hour
        content_hash = hashlib.sha256(
            f"ais:{mmsi}:{now.strftime('%Y%m%d%H')}".encode()
        ).hexdigest()

        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_id, source_agent, source_name, content_hash,
                content_headline, content_summary, domain, priority,
                geo, geo_precision, geo_source, confidence
            ) VALUES (
                'SIGINT', 'aishub', %s, %s, %s,
                %s, %s, 'MARITIME', %s,
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
    agent = MaritimeAgent(name="maritime_sentinel_v2", interval_sec=120)
    agent.run()
