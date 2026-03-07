import os
import sys
import psycopg2
import uuid
import time
from psycopg2.extras import execute_batch

# Connect to database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "pia")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "pia")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )

def seed_wikidata():
    print("Starting Wikidata5m seed process...")
    # NOTE: In a real environment, this script would download the gigabytes of Wikidata5m files
    # and stream-parse them. For demonstration, we'll insert a few core strategic entities.
    
    entities_to_seed = [
        ("Q30", "United States of America", "GPE", "A country in North America", 0.9),
        ("Q148", "People's Republic of China", "GPE", "A country in East Asia", 0.95),
        ("Q159", "Russia", "GPE", "A transcontinental country spanning Eastern Europe and Northern Asia", 0.95),
        ("Q37084", "Vladimir Putin", "PERSON", "President of Russia", 0.95),
        ("Q1124", "Bill Clinton", "PERSON", "42nd president of the United States", 0.5),
        ("Q9696", "John F. Kennedy", "PERSON", "35th president of the United States", 0.5),
        ("Q190094", "George W. Bush", "PERSON", "43rd president of the United States", 0.5),
        ("Q76", "Barack Obama", "PERSON", "44th president of the United States", 0.5),
        ("Q6279", "Joe Biden", "PERSON", "46th president of the United States", 0.5),
        ("Q22686", "Donald Trump", "PERSON", "45th and 47th president of the United States", 0.8),
        ("Q132050", "Kamala Harris", "PERSON", "49th vice president of the United States", 0.7),
        ("Q37230", "Federal Bureau of Investigation", "ORGANIZATION", "Civilian intelligence and security service of the United States", 0.85),
        ("Q151035", "National Security Agency", "ORGANIZATION", "National-level intelligence agency of the United States Department of Defense", 0.9),
        ("Q432283", "KGB", "ORGANIZATION", "Main security agency for the Soviet Union from 1954 until its break-up in 1991", 0.8),
        ("Q31843", "FSB", "ORGANIZATION", "Principal security agency of Russia and the main successor agency to the Soviet Union's KGB", 0.9)
    ]

    conn = get_connection()
    cursor = conn.cursor()
    
    insert_sql = """
        INSERT INTO entities (
            entity_id, 
            name, 
            canonical_name, 
            entity_type, 
            description, 
            confidence, 
            threat_score, 
            watch_status
        ) VALUES (
            %s, %s, %s, %s, %s, 1.0, %s, 'ACTIVE'
        ) ON CONFLICT (name) DO NOTHING;
    """
    
    batch_data = []
    for qid, name, entity_type, description, threat_score in entities_to_seed:
        entity_id = str(uuid.uuid4())
        batch_data.append((entity_id, name, name, entity_type, description, threat_score))
        
    try:
        print(f"Inserting {len(batch_data)} core Wikidata entities...")
        execute_batch(cursor, insert_sql, batch_data)
        conn.commit()
        print("Seed complete!")
    except Exception as e:
        print(f"Error seeding Wikidata: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    seed_wikidata()