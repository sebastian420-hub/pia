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
    mention_count     INTEGER DEFAULT 1,
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
    error_message     TEXT,
    
    -- MULTI-TENANCY
    client_id         UUID DEFAULT '00000000-0000-0000-0000-000000000000'
);
CREATE INDEX idx_queue_pending ON analysis_queue(priority DESC, created_at ASC) WHERE status = 'PENDING';
CREATE INDEX idx_queue_status ON analysis_queue(status, created_at DESC);
