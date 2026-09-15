import os
import sys

if "--yes-really" not in sys.argv or os.getenv("PIA_ENV", "").lower() == "production":
    print(f"{os.path.basename(__file__)} deletes graph data. Re-run with --yes-really (refused when PIA_ENV=production).")
    sys.exit(2)

from pia.core.database import DatabaseManager
from loguru import logger

def clean_graph():
    db = DatabaseManager()
    
    # 1. Clean Relational Table
    logger.info("Cleaning relational entity_relationships table...")
    db.execute_query("DELETE FROM entity_relationships;")
    
    # 2. Clean Apache AGE Graph
    logger.info("Cleaning Apache AGE property graph...")
    query = """
    LOAD 'age';
    SET search_path = public, ag_catalog;
    SELECT * FROM cypher('pia_graph', $$
        MATCH (n)-[r]->(m)
        DELETE r
    $$) as (v agtype);
    """
    try:
        db.execute_query(query)
        logger.success("Graph relationships wiped successfully.")
    except Exception as e:
        logger.error(f"Graph wipe failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_graph()
