from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager
from loguru import logger
import json

def populate_embeddings():
    db = DatabaseManager()
    nlp = NLPManager()
    
    # 1. Fetch entities without embeddings
    # We focus on seeded core entities first
    entities = db.execute_query("""
        SELECT entity_id, name, entity_type, description 
        FROM entities 
        WHERE embedding IS NULL 
        OR entity_type = 'ORGANIZATION'
        LIMIT 100;
    """, fetch=True)
    
    if not entities:
        logger.info("No entities found requiring embeddings.")
        return

    logger.info(f"Generating embeddings for {len(entities)} entities...")
    
    for ent in entities:
        # We embed with type context for better semantic resolution
        text_to_embed = f"Entity Name: {ent['name']}, Type: {ent['entity_type']}, Description: {ent['description'] or 'N/A'}"
        vector = nlp.generate_embedding(text_to_embed)
        
        if vector:
            db.execute_query(
                "UPDATE entities SET embedding = %s WHERE entity_id = %s",
                (vector, ent['entity_id'])
            )
            logger.debug(f"Embedded: {ent['name']}")
            
    logger.success("Core Knowledge Graph now has a semantic scent.")
    db.close()

if __name__ == "__main__":
    populate_embeddings()
