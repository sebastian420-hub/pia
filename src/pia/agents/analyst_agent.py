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
        # Create a unique name for concurrency tracking
        import socket
        hostname = socket.gethostname()
        self.name = f"analyst_{hostname}_{uuid.uuid4().hex[:6]}"
        logger.info(f"{self.name} initialized with NLP extraction brain.")

    def poll(self):
        """Processes the oldest PENDING job in the analysis queue using concurrency-safe locking."""
        # Atomic claim: Find one PENDING job, lock it, and mark as PROCESSING in one step.
        # This prevents 'Double Processing' when running multiple agents.
        job_query = """
            UPDATE analysis_queue
            SET status = 'PROCESSING', 
                processed_at = NOW(),
                assigned_agent = %s
            WHERE queue_id = (
                SELECT q.queue_id
                FROM analysis_queue q
                WHERE q.status = 'PENDING'
                ORDER BY q.priority = 'CRITICAL' DESC, q.created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING queue_id, uir_uid;
        """
        
        claimed = self.db.execute_query(job_query, (self.name,), fetch=True)

        if not claimed:
            return

        job_id = claimed[0]['queue_id']
        uir_uid = claimed[0]['uir_uid']
        
        # Fetch the full context for the claimed job
        job_results = self.db.execute_query("""
            SELECT u.uid, u.geo, u.domain, u.priority, u.content_summary, u.content_raw, u.mission_id,
                   m.category as mission_category, m.keywords as mission_keywords
            FROM intelligence_records u
            LEFT JOIN mission_focus m ON u.mission_id = m.focus_id
            WHERE u.uid = %s
        """, (uir_uid,), fetch=True)

        if not job_results:
            logger.error(f"UIR {uir_uid} not found for Job {job_id}")
            self.db.execute_query("UPDATE analysis_queue SET status = 'FAILED', error_message = 'UIR record missing' WHERE queue_id = %s", (job_id,))
            return

        job_context = job_results[0]
        logger.info(f"Agent {self.name} claimed Job {job_id} for UIR {uir_uid} {'[MISSION: ' + job_context['mission_category'] + ']' if job_context['mission_id'] else ''}")

        try:
            # --- SUB-TASK 1: Spatial reasoning ---
            anchor_city = self.find_nearest_anchor(job_context['geo'])
            cluster_id = self.correlate_and_cluster(job_context, anchor_city)

            # --- SUB-TASK 2: NLP Object Extraction (Mission-Aware) ---
            text_to_analyze = job_context['content_raw'] or job_context['content_summary'] or ""
            
            mission_str = None
            if job_context['mission_id']:
                mission_str = f"Category: {job_context['mission_category']}, Keywords: {', '.join(job_context['mission_keywords'] or [])}"

            intelligence_components = self.nlp.extract_intelligence(text_to_analyze, mission_context=mission_str)

            # --- SUB-TASK 3: Entity Resolution and Linking ---
            resolved_entities = self.process_intelligence_components(uir_uid, intelligence_components)

            # --- SUB-TASK 4: Relationship Inference & Graph Sync ---
            self.process_inferred_relationships(resolved_entities, intelligence_components.get('relationships', []))

            # Finalize job
            self.db.execute_query("UPDATE intelligence_records SET cluster_id = %s WHERE uid = %s", (cluster_id, uir_uid))
            self.db.execute_query("UPDATE analysis_queue SET status = 'DONE', result_cluster = %s WHERE queue_id = %s", (cluster_id, job_id))
            
            logger.success(f"Intelligence Fusion Complete for UIR {uir_uid}")

        except Exception as e:
            logger.error(f"Fusion failed for job {job_id}: {e}")
            self.db.execute_query("UPDATE analysis_queue SET status = 'FAILED', error_message = %s WHERE queue_id = %s", (str(e), job_id))

    def process_intelligence_components(self, uir_uid: str, components: Dict) -> Dict[str, str]:
        """Resolves extracted names to database UUIDs using Semantic Disambiguation."""
        resolved_map = {} # Name -> UUID
        
        for ent in components.get('entities', []):
            name = ent['name']
            ent_type = ent['type']
            best_eid = None
            best_score = 0.0
            
            # 1. Generate Query Vector for this entity
            query_vector = self.nlp.generate_embedding(name)
            if not query_vector: continue

            # 2. Candidate 1: Lexical Match (Exact or Alias)
            lexical = self.db.execute_query("""
                SELECT entity_id, name, (1 - (embedding <=> %s::vector)) as similarity
                FROM entities 
                WHERE (name ILIKE %s OR %s = ANY(aliases))
                LIMIT 1
            """, (query_vector, name, name), fetch=True)
            
            if lexical and lexical[0]['similarity']:
                best_eid = lexical[0]['entity_id']
                best_score = lexical[0]['similarity']
                logger.debug(f"Lexical Candidate: '{lexical[0]['name']}' (Score: {best_score:.2f})")

            # 3. Candidate 2: Semantic Match (Nearest Neighbor of same type)
            semantic = self.db.execute_query("""
                SELECT entity_id, name, (1 - (embedding <=> %s::vector)) as similarity
                FROM entities
                WHERE embedding IS NOT NULL
                AND entity_type = %s
                ORDER BY embedding <=> %s::vector
                LIMIT 1
            """, (query_vector, ent_type, query_vector), fetch=True)
            
            if semantic:
                s_eid = semantic[0]['entity_id']
                s_score = semantic[0]['similarity']
                logger.debug(f"Semantic Candidate: '{semantic[0]['name']}' (Score: {s_score:.2f})")
                
                # Tie-Breaker: If semantic match is significantly better, it wins
                if s_score > best_score and s_score > 0.45:
                    best_eid = s_eid
                    best_score = s_score
                    logger.debug(f"Disambiguation: Semantic match outranked Lexical match.")

            # 4. Final Decision
            if best_eid and best_score > 0.45:
                resolved_map[name] = best_eid
                self.db.execute_query("""
                    UPDATE entities 
                    SET mention_count = mention_count + 1,
                        uir_refs = array_append(uir_refs, %s),
                        last_seen = NOW()
                    WHERE entity_id = %s
                """, (uir_uid, best_eid))
                logger.success(f"Resolved: '{name}' -> '{best_eid}' ({best_score:.2f})")
            else:
                # STAGE 3: Create new entity
                new_ent = self.db.execute_query("""
                    INSERT INTO entities (name, entity_type, mention_count, uir_refs, confidence, embedding)
                    VALUES (%s, %s, 1, ARRAY[%s::uuid], 0.3, %s)
                    RETURNING entity_id
                """, (name, ent_type, uir_uid, query_vector), fetch=True)
                resolved_map[name] = new_ent[0]['entity_id']
                logger.debug(f"Created new PENDING entity: {name}")
        
        return resolved_map

    def _safe_cypher_name(self, name: str) -> str:
        """Escapes double quotes in entity names for safe Cypher injection."""
        return name.replace('"', '\\"')

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
                
                safe_a = self._safe_cypher_name(names['name_a'])
                safe_b = self._safe_cypher_name(names['name_b'])
                
                cypher = f"""
                    MERGE (a:ENTITY {{name: "{safe_a}"}})
                    MERGE (b:ENTITY {{name: "{safe_b}"}})
                    MERGE (a)-[r:{predicate}]->(b)
                """
                try:
                    self.db.execute_cypher('pia_graph', cypher)
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
