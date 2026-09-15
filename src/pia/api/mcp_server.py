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
def get_entity_network(name: str, hops: int = 1) -> Dict:
    """
    Connections of an entity in the knowledge web (relations computed from events and Wikidata).
    Use this to discover who is linked to a person, organisation or country, with evidence counts.
    """
    hops = max(1, min(int(hops), 2))
    logger.info(f"MCP Tool: get_entity_network('{name}', hops={hops})")
    try:
        root = db.execute_query("""
            SELECT e.entity_id, e.qid, e.name, e.kind, e.description FROM entity_aliases a
            JOIN entities e ON e.entity_id = a.entity_id
            WHERE a.alias_norm = lower(%s) AND e.resolution = 'RESOLVED'
            ORDER BY e.mention_count DESC LIMIT 1
        """, (name,), fetch=True)
        if not root:
            return {"error": f"'{name}' is not in the knowledge web"}
        root = root[0]
        rows = db.execute_query("""
            SELECT CASE WHEN r.a_id = %s THEN r.b_id ELSE r.a_id END AS other_id, r.kind, r.source, r.label,
                   r.event_count, r.weight, r.first_seen, r.last_seen
            FROM relations r WHERE r.a_id = %s OR r.b_id = %s
            ORDER BY r.weight DESC LIMIT 60
        """, (root['entity_id'], root['entity_id'], root['entity_id']), fetch=True) or []
        others = {r['other_id'] for r in rows}
        names = {n['entity_id']: n for n in (db.execute_query(
            "SELECT entity_id, qid, name, kind FROM entities WHERE entity_id = ANY(%s)", (list(others),), fetch=True) or [])}
        return {
            "root": {"qid": root['qid'], "name": root['name'], "kind": root['kind'], "description": root['description']},
            "connections": [{
                "name": names.get(r['other_id'], {}).get('name'), "qid": names.get(r['other_id'], {}).get('qid'),
                "kind": names.get(r['other_id'], {}).get('kind'), "relation": r['kind'], "label": r['label'],
                "source": r['source'], "events": r['event_count'], "weight": round(float(r['weight']), 3),
                "first_seen": r['first_seen'], "last_seen": r['last_seen'],
            } for r in rows],
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
                source_type, source_id, source_agent, source_name, content_headline, content_raw, body_status, domain, priority
            ) VALUES ('HUMINT', 'director', 'director', 'Director', 'DIRECTOR TASKING', %s, 'OK', 'UNKNOWN', %s)
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
                (SELECT count(*) FROM entities WHERE resolution = 'RESOLVED' AND origin <> 'geonames') as total_entities,
                (SELECT count(*) FROM events) as total_events,
                (SELECT count(*) FROM relations) as total_relations,
                (SELECT count(*) FROM entities WHERE resolution = 'NEEDS_REVIEW') as entities_needing_review,
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
