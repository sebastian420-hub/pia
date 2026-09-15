-- ════════════════════════════════════════════════════════════════
-- LAYER 3: SITUATIONS (clusters of reports; same area + topic + time)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE intelligence_clusters (
    cluster_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title             TEXT NOT NULL,
    description       TEXT,
    domain            TEXT,
    confidence        FLOAT NOT NULL CHECK (confidence BETWEEN 0.0 AND 1.0),
    status            TEXT DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','ESCALATING','RESOLVED','MONITORING','FALSE_POSITIVE')),
    priority          TEXT DEFAULT 'NORMAL' CHECK (priority IN ('CRITICAL','HIGH','NORMAL','LOW')),
    geo_centroid      GEOMETRY(Point, 4326),
    geo_radius_km     FLOAT,
    event_start       TIMESTAMPTZ,
    event_end         TIMESTAMPTZ,
    uir_count         INTEGER DEFAULT 0,
    key_entities      UUID[],
    semantic_dna      VECTOR(1536),
    metadata          JSONB,
    client_id         UUID DEFAULT '00000000-0000-0000-0000-000000000000'
);
CREATE INDEX idx_cluster_centroid  ON intelligence_clusters USING GIST(geo_centroid) WHERE geo_centroid IS NOT NULL;
CREATE INDEX idx_cluster_status    ON intelligence_clusters(status, priority, updated_at DESC);
CREATE INDEX idx_cluster_embedding ON intelligence_clusters USING diskann(semantic_dna vector_cosine_ops) WHERE semantic_dna IS NOT NULL;

ALTER TABLE intelligence_records
    ADD CONSTRAINT fk_uir_cluster FOREIGN KEY (cluster_id) REFERENCES intelligence_clusters(cluster_id) ON DELETE SET NULL;
