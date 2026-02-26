# ADR-002: Containerized Agent Execution
**Status:** Accepted  
**Date:** 2026-02-26  

## Context
Running agents locally on the host machine caused networking and authentication friction between the Python driver and the Dockerized database.

## Decision
Moved all autonomous agents into a dedicated **Agent Container** on the same Docker network as the database.

## Consequences
- **Positive:** Guaranteed connectivity via `DB_HOST=postgres`; consistent dependency management; simplified E2E testing.
- **Negative:** Requires Docker rebuilding when adding new dependencies to `pyproject.toml`.
