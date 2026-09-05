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

import re  # regex liens/années
import time  # pause entre tentatives

import requests  # requêtes HTTP

from database.repository import (
    ensure_database,        # crée la base
    get_connection,          # connexion base
    get_or_create_source,     # id source CGA
    init_schema,                # tables à jour
    save_document,               # enregistre métadonnées
)

BASE_URL = "https://www.cga.gov.tn"
REPORTS_PAGE_URL = f"{BASE_URL}/index.php?id=96&L=0"  # page des rapports
NB_YEARS = 10  # années conservées

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}  # évite blocage anti-bot


# ------------------------------------------------------------------ #
# Requêtes réseau
# ------------------------------------------------------------------ #

# Utilité : requête GET avec 3 tentatives
def _get_with_retries(url, timeout=30, retries=3):
    """Meme approche que bvmt_scraper/ftusa_scraper : le site peut echouer
    ponctuellement (timeout, 5xx passager), quelques tentatives suffisent."""
    for attempt in range(1, retries + 1):  # jusqu'à retries tentatives
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)  # requête GET
            response.raise_for_status()  # lève si erreur HTTP
            return response  # succès
        except requests.RequestException as exc:
            if attempt == retries:  # dernière tentative
                raise  # relève l'erreur
            print(f"  [WARN] Tentative {attempt}/{retries} echouee pour {url} : {exc}")  # log
            time.sleep(1.5)  # pause avant nouvel essai

REPORT_LINK_RE = re.compile(
    r'<a href="([^"]+\.pdf)"[^>]*>(?:(?!</a>).)*?Rapport annuel du secteur des assurances (\d{4})', re.S
)  # capture (chemin_pdf, année)
# Liens vers des pages de news hébergeant le rapport d'une année donnée
# (les rapports les plus récents ne sont plus liés directement en PDF
# depuis la page principale, mais sur une page intermédiaire).
# "Rapport annuel 2024" apparaît AVANT le <a href="...tx_ttnews...">
# -> on capture le texte dans une fenêtre de 400 caractères précédant le lien.
NEWS_LINK_RE = re.compile(
    r'Rapport\s+[Aa]nnuel\s+(\d{4})(?:(?!href=).){1,400}href="([^"]+tx_ttnews[^"]+)"',
    re.S,
)  # capture (année, page_news)
GDRIVE_LINK_RE = re.compile(
    r'https://drive\.google\.com/file/d/([A-Za-z0-9_-]+)/view'
)  # capture l'id Google Drive


# ------------------------------------------------------------------ #
# Résolution des liens (page principale -> page news -> Google Drive)
# ------------------------------------------------------------------ #

# Utilité : construit l'URL de téléchargement direct depuis un id Google Drive
def _gdrive_download_url(file_id):
    return f"https://drive.google.com/uc?export=download&id={file_id}"  # URL de téléchargement direct


# Utilité : récupère les liens PDF (page principale + suivi de lien pour 2023+)
def _fetch_report_links():
    """Renvoie {annee: url_pdf} pour tous les rapports annuels CGA.

    Les rapports jusqu'en 2022 sont liés directement en PDF depuis la page
    principale. Les rapports plus récents (2023, 2024…) sont sur des pages
    de news intermédiaires et hébergés sur Google Drive ; cette fonction les
    suit automatiquement."""
    response = _get_with_retries(REPORTS_PAGE_URL, timeout=30)  # charge la page principale
    by_year = {}  # année -> url pdf

    # Liens PDF directs (2022 et antérieurs)
    for path, year in REPORT_LINK_RE.findall(response.text):  # liens PDF directs
        url = path if path.startswith("http") else f"{BASE_URL}/{path}"  # URL absolue
        by_year[int(year)] = url  # lien direct pour cette année

    # Pages de news pour les rapports récents (2023, 2024…)
    for year, raw_path in NEWS_LINK_RE.findall(response.text):  # liens vers pages news
        year = int(year)  # année en entier
        if year in by_year:
            continue  # déjà résolu en direct
        # Les href HTML contiennent des entités (&amp; → &)
        path = raw_path.replace("&amp;", "&")  # décode l'entité HTML
        news_url = path if path.startswith("http") else f"{BASE_URL}/{path}"  # URL absolue
        try:
            news_resp = _get_with_retries(news_url, timeout=30)  # suit le lien
            m = GDRIVE_LINK_RE.search(news_resp.text)  # cherche un lien Drive
            if m:
                by_year[year] = _gdrive_download_url(m.group(1))  # lien de téléchargement Drive
        except Exception as exc:
            print(f"  [WARN] Impossible de récupérer la page news {year}: {exc}")  # année ignorée

    return by_year  # année -> url (PDF direct ou Drive)


# ------------------------------------------------------------------ #
# Orchestration
# ------------------------------------------------------------------ #

# Utilité : orchestre tout : liens, filtrage, enregistrement
def sync_documents():
    """Enregistre un document pour chacun des NB_YEARS derniers rapports
    annuels CGA disponibles."""
    ensure_database()  # crée la base
    conn = get_connection()  # connexion base
    init_schema(conn)  # tables à jour
    source_id = get_or_create_source(conn, "CGA", REPORTS_PAGE_URL)  # id source CGA

    by_year = _fetch_report_links()  # {année: url} trouvés
    print(f"[STEP] {len(by_year)} rapport(s) annuel(s) CGA trouve(s) sur le site")  # total trouvé

    kept_years = sorted(by_year, reverse=True)[:NB_YEARS]  # années les plus récentes
    saved = 0  # compteur enregistrés
    for year in kept_years:  # années retenues
        nom_pdf = f"CGA_{year}.pdf"  # nom construit, pas téléchargé
        save_document(conn, source_id, None, nom_pdf, year, by_year[year])  # cmf_id=None : sectoriel
        saved += 1  # +1 enregistré
        print(f"  [OK] {year} -> {by_year[year]}")  # confirmation

    conn.close()  # ferme la connexion
    if kept_years:
        print(f"[INFO] {saved} document(s) CGA enregistre(s) en base (annees {min(kept_years)}-{max(kept_years)})\n")  # résumé
    else:
        print("[INFO] Aucun document CGA enregistre\n")  # rien trouvé
    return saved  # documents enregistrés


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # force UTF-8 console
    sync_documents()  # lance le scraping
