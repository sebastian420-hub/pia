import pytest
import uuid
from pia.core.database import DatabaseManager
from pia.ingestion.wikidata_ingestor import WikidataIngestor

@pytest.fixture(scope="module")
def ingestor():
    return WikidataIngestor()

@pytest.fixture(scope="module")
def db():
    manager = DatabaseManager()
    yield manager
    manager.close()

def test_01_entity_insertion(db):
    """Verify we can insert entities with Wikidata metadata."""
    test_qid = "Q_TEST_ORG_1"
    db.execute_query("""
        INSERT INTO entities (name, entity_type, metadata, confidence)
        VALUES ('Test Intelligence Agency', 'ORGANIZATION', %s, 0.99)
        ON CONFLICT DO NOTHING;
    """, (f'{{"wikidata_id": "{test_qid}"}}',))
    
    result = db.execute_query("SELECT count(*) FROM entities WHERE metadata->>'wikidata_id' = %s", (test_qid,), fetch=True)
    assert result[0]['count'] >= 1

def test_02_relationship_logic(db, ingestor):
    """Verify that the ingestor can link two Wikidata entities."""
    # Ensure we have a city and an org
    db.execute_query("""
        INSERT INTO entities (name, entity_type, metadata) 
        VALUES ('Test City', 'LOCATION', '{"wikidata_id": "Q_TEST_CITY"}') 
        ON CONFLICT DO NOTHING;
    """)
    
    # Mock a relationship triple
    batch = [("Q_TEST_ORG_1", "Q_TEST_CITY", "HEADQUARTERED_IN")]
    ingestor._process_rel_batch(batch)
    
    # Check if the relationship was created
    result = db.execute_query("""
        SELECT count(*) FROM entity_relationships 
        WHERE relationship_type = 'HEADQUARTERED_IN';
    """, fetch=True)
    assert result[0]['count'] >= 1

def test_03_apache_age_sync(db, ingestor):
    """Verify that relational data is mirrored into the property graph."""
    ingestor.sync_to_age_graph()
    
    # Query the graph using Cypher
    cypher_query = """
        SELECT * FROM cypher('pia_graph', $$
            MATCH (a:ENTITY {name: "Test Intelligence Agency"})-[:HEADQUARTERED_IN]->(b:ENTITY)
            RETURN b.name
        $$) as (city_name agtype);
    """
    results = db.execute_query(cypher_query, fetch=True)
    
    assert len(results) >= 1
    # AGE returns data wrapped in quotes/agtype, we just check existence
    assert "Test City" in str(results[0]['city_name'])
