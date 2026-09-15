-- ════════════════════════════════════════════════════════════════
-- SENSOR LAYERS (cameras today; flights/vessels later)
-- ════════════════════════════════════════════════════════════════
CREATE TABLE sensor_layers (
    layer_id   TEXT PRIMARY KEY,
    label      TEXT NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('CAMERA','AIRCRAFT','VESSEL','SEISMIC','OTHER')),
    enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    metadata   JSONB
);
INSERT INTO sensor_layers (layer_id, label, kind) VALUES ('cameras', 'Cameras', 'CAMERA');

CREATE TABLE sensors (
    sensor_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    layer_id        TEXT NOT NULL REFERENCES sensor_layers(layer_id),
    provider        TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    name            TEXT,
    geo             GEOMETRY(Point, 4326) NOT NULL,
    city            TEXT,
    country_code    TEXT,
    media_kind      TEXT NOT NULL CHECK (media_kind IN ('SNAPSHOT','HLS','MP4','MJPEG')),
    media_url       TEXT NOT NULL,
    video_url       TEXT,
    refresh_seconds INTEGER NOT NULL DEFAULT 60,
    attribution     TEXT NOT NULL,
    cost_class      TEXT NOT NULL DEFAULT 'FREE' CHECK (cost_class IN ('FREE','ON_DEMAND','SUBSCRIPTION')),
    requires_relay  BOOLEAN NOT NULL DEFAULT FALSE,
    status          TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (status IN ('ONLINE','OFFLINE','UNKNOWN')),
    first_seen      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen       TIMESTAMPTZ,
    last_ok         TIMESTAMPTZ,
    metadata        JSONB,
    UNIQUE (provider, external_id)
);
CREATE INDEX idx_sensors_geo      ON sensors USING GIST(geo);
CREATE INDEX idx_sensors_layer    ON sensors(layer_id, status);
CREATE INDEX idx_sensors_provider ON sensors(provider);

-- ════════════════════════════════════════════════════════════════
-- OPERATIONS: agent heartbeats, live sessions, schema migrations
-- ════════════════════════════════════════════════════════════════
CREATE TABLE agent_heartbeats (
    agent_name  TEXT PRIMARY KEY,
    agent_kind  TEXT,
    hostname    TEXT,
    last_beat   TIMESTAMPTZ NOT NULL,
    status      TEXT NOT NULL DEFAULT 'OK',
    detail      JSONB
);

CREATE TABLE live_sessions (
    session_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMPTZ NOT NULL,
    stopped_at   TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    started_by   TEXT,
    note         TEXT
);
CREATE INDEX idx_live_sessions_active ON live_sessions(expires_at) WHERE stopped_at IS NULL;

-- Cross-process throttle for external APIs (Wikidata asks for ~1 req/s per client)
CREATE TABLE rate_limits (
    name      TEXT PRIMARY KEY,
    last_call TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01'
);

CREATE TABLE schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
