# PIA — Concept, System Design, How It Works, and How to Step It Up

**Status:** WRITTEN 2026-09-19 from the live system (all numbers measured at ~05:30Z today).
**Follows from:** `PIA_STATE_AND_VISION.md` (2026-09-15) — that document is the history and the
decision log; this one is the *current* picture. Detail plans live in `design/`.
**Repos:** `pia` (agents + database), `pia-api` (HTTP/WebSocket), `pia-ui` (browser).
All three on branch `web-view-redesign` (pia `8f90df2`, pia-api `2e9e525`, pia-ui `2039a89`).

---

## 1. The concept in plain words

PIA is **an intelligence agency in a box, for one person.**

A real agency does four things: it *collects* (reads everything), it *remembers* (files, indexes,
cross-references), it *connects* (who is who, who did what to whom), and it *judges* (so what?).
PIA automates the first three, 24 hours a day, and leaves the fourth to you — with the evidence
laid out so you can do it fast.

The core idea, in one sentence: **"Wikidata that moves."** Wikidata already knows who is who —
every country, ministry, company, leader, ship, with a permanent ID. PIA adds what *happens* between
them, day by day, with the exact sentence that proves it. The result is one growing web of the
world: nodes are real identities, lines are dated, counted, sourced events.

What makes this different from "a dashboard with news on a map":

| Ordinary news tool | PIA |
|---|---|
| Headlines come and go | Every event is kept, dated, and linked to the people and places in it |
| "Trump" and "Trump administration" and "Washington" are three strings | All resolve to one identity (Wikidata Q-id), the way a person reads them |
| A claim is just text | A claim is an **event** with actor, action, target, place, time, source and the quote |
| Relationships are guessed once | Relationships are **computed** from events, so they grow, fade, and can be re-checked |
| You trust the AI | You trust the *quote*; the AI only extracts, never asserts on its own |

Three layers, always the same shape:

```
COLLECT     news · GDELT · aircraft · ships · earthquakes · cameras · documents   (agents)
UNDERSTAND  resolve names → identities · extract events with quotes · compute relations · review queue
PRESENT     globe (where) · feed (what, now) · entity card (who) · web (how connected) · evidence (why)
```

The presentation never changes. A **mission** (planned, not yet built) changes only what goes into
COLLECT and what UNDERSTAND pays attention to. That is why "the input is the whole game."

---

## 2. How it works — follow the data

### 2.1 One article, start to finish

1. **`news_agent`** polls 4 RSS feeds every few minutes (BBC World, Al Jazeera, NYT World, The Verge).
   For each new link it fetches the **full article body** (robots-aware, `trafilatura`), records the
   outlet and published time, and inserts one `intelligence_records` row (`source_agent =
   osint_news_v1`, `body_status = OK`). Measured: 207 of 276 news reports have a full body; the LLM
   sees ~4,000 characters instead of the 124-character RSS blurb it used to.
2. A database trigger puts the report in **`analysis_queue`** and notifies listeners.
3. One of **three `analyst_agent`s** claims the job and calls the LLM (`openai/gpt-4o-mini` through
   OpenRouter) with the event-extraction prompt: return 0–5 events, each `{actor, action, target,
   location, time, quote, confidence}`, and a list of names with kind hints. The `action` must be
   one of **23 CAMEO-style verbs** (`kg/ontology.py`: ATTACK, THREATEN, SANCTION, MEET, AGREE, AID,
   APPOINT, RESIGN, ACQUIRE, …).
4. Every name goes through the **resolver** (`kg/resolver.py`), in this order:
   generic-noun filter ("prosecutors", "the kingdom" → dropped) → government seats ("Beijing said" →
   China) → local alias table (477,546 aliases) → resolution cache → Wikidata search with
   abbreviation expansion → **scoring** (exact kind +2.5, UNKNOWN −4, COUNTRY +0.5, context) →
   LLM tie-break only if two candidates are close → otherwise **`NEEDS_REVIEW`**. Concepts
   ("artificial intelligence") never become entities.
5. The analyst writes **`mentions`** (entity ↔ report, with role and surface string) and
   **`events`** (with `quote`, `confidence`, `tone`, a `dedup_key`). If the location resolves, the
   report gets a position on the globe (93 % of reports are positioned today).
6. A **situation** (`intelligence_clusters`) is created only when two reports agree; one report
   never makes a situation.
7. Hourly, **`enrichment_agent`** (kg maintenance) rebuilds **`relations`** from events: pairs are
   grouped by kind (HOSTILE / COOPERATIVE / ROLE / OWNERSHIP), counted, weighted with a 90-day
   decay, and filtered by a noise bar (a pair seen only in GDELT needs ≥ 3 events or ≥ 2 outlets).
   Wikidata's static facts (member of, located in, owned by, position held) sit alongside with
   `source = wikidata` and never decay.
8. In the UI: the report is in the feed and on the globe; click a name → **entity card**
   ("27 accuse/attack/coerce events (aljazeera.com, gdelt) since 09/18"); open the **web** → the
   pair is a solid red line; click the line → **evidence**: the events, the quotes, the sources.

### 2.2 The other inputs

| Input | Agent | What it produces | Volume today |
|---|---|---|---|
| GDELT export (every 15 min) | `gdelt_agent` | coded, geocoded events with no LLM; names resolved *locally only* (strict country) | 1,031 reports, 1,948 events |
| ADS-B (OpenSky) | `aviation_agent` v2 (owner's) | every position into `flight_tracks`; a report per military aircraft per hour; HIGH for squawk 7500/7600/7700 | 383k positions/day, 224 reports/day |
| AIS (AISHub) | `maritime_agent` v2 (owner's) | `vessel_positions` | 0 rows (feed not delivering yet) |
| USGS earthquakes | `seismic_agent` | reports for M ≥ 4 | 206 events, 14 reports |
| City traffic cameras | `camera_agent` | `sensors` rows; snapshot / clip proxy; health probe | 3,371 cameras, 2,386 online, 6 providers |
| Uploaded documents | `document_agent` | report + analysis like an article | on demand |

### 2.3 The data model (the five tables that matter)

```
sources         one row per outlet or dataset, with a trust score               (509 rows)
entities        identity: qid, kind, resolution, origin                          (97,253)
entity_aliases  every name a thing is known by                                   (477,546)
mentions        entity ↔ report, with role and the exact surface string          (1,141)
events          actor · action · target · place · time · source · quote · tone   (2,073, hypertable)
relations       computed summaries: from events (decaying), Wikidata facts, co-mentions (97,586)
```
Plus: `intelligence_records` (the reports), `intelligence_clusters` (situations), `analysis_queue`,
`sensors` / `sensor_layers`, `flight_tracks`, `vessel_positions`, `seismic_events`,
`resolution_cache`, `wikidata_classes`, `ai_feedback`, `agent_heartbeats`, `live_sessions`,
`rate_limits`, `schema_migrations`, `mission_focus` (empty; too thin — see §6).

The rule that keeps the web honest: **the LLM never writes a relation.** It writes events with
quotes. Relations are arithmetic over events. If an event is wrong, you can see the quote and reject
it (`ai_feedback`), and the line recomputes.

---

## 3. System design

### 3.1 Components

```
┌───────────────────────────── docker compose (13 containers) ─────────────────────────────┐
│ postgres (timescaledb-ha: TimescaleDB · PostGIS · pgvector · pg_trgm · unaccent)  389 MB   │
│ pia_init  schema v2 + migrations + GeoNames cities                                         │
│ agents    news · analyst ×3 · enrichment · gdelt · camera · seismic · document · aviation · maritime │
│ pia-api   FastAPI + asyncpg, bearer token, 31 endpoints, WebSocket /ws/live                │
│ mcp_server  tools for an assistant (not wired to the web yet)                              │
└────────────────────────────────────────────────────────────────────────────────────────────┘
                                   ▲ HTTP / WS
pia-ui  React 19 · Vite · Tailwind v4 · Cesium (globe) · react-force-graph-2d (web)
        /  Dashboard (COP frame)   /archive  (table + web workspace)   /review  (identity queue)
```

Size: `pia` ≈ 4,000 lines of Python (9 agents, `kg/` 5 modules, `sensors/` 8 providers);
`pia-api` ≈ 1,500 lines; `pia-ui` ≈ 2,700 lines of TypeScript. 41 unit tests run without Docker.

### 3.2 Design choices and why

| Choice | Why |
|---|---|
| **One store, PostgreSQL** (Apache AGE removed) | AGE held 8 vertices and nothing read it. Postgres with PostGIS + TimescaleDB + pgvector does geo, time and embeddings in one place; k-hop queries are a recursive CTE. A graph engine can be mirrored *by id* later if needed. |
| **Wikidata Q-ids as identity** | The only free, global, maintained who-is-who. 62,954 items loaded as a backbone (countries, capitals, leaders, ministries, forces, parties, agencies, companies, warships, notable people) with aliases and coordinates, cached offline in `data/wikidata_backbone.jsonl`. |
| **Events, not relationships, as the unit** | A relationship asserted once lives forever and cannot be checked. An event has a date, a source and a quote. Relations are recomputed from events, so they can decay, be filtered and be explained. |
| **~20 action verbs (CAMEO-like)** | Enough to say hostile / cooperative / role / ownership; few enough that the LLM and GDELT agree on them. The old 45-verb list produced synonyms and nonsense. |
| **Resolver strict, review queue for the rest** | Better a name waits in review than a wrong node in the web. 161 names are waiting today; the web is right without anyone reviewing. |
| **GDELT as second source** | Independent, geocoded, coded, free, every 15 min. Noisy — hence local-only resolution and the noise bar. |
| **Full article bodies** | Extraction quality is bounded by input text. 124 characters gave garbage; 4,000 gives events. |
| **COP frame in the UI** | Fixed regions (status bar, layer rail, feed, globe/web, inspector, log); nothing overlaps; dark basemap; grey NORMAL; plain vocabulary. Same layout on a desk and a wall. |
| **Globe first, web for investigation** | The globe answers "where / now"; the web answers "who / how connected". The web replaces the globe cell, the inspector column stays. |
| **Snapshot-first cameras + relay for US** | Public city cams are still images or short clips; US providers only answer US IPs → an on-demand relay (built, not deployed). |

### 3.3 What is *not* in the design (on purpose)

- No alert acknowledge / assignment workflow (not wanted yet).
- No multi-user, no roles, no encryption at rest — one shared token. Fine for a personal tool; a
  hard stop before any human reporter is involved (§6.4).
- No automatic "meaning" — no anomaly detection, no summaries. Level-1 reasoning only (counts,
  trends, decay). Levels 2–3 are the next tier.

---

## 4. What we have today (measured 2026-09-19)

**Running:** all 13 containers up, all 11 agent heartbeats `OK`. Backbone reload finished:
62,954 Wikidata entities + 34,138 GeoNames cities.

**Data**
- Reports: 1,545 (1,363 in the last 24 h) — GDELT 1,031, news 276, aviation 224, seismic 14.
- Events: 2,073, every one with a quote. Top actors: United States 301, Russia 121, Saudi Arabia 98,
  Israel 98, Iran 97. Strongest observed pairs: US–Saudi cooperative 34, Russia–Ukraine hostile 30,
  Iran–US cooperative 26 (a signature of the current talks), Pakistan–Saudi cooperative 26.
- Relations: 97,586 — 97,090 Wikidata facts, 284 from events, 212 co-mentions.
- Entities mentioned in reports: 718. Review queue: 161.

**Verified in the browser** (`design/ui_research/`): globe with report/event/camera layers, dense
feed, camera inspector with snapshot/clip, entity card, web view (click → card, click line →
evidence, expand, focus, breadcrumb, filters, dashed facts), review page.

**Known problems right now** (see `design/graph_accuracy_implementation_plan.md` for the
2026-09-19 data-loss incident and its fix — the Postgres volume was mounted at the wrong path)
1. **LLM extraction has been down since 2026-09-18 04:52Z** — OpenRouter returns `402` (no credit).
   88 jobs FAILED, 146 articles unanalysed. The article half of the web is frozen; GDELT and sensors
   still flow. Retries resume by themselves once credit exists.
2. **Only 4 news feeds.** 501 outlets exist as `sources` rows (from GDELT), but PIA reads only
   BBC / Al Jazeera / NYT / Verge itself. The web reflects what four Western desks cover.
3. **Aviation floods the feed:** one HIGH report per military aircraft per hour → 224/day, all
   labelled "Military aircraft". Proposed: one report per aircraft per day, NORMAL unless squawk
   7500/7600/7700. `flight_tracks` grows 383k rows/day (fine for TimescaleDB; needs a retention
   policy).
4. **Maritime delivers nothing** (`vessel_positions` = 0) — the AISHub feed needs checking.
5. **Branches:** everything current is on `web-view-redesign`; `pia-api/main` is far behind.
6. Chrome-extension synthetic clicks do not reach the web canvas (a real mouse does).

---

## 5. Honest assessment

**Right:** identity, evidence, provenance, one store, computed relations, the review queue, the
frame. These are the parts most projects skip and then can never add. They are done.

**Thin:** input. Four feeds, one language, no regional sources, no official sites, no registries.
The system can hold a world; it is being fed a newspaper.

**Missing:** judgement. The web records; it does not notice. "This is the first time A met B",
"hostility between X and Y doubled this month", "a new name appeared next to this ministry" — none
of that exists yet. That is the layer that would make one person feel like an agency.

**Cost:** ≈ $0.5–1 per day of LLM at today's volume (gpt-4o-mini); everything else is free feeds
and one Docker host. Scales with article count and languages, not with users.

---

## 6. How to step it up

Three tiers. Each item says what it gives you, not just what it is.

### 6.1 This week — make it live again (operations, no new features)
| Do | Gives you |
|---|---|
| Add OpenRouter credit | the 88 failed jobs and the 146 backlog articles get analysed; the web starts moving again |
| Aviation rule (1 report / aircraft / day, NORMAL unless emergency squawk) + `flight_tracks` retention (e.g. 7 days) | a readable feed; a database that does not grow 400k rows/day forever |
| Check AISHub | ships on the globe |
| Merge `web-view-redesign` → `main` in all three repos | one base to build on |
| 10 minutes/day on `/review` | 161 names decided; the resolver learns your merges |

### 6.2 Next — from "a world" to "your world"
1. **Sources: 30–50 feeds** — regional outlets, government press rooms, ministries, central banks,
   think tanks, court/registry feeds, in the languages of the area you care about. Gives you:
   coverage no general feed has. This is the single highest-value change and needs no code beyond
   a feed list per mission.
2. **Missions as real objects** (`mission_focus` today has `category` + `keywords` only). A mission
   needs: area (countries or polygon), languages, source list, watchlist (entity ids), alert rules,
   default globe view. Two-tier collection: **broad** (what runs now) + **focused** (the mission's
   sources, stronger model, HIGH on watchlist hits). Switch missions → the same screens show that
   lens. Gives you: the "collect everything, then look at one thing" mode you described.
3. **K8 — the assistant that walks the web.** Tools over the API (`entity_card`, `neighbors`,
   `evidence`, `events_near`, `timeline`) exposed to the UI assistant and MCP. "How is this ship
   linked to that company?" answered with quotes, not opinions. Gives you: investigation in
   sentences instead of clicks.
4. **Timeline** (COP phase 3): a strip with the event histogram, a scrubber, the Cesium clock
   following it. Gives you: "what did this look like in June?"
5. **Deeper backbone per mission**: load the region's provincial officials, local companies, ports,
   bases into Wikidata backbone + a curated local entity set. Gives you: fewer names in review,
   more lines that are correct.

### 6.3 Later — from memory to judgement (Level-2 / Level-3 reasoning)
- **Change detector**: first interaction between A and B; hostility or cooperation doubling in 30
  days; a new entity appearing next to a watched one. Scoped to a mission this is tractable and is
  the feature that makes the system *tell you* something.
- **Leadership watch**: APPOINT / RESIGN / ELECT on watched organisations → an always-current "who
  runs what".
- **Organisation profiler**: a living 30-day profile per watched org (partners, adversaries, trend).
- **Sanctions cross-check**: watched entities against OFAC / EU / UN lists.
- **Situations with SITREPs**: clusters become named situations with a timeline and a generated
  summary that cites its events.
- **Wall mode** (`/wall`): giant Zulu clock, alert ticker, auto-fly to the newest HIGH/CRITICAL,
  nearest camera in the card.
- **Relay deployment** (Fly.io or a $5 US VPS): New York and California live cameras on demand.

### 6.4 Only if humans ever report (HUMINT)
A structured SPOTREP/SALUTE-style form (reporter pseudonym, times, location, basis, confidence,
mission, ENTITIES and EVENTS blocks in the event model's shape) so facts are read deterministically.
**Before any real use:** per-user accounts and roles, pseudonyms only, encrypted storage, audit
log, deletion. Today there is one shared token; that is acceptable for a personal tool and not for
people at risk.

---

## 7. Decision log (short)

| Date | Decision |
|---|---|
| 09-13 | Security first: revoke leaked key (owner), bearer auth, loopback Postgres, no `trust` |
| 09-14 | COP frame; 3-D globe kept (cameras and other layers wanted); desk + wall (1080p TV); no alert ack yet; public city cams everywhere; free + on-demand paid |
| 09-15 | The web is the product; globe first; Wikidata Q-ids; ~20 actions; drop AGE; full bodies + GDELT; reasoning L1 now; wipe and restart on schema v2; ~50k backbone; review queue built, resolver strict |
| 09-16 | Missions = collection plan, presentation unchanged; collect broad then switch missions; HUMINT hypothetical, structured format if ever |
| 09-19 | Web view: click = select, evidence in the inspector, facts dashed, GDELT noise bar |

## 8. Glossary

- **Report** — one collected item (article, GDELT row, aircraft sighting, quake, document).
- **Entity** — a real thing with an identity; `qid` = Wikidata id; `LOCAL` = ours (e.g. a GeoNames city).
- **Mention** — an entity named in a report.
- **Event** — actor · action · target · place · time · source · quote. The atom of the web.
- **Relation** — a computed summary of events (or a Wikidata fact) between two entities.
- **Situation** — a cluster of ≥ 2 reports about the same thing.
- **Resolution** — turning a name into an entity; `NEEDS_REVIEW` = the machine was not sure.
- **Backbone** — the Wikidata subset loaded so names resolve without guessing.
- **Mission** — a collection plan: area, languages, sources, watchlist, alert rules, default view.
- **COP** — common operating picture: the fixed screen layout (status, layers, feed, map, inspector).

## 9. Operating notes

```
pia/.env, pia-ui/.env.local            secrets (gitignored): OPENROUTER_API_KEY, DB password, PIA_API_TOKEN
docker compose up -d                   postgres → pia_init → agents → api
python scripts/seed_wikidata_backbone.py   resumable; cached in data/wikidata_backbone.jsonl
npm run dev (pia-ui)                   http://localhost:5173  ·  /archive  ·  /review
pytest (pia, pia-api)                  unit tests, no database needed
docs/STATUS.md                         what works, what is simulated, what is not built
```
