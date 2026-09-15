# UI/UX and Frontend Architecture Research

**Status:** RESEARCH — for discussion, nothing built yet.
**Follows from:** [`../fix_implementation_plan.md`](../fix_implementation_plan.md) (system now runs end to end).
**Goal stated by the owner:** make the UI "more professional, military real one".
**Evidence:** screenshots in `ui_research/` taken from the live stack on 2026-09-14, plus measurements below.

---

## 1. What the UI is today

### Pages and components

```
App (react-router)
├── /          Dashboard.tsx (415 lines)   ← all state lives here (8 useState)
│   ├── <Viewer> (resium/Cesium)           globe, points, labels, cluster ellipses
│   ├── FilterBar          domain pills (top centre, floating)
│   ├── LiveTicker         left drawer, last 50 events, priority filter
│   ├── EntityDossier      right drawer, one event's summary + entities
│   ├── RelationalWeb      full-screen overlay, 3D force graph (three.js)
│   ├── AICopilot          floating chat bubble (bottom right)
│   ├── DocumentUploader   floating button (top right)
│   └── TerminalLog        bottom strip, polls /logs every 5 s
├── /archive   Archive.tsx (302 lines)     table + semantic search + graph overlay
└── /landing   Landing.tsx                 three.js scroll marketing page
```

### Data flow (measured)

| Source | Mechanism | Where |
|--------|-----------|-------|
| Live events | WebSocket `/ws/live` (pg_notify fan-out) | Dashboard |
| History on load | `GET /archive?limit=100` | Dashboard |
| Clusters | `GET /clusters/active` once on load | Dashboard |
| Watched entities | `GET /entities/bbox` on every camera stop | Dashboard |
| Agent log | `GET /logs` polled every 5 s | TerminalLog |
| Event detail | `GET /event/{uid}` on click | EntityDossier |
| Graph | `GET /graph/network/{name}` | RelationalWeb |
| Archive/entities | paginated REST | Archive |

There is **no shared state layer**: every component fetches for itself, nothing is cached, and
Dashboard and Archive duplicate the same fetching code. There is no notion of "selected time range",
"selected entity", or "active layers" that other components can read.

### Weight (measured with `vite build` and `du`)

| Item | Size |
|------|------|
| JS bundle (one chunk, no code splitting) | 2.1 MB (628 KB gzip) |
| Cesium static assets copied to `dist/cesium` | 15 MB |
| `node_modules/cesium` | 73 MB |
| `node_modules/three` + force-graph + drei/fiber | ~55 MB |
| Landing page pulls three.js even when never visited | yes |

### Design system

Tailwind v4 with five colour tokens (`sentinel-blue`, `-bg`, `-critical`, `-high`, `-normal`) and one
mono font. Everything else is ad-hoc utility classes. No spacing scale, no type scale, no component
library, no icons standard beyond lucide. No UI tests, no Storybook, no accessibility work (focus
states, ARIA, keyboard) at all.

---

## 2. What the screenshots show (concrete problems)

Numbers refer to `ui_research/0N.jpg`.

**Layout — floating panels fight each other**
- 01/02: the domain filter bar sits on top of the globe *and* over the entity search box; at 1600 px
  wide the search input is half hidden.
- 02: opening the dossier covers the AI co-pilot button and the upload button. Panels are overlays
  with no reserved space, so each new feature hides another.
- The terminal strip takes the full width but shows raw job UUIDs — noise, not information.

**Map**
- 01/02: basemap is the bright OpenStreetMap street style on a black HUD. It is the loudest thing on
  the screen. (With a Cesium ion token it would be Bing satellite — also busy.) Real COP/C2 tools use
  dark, desaturated basemaps so that colour is reserved for meaning.
- Yellow points for `NORMAL` priority. In every military convention yellow means *unknown/caution*
  and draws the eye; normal traffic should be neutral (grey/white) so that HIGH/CRITICAL stand out.
- No layer control (sources, entities, clusters, sensors on/off with counts). No scale, no
  coordinates readout, no measurement, no north indicator, no time.

**Information density**
- 01: the ticker shows five events in 550 px of height. An operator screen shows 20–40 rows in the
  same space. Cards, big badges and two-line wrapping cost density for no gain.
- 03: the archive table is good (tabular, mono, scannable) but "TIME (UTC)" shows **local time**
  (`toLocaleString`), and "Advanced filters … coming soon" is the only filter.

**Graph (05)**
- Nodes float in a black void with 6-px labels; there is no time axis, no evidence count, no way to
  see *why* an edge exists without clicking. It is a demo, not an analysis tool.
- Data quality shows through: `Iran`, `United States`, `Russia` are typed `ORGANIZATION` by the
  seed script (04), so the legend colours are wrong.

**Language and tone**
- "OMNISCIENT ARCHIVE", "Neural Core", "INJECTING INTO NEURAL QUEUE", "Querying Cold Storage",
  "Vectorizing Query", "Decision Dominance". This is science-fiction vocabulary. Real intelligence
  software uses flat, precise words: *Reports, Tracks, Entities, Alerts, SITREP, Source,
  Confidence, Acknowledge.* The current tone undermines the "professional" goal more than any
  single visual choice.

**Missing frame**
- No persistent status bar: no clock (Zulu), no connection/health state beyond a tiny LIVE pill,
  no mission/focus name, no operator, no classification banner (every real system has one, even
  if it says UNCLASSIFIED).
- No alert workflow: CRITICAL events scroll past like everything else. There is no queue to
  acknowledge, assign, or close.
- No timeline. Intelligence is about *when*; the UI has no time control at all.
- No keyboard operation.

---

## 3. What "professional military / intelligence" UIs actually do

Reference systems looked at: ATAK/WinTAK (tactical map), GCCS-J style COPs, Palantir Gotham
(analysis), Maxar/Windward (maritime), Dataminr and Recorded Future (OSINT alerting), and SOC
consoles (Kibana/Splunk). They differ a lot, but share these rules:

1. **A fixed frame, not floating widgets.** Top bar (classification, mission, clock, health), left
   rail (layers / filters / sources), centre map or workspace, right inspector (details of the
   selected thing), bottom timeline. Panels resize, they never overlap.
2. **Dark, muted basemap; colour means something.** Colours follow a convention. The closest
   standard is MIL-STD-2525 / APP-6 affiliation: red hostile, blue friendly, green neutral, yellow
   unknown. For an OSINT tool a practical mapping is: priority → colour intensity, domain → icon,
   source type → shape/outline. `NORMAL` is grey.
3. **Density and tables.** Monospace numbers, aligned columns, 24–28 px rows, hover for detail. Icons
   over words. Thousands of items must be scannable.
4. **Time is a first-class control.** A timeline strip with the event histogram, a scrubber, and
   playback. Everything on the map respects the selected window.
5. **Provenance on every item.** Source, time (Zulu), confidence, and a link to the evidence.
   Nothing is shown without its origin.
6. **Alerts are a workflow, not a feed.** Separate queue for HIGH/CRITICAL with acknowledge → assign
   → resolve, an audible/visual state change, and a count in the top bar.
7. **Entities and situations have pages.** Click an entity → its profile, mention timeline,
   relationships, recent reports. Click a cluster → what it is, evidence, trend.
8. **Plain, consistent vocabulary and keyboard shortcuts.** `/` to search, `J/K` to move, `A` to
   acknowledge, `Esc` to close.
9. **Layers with counts.** "Reports (118) · Entities (34) · Clusters (3) · Sensors (2)" — always
   visible, toggleable.

3D globes are rare in operational tools; they are used for demos and for space/air situational
awareness. Most COPs are 2D with optional terrain. This matters for cost: Cesium is 15 MB of assets
and most of the current bundle.

---

## 4. Frontend architecture assessment

| Area | Today | Problem | Direction |
|------|-------|---------|-----------|
| State | local `useState` per component | no shared selection/time/layers; duplicate fetches; nothing cached | one small store (Zustand) for UI state + TanStack Query for server data + one WebSocket service that writes into the query cache |
| Routing | 3 flat routes | entity/cluster/report have no URLs; nothing is linkable or bookmarkable | routes per object: `/reports/:uid`, `/entities/:id`, `/situations/:id`, `/alerts` |
| Map | Cesium 3D, 15 MB assets | heavy, bright basemap, no layers | MapLibre GL (2D, vector tiles, dark style, ~1 MB) as the default; keep Cesium behind a lazy "3D" toggle only if the globe is wanted |
| Graph | react-force-graph-3d + three | pretty, not analytical | 2D graph (Cytoscape or Sigma) with time filter, edge evidence, expand-on-click |
| Bundle | one 2.1 MB chunk | slow first load | lazy routes, split Cesium/three/landing |
| Styling | ad-hoc Tailwind | inconsistent | design tokens (semantic colours, 4-pt spacing, type scale), a small component set (Panel, DataTable, Badge, StatusBar, Timeline) |
| Type safety | fixed in the last pass (`lib/types.ts`) | ok | keep; generate types from the API's OpenAPI |
| Tests | none | regressions invisible | Vitest + Testing Library for components; Playwright smoke for the 3 main flows |
| Accessibility | none | keyboard-only operators impossible | focus rings, ARIA on panels, shortcuts |

### Backend gaps the new UI will hit

The API serves what the demo needed. A COP-style UI needs endpoints that do not exist yet:

- time-range queries (`from`/`to`) on reports, entities, clusters — today only `page/limit`
- counts by domain / source / priority per time bucket (for the timeline histogram and layer counts)
- an alerts resource with state (`OPEN → ACK → CLOSED`), assignee, and audit — needs a table
- entity detail: profile, mention timeline, relationships, top reports — one call
- cluster detail: description, evidence, trend
- agent health / heartbeat (which agents are alive, last poll, queue depth) — replaces the log strip
- WebSocket events for cluster updates and alert state changes, not only new records

None of these are hard; the schema already has most of the columns. They should be planned with the
UI, not after it.

---

## 5. Options for discussion

| | A — Polish | B — COP layout (recommended) | C — Analyst workstation |
|---|---|---|---|
| Idea | keep the current layout, fix what is wrong | rebuild the frame around the map | B + investigation workspace |
| Scope | dark basemap, no overlaps, grey NORMAL, dense ticker, real vocabulary, Zulu clock/status bar, fix UTC bug | fixed frame; 2D MapLibre map with layers + timeline; alerts queue; entity and situation pages; state layer; lazy Cesium as optional 3D | cases, pinned entities, link analysis over time, SITREP/report generation, multi-user |
| Effort | 1–2 weeks | 4–6 weeks | +2–3 months |
| Risk | still a demo underneath | needs the backend gaps above | needs real users to be worth it |

Recommendation: do A's items in the first week (they are cheap and remove the "sci-fi demo" feel
immediately), then build B properly. C only once someone actually uses B daily.

---

## 6. Questions the design depends on

1. **Who sits in front of it?** One person watching a wall screen, or an analyst at a desk doing
   investigations? (Wall = density + alerts + map. Desk = search + entity pages + graph.)
2. **2D or 3D?** Is the globe a requirement or a "cool" feature? It costs 15 MB and most of the
   layout problems.
3. **Real-time or history?** Is the main question "what is happening now" or "what happened around
   X"? Decides whether the timeline or the live feed is the primary control.
4. **Classification banner and Zulu time** — wanted, or is this civilian OSINT?
5. **Alerts** — should CRITICAL items require a human acknowledge, or is it just a feed?
6. **Screen size** — 1080p laptop, 4K, multi-monitor?
7. **Keyboard-first** — matters for operators; ignored by demos.
