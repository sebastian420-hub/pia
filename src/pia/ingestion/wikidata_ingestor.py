from loguru import logger
import os
import requests
import tarfile
from typing import Dict, List, Optional
import psycopg2
import psycopg2.extras

from pia.core.database import DatabaseManager

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
        # URLs for Wikidata5M (Subset from TransE/KE models)
        url = "https://deepgraphlearning.github.io/project/wikidata5m"
        logger.info(f"Please ensure you have downloaded the Wikidata5M TSV files to {self.data_dir}")
        # Note: In a full implementation, we would automate the download from a reliable mirror

    def ingest_entities(self, file_path: str):
        """
        Streams entity descriptions and performs bulk COPY into public.entities.
        Matches Wikidata5M format: <QID> \t <Label> \t <Description>
        """
        if not os.path.exists(file_path):
            logger.error(f"Entity file not found: {file_path}")
            return

        logger.info(f"Starting entity ingestion from {file_path}")
        
        # Use a temporary file to store formatted data for COPY
        temp_buffer_path = "/tmp/entity_buffer.tsv"
        batch_size = 50000
        count = 0

        with open(file_path, 'r', encoding='utf-8') as f_in:
            with open(temp_buffer_path, 'w', encoding='utf-8') as f_out:
                for line in f_in:
                    parts = line.strip().split('\t')
                    if len(parts) < 2:
                        continue
                    
                    qid = parts[0]
                    name = parts[1]
                    desc = parts[2] if len(parts) > 2 else ""
                    
                    # 1. Plan Constraint: Filter noise (Must have label)
                    if not name:
                        continue

                    # 2. Map to our entities schema format:
                    # entity_type, name, aliases, description, metadata
                    # We default to 'ORGANIZATION' for the general seed, to be refined by properties
                    f_out.write(f"ORGANIZATION\t{name}\t{{}}\t{desc}\t{{\"wikidata_id\": \"{qid}\"}}\n")
                    count += 1

                    if count % batch_size == 0:
                        self._flush_buffer(temp_buffer_path)
                        logger.info(f"Ingested {count} entities...")
                        # Reset the buffer file
                        f_out.seek(0)
                        f_out.truncate()

                # Flush remaining
                if count % batch_size != 0:
                    self._flush_buffer(temp_buffer_path)
        
        logger.success(f"Total entities ingested: {count}")

    def _flush_buffer(self, buffer_path: str):
        """Executes the PostgreSQL COPY command for the current buffer."""
        conn = self.db.get_connection()
        with conn.cursor() as cur:
            with open(buffer_path, 'r', encoding='utf-8') as f:
                cur.copy_from(f, 'entities', sep='\t', 
                             columns=('entity_type', 'name', 'aliases', 'description', 'metadata'))
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
        conn = self.db.get_connection()
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
        node_query = """
            SELECT * FROM cypher('pia_graph', $$
                MATCH (v) RETURN count(v)
            $$) as (count agtype);
        """
        
        # In a real large-scale sync, we'd batch this. 
        # For the MVP, we'll sync relationships that have been added.
        rel_query = """
            SELECT a.name as name_a, b.name as name_b, r.relationship_type
            FROM entity_relationships r
            JOIN entities a ON r.entity_a_id = a.entity_id
            JOIN entities b ON r.entity_b_id = b.entity_id
            LIMIT 1000; -- Sync in chunks for the MVP
        """
        
        conn = self.db.get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(rel_query)
            rels = cur.fetchall()
            
            for row in rels:
                # Use Cypher to MERGE nodes and CREATE edges
                cypher = f"""
                    SELECT * FROM cypher('pia_graph', $$
                        MERGE (a:ENTITY {{name: "{row['name_a']}"}})
                        MERGE (b:ENTITY {{name: "{row['name_b']}"}})
                        MERGE (a)-[r:{row['relationship_type']}]->(b)
                    $$) as (v agtype);
                """
                try:
                    cur.execute(cypher)
                except Exception as e:
                    logger.warning(f"Failed to sync graph edge: {e}")
        
        conn.commit()
        logger.success("Graph synchronization complete.")

if __name__ == "__main__":
    ingestor = WikidataIngestor()
    logger.info("Wikidata Ingestor initialized.")
