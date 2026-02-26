Complete, definitive system design document — incorporating OpenClaw, Cortex, Claude/MCP, the geospatial globe, and the intelligence pipeline as one unified ecosystem.

***

# PERSONAL INTELLIGENCE AGENCY (PIA)

## Complete Concept, System Design \& Technical Architecture

**Version 1.0 — February 2026**
**Operator: Solo Director**
**Classification: Personal Use**

***

## PART I — VISION \& DOCTRINE

### What This Is

The Personal Intelligence Agency is a fully automated, AI-driven intelligence ecosystem operated by a single human director. Every function traditionally staffed by dozens of analysts, collectors, and technicians is replaced by specialized AI agents running 24/7 on private self-hosted infrastructure. The system continuously collects raw intelligence from the world, processes and cross-correlates it, stores everything in a shared knowledge base, and delivers finished intelligence products to the Director on demand and on schedule.[^1][^2]

This is not a chatbot. It is not a dashboard. It is not a research tool. It is a **living, persistent, self-updating operational system** — a force multiplier that gives one person the analytical output of a small intelligence team.

### The Three Pillars

Every component in the PIA belongs to one of three interlocking pillars:

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│    SENTINEL     │   │     NEXUS       │   │     ORACLE      │
│                 │   │                 │   │                 │
│  Live 3D Globe  │   │  Intelligence   │   │  Command &      │
│  Geospatial     │   │  Pipeline       │   │  Control        │
│  Tactical Map   │   │  AI Agents      │   │  Interface      │
│                 │   │                 │   │                 │
│  Aircraft       │   │  OSINT          │   │  Natural Lang   │
│  Satellites     │   │  GEOINT         │   │  Query          │
│  Earthquakes    │   │  SIGINT         │   │  Daily Briefs   │
│  Vessels        │   │  Analysis       │   │  Alerts         │
│  OSINT markers  │   │  Reports        │   │  Mobile Access  │
└─────────────────┘   └─────────────────┘   └─────────────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                              │
                  ONE SHARED DATABASE BACKBONE
```

All three pillars share exactly one data backbone. A geo-tagged OSINT event collected by NEXUS automatically becomes a marker on SENTINEL. A flight anomaly flagged on SENTINEL automatically triggers an analysis report in NEXUS, delivered via ORACLE.[^3][^4]

### The Intelligence Cycle — Automated

```
1. TASKING        ← Director (you) or automated triggers
2. COLLECTION     ← AI collector agents, APIs, scrapers, live feeds
3. PROCESSING     ← Normalization, geo-tagging, entity extraction, embedding
4. ANALYSIS       ← Cross-correlation, anomaly detection, pattern recognition
5. PRODUCTION     ← Finished reports, briefs, alerts
6. DISSEMINATION  ← Globe markers, Telegram, email, dashboard
7. FEEDBACK       ← Your actions and reactions retask the collectors
```


***

## PART II — THE THREE-AGENT COMMAND STRUCTURE

### Your Agency Has Three Human-Replacements

Before designing any database or pipeline, understand the three tools you already have and what role each plays. They are not interchangeable — they are **complementary layers**:[^5][^6][^1]

```
╔══════════════════════════════════════════════════════════════════════╗
║                    DIRECTOR (YOU)                                    ║
║    Message via Telegram / WhatsApp / Discord / CLI                   ║
╚══════════════════════════════╦═══════════════════════════════════════╝
                               ║
              ┌────────────────▼─────────────────┐
              │           OPENCLAW               │
              │   24/7 Personal Command Layer    │
              │   • Always-on, always listening  │
              │   • Omnichannel messaging        │
              │   • Cron jobs & proactive alerts │
              │   • Routes tasks to other agents │
              │   • Skills system (custom tools) │
              └──────────┬─────────────┬─────────┘
                         │             │
           ┌─────────────▼──┐     ┌────▼──────────────────┐
           │    CORTEX      │     │   CLAUDE (via API+MCP) │
           │  Engineer Agent│     │   Director Agent       │
           │                │     │   Analyst Agent        │
           │ • Builds code  │     │   Report Writer        │
           │ • Fixes bugs   │     │   ORACLE (NL queries)  │
           │ • Deploys svcs │     │   Cross-correlation    │
           │ • Runs ops cmds│     │   Pattern recognition  │
           │ • Hybrid Rust/ │     │   Finished briefs      │
           │   Go native    │     │                        │
           └────────┬───────┘     └──────────┬─────────────┘
                    │                        │
                    └────────────┬───────────┘
                                 ▼
                    UNIFIED INTELLIGENCE DATABASE
```


### Agent Role Matrix

| Agent | Layer | Primary Role | Never Does |
| :-- | :-- | :-- | :-- |
| **OpenClaw** | Human Interface | 24/7 comms, cron jobs, alerts, task routing | Deep analysis, code execution |
| **Claude + MCP** | Cognitive Core | Analysis, correlation, reports, NL queries, directing | System ops, file writes |
| **Cortex** | Engineering Core | Code, DevOps, infra, building agents, debugging | Intelligence analysis |

[^6][^1][^5]

### How They Communicate

All three agents communicate through two mechanisms — never directly to each other's internals:[^7][^8]

1. **Webhooks** — OpenClaw dispatches to Claude (via API webhook) and to Cortex (via Cortex's webhook receiver). Results POST back to OpenClaw
2. **Shared Database** — All three read from and write to PostgreSQL. This is the true shared memory. An insight written by Claude becomes a UIR that Cortex can query, and a UIR written by Cortex's build log is visible to Claude's analysis

***

## PART III — THE UNIFIED INTELLIGENCE DATABASE

### Design Principle

One database. Every agent reads from it and writes to it. No agent has a private data store. This is what enables cross-domain correlation — your OSINT agent and GEOINT agent can independently discover they are tracking the same location at the same time, because they share memory.[^4][^3]

### Database Stack — Consolidated PostgreSQL

Rather than running four separate database systems, consolidate into **PostgreSQL with three extensions**:[^9][^10][^11]

```sql
-- Single PostgreSQL 16 instance with all extensions
CREATE EXTENSION postgis;       -- Spatial: flight tracks, geo-tagged events
CREATE EXTENSION vector;        -- pgvector: semantic embeddings, RAG search  
CREATE EXTENSION timescaledb;   -- Time-series: telemetry, track history
```

Redis runs separately as a hot cache and pub/sub event bus only — never as a primary store.[^12]

### The Universal Intelligence Record (UIR)

Every piece of information — regardless of which agent collected it, from what source, in what domain — is stored as a UIR with the same schema. This is the contract all agents share:

```sql
CREATE TABLE intelligence_records (
    uid             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Source provenance (mandatory, always traceable)
    source_type     TEXT NOT NULL CHECK (source_type IN (
                        'OSINT','GEOINT','SIGINT','TECHINT',
                        'FININT','DERIVED','HUMINT','SYSTEM')),
    source_agent    TEXT NOT NULL,    -- 'openclaw','claude','cortex',
                                      -- 'osint_collector', etc.
    source_url      TEXT,
    source_credibility FLOAT DEFAULT 0.5, -- 0.0 to 1.0

    -- Content
    confidence      FLOAT CHECK (confidence BETWEEN 0.0 AND 1.0),
    classification  TEXT DEFAULT 'UNCLASSIFIED',
    content_raw     TEXT,
    content_summary TEXT,             -- AI-generated 2-sentence summary
    entities        TEXT[],           -- extracted: people, orgs, locations
    tags            TEXT[],           -- domain tags for routing

    -- Geospatial (PostGIS)
    geo             GEOMETRY(Point, 4326),
    geo_precision   TEXT,             -- 'exact','city','region','country'

    -- Semantic memory (pgvector)
    embedding       VECTOR(1536),     -- for RAG and semantic search

    -- Relationships
    linked_uids     UUID[],           -- related UIRs
    agent_task_id   UUID,

    -- Lifecycle
    ttl             TIMESTAMPTZ,
    verified        BOOLEAN DEFAULT FALSE
);

-- Critical indexes
CREATE INDEX idx_geo    ON intelligence_records USING GIST(geo);
CREATE INDEX idx_embed  ON intelligence_records
    USING ivfflat(embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_time   ON intelligence_records(created_at DESC);
CREATE INDEX idx_tags   ON intelligence_records USING GIN(tags);
CREATE INDEX idx_type   ON intelligence_records(source_type);
```


### Geospatial Time-Series Tables

Live positional data is too high-volume for the UIR table. It lives in dedicated TimescaleDB hypertables that the globe reads directly:

```sql
-- Flight tracks (GEOINT Agent writes every 5 seconds)
CREATE TABLE flight_tracks (
    time        TIMESTAMPTZ NOT NULL,
    icao24      TEXT NOT NULL,
    callsign    TEXT,
    position    GEOMETRY(Point, 4326),
    altitude_ft INTEGER,
    speed_kts   FLOAT,
    heading     FLOAT,
    squawk      TEXT,
    anomaly_score FLOAT DEFAULT 0.0   -- filled by Anomaly Detector
);
SELECT create_hypertable('flight_tracks', 'time');
CREATE INDEX ON flight_tracks USING GIST(position);

-- Satellite positions (updated every 30 seconds via SGP4 propagation)
CREATE TABLE satellite_positions (
    time        TIMESTAMPTZ NOT NULL,
    norad_id    INTEGER NOT NULL,
    name        TEXT,
    position    GEOMETRY(Point, 4326),
    altitude_km FLOAT,
    velocity_kms FLOAT,
    category    TEXT   -- 'MILITARY','WEATHER','COMMS','ISS', etc.
);
SELECT create_hypertable('satellite_positions', 'time');

-- Agent task log (every agent logs its actions here)
CREATE TABLE agent_tasks (
    task_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    agent       TEXT NOT NULL,
    task_type   TEXT NOT NULL,
    input       JSONB,
    output      JSONB,
    status      TEXT DEFAULT 'PENDING',  -- PENDING/RUNNING/DONE/FAILED
    duration_ms INTEGER,
    uirs_written UUID[]   -- UIRs produced by this task
);
```


***

## PART IV — SENTINEL (THE GLOBE)

### Rendering Stack

```
Tauri v2 (Rust shell — cross-platform desktop, no Electron)
└── WKWebView → React 18 + TypeScript
    ├── Cesium.js via resium
    │   └── WGS84 photorealistic globe, terrain, CZML streaming
    ├── deck.gl (GPU-accelerated overlay layers)
    │   ├── ScatterplotLayer   → live aircraft (color by altitude)
    │   ├── TripsLayer         → animated flight track history
    │   ├── ColumnLayer        → earthquake magnitude 3D columns
    │   ├── IconLayer          → geo-tagged OSINT event markers
    │   ├── HeatmapLayer       → SIGINT event density
    │   └── ArcLayer           → correlated event connections
    ├── Zustand                → reactive globe state
    ├── WebSocket client       → live Redis Stream feed
    └── Tailwind CSS           → tactical HUD chrome
```


### Data Sources → Globe

| Layer | Source | Update Rate | Protocol |
| :-- | :-- | :-- | :-- |
| Aircraft | OpenSky Network API | 5 seconds | REST → Redis → WebSocket |
| Satellites | CelesTrak TLE + SGP4 | 30 seconds | Propagated locally |
| Earthquakes | USGS GeoJSON feed | 60 seconds | REST poll |
| Vessels | MarineTraffic / AIS | 30 seconds | REST → Redis |
| OSINT Events | PostgreSQL UIR table | On insert | Redis pub/sub |
| Anomalies | Analyst Agent output | On detection | Redis pub/sub |
| Weather | NOAA NEXRAD tiles | 5 minutes | Tile overlay |

### HUD Layer Composition

```
Layer 5: React UI (absolute positioned, z-index 1000)
          Classification banner, sidebar panels, MGRS readout,
          alert ticker, agent status indicators

Layer 4: Anomaly Highlights (deck.gl, z-index 900)
          Red pulsing rings on flagged positions

Layer 3: OSINT Event Markers (deck.gl IconLayer, z-index 800)
          Color-coded by source_type, click → UIR detail panel

Layer 2: Live Data Overlays (deck.gl, z-index 700)
          Aircraft, satellites, vessels, earthquakes

Layer 1: Cesium Globe (WebGL canvas, z-index 0)
          Terrain, imagery, atmosphere, MGRS grid

CSS HUD filter on canvas:
.globe-hud::after {
  background: repeating-linear-gradient(
    0deg, transparent 2px, rgba(0,255,70,0.03) 4px
  );
  mix-blend-mode: screen;
  pointer-events: none;
}
```


### macOS Sandbox Fix

Tauri on macOS requires explicit WKWebView entitlements. Without these, Cesium.js WebGL resources silently fail to load:[^13]

```xml
<!-- Entitlements.plist -->
<key>com.apple.security.network.client</key><true/>
<key>com.apple.security.network.server</key><true/>
```

Serve Cesium assets via Tauri's localhost plugin (`tauri-plugin-localhost`) — not as file:// assets. This bypasses WKWebView's origin sandbox entirely.

***

## PART V — NEXUS (THE INTELLIGENCE PIPELINE)

### Agent Roster \& Responsibilities

**OSINT Collector Agent** (CrewAI, Python)

- Scrapes news APIs, RSS feeds, social media, Telegram channels, forums, public records, company registries
- Tools: Firecrawl, Jina.ai, SerpAPI, Playwright, Nitter (Twitter), Reddit API, Feedly
- Schedule: Topic monitoring every 15 min; deep domain crawl every 6 hours
- Output: UIRs tagged `OSINT` with entity extraction and embeddings written to PostgreSQL[^14][^15]

**GEOINT Agent** (Python + asyncio)

- Manages all positional data collection; feeds SENTINEL
- Tools: OpenSky Network, CelesTrak + satellite.js SGP4, USGS GeoJSON, MarineTraffic, NOAA
- Schedule: Flights every 5 sec; satellites every 30 sec; seismic every 60 sec
- Output: Writes to `flight_tracks` and `satellite_positions` hypertables; geo-tagged UIRs for significant events (new earthquake M5+, unusual satellite maneuver)

**SIGINT Monitor Agent** (Go, event-driven)

- Watches keyword triggers across APIs, webhooks, and feeds in real time
- Tools: Shodan webhooks, Twitter/X filtered streams, keyword RSS watchers, DNS monitoring, dark web forum crawlers
- Trigger: Fires immediately on keyword match; writes alert UIR; publishes to Redis `alerts:live` stream
- Output: `SIGINT` UIRs with immediate Redis pub/sub notification[^15]

**TECHINT Agent** (Python)

- Technical infrastructure intelligence: domain reconnaissance, IP mapping, breach monitoring
- Tools: Shodan API, Censys, SecurityTrails, DNSDumpster, DeHashed, theHarvester, VirusTotal
- Schedule: Daily deep scan on monitored targets; immediate on SIGINT trigger for same entity
- Output: `TECHINT` UIRs with infrastructure maps and relationships[^15]

**All-Source Analyst Agent** (LangGraph, Claude API)

- The cognitive core. Wakes on new UIR events via Redis subscription
- Process: New UIR arrives → semantic search pgvector for related records → PostGIS spatial proximity query → TimescaleDB temporal correlation → DBSCAN anomaly clustering → produce DERIVED UIR with confidence score
- Critical pattern: *"New OSINT about military exercise near Taiwan → query all GEOINT + SIGINT within 500km in last 72 hours → finds 3 correlated flight anomalies + 2 satellite passes → produces correlated intelligence report"*
- Output: `DERIVED` UIRs; updates `anomaly_score` on related `flight_tracks` rows[^16][^17]

**Report Writer Agent** (Claude API, AutoGen)

- Formats finished intelligence products for human consumption
- Products: Daily Morning Brief (0700), Situation Reports (on-demand), Anomaly Alerts (immediate), Weekly Intelligence Summary
- Output: Markdown/PDF delivered to OpenClaw → Telegram/email to Director

**Memory Librarian Agent** (Python, cron)

- Nightly maintenance: deduplication via cosine similarity threshold, TTL enforcement, pgvector index rebuild, dangling `linked_uids` repair
- Ensures the corpus stays clean and searchable over months/years[^3]

**Counterintel / Validator Agent** (Python, always-on)

- Guards every ingest path against prompt injection in scraped content
- Scores source credibility, cross-references claims against existing UIRs
- Validates DERIVED UIRs before they become alerts — prevents hallucinated intelligence from reaching the Director[^18]


### LangGraph Orchestration — Director Agent

The Director Agent uses LangGraph's stateful graph pattern — the right choice for complex conditional routing with branching logic:[^19][^20]

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class DirectorState(TypedDict):
    directive: str          # from Director (you)
    task_type: str          # classified by router
    subtasks: list          # decomposed tasks
    assigned_agents: list   # which agents are working
    results: dict           # collected results
    report: str             # finished product

# Graph nodes: router → planner → dispatcher → synthesizer → deliver
# Conditional edges route based on task_type:
# "monitor"  → OSINT + SIGINT agents
# "analyze"  → Analyst Agent
# "locate"   → GEOINT Agent + PostGIS query
# "build"    → dispatch to Cortex via webhook
# "report"   → Report Writer
```


***

## PART VI — ORACLE (THE COMMAND INTERFACE)

### What ORACLE Is

ORACLE is your Director's desk — the interface through which you query and command your entire agency. It has three surfaces:[^21][^1]

1. **OpenClaw (Telegram/WhatsApp/Discord)** — Mobile, conversational, anywhere
2. **Terminal CLI** — Your existing Cortex terminal for direct system interaction
3. **Web Dashboard** — SENTINEL globe + intelligence panels in the browser

### Natural Language → Intelligence

Claude, connected to your PostGIS database via MCP, translates plain English into spatial SQL:[^22][^8]

```
YOU (via Telegram):
"Any aircraft acting weird near the Taiwan Strait in the last 24 hours?"

OPENCLAW → CLAUDE (MCP: postgis_intelligence tool):
SELECT ft.*, ir.content_summary
FROM flight_tracks ft
LEFT JOIN intelligence_records ir
  ON ST_DWithin(ft.position, ir.geo, 50000)
  AND ir.source_type IN ('OSINT','SIGINT')
WHERE ST_Within(ft.position,
    ST_GeomFromText('POLYGON((119 21, 122 21, 122 26, 119 26, 119 21))',4326))
  AND ft.time > NOW() - INTERVAL '24 hours'
  AND ft.anomaly_score > 0.7
ORDER BY ft.anomaly_score DESC LIMIT 20;

CLAUDE → OpenClaw → YOU (Telegram):
"3 aircraft flagged in the last 24 hours near the Taiwan Strait:
 - SQ7721: transponder squawk changed mid-flight (anomaly: 0.91)
 - Unknown ICAO: operating below FL050 with no flight plan (anomaly: 0.88)
 - Correlated: 2 OSINT UIRs from Reuters + AP about military exercises
   in the same region within 6 hours of these tracks."
```


### MCP Server Architecture

Claude connects to your infrastructure through four lightweight MCP servers:[^8][^23]

```python
# MCP Server 1: Intelligence Database
# Exposes: query_uirs(), semantic_search(), spatial_query()
# Claude writes SQL → MCP executes parameterized query → returns JSON

# MCP Server 2: Live Feeds  
# Exposes: get_active_flights(), get_anomalies(), get_alerts()
# Reads from Redis hot cache → returns current state

# MCP Server 3: Globe Control
# Exposes: highlight_position(), add_marker(), set_filter()
# Sends WebSocket commands to SENTINEL frontend

# MCP Server 4: Agent Dispatch
# Exposes: task_osint(), task_geoint(), task_cortex()
# Creates agent_task records + triggers via webhook
```


***

## PART VII — OPENCLAW INTEGRATION DESIGN

### OpenClaw's Three Extension Types in Your PIA

OpenClaw supports three integration mechanisms, each serving a different purpose:[^24]

- **Skills** — Natural language driven; SKILL.md files that tell OpenClaw how to call your API endpoints when you phrase a request a certain way
- **Plugins** — Deep TypeScript/JavaScript Gateway extensions for persistent background listeners (your SIGINT monitor notifications)
- **Webhooks** — HTTP endpoints for bidirectional communication with n8n, Claude, and Cortex


### Custom Skills for Your PIA

```
pia-brief          → "Get my morning brief" → GET /api/brief/latest
pia-query          → "Show me X" → POST /api/oracle/query {nl: "..."}
pia-globe          → "What's on the globe?" → GET /api/sentinel/summary
pia-alert-status   → "Any new alerts?" → GET /api/alerts/active
pia-task-osint     → "Research [target]" → POST /api/agents/osint/task
pia-task-cortex    → "Build X" → POST /api/cortex/webhook/task
pia-add-memory     → "Remember that..." → POST /api/intelligence/humint
```


### OpenClaw + n8n Proxy Pattern

For any integration requiring API keys (Telegram bot, NOAA, Twitter API), use the **OpenClaw → n8n proxy pattern** to keep secrets out of OpenClaw entirely:[^25][^7]

```
OpenClaw decides to send a Telegram alert
    ↓
OpenClaw calls: POST http://n8n:5678/webhook/pia-alert
    { "message": "...", "severity": "HIGH", "uid": "..." }
    ↓
n8n workflow executes (holds the Telegram Bot Token credential)
    ↓
n8n sends formatted message to your Telegram
    ↓
n8n POSTs result back to OpenClaw's webhook receiver
```

OpenClaw never touches your Telegram Bot Token. All credentials live in n8n's encrypted credential store.[^26][^25]

### Proactive Cron Jobs (OpenClaw Scheduled Tasks)

```
0700 daily    → fetch Morning Brief → send to Telegram
*/30 * * * *  → check Redis alerts:live stream → notify if new HIGH alerts
0 */6 * * *   → trigger OSINT deep crawl on monitored topics
0 0 * * 0     → request Weekly Intelligence Summary from Report Writer
*/5 * * * *   → system health check: verify last UIR < 10 min ago
```


***

## PART VIII — CORTEX INTEGRATION DESIGN

### Cortex's Role Is Exclusively Engineering

Cortex  is never used for intelligence analysis. Its role is purely **building and maintaining the system itself**:[^6]

- Writing new collector agent code from Claude's specification
- Debugging failing microservices (reads Docker logs, diagnoses, patches)
- Deploying updated containers to VPS
- Writing and running database migrations
- Adding new Kafka topics and Redis Stream consumers
- Modifying ingestor configs when new data sources are added


### Cortex Webhook Receiver

Add a FastAPI endpoint to Cortex that accepts structured engineering tasks from Claude or OpenClaw:

```python
# cortex/webhook_receiver.py
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import uuid

app = FastAPI()

class EngineeringTask(BaseModel):
    task_id: str = str(uuid.uuid4())
    task_type: str   # 'build_agent'|'debug_service'|'deploy'|'migrate_db'
    spec: str        # natural language specification or structured JSON
    context: dict    # relevant codebase context
    priority: str    # 'HIGH'|'NORMAL'|'LOW'
    callback_url: str  # where to POST the result

@app.post("/webhook/task")
async def receive_task(task: EngineeringTask, bg: BackgroundTasks):
    # Log to agent_tasks table
    # Dispatch to Cortex planning engine
    bg.add_task(cortex_execute, task)
    return {"status": "accepted", "task_id": task.task_id}
```


### Cortex UIR Writer

After every completed task, Cortex writes a `SYSTEM` UIR to PostgreSQL — keeping the Director (Claude) aware of all engineering changes:[^3]

```python
# After task completion, Cortex writes:
{
  "source_type": "SYSTEM",
  "source_agent": "cortex",
  "content_summary": "Added MarineTraffic vessel ingestor. 
                       Redis Stream 'intelligence:geoint:vessels' active. 
                       Deployed to VPS. Commit: a3f92b1",
  "tags": ["engineering", "deployment", "vessels"],
  "confidence": 1.0
}
```


### Memory Bridge — ChromaDB → pgvector

Cortex uses ChromaDB natively. Run a nightly sync job that embeds Cortex's ChromaDB engineering knowledge into pgvector — so Claude can query codebase knowledge during analysis:[^11][^6]

```python
# nightly_sync.py
# 1. Query ChromaDB for entries modified since last sync
# 2. Re-embed with your standard embedding model
# 3. INSERT into intelligence_records with source_agent='cortex_memory'
# 4. Cortex's engineering decisions become queryable alongside intelligence
```


***

## PART IX — EVENT BUS \& COMMUNICATION

### Redis Streams Topology

All inter-agent communication flows through Redis Streams. Agents never call each other directly:[^27][^28]

```
Stream: intelligence:osint        ← OSINT Collector writes
Stream: intelligence:geoint       ← GEOINT Agent writes  
Stream: intelligence:sigint       ← SIGINT Monitor writes
Stream: intelligence:techint      ← TECHINT Agent writes
Stream: intelligence:derived      ← Analyst Agent writes
Stream: system:tasks              ← Director Agent writes task assignments
Stream: system:health             ← All agents write heartbeats
Stream: alerts:live               ← High-priority alerts (OpenClaw subscribes)
Stream: globe:events              ← SENTINEL frontend subscribes
```

Every stream message carries only the `uid` of the UIR just written to PostgreSQL + metadata. Downstream agents fetch the full record from the database by UID — the stream is the notification, not the payload.[^28]

### When to Upgrade to Kafka

Upgrade from Redis Streams to Kafka when any of these thresholds are hit:[^29][^27]

- Processing >50,000 events/hour consistently
- Needing windowed stream joins across 3+ topics simultaneously
- Requiring full event replay from T-0 for audit or reprocessing
- Running more than 10 concurrent stream consumers

At solo operator scale, Redis Streams handles everything cleanly with vastly lower operational overhead.

***

## PART X — INFRASTRUCTURE \& SECURITY

### Self-Hosted Stack

```
VPS: Hetzner CX31 or Contabo VDS (~$15-25/month)
OS: Ubuntu 22.04 LTS
Runtime: Docker Compose (MVP) → K3s (at scale)

Services:
├── postgres:16-alpine
│   (+ PostGIS + pgvector + TimescaleDB extensions)
├── redis:7-alpine
├── openclaw:latest          (port 3456)
├── n8n:latest               (port 5678)
├── cortex-webhook:latest    (port 8001, FastAPI)
├── ingestor-geoint          (Go, no exposed port)
├── ingestor-osint           (Python, no exposed port)
├── ingestor-sigint          (Go, no exposed port)
├── websocket-gateway        (Go, port 8080)
├── mcp-server               (Node.js, port 3000)
├── nginx                    (reverse proxy, port 443)
├── grafana                  (port 3001, observability)
└── loki + promtail          (log aggregation)
```


### Docker Network Isolation

```yaml
networks:
  intelligence-internal:   # DB, agents, ingestors — no external access
  gateway-external:        # Only nginx, openclaw, mcp-server
  
# Ingestors: intelligence-internal only
# PostgreSQL: intelligence-internal only  
# OpenClaw: both networks (needs internet for messaging apps)
# Nginx: both networks (terminates TLS, proxies inward)
```


### Security Layers

Given that your system ingests untrusted external content, security is non-negotiable:[^30][^18]

- **Prompt injection defense** — Counterintel Agent validates all scraped content before any LLM call; raw HTML is never passed directly to Claude or Cortex
- **Append-only UIRs** — Records are never updated, only versioned via `linked_uids`; full audit trail
- **n8n credential proxy** — All external API keys live in n8n's encrypted credential store; OpenClaw and agents only see webhook URLs[^25]
- **Cortex sandboxing** — Cortex runs in a Docker container with explicit filesystem mounts; cannot access PostgreSQL directly — only through the validated gateway API
- **Rate limiting** — Nginx upstream of all services; 429 responses on threshold breach
- **JWT auth** — All internal API calls carry short-lived JWTs; OpenClaw authenticates to MCP server and Cortex webhook with rotating tokens
- **Observability** — OpenTelemetry → Grafana; every agent heartbeat logged to `system:health` Redis stream; alert if any agent silent >10 minutes

***

## PART XI — BUILD SEQUENCE

Build one stable layer before adding the next. Never skip ahead:[^31]


| Phase | What You Build | Done When |
| :-- | :-- | :-- |
| **1. Infrastructure** | VPS + PostgreSQL + PostGIS + pgvector + TimescaleDB + Redis + Docker Compose | DB accepts connections; tables created |
| **2. Globe MVP** | Tauri + React + Cesium.js + deck.gl + static GeoJSON test data | 3D globe renders on macOS + Windows |
| **3. First Live Feed** | GEOINT Go ingestor → OpenSky → Redis Stream → WebSocket gateway → deck.gl layer | Live aircraft appear on globe |
| **4. OpenClaw Setup** | OpenClaw + n8n on VPS; Telegram channel connected; first custom PIA skill | You can message your server from Telegram |
| **5. OSINT Collector** | OSINT Python agent → news/RSS → UIR → PostgreSQL + pgvector | First intelligence records in DB |
| **6. Shared Backbone** | Globe shows geo-tagged OSINT markers from PostgreSQL; both agents writing UIRs | Globe and intel pipeline unified |
| **7. Claude + MCP** | 4 MCP servers; natural language → PostGIS query → Telegram response | "Show me X" works end-to-end |
| **8. Cortex Webhook** | FastAPI webhook receiver in Cortex; UIR writer on task completion | Claude can dispatch to Cortex |
| **9. Director + Analyst** | LangGraph Director + Analyst agents; cross-domain correlation; DERIVED UIRs | First correlated intelligence report |
| **10. Daily Brief** | Report Writer on cron; Morning Brief → Telegram at 0700 | Morning brief arrives automatically |
| **11. SIGINT + TECHINT** | Keyword monitors + Shodan/Censys integration | Real-time keyword alerts firing |
| **12. Anomaly Detection** | DBSCAN on flight tracks; anomaly_score updates; globe highlights anomalies | First automated anomaly flag |
| **13. Full Hardening** | Kafka migration, K3s, full observability, Counterintel Agent | Production-grade scale |


***

## THE CORE INSIGHT

What you are building does not exist as a single purchasable product. Enterprise equivalents — Palantir Gotham, Babel Street, Recorded Future — cost intelligence agencies and corporations millions of dollars per year. Your advantage is being a solo builder in 2026, at the precise moment when LLM APIs, open-source geospatial tooling, agentic frameworks, and self-hosted infrastructure have all matured simultaneously to the point where one person can assemble what previously required an engineering team of 20 and an analyst team of 10.[^2][^32][^33][^1]

OpenClaw is your front door — the human-to-machine interface that makes the entire system accessible from your phone at 3am. Claude is the brain — the cognitive layer that thinks, correlates, and writes finished intelligence. Cortex is the hands — the engineering layer that builds, fixes, and evolves the system itself. The database is the soul — the accumulated intelligence corpus that grows more valuable with every passing day.[^4][^3]

Design the UIR schema correctly from day one. Every other component is replaceable. The corpus is not.
<span style="display:none">[^34][^35][^36][^37][^38][^39][^40][^41][^42][^43][^44][^45][^46][^47][^48][^49][^50][^51][^52][^53][^54][^55][^56][^57]</span>

<div align="center">⁂</div>

[^1]: https://www.digitalocean.com/resources/articles/what-is-openclaw

[^2]: https://developer.microsoft.com/blog/designing-multi-agent-intelligence

[^3]: https://www.tigerdata.com/learn/building-ai-agents-with-persistent-memory-a-unified-database-approach

[^4]: https://milvus.io/blog/openagents-milvus-how-to-build-smarter-multi-agent-systems-that-share-memory.md

[^5]: https://www.anthropic.com/engineering/multi-agent-research-system

[^6]: README.md

[^7]: https://clawtank.dev/blog/openclaw-n8n-integration-guide

[^8]: https://platform.claude.com/docs/en/agent-sdk/mcp

[^9]: https://www.tigerdata.com/learn/postgresql-extensions-pgvector

[^10]: https://oneuptime.com/blog/post/2026-01-27-timescaledb-postgresql-extensions/view

[^11]: https://liambx.com/blog/postgresql-timescale-vector-ai-guide

[^12]: https://streamkap.com/resources-and-guides/redis-real-time-analytics-explained-en

[^13]: https://www.reddit.com/r/tauri/comments/1m76w9q/tauri_macos_production_build_failing_all_outgoing/

[^14]: https://shadowdragon.io/blog/osint-techniques/

[^15]: https://shadowdragon.io/blog/best-osint-tools/

[^16]: https://bix-tech.com/langgraph-in-practice-orchestrating-multiagent-systems-and-distributed-ai-flows-at-scale/

[^17]: https://www.nv5.com/news/orchestrating-intelligence/

[^18]: https://blogs.cisco.com/ai/personal-ai-agents-like-openclaw-are-a-security-nightmare

[^19]: https://iterathon.tech/blog/ai-agent-orchestration-frameworks-2026

[^20]: https://www.datacamp.com/tutorial/crewai-vs-langgraph-vs-autogen

[^21]: https://carto.com/ai-agents

[^22]: https://playbooks.com/mcp/receptopalak-postgis

[^23]: https://resollm.ai/blog/claude-server-protocols-power-gen-ai-workflows/

[^24]: https://lumadock.com/tutorials/openclaw-custom-api-integration-guide

[^25]: https://github.com/hesamsheikh/awesome-openclaw-usecases/blob/main/usecases/n8n-workflow-orchestration.md

[^26]: https://www.linkedin.com/posts/simonhoiberg_openclaw-n8n-this-is-an-extremely-powerful-activity-7426609585601445888-rAsK

[^27]: https://dev.to/mtk3d/beyond-the-hype-why-we-chose-redis-streams-over-kafka-for-our-microservices-dmc

[^28]: https://www.harness.io/blog/event-driven-architecture-redis-streams

[^29]: https://github.com/AutoMQ/automq/wiki/Apache-Kafka-vs.-Redis-Streams:-Differences-\&-Comparison

[^30]: https://www.crowdstrike.com/en-us/blog/what-security-teams-need-to-know-about-openclaw-ai-super-agent/

[^31]: https://www.wave-access.com/public_en/blog/2026/february/05/how-to-build-ai-agents-that-scale-from-pilot-to-ecosystem/

[^32]: https://aimlapi.com/blog/what-is-openclaw

[^33]: https://www.prowaveai.com

[^34]: https://vallettasoftware.com/blog/post/openclaw-2026-guide

[^35]: https://github.com/VoltAgent/awesome-openclaw-skills

[^36]: https://xcloud.host/openclaw-n8n-integration/

[^37]: https://lumadock.com/tutorials/openclaw-custom-api-integration-guide?language=ukranian

[^38]: https://www.reddit.com/r/LangChain/comments/1onoufx/building_a_langchainlanggraph_multiagent/

[^39]: https://latenode.com/blog/ai/ai-agents/what-is-openclaw

[^40]: https://docs.openclaw.ai/automation/webhook

[^41]: https://docs.openclaw.ai/cli/webhooks

[^42]: https://www.langchain.com/langgraph

[^43]: https://getclawdbot.org/docs/api

[^44]: https://redis.io/blog/ai-agent-orchestration-platforms/

[^45]: https://openclawskills.org

[^46]: https://lumadock.com/tutorials/openclaw-webhooks-explained

[^47]: https://www.reddit.com/r/n8n/comments/1r24b7c/i_rebuilt_most_of_openclaws_core_functionality_in/

[^48]: https://github.com/caprihan/openclaw-n8n-stack

[^49]: https://www.youtube.com/watch?v=7ekNNMmiNrM

[^50]: https://www.youtube.com/watch?v=CqMV5-iOf4M

[^51]: https://n8n.io/integrations/webhook/

[^52]: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview

[^53]: https://www.youtube.com/watch?v=-wgXFUg3ivc

[^54]: https://www.dni.gov/files/ODNI/documents/IC_OSINT_Strategy.pdf

[^55]: https://talks.osgeo.org/foss4g-2025/talk/N3KH8B/

[^56]: https://matom.ai/insights/cesium-vs-deck-gl/

[^57]: https://open-claw.org

