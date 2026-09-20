# Access control — design note (build when the first private source arrives)

**Status:** DESIGN 2026-09-20. Not built. The hooks it needs already exist (`client_id` on records and
queue rows, `sources` as the unit of provenance, one API token). Follows `missions_and_connectors_plan.md`
§4 and `PIA_CONCEPT_AND_STATUS_2026-09-20.md` §5.5.

## 0. Why not now
Today PIA holds public data (news, wire, sensors, OpenSanctions) for one person behind one bearer
token. Nothing in it is secret. The moment a private source is plugged in — a government or
company database, a reporter's SPOTREPs, a client's documents — three things become true at once:
some rows must be invisible to some people, every read must be attributable, and deletion must be
real. That is a hard stop before such a source, not a nice-to-have after.

## 1. The model (four ideas, nothing exotic)
1. **Users and roles.** `users (user_id, name, email, role, created_at, disabled_at)`; roles
   `viewer` (read what is visible), `analyst` (+ review, missions, uploads), `admin` (+ users,
   sources, deletion). API tokens become per-user (`api_tokens (token_hash, user_id, label,
   expires_at, last_used)`); the current single token becomes the first admin's.
2. **Visibility lives on the source.** `sources.visibility` = `public | org | restricted`, and for
   `restricted`, `source_grants (source_id, user_id)`. A report, event, fact or entity alias is as
   visible as its `source_id`. Entities themselves are always visible (a name is not a secret); what
   is *said* about them is filtered. This is the whole rule — no per-row ACLs.
3. **Row filters in one place.** The API already goes through `get_pool`; a `visible_sources(user)`
   CTE is joined into every query that returns records, events, relations evidence, aliases, external
   ids, listings and briefs. Briefs are rewritten from visible events only (cache keyed by visibility
   set). The web overview and relations counts use the same filter, so a restricted source never
   changes the picture for someone who cannot see it.
4. **Audit and deletion.** `audit_log (at, user_id, action, object, detail)` written by the API for
   reads of restricted sources, all writes, logins and token use. Deletion is by source or by record:
   `DELETE` cascades (mentions, events, relations rebuilt) and leaves an audit row; entities that lose
   every mention are archived (not deleted — other sources may name them).

## 2. What changes in code (when built)
| Area | Change |
|---|---|
| schema | `users`, `api_tokens`, `source_grants`, `audit_log`; `sources.visibility` (default `public`); migration keeps every existing source public |
| pia-api | `auth.py` resolves a token to a user; `require_role(...)`; `visible_sources` CTE helper; filters in `routers.py`, `kg_router.py`, `missions_router.py`; audit middleware |
| agents | unchanged — collection is not access-controlled; connectors set `visibility` on their source row |
| pia-ui | login (token paste or SSO later), role-aware menus (review/missions/upload for analysts), "restricted" badge on evidence rows |
| relay / sensors | unchanged (public feeds) |

≈ 3 days. No LLM cost.

## 3. What it deliberately does not do
- No document-level classification markings (UNCLASSIFIED // etc. stays cosmetic). If needed, it is
  a `sources.visibility` level, not a new mechanism.
- No field-level redaction. A source is visible or it is not.
- No multi-tenant separation of the knowledge web: one web, filtered. Tenants that must never share
  a graph get their own deployment.

## 4. Verification when built
A restricted source (a SPOTREP reporter) is loaded; a viewer's card for the named entity shows the
public lines only; the analyst with a grant sees the reporter's recorded events; the audit log has
one row per restricted read; deleting the source removes its events and the line they drew, and the
card no longer mentions it.
