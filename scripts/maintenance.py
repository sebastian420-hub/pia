import time
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

        # 3. Clean up old PENDING entities that never got enriched
        logger.info("   Purging stale pending entities...")
        db.execute_query("DELETE FROM entities WHERE confidence < 0.4 AND last_seen < NOW() - INTERVAL '24 hours';")

        logger.success("✅ MAINTENANCE COMPLETE: Brain optimized.")
    except Exception as e:
        logger.error(f"Maintenance failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    run_maintenance()
