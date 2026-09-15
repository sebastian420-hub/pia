-- Schema v2 (2026-09-15). Single store: PostgreSQL + TimescaleDB + PostGIS + pgvector.
-- Apache AGE was removed: it held a by-name mirror nobody read.
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS vectorscale;
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
