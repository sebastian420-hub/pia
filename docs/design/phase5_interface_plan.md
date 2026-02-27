# PIA Phase 5: Interface Layer (OpenClaw & MCP)

## Objective
To connect the Director (You) to the PIA Core using natural language. This phase implements the **Model Context Protocol (MCP)** server, transforming the database into an interactive "ORACLE" that can be queried by any MCP-compliant AI agent (OpenClaw, Claude Desktop, etc.).

---

## 1. Technical Components

### 1.1 The FastMCP Server (`src/pia/api/mcp_server.py`)
A Python-based server that uses the `FastMCP` framework to expose our six-layer data model as callable tools.

### 1.2 Tool Library (The "Intelligence Vocabulary")
We will implement 5 core Tool Groups:
1.  **Entity Group:** `get_entity_profile`, `traverse_graph(hops=2)`
2.  **Intelligence Group:** `search_semantic`, `search_spatial(radius)`
3.  **Analytical Group:** `get_active_clusters`, `get_cluster_timeline`
4.  **Sensory Group:** `get_live_seismic`, `get_system_heartbeat`
5.  **Tasking Group:** `submit_director_instruction` (writes to `analysis_queue`)

### 1.3 Containerization
Update `docker-compose.yml` to include the `mcp_server` as a permanent service on the internal network.

---

## 2. The "Session Start Protocol"
As per the **OpenClaw Integration Doc**, the agent will be programmed to run an orientation sequence every time you open a chat:
1.  **Auto-Query:** Get current system health and unread CRITICAL clusters.
2.  **Context Loading:** Summarize the last 24 hours of global activity.
3.  **Ready State:** Present a "Morning Brief" headline to the Director.

---

## 3. Implementation Sequence

### Step 1: FastMCP Scaffolding
Create the Python server using the `DatabaseManager` to handle sessions.

### Step 2: Tool Implementation (Relational)
Implement the SQL-backed tools for clusters, UIRs, and seismic events.

### Step 3: Tool Implementation (Graph)
Implement the OpenCypher-backed tools for entity relationship traversal (Apache AGE).

### Step 4: OpenClaw Configuration
Draft the `openclaw-config.json` that points to our local container and uses **Kimi K2.5** as the reasoning engine.

### Step 5: Verification (The "Oracle Test")
1.  Connect an agent to the MCP server.
2.  Ask: *"What are the most significant clusters near my seeded locations?"*
3.  **Success Condition:** The agent correctly identifies the Clearlake cluster and cites the specific UIR supporting it.

---

## 4. Security & Governance
*   **ReadOnly by Default:** Most MCP tools will use a read-only database connection to prevent accidental data deletion.
*   **Traceability:** Every question asked by the Director is logged as a `HUMINT` UIR in the database.
