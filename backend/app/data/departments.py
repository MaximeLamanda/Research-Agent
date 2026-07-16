import re
import unicodedata

FR_DEPARTMENTS: dict[str, str] = {
    "01": "Ain",
    "02": "Aisne",
    "03": "Allier",
    "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes",
    "06": "Alpes-Maritimes",
    "07": "Ardèche",
    "08": "Ardennes",
    "09": "Ariège",
    "10": "Aube",
    "11": "Aude",
    "12": "Aveyron",
    "13": "Bouches-du-Rhône",
    "14": "Calvados",
    "15": "Cantal",
    "16": "Charente",
    "17": "Charente-Maritime",
    "18": "Cher",
    "19": "Corrèze",
    "2A": "Corse-du-Sud",
    "2B": "Haute-Corse",
    "21": "Côte-d'Or",
    "22": "Côtes-d'Armor",
    "23": "Creuse",
    "24": "Dordogne",
    "25": "Doubs",
    "26": "Drôme",
    "27": "Eure",
    "28": "Eure-et-Loir",
    "29": "Finistère",
    "30": "Gard",
    "31": "Haute-Garonne",
    "32": "Gers",
    "33": "Gironde",
    "34": "Hérault",
    "35": "Ille-et-Vilaine",
    "36": "Indre",
    "37": "Indre-et-Loire",
    "38": "Isère",
    "39": "Jura",
    "40": "Landes",
    "41": "Loir-et-Cher",
    "42": "Loire",
    "43": "Haute-Loire",
    "44": "Loire-Atlantique",
    "45": "Loiret",
    "46": "Lot",
    "47": "Lot-et-Garonne",
    "48": "Lozère",
    "49": "Maine-et-Loire",
    "50": "Manche",
    "51": "Marne",
    "52": "Haute-Marne",
    "53": "Mayenne",
    "54": "Meurthe-et-Moselle",
    "55": "Meuse",
    "56": "Morbihan",
    "57": "Moselle",
    "58": "Nièvre",
    "59": "Nord",
    "60": "Oise",
    "61": "Orne",
    "62": "Pas-de-Calais",
    "63": "Puy-de-Dôme",
    "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées",
    "66": "Pyrénées-Orientales",
    "67": "Bas-Rhin",
    "68": "Haut-Rhin",
    "69": "Rhône",
    "70": "Haute-Saône",
    "71": "Saône-et-Loire",
    "72": "Sarthe",
    "73": "Savoie",
    "74": "Haute-Savoie",
    "75": "Paris",
    "76": "Seine-Maritime",
    "77": "Seine-et-Marne",
    "78": "Yvelines",
    "79": "Deux-Sèvres",
    "80": "Somme",
    "81": "Tarn",
    "82": "Tarn-et-Garonne",
    "83": "Var",
    "84": "Vaucluse",
    "85": "Vendée",
    "86": "Vienne",
    "87": "Haute-Vienne",
    "88": "Vosges",
    "89": "Yonne",
    "90": "Territoire de Belfort",
    "91": "Essonne",
    "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne",
    "95": "Val-d'Oise",
}

DE_LANDER: dict[str, str] = {
    "BW": "Baden-Württemberg",
    "BY": "Bayern",
    "BE": "Berlin",
    "BB": "Brandenburg",
    "HB": "Bremen",
    "HH": "Hamburg",
    "HE": "Hessen",
    "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz",
    "SL": "Saarland",
    "SN": "Sachsen",
    "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein",
    "TH": "Thüringen",
}

GB_REGIONS: dict[str, str] = {
    "UKC": "North East",
    "UKD": "North West",
    "UKE": "Yorkshire and The Humber",
    "UKF": "East Midlands",
    "UKG": "West Midlands",
    "UKH": "East of England",
    "UKI": "London",
    "UKJ": "South East",
    "UKK": "South West",
    "UKL": "Wales",
    "UKM": "Scotland",
    "UKN": "Northern Ireland",
}

IE_PROVINCES: dict[str, str] = {
    "LE": "Leinster",
    "MU": "Munster",
    "CN": "Connacht",
    "UL": "Ulster",
}

REGIONS_BY_COUNTRY: dict[str, dict[str, str]] = {
    "FR": FR_DEPARTMENTS,
    "DE": DE_LANDER,
    "GB": GB_REGIONS,
    "IE": IE_PROVINCES,
}

# Backward compatibility
DEPARTMENTS = FR_DEPARTMENTS

_FORMATTED_RE = re.compile(r"^([A-Z]{2,3}|\d{2}[AB]?)\s*[-—]\s*(.+)$", re.IGNORECASE)
_FR_CODE_RE = re.compile(r"^\d{2}[AB]?$", re.IGNORECASE)
_DE_CODE_RE = re.compile(r"^[A-Z]{2}$")
_GB_CODE_RE = re.compile(r"^UK[A-Z]$")


def _normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def _name_to_code_map(country: str) -> dict[str, str]:
    regions = REGIONS_BY_COUNTRY.get(country, FR_DEPARTMENTS)
    return {_normalize_name(name): code for code, name in regions.items()}


def _normalize_code(code: str, country: str = "FR") -> str:
    normalized_code = code.strip().upper()
    if country == "FR" and normalized_code.isdigit() and len(normalized_code) == 1:
        normalized_code = normalized_code.zfill(2)
    return normalized_code


def _detect_country_from_code(code: str) -> str | None:
    upper = code.upper()
    if _FR_CODE_RE.match(upper):
        return "FR"
    if _GB_CODE_RE.match(upper):
        return "GB"
    if upper in IE_PROVINCES:
        return "IE"
    if _DE_CODE_RE.match(upper) and upper in DE_LANDER:
        return "DE"
    return None


def infer_country_from_department(department: str | None) -> str | None:
    if not department:
        return None

    raw = department.strip()
    if not raw:
        return None

    formatted = _FORMATTED_RE.match(raw)
    if formatted:
        return _detect_country_from_code(formatted.group(1).upper())

    if _FR_CODE_RE.match(raw):
        return "FR"

    if _GB_CODE_RE.match(raw):
        return "GB"

    if raw.upper() in IE_PROVINCES:
        return "IE"

    if _DE_CODE_RE.match(raw) and raw.upper() in DE_LANDER:
        return "DE"

    return None


def regions_for_country(country: str) -> dict[str, str]:
    return REGIONS_BY_COUNTRY.get(country, FR_DEPARTMENTS)


def department_name(code: str, country: str = "FR") -> str | None:
    normalized_code = _normalize_code(code, country)
    return regions_for_country(country).get(normalized_code)


def format_department(code: str, country: str = "FR") -> str | None:
    normalized_code = _normalize_code(code, country)
    name = regions_for_country(country).get(normalized_code)
    if not name:
        return None
    return f"{normalized_code} - {name}"


def normalize_department(value: str | None, country: str = "FR") -> str | None:
    if value is None:
        return None

    raw = value.strip()
    if not raw:
        return None

    formatted = _FORMATTED_RE.match(raw)
    if formatted:
        code = formatted.group(1).upper()
        detected = _detect_country_from_code(code)
        if detected:
            return format_department(code, detected)
        return None

    if _FR_CODE_RE.match(raw):
        return format_department(raw, "FR")

    if _GB_CODE_RE.match(raw):
        return format_department(raw, "GB")

    if raw.upper() in IE_PROVINCES:
        return format_department(raw, "IE")

    if _DE_CODE_RE.match(raw) and raw.upper() in DE_LANDER:
        return format_department(raw, "DE")

    code = _name_to_code_map(country).get(_normalize_name(raw))
    if code:
        return format_department(code, country)

    for fallback_country in ("FR", "DE", "GB", "IE"):
        if fallback_country == country:
            continue
        code = _name_to_code_map(fallback_country).get(_normalize_name(raw))
        if code:
            return format_department(code, fallback_country)

    return None


def ensure_department(
    value: str | None, fallback_code: str | None = None, country: str = "FR"
) -> str | None:
    normalized = normalize_department(value, country)
    if normalized:
        return normalized
    if fallback_code:
        return format_department(fallback_code, country)
    return value
