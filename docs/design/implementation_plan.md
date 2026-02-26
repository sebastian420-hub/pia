# Personal Intelligence Agency (PIA)
## Implementation Plan & Repository Architecture

This document provides a systematic, step-by-step technical implementation plan and a proposed monorepo architecture for building the PIA system, based on the v2.0 Design Document.

---

## 1. Repository Architecture (Monorepo)

A professional monorepo structure is used to maintain clean separation between the "Brain" (Python source) and the "Body" (PostgreSQL, Docker, SQL schemas).

```text
pia-core/
├── .env.example                 # Environment variables template
├── docker-compose.yml           # Local dev infrastructure (Postgres, Redis, PgBouncer)
├── Makefile                     # Shortcut commands for devs
├── pyproject.toml               # Modern Python dependency management
├── README.md
│
├── database/                    # All SQL artifacts
│   ├── schema/                  # 02-06 SQL files defining the 6 layers
│   └── seeds/                   # Raw SQL ingestion scripts (geo, wikidata)
│
├── infra/                       # DevOps & Infrastructure
│   └── postgres/                # Custom build (Timescale + Apache AGE)
│       ├── Dockerfile
│       └── init/                # 01_extensions.sql
│
├── src/                         # The Python App
│   └── pia/                     # Main package
│       ├── core/                # Database clients, models, shared logic
│       ├── agents/              # Autonomous agent implementations
│       ├── ingestion/           # Python wrappers for data loaders
│       └── api/                 # FastMCP server exposing tools to OpenClaw
│
├── scripts/                     # Developer utility scripts (PowerShell/Bash)
│
└── tests/                       # Complete testing suite
    ├── unit/                    # Logic tests (no DB)
    ├── integration/             # Tests requiring a live DB
    └── conftest.py              # Pytest fixtures
```

---

## 2. Systematic Implementation Plan

### Phase 0: Validate the Stack (Day 1, ~2 hours)
**Goal:** Prove every extension works before writing real schema.

*   `docker-compose up` → PostgreSQL 16 running
*   `CREATE EXTENSION postgis` → verify with `ST_Point(0,0)`
*   `CREATE EXTENSION vector` → verify with `'[1,2,3]'::vector`
*   `CREATE EXTENSION timescaledb` → verify `create_hypertable` works
*   `CREATE EXTENSION age` → verify `CREATE GRAPH` works
*   `CREATE EXTENSION pg_cron` → verify `cron.schedule` works

If all five pass: proceed to Phase 1.
If any fail: fix the Docker image now, not after you have written 500 lines of schema SQL. This saves days of debugging, especially for Apache AGE which has strict shared library requirements.

### Phase 1: Core Database & Geographic Seed (Week 1)
**Goal:** Stand up the infrastructure, define the core schemas, and populate the base layer of the world.

1.  **Infrastructure Setup:**
    *   Create a `docker-compose.yml` leveraging PostgreSQL 16.
    *   Use a custom Dockerfile or a pre-built image to ensure all 5 critical extensions are installed: `postgis`, `pgvector`, `pgvectorscale`, `timescaledb`, and `age`.
    *   Start the database and run the `01_extensions.sql` script to enable them.
2.  **Schema Creation (Phase 1):**
    *   Execute SQL for Layer 1 (Telemetry hypertables: `flight_tracks`, `seismic_events`).
    *   Execute SQL for Layer 2 (`intelligence_records` / UIR) with GIST (spatial) and DiskANN (semantic) indexes.
    *   Execute SQL for Layer 3 (`intelligence_clusters`) and Layer 4 (`intelligence_digests`).
3.  **Tier 1 Seeding (Geography):**
    *   Write `database/seeds/geo/ingest_geonames.sql`.
    *   Create a `scripts/seed_geo.ps1` to download `allCountries.zip` from GeoNames and push it to the container.
    *   Run `make seed-geo` to execute the bulk insert (`COPY`) into a foundational `entities` table as `LOCATION` types with PostGIS geometries.

### Phase 2: The Knowledge Graph Seed (Week 2)
**Goal:** Pre-populate the system's "memory" with the world's entities and relationships.

1.  **Phase 2 Schema (Entities & Graph):**
    *   Create the `entities`, `entity_relationships`, and history tables.
    *   Initialize the Apache AGE graph namespace (`pia_graph`).
2.  **Tier 2 Seeding (Wikidata):**
    *   Write `ingestion/wikidata/import_wikidata5m.py`.
    *   Download the Wikidata5M subset.
    *   Import nodes into `entities`.
    *   Import edges into `entity_relationships` and sync them into the Apache AGE cypher layer.

### Phase 3: Telemetry & Ingestion Pipelines (Week 3)
**Goal:** Start the flow of live data and test historical ingest.

1.  **Live Telemetry Agent (Quick Win):**
    *   Write `agents/collectors/seismic_agent.py`.
    *   Poll the USGS GeoJSON feed every 60s and write directly to the `seismic_events` hypertable.
2.  **Live OSINT Pipeline:**
    *   Write a basic RSS or News API scraper (`osint_collector.py`).
    *   Pass articles through a local LLM to extract a summary, headline, and domain tags.
    *   Generate embeddings (e.g., via `text-embedding-3-small` or local equivalent).
    *   Insert as a UIR into `intelligence_records`.
3.  **Historical Ingestion (Background Task):**
    *   Begin running scripts from `ingestion/historical/` to parse static datasets like ACLED (conflict data) into HISTORICAL UIRs.

### Phase 4: The Analysis Heartbeat & Triggers (Week 4)
**Goal:** Make the database "alive" by connecting data ingestion to automated analysis.

1.  **Database Triggers (06_functions_triggers.sql):**
    *   This is the most important function in the entire system. Every UIR insert fires this. The system wakes up here.
    *   Write this in `06_functions_triggers.sql` before any agent runs:

    ```sql
    -- Every UIR insert fires this. The system wakes up here.
    CREATE OR REPLACE FUNCTION trigger_analysis_queue()
    RETURNS TRIGGER AS $$
    BEGIN
        INSERT INTO analysis_queue (
            uir_uid,
            trigger_type,
            geo,
            domain,
            priority,
            status,
            created_at
        ) VALUES (
            NEW.uid,
            'NEW_UIR',
            NEW.geo,
            NEW.domain,
            NEW.priority,
            'PENDING',
            NOW()
        );
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER uir_analysis_trigger
        AFTER INSERT ON intelligence_records
        FOR EACH ROW
        EXECUTE FUNCTION trigger_analysis_queue();
    ```
    *   The moment the first seismic UIR lands, the queue fires, the heartbeat agent picks it up, and the system proves it is alive end-to-end. That validation is everything.
2.  **The Analyst Agent Loop:**
    *   Write `agents/analysts/heartbeat_agent.py`.
    *   This script continuously polls `analysis_queue` for `PENDING` jobs.
    *   When a new UIR arrives, the agent reads it, queries the database for semantic/spatial matches, and either creates a new `intelligence_cluster` or updates an existing one's confidence score.
3.  **Continuous Aggregates:**
    *   Set up TimescaleDB continuous aggregates (e.g., `flight_hourly_anomalies`) and configure `pg_cron` jobs to refresh your materialized views for the globe UI.

### Phase 5: The Interface Layer (Month 2)
**Goal:** Connect the Director (You) to the system using natural language via MCP.

1.  **MCP Server Setup:**
    *   Initialize the `mcp-server` directory using `@pg-mcp/server` or build a custom Python FastMCP server.
    *   Implement the 5 core tool groups defined in the design (e.g., `get_entity_profile`, `search_intelligence_semantic`, `traverse_entity_graph`).
2.  **OpenClaw Configuration:**
    *   Configure the OpenClaw agent to connect to your MCP server.
    *   Implement the "Session Start Protocol" so OpenClaw automatically queries the database for system health, morning briefs, and active anomalies upon startup.
3.  **End-to-End Validation:**
    *   Query OpenClaw: *"Are there any anomalies near the Strait of Hormuz?"*
    *   Verify the agent uses MCP to hit the PostGIS index, traverses the AGE graph, and reads historical UIRs to construct a fully grounded, evidence-backed response.
