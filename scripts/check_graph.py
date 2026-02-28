from pia.core.database import DatabaseManager
from loguru import logger

def check_graph():
    db = DatabaseManager()
    query = """
    LOAD 'age';
    SET search_path = public, ag_catalog;
    SELECT * FROM cypher('pia_graph', $$
        MATCH (n)-[r]->(m)
        RETURN n.name, type(r), m.name
    $$) as (subject agtype, predicate agtype, object agtype);
    """
    try:
        results = db.execute_query(query, fetch=True)
        if not results:
            logger.warning("Graph is empty or no relationships found.")
        else:
            logger.success(f"Found {len(results)} relationships in the AGE graph:")
            for row in results:
                print(f"{row['subject']} --[{row['predicate']}]--> {row['object']}")
    except Exception as e:
        logger.error(f"Graph query failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_graph()
