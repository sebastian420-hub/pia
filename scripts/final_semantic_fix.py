from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager
from loguru import logger

def final_fix():
    db = DatabaseManager()
    nlp = NLPManager()
    
    phrase = "The private American aerospace firm founded by Elon Musk"
    logger.info(f"Comparing: '{phrase}'")
    
    vec = nlp.generate_embedding(phrase)
    
    # 1. Check SpaceX similarity specifically
    spacex = db.execute_query("""
        SELECT name, (1 - (embedding <=> %s::vector)) as similarity
        FROM entities
        WHERE name = 'SpaceX' AND embedding IS NOT NULL
        LIMIT 1;
    """, (vec,), fetch=True)
    
    if spacex:
        logger.info(f"SpaceX Similarity: {spacex[0]['similarity']:.4f}")
    
    # 2. See what is actually winning
    top = db.execute_query("""
        SELECT name, entity_type, (1 - (embedding <=> %s::vector)) as similarity
        FROM entities
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT 3;
    """, (vec, vec), fetch=True)
    
    logger.info("Top Winners:")
    for t in top:
        logger.info(f"- {t['name']} ({t['entity_type']}): {t['similarity']:.4f}")

    db.close()

if __name__ == "__main__":
    final_fix()
