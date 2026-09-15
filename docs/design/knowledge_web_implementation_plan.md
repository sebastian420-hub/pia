# Knowledge Web — Implementation Plan

**Status:** K0–K3 + K5 (backend) BUILT 2026-09-15 on a wiped database (schema v2, AGE removed). Backbone loading in progress. K4 (GDELT), K6–K8 (UI, assistant tools) pending.
**Deviations:** schema v2 written directly instead of migrations 010–016 (no data to preserve); P31→kind classification walks `subclass of` through the entity API instead of SPARQL (SPARQL timed out); a cross-process Wikidata rate limit (advisory lock + `rate_limits` table) was needed once three analysts, the maintenance agent and the seed script ran together.
**Follows from:** [`knowledge_web_research.md`](knowledge_web_research.md) (why the current graph fails)
and the 2026-09-15 decisions:

| # | Decision | Taken |
|---|----------|-------|
| 1 | Identity backbone = **Wikidata Q-ids** | yes |
| 2 | **Globe first**; the web is the backend knowledge graph + the investigation view | yes |
| 3 | ~**20 event types** (CAMEO-style) replace the 45 stance verbs | yes |
| 4 | **Drop Apache AGE**; PostgreSQL is the single store | yes |
| 5 | **Fetch full article bodies** + add **GDELT** as a second event source | yes |
| 6 | Reasoning: **Level 1 now** (computed, dated relations and trends), Level 2 next (assistant with graph tools), Level 3 later | yes |

## 0. Evidence gathered for this plan (2026-09-15)

```
Wikidata search API   wbsearchentities "United States" → Q30 (country…), "Houthis" → Q3042087   ✔ works from here
Wikidata entity JSON  Q30: P31 types, P625 coords, 6 English aliases, P35 head of state, 56× P463  ✔
Wikidata SPARQL       count sovereign states → 202                                                ✔ (backbone preload feasible)
GDELT 2.0             lastupdate.txt → 20260915114500.export.CSV.zip, 87 KB, 1,424 events/15 min,
                      each with CAMEO code, Goldstein score, lat/lon, source URL                  ✔
trafilatura 2.2.0     article body extraction, on PyPI                                           ✔
Current DB            0/208 news articles have a body; LLM sees 124 chars avg; 0 entities with Q-id;
                      AGE holds 8 vertices vs 122 entities in tables                             (research doc)
```

Design consequence: **do not load a Wikidata dump** (100+ GB). Preload a small backbone with SPARQL
(~50k items: countries, capitals, governments, heads of state/government, ministers, armed groups,
international organisations, largest companies, navies' named vessels) and **resolve everything else
on demand** through the search API with a local cache. Wikidata asks for ≤ ~1 request/s per client
with a descriptive User-Agent; caching makes that trivial after the first day.

---

## 1. Data model (migrations 010–016)

### 1.1 Entities become identities

```sql
-- 010_entities_identity.sql
ALTER TABLE entities
  ADD COLUMN qid              TEXT,                              -- 'Q30'; NULL for PIA-local entities
  ADD COLUMN kind             TEXT NOT NULL DEFAULT 'UNKNOWN'    -- PERSON | ORG | COUNTRY | PLACE | VESSEL | AIRCRAFT | EVENT | UNKNOWN
        CHECK (kind IN ('PERSON','ORG','COUNTRY','PLACE','VESSEL','AIRCRAFT','EVENT','UNKNOWN')),
  ADD COLUMN resolution       TEXT NOT NULL DEFAULT 'LOCAL'      -- RESOLVED (has qid) | LOCAL | NEEDS_REVIEW | REJECTED
        CHECK (resolution IN ('RESOLVED','LOCAL','NEEDS_REVIEW','REJECTED')),
  ADD COLUMN wikidata_synced_at TIMESTAMPTZ,
  ADD COLUMN country_qid      TEXT;                              -- P17, for context scoring
CREATE UNIQUE INDEX entities_qid_uq ON entities(qid) WHERE qid IS NOT NULL;

CREATE TABLE entity_aliases (
    entity_id UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    alias     TEXT NOT NULL,
    alias_norm TEXT NOT NULL,          -- lower(unaccent(alias)), articles stripped
    lang      TEXT DEFAULT 'en',
    source    TEXT NOT NULL,           -- 'wikidata' | 'llm' | 'human'
    PRIMARY KEY (entity_id, alias_norm)
);
CREATE INDEX idx_alias_norm ON entity_aliases USING gin (alias_norm gin_trgm_ops);   -- pg_trgm
CREATE TABLE resolution_cache (        -- what the search API answered for a name, with TTL
    query_norm TEXT PRIMARY KEY, candidates JSONB NOT NULL, fetched_at TIMESTAMPTZ NOT NULL
);
```

The existing `entity_type` column stays for one release (views map it to `kind`), then goes.
`LOCATION` rows from GeoNames get `kind = 'PLACE'`; the 122 news-made entities are re-resolved by
the new resolver (most will get a Q-id; the generic nouns become `REJECTED`).

### 1.2 Sources, mentions, events, relations

```sql
-- 011_sources.sql        one row per outlet; trust is per outlet, not "RSS News Feed"
CREATE TABLE sources (
    source_id   TEXT PRIMARY KEY,      -- domain: 'bbc.co.uk', 'aljazeera.com', 'gdelt'
    label       TEXT NOT NULL,
    kind        TEXT NOT NULL,         -- NEWS | AGENCY | GOVERNMENT | SENSOR | DATASET | HUMAN
    trust       FLOAT NOT NULL DEFAULT 0.5 CHECK (trust BETWEEN 0 AND 1),
    country_qid TEXT, language TEXT, notes TEXT
);
ALTER TABLE intelligence_records ADD COLUMN source_id TEXT REFERENCES sources(source_id),
                                 ADD COLUMN published_at TIMESTAMPTZ,
                                 ADD COLUMN body_fetched_at TIMESTAMPTZ, ADD COLUMN body_status TEXT;

-- 012_mentions.sql       which entity appears in which report, in which role
CREATE TABLE mentions (
    report_uid  UUID NOT NULL REFERENCES intelligence_records(uid) ON DELETE CASCADE,
    entity_id   UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    surface     TEXT,                  -- the string as written ('the US', 'Beijing')
    role        TEXT,                  -- ACTOR | TARGET | LOCATION | MENTIONED
    confidence  FLOAT,
    PRIMARY KEY (report_uid, entity_id, COALESCE(role,''))
);

-- 013_events.sql         the thing that actually happened (hypertable on event_time)
CREATE TABLE events (
    event_id     UUID NOT NULL DEFAULT gen_random_uuid(),
    event_time   TIMESTAMPTZ NOT NULL,
    time_precision TEXT NOT NULL DEFAULT 'day',     -- minute | hour | day | month
    action       TEXT NOT NULL,                     -- see ontology below
    actor_id     UUID REFERENCES entities(entity_id),
    target_id    UUID REFERENCES entities(entity_id),
    location_id  UUID REFERENCES entities(entity_id),
    geo          GEOMETRY(Point, 4326),
    report_uid   UUID REFERENCES intelligence_records(uid) ON DELETE SET NULL,
    source_id    TEXT REFERENCES sources(source_id),
    origin       TEXT NOT NULL,                     -- 'llm' | 'gdelt' | 'human'
    quote        TEXT,                              -- the sentence this came from
    confidence   FLOAT NOT NULL,
    tone         FLOAT,                             -- GDELT Goldstein / LLM sentiment, -10..10
    external_id  TEXT,                              -- GDELT GlobalEventID
    dedup_key    TEXT NOT NULL,                     -- hash(actor,target,action,day,source)
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_time, event_id)
);
SELECT create_hypertable('events', 'event_time');
CREATE UNIQUE INDEX events_dedup ON events(dedup_key, event_time);
CREATE INDEX idx_events_actor ON events(actor_id, event_time DESC);
CREATE INDEX idx_events_target ON events(target_id, event_time DESC);
CREATE INDEX idx_events_geo ON events USING GIST(geo) WHERE geo IS NOT NULL;

-- 014_relations.sql      computed summaries; never written by the LLM
CREATE TABLE relations (
    a_id        UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    b_id        UUID NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,         -- HOSTILE | COOPERATIVE | ROLE | OWNERSHIP | MEMBERSHIP | LOCATED | MENTIONED_WITH
    source      TEXT NOT NULL,         -- 'events' | 'wikidata' | 'cooccurrence'
    property    TEXT,                  -- Wikidata P-id when source = 'wikidata'
    first_seen  TIMESTAMPTZ, last_seen TIMESTAMPTZ,
    event_count INTEGER NOT NULL DEFAULT 0,
    weight      FLOAT NOT NULL DEFAULT 0,          -- decayed: Σ exp(-age_days/90) over events
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (a_id, b_id, kind, source)
);
CREATE INDEX idx_relations_b ON relations(b_id);
CREATE INDEX idx_relations_weight ON relations(weight DESC);

-- 015_deprecate_old_graph.sql
ALTER TABLE entity_relationships RENAME TO entity_relationships_legacy;   -- read-only, dropped in a later release
DROP EXTENSION IF EXISTS age CASCADE;

-- 016_ai_feedback_events.sql   feedback targets an event (a claim), not a relation
ALTER TABLE ai_feedback ADD COLUMN event_id UUID;
```

### 1.3 Event ontology (20 actions)

Modelled on CAMEO root codes, which GDELT already uses, so GDELT events map 1:1 without an LLM.

| Cooperative | Conflictual | Structural / other |
|-------------|-------------|--------------------|
| STATEMENT (01), APPEAL (02), COOPERATE (03/04), AID (07), AGREE (05/06), MEET (04) | ACCUSE (11), REJECT (12), THREATEN (13), PROTEST (14), SANCTION (16), COERCE (17), ATTACK (18/19/20), ARREST (17) | APPOINT, RESIGN, ELECT, ACQUIRE, INVEST, DEPLOY, VISIT, DISASTER, OTHER |

Relation `kind` derivation: ATTACK/THREATEN/SANCTION/COERCE/ACCUSE/ARREST → `HOSTILE`;
COOPERATE/AID/AGREE/MEET/VISIT → `COOPERATIVE`; APPOINT/RESIGN/ELECT → `ROLE`; ACQUIRE/INVEST →
`OWNERSHIP`. Static Wikidata facts: P39/P169/P488 → `ROLE`, P127/P749/P355 → `OWNERSHIP`,
P463/P361 → `MEMBERSHIP`, P17/P131/P159 → `LOCATED`.

---

## 2. Components

### 2.1 Resolver (`src/pia/kg/resolver.py`) — the heart of "connecting correctly"

```
resolve(surface, kind_hint, context) -> Entity | None
  1. normalise: lower, unaccent, strip 'the ', possessives ("Iran's president" → hint ROLE-OF Iran)
  2. reject generic nouns: lowercase single common word, or in stoplist (king, minister, prosecutors, pipeline, forces…)
  3. local alias hit (entity_aliases, exact norm → else trigram ≥ 0.9) with compatible kind → RESOLVED
  4. else resolution_cache / Wikidata wbsearchentities (limit 5) → candidates with description + P31
     4a. one candidate of compatible kind → fetch entity (wbgetentities, batched), store, RESOLVED
     4b. several → context score: same country as article (P17), co-mentioned entities share links,
         label exact match, sitelinks count (popularity); if best − second ≥ margin → RESOLVED
     4c. still tied → LLM chooses from the candidate list (constrained: returns an index or "none")
  5. no candidate → LOCAL entity with resolution = NEEDS_REVIEW (shown in a review queue, not in the web)
  Government-of pattern: 'Washington', 'Beijing', 'the Kremlin', 'Tehran' as actors → the country
  Q-id with mention.role = 'GOVERNMENT'; the city is not the actor.
```

Wikidata fetch stores: label, description, aliases (en + article language), P31 → kind, P625 coords,
P17 country, sitelink count, and the static relations listed in 1.3 (into `relations`, source =
'wikidata'). One `wbgetentities` call fetches 50 ids; the enrichment agent refreshes items older
than 30 days.

### 2.2 Backbone preload (`scripts/seed_wikidata_backbone.py`, one-off + monthly)

SPARQL queries, each ≤ 10k rows, paged: sovereign states (202) and their capitals; heads of state /
government and foreign/defence ministers (P39 current holders); international organisations (P31
Q484652 and subclasses, sitelinks ≥ 20); armed forces and armed groups (Q17149090, Q61883); companies
with market cap or sitelinks ≥ 30; named warships and large merchant vessels (P31 Q11446 subclasses
with P8047/IMO). Target ≈ 50k entities + ≈ 300k static relations. Runs in ~1 hour with polite
pacing; result is cached in `data/wikidata_backbone.jsonl` so re-seeding a fresh DB is offline.

### 2.3 Article bodies (`news_agent.py` + `src/pia/ingest/article.py`)

- On ingest: record `source_id` = outlet domain (from feed URL), `published_at` from `pubDate`.
- Body fetch (same agent, after insert): `robots.txt` check via `urllib.robotparser` (cached per
  domain), GET with a descriptive UA, 20 s timeout, `trafilatura.extract()` → `content_raw`
  (cap 12k chars), `body_status` = OK | ROBOTS_DENIED | PAYWALL | ERROR. Denied/paywalled articles
  are still analysed from the blurb, marked low confidence.
- Only *then* is the analysis job queued (trigger changes: queue on body fetch completion, not on
  insert; migration adjusts the trigger to fire on `body_status IS NOT NULL`).

### 2.4 Event extraction (`analyst_agent.py` → `src/pia/kg/extractor.py`)

Prompt receives the full article and returns:

```json
{"summary": "...", "language": "en", "country_context": "Yemen",
 "mentions": [{"surface": "the Houthis", "kind": "ORG", "role": "ACTOR"}],
 "events": [{"actor": "the Houthis", "action": "ATTACK", "target": "MV Example", "location": "Red Sea",
             "date": "2026-09-14", "precision": "day", "quote": "…exact sentence…", "confidence": 0.85}]}
```

The analyst: resolve every mention → `mentions`; resolve actor/target/location → `events` (dedup
key: resolved ids + action + day + source); write `intelligence_records.entities` (names) for the
existing UI; geocode the report from `location` (P625) when the record has no `geo` — this is the
geocoding fix from the earlier discussion. `max_tokens` 2,000; model gpt-4o-mini (≈ $0.001/article
at 4k input chars; 500 articles/day ≈ $0.50/day).

### 2.5 GDELT ingester (`src/pia/agents/gdelt_agent.py`)

Every 15 min: read `lastupdate.txt`, download the export CSV (~90 KB, ~1,400 rows), keep rows with
`NumMentions ≥ 3` or `|Goldstein| ≥ 5` or inside an active mission's area, map CAMEO root code →
action, `Actor1Name`/`Actor2Name` + CAMEO country codes → resolver, `ActionGeo_Lat/Long` → geo,
`SOURCEURL` → a lightweight `intelligence_records` row (source_id = domain, no LLM), `GlobalEventID`
→ `external_id`. Expect ≈ 20–40k events/day; no LLM cost.

### 2.6 Relations job (`src/pia/kg/relations.py`, hourly + on demand)

```sql
INSERT INTO relations (a_id, b_id, kind, source, first_seen, last_seen, event_count, weight)
SELECT LEAST(actor_id,target_id), GREATEST(actor_id,target_id), kind_of(action), 'events',
       min(event_time), max(event_time), count(*),
       sum(confidence * exp(-EXTRACT(EPOCH FROM NOW()-event_time)/86400/90))
FROM events WHERE actor_id IS NOT NULL AND target_id IS NOT NULL
GROUP BY 1,2,3
ON CONFLICT (a_id,b_id,kind,source) DO UPDATE SET …;
```

Plus `MENTIONED_WITH` from co-mentions (same report, both resolved) with a low weight, and a
per-entity `trend` (events last 7 d vs previous 7 d) materialised for the entity page.
**This is Reasoning Level 1.**

### 2.7 API (`pia-api`)

| Endpoint | Purpose |
|----------|---------|
| `GET /entities/{id or Qxx}` | card: names, kind, description, coords, country, trend, top relations by kind, roles (Wikidata), counts |
| `GET /entities/{id}/events?from&to&action` | timeline |
| `GET /entities/{id}/neighbors?kinds&limit&depth=1..2` | web expansion, weight-sorted |
| `GET /relations/{a}/{b}` | the evidence: events with quotes and sources |
| `GET /events?from&to&bbox&action&min_confidence` | events on the globe |
| `GET /search/entities?q=` | alias search (trigram), falls back to Wikidata search |
| `GET /review/entities` · `POST /review/entities/{id}` | NEEDS_REVIEW queue: merge into Q-id / keep local / reject |
| `POST /feedback` | now takes `event_id` |
| `GET /graph/network/{name}` | kept for the current UI, backed by `relations` |

### 2.8 UI (globe first; web = investigation view)

- **Entity inspector** (right column, replaces the graph pop-up as the first stop): card from
  `/entities/{id}`, event timeline, connections grouped by kind with counts, "show on globe", "open web".
- **Events on the globe**: an *Events* layer (actions as small glyphs, colour by cooperative /
  conflictual), driven by the same time window as reports.
- **Web view** (`/web/:id`, also from the archive): 2-D Sigma.js graph, node size = mentions in the
  window, colour = kind, edge width = weight, edge click → evidence panel with quotes, time slider
  (7 d / 30 d / 90 d / all), expand one hop per click, search box jumps to a node.
- **Review queue** page: unresolved names with the article sentence and Wikidata candidates → one
  click to merge. (Cheap to build, hugely improves the web over time.)
- The "Relationships" 3-D overlay and its API path are removed once the web view ships.

---

## 3. Order of work

| Phase | Deliverable | Proves | Effort |
|-------|-------------|--------|--------|
| **K0** | Migrations 010–016; drop AGE from image/compose; `sources` seeded for the 4 outlets + gdelt + usgs | schema applies; old data still readable | 1 day |
| **K1** | Resolver + Wikidata client + cache; backbone preload script; re-resolve the 122 existing entities | `US`/`United States`/`Beijing (gov)` → Q30/Q148; generic nouns rejected; ≥ 80 % of existing entities get a Q-id (measured) | 4–5 days |
| **K2** | Article bodies (robots, trafilatura, outlet + published_at); trigger on body completion | avg text to LLM goes from 124 chars to > 2,000 (measured) | 2 days |
| **K3** | Event extractor + new analyst flow (mentions, events, geocode); 20-action ontology; feedback on events | one article → events with quotes; the "Dozens of aircraft" article yields ATTACK events | 4 days |
| **K4** | GDELT agent | ≥ 10k events/day with geo, no LLM cost | 2 days |
| **K5** | Relations job + trend; API endpoints in 2.7 | `/entities/Q30` returns dated, weighted relations | 3 days |
| **K6** | Entity inspector + Events layer on the globe + review queue | click Iran on the globe → card + timeline; reviewer merges 20 names in 5 minutes | 4 days |
| **K7** | 2-D web view with time slider and evidence panel; remove the 3-D overlay | "how are Iran and the Houthis connected" answered with quotes | 4 days |
| **K8** | Reasoning L2: assistant tools over the web (`entity_card`, `neighbors`, `evidence`, `events_near`) via MCP + the UI assistant | ask "who is linked to this ship?" → answer with sources | 3 days |

≈ **5–6 weeks**. K1–K3 are the ones that change everything; K6–K7 are what you see.

---

## 4. Risks and what is deliberately not done

- **Wikidata rate limits / outages**: mitigated by the backbone preload, the cache table, batching,
  and a "resolve later" queue; the pipeline never blocks on Wikidata.
- **Wrong merges** (the worst failure in a knowledge web): resolver only auto-merges with a clear
  margin; everything else goes to review; every merge is reversible (mentions/events point to ids,
  a split re-points them).
- **Article bodies**: some outlets deny robots or paywall; those articles stay blurb-only and
  low-confidence. GDELT covers events from thousands of other outlets anyway.
- **LLM cost** rises (bigger inputs): ≈ $0.50–1/day at current volume with gpt-4o-mini; GDELT events
  cost nothing.
- **Old graph**: the 102 legacy edges are not migrated (single-sentence, undated); the table is kept
  read-only for one release, then dropped.
- **Not in this plan**: Reasoning Level 3 (automatic pattern alerts), the timeline UI (separate
  phase 3 of the COP plan — the events layer here reuses it when it exists), multi-language
  extraction beyond what gpt-4o-mini handles, Wikidata edits back upstream.

## 5. Sign-off questions

1. K-order OK (identity and text quality before anything visible)?
2. Backbone scope (~50k items) — enough, or do you want a specific region/country loaded deeper first?
3. Review queue — will you actually use it? (If not, the resolver must be stricter and the web smaller.)
