# ADR-001: Monorepo Clean Architecture
**Status:** Accepted  
**Date:** 2026-02-26  

## Context
We needed a repository structure that supports high-velocity development of both database schemas (SQL) and autonomous agents (Python).

## Decision
Adopted an **Enterprise Python Monorepo** with the `src/` layout.
- `src/pia/`: Strictly Python packages.
- `database/`: Strictly SQL artifacts.
- `infra/`: Strictly Docker/Deployment configurations.

## Consequences
- **Positive:** Atomic commits across SQL and Python; clear separation of concerns; fast linting/testing.
- **Negative:** Slightly more complex directory nesting.
