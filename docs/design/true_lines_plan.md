# True lines — the web draws only what an article actually says

**Status:** BUILT 2026-09-19 — hygiene (story-day dedup, verbal class, is_root), reader agent
(`gdelt_reader_v1`, 400/day), verified/wire ledgers in relations, API and UI (solid = verified, faint =
wire behind a toggle, off by default on the globe). First hour: 19 articles read → 17 analysed → verified
events with quotes ("A Russian barrage of missiles and drones… injured at least 19"; "The House approved
the sanctions package targeting Russian officials"); relations 500 → 67 (34 verified); the Ukraine–Russia
green line is gone; screenshot `ui_research/web_11_verified_arcs.jpg`. Countries now sit at their capital
on the globe (Wikidata's point for Russia is in Siberia). Re-audit (step 4) due after a full day of reading.
Was: PLAN — after `arc_accuracy_audit.md` (green arcs ≈ 30 % right, red ≈ 70 %).
**Follows from:** `web_map_and_wheel_plan.md` (BUILT), `graph_accuracy_implementation_plan.md` (BUILT).
**Principle (unchanged since 09-15):** *you trust the quote, not the AI.* Today the strongest lines
have no quote behind them — they are GDELT's word-order guesses, syndicated copies included.

---

## 1. What was measured

| Question | Result | Source |
|---|---|---|
| Are GDELT events right? | hostile/material ≈ 70 %; cooperative/verbal ≈ 30 %; Ukraine–Russia "cooperative" 0/7; Russia–China "hostile" 0/12 (stories about Iran / Austria / US Air Force) | `arc_accuracy_audit.md` |
| Does GDELT know its own confidence? | mentions file `Confidence`: mean 39–40; only **16 %** of events ≥ 70; no difference between verbal and material; `IsRootEvent` = 1 for 57–60 % | slot `20260919160000` export + mentions |
| Does syndication inflate? | 4,722 pair-events → 3,700 distinct (pair, action, day); EU–Carney 62 → ~4 | `events` |
| Can a cheap model verify a claim against the article? | **5 / 5 correct**: rejected "Russia gives military aid to Ukraine" (*"struck a ship carrying supplies for Ukraine"*), "Russia releases persons", "China threatens Russia"; confirmed "Russian strikes killed eight civilians" with the quote | gpt-4o-mini, temperature 0, article via `fetch_body` |
| How much would reading cost? | pairs with ≥ 3 story-days: 344 pairs, 2,880 URLs / 7 days ≈ **400 articles/day ≈ $0.35/day** at 4o-mini; analysts already do 398 articles/day | `events`, `analysis_queue` |
| How many of our own (quoted) events exist? | 92 in 7 days, from 4 feeds | `events` |

Conclusion: filtering GDELT harder helps a little (fewer copies, fewer "said" rows); it cannot fix
wrong direction or wrong story, because nothing reads the sentence. **Reading is cheap and works.**

## 2. Design: GDELT finds the articles, PIA reads them, only what is read draws a line

```
GDELT export ──► candidate events (as today, hygiene tightened)          origin = gdelt  (wire)
      │
      └─► reader queue: the URLs behind pairs that would become lines
                │  budget 400/day, robots/paywall aware, one read per URL
                ▼
           report (source_agent = gdelt_reader_v1, body fetched) ──► analyst (existing) ──► events with quotes   origin = llm
                                                                                                    │
relations ◄─────────────────────────────────────────────────────────────────────────────────────────┘
   verified_count / wire_count per (pair, kind); weight from verified; wire only as a hint
globe arcs + wheel lines: drawn from verified; wire-only pairs faint (or hidden) and labelled "wire"
```

The analyst, prompt, resolver, card, evidence panel are all reused. The only new agent is a
reader that turns GDELT URLs into reports. The wire events stay: they are what decides *which*
articles are worth reading, and they show on the card as "wire signals".

### 2.1 Hygiene on the wire (GDELT agent)
- **Story-days, not copies:** dedup key = `(pair, action, day)`; the outlet list accumulates on
  the event (`source_id` stays the first outlet; `outlets` jsonb gains the rest; `confidence`
  rises with distinct outlets).
- **`IsRootEvent`** (column 25) stored; events that are not the article's main event never
  feed relations.
- **Verbal classes** (roots 01 statement, 02 appeal, 03 intent, 051 praise, 052 defend, 11
  disapprove/accuse, 12 reject, 13 threaten) keep their kind but get `weight_class = 'verbal'`;
  they never draw a line on their own.

### 2.2 The reader (`gdelt_reader_v1`, new agent in `pia`)
- Every 15 min: candidate URLs = source URLs of wire events whose pair has ≥ 3 story-days in
  the last 7 days (or ≥ 1 material event with ≥ 2 outlets), not yet read, not paywalled, robots
  allowed; ordered by pair strength; capped by `READER_DAILY_BUDGET` (default 400).
- Each URL → `intelligence_records` row (`source_agent = gdelt_reader_v1`, `source_id` = outlet,
  `body_status`, `metadata.via = 'gdelt'`, `metadata.wire_event_ids = [...]`) → normal
  `analysis_queue` job → the analyst extracts events with quotes (`origin = llm`).
- Articles that cannot be fetched (404, paywall, robots) are marked `unreadable`; their wire
  events stay wire.

### 2.3 Relations and the picture
- `relations` gains `verified_count`, `wire_count`, `verified_topics`; `weight` = Σ over
  **llm** events only (decay as today) + 0.1 × wire material events (so a strong wire-only pair
  still surfaces faintly); `label`/`topics` prefer verified.
- Noise bar becomes: **a line needs ≥ 1 verified event**, or ≥ 5 wire material story-days
  from ≥ 3 outlets (then drawn faint, labelled *wire*).
- API: entity card, evidence, `/graph/network`, `/kg/web/overview` return both counts; the
  card sentence reads *"diplomacy (12 verified · 40 wire) — since 09/14"*.
- UI: globe arcs and wheel lines: width from verified; wire-only = thin, 40 % alpha, dashed;
  a **"wire"** toggle next to hostile/coop (off by default on the globe, on in the wheel);
  evidence panel groups *Verified (with quotes)* above *Wire signals*.

### 2.4 What happens to the numbers
Expected after one day: the Ukraine–Russia green line vanishes (no article says they
cooperated); Ukraine–Russia red stays with quotes; China–US keeps a verified green (visit,
handover); EU–Carney becomes a thin verified line with 2–4 events; Russia–China hostile
disappears. Total lines drop from ~180 (7 d, ≥ 5) to perhaps 40–60 verified — the honest size.

## 3. Changes

| Repo | Change |
|---|---|
| `pia` | `gdelt_agent`: story-day dedup, outlets accumulation, `is_root`, `weight_class` (migration 007: `events.is_root bool`, `events.outlets jsonb`, `events.weight_class text`); new `agents/reader_agent.py` (+ compose service, env `READER_DAILY_BUDGET`); `kg/relations.py`: verified/wire split (migration 007: `relations.verified_count`, `wire_count`, `verified_topics`); noise bar; tests for dedup, class, reader selection |
| `pia-api` | card / evidence / graph / overview carry `verified_count`, `wire_count`; evidence groups events by origin |
| `pia-ui` | card sentence; evidence sections; `WebLayer` and `WebView` line style by verified share; "wire" toggle |
| docs | `STATUS.md`: what a line means now |

## 4. Order and verification
1. Migration 007 + GDELT hygiene + tests → replay 7 days (`gdelt_backfill.py`) → `select count(*)` of pair-events drops to ~3,700; EU–Carney ≤ 6.
2. Reader agent → after 2 hours: ≥ 100 `gdelt_reader_v1` reports with bodies; `events origin='llm'` growing; sample 10 verified events by hand against their quotes.
3. Relations split + API + UI → globe: Ukraine–Russia red solid with quotes, no green; Russia–China gone; screenshot `web_11_verified_arcs.jpg`.
4. Audit again the same way as today (7 random events behind the 5 strongest verified lines) → target ≥ 90 % right.

Effort: 1 (½ day) · 2 (½ day) · 3 (1 day) · 4 (1 h). Running cost ≈ $0.35/day extra.

## 5. Not covered
- Non-English articles: read as-is (4o-mini copes with major languages); no translation layer.
- GDELT GKG / mentions confidence: measured, not useful enough to add a second download.
- Re-verifying the *existing* wire events one by one: replaced by reading their articles, which
  yields every event in the article, not just the claimed one.
