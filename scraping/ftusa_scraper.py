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

import io  # traite les bytes du PDF telecharge comme un fichier en memoire
import re  # extraction de liens et d'annees par expressions regulieres
import sys  # reconfigure l'encodage de la sortie standard
import time  # pauses entre tentatives de telechargement

import pdfplumber  # lit le texte des pages PDF (detection de l'annee)
import requests  # requetes HTTP vers le site FTUSA

# Certains liens de la page (ex: un formulaire au nom en arabe) contiennent
# des caractères hors de la page de code par défaut de la console Windows
# (cp1252) : on bascule stdout en UTF-8 pour ne jamais planter sur un print.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # evite les erreurs d'encodage a l'affichage

from database.repository import (
    ensure_database,       # cree la base si elle n'existe pas encore
    get_connection,          # ouvre la connexion a la base
    get_or_create_source,      # recupere/cree l'id de la source "FTUSA"
    init_schema,                 # cree/met a jour les tables si besoin
    save_document,                 # enregistre les metadonnees d'un document
)
from utils.pdf_utils import is_valid_pdf  # verifie que le contenu telecharge est bien un PDF

FTUSA_BASE_URL = "https://www.ftusanet.org"  # domaine racine, prefixe des liens relatifs
FTUSA_REPORTS_PAGE = f"{FTUSA_BASE_URL}/rapports-annuels/"  # page listant les rapports annuels
# Bloc "à la une" en bas de page : ne contient pas des rapports annuels
# (voir docstring ci-dessus) -> tout ce qui suit ce marqueur est ignoré.
SIDEBAR_MARKER = '<section id="actusBottom"'  # marqueur HTML du debut de la zone a ignorer
NB_YEARS = 10  # nombre d'annees les plus recentes a conserver en base

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}  # UA pour eviter les blocages serveur

YEAR_TITLE_RE = re.compile(r"\ben\s+(20\d{2})\b", re.IGNORECASE)  # motif "en 2024" typique du titre du rapport
BARE_YEAR_RE = re.compile(r"\b(20\d{2})\b")  # repli : n'importe quelle annee 20xx isolee dans le texte


# ------------------------------------------------------------------ #
# Requêtes réseau
# ------------------------------------------------------------------ #

# Utilité : requête GET avec 3 tentatives en cas d'échec réseau
def _get_with_retries(url, timeout=30, retries=3):
    """Le site peut echouer ponctuellement (timeout, 5xx passager) :
    quelques nouvelles tentatives suffisent (meme approche que bvmt_scraper)."""
    for attempt in range(1, retries + 1):  # jusqu'a `retries` tentatives
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)  # requete GET simple
            response.raise_for_status()  # leve une exception si code HTTP d'erreur
            return response  # succes, on renvoie la reponse
        except requests.RequestException as exc:
            if attempt == retries:
                raise  # derniere tentative epuisee, on remonte l'erreur
            print(f"  [WARN] Tentative {attempt}/{retries} echouee pour {url} : {exc}")  # log avant nouvel essai
            time.sleep(1.5)  # petite pause avant de reessayer


# ------------------------------------------------------------------ #
# Collecte et détection de l'année
# ------------------------------------------------------------------ #

# Utilité : récupère les liens PDF de la zone principale (exclut le bloc "à la une")
def _collect_main_pdf_links():
    """Renvoie les liens .pdf de la zone principale de la page (avant le
    bloc "à la une"), sans doublon, dans l'ordre d'apparition (du plus
    récent au plus ancien)."""
    response = _get_with_retries(FTUSA_REPORTS_PAGE, timeout=30)  # telecharge la page HTML des rapports
    html = response.text  # contenu HTML brut
    cutoff = html.find(SIDEBAR_MARKER)  # position du bloc "à la une" a exclure
    main_html = html[:cutoff] if cutoff != -1 else html  # ne garde que la zone principale
    seen = set()  # liens deja rencontres (deduplication)
    ordered = []  # liens retenus, dans l'ordre d'apparition
    for link in re.findall(r'href="([^"]+\.pdf)"', main_html):  # tous les liens .pdf de la zone principale
        if link not in seen:
            seen.add(link)  # marque ce lien comme deja vu
            ordered.append(link)  # conserve l'ordre d'apparition (recent -> ancien)
    return ordered


# Utilité : lit les 2 premières pages du PDF pour trouver l'année du rapport
def _detect_report_year(pdf_bytes):
    """Détermine l'année couverte par le rapport en lisant son titre (les 2
    premières pages), plutôt que son nom de fichier (trop peu fiable sur
    l'ensemble des archives, ex: "Rapport-FTUSA-DEFINITIF.pdf")."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:  # ouvre le PDF depuis les bytes en memoire
        text = ""  # texte cumule des premieres pages
        for page in pdf.pages[:2]:  # ne lit que les 2 premieres pages (titre)
            text += page.extract_text() or ""  # ajoute le texte extrait (vide si page illisible)
    match = YEAR_TITLE_RE.search(text) or BARE_YEAR_RE.search(text)  # motif precis puis repli plus large
    return int(match.group(1)) if match else None  # annee trouvee, sinon None


# ------------------------------------------------------------------ #
# Orchestration
# ------------------------------------------------------------------ #

# Utilité : orchestre tout : collecte, téléchargement, filtrage, enregistrement
def sync_documents():
    """Télécharge (en mémoire) les rapports de la zone principale de la page
    FTUSA, détermine l'année réelle de chacun d'après son contenu, et
    enregistre en base le rapport le plus récent pour chacune des NB_YEARS
    dernières années disponibles. Aucun PDF n'est écrit sur disque."""
    ensure_database()  # cree la base si necessaire
    conn = get_connection()  # ouvre la connexion a la base
    init_schema(conn)  # cree/migre les tables si besoin
    source_id = get_or_create_source(conn, "FTUSA", FTUSA_REPORTS_PAGE)  # id de la source "FTUSA"

    links = _collect_main_pdf_links()  # liens PDF de la zone principale, recent -> ancien
    print(f"[STEP] {len(links)} document(s) trouve(s) dans la zone principale de la page FTUSA")

    by_year = {}  # annee -> url du rapport retenu pour cette annee
    for link in links:
        url = link if link.startswith("http") else FTUSA_BASE_URL + link  # normalise en URL absolue
        try:
            response = _get_with_retries(url, timeout=60)  # telecharge le PDF en memoire
        except requests.RequestException as exc:
            print(f"  [WARN] Telechargement echoue apres 3 tentatives, ignore : {url} ({exc})")
            continue  # document inaccessible, passe au suivant
        if not is_valid_pdf(response.content):
            print(f"  [WARN] Contenu recu non-PDF (page d'erreur probable), ignore : {url}")
            continue  # contenu recu invalide, ignore ce lien
        year = _detect_report_year(response.content)  # annee lue dans le contenu du PDF
        if year is None:
            print(f"  [WARN] Annee introuvable dans le contenu, ignore : {url}")
            continue  # impossible de dater le rapport, ignore
        # La page liste les rapports du plus recent au plus ancien : la
        # premiere occurrence d'une annee est donc la version a conserver
        # (cas d'une version preliminaire republiee ensuite en "definitive").
        if year not in by_year:
            by_year[year] = url  # premiere occurrence de cette annee = version a garder
            print(f"  [OK] {year} -> {url}")

    kept_years = sorted(by_year, reverse=True)[:NB_YEARS]  # les NB_YEARS annees les plus recentes disponibles
    saved = 0  # compteur de documents enregistres
    for year in kept_years:
        nom_pdf = f"FTUSA_{year}.pdf"  # nom de fichier construit (aucun fichier ecrit sur disque)
        save_document(conn, source_id, None, nom_pdf, year, by_year[year])  # cmf_id=None : source sectorielle
        saved += 1

    conn.close()  # ferme la connexion a la base
    if kept_years:
        print(f"[INFO] {saved} document(s) FTUSA enregistre(s) en base (annees {min(kept_years)}-{max(kept_years)})")
    else:
        print("[INFO] Aucun document FTUSA enregistre")
    return saved


if __name__ == "__main__":
    sync_documents()  # point d'entree quand le script est lance directement
