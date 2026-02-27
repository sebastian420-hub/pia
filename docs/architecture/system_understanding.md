Personal Intelligence Agency (PIA) — Complete System Understanding

## Part 1: What This System Is

The Personal Intelligence Agency is not a chatbot, a dashboard, or a research tool. It is a **fully automated, AI-driven intelligence ecosystem operated by a single human Director**. Every function that traditionally requires dozens of analysts, collectors, and technicians is replaced by specialized AI agents running 24/7 on private, self-hosted infrastructure.[^1]

The core value proposition is this: enterprise intelligence platforms like Palantir Gotham or Recorded Future cost millions of dollars per year and require teams of 20+ engineers and 10+ analysts. In 2026, LLM APIs, open-source geospatial tooling, agentic frameworks, and self-hosted infrastructure have all matured to the point where one person can assemble an equivalent system. That is what PIA is.[^1]

The system continuously collects raw intelligence from the world, processes and cross-correlates it across multiple domains simultaneously, stores everything in a shared knowledge base, and delivers finished intelligence products to you on demand and on schedule.[^1]

The four biological analogies that define PIA:

- **Senses** — agents that perceive the world
- **Memory** — the PostgreSQL database that retains everything
- **Brain** — the Analyst Agent and Claude that reason over memory
- **Voice** — ORACLE and OpenClaw that communicate findings to you

***

## Part 2: The Three Pillars

Every component belongs to one of three interlocking pillars that share exactly one database backbone:[^1]

```
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│    SENTINEL     │   │     NEXUS       │   │     ORACLE      │
│  Live 3D Globe  │   │  Intelligence   │   │  Command        │
│  Geospatial     │   │  Pipeline       │   │  Interface      │
│  Tactical Map   │   │  AI Agents      │   │  Natural Lang   │
│                 │   │                 │   │  Daily Briefs   │
│  Aircraft       │   │  OSINT          │   │  Alerts         │
│  Satellites     │   │  GEOINT         │   │  Reports        │
│  Earthquakes    │   │  SIGINT         │   │  Mobile Access  │
│  Vessels        │   │  Analysis       │   │                 │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                    │                      │
         └────────────────────┴──────────────────────┘
                      ONE SHARED DATABASE
```

A geo-tagged OSINT event collected by NEXUS automatically becomes a marker on SENTINEL. A flight anomaly flagged on SENTINEL automatically triggers an analysis report in NEXUS, delivered via ORACLE. The three pillars are inseparable because they share one memory.[^1]

***

## Part 3: The Three Command Agents

These are not collection agents — they are the **command and control layer** that routes tasks, builds the system, and interfaces with you:[^1]


| Agent | Role | Never Does |
| :-- | :-- | :-- |
| **OpenClaw** | Human interface — 24/7 comms, cron alerts, task routing | Deep analysis, code execution |
| **Claude (MCP)** | Cognitive core — analysis, correlation, NL queries, directing | System ops, file writes |
| **Cortex** | Engineering core — code, DevOps, infra, debugging | Intelligence analysis |

**OpenClaw** is your front door. You message it from Telegram at 3am. It delivers your morning brief. It routes your task to Claude or Cortex depending on what you asked. It never touches your API keys — those live in n8n's encrypted credential store, and OpenClaw only calls webhook URLs.[^1]

**Claude via MCP** is the brain. Four lightweight MCP servers connect Claude directly to your PostgreSQL database, your Redis live feeds, your SENTINEL globe, and your agent dispatch system. Plain English becomes parameterized SQL. "Any aircraft acting weird near Taiwan?" becomes a PostGIS + TimescaleDB join query that returns actionable intelligence.[^1]

**Cortex** is the hands. It builds new collector agents from Claude's specifications, debugs failing microservices, deploys containers, and runs database migrations. After every task, it writes a `SYSTEM` UIR to PostgreSQL so Claude knows exactly what changed in the infrastructure.[^1]

They never call each other directly. They communicate through two shared channels: webhooks for task dispatch, and the shared PostgreSQL database as the true shared memory.[^1]

***

## Part 4: The Intelligence Collection Agents

These are the senses of the system — specialized agents that watch the world continuously and write everything they find into the database:[^1]

### OSINT Collector (Python / CrewAI)

Scrapes news APIs, RSS feeds, social media, Telegram channels, forums, and public records.

- Every 15 minutes: topic monitoring
- Every 6 hours: deep domain crawl
- Tools: Firecrawl, Jina.ai, SerpAPI, Playwright, Nitter, Reddit API, Feedly
- Output: UIRs tagged `OSINT` with entity extraction and embeddings


### GEOINT Agent (Python asyncio)

Manages all positional data. The only agent that writes to Layer 1.

- Every 5 seconds: OpenSky → flight positions → `flight_tracks`
- Every 30 seconds: CelesTrak TLE + SGP4 propagation → `satellite_positions`
- Every 30 seconds: MarineTraffic AIS → `vessel_positions`
- Every 60 seconds: USGS GeoJSON → `seismic_events`
- Also writes Layer 2 UIRs for significant events only (transponder off, M5+ earthquake, unusual satellite maneuver)


### SIGINT Monitor (Go, event-driven)

The tripwire. Not scheduled — fires on detection.

- Always watching: Twitter/X filtered streams, Shodan webhooks, keyword RSS, DNS monitors, dark web crawlers
- On keyword match: immediately writes `SIGINT` UIR, publishes to Redis `alerts.live` stream
- OpenClaw receives the alert and notifies you on Telegram within seconds


### TECHINT Agent (Python)

The infrastructure mapper.

- Daily: Shodan/Censys scans on monitored IP ranges and domains
- Immediate on SIGINT trigger for same entity
- Tools: Shodan, Censys, SecurityTrails, DNSDumpster, DeHashed, VirusTotal
- Output: `TECHINT` UIRs with infrastructure maps and entity relationships


### All-Source Analyst Agent (LangGraph / Claude API)

The cognitive core of NEXUS. Wakes on every new UIR via the analysis queue.

- Runs semantic search (pgvector) — finds related records by meaning
- Runs spatial query (PostGIS) — finds correlated records by geography
- Runs temporal correlation (TimescaleDB) — finds related events by time window
- Runs DBSCAN clustering — groups correlated UIRs into a pattern
- Produces DERIVED UIRs, creates/updates clusters, updates entity profiles


### Report Writer Agent (Claude API / AutoGen)

The communicator. Cron-triggered.

- 0700 daily: Morning Brief → Telegram
- Sunday night: Weekly Intelligence Summary
- On-demand: SITREPs, domain reports, entity profile deep dives, alert digests


### Counterintel Validator (Python, always-on)

The gatekeeper. Invisible but critical.

- Intercepts every scraped payload before any LLM call
- Scans for prompt injection in raw HTML
- Scores source credibility
- Cross-references claims against existing UIRs
- Validates DERIVED UIRs before they become alerts


### Memory Librarian (Python, cron)

The janitor. Runs nightly.

- Finds near-duplicate UIRs via cosine similarity
- Enforces TTL on expired records
- Rebuilds pgvector indexes
- Repairs dangling linked_uids
- Syncs Cortex's ChromaDB engineering knowledge → pgvector

***

## Part 5: How Agents Work Together — The Communication Rules

**Rule 1: Agents never call each other directly.**

All inter-agent communication flows through two channels:[^1]

1. **Redis Streams** — notification bus carrying only UIR UIDs
2. **Shared PostgreSQL** — the payload, the truth, the actual data

Every stream message carries only `{uid: "abc-123"}`. Downstream agents fetch the full record from PostgreSQL by UID. The stream is the notification. The database is the truth.[^1]

```
Redis Streams topology:
  intelligence.osint    ← OSINT Collector writes
  intelligence.geoint   ← GEOINT Agent writes
  intelligence.sigint   ← SIGINT Monitor writes
  intelligence.techint  ← TECHINT Agent writes
  intelligence.derived  ← Analyst Agent writes
  system.tasks          ← Director Agent writes task assignments
  system.health         ← All agents write heartbeats
  alerts.live           ← High-priority alerts, OpenClaw subscribes
  globe.events          ← SENTINEL frontend subscribes
```

**Rule 2: PostgreSQL is truth. Redis is cache only.**

Redis handles pub/sub and hot cache. It never stores primary data. If Redis goes down, no data is lost. PostgreSQL holds everything permanently.[^1]

***

## Part 6: The Database — Six-Layer Architecture

The entire system rests on a **single PostgreSQL 16 instance** with five extensions:[^2]


| Extension | Role | Key Capability |
| :-- | :-- | :-- |
| **PostGIS** | Spatial intelligence | "All events within 500km of Taiwan" |
| **pgvector** | Semantic memory | "Find records similar in meaning to this" |
| **pgvectorscale** | Production ANN search | 28x lower latency than Pinecone at 50M vectors |
| **TimescaleDB** | Time-series telemetry | Auto-partitioning, 10:1 compression |
| **Apache AGE** | Knowledge graph | Cypher queries over entity relationship graph |

The database is organized into six ascending layers of abstraction, each answering a different question:[^2]

```
LAYER 6 — CONTINUOUS AGGREGATES
  "What's the pre-computed summary?" → materialized views, auto-refresh
  Used by: SENTINEL globe heatmaps, ORACLE fast queries

LAYER 5 — KNOWLEDGE GRAPH
  "What do we know about X and who is connected to it?"
  Tables: entities, entity_relationships, entity_profile_history
  Used by: Analyst Agent, ORACLE entity queries, Apache AGE Cypher

LAYER 4 — STRATEGIC DIGESTS
  "What is the state of the world this week?"
  Table: intelligence_digests
  Used by: OpenClaw → Telegram delivery

LAYER 3 — INTELLIGENCE CLUSTERS
  "What connected patterns are developing?"
  Tables: intelligence_clusters, cluster_revisions
  Used by: SENTINEL globe anomaly highlighting, Report Writer

LAYER 2 — UNIVERSAL INTELLIGENCE RECORDS (UIR)
  "What exactly was collected?"
  Table: intelligence_records
  Written by: ALL agents + seed importer
  APPEND ONLY — never UPDATE, ever

LAYER 1 — RAW TELEMETRY
  "Where was X at exactly what time?"
  Tables: flight_tracks, satellite_positions, vessel_positions, seismic_events
  Written by: GEOINT Agent ONLY
  TimescaleDB hypertables, 1-year retention
```


***

## Part 7: The Universal Intelligence Record (UIR) — The Spine

Every piece of intelligence — regardless of which agent collected it, from what source, in what domain — is stored as a UIR. This is the universal contract all agents share. It is the single most important table in the system.[^2]

### What a UIR Contains

```
IDENTITY
  uid          → unique UUID, auto-generated
  created_at   → timestamp

PROVENANCE (mandatory — every record must be fully traceable)
  source_type      → OSINT / GEOINT / SIGINT / TECHINT / FININT /
                     HUMINT / DERIVED / SYSTEM
  source_agent     → "osint_collector_v1", "cortex", etc.
  source_url       → origin URL
  source_credibility → 0.0 to 1.0

ASSESSMENT
  confidence   → 0.0 to 1.0
  priority     → CRITICAL / HIGH / NORMAL / LOW
  verified     → false until Counterintel approves

CONTENT — Three Zoom Levels
  content_headline → 1 line: globe tooltips, alert tickers
  content_summary  → 2-3 sentences: Claude reads this
  content_raw      → full original text: audit trail

TAXONOMY
  entities[]   → extracted: ["Iran", "Strait of Hormuz", "IRGC"]
  tags[]       → ["maritime", "military", "sanctions"]
  domain       → MILITARY / MARITIME / AVIATION / CYBER / etc.

GEOSPATIAL — on EVERY record, even if just country centroid
  geo          → PostGIS point (WGS84)
  geo_precision → exact / city / region / country / global

SEMANTIC MEMORY
  embedding    → 1536-dimension vector (text-embedding-3-large)

RELATIONSHIPS
  linked_uids[]    → related UIRs
  supersedes_uid   → if this updates a previous record
  cluster_id       → parent cluster
  layer1_refs      → JSON pointer to raw telemetry rows
```


### Three Critical Design Rules

**Append-only** — No `UPDATE` ever. If new intelligence changes the picture, write a new UIR with `supersedes_uid` pointing to the old one. The old record is preserved for audit. The new record is current truth.[^2]

**Geo on everything** — Even a news article about Iran gets `geo = Iran centroid, precision = country`. This enables spatial joins between OSINT text and GEOINT flight tracks — the highest-value query in the system.[^2]

**Three content zoom levels** — One write serves three consumers: the globe reads `content_headline`, Claude reads `content_summary`, the audit trail reads `content_raw`.[^2]

***

## Part 8: The Heartbeat — How the System Reacts

The `analysis_queue` trigger is the single most important mechanism in Phase 2. It is what makes the system alive.[^2]

Every `INSERT` into `intelligence_records` automatically fires three things simultaneously:

```
UIR INSERT
    ↓
pg_trigger fires:

① → writes row to analysis_queue
    → Analyst Agent polls this, wakes immediately

② → pg_notify → Go gateway → Redis pub/sub
    → SENTINEL globe: new geo marker appears
    → OpenClaw: checks priority, fires Telegram alert if HIGH/CRITICAL

③ → analysis_queue job processed:
    → semantic search finds related UIRs by meaning
    → PostGIS finds correlated UIRs by geography
    → TimescaleDB finds related telemetry by time
    → DBSCAN groups them into a cluster
    → DERIVED UIR written
    → entity profiles updated
    → cluster_revision written if confidence changed
```

One INSERT. Three downstream reactions. The system never polls for new data. It reacts in real time.[^2]

***

## Part 9: The Knowledge Graph — Layer 5

Layer 5 is what transforms the system from a database into a **living intelligence web**.[^2]

### The Entity Node

Every named subject — person, organization, location, vessel, aircraft, domain, infrastructure — becomes an entity node with a living profile:

```
ENTITY: "Al Rashid Air Cargo"
─────────────────────────────────────
type:           ORGANIZATION
watch_status:   CRITICAL
threat_score:   0.87
confidence:     0.91
first_seen:     2026-01-14
last_seen:      2026-02-26
profile_version: 7  ← rewritten 7 times as evidence arrived

current_profile:
  "Al Rashid Air Cargo is a cargo airline operating in
   East Africa and the Middle East. Three independent
   intelligence streams confirm affiliation with IRGC
   logistics networks. US Treasury OFAC sanctioned
   January 2026..."

uir_refs:      [uid1, uid4, uid7, uid12, uid15...]
cluster_refs:  [cid2, cid5]
embedding:     [0.023, -0.41, ...]
```


### The Relationship Edge

Every connection between entities is an evidence-backed edge:[^2]

```
entity_a:         "Al Rashid Air Cargo"
relationship:     SANCTIONED_BY
entity_b:         "US Treasury OFAC"
confidence:       0.91
evidence_uids:    [uid7, uid12]  ← the UIRs that proved this
first_observed:   2026-01-14
still_valid:      true
```


### The Graph Structure

Apache AGE runs Cypher queries over the entity tables, enabling multi-hop traversal that SQL cannot do efficiently:[^2]

```
Iran ──CONTROLS──→ Strait of Hormuz
 │
 └──OPERATES──→ IRGC Navy ──AFFILIATED_WITH──→ Al Rashid Air Cargo
                                                       │
                                               SANCTIONED_BY
                                                       │
                                              US Treasury OFAC
```

"Find everything connected to Al Rashid within 3 hops" — one Cypher query, returns the entire network.[^2]

### Profile History

Every time an entity's understanding changes, the old version is preserved in `entity_profile_history`:[^2]

```
Feb 4:  watch_status = PASSIVE,   confidence = 0.40
Feb 11: watch_status = MONITORING, confidence = 0.61  ← new OSINT
Feb 19: watch_status = ACTIVE,    confidence = 0.78  ← SIGINT hit
Feb 25: watch_status = CRITICAL,  confidence = 0.91  ← OFAC confirmed
```

The trajectory of understanding is itself intelligence. A confidence jump from 0.40 → 0.91 overnight tells a completely different story than the same change over three weeks.[^2]

***

## Part 10: The Seeding Strategy — Starting From History

Before a single live record is collected, the system is pre-loaded with historical context.[^3]

### Two Types of Knowledge

**Type 1 — Historical Baseline** (seeded once, runs in background)
What the world was before your system started watching. Gives context to everything collected live.

**Type 2 — Live Intelligence** (collected continuously)
What the world is doing right now. Gains meaning because the historical baseline exists beneath it.[^3]

### What Gets Seeded and Where

```
GeoNames (11M place names) ──────────────→ Layer 5 (entities, LOCATION type)
OSMNames (21M places + bboxes) ──────────→ Layer 5 (entities, geo precision)
Wikidata5M (5M entities) ────────────────→ Layer 5 (entities table)
Wikidata (50M relationships) ────────────→ Layer 5 (entity_relationships)

CIA CREST (775K declassified docs) ──────→ Layer 2 (UIRs, source=OSINT)
ACLED (conflict events since 1997) ──────→ Layer 2 (UIRs, domain=MILITARY)
Gutenberg (75K books, chunked) ──────────→ Layer 2 (UIRs, historical context)
World Bank data ─────────────────────────→ Layer 2 (UIRs, domain=FINANCIAL)
SIPRI arms trade data ───────────────────→ Layer 2 (UIRs, domain=MILITARY)
Global Terrorism Database ───────────────→ Layer 2 (UIRs, domain=MILITARY)
```

**Layer 1 receives NO seed data.** Layer 1 is exclusively for live positional telemetry.[^2]

### The Bootstrapped World Model

After seeding, before live collection begins:[^3]

- **25 million** seeded UIRs
- **5 million** named entities
- **50 million** relationship edges
- Every country, capital, border, major port, strait, chokepoint with PostGIS coordinates
- 775,000 CIA declassified documents from 1947–1990s
- Every armed conflict globally since 1997 with GPS coordinates

On day one of live collection, when a vessel anomaly appears in the Persian Gulf, the system doesn't encounter the Persian Gulf as an unknown. It already knows the Strait of Hormuz is a critical chokepoint, that 20% of global oil transits through it, that there are 340 ACLED conflict events in the region since 1997, and that three entities in the Wikidata graph are flagged as operating in the corridor.[^3]

### Correct Seeding Sequence

Don't seed everything before going live. This is the failure mode that kills projects:[^3]

```
Week 1: GeoNames + OSMNames → geographic baseline (2 hours)
Week 2: Wikidata entities → entity baseline (6 hours)
Week 3: GO LIVE → first live collection begins

Background (ongoing while system runs):
  → CIA CREST (weeks, parallelized)
  → ACLED, GTD, World Bank (days)
  → Gutenberg (days to weeks)
```

80% of contextual value in 2 weeks. Live system running. Historical enrichment completing in the background.

***

## Part 11: The Complete Data Flow

From world event to your Telegram, end to end:[^1][^2]

```
1. GEOINT Agent detects flight anomaly near Taiwan Strait
   → anomaly_score = 0.91 written to flight_tracks (Layer 1)

2. GEOINT Agent writes UIR to intelligence_records (Layer 2)
   → source_type: GEOINT
   → content_headline: "SQ7721 transponder anomaly, Taiwan Strait"
   → geo: exact GPS coordinates
   → entities: ["SQ7721", "Taiwan Strait"]
   → priority: HIGH

3. pg_trigger fires automatically on INSERT:
   → analysis_queue row created (priority: HIGH)
   → pg_notify → Go gateway → Redis pub/sub

4. SENTINEL globe receives Redis event
   → red pulsing ring appears over Taiwan Strait in real time

5. OpenClaw receives Redis alert
   → priority is HIGH → sends Telegram to you: "Flight anomaly detected"

6. Analyst Agent wakes from analysis_queue:
   → semantic search: finds 2 OSINT articles about Taiwan military exercises
   → PostGIS: finds 2 more anomalous flights within 500km, last 72 hours
   → temporal correlation: satellite pass over same region 6 hours earlier
   → DBSCAN: clusters all 5 UIRs into one pattern
   → writes intelligence_cluster: "Taiwan Strait Military Activity"
     confidence: 0.84, status: ACTIVE, priority: HIGH
   → writes cluster_revision: first revision, confidence 0.0→0.84
   → updates entity profiles: Taiwan Strait, SQ7721
   → writes DERIVED UIR with correlation findings

7. Report Writer Agent (0700 cron):
   → reads active clusters from last 24 hours
   → includes "Taiwan Strait Military Activity" in Morning Brief
   → writes intelligence_digest
   → OpenClaw delivers formatted Markdown to your Telegram

8. You query ORACLE at 0710:
   "Tell me more about those Taiwan flights"
   → OpenClaw routes to Claude
   → Claude MCP queries cluster + linked UIRs + entity profiles + Layer 1 raw tracks
   → Returns full intelligence summary with confidence history

9. You task Cortex:
   "Build a dedicated Taiwan watcher that checks every 5 minutes"
   → OpenClaw dispatches to Cortex webhook
   → Cortex builds the agent, deploys to VPS
   → Cortex writes SYSTEM UIR: "Taiwan watcher deployed, commit a3f92b1"
   → Claude sees this UIR and knows the system has been updated
```


***

## Part 12: The Web of Nodes — The Final Result

After sustained operation, the result is not just a database. It is a **living, evidence-backed, spatially-anchored, temporally-aware map of the world**.[^3][^1][^2]

Every node has:

- A confidence-scored living profile, rewritten as new evidence arrives
- A full revision history showing exactly how understanding evolved
- Connections to dozens or hundreds of other entities via evidence-backed edges
- A real-world geographic anchor via PostGIS
- A semantic fingerprint enabling similarity search
- References to every UIR that ever mentioned it

Every cluster has:

- A confidence trajectory showing how certainty built or collapsed over time
- UIRs from multiple intelligence disciplines (OSINT + GEOINT + SIGINT fused)
- Connections to the entities involved
- A link to the digest that reported it

Every UIR has:

- Immutable original content preserved forever
- A pointer back to the raw telemetry that triggered it (if GEOINT)
- A pointer to the UIR it superseded (if an update)
- A cluster membership showing what pattern it contributed to

The SENTINEL globe is the spatial view of this web. Every marker is a node. Every arc between markers is an edge. The globe and the graph are the same data, two different perspectives.[^1]

***

## Part 13: The Three Design Rules

Everything in this system follows three inviolable rules:[^2]

**1. Never lose data.**
Append-only UIRs. Permanent retention on all analytical layers. Full revision history on every cluster and entity. Old records are never deleted — they are the audit trail.

**2. Always answer "where?" and "when?"**
PostGIS on every UIR, even at country precision. TimescaleDB on every telemetry stream. The spatial and temporal dimensions are what enable cross-domain correlation.

**3. Connect everything.**
`linked_uids` between UIRs. `cluster_id` linking UIRs to patterns. `entity_refs` linking entities to evidence. Graph edges carrying intelligence between nodes. The connections are what turn isolated facts into understanding.

***

## Part 14: The Core Insight

> *OpenClaw is your front door. Claude is the brain. Cortex is the hands. The database is the soul.*

The corpus that accumulates in this database over months and years — the UIRs, the entity profiles, the cluster histories, the relationship graph — is the irreplaceable asset.[^1]

The agents are replaceable. The globe is replaceable. The interfaces are replaceable.

**The intelligence corpus is not.**

Design it correctly from the first insert.[^2]

<div align="center">⁂</div>

[^1]: core_concept.md

[^2]: pia_system_design_v2.md

[^3]: knowledge_graph_bootstrap.md

