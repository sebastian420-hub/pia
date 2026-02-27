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
