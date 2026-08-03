import re
from config import MOIS_FR


def normalize_date(date_str):
    if not date_str:
        return "2026"
    date_str = date_str.strip()
    if re.match(r'\d{2}/\d{2}/\d{4}', date_str):
        return date_str
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = re.search(r'(\d{1,2})\s+([a-zéûôàâùè]+)\s+(\d{4})', date_str.lower())
    if m:
        day = m.group(1).zfill(2)
        month = MOIS_FR.get(m.group(2)[:3], "01")
        return f"{day}/{month}/{m.group(3)}"
    m = re.search(r'\b(20\d{2})\b', date_str)
    if m:
        return m.group(1)
    return "2026"


def categorize_article(titre):
    t = titre.lower()
    if any(k in t for k in ["résultat", "chiffre", "prime", "bénéfice", "profit",
                             "sinistre", "ratio", "bilan", "performance", "financier"]):
        return "Résultats financiers"
    if any(k in t for k in ["gouvern", "conseil", "assemblée", "nomination", "direction"]):
        return "Gouvernance"
    if any(k in t for k in ["partenariat", "accord", "convention", "protocole", "collaboration"]):
        return "Partenariat"
    if any(k in t for k in ["digital", "numéri", "application", "plateforme", "technolog", "ia ", "intelligence"]):
        return "Digital"
    if any(k in t for k in ["innov", "borne", "électrique", "développement durable", "énergie", "verte"]):
        return "Innovation"
    if any(k in t for k in ["règlement", "loi", "décret", "circulaire", "obligation", "réglementaire"]):
        return "Réglementation"
    return "Actualité"


def detect_doc_type(text):
    t = text.lower()
    if "règlement" in t or "reglement" in t:
        return "Règlement"
    if "décision" in t or "decision" in t:
        return "Décision"
    if "circulaire" in t:
        return "Circulaire"
    if "avenant" in t:
        return "Avenant"
    if "communiqué" in t or "avis" in t:
        return "Communiqué"
    if "arrêté" in t or "arrete" in t:
        return "Arrêté"
    if "décret" in t or "decret" in t:
        return "Décret"
    if "loi" in t:
        return "Loi"
    if "code" in t:
        return "Code"
    return "Texte"


def extract_date_from_title(titre):
    t = titre.lower()
    m = re.search(r'\bdu\s+(\d{1,2})(?:er)?\s+([a-zéûôàâùè]+)\s+(\d{4})', t)
    if m:
        day = m.group(1).zfill(2)
        month = MOIS_FR.get(m.group(2)[:3], None) or MOIS_FR.get(m.group(2)[:4], "01")
        year = m.group(3)
        return f"{day}/{month}/{year}", int(year)
    m = re.search(r'\b(\d{4})\b', titre)
    if m:
        return m.group(1), int(m.group(1))
    return "", None
