import hashlib
import os
import sys
from loguru import logger
from datetime import datetime, timezone

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

class AviationAgent(BaseAgent):
    """
    The Aviation Sentinel.

    There is no real ADS-B integration yet. This agent emits a fixed list of
    SIMULATED aircraft hits and only runs when SIMULATED_SENSORS=true.
    Simulated records are labelled 'SIMULATED ADS-B Feed' with confidence 0.1.
    """

    SOURCE_NAME = "SIMULATED ADS-B Feed"

    def setup(self):
        if os.getenv("SIMULATED_SENSORS", "false").lower() not in ("1", "true", "yes"):
            logger.warning(f"{self.name}: no real ADS-B feed is implemented; set SIMULATED_SENSORS=true to emit demo data. Exiting.")
            sys.exit(0)
        self.db = DatabaseManager()
        logger.info(f"{self.name} initialized (SIMULATED aviation data).")

    def poll(self):
        """Emits the fixed simulated flight hits."""
        flights = [
            {"callsign": "AF1", "icao24": "adf032", "reg": "28000", "alt": 35000, "lat": 38.8, "lon": -77.0, "squawk": "None"},
            {"callsign": "TITAN25", "icao24": "ae01ce", "reg": "62-4128", "alt": 28000, "lat": 52.5, "lon": 13.4, "squawk": "None"}, # RC-135V Rivet Joint
            {"callsign": "MAYDAY1", "icao24": "abc123", "reg": "N12345", "alt": 5000, "lat": 34.0, "lon": -118.2, "squawk": "7700"} # Emergency squawk
        ]

        for flight in flights:
            self.ingest_flight_hit(flight)

    def ingest_flight_hit(self, flight):
        """Converts a flight hit into a telemetry record and a UIR for the Brain."""
        now = datetime.now(timezone.utc)
        
        # 1. Store in Layer 1 (Telemetry - TimescaleDB)
        self.db.execute_query(
            """
            INSERT INTO flight_tracks (time, icao24, callsign, registration, position, altitude_ft, squawk)
            VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)
            ON CONFLICT (time, icao24) DO NOTHING
            """, (now, flight['icao24'], flight['callsign'], flight['reg'], flight['lon'], flight['lat'], flight['alt'], flight['squawk'])
        )

        # 2. Convert to Layer 2 (Universal Intelligence Record)
        # We auto-escalate priority if an emergency squawk is detected
        priority = 'NORMAL'
        headline = f"[SIM] AIRCRAFT HIT: {flight['callsign']} ({flight['reg']}) detected"

        if flight['squawk'] == '7700':
            priority = 'CRITICAL'
            headline = f"[SIM] ⚠️ EMERGENCY: Flight {flight['callsign']} squawking 7700"
        elif flight['callsign'] == 'AF1':
            priority = 'HIGH'
            headline = f"[SIM] 🎯 TARGET DETECTED: Air Force One ({flight['callsign']}) active"

        summary = f"SIMULATED demo data. Aircraft {flight['reg']} at {flight['alt']}ft. Position: {flight['lat']}, {flight['lon']}. Squawk: {flight['squawk']}"
        
        content_hash = hashlib.sha256(f"{flight['icao24']}_{now.strftime('%Y%m%d%H')}".encode()).hexdigest()

        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_id, source_agent, source_name, content_hash,
                content_headline, content_summary, domain, priority, geo, confidence
            ) VALUES (
                'SIGINT', 'simulated', %s, %s, %s,
                %s, %s, 'AVIATION', %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), 0.1
            ) ON CONFLICT (content_hash) DO NOTHING
            """, (self.name, self.SOURCE_NAME, content_hash, headline, summary, priority, flight['lon'], flight['lat'])
        )
        
        logger.info(f"Aviation Hit Processed: {flight['callsign']} ({priority})")

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = AviationAgent(name="aviation_sentinel_v1", interval_sec=60)
    agent.run()
