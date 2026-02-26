# Changelog

## [0.1.0] - 2026-02-26
### Added
- **Engine:** Custom PostgreSQL 16 image with PostGIS, TimescaleDB, pgvector, Apache AGE, and pg_cron.
- **Schema:** Full 6-layer intelligence data model implemented in `database/schema/full_schema.sql`.
- **Seeding:** Tier 1 Geographic baseline (GeoNames) with 33,336 urban center entities.
- **Python Core:** `DatabaseManager` (SQLAlchemy/Psycopg2) and `BaseAgent` (ABC lifecycle).
- **Agents:** `SeismicAgent` for real-time USGS GeoJSON telemetry ingestion.
- **Trigger:** `uir_analysis_trigger` (Heartbeat) for automated analysis queueing.
- **Testing:** `test_signal_path.py` for full E2E validation.

### Fixed
- Authentication failures between Host and Container resolved via containerized agent service.
- Filename synchronization in database initialization scripts.
- Apache AGE `search_path` and `create_graph` session persistence.

### Verified
- **Health Check:** 100% GREEN pass rate on E2E signal propagation tests.
