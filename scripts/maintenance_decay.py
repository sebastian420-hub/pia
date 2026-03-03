import sys, os
from loguru import logger

sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_decay_sweep():
    db = DatabaseManager()
    
    logger.info("🧹 STARTING KNOWLEDGE GRAPH MAINTENANCE SWEEP (DECAY & PRUNE)")
    
    # 1. Decay Phase: Flag old, low-confidence rumors as invalid
    decay_query = """
        UPDATE entity_relationships 
        SET still_valid = FALSE, 
            confidence = confidence - 0.1,
            updated_at = NOW()
        WHERE confidence < 0.5 
          AND last_confirmed < NOW() - INTERVAL '7 days'
          AND still_valid = TRUE
        RETURNING relationship_id;
    """
    decayed = db.execute_query(decay_query, fetch=True)
    logger.info(f"Decayed {len(decayed)} unverified relationships (flagged as invalid).")

    # 2. Prune Phase: Delete extremely low confidence / invalid data from PostgreSQL
    prune_query = """
        DELETE FROM entity_relationships
        WHERE (confidence < 0.2 AND still_valid = FALSE)
           OR (confidence < 0.1)
        RETURNING entity_a_id, entity_b_id, relationship_type;
    """
    pruned = db.execute_query(prune_query, fetch=True)
    
    # 3. Synchronize Graph Database: Delete the edges from Apache AGE
    graph_deletions = 0
    for edge in pruned:
        try:
            # We must fetch the names to delete the edge in Cypher
            names = db.execute_query("""
                SELECT 
                    (SELECT name FROM entities WHERE entity_id = %s) as name_a,
                    (SELECT name FROM entities WHERE entity_id = %s) as name_b
            """, (edge['entity_a_id'], edge['entity_b_id']), fetch=True)[0]
            
            if names['name_a'] and names['name_b']:
                safe_a = names['name_a'].replace('"', '"')
                safe_b = names['name_b'].replace('"', '"')
                pred = edge['relationship_type']
                
                cypher_delete = f"""
                    MATCH (a:ENTITY {{name: "{safe_a}"}})-[r:{pred}]->(b:ENTITY {{name: "{safe_b}"}})
                    DELETE r
                """
                db.execute_cypher('pia_graph', cypher_delete)
                graph_deletions += 1
        except Exception as e:
            logger.warning(f"Failed to prune edge from graph: {e}")

    logger.info(f"Pruned {len(pruned)} relationships from PostgreSQL and {graph_deletions} from Apache AGE.")
    logger.success("✅ Maintenance sweep complete.")
    db.close()

if __name__ == "__main__":
    run_decay_sweep()