import pytest
import uuid
import time
from pia.core.database import DatabaseManager
from pia.api.mcp_server import get_active_clusters, get_system_health

@pytest.fixture(scope="module")
def db():
    manager = DatabaseManager()
    yield manager
    manager.close()

def test_01_core_engine_integrity(db):
    """Verify all 5 critical extensions are functional."""
    query = "SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'timescaledb', 'vector', 'age', 'pg_cron');"
    results = db.execute_query(query, fetch=True)
    assert len(results) >= 5

def test_02_seeded_knowledge(db):
    """Verify that the 33k cities are still present and indexed."""
    query = "SELECT count(*) FROM entities WHERE entity_type = 'LOCATION';"
    result = db.execute_query(query, fetch=True)
    assert result[0]['count'] >= 30000

def test_03_autonomous_reasoning_loop(db):
    """
    Verify that the Analyst Agent has processed signals into clusters.
    """
    # Query for active clusters
    query = "SELECT count(*) FROM intelligence_clusters WHERE status = 'ACTIVE';"
    result = db.execute_query(query, fetch=True)
    assert result[0]['count'] > 0, "No active intelligence clusters found. The brain is not reasoning."

def test_04_mcp_interface_tools():
    """
    Verify that the MCP tools can retrieve system data programmatically.
    """
    health = get_system_health()
    assert 'total_entities' in health
    assert health['total_entities'] >= 33000
    
    clusters = get_active_clusters(limit=1)
    assert len(clusters) > 0
    assert 'title' in clusters[0]
    assert 'cluster_id' in clusters[0]
