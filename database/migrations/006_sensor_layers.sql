-- Sensor layers: cameras today; flights/vessels later. A sensor is a thing with a
-- position and a live state, not a report, so it lives outside intelligence_records.
CREATE TABLE IF NOT EXISTS sensor_layers (
    layer_id   TEXT PRIMARY KEY,
    label      TEXT NOT NULL,
    kind       TEXT NOT NULL CHECK (kind IN ('CAMERA','AIRCRAFT','VESSEL','SEISMIC','OTHER')),
    enabled    BOOLEAN NOT NULL DEFAULT TRUE,
    metadata   JSONB
);
INSERT INTO sensor_layers (layer_id, label, kind) VALUES ('cameras', 'Cameras', 'CAMERA')
ON CONFLICT (layer_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS sensors (
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
CREATE INDEX IF NOT EXISTS idx_sensors_geo   ON sensors USING GIST(geo);
CREATE INDEX IF NOT EXISTS idx_sensors_layer ON sensors(layer_id, status);
CREATE INDEX IF NOT EXISTS idx_sensors_provider ON sensors(provider);
