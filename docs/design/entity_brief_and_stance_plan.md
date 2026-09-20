# Say what is going on — stance that is right, cards that explain, a picture that stays clean

**Status:** PLAN v2 2026-09-20 — §2 replaced after the owner asked for *"a real solution that lasts for every edge case"*: stance is no longer derived from a verb table (§2A), every line-forming event gets an independent check (§2B), and human corrections feed a golden set that scores the extractor every night (§2C). Owner: *"for Ed Sheeran it is showing up on the globe but it is still not
describing enough, and it's showing [PACBI] with a Palestine organisation [as cooperative] but it is
actually being boycotted by them… make sure it shows right information and easy for users to see
everything but not messy."*
**Follows from:** `true_lines_plan.md` (BUILT — lines are 94 % right), `web_map_and_wheel_plan.md`.

---

## 1. What was found

### 1.1 The wrong colour (codebase + database)
The event behind the green line:

> Palestinian Campaign for the Academic and Cultural Boycott of Israel → Ed Sheeran · **APPEAL** ·
> "We now extend our call for boycotting Ed Sheeran's entire world tour…"

The quote is right; the verb is wrong. The extractor chose `APPEAL` ("a call for…"), and the
ontology maps `APPEAL → COOPERATIVE (+1)`, so a boycott call became a green line. Two causes:
- **`APPEAL` is treated as cooperative.** In CAMEO, 02 *appeal* is "verbal cooperation" — but a
  call *against* someone is not cooperation. Our vocabulary has no `BOYCOTT`.
- **The prompt gives no rule for calls-to-action against a target** ("call to boycott / condemn /
  cancel / sanction" → hostile). 81 article-read events are `APPEAL`; 3 of them contain
  boycott / condemn / sanction in the quote.

Same family of error: `STATEMENT` (377) and `OTHER` (197) are the two biggest verbs the
extractor uses — 46 % of article-read events say nothing about stance or subject.

### 1.2 "Not describing enough" (browser)
The Ed Sheeran card shows: Wikidata line ("English singer-songwriter"), mention trend, aliases,
a verb count list (`threaten 1 · appeal 2 …`), connections with counts, recent reports. Nothing
says **what is happening**: *Robert Kraft threatened to cancel Sheeran's Boston show if Macklemore
performs; PACBI extended its boycott call to the whole tour.* The reader has to open each
connection and read quotes to find out.

### 1.3 How the real tools do it (web)
- **Recorded Future Intelligence Cards**: a card opens with an **AI-written summary** ("AI
  Insights") of what matters now, then the risk score with the **evidence for each triggered
  rule**, then relationships that are "technically validated" with their sources
  ([Inside the Intelligence Card](https://www.recordedfuture.com/blog/intel-cards-overview),
  [Intelligence Graph](https://www.recordedfuture.com/platform/intelligence-graph),
  [AI data sheet](https://assets.recordedfuture.com/Datasheets/2026_0313%20-%20Recorded%20Future%20AI.pdf)).
- **Palantir Gotham**: every object has a view with **typed, labelled links** (not colours),
  a **timeline** of the linked events, and an immutable **provenance trail**; the graph is a
  whiteboard you build, not a hairball you receive
  ([Inside Palantir: Gotham](https://goldingresearch.substack.com/p/inside-palantir-gotham),
  [Object views](https://www.palantir.com/docs/foundry/object-views/widgets-visualization)).
- Common pattern: **summary first, evidence one click away, relationships named in words**
  ("called for boycott of", "threatened to cancel show"), a **time axis**, and a **relevance /
  risk** number so noise sinks. Colour is a hint, never the message.

### 1.4 "Ed Sheeran on the globe" (relevance)
The report is real news (a Boston concert dispute over antisemitism) and correctly placed. It is
noise only relative to a *purpose* — which is the missions concept, not built yet. Until then the
feed's domain filter is the only lever, and the report is tagged POLITICAL, so it shows.

---

## 2. Design — why a verb table can never be the answer, and what is

Today one LLM choice (the verb) decides three different things at once: *what happened*, *whether
it is friendly or hostile*, and *what it is about*; then a static table turns the verb into a
colour. Every new phrasing ("called for a boycott", "recalled its ambassador", "recognised the
state", "refused to rule out") is a new chance for the table to be wrong. Adding BOYCOTT fixes
one word. The durable fix is to stop asking the verb to carry the stance, and to check every
line-forming event independently, and to learn from corrections. This is how event-extraction
standards (ACE / ERE) and the intelligence tools do it: an event has **polarity, modality,
and a predicate in words**, separate from its type.

### A. The event carries its own stance, modality and words (extractor)
Each extracted event gets, from the model reading the sentence:
- **`predicate`** — the action in the article's own words, ≤ 8 words: *"called for a boycott
  of"*, *"threatened to cancel the show of"*, *"met with"*. This is the label the UI shows.
  No table needed; it reads right for every phrasing.
- **`stance`** — the act's effect on the target, judged directly: −3 … +3 (−3 attack, −2
  sanction / boycott / threat, −1 criticism, 0 neutral, +1 praise / support, +2 agreement /
  aid, +3 alliance / rescue). The colour and the hostile/cooperative ledger come from `stance`,
  never from the verb.
- **`modality`** — *asserted* (it happened), *claimed* (someone says it happened), *intended*
  (announced / planned / threatened to), *hypothetical* (if / could / would), *denied*.
  Only *asserted* events draw lines; *intended* ones count at half weight and say so
  ("threatened to…"); the rest stay on the card as context.
- **`polarity`** — did it happen or is it negated ("did not sanction", "refused to meet").
  Negated events never draw lines.
- `action` (the 23-verb code) stays as a best-effort category for grouping and GDELT parity,
  and `topic` stays. The prompt shows six worked edge cases: boycott call, denial, threat vs
  act, third-party claim, reversed direction ("X was attacked by Y"), and a quote about a
  third party.

### B. Every line-forming event is checked before it draws a line (verifier)
The reading pass extracts; a second, independent pass judges. For every asserted event of a
pair that would become a line (≥ 1 verified event), a **verifier** call gets the quote, the
surrounding paragraph and the structured event and answers: *does the text state that ACTOR
did PREDICATE to TARGET (this direction)? stance −3…+3? modality?* → `verifier_verdict` (yes /
partly / no), `verifier_stance`. Disagreement → the event is not drawn (shows on the card as
"unverified"). This is the 5/5 test from `true_lines_plan.md`, made permanent. ≈ 300–600
calls/day ≈ $0.1–0.2/day. A different model for the judge (e.g. a stronger one at low volume)
is one env variable.

### C. Corrections become the standard (golden set + nightly score)
- Any event can be marked **wrong / right / wrong stance / wrong direction** from the evidence
  panel and the card (the `ai_feedback` table already exists; it gets `field` and `correct_value`).
- Corrections form a **golden set** (`data/golden_events.jsonl`, checked in). Every night the
  extractor and the verifier are re-run on the golden set; the score (precision on stance,
  direction, modality) is stored and shown in the status bar as *"extraction 94 %"*. A drop
  below a threshold raises an alert in the feed. A random 30-event sample is also judged by the
  verifier each night (the audit I did by hand, automated) so the score covers new data too.
- The 20 most relevant corrections are injected into the extraction prompt as examples
  (nearest by embedding to the article), so a corrected mistake does not recur.

### D. The card explains (brief, why, timeline) — as in v1
- **Brief**: 3–5 sentences from verified quotes only, sources in brackets, regenerated when the
  event set changes (≈ $0.06/day).
- **Why** on every connection: `predicate` + quote + verdict badge (verified / unverified).
- **30-day strip** of the entity's events.

### E. Relevance (missions) — separate plan
The Ed Sheeran-on-the-globe question is "what matters to me", which only a mission can answer.

## 3. Changes

| Repo | Change |
|---|---|
| `pia` | migration 008: `events.predicate, stance, modality, polarity, verifier_verdict, verifier_stance`; `entity_briefs`; `ai_feedback.field / correct_value`. Prompt v3 with the six edge cases; analyst stores the new fields; `kind` = from stance (≤ −1 hostile, ≥ +1 cooperative) for llm events; `kg/relations`: only `modality = asserted AND polarity AND verifier_verdict = yes` count as verified; new `verifier_agent.py` (queue: line-forming unverified events; `VERIFIER_MODEL`); `scripts/golden_set.py` (export corrections, nightly score) + enrichment writes briefs and the nightly score; `APPEAL → None` and the relabel script as a bridge for the 81 old rows |
| `pia-api` | card: `brief`, `why` (predicate + quote + verdict), `timeline`; evidence: verdicts; `POST /feedback` accepts `field` + `correct_value`; `GET /kg/quality` (nightly score) |
| `pia-ui` | EntityInspector: brief, connection rows with predicate + quote + badge, strip; evidence panel: "wrong / wrong stance / wrong direction" buttons; status bar: extraction score |
| docs | `STATUS.md`: what a card shows |

## 4. Order and verification
1. A (schema + prompt v3 + analyst) → re-read the 12 articles behind the audit's wrong / weak events: the PACBI event comes back `predicate = "called for a boycott of"`, `stance = −2`, `modality = asserted`; the "Iraqi militia" pipeline strike no longer lands on the Houthis; "threatened to cancel" is `intended`.
2. B (verifier) → the 35 audited events re-judged: ≥ 33 yes; the 2 wrong ones no.
3. C (feedback + golden set + nightly score) → mark 5 events wrong in the UI; `scripts/golden_set.py score` prints precision; status bar shows it.
4. D (brief, why, strip) → Ed Sheeran card opens with the brief; connection row reads `Robert Kraft — threatened to cancel the show of · "Kraft told Sheeran…" · verified`.
5. Full re-audit (35 events) after 24 h → target ≥ 95 % with the verifier on. Screenshots `ui_research/card_02_brief.jpg`.

Effort: A 1 day · B ½ day · C ½ day · D ¾ day ≈ 3 days. Running cost ≈ $0.2–0.3/day extra.

## 5. Not covered
- Relevance / missions (E) — separate plan, the one the owner has been circling since 09-16.
- Situation briefs (clusters) — same mechanism, later.
- Fixing verbs in already-stored wire events — they never draw lines now.
