from loguru import logger
import json
from typing import Optional, Dict, List
import uuid

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager

class AnalystAgent(BaseAgent):
    """
    The Upgraded Heartbeat Analyst. 
    Performs Spatial Correlation, Entity Extraction (NLP), and Graph Linking.
    """

    def setup(self):
        self.db = DatabaseManager()
        self.nlp = NLPManager()
        logger.info(f"{self.name} initialized with NLP extraction brain.")

    def poll(self):
        """Processes the oldest PENDING job in the analysis queue."""
        # 1. Get the oldest pending job with full UIR context
        job = self.db.execute_query("""
            SELECT q.queue_id, q.uir_uid, u.geo, u.domain, u.priority, u.content_summary, u.content_raw
            FROM analysis_queue q
            JOIN intelligence_records u ON q.uir_uid = u.uid
            WHERE q.status = 'PENDING' 
            ORDER BY q.created_at ASC 
            LIMIT 1
        """, fetch=True)

        if not job:
            return

        job = job[0]
        logger.info(f"Processing Job {job['queue_id']} for UIR {job['uir_uid']}")

        try:
            self.db.execute_query("UPDATE analysis_queue SET status = 'PROCESSING', processed_at = NOW() WHERE queue_id = %s", (job['queue_id'],))

            # --- SUB-TASK 1: Spatial reasoning ---
            anchor_city = self.find_nearest_anchor(job['geo'])
            cluster_id = self.correlate_and_cluster(job, anchor_city)

            # --- SUB-TASK 2: NLP Object Extraction ---
            text_to_analyze = job['content_raw'] or job['content_summary'] or ""
            intelligence_components = self.nlp.extract_intelligence(text_to_analyze)

            # --- SUB-TASK 3: Entity Resolution and Linking ---
            resolved_entities = self.process_intelligence_components(job['uir_uid'], intelligence_components)

            # --- SUB-TASK 4: Relationship Inference & Graph Sync ---
            self.process_inferred_relationships(resolved_entities, intelligence_components.get('relationships', []))

            # Finalize job
            self.db.execute_query("UPDATE intelligence_records SET cluster_id = %s WHERE uid = %s", (cluster_id, job['uir_uid']))
            self.db.execute_query("UPDATE analysis_queue SET status = 'DONE', result_cluster = %s WHERE queue_id = %s", (cluster_id, job['queue_id']))
            
            logger.success(f"Intelligence Fusion Complete for UIR {job['uir_uid']}")

        except Exception as e:
            logger.error(f"Fusion failed for job {job['queue_id']}: {e}")
            self.db.execute_query("UPDATE analysis_queue SET status = 'FAILED', error_message = %s WHERE queue_id = %s", (str(e), job['queue_id']))

    def process_intelligence_components(self, uir_uid: str, components: Dict) -> Dict[str, str]:
        """Resolves extracted names to database UUIDs and updates mention telemetry."""
        resolved_map = {} # Name -> UUID
        
        for ent in components.get('entities', []):
            name = ent['name']
            ent_type = ent['type']
            
            # Resolution logic: Search by name or alias
            entity = self.db.execute_query("""
                SELECT entity_id FROM entities 
                WHERE name ILIKE %s OR %s = ANY(aliases)
                LIMIT 1
            """, (name, name), fetch=True)
            
            if entity:
                eid = entity[0]['entity_id']
                resolved_map[name] = eid
                # Update entity mention telemetry (Part IV of design)
                self.db.execute_query("""
                    UPDATE entities 
                    SET mention_count = mention_count + 1,
                        uir_refs = array_append(uir_refs, %s),
                        last_seen = NOW()
                    WHERE entity_id = %s
                """, (uir_uid, eid))
                logger.debug(f"Linked UIR to existing entity: {name} ({eid})")
            else:
                # Placeholder: Create a PENDING entity for future Wikidata resolution
                new_ent = self.db.execute_query("""
                    INSERT INTO entities (name, entity_type, mention_count, uir_refs, confidence)
                    VALUES (%s, %s, 1, ARRAY[%s::uuid], 0.3)
                    RETURNING entity_id
                """, (name, ent_type, uir_uid), fetch=True)
                resolved_map[name] = new_ent[0]['entity_id']
                logger.debug(f"Created new PENDING entity: {name}")
        
        return resolved_map

    def process_inferred_relationships(self, resolved_map: Dict[str, str], relationships: List[Dict]):
        """Creates relationship records and mirrors to Apache AGE graph."""
        for rel in relationships:
            sub_id = resolved_map.get(rel['subject'])
            obj_id = resolved_map.get(rel['object'])
            predicate = rel['predicate']
            
            if sub_id and obj_id:
                # 1. Relational insert
                self.db.execute_query("""
                    INSERT INTO entity_relationships (entity_a_id, entity_b_id, relationship_type, confidence)
                    VALUES (%s, %s, %s, 0.6)
                    ON CONFLICT (entity_a_id, entity_b_id, relationship_type) DO UPDATE
                    SET last_confirmed = NOW(), confidence = LEAST(entity_relationships.confidence + 0.05, 1.0)
                """, (sub_id, obj_id, predicate))
                
                # 2. Apache AGE Sync (using entity names for the graph nodes)
                # We fetch names to ensure graph readability
                names = self.db.execute_query("""
                    SELECT 
                        (SELECT name FROM entities WHERE entity_id = %s) as name_a,
                        (SELECT name FROM entities WHERE entity_id = %s) as name_b
                """, (sub_id, obj_id), fetch=True)[0]
                
                cypher = f"""
                    SELECT * FROM cypher('pia_graph', $$
                        MERGE (a:ENTITY {{name: "{names['name_a']}"}})
                        MERGE (b:ENTITY {{name: "{names['name_b']}"}})
                        MERGE (a)-[r:{predicate}]->(b)
                    $$) as (v agtype);
                """
                try:
                    self.db.execute_query(f"LOAD 'age'; SET search_path = public, ag_catalog; {cypher}")
                except Exception as e:
                    logger.warning(f"Graph relationship sync failed: {e}")

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
        
        city_name = anchor_city['name'] if anchor_city else "Unknown Location"
        default_title = f"Active {domain} events near {city_name}"

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
                self.db.execute_query("""
                    UPDATE intelligence_clusters 
                    SET updated_at = NOW(), uir_count = uir_count + 1
                    WHERE cluster_id = %s
                """, (cid,))
                return cid

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
    agent = AnalystAgent(name="heartbeat_analyst_v1", interval_sec=10)
    agent.run()
