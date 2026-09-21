# SPOTREP — the human report format

Upload a `.md` or `.json` file (globe → upload button, or drop it in `data/documents/`). The
header and the ENTITIES / EVENTS rows are read exactly as written — nothing is guessed. NOTES
are read by the analyst like an article: quoted, verified, and drawn as lines only when checked.

```
reporter: crow                      # your pseudonym — becomes a source with its own trust
observed: 2026-09-20T08:15Z         # when you saw it (reported: is optional, defaults to now)
location: 26.22, 50.58              # lat, lon of the report (optional)
basis: direct | indirect | hearsay  # how you know
confidence: 0.8                     # 0–1
mission: Gulf                       # optional: the mission this belongs to

ENTITIES:
- Abu Khalid al-Bahraini | person | passport: BH-771; plate: 4471-KZ | seen twice at the port
- Manama Port Authority | org
  (name | kind | ids | notes — kinds: person, org/unit/group/company, country, place, vessel, aircraft)

EVENTS:
- Iran | delivered supplies to | Houthis | 2026-09-19T22:00Z | 15.35, 44.20 | 2
- Manama Port Authority | detained | Abu Khalid al-Bahraini
  (actor | predicate | target | time | lat, lon | stance −3…+3 — the last four are optional)

NOTES:
Free text. Anything here goes through the normal reading, verification and line rules.
```

Who sees it: a reporter is a **restricted** source — only the person who uploaded the report, users an admin grants,
and admins see its entities, events and notes; everyone else's picture is unchanged. An admin can make a reporter
`org` (any signed-in user) or `public` on the admin page.

What happens: every name is matched to the web (Iran → Q794, Houthis → their node; unknown
names become local entities with your ids attached), events become *recorded* events (blue
badge, no verifier — the trust is yours: direct 0.7 · indirect 0.5 · hearsay 0.3, scaled by
confidence), the NOTES become a HUMINT report on the feed and the globe, tagged with the
mission. A rejected report says why (`data/documents/failed/`, agent log): unknown header,
unreadable time, unknown kind, stance out of range, empty report.

JSON form, same keys: `{"reporter": "crow", "observed": "2026-09-20T08:15Z", "basis": "direct",
"confidence": 0.8, "mission": "Gulf", "entities": [{"name": "…", "kind": "person", "ids":
{"passport": "BH-771"}, "notes": "…"}], "events": [{"actor": "…", "predicate": "…", "target":
"…", "time": "…", "place": "15.35, 44.20", "stance": -2}], "notes": "…"}`.
