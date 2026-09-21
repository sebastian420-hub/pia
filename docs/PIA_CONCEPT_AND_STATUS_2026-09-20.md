# PIA — Concept, System, Status, and What Comes Next

**Written:** 2026-09-20, from the live system (numbers measured at ~14:00Z).
**Supersedes** `PIA_CONCEPT_AND_SYSTEM.md` (09-19) for the current picture; that file and
`PIA_STATE_AND_VISION.md` (09-15) remain the history. The implementation plan for what comes next is
`design/missions_and_connectors_plan.md`.
**Repos / branch:** `pia efa5d4d`, `pia-api 49c9837`, `pia-ui a696b2a` — all on `web-view-redesign`
(merge to `main` pending). Size: 5,800 lines Python, 1,700 API, 3,700 TypeScript; 8 migrations;
75 + 12 + 7 tests.

---

## 1. The concept, as agreed with the owner

**A personal intelligence agency in a box.** It collects the world's information, turns it into one
connected web of *who is who* and *who did what to whom*, and lets one person investigate like a
team. Collection and understanding are automated, around the clock; the human does the judging.

Principles the owner set, in order of how often they came up:
1. **True, not impressive.** A line exists only if something someone wrote proves it. Less, but trusted.
2. **Organised but adaptable.** Fixed skeleton (identities, families, stance scale); open vocabulary
   (verbs grow from the news). No hard-coded lists that break on the next phrasing.
3. **Lasting solutions.** Fix the cause for every case, not the example in front of us.
4. **Clear, not messy.** Far: the picture on a globe. Near: one thing and everything around it, in
   words, with evidence one click away.
5. **Self-maintaining.** Review pages help; nothing waits on them.

How it is meant to be used: **collect broadly, look narrowly.** The system gathers everything it can;
a *mission* decides what matters now. **Any input**: news and wire today; human reports in a fixed
format; later any database the owner can get. **One engine**: every source becomes the same three
things — entity, event, document — and lands on the same identities, so sources enrich each other.

---

## 2. How it works today (follow one article)

```
COLLECT     news_agent (4 RSS) · gdelt_agent (wire, every 15 min) · reader_agent (400 GDELT articles/day)
            aviation · maritime · seismic · camera · document upload
                 │
UNDERSTAND  analyst ×3  ─ prompt v3 ─►  entities (Wikidata Q-id or local) · mentions ·
                                        events: predicate · verb (catalogue) · family · stance −3…+3 ·
                                                modality (asserted/intended/claimed/hypothetical/denied) ·
                                                polarity · topic · quote · confidence
            enrichment agent ─►  verifier (2nd model call: yes / partly / no) · briefs · relations (hourly) ·
                                 Wikidata facts · verb embeddings
                 │
PRESENT     globe (web layer: verified arcs; reports, events, cameras) · wheel (one entity, partners on a
            fixed ring, list) · card (brief · connections in words + verdict · 30-day strip) · evidence
            (verified quotes, then wire signals) · archive (search, tables) · review (names · verbs) ·
            assistant (answers from the web with [n] sources, within what the user may see — 09-21)
```

- **Wire vs verified.** GDELT's coded guesses are kept as *wire* signals (faint, off by default on the
  globe) and used to decide which articles to read. Only article-read events that the verifier
  confirmed draw lines.
- **Living verbs.** 12 families (HOSTILE force/coercion/sanction/accusation/threat · COOPERATIVE
  agreement/aid/support/meeting · NEUTRAL role/ownership/statement); 75 verbs, 5 created by the
  model this afternoon (*ban, drop, remove, assert, approve*). Stance is judged per event, never
  read off the verb.
- **Identity.** Wikidata backbone (66,308 items), 34,138 GeoNames cities, local entities for what
  Wikidata lacks (854, all in review), government seats and bodies collapsing to their country.

## 3. Status (measured)

| Area | Number | Note |
|---|---|---|
| Reports | 8,095 (964 with full text; 800 read on the wire's advice) | 4 RSS feeds + GDELT-chosen articles |
| Article-read events | 1,286 (19 since prompt v3 at 11:58Z) | v3 events carry stance / modality |
| Verifier | 158 yes · 108 partly · 74 no (340 judged) | ~46 % of pre-v3 events pass cleanly — the reason the verifier exists |
| Wire events | 5,008 (story-days, not copies) | hints only |
| Relations | 271 event-based, 245 with ≥ 1 verified event | lines on the globe/wheel |
| Briefs | 29 | entities with ≥ 2 verified events |
| Names in review | 854 | growing ~300/day; harmless, but see §5 |
| Sensors | 3,371 cameras, ADS-B, AIS, USGS | unchanged this week |
| Accuracy | verified lines 33/35 ≈ 94 % (09-20 morning audit); v3 + verifier re-audit due 09-21 | `design/arc_accuracy_audit.md` |

Running cost ≈ $1/day (extraction + reader + verifier + briefs), one Docker host.

**Known weak spots**
- Input breadth: four feeds and what GDELT points at. The picture is "the news", not "your question".
- ~~No mission: Ed Sheeran and Iran carry equal weight.~~ Built 09-20 evening: missions (see plan, steps 2–3).
- ~~Review queue for names grows.~~ Self-maintaining since 09-20 evening; watch that it stays flat.
- Items whose Wikidata labels exist only in non-Western languages show as bare Q-ids (fetch all-language labels).
- ~~One shared token; no users, roles, audit.~~ Access control built 09-21.

## 4. How the real tools do it, and what we take from them

- **Palantir Gotham** — ontology of objects/links, every fact traced to its document, map + graph +
  timeline + card, humans build the knowledge. We share the shape; ours *fills itself*
  ([Inside Gotham](https://goldingresearch.substack.com/p/inside-palantir-gotham)).
- **Recorded Future** — a card opens with an AI summary, then evidence per rule, then validated
  relationships. Our brief / verdict badges / evidence panel follow this
  ([Intelligence Cards](https://www.recordedfuture.com/blog/intel-cards-overview)).
- **OCCRP Aleph / OpenSanctions — the idea worth adopting now.** Investigative journalism has an
  open, mature **data model for structured sources**: *FollowTheMoney* — schemata for Person,
  Company, Vessel, Sanction, Ownership, Directorship, Payment…, each with properties and links,
  used by OCCRP's Aleph and by OpenSanctions' 463-source database of sanctions, PEPs and watchlists,
  downloadable free for non-commercial use as JSON
  ([FollowTheMoney](https://github.com/opensanctions/followthemoney),
  [entity structure](https://www.opensanctions.org/docs/entities/),
  [bulk data](https://www.opensanctions.org/docs/bulk/)). Adopting FtM as the *interchange format*
  for structured sources means: any database that can be exported to FtM (and the OCCRP ecosystem
  has converters for many) plugs into PIA with one connector — and OpenSanctions becomes the first,
  harmless, high-value structured source (who is sanctioned, who is politically exposed, who owns
  what).

## 5. What comes next (agreed direction; details in the plan)

1. **Connectors and external IDs** — one interface every source implements (entity / event /
   document + provenance), an `external_ids` table (their ID ↔ our entity), FtM as the wire format
   for structured data; **OpenSanctions as the first connector** (sanctions, PEPs, ownership). BUILT 09-20/21:
   sanctions (73k entities, 169k facts), PEPs (723k people, 998k positions), **GLEIF** ownership register
   (36k companies around the ones the web knows, 44k consolidation facts) — three databases on one web.
2. **Missions** — BUILT. A mission is a collection plan: countries, area, feeds, watchlist, topics, alert
   rules. Broad collection continues; the mission scores relevance (every 15 min), and the globe, feed,
   alerts and web follow the active mission (`MISSION ▾` in the status bar; "show all" lifts it).
3. **Human reports in a fixed format** — BUILT. SPOTREP (`docs/SPOTREP_FORMAT.md`): upload a `.md`/`.json`;
   entities and events are read as written, NOTES like an article; reporters are sources with their own trust.
4. **Self-maintaining names** — BUILT. The review queue decides its clear cases itself (collectives →
   their country/group, spelling variants, demonyms, quiet names); review stays optional.
5. **Access control** — BUILT 09-21. Users (viewer / analyst / admin) with their own tokens, sign-in
   screen, a row is as visible as its source (public · org · restricted + grants), lines built from the
   shared picture only, audit log, real deletion, admin page. Private sources can come in now.

Not now: golden-set nightly scoring (phase 2 of the verbs work), situation briefs, wall mode, relay.

## 6. Operating notes
```
docker compose up -d                 postgres (volume at /home/postgres/pgdata/data!) → pia_init → agents → api
python scripts/seed_verbs.py         verb catalogue (idempotent); scripts/seed_wikidata_backbone.py --offline (2 min)
python scripts/reread.py --headline "…"    re-read articles with the current prompt
READER_DAILY_BUDGET / VERIFIER_DAILY_BUDGET / BRIEF_BATCH / VERIFIER_MODEL / BRIEF_MODEL   in .env
/review → names · verbs             optional curation
```
