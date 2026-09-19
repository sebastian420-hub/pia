"""
GDELT geocodes places with FIPS 10-4 country codes ("CH" = China, "UK", "GM" = Germany) while
its actors carry ISO-3166 alpha-3 ("CHN", "GBR", "DEU"). This table maps the FIPS codes that
differ from ISO alpha-2; every other FIPS code equals its ISO alpha-2 code.
"""

FIPS_TO_ISO2 = {
    "AG": "DZ", "AJ": "AZ", "AN": "AD", "AS": "AU", "AU": "AT", "BA": "BH", "BD": "BM", "BF": "BS",
    "BG": "BD", "BK": "BA", "BL": "BO", "BM": "MM", "BN": "BJ", "BO": "BY", "BU": "BG", "BX": "BN",
    "BY": "BI", "CB": "KH", "CD": "TD", "CE": "LK", "CF": "CG", "CG": "CD", "CH": "CN", "CI": "CL",
    "CJ": "KY", "CN": "KM", "CS": "CR", "CT": "CF", "DA": "DK", "DR": "DO", "EI": "IE", "EK": "GQ",
    "EN": "EE", "ES": "SV", "EZ": "CZ", "GA": "GM", "GB": "GA", "GG": "GE", "GJ": "GD", "GM": "DE",
    "GV": "GN", "HA": "HT", "HO": "HN", "IC": "IS", "IS": "IL", "IV": "CI", "IZ": "IQ", "JA": "JP",
    "KN": "KP", "KS": "KR", "KU": "KW", "LE": "LB", "LG": "LV", "LH": "LT", "LI": "LR", "LO": "SK",
    "LS": "LI", "MA": "MG", "MC": "MO", "MG": "MN", "MI": "MW", "MN": "MC", "MO": "MA", "MP": "MU",
    "MU": "OM", "NG": "NE", "NI": "NG", "NS": "SR", "NU": "NI", "PA": "PY", "PM": "PA", "PO": "PT",
    "RI": "RS", "RP": "PH", "RS": "RU", "SE": "SC", "SF": "ZA", "SG": "SN", "SN": "SG", "SP": "ES",
    "SU": "SD", "SW": "SE", "SZ": "CH", "TD": "TT", "TI": "TJ", "TO": "TG", "TS": "TN", "TT": "TL",
    "TU": "TR", "TX": "TM", "UK": "GB", "UP": "UA", "UV": "BF", "VM": "VN", "WA": "NA", "WI": "EH",
    "WZ": "SZ", "YM": "YE", "ZA": "ZM", "ZI": "ZW",
}


def fips_to_iso2(code: str) -> str:
    code = (code or "").strip().upper()
    return FIPS_TO_ISO2.get(code, code)
