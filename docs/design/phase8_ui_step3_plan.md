# 🏢 BURMANLABS: Phase 8 UI Architecture - Step 3 (Active Interrogation)

**Phase:** 8.3 (Active Exploration & AI Co-Pilot)
**Subject:** Implementation Plan for Global Entity Search, Intelligence Archive, and the AI Analyst Chatbot.

---

## 1. Objective
To transition the dashboard from a passive monitoring tool (watching dots appear) into an **Active Intelligence Exploration Platform**. The user must be able to search the graph, review historical data, and ask complex questions using an AI Co-Pilot that understands the current state of the database.

---

## 2. Technical Architecture

### Feature 1: Global Entity Search (The Input Button)
A persistent search bar in the HUD that allows users to instantly query the Knowledge Graph.
*   **UI (`Dashboard.tsx`):** Add an input field next to the "Filter Bar" or top-right controls.
*   **Action:** Submitting a name (e.g., "China") directly sets the `activeGraphEntity` state, bypassing the need to click an event in the Live Ticker. The `RelationalWeb` component will automatically query the API and render the 3D graph.

### Feature 2: The Intelligence Archive
A dedicated dashboard view for historical data analysis.
*   **API (`pia-api/main.py`):** Create `GET /api/v1/archive?page=1&limit=50` to fetch paginated `intelligence_records`.
*   **UI (`src/pages/Archive.tsx`):** A new route (`/archive`). A heavy-duty data table allowing sorting by priority, domain, and date.
*   **Navigation:** Add a toggle in the main `App.tsx` or `Dashboard.tsx` to switch between the "Live COP (Globe)" and the "Archive Ledger".

### Feature 3: The AI Analyst Co-Pilot (Chatbot)
A sliding chat panel that allows the user to interrogate the system using natural language.
*   **API (`pia-api/main.py`):** Create `POST /api/v1/chat`.
    *   **Logic:** Port the reasoning engine from `telegram_voice.py`. The LLM receives the user's prompt alongside a list of available tools (e.g., `get_entity_network`, `search_spatial`). 
    *   **Execution:** If the LLM requests a tool call, the API executes the backend database query, appends the raw JSON result to the context, and asks the LLM to synthesize a tactical insight for the user.
*   **UI (`src/components/hud/AICopilot.tsx`):** A collapsible chat window on the dashboard. It sends messages to the `/api/v1/chat` endpoint and displays the synthesized responses.

---

## 3. Implementation Steps

### Step 1: The AI Co-Pilot Backend (API)
1. Add `openai` to `pia-api` requirements.
2. Build `POST /api/v1/chat` in `main.py` leveraging the existing MCP tool logic to allow the LLM to query the database.

### Step 2: The Archive Backend (API)
1. Build `GET /api/v1/archive` in `main.py` to return historical UIRs.

### Step 3: Global Entity Search (UI)
1. Update `Dashboard.tsx` to include an `<input>` field for direct entity search, wired to `setActiveGraphEntity`.

### Step 4: The Archive Dashboard (UI)
1. Create `Archive.tsx`.
2. Add routing in `App.tsx` to switch between `/` (Globe) and `/archive` (Ledger).

### Step 5: The Co-Pilot Chat Interface (UI)
1. Build `AICopilot.tsx` (a slide-out panel similar to the Dossier).
2. Wire it to the new `/api/v1/chat` endpoint.

---
*End of Plan.*