import uuid, hashlib, sys, os, time
from loguru import logger

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_target_test():
    db = DatabaseManager()
    
    logger.info("🎯 STARTING TARGET TEST: 'The Trump Directive'")
    
    # 1. SET STRATEGIC MISSION
    mission_id = str(uuid.uuid4())
    db.execute_query(
        """
        INSERT INTO mission_focus (focus_id, category, keywords, target_entities, is_active) 
        VALUES (%s, 'POLITICAL', ARRAY['Mar-a-Lago', 'President', 'Palm Beach'], ARRAY['Donald Trump'], TRUE)
        """,
        (mission_id,)
    )
    logger.info(f"Step 1: Mission Activated (ID: {mission_id})")

    # 2. INJECT INTELLIGENCE SIGNAL
    headline = f"Former President Trump spotted at Mar-a-Lago event {uuid.uuid4().hex[:4]}"
    summary = "Donald Trump held a high-level briefing in Palm Beach today regarding new policy directions. Several associates were present."
    content_hash = hashlib.sha256(headline.encode()).hexdigest()
    
    # We use Mar-a-Lago coordinates (~26.67, -80.03)
    uir_results = db.execute_query(
        """
        INSERT INTO intelligence_records (
            source_type, source_agent, source_name, content_hash,
            content_headline, content_summary, domain, priority, mission_id, geo
        ) VALUES (
            'OSINT', 'target_tester', 'Field Report', %s,
            %s, %s, 'POLITICAL', 'HIGH', %s, ST_SetSRID(ST_MakePoint(-80.03, 26.67), 4326)
        ) RETURNING uid;
        """,
        (content_hash, headline, summary, mission_id),
        fetch=True
    )
    uir_uid = uir_results[0]['uid']
    logger.info(f"Step 2: Signal Injected (UIR: {uir_uid}) at Mar-a-Lago")

    # 3. MONITOR BRAIN ACTIVITY
    logger.info("Step 3: Waiting for Analyst Swarm to process target...")
    
    max_wait = 30
    for i in range(max_wait // 2):
        q_status = db.execute_query("SELECT status FROM analysis_queue WHERE uir_uid = %s", (uir_uid,), fetch=True)
        if q_status and q_status[0]['status'] == 'DONE':
            logger.success("✅ Brain Processed Signal.")
            break
        time.sleep(2)

    # 4. AUDIT DISCOVERY
    logger.info("--- TARGET AUDIT RESULTS ---")
    
    # A. Entity Check
    entity = db.execute_query(
        "SELECT entity_id, name, confidence, mention_count FROM entities WHERE name = 'Donald Trump'", 
        fetch=True
    )
    if entity:
        logger.success(f"✅ TARGET DISCOVERED: {entity[0]['name']} (ID: {entity[0]['entity_id']})")
        logger.info(f"   Confidence: {entity[0]['confidence']} | Mentions: {entity[0]['mention_count']}")
    else:
        logger.error("❌ TARGET MISSING: The brain failed to extract the entity.")

    # B. Relationship Check
    rels = db.execute_query(
        """
        SELECT a.name as sub, r.relationship_type as pred, b.name as obj 
        FROM entity_relationships r 
        JOIN entities a ON r.entity_a_id = a.entity_id 
        JOIN entities b ON r.entity_b_id = b.entity_id 
        WHERE a.name = 'Donald Trump' OR b.name = 'Donald Trump'
        """, fetch=True
    )
    if rels:
        for r in rels:
            logger.success(f"✅ NETWORK FORMED: [{r['sub']}] --{r['pred']}--> [{r['obj']}]")
    else:
        logger.warning("⚠️ No relationships formed yet.")

    # C. Clustering Check
    cluster = db.execute_query(
        "SELECT title FROM intelligence_clusters WHERE cluster_id = (SELECT cluster_id FROM intelligence_records WHERE uid = %s)",
        (uir_uid,), fetch=True
    )
    if cluster:
        logger.success(f"✅ SITUATIONAL AWARENESS: Target linked to '{cluster[0]['title']}'")

    db.close()

if __name__ == "__main__":
    run_target_test()
