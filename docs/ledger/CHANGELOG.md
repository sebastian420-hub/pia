# Changelog

## [0.4.0] - 2026-02-28
### Added
- **Tactical Voice:** Implemented `TelegramVoice` agent to securely process commands and synthesize MCP tool results via Telegram.
- **MCP Tactical Tools:** Added `search_spatial`, `get_entity_network`, and `submit_tasking` to `mcp_server.py`.
- **Senses:** `NewsAgent` added for real-time global OSINT ingestion (BBC, WSJ).
- **Knowledge Graph Toolset:** Added scripts to seed, verify (`check_graph`), and reset (`clean_graph`) the Apache AGE graph and relational database seamlessly.
- **Stress Testing:** Introduced `stress_test.py` to synthetically flood the database with OSINT and test agent concurrency.
- **Serialization Handling:** Added `TacticalEncoder` to manage PostgreSQL datetime objects dynamically within the AI pipeline.

### Changed
- **Robust Brain:** Refactored `AnalystAgent.poll()` with `FOR UPDATE SKIP LOCKED` and scaled to 3 instances to enable high-concurrency intelligence fusion.
- **LLM Integration:** Upgraded `NLPManager` to use OpenRouter API (`google/gemini-2.0-flash-exp:free`) for real-world factual extraction.
- **Idempotency:** Replaced URL-based deduplication with robust SHA-256 `content_hash` indexing in `intelligence_records`.
- **Initialization:** Made the `validate_system.py` script idempotent so the database schema doesn't throw errors upon container restart.

### Fixed
- Handled `ModuleNotFoundError` by switching to `pip install -e .` in the Dockerfile.
- Fixed Apache AGE `$$` escaping issues via direct Python driver implementation.
- Fixed `429 RateLimitError` in the Telegram Bot by adding user alerts and migrating to a stable model.
- Fixed `Object of type datetime is not JSON serializable` in the Telegram bridge via custom JSON encoder.

### Verified
- **High-Volume Fusion:** The system passed a 50-record injection stress test with zero collisions among the parallel analyst swarm.
- **End-to-End Voice:** The Director successfully queried the agency via Telegram and received a factually grounded, parsed Markdown response.

## [0.3.0] - 2026-02-26
### Added
- **Brain:** Upgraded `AnalystAgent` with NLP processing capabilities for entity discovery.
- **NLP Core:** `NLPManager` class for structured intelligence extraction via local LLM.
- **Resolver:** Entity Resolution logic to link news text to existing database UUIDs.
- **Telemetry:** Automated tracking of `mention_count` and `uir_refs` for all graph entities.
- **Testing:** `test_intelligence_fusion.py` integration suite for triple-join validation.

### Fixed
- Handled LLM connection timeouts with intelligent fallback logic to ensure agent uptime.
- Resolved PostgreSQL volume persistence issues in `docker-compose`.

### Verified
- **Fusion Path:** Verified that raw OSINT text results in autonomous entity linking and graph edge creation.
- **Stability:** System passed all tests with 100% success rate under multi-agent load.
