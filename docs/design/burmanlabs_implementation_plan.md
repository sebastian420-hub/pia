# 🚀 BURMANLABS: Technical Implementation Plan

**Phase:** Architecture Upgrade (Single-Tenant to Multi-Tenant SaaS)
**Goal:** Transform the core PIA engine into a secure, multi-tenant enterprise intelligence platform using Row-Level Security (RLS) and dynamic client-based routing.

---

## Phase 1: Database Hardening & Multi-Tenancy (The "Four Faces")
We must upgrade the database to ensure clients can steer the engine and securely view *only* their data.

### 1.1 Add Client Identification to Layer 0 (Mission Control)
*   **Action:** Add `client_id` (UUID) to the `mission_focus` table.
*   **Why:** This allows a VC client and a Military client to have different active missions simultaneously. The swarm will know *who* requested the data.
*   **SQL Change:** `ALTER TABLE mission_focus ADD COLUMN client_id UUID DEFAULT '00000000-0000-0000-0000-000000000000';`

### 1.2 Data Tagging on Core Layers
*   **Action:** Add `client_id` to `intelligence_records` (Layer 2) and `intelligence_clusters` (Layer 3).
*   **Why:** When an agent ingests a record or forms a cluster based on a mission, it tags the resulting intelligence with the client who requested it. (Note: Global non-mission OSINT can be tagged as 'Global' and shared).

### 1.3 Implement Row-Level Security (RLS)
*   **Action:** Enable PostgreSQL RLS on the core tables.
*   **Why:** This physically prevents the API from returning data that belongs to another client, regardless of bugs in the Python code. This is the core of the "One Brain, Four Faces" architecture.
*   **SQL Logic:** 
    ```sql
    ALTER TABLE intelligence_clusters ENABLE ROW LEVEL SECURITY;
    CREATE POLICY client_isolation ON intelligence_clusters 
    USING (client_id = current_setting('app.current_client_id')::UUID OR client_id IS NULL);
    ```

---

## Phase 2: Dynamic Swarm Routing (The Cognitive Upgrade)
The agents must adapt to the client's specific lens when evaluating data.

### 2.1 Pass Client Context through the Queue
*   **Action:** Update the `trigger_analysis_queue()` trigger in `06_system_heartbeat.sql` to carry the `client_id` and the specific `mission_id` into the `analysis_queue`.
*   **Why:** The Analyst Agent needs to know *who* it is analyzing this data for before it calls the LLM.

### 2.2 Dynamic Prompting in `NLPManager`
*   **Action:** Modify `pia-core/src/pia/core/nlp.py`.
*   **Why:** Instead of one static system prompt, the agent will select a prompt based on the mission category.
*   **Logic:**
    *   `if mission.category == 'FINANCIAL':` Inject prompts focusing on *INVESTED_IN, SEC filings, venture capital.*
    *   `elif mission.category == 'MILITARY':` Inject prompts focusing on *DEPLOYED_TO, weapon systems, troop movements.*

---

## Phase 3: The API & UI Gateway (The Dashboards)
Connecting the protected engine to the frontend.

### 3.1 FastAPI Middleware for Client Authentication
*   **Action:** Update `pia-api/main.py`.
*   **Why:** When the React UI connects via WebSocket or REST, the API must authenticate the user, determine their `client_id`, and execute a `SET LOCAL app.current_client_id = '...'` command on the database session before running any queries.

### 3.2 Tailored UI Themes (React/CesiumJS)
*   **Action:** Update `pia-ui/src/App.tsx`.
*   **Why:** Build the visual moat.
*   **Logic:** Implement state-based themes. 
    *   **VC Radar Mode:** Wireframe UI, glowing blue financial nodes, hiding military basemaps.
    *   **Threat Board Mode:** Dark satellite imagery, red pulsing nodes, military tactical symbols (MIL-STD-2525).

---

## Phase 4: Minimum Viable Product (MVP) Execution
To prove the business model (The "Trojan Horse"), we will build the first targeted vertical.

**Target MVP:** The "Follow the Money" Engine / Corporate War Room
*   **Task 1:** Build a specific ingestion agent (e.g., `edgar_agent.py` to pull SEC filings or a `github_agent.py` for tech startups).
*   **Task 2:** Set up a test `client_id`.
*   **Task 3:** Run the system against a real-world target (e.g., "OpenAI" or a specific Oligarch) and record the live 3D visualization.
*   **Task 4:** Package the result as a demo video to pitch to investigative journalists and initial VC prospects.