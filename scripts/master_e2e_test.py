import time
from loguru import logger
import hashlib
import uuid
import sys
import os

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_master_test():
    db = DatabaseManager()
    
    logger.info("🚀 STARTING MASTER E2E TEST: 'The Boca Chica Flight'")
    
    # 1. SET MISSION
    mission_id = str(uuid.uuid4())
    db.execute_query(
        "INSERT INTO mission_focus (focus_id, category, keywords, is_active) VALUES (%s, 'TECH', ARRAY['Starship', 'Launch'], TRUE)",
        (mission_id,)
    )
    logger.info(f"Step 1: Mission Created ({mission_id})")

    # 2. INJECT INTELLIGENCE (UIR)
    headline = f"TEST: Starship Launch Detected at Boca Chica {uuid.uuid4().hex[:4]}"
    summary = "A massive rocket engine ignition was detected at the SpaceX facility."
    content_hash = hashlib.sha256(headline.encode()).hexdigest()
    
    uir_results = db.execute_query(
        """
        INSERT INTO intelligence_records (
            source_type, source_agent, source_name, source_url, content_hash,
            content_headline, content_summary, domain, priority, mission_id, geo
        ) VALUES (
            'OSINT', 'e2e_tester', 'Test Feed', 'https://test.com', %s,
            %s, %s, 'POLITICAL', 'HIGH', %s, ST_SetSRID(ST_MakePoint(-97.15, 25.99), 4326)
        ) RETURNING uid;
        """,
        (content_hash, headline, summary, mission_id),
        fetch=True
    )
    uir_uid = uir_results[0]['uid']
    logger.info(f"Step 2: Intelligence Injected (UIR: {uir_uid})")

    # 3. WAIT FOR ANALYSIS SWARM
    logger.info("Step 3: Waiting up to 30s for Analyst Swarm to fuse intelligence...")
    
    max_retries = 15
    processed = False
    for i in range(max_retries):
        q_status = db.execute_query("SELECT status, assigned_agent FROM analysis_queue WHERE uir_uid = %s", (uir_uid,), fetch=True)
        if q_status and q_status[0]['status'] == 'DONE':
            logger.success(f"✅ Analysis Verified: Processed by {q_status[0]['assigned_agent']} (at retry {i})")
            processed = True
            break
        elif q_status and q_status[0]['status'] == 'FAILED':
            logger.error(f"❌ Analysis FAILED: {q_status[0].get('error_message')}")
            break
        time.sleep(2)

    if not processed:
        logger.error("❌ E2E timeout: Job never reached DONE status.")

    # 4. VERIFY RESULTS
    if processed:
        # A. Check Clustering (Spatial Join)
        cluster_res = db.execute_query("SELECT cluster_id FROM intelligence_records WHERE uid = %s", (uir_uid,), fetch=True)
        cluster_id = cluster_res[0]['cluster_id']
        if cluster_id:
            title_res = db.execute_query("SELECT title FROM intelligence_clusters WHERE cluster_id = %s", (cluster_id,), fetch=True)
            title = title_res[0]['title']
            logger.success(f"✅ Clustering Verified: Attached to '{title}'")
        else:
            logger.error("❌ Clustering Failed: No cluster attached.")

        # B. Check Entity Extraction (Knowledge Graph)
        entities = db.execute_query("SELECT name FROM entities WHERE %s = ANY(uir_refs)", (uir_uid,), fetch=True)
        if entities:
            names = [e['name'] for e in entities]
            logger.success(f"✅ Knowledge Graph Verified: Extracted {names}")
        else:
            logger.warning("⚠️ Entity extraction returned 0 matches (check LLM availability).")

    logger.info("🏁 MASTER E2E TEST COMPLETE")
    db.close()

if __name__ == "__main__":
    run_master_test()
