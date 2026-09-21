# GLEIF connector — who owns whom, for the companies the web already knows

**Status:** BUILT 2026-09-21 — seed 3,829 LEIs (2,614 OpenSanctions + 1,288 Wikidata P1278) → grown to 36,555
companies and 59,550 edges in 2 hops → 36,555 records fetched in 13 min (API, cached) → 43,970 facts, 623 of them on
Wikidata nodes. Rosneft card: OWNERSHIP → *RN-Capital · directly consolidated by · gleif · 2025-06-05 · source ↗* and
*Rosneft Deutschland · directly consolidated by · 2021-01-01*. Twin check: 16 merged, 15 ambiguous skipped (rule
tightened on the way: generic institution names join only on a matching country). Deviation from the plan: one fact per
pair — "directly consolidated by" replaces the redundant "ultimately" edge; the relation row remembers every predicate
seen. Was: PLAN 2026-09-21. Follows `missions_and_connectors_plan.md` §1 (connector contract, BUILT) and
the OpenSanctions PEPs load of the same day. Second structured database; first one with *its own* columns
(not FollowTheMoney), so it is the real test of "any database plugs in with a small connector".

---

## 0. Evidence (measured 2026-09-21)

| Fact | Where |
|---|---|
| GLEIF Golden Copy: **3,436,126 LEI records** (companies, funds, branches), daily, CSV/JSON/XML; the LEI file is 504 MB zipped | `goldencopy.gleif.org/api/v2/golden-copies/publishes/lei2/latest` |
| **488,449 relationship records**, 24 MB zipped CSV: `IS_DIRECTLY_CONSOLIDATED_BY` 126,788 · `IS_ULTIMATELY_CONSOLIDATED_BY` 132,946 · `IS_FUND-MANAGED_BY` 151,113 · `IS_SUBFUND_OF` 73,839 · `IS_INTERNATIONAL_BRANCH_OF` 1,959, each with start/end dates, status, and a validation document URL (e.g. an SEC filing) | `…/publishes/rr/latest`, file downloaded and counted |
| Public JSON:API, **no key**, `Accept: application/vnd.api+json` required; endpoints `lei-records/{lei}`, `/direct-parent`, `/ultimate-parent`, `/direct-children`, fuzzy name search; documented limit 60 requests/min | `api.gleif.org/api/v1` (probed) |
| Rosneft's LEI `253400JT3MQWNDKMJE44` → 2 direct children via the API (RN-Capital …); parent 404 (Rosneft reports no parent) | probed |
| We already hold **2,614 LEIs** as hard ids (from OpenSanctions `leiCode`) → the seed set | `external_ids WHERE kind='lei'` |
| Wikidata has LEI as property **P1278** on ~40k items; our backbone does not store it yet | Wikidata |
| Licence: LEI data is public domain (CC0) | GLEIF terms |

## 1. What it adds
A company card gains an **OWNERSHIP** section from the world's official register: *Rosneft — directly
consolidates → RN-Capital (since 2015, SEC filing)*, and upward: *Nayara Energy — ultimately consolidated
by → Rosneft*. Sanctions, PEP and ownership then sit on one node: "this sanctioned company is owned by
that one, whose director is a PEP" — the question every investigation asks. The lines are dashed
(facts, never decaying), source shown, one click to the validation document.

## 2. Design — seed and grow, not "load 3.4 million companies"
Loading every LEI would add 3.4M mostly irrelevant nodes (funds, one-person firms) and slow name
resolution. Instead the connector loads **only what touches something the web already knows**:

1. **Seed** = LEIs on our entities: `external_ids(kind='lei')` (2,614 today) + Wikidata **P1278** for
   backbone ORGs (one-off fetch, stored as external ids under source `wikidata`, kind `lei`) — expect
   ~10k more.
2. **Grow** = from the relationship file (24 MB, nightly), walk **consolidation** edges
   (`IS_DIRECTLY_CONSOLIDATED_BY`, `IS_ULTIMATELY_CONSOLIDATED_BY`, `IS_INTERNATIONAL_BRANCH_OF`) two
   hops up and down from the seed. Fund edges (`IS_FUND-MANAGED_BY`, `IS_SUBFUND_OF`) are skipped in v1
   (150k fund relationships, little intelligence value; a flag turns them on).
3. **Fetch** the LEI records for the grown set through the API (`filter[lei]=…`, up to 200 per page,
   ≤ 60 requests/min → ~30k records in ~10 minutes; cached on disk by LEI so nightly runs only fetch
   new ones). Fallback when the API is unhappy: stream the 504 MB CSV and keep the needed rows.
4. **Emit** the four shapes the engine knows:
   - `Entity(external_id=LEI, kind=ORG, name=legalName (Latin transliteration preferred), aliases=otherNames,
     country=legalAddress.country, properties={legalForm, status, registeredAs, headquarters city},
     other_ids=[("lei", LEI), ("registration", registeredAs)])`
   - `Fact(subject=child LEI, predicate="directly consolidated by" | "ultimately consolidated by" |
     "branch of", object=parent LEI, family="NEUTRAL·ownership", valid_from/to=period, record_ref=validation URL,
     properties={"status", "accounting standard"})`
   - Reporting exceptions ("no parent: natural persons", "non-consolidating") as a property on the company —
     the *absence* of a parent is information.
   - No Documents, no Events.
5. **Identity**: the Ingestor's order already fits — hard id `lei` → Wikidata Q-id (from P1278 seed) →
   name/bare-name (the Rosneft rule from today) → new local ORG. A GLEIF record for a company we know
   lands on its node; a parent we do not know becomes a local ORG carrying its LEI, so the next source
   naming that LEI (OpenSanctions, a document) joins it.

## 3. Changes

| Where | What |
|---|---|
| `pia/connectors/gleif.py` | `GleifConnector(db, hops=2, funds=False)`: seed → relationship walk → API fetch (cached `data/gleif/lei/<LEI>.json`) → items. ~150 lines. |
| `scripts/seed_wikidata_lei.py` | one-off: P1278 for backbone ORGs → `external_ids(source='wikidata', kind='lei')` |
| `agents/connector_agent.py` | register GLEIF after OpenSanctions (env `GLEIF_ENABLED=1`, `GLEIF_HOPS=2`) |
| `kg/relations.py` / card | nothing new: connector facts already draw as `OWNERSHIP` dashed lines with `via_source` and `record_ref`; the card's OWNERSHIP group shows them with dates |
| `pia-ui` | card OWNERSHIP rows show "since 2015 · SEC filing ↗" from `record_ref` (small) |
| tests | mapper (CSV row → Fact, name pick, period parsing), walk (2 hops, fund edges off), API paging stub |

## 4. Order, effort, verification

| Step | Effort | Check |
|---|---|---|
| 1. P1278 seed | ½ d | `select count(*) from external_ids where kind='lei'` ≈ 12k; Rosneft, Gazprom, Huawei have one |
| 2. Relationship walk + API fetch + mapper | 1 d | dry run prints the grown set size (expect 20–40k LEIs) and the first 50 facts |
| 3. Nightly run + card | ½ d | Rosneft card: OWNERSHIP → RN-Capital and the other child, dates, filing link; Nayara Energy → "ultimately consolidated by Rosneft"; a sanctioned shell company shows its parent |
| 4. Twin check | ¼ d | `merge_connector_twins.py --dry` finds < 20 new twins (the LEI seed should have joined most) |

≈ 2¼ days. Running cost: none (public API, 24 MB nightly file).

## 5. Risks, honestly
- **Funds noise** — off by default; turning it on adds ~150k edges and needs a "fund" kind on the card.
- **API limits** — first run ~30k records = ~150 requests at 200/page; well under 60/min. The CSV
  fallback exists if GLEIF throttles.
- **Names** — GLEIF legal names are often in the local script ("публичное акционерное общество …");
  the mapper prefers the Latin `otherNames`/transliterated name for display, keeps the legal name as alias.
- **Ownership ≠ control** — GLEIF says "consolidated by" (accounting), not "owned x%". The predicate keeps
  GLEIF's wording; no percentages are invented.
