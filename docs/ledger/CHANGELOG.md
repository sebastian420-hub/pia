# Changelog

## [0.1.0] - 2026-02-26
### Added
- **Engine:** Standard PostgreSQL 16 image with PostGIS, TimescaleDB, pgvector, Apache AGE, and pg_cron.
- **Schema:** Full 6-layer intelligence data model implemented via modular 01-06 SQL sequence.
- **Seeding:** Tier 1 Geographic baseline (GeoNames) with 33,336 urban center entities.
- **Python Core:** `DatabaseManager` (psycopg2) and `BaseAgent` (ABC lifecycle).
- **Agents:** `SeismicAgent` service running in a dedicated container for real-time telemetry.
- **Trigger:** `uir_analysis_trigger` (Heartbeat) with `pg_notify` support.
- **Validation:** `validate_system.py` orchestrator for atomic deployment and testing.
- **Ledger:** ROADMAP, CHANGELOG, and ADR system initialized.

### Fixed
- Host-to-Container connectivity resolved via Internal Docker Network (`DB_HOST=postgres`).
- Schema persistence issues resolved via unified `validate_system.py` logic.
- Apache AGE initialization and global `search_path` configuration.

### Verified
- **End-to-End Flow:** 100% success rate on signal propagation tests (External API -> Database -> Analysis Queue).
