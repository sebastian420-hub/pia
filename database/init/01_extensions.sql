-- 01_extensions.sql
-- Enable the 5 critical extensions for the PIA architecture

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Load Apache AGE
LOAD 'age';
SET search_path = ag_catalog, "$user", public;
