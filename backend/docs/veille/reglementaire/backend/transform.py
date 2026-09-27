import re
from collect import fetch_cga_pages, fetch_ftusa_textes, fetch_ftusa_code
from extract import from_cga, from_ftusa_textes, from_ftusa_code
from config import MOIS_FR


def detect_type(text):
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


def extract_date(titre):
    t = titre.lower()
    m = re.search(r"\bdu\s+(\d{1,2})(?:er)?\s+([a-zéûôàâùè]+)\s+(\d{4})", t)
    if m:
        month = MOIS_FR.get(m.group(2)[:3]) or MOIS_FR.get(m.group(2)[:4], "01")
        return f"{m.group(1).zfill(2)}/{month}/{m.group(3)}", int(m.group(3))
    m = re.search(r"\b(\d{4})\b", titre)
    if m:
        return m.group(1), int(m.group(1))
    return "", None


def _sort_key(d):
    parts = d.get("date", "").split("/")
    if len(parts) == 3:
        return f"{parts[2]}{parts[1]}{parts[0]}"
    return str(d["annee"]) if d.get("annee") else "0000"


def build_docs():
    raw = []

    for html_bytes in fetch_cga_pages():
        raw += from_cga(html_bytes)

    code_html = fetch_ftusa_code()
    raw += from_ftusa_code(code_html)

    textes_html = fetch_ftusa_textes()
    if textes_html:
        raw += from_ftusa_textes(textes_html)

    docs = []
    seen_keys = set()
    seen_titles = set()

    for d in raw:
        type_ = detect_type(d["titre"])
        if type_ == "Texte" and d["src"] == "FTUSA" and d.get("id") != "ftusa_code_ass":
            continue

        date, annee = extract_date(d["titre"])
        if d.get("id") == "ftusa_code_ass":
            date, annee = "09/03/1992", 1992

        key = d.get("id") or d["url"]
        title_key = re.sub(r"\s+", " ", d["titre"].lower())[:80]

        if key in seen_keys or title_key in seen_titles:
            continue
        seen_keys.add(key)
        seen_titles.add(title_key)

        docs.append({
            "id":      d["id"],
            "src":     d["src"],
            "type":    type_,
            "titre":   d["titre"],
            "url":     d["url"],
            "pdf_url": d.get("pdf_url"),
            "date":    date,
            "annee":   annee,
        })

    docs.sort(key=_sort_key, reverse=True)
    return docs
