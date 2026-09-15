-- ════════════════════════════════════════════════════════════════
-- LAYER 2: REPORTS (Universal Intelligence Record). One row per article / reading / document chunk.
-- ════════════════════════════════════════════════════════════════
CREATE TABLE intelligence_records (
    uid               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at      TIMESTAMPTZ,

    -- PROVENANCE
    source_type       TEXT NOT NULL CHECK (source_type IN ('OSINT','GEOINT','SIGINT','TECHINT','FININT','HUMINT','DERIVED','SYSTEM')),
    source_id         TEXT REFERENCES sources(source_id),
    source_agent      TEXT NOT NULL,
    source_url        TEXT,
    source_name       TEXT,                       -- display name (outlet), kept for the UI
    language          TEXT,

    -- ASSESSMENT
    confidence        FLOAT CHECK (confidence BETWEEN 0.0 AND 1.0),
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN ('CRITICAL','HIGH','NORMAL','LOW')),
    verified          BOOLEAN DEFAULT FALSE,

    -- CONTENT
    content_headline  TEXT,
    content_summary   TEXT,                       -- feed blurb, later replaced by the LLM summary
    content_raw       TEXT,                       -- full article body (fetched) or document chunk
    content_hash      TEXT UNIQUE,
    body_status       TEXT CHECK (body_status IN ('OK','ROBOTS_DENIED','PAYWALL','ERROR','NONE')),
    body_fetched_at   TIMESTAMPTZ,

    -- CLASSIFICATION
    entities          TEXT[],                     -- resolved entity names, for quick display
    domain            TEXT CHECK (domain IN ('MILITARY','MARITIME','AVIATION','CYBER','FINANCIAL','POLITICAL',
                                             'NATURAL','INFRASTRUCTURE','PERSONNEL','INVESTIGATIVE','UNKNOWN')),
    mission_id        UUID,

    -- GEOSPATIAL
    geo               GEOMETRY(Point, 4326),
    geo_precision     TEXT CHECK (geo_precision IN ('exact','city','region','country','global')),
    geo_source        TEXT,                       -- 'sensor' | 'gdelt' | 'entity:Qxx' | 'feed'

    -- SEMANTIC
    embedding         VECTOR(1536),

    -- LINKS
    cluster_id        UUID,
    metadata          JSONB,
    client_id         UUID DEFAULT '00000000-0000-0000-0000-000000000000'
);

CREATE INDEX idx_uir_time         ON intelligence_records(created_at DESC);
CREATE INDEX idx_uir_time_facets  ON intelligence_records(created_at, domain, priority);
CREATE INDEX idx_uir_geo          ON intelligence_records USING GIST(geo) WHERE geo IS NOT NULL;
CREATE INDEX idx_uir_embedding    ON intelligence_records USING diskann(embedding vector_cosine_ops);
CREATE INDEX idx_uir_source       ON intelligence_records(source_id, created_at DESC);
CREATE INDEX idx_uir_url          ON intelligence_records(source_url);
CREATE INDEX idx_uir_priority     ON intelligence_records(priority, created_at DESC) WHERE priority IN ('CRITICAL','HIGH');
CREATE INDEX idx_uir_entities     ON intelligence_records USING GIN(entities);
CREATE INDEX idx_uir_cluster      ON intelligence_records(cluster_id) WHERE cluster_id IS NOT NULL;
