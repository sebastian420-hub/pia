# 🏢 BURMANLABS: Phase 9 UI Architecture - The "Decision Dominance" Upgrade

**Document Version:** 1.0
**Phase:** 9 (Knowledge Underlay & Strategic Context)
**Subject:** Upgrading the dashboard from a Live COP to a Strategic Intelligence Environment.

---

## 1. Objective
The current iteration of the PIA Dashboard successfully visualizes live, high-velocity telemetry (earthquakes, flights). However, it fails to display the engine's "Pre-Knowledge" or correctly map semantic news events that lack explicit GPS coordinates. 

To achieve a true "Military Intelligence" capability, the system must render the **Knowledge Underlay** (pre-seeded entities) and actively resolve unstructured news to physical space using graph-based geo-tagging.

---

## 2. Technical Architecture

### Feature 1: The "Target Deck" (Pre-Knowledge Seeding)
The system currently relies solely on live news to learn about people and organizations. We must seed a baseline "Target Deck."
*   **Database (`entities` table):** Inject high-value targets (HVTs) including global leaders, defense contractors (SpaceX), and military assets.
*   **Alias Resolution:** Utilize the existing `aliases` `text[]` column to map variations ("Elon", "Tesla CEO") to a singular canonical entity ("Elon Musk") to prevent graph fracturing.
*   **Action:** Create a Python seed script (`scripts/seed_target_deck.py`) to inject these entities with baseline embeddings and geographic coordinates.

### Feature 2: Semantic Geo-Tagging (News to Map)
Unstructured OSINT (news) often lacks lat/lon coordinates. Currently, these events bypass the Cesium globe.
*   **Backend (`analyst_agent.py`):** Update the `process_intelligence_components` function. If a new UIR lacks a `geo` coordinate, the agent will query the newly resolved entities. If it finds a resolved entity with a `primary_geo` (e.g., SpaceX HQ), it will update the UIR's geometry to match, effectively pulling the news story onto the map.

### Feature 3: The "Knowledge Underlay" (UI Persistent Globe)
The Cesium globe must reflect the "static" knowledge of the agency, not just live events.
*   **API (`pia-api/main.py`):** Create a new endpoint `GET /api/v1/entities/strategic` that returns the top 200 entities sorted by `threat_score` or `mention_count` that possess coordinates.
*   **UI (`Dashboard.tsx`):** Create a secondary Cesium `<Entity>` collection. These "Knowledge Nodes" will be rendered as small, low-opacity, pulsating hexagons beneath the bright, live intelligence dots.

### Feature 4: Relational Globe Arcs (In-World Insights)
Visualizing connections on the geography, not just in the abstract 3D graph.
*   **UI (`Dashboard.tsx`):** When the "Entity Dossier" is opened for a specific event, query the graph and draw physical Cesium `Polyline` arcs stretching across the globe from the event's location to the locations of its related entities.

---

## 3. Implementation Steps

### Step 1: Execute the Target Deck Seed
1. Write `scripts/seed_target_deck.py`.
2. Define a JSON payload of ~50 strategic entities (SpaceX, UN, Pentagon, key leaders) with strict aliases and coordinates.
3. Run the script against the `pia` PostgreSQL database.

### Step 2: Implement Semantic Geo-Tagging
1. Modify `pia-core/src/pia/agents/analyst_agent.py`.
2. Add logic: `IF record.geo IS NULL -> Look up best entity -> UPDATE record SET geo = entity.primary_geo`.
3. Restart the analyst swarm.

### Step 3: Build the Knowledge Underlay UI
1. Add `/api/v1/entities/strategic` to `pia-api`.
2. Update `Dashboard.tsx` to fetch this list on mount.
3. Render these entities using Resium with a distinct, muted visual style (e.g., `Color.fromCssColorString('rgba(255,255,255,0.1)')`).

---
*End of Plan.*