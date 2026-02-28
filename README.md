# Personal Intelligence Agency (PIA) Core

> *"The database is not a storage system. It is a reasoning system."*

**PIA Core** is the foundational data engine for a continuous, multi-dimensional intelligence collection and understanding system. It is designed to act as the "memory" and "spatial reasoning" layer for autonomous AI agents (like Cortex and OpenClaw), allowing them to ingest, relate, and understand global events in real-time.

---

## 🎯 The Concept

Humanity produces quintillions of bytes of data daily—flight tracks, news articles, financial flows, seismic events. Most systems *retrieve* this data. PIA is designed to *understand* it. 

PIA does this by decoupling ingestion from analysis via a highly specialized database architecture:

1. **The Seed:** The system is pre-loaded with a massive "Historical Baseline" (e.g., every major city on Earth, millions of entities via Wikidata, decades of declassified CIA documents). 
2. **The Telemetry:** Agents stream live data (OSINT, GEOINT, SIGINT) into the system.
3. **The Spine:** Every piece of data is converted into a **Universal Intelligence Record (UIR)**.
4. **The Heartbeat:** Every new UIR triggers an automated database event, waking up autonomous "Analyst Agents" to review the new data, generate semantic embeddings, and link it to the existing knowledge graph.

Instead of answering, *"What did the news say about the Strait of Hormuz today?"* 
PIA is designed to answer, *"How does today's maritime anomaly in the Strait of Hormuz relate to historical CIA assessments of the region, and which organizations in our graph are currently active there?"*

---

## 🏗️ System Architecture

The repository is structured as a professional Python monorepo using the `src/` layout, separating the Python logic ("The Brain") from the SQL/Docker infrastructure ("The Body").

### The Seven-Layer Data Model

The intelligence flows upward through seven layers within a custom-built **PostgreSQL 16** instance:

| Layer | Name | Technology | Purpose |
| :--- | :--- | :--- | :--- |
| **Layer 0** | Mission Control | mission_focus | Dynamic re-tasking of the entire agency focus (Category/Keywords). |
| **Layer 1** | Raw Telemetry | TimescaleDB | High-velocity time-series data (Flights, Seismic). |
| **Layer 2** | Intelligence Records (UIR) | pgvector / PostGIS | The core spine. Indexed by Time, Space, and Meaning. |
| **Layer 3** | Intelligence Clusters | DiskANN | Groupings of UIRs representing evolving patterns. |
| **Layer 4** | Strategic Digests | OpenRouter LLM | Finished, readable intelligence SITREPs. |
| **Layer 5** | Knowledge Graph | Apache AGE | Cypher-queryable graph of Entities and Relationships. |
| **Layer 6** | Continuous Aggregates | pg_cron | Auto-refreshing materialized views for real-time dashboards. |

### Repository Structure

```text
pia-core/
├── src/pia/                     # The Brain: Python App (Agents, Models, Core)
├── database/                    # The Memory: SQL Artifacts (Schema, Seeds)
│   ├── schema/                  # 01-06 SQL files defining the 6 layers
│   └── seeds/                   # Foundational seed data (Geography)
├── infra/                       # The Body: Infrastructure (Postgres, Agents)
├── scripts/                     # The Tools: Orchestration & Utility Scripts
├── tests/                       # The Validation: Integration & Unit Tests
├── docs/                        # The Ledger: Design Docs & Status Reports
├── pyproject.toml               # Python Dependency Management
└── docker-compose.yml           # Service Orchestration
```

---

## ⚡ Core Features

### 🧠 Parallel Analyst Swarm
The "Brain" is a distributed cluster of Analyst Agents using `FOR UPDATE SKIP LOCKED` to process the analysis queue concurrently. This ensures high-volume intelligence bursts are fused in real-time without bottlenecks.

### 🔍 Semantic Vector Resolution
Moving beyond keyword matching, PIA uses **pgvector** and **OpenRouter LLMs** to perform conceptual entity resolution. It can link a description like *"The Hawthorne-based rocket manufacturer"* to the hardened entity *"SpaceX"* using 1536-dimensional vector similarity.

### 🎯 Focus Mechanism (C2)
The Director can re-task the entire Agency instantly. By setting a **Mission Focus** (e.g., TECH or FINANCE), the sensors automatically prioritize matching data and the brain focuses extraction on mission-relevant entities.

### 📱 Tactical Voice (Telegram Interface)
Command the Agency from your phone. The built-in Telegram bot acts as an **OpenClaw Reasoning Agent**, allowing you to perform spatial searches, graph traversals, and mission tasking via natural language while on the move.

---

## 🚀 Getting Started

### Prerequisites
* Docker and Docker Compose
* Make (Optional, but recommended)
* PowerShell (For utility scripts)

### 1. Build and Run the Database Engine
The custom PostgreSQL image compiles Apache AGE from source and installs TimescaleDB and PostGIS.
```bash
# Linux/macOS
make build
make up

# Windows
./ps.ps1 build
./ps.ps1 up
```

### 2. Run the Test Suite
Ensure the engine is running properly and all 5 critical extensions are active.
```bash
# Linux/macOS
make test

# Windows
./ps.ps1 test
```

### 3. Seed the Geographic Foundation
Before the system can map intelligence, it needs to know the world map.
```bash
# Linux/macOS
make seed-geo

# Windows
./ps.ps1 seed-geo
```

---

## 📚 Documentation
Detailed architectural blueprints and implementation plans can be found in the `docs/` directory:
* `docs/STATUS.md`: The current technical state of the build.
* `docs/architecture/`: Long-term vision and system design documents.
* `docs/guides/`: Strategies for seeding the knowledge graph and integrating OpenClaw.

---
**Classification:** Open Source Vision Prototype  
**Version:** 0.6.0 (Strategic Evolution)
