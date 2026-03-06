import os
import sys
import json
from loguru import logger

# Add src to path so we can import the database manager
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager
from pia.core.nlp import NLPManager

# ---------------------------------------------------------
# TARGET DECK DEFINITION
# ---------------------------------------------------------
# This is our pre-knowledge. If the AI sees these aliases in the news, 
# it will instantly map them to these master entities and their coordinates.
TARGET_DECK = [
    {
        "name": "Elon Musk",
        "entity_type": "PERSON",
        "aliases": ["Elon", "Musk", "Tesla CEO", "SpaceX CEO", "Elon Reeve Musk"],
        "description": "CEO of SpaceX and Tesla. High-value strategic individual.",
        "threat_score": 0.3, # Influential, not inherently a kinetic threat
        "lat": 30.2215, # Boca Chica / Starbase (Rough anchor)
        "lon": -97.6253 # Austin HQ
    },
    {
        "name": "SpaceX",
        "entity_type": "ORGANIZATION",
        "aliases": ["Space Exploration Technologies Corp", "Starlink"],
        "description": "American aerospace manufacturer and space transport services company.",
        "threat_score": 0.4,
        "lat": 33.9207, # Hawthorne, CA HQ
        "lon": -118.3278
    },
    {
        "name": "The Pentagon",
        "entity_type": "INFRASTRUCTURE",
        "aliases": ["DoD", "Department of Defense", "US Military Headquarters"],
        "description": "Headquarters of the United States Department of Defense.",
        "threat_score": 0.8,
        "lat": 38.8719,
        "lon": -77.0563
    },
    {
        "name": "Kremlin",
        "entity_type": "INFRASTRUCTURE",
        "aliases": ["Russian Government", "Putin Administration", "Moscow HQ"],
        "description": "Executive headquarters of the Russian Federation.",
        "threat_score": 0.9,
        "lat": 55.7520,
        "lon": 37.6175
    },
    {
        "name": "TSMC",
        "entity_type": "ORGANIZATION",
        "aliases": ["Taiwan Semiconductor Manufacturing Company", "Taiwan Semiconductor"],
        "description": "World's most valuable semiconductor company. Critical global supply chain node.",
        "threat_score": 0.5,
        "lat": 24.7736, # Hsinchu Science Park
        "lon": 121.0116
    }
]

def seed_target_deck():
    logger.info("Initializing Target Deck Seeding Sequence...")
    db = DatabaseManager()
    nlp = NLPManager()

    success_count = 0

    for target in TARGET_DECK:
        # Generate embedding for the canonical name so the AI can match it semantically later
        embedding = nlp.generate_embedding(target["name"])
        
        # Check if it already exists
        exists = db.execute_query(
            "SELECT entity_id FROM entities WHERE name = %s", 
            (target["name"],), 
            fetch=True
        )

        if exists:
            logger.info(f"Target '{target['name']}' already exists. Updating aliases and coordinates...")
            query = """
                UPDATE entities 
                SET aliases = %s, 
                    description = %s, 
                    threat_score = %s,
                    primary_geo = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    embedding = %s::vector
                WHERE name = %s
            """
            db.execute_query(query, (
                target["aliases"], target["description"], target["threat_score"],
                target["lon"], target["lat"], embedding, target["name"]
            ))
            success_count += 1
        else:
            logger.info(f"Injecting new Target: {target['name']}")
            query = """
                INSERT INTO entities (
                    entity_type, name, aliases, description, threat_score, watch_status,
                    primary_geo, embedding
                ) VALUES (
                    %s, %s, %s, %s, %s, 'MONITORING',
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s::vector
                )
            """
            db.execute_query(query, (
                target["entity_type"], target["name"], target["aliases"], target["description"],
                target["threat_score"], target["lon"], target["lat"], embedding
            ))
            success_count += 1

    logger.info(f"Seeding complete. {success_count} Strategic Targets injected into the Knowledge Graph.")

if __name__ == "__main__":
    seed_target_deck()