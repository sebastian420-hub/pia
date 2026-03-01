import time, uuid, json, random
from loguru import logger
from datetime import datetime

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

class MaritimeAgent(BaseAgent):
    """
    The Maritime Sentinel.
    Polls AIS data and ingests vessel movements into the Agency's spine.
    """

    def setup(self):
        self.db = DatabaseManager()
        # Ensure source authority exists
        self.db.execute_query(
            "INSERT INTO source_authority (source_name, source_type, trust_score, notes) VALUES ('AIS Maritime Feed', 'SIGINT', 0.90, 'Real-time vessel tracking') ON CONFLICT DO NOTHING"
        )
        logger.info(f"{self.name} initialized for global maritime surveillance.")

    def poll(self):
        """Simulates/Polls real-time AIS vessel hits."""
        # In a production environment, we would call an API like Spire, Marinetraffic, or an AISHub feed.
        # For the prototype, we simulate hits in high-priority zones (e.g. Strait of Hormuz, Suez, etc.)
        
        vessels = [
            {"name": "EVER GIVEN", "mmsi": "353136000", "type": "CARGO", "flag": "Panama", "lat": 29.9, "lon": 32.5},
            {"name": "COSCO SHIPPING", "mmsi": "477353100", "type": "CARGO", "flag": "Hong Kong", "lat": 1.2, "lon": 103.8},
            {"name": "USS ABRAHAM LINCOLN", "mmsi": "368926000", "type": "MILITARY", "flag": "USA", "lat": 25.0, "lon": 55.0}
        ]

        for ship in vessels:
            self.ingest_vessel_hit(ship)

    def ingest_vessel_hit(self, ship):
        """Converts a vessel hit into a telemetry record and a UIR for the Brain."""
        now = datetime.now()
        
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
        headline = f"VESSEL HIT: {ship['name']} ({ship['type']}) detected"
        summary = f"Vessel flying {ship['flag']} flag detected at lat {ship['lat']}, lon {ship['lon']}. MMSI: {ship['mmsi']}"
        
        import hashlib
        content_hash = hashlib.sha256(f"{ship['mmsi']}_{now.strftime('%Y%m%d%H')}".encode()).hexdigest()

        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_agent, source_name, content_hash,
                content_headline, content_summary, domain, priority, geo
            ) VALUES (
                'SIGINT', %s, 'AIS Maritime Feed', %s,
                %s, %s, 'MILITARY', 'NORMAL', ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            ) ON CONFLICT (content_hash) DO NOTHING
            """, (self.name, content_hash, headline, summary, ship['lon'], ship['lat'])
        )
        
        logger.info(f"Maritime Hit Processed: {ship['name']}")

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = MaritimeAgent(name="maritime_sentinel_v1", interval_sec=60)
    agent.run()
