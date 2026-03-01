import uuid, hashlib, sys, os, time
from loguru import logger

# Add src to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))
from pia.core.database import DatabaseManager

def run_integrity_test():
    db = DatabaseManager()
    
    logger.info("🛡️ STARTING INTEGRITY GAUNTLET: Data Quality Validation")
    
    # 0. Setup a Low-Trust Source
    db.execute_query(
        "INSERT INTO source_authority (source_name, source_type, trust_score, notes) VALUES ('rumor_mill', 'OSINT', 0.2, 'Testing low trust') ON CONFLICT DO NOTHING"
    )

    # 1. INJECT LOW-TRUST RUMOR
    h1 = hashlib.sha256(f"rumor_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query(
        """
        INSERT INTO intelligence_records (
            source_type, source_agent, source_name, content_hash,
            content_headline, content_summary, domain, priority
        ) VALUES (
            'OSINT', 'integrity_tester', 'rumor_mill', %s,
            'RUMOR: Global Tech Acquisition', 'Unverified chatter suggests that the company Apple is looking to acquire the streaming giant Netflix in a multi-billion dollar deal.', 'FINANCIAL', 'NORMAL'
        ) RETURNING uid;
        """, (h1,), fetch=True
    )
    logger.info("Step 1: Low-Trust rumor injected ('Apple' + 'Netflix')")

    # Wait for processing
    time.sleep(15)

    # Check relationship confidence (should be low)
    res = db.execute_query(
        """
        SELECT r.confidence FROM entity_relationships r
        JOIN entities a ON r.entity_a_id = a.entity_id
        JOIN entities b ON r.entity_b_id = b.entity_id
        WHERE a.name = 'Apple' AND b.name = 'Netflix'
        """, fetch=True
    )
    if res:
        logger.info(f"   Provisional Confidence: {res[0]['confidence']:.2f}")
    else:
        logger.warning("   Relationship not yet formed.")

    # 2. INJECT HIGH-TRUST CORROBORATION
    h2 = hashlib.sha256(f"confirm_{uuid.uuid4()}".encode()).hexdigest()
    db.execute_query(
        """
        INSERT INTO intelligence_records (
            source_type, source_agent, source_name, content_hash,
            content_headline, content_summary, domain, priority
        ) VALUES (
            'OSINT', 'integrity_tester', 'Reuters', %s,
            'REUTERS: Apple and Netflix in advanced talks', 'Confidential sources at Apple and Netflix confirm that both organizations are in advanced stages of acquisition talks.', 'FINANCIAL', 'HIGH'
        ) RETURNING uid;
        """, (h2,), fetch=True
    )
    logger.info("Step 2: High-Trust corroboration injected (Reuters)")

    # Wait for processing and enrichment
    logger.info("Waiting 30s for Cross-Verification and Enrichment...")
    time.sleep(30)

    # 3. AUDIT FINAL INTELLIGENCE
    logger.info("--- INTEGRITY AUDIT RESULTS ---")
    
    # A. Corroboration Check
    res = db.execute_query(
        """
        SELECT r.confidence FROM entity_relationships r
        JOIN entities a ON r.entity_a_id = a.entity_id
        JOIN entities b ON r.entity_b_id = b.entity_id
        WHERE a.name = 'Apple' AND b.name = 'Netflix'
        """, fetch=True
    )
    if res and res[0]['confidence'] > 0.5:
        logger.success(f"✅ CROSS-VERIFICATION: Verified. Confidence raised to {res[0]['confidence']:.2f}")
    else:
        logger.error("❌ CROSS-VERIFICATION: Failed to corroborate or raise confidence.")

    # B. Enrichment Check
    ent = db.execute_query("SELECT name, description, confidence FROM entities WHERE name IN ('Apple', 'Netflix')", fetch=True)
    for e in ent:
        if e['confidence'] >= 0.8:
            logger.success(f"✅ ENRICHMENT: {e['name']} profile hardened. Confidence: {e['confidence']}")
            logger.info(f"   Description: {e['description']}")
        else:
            logger.warning(f"⚠️ ENRICHMENT: {e['name']} still pending full hardening.")

    db.close()

if __name__ == "__main__":
    run_integrity_test()
