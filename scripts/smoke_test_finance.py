import uuid, hashlib, sys, os, time
from loguru import logger

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_finance_e2e():
    db = DatabaseManager()
    
    # Financial Hub Coordinates (e.g., Wall Street, NYC ~40.7, -74.0)
    lat, lon = 40.706, -74.009
    
    logger.info("💰 STARTING TARGETED OPERATION: FINANCIAL & NETWORK MAPPING")
    
    # 1. Set Strategic Mission
    res = db.execute_query(
        "INSERT INTO mission_focus (category, keywords, is_active) VALUES ('FINANCIAL', ARRAY['Acme Corp', 'Finance', 'Investment', 'CEO'], TRUE) RETURNING focus_id",
        fetch=True
    )
    mission_id = res[0]['focus_id']
    logger.info(f"Step 1: FINANCIAL Mission Active (ID: {mission_id})")

    # 2. Inject OSINT (News about Investment)
    h_news1 = hashlib.sha256(f"news1_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('OSINT', 'financial_agent', 'WSJ Feed', %s, 'Venture Capitalist John Doe invests heavily in Acme Corp', 'Billionaire investor John Doe has successfully invested 50 million dollars in Acme Corp to fund their new AI division.', 'FINANCIAL', 'HIGH', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_news1, lon, lat, mission_id))
    
    # 3. Inject OSINT (News about Affiliation / Friends)
    h_news2 = hashlib.sha256(f"news2_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('OSINT', 'news_agent', 'Bloomberg', %s, 'Acme Corp forms strategic alliance with Globex', 'Acme Corp is now allied with Globex Corporation, and Acme Corp CEO Jane Smith works closely with them on infrastructure projects.', 'FINANCIAL', 'NORMAL', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_news2, lon + 0.01, lat + 0.01, mission_id))

    logger.info("Step 2-3: Financial signals injected. Waiting for Swarm Fusion and NLP Extraction...")
    
    # Wait for processing
    logger.info("Sleeping for 40 seconds to allow Analyst Agent NLP processing...")
    for i in range(4):
        time.sleep(10)
        logger.info(f"... {40 - (i+1)*10} seconds remaining ...")

    # 4. Audit Fusion Results
    logger.info("--- MISSION AUDIT: SITUATIONAL AWARENESS ---")
    
    clusters = db.execute_query("""
        SELECT cluster_id, title, uir_count, priority 
        FROM intelligence_clusters 
        WHERE geo_centroid && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
        AND domain = 'FINANCIAL'
        ORDER BY updated_at DESC LIMIT 1
    """, (lon-1, lat-1, lon+1, lat+1), fetch=True)

    if clusters and clusters[0]['uir_count'] >= 1:
        logger.success(f"✅ CROSS-DOMAIN FUSION: SUCCESS.")
        logger.info(f"   Situation Identified: '{clusters[0]['title']}'")
        logger.info(f"   Fused Records: {clusters[0]['uir_count']}")
    else:
        logger.error("❌ FUSION FAILURE: Signals remained fragmented or unprocessed.")

    # Check Knowledge Graph Extracted Entities & Relationships
    logger.info("--- MISSION AUDIT: EXTRACTED FINANCIAL/ALLIANCE RELATIONSHIPS ---")
    rels = db.execute_query("""
        SELECT a.name as sub, r.relationship_type as pred, b.name as obj, r.confidence
        FROM entity_relationships r
        JOIN entities a ON r.entity_a_id = a.entity_id
        JOIN entities b ON r.entity_b_id = b.entity_id
        WHERE a.name ILIKE '%Acme Corp%' OR b.name ILIKE '%Acme Corp%'
           OR a.name ILIKE '%John Doe%' OR b.name ILIKE '%John Doe%'
           OR a.name ILIKE '%Jane Smith%' OR b.name ILIKE '%Jane Smith%'
           OR a.name ILIKE '%Globex%' OR b.name ILIKE '%Globex%'
        ORDER BY r.confidence DESC
    """, fetch=True)
    
    if rels:
        for r in rels:
            logger.success(f"✅ RELATIONSHIP DISCOVERED: [{r['sub']}] --{r['pred']}--> [{r['obj']}] (Confidence: {r['confidence']:.2f})")
    else:
        logger.warning("⚠️ No new graph connections hardened yet. Check if NLP agent is functioning.")

    logger.info("--- MISSION AUDIT: EXTRACTED ENTITIES ---")
    ents = db.execute_query("""
        SELECT name, entity_type, mention_count
        FROM entities
        WHERE name ILIKE '%Acme Corp%' OR name ILIKE '%John Doe%' OR name ILIKE '%Jane Smith%' OR name ILIKE '%Globex%'
        ORDER BY mention_count DESC
    """, fetch=True)

    if ents:
         for e in ents:
             logger.info(f"   Entity: {e['name']} (Type: {e['entity_type']}, Mentions: {e['mention_count']})")
             
    db.close()

if __name__ == "__main__":
    run_finance_e2e()