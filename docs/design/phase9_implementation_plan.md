# PIA Phase 9 Implementation Plan: Strategic Knowledge Underlay & Semantic Correlation

## Executive Summary
The system has successfully completed Phase 8, establishing a real-time data pipeline from raw sensor ingestion to 3D visualization. The immediate next priority is **Phase 9**, which transitions the dashboard from a purely "reactive" live-feed monitor into a "proactive" strategic intelligence tool. This involves massive data seeding, fixing spatial API endpoints, and upgrading the 3D globe to render relational context.

## 1. The Data Density Imperative (The Heavy Seed)
Currently, the system operates on a handful of demo Wikidata entities and a subset of GeoNames. Phase 9 requires high-density context.
*   **Action 1.1:** Finalize and execute the `seed_wikidata5m.py` script to stream and batch-insert the 5 million entity Wikidata dump into `layer5_kg.entities`.
*   **Action 1.2:** Write and execute `seed_geonames_full.py` to ingest the complete 11 million node `allCountries.txt` dataset from GeoNames.
*   **Action 1.3:** Optimize the `populate_embeddings.py` worker to handle batch vector generation (via Kimi K2.5 or a local smaller model to save costs) for these millions of new records.

## 2. API & Backend Rectification
During the transition to Phase 9, several gaps in the data delivery bridge must be addressed to handle the incoming massive data scale.
*   **Action 2.1 (Critical Bug Fix):** The `GET /api/v1/entities/bbox` endpoint in `pia-api/routers.py` currently accepts bounding box parameters (`minLat`, `minLon`, etc.) but the SQL query is a stub. It must be updated to use PostGIS `ST_MakeEnvelope` correctly so it doesn't return the entire database and crash the frontend.
*   **Action 2.2 (Multi-Hop Graph):** The `GET /api/v1/graph/network/{entity_name}` endpoint only supports 1-hop queries. It must be refactored using a recursive CTE (Common Table Expression) or Apache AGE cypher queries to allow operators to traverse 2-hop or 3-hop relationships.

## 3. Analyst Agent Upgrade: Semantic Geo-Tagging
The `AnalystAgent` (Kimi K2.5) successfully extracts entities but often leaves them without coordinates if the raw text doesn't specify them.
*   **Action 3.1:** Update the `process_intelligence_components` function in `pia-core/src/pia/agents/analyst_agent.py`. If a UIR mentions an organization (e.g., "Hamas"), the agent must query the Knowledge Graph to find its known anchor locations and retroactively apply those coordinates (`semantic geo-tagging`) to the live event.

## 4. 3D Globe Visualization Enhancements
The `pia-ui` dashboard must evolve to render relationships globally, not just as a 2D sidebar.
*   **Action 4.1 (Relational Arcs):** When an entity is selected on the globe, the UI should render 3D parabolic arcs (using Cesium `PolylineGraphics` with glowing materials) connecting it to its known associates directly across the planet.
*   **Action 4.2 (Cluster Heatmaps):** The system generates `intelligence_clusters`, but they are invisible. Implement a spatial heatmap layer on the Cesium globe that renders active clusters as red/orange gradient zones, providing immediate visual threat context before zooming in.

## Execution Order
1.  Fix API Bug (`routers.py` bbox query).
2.  Implement 3D Relational Arcs on the Cesium globe.
3.  Upgrade the `AnalystAgent` for Semantic Geo-tagging.
4.  Execute the Heavy Seed (Wikidata + GeoNames).
