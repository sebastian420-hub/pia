import logging
from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_anchors():
    db = DatabaseManager()
    nlp = NLPManager()

    # The high-gravity anchors for the Epstein Files
    anchors = [
        {
            "name": "Jeffrey Epstein",
            "aliases": ["Epstein", "J. Epstein", "Jeffrey E.", "J.E."],
            "type": "PERSON",
            "description": "Deceased American financier and convicted sex offender.",
            "geo": None
        },
        {
            "name": "Ghislaine Maxwell",
            "aliases": ["Maxwell", "G. Maxwell", "Ghislaine", "G.M."],
            "type": "PERSON",
            "description": "British socialite and convicted sex offender, associate of Jeffrey Epstein.",
            "geo": None
        },
        {
            "name": "Little St. James",
            "aliases": ["Epstein Island", "LSJ", "The Island"],
            "type": "LOCATION",
            "description": "Private island in the US Virgin Islands previously owned by Jeffrey Epstein.",
            "geo": "0101000020E6100000D00F9DB697F850C0C6287A9A16462240" # POINT(-64.832 18.273) approx
        },
        {
            "name": "Lolita Express",
            "aliases": ["Epstein's Jet", "Boeing 727", "N273JE"],
            "type": "AIRCRAFT",
            "description": "Boeing 727 private jet owned by Jeffrey Epstein.",
            "geo": None
        }
    ]

    try:
        for anchor in anchors:
            # Check if it exists by checking name or aliases
            query = """
                SELECT entity_id, name FROM entities 
                WHERE name ILIKE %s OR %s = ANY(aliases)
                LIMIT 1
            """
            exists = db.execute_query(query, (anchor['name'], anchor['name']), fetch=True)

            if exists:
                eid = exists[0]['entity_id']
                logger.info(f"Anchor '{anchor['name']}' already exists. Hardening...")
                db.execute_query("""
                    UPDATE entities 
                    SET canonical_name = %s,
                        aliases = array_cat(aliases, %s::text[]),
                        confidence = 1.0,
                        watch_status = 'ACTIVE',
                        threat_score = 0.9,
                        primary_geo = %s
                    WHERE entity_id = %s
                """, (anchor['name'], anchor['aliases'], anchor['geo'], eid))
            else:
                logger.info(f"Creating new Anchor: '{anchor['name']}'...")
                embedding = nlp.generate_embedding(anchor['name'] + ". " + anchor['description'])
                db.execute_query("""
                    INSERT INTO entities (
                        name, canonical_name, aliases, entity_type, description, 
                        confidence, mention_count, watch_status, threat_score, primary_geo, embedding
                    ) VALUES (%s, %s, %s, %s, %s, 1.0, 50, 'ACTIVE', 0.9, %s, %s)
                """, (anchor['name'], anchor['name'], anchor['aliases'], anchor['type'], anchor['description'], anchor['geo'], embedding))
        
        logger.info("Epstein Anchors successfully seeded and hardened.")
        
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_anchors()
