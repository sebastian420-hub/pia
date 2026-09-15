# COP-Style UI, Camera Layers and Wall Mode — Implementation Plan

**Status:** Phases 1, 2 and 6 BUILT 2026-09-15 and verified in the browser (screenshots `ui_research/after_*.jpg`); relay written but not deployed (needs a US host); Phases 3–5 (timeline, entity/situation pages, wall mode) not started.
**Deviation from Part C2:** CARTO dark tiles watermark "API KEY REQUIRED" for browser requests, so the basemap is Esri *World Dark Gray Base* (token-free, attribution shown).
**Follows from:** [`ui_ux_research.md`](ui_ux_research.md) and the discussion on 2026-09-14.
**Decisions taken in that discussion:**
- Users: the owner at a desk, plus a passive **wall screen** (assume 1080p TV, viewed from ~3 m).
- **3D globe stays** (Cesium) — cameras and other geospatial layers justify it.
- Both "what is happening now" and "what happened around X" → a **timeline** is the primary time control.
- Look: *military discipline, civilian honesty* — dark, dense, Zulu clock, plain vocabulary, an honest
  `UNCLASSIFIED // OSINT` banner, no sci-fi words.
- No alert acknowledge workflow yet; HIGH/CRITICAL get their own lane.
- Cameras: **public city traffic cameras, all big cities that publish them.**

---

## Part A — Camera research (verified 2026-09-14 from this machine, Asia network)

"All big cities" is not one feed. It is a list of city/country open-data APIs, each with its own
shape, plus a global aggregator. Everything below was actually fetched today; counts are from the
responses.

### A1. Free, no key, working from here

| Provider | Coverage | Cameras | Format | Endpoint (verified) |
|----------|----------|---------|--------|---------------------|
| Hong Kong Transport Dept | Hong Kong | **1,013** | JPEG snapshot (~2 min) | `static.data.gov.hk/td/traffic-snapshot-images/code/Traffic_Camera_Locations_En.csv` (UTF-16 TSV: key, district, lat, lon, url) → `tdcctv.data.one.gov.hk/<KEY>.JPG` (fetched: 200, image/jpeg, 16 KB) |
| TfL JamCams | London | **890** | JPEG + 10 s MP4 clip | `api.tfl.gov.uk/Place/Type/JamCam` (1.1 MB JSON; `lat`,`lon`, props `imageUrl`,`videoUrl`,`available`) |
| Finland Digitraffic | Finland (Helsinki + highways) | **811 stations**, ~3 presets each | JPEG | `tie.digitraffic.fi/api/weathercam/v1/stations` (GeoJSON; **requires `Accept-Encoding: gzip`** or returns 406) |
| NZTA | New Zealand (Auckland, Wellington, Christchurch) | **313** | JPEG | `trafficnz.info/service/traffic/rest/4/cameras/all` (XML, `<imageUrl>`) |
| Toronto Open Data | Toronto | list only verified | JPEG | CKAN package `traffic-cameras` → `Traffic Camera List - 4326.geojson` |
| Singapore data.gov.sg | Singapore | ~90 (8 in this response — the API returns whatever is fresh) | JPEG, timestamped | `api.data.gov.sg/v1/transport/traffic-images` (JSON; `camera_id`, `location.latitude/longitude`, `image`) |

Total available on day one without any key: **~3,100 cameras** in 6 regions.

### A2. Exists, free, but **unreachable from this network**

| Provider | Coverage | Cameras | Note |
|----------|----------|---------|------|
| NYC DOT (`webcams.nyctmc.org/api/cameras`) | New York | ~900 | TCP **timed out** twice (15 s). Documented as public and key-less. Almost certainly geo-restricted to US IPs. |
| Caltrans (`cwwp2.dot.ca.gov/data/d<N>/cctv/cctvStatusD<NN>.json`) | Los Angeles, SF Bay, San Diego… | thousands | Same: **timed out**. JSON has `currentImageURL` and `streamingVideoURL`. |

Consequence: US feeds need a **small relay in a US region** (a $5 VPS or a Cloudflare Worker) that the
camera agent calls instead. This is a real infrastructure item, not a code fix.

### A3. Free with an API key (sign-up only)

| Provider | Coverage | Note |
|----------|----------|------|
| Transport for NSW Open Data | Sydney | `api.transport.nsw.gov.au/v1/live/cameras` → 401 without key |
| QLDTraffic | Brisbane | 403 without key |
| Seoul TOPIS / Seoul Open Data | Seoul | key; sample endpoint errored today |
| 511NY, WSDOT (Seattle), 511 systems in most US states | US | key; also likely US-only |
| **Windy Webcams API v3** | global (thousands of cities) | free key; **image URLs expire after 10 min on the free tier**, so the agent must refresh, not cache URLs. Mostly scenic/webcams rather than traffic cams — good filler for cities with no open traffic API. |

### A4. No usable public API (today)

Austria ASFINAG (403), Ireland TII (403), Bangkok BMA (HTML player pages only — scraping), Tokyo,
Paris, Berlin (Autobahn API returned empty webcam lists for A3/A9/A100), Madrid, Istanbul, Dubai,
Jakarta, Mumbai, Moscow, Yangon. These are *not* in scope for the first release; Windy fills the gap
where it has coverage.

### A5. What this means for the design

- A **provider adapter** per source (6 on day one, ~30 lines each), all producing the same
  `CameraSpec {external_id, name, lat, lon, snapshot_url, video_url?, refresh_seconds, attribution}`.
- Camera **lists** are refreshed every 30–60 min; **snapshots** are fetched on demand through a
  proxy with a short cache, never all at once (3,000 cameras × 1 JPEG/min would be 50 GB/day).
- Each provider carries an `attribution` string shown in the inspector — every one of these
  datasets requires it.
- Snapshot-first. HLS/MP4 only where the provider gives it (TfL clips, Caltrans streams).

---

## Part B — Backend: a real layer/sensor model

Today "sensors" are two fake agents writing straight into `intelligence_records`. Cameras must not do
that (a camera is not a report). They need their own model, and the same model later hosts real
ADS-B/AIS.

### B1. Schema (migrations 006–008)

```sql
-- 006_sensor_layers.sql
CREATE TABLE sensor_layers (
    layer_id        TEXT PRIMARY KEY,              -- 'cameras', 'flights', 'vessels', 'seismic'
    label           TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('CAMERA','AIRCRAFT','VESSEL','SEISMIC','OTHER')),
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB
);
CREATE TABLE sensors (
    sensor_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    layer_id        TEXT NOT NULL REFERENCES sensor_layers(layer_id),
    provider        TEXT NOT NULL,                 -- 'tfl', 'hk_td', 'sg_lta', 'nzta', 'fi_digitraffic', 'toronto', 'nyc_dot', 'windy'
    external_id     TEXT NOT NULL,
    name            TEXT,
    geo             GEOMETRY(Point, 4326) NOT NULL,
    city            TEXT, country_code TEXT,
    media_kind      TEXT NOT NULL CHECK (media_kind IN ('SNAPSHOT','HLS','MP4','MJPEG')),
    media_url       TEXT NOT NULL,                 -- upstream URL (never sent to the browser raw if CORS-blocked)
    refresh_seconds INTEGER NOT NULL DEFAULT 60,
    attribution     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (status IN ('ONLINE','OFFLINE','UNKNOWN')),
    last_seen       TIMESTAMPTZ, last_ok TIMESTAMPTZ,
    metadata        JSONB,
    UNIQUE (provider, external_id)
);
CREATE INDEX idx_sensors_geo ON sensors USING GIST(geo);
CREATE INDEX idx_sensors_layer ON sensors(layer_id, status);

-- 007_agent_heartbeats.sql  (replaces the log strip with real health)
CREATE TABLE agent_heartbeats (
    agent_name  TEXT PRIMARY KEY,
    agent_kind  TEXT, hostname TEXT,
    last_beat   TIMESTAMPTZ NOT NULL,
    status      TEXT, detail JSONB
);

-- 008_report_time_index.sql  (timeline queries)
CREATE INDEX idx_uir_time_domain_prio ON intelligence_records(created_at, domain, priority);
```

Later (not this plan): `sensor_observations` hypertable for detections on snapshots.

### B2. Camera agent (`src/pia/agents/camera_agent.py` + `src/pia/sensors/providers/*.py`)

- `CameraProvider` interface: `provider_id`, `attribution`, `list_cameras() -> list[CameraSpec]`.
- Providers on day one: `hk_td`, `tfl`, `sg_lta`, `nzta`, `fi_digitraffic`, `toronto`. Then
  `nyc_dot`, `caltrans` (through the US relay, `CAMERA_RELAY_URL` env), `windy` (key).
- Loop: every `CAMERA_LIST_REFRESH_MIN` (60) → `list_cameras()` per provider → upsert into `sensors`
  (`ON CONFLICT (provider, external_id)`), mark missing ones `OFFLINE`.
- Health probe: every 10 min, HEAD/GET a random 2 % sample per provider, update `status`/`last_ok`.
- Heartbeat: `BaseAgent.run()` upserts `agent_heartbeats` every poll (all agents get this for free).

### B3. API additions (`pia-api/routers.py`, all behind the token)

| Endpoint | Purpose |
|----------|---------|
| `GET /layers` | layers with counts (`reports`, `entities`, `situations`, `cameras`, …) for the given time window |
| `GET /sensors?layer=cameras&bbox=…&limit=2000` | cameras in view (lightweight: id, name, lat, lon, status, media_kind) |
| `GET /sensors/{id}` | full detail incl. attribution and refresh interval |
| `GET /sensors/{id}/snapshot` | **proxy**: fetch upstream, cache `refresh_seconds` (in-memory LRU, size cap), stream JPEG with `Cache-Control`. Solves CORS and hides upstream URLs. Rate-limited per IP. |
| `GET /reports?from=&to=&domain=&priority=&bbox=&limit=` | time-windowed reports (replaces `/archive` for the map) |
| `GET /timeline/histogram?from=&to=&bucket=1h&by=priority` | counts per bucket for the timeline strip |
| `GET /entities/{id}` | profile, mention timeline, relationships, top reports — one call |
| `GET /situations/{id}` | cluster detail: evidence list, trend |
| `GET /health` | agents (from heartbeats), queue depth, DB, last event age |
| WebSocket | add `cluster_updated`, `sensor_status` message types alongside `new_intelligence` |

### B4. Cost controls

- Snapshot proxy: `max 4 concurrent upstream fetches per provider`, 5–60 s cache, 512 KB size cap,
  10 s timeout, no proxying of arbitrary URLs (only `sensors.media_url` by id).
- Camera lists in the browser are paged by viewport (`bbox`) — never "all 3,000".
- Windy URLs re-fetched on demand (10-min expiry).

---

## Part C — Frontend: COP frame, layers, timeline, wall mode

### C1. Frame (desk view, ≥1280 px)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ UNCLASSIFIED // OSINT   ▸ Mission: —   14:52:07Z   ● agents 7/8   ⚠ 2 HIGH  │ 32 px status bar
├──────────┬───────────────────────────────────────────────────┬───────────────┤
│ LAYERS   │                                                   │ INSPECTOR     │
│ ☑ Reports│                                                   │ (report /     │
│   118    │              CESIUM GLOBE (dark basemap)          │  entity /     │
│ ☑ Entit. │                                                   │  situation /  │
│ ☑ Situat.│                                                   │  camera+image)│
│ ☑ Cameras│                                                   │               │
│  3,104   │                                                   │               │
│ ─────    │                                                   │               │
│ FEED     │                                                   │               │
│ dense    │                                                   │               │
│ rows     │                                                   │               │
├──────────┴───────────────────────────────────────────────────┴───────────────┤
│ TIMELINE  ◀ 24h ▶  ▁▂▃▅▂▁▃▇▂▁▁▂   [now]                       LIVE ●        │ 96 px
└──────────────────────────────────────────────────────────────────────────────┘
```

- Left rail 280 px (collapsible to 48 px icons), right inspector 360 px (collapsible), bottom
  timeline 96 px. **Nothing overlaps the globe**; the globe resizes.
- Feed rows: 28 px, one line: `14:51Z  HIGH  POLITICAL  Headline…  OSINT`. 20+ visible.
- Alerts: HIGH/CRITICAL pinned at the top of the feed in their own lane, count in the status bar.

### C2. Globe

- Basemap: **CARTO dark_all** (`basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png`, verified 200, free
  with attribution for non-commercial use) — or Esri *World Dark Gray Base* (verified 200). Both
  key-less; both need their attribution line kept visible. Ion token stays optional for terrain.
- Symbology: NORMAL grey, HIGH amber, CRITICAL red (pulsing), domain = small icon in the label;
  cameras = camera glyph, dim when OFFLINE; situations = translucent ring; entities = hollow point.
- `PointPrimitiveCollection` for reports/entities (already), `BillboardCollection` for cameras,
  Cesium `EntityCluster` for label declutter beyond ~300 visible.
- Globe respects the timeline window: entities have `availability` intervals; the Cesium `Clock`
  is the single source of time truth (timeline component drives it).

### C3. State and data layer

- `zustand` store: `timeWindow`, `live: boolean`, `layers: {id: on/off}`, `selection: {kind, id}`,
  `viewport bbox`, `mode: desk|wall`.
- `@tanstack/react-query` for all reads, keyed by time window + bbox; WebSocket service pushes
  new records into the `reports` query cache (no refetch storms).
- Routes: `/` desk, `/wall`, `/reports/:uid`, `/entities/:id`, `/situations/:id`, `/cameras/:id`
  (all open the desk view with the inspector pre-selected — linkable).
- Lazy-load Cesium bundle and the graph view; drop the three.js landing from the main bundle.

### C4. Camera inspector

- Snapshot cameras: `<img src=/api/v1/sensors/{id}/snapshot?t=…>` refreshed every
  `refresh_seconds`; shows name, city, provider attribution, last OK time, "open in new tab".
- Video cameras: TfL MP4 clips play in `<video loop>`; HLS via `hls.js` when present.
- "Cameras near this report" button in the report inspector: `GET /sensors?layer=cameras&bbox=`
  around the report's point (5 km) — this is the link between OSINT and the camera layer, and the
  first genuinely new capability the layer gives the system.

### C5. Wall mode (`/wall`, 1080p TV from 3 m)

- Globe full-bleed with a dark vignette; no rails, no inspector, no mouse needed.
- Top lane (120 px): `UNCLASSIFIED // OSINT` · **clock 64 px Zulu** · alert count · agents health dots.
- Alert ticker across the top lane: HIGH/CRITICAL headlines, ≥28 px.
- Auto-director: fly to the newest HIGH/CRITICAL (hold 30 s), else cycle active situations (20 s
  each) with a "NOW SHOWING" card (≥26 px) bottom-left: headline, domain, source, Zulu time, and
  when a camera is within 5 km, its live snapshot in the card.
- Minimum text 22 px; no hover states; reconnect/resume without user input; `?rotate=1` idle spin.

### C6. Design system (small, real)

- Tokens: `bg-0/1/2`, `line`, `text-1/2/3`, `prio-normal/high/critical`, `domain-*`, `status-ok/warn/err`;
  4-pt spacing; type scale 12/14/16/20/28/40/64; fonts: Inter (UI) + JetBrains Mono (data/time).
- Components: `StatusBar`, `Rail`, `LayerToggle`, `FeedRow`, `Inspector` (+ 4 bodies), `Timeline`,
  `Badge`, `DataTable`, `CameraView`, `WallCard`.
- Vocabulary: Reports · Entities · Situations · Cameras · Alerts · Source · Confidence · SITREP.
  Delete: Omniscient, Neural, Vault, Cold Storage, Decision Dominance, Vectorizing.

---

## Part B2 — Live sessions: free always, paid/relayed only on demand

**Finding (2026-09-14):** no live-camera vendor sells by the minute. TrafficLand (18,000 US
cameras, real video) is a yearly enterprise licence; Windy Pro is €9,990/year; EarthCam and Skyline
are monthly consumer subscriptions without an API. So an "on-demand paid feed" cannot be bought.

What *is* pay-per-use is the **US relay**: a small cloud machine in the US (≈ $0.01/hour while
running, $0 stopped) that fetches the free-but-US-only feeds — NYC (photo every 2 s) and Caltrans
(true live streams). That is the best live video available and it costs cents.

### Source cost classes

| Class | Examples | Behaviour |
|-------|----------|-----------|
| `FREE` | HK, TfL, SG, NZ, FI, Toronto | always on |
| `ON_DEMAND` | NYC, Caltrans via the relay | visible only while a **live session** is active |
| `SUBSCRIPTION` | TrafficLand, Windy Pro (if ever bought) | adapter slot with a monthly cap and an on/off switch; not built now |

### Live session (backend)

- Table `live_sessions (session_id, started_at, expires_at, stopped_at, started_by, minutes, note)`.
- `POST /api/v1/live/start {minutes: 30}` → runs `RELAY_START_CMD` (e.g. `flyctl machine start …`
  or a Hetzner/DO API call), waits until `RELAY_URL/healthz` answers, records the session.
- `POST /api/v1/live/stop` and an automatic stop when `expires_at` passes (background task in the
  API; also stops if no snapshot was requested for `LIVE_IDLE_MINUTES`, default 15).
- `GET /api/v1/live` → `{active, expires_at, minutes_used_today, estimated_cost_today}` for the meter.
- If `RELAY_URL` is set but no start/stop commands are, the relay is treated as always on (PIA
  itself hosted in the US).
- `sensors.requires_relay = TRUE` for ON_DEMAND providers; `/sensors` hides them while no session is
  active; the snapshot proxy routes their fetches through the relay.

### Relay (its own tiny service, `pia-api/relay/`)

- One endpoint: `GET /fetch?url=…` with a bearer token, an **allow-list of upstream hosts**
  (`webcams.nyctmc.org`, `cwwp2.dot.ca.gov`, `cctv*.dot.ca.gov`), 10 s timeout, 2 MB cap,
  streams the body back. Nothing else. Dockerfile included; deploy on any US host.
- For HLS streams the relay rewrites playlist URLs so segments also pass through it.

### UI

- Status bar: **GO LIVE** button → picks a duration (15/30/60 min) → shows `LIVE 12:40 · $0.00`
  countdown; ON_DEMAND cameras appear on the globe when active and disappear when it ends.
- Camera inspector shows the source class and, for relayed cameras, "via US relay".

### Open (owner to decide)

- Where PIA runs (home Mac vs server). If the server is in the US, no relay is needed.
- Which cloud account for the relay (Fly.io machines stop/start in seconds and bill per second —
  best fit; Hetzner/DO also fine).

## Part D — Order of work

| Phase | Deliverable | Effort | Depends on |
|-------|-------------|--------|------------|
| **0** | **Mockup** of desk + wall (design canvas) → sign-off | 1 day | this plan |
| **1 Quick wins** | dark basemap, grey NORMAL, fix "UTC" label, plain vocabulary, remove overlaps by giving panels fixed slots, Zulu clock + health in a status bar | 3–4 days | — |
| **2 Backend layers** | migrations 006–008, heartbeats in `BaseAgent`, `camera_agent` + 6 providers, `/layers`, `/sensors`, snapshot proxy, `/health` | 4–5 days | — |
| **3 Time** | `/reports?from&to`, `/timeline/histogram`, `/entities/{id}`, `/situations/{id}`; frontend store + react-query + WebSocket service; Timeline component driving Cesium clock | 5–6 days | 2 |
| **4 Frame** | rails, inspector bodies, dense feed, alert lane, routes, camera inspector, "cameras near report" | 6–8 days | 2, 3 |
| **5 Wall** | `/wall` with auto-director | 3–4 days | 4 |
| **6 Live sessions** | relay service, `live_sessions`, start/stop hooks, GO LIVE meter, NYC + Caltrans providers | 3–4 days + a US host | 2 |
| **6b Windy + keyed providers** | Windy, Sydney, Brisbane, Seoul | 2 days | 2 |
| **7 Hardening** | Vitest components, Playwright smoke, bundle split, a11y pass, docs | 3–4 days | 4, 5 |

≈ 6–7 working weeks for one person. Phase 1 alone already removes the "sci-fi demo" feel.

---

## Part E — What this plan does not do, and open risks

- **Detection on cameras** (vehicles, crowds, smoke) — out of scope; the schema leaves room.
- **Real ADS-B/AIS** — the layer model is ready for them; the feeds themselves are a separate plan.
- **Alert acknowledge workflow** — explicitly deferred by the owner.
- **Terms of use:** each open-data feed has an attribution requirement; Windy free tier forbids
  caching image URLs; CARTO basemap is free for non-commercial use only — if PIA is sold, switch to
  a paid tile plan or self-host tiles. NYC/Caltrans terms should be read before relaying.
- **Coverage honesty:** "all big cities" today means London, Hong Kong, Singapore, Helsinki,
  Auckland/Wellington, Toronto, and (via relay) New York and California. Bangkok, Tokyo, Paris,
  Seoul (without a key), Dubai, Jakarta have no usable public traffic-camera API.
- **Load on upstream providers** — the proxy cache and viewport paging are mandatory, not optional.
- **Wall screen unknowns** — if it ends up 4K or a video wall, only type sizes change.

## Part F — Questions still open

1. Is a US relay acceptable (one small VPS)? Without it, no US cameras.
2. Windy key: sign up now, or first release without it?
3. Phase 0 mockup: two screens (desk, wall) — proceed?
