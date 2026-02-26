PERSONAL INTELLIGENCE AGENCY (PIA)

## Complete System \& Database Design Document

### Phase 1 + Phase 2

**Version 2.0 — February 2026**
**Classification: Personal Use**

***

## PREFACE — TWO PHASES, ONE VISION

**Phase 1** builds a *collection and storage system* — a well-organized, indexed corpus of intelligence records with geospatial, temporal, and semantic retrieval. It answers questions about events.

**Phase 2** builds a *living understanding system* — an entity graph with evolving profiles, relationship networks, confidence histories, and a continuous analysis heartbeat. It answers questions about subjects and what they mean.

Both phases share the same PostgreSQL instance. Phase 2 is additive — four new table groups added on top of Phase 1's foundation. Nothing in Phase 1 is thrown away or changed.

***

## PART I — TECHNOLOGY STACK

### Core Database Engine

```sql
-- Single PostgreSQL 16 instance with five extensions
CREATE EXTENSION IF NOT EXISTS postgis;         -- Spatial geometry, geo-indexing
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector: semantic embeddings
CREATE EXTENSION IF NOT EXISTS vectorscale;     -- pgvectorscale: production ANN search
CREATE EXTENSION IF NOT EXISTS timescaledb;     -- Time-series hypertables, compression
CREATE EXTENSION IF NOT EXISTS age;             -- Apache AGE: graph queries (Phase 2)
CREATE EXTENSION IF NOT EXISTS pg_cron;         -- Scheduled jobs inside PostgreSQL
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- Query performance monitoring
```


### Why These Five Extensions Together

| Extension | Role | Key Capability |
| :-- | :-- | :-- |
| **PostGIS** | Spatial intelligence | "All events within 500km of Taiwan" — GiST index [^1] |
| **pgvector** | Semantic memory | "Find records similar in meaning to this" — cosine similarity [^2] |
| **pgvectorscale** | Production vector scale | 28x lower p95 latency vs Pinecone at 50M vectors [^3][^4] |
| **TimescaleDB** | Time-series telemetry | Auto-partitioning, 10:1 compression, continuous aggregates [^5] |
| **Apache AGE** | Knowledge graph | Cypher queries over entity relationship graph (Phase 2) [^6][^7] |

### Supporting Infrastructure

```
PostgreSQL 16 (primary)
├── PgBouncer 1.22 (connection pooling, transaction mode)
├── pg_cron (scheduled agent tasks, aggregate refreshes)
├── Redis 7 (hot cache + pub/sub event bus only)
└── Grafana + pg_stat_statements (query monitoring)
```


### Performance Configuration

```ini
# postgresql.conf — tuned for intelligence workload
shared_buffers = 4GB                    # 25% of RAM
effective_cache_size = 12GB             # 75% of RAM
work_mem = 256MB                        # per-query sort/hash operations
maintenance_work_mem = 1GB              # for index builds
max_parallel_workers_per_gather = 4     # parallel query execution
max_parallel_workers = 8
wal_level = replica                     # enable WAL archiving
archive_mode = on
checkpoint_completion_target = 0.9
random_page_cost = 1.1                  # SSD-optimized
```


***

## PART II — ARCHITECTURAL OVERVIEW

### The Six-Layer Data Model

```
╔══════════════════════════════════════════════════════════════════╗
║  LAYER 6 — CONTINUOUS AGGREGATES (TimescaleDB auto-refresh)     ║
║  Pre-computed views: hourly summaries, domain activity, trends  ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 5 — KNOWLEDGE GRAPH (Phase 2)                            ║
║  Apache AGE + entity/relationship tables                        ║
║  "What do we know about X and who/what is connected to it?"     ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 4 — STRATEGIC DIGESTS                                    ║
║  intelligence_digests                                           ║
║  "What is the state of the world this week?"                    ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 3 — INTELLIGENCE CLUSTERS                                ║
║  intelligence_clusters + cluster_revisions (Phase 2)           ║
║  "What connected patterns are developing?"                      ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 2 — INTELLIGENCE RECORDS (UIR)                           ║
║  intelligence_records                                           ║
║  "What exactly was collected?"                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 1 — RAW TELEMETRY (TimescaleDB hypertables)              ║
║  flight_tracks, satellite_positions, seismic_events             ║
║  "Where was X at exactly what time?"                            ║
╚══════════════════════════════════════════════════════════════════╝

Supporting: analysis_queue (Phase 2 heartbeat)
            agent_tasks (observability)
            Redis (hot cache, pub/sub only)
```


### Data Flow — How Information Moves

```
WORLD (APIs, scrapers, feeds)
        ↓ agents collect + normalize
LAYER 1 telemetry (raw positions)
LAYER 2 UIRs (intelligence records)
        ↓ Redis pub/sub fires on every INSERT
ANALYSIS QUEUE (Phase 2 heartbeat picks up)
        ↓ Analyst Agent processes queue
LAYER 3 clusters CREATED or REVISED
        ↓ if revised, cluster_revision written
LAYER 5 entity profiles UPDATED
LAYER 5 relationships UPDATED or CREATED
        ↓ Report Writer Agent (cron)
LAYER 4 digest WRITTEN
LAYER 6 continuous aggregates AUTO-REFRESH
        ↓ Globe + ORACLE consume
YOU (Telegram, dashboard, terminal)
```


***

## PART III — PHASE 1 SCHEMA

### LAYER 1A: Flight Tracks

```sql
-- ════════════════════════════════════════════════════════════════
-- FLIGHT TRACKS
-- Source: OpenSky Network REST API (5-second cadence)
-- Writer: GEOINT Agent
-- Consumers: SENTINEL globe (ScatterplotLayer + TripsLayer)
--            Anomaly Detector Agent
-- ════════════════════════════════════════════════════════════════

CREATE TABLE flight_tracks (
    -- Partition key (TimescaleDB requirement)
    time              TIMESTAMPTZ NOT NULL,

    -- Aircraft identity
    icao24            TEXT NOT NULL,        -- unique ICAO hex address
    callsign          TEXT,                 -- flight number (nullable)
    registration      TEXT,                 -- tail number if known

    -- Position (PostGIS WGS84)
    position          GEOMETRY(Point, 4326) NOT NULL,
    altitude_ft       INTEGER,
    speed_kts         FLOAT,
    heading           FLOAT,               -- degrees, true north
    vertical_rate     FLOAT,               -- ft/min, negative = descending
    on_ground         BOOLEAN DEFAULT FALSE,
    squawk            TEXT,                -- transponder squawk code

    -- Anomaly scoring (written by Anomaly Detector Agent)
    anomaly_score     FLOAT DEFAULT 0.0
                          CHECK (anomaly_score BETWEEN 0.0 AND 1.0),
    anomaly_type      TEXT,               -- TRANSPONDER_OFF|ALTITUDE_SPIKE
                                          -- ROUTE_DEVIATION|SPEED_ANOMALY
    anomaly_flagged_at TIMESTAMPTZ,

    PRIMARY KEY (time, icao24)
);

-- Convert to TimescaleDB hypertable
-- Chunks by day: each day's data is one physical chunk
SELECT create_hypertable('flight_tracks', 'time',
    chunk_time_interval => INTERVAL '1 day');

-- Indexes
CREATE INDEX idx_ft_position ON flight_tracks
    USING GIST(position);                   -- spatial: "all aircraft near X"

CREATE INDEX idx_ft_icao_time ON flight_tracks
    (icao24, time DESC);                    -- "track history for this aircraft"

CREATE INDEX idx_ft_anomaly ON flight_tracks
    (anomaly_score DESC, time DESC)
    WHERE anomaly_score > 0.7;              -- "all flagged aircraft" — partial index

CREATE INDEX idx_ft_squawk ON flight_tracks
    (squawk, time DESC)
    WHERE squawk IN ('7700','7600','7500'); -- emergency squawk codes only

-- Compression: after 7 days, compress to ~10% original size
-- Queries remain transparent — TimescaleDB decompresses on-the-fly
SELECT add_compression_policy('flight_tracks',
    compress_after => INTERVAL '7 days');

-- Retention: drop data older than 1 year
SELECT add_retention_policy('flight_tracks',
    drop_after => INTERVAL '1 year');

-- Continuous aggregate: hourly anomaly counts per region
-- Pre-computed every 5 minutes — globe heatmap reads this, not raw table
CREATE MATERIALIZED VIEW flight_hourly_anomalies
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    COUNT(*) FILTER (WHERE anomaly_score > 0.7) AS anomaly_count,
    AVG(anomaly_score) AS avg_anomaly_score,
    ST_Collect(position) AS positions
FROM flight_tracks
GROUP BY bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('flight_hourly_anomalies',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');
```

**Design Insights:**

- **Composite primary key `(time, icao24)`** prevents duplicate records if the ingestor retries on network failure — idempotent inserts
- **Partial index on emergency squawks** (`7700`=emergency, `7600`=radio failure, `7500`=hijacking) covers only ~0.01% of rows but enables instant detection of critical events
- **Continuous aggregate for heatmap** means the SENTINEL globe never queries millions of raw rows — it reads the pre-aggregated view. New data automatically included via real-time aggregation[^5][^8]
- **`anomaly_score` lives on the raw table**, not a separate table — globe reads a single row to decide whether to highlight an aircraft

***

### LAYER 1B: Satellite Positions

```sql
-- ════════════════════════════════════════════════════════════════
-- SATELLITE POSITIONS
-- Source: CelesTrak TLE + SGP4 orbital propagation (30s cadence)
-- Writer: GEOINT Agent
-- ════════════════════════════════════════════════════════════════

CREATE TABLE satellite_positions (
    time              TIMESTAMPTZ NOT NULL,
    norad_id          INTEGER NOT NULL,
    name              TEXT,
    category          TEXT CHECK (category IN (
                          'MILITARY','WEATHER','COMMS',
                          'NAVIGATION','OBSERVATION','ISS','DEBRIS'
                      )),
    position          GEOMETRY(Point, 4326) NOT NULL,  -- ground track
    altitude_km       FLOAT,
    velocity_kms      FLOAT,
    inclination_deg   FLOAT,
    tle_epoch         TIMESTAMPTZ,  -- TLE validity timestamp
    country_origin    TEXT,

    PRIMARY KEY (time, norad_id)
);

SELECT create_hypertable('satellite_positions', 'time',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX idx_sat_position ON satellite_positions USING GIST(position);
CREATE INDEX idx_sat_category ON satellite_positions(category, time DESC);
CREATE INDEX idx_sat_country ON satellite_positions(country_origin, time DESC);

SELECT add_compression_policy('satellite_positions', INTERVAL '7 days');
SELECT add_retention_policy('satellite_positions', INTERVAL '1 year');
```


***

### LAYER 1C: Seismic Events

```sql
-- ════════════════════════════════════════════════════════════════
-- SEISMIC EVENTS
-- Source: USGS GeoJSON real-time feed (60s polling)
-- Writer: GEOINT Agent
-- Note: sparse events — no compression needed
-- ════════════════════════════════════════════════════════════════

CREATE TABLE seismic_events (
    time              TIMESTAMPTZ NOT NULL,
    usgs_id           TEXT NOT NULL,
    position          GEOMETRY(Point, 4326) NOT NULL,
    depth_km          FLOAT,
    magnitude         FLOAT NOT NULL,
    magnitude_type    TEXT,           -- Mw|ML|Md|mb
    location_name     TEXT,
    felt_reports      INTEGER DEFAULT 0,
    tsunami_warning   BOOLEAN DEFAULT FALSE,
    updated_at        TIMESTAMPTZ,

    PRIMARY KEY (time, usgs_id)
);

SELECT create_hypertable('seismic_events', 'time');
CREATE INDEX idx_seis_position ON seismic_events USING GIST(position);
CREATE INDEX idx_seis_magnitude ON seismic_events(magnitude DESC, time DESC);
CREATE INDEX idx_seis_tsunami ON seismic_events(time DESC)
    WHERE tsunami_warning = TRUE;

SELECT add_retention_policy('seismic_events', INTERVAL '5 years');
-- No compression: seismic events are sparse, keep full fidelity indefinitely
```


***

### LAYER 1D: Vessel Positions

```sql
-- ════════════════════════════════════════════════════════════════
-- VESSEL POSITIONS (AIS — Automatic Identification System)
-- Source: MarineTraffic API (30s cadence for watched vessels)
-- Writer: GEOINT Agent
-- ════════════════════════════════════════════════════════════════

CREATE TABLE vessel_positions (
    time              TIMESTAMPTZ NOT NULL,
    mmsi              TEXT NOT NULL,         -- vessel identifier
    name              TEXT,
    vessel_type       TEXT,                  -- CARGO|TANKER|MILITARY|etc
    flag              TEXT,                  -- country of registration
    position          GEOMETRY(Point, 4326) NOT NULL,
    speed_kts         FLOAT,
    heading           FLOAT,
    destination       TEXT,
    eta               TIMESTAMPTZ,
    anomaly_score     FLOAT DEFAULT 0.0,

    PRIMARY KEY (time, mmsi)
);

SELECT create_hypertable('vessel_positions', 'time',
    chunk_time_interval => INTERVAL '1 day');

CREATE INDEX idx_vessel_position ON vessel_positions USING GIST(position);
CREATE INDEX idx_vessel_type ON vessel_positions(vessel_type, time DESC);
CREATE INDEX idx_vessel_anomaly ON vessel_positions(anomaly_score DESC)
    WHERE anomaly_score > 0.7;

SELECT add_compression_policy('vessel_positions', INTERVAL '7 days');
SELECT add_retention_policy('vessel_positions', INTERVAL '1 year');
```


***

### LAYER 2: Universal Intelligence Record (UIR)

The core table. Every agent writes here. This is the universal contract.

```sql
-- ════════════════════════════════════════════════════════════════
-- UNIVERSAL INTELLIGENCE RECORD (UIR)
-- The spine of the entire system.
-- Every agent writes here. Every analysis reads from here.
-- One record per collected intelligence item.
-- APPEND ONLY — never UPDATE, only INSERT new versions.
-- ════════════════════════════════════════════════════════════════

CREATE TABLE intelligence_records (

    -- ── IDENTITY ────────────────────────────────────────────────
    uid               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ── PROVENANCE ──────────────────────────────────────────────
    -- Mandatory. Every record must be fully traceable.
    source_type       TEXT NOT NULL CHECK (source_type IN (
                          'OSINT',      -- open-source intelligence
                          'GEOINT',     -- geospatial/positional
                          'SIGINT',     -- signals/keyword triggered
                          'TECHINT',    -- technical/infrastructure
                          'FININT',     -- financial intelligence
                          'HUMINT',     -- Director manual input
                          'DERIVED',    -- Analyst Agent cross-correlation
                          'SYSTEM'      -- infrastructure/engineering logs
                      )),
    source_agent      TEXT NOT NULL,    -- 'osint_collector_v1', 'cortex', etc.
    source_url        TEXT,             -- origin URL if applicable
    source_name       TEXT,             -- human-readable source name
    source_credibility FLOAT DEFAULT 0.5
                          CHECK (source_credibility BETWEEN 0.0 AND 1.0),
    agent_task_id     UUID,             -- → agent_tasks.task_id

    -- ── ASSESSMENT ──────────────────────────────────────────────
    confidence        FLOAT CHECK (confidence BETWEEN 0.0 AND 1.0),
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN (
                          'CRITICAL','HIGH','NORMAL','LOW'
                      )),
    classification    TEXT DEFAULT 'UNCLASSIFIED',
    verified          BOOLEAN DEFAULT FALSE,      -- Counterintel approval
    verified_at       TIMESTAMPTZ,
    verified_by       TEXT,                       -- which agent verified

    -- ── CONTENT (Three Zoom Levels) ─────────────────────────────
    -- Never throw away raw data. Never START with raw data.
    content_headline  TEXT,      -- 1 line: globe tooltips, alert tickers
    content_summary   TEXT,      -- 2-3 sentences: Claude analysis, ORACLE
    content_raw       TEXT,      -- full original text/data: deep dives, audit

    -- ── CLASSIFICATION TAXONOMY ─────────────────────────────────
    entities          TEXT[],    -- extracted: people, orgs, places, vessels
    tags              TEXT[],    -- free-form domain tags
    domain            TEXT CHECK (domain IN (
                          'MILITARY','MARITIME','AVIATION','CYBER',
                          'FINANCIAL','POLITICAL','NATURAL','INFRASTRUCTURE',
                          'PERSONNEL','UNKNOWN'
                      )),
    event_type        TEXT,      -- ANOMALY|ALERT|PATTERN|REPORT|EVENT

    -- ── GEOSPATIAL ──────────────────────────────────────────────
    -- Every record should answer "where?" even if imprecise.
    -- A news article about Iran → geo = Iran centroid, precision = 'country'
    geo               GEOMETRY(Point, 4326),
    geo_precision     TEXT CHECK (geo_precision IN (
                          'exact',      -- GPS coordinate, <100m accuracy
                          'city',       -- city-level, ±10km
                          'region',     -- province/state, ±100km
                          'country',    -- nation-level centroid
                          'global'      -- no specific location
                      )),
    geo_bbox          GEOMETRY(Polygon, 4326),  -- area of interest if not point

    -- ── SEMANTIC MEMORY ─────────────────────────────────────────
    -- Every record embedded for semantic similarity search.
    -- pgvectorscale StreamingDiskANN index at scale [web:207]
    embedding         VECTOR(1536),    -- text-embedding-3-large dimensions

    -- ── RELATIONSHIPS ───────────────────────────────────────────
    linked_uids       UUID[],      -- related UIRs (append-only versioning)
    supersedes_uid    UUID,        -- if this record updates a previous one
    cluster_id        UUID,        -- → intelligence_clusters.cluster_id
    layer1_refs       JSONB,       -- refs to raw telemetry
                                   -- {"flights": [{icao24, time_range}]}

    -- ── LIFECYCLE ───────────────────────────────────────────────
    ttl               TIMESTAMPTZ, -- NULL = permanent
    version           INTEGER DEFAULT 1,
    metadata          JSONB        -- agent-specific flexible data

);

-- ══════════════════════════════════════════════════════════════
-- INDEXES — optimized for three-dimensional retrieval
-- Time + Space + Semantic simultaneously
-- ══════════════════════════════════════════════════════════════

-- Time (most queries filter by recency first)
CREATE INDEX idx_uir_time
    ON intelligence_records(created_at DESC);

-- Spatial (PostGIS GIST — proximity queries)
CREATE INDEX idx_uir_geo
    ON intelligence_records USING GIST(geo)
    WHERE geo IS NOT NULL;

-- Semantic (pgvectorscale StreamingDiskANN — production ANN search)
-- 28x lower latency than Pinecone at 50M vectors [web:179]
CREATE INDEX idx_uir_embedding
    ON intelligence_records
    USING diskann(embedding vector_cosine_ops);

-- Domain + time (filtered scans by discipline)
CREATE INDEX idx_uir_domain
    ON intelligence_records(domain, created_at DESC);

CREATE INDEX idx_uir_source_type
    ON intelligence_records(source_type, created_at DESC);

-- Priority (alert queue — partial index on actionable records only)
CREATE INDEX idx_uir_priority
    ON intelligence_records(priority, created_at DESC)
    WHERE priority IN ('CRITICAL','HIGH');

-- Entity search (GIN for array containment @> operator)
CREATE INDEX idx_uir_entities
    ON intelligence_records USING GIN(entities);

CREATE INDEX idx_uir_tags
    ON intelligence_records USING GIN(tags);

-- Cluster membership
CREATE INDEX idx_uir_cluster
    ON intelligence_records(cluster_id)
    WHERE cluster_id IS NOT NULL;

-- Unverified high-priority (Counterintel review queue)
CREATE INDEX idx_uir_review
    ON intelligence_records(created_at DESC)
    WHERE verified = FALSE AND priority IN ('CRITICAL','HIGH');

-- Partial index for DERIVED records (Analyst output)
CREATE INDEX idx_uir_derived
    ON intelligence_records(created_at DESC, confidence DESC)
    WHERE source_type = 'DERIVED';
```

**Design Insights:**

- **Three content fields** serve three different consumers. The globe reads `content_headline`. Claude reads `content_summary`. The audit trail reads `content_raw`. One write serves all three use cases without redundant storage[^9]
- **`geo` on every record** even at country precision enables spatial joins between OSINT text articles and GEOINT flight tracks — this cross-domain correlation is the highest-value query in the entire system
- **pgvectorscale StreamingDiskANN index** instead of standard pgvector ivfflat — 28x lower latency at production scale, stores index on disk rather than RAM, critical for a corpus that grows to millions of records[^4][^3]
- **`supersedes_uid`** enables explicit versioning — when new intelligence contradicts old, write a new UIR pointing to the old one. Old record preserved for audit. New record is the current truth
- **Append-only** is an architectural guarantee, not just a convention. No `UPDATE` statements on `intelligence_records`. Ever.

***

### LAYER 3: Intelligence Clusters

```sql
-- ════════════════════════════════════════════════════════════════
-- INTELLIGENCE CLUSTERS
-- The system's "opinions" about patterns in the world.
-- One record per detected correlation or developing situation.
-- Written by: Analyst Agent (via DBSCAN + semantic search)
-- Updated: every time new corroborating UIRs arrive
-- Globe reads this table for anomaly highlighting
-- ════════════════════════════════════════════════════════════════

CREATE TABLE intelligence_clusters (

    -- ── IDENTITY ────────────────────────────────────────────────
    cluster_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ── CLASSIFICATION ──────────────────────────────────────────
    title             TEXT NOT NULL,
    description       TEXT,        -- 3-5 sentence analyst assessment
    cluster_type      TEXT CHECK (cluster_type IN (
                          'ANOMALY',       -- detected deviation from baseline
                          'PATTERN',       -- recurring behavior identified
                          'THREAT',        -- potential threat correlation
                          'EVENT',         -- significant discrete occurrence
                          'TREND',         -- developing situation over time
                          'RELATIONSHIP'   -- entity connection identified
                      )),
    domain            TEXT,        -- MILITARY|MARITIME|CYBER|etc

    -- ── ASSESSMENT ──────────────────────────────────────────────
    confidence        FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    status            TEXT DEFAULT 'ACTIVE' CHECK (status IN (
                          'ACTIVE',           -- ongoing, being monitored
                          'ESCALATING',       -- confidence rising rapidly
                          'RESOLVED',         -- situation concluded
                          'MONITORING',       -- low-level watch status
                          'FALSE_POSITIVE'    -- dismissed after review
                      )),
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN (
                          'CRITICAL','HIGH','NORMAL','LOW'
                      )),

    -- ── GEOSPATIAL ──────────────────────────────────────────────
    geo_centroid      GEOMETRY(Point, 4326),
    geo_bbox          GEOMETRY(Polygon, 4326),   -- bounding box of all UIRs
    geo_radius_km     FLOAT,                     -- max distance from centroid

    -- ── TEMPORAL SPAN ───────────────────────────────────────────
    event_start       TIMESTAMPTZ,
    event_end         TIMESTAMPTZ,
    duration          INTERVAL GENERATED ALWAYS AS
                          (event_end - event_start) STORED,

    -- ── COMPOSITION ─────────────────────────────────────────────
    uir_count         INTEGER DEFAULT 0,
    source_types      TEXT[],      -- disciplines contributing: [OSINT,GEOINT]
    key_entities      TEXT[],      -- most significant entities
    domains           TEXT[],      -- all domains involved

    -- ── SEMANTIC ────────────────────────────────────────────────
    -- Cluster-level embedding (average of constituent UIR embeddings)
    -- Enables "find clusters similar to this situation"
    embedding         VECTOR(1536),

    -- ── RELATIONSHIPS ───────────────────────────────────────────
    linked_clusters   UUID[],      -- related/overlapping clusters
    digest_id         UUID,        -- → Layer 4: digest that summarized this

    -- ── METHODOLOGY ─────────────────────────────────────────────
    correlation_method TEXT,       -- DBSCAN|SEMANTIC|TEMPORAL|SPATIAL|MANUAL
    analyst_notes     TEXT,

    metadata          JSONB
);

CREATE INDEX idx_cluster_centroid ON intelligence_clusters
    USING GIST(geo_centroid) WHERE geo_centroid IS NOT NULL;

CREATE INDEX idx_cluster_bbox ON intelligence_clusters
    USING GIST(geo_bbox) WHERE geo_bbox IS NOT NULL;

CREATE INDEX idx_cluster_status ON intelligence_clusters
    (status, priority, updated_at DESC);

CREATE INDEX idx_cluster_embedding ON intelligence_clusters
    USING diskann(embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

CREATE INDEX idx_cluster_domain ON intelligence_clusters
    (domain, cluster_type, updated_at DESC);

-- Foreign key: UIRs reference their cluster
ALTER TABLE intelligence_records
    ADD CONSTRAINT fk_uir_cluster
    FOREIGN KEY (cluster_id)
    REFERENCES intelligence_clusters(cluster_id)
    ON DELETE SET NULL;
```


***

### LAYER 4: Strategic Digests

```sql
-- ════════════════════════════════════════════════════════════════
-- INTELLIGENCE DIGESTS
-- Finished intelligence products. One per reporting period.
-- Written by: Report Writer Agent (cron-triggered)
-- Consumers: OpenClaw → Telegram delivery, ORACLE dashboard
-- ════════════════════════════════════════════════════════════════

CREATE TABLE intelligence_digests (

    digest_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ── SCOPE ───────────────────────────────────────────────────
    period_start      TIMESTAMPTZ NOT NULL,
    period_end        TIMESTAMPTZ NOT NULL,
    digest_type       TEXT CHECK (digest_type IN (
                          'DAILY_BRIEF',       -- 0700 automatic
                          'WEEKLY_SUMMARY',    -- Sunday night
                          'DOMAIN_REPORT',     -- deep domain dive
                          'SITREP',            -- situation report on-demand
                          'ALERT_DIGEST',      -- critical event summary
                          'ENTITY_PROFILE'     -- on-demand entity deep dive
                      )),
    domain            TEXT DEFAULT 'GLOBAL',

    -- ── CONTENT ─────────────────────────────────────────────────
    title             TEXT NOT NULL,
    content           TEXT NOT NULL,    -- full formatted Markdown report
    key_developments  TEXT[],           -- top 3-5 bullet headlines
    executive_summary TEXT,             -- 2-paragraph summary

    -- ── COMPOSITION ─────────────────────────────────────────────
    cluster_count     INTEGER,
    uir_count         INTEGER,
    cluster_ids       UUID[],           -- clusters included in this digest
    new_clusters      INTEGER DEFAULT 0,
    escalated_clusters INTEGER DEFAULT 0,

    -- ── DELIVERY ────────────────────────────────────────────────
    delivered         BOOLEAN DEFAULT FALSE,
    delivery_channel  TEXT,             -- TELEGRAM|EMAIL|DASHBOARD
    delivered_at      TIMESTAMPTZ,

    metadata          JSONB
);

CREATE INDEX idx_digest_period ON intelligence_digests(period_end DESC);
CREATE INDEX idx_digest_type ON intelligence_digests
    (digest_type, domain, period_end DESC);
CREATE INDEX idx_digest_pending ON intelligence_digests(created_at DESC)
    WHERE delivered = FALSE;
```


***

### Supporting Tables (Phase 1)

```sql
-- ════════════════════════════════════════════════════════════════
-- AGENT TASK LOG
-- Every agent logs every task. Full observability.
-- Alert if any agent has no DONE task in >30 minutes.
-- ════════════════════════════════════════════════════════════════

CREATE TABLE agent_tasks (
    task_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,

    agent             TEXT NOT NULL,
    task_type         TEXT NOT NULL,    -- 'collect'|'analyze'|'deploy'|'report'
    input             JSONB,
    output            JSONB,

    status            TEXT DEFAULT 'PENDING' CHECK (status IN (
                          'PENDING','RUNNING','DONE','FAILED','RETRYING'
                      )),
    duration_ms       INTEGER,
    retry_count       INTEGER DEFAULT 0,
    error_message     TEXT,

    uirs_written      UUID[],           -- UIRs produced
    clusters_written  UUID[]            -- clusters produced
);

CREATE INDEX idx_task_agent_time ON agent_tasks(agent, created_at DESC);
CREATE INDEX idx_task_status ON agent_tasks(status, created_at DESC)
    WHERE status NOT IN ('DONE');
CREATE INDEX idx_task_failed ON agent_tasks(created_at DESC)
    WHERE status = 'FAILED';
```


***

## PART IV — PHASE 2 SCHEMA

### Component A: Entity Graph (Core Tables)

```sql
-- ════════════════════════════════════════════════════════════════
-- ENTITIES
-- Every subject the system has ever encountered becomes a node.
-- Written by: Entity Agent (triggered by every new UIR)
-- This is the living profile of every subject.
-- ════════════════════════════════════════════════════════════════

CREATE TABLE entities (

    -- ── IDENTITY ────────────────────────────────────────────────
    entity_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),

    -- ── CLASSIFICATION ──────────────────────────────────────────
    entity_type       TEXT NOT NULL CHECK (entity_type IN (
                          'PERSON',
                          'ORGANIZATION',
                          'LOCATION',
                          'VESSEL',
                          'AIRCRAFT',
                          'DOMAIN',           -- internet domain
                          'INFRASTRUCTURE',   -- IP, network, facility
                          'EVENT'             -- recurring named event
                      )),
    name              TEXT NOT NULL,
    canonical_name    TEXT,                   -- normalized/official name
    aliases           TEXT[],                 -- alternative names
    description       TEXT,                   -- static factual description

    -- ── LIVING PROFILE ──────────────────────────────────────────
    -- This is the "opinion" — the system's current understanding.
    -- Automatically rewritten by Entity Agent on new evidence.
    current_profile   TEXT,
    profile_updated   TIMESTAMPTZ,
    profile_version   INTEGER DEFAULT 0,

    -- ── INTELLIGENCE ASSESSMENT ─────────────────────────────────
    confidence        FLOAT DEFAULT 0.5
                          CHECK (confidence BETWEEN 0.0 AND 1.0),
    threat_score      FLOAT DEFAULT 0.0
                          CHECK (threat_score BETWEEN 0.0 AND 1.0),
    watch_status      TEXT DEFAULT 'PASSIVE' CHECK (watch_status IN (
                          'PASSIVE',          -- noted but not prioritized
                          'MONITORING',       -- regular collection tasked
                          'ACTIVE',           -- priority collection
                          'CRITICAL'          -- maximum attention
                      )),

    -- ── TEMPORAL TRACKING ───────────────────────────────────────
    first_seen        TIMESTAMPTZ DEFAULT NOW(),
    last_seen         TIMESTAMPTZ DEFAULT NOW(),
    mention_count     INTEGER DEFAULT 0,

    -- ── GEOSPATIAL ──────────────────────────────────────────────
    -- Primary location of this entity (organization HQ, person base, etc.)
    primary_geo       GEOMETRY(Point, 4326),
    geo_precision     TEXT,

    -- ── SEMANTIC ────────────────────────────────────────────────
    embedding         VECTOR(1536),    -- entity profile embedding

    -- ── REFERENCES ──────────────────────────────────────────────
    uir_refs          UUID[],          -- all UIRs mentioning this entity
    cluster_refs      UUID[],          -- clusters involving this entity

    metadata          JSONB
);

CREATE INDEX idx_entity_type ON entities(entity_type, mention_count DESC);
CREATE INDEX idx_entity_name ON entities
    USING GIN(to_tsvector('english', name));
CREATE INDEX idx_entity_aliases ON entities USING GIN(aliases);
CREATE INDEX idx_entity_watch ON entities(watch_status, threat_score DESC);
CREATE INDEX idx_entity_geo ON entities
    USING GIST(primary_geo) WHERE primary_geo IS NOT NULL;
CREATE INDEX idx_entity_embedding ON entities
    USING diskann(embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
```


***

### Component B: Entity Relationships (The Graph Edges)

```sql
-- ════════════════════════════════════════════════════════════════
-- ENTITY RELATIONSHIPS
-- The edges of the knowledge graph.
-- Each row = one directional relationship between two entities.
-- Evidence-backed: every relationship has proof.
-- ════════════════════════════════════════════════════════════════

CREATE TABLE entity_relationships (

    relationship_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),

    -- ── THE EDGE ────────────────────────────────────────────────
    entity_a_id       UUID NOT NULL REFERENCES entities(entity_id)
                          ON DELETE CASCADE,
    entity_b_id       UUID NOT NULL REFERENCES entities(entity_id)
                          ON DELETE CASCADE,

    -- ── RELATIONSHIP TYPE ────────────────────────────────────────
    relationship_type TEXT NOT NULL CHECK (relationship_type IN (
                          -- Organizational
                          'OWNS', 'OWNED_BY',
                          'CONTROLS', 'CONTROLLED_BY',
                          'EMPLOYS', 'EMPLOYED_BY',
                          'AFFILIATED_WITH',
                          'SUBSIDIARY_OF', 'PARENT_OF',
                          -- Operational
                          'OPERATES', 'OPERATED_BY',
                          'LOCATED_IN', 'CONTAINS',
                          'FLEW_TO', 'DEPARTED_FROM',
                          'SAILED_TO', 'SAILED_FROM',
                          -- Intelligence
                          'LINKED_TO',           -- weak/unclear connection
                          'SAME_AS',             -- entity deduplication
                          'CONTRADICTS',         -- conflicting entity
                          'SANCTIONED_BY',
                          'INVESTIGATED_BY',
                          -- Temporal
                          'PRECEDED', 'FOLLOWED',
                          'CO_OCCURRED_WITH'
                      )),

    -- ── EVIDENCE ────────────────────────────────────────────────
    -- Every relationship is proven by specific UIRs
    confidence        FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    evidence_uids     UUID[],          -- UIRs that established this edge
    evidence_count    INTEGER DEFAULT 0,

    -- ── TEMPORAL ────────────────────────────────────────────────
    first_observed    TIMESTAMPTZ DEFAULT NOW(),
    last_confirmed    TIMESTAMPTZ DEFAULT NOW(),
    still_valid       BOOLEAN DEFAULT TRUE,

    -- ── DESCRIPTION ─────────────────────────────────────────────
    description       TEXT,           -- natural language edge description

    -- ── SEMANTIC ────────────────────────────────────────────────
    -- Edge embedding: enables "find relationships similar to this one"
    embedding         VECTOR(1536),

    -- Prevent duplicate edges (same relationship between same entities)
    UNIQUE (entity_a_id, entity_b_id, relationship_type)
);

CREATE INDEX idx_rel_entity_a ON entity_relationships(entity_a_id);
CREATE INDEX idx_rel_entity_b ON entity_relationships(entity_b_id);
CREATE INDEX idx_rel_type ON entity_relationships(relationship_type, confidence DESC);
CREATE INDEX idx_rel_confidence ON entity_relationships(confidence DESC)
    WHERE confidence > 0.7;
CREATE INDEX idx_rel_invalid ON entity_relationships(updated_at DESC)
    WHERE still_valid = FALSE;
```

**Design Insight — Apache AGE for Graph Queries:**

The `entities` + `entity_relationships` tables are standard PostgreSQL. Apache AGE runs **on top of these tables**, enabling Cypher graph queries:[^6][^7]

```cypher
-- "Find all entities within 2 hops of Al Rashid Air Cargo
--  that have sanctions connections"
MATCH (org:Organization {name: 'Al Rashid Air Cargo'})
      -[:OWNS|AFFILIATED_WITH*1..2]->
      (connected)
      -[:SANCTIONED_BY]->
      (authority)
RETURN org, connected, authority, authority.name AS sanctioned_by
ORDER BY connected.confidence DESC;
```

This traversal is impossible in standard SQL without recursive CTEs. Apache AGE makes it a single readable query.[^10][^7]

***

### Component C: Entity Profile History

```sql
-- ════════════════════════════════════════════════════════════════
-- ENTITY PROFILE HISTORY
-- Every time an entity's profile is revised, the old version
-- is preserved here. You can see how understanding evolved.
-- "This entity was a minor note on Feb 4. Critical by Feb 25."
-- ════════════════════════════════════════════════════════════════

CREATE TABLE entity_profile_history (
    history_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id         UUID NOT NULL REFERENCES entities(entity_id)
                          ON DELETE CASCADE,
    revised_at        TIMESTAMPTZ DEFAULT NOW(),

    -- What changed
    previous_profile  TEXT,
    new_profile       TEXT,
    previous_confidence FLOAT,
    new_confidence      FLOAT,
    previous_watch_status TEXT,
    new_watch_status      TEXT,
    previous_threat_score FLOAT,
    new_threat_score      FLOAT,

    -- What caused the revision
    trigger_uid       UUID,           -- UIR that triggered this revision
    trigger_cluster   UUID,           -- cluster that triggered this
    revision_reason   TEXT,           -- natural language: "new sanctions link"
    revised_by        TEXT            -- which agent made the revision
);

CREATE INDEX idx_eph_entity ON entity_profile_history(entity_id, revised_at DESC);
CREATE INDEX idx_eph_time ON entity_profile_history(revised_at DESC);
```


***

### Component D: Cluster Revision History

```sql
-- ════════════════════════════════════════════════════════════════
-- CLUSTER REVISION HISTORY
-- Complete audit trail of how every "opinion" changed over time.
-- The trajectory of confidence IS intelligence.
-- Confidence 0.40 → 0.91 over 3 weeks tells a story.
-- Confidence 0.40 → 0.91 overnight tells a different story.
-- ════════════════════════════════════════════════════════════════

CREATE TABLE cluster_revisions (
    revision_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id        UUID NOT NULL REFERENCES intelligence_clusters(cluster_id)
                          ON DELETE CASCADE,
    revised_at        TIMESTAMPTZ DEFAULT NOW(),

    -- What changed
    previous_confidence  FLOAT,
    new_confidence       FLOAT,
    confidence_delta     FLOAT GENERATED ALWAYS AS
                             (new_confidence - previous_confidence) STORED,
    previous_status      TEXT,
    new_status           TEXT,
    previous_priority    TEXT,
    new_priority         TEXT,
    previous_uir_count   INTEGER,
    new_uir_count        INTEGER,

    -- What caused the revision
    trigger_uid          UUID,        -- UIR that caused this revision
    trigger_entity       UUID,        -- entity update that caused this
    revision_reason      TEXT,
    revised_by           TEXT,        -- agent name

    -- Snapshot of key description at this moment
    description_snapshot TEXT
);

CREATE INDEX idx_cr_cluster ON cluster_revisions(cluster_id, revised_at DESC);
CREATE INDEX idx_cr_delta ON cluster_revisions(confidence_delta DESC)
    WHERE ABS(confidence_delta) > 0.1;  -- significant changes only
```


***

### Component E: Continuous Analysis Queue

```sql
-- ════════════════════════════════════════════════════════════════
-- ANALYSIS QUEUE
-- The heartbeat of the living system.
-- Every new UIR insert triggers a row here via pg_trigger.
-- Analyst Agent polls this table continuously.
-- This is what makes the database "always thinking."
-- ════════════════════════════════════════════════════════════════

CREATE TABLE analysis_queue (
    queue_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),

    -- What triggered this analysis job
    trigger_uid       UUID,           -- new UIR that arrived
    trigger_type      TEXT NOT NULL CHECK (trigger_type IN (
                          'NEW_UIR',          -- new intelligence record
                          'NEW_CLUSTER',      -- new cluster created
                          'ENTITY_UPDATED',   -- entity profile changed
                          'CLUSTER_ESCALATED',-- cluster priority elevated
                          'SCHEDULED',        -- periodic re-analysis
                          'DIRECTOR_TASKED'   -- manual Director instruction
                      )),

    -- What needs to be analyzed
    target_id         UUID,           -- cluster_id, entity_id, or UIR uid
    target_type       TEXT CHECK (target_type IN (
                          'UIR','CLUSTER','ENTITY','DOMAIN','GLOBAL'
                      )),

    -- Processing
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN (
                          'CRITICAL','HIGH','NORMAL','LOW'
                      )),
    status            TEXT DEFAULT 'PENDING' CHECK (status IN (
                          'PENDING','PROCESSING','DONE','FAILED'
                      )),
    assigned_agent    TEXT,
    assigned_at       TIMESTAMPTZ,
    processed_at      TIMESTAMPTZ,
    result_uid        UUID,           -- DERIVED UIR produced from this job
    result_cluster    UUID,           -- cluster updated from this job
    error_message     TEXT
);

CREATE INDEX idx_queue_pending ON analysis_queue(priority DESC, created_at ASC)
    WHERE status = 'PENDING';           -- Analyst Agent polls this index

CREATE INDEX idx_queue_status ON analysis_queue(status, created_at DESC);

-- ── THE HEARTBEAT TRIGGER ────────────────────────────────────────
-- Every INSERT into intelligence_records automatically queues analysis.
-- This is what makes the system react without being asked.

CREATE OR REPLACE FUNCTION trigger_analysis_queue()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO analysis_queue (
        trigger_uid,
        trigger_type,
        target_id,
        target_type,
        priority
    ) VALUES (
        NEW.uid,
        'NEW_UIR',
        NEW.uid,
        'UIR',
        -- Inherit priority from the triggering UIR
        COALESCE(NEW.priority, 'NORMAL')
    );

    -- Also notify Redis pub/sub via pg_notify
    -- Go gateway listens and forwards to Redis
    PERFORM pg_notify(
        'new_intelligence',
        json_build_object(
            'uid', NEW.uid,
            'source_type', NEW.source_type,
            'priority', NEW.priority,
            'domain', NEW.domain,
            'geo', CASE
                WHEN NEW.geo IS NOT NULL
                THEN json_build_object(
                    'lat', ST_Y(NEW.geo),
                    'lon', ST_X(NEW.geo)
                )
                ELSE NULL
            END
        )::text
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER uir_analysis_trigger
    AFTER INSERT ON intelligence_records
    FOR EACH ROW
    EXECUTE FUNCTION trigger_analysis_queue();
```

**Design Insight — The Trigger is the Heartbeat:**

This trigger is the single most important mechanism in Phase 2. Without it, agents write UIRs and nothing happens automatically. With it, every INSERT into `intelligence_records` fires three things simultaneously:[^11]

1. Queues an analysis job in `analysis_queue`
2. Emits a `pg_notify` event that the Go gateway forwards to Redis pub/sub
3. The Redis pub/sub wakes the SENTINEL globe (new geo marker) AND OpenClaw (potential alert)

One INSERT → three downstream reactions. The system never needs to poll for new data. It reacts in real time.

***

## PART V — APACHE AGE GRAPH LAYER

### Setup and Graph Creation

```sql
-- Enable Apache AGE
CREATE EXTENSION IF NOT EXISTS age CASCADE;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Create the intelligence knowledge graph
SELECT create_graph('pia_graph');

-- Expose PostgreSQL entities table as AGE vertices
-- (Apache AGE can query both native graph data AND PostgreSQL tables)
SELECT * FROM cypher('pia_graph', $$
    CREATE (n:Entity {
        entity_id: 'uuid-here',
        name: 'Al Rashid Air Cargo',
        entity_type: 'ORGANIZATION',
        confidence: 0.91,
        watch_status: 'CRITICAL'
    })
$$) AS (result agtype);
```


### Graph Queries (Cypher via AGE)

```cypher
-- "Everything connected to Al Rashid within 3 hops"
MATCH path = (org:Entity {name: 'Al Rashid Air Cargo'})-[*1..3]-(connected)
RETURN path, connected.name, connected.entity_type,
       connected.confidence
ORDER BY connected.threat_score DESC;

-- "Find all organizations with sanctions links"
MATCH (org:Entity {entity_type: 'ORGANIZATION'})
      -[:SANCTIONED_BY|LINKED_TO]->(s:Entity)
WHERE org.confidence > 0.7
RETURN org.name, org.threat_score, s.name AS sanctioned_by
ORDER BY org.threat_score DESC;

-- "What entities co-occur most with military domain activity?"
MATCH (e:Entity)-[:CO_OCCURRED_WITH]->
      (cluster:Entity {entity_type: 'Event'})
WHERE cluster.domain = 'MILITARY'
RETURN e.name, COUNT(*) AS co_occurrences
ORDER BY co_occurrences DESC
LIMIT 20;
```


***

## PART VI — MATERIALIZED VIEWS \& CONTINUOUS AGGREGATES

### For ORACLE Queries (Hot Paths)

```sql
-- ════════════════════════════════════════════════════════════════
-- ACTIVE GLOBE STATE
-- What the SENTINEL globe reads every 5 seconds.
-- Refreshed every 5 minutes via pg_cron.
-- Much faster than querying live tables.
-- ════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW mv_active_globe_state AS
SELECT
    cluster_id,
    title,
    cluster_type,
    priority,
    status,
    confidence,
    ST_Y(geo_centroid) AS lat,
    ST_X(geo_centroid) AS lon,
    geo_radius_km,
    uir_count,
    updated_at
FROM intelligence_clusters
WHERE status IN ('ACTIVE', 'ESCALATING')
ORDER BY priority DESC, confidence DESC;

CREATE UNIQUE INDEX ON mv_active_globe_state(cluster_id);
CREATE INDEX ON mv_active_globe_state
    USING GIST(ST_SetSRID(ST_MakePoint(lon, lat), 4326));

-- ════════════════════════════════════════════════════════════════
-- ENTITY WATCH LIST
-- Fast entity lookup for ORACLE queries.
-- "Who are we actively watching and what's their current status?"
-- ════════════════════════════════════════════════════════════════

CREATE MATERIALIZED VIEW mv_entity_watchlist AS
SELECT
    entity_id, name, entity_type,
    watch_status, threat_score, confidence,
    mention_count, last_seen,
    current_profile,
    ST_Y(primary_geo) AS lat,
    ST_X(primary_geo) AS lon
FROM entities
WHERE watch_status IN ('MONITORING','ACTIVE','CRITICAL')
ORDER BY threat_score DESC, mention_count DESC;

CREATE UNIQUE INDEX ON mv_entity_watchlist(entity_id);

-- Refresh both views every 5 minutes
SELECT cron.schedule('refresh-globe-state', '*/5 * * * *',
    'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_active_globe_state');

SELECT cron.schedule('refresh-watchlist', '*/5 * * * *',
    'REFRESH MATERIALIZED VIEW CONCURRENTLY mv_entity_watchlist');
```


***

## PART VII — DATA LIFECYCLE MATRIX

| Table | Retention | Compression | Rationale |
| :-- | :-- | :-- | :-- |
| `flight_tracks` | 1 year | After 7 days | High volume; precise data matters short-term [^1] |
| `satellite_positions` | 1 year | After 7 days | Same as flights |
| `vessel_positions` | 1 year | After 7 days | Same as flights |
| `seismic_events` | 5 years | None | Sparse; full fidelity valuable long-term |
| `intelligence_records` | Permanent | None | Core asset — never delete |
| `intelligence_clusters` | Permanent | None | Pattern history irreplaceable |
| `intelligence_digests` | Permanent | None | Institutional memory |
| `entity_profile_history` | Permanent | None | Understanding evolution |
| `cluster_revisions` | Permanent | None | Confidence trajectory |
| `analysis_queue` | 90 days | None | Operational log only |
| `agent_tasks` | 90 days | None | Operational log only |


***

## PART VIII — COMPLETE BUILD SEQUENCE

### Phase 1 Build Order (Weeks 1–4)

```
Week 1: Core infrastructure
├── PostgreSQL 16 + all extensions
├── Layer 1 tables (flight_tracks, satellite_positions,
│   seismic_events, vessel_positions)
├── TimescaleDB hypertables + compression policies
└── Test: GEOINT agent inserts one flight record

Week 2: Intelligence core
├── Layer 2 (intelligence_records) with all indexes
├── Layer 3 (intelligence_clusters)
├── Layer 4 (intelligence_digests)
├── agent_tasks table
└── Test: OSINT agent writes one UIR; Analyst reads it

Week 3: Performance layer
├── PgBouncer connection pooling
├── Materialized view: mv_active_globe_state
├── Continuous aggregate: flight_hourly_anomalies
├── pg_cron refresh schedules
└── Test: ORACLE NL query returns results in <500ms

Week 4: Observability
├── Grafana dashboard wired to pg_stat_statements
├── Agent heartbeat monitoring queries
├── Backup procedures (WAL + daily pg_dump)
└── Test: simulate agent failure, verify alert fires
```


### Phase 2 Build Order (Months 2–3, after 10K UIRs)

```
Month 2, Week 1: Entity foundation
├── entities table + indexes
├── entity_profile_history table
├── Entity Agent (reads new UIRs, creates/updates entity records)
└── Test: 100 UIRs processed, 20+ entities auto-created

Month 2, Week 2: Relationship graph
├── entity_relationships table
├── entity_profile_history indexes
├── Relationship Inference Agent (reads entity pairs in UIRs)
├── Apache AGE graph layer on top of entities tables
└── Test: Cypher query traverses 3-hop relationship

Month 2, Week 3: Living revision system
├── cluster_revisions table
├── entity_profile_history fully wired
├── Analyst Agent updated to write revision records
└── Test: new UIR causes cluster confidence to update,
         revision record written with reason

Month 2, Week 4: Continuous analysis heartbeat
├── analysis_queue table
├── UIR INSERT trigger (pg_trigger → analysis_queue)
├── pg_notify → Redis pub/sub wiring
├── Analyst Agent polling loop on analysis_queue
└── Test: one article inserted → globe updates within 10 seconds
         → analyst processes queue → cluster revised
         → Telegram alert fires if HIGH priority
```


***

## PART IX — QUERY REFERENCE GUIDE

### The Seven Core Query Patterns

```sql
-- ─────────────────────────────────────────────────────────────
-- 1. MORNING BRIEF (Layer 4)
-- "What happened overnight?"
-- ─────────────────────────────────────────────────────────────
SELECT content, key_developments, cluster_count
FROM intelligence_digests
WHERE digest_type = 'DAILY_BRIEF'
  AND period_end::date = CURRENT_DATE
ORDER BY created_at DESC LIMIT 1;


-- ─────────────────────────────────────────────────────────────
-- 2. ACTIVE ANOMALIES (Layer 3 → Globe)
-- "What should be highlighted on the globe right now?"
-- ─────────────────────────────────────────────────────────────
SELECT * FROM mv_active_globe_state
WHERE priority IN ('CRITICAL','HIGH')
ORDER BY confidence DESC;


-- ─────────────────────────────────────────────────────────────
-- 3. SEMANTIC SEARCH (Layer 2)
-- "Find intelligence semantically similar to this topic"
-- ─────────────────────────────────────────────────────────────
SELECT uid, content_headline, source_type, created_at,
       1 - (embedding <=> $1::vector) AS similarity
FROM intelligence_records
WHERE 1 - (embedding <=> $1) > 0.75
  AND created_at > NOW() - INTERVAL '30 days'
ORDER BY embedding <=> $1
LIMIT 20;


-- ─────────────────────────────────────────────────────────────
-- 4. SPATIAL INTELLIGENCE (PostGIS join across layers)
-- "All intelligence near Taiwan in last 48 hours"
-- ─────────────────────────────────────────────────────────────
SELECT ir.uid, ir.content_headline, ir.source_type,
       ir.confidence, ir.created_at,
       ST_Distance(ir.geo,
           ST_SetSRID(ST_MakePoint(121.0, 23.5), 4326)
       ) / 1000 AS distance_km
FROM intelligence_records ir
WHERE ST_DWithin(
    ir.geo,
    ST_SetSRID(ST_MakePoint(121.0, 23.5), 4326),
    300000  -- 300km radius
)
AND ir.created_at > NOW() - INTERVAL '48 hours'
ORDER BY ir.confidence DESC, distance_km ASC;


-- ─────────────────────────────────────────────────────────────
-- 5. ENTITY DEEP DIVE (Phase 2)
-- "Everything we know about this entity"
-- ─────────────────────────────────────────────────────────────
SELECT e.*,
    (SELECT COUNT(*) FROM entity_relationships
     WHERE entity_a_id = e.entity_id
       OR entity_b_id = e.entity_id) AS relationship_count,
    (SELECT json_agg(json_build_object(
        'revised_at', revised_at,
        'confidence', new_confidence,
        'reason', revision_reason
     ) ORDER BY revised_at)
     FROM entity_profile_history
     WHERE entity_id = e.entity_id
     LIMIT 20) AS confidence_history
FROM entities e
WHERE e.name ILIKE '%Al Rashid%'
  OR $1::text = ANY(e.aliases);


-- ─────────────────────────────────────────────────────────────
-- 6. CLUSTER CONFIDENCE TRAJECTORY (Phase 2)
-- "How has our understanding of this situation evolved?"
-- ─────────────────────────────────────────────────────────────
SELECT revised_at, new_confidence, confidence_delta,
       new_priority, new_status, revision_reason
FROM cluster_revisions
WHERE cluster_id = $1
ORDER BY revised_at ASC;


-- ─────────────────────────────────────────────────────────────
-- 7. CROSS-DOMAIN TRIPLE JOIN
-- "Show all intelligence that has correlated OSINT + GEOINT
--  + SIGINT evidence within same cluster"
-- The highest-value query in the system.
-- ─────────────────────────────────────────────────────────────
SELECT
    ic.cluster_id,
    ic.title,
    ic.confidence,
    COUNT(*) FILTER (WHERE ir.source_type = 'OSINT') AS osint_count,
    COUNT(*) FILTER (WHERE ir.source_type = 'GEOINT') AS geoint_count,
    COUNT(*) FILTER (WHERE ir.source_type = 'SIGINT') AS sigint_count
FROM intelligence_clusters ic
JOIN intelligence_records ir ON ir.cluster_id = ic.cluster_id
WHERE ic.status = 'ACTIVE'
  AND ic.created_at > NOW() - INTERVAL '7 days'
GROUP BY ic.cluster_id, ic.title, ic.confidence
HAVING
    COUNT(*) FILTER (WHERE ir.source_type = 'OSINT') > 0
    AND COUNT(*) FILTER (WHERE ir.source_type = 'GEOINT') > 0
    AND COUNT(*) FILTER (WHERE ir.source_type = 'SIGINT') > 0
ORDER BY ic.confidence DESC;
```


***

## PART X — THE DESIGN PHILOSOPHY IN ONE PAGE

**The database is not a storage system. It is a reasoning system.**

Phase 1 gives it **facts**. Phase 2 gives it **understanding**. The UIR is the universal language all agents speak. The entity graph is the accumulated knowledge about subjects. The cluster revisions are the memory of how understanding changed. The analysis queue trigger is the heartbeat that makes it alive.

Every design decision follows three rules:

1. **Never lose data** — append-only UIRs, permanent retention on all analytical layers, full revision history
2. **Always answer "where?" and "when?"** — PostGIS on every record, TimescaleDB on every telemetry stream
3. **Connect everything** — linked_uids between UIRs, cluster_id linking UIRs to patterns, entity_refs linking entities to evidence, the graph edges carrying intelligence between nodes

The corpus that builds in this database over months and years — the UIRs, the entity profiles, the cluster histories, the relationship graph — **that is the irreplaceable asset**. The agents are replaceable. The globe is replaceable. The interfaces are replaceable. The intelligence corpus is not. Design it correctly from the first insert.

***

**End of System \& Database Design Document v2.0**
<span style="display:none">[^12][^13][^14][^15][^16][^17][^18][^19][^20][^21][^22][^23][^24][^25][^26][^27][^28][^29][^30][^31]</span>

<div align="center">⁂</div>

[^1]: https://oneuptime.com/blog/post/2026-01-27-timescaledb-postgresql-extensions/view

[^2]: https://www.timescale.com/learn/postgresql-extensions-pgvector?_hsmi=295422343

[^3]: https://github.com/timescale/pgvectorscale/blob/main/README.md

[^4]: https://www.dbvis.com/thetable/pgvectorscale-an-extension-for-improved-vector-search-in-postgres/

[^5]: https://oneuptime.com/blog/post/2026-01-27-timescaledb-continuous-aggregates/view

[^6]: https://learn.microsoft.com/en-us/azure/postgresql/flexible-server/generative-ai-age-overview

[^7]: https://pgxn.org/dist/apacheage/

[^8]: https://www.tigerdata.com/docs/about/latest/whitepaper

[^9]: https://www.tigerdata.com/blog/timescale-vector-x-llamaindex-making-postgresql-a-better-vector-database-for-ai-applications

[^10]: https://github.com/apache/age

[^11]: https://appstekcorp.com/blog/design-patterns-for-agentic-ai-and-multi-agent-systems/

[^12]: https://www.getgalaxy.io/articles/top-knowledge-graph-platforms-enterprise-data-intelligence-2026

[^13]: https://www.falkordb.com/blog/graph-database-guide/

[^14]: https://www.puppygraph.com/blog/knowledge-graph-examples

[^15]: https://www.linkedin.com/pulse/use-case-exercise-knowledge-graph-generation-from-existing-idehen-zkcje

[^16]: https://app.readytensor.ai/publications/knowledge-graphs-with-postgresql-eQyINuo4ojwW

[^17]: https://www.stardog.com/platform/

[^18]: https://age.apache.org

[^19]: https://www.linkedin.com/posts/ready-tensor_knowledgegraphs-lightrag-postgresql-activity-7313583823428993024-ymx0

[^20]: https://github.com/timescale/pgvectorscale/

[^21]: https://www.puppygraph.com/blog/knowledge-graph-vs-graph-database

[^22]: https://www.tigerdata.com/blog/top-8-postgresql-extensions

[^23]: https://age.apache.org/overview/

[^24]: https://www.reddit.com/r/PostgreSQL/comments/1avqzu3/apache_age_postgresql_graph_extension/

[^25]: https://www.tigerdata.com/blog/materialized-views-the-timescale-way

[^26]: https://www.reddit.com/r/opensource/comments/1bpd2a9/lets_talk_about_apache_age_a_graph_extension_for/

[^27]: https://postgrespro.com/docs/enterprise/current/apache-age

[^28]: https://www.tigerdata.com/docs/api/latest/continuous-aggregates/create_materialized_view

[^29]: https://learn.microsoft.com/pl-pl/azure/postgresql/azure-ai/generative-ai-age-overview

[^30]: https://www.timescale.com/forum/t/continuous-aggregates-vs-materialized-views/302

[^31]: https://github.com/apache/age-viewer

