"""
Countries must resolve by their everyday names. Wikidata's English label for Q148 is
"People's Republic of China" and its aliases do not include "China" — so "China" matched a
region and three towns. This adds, for every COUNTRY entity:
  1. Wikidata P1813 (short name) values, fetched in batches (best effort, needs network)
  2. a curated list of common names the wire and the press actually use
Idempotent (ON CONFLICT DO NOTHING). Run once after the backbone load, or whenever it changes.
"""
import os
import sys

sys.path.append(os.path.join(os.getcwd(), "src"))
from loguru import logger

from pia.core.database import DatabaseManager
from pia.kg import wikidata
from pia.kg.normalize import normalize

COMMON_NAMES = {
    "Q148": ["China", "Mainland China"],
    "Q30": ["United States", "America", "US", "USA", "U.S."],
    "Q145": ["United Kingdom", "UK", "Britain", "Great Britain"],
    "Q159": ["Russia", "Russian Federation"],
    "Q794": ["Iran", "Islamic Republic of Iran"],
    "Q858": ["Syria", "Syrian Arab Republic"],
    "Q423": ["North Korea", "DPRK", "Democratic People's Republic of Korea"],
    "Q884": ["South Korea", "Republic of Korea", "ROK", "Korea"],
    "Q881": ["Vietnam", "Viet Nam"],
    "Q819": ["Laos", "Lao PDR"],
    "Q213": ["Czechia", "Czech Republic"],
    "Q865": ["Taiwan", "Republic of China", "ROC"],
    "Q219060": ["Palestine", "State of Palestine", "Palestinian Authority", "Palestinians"],
    "Q974": ["DR Congo", "DRC", "Democratic Republic of the Congo", "Congo-Kinshasa"],
    "Q971": ["Congo", "Republic of the Congo", "Congo-Brazzaville"],
    "Q836": ["Myanmar", "Burma"],
    "Q55": ["Netherlands", "Holland"],
    "Q43": ["Turkey", "Türkiye", "Turkiye"],
    "Q1008": ["Ivory Coast", "Côte d'Ivoire", "Cote d'Ivoire"],
    "Q1050": ["Eswatini", "Swaziland"],
    "Q221": ["North Macedonia", "Macedonia"],
    "Q217": ["Moldova", "Republic of Moldova"],
    "Q750": ["Bolivia"],
    "Q717": ["Venezuela"],
    "Q924": ["Tanzania"],
    "Q702": ["Micronesia"],
    "Q921": ["Brunei"],
    "Q778": ["Bahamas", "The Bahamas"],
    "Q1005": ["Gambia", "The Gambia"],
    "Q1011": ["Cape Verde", "Cabo Verde"],
    "Q801": ["Israel"],
    "Q851": ["Saudi Arabia", "Saudi", "KSA"],
    "Q878": ["UAE", "United Arab Emirates", "Emirates"],
    "Q79": ["Egypt"],
    "Q796": ["Iraq"],
    "Q889": ["Afghanistan"],
    "Q843": ["Pakistan"],
    "Q668": ["India"],
    "Q183": ["Germany"],
    "Q142": ["France"],
    "Q38": ["Italy"],
    "Q29": ["Spain"],
    "Q212": ["Ukraine"],
    "Q36": ["Poland"],
    "Q17": ["Japan"],
    "Q16": ["Canada"],
    "Q155": ["Brazil"],
    "Q96": ["Mexico"],
    "Q408": ["Australia"],
    "Q664": ["New Zealand"],
    "Q252": ["Indonesia"],
    "Q928": ["Philippines"],
    "Q869": ["Thailand"],
    "Q833": ["Malaysia"],
    "Q334": ["Singapore"],
    "Q258": ["South Africa"],
    "Q1033": ["Nigeria"],
    "Q114": ["Kenya"],
    "Q115": ["Ethiopia"],
    "Q1049": ["Sudan"],
    "Q805": ["Yemen"],
    "Q822": ["Lebanon"],
    "Q810": ["Jordan"],
    "Q846": ["Qatar"],
    "Q398": ["Bahrain"],
    "Q817": ["Kuwait"],
    "Q842": ["Oman"],
    "Q1028": ["Morocco"],
    "Q262": ["Algeria"],
    "Q948": ["Tunisia"],
    "Q1016": ["Libya"],
    "Q229": ["Cyprus"],
    "Q41": ["Greece"],
    "Q45": ["Portugal"],
    "Q31": ["Belgium"],
    "Q39": ["Switzerland"],
    "Q40": ["Austria"],
    "Q34": ["Sweden"],
    "Q20": ["Norway"],
    "Q35": ["Denmark"],
    "Q33": ["Finland"],
    "Q191": ["Estonia"],
    "Q211": ["Latvia"],
    "Q37": ["Lithuania"],
    "Q28": ["Hungary"],
    "Q218": ["Romania"],
    "Q219": ["Bulgaria"],
    "Q403": ["Serbia"],
    "Q224": ["Croatia"],
    "Q225": ["Bosnia", "Bosnia and Herzegovina"],
    "Q184": ["Belarus"],
    "Q230": ["Georgia"],
    "Q399": ["Armenia"],
    "Q227": ["Azerbaijan"],
    "Q232": ["Kazakhstan"],
    "Q265": ["Uzbekistan"],
    "Q1246": ["Kosovo"],
    "Q298": ["Chile"],
    "Q414": ["Argentina"],
    "Q739": ["Colombia"],
    "Q419": ["Peru"],
    "Q241": ["Cuba"],
    "Q1042": ["Seychelles"],
    "Q1000": ["Gabon"],
    "Q1029": ["Mozambique"],
    "Q1036": ["Uganda"],
    "Q1037": ["Rwanda"],
    "Q1032": ["Niger"],
    "Q912": ["Mali"],
    "Q965": ["Burkina Faso"],
    "Q1006": ["Guinea"],
    "Q1041": ["Senegal"],
    "Q117": ["Ghana"],
    "Q1044": ["Sierra Leone"],
    "Q1014": ["Liberia"],
    "Q1027": ["Mauritius"],
    "Q1025": ["Mauritania"],
    "Q1009": ["Cameroon"],
    "Q657": ["Chad"],
    "Q1007": ["Guinea-Bissau"],
    "Q1030": ["Namibia"],
    "Q963": ["Botswana"],
    "Q954": ["Zimbabwe"],
    "Q953": ["Zambia"],
    "Q1020": ["Malawi"],
    "Q1019": ["Madagascar"],
    "Q1045": ["Somalia"],
    "Q986": ["Eritrea"],
    "Q977": ["Djibouti"],
    "Q1013": ["Lesotho"],
    "Q1039": ["Sao Tome and Principe", "São Tomé and Príncipe"],
    "Q983": ["Equatorial Guinea"],
    "Q929": ["Central African Republic", "CAR"],
    "Q962": ["Benin"],
    "Q945": ["Togo"],
    "Q1008": ["Ivory Coast", "Côte d'Ivoire", "Cote d'Ivoire"],
    "Q1246": ["Kosovo"],
    "Q1013": ["Lesotho"],
    "Q1044": ["Sierra Leone"],
}


def short_names(qids):
    """Wikidata P1813 (short name), P298 (ISO3), P297 (ISO2) → {qid: (names, iso3, iso2)}; empty on network failure."""
    out = {}
    try:
        for i in range(0, len(qids), 50):
            batch = qids[i:i + 50]
            r = wikidata._get({"action": "wbgetentities", "ids": "|".join(batch), "props": "claims",
                               "format": "json"}, timeout=40)
            for qid, ent in (r.json().get("entities") or {}).items():
                claims = ent.get("claims") or {}
                names = []
                for claim in claims.get("P1813", []):
                    v = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                    if isinstance(v, dict) and v.get("language", "").startswith("en") and v.get("text"):
                        names.append(v["text"])

                def first_str(prop):
                    for claim in claims.get(prop, []):
                        v = ((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")
                        if isinstance(v, str):
                            return v
                    return None
                out[qid] = (names, first_str("P298"), first_str("P297"))
    except Exception as e:
        logger.warning(f"Wikidata fetch failed: {e}")
    return out


def main():
    db = DatabaseManager()
    wikidata.set_db(db)
    try:
        rows = db.execute_query("SELECT entity_id, qid, name FROM entities WHERE kind = 'COUNTRY' AND qid IS NOT NULL", fetch=True) or []
        by_qid = {r['qid']: r for r in rows}
        fetched = short_names(list(by_qid))
        added = codes = 0
        for qid, row in by_qid.items():
            names_wd, iso3, iso2 = fetched.get(qid, ([], None, None))
            if iso3:
                db.execute_query("UPDATE entities SET metadata = metadata || %s::jsonb WHERE entity_id = %s AND NOT metadata ? 'iso3'",
                                 ('{"iso3": "%s", "iso2": "%s"}' % (iso3, iso2 or ""), row['entity_id']))
                codes += 1
            names = set(COMMON_NAMES.get(qid, [])) | set(names_wd)
            for name in names:
                norm = normalize(name)
                if not norm:
                    continue
                res = db.execute_query("""
                    INSERT INTO entity_aliases (entity_id, alias, alias_norm, source) VALUES (%s, %s, %s, 'curated')
                    ON CONFLICT (entity_id, alias_norm) DO NOTHING RETURNING alias
                """, (row['entity_id'], name, norm), fetch=True)
                added += 1 if res else 0
        logger.success(f"country aliases: {added} added across {len(by_qid)} countries; "
                       f"ISO codes set for {codes}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
