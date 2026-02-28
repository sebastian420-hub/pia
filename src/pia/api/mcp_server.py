from fastmcp import FastMCP
from loguru import logger
from typing import List, Dict, Optional
import os
import sys

# Ensure the 'src' directory is in the path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))

from pia.core.database import DatabaseManager

# Initialize FastMCP with a name
mcp = FastMCP("pia-core")
db = DatabaseManager()

# ═══════════════════════════════════════════════════════════
# ANALYTICAL TOOLS
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_active_clusters(limit: int = 10) -> List[Dict]:
    """
    Retrieve currently active intelligence clusters. 
    Use this to see the high-level situation report of the world.
    """
    logger.info(f"MCP Tool: get_active_clusters called (limit={limit})")
    query = """
        SELECT cluster_id, title, domain, priority, status, uir_count, updated_at,
               ST_Y(geo_centroid) as lat, ST_X(geo_centroid) as lon
        FROM intelligence_clusters
        WHERE status = 'ACTIVE'
        ORDER BY priority = 'CRITICAL' DESC, updated_at DESC
        LIMIT %s
    """
    try:
        results = db.execute_query(query, (limit,), fetch=True)
        # Convert objects to standard dicts for MCP compatibility
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"MCP get_active_clusters failed: {e}")
        return [{"error": str(e)}]

@mcp.tool()
def get_cluster_details(cluster_id: str) -> Dict:
    """
    Get detailed information about a specific cluster, including its history and evidence.
    """
    logger.info(f"MCP Tool: get_cluster_details called for {cluster_id}")
    try:
        cluster = db.execute_query("SELECT * FROM intelligence_clusters WHERE cluster_id = %s", (cluster_id,), fetch=True)
        if not cluster:
            return {"error": "Cluster not found"}
        
        uirs = db.execute_query("""
            SELECT uid, content_headline, source_type, created_at
            FROM intelligence_records
            WHERE cluster_id = %s
            ORDER BY created_at DESC
            LIMIT 5
        """, (cluster_id,), fetch=True)
        
        result = dict(cluster[0])
        result['supporting_evidence'] = [dict(u) for u in uirs]
        return result
    except Exception as e:
        logger.error(f"MCP get_cluster_details failed: {e}")
        return {"error": str(e)}

# ═══════════════════════════════════════════════════════════
# TACTICAL & GRAPH TOOLS
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def search_spatial(lat: float, lon: float, radius_km: float = 50.0) -> List[Dict]:
    """
    Search for intelligence records and active clusters near a specific coordinate.
    Use this to check for danger or relevant events near your current location.
    """
    logger.info(f"MCP Tool: search_spatial called (lat={lat}, lon={lon}, radius={radius_km}km)")
    radius_m = radius_km * 1000
    
    query = """
        SELECT 'CLUSTER' as type, cluster_id::text as id, title, domain, priority, 
               ST_Distance(geo_centroid, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) / 1000 as distance_km
        FROM intelligence_clusters
        WHERE ST_DWithin(geo_centroid, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
        AND status = 'ACTIVE'
        UNION ALL
        SELECT 'RECORD' as type, uid::text as id, content_headline as title, domain, priority,
               ST_Distance(geo, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) / 1000 as distance_km
        FROM intelligence_records
        WHERE ST_DWithin(geo, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
        AND created_at > NOW() - INTERVAL '7 days'
        ORDER BY distance_km ASC
        LIMIT 20
    """
    try:
        # We pass coordinates twice for the UNION ALL
        results = db.execute_query(query, (lon, lat, lon, lat, radius_m, lon, lat, lon, lat, radius_m), fetch=True)
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"MCP search_spatial failed: {e}")
        return [{"error": str(e)}]

@mcp.tool()
def get_entity_network(name: str, hops: int = 2) -> Dict:
    """
    Traverse the knowledge graph from an entity outward to find connections.
    Use this to discover hidden relationships between people, organizations, or locations.
    """
    logger.info(f"MCP Tool: get_entity_network called for '{name}' (hops={hops})")
    
    # We use Apache AGE for the graph traversal
    cypher_query = f"""
        LOAD 'age';
        SET search_path = public, ag_catalog;
        SELECT * FROM cypher('pia_graph', $$
            MATCH (a:ENTITY {{name: "{name}"}})
            MATCH path = (a)-[*1..{hops}]-(connected:ENTITY)
            RETURN connected.name, type(relationships(path)[0]), length(path)
        $$) as (connected_name agtype, relationship_type agtype, distance agtype)
        LIMIT 20;
    """
    try:
        results = db.execute_query(cypher_query, fetch=True)
        return {
            "root": name,
            "connections": [dict(r) for r in results],
            "total_connections": len(results)
        }
    except Exception as e:
        logger.error(f"MCP get_entity_network failed: {e}")
        return {"error": str(e)}

@mcp.tool()
def submit_tasking(instruction: str, priority: str = "NORMAL") -> Dict:
    """
    Submit a manual tasking instruction from the Director.
    This creates an entry in the analysis queue for the agents to process.
    Example: 'Focus analysis on the recent border activity'
    """
    logger.info(f"MCP Tool: submit_tasking called: '{instruction}'")
    try:
        # 1. Create a HUMINT UIR for the instruction
        uir_query = """
            INSERT INTO intelligence_records (
                source_type, source_agent, content_headline, content_summary, domain, priority
            ) VALUES ('HUMINT', 'director', 'DIRECTOR TASKING', %s, 'UNKNOWN', %s)
            RETURNING uid
        """
        uir_id = db.execute_query(uir_query, (instruction, priority), fetch=True)[0]['uid']
        
        # 2. Queue the analysis
        queue_query = """
            INSERT INTO analysis_queue (
                trigger_uid, trigger_type, target_id, target_type, priority
            ) VALUES (%s, 'DIRECTOR_TASKED', %s, 'UIR', %s)
            RETURNING queue_id
        """
        queue_id = db.execute_query(queue_query, (uir_id, uir_id, priority), fetch=True)[0]['queue_id']
        
        return {
            "status": "QUEUED",
            "instruction_uir": str(uir_id),
            "queue_id": str(queue_id),
            "message": "Tasking successfully injected into the Agency's brain."
        }
    except Exception as e:
        logger.error(f"MCP submit_tasking failed: {e}")
        return {"error": str(e)}

# ═══════════════════════════════════════════════════════════
# SYSTEM TOOLS
# ═══════════════════════════════════════════════════════════

@mcp.tool()
def get_system_health() -> Dict:
    """
    Check the current status of the PIA Core sensors and brain.
    """
    logger.info("MCP Tool: get_system_health called")
    try:
        stats = db.execute_query("""
            SELECT 
                (SELECT count(*) FROM intelligence_records) as total_records,
                (SELECT count(*) FROM entities) as total_entities,
                (SELECT count(*) FROM analysis_queue WHERE status = 'PENDING') as pending_jobs,
                (SELECT count(*) FROM intelligence_clusters WHERE status = 'ACTIVE') as active_clusters
        """, fetch=True)
        return dict(stats[0])
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    # Start server with SSE transport on all interfaces
    logger.info("Starting PIA MCP Server on port 8000...")
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
