import inspect
import os
import sys
from typing import Callable, Dict, List

from fastmcp import FastMCP
from loguru import logger

# Ensure the 'src' directory is in the path for internal imports
sys.path.append(os.path.join(os.getcwd(), "src"))

from pia.core.database import DatabaseManager

# Initialize FastMCP with a name
mcp = FastMCP("pia-core")
db = DatabaseManager()

# Plain functions live here so other code (the Telegram bridge) can call them
# directly; they are registered with FastMCP at the bottom of the file.
TOOLS: Dict[str, Callable] = {}


def tool(fn):
    TOOLS[fn.__name__] = fn
    return fn


def call_tool(name: str, args: dict):
    """Calls a registered tool by name after checking the argument names."""
    fn = TOOLS.get(name)
    if fn is None:
        raise KeyError(f"Unknown tool: {name}")
    args = args or {}
    allowed = set(inspect.signature(fn).parameters)
    unknown = set(args) - allowed
    if unknown:
        raise TypeError(f"Unknown arguments for {name}: {sorted(unknown)}")
    return fn(**args)


# ═══════════════════════════════════════════════════════════
# ANALYTICAL TOOLS
# ═══════════════════════════════════════════════════════════

@tool
def get_active_clusters(limit: int = 10) -> List[Dict]:
    """
    Retrieve currently active intelligence clusters.
    Use this to see the high-level situation report of the world.
    """
    limit = max(1, min(int(limit), 100))
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
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"MCP get_active_clusters failed: {e}")
        return [{"error": str(e)}]


@tool
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
        result.pop('semantic_dna', None)  # 1536 floats are noise for an LLM
        result['supporting_evidence'] = [dict(u) for u in uirs]
        return result
    except Exception as e:
        logger.error(f"MCP get_cluster_details failed: {e}")
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════
# TACTICAL & GRAPH TOOLS
# ═══════════════════════════════════════════════════════════

@tool
def search_spatial(lat: float, lon: float, radius_km: float = 50.0) -> List[Dict]:
    """
    Search for intelligence records and active clusters near a specific coordinate.
    Use this to check for danger or relevant events near your current location.
    """
    logger.info(f"MCP Tool: search_spatial called (lat={lat}, lon={lon}, radius={radius_km}km)")
    radius_m = max(0.0, float(radius_km)) * 1000

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
        results = db.execute_query(query, (lon, lat, lon, lat, radius_m, lon, lat, lon, lat, radius_m), fetch=True)
        return [dict(r) for r in results]
    except Exception as e:
        logger.error(f"MCP search_spatial failed: {e}")
        return [{"error": str(e)}]


@tool
def get_entity_network(name: str, hops: int = 2) -> Dict:
    """
    Traverse the knowledge graph from an entity outward to find connections.
    Use this to discover hidden relationships between people, organizations, or locations.
    """
    hops = max(1, min(int(hops), 3))
    logger.info(f"MCP Tool: get_entity_network called for '{name}' (hops={hops})")

    # The name is a Cypher parameter ($name); only the validated hop count is
    # formatted into the query text. AGE column lists must match the RETURN
    # arity, so the three values are returned as one map.
    cypher_query = (
        "MATCH (a:ENTITY {name: $name}) "
        f"MATCH p = (a)-[*1..{hops}]-(connected:ENTITY) "
        "RETURN {name: connected.name, relationship: type(relationships(p)[0]), depth: length(p)}"
    )
    try:
        rows = db.execute_cypher('pia_graph', cypher_query, {"name": name})
        connections = [db.parse_agtype(r['v']) for r in rows]
        return {
            "root": name,
            "connections": connections,
            "total_connections": len(connections)
        }
    except Exception as e:
        logger.error(f"MCP get_entity_network failed: {e}")
        return {"error": str(e)}


@tool
def submit_tasking(instruction: str, priority: str = "NORMAL") -> Dict:
    """
    Submit a manual tasking instruction from the Director.
    This creates an entry in the analysis queue for the agents to process.
    Example: 'Focus analysis on the recent border activity'
    """
    logger.info(f"MCP Tool: submit_tasking called: '{instruction}'")
    priority = priority.upper() if priority else "NORMAL"
    if priority not in ("CRITICAL", "HIGH", "NORMAL", "LOW"):
        priority = "NORMAL"
    try:
        # The heartbeat trigger on intelligence_records queues the analysis job;
        # inserting a second queue row here (without uir_uid) produced a FAILED job.
        uir_query = """
            INSERT INTO intelligence_records (
                source_type, source_agent, source_name, content_headline, content_summary, domain, priority
            ) VALUES ('HUMINT', 'director', 'Director', 'DIRECTOR TASKING', %s, 'UNKNOWN', %s)
            RETURNING uid
        """
        uir_id = db.execute_query(uir_query, (instruction, priority), fetch=True)[0]['uid']
        queued = db.execute_query(
            "SELECT queue_id FROM analysis_queue WHERE uir_uid = %s ORDER BY created_at DESC LIMIT 1",
            (uir_id,), fetch=True
        )
        queue_id = queued[0]['queue_id'] if queued else None

        return {
            "status": "QUEUED",
            "instruction_uir": str(uir_id),
            "queue_id": str(queue_id) if queue_id else None,
            "message": "Tasking successfully injected into the Agency's brain."
        }
    except Exception as e:
        logger.error(f"MCP submit_tasking failed: {e}")
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════
# SYSTEM TOOLS
# ═══════════════════════════════════════════════════════════

@tool
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
                (SELECT count(*) FROM analysis_queue WHERE status = 'FAILED') as failed_jobs,
                (SELECT count(*) FROM intelligence_clusters WHERE status = 'ACTIVE') as active_clusters
        """, fetch=True)
        return dict(stats[0])
    except Exception as e:
        return {"error": str(e)}


# Register the plain functions with FastMCP (works across fastmcp 1.x/2.x).
for _fn in TOOLS.values():
    mcp.tool(_fn)


if __name__ == "__main__":
    # Inside docker the container must bind 0.0.0.0; docker-compose publishes the
    # port on 127.0.0.1 only. Outside docker the default keeps it local.
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))
    logger.info(f"Starting PIA MCP Server on {host}:{port}...")
    mcp.run(transport="sse", host=host, port=port)
