# The web, readable at both distances — "web layer on the globe" and "wheel"

**Status:** BUILT 2026-09-19 — wheel (`ui_research/web_08_wheel_usa.jpg`, `web_08b_wheel_iran_dashboard.jpg`)
and globe web layer (`web_09_globe_web.jpg`, `web_10_globe_arc_evidence.jpg`); person countries backfilled
(1,917 / 1,960). Open: label declutter on the globe at far zoom (Cesium has none; Europe's labels overlap),
arcs win picks over labels they cross. Written after the owner's verdict on the force graph: *"not easy to
use, due to messiness"* and *"when you look from far it should show it too, but more clearly and nicely."*
**Follows from:** `graph_accuracy_implementation_plan.md` (data is now clean; the picture is not).
**Goal:** replace the force-directed graph with two deterministic pictures of the same data:
a **web layer on the globe** (far) and a **wheel around one entity** (near). Nothing moves on its
own, every visible node is labelled, no line crosses another it does not need to.
**Decision 2026-09-19 (owner):** the far view lives **on the Cesium globe**, not in a flat 2-D map —
one screen, globe first, the web as arcs on it. The flat "world map" idea below is replaced by §3.1.

---

## 1. What is wrong with the current picture (browser, `web_05`–`web_07`, Russia session)

| Problem | Cause |
|---|---|
| Layout re-shuffles after every action; you lose your place | d3 force simulation re-heats on every data change |
| Curved red + green lines between the same pair, 30 others on top → hairball | one curve per (pair, kind); force layout ignores line crossings |
| Half the nodes unlabelled | labels thinned to avoid overlap, because positions are arbitrary |
| "Hostile left / cooperative right" does not hold | a sector force competes with link + charge forces |
| Two rows of chips, a slider, a legend, a sentence | too many controls for a screen that answers one question |
| From far away it says nothing | a 1-hop star around one node has no "far" |

Root cause: a force graph is a tool for *seeing a whole network's shape*; what the owner does is
*look at one thing* (near) or *look at the world* (far). Neither needs physics.

## 2. What the data supports (measured 2026-09-19)

- 301 entities active in the last 7 days: 162 countries, 94 orgs, 21 persons, 20 vessels, 4 places.
- Coordinates: 212 / 222 countries have `primary_geo`; 180 of the 301 active entities do.
- Country link: 91 of 139 active non-country entities have `country_qid`; **persons have none**
  (0 / 1,620 — P27 citizenship is not imported). Fix in the plan (§4.1).
- Event relations: 382; ≥ 5 events 203; ≥ 20 events 26; ≥ 50 events 6 → a far view with
  "≥ 20" shows ~26 lines, "≥ 5" ~200. Good thresholds for semantic zoom.
- `react-force-graph-2d` accepts fixed nodes (`fx`, `fy`) with the simulation off: zoom, pan,
  hit-testing, hover and canvas drawing stay; no new dependency.

## 3. Design

### 3.1 Web layer on the globe (far) — *what is happening between whom, where?*
- A new globe layer **WEB** in the layer rail (next to Reports, Events, Cameras), with a count
  ("Web (26)" = arcs shown). Data from `GET /kg/web/overview` (§4.2).
- **Nodes on the globe**: countries at their `primary_geo`; organisations at their HQ
  (`primary_geo`) or beside their country; persons beside their country (P27, §4.1); vessels at
  their last position when known. Drawn as billboards sized by activity in the window, coloured
  by kind (same palette), labelled with Cesium's label collision (top 30 always labelled).
- **Arcs**: one polyline per pair, arc height ∝ distance, width = log(events), colour = the
  dominant kind; both kinds present → two thinner parallel arcs (red / green). Back-side arcs
  are hidden (depth test), which also keeps the far view clean.
- **Semantic zoom by camera height**: > 8,000 km: countries + IGOs, arcs ≥ 20 events, top-30
  labels; 2,000–8,000 km: arcs ≥ 5, orgs appear, top-100 labels; < 2,000 km: everything.
- **Window**: 24 h / 7 d / 30 d / 90 d (defaults to 7 d) in the layer's small toolbar; kind
  toggles and topic chips there too. Same `Selection`: click an arc → evidence panel; click a
  node → entity card; the card's "open web" → the wheel.
- The layer is memoised like the camera layer (constant Cesium objects; rebuild only on data
  change) so 400 billboards + 200 arcs do not freeze the page.

### 3.2 Wheel (near) — *who is around this one thing?*
- The entity in the centre; partners on a ring at fixed angles by sector: **hostile 150°–210°
  (left), cooperative −30°–30° (right), role/ownership bottom (60°–120°), Wikidata facts top
  (240°–300°)**. Inside a sector, partners are ordered by weight (strongest nearest the
  horizontal axis) and spaced evenly; a sector with > 14 partners gets a second, outer ring.
  A pair with both hostile and cooperative goes to the side with more events; its line is the
  two-stroke line.
- Every partner labelled (the ring guarantees room: label radial, outside the ring).
- **Expand** (double-click / `+` on the card): the partner's own partners fan out in a small
  outer arc centred on that partner's angle, dimmed; **focus** re-centres (breadcrumb, as now).
- **Ranked list** on the left of the wheel (inside the web cell, 300 px): partner · kind · top
  topics · events · sparkline (events per day, 14 d) · last seen; sortable; typing filters the
  list and highlights on the wheel; click → card, as clicking the node.
- Same filters row; the `≥ events` slider goes; the noise bar in the data already handles it.

### 3.3 Navigation between the two
- **Far** = the globe with the WEB layer on. **Near** = the wheel, which replaces the globe cell
  (as the web does today) when opened from a card, the archive list, or a node on the globe.
- Breadcrumb in the wheel: *Globe › United States › Iran*; `ESC` / *Globe* → back to the globe
  with the camera where it was.
- Card and evidence panel unchanged; `Selection` unchanged.

## 4. Changes

### 4.1 Data (`pia`)
- `wikidata.parse_entity`: `country_qid` for persons from **P27** (citizenship) when P17 is
  absent; one-off script `scripts/backfill_person_country.py` for the 1,620 loaded persons
  (batches of 50 via the entity API, ~35 requests).
- `relations`: nothing new — `topics`, `event_count`, `first/last_seen` already exist.

### 4.2 API (`pia-api`)
- **`GET /kg/web/overview?window=7d&min_events=5&limit=400`** → `{nodes:[{id, qid, name, kind,
  lat, lon, country_id, activity}], links:[{source, target, kind, event_count, weight, topics,
  outlets, hostile_n, coop_n, last_seen}]}`. Nodes = entities with ≥ 1 event in the window (plus
  the countries they hang from); `activity` = events in the window; `lat/lon` = own `primary_geo`,
  else the country's point (the UI offsets orbiting nodes); links from `relations`
  (`source='events'`) between them, `event_count ≥ min_events`, ordered by weight, capped.
  `hostile_n` / `coop_n` come from the two kind rows of the same pair so the UI can draw the
  split arcs.
- **`GET /graph/network/{key}`** (wheel): add `series` per event link — events per day for the
  last 14 days (for the sparkline) — and keep everything else.
- Both endpoints: `lat/lon` from `primary_geo` (`ST_Y/ST_X`), `country_id` = entity_id of the
  `country_qid` when loaded.

### 4.3 UI (`pia-ui`)
- New `components/web/`:
  - `wheelLayout.ts` — `wheelLayout(root, links)` (sectors, rings, orbit offsets for orbiting
    nodes on the globe) → `{id → {x, y}}`; pure, unit-tested with Vitest (first UI tests).
  - `WheelCanvas.tsx` — `react-force-graph-2d` with all nodes fixed (`fx/fy`), `cooldownTicks={0}`,
    `enableNodeDrag={false}`; custom painters (split stroke, radial labels).
  - `WheelView.tsx`, `PartnerList.tsx`, `WebHeader.tsx` (one row).
  - `WebView.tsx` becomes wheel + breadcrumb and keeps the `WebViewHandle` (`expand`, `focus`)
    so Dashboard / Archive / InspectorColumn need no change.
- `components/globe/layers.tsx`: a memoised **`WebLayer`** (billboards + polyline arcs, semantic
  zoom from the camera height, click → `Selection`), fed by a `useWebOverview(window)` hook;
  `LayerRail` gains the WEB toggle with its count and a small toolbar (window, kinds, topics).
- Delete the force-based drawing, curvature code and sector force.

### 4.4 Order and verification
| Step | Check | Expected |
|---|---|---|
| 1. `wheelLayout` + `WheelView` + `PartnerList` | open United States from the archive | ring with all 41 partners labelled, hostile left / cooperative right, list sorted by events; nothing moves after load; screenshot `web_08_wheel_usa.jpg` |
| 2. Expand / focus / breadcrumb | double-click Iran; click *United States* in the breadcrumb | outer arc around Iran; back restores the ring exactly |
| 3. `/kg/web/overview` + `WebLayer` | toggle WEB in the layer rail | arcs between countries on the globe, ≥ 20 events only when far, top-30 labels; zoom in → more; back-side arcs hidden; screenshot `web_09_globe_web.jpg` |
| 4. Person country backfill | `select count(*) from entities where kind='PERSON' and country_qid is not null` | > 1,200 |
| 5. Click a country on the globe → wheel → ESC | breadcrumb *Globe › Iran*; ESC returns to the globe with the camera unchanged | |
| 6. Tests | `npx vitest run` (layout), 71 unit + 12 API | pass |

Effort: wheel + list 1 day; globe web layer + overview endpoint 1½ days; person countries ½ day.

## 5. Not covered
- A "timeline scrubber" for the window (COP phase 3) — the window switch is four buttons for now.
- Clustering / community detection for the far view — geography is the grouping; revisit if a
  mission is not geographic (e.g. a supply chain).
- A flat 2-D map mode for the wall (if 3-D arcs prove hard to read on a TV) — decide after seeing it.
- Touch / wall-screen interaction for the wheel (phase 5).
