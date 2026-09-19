# Web View Redesign — Research and Plan

**Status:** BUILT 2026-09-19, verified in the browser (`ui_research/web_0*.jpg`): click → card, click a line → evidence, +expand / focus / breadcrumb, filters, dashed facts, curved multi-edges, GDELT noise bar. Open: real-mouse click precision on thin edges (hover precision set to 10 px); aviation v2 alert flood is the owner's agent and untouched.
**Follows from:** `knowledge_web_implementation_plan.md` (K7 delivered a first web view) and the owner's
report: *"When I clicked on it, it should show the details, and the current design is not intuitive."*

## 1. What I found (evidence)

### 1.1 The system today
- The database was recreated on 2026-09-18 (rows start 04:21Z that day); the 59,911-item Wikidata
  backbone was lost. Its cache (`data/wikidata_backbone.jsonl`) survived; an offline reload was started.
- New work by the owner since 09-15 (on `main`): real OpenSky ADS-B and AISHub agents (`03f9743`),
  a basemap switcher and depth-test fix in the UI (`f5b6e17`), migration 003 (`opensky`, `aishub`
  sources). `pia-api` is still served from the `knowledge-web` build.
- Data: 2,908 Wikidata entities (before reload), 713 mentioned, 1,814 events (125 from articles,
  1,689 from GDELT), 7,909 relations (519 from events, 7,178 Wikidata facts, 212 co-mentions),
  80 FAILED jobs — all `402` from OpenRouter (**the account ran out of credit**).

### 1.2 The web view, measured
| Problem | Evidence |
|---------|----------|
| Click on a node **expands** it; details only appear on a second click | `WebView.tsx:92-96` (`expand`: `if (expanded.has(id)) onOpenEntity(id)`) |
| The header names the wrong root ("Poland" on Ukraine's web) | root = first node with `val === 30`; `val = min(30, 3 + mentions)` saturates for any entity with ≥ 27 mentions (`routers.py:463`) |
| Ukraine–Russia drawn **green** though the card says "attack · 27×" | two relations (HOSTILE 27 events, COOPERATIVE 19) → two overlapping lines; the last painted wins |
| Wikidata facts and observed events look the same | one line style for all sources; `relations` holds 7,178 static facts vs 519 event-based |
| Memberships/locations drown the few edges that matter | per-entity API returns up to 300 edges by weight; Wikidata facts weigh 1.0, most event edges 0.3–2 |
| GDELT noise reaches the web | "Ukraine attack United States 2×", "NATO attack Ukraine 1×", "Ukraine coerce Delhi 1×": low-count pairs from mis-coded wire stories |
| Labels: all on (clutter) or off | thinning rule `val >= 5 or ≤ 25 nodes or zoom > 1.6` (`WebView.tsx:drawNode`) |
| No way back after expanding | no breadcrumb / re-root |
| Evidence opens in a second column inside the overlay, separate from the entity card | `WebView.tsx:177` |
| Not related to the web, but visible: 141 alerts, feed all "Military aircraft:" | aviation v2 emits a HIGH report per military aircraft per poll |

The Chrome extension's synthetic clicks do not reach the canvas (real mouse clicks do); interaction
was verified by dispatching pointer events.

## 2. Interaction model (the fix)

1. **Click = select.** Selecting a node highlights it and its edges and puts its **entity card in
   the right inspector column** (same card as on the globe). Expansion is explicit: a `+` button
   in the card header or double-click on the node.
2. **Click an edge = evidence in the same column** (events with quotes, sources, Wikidata facts,
   shared reports), with "open A" / "open B".
3. **Hover** shows a tooltip (name · kind · mentions); labels always on for root, selected node and
   its neighbours; others on hover or when zoomed in.
4. **Focus / breadcrumb.** "Focus here" re-roots the web on the selected node; a breadcrumb in the
   web header (Ukraine › Zelenskyy › …) navigates back.
5. **Facts vs. observations.** Dashed = Wikidata fact; solid = observed events (width = count);
   dotted grey = co-mentions. Colour = kind. When a pair has several relations, draw **one curved
   line per relation** (no overlap) and let the strongest by weight sit on top.
6. **Filters in the web header**: kind toggles (HOSTILE, COOPERATIVE, ROLE, OWNERSHIP on by
   default; MEMBERSHIP, LOCATED, MENTIONED_WITH off), "Wikidata facts" toggle (on), and a
   *minimum events* slider (default 2 for GDELT-only pairs, 1 when an article backs the pair).
7. **Web in the centre cell, never an overlay over the inspector.** Dashboard: the web replaces
   the globe cell; the right column stays. Archive: a `WebWorkspace` (web + inspector column).
8. **Card wording**: "27 attacks reported (bbc.co.uk, aljazeera.com, gdelt) since 12 Sep" instead
   of "attack · 27×".

## 3. Changes

### API (`pia-api`)
- `GET /graph/network/{key}`: add `kinds=` (csv), `sources=` (csv of events|wikidata|cooccurrence),
  `min_events=`, `limit=` (default 60); rank event-based edges above facts; return `source`,
  `event_count`, `sources` (outlets) per link; fix root marking (`is_root: true`, not `val === 30`).
- `GET /kg/entities/{key}`: each relation entry gains `sources` (distinct outlets from events) and
  `first_seen/last_seen` already present → the UI can write the sentence.
- Noise bar in `kg/relations.py`: pairs whose events are **only GDELT** need ≥ 3 events (or
  |tone| ≥ 7) to become a relation; single-source, single-event pairs stay as events but not edges.

### UI (`pia-ui`)
- `Selection` gains `{ kind: 'evidence', a, b }`; `InspectorColumn` component renders
  report / camera / entity / evidence bodies (extracted from Dashboard so Archive can reuse it).
- `WebView` rewrite: props `entityKey`, `onSelectEntity`, `onSelectEvidence`, `onFocus`;
  breadcrumb; filters; curved multi-edges; dashed/solid/dotted styles; hover tooltip; label rules;
  no internal evidence panel.
- `EntityInspector`: `+ expand` and `focus` actions when opened from the web; relation sentence.
- Dashboard: web replaces the globe cell (globe layers keep their state); Archive: `WebWorkspace`.

### Data hygiene (small, needed for the web to read well)
- Aviation v2: one report per aircraft per 24 h, priority NORMAL unless squawk 7500/7600/7700
  (owner's agent; propose the rule, keep the feed usable).
- Reload the backbone offline (started).
- OpenRouter credit: the 80 FAILED jobs will retry once credit is added.

## 4. Order and verification
1. API changes + unit tests for the filter parameters → `curl …/graph/network/Q212?kinds=HOSTILE`
   returns only hostile edges, root marked, sources listed.
2. `InspectorColumn` + `Selection.evidence` → Dashboard still type-checks; report/camera unchanged.
3. `WebView` rewrite → in the browser: click Russia → card in the column; click the edge → evidence;
   `+` expands; breadcrumb back; Ukraine–Russia shows a red solid line (27) and a green one (19).
4. Archive workspace → same behaviour from `/archive`.
5. Relations noise bar → "Ukraine attack United States 2×" disappears unless a third source appears.
6. Screenshots into `ui_research/web_*.jpg`; commit; push.
