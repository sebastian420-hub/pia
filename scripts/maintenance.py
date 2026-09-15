from loguru import logger
import sys
import os

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_maintenance():
    db = DatabaseManager()
    logger.info("🛠️ STARTING SYSTEM MAINTENANCE: Optimizing Brain Integrity")
    
    try:
        # 1. Clear AGE Cache Leaks (Checkpoints flush memory buffers)
        logger.info("   Executing Database Checkpoint...")
        db.execute_query("CHECKPOINT;")
        
        # 2. Re-index and Vacuum (Crucial for high-velocity Timescale and Graph tables)
        logger.info("   Performing VACUUM ANALYZE on core tables...")
        tables = [
            'intelligence_records', 
            'analysis_queue', 
            'entities', 
            'entity_relationships',
            'intelligence_clusters'
        ]
        for table in tables:
            db.execute_query(f"VACUUM ANALYZE {table};")
            logger.info(f"      Optimized: {table}")

        # 3. Purge only true orphans: entities no record references and that hold
        #    no relationships. (The old rule deleted every analyst-created entity
        #    under confidence 0.4 after 24h, cascading their relationships.)
        logger.info("   Purging orphan entities...")
        orphans = db.execute_query("""
            DELETE FROM entities e
            WHERE e.entity_type <> 'LOCATION'
              AND COALESCE(array_length(e.uir_refs, 1), 0) = 0
              AND e.last_seen < NOW() - INTERVAL '7 days'
              AND NOT EXISTS (SELECT 1 FROM entity_relationships r
                              WHERE r.entity_a_id = e.entity_id OR r.entity_b_id = e.entity_id)
            RETURNING name
        """, fetch=True) or []
        # Keep the AGE graph in step with the tables.
        for row in orphans:
            try:
                db.execute_cypher('pia_graph', "MATCH (n:ENTITY {name: $name}) DETACH DELETE n", {"name": row['name']})
            except Exception as e:
                logger.warning(f"      Graph cleanup failed for {row['name']}: {e}")
        logger.info(f"      Removed {len(orphans)} orphan entities.")

        logger.success("✅ MAINTENANCE COMPLETE: Brain optimized.")
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_maintenance()
