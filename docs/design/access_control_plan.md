# Access control — implementation plan

**Status:** BUILT 2026-09-21 (all five steps, one afternoon). Migration 012; `auth.py` resolves tokens to users (the
old `PIA_API_TOKEN` became the owner's admin token — nothing broke); roles on every write; visibility fragment in 33
queries + the WebSocket fan-out; relations, co-mentions, briefs and mission alerts built from public+org only, restricted
events shown on top with a badge to those granted; entities born from a restricted source hidden with it; audit of
writes, admin actions and restricted reads; real deletion by report or by source; sign-in screen, session, role-aware
chrome, admin page (users, tokens, sources, grants, audit); SPOTREP reporters restricted by default and granted to
the uploader. **Verified with one restricted SPOTREP (reporter `crow`)**: viewer — no card row, no timeline, no feed
item, no search hit, no WebSocket message; analyst with a grant — the row (*recorded · restricted*), the event, the
feed item, the socket message, and an audit row `read_restricted`; admin — the same plus deletion:
`DELETE /sources/reporter:crow` removed 1 report, 1 event, 1 alias, 3 ids, archived the one entity only it named, and
the card no longer mentions it. Tests: API 16 (was 12), unit 101. Deviation from §2: the filter is written as
"NOT IN (restricted sources the user may not read)" instead of "IN visible" — same result, zero cost when nothing is
restricted. Was: PLAN 2026-09-21.
**Follows from:** `missions_and_connectors_plan.md` §4, `gleif_connector_plan.md` (BUILT).

---

## 0. Evidence (measured 2026-09-21)

| Fact | Where |
|---|---|
| **One shared bearer token** for everything; it is compiled into the browser bundle (`VITE_API_TOKEN`), so anyone who can open the UI holds the API key | `pia-api/auth.py`, `pia-ui/src/lib/api.ts:6,21` |
| 40 REST endpoints + 1 WebSocket, all behind that token; no notion of who is calling | `routers.py`, `kg_router.py`, `sensors_router.py`, `missions_router.py`, `main.py:130` |
| 33 queries read `intelligence_records` / `events` / `relations` — the rows that carry what a source said | grep |
| Every row that says something carries its source: `intelligence_records.source_id`, `events.source_id`, `relations.via_source` (facts) / `source` (events, wikidata, cooccurrence), `entity_aliases.source`, `external_ids.source_id`; `entities.listings[]` items carry `list` and `url` but **not** the source id (658,503 entities have listings) | schema, data |
| `client_id` columns exist on records and queue rows from schema v1 — unused (all zeros) | 6 columns |
| Briefs are written from verified quotes of events; `mission_relevance`, `mission_memory`, alerts are derived from records/events | `kg/briefs.py`, `kg/missions.py` |
| Live feed: Postgres `NOTIFY` → one fan-out to every WebSocket; the payload has `source_id` | `06_heartbeat_trigger.sql`, `main.py` |
| Cameras/sensors, GDELT, Wikidata, OpenSanctions, GLEIF are public data; `reporter:*` (SPOTREP) sources are the first candidates for restriction | `sources` |
| API tests: 12 (`tests/test_api_validation.py`); no auth tests beyond "missing token → 401" | tests |

## 1. The model (unchanged from the design note, made concrete)

```
users        user_id, name, email, role (viewer | analyst | admin), disabled_at
api_tokens   token_hash (sha256), user_id, label, created_at, expires_at, last_used_at
sources      + visibility  public | org | restricted      (default public — nothing changes for today's data)
source_grants source_id, user_id                         (only for restricted sources)
audit_log    at, user_id, action, object, detail jsonb   (writes, restricted reads, logins, deletions)
```

**One rule:** a row is as visible as its source. `visible_sources(user)` = all `public` + all `org` (any
signed-in user) + `restricted` with a grant (or role admin). Entities are always visible (a name is not
a secret); what is *said* about them is filtered. No per-row ACLs.

**Roles:** `viewer` reads; `analyst` + review, missions, uploads, verb edits, feedback; `admin` + users,
tokens, source visibility, grants, deletion.

## 2. Where the filter goes (the whole list)

| Endpoint | Rows | Filter |
|---|---|---|
| `/archive`, `/reports/{uid}`, `/event/{uid}`, `/search/semantic`, `/chat` (context rows), `/missions/{id}/alerts`, `/clusters/active` | `intelligence_records` | `source_id IN visible` (alerts: `source_agent='mission_alerts'` are system rows → org) |
| `/kg/events`, `/kg/entities/{key}/events`, card `timeline`/`why`/`event_counts`/`recent_reports`, `/kg/relations/{a}/{b}` events, `/kg/web/overview` counts, `/graph/network` | `events` | `source_id IN visible` |
| card `relations`, `/graph/network`, `/kg/relations` relations, overview links | `relations` | `source='events'`: recomputed counts from visible events (see §3); `source='connector'`: `via_source IN visible`; `wikidata`/`cooccurrence`: public |
| card `aliases`, `external_ids`, `listings` | `entity_aliases.source`, `external_ids.source_id`, `listings[].source` | `IN visible` (listings gain a `source` key at write time — migration backfills from `url`/`list`) |
| card `brief` | `entity_briefs` | briefs are cached per entity; a restricted event must never leak through a brief → briefs are written **from public+org events only** (one brief per entity), and the card shows a "+ N restricted events" line to users with a grant |
| WebSocket `/ws/live` | notify payload | the handshake resolves the user; the fan-out skips payloads whose `source_id` the socket may not see |
| `/kg/verbs`, `/sensors*`, `/layers`, `/health`, `/logs` | none (public / system) | role only (`/logs` admin, `/kg/verbs` POST analyst) |
| writes: upload, feedback, review, verbs, missions | — | role `analyst`; missions `DELETE` admin; every write → `audit_log` |

## 3. The hard part: relations built from events
`relations` rows for `source='events'` are aggregates (hourly rebuild) over *all* events. A restricted
event must not change the line a viewer sees. Two options; the plan takes the second:
1. rebuild relations per visibility set — combinatorial, no;
2. **rebuild counts from public+org events only** (`kg/relations.py` gets `WHERE visible`), and the
   evidence / card / overview add the restricted events **on top, at query time, only for users who may
   see them** (a `restricted_count` per pair, computed live). Lines on the globe and wheel are therefore
   the shared truth; a grantee sees extra evidence rows and a "+ N restricted" badge, never a different
   picture. Simple, honest, and it keeps the hourly rebuild cheap.

## 4. Changes

| Repo | Change |
|---|---|
| `pia` | migration 012: `users`, `api_tokens`, `source_grants`, `audit_log`, `sources.visibility` (default `public`), `listings[].source` backfill; first admin + token minted from the current `PIA_API_TOKEN` (so nothing breaks on deploy). `connectors/base.py`: listings carry `source`; connector `source` dict gains `visibility`. `kg/relations.py`, `kg/briefs.py`: public+org only. SPOTREP: a reporter source is created `restricted`, granted to the uploader. |
| `pia-api` | `auth.py`: token → `User` (hash lookup, cached 60 s), `require_role(...)`, `visible_sources(user)` (cached per request); `visibility.py` helper producing the SQL fragment; filters in the 33 queries (§2); `audit.py` middleware; `users_router.py`: `GET /me`, admin `users` / `tokens` / `sources/{id}/visibility` / `grants`; WebSocket per-socket filter; `DELETE /sources/{id}` and `DELETE /reports/{uid}` with cascade + audit. Tests: viewer vs grantee vs admin on the same restricted SPOTREP (fixtures), role denials, audit rows. |
| `pia-ui` | token no longer in the build: a **sign-in screen** (paste a token; stored in `localStorage`; `/me` shows name + role); role-aware chrome (REVIEW / upload / mission edit / verb edit only for analysts; an ADMIN page for users, tokens, source visibility, grants, audit); "restricted" badge on evidence rows and cards; sign-out. |
| docs | `STATUS.md` / concept doc: who sees what; `SPOTREP_FORMAT.md`: reporters are restricted by default |

## 5. Order, effort, verification

| Step | Effort | Check |
|---|---|---|
| 1. Migration + users/tokens + `auth.py` resolving a user; UI sign-in; existing token = admin | ¾ d | old token still works; a new viewer token sees the app read-only; `/logs` is 403 for viewer |
| 2. Visibility on sources + filters on records/events/aliases/ids/listings + WebSocket | 1 d | a SPOTREP from reporter `crow` (restricted): viewer's card for the named entity shows no `recorded` row, no alias from crow, no HUMINT report; the analyst with a grant sees them; feed over WebSocket never shows crow's report to the viewer |
| 3. Relations/briefs from public+org; `restricted_count` on top | ½ d | globe/wheel identical for viewer and grantee; grantee's evidence panel has the extra rows and the badge |
| 4. Audit + deletion + admin page | ¾ d | every restricted read and every write has an audit row; deleting source `reporter:crow` removes its report, events, aliases, ids, the line they drew, and the card no longer mentions it |
| 5. Tests + docs | ¼ d | API tests ≥ 25; unit tests for `visible_sources` and the SQL fragment |

≈ 3¼ days. Running cost: none.

## 6. Not covered (on purpose)
Field-level redaction; classification markings; multi-tenant graphs; SSO/OAuth (a token paste is enough
for one team; SSO is a later swap inside `auth.py`); rate limiting; encryption at rest (the host's job).

## 7. Risks, honestly
- **Leaks through derived data.** Briefs, mission alerts, cooccurrence relations and the copilot all read
  rows. Each is listed in §2; the tests in step 2 exercise every one with the same restricted fixture.
- **33 hand-edited queries.** Mitigated by one helper that builds the fragment and one fixture that fails
  loudly if any endpoint returns a restricted row to a viewer.
- **Performance.** `source_id IN (…)` over a few hundred sources is an index hit; the live
  `restricted_count` is per pair on the card, not on the overview.
- **The token in localStorage** is the usual trade-off for a single-page app; tokens expire and can be
  revoked by an admin.
