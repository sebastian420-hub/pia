import psycopg2
import time
from loguru import logger
import hashlib
import uuid

def test_semantic():
    conn = psycopg2.connect(host="postgres", user="pia", password="password", database="pia")
    conn.autocommit = True
    cur = conn.cursor()
    
    logger.info("🚀 STARTING SEMANTIC RESOLUTION TEST")
    
    # Use a headline that is conceptually VERY close to SpaceX
    headline = f"The private aerospace company founded by Elon Musk announced a launch milestone {uuid.uuid4().hex[:4]}"
    summary = "The company is based in Hawthorne and reached a new orbital record today."
    content_hash = hashlib.sha256(headline.encode()).hexdigest()
    
    # We manually inject a report that will trigger the NLP engine
    cur.execute(
        """
        INSERT INTO intelligence_records (
            source_type, source_agent, source_name, source_url, content_hash,
            content_headline, content_summary, domain, priority
        ) VALUES (
            'OSINT', 'semantic_tester', 'Test Feed', 'https://test.com/semantic', %s,
            %s, %s, 'POLITICAL', 'HIGH'
        ) RETURNING uid;
        """,
        (content_hash, headline, summary)
    )
    uir_uid = cur.fetchone()[0]
    logger.info(f"Report Injected: {uir_uid}")

    logger.info("Waiting 20s for Semantic Resolution...")
    time.sleep(20)

    # Check if 'SpaceX' mention count increased
    cur.execute("SELECT mention_count FROM entities WHERE name = 'SpaceX' LIMIT 1;")
    count = cur.fetchone()[0]
    logger.success(f"SpaceX Mention Count: {count}")
    
    # Final Check: Was the UIR linked to SpaceX?
    cur.execute("SELECT name FROM entities WHERE %s = ANY(uir_refs)", (uir_uid,))
    linked_entities = cur.fetchall()
    
    if linked_entities:
        logger.success(f"✅ Semantic Match SUCCESS: Linked to {linked_entities}")
    else:
        logger.error("❌ Semantic Match FAILED: No entities linked.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    test_semantic()
