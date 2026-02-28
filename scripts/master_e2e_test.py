import psycopg2
import time
from loguru import logger
import hashlib
import uuid

def run_master_test():
    conn = psycopg2.connect(host="postgres", user="pia", password="password", database="pia")
    conn.autocommit = True
    cur = conn.cursor()
    
    logger.info("🚀 STARTING MASTER E2E TEST: 'The Boca Chica Flight'")
    
    # 1. SET MISSION
    mission_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO mission_focus (focus_id, category, keywords, is_active) VALUES (%s, 'TECH', ARRAY['Starship', 'Launch'], TRUE)",
        (mission_id,)
    )
    logger.info(f"Step 1: Mission Created ({mission_id})")

    # 2. INJECT INTELLIGENCE (UIR)
    headline = f"TEST: Starship Launch Detected at Boca Chica {uuid.uuid4().hex[:4]}"
    summary = "A massive rocket engine ignition was detected at the SpaceX facility."
    content_hash = hashlib.sha256(headline.encode()).hexdigest()
    
    cur.execute(
        """
        INSERT INTO intelligence_records (
            source_type, source_agent, source_name, source_url, content_hash,
            content_headline, content_summary, domain, priority, mission_id, geo
        ) VALUES (
            'OSINT', 'e2e_tester', 'Test Feed', 'https://test.com', %s,
            %s, %s, 'POLITICAL', 'HIGH', %s, ST_SetSRID(ST_MakePoint(-97.15, 25.99), 4326)
        ) RETURNING uid;
        """,
        (content_hash, headline, summary, mission_id)
    )
    uir_uid = cur.fetchone()[0]
    logger.info(f"Step 2: Intelligence Injected (UIR: {uir_uid})")

    # 3. WAIT FOR ANALYSIS SWARM
    logger.info("Step 3: Waiting 20s for Analyst Swarm to fuse intelligence...")
    time.sleep(20)

    # 4. VERIFY RESULTS
    # A. Check Queue Status
    cur.execute("SELECT status, assigned_agent FROM analysis_queue WHERE uir_uid = %s", (uir_uid,))
    q_status = cur.fetchone()
    if q_status and q_status[0] == 'DONE':
        logger.success(f"✅ Analysis Verified: Processed by {q_status[1]}")
    else:
        logger.error(f"❌ Analysis Failed: Status is {q_status}")

    # B. Check Clustering (Spatial Join)
    cur.execute("SELECT cluster_id FROM intelligence_records WHERE uid = %s", (uir_uid,))
    cluster_id = cur.fetchone()[0]
    if cluster_id:
        cur.execute("SELECT title FROM intelligence_clusters WHERE cluster_id = %s", (cluster_id,))
        title = cur.fetchone()[0]
        logger.success(f"✅ Clustering Verified: Attached to '{title}'")
    else:
        logger.error("❌ Clustering Failed: No cluster attached.")

    # C. Check Entity Extraction (Knowledge Graph)
    cur.execute("SELECT name FROM entities WHERE %s = ANY(uir_refs)", (uir_uid,))
    entities = cur.fetchall()
    if entities:
        names = [e[0] for e in entities]
        logger.success(f"✅ Knowledge Graph Verified: Extracted {names}")
    else:
        logger.warning("⚠️ Entity extraction returned 0 matches (check LLM availability).")

    logger.info("🏁 MASTER E2E TEST COMPLETE")
    cur.close()
    conn.close()

if __name__ == "__main__":
    run_master_test()
