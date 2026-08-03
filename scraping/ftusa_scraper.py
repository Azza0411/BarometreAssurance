"""
Scraper pour le site de la Fédération Tunisienne des Sociétés d'Assurances
(FTUSA) : https://www.ftusanet.org/rapports-annuels/

Contrairement au portail CMF, FTUSA ne publie pas des documents par société
mais des rapports sectoriels sur le marché tunisien des assurances dans son
ensemble -> pas de boucle sur une liste de sociétés, et pas de `cmf_id`
associé aux documents enregistrés (voir database.repository : cmf_id est
NULL pour les documents d'une source sectorielle).

La page liste les liens PDF des rapports annuels dans une zone principale,
et quelques publications sans rapport avec les rapports annuels (classement
des risques émergents, formulaire d'assurance auto en arabe, doublon d'un
rapport déjà listé plus haut) dans un bloc "à la une" en bas de page -> seule
la zone principale (avant la section "actusBottom") est prise en compte.

L'année couverte par chaque rapport est déterminée en lisant son contenu
(titre en première page, ex: "L'ASSURANCE TUNISIENNE en 2024"), pas son nom
de fichier : les conventions de nommage varient trop sur 25 ans d'archives
(ex: "Rapport-FTUSA-DEFINITIF.pdf" ne contient aucune année dans son nom).
"""

import io
import re
import sys
import time

import pdfplumber
import requests

# Certains liens de la page (ex: un formulaire au nom en arabe) contiennent
# des caractères hors de la page de code par défaut de la console Windows
# (cp1252) : on bascule stdout en UTF-8 pour ne jamais planter sur un print.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from database.repository import (
    ensure_database,
    get_connection,
    get_or_create_source,
    init_schema,
    save_document,
)
from utils.pdf_utils import is_valid_pdf

FTUSA_BASE_URL = "https://www.ftusanet.org"
FTUSA_REPORTS_PAGE = f"{FTUSA_BASE_URL}/rapports-annuels/"
# Bloc "à la une" en bas de page : ne contient pas des rapports annuels
# (voir docstring ci-dessus) -> tout ce qui suit ce marqueur est ignoré.
SIDEBAR_MARKER = '<section id="actusBottom"'
NB_YEARS = 10

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}

YEAR_TITLE_RE = re.compile(r"\ben\s+(20\d{2})\b", re.IGNORECASE)
BARE_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _get_with_retries(url, timeout=30, retries=3):
    """Le site peut echouer ponctuellement (timeout, 5xx passager) :
    quelques nouvelles tentatives suffisent (meme approche que bvmt_scraper)."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            print(f"  [WARN] Tentative {attempt}/{retries} echouee pour {url} : {exc}")
            time.sleep(1.5)


def _collect_main_pdf_links():
    """Renvoie les liens .pdf de la zone principale de la page (avant le
    bloc "à la une"), sans doublon, dans l'ordre d'apparition (du plus
    récent au plus ancien)."""
    response = _get_with_retries(FTUSA_REPORTS_PAGE, timeout=30)
    html = response.text
    cutoff = html.find(SIDEBAR_MARKER)
    main_html = html[:cutoff] if cutoff != -1 else html
    seen = set()
    ordered = []
    for link in re.findall(r'href="([^"]+\.pdf)"', main_html):
        if link not in seen:
            seen.add(link)
            ordered.append(link)
    return ordered


def _detect_report_year(pdf_bytes):
    """Détermine l'année couverte par le rapport en lisant son titre (les 2
    premières pages), plutôt que son nom de fichier (trop peu fiable sur
    l'ensemble des archives, ex: "Rapport-FTUSA-DEFINITIF.pdf")."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = ""
        for page in pdf.pages[:2]:
            text += page.extract_text() or ""
    match = YEAR_TITLE_RE.search(text) or BARE_YEAR_RE.search(text)
    return int(match.group(1)) if match else None


def sync_documents():
    """Télécharge (en mémoire) les rapports de la zone principale de la page
    FTUSA, détermine l'année réelle de chacun d'après son contenu, et
    enregistre en base le rapport le plus récent pour chacune des NB_YEARS
    dernières années disponibles. Aucun PDF n'est écrit sur disque."""
    ensure_database()
    conn = get_connection()
    init_schema(conn)
    source_id = get_or_create_source(conn, "FTUSA", FTUSA_REPORTS_PAGE)

    links = _collect_main_pdf_links()
    print(f"[STEP] {len(links)} document(s) trouve(s) dans la zone principale de la page FTUSA")

    by_year = {}
    for link in links:
        url = link if link.startswith("http") else FTUSA_BASE_URL + link
        try:
            response = _get_with_retries(url, timeout=60)
        except requests.RequestException as exc:
            print(f"  [WARN] Telechargement echoue apres 3 tentatives, ignore : {url} ({exc})")
            continue
        if not is_valid_pdf(response.content):
            print(f"  [WARN] Contenu recu non-PDF (page d'erreur probable), ignore : {url}")
            continue
        year = _detect_report_year(response.content)
        if year is None:
            print(f"  [WARN] Annee introuvable dans le contenu, ignore : {url}")
            continue
        # La page liste les rapports du plus recent au plus ancien : la
        # premiere occurrence d'une annee est donc la version a conserver
        # (cas d'une version preliminaire republiee ensuite en "definitive").
        if year not in by_year:
            by_year[year] = url
            print(f"  [OK] {year} -> {url}")

    kept_years = sorted(by_year, reverse=True)[:NB_YEARS]
    saved = 0
    for year in kept_years:
        nom_pdf = f"FTUSA_{year}.pdf"
        save_document(conn, source_id, None, nom_pdf, year, by_year[year])
        saved += 1

    conn.close()
    if kept_years:
        print(f"[INFO] {saved} document(s) FTUSA enregistre(s) en base (annees {min(kept_years)}-{max(kept_years)})")
    else:
        print("[INFO] Aucun document FTUSA enregistre")
    return saved


if __name__ == "__main__":
    sync_documents()
