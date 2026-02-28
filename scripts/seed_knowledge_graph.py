import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

from pia.ingestion.wikidata_ingestor import WikidataIngestor
from loguru import logger

def main():
    logger.info("Starting Knowledge Graph Seeding (Mini-Batch)...")
    ingestor = WikidataIngestor()
    
    # 1. Ingest Entities
    entity_file = os.path.join(ingestor.data_dir, "wikidata5m_entity.txt")
    ingestor.ingest_entities(entity_file)
    
    # 2. Ingest Relationships
    rel_file = os.path.join(ingestor.data_dir, "wikidata5m_truth.txt")
    ingestor.ingest_relationships(rel_file)
    
    # 3. Sync to Graph (Apache AGE)
    ingestor.sync_to_age_graph()
    
    logger.success("Knowledge Graph seeding completed successfully.")

if __name__ == "__main__":
    main()
