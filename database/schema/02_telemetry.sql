-- ════════════════════════════════════════════════════════════════
-- LAYER 1: RAW TELEMETRY (TimescaleDB hypertables)
-- ════════════════════════════════════════════════════════════════
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

-- Reserved for real ADS-B / AIS feeds (the simulated agents write here only when SIMULATED_SENSORS=true)
CREATE TABLE flight_tracks (
    time              TIMESTAMPTZ NOT NULL,
    icao24            TEXT NOT NULL,
    callsign          TEXT,
    registration      TEXT,
    position          GEOMETRY(Point, 4326) NOT NULL,
    altitude_ft       INTEGER,
    speed_kts         FLOAT,
    heading           FLOAT,
    squawk            TEXT,
    PRIMARY KEY (time, icao24)
);
SELECT create_hypertable('flight_tracks', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_ft_position ON flight_tracks USING GIST(position);

CREATE TABLE vessel_positions (
    time              TIMESTAMPTZ NOT NULL,
    mmsi              TEXT NOT NULL,
    name              TEXT,
    vessel_type       TEXT,
    flag              TEXT,
    position          GEOMETRY(Point, 4326) NOT NULL,
    speed_kts         FLOAT,
    heading           FLOAT,
    PRIMARY KEY (time, mmsi)
);
SELECT create_hypertable('vessel_positions', 'time', chunk_time_interval => INTERVAL '1 day');
CREATE INDEX idx_vessel_position ON vessel_positions USING GIST(position);
