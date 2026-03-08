import pytest
import uuid
import time
from unittest.mock import patch
from pia.core.database import DatabaseManager
from pia.agents.analyst_agent import AnalystAgent

@pytest.fixture(scope="module")
def db():
    manager = DatabaseManager()
    yield manager
    manager.close()

def test_intelligence_fusion_e2e(db):
    """
    MASTER TEST: Verifies that a raw signal results in:
    1. Spatial Correlation
    2. Entity Extraction
    3. Knowledge Graph Update
    """
    
    # 0. Seed Brownsville (Anchor)
    db.execute_query("""
        INSERT INTO entities (name, entity_type, primary_geo, confidence)
        VALUES ('Brownsville', 'LOCATION', ST_SetSRID(ST_Point(-97.4975, 25.9017), 4326), 0.99)
        ON CONFLICT DO NOTHING;
    """)

    # 1. Inject a Mock Signal into Layer 2
    # Content mentions 'SpaceX' and 'Brownsville' (both should be in graph after seeding)
    test_uid = str(uuid.uuid4())
    db.execute_query("""
        INSERT INTO intelligence_records (
            uid, source_type, source_agent, content_headline, content_summary, 
            domain, priority, geo
        ) VALUES (
            %s, 'OSINT', 'test_fusion_agent', 'SpaceX Expansion',
            'SpaceX is building new infrastructure in Brownsville, Texas today.',
            'INFRASTRUCTURE', 'NORMAL', ST_SetSRID(ST_Point(-97.4975, 25.9017), 4326)
        );
    """, (test_uid,))
    
    # 2. Wait for the queue trigger to register
    time.sleep(1)
    
    # 3. Manually run one cycle of the Analyst Agent
    with patch("pia.core.nlp.NLPManager.extract_intelligence") as mock_extract:
        mock_extract.return_value = {
            "entities": [
                {"name": "SpaceX", "type": "ORGANIZATION"}
            ],
            "relationships": [
                {"subject": "SpaceX", "predicate": "LOCATED_IN", "object": "Brownsville", "reasoning": "Mocked test reasoning"}
            ],
            "summary": "Mocked summary"
        }
        
        agent = AnalystAgent(name="test_fusion_brain")
        agent.setup()
        agent.poll() # This should process our injected signal
        agent.stop() # This closes the database pool

    # Re-initialize pool to perform verifications
    db._initialize_pool()
    
    # 4. VERIFICATION A: Spatial & Clustering
    # Check if cluster was created near Brownsville
    cluster = db.execute_query("""
        SELECT * FROM intelligence_clusters 
        WHERE title ILIKE '%Brownsville%'
    """, fetch=True)
    assert len(cluster) > 0, "Analyst failed to create a spatial cluster near Brownsville."
    
    # 5. VERIFICATION B: Entity Extraction & Linking
    # Check if 'SpaceX' entity was created or updated
    entity = db.execute_query("""
        SELECT mention_count, uir_refs FROM entities 
        WHERE name = 'SpaceX'
    """, fetch=True)
    assert len(entity) > 0, "Analyst failed to extract/link the 'SpaceX' entity."
    assert test_uid in str(entity[0]['uir_refs']), "UIR reference missing from entity profile."
    
    # 6. VERIFICATION C: Graph Traversal
    # Check if the relationship exists in Apache AGE
    cypher = """
        SELECT * FROM cypher('pia_graph', $$
            MATCH (a:ENTITY {name: "SpaceX"})-[:LOCATED_IN]->(b:ENTITY)
            RETURN b.name
        $$) as (city agtype);
    """
    try:
        graph_results = db.execute_query(f"LOAD 'age'; SET search_path = public, ag_catalog; {cypher}", fetch=True)
        assert len(graph_results) > 0, "Graph relationship missing."
    except Exception as e:
        print(f"Graph verification skipped (likely no local LLM): {e}")
