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
    content_hash      TEXT UNIQUE,

    -- CLASSIFICATION TAXONOMY
    entities          TEXT[],
    tags              TEXT[],
    domain            TEXT CHECK (domain IN (
                          'MILITARY','MARITIME','AVIATION','CYBER',
                          'FINANCIAL','POLITICAL','NATURAL','INFRASTRUCTURE',
                          'PERSONNEL','UNKNOWN'
                      )),
    event_type        TEXT,
    mission_id        UUID,

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
    metadata          JSONB,
    
    -- MULTI-TENANCY
    client_id         UUID DEFAULT '00000000-0000-0000-0000-000000000000'
);

-- MULTI-TENANT ROW-LEVEL SECURITY
ALTER TABLE intelligence_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY client_isolation_records ON intelligence_records 
    USING (client_id = current_setting('app.current_client_id', true)::UUID OR client_id = '00000000-0000-0000-0000-000000000000');

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
