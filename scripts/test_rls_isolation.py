import uuid, hashlib, sys, os, time
from loguru import logger
from datetime import datetime

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_multi_tenant_test():
    db = DatabaseManager()
    
    logger.info("🛡️ STARTING MULTI-TENANT ISOLATION TEST")
    
    # 1. Create two simulated clients
    client_vc = str(uuid.uuid4())
    client_mil = str(uuid.uuid4())
    logger.info(f"Generated Client VC ID: {client_vc}")
    logger.info(f"Generated Client MIL ID: {client_mil}")

    # 2. Register separate missions for each client
    # VC cares about OpenAI
    res_vc = db.execute_query(
        "INSERT INTO mission_focus (category, keywords, is_active, client_id) VALUES ('FINANCIAL', ARRAY['OpenAI', 'Startup'], TRUE, %s) RETURNING focus_id",
        (client_vc,), fetch=True
    )
    mission_vc = res_vc[0]['focus_id']
    
    # MIL cares about Drones
    res_mil = db.execute_query(
        "INSERT INTO mission_focus (category, keywords, is_active, client_id) VALUES ('MILITARY', ARRAY['Drone', 'UAV'], TRUE, %s) RETURNING focus_id",
        (client_mil,), fetch=True
    )
    mission_mil = res_mil[0]['focus_id']

    # 3. Inject Data
    # Data 1: Startup News (Should trigger VC mission)
    h_news1 = hashlib.sha256(f"test_vc_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, mission_id, client_id)
        VALUES ('OSINT', 'news_agent', 'TechBlog', %s, 'OpenAI launches new fund', 'OpenAI is investing in a new AI startup.', 'FINANCIAL', 'HIGH', %s, %s)
    """, (h_news1, mission_vc, client_vc))

    # Data 2: Military News (Should trigger MIL mission)
    h_news2 = hashlib.sha256(f"test_mil_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query("""
        INSERT INTO intelligence_records (source_type, source_agent, source_name, content_hash, content_headline, content_summary, domain, priority, mission_id, client_id)
        VALUES ('OSINT', 'news_agent', 'DefenseNews', %s, 'New drone deployed', 'A new tactical UAV drone has been spotted.', 'MILITARY', 'HIGH', %s, %s)
    """, (h_news2, mission_mil, client_mil))

    logger.info("Data injected. Waiting 30s for Agent Swarm to process and cluster with RLS tags...")
    time.sleep(30)

    # 4. Test RLS Isolation
    logger.info("--- RLS ISOLATION AUDIT ---")
    
    # We must connect as the restricted client role to trigger RLS
    import psycopg2
    
    # Test as VC Client
    try:
        conn = psycopg2.connect(host="postgres", user="pia_client", password="password", database="pia")
        cur = conn.cursor()
        cur.execute(f"SET LOCAL app.current_client_id = '{client_vc}'; SELECT content_headline FROM intelligence_records;")
        vc_records = cur.fetchall()
        cur.execute(f"SET LOCAL app.current_client_id = '{client_vc}'; SELECT title FROM intelligence_clusters;")
        vc_clusters = cur.fetchall()
        
        logger.info(f"VC Client sees {len(vc_records)} records and {len(vc_clusters)} clusters.")
        for r in vc_records:
            if 'drone' in r[0].lower():
                logger.error("❌ ISOLATION FAILURE: VC saw military data.")
                
        if not any('drone' in r[0].lower() for r in vc_records):
            logger.success("✅ VC Isolation Confirmed.")
            
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"VC Context Error: {e}")

    # Test as MIL Client
    try:
        conn = psycopg2.connect(host="postgres", user="pia_client", password="password", database="pia")
        cur = conn.cursor()
        cur.execute(f"SET LOCAL app.current_client_id = '{client_mil}'; SELECT content_headline FROM intelligence_records;")
        mil_records = cur.fetchall()
        cur.execute(f"SET LOCAL app.current_client_id = '{client_mil}'; SELECT title FROM intelligence_clusters;")
        mil_clusters = cur.fetchall()
        
        logger.info(f"MIL Client sees {len(mil_records)} records and {len(mil_clusters)} clusters.")
        for r in mil_records:
            if 'OpenAI launches new fund' in r[0]:
                logger.error("❌ ISOLATION FAILURE: MIL saw financial data.")
                
        if not any('OpenAI launches new fund' in r[0] for r in mil_records):
             logger.success("✅ MIL Isolation Confirmed.")
             
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"MIL Context Error: {e}")
        
    db.close()

if __name__ == "__main__":
    run_multi_tenant_test()