# Changelog

## [0.7.0] - 2026-03-01
### Added
- **Global SIGINT:** Integrated Aviation (ADS-B) and Maritime (AIS) sentinel agents for real-time asset tracking.
- **Grounding Engine:** Implemented "Geospatial Veto" logic to prevent semantic collisions between distant entities.
- **Data Integrity Layer:** Added `source_authority` table and weighted confidence scoring based on sensor trust.
- **Precision Fusion:** Added Semantic-Spatial Gating (Double-Gate) for situational clustering.
- **Enrichment Agent:** Created autonomous "Ground Truth" agent to harden entity profiles and identify aliases.
- **Maintenance Suite:** Added `maintenance.py` for database optimization and Apache AGE reference leak mitigation.
- **Validation Suite:** Created `master_e2e_real.py`, `signal_storm.py`, and `test_integrity.py` for world-class stress testing.

### Changed
- **Core Infrastructure:** Refactored `DatabaseManager` from a singleton connection to a `ThreadedConnectionPool`.
- **Graph Security:** Shielded all Cypher queries with parameterized SQL and mandatory string escaping.
- **OSINT Sensing:** Replaced legacy Reuters feeds with stable 2026 AP News and Al Jazeera streams.
- **Situational Awareness:** Upgraded `correlate_and_cluster` with Multi-Level Matching (Semantic + Mission fallback).

### Fixed
- Fixed **"Dubai-Florida Collision"** by implementing geospatial distance validation in entity resolution.
- Fixed **"Analyst Crash"** bug where failed jobs triggered NameErrors in the polling loop.
- Fixed **"Deaf Bot"** issue by injecting manual DNS settings (8.8.8.8) into the Telegram container.
- Fixed **"Reference Leak"** by implementing periodic database checkpoints and vacuuming.

### Verified
- **Operation: Global Synchrony:** Successfully fused Aviation, Maritime, and News signals into a single Baltic situational cluster.
- **Signal Storm:** Confirmed system can process 30+ concurrent high-velocity intelligence hits under 120s with 100% accuracy.

## [0.6.0] - 2026-02-28
### Added
- **Semantic Intelligence:** Implemented `pgvector` embeddings for all entities, enabling "Conceptual Understanding" beyond simple keyword matches.
- **Semantic Resolver:** Upgraded `AnalystAgent` with a Two-Stage Resolution engine (Lexical + Semantic Fallback) and a "Highest Similarity Wins" disambiguation tie-breaker.
- **Mission Control (Layer 0):** Added `mission_focus` table and schema relations to track dynamic strategic priorities.
- **Telegram C2:** Added `/mission` and `/missions_active` commands to `telegram_voice.py` for real-time agency retasking.
- **Embedding Toolset:** Created `populate_embeddings.py` to prime the Knowledge Graph and `diagnostic_resolution.py` for similarity auditing.
- **Master Validation:** Created `master_e2e_test.py` and `test_semantic_resolution.py` to programmatically verify the full pipeline.

### Changed
- **Adaptive Senses:** Upgraded `NewsAgent` to scan for active mission keywords and auto-escalate UIR priority to `HIGH` upon match.
- **Adaptive Brain:** Upgraded `AnalystAgent` and `NLPManager` to fetch active mission context and dynamically rewrite the LLM system prompt to focus extraction on mission targets.
- **Resolution Tuning:** Calibrated semantic thresholds (0.50) to optimize cross-description matching (e.g., "rocket firm" -> "SpaceX").
- **LLM Stability:** Switched OpenRouter model to `google/gemini-2.0-flash-lite-001` for improved reliability and extraction accuracy.

### Fixed
- Fixed **"Lexical Greed"** bug where city names (e.g., Hawthorne) would intercept organization-level conceptual matches.
- Fixed `CheckViolation` error during intelligence injection by ensuring dynamic domain mapping aligns with database schema constraints.
- Fixed `datetime` serialization issues in the Telegram Voice bridge via `TacticalEncoder`.

### Verified
- **Master E2E:** System successfully passed the "Boca Chica Flight" scenario, autonomously prioritizing, extracting ("SpaceX"), and spatially clustering ("Brownsville") based on active mission parameters.
- **Semantic E2E:** Confirmed that descriptive reports correctly link to target entities even when exact names are missing.

## [0.5.0] - 2026-02-28
### Added
- **Tactical Voice:** Implemented `TelegramVoice` agent to securely process commands and synthesize MCP tool results via Telegram.
- **MCP Tactical Tools:** Added `search_spatial`, `get_entity_network`, and `submit_tasking` to `mcp_server.py`.
- **Stress Testing:** Introduced `stress_test.py` to synthetically flood the database with OSINT and test agent concurrency.

### Changed
- **Robust Brain:** Refactored `AnalystAgent.poll()` with `FOR UPDATE SKIP LOCKED` and scaled to 3 instances to enable high-concurrency intelligence fusion.
- **Idempotency:** Replaced URL-based deduplication with robust SHA-256 `content_hash` indexing in `intelligence_records`.
