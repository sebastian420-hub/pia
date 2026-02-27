# Changelog

## [0.2.0] - 2026-02-26
### Added
- **Interface:** FastMCP server implementing Server-Sent Events (SSE) on port 8000.
- **Tools:** `get_active_clusters`, `get_cluster_details`, and `get_system_health` exposed to AI agents.
- **Brain:** Functional `AnalystAgent` performing spatial correlation and automated clustering.
- **Testing:** `test_final_stack.py` master validation suite.
- **Persistence:** Self-healing `pia_init` container for automated schema and seed restoration.

### Fixed
- MCP server stability issues resolved via SSE transport transition.
- Silent schema rollbacks fixed by removing graph initialization from transactional SQL.
- Dynamic environment variable resolution in `DatabaseManager`.

### Verified
- **Master Status:** 100% GREEN pass on all E2E system tests.
- **Interface:** Programmatic retrieval of intelligence clusters verified via MCP tool calls.
