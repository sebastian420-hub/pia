import time, uuid, json, hashlib
from loguru import logger
from datetime import datetime

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

class AviationAgent(BaseAgent):
    """
    The Aviation Sentinel.
    Polls ADS-B data and ingests aircraft movements into the Agency's spine.
    """

    def setup(self):
        self.db = DatabaseManager()
        # Ensure source authority exists
        self.db.execute_query(
            "INSERT INTO source_authority (source_name, source_type, trust_score, notes) VALUES ('ADS-B Aviation Feed', 'SIGINT', 0.95, 'Real-time flight tracking') ON CONFLICT DO NOTHING"
        )
        logger.info(f"{self.name} initialized for global aviation surveillance.")

    def poll(self):
        """Simulates/Polls real-time ADS-B flight hits."""
        # Simulated high-interest targets
        flights = [
            {"callsign": "AF1", "icao24": "adf032", "reg": "28000", "alt": 35000, "lat": 38.8, "lon": -77.0, "squawk": "None"},
            {"callsign": "TITAN25", "icao24": "ae01ce", "reg": "62-4128", "alt": 28000, "lat": 52.5, "lon": 13.4, "squawk": "None"}, # RC-135V Rivet Joint
            {"callsign": "MAYDAY1", "icao24": "abc123", "reg": "N12345", "alt": 5000, "lat": 34.0, "lon": -118.2, "squawk": "7700"} # Emergency squawk
        ]

        for flight in flights:
            self.ingest_flight_hit(flight)

    def ingest_flight_hit(self, flight):
        """Converts a flight hit into a telemetry record and a UIR for the Brain."""
        now = datetime.now()
        
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
        headline = f"AIRCRAFT HIT: {flight['callsign']} ({flight['reg']}) detected"
        
        if flight['squawk'] == '7700':
            priority = 'CRITICAL'
            headline = f"⚠️ EMERGENCY: Flight {flight['callsign']} squawking 7700"
        elif flight['callsign'] == 'AF1':
            priority = 'HIGH'
            headline = f"🎯 TARGET DETECTED: Air Force One ({flight['callsign']}) active"

        summary = f"Aircraft {flight['reg']} detected at {flight['alt']}ft. Position: {flight['lat']}, {flight['lon']}. Squawk: {flight['squawk']}"
        
        content_hash = hashlib.sha256(f"{flight['icao24']}_{now.strftime('%Y%m%d%H')}".encode()).hexdigest()

        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_agent, source_name, content_hash,
                content_headline, content_summary, domain, priority, geo
            ) VALUES (
                'SIGINT', %s, 'ADS-B Aviation Feed', %s,
                %s, %s, 'MILITARY', %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            ) ON CONFLICT (content_hash) DO NOTHING
            """, (self.name, content_hash, headline, summary, priority, flight['lon'], flight['lat'])
        )
        
        logger.info(f"Aviation Hit Processed: {flight['callsign']} ({priority})")

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = AviationAgent(name="aviation_sentinel_v1", interval_sec=60)
    agent.run()
