# Are the lines true? — audit of the events behind the globe arcs

**Status:** RESEARCH 2026-09-19 — findings only. Owner: *"I feel like it is not accurate."*
**Method:** took the strongest pairs, sampled 7 GDELT events each at random, fetched the real
headline of each source page, and judged whether the coded event matches the story.

## 1. Sample (verbatim headlines)

| Pair · kind (count) | Coded as | Real headline | Verdict |
|---|---|---|---|
| Ukraine–Russia · COOPERATIVE (72) | Russia MILITARY_AID Ukraine | "Russia Hits Container Ship With Cargo for Ukrainian Forces" | **wrong** (the opposite) |
| | Russia RELEASE Ukraine | "Children among injured in Russian barrage on Ukraine" | **wrong** |
| | Russia COOPERATE Ukraine | "Ukraine, Russia trade fresh strikes after Trump's assurance" | **wrong** |
| | Russia NEGOTIATE Ukraine | "Poland warns Russia is planning drone strikes on NATO territory" | **wrong** |
| | Russia NEGOTIATE Ukraine | "Russian strikes kill 9 … as Zelenskyy offers to meet Putin" | half (talk offer exists) |
| | Ukraine AGREE Russia | "Ukraine war briefing: new anti-drone weapon scores hit" | **wrong** |
| | Russia NEGOTIATE Ukraine | "Zelenskyy arrives in Canada, wants more support to fight Russia" | **wrong** |
| Ukraine–Russia · HOSTILE (64) | Russia ARMED_ATTACK Ukraine | "8 killed in Russian strikes on Ukraine" | right |
| | Ukraine ATTACK Russia | "Ukrainian drones kill 2 in Russia as Moscow hits port hub" | right |
| | Russia ARMED_ATTACK Ukraine | "Zelenskyy urges more pressure on Russia for civilian deaths" | right |
| | Ukraine SANCTION Russia | "Speaker Johnson recesses the House early…" | **wrong** |
| | Ukraine ARMED_ATTACK Russia | "Poland strengthens eastern defenses after Russian strikes" | wrong direction |
| China–US · COOPERATIVE (134) | US HOST China | "Trump plans to greet Xi at air base on arrival" | right |
| | US HOST China | "US hands over 64 smuggled artefacts to China before summit" | right |
| | China AGREE US | "A detained US scholar's wife asks Trump for help as Xi's visit nears" | weak |
| | US HOST China | "US nearly launches military operation over AI-generated information" | **wrong** |
| EU–Mark Carney · COOPERATIVE (62) | Carney VISIT EU / EU HOST Carney ×30 | "Canada seeks closer EU ties…" (one story, many outlets) | right, but **one story counted ~30 times** |

Rough score: **hostile / material lines ≈ 70 % right; cooperative / verbal lines ≈ 30 % right**
(Ukraine–Russia "cooperative" is 0 for 7). The strongest cooperative arcs are the least reliable.

## 2. Why (measured)

1. **Syndication counts as many events.** Dedup is per `(pair, action, day, outlet)`; a wire
   story reprinted by 30 sites becomes 30 events. EU–Carney: two stories → 62 events.
2. **Three quarters of GDELT events are "verbal".** 3,251 of 4,319 kind-bearing GDELT events are
   codes 01–05 / 11–13 (statement, appeal, intent, consult, praise, disapprove, threaten) — the
   classes GDELT itself codes worst; only 1,068 are material (aid, agreements, sanctions, force).
   Cooperative arcs are 87 % verbal.
3. **Direction and role are guessed from sentence order.** "Russia hits ship with cargo for
   Ukrainian forces" → *Russia gives military aid to Ukraine*. Nothing in our pipeline reads the
   sentence; only the LLM path does, and it covers 4 feeds.
4. **Only 509 of 6,438 GDELT events have ≥ 3 sources**; the rest are single-source rows that we
   still count at 0.5–0.6 confidence.

## 3. What would make a line true

| Fix | Effect | Cost |
|---|---|---|
| **A. Count stories, not copies** — dedup per `(pair, action, day)`; outlets accumulate on the event; `event_count` = story-days | EU–Carney 62 → ~4; every count becomes "how many distinct story-days", not "how syndicated" | small |
| **B. Verbal events do not draw lines alone** — arcs and wheel lines use material events + agreements + visits/hosting + accusations/threats with ≥ 2 sources; statements / intents / praise stay on the card as "talk" | Ukraine–Russia cooperative line disappears; China–US stays (visits, handovers) | small |
| **C. Verify before drawing** — an agent fetches the article behind each GDELT event that would feed an arc (≥ 3 story-days) and asks the LLM: *does this text say A did ACTION to B?* → keep with the quote, or reject | wrong-direction and wrong-story rows go; every line gets quotes; ≈ 300 checks/day ≈ $0.3/day | 1 day |
| **D. Show what is verified** — solid = verified (has quotes); faint = GDELT-only | the picture is honest about its own confidence | small |

Recommendation: A + B now (an afternoon), C + D next (a day). After A+B the counts drop
sharply — that is the point.

## 4. Re-audit after "true lines" (2026-09-20, ~14 h of reading)

Same method: 7 random **verified** events behind each of the 5 strongest verified lines, judged
against their own quote and source.

| Line (verified events) | Right | Wrong / weak |
|---|---|---|
| Ukraine–Russia · HOSTILE (40) | 7 | one quote is thin ("shortly after CIA Director… visited Moscow") but the event (Russian strike) is real |
| Houthis–Saudi Arabia · HOSTILE (30) | 6 | "pipeline struck by a militia in Iraq" credited to the Houthis — wrong actor |
| Iran–United States · HOSTILE (23) | 7 | — (Feb 28 strikes, Iranian missile strikes on US warships, "economic D-Day" sanctions, accusations) |
| Trump–Denmark · COOPERATIVE (15) | 7 | all the same Greenland agreement, reported by 7 outlets — right, but one story counted 7× |
| Modi–Xi · COOPERATIVE (11) | 7 | — (BRICS summit meeting, border "essential basis" statements) |

**33 / 35 ≈ 94 % right** (was ≈ 30 % for cooperative and ≈ 70 % for hostile wire lines).
Remaining weaknesses: (1) one story syndicated to many outlets is counted once per article on the
verified ledger too — fix: dedup verified events per (pair, action, day) with an outlet list, as
the wire already does; (2) occasional wrong actor when an article discusses several militias;
(3) items whose Wikidata labels exist only in non-Western languages show as bare Q-ids — fetch
labels in all languages for relation targets.
