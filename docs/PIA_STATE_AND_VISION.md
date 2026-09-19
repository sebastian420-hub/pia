# PIA — State of the Project and Where It Can Go

**Written:** 2026-09-15, after two working days on the three repositories (`pia`, `pia-api`, `pia-ui`).
**Superseded for the current picture by:** `PIA_CONCEPT_AND_SYSTEM.md` (2026-09-19). This file remains the history and decision record.
**Purpose:** one document that records what was found, what was built, what was decided in
discussion, what is still open, and what the project can become. Everything else in `docs/` is a
detail of something in here.

---

## 1. One-paragraph summary

PIA (Personal Intelligence Agency) started as a demo: a 3-D globe showing news headlines and small
earthquakes, an LLM inventing a "knowledge graph" from 124-character RSS blurbs, a leaked API key,
no authentication, and documentation that called it "Tier-1 Operational". In two days it became a
running system with a defined purpose: **one living web of the world — who is who, and what is
happening between them — fed by news, public data and sensors, shown on a globe, backed by
Wikidata identities and evidence-carrying events.** The foundation is now honest and correct. What
it becomes next depends on feeding it well, using it daily, and choosing a focus (missions).

---

## 2. Where it came from (the review, day 1)

Full findings: `../REVIEW.md` (sections 3, 4, 9). The important ones:

| Finding | Consequence |
|---------|-------------|
| OpenRouter key hardcoded in `scripts/quick_embed.py`, still in git history | must be revoked by the owner (done? — owner action) |
| Cypher text pasted into SQL inside `$$…$$` → SQL injection from LLM output on public articles | closed, then the whole AGE layer was removed |
| No auth on API, MCP or Postgres (`trust`, port 5432 public) | bearer token, loopback binding, no trust |
| Document upload could not work (`INVESTIGATIVE` violated a CHECK; files moved to `processed/` anyway; wrong shared folder) | fixed, verified end to end |
| `/entities/bbox` always errored (SQL had no placeholders) | rewritten with a real envelope filter |
| UI filter used `FINANCE`; DB uses `FINANCIAL` — financial news never showed | one shared domain list |
| Embedding never written; semantic search of records returned nothing | analyst persists it |
| 2 of 4 "sensors" were hardcoded fake data (Air Force One, Ever Given at fixed coordinates, every 60 s) | gated behind `SIMULATED_SENSORS`, labelled `[SIM]` |
| Analyst processed 1 job per 10 s; failures marked DONE; stuck jobs never recovered | drains queue, FAILED with retries, stale re-claim |
| `maintenance.py` deleted every new entity after 24 h | orphan-only rule |
| 38 MB Windows `venv/` and `.env` committed to pia-api | removed |
| Docs claimed "100% stable"; half the schema had no writer | `STATUS.md` rewritten honestly |

---

## 3. What was built (day 1 → day 2)

### 3.1 Hardening (branch `hardening-and-cameras`, all three repos)
Security fixes above; pinned dependencies; `.env.example`s; migrations runner; 47 unit tests that
run without Docker; CI with gitleaks; pia-api rewritten with `config.py`, `auth.py`, a connection
pool and real HTTP status codes; UI with a typed API client and zero ESLint errors.

### 3.2 COP frame and camera layer (same branch; plan: `design/cop_ui_and_camera_layers_plan.md`)
- **UI frame**: status bar (`UNCLASSIFIED // OSINT`, Zulu clock, feed/agents/queue/alerts, GO LIVE),
  tool row, layers rail with counts, dense report feed with an alert lane, globe, inspector column,
  agent log. Nothing overlaps. Dark Esri basemap. NORMAL is grey; colour only for HIGH/CRITICAL.
  Plain vocabulary (Reports, Entities, Situations, Cameras, Alerts — no "Neural Core").
- **Cameras**: a `sensors` layer model; a camera agent with providers for Hong Kong TD (1,013),
  London TfL (890, with 10 s clips), Finland Digitraffic (809), Toronto (336), New Zealand (313),
  Singapore (~90) — **~3,370 public cameras**, refreshed hourly, health-probed. A snapshot/video proxy
  with caching and size caps. "Cameras within 5 km" on every positioned report.
- **Live sessions**: NYC DOT and Caltrans only answer US IPs → an `ON_DEMAND` source class, a
  one-file US relay (`pia-api/relay/`, Fly.io config), and a time-boxed live session with idle stop
  and a cost meter. Not deployed yet (needs a cloud account).
- Screenshots: `design/ui_research/after_*.jpg`.

### 3.3 The knowledge web (branch `knowledge-web`; research: `design/knowledge_web_research.md`;
plan: `design/knowledge_web_implementation_plan.md`)
The database was wiped and rebuilt on **schema v2** (`database/schema/`):

```
sources        one row per outlet / dataset, with trust
entities       identity: qid (Wikidata), kind, resolution (RESOLVED | LOCAL | NEEDS_REVIEW | REJECTED), origin
entity_aliases every name a thing is known by (Wikidata aliases, GeoNames names, human merges)
mentions       entity ↔ report, with role and the surface string
events         actor · action · target · place · time · source · quote · confidence · tone   (hypertable)
relations      computed: from events (decaying weight), from Wikidata facts, from co-mentions
```
Apache AGE is gone (it held 8 vertices; nothing read it). The Postgres image is the plain
timescaledb-ha base.

Pipeline, verified live:
- `news_agent` fetches **full article bodies** (robots-aware, trafilatura), records outlet and time.
  Extractor input went from 124 characters to ~4,000.
- `analyst_agent` v2: event-extraction prompt (23 CAMEO-style actions), mentions, events with the
  exact quote, report geocoding from resolved places, situations only when two reports agree.
- `kg/resolver.py`: generic-noun filter → government seats ("Beijing said" → China) → local alias
  table → Wikidata search with context scoring → optional LLM tie-break among candidates →
  **review queue for anything unsure**. Concepts never become entities. Wrong-country alias hits are
  refused for bulk sources.
- `seed_wikidata_backbone.py`: ~52k items (countries, capitals, leaders, ministries, armed forces
  and groups, parties, agencies, notable companies, warships, notable politicians/executives/officers)
  with aliases, coordinates and static relations; cached to `data/wikidata_backbone.jsonl`.
- `gdelt_agent`: every 15 minutes, GDELT's export file → geocoded, coded events, no LLM; noise rules
  (no self-pairs, directed actions need a target, target-less need ≥ 10 mentions).
- `enrichment_agent` (now "kg maintenance"): fills Wikidata relation targets, refreshes items,
  retries failed lookups, rebuilds relations hourly, merges review outcomes.
- A cross-process Wikidata rate limit (advisory lock + `rate_limits`) after three analysts, the
  maintenance agent and the seed script triggered 429s together.

API (`pia-api/kg_router.py`): entity card, entity events, relation evidence, events for the globe,
alias search, review queue with merge/keep/reject.

UI: entity search with typeahead; **entity card** (identity, trend, connections by kind with
"former" marked, events with quotes, reports); **events layer** on the globe; **2-D web** (expand a
node, click an edge for evidence); **review page**. Globe layers were memoised after a freeze with
3,000 camera billboards. Screenshots: `design/ui_research/kg_*.{jpg,png}`.

### 3.4 Numbers at the time of writing
Backbone ~20 % loaded (runs in the background at 1 req/s). 840 resolved non-city entities (238
mentioned in reports), 106 events (63 from articles, 43 from GDELT), 1,858 relations, 87 articles
analysed, 64/120 news reports positioned (was 20 %), 129 names in review.

### 3.5 Commits
`hardening-and-cameras`: pia 8175741, pia-api f65d063, pia-ui 084c8c9.
`knowledge-web`: pia 88306ec → d2b8256, pia-api 5cbbae4 → c0f2f58, pia-ui c14863a.
Neither branch is merged to `main`.

---

## 4. What we discussed and decided

### 4.1 Product identity (the conversation that mattered most)
The owner's goal: *"collect the world data and map it into one giant web of knowledge that shows
who is who and connects everything."* Three directions were laid out — point-at-a-place, watch-my-
missions, investigate — and the conclusion was: **the web is the product**, the globe is the main
screen and a lens on the web, and the web view is for investigation. Formulated as *"Wikidata that
moves"*: Wikidata gives the static who-is-who; PIA adds what happens between them, dated, sourced,
quoted.

### 4.2 Design decisions taken
| Topic | Decision |
|-------|----------|
| Identity | Wikidata Q-ids as the backbone; local entities allowed; unsure → review, never into the web |
| Main screen | Globe first; web = backend + investigation view |
| Event vocabulary | ~20 CAMEO-style actions, not 45 stance verbs |
| Graph store | Drop Apache AGE; Postgres only; a graph engine can be mirrored *by id* later if needed |
| Text | Fetch full article bodies; add GDELT |
| Reasoning | Level 1 now (counts, trends, decay), Level 2 next (assistant with graph tools), Level 3 later (automatic pattern alerts) |
| Review queue | Built; resolver strict so the web is right even if nobody reviews |
| Data reset | Yes: wipe and restart on schema v2 rather than 16 migrations over demo data |
| Backbone scope | ~50k items worldwide first; a region can be loaded deeper per mission |
| UI look | "Military discipline, civilian honesty": dark, dense, Zulu clock, plain words, honest `UNCLASSIFIED // OSINT` banner, no sci-fi |
| Users | The owner at a desk + a passive wall screen (1080p TV) |
| Cameras | Public city traffic cams, all cities that publish them; snapshot-first; paid vendors don't sell by the minute, so "on demand" = the US relay |
| Alerts | No acknowledge workflow yet; HIGH/CRITICAL in their own lane |

### 4.3 Discussed, agreed in principle, not built
- **COP plan phases 3–5**: timeline (drag back in time; drives the Cesium clock), entity/situation
  pages by URL, `/wall` mode (giant Zulu clock, alert ticker, auto-fly to the newest HIGH/CRITICAL,
  nearby camera in the card, 22 px minimum text).
- **Live sessions**: deploy the relay on a US host (Fly.io or a $5 VPS) → New York and California
  live video; Windy Webcams and keyed providers (Sydney, Brisbane, Seoul).
- **K8**: assistant tools over the web (`entity_card`, `neighbors`, `evidence`, `events_near`) via
  MCP and the UI assistant — "how is this ship linked to that company?" answered with quotes.
- **Missions as first-class objects** (see 5.1).
- **Human field reports** (see 5.3).
- Real ADS-B / AIS (OpenSky, aisstream.io) to replace the simulated agents.
- More sources: 30–50 feeds, regional outlets, government press rooms, think tanks.
- A US relay is the one piece of infrastructure the owner must provide (cloud account).

---

## 5. What this could become

### 5.1 Missions: one global web, many lenses
A mission is a **collection plan**, not a separate database. It changes *what PIA collects and
cares about*; the presentation stays the same:

- **Collection**: the mission's sources (local outlets in the region's languages, official sites,
  the area's cameras, GDELT filtered to the area).
- **Attention**: a watchlist of entities (Q-ids or curated local entities) and topics; anything
  touching them is HIGH, reviewed first, extracted with a stronger model.
- **Presentation**: default globe position, scoped feed/events/alerts, the wall shows that mission,
  the assistant answers in that context.
- **Memory**: the web stays global; the mission remembers "new entity in this theatre", "first
  interaction between A and B".

`mission_focus` exists but is too thin (category + keywords). A real mission needs: area (polygon
or countries), languages, source list, watchlist of entity ids, alert rules, default view.
Switching one mission at a time first; stacking later.

"Input quality" then has three parts: coverage (feeds), extraction quality per language (bigger
model or translation for some), and **identity coverage** — Wikidata is thin for local companies,
generals, provincial officials, so a mission's curated local entities become the asset nobody
else has.

### 5.2 Mission agents (the intelligence layer)
Because everything is entities + events, a new agent is another producer or reader of events and
needs no new UI:
- **Leadership watch** — APPOINT/RESIGN/ELECT on watched organisations → an always-current "who
  runs what".
- **Organisation profiler** — a living profile per watched org from its events: partners,
  adversaries, activity trend, 30-day summary.
- **Relationship change detector** — first interactions, hostility doubling, unusual co-mentions
  (Level-3 reasoning, tractable when scoped to a mission).
- **Sanctions/lists cross-check** — watched entities against OFAC/EU/UN lists.
- **Physical layer** — ships in a strait, flights into an airport, cameras at a crossing, tied to
  the same entities.
- **Situations that mean something** — with real events, clusters can become named situations with
  a timeline and a SITREP.

### 5.3 Human field reports (HUMINT)
Hypothetical for now. The upload pipeline already exists; what is missing is a **structured
format** so facts are read deterministically, not guessed. A SPOTREP/SALUTE-style template:
reporter id (pseudonym), reported/observed times, location, basis (direct/indirect/hearsay),
confidence, mission; then ENTITIES and EVENTS blocks in the same shape as the event model, and free
NOTES for the LLM. A phone form (or a Telegram `/spotrep`) beats a document. Reporters are
`sources` with their own trust, adjusted by corroboration.

**Non-negotiable before any real use:** per-user accounts and roles, pseudonyms only, encrypted
storage, audit logs, deletion — today the system has one shared token and no users, which is
acceptable for a personal tool and not for people at risk.

### 5.4 The honest ceiling
- Extraction hallucinates occasionally, GDELT is noisy by nature, Wikidata has odd items. The web
  will never be perfect; the presentation must stay honest about confidence (evidence, quotes,
  "former", scores) — this is why events carry quotes and relations carry counts.
- It is a real system now (~12 services). It needs an owner who reads the logs and uses the review
  queue. Heartbeats, retries and the review page help; they do not replace attention.
- Costs are small (≈ $0.5–1/day LLM at current volume, free feeds, one Docker host), and scale
  with article count and mission languages.
- Wide ambition produces shallow products. **Depth on one theatre beats breadth**: the impressive
  version is "the best free view of region X", not "everything in the world".

---

## 6. Operating notes

```
pia/.env, pia-ui/.env.local        secrets (gitignored) — OPENROUTER key, DB password, PIA_API_TOKEN
docker compose up -d               postgres → pia_init (schema + migrations + GeoNames) → agents → api
python scripts/seed_wikidata_backbone.py   ~1–2 h, resumable, cached in data/
npm run dev  (pia-ui)              http://localhost:5173  ·  /archive  ·  /review
pytest (pia, pia-api)              unit tests without a database
docs/STATUS.md                     what works, what is simulated, what is not built
```
Old containers from previous runs were renamed `*_old_0914`; old volumes `pia_oia_pia_pgdata` and
`black-rabbit-pia_pia_pgdata` are untouched.

Known small issues at the time of writing: the backbone load is still running; "AGENTS n/m" counts
stale heartbeat rows from replaced containers for an hour; the Chrome extension's synthetic clicks
don't reach the web canvas (a real mouse does); event relations are few until more articles flow.

---

## 7. Suggested next steps, in order

1. Let the backbone finish; run the system for a few days; use `/review` daily; tune the resolver
   and the prompt from what you see.
2. **Choose mission one.** Design the mission object around it (area, languages, sources,
   watchlist, alert rules); wire in its sources; load its region deeper into the backbone.
3. K8 — the assistant that walks the web with evidence.
4. COP phases 3–5 — timeline, entity/situation pages, wall mode.
5. First mission agents — leadership watch and the change detector — against real data.
6. Relay deployment for US cameras; real ADS-B/AIS.
7. Only if humans ever report: the security phase (users, roles, encryption, audit, deletion).
