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
