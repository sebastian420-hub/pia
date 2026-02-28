import asyncio
from pia.api.mcp_server import mcp
from loguru import logger

async def list_tools():
    tools = await mcp.list_tools()
    logger.info(f"Registered MCP Tools: {[t.name for t in tools]}")
    
    # 1. Test Spatial Search (Mock coordinates near Brownsville/Ardmore)
    # We use Ardmore (where we have a cluster)
    # 34.1743, -97.1436 (Ardmore, OK)
    logger.info("Testing Spatial Search Tool...")
    from pia.api.mcp_server import search_spatial
    results = search_spatial(34.1743, -97.1436, 100.0)
    logger.info(f"Spatial Results: {results}")

if __name__ == "__main__":
    asyncio.run(list_tools())
