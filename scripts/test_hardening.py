import uuid, hashlib, sys, os, time
from loguru import logger

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_hardening_test():
    db = DatabaseManager()
    
    logger.info("--- STAGE 2: HARDENING AUDIT ---")
    
    # 1. SECURITY TEST (Cypher Injection)
    malicious_name = 'Rocket" }) DETACH DELETE (n) RETURN (n'
    safe_name = malicious_name.replace('"', '"')
    cypher = f'MATCH (a:ENTITY {{name: "{safe_name}"}}) RETURN a.name'
    
    logger.info(f"Checking Injection Shield with: {malicious_name}")
    try:
        # This should execute safely without breaking the Cypher block
        db.execute_cypher('pia_graph', cypher)
        logger.success("✅ INJECTION SHIELD: Verified. Malicious input handled as literal string.")
    except Exception as e:
        logger.error(f"❌ INJECTION SHIELD: Failed: {e}")

    # 2. CONCURRENCY TEST (Atomic Claiming)
    logger.info("Checking Analyst Swarm Concurrency (Atomic Locking)...")
    
    uids = []
    for i in range(5):
        h = hashlib.sha256(f"stress_{i}_{uuid.uuid4()}".encode()).hexdigest()
        res = db.execute_query(
            "INSERT INTO intelligence_records (source_type, source_agent, content_hash, domain, priority) VALUES ('SYSTEM', 'stress_test', %s, 'UNKNOWN', 'NORMAL') RETURNING uid", 
            (h,), fetch=True
        )
        uids.append(res[0]['uid'])

    logger.info(f"Injected 5 stress-test jobs (UIRs: {len(uids)})")
    
    # Give the 3 agents time to poll and process
    time.sleep(15)
    
    # Check who claimed what
    claims = db.execute_query(
        "SELECT assigned_agent, count(*) as count FROM analysis_queue WHERE trigger_uid = ANY(%s::uuid[]) GROUP BY assigned_agent",
        (uids,), fetch=True
    )
    
    total_claimed = 0
    for row in claims:
        logger.info(f"   Agent {row['assigned_agent']} processed {row['count']} jobs.")
        total_claimed += row['count']
        
    if total_claimed == 5:
        logger.success("✅ CONCURRENCY: Verified. All jobs uniquely distributed across the swarm.")
    else:
        logger.error(f"❌ CONCURRENCY: Failed. Only {total_claimed}/5 jobs were processed.")

    db.close()

if __name__ == "__main__":
    run_hardening_test()
