import json
import os
from typing import List

from loguru import logger
from psycopg2.extras import execute_values

from pia.core.database import DatabaseManager, assert_safe_label, CypherLabelError

class WikidataIngestor:
    """
    Handles the ingestion of the Wikidata5M dataset into the PIA Knowledge Graph.
    """

    # Mapping of common Wikidata properties to PIA relationship types
    PROPERTY_MAP = {
        "P17": "COUNTRY",
        "P131": "LOCATED_IN",
        "P127": "OWNED_BY",
        "P159": "HEADQUARTERED_IN",
        "P31": "INSTANCE_OF",
        "P361": "PART_OF",
        "P138": "NAMED_AFTER",
        "P607": "CONFLICT",
        "P108": "EMPLOYER",
        "P463": "MEMBER_OF",
        "P241": "MILITARY_BRANCH",
        "P137": "OPERATOR",
        "P355": "SUBSIDIARY",
        "P126": "MAINTAINED_BY",
        "P749": "PARENT_ORGANIZATION"
    }

    def __init__(self):
        self.db = DatabaseManager()
        self.data_dir = "data/wikidata"
        os.makedirs(self.data_dir, exist_ok=True)

    def download_wikidata5m(self):
        """Downloads the core Wikidata5M dataset."""
        # Dataset page: https://deepgraphlearning.github.io/project/wikidata5m
        logger.info(f"Please ensure you have downloaded the Wikidata5M TSV files to {self.data_dir}")
        # Note: In a full implementation, we would automate the download from a reliable mirror

    def ingest_entities(self, file_path: str, entity_type: str = "UNKNOWN"):
        """
        Streams entity descriptions and bulk-inserts them into public.entities.
        Matches Wikidata5M format: <QID> \t <Label> \t <Description>

        The dataset does not carry a type, so rows are stored as UNKNOWN (honest)
        rather than ORGANIZATION. Names/descriptions go through parameter binding,
        so tabs, backslashes and quotes in labels are safe.
        """
        if not os.path.exists(file_path):
            logger.error(f"Entity file not found: {file_path}")
            return

        logger.info(f"Starting entity ingestion from {file_path}")
        batch_size = 5000
        batch = []
        count = 0

        with open(file_path, 'r', encoding='utf-8') as f_in:
            for line in f_in:
                parts = line.rstrip('\n').split('\t')
                if len(parts) < 2 or not parts[1]:
                    continue
                qid, name = parts[0], parts[1]
                desc = parts[2] if len(parts) > 2 else ""
                batch.append((entity_type, name, desc, json.dumps({"wikidata_id": qid})))
                count += 1
                if len(batch) >= batch_size:
                    self._flush_batch(batch)
                    batch = []
                    logger.info(f"Ingested {count} entities...")
            if batch:
                self._flush_batch(batch)

        logger.success(f"Total entities ingested: {count}")

    def _flush_batch(self, batch: List[tuple]):
        """Bulk insert with an explicit commit (the pooled connection is not in autocommit)."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    "INSERT INTO entities (entity_type, name, description, metadata) VALUES %s "
                    "ON CONFLICT DO NOTHING",
                    batch,
                    template="(%s, %s, %s, %s::jsonb)",
                )
            conn.commit()

    def ingest_relationships(self, file_path: str):
        """
        Streams relationship triples and populates public.entity_relationships.
        Format: <Subject_QID> \t <Property_PID> \t <Object_QID>
        """
        if not os.path.exists(file_path):
            logger.error(f"Relationship file not found: {file_path}")
            return

        logger.info(f"Starting relationship ingestion from {file_path}")
        
        batch_size = 10000
        buffer = []
        count = 0

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) < 3:
                    continue
                
                sub_qid, pid, obj_qid = parts[0], parts[1], parts[2]
                
                # Only process properties we care about (Plan Step 1)
                rel_type = self.PROPERTY_MAP.get(pid)
                if not rel_type:
                    continue

                buffer.append((sub_qid, obj_qid, rel_type))
                count += 1

                if len(buffer) >= batch_size:
                    self._process_rel_batch(buffer)
                    buffer = []
                    logger.info(f"Processed {count} relationships...")

            if buffer:
                self._process_rel_batch(buffer)

        logger.success(f"Total relationships ingested: {count}")

    def _process_rel_batch(self, batch: List):
        """Resolves UUIDs and inserts relationship records."""
        query = """
            INSERT INTO entity_relationships (entity_a_id, entity_b_id, relationship_type, confidence)
            SELECT a.entity_id, b.entity_id, %s, 0.9
            FROM entities a, entities b
            WHERE a.metadata->>'wikidata_id' = %s 
            AND b.metadata->>'wikidata_id' = %s
            ON CONFLICT DO NOTHING;
        """
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                for sub_qid, obj_qid, rel_type in batch:
                    cur.execute(query, (rel_type, sub_qid, obj_qid))
            conn.commit()

    def sync_to_age_graph(self):
        """
        Mirror relationship table data into the Apache AGE property graph.
        """
        logger.info("Synchronizing relationships to Apache AGE graph...")
        
        # 1. Create Nodes (Vertices) for all entities not yet in the graph
        # We use cypher's MERGE to ensure idempotency
        # (Simplified for the fix)
        
        # In a real large-scale sync, we'd batch this. 
        # For the MVP, we'll sync relationships that have been added.
        rel_query = """
            SELECT a.name as name_a, b.name as name_b, r.relationship_type
            FROM entity_relationships r
            JOIN entities a ON r.entity_a_id = a.entity_id
            JOIN entities b ON r.entity_b_id = b.entity_id
            LIMIT 1000; -- Sync in chunks for the MVP
        """
        
        rels = self.db.execute_query(rel_query, fetch=True)
        if not rels:
            return

        for row in rels:
            # Names are Cypher parameters; only the validated label is formatted in.
            try:
                label = assert_safe_label(row['relationship_type'])
            except CypherLabelError as e:
                logger.warning(f"Skipping edge: {e}")
                continue
            cypher = (
                "MERGE (a:ENTITY {name: $name_a}) "
                "MERGE (b:ENTITY {name: $name_b}) "
                f"MERGE (a)-[r:{label}]->(b)"
            )
            try:
                self.db.execute_cypher('pia_graph', cypher, {"name_a": row['name_a'], "name_b": row['name_b']})
            except Exception as e:
                logger.warning(f"Failed to sync graph edge: {e}")
        
        logger.success("Graph synchronization complete.")

if __name__ == "__main__":
    ingestor = WikidataIngestor()
    logger.info("Wikidata Ingestor initialized.")
