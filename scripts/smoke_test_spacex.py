import uuid, hashlib, sys, os, time
from loguru import logger
from datetime import datetime

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_spacex_e2e():
    db = DatabaseManager()
    
    # Coordinates for Boca Chica (~25.99, -97.15)
    lat, lon = 25.9973, -97.1566
    
    logger.info("🚀 STARTING TARGETED OPERATION: SPACEX BOCA CHICA")
    
    # 1. Set Strategic Mission
    res = db.execute_query(
        "INSERT INTO mission_focus (category, keywords, is_active) VALUES ('AEROSPACE', ARRAY['SpaceX', 'Starship', 'Boca Chica', 'Launch'], TRUE) RETURNING focus_id",
        fetch=True
    )
    mission_id = res[0]['focus_id']
    logger.info(f"Step 1: AEROSPACE Mission Active (ID: {mission_id})")

    # 2. Inject OSINT (News about Launch)
    h_news = hashlib.sha256(f"news_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('OSINT', 'news_agent', 'SpaceNews', %s, 'SpaceX preparing for Starship orbital flight', 'SpaceX is finalizing preparations for the Starship launch at the Starbase facility in Boca Chica.', 'INFRASTRUCTURE', 'HIGH', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_news, lon, lat, mission_id))
    
    # 3. Inject SIGINT (Aviation - SpaceX Heli)
    h_air = hashlib.sha256(f"air_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('SIGINT', 'aviation_sentinel', 'ADS-B Aviation Feed', %s, 'AIRCRAFT: N272BG active over Starbase', 'SpaceX corporate helicopter N272BG conducting aerial surveillance over the launch pad.', 'AVIATION', 'NORMAL', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_air, lon + 0.01, lat + 0.01, mission_id))
    
    # 4. Inject SIGINT (Maritime - Recovery Ship)
    h_sea = hashlib.sha256(f"sea_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('SIGINT', 'maritime_sentinel', 'AIS Maritime Feed', %s, 'VESSEL: GO Searcher moving to splashdown zone', 'SpaceX recovery vessel GO Searcher is navigating into the Gulf of Mexico holding area.', 'MARITIME', 'HIGH', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_sea, lon + 0.5, lat + 0.1, mission_id))

    logger.info("Step 2-4: Multi-Domain signals injected. Waiting for Swarm Fusion and NLP Extraction...")
    
    # Wait for processing
    logger.info("Sleeping for 40 seconds to allow Analyst Agent NLP processing...")
    for i in range(4):
        time.sleep(10)
        logger.info(f"... {40 - (i+1)*10} seconds remaining ...")

    # 5. Audit Fusion Results
    logger.info("--- MISSION AUDIT: SITUATIONAL AWARENESS ---")
    
    # Check if a single cluster captured them
    clusters = db.execute_query("""
        SELECT cluster_id, title, uir_count, priority 
        FROM intelligence_clusters 
        WHERE geo_centroid && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
        ORDER BY updated_at DESC LIMIT 1
    """, (lon-1, lat-1, lon+1, lat+1), fetch=True)

    if clusters and clusters[0]['uir_count'] >= 1:
        logger.success(f"✅ CROSS-DOMAIN FUSION: SUCCESS.")
        logger.info(f"   Situation Identified: '{clusters[0]['title']}'")
        logger.info(f"   Fused Records: {clusters[0]['uir_count']}")
        logger.info(f"   Escalated Priority: {clusters[0]['priority']}")
    else:
        logger.error("❌ FUSION FAILURE: Signals remained fragmented or unprocessed.")

    # Check Knowledge Graph Extracted Entities & Relationships
    logger.info("--- MISSION AUDIT: EXTRACTED RELATIONSHIPS (KNOWLEDGE GRAPH) ---")
    rels = db.execute_query("""
        SELECT a.name as sub, r.relationship_type as pred, b.name as obj, r.confidence
        FROM entity_relationships r
        JOIN entities a ON r.entity_a_id = a.entity_id
        JOIN entities b ON r.entity_b_id = b.entity_id
        WHERE a.name ILIKE '%SpaceX%' OR b.name ILIKE '%SpaceX%'
           OR a.name ILIKE '%Starship%' OR b.name ILIKE '%Starship%'
           OR a.name ILIKE '%Boca Chica%' OR b.name ILIKE '%Boca Chica%'
           OR a.name ILIKE '%Starbase%' OR b.name ILIKE '%Starbase%'
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
        WHERE name ILIKE '%SpaceX%' OR name ILIKE '%Starship%' OR name ILIKE '%Boca Chica%' OR name ILIKE '%Starbase%'
           OR name ILIKE '%N272BG%' OR name ILIKE '%GO Searcher%'
        ORDER BY mention_count DESC
    """, fetch=True)

    if ents:
         for e in ents:
             logger.info(f"   Entity: {e['name']} (Type: {e['entity_type']}, Mentions: {e['mention_count']})")
             
    db.close()

if __name__ == "__main__":
    run_spacex_e2e()