# PIA Phase 4: Heartbeat Analyst Agent Plan

## Objective
To implement the "Brain" of the PIA. The Analyst Agent will autonomously monitor the `analysis_queue`, correlate incoming signals with existing world knowledge, and group related records into high-level **Intelligence Clusters**.

---

## 1. Logic Flow: The Reasoning Loop
The Analyst Agent follows a deterministic "Signal-to-Insight" pipeline for every record in the queue:

1.  **Ingestion:** Poll `analysis_queue` for the oldest `PENDING` job.
2.  **Context Retrieval:** Fetch the full Universal Intelligence Record (UIR) associated with the job.
3.  **Spatial Correlation:** Query the `entities` table (Layer 5) using PostGIS to find the nearest significant locations/organizations within a 100km radius.
4.  **Clustering Logic (MVP):**
    *   Search `intelligence_clusters` (Layer 3) for active clusters within the same domain and geographic vicinity.
    *   **Decision:**
        *   **MATCH FOUND:** Attach the UIR to the existing cluster and increment its confidence/count.
        *   **NO MATCH:** Create a new `intelligence_cluster` representing a new unique event.
5.  **Finalization:** Update the `analysis_queue` status to `DONE`.

---

## 2. Technical Components

### 2.1 The Analyst Agent (`src/pia/agents/analyst_agent.py`)
*   Inherits from `BaseAgent`.
*   Uses `DatabaseManager` for all correlations.
*   Operates on a fast poll (every 10–30s) to keep up with incoming telemetry.

### 2.2 Intelligence Cluster Schema (Refinement)
*   Ensure `intelligence_clusters` table is ready to receive:
    *   `title`: Auto-generated summary (e.g., "Seismic Activity near [City Name]").
    *   `geo_centroid`: The geographic center of all events in the cluster.
    *   `uir_count`: How many signals support this insight.

---

## 3. Implementation Sequence

### Step 1: Spatial Reasoning Query
Write a specialized SQL function or Python method to find "Nearby Anchors" for any GPS coordinate. This connects raw signals to the 33k cities we seeded in Phase 1.

### Step 2: The Core Analyst Logic
Implement the `AnalystAgent.poll()` method to:
*   Read the queue.
*   Perform the spatial lookup.
*   Execute the "Cluster or Create" logic.

### Step 3: Containerization
Update `docker-compose.yml` to run the `analyst_agent` as a permanent service alongside the `seismic_agent`.

### Step 4: Verification (The "Grand Loop")
1.  Clear the queue.
2.  Let the `seismic_agent` ingest a new earthquake.
3.  Wait 30 seconds.
4.  **Success Condition:** The `intelligence_clusters` table contains a new entry like "Seismic Activity detected near Anchorage, Alaska," supported by the live earthquake UIR.

---

## 4. Future Expansion (Phase 4.1+)
*   **LLM Enhancement:** Use a local LLM to write more descriptive titles and descriptions for clusters.
*   **Semantic Search:** Use `pgvector` to find clusters that are "conceptually" related even if they aren't geographically close.
