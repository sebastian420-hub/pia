from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager
from loguru import logger

def diagnose():
    db = DatabaseManager()
    nlp = NLPManager()
    
    test_phrase = "Hawthorne rocket manufacturer"
    logger.info(f"Diagnosing semantic match for: '{test_phrase}'")
    
    vector = nlp.generate_embedding(test_phrase)
    
    if not vector:
        logger.error("Failed to generate embedding for test phrase.")
        return

    # Direct Vector Search
    results = db.execute_query("""
        SELECT entity_id, name, entity_type, (1 - (embedding <=> %s::vector)) as similarity
        FROM entities
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT 5
    """, (vector, vector), fetch=True)
    
    logger.info("Top Semantic Matches in Database:")
    for r in results:
        logger.info(f"- {r['name']} ({r['entity_type']}): {r['similarity']:.4f}")

    db.close()

if __name__ == "__main__":
    diagnose()
