from loguru import logger
import json
from typing import Optional, Dict

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager

class AnalystAgent(BaseAgent):
    """
    The Heartbeat Analyst. Processes the analysis_queue to correlate 
    UIRs with entities and create intelligence clusters.
    """

    def setup(self):
        self.db = DatabaseManager()
        logger.info(f"{self.name} initialized database connection.")

    def poll(self):
        """Processes the oldest PENDING job in the analysis queue."""
        # 1. Get the oldest pending job
        job = self.db.execute_query("""
            SELECT queue_id, uir_uid, geo, domain, priority 
            FROM analysis_queue 
            WHERE status = 'PENDING' 
            ORDER BY created_at ASC 
            LIMIT 1
        """, fetch=True)

        if not job:
            return

        job = job[0]
        queue_id = job['queue_id']
        uir_uid = job['uir_uid']
        
        logger.info(f"Processing Job {queue_id} for UIR {uir_uid}")

        try:
            # 2. Mark job as PROCESSING
            self.db.execute_query(
                "UPDATE analysis_queue SET status = 'PROCESSING', processed_at = NOW() WHERE queue_id = %s",
                (queue_id,)
            )

            # 3. Perform Spatial Correlation (Find the nearest city)
            anchor_city = self.find_nearest_anchor(job['geo'])
            
            # 4. Clustering Logic: Match or Create
            cluster_id = self.correlate_and_cluster(job, anchor_city)

            # 5. Link UIR to Cluster and finalize job
            self.db.execute_query(
                "UPDATE intelligence_records SET cluster_id = %s WHERE uid = %s",
                (cluster_id, uir_uid)
            )
            
            self.db.execute_query(
                "UPDATE analysis_queue SET status = 'DONE', result_cluster = %s WHERE queue_id = %s",
                (cluster_id, queue_id)
            )
            
            logger.success(f"Job {queue_id} complete. UIR linked to cluster {cluster_id}")

        except Exception as e:
            logger.error(f"Failed to process job {queue_id}: {e}")
            self.db.execute_query(
                "UPDATE analysis_queue SET status = 'FAILED', error_message = %s WHERE queue_id = %s",
                (str(e), queue_id)
            )

    def find_nearest_anchor(self, geo_point) -> Optional[Dict]:
        """Finds the nearest seeded city within 100km using PostGIS."""
        if not geo_point:
            return None

        query = """
            SELECT name, canonical_name, entity_id, 
                   ST_Distance(primary_geo, %s) as distance_meters
            FROM entities
            WHERE entity_type = 'LOCATION'
            AND ST_DWithin(primary_geo, %s, 100000) -- 100km radius
            ORDER BY distance_meters ASC
            LIMIT 1
        """
        results = self.db.execute_query(query, (geo_point, geo_point), fetch=True)
        return results[0] if results else None

    def correlate_and_cluster(self, job, anchor_city) -> str:
        """Finds an existing active cluster or creates a new one."""
        domain = job['domain']
        geo = job['geo']
        
        # Determine a title for the potential cluster
        city_name = anchor_city['name'] if anchor_city else "Unknown Location"
        default_title = f"Active {domain} events near {city_name}"

        # 1. Search for an existing active cluster in the same domain and vicinity (50km)
        if geo:
            existing = self.db.execute_query("""
                SELECT cluster_id FROM intelligence_clusters
                WHERE status = 'ACTIVE'
                AND domain = %s
                AND ST_DWithin(geo_centroid, %s, 50000)
                LIMIT 1
            """, (domain, geo), fetch=True)
            
            if existing:
                cid = existing[0]['cluster_id']
                # Update existing cluster metadata
                self.db.execute_query("""
                    UPDATE intelligence_clusters 
                    SET updated_at = NOW(), 
                        uir_count = uir_count + 1
                    WHERE cluster_id = %s
                """, (cid,))
                return cid

        # 2. Create a NEW cluster if no match found
        new_cluster = self.db.execute_query("""
            INSERT INTO intelligence_clusters (
                title, domain, status, priority, confidence, geo_centroid, uir_count
            ) VALUES (
                %s, %s, 'ACTIVE', %s, 0.7, %s, 1
            ) RETURNING cluster_id
        """, (default_title, domain, job['priority'], geo), fetch=True)
        
        return new_cluster[0]['cluster_id']

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    # The Analyst Agent polls more frequently (every 10s) to keep up with ingestion
    agent = AnalystAgent(name="heartbeat_analyst_v1", interval_sec=10)
    agent.run()
