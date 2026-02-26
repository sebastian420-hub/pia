-- 01_extensions.sql
-- Enable the 5 critical extensions for the PIA architecture

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Load Apache AGE
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
-- 02_layer1_telemetry.sql

-- 1. FLIGHT TRACKS
CREATE TABLE flight_tracks (
    time              TIMESTAMPTZ NOT NULL,
    icao24            TEXT NOT NULL,
    callsign          TEXT,
    registration      TEXT,
    position          GEOMETRY(Point, 4326) NOT NULL,
    altitude_ft       INTEGER,
    speed_kts         FLOAT,
    heading           FLOAT,
    vertical_rate     FLOAT,
    on_ground         BOOLEAN DEFAULT FALSE,
    squawk            TEXT,
    anomaly_score     FLOAT DEFAULT 0.0 CHECK (anomaly_score BETWEEN 0.0 AND 1.0),
    anomaly_type      TEXT,
    anomaly_flagged_at TIMESTAMPTZ,
    PRIMARY KEY (time, icao24)
);

SELECT create_hypertable('flight_tracks', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_ft_position ON flight_tracks USING GIST(position);
CREATE INDEX idx_ft_icao_time ON flight_tracks (icao24, time DESC);
CREATE INDEX idx_ft_anomaly ON flight_tracks (anomaly_score DESC, time DESC) WHERE anomaly_score > 0.7;
CREATE INDEX idx_ft_squawk ON flight_tracks (squawk, time DESC) WHERE squawk IN ('7700','7600','7500');

-- Continuous Aggregate for flights (globe heatmap reads this)
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
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes');

-- 2. SATELLITE POSITIONS
CREATE TABLE satellite_positions (
    time              TIMESTAMPTZ NOT NULL,
    norad_id          INTEGER NOT NULL,
    name              TEXT,
    category          TEXT CHECK (category IN ('MILITARY','WEATHER','COMMS','NAVIGATION','OBSERVATION','ISS','DEBRIS')),
    position          GEOMETRY(Point, 4326) NOT NULL,
    altitude_km       FLOAT,
    velocity_kms      FLOAT,
    inclination_deg   FLOAT,
    tle_epoch         TIMESTAMPTZ,
    country_origin    TEXT,
    PRIMARY KEY (time, norad_id)
);

SELECT create_hypertable('satellite_positions', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_sat_position ON satellite_positions USING GIST(position);
CREATE INDEX idx_sat_category ON satellite_positions(category, time DESC);
CREATE INDEX idx_sat_country ON satellite_positions(country_origin, time DESC);

-- 3. SEISMIC EVENTS
CREATE TABLE seismic_events (
    time              TIMESTAMPTZ NOT NULL,
    usgs_id           TEXT NOT NULL,
    position          GEOMETRY(Point, 4326) NOT NULL,
    depth_km          FLOAT,
    magnitude         FLOAT NOT NULL,
    magnitude_type    TEXT,
    location_name     TEXT,
    felt_reports      INTEGER DEFAULT 0,
    tsunami_warning   BOOLEAN DEFAULT FALSE,
    updated_at        TIMESTAMPTZ,
    PRIMARY KEY (time, usgs_id)
);

SELECT create_hypertable('seismic_events', 'time');
CREATE INDEX idx_seis_position ON seismic_events USING GIST(position);
CREATE INDEX idx_seis_magnitude ON seismic_events(magnitude DESC, time DESC);
CREATE INDEX idx_seis_tsunami ON seismic_events(time DESC) WHERE tsunami_warning = TRUE;

-- 4. VESSEL POSITIONS
CREATE TABLE vessel_positions (
    time              TIMESTAMPTZ NOT NULL,
    mmsi              TEXT NOT NULL,
    name              TEXT,
    vessel_type       TEXT,
    flag              TEXT,
    position          GEOMETRY(Point, 4326) NOT NULL,
    speed_kts         FLOAT,
    heading           FLOAT,
    destination       TEXT,
    eta               TIMESTAMPTZ,
    anomaly_score     FLOAT DEFAULT 0.0,
    PRIMARY KEY (time, mmsi)
);

SELECT create_hypertable('vessel_positions', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_vessel_position ON vessel_positions USING GIST(position);
CREATE INDEX idx_vessel_type ON vessel_positions(vessel_type, time DESC);
CREATE INDEX idx_vessel_anomaly ON vessel_positions(anomaly_score DESC) WHERE anomaly_score > 0.7;
-- 03_layer2_uir.sql

-- UNIVERSAL INTELLIGENCE RECORD (UIR)
CREATE TABLE intelligence_records (
    -- IDENTITY
    uid               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- PROVENANCE
    source_type       TEXT NOT NULL CHECK (source_type IN (
                          'OSINT', 'GEOINT', 'SIGINT', 'TECHINT', 
                          'FININT', 'HUMINT', 'DERIVED', 'SYSTEM'
                      )),
    source_agent      TEXT NOT NULL,
    source_url        TEXT,
    source_name       TEXT,
    source_credibility FLOAT DEFAULT 0.5 CHECK (source_credibility BETWEEN 0.0 AND 1.0),
    agent_task_id     UUID,

    -- ASSESSMENT
    confidence        FLOAT CHECK (confidence BETWEEN 0.0 AND 1.0),
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN (
                          'CRITICAL','HIGH','NORMAL','LOW'
                      )),
    classification    TEXT DEFAULT 'UNCLASSIFIED',
    verified          BOOLEAN DEFAULT FALSE,
    verified_at       TIMESTAMPTZ,
    verified_by       TEXT,

    -- CONTENT
    content_headline  TEXT,
    content_summary   TEXT,
    content_raw       TEXT,

    -- CLASSIFICATION TAXONOMY
    entities          TEXT[],
    tags              TEXT[],
    domain            TEXT CHECK (domain IN (
                          'MILITARY','MARITIME','AVIATION','CYBER',
                          'FINANCIAL','POLITICAL','NATURAL','INFRASTRUCTURE',
                          'PERSONNEL','UNKNOWN'
                      )),
    event_type        TEXT,

    -- GEOSPATIAL
    geo               GEOMETRY(Point, 4326),
    geo_precision     TEXT CHECK (geo_precision IN (
                          'exact','city','region','country','global'
                      )),
    geo_bbox          GEOMETRY(Polygon, 4326),

    -- SEMANTIC MEMORY
    embedding         VECTOR(1536),

    -- RELATIONSHIPS
    linked_uids       UUID[],
    supersedes_uid    UUID,
    cluster_id        UUID,
    layer1_refs       JSONB,

    -- LIFECYCLE
    ttl               TIMESTAMPTZ,
    version           INTEGER DEFAULT 1,
    metadata          JSONB
);

-- INDEXES: Time + Space + Semantic simultaneously

-- Time
CREATE INDEX idx_uir_time ON intelligence_records(created_at DESC);

-- Space (PostGIS GIST)
CREATE INDEX idx_uir_geo ON intelligence_records USING GIST(geo) WHERE geo IS NOT NULL;

-- Semantic (pgvectorscale StreamingDiskANN)
CREATE INDEX idx_uir_embedding ON intelligence_records USING diskann(embedding vector_cosine_ops);

-- Domain + Time
CREATE INDEX idx_uir_domain ON intelligence_records(domain, created_at DESC);
CREATE INDEX idx_uir_source_type ON intelligence_records(source_type, created_at DESC);

-- Priority (Partial index for alert queue)
CREATE INDEX idx_uir_priority ON intelligence_records(priority, created_at DESC) WHERE priority IN ('CRITICAL','HIGH');

-- Array Containment (GIN)
CREATE INDEX idx_uir_entities ON intelligence_records USING GIN(entities);
CREATE INDEX idx_uir_tags ON intelligence_records USING GIN(tags);

-- Cluster Membership
CREATE INDEX idx_uir_cluster ON intelligence_records(cluster_id) WHERE cluster_id IS NOT NULL;

-- Counterintel Review Queue
CREATE INDEX idx_uir_review ON intelligence_records(created_at DESC) WHERE verified = FALSE AND priority IN ('CRITICAL','HIGH');

-- Derived Records
CREATE INDEX idx_uir_derived ON intelligence_records(created_at DESC, confidence DESC) WHERE source_type = 'DERIVED';
-- 04_layer3_4_clusters.sql

-- ════════════════════════════════════════════════════════════════
-- LAYER 3: INTELLIGENCE CLUSTERS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE intelligence_clusters (
    cluster_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title             TEXT NOT NULL,
    description       TEXT,
    cluster_type      TEXT CHECK (cluster_type IN (
                          'ANOMALY','PATTERN','THREAT','EVENT','TREND','RELATIONSHIP'
                      )),
    domain            TEXT,
    confidence        FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    status            TEXT DEFAULT 'ACTIVE' CHECK (status IN (
                          'ACTIVE','ESCALATING','RESOLVED','MONITORING','FALSE_POSITIVE'
                      )),
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN (
                          'CRITICAL','HIGH','NORMAL','LOW'
                      )),
    geo_centroid      GEOMETRY(Point, 4326),
    geo_bbox          GEOMETRY(Polygon, 4326),
    geo_radius_km     FLOAT,
    event_start       TIMESTAMPTZ,
    event_end         TIMESTAMPTZ,
    duration          INTERVAL GENERATED ALWAYS AS (event_end - event_start) STORED,
    uir_count         INTEGER DEFAULT 0,
    source_types      TEXT[],
    key_entities      TEXT[],
    domains           TEXT[],
    embedding         VECTOR(1536),
    linked_clusters   UUID[],
    digest_id         UUID,
    correlation_method TEXT,
    analyst_notes     TEXT,
    metadata          JSONB
);

CREATE INDEX idx_cluster_centroid ON intelligence_clusters USING GIST(geo_centroid) WHERE geo_centroid IS NOT NULL;
CREATE INDEX idx_cluster_bbox ON intelligence_clusters USING GIST(geo_bbox) WHERE geo_bbox IS NOT NULL;
CREATE INDEX idx_cluster_status ON intelligence_clusters(status, priority, updated_at DESC);
CREATE INDEX idx_cluster_embedding ON intelligence_clusters USING diskann(embedding vector_cosine_ops) WHERE embedding IS NOT NULL;
CREATE INDEX idx_cluster_domain ON intelligence_clusters(domain, cluster_type, updated_at DESC);

-- Link UIRs to Clusters
ALTER TABLE intelligence_records
    ADD CONSTRAINT fk_uir_cluster
    FOREIGN KEY (cluster_id)
    REFERENCES intelligence_clusters(cluster_id)
    ON DELETE SET NULL;

-- ════════════════════════════════════════════════════════════════
-- LAYER 4: INTELLIGENCE DIGESTS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE intelligence_digests (
    digest_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    period_start      TIMESTAMPTZ NOT NULL,
    period_end        TIMESTAMPTZ NOT NULL,
    digest_type       TEXT CHECK (digest_type IN (
                          'DAILY_BRIEF','WEEKLY_SUMMARY','DOMAIN_REPORT','SITREP','ALERT_DIGEST','ENTITY_PROFILE'
                      )),
    domain            TEXT DEFAULT 'GLOBAL',
    title             TEXT NOT NULL,
    content           TEXT NOT NULL,
    key_developments  TEXT[],
    executive_summary TEXT,
    cluster_count     INTEGER,
    uir_count         INTEGER,
    cluster_ids       UUID[],
    new_clusters      INTEGER DEFAULT 0,
    escalated_clusters INTEGER DEFAULT 0,
    delivered         BOOLEAN DEFAULT FALSE,
    delivery_channel  TEXT,
    delivered_at      TIMESTAMPTZ,
    metadata          JSONB
);

CREATE INDEX idx_digest_period ON intelligence_digests(period_end DESC);
CREATE INDEX idx_digest_type ON intelligence_digests(digest_type, domain, period_end DESC);
CREATE INDEX idx_digest_pending ON intelligence_digests(created_at DESC) WHERE delivered = FALSE;

-- ════════════════════════════════════════════════════════════════
-- AGENT TASKS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE agent_tasks (
    task_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    completed_at      TIMESTAMPTZ,
    agent             TEXT NOT NULL,
    task_type         TEXT NOT NULL,
    input             JSONB,
    output            JSONB,
    status            TEXT DEFAULT 'PENDING' CHECK (status IN (
                          'PENDING','RUNNING','DONE','FAILED','RETRYING'
                      )),
    duration_ms       INTEGER,
    retry_count       INTEGER DEFAULT 0,
    error_message     TEXT,
    uirs_written      UUID[],
    clusters_written  UUID[]
);

CREATE INDEX idx_task_agent_time ON agent_tasks(agent, created_at DESC);
CREATE INDEX idx_task_status ON agent_tasks(status, created_at DESC) WHERE status NOT IN ('DONE');
CREATE INDEX idx_task_failed ON agent_tasks(created_at DESC) WHERE status = 'FAILED';
-- 05_phase2_entities_graph.sql

-- ════════════════════════════════════════════════════════════════
-- ENTITIES
-- ════════════════════════════════════════════════════════════════
CREATE TABLE entities (
    entity_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    entity_type       TEXT NOT NULL CHECK (entity_type IN (
                          'PERSON','ORGANIZATION','LOCATION','VESSEL',
                          'AIRCRAFT','DOMAIN','INFRASTRUCTURE','EVENT'
                      )),
    name              TEXT NOT NULL,
    canonical_name    TEXT,
    aliases           TEXT[],
    description       TEXT,
    current_profile   TEXT,
    profile_updated   TIMESTAMPTZ,
    profile_version   INTEGER DEFAULT 0,
    confidence        FLOAT DEFAULT 0.5 CHECK (confidence BETWEEN 0.0 AND 1.0),
    threat_score      FLOAT DEFAULT 0.0 CHECK (threat_score BETWEEN 0.0 AND 1.0),
    watch_status      TEXT DEFAULT 'PASSIVE' CHECK (watch_status IN (
                          'PASSIVE','MONITORING','ACTIVE','CRITICAL'
                      )),
    first_seen        TIMESTAMPTZ DEFAULT NOW(),
    last_seen         TIMESTAMPTZ DEFAULT NOW(),
    mention_count     INTEGER DEFAULT 0,
    primary_geo       GEOMETRY(Point, 4326),
    geo_precision     TEXT,
    embedding         VECTOR(1536),
    uir_refs          UUID[],
    cluster_refs      UUID[],
    metadata          JSONB
);

CREATE INDEX idx_entity_type ON entities(entity_type, mention_count DESC);
CREATE INDEX idx_entity_name ON entities USING GIN(to_tsvector('english', name));
CREATE INDEX idx_entity_aliases ON entities USING GIN(aliases);
CREATE INDEX idx_entity_watch ON entities(watch_status, threat_score DESC);
CREATE INDEX idx_entity_geo ON entities USING GIST(primary_geo) WHERE primary_geo IS NOT NULL;
CREATE INDEX idx_entity_embedding ON entities USING diskann(embedding vector_cosine_ops) WHERE embedding IS NOT NULL;

-- ════════════════════════════════════════════════════════════════
-- ENTITY RELATIONSHIPS
-- ════════════════════════════════════════════════════════════════
CREATE TABLE entity_relationships (
    relationship_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    entity_a_id       UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    entity_b_id       UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    confidence        FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    evidence_uids     UUID[],
    evidence_count    INTEGER DEFAULT 0,
    first_observed    TIMESTAMPTZ DEFAULT NOW(),
    last_confirmed    TIMESTAMPTZ DEFAULT NOW(),
    still_valid       BOOLEAN DEFAULT TRUE,
    description       TEXT,
    embedding         VECTOR(1536),
    UNIQUE (entity_a_id, entity_b_id, relationship_type)
);

CREATE INDEX idx_rel_entity_a ON entity_relationships(entity_a_id);
CREATE INDEX idx_rel_entity_b ON entity_relationships(entity_b_id);
CREATE INDEX idx_rel_type ON entity_relationships(relationship_type, confidence DESC);
CREATE INDEX idx_rel_confidence ON entity_relationships(confidence DESC) WHERE confidence > 0.7;
CREATE INDEX idx_rel_invalid ON entity_relationships(updated_at DESC) WHERE still_valid = FALSE;

-- ════════════════════════════════════════════════════════════════
-- HISTORY TABLES
-- ════════════════════════════════════════════════════════════════
CREATE TABLE entity_profile_history (
    history_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id         UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    revised_at        TIMESTAMPTZ DEFAULT NOW(),
    previous_profile  TEXT,
    new_profile       TEXT,
    previous_confidence FLOAT,
    new_confidence      FLOAT,
    previous_watch_status TEXT,
    new_watch_status      TEXT,
    previous_threat_score FLOAT,
    new_threat_score      FLOAT,
    trigger_uid       UUID,
    trigger_cluster   UUID,
    revision_reason   TEXT,
    revised_by        TEXT
);
CREATE INDEX idx_eph_entity ON entity_profile_history(entity_id, revised_at DESC);
CREATE INDEX idx_eph_time ON entity_profile_history(revised_at DESC);

CREATE TABLE cluster_revisions (
    revision_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cluster_id        UUID NOT NULL REFERENCES intelligence_clusters(cluster_id) ON DELETE CASCADE,
    revised_at        TIMESTAMPTZ DEFAULT NOW(),
    previous_confidence  FLOAT,
    new_confidence       FLOAT,
    confidence_delta     FLOAT GENERATED ALWAYS AS (new_confidence - previous_confidence) STORED,
    previous_status      TEXT,
    new_status           TEXT,
    previous_priority    TEXT,
    new_priority         TEXT,
    previous_uir_count   INTEGER,
    new_uir_count        INTEGER,
    trigger_uid          UUID,
    trigger_entity       UUID,
    revision_reason      TEXT,
    revised_by           TEXT,
    description_snapshot TEXT
);
CREATE INDEX idx_cr_cluster ON cluster_revisions(cluster_id, revised_at DESC);
CREATE INDEX idx_cr_delta ON cluster_revisions(confidence_delta DESC) WHERE ABS(confidence_delta) > 0.1;

-- ════════════════════════════════════════════════════════════════
-- ANALYSIS QUEUE
-- ════════════════════════════════════════════════════════════════
CREATE TABLE analysis_queue (
    queue_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    uir_uid           UUID, 
    trigger_uid       UUID,
    trigger_type      TEXT NOT NULL CHECK (trigger_type IN (
                          'NEW_UIR','NEW_CLUSTER','ENTITY_UPDATED',
                          'CLUSTER_ESCALATED','SCHEDULED','DIRECTOR_TASKED'
                      )),
    target_id         UUID,
    target_type       TEXT CHECK (target_type IN ('UIR','CLUSTER','ENTITY','DOMAIN','GLOBAL')),
    geo               GEOMETRY(Point, 4326),
    domain            TEXT,
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN ('CRITICAL','HIGH','NORMAL','LOW')),
    status            TEXT DEFAULT 'PENDING' CHECK (status IN ('PENDING','PROCESSING','DONE','FAILED')),
    assigned_agent    TEXT,
    assigned_at       TIMESTAMPTZ,
    processed_at      TIMESTAMPTZ,
    result_uid        UUID,
    result_cluster    UUID,
    error_message     TEXT
);
CREATE INDEX idx_queue_pending ON analysis_queue(priority DESC, created_at ASC) WHERE status = 'PENDING';
CREATE INDEX idx_queue_status ON analysis_queue(status, created_at DESC);

-- AGE GRAPH INITIALIZATION
SELECT create_graph('pia_graph');
-- 06_functions_triggers.sql

-- ════════════════════════════════════════════════════════════════
-- THE HEARTBEAT TRIGGER
-- ════════════════════════════════════════════════════════════════
-- This is the most important function in the entire system.
-- Every INSERT into intelligence_records automatically queues analysis.
-- This is what makes the system react without being asked.

CREATE OR REPLACE FUNCTION trigger_analysis_queue()
RETURNS TRIGGER AS $$
BEGIN
    -- 1. Insert into the persistent analysis queue for the Analyst Agent
    INSERT INTO analysis_queue (
        uir_uid,
        trigger_uid,
        trigger_type,
        target_id,
        target_type,
        geo,
        domain,
        priority,
        status,
        created_at
    ) VALUES (
        NEW.uid,
        NEW.uid,
        'NEW_UIR',
        NEW.uid,
        'UIR',
        NEW.geo,
        NEW.domain,
        COALESCE(NEW.priority, 'NORMAL'),
        'PENDING',
        NOW()
    );

    -- 2. Emit a real-time notification via pg_notify
    -- External listeners (like Redis pub/sub bridge) consume this for instant alerts
    PERFORM pg_notify(
        'new_intelligence',
        json_build_object(
            'uid', NEW.uid,
            'source_type', NEW.source_type,
            'priority', NEW.priority,
            'domain', NEW.domain,
            'headline', NEW.content_headline,
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

-- Attach trigger to Layer 2
DROP TRIGGER IF EXISTS uir_analysis_trigger ON intelligence_records;
CREATE TRIGGER uir_analysis_trigger
    AFTER INSERT ON intelligence_records
    FOR EACH ROW
    EXECUTE FUNCTION trigger_analysis_queue();
