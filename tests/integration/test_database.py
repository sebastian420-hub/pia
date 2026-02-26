import pytest

def test_extensions_installed(cursor):
    """Verify all 5 core extensions are enabled in the database."""
    cursor.execute("SELECT extname FROM pg_extension;")
    extensions = [row[0] for row in cursor.fetchall()]
    
    required_extensions = {
        'postgis', 
        'vector', 
        'vectorscale', 
        'timescaledb', 
        'age', 
        'pg_cron'
    }
    
    installed_extensions = set(extensions)
    for ext in required_extensions:
        assert ext in installed_extensions, f"Missing required extension: {ext}"

def test_layer1_hypertables_exist(cursor):
    """Verify telemetry hypertables were created."""
    cursor.execute("SELECT hypertable_name FROM timescaledb_information.hypertables;")
    hypertables = [row[0] for row in cursor.fetchall()]
    
    expected = {'flight_tracks', 'vessel_positions', 'satellite_positions', 'seismic_events'}
    for table in expected:
        assert table in hypertables, f"Hypertable missing: {table}"

def test_layer2_uir_structure(cursor):
    """Verify the Universal Intelligence Record table and its 3D columns."""
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'intelligence_records';
    """)
    columns = {row[0]: row[1] for row in cursor.fetchall()}
    
    assert 'uid' in columns
    assert 'geo' in columns  # PostGIS point
    assert 'embedding' in columns  # pgvector
    assert 'created_at' in columns # TimescaleDB / Time-series

def test_heartbeat_trigger_active(cursor):
    """Verify the analysis trigger is correctly armed."""
    cursor.execute("""
        SELECT trigger_name 
        FROM information_schema.triggers 
        WHERE event_object_table = 'intelligence_records';
    """)
    triggers = [row[0] for row in cursor.fetchall()]
    assert 'uir_analysis_trigger' in triggers

def test_apache_age_graph_exists(cursor):
    """Verify the pia_graph property graph exists."""
    cursor.execute("LOAD 'age'; SELECT count(*) FROM ag_catalog.ag_graph WHERE name = 'pia_graph';")
    count = cursor.fetchone()[0]
    assert count == 1, "Apache AGE graph 'pia_graph' not found."

def test_geo_seeding_results(cursor):
    """Verify that Tier 1 geographic seeding actually happened."""
    cursor.execute("SELECT count(*) FROM entities WHERE entity_type = 'LOCATION';")
    count = cursor.fetchone()[0]
    assert count >= 30000, f"Expected >30k seeded locations, found {count}."
