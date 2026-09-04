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

import re  # regex pour extraire annees et liens dans le HTML
import time  # pauses entre tentatives de requete

import requests  # requetes HTTP vers le site CGA

from database.repository import (
    ensure_database,        # crée la base si elle n'existe pas
    get_connection,          # ouvre la connexion à la base
    get_or_create_source,     # récupère ou crée l'id de la source "CGA"
    init_schema,                # crée/met à jour les tables si besoin
    save_document,               # enregistre (ou met à jour) les métadonnées d'un document
)

BASE_URL = "https://www.cga.gov.tn"
REPORTS_PAGE_URL = f"{BASE_URL}/index.php?id=96&L=0"  # page listant les rapports annuels
NB_YEARS = 10  # nombre d'années de rapports à conserver au final

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}  # évite un blocage anti-bot basique


def _get_with_retries(url, timeout=30, retries=3):
    """Meme approche que bvmt_scraper/ftusa_scraper : le site peut echouer
    ponctuellement (timeout, 5xx passager), quelques tentatives suffisent."""
    for attempt in range(1, retries + 1):  # jusqu'à `retries` tentatives
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)  # requête GET
            response.raise_for_status()  # lève une exception si code HTTP >= 400
            return response  # succès, on retourne la réponse
        except requests.RequestException as exc:
            if attempt == retries:  # dernière tentative épuisée
                raise  # on relève l'exception au niveau appelant
            print(f"  [WARN] Tentative {attempt}/{retries} echouee pour {url} : {exc}")  # log de l'échec
            time.sleep(1.5)  # pause avant de réessayer

REPORT_LINK_RE = re.compile(
    r'<a href="([^"]+\.pdf)"[^>]*>(?:(?!</a>).)*?Rapport annuel du secteur des assurances (\d{4})', re.S
)  # capture (chemin_pdf, annee) pour les liens PDF directs
# Liens vers des pages de news hébergeant le rapport d'une année donnée
# (les rapports les plus récents ne sont plus liés directement en PDF
# depuis la page principale, mais sur une page intermédiaire).
# "Rapport annuel 2024" apparaît AVANT le <a href="...tx_ttnews...">
# -> on capture le texte dans une fenêtre de 400 caractères précédant le lien.
NEWS_LINK_RE = re.compile(
    r'Rapport\s+[Aa]nnuel\s+(\d{4})(?:(?!href=).){1,400}href="([^"]+tx_ttnews[^"]+)"',
    re.S,
)  # capture (annee, chemin_page_news) pour les rapports récents
GDRIVE_LINK_RE = re.compile(
    r'https://drive\.google\.com/file/d/([A-Za-z0-9_-]+)/view'
)  # capture l'id du fichier Google Drive dans la page news


def _gdrive_download_url(file_id):
    return f"https://drive.google.com/uc?export=download&id={file_id}"  # construit l'URL de téléchargement direct du PDF


def _fetch_report_links():
    """Renvoie {annee: url_pdf} pour tous les rapports annuels CGA.

    Les rapports jusqu'en 2022 sont liés directement en PDF depuis la page
    principale. Les rapports plus récents (2023, 2024…) sont sur des pages
    de news intermédiaires et hébergés sur Google Drive ; cette fonction les
    suit automatiquement."""
    response = _get_with_retries(REPORTS_PAGE_URL, timeout=30)  # charge la page principale des rapports
    by_year = {}  # dict annee -> url pdf, rempli au fil des deux passes ci-dessous

    # Liens PDF directs (2022 et antérieurs)
    for path, year in REPORT_LINK_RE.findall(response.text):  # parcourt tous les liens PDF directs trouvés
        url = path if path.startswith("http") else f"{BASE_URL}/{path}"  # construit une URL absolue
        by_year[int(year)] = url  # enregistre le lien direct pour cette année

    # Pages de news pour les rapports récents (2023, 2024…)
    for year, raw_path in NEWS_LINK_RE.findall(response.text):  # parcourt les liens vers des pages news
        year = int(year)  # convertit l'année capturée en entier
        if year in by_year:
            continue  # déjà résolu via lien PDF direct
        # Les href HTML contiennent des entités (&amp; → &)
        path = raw_path.replace("&amp;", "&")  # décode l'entité HTML dans l'URL
        news_url = path if path.startswith("http") else f"{BASE_URL}/{path}"  # URL absolue de la page news
        try:
            news_resp = _get_with_retries(news_url, timeout=30)  # suit le lien : charge la page news intermédiaire
            m = GDRIVE_LINK_RE.search(news_resp.text)  # cherche un lien Google Drive dans cette page
            if m:
                by_year[year] = _gdrive_download_url(m.group(1))  # enregistre l'URL de téléchargement direct Drive
        except Exception as exc:
            print(f"  [WARN] Impossible de récupérer la page news {year}: {exc}")  # log, année simplement ignorée

    return by_year  # dict complet annee -> url (PDF direct ou Google Drive)


def sync_documents():
    """Enregistre un document pour chacun des NB_YEARS derniers rapports
    annuels CGA disponibles."""
    ensure_database()  # crée la base si elle n'existe pas déjà
    conn = get_connection()  # ouvre la connexion à la base
    init_schema(conn)  # crée/migre les tables si nécessaire
    source_id = get_or_create_source(conn, "CGA", REPORTS_PAGE_URL)  # id de la source "CGA" (créée si absente)

    by_year = _fetch_report_links()  # {annee: url} pour tous les rapports trouvés sur le site
    print(f"[STEP] {len(by_year)} rapport(s) annuel(s) CGA trouve(s) sur le site")  # log du nombre total trouvé

    kept_years = sorted(by_year, reverse=True)[:NB_YEARS]  # filtre : ne garde que les NB_YEARS années les plus récentes
    saved = 0  # compteur de documents enregistrés
    for year in kept_years:  # parcourt les années retenues
        nom_pdf = f"CGA_{year}.pdf"  # nom de fichier construit (aucun PDF réellement téléchargé)
        save_document(conn, source_id, None, nom_pdf, year, by_year[year])  # cmf_id=None : rapport sectoriel, pas lié à une société ; dédup gérée dans save_document
        saved += 1  # incrémente le compteur
        print(f"  [OK] {year} -> {by_year[year]}")  # log de l'enregistrement

    conn.close()  # ferme la connexion à la base
    if kept_years:
        print(f"[INFO] {saved} document(s) CGA enregistre(s) en base (annees {min(kept_years)}-{max(kept_years)})\n")  # log résumé
    else:
        print("[INFO] Aucun document CGA enregistre\n")  # aucun rapport trouvé/retenu
    return saved  # nombre de documents enregistrés


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # force l'UTF-8 pour l'affichage console
    sync_documents()  # lance le scraping complet
