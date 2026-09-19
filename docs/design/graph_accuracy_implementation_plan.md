# Graph accuracy — implementation plan

**Status:** BUILT 2026-09-19 (A, B, C, D coded; 70 unit tests pass). Verification pending the
7-day GDELT backfill and OpenRouter credit (agents are stopped until the owner adds credit).
**Incident, same day:** rebuilding the API container recreated Postgres and the database came
back empty. Root cause: `docker-compose.yml` mounted the data volume at `/var/lib/postgresql/data`
while the timescaledb-ha image keeps its cluster at `/home/postgres/pgdata/data` — the data had
never been on the volume (this also explains the 2026-09-18 wipe). Fixed (volume path), verified
by a forced recreate; schema re-initialised; backbone reloaded from cache in ~2 min (two-phase
loader + joint class walk, was 11 items/min); GDELT replayed for 7 days. Lost: reports/events of
09-18/19, the 161 review names, 1 feedback row.
**Deviations from the plan:** `events.kind` column added (migration 005) so API and relations
job no longer keep their own action→kind tables; class cache `data/wikidata_classes.jsonl`;
aviation flood rule applied (NORMAL, one report per aircraft per day) + 7-day `flight_tracks`
retention (migration 006).
**Follows from:** `graph_accuracy_usa_research.md` (findings, numbers) and `web_view_redesign_plan.md`.
**Goal:** the USA web stops saying "friend and enemy of everyone" and starts saying *what* each
relationship is about, with evidence that was actually written by someone.

---

## 0. Evidence the plan rests on (measured today)

| Fact | Where |
|---|---|
| USA events: 631 GDELT, 15 LLM; USA web = 41 COOPERATIVE + 19 HOSTILE links, 11 pairs with both | `events`, `/api/v1/graph/network/Q30` |
| GDELT agent reads only the 2-digit root code (col 28) and no actor type (col 12 / 22) | `gdelt_agent.py:25` `COL` |
| Root 05 in a live export = 051 "praise or endorse" 82×, 057 "sign agreement" 30× | scratchpad `20260915114500.export.CSV` |
| 51 / 96 rows with Actor1Name = UNITED STATES have no Actor1Type1Code; USA "attack" rows were a redistricting story, a TV article, a poker tournament | same file |
| 37 USA-actor GDELT events with no target (domestic stories); "United States — attack — Garfield County, Oklahoma" = murder trial | `events` ⋈ `intelligence_records` |
| GDELT `quote` is synthesised: `f"{a1} {action} {a2} — {geo}"` | `gdelt_agent.py:119-121` |
| Alias `china` → Q29520 (PLACE, 81 sitelinks) + 3 towns; **Q148 has no alias "china"** (`china pr, cn, prc, …`) | `entity_aliases` |
| Continents Q46 Europe, Q15 Africa and Q1355327 "Executive Office of the President" appear as USA partners | graph response |
| Relations are grouped by `(pair, kind)` only; no subject | `kg/relations.py:22-31` |
| LLM prompt has 23 actions and no topic; "US granted visas to Iranian officials" → `OTHER` | `core/nlp.py:96-97`, `events` |

---

## A. GDELT precision (`pia`)

### A1. Read the columns that carry meaning
`COL` gains: `code=26` (EventCode, 3–4 digits), `base=27`, `quad=29`, `a1type=12`, `a2type=22`,
`nsources=32` (already `sources`), `a1kg=8`/`a2kg=18` (known-group codes such as UNO, NAT, EEC).

### A2. Finer actions from the full CAMEO code
`kg/ontology.py`: keep the 23 actions the LLM uses; add a **`CAMEO_CODE_TO_ACTION`** table (most
specific prefix wins) with new finer actions, each with its relation kind and tone. Additions:

| CAMEO | Action | Kind / tone | Topic (see C) |
|---|---|---|---|
| 051 | PRAISE | COOPERATIVE +1 | diplomacy |
| 052 | DEFEND | COOPERATIVE +2 | diplomacy |
| 054 / 161 | RECOGNIZE / CUT_RELATIONS | COOPERATIVE +4 / HOSTILE −4 | diplomacy |
| 057 | SIGN_AGREEMENT | COOPERATIVE +6 | diplomacy (or trade/military/nuclear from 061/062/… if base 06) |
| 036, 046 | NEGOTIATE | COOPERATIVE +3 | diplomacy |
| 041 | CALL (phone) | COOPERATIVE +1 | diplomacy |
| 042 / 043 | VISIT / HOST | COOPERATIVE +2 | diplomacy |
| 061 / 1211 | TRADE_COOPERATE / REJECT_TRADE | COOPERATIVE +4 / HOSTILE −3 | trade |
| 062 / 072 | MILITARY_COOPERATE / MILITARY_AID | COOPERATIVE +5 | military |
| 071 / 073 | ECONOMIC_AID / HUMANITARIAN_AID | COOPERATIVE +5 | economy / humanitarian |
| 085 / 1233 / 163 / 1312 | EASE_SANCTIONS / REFUSE_EASE / SANCTION / THREATEN_SANCTION | ±6 | sanctions |
| 0841 / 173 / 174 | RELEASE / ARREST / DEPORT | ±5 | detention |
| 0871 / 196 | TRUCE / VIOLATE_CEASEFIRE | +6 / −7 | military |
| 138x / 150–154 | THREATEN_FORCE / MILITARY_POSTURE | HOSTILE −5 / −3 | military |
| 176 / 155 | CYBER_ATTACK / CYBER_MOBILIZE | HOSTILE −7 / −3 | cyber |
| 181 / 185 / 186 | ABDUCT / ASSASSINATION_ATTEMPT / ASSASSINATE | HOSTILE −9 | security |
| 183 | BOMBING | HOSTILE −9 | security |
| 190 / 193 / 194 / 195 | ARMED_ATTACK / SMALL_ARMS / ARTILLERY / AIRSTRIKE | HOSTILE −9 | military |
| 191 / 192 | BLOCKADE / OCCUPY | HOSTILE −8 | territory |
| 201–204 | MASS_EXPULSION / MASS_KILLING / ETHNIC_CLEANSING / WMD | HOSTILE −10 | human_rights |
| 1121–1125 | ACCUSE (kept) with topic crime / human_rights / aggression / war_crimes / espionage | HOSTILE −3 | per code |
| 010–019, 020–029 | STATEMENT / APPEAL (kept) | — | other |

Unmapped codes fall back to the root as today. `events.code` stores the raw code (migration 004).

### A3. Who counts as "the country"
For a resolved **COUNTRY** actor/target, keep the row only when its `Actor*Type1Code` ∈
`{GOV, MIL, LEG, SPY, JUD}` **or** the name is a government seat / known group (a1kg set).
Untyped country actors are stories *about* a place → no event (the report is still created).
Region codes (`EUR, AFR, ASA, NMR, SAM, MEA, WST, LAM, CRB, SAS, EEC, BLK, …`) never become
actors; `EEC`/`EUR` with type IGO → European Union (Q458).

### A4. Evidence that exists
- `quote = NULL` for GDELT events. The evidence panel shows: **headline of the source page**
  (fetched `<title>`, first 64 KB, 5 s timeout, cached by URL, best effort), outlet, URL, and
  *"coded by GDELT as 051 — praise or endorse"*.
- Location: keep `ActionGeo` only when its country is one of the two actors' countries; otherwise
  the event has no `geo` (the report keeps it, labelled `geo_source = 'gdelt-dateline'`).
- Symmetric actions (MEET, NEGOTIATE, CALL, SIGN_AGREEMENT, COOPERATE, AGREE, TRUCE) dedup on the
  unordered pair, so "Washington agree Iran" and "Iran agree Washington" are one event.
- `confidence` = f(NumSources) instead of NumMentions (≥ 3 sources → 0.8).

### A5. Backfill
`scripts/gdelt_backfill.py --days 7`: deletes `origin='gdelt'` events (not reports), replays the
export files from GDELT's master list through the new agent code, rebuilds relations. Reports
are matched by URL so nothing is duplicated.

---

## B. Identity (`pia`)

1. **Country by code, never by name search.** In `gdelt_agent._actor`: if `a1cc` is a real ISO3
   and the name is the country itself (norm ∈ that country's aliases, or type ∈ GOV/MIL/LEG/SPY),
   resolve **directly** via `iso3 → Q-id`. Alias search is only for non-country actors.
2. **Country beats place.** `resolver._lookup_local`: for roles ACTOR/TARGET, rank `kind =
   'COUNTRY'` above PLACE before sitelinks. Fixes "China" everywhere, not only GDELT.
3. **Short names as aliases.** `scripts/fix_country_aliases.py`: for all 264 COUNTRY entities add
   Wikidata P1813 (short name) and the GeoNames country name (`china`, `united states`, `russia`,
   `south korea`, `syria`, `vietnam`, …). Verify `select … where alias_norm='china'` includes Q148.
4. **Continents are not actors.** Q15 Q46 Q48 Q49 Q18 Q538 Q51 get `metadata.continent = true`;
   the resolver returns them only for role LOCATION.
5. **Government bodies collapse to their country as actor/target.** Using `wikidata_classes`
   (P279 ancestors: government agency Q327333, ministry Q192350, executive office…), when an
   ORG whose `country_qid = X` is an ACTOR/TARGET, the *event* uses X; the *mention* keeps the
   org. Same rule the prompt already gives the LLM (rule 5). Removes "United States ↔ Executive
   Office of the President".

---

## C. Topic — what the relationship is about

### C1. Schema (migration `004_event_topic.sql`)
```sql
ALTER TABLE events ADD COLUMN topic text, ADD COLUMN code text;
CREATE INDEX events_topic_idx ON events (topic);
ALTER TABLE relations ADD COLUMN topics jsonb NOT NULL DEFAULT '{}'::jsonb;  -- {"nuclear": 26, "military": 19}
```
Controlled list (`kg/ontology.py: TOPICS`): `nuclear, sanctions, trade, territory, military,
security, diplomacy, detention, migration, energy, technology, cyber, elections, human_rights,
humanitarian, economy, health, environment, crime, other`.

### C2. Producers
- **GDELT**: topic from the code table (A2); `other` when unmapped.
- **LLM**: prompt gains `"topic": "ONE OF THE TOPICS"` per event, with two lines of guidance
  ("what the action is *about*, not the action itself"). `OTHER` events with a clear topic are
  still worth keeping (the visas example → action STATEMENT? no: action `AID`? → keep `OTHER`,
  topic `migration`), so the card can say something.
- **Relations**: `rebuild()` adds `jsonb_object_agg(topic, n)` per `(pair, kind)`; the noise bar
  is unchanged. `label` becomes the top topic.

### C3. API (`pia-api`)
- `/kg/entities/{key}` relation entries: `topics: [{topic, count}]` (top 3).
- `/graph/network/{key}` links: `topics` (top 3) and `label = top topic`.
- `/kg/relations/{a}/{b}` events: `topic`, `code`, `code_label`; GDELT events return `quote: null`
  and the report headline, so the UI never prints a synthesised sentence.

### C4. UI (`pia-ui`)
- Card sentence: *"diplomacy (26) · military (19) with Iran — 45 events (aljazeera.com, gdelt)
  since 09/18"*.
- Evidence panel: grouped by topic; GDELT rows show headline · outlet · "GDELT 051 praise or
  endorse" instead of a quote; LLM rows show the quote as today.
- Link hover tooltip: kind · top topic · count.

---

## D. Web UX (`pia-ui/WebView.tsx`)

1. **Sectors, not a star.** A custom d3 force places 1-hop neighbours by relation kind: hostile
   left, cooperative right, role/ownership below, Wikidata facts above (angle target per node,
   strength 0.15); expanded nodes inherit their parent's sector. Two-kind pairs sit on the
   boundary.
2. **Labels always on** for the root, the selected node and its neighbours, and the top 12 by
   weight; others on hover or when zoomed in (today: only root until hover).
3. **Legend** in the header: node colours (country / org / person / place / vessel) and line
   styles; a **topic filter** row built from the links' topics.
4. **One ribbon per pair when both kinds exist**: keep the two curved lines but scale each width
   by its share, and put the top topic on the thicker one's hover.

---

## E. Order and verification

| Step | Check (command / screen) | Expected |
|---|---|---|
| A1–A4 + unit tests for the code table and actor gating | `pytest tests/unit/test_gdelt_codes.py` | 051 → PRAISE/diplomacy; untyped USA actor dropped; region codes dropped |
| A5 backfill 7 days | `select action, count(*) from events where origin='gdelt' group by 1` | AGREE ≪ before; PRAISE, VISIT, SIGN_AGREEMENT present; `select count(*) … quote is not null and origin='gdelt'` = 0 |
| B1–B5 | `select qid from entities e join entity_aliases a using(entity_id) where alias_norm='china' and kind='COUNTRY'` | Q148; USA network has one China, no Europe/Africa/EOP |
| C | `/api/v1/kg/entities/Q30` | Iran entry shows `topics`; card sentence reads "diplomacy (n) · military (n)" |
| D | screenshot `ui_research/web_05_usa_sectors.jpg` | hostile left, cooperative right, labels readable, legend visible |
| Regression | 41 existing unit tests + 12 API tests | pass |

Effort: A ≈ 1 day, B ≈ ½ day, C ≈ 1 day, D ≈ 1 day.

## F. Not covered
- LLM extraction stays frozen until OpenRouter credit is added (owner); C2's prompt change is
  verified on the 88 failed jobs once they retry.
- GDELT GKG (themes, 15-min, large) could give richer topics later; not in this plan.
- Non-English sources / translation; the aviation feed flood (separate small fix).
