"""
Scraper pour le site du Comité Général des Assurances (CGA) :
https://www.cga.gov.tn/index.php?id=96&L=0 (page "Rapports annuels")

Comme FTUSA, le CGA publie des rapports sectoriels (pas de societe
associee, cmf_id NULL) : on prend les rapports des NB_YEARS dernieres
annees disponibles sur le site.

Contrairement a FTUSA, le texte du lien de chaque rapport contient deja
l'annee de facon fiable ("Rapport annuel du secteur des assurances 2022"),
pas besoin de l'annee deduite du contenu du PDF.
"""

import re

import requests

from database.repository import (
    ensure_database,
    get_connection,
    get_or_create_source,
    init_schema,
    save_document,
)

BASE_URL = "https://www.cga.gov.tn"
REPORTS_PAGE_URL = f"{BASE_URL}/index.php?id=96&L=0"
NB_YEARS = 10

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}

REPORT_LINK_RE = re.compile(
    r'<a href="([^"]+\.pdf)"[^>]*>(?:(?!</a>).)*?Rapport annuel du secteur des assurances (\d{4})', re.S
)
# Liens vers des pages de news hébergeant le rapport d'une année donnée
# (les rapports les plus récents ne sont plus liés directement en PDF
# depuis la page principale, mais sur une page intermédiaire).
# "Rapport annuel 2024" apparaît AVANT le <a href="...tx_ttnews...">
# -> on capture le texte dans une fenêtre de 400 caractères précédant le lien.
NEWS_LINK_RE = re.compile(
    r'Rapport\s+[Aa]nnuel\s+(\d{4})(?:(?!href=).){1,400}href="([^"]+tx_ttnews[^"]+)"',
    re.S,
)
GDRIVE_LINK_RE = re.compile(
    r'https://drive\.google\.com/file/d/([A-Za-z0-9_-]+)/view'
)


def _gdrive_download_url(file_id):
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def _fetch_report_links():
    """Renvoie {annee: url_pdf} pour tous les rapports annuels CGA.

    Les rapports jusqu'en 2022 sont liés directement en PDF depuis la page
    principale. Les rapports plus récents (2023, 2024…) sont sur des pages
    de news intermédiaires et hébergés sur Google Drive ; cette fonction les
    suit automatiquement."""
    response = requests.get(REPORTS_PAGE_URL, headers=REQUEST_HEADERS, timeout=30)
    response.raise_for_status()
    by_year = {}

    # Liens PDF directs (2022 et antérieurs)
    for path, year in REPORT_LINK_RE.findall(response.text):
        url = path if path.startswith("http") else f"{BASE_URL}/{path}"
        by_year[int(year)] = url

    # Pages de news pour les rapports récents (2023, 2024…)
    for year, raw_path in NEWS_LINK_RE.findall(response.text):
        year = int(year)
        if year in by_year:
            continue  # déjà résolu via lien PDF direct
        # Les href HTML contiennent des entités (&amp; → &)
        path = raw_path.replace("&amp;", "&")
        news_url = path if path.startswith("http") else f"{BASE_URL}/{path}"
        try:
            news_resp = requests.get(news_url, headers=REQUEST_HEADERS, timeout=30)
            news_resp.raise_for_status()
            m = GDRIVE_LINK_RE.search(news_resp.text)
            if m:
                by_year[year] = _gdrive_download_url(m.group(1))
        except Exception as exc:
            print(f"  [WARN] Impossible de récupérer la page news {year}: {exc}")

    return by_year


def sync_documents():
    """Enregistre un document pour chacun des NB_YEARS derniers rapports
    annuels CGA disponibles."""
    ensure_database()
    conn = get_connection()
    init_schema(conn)
    source_id = get_or_create_source(conn, "CGA", REPORTS_PAGE_URL)

    by_year = _fetch_report_links()
    print(f"[STEP] {len(by_year)} rapport(s) annuel(s) CGA trouve(s) sur le site")

    kept_years = sorted(by_year, reverse=True)[:NB_YEARS]
    saved = 0
    for year in kept_years:
        nom_pdf = f"CGA_{year}.pdf"
        save_document(conn, source_id, None, nom_pdf, year, by_year[year])
        saved += 1
        print(f"  [OK] {year} -> {by_year[year]}")

    conn.close()
    if kept_years:
        print(f"[INFO] {saved} document(s) CGA enregistre(s) en base (annees {min(kept_years)}-{max(kept_years)})\n")
    else:
        print("[INFO] Aucun document CGA enregistre\n")
    return saved


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    sync_documents()
