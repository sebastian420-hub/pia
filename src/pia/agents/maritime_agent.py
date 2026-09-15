import hashlib
import os
import sys
from loguru import logger
from datetime import datetime, timezone

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

class MaritimeAgent(BaseAgent):
    """
    The Maritime Sentinel.

    There is no real AIS integration yet. This agent emits a fixed list of
    SIMULATED vessel hits and only runs when SIMULATED_SENSORS=true.
    Simulated records are labelled 'SIMULATED AIS Feed' with confidence 0.1.
    """

    SOURCE_NAME = "SIMULATED AIS Feed"

    def setup(self):
        if os.getenv("SIMULATED_SENSORS", "false").lower() not in ("1", "true", "yes"):
            logger.warning(f"{self.name}: no real AIS feed is implemented; set SIMULATED_SENSORS=true to emit demo data. Exiting.")
            sys.exit(0)
        self.db = DatabaseManager()
        logger.info(f"{self.name} initialized (SIMULATED maritime data).")

    def poll(self):
        """Emits the fixed simulated vessel hits."""
        vessels = [
            {"name": "EVER GIVEN", "mmsi": "353136000", "type": "CARGO", "flag": "Panama", "lat": 29.9, "lon": 32.5},
            {"name": "COSCO SHIPPING", "mmsi": "477353100", "type": "CARGO", "flag": "Hong Kong", "lat": 1.2, "lon": 103.8},
            {"name": "USS ABRAHAM LINCOLN", "mmsi": "368926000", "type": "MILITARY", "flag": "USA", "lat": 25.0, "lon": 55.0}
        ]

        for ship in vessels:
            self.ingest_vessel_hit(ship)

    def ingest_vessel_hit(self, ship):
        """Converts a vessel hit into a telemetry record and a UIR for the Brain."""
        now = datetime.now(timezone.utc)
        
        # 1. Store in Layer 1 (Telemetry)
        self.db.execute_query(
            """
            INSERT INTO vessel_positions (time, mmsi, name, vessel_type, flag, position)
            VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            ON CONFLICT (time, mmsi) DO NOTHING
            """, (now, ship['mmsi'], ship['name'], ship['type'], ship['flag'], ship['lon'], ship['lat'])
        )

        # 2. Convert to Layer 2 (Universal Intelligence Record)
        # This triggers the Analyst Swarm to look for anomalies or links
        headline = f"[SIM] VESSEL HIT: {ship['name']} ({ship['type']}) detected"
        summary = f"SIMULATED demo data. Vessel flying {ship['flag']} flag at lat {ship['lat']}, lon {ship['lon']}. MMSI: {ship['mmsi']}"

        content_hash = hashlib.sha256(f"{ship['mmsi']}_{now.strftime('%Y%m%d%H')}".encode()).hexdigest()

        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_id, source_agent, source_name, content_hash,
                content_headline, content_summary, domain, priority, geo, confidence
            ) VALUES (
                'SIGINT', 'simulated', %s, %s, %s,
                %s, %s, 'MARITIME', 'NORMAL', ST_SetSRID(ST_MakePoint(%s, %s), 4326), 0.1
            ) ON CONFLICT (content_hash) DO NOTHING
            """, (self.name, self.SOURCE_NAME, content_hash, headline, summary, ship['lon'], ship['lat'])
        )
        
        logger.info(f"Maritime Hit Processed: {ship['name']}")

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = MaritimeAgent(name="maritime_sentinel_v1", interval_sec=60)
    agent.run()
