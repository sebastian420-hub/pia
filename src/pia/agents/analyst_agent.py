from loguru import logger
import json
import os
from typing import Optional, Dict, List, Tuple

from pia.core.base_agent import BaseAgent
from pia.core.database import DatabaseManager, assert_safe_label, CypherLabelError
from pia.core.nlp import NLPManager, ExtractionError


class AnalystAgent(BaseAgent):
    """
    The Upgraded Heartbeat Analyst.
    Performs Spatial Correlation, Entity Extraction (NLP), and Graph Linking.
    """

    # A job left in PROCESSING longer than this is assumed to belong to a dead
    # worker and is re-claimed. FAILED jobs are retried up to MAX_RETRIES times.
    STALE_MINUTES = int(os.getenv("ANALYST_STALE_MINUTES", "10"))
    MAX_RETRIES = int(os.getenv("ANALYST_MAX_RETRIES", "3"))
    RETRY_DELAY_MINUTES = int(os.getenv("ANALYST_RETRY_DELAY_MINUTES", "5"))
    NEW_ENTITY_CONFIDENCE = 0.5  # maintenance.py purges < 0.4; new work must survive

    def setup(self):
        self.db = DatabaseManager()
        self.nlp = NLPManager()
        # One stable name per container (hostname = container id) so heartbeats survive restarts
        import socket
        self.name = f"analyst_{socket.gethostname()}"
        logger.info(f"{self.name} initialized with NLP extraction brain.")

    def poll(self):
        """Drains the analysis queue: keeps claiming jobs until none are left."""
        while self.running:
            if not self.process_one_job():
                return

    def claim_job(self) -> Optional[Dict]:
        """Atomically claims one job (PENDING, stale PROCESSING, or retryable FAILED)."""
        job_query = """
            UPDATE analysis_queue
            SET status = 'PROCESSING',
                processed_at = NOW(),
                assigned_at = NOW(),
                assigned_agent = %s
            WHERE queue_id = (
                SELECT q.queue_id
                FROM analysis_queue q
                WHERE q.status = 'PENDING'
                   OR (q.status = 'PROCESSING'
                       AND q.processed_at < NOW() - make_interval(mins => %s))
                   OR (q.status = 'FAILED'
                       AND q.retry_count < %s
                       AND q.processed_at < NOW() - make_interval(mins => %s))
                ORDER BY q.priority = 'CRITICAL' DESC, q.created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING queue_id, uir_uid, retry_count;
        """
        claimed = self.db.execute_query(
            job_query,
            (self.name, self.STALE_MINUTES, self.MAX_RETRIES, self.RETRY_DELAY_MINUTES),
            fetch=True,
        )
        return claimed[0] if claimed else None

    def fail_job(self, job_id, message: str, retryable: bool = True):
        """Marks a job FAILED. Retryable failures count towards MAX_RETRIES."""
        self.db.execute_query(
            """
            UPDATE analysis_queue
            SET status = 'FAILED',
                error_message = %s,
                retry_count = CASE WHEN %s THEN retry_count + 1 ELSE %s END
            WHERE queue_id = %s
            """,
            (str(message)[:2000], retryable, self.MAX_RETRIES, job_id),
        )

    def process_one_job(self) -> bool:
        """Processes a single job. Returns False when the queue is empty."""
        claimed = self.claim_job()
        if not claimed:
            return False

        job_id = claimed['queue_id']
        uir_uid = claimed['uir_uid']

        if uir_uid is None:
            self.fail_job(job_id, "Queue row has no uir_uid", retryable=False)
            return True

        # Fetch the full context for the claimed job, including source authority
        job_results = self.db.execute_query("""
            SELECT u.uid, u.geo, u.domain, u.priority, u.content_headline, u.content_summary, u.content_raw, u.mission_id, u.client_id,
                   u.source_name, COALESCE(s.trust_score, 0.5) as source_trust,
                   m.category as mission_category, m.keywords as mission_keywords
            FROM intelligence_records u
            LEFT JOIN mission_focus m ON u.mission_id = m.focus_id
            LEFT JOIN source_authority s ON u.source_name = s.source_name
            WHERE u.uid = %s
        """, (uir_uid,), fetch=True)

        if not job_results:
            logger.error(f"UIR {uir_uid} not found for Job {job_id}")
            self.fail_job(job_id, "UIR record missing", retryable=False)
            return True

        job_context = job_results[0]
        logger.info(f"Agent {self.name} claimed Job {job_id} from {job_context['source_name']} (Trust: {job_context['source_trust']})")

        try:
            # --- SUB-TASK 1: Spatial reasoning ---
            anchor_city = self.find_nearest_anchor(job_context['geo'])
            cluster_id, record_vector = self.correlate_and_cluster(job_context, anchor_city)

            # --- SUB-TASK 2: NLP Object Extraction (Mission-Aware) ---
            text_to_analyze = job_context['content_raw'] or job_context['content_summary'] or job_context['content_headline'] or ""

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

            # Extract entity names to save back to the UIR
            extracted_entity_names = list(resolved_entities.keys())
            summary = intelligence_components.get('summary')
            if not isinstance(summary, str) or not summary.strip():
                summary = None

            # Finalize job: also persist the embedding (semantic search) and the LLM summary
            self.db.execute_query("""
                UPDATE intelligence_records
                SET cluster_id = %s,
                    entities = %s,
                    embedding = COALESCE(%s::vector, embedding),
                    content_summary = COALESCE(content_summary, %s)
                WHERE uid = %s
            """, (cluster_id, extracted_entity_names, record_vector or None, summary, uir_uid))
            self.db.execute_query(
                "UPDATE analysis_queue SET status = 'DONE', error_message = NULL, result_cluster = %s WHERE queue_id = %s",
                (cluster_id, job_id),
            )

            logger.success(f"Intelligence Fusion Complete for UIR {uir_uid}")

        except ExtractionError as e:
            logger.error(f"Extraction failed for job {job_id}: {e}")
            self.fail_job(job_id, f"extraction: {e}")
        except Exception as e:
            logger.error(f"Fusion failed for job {job_id}: {e}")
            self.fail_job(job_id, str(e))
        return True

    def process_intelligence_components(self, uir_uid: str, components: Dict) -> Dict[str, str]:
        """Resolves extracted names to database UUIDs using Multi-Factor Grounding."""
        resolved_map = {}

        # Fetch current record context for grounding
        context = self.db.execute_query("SELECT geo, source_name FROM intelligence_records WHERE uid = %s", (uir_uid,), fetch=True)[0]
        record_geo = context['geo']

        for ent in components.get('entities', []):
            if not isinstance(ent, dict):
                continue
            name = (ent.get('name') or "").strip()
            ent_type = (ent.get('type') or "").strip().upper()
            if not name or not ent_type:
                continue

            # Map restricted types to allowed types
            if ent_type == 'GPE':
                ent_type = 'LOCATION'

            best_eid = None
            best_score = 0.0

            query_vector = self.nlp.generate_embedding(name)

            # 1. Candidate 1: Lexical Match (an exact name match wins even when the
            #    stored entity has no embedding yet; prefer the most-mentioned duplicate)
            if query_vector:
                lexical = self.db.execute_query("""
                    SELECT entity_id, name, (1 - (embedding <=> %s::vector)) as similarity
                    FROM entities
                    WHERE (name ILIKE %s OR %s = ANY(aliases))
                    ORDER BY mention_count DESC, created_at ASC
                    LIMIT 1
                """, (query_vector, name, name), fetch=True)
            else:
                lexical = self.db.execute_query("""
                    SELECT entity_id, name, NULL::float as similarity
                    FROM entities
                    WHERE (name ILIKE %s OR %s = ANY(aliases))
                    ORDER BY mention_count DESC, created_at ASC
                    LIMIT 1
                """, (name, name), fetch=True)

            if lexical:
                best_eid = lexical[0]['entity_id']
                best_score = lexical[0]['similarity'] if lexical[0]['similarity'] is not None else 1.0

            # 2. Candidate 2: Semantic Match (Nearest Neighbor)
            semantic = None
            if query_vector and record_geo:
                semantic = self.db.execute_query("""
                    SELECT entity_id, name, entity_type, (1 - (embedding <=> %s::vector)) as similarity,
                           ST_Distance(primary_geo, %s) as distance_meters
                    FROM entities
                    WHERE embedding IS NOT NULL
                    AND entity_type = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT 1
                """, (query_vector, record_geo, ent_type, query_vector), fetch=True)
            elif query_vector:
                semantic = self.db.execute_query("""
                    SELECT entity_id, name, entity_type, (1 - (embedding <=> %s::vector)) as similarity,
                           NULL as distance_meters
                    FROM entities
                    WHERE embedding IS NOT NULL
                    AND entity_type = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT 1
                """, (query_vector, ent_type, query_vector), fetch=True)

            if semantic:
                s_cand = semantic[0]
                s_score = s_cand['similarity'] or 0.0

                # Physics Guardrail (Only applies if we have a geo constraint)
                is_far = bool(s_cand['distance_meters'] and s_cand['distance_meters'] > 100000)

                # Logic Tie-Breaker
                if s_score > 0.45 and not is_far and s_cand['entity_id'] != best_eid:
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

                # Semantic Geo-Tagging Fallback (Phase 9 Upgrade)
                if not record_geo:
                    entity_geo = self.db.execute_query("SELECT primary_geo FROM entities WHERE entity_id = %s", (best_eid,), fetch=True)
                    if entity_geo and entity_geo[0]['primary_geo']:
                        # Give the UIR the entity's coordinates so it renders on the globe
                        self.db.execute_query(
                            "UPDATE intelligence_records SET geo = %s WHERE uid = %s",
                            (entity_geo[0]['primary_geo'], uir_uid)
                        )
                        record_geo = entity_geo[0]['primary_geo']
                        logger.success(f"Semantic Geo-Tagging applied: Anchored UIR {uir_uid} to '{name}' ({best_eid})")

                self.db.execute_query("""
                    UPDATE entities
                    SET mention_count = mention_count + 1,
                        uir_refs = array_append(uir_refs, %s),
                        last_seen = NOW()
                    WHERE entity_id = %s
                """, (uir_uid, best_eid))
                logger.success(f"Grounded Resolution: '{name}' -> '{best_eid}' ({best_score:.2f})")
            else:
                # New entity creation. Non-LOCATION names are unique per type
                # (partial index entities_name_type_uq), so concurrent analysts
                # converge on one row instead of creating duplicates.
                new_ent = self.db.execute_query("""
                    INSERT INTO entities (name, entity_type, mention_count, uir_refs, confidence, embedding, primary_geo)
                    VALUES (%s, %s, 1, ARRAY[%s::uuid], %s, %s::vector, %s)
                    ON CONFLICT (lower(name), entity_type) WHERE entity_type <> 'LOCATION'
                    DO UPDATE SET mention_count = entities.mention_count + 1,
                                  uir_refs = array_append(entities.uir_refs, EXCLUDED.uir_refs[1]),
                                  last_seen = NOW()
                    RETURNING entity_id
                """, (name, ent_type, uir_uid, self.NEW_ENTITY_CONFIDENCE, query_vector or None, record_geo), fetch=True)
                resolved_map[name] = new_ent[0]['entity_id']
                logger.debug(f"Created new GROUNDED entity: {name}")

        return resolved_map

    def process_inferred_relationships(self, resolved_map: Dict[str, str], relationships: List[Dict], context: Dict):
        """Creates relationship records with Cross-Verification logic."""
        source_trust = context['source_trust']
        client_id = context.get('client_id') or '00000000-0000-0000-0000-000000000000'
        uir_uid = context['uid']

        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            sub_id = resolved_map.get(rel.get('subject'))
            obj_id = resolved_map.get(rel.get('object'))
            predicate = rel.get('predicate')
            reasoning = rel.get('reasoning', 'No reasoning provided.')

            # STRICT VERB VALIDATION (Anti-Hallucination Guardrail)
            if predicate not in self.nlp.ALL_VALID_VERBS:
                logger.warning(f"Dropping hallucinated relationship predicate: '{predicate}'")
                continue

            if sub_id and obj_id and sub_id != obj_id:
                # CROSS-VERIFICATION LOGIC:
                # 1. We check if this relationship exists FOR THIS CLIENT
                existing = self.db.execute_query("""
                    SELECT relationship_id, confidence, evidence_uids
                    FROM entity_relationships
                    WHERE entity_a_id = %s AND entity_b_id = %s AND relationship_type = %s AND client_id = %s
                """, (sub_id, obj_id, predicate, client_id), fetch=True)

                base_confidence = source_trust * 0.6 # Initial trust weighted by source
                new_confidence = base_confidence

                if existing:
                    # Relationship corroborated!
                    e_uids = existing[0]['evidence_uids'] or []
                    if isinstance(e_uids, str):
                        # Convert {uuid1,uuid2} to list
                        e_uids = e_uids.strip('{}').split(',') if e_uids != '{}' else []
                    e_uids = [str(u).strip() for u in e_uids if str(u).strip()]

                    if str(uir_uid) not in e_uids:
                        e_uids.append(str(uir_uid))
                        new_confidence = min(existing[0]['confidence'] + (source_trust * 0.2), 0.98)
                    else:
                        new_confidence = existing[0]['confidence']

                    self.db.execute_query("""
                        UPDATE entity_relationships
                        SET last_confirmed = NOW(),
                            updated_at = NOW(),
                            confidence = %s,
                            mention_count = mention_count + 1,
                            evidence_count = array_length(%s::uuid[], 1),
                            evidence_uids = %s::uuid[],
                            metadata = jsonb_set(COALESCE(metadata, '{}'), '{latest_reasoning}', %s)
                        WHERE relationship_id = %s
                    """, (new_confidence, e_uids, e_uids, json.dumps(reasoning), existing[0]['relationship_id']))
                    logger.info(f"Relationship Corroborated: confidence raised to {new_confidence:.2f}")
                else:
                    # First time seeing this link
                    self.db.execute_query("""
                        INSERT INTO entity_relationships (
                            entity_a_id, entity_b_id, relationship_type, confidence,
                            mention_count, evidence_count, evidence_uids, client_id, metadata
                        ) VALUES (%s, %s, %s, %s, 1, 1, ARRAY[%s::uuid], %s, %s)
                        ON CONFLICT (entity_a_id, entity_b_id, relationship_type, client_id) DO NOTHING
                    """, (sub_id, obj_id, predicate, base_confidence, uir_uid, client_id, json.dumps({"reasoning": reasoning})))

                # Sync to Graph only if confidence > 0.5
                if new_confidence > 0.5:
                    self._sync_to_graph(sub_id, obj_id, predicate)

    def _sync_to_graph(self, sub_id, obj_id, predicate):
        """Mirrors a relationship to Apache AGE. Names travel as Cypher parameters."""
        names = self.db.execute_query("""
            SELECT
                (SELECT name FROM entities WHERE entity_id = %s) as name_a,
                (SELECT name FROM entities WHERE entity_id = %s) as name_b
        """, (sub_id, obj_id), fetch=True)[0]

        try:
            label = assert_safe_label(predicate)
        except CypherLabelError as e:
            logger.warning(f"Graph sync skipped: {e}")
            return

        cypher = (
            "MERGE (a:ENTITY {name: $name_a}) "
            "MERGE (b:ENTITY {name: $name_b}) "
            f"MERGE (a)-[r:{label}]->(b)"
        )
        try:
            self.db.execute_cypher('pia_graph', cypher, {"name_a": names['name_a'], "name_b": names['name_b']})
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

    def correlate_and_cluster(self, job, anchor_city) -> Tuple[str, List[float]]:
        """
        Finds an existing active cluster using Multi-Level Matching, or creates one.
        Returns (cluster_id, record_vector) so the caller can persist the embedding.
        """
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
                AND semantic_dna IS NOT NULL
                AND (1 - (semantic_dna <=> %s::vector)) > 0.35
                LIMIT 1
            """, (domain, job['client_id'], geo, record_vector), fetch=True)
            if existing: cid = existing[0]['cluster_id']

        if geo and not cid and (job.get('mission_keywords') or job.get('mission_category')):
            # LEVEL 2: Mission-Spatial Fallback
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
            return cid, record_vector

        # STAGE 3: Create new cluster
        title = f"Situation: {domain} activity"
        if city_name: title += f" near {city_name}"

        new_cluster = self.db.execute_query("""
            INSERT INTO intelligence_clusters (
                title, domain, status, priority, confidence, geo_centroid, uir_count, semantic_dna, client_id
            ) VALUES (
                %s, %s, 'ACTIVE', %s, 0.7, %s, 1, %s::vector, %s
            ) RETURNING cluster_id
        """, (title, domain, job['priority'], geo, record_vector or None, job['client_id']), fetch=True)

        return new_cluster[0]['cluster_id'], record_vector

    def stop(self):
        self.db.close()


if __name__ == "__main__":
    agent = AnalystAgent(name="heartbeat_analyst_v1", interval_sec=10)
    agent.run()
