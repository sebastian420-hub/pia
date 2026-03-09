import logging
from pia.core.database import DatabaseManager

def check_epstein():
    try:
        db = DatabaseManager()
        results = db.execute_query("SELECT entity_id, name, mention_count FROM entities WHERE name ILIKE '%epstein%' LIMIT 5;", fetch=True)
        if results:
            print(f"Found {len(results)} entities matching 'epstein':")
            for r in results:
                print(f" - {r['name']} (Mentions: {r['mention_count']}, ID: {r['entity_id']})")
        else:
            print("No entities matching 'epstein' found in the database.")
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_epstein()
