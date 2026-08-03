import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from collect import fetch_ilboursa_pages, fetch_atlas_pages, fetch_article_meta
from extract import from_ilboursa, from_atlas
from config import MOIS_FR


def normalize_date(raw):
    if not raw:
        return str(datetime.now().year)
    raw = raw.strip()
    if re.match(r"\d{2}/\d{2}/\d{4}", raw):
        return raw
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = re.search(r"(\d{1,2})\s+([a-zéûôàâùè]+)\s+(\d{4})", raw.lower())
    if m:
        month = MOIS_FR.get(m.group(2)[:3], "01")
        return f"{m.group(1).zfill(2)}/{month}/{m.group(3)}"
    m = re.search(r"\b(20\d{2})\b", raw)
    if m:
        return m.group(1)
    return str(datetime.now().year)


def categorize(titre):
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


def _fix_short_year(date_raw):
    if re.match(r"\d{1,2}/\d{1,2}/\d{2}$", date_raw):
        parts = date_raw.split("/")
        parts[2] = "20" + parts[2]
        return "/".join(parts)
    return date_raw


def _sort_key(a):
    p = a["date"].split("/")
    if len(p) == 3:
        return f"{p[2]}{p[1]}{p[0]}"
    return a["date"] + "0101"


def build_feed():
    raw_items = []

    for html, default_company in fetch_ilboursa_pages():
        raw_items += from_ilboursa(html, default_company)

    cutoff = datetime.now().year - 5
    for html in fetch_atlas_pages():
        candidates = from_atlas(html)
        for item in candidates:
            nd = normalize_date(item["date_raw"])
            yr = re.search(r"\b(20\d{2})\b", nd)
            if yr and int(yr.group()) < cutoff:
                continue
            item["date_raw"] = nd
            raw_items.append(item)

    def enrich(item):
        date_raw = _fix_short_year(item["date_raw"])
        img, resume = fetch_article_meta(item["url"])
        return {
            "src":       item["src"],
            "titre":     item["titre"],
            "url":       item["url"],
            "date":      normalize_date(date_raw),
            "categorie": categorize(item["titre"]),
            "compagnie": item["company"],
            "resume":    resume,
            "image":     img,
            "pdf_url":   None,
        }

    articles = []
    seen_urls = set()

    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(enrich, item): item for item in raw_items[:50]}
        for fut in as_completed(futures):
            try:
                art = fut.result()
                if art["url"] not in seen_urls:
                    seen_urls.add(art["url"])
                    articles.append(art)
            except Exception:
                pass

    articles.sort(key=_sort_key, reverse=True)
    return articles
