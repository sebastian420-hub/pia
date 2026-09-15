# PIA Project Status

**Updated:** 2026-09-14 (after the fix plan in `docs/fix_implementation_plan.md`)
**Classification:** Prototype. Single-tenant. Not production.

This file describes what the code does today. Marketing language from earlier
versions ("Tier-1 Operational", "100% stable") has been removed because it did
not match the code.

## What works

| Area | State | Notes |
|------|-------|-------|
| News ingestion (RSS) | Working | BBC, Al Jazeera, NYT, The Verge. Dedup by URL + content hash. |
| Seismic ingestion (USGS) | Working | Real feed, polled every 60 s, UTC timestamps. |
| Document ingestion (PDF/TXT) | Working (after migration 001) | Upload via API → shared folder → `document_agent` chunks → HUMINT records. Failed files go to `failed/`, not lost. |
| Heartbeat trigger → analysis queue | Working | Every new record queues one analyst job and emits `pg_notify`. |
| Analyst swarm | Working | Drains the queue, retries failed jobs 3×, re-claims stale jobs after 10 min, writes embedding + summary back to the record. Needs `OPENROUTER_API_KEY`. |
| Entity resolution + relationships | Working | Lexical + semantic match, verb allowlist, non-LOCATION names unique per type. |
| Apache AGE graph mirror | Working, parameterised | Names travel as Cypher parameters; labels are validated. |
| API bridge | Working | Bearer token required. Connection pool. Real HTTP status codes. |
| Live WebSocket | Working | `ws://host/ws/live?token=…` |
| 3D globe / ticker / archive / graph viewer | Working | Loads last 100 records on start. Token-free OSM imagery unless `VITE_CESIUM_ION_TOKEN` is set. |
| Semantic search (records + entities) | Working once records have embeddings | Records ingested before this fix have no embedding; run `scripts/backfill_record_embeddings.py` or let new records accrue. |
| Human feedback on relationships | Working | `POST /api/v1/feedback`; 👍/👎 in the graph viewer. Rejections feed the analyst's negative examples. |
| MCP server | Working | Bound to `127.0.0.1:8000` on the host. No auth — do not expose. |
| Telegram bot | Working, untested end-to-end in this pass | Only registered tools with declared arguments can be called. |

## What is simulated

- **Aviation (ADS-B) and Maritime (AIS) agents emit hardcoded demo data.** There is no real feed.
  They only run when `SIMULATED_SENSORS=true`; their records are labelled `[SIM]`, source
  `SIMULATED … Feed`, confidence 0.1, and the UI shows a `SIM` badge.

## What is not built

- **Layer 4 – Strategic Digests** (`intelligence_digests`): table exists, nothing writes it.
- **Layer 6 – Continuous aggregates**: one Timescale aggregate on `flight_tracks` exists; nothing reads it.
- `agent_tasks`, `entity_profile_history`, `cluster_revisions`, `satellite_positions`: reserved tables, no writer.
- **Multi-tenancy**: row-level security policies exist in the schema, but the API connects as the
  table owner and does not set a client id. The system is single-tenant. See plan item 1.6.
- **Wikidata5M bulk seed**: ingestor is fixed (commits, parameterised inserts, `UNKNOWN` type) but
  has not been run at scale; embedding millions of entities has no cost plan.
- Real ADS-B / AIS feeds.

## Known limits

- Extraction quality depends on the free-tier OpenRouter models in `LLM_MODEL_POOL`; expect rate
  limits (jobs go to `FAILED` and are retried, not silently marked `DONE`).
- One embedding call per extracted entity name per record; cost scales with entity count.
- The graph network endpoint caps at 3 hops and 500 edges.

## Verification status of the fix pass

- Without a database: 35 core unit tests + 12 API unit tests pass, `ruff` clean, UI `tsc` / `eslint` /
  `vite build` clean, `docker compose config` valid.
- On a real PostgreSQL + AGE database (throwaway container): schema + migrations apply; injection
  attempts are stored as literal names; bbox, claim/retry, embedding write-back, entity upsert,
  feedback and orphan cleanup all behave. Details in `docs/fix_implementation_plan.md` →
  "Implementation log".
- Not exercised end-to-end: the full agent swarm with a live LLM key, the Telegram bot, MCP over SSE.
  Run `make up && make test` then `pytest -m integration tests/integration`.
