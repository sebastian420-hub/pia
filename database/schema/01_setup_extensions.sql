-- 01_extensions.sql
-- Enable the 5 critical extensions for the PIA architecture

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Set a global search path that prioritizes standard tables but allows graph queries
-- This ensures that tables are created in 'public' by default.
ALTER ROLE pia SET search_path = public, ag_catalog;
