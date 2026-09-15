# PIA Fix Implementation Plan

**Status:** IMPLEMENTED 2026-09-14 (working tree, not committed). Every phase below is done except the
items listed under "Deviations and leftovers". Decision taken: multi-tenancy deferred (1.6 option a).
**Follows from:** [`../../REVIEW.md`](../../REVIEW.md) (full code review, sections 3–4 and 9).
**Repos:** `pia` (core), `pia-api`, `pia-ui` — all at `main`, last commit 2026-03-08.
**Scope:** Make the existing system secure, honest, and working as described. Not adding new features.

Every step lists: what to change, the files, and a command that proves it worked.
Steps are ordered. Phase 0 and 1 must be done first and can be done in a day.

---

## How the evidence was gathered

All claims below come from reading the code and running these on the cloned repos:

```
git log --all -p -S'sk-or-v1-'                 # key in history → scripts/quick_embed.py, commit 3c0660e
git ls-files | grep -c '^venv/'                # pia-api → 2329 files, 38 MB
file pia-api/requirements.txt                  # UTF-16 LE, CRLF
grep -rn "UPDATE intelligence_records" src     # embedding never written
grep -rl intelligence_digests src pia-api      # 0 files → dead table
npx tsc -b && npx vite build                   # UI builds clean
npx eslint .                                   # 20 errors
python3 -m pyflakes src                        # ~30 unused imports
```

---

## Phase 0 — Secrets and repo hygiene (do today)

### 0.1 Rotate the leaked OpenRouter key
- The key `sk-or-v1-02d811…` is hardcoded as a default in `pia/scripts/quick_embed.py:16` and is in git history since commit `3c0660e`.
- **Action:** Revoke it in the OpenRouter dashboard. Create a new one. Never put it in code.
- **Change:** `quick_embed.py` → `api_key=os.environ["OPENROUTER_API_KEY"]` (no default; fail loudly).
- **Verify:** `git grep -n 'sk-or-v1-' HEAD` → no output.
- **Optional:** rewrite history with `git filter-repo --replace-text` and force-push. Only worth it if the repo is public. Rotating the key is what actually matters.

### 0.2 Purge `venv/` and `.env` from pia-api
- **Change:** `git rm -r --cached venv .env __pycache__`; add `pia-api/.gitignore` with `venv/ .env __pycache__/ *.pyc`; add `pia-api/.env.example` with the five DB vars + `OPENROUTER_API_KEY` + `LLM_MODEL`.
- **Verify:** `git ls-files | grep -c '^venv/'` → `0`.

### 0.3 Fix `requirements.txt` encoding and pin versions
- File is UTF-16 with CRLF (written by PowerShell `>`).
- **Change:** rewrite as UTF-8, one package per line, pinned:
  `fastapi==0.115.*`, `uvicorn[standard]`, `asyncpg`, `openai`, `python-dotenv`, `python-multipart`, `pydantic`.
- **Verify:** `file requirements.txt` → `ASCII text`.

### 0.4 Pin core dependencies
- `pia/pyproject.toml` has `fastmcp>=0.4.1` (unpinned; 2.x changed the tool API — see 3.6) and `openai>=1.12.0`.
- **Change:** pin every dependency to a known-good version (`fastmcp==2.x` chosen together with the 3.6 fix).
- **Verify:** `pip install -e .` inside the agents image succeeds; `python -c "import fastmcp; print(fastmcp.__version__)"`.

---

## Phase 1 — Security

### 1.1 Cypher / SQL injection through entity names (critical)
**Where:** `pia/src/pia/core/database.py:75-78` (`execute_cypher`), callers `analyst_agent.py:306`, `mcp_server.py:119`, `wikidata_ingestor.py:191`.

**Why it is dangerous:** the Cypher text (containing an entity name from LLM output or an MCP argument) is pasted into `SELECT * FROM cypher(%s, $$ … $$)`. A name containing `$$` ends the dollar-quote and the rest runs as SQL. `_safe_cypher_name` only escapes `"`.

**Change (two layers):**
1. `execute_cypher` must never build SQL by string concatenation. Pass the Cypher text as a bound parameter so psycopg2 quotes it:
   ```python
   sql = "LOAD 'age'; SET search_path = public, ag_catalog; SELECT * FROM cypher(%s, %s, %s::agtype) AS (v agtype);"
   self.execute_query(sql, (graph_name, cypher_query, json.dumps(params or {})), fetch=True)
   ```
2. Callers pass names as Cypher parameters, never inline:
   ```
   MERGE (a:ENTITY {name: $name_a}) MERGE (b:ENTITY {name: $name_b}) MERGE (a)-[r:PREDICATE]->(b)
   ```
   The relationship label cannot be a parameter in Cypher. Keep the existing allowlist check (`ALL_VALID_VERBS`) and add `re.fullmatch(r"[A-Z_]{1,40}", predicate)` before use.
3. Delete `_safe_cypher_name` from all three files.
4. **Fallback if AGE rejects the `::agtype` literal param** (older AGE builds require `PREPARE`): keep step 1 and add a strict escape — reject names containing `$$`, escape `\` then `"`.

**Verify:** unit test with name `x" }) RETURN 1 //` and name `a $$; SELECT 1; --` — both must be stored as literal node names, and `SELECT count(*) FROM ag_catalog.ag_label` unchanged. Add to `tests/unit/test_cypher_safety.py`.

### 1.2 Add authentication to pia-api and the MCP server
- pia-api: no auth, `allow_origins=["*"]`. MCP: `0.0.0.0:8000`, no auth.
- **Change (minimum viable):** one shared bearer token from env `PIA_API_TOKEN`. FastAPI dependency `require_token` on every router and on the WebSocket handshake (`?token=` query param). Restrict `allow_origins` to `FRONTEND_ORIGIN` env. Bind MCP to `127.0.0.1` (only the Telegram container needs it → put them on the same compose network and bind to service name, not `0.0.0.0` with a host port).
- UI: send `Authorization: Bearer ${import.meta.env.VITE_API_TOKEN}` from one `api.ts` helper (see 4.2).
- **Verify:** `curl -s localhost:8001/api/v1/logs` → 401; with header → 200.

### 1.3 Postgres exposure
- `docker-compose.yml:12-14`: `POSTGRES_HOST_AUTH_METHOD: trust` and `ports: 5432:5432`.
- **Change:** remove `trust`; remove the host port mapping (use `docker compose exec postgres psql` for admin), or bind to `127.0.0.1:5432`. Move `POSTGRES_PASSWORD` to `.env`.
- **Verify:** `psql -h <lan-ip> -U pia` from another machine → refused.

### 1.4 Upload path traversal
- `pia-api/main.py:209` uses `file.filename` directly.
- **Change:** `safe = f"{uuid4().hex}_{re.sub(r'[^A-Za-z0-9._-]', '_', os.path.basename(file.filename))[:100]}"`; enforce extension in `{.pdf, .txt}`; enforce size limit (e.g. 25 MB) by streaming; reject if final path is not under `DOC_DIR` (`os.path.commonpath`).
- **Verify:** upload with filename `../../x.txt` → file lands inside `DOC_DIR`.

### 1.5 Stop leaking exceptions to clients
- Every handler returns HTTP 200 `{"status":"error","message": str(e)}`.
- **Change:** raise `HTTPException(500, "internal error")`, log the traceback server-side. Use 404 for not-found, 422 for bad input.
- **Verify:** hit `/api/v1/graph/network/zzz` → 404 JSON, no SQL text in the body.

### 1.6 RLS is bypassed by the API
- API connects as `pia` (table owner) and never sets `app.current_client_id` → RLS does nothing.
- **Decision needed:** multi-tenancy is not used by the UI today. Two options:
  - (a) **Defer:** document that the system is single-tenant for now; leave RLS in the schema. *Recommended for this plan.*
  - (b) Implement: API connects as `pia_client`, sets `SET LOCAL app.current_client_id` per request from the token's claims, and `ALTER TABLE … FORCE ROW LEVEL SECURITY`.
- **Verify (if b):** `scripts/test_rls_isolation.py` run through the API, not through a raw psql role.

### 1.7 Guard destructive scripts
- `scripts/clean_graph.py`, `engine_bootstrap_hq.py` run `DELETE FROM entity_relationships;` unguarded.
- **Change:** require `--yes-really` flag and refuse if `PIA_ENV=production`.

---

## Phase 2 — Broken features (each one is small)

### 2.1 Document ingestion
Three breaks, fix all three:
1. `document_agent.py:119` inserts `domain='INVESTIGATIVE'`; the CHECK on `intelligence_records.domain` (`03_layer2_uir_spine.sql:38-42`) does not allow it → every insert fails and is swallowed.
   **Change:** add a migration `database/migrations/001_domain_investigative.sql`:
   `ALTER TABLE intelligence_records DROP CONSTRAINT intelligence_records_domain_check; ALTER TABLE … ADD CONSTRAINT … CHECK (domain IN (…existing…, 'INVESTIGATIVE'));`
   and run it in `validate_system.py` (see 4.5 for a migrations runner). Also add `INVESTIGATIVE` to the UI filter list (2.3).
2. `_mark_processed` runs even when every chunk failed → the file vanishes.
   **Change:** only move the file when `inserted_count > 0 or all chunks already existed`; otherwise move it to `failed/` and log why.
3. Upload dir: `pia-api/main.py:21` writes to `../pia-core/data/documents` (folder does not exist; not shared with the agent container).
   **Change:** `DOC_DIR = os.getenv("DOC_DIR", "/app/data/documents")`; in `docker-compose.yml` mount the same host folder into `api_bridge` and `document_agent`:
   ```yaml
   volumes: [ "./data/documents:/app/data/documents" ]
   environment: [ "DOC_DIR=/app/data/documents" ]
   ```
- **Verify:** upload a 2-page PDF via the UI → within 30 s `SELECT count(*) FROM intelligence_records WHERE source_type='HUMINT'` increases; file moved to `processed/`.

### 2.2 `/entities/bbox` always errors
- `routers.py:113-128`: SQL has no `$1..$4`, but 4 args are passed → asyncpg `InterfaceError` on every camera move.
- **Change:** add `AND primary_geo && ST_MakeEnvelope($1, $2, $3, $4, 4326)`; clamp inputs (`-180..180`, `-90..90`); when the UI sends `maxLon > 180` (antimeridian), split into two envelopes with `OR`.
- **Verify:** `curl "…/entities/bbox?minLat=40&minLon=-75&maxLat=41&maxLon=-73"` → `status: success` with New York area entities only.

### 2.3 Domain filter mismatch
- `FilterBar.tsx:10`, `Dashboard.tsx:29`: `'FINANCE'` vs DB `'FINANCIAL'`; `MARITIME, AVIATION, INFRASTRUCTURE, PERSONNEL` missing.
- **Change:** one shared `DOMAINS` const in `src/lib/domains.ts` matching the SQL CHECK list exactly (+ `INVESTIGATIVE` after 2.1).
- **Verify:** a FINANCIAL RSS item appears on the globe.

### 2.4 Director tasking creates a FAILED job every time
- `mcp_server.py:144-160`: UIR insert (trigger already queues it) + a second queue row with `uir_uid = NULL` → analyst marks it FAILED.
- **Change:** delete the second insert; return the queue row created by the trigger (`SELECT queue_id FROM analysis_queue WHERE uir_uid = $uid`).
- **Verify:** `submit_tasking("test")` → exactly one queue row, status ends `DONE`.

### 2.5 Embedding model name mismatch
- `routers.py:36` → `text-embedding-3-small`; `nlp.py:201` → `openai/text-embedding-3-small`.
- **Change:** one env var `EMBEDDING_MODEL`, same value in both repos. Test which name OpenRouter accepts *before* choosing (`curl https://openrouter.ai/api/v1/embeddings …`). If OpenRouter's embeddings endpoint is unreliable, call OpenAI directly for embeddings with a separate key.
- **Verify:** Archive semantic search returns rows (after 3.3 writes embeddings).

### 2.6 Telegram tool dispatch
- `telegram_voice.py:96-100`: `getattr(mcp_server, tool_name)` fetches *any* module attribute; `tool_func(**args)` breaks on fastmcp 2.x.
- **Change:** explicit dict `TOOLS = {"search_spatial": search_spatial.fn, …}` (or plain functions registered with `mcp.tool()(fn)` so the plain fn stays importable); validate `args` keys against the function signature; reject unknown tools.
- **Verify:** send `{"tool":"db","args":{}}` from the LLM path → "unknown tool"; a real tool call returns a summary.

### 2.7 Pagination input validation
- `main.py:303`, `routers.py:151`: `limit=0` → `ZeroDivisionError`; negative page → bad `OFFSET`.
- **Change:** `page: int = Query(1, ge=1)`, `limit: int = Query(50, ge=1, le=200)`.

### 2.8 Enrichment agent stuck loop
- `enrichment_agent.py:25-31`: same failing entity retried every 15 s forever.
- **Change:** add `enrichment_attempts INT DEFAULT 0` + `enrichment_next_at TIMESTAMPTZ` to `entities` (migration). Query `WHERE confidence < 0.5 AND (enrichment_next_at IS NULL OR enrichment_next_at < NOW())`; on failure set `attempts+1`, `next_at = NOW() + (2^attempts) minutes`; give up after 5.
- Also: stop stamping `confidence = 0.8` on LLM-invented descriptions. Use `0.5` and record `metadata.enrichment_source = 'llm'`. Real "ground truth" needs a real source (Wikidata API lookup by name) — out of scope here, but note it.

---

## Phase 3 — Pipeline correctness and throughput

### 3.1 Analyst drains the queue
- `analyst_agent.py:25-47`: one job per 10 s poll → 3 replicas ≈ 18 jobs/min max.
- **Change:** in `poll()`, loop `while self.running:` claim → process; break only when no job was claimed. Keep the outer `interval_sec` sleep for the idle case.
- **Verify:** insert 50 test UIRs; measure time to all `DONE` before/after (`scripts/signal_storm.py` already exists for this).

### 3.2 Extraction failure must not be DONE
- `nlp.py:181-188` returns empty entities on any error; analyst marks the job `DONE`.
- **Change:** `extract_intelligence` raises `ExtractionError`; the analyst catches it and sets `FAILED` with the message. Add retry: `retry_count INT DEFAULT 0` on `analysis_queue` (migration); the claim query includes `status='FAILED' AND retry_count < 3 AND processed_at < NOW() - interval '5 min'`.
- Raise `max_tokens` from 500 to 1500 for JSON output; long document chunks (1500 chars) currently overflow 500 tokens and truncate the JSON.
- **Verify:** point `OPENROUTER_API_KEY` at an invalid key → jobs become `FAILED`, not `DONE`.

### 3.3 Write the UIR embedding and the summary
- The analyst already computes `record_vector` (`analyst_agent.py:338`) and receives `summary` (`nlp.py:84`) — both discarded.
- **Change:** in the finalize `UPDATE intelligence_records` at `analyst_agent.py:96-100` add `embedding = %s, content_summary = COALESCE(content_summary, %s)`. Pass `record_vector` out of `correlate_and_cluster` (return a tuple) so it is computed once.
- **Verify:** `SELECT count(*) FROM intelligence_records WHERE embedding IS NOT NULL` grows; Archive semantic search on "earthquake" returns seismic records.

### 3.4 Stale `PROCESSING` recovery
- No code touches `PROCESSING` after the claim.
- **Change:** in the claim subquery: `WHERE status='PENDING' OR (status='PROCESSING' AND processed_at < NOW() - INTERVAL '10 minutes')`.
- **Verify:** set a row to `PROCESSING` with old `processed_at`; it is re-claimed.

### 3.5 Stop `maintenance.py` from deleting new entities
- New entities are created at `confidence 0.3` (`analyst_agent.py:215`); `maintenance.py:34` deletes `< 0.4` after 24 h, cascading relationships.
- **Change:** either create new entities at `0.5`, or make maintenance delete only `mention_count = 1 AND array_length(uir_refs,1) IS NULL` orphans. Also delete the matching AGE vertex in the same script so the graph does not drift (`MATCH (n:ENTITY {name:$name}) DETACH DELETE n` via the safe `execute_cypher`).

### 3.6 Entity uniqueness and lexical match
- `entities.name` has no unique index; `ON CONFLICT DO NOTHING` is a no-op; `LIMIT 1` without `ORDER BY`.
- **Change:** migration `CREATE UNIQUE INDEX entities_name_type_uq ON entities (lower(name), entity_type)`. First run `scripts/merge_entities.py` to collapse existing duplicates. Lexical query: `ORDER BY mention_count DESC`. Fix `analyst_agent.py:139` so an exact name match wins even if the stored entity has no embedding (`similarity` NULL → treat as 1.0).
- **Verify:** `SELECT lower(name), entity_type, count(*) FROM entities GROUP BY 1,2 HAVING count(*)>1` → 0 rows.

### 3.7 Time zones
- `models/seismic.py:48`: `datetime.fromtimestamp(ms/1000)` → naive local time.
- **Change:** `datetime.fromtimestamp(ms/1000, tz=timezone.utc)`. Same for `datetime.now()` in aviation/maritime agents → `datetime.now(timezone.utc)`.

### 3.8 Wikidata ingestor
- `_flush_buffer` never commits; can leave an open transaction on a pooled connection (next `autocommit = True` raises). All entities typed `ORGANIZATION`. TSV `COPY` breaks on tabs/backslashes in names.
- **Change:** `conn.commit()` after `copy_from`; use `psycopg2.extras.execute_values` instead of TSV; map type from Wikidata `P31` where available, else `UNKNOWN`… but `UNKNOWN` is not in the entity_type CHECK — add it via migration. This script is not on the critical path; can be last.

---

## Phase 4 — Config and deployability

### 4.1 Docker build from a clean clone
- `infra/agents/Dockerfile:14` `COPY .env .env` — `.env` is gitignored → build fails; also bakes secrets into the image.
- **Change:** delete that line. Compose already passes env vars. `.env.example` is the template.
- Also `.env.example` lists `LLM_ENDPOINT` / `kimi-k2.5-int4` which nothing reads; replace with `OPENROUTER_API_KEY`, `LLM_MODEL`, `EMBEDDING_MODEL`, `TELEGRAM_BOT_TOKEN`, `ALLOWED_TELEGRAM_USER_IDS`, `PIA_API_TOKEN`.
- **Verify:** `git clone … && cp .env.example .env && docker compose build` succeeds with no manual steps.

### 4.2 UI API base URL
- `http://localhost:8001` hardcoded in 12 places across 8 files.
- **Change:** `src/lib/api.ts` exporting `API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8001'`, `WS_BASE`, and `apiFetch(path, init)` that adds the bearer header. Replace all 12 call sites.
- **Verify:** `grep -rn "localhost:8001" src` → 0 hits outside `api.ts`.

### 4.3 pia-api config order and duplication
- `main.py:14` imports `routers` before `load_dotenv()` at `:18` → `routers.py` reads defaults.
- **Change:** new `config.py` that calls `load_dotenv()` at import and exposes `DATABASE_URL`, `llm_client`, `EMBEDDING_MODEL`. Both `main.py` and `routers.py` import from it. Create one `asyncpg.create_pool()` in `lifespan` and use `app.state.pool` everywhere (also fixes connection leaks on exceptions and per-request connects).
- **Verify:** `grep -c "asyncpg.connect" main.py routers.py` → 0 (only the LISTEN connection remains).

### 4.4 Repo layout assumptions
- README says `pia-core/`; repo is `pia`; compose builds `../pia-api`.
- **Change:** README documents the required sibling layout (`pia/`, `pia-api/`, `pia-ui/`) or move `pia-api` into `pia/` as a subfolder (simplest). The document upload dir follows 2.1.

### 4.5 Schema migrations
- `validate_system.py` applies schema only when `flight_tracks` is absent → no way to change an existing DB. Phases 2–3 need ~5 `ALTER`s.
- **Change:** `database/migrations/NNN_*.sql` + `schema_migrations(version)` table; `validate_system.py` applies unapplied ones in order every start. Also read DB creds from env there instead of hardcoding `host="postgres", password="password"`.

### 4.6 Fake sensors
- Aviation and Maritime agents insert hardcoded rows every 60 s (`aviation_agent.py:25-29`, `maritime_agent.py:27-31`), creating `flight_tracks`/`vessel_positions` rows forever and `MILITARY`-domain UIRs hourly.
- **Change (this plan):** gate both with `SIMULATED_SENSORS=true` env (default `false` → agents exit with a clear log line); label simulated UIRs with `source_name = 'SIMULATED …'` and `confidence 0.1`; UI shows a "SIM" badge. Replacing them with real feeds (OpenSky for ADS-B has a free API; AIS needs a paid or self-hosted receiver) is a separate feature plan.

### 4.7 Cesium
- No `Ion.defaultAccessToken`; credits hidden with CSS (violates Cesium's attribution terms).
- **Change:** set token from `VITE_CESIUM_ION_TOKEN` in `main.tsx`, or switch base imagery to an OpenStreetMap/`TileMapServiceImageryProvider` that needs no token. Remove the `.cesium-viewer-bottom { display:none }` rule; style it small instead.

---

## Phase 5 — Honesty of docs and dead code

- Rewrite `docs/STATUS.md` to list what works today (News, Seismic, analyst, globe, archive list) and what is simulated, unbuilt, or broken. Delete "Tier-1 Operational".
- Mark `docs/systematic_test_report.md` as historical; its "100% stable" claim predates the broken features.
- README: remove "Layer 4 Strategic Digests" and "Layer 6 Continuous Aggregates" from the feature table, or move them to a "Planned" section. Remove the Landing page claims about dark web / chain-of-thought.
- Either drop the six dead tables (`intelligence_digests`, `agent_tasks`, `entity_profile_history`, `cluster_revisions`, `satellite_positions`, `flight_hourly_anomalies`) in a migration, or leave them with a comment `-- reserved, no writer yet`. Recommended: leave, comment.
- `ai_feedback`: add the one missing writer — `POST /api/v1/feedback` (relationship_id, feedback_type, correction) and a thumbs-down button in `RelationalWeb` link tooltip. Small, and it makes the existing HITL prompt code real.
- Remove the "Static Test Marker (New York)" from `Dashboard.tsx:203-212`. Replace `README.md` in pia-ui (Vite template) with real run instructions.
- Change `HTTP-Referer` in `nlp.py:61` and `telegram_voice.py:24` from `github.com/google/gemini-cli` to the project's own URL.

---

## Phase 6 — Tests and CI

- **Unit tests that need no Docker** (`tests/unit/`): Cypher safety (1.1), NLP JSON parsing incl. truncated output (3.2), chunking, domain/priority heuristics in `news_agent`, pagination validation, `SeismicEvent` parsing with a saved USGS fixture.
- **Integration tests** stay in `tests/integration/` and get a `pytest -m integration` marker so `pytest` alone runs unit tests.
- **CI** (`.github/workflows/ci.yml`): `pyflakes`/`ruff`, `pytest tests/unit`, `pip-audit`; for the UI `npm ci && npx tsc -b && npx eslint . && npx vite build`. Fix the 20 ESLint errors (`any` → typed responses in `src/lib/types.ts`, `let` → `const`).
- **Secret scan**: `gitleaks` in CI so 0.1 cannot happen again.

---

## Implementation log (what was actually done and verified)

**Verified on a real PostgreSQL 16 + TimescaleDB + Apache AGE database** (throwaway container from the
already-built `pia` postgres image, fresh volume, removed afterwards):

- Base schema + all five migrations apply cleanly on a fresh database (`validate_system.py`).
- **1.1** Hostile names (`x" }) RETURN 1 //`, `a $$; DROP TABLE entities; --`, a fake `$pia_…$` tag)
  are stored as literal vertex names; the `entities` table is untouched. Multi-value Cypher RETURN
  works as a single map. Orphan cleanup deletes the matching AGE vertex.
- **2.1** `domain='INVESTIGATIVE'` inserts succeed and queue a job.
- **2.2** `/entities/bbox` filters spatially (New York box → only New York; Tokyo box → only Tokyo;
  world box → both; antimeridian box accepted; inverted latitudes → 422).
- **3.1/3.2/3.4** Claim query takes PENDING, re-claims PROCESSING older than 10 min, and refuses
  FAILED rows whose retries are exhausted.
- **3.3** Embedding + summary write-back; a NULL vector keeps the existing embedding.
- **3.6** Upsert on `(lower(name), entity_type)` returns the same id for `SpaceX` / `spacex`;
  1,311 real city names are shared by more than one LOCATION row, which is why LOCATION is excluded.
- **5** `ai_feedback` insert; `/api/v1/feedback` wired to the graph viewer.
- API live: 401 without token, 404/422 with the `{"status":"error"}` shape, upload of
  `../../x.txt` stored as `<uuid>_x.txt` inside `DOC_DIR`, semantic search with a bad key → 502.

**Verified without a database:** 35 core unit tests, 12 API unit tests, `ruff` clean on both Python
repos, UI `tsc` / `eslint` (was 20 errors) / `vite build` clean, `docker compose config` valid.

**Deviations from the plan text:**
- 1.1: AGE rejects a bound-parameter Cypher string ("a dollar-quoted string constant is expected"),
  so the text is wrapped in a per-call random tag `$pia_<128-bit hex>$…$` instead. Data still never
  enters the query text (it goes through the `$1` agtype parameter of a prepared statement), and the
  graph name is validated against `[A-Za-z0-9_]+`.
- 2.8: enrichment now targets entities with no description (not `confidence < 0.5`), since new
  entities are created at 0.5 and would never have been enriched.
- Telegram replies no longer use `parse_mode="Markdown"`; LLM markdown routinely broke Telegram's
  parser and surfaced as "CRITICAL ERROR".
- Added `scripts/backfill_record_embeddings.py` for records ingested before embeddings were persisted.

**Leftovers (not done, on purpose):**
- 0.1: the leaked OpenRouter key must still be **revoked in the OpenRouter dashboard** — only the
  owner can do that. It is removed from the working tree; git history still contains it.
- 1.6 option b (RLS through the API) — deferred, documented as single-tenant.
- 3.8 Wikidata P31 type mapping — rows are stored as `UNKNOWN`; a real mapping needs the relation file.
- The Telegram bot and MCP SSE transport were not exercised end-to-end (no bot token here).
- Nothing is committed; all three repos have uncommitted working-tree changes.

## Order of work and effort

| Phase | Items | Est. effort |
|-------|-------|-------------|
| 0 | key rotation, venv purge, encoding, pins | ½ day |
| 1 | injection fix, auth, postgres, upload, errors, script guards | 1–2 days |
| 2 | 8 broken features | 1–2 days |
| 3 | drain queue, FAILED semantics, embeddings, stale jobs, maintenance, uniqueness, TZ | 2 days |
| 4 | Dockerfile, api.ts, config.py + pool, migrations, sim gate, Cesium | 1–2 days |
| 5 | docs and dead code | ½ day |
| 6 | tests + CI | 1–2 days |

Total ≈ 8–11 working days for one person.

---

## Verification checklist (end state)

```
git grep 'sk-or-v1-' HEAD                                   → nothing
git ls-files | grep -c '^venv/'                             → 0
docker compose build (from clean clone + .env.example)      → OK
curl -s localhost:8001/api/v1/logs                          → 401
curl -H "Authorization: Bearer $T" …/entities/bbox?…        → success, filtered rows
upload PDF via UI → HUMINT rows appear; file in processed/  → yes
SELECT count(*) FROM intelligence_records WHERE embedding IS NOT NULL → > 0 and growing
Archive semantic search "earthquake"                        → returns seismic rows
submit_tasking via Telegram                                 → one queue row, DONE
Invalid OPENROUTER key                                      → jobs FAILED, not DONE
pytest tests/unit                                           → green, no Docker
npx tsc -b && npx eslint . && npx vite build                → 0 errors
```

## Out of scope (separate plans)

- Real ADS-B / AIS feeds (4.6 only gates the fake ones).
- Real multi-tenant auth with per-user tokens and RLS through the API (1.6 option b).
- Building Layer 4 digests and Layer 6 aggregates.
- Wikidata5M full ingestion and embedding of millions of entities (cost model needed first).
- Replacing free-tier rotating LLMs with a stable paid model (affects every quality number in the docs).
