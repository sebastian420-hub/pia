import uuid, hashlib, sys, os, time
from loguru import logger

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_real_world_e2e():
    db = DatabaseManager()
    
    # Tech Hub Coordinates (San Francisco ~37.77, -122.41)
    lat, lon = 37.7749, -122.4194
    
    logger.info("🌍 STARTING REAL-WORLD OPERATION: AI INDUSTRY MAPPING (2026)")
    
    # 1. Set Strategic Mission
    res = db.execute_query(
        "INSERT INTO mission_focus (category, keywords, is_active) VALUES ('TECH_FINANCE', ARRAY['OpenAI', 'Microsoft', 'Sam Altman', 'Amazon', 'Nvidia'], TRUE) RETURNING focus_id",
        fetch=True
    )
    mission_id = res[0]['focus_id']
    logger.info(f"Step 1: TECH_FINANCE Mission Active (ID: {mission_id})")

    # 2. Inject OSINT (Real News 1: Funding Round)
    h_news1 = hashlib.sha256(f"news1_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('OSINT', 'financial_agent', 'GeekWire', %s, 'OpenAI closes historic $110 billion funding round', 'On February 27, 2026, OpenAI closed a historic funding round. New major investors include Amazon, Nvidia, and SoftBank. Amazon is now the exclusive third-party cloud provider for OpenAI Frontier.', 'FINANCIAL', 'CRITICAL', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_news1, lon, lat, mission_id))
    
    # 3. Inject OSINT (Real News 2: Microsoft Partnership)
    h_news2 = hashlib.sha256(f"news2_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('OSINT', 'news_agent', 'The Register', %s, 'Microsoft and OpenAI reassure market on core alliance', 'Despite capital from competitors, Microsoft Azure remains the exclusive cloud provider for all stateless OpenAI APIs, and Microsoft maintains a 27 percent stake in OpenAI.', 'FINANCIAL', 'CRITICAL', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_news2, lon + 0.01, lat + 0.01, mission_id))

    # 4. Inject OSINT (Real News 3: Defense Deal)
    h_news3 = hashlib.sha256(f"news3_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, geo, mission_id)
        VALUES ('OSINT', 'news_agent', 'TechCrunch', %s, 'Sam Altman signs Pentagon AI deal', 'OpenAI CEO Sam Altman announced a landmark agreement with the U.S. Department of Defense to deploy GPT models on classified networks.', 'MILITARY', 'CRITICAL', ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
    """, (h_news3, lon - 0.01, lat - 0.01, mission_id))

    logger.info("Step 2-4: Real-world signals injected. Waiting for Swarm Fusion and NLP Extraction...")
    
    # Wait for processing
    logger.info("Sleeping for 50 seconds to allow Analyst Agent NLP processing...")
    for i in range(5):
        time.sleep(10)
        logger.info(f"... {50 - (i+1)*10} seconds remaining ...")

    # 5. Audit Fusion Results
    logger.info("--- MISSION AUDIT: EXTRACTED RELATIONSHIPS (KNOWLEDGE GRAPH) ---")
    rels = db.execute_query("""
        SELECT a.name as sub, r.relationship_type as pred, b.name as obj, r.confidence
        FROM entity_relationships r
        JOIN entities a ON r.entity_a_id = a.entity_id
        JOIN entities b ON r.entity_b_id = b.entity_id
        WHERE a.name ILIKE '%OpenAI%' OR b.name ILIKE '%OpenAI%'
           OR a.name ILIKE '%Sam Altman%' OR b.name ILIKE '%Sam Altman%'
           OR a.name ILIKE '%Microsoft%' OR b.name ILIKE '%Microsoft%'
           OR a.name ILIKE '%Amazon%' OR b.name ILIKE '%Amazon%'
           OR a.name ILIKE '%Nvidia%' OR b.name ILIKE '%Nvidia%'
        ORDER BY r.confidence DESC
    """, fetch=True)
    
    if rels:
        for r in rels:
            logger.success(f"✅ RELATIONSHIP DISCOVERED: [{r['sub']}] --{r['pred']}--> [{r['obj']}]")
    else:
        logger.warning("⚠️ No new graph connections hardened yet. Check if NLP agent is functioning.")

    logger.info("--- MISSION AUDIT: EXTRACTED ENTITIES ---")
    ents = db.execute_query("""
        SELECT name, entity_type, mention_count
        FROM entities
        WHERE name ILIKE '%OpenAI%' OR name ILIKE '%Microsoft%' OR name ILIKE '%Amazon%' 
           OR name ILIKE '%Nvidia%' OR name ILIKE '%SoftBank%' OR name ILIKE '%Sam Altman%' OR name ILIKE '%Department of Defense%'
        ORDER BY mention_count DESC
    """, fetch=True)

    if ents:
         for e in ents:
             logger.info(f"   Entity: {e['name']} (Type: {e['entity_type']}, Mentions: {e['mention_count']})")
             
    db.close()

if __name__ == "__main__":
    run_real_world_e2e()