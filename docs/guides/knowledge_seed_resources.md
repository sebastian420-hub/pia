## THE COMPLETE PIA KNOWLEDGE SEED RESOURCE LIST

Organized in the exact order you should ingest them — foundation first, then historical intelligence, then conflict data, then live feeds.

***

## TIER 1 — GEOGRAPHIC FOUNDATION

*Ingest first. Everything else needs coordinates.*

**1. GeoNames — World Geographic Database**

- **URL:** https://www.geonames.org/export/
- **Direct download:** http://download.geonames.org/export/dump/allCountries.zip
- **What:** 11 million place names worldwide with lat/lon, country, population, elevation[^1][^2]
- **Format:** TSV (tab-separated), free, updated daily
- **License:** Creative Commons Attribution
- **Size:** ~1.5 GB uncompressed
- **Ingest as:** LOCATION entities in your entities table

**2. OSMNames — OpenStreetMap Place Names with Bounding Boxes**

- **URL:** https://osmnames.org/download/
- **What:** 21 million place names with full hierarchy + bounding boxes[^3]
- **Format:** TSV, free
- **License:** Open Database License (same as OpenStreetMap)
- **Size:** ~3 GB uncompressed
- **Ingest as:** LOCATION entities with `geo_bbox` bounding polygons — critical for PostGIS spatial queries

***

## TIER 2 — WORLD KNOWLEDGE GRAPH

*Ingest second. Populates your entity graph before any live collection.*

**3. Wikidata Full Dump**

- **URL:** https://www.wikidata.org/wiki/Wikidata:Database_download
- **Direct download:** https://dumps.wikimedia.org/wikidatawiki/latest/
- **What:** 112 million entities, all relationships, all descriptions[^4][^5]
- **Format:** JSON or RDF (Turtle), free
- **License:** Creative Commons CC0 (public domain)
- **Size:** ~100 GB compressed (filter to ~5GB for relevant entities)
- **Ingest as:** entities + entity_relationships tables + Apache AGE graph
- **Note:** Filter to entities with >10 Wikipedia sitelinks to reduce noise — gives ~5 million high-quality entities

**4. Wikidata5M — Curated Subset (Recommended Starting Point)**

- **URL:** https://deepgraphlearning.github.io/project/wikidata5m
- **What:** 5 million entities pre-filtered with Wikipedia descriptions and relations[^5]
- **Format:** TSV triples, free
- **Size:** ~2 GB
- **Ingest as:** entities + entity_relationships — faster to start than full dump

***

## TIER 3 — DECLASSIFIED INTELLIGENCE

*The historical intelligence baseline. Gives your system 75 years of CIA analytical context.*

**5. CIA FOIA Electronic Reading Room (Primary)**

- **URL:** https://www.cia.gov/readingroom/home
- **What:** All publicly released CIA documents — FOIA releases, historical collections, CREST archive[^6][^7]
- **Format:** PDF, searchable online, no bulk download API — requires scraping
- **License:** US Government public domain
- **Volume:** 30+ million pages released since 1995[^8]

**6. CIA CREST 25-Year Program Archive (Specific Collection)**

- **URL:** https://www.cia.gov/readingroom/collection/crest-25-year-program-archive
- **What:** 10+ million pages of CIA records reviewed under the 25-year declassification program[^9][^8]
- **Highlights:** National Intelligence Estimates, Central Intelligence Bulletins, Director memos
- **Ingest as:** HISTORICAL UIRs with `tags = ['historical', 'declassified', 'CIA', 'CREST']`

**7. CIA Historical Collections (Thematic)**

- **URL:** https://www.cia.gov/readingroom/historical-collections
- **What:** Curated collections on specific topics — Cold War, Cuban Missile Crisis, Korean War, Vietnam, Berlin, Kissinger[^8][^6]
- **Why:** Pre-organized by topic — easier to ingest thematically than raw CREST
- **Start here** before the full CREST archive

**8. National Security Archive (George Washington University)**

- **URL:** https://nsarchive.gwu.edu
- **What:** Declassified NSC, State Department, Defense Department documents obtained through FOIA[^10]
- **Highlights:** Coup histories, nuclear policy, Cold War coups, diplomatic cables
- **License:** Free to access, free for research use

**9. State Department FOIA — Historical Diplomatic Cables**

- **URL:** https://foia.state.gov/search/collections.aspx
- **What:** Declassified diplomatic cables and foreign policy records[^11]
- **Format:** PDF, searchable
- **Why:** Complements CIA documents with diplomatic context

**10. National Archives — CIA Records**

- **URL:** https://www.archives.gov/research/intelligence/cia
- **What:** Physical and digitized CIA records held at National Archives[^12]
- **Highlights:** JFK assassination records (partially released), Church Committee materials

**11. FBI Vault — Declassified Investigations**

- **URL:** https://vault.fbi.gov
- **What:** Declassified FBI investigation files — organized crime, Cold War counterintelligence, historical surveillance
- **Format:** PDF, free, searchable online
- **Ingest as:** HISTORICAL UIRs with `domain = 'POLITICAL'` or `domain = 'INFRASTRUCTURE'`

***

## TIER 4 — CONFLICT \& VIOLENCE DATA

*Geo-tagged events with coordinates — perfect UIR seeds.*

**12. ACLED — Armed Conflict Location \& Event Data**

- **URL:** https://acleddata.com
- **Download:** https://acleddata.com/conflict-data/download-data-files
- **What:** Every armed conflict event and protest globally since 1997, with GPS coordinates[^13][^14][^15]
- **Format:** CSV/Excel, free with registration
- **Coverage:** 1997–present, real-time updates weekly
- **Volume:** 1.3+ million geo-tagged events
- **Note:** Requires free account registration[^14]
- **Ingest as:** UIRs with `source_type = 'OSINT'`, `domain = 'MILITARY'`, geo-coordinates direct from data

**13. Global Terrorism Database (GTD)**

- **URL:** https://www.start.umd.edu/gtd-download
- **What:** 200,000+ terrorist incidents worldwide since 1970, all geo-tagged[^16][^17][^18]
- **Format:** Excel/CSV, free with brief registration form
- **Coverage:** 1970–2020 (most recent release)
- **License:** Non-commercial research use
- **Ingest as:** UIRs with `domain = 'MILITARY'`, `tags = ['terrorism', 'historical', 'GTD']`

***

## TIER 5 — MILITARY \& ECONOMIC BASELINE

**14. SIPRI Arms Transfers Database**

- **URL:** https://www.sipri.org/databases/armstransfers
- **Direct access:** https://armstransfers.sipri.org
- **What:** Every international transfer of major conventional arms since 1950[^19][^20]
- **Format:** Online query + CSV export, free
- **Updated:** Annually (last update March 2025, covers 1950–2024)[^19]
- **Ingest as:** UIRs with `domain = 'MILITARY'`, `source_name = 'SIPRI'`

**15. SIPRI Military Expenditure Database**

- **URL:** https://www.sipri.org/databases/milex
- **What:** Military spending for every country since 1949
- **Format:** Excel, free download
- **Why:** Gives your system economic baseline for military capability assessment

**16. World Bank Open Data**

- **URL:** https://data.worldbank.org
- **API:** https://api.worldbank.org/v2/
- **What:** Every country's GDP, trade, debt, population since 1960[^1]
- **Format:** JSON API or CSV bulk download, fully free
- **Why:** Economic context for every geopolitical event your system monitors

**17. UN Comtrade — Global Trade Flows**

- **URL:** https://comtradeplus.un.org
- **What:** Bilateral trade data between every country pair since 1962
- **Format:** CSV via API, free tier available
- **Why:** "Who sells what to whom" — critical for sanctions evasion and supply chain intelligence

***

## TIER 6 — OFFSHORE \& FINANCIAL NETWORKS

**18. ICIJ Offshore Leaks Database**

- **URL:** https://offshoreleaks.icij.org
- **Data download:** https://offshoreleaks.icij.org/pages/database
- **What:** Panama Papers, Pandora Papers, Paradise Papers — shell company networks and beneficial ownership[^10]
- **Format:** CSV bulk download, completely free
- **Volume:** 810,000+ offshore entities with relationship graphs
- **Ingest as:** entities + entity_relationships — these map directly to your Apache AGE graph schema
- **This is rare:** A pre-built corporate relationship graph you can directly import

***

## TIER 7 — HISTORICAL BOOKS \& TEXTS

**19. Project Gutenberg — 75,000 Free Books**

- **URL:** https://www.gutenberg.org
- **Bulk download:** https://github.com/pgcorpus/gutenberg (standardized corpus pipeline)[^21][^22]
- **API:** https://gutenbergapi.com[^23]
- **What:** Every public domain book — history, military theory, geography, political philosophy[^24][^25]
- **Format:** Plain text, free, no registration
- **Key categories to prioritize:**
    - History — Ancient: gutenberg.org/ebooks/bookshelf/659
    - History — Modern (1750+): gutenberg.org/ebooks/bookshelf/662
- **Ingest as:** 2,000-token chunked UIRs with `tags = ['historical', 'literature']`

***

## TIER 8 — REAL-TIME LIVE FEEDS

*Start collecting after seed ingestion is complete.*

**20. OpenSky Network — Live Flight Tracking**

- **URL:** https://opensky-network.org
- **API:** https://opensky-network.org/apidoc/rest.html
- **What:** Real-time ADS-B flight positions globally, free REST API
- **Rate:** 5-second position updates, free tier available

**21. USGS Earthquake Feeds — Seismic Events**

- **URL:** https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
- **What:** Real-time global earthquake data, GeoJSON format
- **Rate:** Updated every minute, completely free, no registration

**22. CelesTrak — Satellite TLE Data**

- **URL:** https://celestrak.org/SOCRATES/
- **TLE data:** https://celestrak.org/SOCRATES/
- **What:** Two-Line Element sets for all tracked satellites — use with SGP4 propagator for real-time positions
- **Rate:** Updated daily, free

**23. MarineTraffic — Vessel AIS Positions**

- **URL:** https://www.marinetraffic.com/en/ais-api-services
- **What:** Real-time AIS vessel position data
- **Note:** Paid API for real-time; free tier available for historical data

***

## INGESTION ORDER SUMMARY

```
WEEK 1:  GeoNames + OSMNames (geographic foundation)
WEEK 2:  Wikidata5M (entity graph skeleton)
WEEK 3:  World Bank + SIPRI + UN Comtrade (economic baseline)
WEEK 4:  ACLED + GTD (conflict event UIRs)
WEEK 5:  ICIJ Offshore Leaks (corporate relationship graph)
WEEK 6+: CIA CREST + NSA + FBI Vault (background processing
          by Kimi K2.5 — runs for weeks)
ONGOING: Project Gutenberg (background, low priority)
THEN:    Start live collection agents
```


***

## One Important Note

**CIA CREST, NSA documents, FBI Vault, and GTD** do not have bulk download APIs — they require either scraping or manual batch downloads. Cortex should handle the scraping pipeline. **ACLED and GTD require free registration** before downloading. Everything else is direct download with no gates. All of it is legal, public domain or openly licensed, and appropriate for personal research use.[^7][^18][^9][^6][^14]
<span style="display:none">[^26][^27][^28][^29][^30][^31][^32][^33][^34][^35][^36][^37]</span>

<div align="center">⁂</div>

[^1]: https://www.geonames.org/export/

[^2]: http://download.geonames.org/export/dump/

[^3]: https://osmnames.org/download/

[^4]: https://lod-cloud.net/dataset/wikidata

[^5]: https://deepgraphlearning.github.io/project/wikidata5m

[^6]: https://www.cia.gov/readingroom/home

[^7]: https://www.cia.gov/readingroom/what-electronic-reading-room

[^8]: https://www.cia.gov/readingroom/historical-collections

[^9]: https://www.cia.gov/readingroom/collection/crest-25-year-program-archive

[^10]: https://guides.library.harvard.edu/usdeclassifieddocs/agency

[^11]: https://foia.state.gov/search/collections.aspx

[^12]: https://www.archives.gov/research/intelligence/cia

[^13]: https://acleddata.com

[^14]: https://acleddata.com/conflict-data/download-data-files

[^15]: https://en.wikipedia.org/wiki/Armed_Conflict_Location_and_Event_Data

[^16]: https://www.start.umd.edu/news/gtd-data-now-downloadable

[^17]: https://www.start.umd.edu/gtd-faqs

[^18]: https://www.start.umd.edu/gtd-download

[^19]: https://www.sipri.org/databases/armstransfers

[^20]: https://www.sipri.org/databases

[^21]: https://www.gutenberg.org

[^22]: https://github.com/pgcorpus/gutenberg

[^23]: https://gutenbergapi.com

[^24]: http://www.gutenberg.org/ebooks/subject/58

[^25]: http://www.gutenberg.org/ebooks/subject/2091

[^26]: https://www.cia.gov/readingroom/document-type/crest

[^27]: https://www.reddit.com/r/holofractal/comments/y2a0qo/is_there_a_place_where_i_can_download_a_complete/

[^28]: https://research.lib.buffalo.edu/fedgov/declassified

[^29]: https://poldham.github.io/places/

[^30]: https://libguides.northwestern.edu/c.php?g=428800\&p=2925763

[^31]: https://bellingcat.gitbook.io/toolkit/more/all-tools/acled

[^32]: https://www.esri.com/arcgis-blog/products/arcgis-living-atlas/announcements/armed-conflict-data-now-available-in-arcgis-living-atlas

[^33]: https://www.linkedin.com/company/acleddata

[^34]: https://journals.sagepub.com/doi/10.1177/0022343310378914

[^35]: https://phacnetwork.utah.edu/data-overview/conflict-violent-event.php

[^36]: https://nasalifelines.org/lifelines-gallery/armed-conflict-location-event-data-project-acled/

[^37]: https://www.cao.go.jp/pko/pko_j/info/other/other_link_43.html

