# Changelog

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
