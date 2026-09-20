# Living verbs — an event vocabulary that grows on its own, a stance that is judged, lines that are checked

**Status:** BUILT 2026-09-20 — catalogue (65 seed verbs, 12 families, embeddings), prompt v3, analyst
storing predicate / verb / family / stance / modality / polarity, verifier step (budget 800/day), briefs,
card (brief · connection words · verdict badge · 30-day strip), evidence and wheel list with the words,
Verbs tab. Checked on the Ed Sheeran articles: PACBI → Ed Sheeran now *call for a boycott of · stance −2 ·
verified*; three hallucinated events ("Macklemore called for a boycott of Ed Sheeran", "Ed Sheeran called for
a boycott of Palestine") were **rejected by the verifier**, so they draw nothing. Step 6 (re-audit after 24 h)
pending. Lesson recorded: worked examples in the prompt must be invented, never the story under test — the
model copied "call for a boycott of" into unrelated events until they were changed.
Was: PLAN (v3 of the stance work; replaces §2 of `entity_brief_and_stance_plan.md`).
**Decisions with the owner today:** (1) no hard-coded verb list — verbs are an open catalogue under fixed
families; (2) the catalogue **maintains itself** — review is optional, never a bottleneck; (3) stance and
"did it happen" are judged per event, separate from the verb; (4) every line-forming event is checked by an
independent pass; (5) the golden set / nightly score is phase 2.
**Follows from:** `true_lines_plan.md` (BUILT, 94 %), `arc_accuracy_audit.md`.

---

## 1. Evidence from the code and data (2026-09-20)

| Fact | Where |
|---|---|
| 1,278 article-read events, using only **22 distinct verbs**; `STATEMENT` 377 and `OTHER` 197 = 45 % of them say nothing | `events` |
| The verb → colour table is consulted in 4 places: analyst (`ACTIONS[action][1]` = kind, `[2]` = tone), GDELT agent, `kg/relations.py` (`ACTION_KIND_SQL`), and the UI sector rule (`sectorOfKind`) | grep |
| The prompt lists 23 verbs and 20 topics inline; the parser keeps any event with `actor` and `action` | `core/nlp.py:96-121,148` |
| Embeddings are available (`generate_embedding`, text-embedding-3-small, pgvector installed) — enough to match "bombed" to "strike" without a person | `core/nlp.py:175`, `00_extensions.sql` |
| `ai_feedback` exists (`event_id, feedback_type, human_correction`) with three fixed types; no field-level correction | schema, `routers.py:529` |
| Enrichment agent runs steps every poll and rebuilds relations hourly — the natural home for the verifier queue and the verb matcher | `enrichment_agent.py:29-38` |
| Volume: ~100 article-read events/day now; 400 read articles/day budget → ~600 events/day at most | `events` |

## 2. The model

```
families (fixed, ~12)         verbs (open, self-maintaining)            events (one per act)
──────────────────────        ─────────────────────────────────         ─────────────────────
HOSTILE   force               strike · shell · occupy · …               predicate  "launched strikes on"  (article's words)
          coercion            arrest · expel · blockade · …             verb_id    → strike
          sanction/boycott    impose sanctions on · call for a          stance     −3          (judged for THIS event)
                              boycott of · divest from · …              modality   asserted | intended | claimed | hypothetical | denied
          accusation          accuse · condemn · …                      polarity   true | false ("did not…")
          threat              threaten · warn · …                       topic, quote, confidence, verifier_verdict
COOPERATIVE agreement         sign an agreement with · agree to · …
          aid                 send aid to · fund · …
          alliance/support    back · endorse · defend · …
          meeting             meet · visit · host · call · …
NEUTRAL   role                appoint · resign · elect · …
          ownership           acquire · invest in · …
          statement           say · announce · deny · …
```

- **Family** decides the wheel sector and the default colour family; **stance** (−3…+3) decides the
  colour and the hostile/cooperative ledger; **modality + polarity** decide whether it draws a
  line at all; the **predicate** is what people read; the **verb** keeps counts and labels
  consistent ("strike ×3").
- A verb row: `verb_id, verb (canonical phrase), family, default_stance, status (auto | curated |
  merged_into), examples (up to 5 quotes), embedding, seen_count, created_by (model | human)`.

## 3. How an event flows

1. **Read.** The analyst prompt (v3) lists the families with their current top verbs (≤ 8 per
   family, from the catalogue, ~500 tokens) and six worked edge cases (boycott call, denial,
   threat vs act, third-party claim, passive voice, quote about a third party). For each event
   the model returns `predicate, verb (from the list, or a new phrase), family, stance,
   modality, polarity, topic, quote, confidence`.
2. **Match.** `kg/verbs.py::canonical(predicate, family)`: exact/alias hit → that verb; else
   embedding similarity to verbs in the same family ≥ 0.86 → that verb (predicate stored as
   alias); else a **new verb** is created in that family with `status = auto`, `default_stance =
   stance`. No human in the loop. Guard: a family the model invents is mapped to the closest
   family by stance (≤ −1 → HOSTILE·accusation, ≥ +1 → COOPERATIVE·alliance, else NEUTRAL·statement).
3. **Store.** `events` gets the new columns; `kind` = HOSTILE if stance ≤ −1, COOPERATIVE if
   ≥ +1, else NULL (for llm events; wire events keep the CAMEO mapping, which is expressed as
   catalogue verbs too). `weight_class` = material unless modality ≠ asserted.
4. **Verify (before a line).** The verifier step in the enrichment agent takes asserted events of
   pairs with ≥ 1 verified-candidate event and no verdict yet, sends `quote + ±400 chars of the
   article + the structured event` to `VERIFIER_MODEL` and stores `verifier_verdict` (yes /
   partly / no), `verifier_stance`. Relations count an event as verified only when
   `origin = llm AND modality = asserted AND polarity AND verifier_verdict = yes`; `partly` and
   unverified events appear on the card as such. Budget `VERIFIER_DAILY_BUDGET` (default 800).
5. **Show.** Card / wheel list / evidence use `predicate` ("called for a boycott of"), stance
   colour, a *threatened to / claimed / denied* prefix from modality, and a verified badge. The
   brief is written from verified quotes. Counts by verb ("strike ×3") come from `verb_id`.
6. **Curate (optional).** `/review` gains a **Verbs** tab: new auto verbs of the last 7 days
   with family, stance, examples, seen count; actions: rename, move family, set default stance,
   merge into another verb (aliases follow), reject (events keep the predicate; the verb is
   hidden from the prompt). Nothing waits on this.

## 4. Changes

| Repo | Change |
|---|---|
| `pia` | migration 008: `verbs`, `verb_aliases`; `events.predicate, verb_id, family, stance, modality, polarity, verifier_verdict, verifier_stance, verified_at`; `entity_briefs`. `kg/verbs.py` (seed from the current 23 + CAMEO table into families; `canonical()`; prompt block builder). `core/nlp.py` prompt v3 + parser (new fields, validation, family guard). `analyst_agent.store_events`: match + store; `kind` from stance. `gdelt_agent`: map CAMEO codes to catalogue verbs (seeded rows). `enrichment_agent`: `verify_pending()` step + `write_briefs()` step. `kg/relations.py`: verified = asserted ∧ polarity ∧ verdict = yes; `verified_topics` unchanged. Tests: canonical matching (exact, alias, embedding-stub, new), family guard, parser, relations rule. |
| `pia-api` | `GET /kg/verbs` (+ `POST /kg/verbs/{id}` rename / move / merge / reject); card connections carry `why` = {predicate, quote, modality, verdict}; evidence events carry the new fields; `GET /kg/entities/{key}` gains `brief` and `timeline` (30 d). |
| `pia-ui` | `/review` Verbs tab; EntityInspector: brief, connection rows `Actor — predicate · badge · "quote"`, 30-day strip; PartnerList and wheel tooltip use predicate + stance; evidence shows modality prefix and verdict. Colours from stance. |
| docs | `STATUS.md` (what a line means, what a verb is), `PIA_CONCEPT_AND_SYSTEM.md` §2.1 step 3–7. |

## 5. Order and verification

| Step | Check | Expected |
|---|---|---|
| 1. Migration + `kg/verbs.py` + seed | `select family, count(*) from verbs group by 1` | 12 families, ~70 seeded verbs (23 + CAMEO fine actions) |
| 2. Prompt v3 + analyst + matcher | re-read the PACBI article (`scripts/reread.py <uid>`) | `predicate = "called for a boycott of"`, `family = HOSTILE·sanction/boycott`, `stance = −2`, `modality = asserted`; "threatened to cancel" → `modality = intended` |
| 3. Verifier step | run once on the 35 audited events | ≥ 33 `yes`, the Houthi/Iraqi-militia one `no` |
| 4. Relations rule + API + UI | Ed Sheeran card | red line to PACBI labelled *called for a boycott of · verified*; Kraft row reads *threatened to cancel the show of · threat*; brief on top |
| 5. Verbs tab | read 200 new articles | new auto verbs appear with families; rename one; the card label changes |
| 6. Re-audit (35 events) after 24 h | as before | ≥ 95 % right |

Effort: 1 (½ d) · 2 (1 d) · 3 (½ d) · 4 (1 d) · 5 (½ d) ≈ 3½ days. Running cost ≈ $0.2–0.3/day.

## 6. Phase 2 (not now)
Golden set from corrections, nightly self-score in the status bar, corrected examples injected
into the prompt, situation briefs, relevance/missions.

## 7. Risks, honestly
- **Stance drift between sentences** (−1 vs −2 for the same act): harmless for colours,
  slightly noisy for counts; the verifier's stance is what the ledger uses.
- **Verb sprawl inside a family** (strike / hit / bomb as three verbs): the embedding merge at
  0.86 catches most; the Verbs tab merges the rest; counts by family are always clean.
- **Double LLM cost per line-forming event**: bounded by the verifier budget; wire-only pairs
  are never verified.
- **Non-English articles**: predicates come back in English by instruction; if a model returns
  another language the matcher still works on embeddings.
