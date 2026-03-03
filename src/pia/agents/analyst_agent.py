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
        
        # Fetch the full context for the claimed job, including source authority
        job_results = self.db.execute_query("""
            SELECT u.uid, u.geo, u.domain, u.priority, u.content_summary, u.content_raw, u.mission_id, u.client_id,
                   u.source_name, COALESCE(s.trust_score, 0.5) as source_trust,
                   m.category as mission_category, m.keywords as mission_keywords
            FROM intelligence_records u
            LEFT JOIN mission_focus m ON u.mission_id = m.focus_id
            LEFT JOIN source_authority s ON u.source_name = s.source_name
            WHERE u.uid = %s
        """, (uir_uid,), fetch=True)

        if not job_results:
            logger.error(f"UIR {uir_uid} not found for Job {job_id}")
            self.db.execute_query("UPDATE analysis_queue SET status = 'FAILED', error_message = 'UIR record missing' WHERE queue_id = %s", (job_id,))
            return

        job_context = job_results[0]
        logger.info(f"Agent {self.name} claimed Job {job_id} from {job_context['source_name']} (Trust: {job_context['source_trust']})")

        try:
            # --- SUB-TASK 1: Spatial reasoning ---
            anchor_city = self.find_nearest_anchor(job_context['geo'])
            cluster_id = self.correlate_and_cluster(job_context, anchor_city)

            # --- SUB-TASK 2: NLP Object Extraction (Mission-Aware) ---
            text_to_analyze = job_context['content_raw'] or job_context['content_summary'] or ""
            
            intelligence_components = self.nlp.extract_intelligence(
                text_to_analyze, 
                mission_category=job_context.get('mission_category'),
                mission_keywords=job_context.get('mission_keywords'),
                client_id=job_context.get('client_id')
            )

            # --- SUB-TASK 3: Entity Resolution and Linking ---
            resolved_entities = self.process_intelligence_components(uir_uid, intelligence_components)

            # --- SUB-TASK 4: Relationship Inference & Graph Sync ---
            self.process_inferred_relationships(resolved_entities, intelligence_components.get('relationships', []), job_context)

            # Finalize job
            self.db.execute_query("UPDATE intelligence_records SET cluster_id = %s WHERE uid = %s", (cluster_id, uir_uid))
            self.db.execute_query("UPDATE analysis_queue SET status = 'DONE', result_cluster = %s WHERE queue_id = %s", (cluster_id, job_id))
            
            logger.success(f"Intelligence Fusion Complete for UIR {uir_uid}")

        except Exception as e:
            logger.error(f"Fusion failed for job {job_id}: {e}")
            self.db.execute_query("UPDATE analysis_queue SET status = 'FAILED', error_message = %s WHERE queue_id = %s", (str(e), job_id))

    def process_intelligence_components(self, uir_uid: str, components: Dict) -> Dict[str, str]:
        """Resolves extracted names to database UUIDs using Multi-Factor Grounding."""
        resolved_map = {} 
        
        # Fetch current record context for grounding
        context = self.db.execute_query("SELECT geo, source_name FROM intelligence_records WHERE uid = %s", (uir_uid,), fetch=True)[0]
        record_geo = context['geo']

        for ent in components.get('entities', []):
            name = ent['name']
            ent_type = ent['type']
            best_eid = None
            best_score = 0.0
            
            query_vector = self.nlp.generate_embedding(name)
            if not query_vector: continue

            # 1. Candidate 1: Lexical Match
            lexical = self.db.execute_query("""
                SELECT entity_id, name, (1 - (embedding <=> %s::vector)) as similarity
                FROM entities 
                WHERE (name ILIKE %s OR %s = ANY(aliases))
                LIMIT 1
            """, (query_vector, name, name), fetch=True)
            
            if lexical and lexical[0]['similarity']:
                best_eid = lexical[0]['entity_id']
                best_score = lexical[0]['similarity']

            # 2. Candidate 2: Semantic Match (Nearest Neighbor)
            semantic = self.db.execute_query("""
                SELECT entity_id, name, entity_type, (1 - (embedding <=> %s::vector)) as similarity,
                       ST_Distance(primary_geo, %s) as distance_meters
                FROM entities
                WHERE embedding IS NOT NULL
                AND entity_type = %s
                ORDER BY embedding <=> %s::vector
                LIMIT 1
            """, (query_vector, record_geo, ent_type, query_vector), fetch=True)
            
            if semantic:
                s_cand = semantic[0]
                s_score = s_cand['similarity']
                
                # Physics Guardrail
                is_far = s_cand['distance_meters'] and s_cand['distance_meters'] > 100000 
                
                # Logic Tie-Breaker
                if s_score > 0.45 and not is_far:
                    if s_score < 0.85:
                        cand_info = {"name": s_cand['name'], "type": s_cand['entity_type']}
                        new_info = {"name": name, "type": ent_type}
                        if not self.nlp.verify_fusion(cand_info, new_info):
                            s_score = 0.0 
                    
                    if s_score > best_score:
                        best_eid = s_cand['entity_id']
                        best_score = s_score

            # 3. Final Decision
            if best_eid and best_score > 0.45:
                resolved_map[name] = best_eid
                self.db.execute_query("""
                    UPDATE entities 
                    SET mention_count = mention_count + 1,
                        uir_refs = array_append(uir_refs, %s),
                        last_seen = NOW()
                    WHERE entity_id = %s
                """, (uir_uid, best_eid))
                logger.success(f"Grounded Resolution: '{name}' -> '{best_eid}' ({best_score:.2f})")
            else:
                # New entity creation
                new_ent = self.db.execute_query("""
                    INSERT INTO entities (name, entity_type, mention_count, uir_refs, confidence, embedding, primary_geo)
                    VALUES (%s, %s, 1, ARRAY[%s::uuid], 0.3, %s, %s)
                    RETURNING entity_id
                """, (name, ent_type, uir_uid, query_vector, record_geo), fetch=True)
                resolved_map[name] = new_ent[0]['entity_id']
                logger.debug(f"Created new GROUNDED entity: {name}")
        
        return resolved_map

    def _safe_cypher_name(self, name: str) -> str:
        """Escapes double quotes in entity names for safe Cypher injection."""
        return name.replace('"', '\\"')

    def process_inferred_relationships(self, resolved_map: Dict[str, str], relationships: List[Dict], context: Dict):
        """Creates relationship records with Cross-Verification logic."""
        source_trust = context['source_trust']
        
        for rel in relationships:
            sub_id = resolved_map.get(rel['subject'])
            obj_id = resolved_map.get(rel['object'])
            predicate = rel['predicate']
            
            if sub_id and obj_id:
                # CROSS-VERIFICATION LOGIC:
                # 1. We check if this relationship exists from a DIFFERENT source
                existing = self.db.execute_query("""
                    SELECT confidence, last_confirmed 
                    FROM entity_relationships 
                    WHERE entity_a_id = %s AND entity_b_id = %s AND relationship_type = %s
                """, (sub_id, obj_id, predicate), fetch=True)

                base_confidence = source_trust * 0.6 # Initial trust weighted by source
                
                if existing:
                    # Relationship corroborated! Increase confidence based on source authority
                    new_confidence = min(existing[0]['confidence'] + (source_trust * 0.2), 0.98)
                    self.db.execute_query("""
                        UPDATE entity_relationships 
                        SET last_confirmed = NOW(), 
                            confidence = %s,
                            mention_count = mention_count + 1
                        WHERE entity_a_id = %s AND entity_b_id = %s AND relationship_type = %s
                    """, (new_confidence, sub_id, obj_id, predicate))
                    logger.info(f"Relationship Corroborated: confidence raised to {new_confidence:.2f}")
                else:
                    # First time seeing this link
                    self.db.execute_query("""
                        INSERT INTO entity_relationships (entity_a_id, entity_b_id, relationship_type, confidence, mention_count)
                        VALUES (%s, %s, %s, %s, 1)
                    """, (sub_id, obj_id, predicate, base_confidence))
                
                # Sync to Graph only if confidence > 0.5
                if (existing and new_confidence > 0.5) or (not existing and base_confidence > 0.5):
                    self._sync_to_graph(sub_id, obj_id, predicate)

    def _sync_to_graph(self, sub_id, obj_id, predicate):
        """Internal helper to mirror relationships to Apache AGE."""
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
        """Finds an existing active cluster using Multi-Level Matching."""
        domain = job['domain']
        geo = job['geo']
        content = (job['content_summary'] or job['content_headline'] or "").lower()
        record_vector = self.nlp.generate_embedding(content)
        
        city_name = anchor_city['name'] if anchor_city else None
        
        # Determine the best match
        cid = None
        if geo and record_vector:
            # LEVEL 1: High-Confidence Semantic Match
            existing = self.db.execute_query("""
                SELECT cluster_id FROM intelligence_clusters
                WHERE status = 'ACTIVE' AND domain = %s AND client_id = %s
                AND ST_DWithin(geo_centroid, %s, 50000)
                AND (1 - (semantic_dna <=> %s::vector)) > 0.35
                LIMIT 1
            """, (domain, job['client_id'], geo, record_vector), fetch=True)
            if existing: cid = existing[0]['cluster_id']

            # LEVEL 2: Mission-Spatial Fallback
            if not cid and (job.get('mission_keywords') or job.get('mission_category')):
                targets = [k.lower() for k in (job.get('mission_keywords') or [])]
                if job.get('mission_category'): targets.append(job['mission_category'].lower())
                
                if any(t in content for t in targets):
                    spatial = self.db.execute_query("""
                        SELECT cluster_id FROM intelligence_clusters
                        WHERE status = 'ACTIVE' AND domain = %s AND client_id = %s
                        AND ST_DWithin(geo_centroid, %s, 50000)
                        LIMIT 1
                    """, (domain, job['client_id'], geo), fetch=True)
                    if spatial: cid = spatial[0]['cluster_id']

        if cid:
            self.db.execute_query("""
                UPDATE intelligence_clusters 
                SET updated_at = NOW(), uir_count = uir_count + 1
                WHERE cluster_id = %s
            """, (cid,))
            return cid

        # STAGE 3: Create new cluster
        title = f"Situation: {domain} activity"
        if city_name: title += f" near {city_name}"
        
        new_cluster = self.db.execute_query("""
            INSERT INTO intelligence_clusters (
                title, domain, status, priority, confidence, geo_centroid, uir_count, semantic_dna, client_id
            ) VALUES (
                %s, %s, 'ACTIVE', %s, 0.7, %s, 1, %s, %s
            ) RETURNING cluster_id
        """, (title, domain, job['priority'], geo, record_vector, job['client_id']), fetch=True)
        
        return new_cluster[0]['cluster_id']

    def stop(self):
        self.db.close()

if __name__ == "__main__":
    agent = AnalystAgent(name="heartbeat_analyst_v1", interval_sec=10)
    agent.run()
