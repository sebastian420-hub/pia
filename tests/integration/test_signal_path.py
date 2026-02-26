import pytest
import uuid
import time
from pia.core.database import DatabaseManager

@pytest.fixture(scope="module")
def db():
    manager = DatabaseManager()
    yield manager
    manager.close()

def test_01_extension_integrity(db):
    """Confirm the Five Pillar extensions are functional."""
    query = """
    SELECT extname FROM pg_extension 
    WHERE extname IN ('postgis', 'timescaledb', 'vector', 'age', 'pg_cron');
    """
    results = db.execute_query(query, fetch=True)
    extensions = [r['extname'] for r in results]
    assert len(extensions) == 5, f"Missing extensions. Found: {extensions}"

def test_02_geographic_baseline(db):
    """Verify that Tier 1 seeding (GeoNames) is present."""
    query = "SELECT count(*) FROM entities WHERE entity_type = 'LOCATION';"
    result = db.execute_query(query, fetch=True)
    count = result[0]['count']
    assert count >= 30000, f"Geographic baseline missing or incomplete. Count: {count}"

def test_03_signal_propagation_heartbeat(db):
    """
    CRITICAL TEST: Verify that inserting a UIR (Layer 2) 
    automatically triggers a Heartbeat job (Analysis Queue).
    """
    test_uid = str(uuid.uuid4())
    
    # 1. Insert a Mock UIR
    db.execute_query("""
        INSERT INTO intelligence_records (
            uid, source_type, source_agent, content_headline, domain, confidence, priority
        ) VALUES (
            %s, 'SYSTEM', 'e2e_tester', 'E2E Signal Test', 'NATURAL', 0.1, 'HIGH'
        );
    """, (test_uid,))
    
    # 2. Wait a split second for the trigger to fire
    time.sleep(0.5)
    
    # 3. Check if the heartbeat created an analysis job
    query = "SELECT * FROM analysis_queue WHERE uir_uid = %s;"
    results = db.execute_query(query, (test_uid,), fetch=True)
    
    assert len(results) == 1, "Heartbeat failed: No analysis job created for the UIR."
    assert results[0]['trigger_type'] == 'NEW_UIR'
    assert results[0]['priority'] == 'HIGH'
    
    print(f"\n[E2E] Heartbeat confirmed for UIR {test_uid}")

def test_04_live_telemetry_check(db):
    """Verify that the Seismic Agent has successfully written real-world data."""
    query = "SELECT count(*) FROM seismic_events;"
    result = db.execute_query(query, fetch=True)
    count = result[0]['count']
    
    # Since the agent runs every 60s, there should be data by now
    assert count > 0, "Telemetry failure: No live seismic events found in Layer 1."
