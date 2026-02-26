# PIA Phase 3: Telemetry & Ingestion Plan
## Objective
To establish a professional, production-grade telemetry ingestion pipeline. This phase transforms the "Static Memory" (the database) into a "Live Intelligence Engine" by connecting the first real-time data feed (USGS Seismic).

---

## 1. Professional Agent Architecture
Every agent in the PIA system will follow the **BaseAgent Pattern** to ensure consistent logging, error handling, and database communication.

### 1.1 Components
*   **Core Logic (`src/pia/core/`):**
    *   `database.py`: Singleton-style `DatabaseManager` for connection pooling.
    *   `base_agent.py`: Abstract Base Class (ABC) defining the lifecycle (`start`, `poll`, `process`, `stop`).
*   **Domain Models (`src/pia/models/`):**
    *   `seismic.py`: Pydantic models to validate incoming USGS GeoJSON data.
*   **Agent Implementation (`src/pia/agents/`):**
    *   `seismic_agent.py`: The concrete implementation of the USGS collector.

---

## 2. Technical Standards
*   **Data Validation:** All incoming external data *must* be validated via Pydantic before touching the database.
*   **Logging:** Use `loguru` for structured, leveled logging (INFO for heartbeat, ERROR for failures).
*   **Idempotency:** Every ingestion must be idempotent. If the agent crashes and restarts, it should not create duplicate records for the same event (achieved via `usgs_id` primary keys).
*   **Heartbeat Awareness:** Every ingestion must write to **both** the Layer 1 table (`seismic_events`) and the Layer 2 table (`intelligence_records`). This ensures the "Analysis Heartbeat" (Trigger) fires correctly.

---

## 3. Implementation Sequence

### Step 1: Core Utilities (The Bridge)
Establish the `DatabaseManager` to handle connections to our custom Postgres/Docker container.
*   File: `src/pia/core/database.py`

### Step 2: The Base Agent Contract
Create the `BaseAgent` class. This ensures that every future agent (OSINT, Flight, etc.) has built-in retry logic and structured logging.
*   File: `src/pia/core/base_agent.py`

### Step 3: Domain Modeling (The Schema)
Define the `SeismicEvent` Pydantic model. This acts as the "contract" between the USGS API and our database.
*   File: `src/pia/models/seismic.py`

### Step 4: The Seismic Collector (The Ingestion)
Implement the `SeismicAgent`.
*   **API:** Poll `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson` every 60 seconds.
*   **Processing:**
    1.  Fetch GeoJSON.
    2.  Validate each feature via `SeismicEvent` model.
    3.  Check if `usgs_id` already exists (to avoid duplicates).
    4.  **Insert A:** Write raw telemetry to `seismic_events`.
    5.  **Insert B:** Write a high-level summary to `intelligence_records` (UIR).
*   File: `src/pia/agents/seismic_agent.py`

### Step 5: Integration Testing
Verify the "Heartbeat" works.
1.  Start the `SeismicAgent`.
2.  Wait for an insert.
3.  Check the `analysis_queue` table:
    ```sql
    SELECT * FROM analysis_queue WHERE trigger_type = 'NEW_UIR';
    ```
4.  **Success Condition:** Inserting one earthquake results in one `seismic_events` row AND one `analysis_queue` entry.

---

## 4. Why This is the "Best Practice"
1.  **Decoupling:** If the USGS changes their API, you only change the Pydantic model, not the entire agent.
2.  **Scalability:** The `DatabaseManager` ensures we don't overwhelm Postgres with too many open connections.
3.  **Observability:** Because every agent uses the same `BaseAgent` pattern, you can monitor the health of the entire PIA system from a single log stream.
