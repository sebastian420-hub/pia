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
    semantic_dna      VECTOR(1536),
    linked_clusters   UUID[],
    digest_id         UUID,
    correlation_method TEXT,
    analyst_notes     TEXT,
    metadata          JSONB,
    
    -- MULTI-TENANCY
    client_id         UUID DEFAULT '00000000-0000-0000-0000-000000000000'
);

-- MULTI-TENANT ROW-LEVEL SECURITY
ALTER TABLE intelligence_clusters ENABLE ROW LEVEL SECURITY;
CREATE POLICY client_isolation_clusters ON intelligence_clusters 
    USING (client_id = current_setting('app.current_client_id', true)::UUID OR client_id = '00000000-0000-0000-0000-000000000000');

CREATE INDEX idx_cluster_centroid ON intelligence_clusters USING GIST(geo_centroid) WHERE geo_centroid IS NOT NULL;
CREATE INDEX idx_cluster_bbox ON intelligence_clusters USING GIST(geo_bbox) WHERE geo_bbox IS NOT NULL;
CREATE INDEX idx_cluster_status ON intelligence_clusters(status, priority, updated_at DESC);
CREATE INDEX idx_cluster_embedding ON intelligence_clusters USING diskann(semantic_dna vector_cosine_ops) WHERE semantic_dna IS NOT NULL;
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
