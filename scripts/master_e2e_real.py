import uuid, hashlib, sys, os, time
from loguru import logger
from datetime import datetime

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_real_e2e():
    db = DatabaseManager()
    
    # Coordinates for the Baltic Synchrony (~54.7, 18.5)
    lat, lon = 54.7, 18.5
    
    logger.info("📡 STARTING OPERATION: GLOBAL SYNCHRONY")
    
    # 1. Set Strategic Mission
    res = db.execute_query(
        "INSERT INTO mission_focus (category, keywords, is_active) VALUES ('MILITARY', ARRAY['Drill', 'Naval', 'Aviation', 'Baltic'], TRUE) RETURNING focus_id",
        fetch=True
    )
    mission_id = res[0]['focus_id']
    logger.info(f"Step 1: Military Mission Active (ID: {mission_id})")

    # 2. Inject Aviation Signal (SIGINT)
    h_air = hashlib.sha256(f"air_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('SIGINT', 'aviation_sentinel', 'ADS-B Aviation Feed', %s, 'AIRCRAFT: TITAN25 active in Baltic', 'Military reconnaissance aircraft detected.', 'MILITARY', 'HIGH', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_air, lon, lat, mission_id))
    
    # 3. Inject Maritime Signal (SIGINT)
    h_sea = hashlib.sha256(f"sea_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('SIGINT', 'maritime_sentinel', 'AIS Maritime Feed', %s, 'VESSEL: COSCO SHIPPING entering zone', 'Cargo vessel crossing the reconnaissance path.', 'MILITARY', 'NORMAL', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_sea, lon + 0.1, lat + 0.1, mission_id))

    # 4. Inject News Signal (OSINT)
    h_news = hashlib.sha256(f"news_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('OSINT', 'news_agent', 'Reuters', %s, 'REUTERS: Naval drills confirmed in Baltic', 'Confidential sources report a joint naval-air operation.', 'MILITARY', 'HIGH', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_news, lon - 0.1, lat - 0.1, mission_id))

    logger.info("Step 2-4: Three-Domain signals injected. Waiting for Swarm Fusion...")
    
    # Wait for processing
    time.sleep(25)

    # 5. Audit Fusion Results
    logger.info("--- MISSION AUDIT: SITUATIONAL AWARENESS ---")
    
    # Check if a single cluster captured all three
    clusters = db.execute_query("""
        SELECT cluster_id, title, uir_count, priority 
        FROM intelligence_clusters 
        WHERE geo_centroid && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
        AND domain = 'MILITARY'
        ORDER BY updated_at DESC LIMIT 1
    """, (lon-1, lat-1, lon+1, lat+1), fetch=True)

    if clusters and clusters[0]['uir_count'] >= 3:
        logger.success(f"✅ CROSS-DOMAIN FUSION: SUCCESS.")
        logger.info(f"   Situation Identified: '{clusters[0]['title']}'")
        logger.info(f"   Fused Records: {clusters[0]['uir_count']}")
        logger.info(f"   Escalated Priority: {clusters[0]['priority']}")
    else:
        logger.error("❌ FUSION FAILURE: Signals remained fragmented.")

    # Check Knowledge Graph
    logger.info("--- MISSION AUDIT: KNOWLEDGE GRAPH ---")
    rels = db.execute_query("""
        SELECT a.name as sub, r.relationship_type as pred, b.name as obj
        FROM entity_relationships r
        JOIN entities a ON r.entity_a_id = a.entity_id
        JOIN entities b ON r.entity_b_id = b.entity_id
        WHERE a.name IN ('TITAN25', 'COSCO SHIPPING', 'Reuters')
        OR b.name IN ('TITAN25', 'COSCO SHIPPING', 'Reuters')
    """, fetch=True)
    
    if rels:
        for r in rels:
            logger.success(f"✅ RELATIONSHIP DISCOVERED: [{r['sub']}] --{r['pred']}--> [{r['obj']}]")
    else:
        logger.warning("⚠️ No new graph connections hardened yet (awaiting corroboration threshold).")

    db.close()

if __name__ == "__main__":
    run_real_e2e()
