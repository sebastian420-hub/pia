# 🏢 BURMANLABS: Phase 8 UI Architecture & Implementation Plan

**Document Version:** 1.0
**Phase:** 8 (Visualization & User Experience)
**Subject:** Technical Design for the "Sentinel" Relational Command Center

---

## 1. Executive Summary
The primary goal of Phase 8 is to transform the raw backend intelligence swarm into a cinematic, intuitive **Decision Dominance** interface. The current iteration features a bare 3D Cesium globe. To achieve operational utility, the system will evolve into a **Hybrid Relational Architecture**, seamlessly bridging spatial telemetry (The Globe) with semantic reasoning (The Knowledge Web).

---

## 2. Core Interaction Model: "From Dot to Web"
The system must solve the "context deficit" inherent in map-based interfaces. A dot on a map shows *where*, but not *why*.

### 2.1 Dual-View Toggle
The user can seamlessly switch between two macroscopic views:
1.  **The Spatial View (CesiumJS):** A 3D geographic digital twin. Useful for tracking physical assets (vessels, aircraft, seismic events).
2.  **The Relational View (3D Force Graph):** A physics-based, boundless web (`react-force-graph-3d`) representing the Apache AGE knowledge graph. Entities are nodes; AI-extracted connections are edges.

### 2.2 The "Deep Dive" Transition
When a user clicks an active intelligence marker (e.g., a red dot) on the Spatial Globe:
1.  The globe layer dims or blurs.
2.  A localized Force-Graph "blooms" directly out of the clicked point.
3.  The graph reveals the entity's 1st and 2nd-degree connections (e.g., clicking a "Lebanon" event reveals its connections to "Hezbollah" and "Israel").
4.  The user can infinitely zoom and pan through this resulting relational galaxy.

---

## 3. The HUD (Heads-Up Display) Layout
A glassmorphic overlay will sit above the 3D canvases to provide real-time command and control.

### 3.1 The "Live Wire" Ticker (Left Sidebar)
*   **Purpose:** Triage incoming events as they are broadcast over the FastAPI WebSocket.
*   **Structure:** A scrolling list of intelligence cards (Priority Color, Domain, Relative Time, Headline).
*   **Interaction:** Hovering over a card "ghosts" the camera to the event's location on the globe. Clicking locks the camera and opens the Right Sidebar.

### 3.2 Intelligence Deep Dive (Right Sidebar)
*   **Purpose:** Contextualize the selected event or entity.
*   **Structure:**
    *   **AI Summary:** The LLM's automated SITREP.
    *   **Entity Chips:** Clickable tags for extracted entities (People, Orgs, Locations). Clicking a chip flies the user to its node in the Relational Web.
    *   **Confidence Metrics:** Visual representation of the `source_trust` and `semantic_distance` scores.

### 3.3 The Intelligence Terminal (Bottom Panel)
*   **Purpose:** A raw, monospaced "console" streaming the system's internal thoughts.
*   **Structure:** Real-time text logs of the agent swarm's activity:
    *   `[INGEST] OSINT Feed -> ...`
    *   `[ANALYST] Extracting entities...`
    *   `[GRAPH] Created relationship...`
*   **Interaction:** Log entries containing UUIDs or Entities are hyperlinked to trigger camera flights.

### 3.4 The Filter & Triage Bar (Top Edge)
*   **Purpose:** Control signal-to-noise ratio during a massive intelligence surge.
*   **Structure:** Pill-shaped toggles for Domains (`MILITARY`, `CYBER`) and Priorities (`CRITICAL`). A global search input for finding specific entities.

---

## 4. Technical Implementation Plan

### Step 1: API Bridge Extension (`pia-api`)
To support the Relational View, the FastAPI bridge must expose the Knowledge Graph.
1.  **New Endpoint:** `GET /api/v1/graph/network/{entity_name}?hops=2`
2.  **Logic:** Connect via `asyncpg` and execute a Cypher query against the `pia_graph` in Apache AGE.
3.  **Payload:** Return a structured JSON of `nodes` (id, name, group) and `links` (source, target, relationship_type) compatible with `react-force-graph-3d`.

### Step 2: UI Foundation & Dependencies (`pia-ui`)
1.  **Install Styling:** `npm install -D tailwindcss postcss autoprefixer && npx tailwindcss init -p` to implement the dark, glassmorphic HUD.
2.  **Install Animation:** Utilize existing `gsap` for camera flights, and add `framer-motion` for smooth sidebar transitions.
3.  **Install Graph Lib:** `npm install react-force-graph-3d` for the relational web.

### Step 3: Component Construction
1.  **`Layout.tsx`:** The root shell managing the z-index layers (Canvases at `z-0`, HUD at `z-10`).
2.  **`LiveTicker.tsx`:** Consumes the existing `events` state from the WebSocket.
3.  **`TerminalLog.tsx`:** A new WebSocket listener hooked into a broader system-log channel.
4.  **`RelationalWeb.tsx`:** The 3D Force Graph wrapper component.

### Step 4: State Management & Wiring
Implement a global state manager (Zustand or React Context) to handle the `activeEntity` and `viewMode` (Globe vs. Web) so that clicking an item in the Ticker updates both the Right Sidebar and the 3D cameras simultaneously.

---
*End of Design Document.*