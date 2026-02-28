import psycopg2
from faker import Faker
import random
import time
from loguru import logger
import hashlib

def stress_test(num_records=100):
    fake = Faker()
    conn = psycopg2.connect(host="postgres", user="pia", password="password", database="pia")
    conn.autocommit = True
    cur = conn.cursor()
    
    logger.info(f"Injecting {num_records} synthetic OSINT records to stress test the Analyst Agents...")
    
    entities = ["Elon Musk", "SpaceX", "Donald Trump", "Google", "Palantir Technologies", "Taiwan", "Joe Biden"]
    
    for i in range(num_records):
        entity = random.choice(entities)
        action = random.choice(["announced a new partnership with", "denied allegations regarding", "was seen visiting", "published a report on"])
        headline = f"BREAKING: {entity} {action} {fake.company()}"
        summary = fake.paragraph(nb_sentences=3)
        
        normalized_content = (headline + summary).lower().strip()
        content_hash = hashlib.sha256(normalized_content.encode('utf-8')).hexdigest()
        
        try:
            cur.execute(
                """
                INSERT INTO intelligence_records (
                    source_type, source_agent, source_name, source_url, content_hash,
                    content_headline, content_summary, domain, priority, confidence
                ) VALUES (
                    'OSINT', 'stress_test_bot', 'Synthetic Feed', %s, %s,
                    %s, %s, 'POLITICAL', 'NORMAL', 0.5
                ) ON CONFLICT (content_hash) DO NOTHING;
                """,
                (fake.url(), content_hash, headline, summary)
            )
        except Exception as e:
            logger.error(f"Insert failed: {e}")
            
    logger.success(f"Injection complete. Monitor the analysis_queue to observe the swarm.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    stress_test(50)  # Inject 50 records rapidly
