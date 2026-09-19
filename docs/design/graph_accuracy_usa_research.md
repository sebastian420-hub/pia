# Graph accuracy and UX — the United States web (research)

**Status:** RESEARCH 2026-09-19 — findings only, nothing built. Owner's question: *"the vocabs
are not expressive enough to be accurate"* — checked against the live data and the browser.
**Follows from:** `web_view_redesign_plan.md` (BUILT). Screenshot: `ui_research/web_04_usa_star.jpg`.

## 1. What the USA web shows (browser + API, measured)

- `GET /api/v1/graph/network/Q30` → 50 nodes, 60 links: **41 COOPERATIVE, 19 HOSTILE**, nothing
  else. 11 of 49 pairs have *both* a red and a green line (Iran, Russia, Canada, Israel, China…).
- The picture is a star: every line goes to the centre; no node labels until hover; no grouping;
  the colours of the nodes (purple country, green place, orange org, blue person) have no legend.
- Wrong or meaningless neighbours in the 50: **China (Q29520, a PLACE)** next to **People's
  Republic of China (Q148)** — two nodes for one country (88 vs 26 events); **Europe**, **Africa**
  (continents as partners); **Executive Office of the President of the United States** as a
  partner of the United States; **Boston, Bergen, California, New South Wales, Mexico City**.

## 2. Where the events come from

USA events: **GDELT 631, LLM 15** (96 % wire data). Top GDELT actions: MEET 154, AGREE 141,
STATEMENT 87, COOPERATE 69, ATTACK 43.

### 2.1 GDELT: what "agree", "meet", "attack" actually mean here
- We keep only the **2-digit root code** (`COL['root']` = column 28) and drop the 4-digit
  `EventCode` (column 26). In a live export, root 05 ("engage in diplomatic cooperation") was
  **051 "praise or endorse" 82×**, 057 "sign formal agreement" 30×. So *"Iran agree United
  States"* mostly means *someone praised something*. MEET = root 04 "consult", which includes
  phone calls and "make a visit".
- We drop `Actor1Type1Code` (column 12: GOV, MIL, COP, JUD, BUS, CVL…). In the same export,
  **51 of 96** rows with Actor1Name = UNITED STATES had **no type at all** — those are stories
  that merely mention America. USA "attack" rows in that file: a Fox News redistricting story, a
  Collider article about a TV producer, a poker tournament in Jeju. In our database: *"United
  States — attack — Garfield County, Oklahoma"* is a murder-trial report; *"Houston — cooperate"*
  is a school band festival. **37 USA-actor GDELT events have no target** (domestic stories).
- The `quote` on GDELT events is **synthesised** (`"Iran agree Washington — New Delhi, India"`),
  so the evidence panel shows a sentence nobody wrote. GDELT has no quote; it has the URL.
- The location is GDELT's *ActionGeo* = where the story is set, often the dateline (New Delhi for
  an Iran–US story).
- Direction is not reliable: both "Washington agree Iran" and "Iran agree Washington" exist for
  the same day.

### 2.2 LLM: fewer, better, still lossy
Iran–US from articles: ATTACK ×3 with real quotes ("the US committed possible war crimes when it
launched two strikes… on February 28"), and `OTHER` for *"The US government has granted visas to
Iranian officials so they can travel to the UN General Assembly"* — a meaningful event with no
verb for it. The 23 actions carry **stance** (hostile/cooperative) but not **subject**: nuclear
talks, tariffs, Greenland, Gaza, visas all collapse into AGREE / ACCUSE / OTHER.

## 3. Diagnosis

| Symptom on screen | Real cause | Vocabulary problem? |
|---|---|---|
| Red + green to almost everyone | GDELT 051 "praise" → AGREE; 04 "consult" → MEET; both become COOPERATIVE; any accusation becomes HOSTILE | partly — the 4 relation kinds are too coarse |
| USA "attacks" Oklahoma, Houston "cooperates" | actor "United States" with no type code = story about America, not the state | no — filtering problem |
| Two Chinas, continents, "Executive Office" | resolver picks the wrong Q-id for GDELT (local-only alias "China" → Q29520 PLACE) and lets continents through | no — identity problem |
| "Evidence" is a made-up sentence | GDELT events have no quote; we fabricate one | no — provenance problem |
| Star with no labels, no legend | web view draws 1-hop only, labels off unless hover | UX |
| Iran–US shows 27 green / 19 red and nothing else | relations summarise stance only; no topic, no "what" | **yes** — this is the expressiveness gap |

Conclusion: the vocabulary is the *smaller* half. Roughly two thirds of what looks wrong on the
USA web is GDELT being ingested at its coarsest, plus identity slips. The remaining third is that
"cooperative / hostile" says *how* but never *what*.

## 4. Directions (for discussion before a plan)

1. **GDELT precision** — read `EventCode` (4-digit) and `Actor*Type1Code`; require GOV/MIL/
   diplomatic types for country-level actors; map sub-codes to finer actions (051 PRAISE, 057
   SIGN_AGREEMENT, 042 VISIT, 173 ARREST, 190 ARMED_ATTACK, 1823 CYBER_ATTACK…); store the URL as
   the evidence and the headline of the source page, not a synthetic quote; use `NumSources` as
   corroboration; drop untyped country actors from the web (keep as reports).
2. **Identity** — force COUNTRY kind for GDELT country codes (ISO3 → Q-id directly, never alias
   search); reject continents and government-seat orgs as *partners* of their own country.
3. **Vocabulary** — keep the ~23 actions (they match CAMEO and are what GDELT can give) but add
   **`topic`** to events (a short controlled list: nuclear, sanctions, trade/tariffs, territory,
   military strike, hostages/visas, energy, migration, elections, tech, aid…) and compute relations
   per **(kind, topic)** so the card can say *"talks on nuclear programme (26) · strikes (19)"*
   instead of *"27 cooperative · 19 hostile"*.
4. **UX** — cluster the star: group neighbours by kind/topic in sectors; labels always on for the
   top N by weight; a legend for node colours; a "what is this about" line per edge on hover.

Order: 1 and 2 first (they are cheap and remove most of the wrong lines), then 3, then 4.
