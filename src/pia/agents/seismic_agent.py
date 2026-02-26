import requests
from loguru import logger
from typing import List
import json

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.models.seismic import SeismicEvent

class SeismicAgent(BaseAgent):
    """Polls USGS for real-time earthquake data and ingests into PIA."""
    
    USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"

    def setup(self):
        self.db = DatabaseManager()
        logger.info(f"{self.name} initialized database connection.")

    def poll(self):
        logger.debug(f"{self.name} polling USGS feed...")
        response = requests.get(self.USGS_URL)
        response.raise_for_status()
        data = response.json()

        features = data.get("features", [])
        logger.info(f"Retrieved {len(features)} events from USGS.")

        for feature in features:
            try:
                event = SeismicEvent(**feature)
                self.process_event(event)
            except Exception as e:
                logger.error(f"Failed to process seismic feature: {e}")

    def process_event(self, event: SeismicEvent):
        """Ingests a validated event into Layer 1 and Layer 2."""
        
        # 1. Check if we've already processed this event (Idempotency)
        exists = self.db.execute_query(
            "SELECT 1 FROM seismic_events WHERE usgs_id = %s", 
            (event.id,), 
            fetch=True
        )
        if exists:
            return

        logger.info(f"New Seismic Event detected: {event.properties.title}")

        # 2. Insert into Layer 1 (Telemetry)
        self.db.execute_query(
            """
            INSERT INTO seismic_events (
                time, usgs_id, position, depth_km, magnitude, 
                magnitude_type, location_name, tsunami_warning
            ) VALUES (
                %s, %s, ST_SetSRID(ST_Point(%s, %s), 4326), %s, %s, %s, %s, %s
            )
            """,
            (
                event.event_time, event.id, event.lon, event.lat, 
                event.depth, event.properties.mag, event.properties.magType,
                event.properties.place, bool(event.properties.tsunami)
            )
        )

        # 3. Insert into Layer 2 (Universal Intelligence Record)
        # This will fire the 'Heartbeat' Trigger automatically
        self.db.execute_query(
            """
            INSERT INTO intelligence_records (
                source_type, source_agent, source_name, source_url,
                content_headline, content_summary, domain, priority,
                geo, confidence
            ) VALUES (
                'GEOINT', %s, 'USGS Seismic Feed', %s,
                %s, %s, 'NATURAL', %s,
                ST_SetSRID(ST_Point(%s, %s), 4326), 0.95
            )
            """,
            (
                self.name, event.properties.url,
                event.properties.title, 
                f"Earthquake of magnitude {event.properties.mag} detected at {event.properties.place}.",
                'HIGH' if (event.properties.mag or 0) >= 5.0 else 'NORMAL',
                event.lon, event.lat
            )
        )

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    # In a professional setup, we'd use a CLI entry point or runner script
    agent = SeismicAgent(name="seismic_collector_v1", interval_sec=60)
    agent.run()
