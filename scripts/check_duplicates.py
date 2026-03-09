import logging
from pia.core.database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_duplicate_entities():
    db = DatabaseManager()
    try:
        # Search for common variations of United States
        query = """
            SELECT entity_id, name, aliases, mention_count, watch_status
            FROM entities 
            WHERE name ILIKE ANY(ARRAY['%%united states%%', '%%usa%%', '%%us%%', '%%u.s.%%'])
            ORDER BY mention_count DESC
            LIMIT 20;
        """
        results = db.execute_query(query, fetch=True)
        
        print("\n--- POTENTIAL DUPLICATES FOUND ---")
        if results:
            for r in results:
                # Basic filter to avoid matching "Just" or "House"
                name = r['name'].upper()
                if name in ['UNITED STATES', 'USA', 'US', 'U.S.', 'UNITED STATES OF AMERICA']:
                    print(f"ID: {r['entity_id']} | Name: {r['name']} | Mentions: {r['mention_count']} | Aliases: {r.get('aliases')}")
        else:
            print("No immediate matches found.")
            
    except Exception as e:
        logger.error(f"Database error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_duplicate_entities()
