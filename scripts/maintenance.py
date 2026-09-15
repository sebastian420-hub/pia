"""Database maintenance: vacuum the hot tables and prune local entities nobody mentions."""
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from loguru import logger

from pia.core.database import DatabaseManager


def run_maintenance():
    db = DatabaseManager()
    logger.info("Maintenance: vacuum + prune")
    try:
        for table in ('intelligence_records', 'analysis_queue', 'entities', 'entity_aliases', 'mentions', 'events', 'relations'):
            db.execute_query(f"VACUUM ANALYZE {table};")
        # Local (non-Wikidata, non-GeoNames) entities that nothing references any more
        removed = db.execute_query("""
            DELETE FROM entities e
            WHERE e.qid IS NULL AND e.origin = 'llm' AND e.last_seen < NOW() - INTERVAL '30 days'
              AND NOT EXISTS (SELECT 1 FROM mentions m WHERE m.entity_id = e.entity_id)
              AND NOT EXISTS (SELECT 1 FROM events x WHERE x.actor_id = e.entity_id OR x.target_id = e.entity_id OR x.location_id = e.entity_id)
            RETURNING name
        """, fetch=True) or []
        db.execute_query("DELETE FROM resolution_cache WHERE fetched_at < NOW() - INTERVAL '30 days'")
        logger.success(f"Maintenance complete: {len(removed)} orphan entities removed")
    finally:
        db.close()


if __name__ == "__main__":
    run_maintenance()
