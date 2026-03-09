import logging
from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_us_embedding():
    db = DatabaseManager()
    nlp = NLPManager()
    
    try:
        # Find the United States entity
        logger.info("Searching for 'United States' in the Knowledge Graph...")
        entity = db.execute_query("SELECT entity_id, name, description FROM entities WHERE name ILIKE 'United States' OR 'United States' = ANY(aliases) LIMIT 1", fetch=True)
        
        if entity:
            eid = entity[0]['entity_id']
            name = entity[0]['name']
            desc = entity[0]['description'] or ''
            
            logger.info(f"Found: {name} ({eid})")
            
            # Combine name and description for a richer semantic vector
            text_to_embed = f"{name}. {desc}".strip()
            
            logger.info("Generating new text-embedding-3-small vector...")
            new_embedding = nlp.generate_embedding(text_to_embed)
            
            if new_embedding:
                db.execute_query("UPDATE entities SET embedding = %s WHERE entity_id = %s", (new_embedding, eid))
                logger.info("Successfully updated semantic embedding for 'United States'.")
            else:
                logger.error("Failed to generate embedding via API.")
        else:
            logger.error("Entity 'United States' not found in the database.")
            
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    update_us_embedding()
