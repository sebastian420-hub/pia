-- Migration 006: flight_tracks grows ~400k rows/day (every ADS-B position). Keep 7 days.
-- Reports about aircraft (intelligence_records) are unaffected.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'flight_tracks') THEN
    PERFORM add_retention_policy('flight_tracks', INTERVAL '7 days', if_not_exists => TRUE);
  END IF;
END $$;
