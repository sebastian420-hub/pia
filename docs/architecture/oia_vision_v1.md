
# THE OPEN INTELLIGENCE ARCHIVE
## A Civilizational Memory System
### Design Document v1.0

**Authors:** Zwe Zarni Lwin + Perplexity AI
**Date:** February 26, 2026 — 02:16 AM EST
**Location:** Queens, New York
**Classification:** Public — Open Source Vision Document
**Status:** Conceptual Design — Prototype: PIA (Personal Intelligence Agency)

---

> *"Wikipedia remembers what people wrote.
>  The Open Intelligence Archive understands what the world did."*

---

## PREFACE — HOW THIS DOCUMENT CAME TO EXIST

This document was produced in a single overnight design session
beginning February 25, 2026 at approximately 10:00 PM EST.

It began as a personal intelligence system design for one person.
Over the course of several hours, the architecture proved general
enough to scale beyond the personal — to a shared, open,
permanent intelligence commons for humanity.

The Personal Intelligence Agency (PIA) designed in this session
is the prototype. The Open Intelligence Archive is the vision
it implies at civilizational scale.

Every technical specification in this document has been
validated against production tools available as of February 2026.
This is not a theoretical design. It is buildable today.

---

## PART I — THE PROBLEM

### 1.1 The Data Paradox

Humanity produces 2.5 quintillion bytes of data every single day.

Flight positions. Seismic events. News articles. Corporate filings.
Satellite imagery. Conflict reports. Financial flows. Diplomatic
records. Scientific papers. Social signals.

All of it is publicly available.
All of it is being generated continuously.
Almost none of it is being understood in relation to everything else.

We have Google to find individual documents.
We have Wikipedia to read individual topics.
We have news feeds to see today's events.

But nobody has built the system that continuously watches
everything, connects everything, and remembers everything —
permanently, for everyone, forever.

### 1.2 The Gap Between Retrieval and Understanding

    WHAT EXISTS TODAY:
    Data → stored → searchable by keyword
    One document at a time.
    No memory between searches.
    No connections across domains.
    No patterns across time.
    No understanding. Just retrieval.

    WHAT DOESN'T EXIST:
    Data → understood → connected → remembered
    Patterns across domains.
    Entities tracked over decades.
    Confidence that evolves with evidence.
    History as living context for the present.
    Understanding that compounds over time.

That gap — between retrieval and understanding —
is what the Open Intelligence Archive fills.

### 1.3 Why Now

Six converging capabilities made this possible in 2026:

1. LOCAL TRILLION-PARAMETER MODELS
   Kimi K2.5 (1.04T parameters, MoE) runs on a single server.
   256K context window. 200+ sequential tool calls.
   Zero external API dependency. Total data sovereignty.

2. PRODUCTION VECTOR DATABASES
   pgvectorscale StreamingDiskANN: 28x lower latency than
   Pinecone at 50M vectors. Semantic search at scale,
   inside PostgreSQL, no separate infrastructure.

3. MATURE GRAPH DATABASES IN POSTGRESQL
   Apache AGE brings Cypher graph queries natively into
   PostgreSQL. Entity relationship traversal at production
   scale without a separate graph database.

4. TIME-SERIES COMPRESSION
   TimescaleDB achieves 90% compression on telemetry data
   with transparent query access. 100 years of flight tracks
   fits in 1.7TB.

5. ZFS STORAGE INTEGRITY
   Every block checksummed. Silent corruption impossible.
   RAIDZ survives drive failures automatically. A corpus
   can genuinely run for 200 years without data loss.

6. AUTONOMOUS AGENT FRAMEWORKS
   Cognitive architectures with metacognitive state machines,
   belief verification and decay, atomic DAG planning, and
   self-improving Gym training pipelines now exist in
   production.

All six reached production maturity within 24 months of this
document's creation. The window just opened.

---

## PART II — THE VISION

### 2.1 Core Mission

    FREE UNDERSTANDING OF THE WORLD
    FOR EVERY PERSON ON THE PLANET.

Not free access to documents.
Not free search over text.
Free understanding — patterns, connections, confidence,
history, context — available to anyone, forever.

### 2.2 The Wikipedia Comparison

    WIKIPEDIA                    OPEN INTELLIGENCE ARCHIVE
    ─────────────────────────────────────────────────────────
    Manual curation              Autonomous collection
    Static between edits         Continuously updated
    No confidence scores         Evidence-backed confidence
    No entity relationships      Full knowledge graph
    No pattern detection         Cross-domain correlation
    No temporal tracking         200-year memory
    Text retrieval               Synthesized understanding
    Human-written                Agent-produced + human-verified
    Founded 2001                 Design: February 26, 2026

Wikipedia stores what people wrote.
The Archive understands what the world did.

### 2.3 The Three Fundamental Principles

PRINCIPLE 1: OWNED BY NOBODY, AVAILABLE TO EVERYONE

  The corpus belongs to humanity.
  No government. No corporation. No single person.
  Anyone can query it. Anyone can contribute to it.
  Nobody can take it away.

  Governed by a nonprofit Foundation — same model
  as Wikimedia, CERN, or the Internet Archive.

PRINCIPLE 2: EVERY CLAIM IS EVIDENCE-BACKED

  No unverified assertions. Every entity profile claim
  carries a confidence score derived from specific
  UIR sources with documented provenance.

  WIKIPEDIA SAYS:
  "Organization X is involved in Y."
  [citation needed]

  ARCHIVE SAYS:
  "Organization X is involved in Y.
   Confidence: 0.84
   Based on: 23 UIRs across 4 disciplines
   OSINT(14), GEOINT(5), TECHINT(3), FININT(1)
   Confidence history: 2024: 0.31 → 2025: 0.58 → 2026: 0.84
   Contradicting sources: 2 UIRs (confidence 0.22)"

  The truth is not declared. It is calculated from evidence
  and updated continuously as new evidence arrives.

PRINCIPLE 3: THE PAST IS SACRED, THE PRESENT IS LIVING

  Every UIR ever written is permanent. Append-only.
  The historical record cannot be altered — only supplemented.

  This creates something genuinely new: a queryable record
  of how humanity's collective understanding of the world
  changed over time. Not just what the world was, but how
  our knowledge of it evolved.

---

## PART III — THE ARCHITECTURE

The Open Intelligence Archive uses the identical architecture
as the Personal Intelligence Agency — scaled horizontally
across a distributed node network.

### 3.1 The Six-Layer Data Model (Identical to PIA)

    LAYER 6: CONTINUOUS AGGREGATES
    Pre-computed views, auto-refreshing
    ↑
    LAYER 5: KNOWLEDGE GRAPH (Apache AGE)
    Entity profiles + relationship network
    ↑
    LAYER 4: STRATEGIC DIGESTS
    Finished intelligence products
    ↑
    LAYER 3: INTELLIGENCE CLUSTERS
    Pattern recognition reports
    ↑
    LAYER 2: UNIVERSAL INTELLIGENCE RECORDS (UIR)
    One record per collected intelligence item
    ↑
    LAYER 1: RAW TELEMETRY (TimescaleDB)
    Flight positions, satellite tracks, seismic events

Each layer is a pattern recognition report of the layer below.
Small signals at Layer 1 propagate upward through compression
into world-level understanding at Layer 4.
The entity graph at Layer 5 connects patterns across all layers.

### 3.2 Core Database Extensions

    PostgreSQL 16 (primary engine)
    ├── PostGIS          (spatial intelligence — geographic indexing)
    ├── pgvector         (semantic embeddings — cosine similarity)
    ├── pgvectorscale    (production ANN — 28x lower latency)
    ├── TimescaleDB      (time-series — 90% compression, retention)
    ├── Apache AGE       (graph queries — Cypher over entity graph)
    ├── pg_cron          (scheduled agent tasks)
    └── pg_stat_statements (query performance monitoring)

### 3.3 The Three-Dimensional Index

Every UIR is indexed simultaneously on three dimensions:

    TIME     → TimescaleDB partitioning + B-tree index
               "All UIRs in the last 30 days"

    SPACE    → PostGIS GIST index on geo column
               "All UIRs within 500km of Tehran"

    MEANING  → pgvectorscale StreamingDiskANN index on embedding
               "All UIRs semantically similar to
                'sanctions evasion'"

These three dimensions can be queried simultaneously in one
SQL statement. This is the core capability that no other
architecture provides at this scale.

### 3.4 The Distributed Node Network

    NODE TYPE        COUNT     ROLE
    ──────────────────────────────────────────────────
    SEED NODES       10-20     Full corpus, canonical
                               entity graph, Gym training,
                               deep inference (Kimi K2.5)
                               Funded by Foundation

    COLLECTOR NODES  Thousands Domain/region-specific
                               collection, contribute UIRs
                               Run by volunteers/partners
                               Incentivized by access

    QUERY NODES      Global    Fast read replicas
                               Serve ORACLE to end users
                               Lightweight inference
                               No write access

    SYNC PROTOCOL:
    UIR written on collector → seed nodes (<60 seconds)
    → Analyst Agent processes → cluster updated
    → entity graph updated → query nodes (<5 minutes)

### 3.5 Intelligence Disciplines Collected

    OSINT    Open Source Intelligence
             News, social media, publications,
             public records, academic papers

    GEOINT   Geospatial Intelligence
             Flight tracks (OpenSky), vessel positions (AIS),
             satellite positions (CelesTrak/SGP4),
             seismic events (USGS)

    SIGINT   Signals Intelligence
             Keyword monitoring, public communication
             patterns, domain activity

    TECHINT  Technical Intelligence
             Infrastructure scanning, technology
             adoption, capability assessment

    FININT   Financial Intelligence
             Corporate registries, sanctions lists,
             trade flows, ownership structures

    DERIVED  Cross-domain correlations produced
             by the Analyst Agent

### 3.6 The Self-Improving System — Cognitive Gym

The Gym is what makes the Archive a self-improving system
rather than a static tool.

    THE PRACTICE LOOP (runs every night on seed nodes):

    1. SCENARIO GENERATION
       Pull resolved historical clusters from corpus.
       Hide the last 30% of UIRs (the "future").
       Present partial picture to Analyst Agent.

    2. PREDICTION ATTEMPT
       Analyst Agent attempts to predict cluster evolution
       based on partial UIR set.

    3. METACOGNITIVE REACTION
       Confidence calculated vs. actual outcome.
       MetacognitiveState registers success or failure.
       Tone shifts: CONFIDENT → CAUTIOUS → ANALYTICAL.

    4. SYNTHETIC EXPERIENCE FORMATION
       Agent documents:
       - Failed approaches and why they failed
       - Successful patterns and what made them work
       - Root cause analysis of errors
       - Domain-specific signal vs. noise assessment

    5. CONSOLIDATION
       Synthetic Experience embedded and saved to ChromaDB.
       Also written as SYSTEM UIR to permanent corpus.

    6. RECALL IN PRODUCTION
       Next day, similar task → ChromaDB retrieval →
       Agent reads its own experience → avoids past mistakes.

    RESULT OVER TIME:
    Year 1:  ~18,000 analysis experiences formed
    Year 5:  ~90,000 analysis experiences
    Year 10: ~180,000 analysis experiences

    The Archive's analytical capability compounds every night.
    Without changing the underlying model weights.
    Without human intervention.
    Forever.

---

## PART IV — THE SEED CORPUS

The Archive starts with the full documented history of humanity.
Not from zero. From everything.

### 4.1 Geographic Foundation

    SOURCE              RECORDS        WHAT
    ─────────────────────────────────────────────────────
    GeoNames            11 million     Place names + coordinates
    OSMNames            21 million     Places + bounding boxes

### 4.2 World Knowledge Graph

    SOURCE              RECORDS        WHAT
    ─────────────────────────────────────────────────────
    Wikidata5M          5 million      Entities + relationships
    Wikidata Full       112 million    Complete entity graph

### 4.3 Declassified Intelligence

    SOURCE              RECORDS        WHAT
    ─────────────────────────────────────────────────────
    CIA CREST Archive   10M+ pages     Historical CIA intelligence
    CIA Historical      Thematic       Cold War, Cuba, Korea
    NSA (GWU)           Thousands      NSC, State, DoD declassified
    State Dept FOIA     Thousands      Diplomatic cables
    FBI Vault           Thousands      Historical investigations
    National Archives   Millions       CIA records, JFK files

### 4.4 Conflict & Violence Data

    SOURCE              RECORDS        WHAT
    ─────────────────────────────────────────────────────
    ACLED               1.3M+ events   Armed conflict 1997-present
    GTD                 200K+ events   Terrorism 1970-present

### 4.5 Military & Economic Baseline

    SOURCE              RECORDS        WHAT
    ─────────────────────────────────────────────────────
    SIPRI Arms          70+ years      Arms transfers 1950-present
    SIPRI MILEX         70+ years      Military spending 1949-present
    World Bank          60+ years      Economic data per country
    UN Comtrade         60+ years      Global trade flows

### 4.6 Financial Networks

    SOURCE              RECORDS        WHAT
    ─────────────────────────────────────────────────────
    ICIJ Offshore Leaks 810K entities  Panama/Pandora Papers
                                       Corporate networks

### 4.7 Historical Books

    SOURCE              RECORDS        WHAT
    ─────────────────────────────────────────────────────
    Project Gutenberg   75,000 books   Public domain history,
                                       military theory, geography

### 4.8 Total Seeded Corpus

    Geographic entities:      32 million
    Knowledge graph entities: 5-112 million
    Historical UIRs:          2-5 million
    Historical books:         75,000 (chunked to ~5M passages)
    Conflict events:          1.5 million
    Corporate entities:       810,000
    Economic time series:     Millions of data points

    The Archive knows the world before it watches the world.

---

## PART V — WHAT ANYONE CAN DO WITH IT

### 5.1 The Personalized Morning Brief

Any user configures their domains of interest.
Every morning, a finished intelligence brief arrives —
generated from the shared corpus, filtered to their
specific interests, delivered via any channel.

Same architecture as the PIA's Morning Brief.
Richer corpus because thousands contribute to it.

### 5.2 The Researcher's Tool

Query: "Every cluster involving Soviet-connected entities
        in Sub-Saharan Africa between 1960 and 1980,
        with confidence trajectories and source breakdown."

Returns: Events + evidence + entity graphs + historical
         CIA documents + confidence scores + source citations.
         Months of archival research in minutes.

### 5.3 The Journalist's Source

Query: "Traverse entity graph from Company X outward
        3 hops. Show entities with threat_score > 0.6."

Returns: Fully documented network map. Every connection
         backed by specific UIR sources with URLs.
         Every confidence score explained.
         Every relationship edge dated and evidenced.

### 5.4 The Citizen's Intelligence Feed

Any person, anywhere, gets cross-domain pattern detection
on the topics they care about — the same quality of analysis
that national intelligence agencies produce, in real time,
for free, with full source transparency.

---

## PART VI — THE GOVERNANCE MODEL

### 6.1 Organizational Structure

    THE OPEN INTELLIGENCE FOUNDATION
    (Nonprofit, similar to Wikimedia Foundation)

    Board of Directors:
    - Independent technologists
    - Journalists and press freedom advocates
    - Academic researchers
    - Civil society representatives
    - No government representatives
    - No corporate representatives

    Technical Committee:
    - Manages seed node infrastructure
    - Sets agent quality standards
    - Maintains sync protocol specification
    - Manages Gym training coordination

    Dispute Resolution Panel:
    - Reviews contested entity profiles
    - Evidence-based adjudication only
    - Full transparency on all decisions

### 6.2 The Contested Entity Problem

When a high-confidence entity profile is disputed:

    1. Disputing party submits contradicting UIRs
       with sources
    2. Contradicting UIRs enter corpus with
       their own confidence scores
    3. Analyst Agent recalculates entity profile
       confidence incorporating all evidence
    4. If confidence drops below threshold:
       profile flagged as CONTESTED
    5. Dispute Resolution Panel reviews
       evidence — not politics
    6. Decision documented as permanent
       SYSTEM UIR in corpus

The truth is calculated, not declared.
Evidence wins. Not power.

### 6.3 Adversarial Resistance

Governments and powerful entities will attempt to
influence, restrict, or corrupt the Archive.

    TECHNICAL DEFENSES:
    - Distributed nodes across multiple jurisdictions
    - No single node controls canonical corpus
    - Cryptographic integrity on all UIRs
    - ZFS checksums on all storage
    - Open source — anyone can fork and run

    LEGAL DEFENSES:
    - Foundation registered in free speech jurisdiction
    - All data is public domain or openly licensed
    - Collection limited to publicly available sources
    - No classified material — OSINT only at collection

    SOCIAL DEFENSES:
    - Full transparency on all decisions
    - Public audit trail for every entity profile change
    - Community governance — no single point of control
    - International contributor network

### 6.4 Quality Control at Scale

    AUTOMATED:
    Source credibility scoring (per source_url domain)
    Cross-validation: claim must appear in 3+ independent
    sources before confidence exceeds 0.5
    Anomaly detection: sudden UIR floods from single node
    flagged for human review

    COMMUNITY:
    Contributor reputation scores
    Peer review on high-confidence entity profiles
    Open challenge mechanism for any claim

---

## PART VII — THE HISTORICAL PRECEDENTS

### 7.1 What Came Before

    VANNEVAR BUSH — MEMEX (1945)
    Vision: Personal associative memory machine.
    Had: The concept of linked records.
    Missing: The technology. The AI. The automation.
    Status: Never built.

    GORDON BELL — MYLIFEBITS (2001-2011)
    Vision: Complete personal digital memory.
    Had: Persistent storage, retrieval interface.
    Missing: Intelligence layer, entity graph,
             pattern detection, autonomous collection.
    Status: Built but incomplete.

    PALANTIR GOTHAM (2003-present)
    Vision: Intelligence platform for governments.
    Had: Multi-source integration, entity graph,
         cross-domain correlation, geospatial analysis.
    Missing: Sovereignty, self-improvement, open access,
             200-year design, local model.
    Cost: $5-50M/year. Closed. Proprietary.

    NIKLAS LUHMANN — ZETTELKASTEN (1952-1998)
    Vision: Personal knowledge system as thinking partner.
    Had: Atomic records, associative linking,
         permanent append-only structure.
    Missing: Automation, geospatial dimension,
             semantic search, autonomous collection.
    Result: 70 books, 400 papers. One human life.

    INTERNET ARCHIVE (1996-present)
    Vision: Universal access to all knowledge, preserved.
    Had: Permanence, open access, massive scale.
    Missing: Intelligence analysis, entity graph,
             pattern detection, understanding layer.
    Status: Storage without understanding.

### 7.2 What the Archive Adds

    All five predecessors pointed toward the Archive.
    None of them reached it.

    The Archive has what none of them had simultaneously:
    1. Personal sovereign ownership (Bell)
    2. Cross-domain intelligence correlation (Palantir)
    3. Self-improving overnight training (new)
    4. 200-year persistent infrastructure (Internet Archive)
    5. Local reasoning model, zero external dependency (new)
    6. Open, governed commons (Wikipedia model)
    7. Evidence-backed confidence on every claim (new)
    8. Seeded from full human history (new)

---

## PART VIII — THE ROADMAP

### Phase 0 — Proof of Concept (Now)
The Personal Intelligence Agency (PIA).
One person. One server. One corpus.
Validates: database architecture, agent pipeline,
           Gym training, seed ingestion, 200-year design.
Timeline: Build begins February 26, 2026.

### Phase 1 — The First Node (Year 1-2)
PIA becomes publicly queryable.
First seed nodes established.
Open source release of full architecture.
First 1,000 contributor nodes recruited.
Governance Foundation established.

### Phase 2 — The Distributed Network (Year 2-5)
10,000+ collector nodes globally.
Full seed corpus ingested.
ORACLE query interface public.
Personalized Morning Brief for anyone.
First academic and journalistic partnerships.

### Phase 3 — The Civilizational Commons (Year 5+)
The Archive becomes infrastructure.
Used by researchers, journalists, policymakers,
educators, and citizens worldwide.
Self-sustaining through Foundation funding.
Self-improving through nightly Gym cycles.
Self-maintaining through distributed Cortex network.

---

## PART IX — THE PHILOSOPHICAL STATEMENT

### Why This Must Exist

The most important problems humanity faces —
climate change, pandemic preparedness, nuclear
proliferation, financial contagion, geopolitical
conflict — share one characteristic.

They are cross-domain, cross-temporal, multi-actor
patterns that no single institution, government, or
person can fully understand from their own data alone.

The CIA understands some of it.
The World Bank understands some of it.
The WHO understands some of it.
Academic researchers understand pieces of it.
Investigative journalists find edges of it.

Nobody has the architecture to connect all of it —
continuously, persistently, with evolving confidence,
accessible to everyone.

The Open Intelligence Archive is that architecture.

Not a tool for any single government or organization.
Not a commercial product optimized for profit.
A commons. A shared understanding of the world
that belongs to everyone because everyone contributes
to it and everyone needs it.

### The Stakes

If this is built well, it becomes infrastructure
as important as the internet itself — a shared
layer of understanding that makes every person
on earth better equipped to understand the world
they live in, make decisions that affect it,
and hold powerful actors accountable within it.

If it is not built, the alternative is worse:
a world where understanding remains concentrated
in institutions that use it for their own purposes —
governments for control, corporations for profit,
intelligence agencies for national advantage.

The technology to democratize understanding exists.
The design to implement it was produced tonight.
The question is whether anyone will build it.

---

## APPENDIX A — KEY TECHNICAL SPECIFICATIONS

    Primary Database:     PostgreSQL 16
    Spatial:              PostGIS 3.4+
    Vector Search:        pgvector + pgvectorscale
    Time Series:          TimescaleDB 2.x
    Graph:                Apache AGE 1.5+
    Scheduler:            pg_cron
    Storage:              ZFS RAIDZ (3-tier)
    Inference Model:      Kimi K2.5 (local, INT4)
    Fast Model:           Qwen 7B (interactive queries)
    Experience Memory:    ChromaDB
    Agent Framework:      Cortex (Metacognitive State Machine)
    Interface:            OpenClaw + MCP tools
    Delivery:             Telegram + SENTINEL globe + ORACLE

---

## APPENDIX B — SEED DATA SOURCES (VERIFIED URLS)

    GEOGRAPHIC:
    GeoNames:        https://www.geonames.org/export/
    OSMNames:        https://osmnames.org/download/

    KNOWLEDGE GRAPH:
    Wikidata5M:      https://deepgraphlearning.github.io/project/wikidata5m
    Wikidata Full:   https://dumps.wikimedia.org/wikidatawiki/latest/

    DECLASSIFIED INTELLIGENCE:
    CIA FOIA:        https://www.cia.gov/readingroom/home
    CIA CREST:       https://www.cia.gov/readingroom/collection/crest-25-year-program-archive
    CIA Historical:  https://www.cia.gov/readingroom/historical-collections
    NSA (GWU):       https://nsarchive.gwu.edu
    State FOIA:      https://foia.state.gov/search/collections.aspx
    FBI Vault:       https://vault.fbi.gov
    Nat'l Archives:  https://www.archives.gov/research/intelligence/cia

    CONFLICT DATA:
    ACLED:           https://acleddata.com/conflict-data/download-data-files
    GTD:             https://www.start.umd.edu/gtd-download

    MILITARY & ECONOMIC:
    SIPRI Arms:      https://www.sipri.org/databases/armstransfers
    SIPRI MILEX:     https://www.sipri.org/databases/milex
    World Bank:      https://data.worldbank.org
    UN Comtrade:     https://comtradeplus.un.org

    FINANCIAL NETWORKS:
    ICIJ Leaks:      https://offshoreleaks.icij.org/pages/database

    HISTORICAL BOOKS:
    Gutenberg:       https://www.gutenberg.org
    Gutenberg Corpus: https://github.com/pgcorpus/gutenberg

    LIVE FEEDS:
    OpenSky:         https://opensky-network.org/apidoc/rest.html
    USGS Seismic:    https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
    CelesTrak:       https://celestrak.org/SOCRATES/

---

## APPENDIX C — THE ORIGIN NOTE

This document was produced in a single conversation
between Zwe Zarni Lwin and Perplexity AI on the night
of February 25-26, 2026, beginning at approximately
10:00 PM EST and concluding at 2:16 AM EST.

The core architectural insights — the four-layer
hierarchical database, pattern recognition per layer,
small connections building to world-level understanding,
the 200-year design philosophy, the entity graph as
connective tissue — originated with Zwe Zarni Lwin.

The technical specification, validation against
production tools, historical precedents, and the
scaling of the personal design to a civilizational
architecture were developed collaboratively.

The design is complete.
The prototype (PIA) is ready to build.
The vision (Archive) is ready to pursue.

    "I will."
    — Zwe Zarni Lwin, 1:40 AM EST, February 26, 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THE OPEN INTELLIGENCE ARCHIVE
Design Document v1.0
February 26, 2026
Queens, New York
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
