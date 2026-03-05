# Personal Intelligence Agency (PIA) Core

> *"The database is not a storage system. It is a reasoning system."*

**PIA Core** is the foundational data engine for a continuous, multi-dimensional intelligence collection and understanding system. It acts as the memory and spatial reasoning layer for autonomous AI agents, allowing them to ingest, relate, and understand global events in real-time.

---

## [MISSION] The Concept

Humanity produces quintillions of bytes of data daily—flight tracks, news articles, financial flows, seismic events. Most systems *retrieve* this data. PIA is designed to *understand* it. 

PIA does this by decoupling ingestion from analysis via a highly specialized database architecture:

1. **The Seed:** A pre-loaded historical baseline (Global cities, Wikidata entities).
2. **The Telemetry:** Live streaming data (OSINT, GEOINT, SIGINT).
3. **The Spine:** Every data point converted into a **Universal Intelligence Record (UIR)**.
4. **The Heartbeat:** Database triggers waking up **Analyst Agents** to fuse, embed, and link data to the Knowledge Graph.

---

## [BUSINESS] Licensing & Strategic Vision

PIA Core follows an **Open-Core** model protected by the **Business Source License (BSL) 1.1**. 

*   **Transparency First:** The foundational intelligence engine is public and audit-ready for government and corporate agencies.
*   **Small-Scale Freedom:** Free for individuals, non-profits, and startups with less than $5M in annual revenue.
*   **Enterprise Protection:** Use by large-scale agencies or commercial competitors requires a separate commercial license. 

Our goal is to create the **Industry Standard for Autonomous Intelligence**. We provide the open "Brain," while selling proprietary "Nervous System" connectors and high-fidelity "Tactical Dashboards."

---

## [SYSTEM] Architecture

The repository is a professional Python monorepo separating logic (The Brain) from SQL/Docker infrastructure (The Body).

### The Seven-Layer Data Model

The intelligence flows upward through seven layers within a custom **PostgreSQL 16** instance:

| Layer | Name | Technology | Purpose |
| :--- | :--- | :--- | :--- |
| **Layer 0** | Mission Control | mission_focus | Dynamic re-tasking of the agency focus (Category/Keywords). |
| **Layer 1** | Raw Telemetry | TimescaleDB | High-velocity time-series data (Flights, Seismic). |
| **Layer 2** | Intelligence Records (UIR) | pgvector / PostGIS | The core spine. Indexed by Time, Space, and Meaning. |
| **Layer 3** | Intelligence Clusters | DiskANN | Groupings of UIRs representing evolving patterns. |
| **Layer 4** | Strategic Digests | OpenRouter LLM | Finished, readable intelligence SITREPs. |
| **Layer 5** | Knowledge Graph | Apache AGE | Cypher-queryable graph of Entities and Relationships. |
| **Layer 6** | Continuous Aggregates | pg_cron | Auto-refreshing materialized views for dashboards. |

### Repository Structure

```text
PIA_OIA/
├── pia-core/                    # The Brain: Data Swarm & Knowledge Graph
│   ├── src/pia/                 # Python App (Agents, Models, Core)
│   └── database/                # The Memory: SQL Artifacts (Schema, Seeds)
├── pia-api/                     # The Bridge: FastAPI Real-Time WebSocket Server
└── pia-ui/                      # The Face: React/Cesium 3D Digital Twin
```

---

## [OPERATIONS] Core Features

### Parallel Analyst Swarm
Distributed cluster of Analyst Agents using `FOR UPDATE SKIP LOCKED` to process the analysis queue concurrently. Ensures real-time fusion of high-volume intelligence.

### Semantic Vector Resolution
Uses **pgvector** and **OpenRouter LLMs** for conceptual entity resolution. Links descriptions like *"The Hawthorne-based rocket manufacturer"* to the entity *"SpaceX"* via 1536-dimensional similarity.

### Focus Mechanism (C2)
Dynamic Command & Control layer. Re-task the entire Agency instantly via **Mission Focus** parameters (e.g., TECH or FINANCE).

### Tactical Voice (Telegram Interface)
Built-in Telegram bot acting as an **OpenClaw Reasoning Agent**. Perform spatial searches, graph traversals, and tasking via natural language.

---

## [COMMAND] Getting Started

### Prerequisites
* Docker and Docker Compose
* Make (Optional)
* PowerShell (For Windows utility scripts)

### 1. Build and Run
```bash
# Linux/macOS
make build && make up

# Windows
./ps.ps1 build && ./ps.ps1 up
```

### 2. Validation
```bash
# Full stack check
make test # or ./ps.ps1 test
```

---

## [LEDGER] Documentation
* `docs/STATUS.md`: Current technical state.
* `docs/architecture/`: Long-term blueprints.
* `docs/ledger/`: Roadmap and Changelog.

---
**Classification:** Open Source Vision Prototype  
**Version:** 0.8.0 (Visualization & User Experience)
