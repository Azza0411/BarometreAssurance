HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

INSURANCE_COMPANIES = [
    {"name": "STAR Assurances",     "ticker": "STAR",  "keys": ["star"]},
    {"name": "COMAR Assurances",    "ticker": "COMAR", "keys": ["comar"]},
    {"name": "GAT Assurances",      "ticker": "GAT",   "keys": [" gat ", "gat ass"]},
    {"name": "Astree Assurances",   "ticker": "ASTRE", "keys": ["astree"]},
    {"name": "Carte Assurances",    "ticker": "CARTE", "keys": ["carte ass"]},
    {"name": "Lloyd Tunisien",      "ticker": "LLOYD", "keys": ["lloyd"]},
    {"name": "Maghrebia",           "ticker": "MGBP",  "keys": ["maghrebia"]},
    {"name": "BH Assurance",        "ticker": "BHASS", "keys": ["bh assurance", "bh-assur"]},
    {"name": "BNA Assurances",      "ticker": "BNASS", "keys": ["bna assur"]},
    {"name": "AMI Assurances",      "ticker": "AMII",  "keys": ["ami assur"]},
    {"name": "Attijari Assurance",  "ticker": "ATT",   "keys": ["attijari"]},
    {"name": "Tunis Re",            "ticker": "TUNRE", "keys": ["tunis re", "tunis-re", "tunisre"]},
    {"name": "CGA",                 "ticker": "CGA",   "keys": ["comité général des assur", " cga "]},
]

MOIS_FR = {
    "janvier": "01", "février": "02", "mars": "03", "avril": "04",
    "mai": "05", "juin": "06", "juillet": "07", "août": "08",
    "septembre": "09", "octobre": "10", "novembre": "11", "décembre": "12",
    "jan": "01", "fév": "02", "mar": "03", "avr": "04", "jun": "06",
    "jul": "07", "aoû": "08", "sep": "09", "oct": "10", "nov": "11", "déc": "12",
}

CACHE_TTL = 3600

PDF_PROXY_ALLOWED_DOMAINS = ["cga.gov.tn", "ftusanet.org", "atlas-mag.net"]
