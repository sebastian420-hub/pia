# Missions and connectors — implementation plan

**Status:** step 1 BUILT 2026-09-21 — connector contract, ingestor, `external_ids`, FtM mapper, OpenSanctions
(sanctions dataset: 73,017 entities, 169,272 facts, 13,186 identifiers, 148,958 registry relations; 416 Wikidata
backbone entities gained listings — e.g. the IRGC card: 21 lists, 12 ownership facts, 'sanctioned by United Kingdom
since 2020-12-31'). Nightly agent `connector_agent` in compose.
**Steps 2 + 3 BUILT 2026-09-20 (evening)** — migration 010 (`missions`, `mission_relevance`, `mission_memory`; `mission_focus`
dropped, General active) + 011 (alerts reach live listeners); `kg/missions.py` (relevance 1.0/0.8/0.6/0.4/0.1 for reports,
entities, events of the last 30 days, ~0.3 s per mission; alerts as HIGH/CRITICAL reports from `mission_alerts`, one per
actor›target·verb·day, remembered in `mission_memory`); enrichment step every 15 min or on edit; news agent reads mission
feeds first and tags reports naming a watchlist entity (word-start match); analyst is told the watchlist; API
`/missions` (list/get/create/update/activate/delete/alerts/options) and `mission_id` on `/archive`, `/kg/events`,
`/entities/bbox`, `/kg/web/overview`; UI `MISSION ▾` switcher (activate, show all, new, edit) and editor (countries,
watchlist, area from the globe view, topics, feeds, databases, alert rules). Checked in the browser with a "Gulf" mission
(IR/SA/IL/AE/YE, watch Iran + Houthis): feed 1,952 → 421 reports, web 337 → 129 links, 8 alerts ("Iran attack United
States", "new org in theatre — Houthis"); switching back to General restores everything. Deviations from §2: relevance
recomputes every 15 min (not hourly) and immediately after an edit; `mission_notes` is `mission_memory`; the Archive page
stays unfiltered (it is the "everything" view). Found on the way and fixed: "Donald Trump" resolved to *Donald Trump III*
in US stories because Q22686 had no country yet and a country match outranked a 300× prominence gap — an unknown country
is no longer a penalty, only a contradicting one (`resolver._lookup_local`), 69 mentions moved; the verifier lost ~40 % of
its answers to `"stance": +2` (not JSON) — `parse_llm_json` repairs `+N` and a bare `-`.
**Step 4 BUILT** — `connectors/spotrep.py` (markdown + JSON forms, `docs/SPOTREP_FORMAT.md`); the document agent routes
`reporter:` files to it; reporter = source with trust from basis × confidence; entities carry hard ids; events are
*recorded* rows (blue badge; count as verified when the source trust ≥ 0.5 — never hearsay); NOTES → HUMINT report on
the feed, tagged with the mission. Checked end to end with a test report (Iran → Q794, Houthis → their node, line drawn,
card row "delivered supplies to · recorded"), then removed from the live web.
**Step 5 BUILT** — `kg/names.py` NameKeeper as an enrichment step: collectives of a known thing ("Chinese Foreign
Ministry" → China, "Houthi militia" → Houthis, "Dutch riot police" → Netherlands) via demonyms (Wikidata P1549, current
state preferred, adjective fallback "iraqi" → Iraq), spelling variants of places/orgs (trigram ≥ 0.9), demonyms filed
as persons rejected, names seen once and quiet for 14 days leave the queue. Dry run on the live queue: 23 merges,
2 variants, 2 rejects, 0 wrong. Runs 200 names per poll; the queue was 877 and started shrinking (865 after one pass).
**Step 6 DONE** — `design/access_control.md` (design only).
PLAN written 2026-09-20. Follows the direction agreed today (`../PIA_CONCEPT_AND_STATUS_2026-09-20.md` §5):
be ready for any database, then focus the picture with missions.
**Follows from:** `living_verbs_plan.md` (BUILT), `true_lines_plan.md` (BUILT), `PIA_STATE_AND_VISION.md` §5.1
(missions as first described on 09-15).

---

## 0. Evidence the plan rests on

| Fact | Where |
|---|---|
| `mission_focus` exists but is thin: `category, keywords[], target_entities[], is_active, client_id`; only the news agent reads it (priority bump + `mission_id` on the report) | schema, `news_agent.py:106-116` |
| The status bar hard-codes `MISSION GENERAL` | `StatusBar.tsx:60` |
| `sources` already carries `kind, trust, country_qid, language, homepage` — enough to describe a connector's source | schema |
| Entities have `qid` (Wikidata) or nothing; no place for a passport number, company register id, phone number | schema |
| Every producer already writes the same three shapes: `intelligence_records` (document), `entities` + `entity_aliases`, `events` with `source_id` and a proof (`quote` or `report_uid`) | agents |
| OpenSanctions consolidated sanctions export: 300,962 entities, 342 MB FtM JSON, updated daily, free for non-commercial use; also PEPs and ownership | `data.opensanctions.org/datasets/latest/sanctions/index.json` (fetched 09-20) |
| FollowTheMoney schemata cover exactly our kinds and more: Person, Company, Organization, Vessel, Airplane, Sanction, Ownership, Directorship, Membership, Payment, Address, Passport… with `id`, `schema`, multi-valued `properties` | [FtM](https://github.com/opensanctions/followthemoney) |

## 1. Connectors — one way in for any source

### 1.1 The contract (`pia/connectors/base.py`)
A connector is a class with `source` (a `sources` row: id, label, kind, trust, homepage) and one
generator method `pull(since) -> Iterable[Item]`, where an `Item` is one of:

```
Entity   {external_id, kind, name, aliases[], description?, country?, geo?, properties{}, wikidata_qid?}
Fact     {subject_external_id, predicate, object_external_id | value, valid_from?, valid_to?, record_ref}
Event    {actor_external_id, predicate, target_external_id?, time, place?, stance?, record_ref, quote?}
Document {external_id, title, text, published?, url?, language?}
```
`record_ref` is the connector's own pointer (row id, URL, file + line) and becomes the proof.
The framework does the rest: identity (external id → entity via `external_ids`; else name
resolution as today), verbs (Fact/Event predicates go through the catalogue), provenance
(`source_id`, `record_ref`), trust (from the source row), and — for Documents — the normal
reader/verifier path. **Structured Facts and Events skip the verifier** (a row is a row; its
trust is the source's), and are marked `origin = 'connector'`.

### 1.2 Identity across sources — `external_ids`
```sql
CREATE TABLE external_ids (
  source_id   TEXT REFERENCES sources,
  external_id TEXT,
  entity_id   UUID REFERENCES entities ON DELETE CASCADE,
  kind        TEXT,               -- passport | company_reg | phone | ftm | case | …
  PRIMARY KEY (source_id, external_id)
);
```
Resolution order becomes: hard id in `external_ids` → Wikidata Q-id (if the source gives one, as
OpenSanctions does) → name resolution (today's path) → new local entity carrying the external id.
A hard identifier beats name matching every time; merging two entities moves their ids.

### 1.3 FollowTheMoney as the interchange format
An `FtmConnector` reads any FtM JSON stream and maps: `Person/Company/Organization/Vessel/
Airplane → Entity`; `Sanction → Fact(subject, "sanctioned by", authority)`; `Ownership/Directorship/
Membership/Employment → Fact`; `Payment → Event("paid")`; `Address/Passport/Identification →
external ids and properties`. Any database that can be exported to FtM (OCCRP has converters)
then needs no new code — only a `sources` row and a URL/file.

### 1.4 First connector: OpenSanctions
- Dataset `sanctions` (300k entities, daily) first; `peps` later. Nightly pull of the FtM export,
  streaming (342 MB), upsert by FtM id; Q-ids from FtM's `wikidataId` property land directly on
  backbone entities (so *Iran's IRGC* gains "sanctioned by OFAC / EU / UN" facts with dates).
- New relation kind label under `MEMBERSHIP`/`OWNERSHIP` families: `sanctioned by` (directed),
  `owned by`, `director of` — as Wikidata facts are today (dashed, never decaying, source shown).
- Card: a **LISTS** line ("OFAC SDN since 2019-04-08 · EU since 2022-02-25") from facts of kind
  `sanction`; the globe's wire-off picture is unchanged.
- Verification: `select count(*) from external_ids where source_id='opensanctions'` ≈ 300k;
  IRGC / Rosneft / a named individual show sanction facts with dates and the authority.

### 1.5 Structured human reports (SPOTREP)
A second connector reads a fixed document format (Markdown/JSON, and a phone-friendly form later):
```
reporter: <pseudonym>      observed: 2026-09-20T08:15Z   reported: …   location: 33.51, 36.29 (or place name)
basis: direct | indirect | hearsay     confidence: 0.7     mission: <id>
ENTITIES:  - name | kind | ids (passport/plate/phone) | notes
EVENTS:    - actor | predicate | target | time | place | stance
NOTES: free text (read by the analyst like an article)
```
ENTITIES/EVENTS are structured (no guessing); NOTES go through the reader. The reporter is a
`sources` row with its own trust, raised by corroboration. Upload path exists; the parser and
the form are new.

## 2. Missions — "look narrowly"

### 2.1 The object
```sql
CREATE TABLE missions (
  mission_id   UUID PRIMARY KEY, name TEXT, description TEXT, is_active BOOLEAN,
  area         GEOMETRY(MultiPolygon, 4326),     -- or NULL = world
  countries    TEXT[],                            -- Q-ids
  languages    TEXT[],
  sources      TEXT[],                            -- source_ids to collect (feeds, connectors)
  watchlist    UUID[],                            -- entity_ids
  topics       TEXT[],                            -- from TOPICS
  alert_rules  JSONB,                             -- e.g. {"watchlist_stance_le": -2, "new_pair": true}
  default_view JSONB,                             -- camera position, layers, window
  created_at, updated_at
);
```
`mission_focus` is migrated into it and dropped.

### 2.2 Two-tier collection, one-tier picture
- **Broad tier** keeps running as today (all feeds, GDELT, sensors).
- **Mission tier**: the mission's sources (its RSS feeds, its connectors) are read in full and
  first; articles mentioning watchlist entities or inside the area get priority `HIGH` and the
  stronger model (`MISSION_MODEL`).
- **Relevance score** on every report, event and entity for the active mission
  (`mission_relevance` table, recomputed hourly): watchlist hit 1.0 · inside area 0.8 · country
  match 0.6 · topic match 0.4 · else 0.1. The globe, feed, alerts, web layer, briefs and the
  assistant filter to relevance ≥ 0.4 by default; a "show all" toggle lifts it.
- **Alerts** from `alert_rules`: watchlist entity in a hostile verified event; first verified
  event between two watchlist entities; a new entity appearing within the area with ≥ 3 events.
- **Mission memory**: `mission_notes` (first seen / first pair / owner notes) so the mission
  remembers what was new.

### 2.3 UI
- Status bar: `MISSION ▾` switcher (name, last alert); creating/editing a mission: name, area
  (draw a rectangle or pick countries), sources (checklist of feeds + connectors + "add RSS"),
  watchlist (entity search, multi), topics, alert rules, default view.
- Everything else unchanged; the mission only changes *what is shown* and *what is read first*.

## 3. Self-maintaining names (small, same idea as verbs)
The resolver auto-decides the clear cases that today wait in review: (a) a local name whose
only Wikidata candidate has the right kind and a country matching the story → merge; (b) a
name seen once, never again in 14 days → archive quietly; (c) generic role words → reject.
Review keeps the rest. Target: the queue stops growing.

## 4. Access control — built when a private source arrives
Users, roles, per-source visibility (`sources.visibility`), row filters in the API, audit log,
deletion. Designed now (the `client_id` columns from schema v1 are the hook), built then.

## 5. Order, effort, verification

| Step | Days | Check |
|---|---|---|
| 1. `external_ids` + connector contract + FtM mapper + OpenSanctions nightly | 2 | IRGC card shows "sanctioned by OFAC (2019-04-08), EU…"; 300k external ids; a sanctioned company from GDELT resolves to the same node |
| 2. Missions table + relevance + two-tier collection + alerts | 3 | mission "Gulf" (SA, IR, YE, AE, QA + 20 regional feeds): feed and globe show only Gulf items; a watchlist hostile event raises an alert; switching to "General" restores everything |
| 3. Mission UI (switcher, editor) | 1½ | create a mission in the browser without touching the DB |
| 4. SPOTREP connector + form | 1 | an uploaded report yields structured events without the LLM; its NOTES yield quoted events |
| 5. Self-maintaining names | 1 | review queue shrinks and stays flat over 3 days |
| 6. Access control design note (build later) | ½ | `design/access_control.md` |

≈ 9 days. Running cost: OpenSanctions pull is free; mission-tier extraction with a stronger
model ≈ +$1–2/day depending on volume.

## 6. Not covered
Golden-set scoring (verbs phase 2), situation briefs, wall mode, relay deployment, non-English
translation, multi-user collaboration (comes with access control).
