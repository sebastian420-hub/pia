# Knowledge Web — Research and Redesign Proposal

**Status:** RESEARCH + PROPOSAL — for discussion. Nothing built.
**Follows from:** the 2026-09-15 conversation: the product is *one living web of the world — who is
who, and what connects them*. The globe, cameras and news are inputs; the web is the output.
**Evidence:** every number below was measured on the live database on 2026-09-15; screenshots in
`ui_research/graph_*.{jpg,png}`.

---

## 1. What the graph contains today (measured)

| Measure | Value | Meaning |
|---------|-------|---------|
| Entities that are not cities | **122** (61 PERSON, 36 ORG, 18 INFRA, 4 VESSEL, 3 EVENT) | tiny |
| Entities with a Wikidata id | **0** | nothing is anchored to a known identity |
| Relationships | 102, using 8 verbs; **HOSTILE_TO 33, LOCATED_IN 27, WORKS_FOR 18** | "who is who" is mostly "who is hostile to whom" |
| Relationships corroborated by >1 report | **4** | 98 % are single-sentence claims |
| Confidence of all edges | 0.30 – 0.36 | none ever passes the 0.5 bar |
| Vertices in the Apache AGE graph | **8** (3 of them my injection-test strings) vs 122 in tables | the graph database is effectively empty |
| Edges in AGE | **5** vs 102 in tables | the UI does not even use AGE; it reads the SQL tables |
| Article text given to the LLM | **124 characters on average**; `content_raw` is NULL for **208 / 208** news records | the extractor only ever sees the RSS headline + one sentence |
| News source recorded | every article is `source_name = 'RSS News Feed'` | BBC / Al Jazeera / NYT / Verge are indistinguishable; trust = default 0.5 |

### What the nodes look like

- Same thing, several nodes: `US` / `United States` / `Beijing` vs `China`; `Trump` / `Trump administration`;
  `Iran` / `Iran's president`.
- Generic nouns became entities despite the prompt forbidding it: `king`, `prime minister`, `pipeline`,
  `security services`, `prosecutors`, `Russians`, `Saudi`, `the kingdom`, `Gulf nations`.
- Types are inconsistent: `Iran`, `Russia`, `United States` are `ORGANIZATION` (seeded that way by
  `scripts/seed_target_deck.py`); `China`, `Israel`, `Ukraine` are `LOCATION`. The prompt offers
  `PERSON|ORGANIZATION|LOCATION|VESSEL|AIRCRAFT|INFRASTRUCTURE` — there is no COUNTRY/GPE, so the
  model has to pick one of two wrong answers for a country.

### What the edges look like (random sample, verbatim)

| Edge | The model's reasoning |
|------|----------------------|
| London **HOSTILE_TO** Wales | "leaders of nationalist parties in Wales assert that London has no right to block democracy" |
| security services **WORKS_FOR** prosecutors | "Security services provide information and support to prosecutors" |
| Trump **LOCATED_IN** West Springfield | "Donald Trump was visiting his golf course in Ireland" |
| Al-Mamlaka **SUPPORTED** Aqaba | a news channel *reported on* an evacuation |
| Beijing **HOSTILE_TO** US | "Beijing is urging the United States not to hype the dangers of A.I." |

The model is not stupid; it is **forced to squeeze a nuanced sentence into 13 stance verbs**, from
124 characters of text, and every output becomes a permanent, undated line between two nodes.

### One article, end to end

"Dozens of aircraft, hundreds of buildings: US loss to Iran attacks revealed" → entities extracted:
`{Pentagon}` → edges produced: **none**. The text the LLM received was the RSS blurb:
"The Pentagon watchdog&#039;s report paints a picture of significant losses…" (HTML entity included).

---

## 2. Root causes (code)

1. **Starved extraction.** `news_agent.py` stores title + RSS description only; nothing fetches the
   article body. `content_raw` is never filled for news. (`news_agent.py:106-137`)
2. **No identity resolution.** `analyst_agent.process_intelligence_components` matches by name /
   alias / embedding-nearest against *whatever PIA created before*. There is no external reference,
   so `US` and `United States` can only merge if their embeddings happen to be > 0.45 similar and an
   LLM "fusion" call agrees. Nothing says "this is Q30".
3. **Relations instead of events.** `entity_relationships` is a bare (a, verb, b, confidence) row;
   time exists only as `first_observed/last_confirmed`. A stance verb is asserted forever.
4. **Vocabulary designed for a demo.** `ALL_VALID_VERBS` mixes finance, war, gossip; several verbs
   are synonyms (`SUED_BY` / `LITIGATING_AGAINST`, `FINANCED_BY` / `FUNDED_BY`), directions are
   implicit, no inverses. (`nlp.py:51-75`)
5. **Two stores.** Truth in Postgres tables; a by-name mirror in Apache AGE only when confidence > 0.5
   — which never happens because every news source has trust 0.5 → base confidence 0.30. The graph
   database is empty and the UI reads the tables through a recursive CTE. (`analyst_agent.py:324,
   383`; `routers.py` graph endpoint)
6. **Provenance lost at ingestion.** Outlet name dropped (`'RSS News Feed'`), so `source_authority`
   cannot weight anything and the reader cannot see who said it.
7. **Seeds typed by hand.** `seed_target_deck.py` creates countries as ORGANIZATION; `seed_wikidata5m.py`
   types everything ORGANIZATION (now UNKNOWN) and was never run.
8. **Viewer.** 3-D force layout in a translucent overlay on top of the globe; 6-px labels; no time,
   no evidence on edges, no grouping; countries and people the same size. (`RelationalWeb.tsx`;
   screenshots `graph_01`, `graph_02`)

None of these is a bug in the usual sense. They are the design of a demo. To get "who is who,
connected correctly", the design has to change, not the thresholds.

---

## 3. Redesign: "Wikidata that moves"

### 3.1 The three kinds of things

```
ENTITY   — a real thing with a stable identity (person, organisation, place, vessel, aircraft)
           anchored to a Wikidata Q-id whenever one exists; PIA-local id otherwise
EVENT    — something that happened: actors, action, target, place, time, sources, confidence
SOURCE   — where a claim came from: outlet, URL, time, trust
RELATION — a *summary* computed from events (and from Wikidata's static facts): "37 hostile
           events since March", "CEO of since 2021 (Wikidata)"
```

Today PIA has entities and relations only. Adding **events** and **sources** as first-class rows
is the single change that makes the web truthful and time-aware.

### 3.2 Identity: resolve against a backbone, not against yourself

- Load a **Wikidata subset** as the backbone: countries, cities > 100k, governments, ministries,
  armed groups, companies (listed + notable), heads of state/government, ministers, executives,
  vessels, aircraft types. Roughly 2–5 million items with labels, aliases (all languages), type
  (P31), coordinates (P625), and a handful of relations (P17 country, P39 position held, P169 CEO,
  P463 member of, P361 part of). Wikidata's own dump or the SPARQL endpoint; refreshed monthly.
- Resolution becomes a **lookup, not a guess**: label/alias match → type check → context check
  (country of the article, co-mentioned entities) → the LLM only breaks ties ("is this *the*
  Cambridge or Cambridge, MA?"). Unknown things get a local id and a `needs_review` flag, and are
  merged into a Q-id later when the enrichment agent finds one.
- `US`, `United States`, `Washington (government)`, `Beijing (government)` all resolve to Q30 /
  Q148 with a *role* ("government of"), which is exactly how newspapers write.

### 3.3 Events: what the LLM should extract

From the **full article** (fetched, cleaned, 2–8k chars), extract 0–5 events:

```json
{"actor": "Iran", "action": "ATTACK", "target": "US forces", "location": "Iraq",
 "time": "2026-09-13", "quote": "…exact sentence…", "confidence": 0.8}
```

- `action` from a **small event ontology** (~20): ATTACK, THREATEN, SANCTION, MEET, AGREE,
  ACCUSE, ARREST, APPOINT, RESIGN, ACQUIRE, INVEST, FUND, SUPPLY, DEPLOY, PROTEST, VISIT, ELECT,
  STATEMENT, DISASTER, OTHER. (CAMEO/GDELT use 20 root codes for the same reason: it is enough.)
- Every event keeps the **quote** it came from → the edge's evidence is readable, and human feedback
  can reject a specific claim.
- Static facts (CEO of, capital of, member of) are **not** extracted from news; they come from
  Wikidata and are marked as such.

### 3.4 Relations: computed, dated, directional

`relation(a, b, kind, first, last, event_count, sources, weight)` is rebuilt from events by a job,
not written by the LLM. `kind` is derived: many ATTACK/THREATEN/SANCTION → `HOSTILE`; MEET/AGREE →
`COOPERATING`; APPOINT/RESIGN/ELECT → `ROLE`. A relation that has had no event for 90 days decays
in weight instead of staying a permanent line. Wikidata relations sit alongside with `source =
wikidata`, never decaying.

### 3.5 One store

Drop the AGE mirror. Keep PostgreSQL as the single store (entities, events, relations, sources,
mentions) with the indexes the queries need; the "graph" is a set of SQL views plus one recursive
query for k-hop neighbourhoods (the API already does this). If a graph database is ever needed for
deep traversal, mirror *by id* from these tables, not by name. AGE can be removed from the Docker
image, which also removes the slow custom build.

### 3.6 Provenance from the first byte

`news_agent`: record outlet (`BBC`, `Al Jazeera`…), URL, published time; fetch and store the article
body (`trafilatura` or `readability`, respecting robots); `source_authority` gets a row per outlet.
Add **GDELT** as a second event source: it already delivers globally geocoded events with CAMEO
codes every 15 minutes — an independent check on what the LLM extracts.

### 3.7 The web as the main screen (if graph-first)

- **Entity page** = the "who is who" card: canonical name, aliases, type, description (Wikidata +
  LLM), where on the globe, roles/positions, connections grouped by kind, and a **timeline of events
  and mentions**. URL per entity (`/entities/Q30`).
- **Web view**: 2-D (Sigma.js / Cytoscape), nodes sized by mention volume in the selected time
  window, grouped/coloured by type, edges by kind with thickness = event count, **time slider**
  that replays the web; click an edge → the events and quotes behind it; expand a node one hop at a
  time; search jumps to a node.
- **Globe** becomes a lens on the same data: select a region → the web filters to entities and events
  there; select an entity → its places light up.

---

## 4. What changes, honestly

| Keep | Change | Drop |
|------|--------|------|
| Postgres, TimescaleDB, PostGIS, pgvector | analyst → *resolver + event extractor* | Apache AGE mirror |
| queue, heartbeats, migrations, API/auth | `entity_relationships` → computed `relations` + new `events`, `sources`, `mentions` | 13-verb stance vocabulary |
| cameras/sensors layer, COP frame | news_agent fetches bodies and keeps outlet | 3-D force graph overlay |
| feedback endpoint (now per event) | Wikidata becomes the backbone (ingestor rewritten around Q-ids) | hand-typed seed scripts |

Rough effort: backbone load + resolver 1.5 weeks; article bodies + event extraction 1 week;
relations job + API 1 week; entity page + 2-D web + time slider 2 weeks; GDELT 3 days. About
**6 weeks** — and it replaces, not extends, the current graph.

---

## 5. Decisions needed

1. **Wikidata as backbone** (Q-ids as identity) — yes/no. This is the foundation of "connecting
   correctly"; without it we can only tune name matching.
2. **Graph-first or globe-first** main screen.
3. **Event ontology size**: ~20 CAMEO-like actions (recommended) vs the current 45 verbs.
4. **Drop AGE** — it contributes nothing today and costs a 10-minute image build.
5. Fetching article bodies: some outlets forbid it in robots.txt; accept partial coverage, or use
   GDELT for those.
