# The assistant — answers from the web, with sources, within what you may see

**Status:** BUILT 2026-09-21 (same afternoon). `pia-api/assistant.py` — understand → resolve → gather (the card's own
queries, visibility-filtered, numbered, ≤ 6k tokens) → answer with [n] per sentence → sources; `/chat` returns
`reply + data{sources, entities, missing, window_days, kind}`; restricted reads audited. UI: chips under the answer
(event/relation → evidence panel, report → report, entity → card), "N sources of M · last 7 d", suggested questions
(mission-aware). Checked: *"What is happening between Iran and the United States this week?"* → four cited sentences
from verified events ("Iran warned it would launch … attacks against U.S. bases [1][11]…"), chip [11] opens the
Iran ↔ United States evidence panel; *"Who is Abbas Araghchi?"* → Wikidata description + this week's verified visit
to China; *"Who owns Rosneft subsidiaries?"* → GLEIF/OpenSanctions facts (found and fixed on the way: ownership facts
were worded from the asset's side, "Rosneft — owned or controlled by — RN Holding"; now "owns", 4,114 rows relabelled);
*"Anything new today?"* → the day's alerts. Tests: 5 new (21 API). Cost ≈ $0.003/question, ~4 s.
Was: PLAN 2026-09-21. Owner: *"what about assistant? is it working?"* — it answered, but from ten headlines.
**Follows from:** `access_control_plan.md` (BUILT — every answer must respect visibility),
`living_verbs_plan.md` (BUILT — verified events with words and quotes are the material), `missions_and_connectors_plan.md`.

---

## 0. Evidence (measured 2026-09-21)

| Fact | Where |
|---|---|
| `/chat` pastes the **10 most recent report headlines** into a prompt and asks gpt-4o-mini; nothing else. Asked *"What is happening between Iran and the United States this week?"* it answered *"Data is unavailable"* — the ten headlines were aircraft tracks | `pia-api/routers.py:63-98`, tried |
| The web it ignores: 886k entities · 534 verified events with quotes · 230 verified lines · 104 briefs · 577k facts · 658k list entries · 2 missions with alerts | DB |
| Retrieval machinery already exists: pgvector, `text-embedding-3-small`, semantic search over reports (2,620 of 8,804 reports embedded — the ones the analyst read), alias search (`/kg/search`, exact + trigram) | `routers.py:380-430`, `kg_router.py` |
| Every card query is already visibility-filtered (`Visibility.sql`) and audited (`note_restricted`) — the assistant can reuse them | `kg_router.py` |
| The UI copilot is a plain chat box: sends `message` + last 20 turns, shows `reply` as text; no links to what the answer rests on | `pia-ui/src/components/hud/AICopilot.tsx` |
| Cost today: one gpt-4o-mini call per question ≈ $0.001 | OpenRouter |

## 1. What "best" means here
The user's principles apply to the assistant as they apply to the lines: **true, not impressive** — it
says only what the web holds, and shows where each sentence comes from; **clear** — short answer,
sources one click away; **respects who you are** — a viewer's assistant knows nothing a viewer may not
see. The alternatives and why not:
- *Bigger model, same ten headlines* — answers nothing new, just more fluently. No.
- *Free-form tool-calling agent that queries SQL* — powerful, but it can wander, it can be talked into
  reading what it should not, and every answer costs 5–10 calls. Later, maybe; not as the base.
- **Retrieve, then answer (chosen):** a fixed, cheap, auditable pipeline — understand the question,
  pull exactly the card material for the things named, answer from that with citations. Two model
  calls, ~4 s, ~$0.003, and every byte the model sees went through the same visibility filter as the UI.

## 2. How a question is answered

```
question ──► 1. UNDERSTAND (small model call, JSON)
                 entities named · time window (default 7 d) · pair? · kind of question (what happened / who is /
                 why connected / what is new / list)
         ──► 2. RESOLVE   names → entities (alias exact → fuzzy → semantic), visibility-aware, ≤ 4 entities
         ──► 3. GATHER    (visibility-filtered, the card's own queries)
                 per entity: brief · top 12 connections with words + verdict + quote · verified events in the
                             window (date, actor, predicate, target, quote, outlet, verdict) · lists · facts (ownership,
                             PEP posts) · recent reports
                 per pair:  the evidence between them (events + shared reports)
                 always:    semantic search over reports for the question (top 8) · the active mission's alerts (if
                             the question is "what is new") · when nothing is named: the window's strongest verified
                             events overall
                 budget:    ≤ ~6k tokens of context, strongest first (verified > recorded > wire), each item numbered
         ──► 4. ANSWER    (model call) — rules: only from the numbered context; cite [n] after each claim; say
                          "verified / recorded / wire" when it matters; say plainly what the web does not hold;
                          ≤ 150 words unless asked for more; no invented dates, numbers or names
         ──► 5. RETURN    reply + sources[] {n, kind: event|report|relation|entity|fact|listing, id, label, url}
                          + entities[] (for the UI to open cards) ; restricted reads audited as everywhere else
```

Worked example — *"What is happening between Iran and the United States this week?"* → UNDERSTAND: Iran, United
States, 7 d, pair → GATHER: evidence Iran↔US (7 verified events: *Iran accused the US of…* [1], *US threatened
Iran…* [2]…), briefs of both, 4 reports → ANSWER: three sentences with [n], "no verified cooperative event this
week; the wire shows 14 more signals" → sources chips under the answer, click → evidence panel.

## 3. Changes

| Where | What |
|---|---|
| `pia-api/assistant.py` (new) | `understand(question, history) -> Plan`; `resolve(conn, names, vis)`; `gather(conn, plan, vis) -> Context` (reuses the card/evidence SQL, extracted into small functions in `kg_router.py`); `answer(context, question, history) -> (reply, sources)`; `ASSISTANT_MODEL` env (default = `LLM_MODEL`; a stronger model is one line) |
| `routers.py` `/chat` | calls the pipeline; returns `{reply, sources, entities, window}`; `note_restricted` on what was gathered; rate limit 30/min per user |
| `pia-ui` `AICopilot.tsx` | source chips under each answer (event → evidence panel, report → report, entity → card); "answered from N sources · window 7 d"; three suggested questions (from the active mission and the day's top pairs); history kept |
| tests | understand-JSON parsing (bad JSON, empty names); context budget ordering (verified before wire; cut at budget); citation check (every `[n]` in the reply exists in sources; reply with none → "not in the web" prefix); viewer vs grantee: the same question, restricted event only in the grantee's context (fake pool) |
| docs | `STATUS.md`: what the assistant knows and does not |

## 4. Order, effort, verification

| Step | Effort | Check |
|---|---|---|
| 1. `understand` + `resolve` | ¼ d | "Iran and the US this week" → {Iran Q794, United States Q30, 7 d, pair}; "who is Abbas Araghchi" → {Q…, who-is}; "what is new" → {mission} |
| 2. `gather` from the card queries, with budget | ½ d | the Iran↔US context lists the 7 verified events with quotes, no wire above them; a viewer's context has no `reporter:*` rows |
| 3. `answer` + citations + `/chat` response shape | ¼ d | the example question gives three cited sentences; "who owns Rosneft's subsidiaries" cites GLEIF facts; a question about nothing in the web answers "not in the web" |
| 4. UI chips + suggestions | ¼ d | click [2] opens the Iran–US evidence panel on that event |
| 5. Tests + docs | ¼ d | 8 new API tests |

≈ 1½ days. Running cost ≈ $0.003 per question (two gpt-4o-mini calls + one embedding).

## 5. Not in this plan (deliberately)
Free-form tool use / SQL by the model; writing anything (missions, notes) from chat; voice; memory across
sessions beyond the 20-turn history; a stronger model by default (one env line when wanted).

## 6. Risks, honestly
- **It will still say "not in the web" often** — because the web is thin outside the news of the last
  weeks. That is the truthful answer; the fix is more sources, not a looser prompt.
- **Name resolution in questions** ("the Guards", "Riyadh") — the same resolver rules as the analyst
  (government seats, demonyms, collectives) apply; misses show as "I could not find X" so the user can rephrase.
- **Context budget** — a country like the US has hundreds of connections; the budget keeps the strongest
  12 and says so ("and 40 more").
