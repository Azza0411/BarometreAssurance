"""
Scraper pour le site de la Bourse de Tunis (BVMT) :
https://tunis-stockexchange.com/

Contrairement à FTUSA (données sectorielles), BVMT publie des informations
PAR société cotée (comme CMF) : on réutilise donc le registre CMF
(config.company_registry) pour reconnaître les sociétés, en ne traitant que
celles effectivement cotées en bourse (un sous-ensemble des sociétés
suivies par CMF, déterminé dynamiquement via la liste du secteur
"Assurance" sur le site — pas de liste codée en dur).

Types de données par société :
  - "Status de cotation" : simple fait de présence dans la liste des
    sociétés cotées du secteur Assurance -> pas de valeur à extraire d'un
    document, la valeur ("Cotée") est enregistrée directement pendant le
    scraping (voir sync_status_cotation), avec un document de traçabilité
    (nom_pdf/lien) pointant vers la fiche de la société pour cette année.
  - Rapports ESG (PDF), un ou plusieurs par société au fil du temps : le
    scraping (sync_esg_documents) se limite à enregistrer les documents ;
    l'extraction des KPI de gouvernance se fait dans
    extraction/bvmt_kpi_extractor.py comme pour les autres sources.
  - Données de marché (sync_market_data) : Mnemo/Denomination/Nombre
    d'actions actuel (sur le document de profil de chaque société), et un
    document sectoriel par année pointant vers le bulletin officiel de la
    cote du dernier jour de bourse de cette année-là (cours de clôture par
    société, extrait dans extraction/kpi_extraction_pipeline.py via
    extraction/bvmt_bulletin_kpi_extractor.py).

Les identifiants numériques utilisés par le site pour filtrer par société
(paramètre `societe` sur la page de reporting ESG) sont découverts
dynamiquement à chaque exécution (pas de valeur codée en dur), en associant
le nom affiché sur le site au registre CMF via find_code_by_name().
"""

import datetime  # année courante, dates de bulletins
import re  # extraction par expressions régulières (HTML brut, pas de parseur)
import time  # pauses entre tentatives HTTP

import requests  # requêtes HTTP simples (pas de navigateur, site scrapable en HTML statique)

from config.company_registry import find_code_by_name  # associe un nom affiché sur BVMT au code CMF
from database.repository import (
    ensure_database,  # crée la base si elle n'existe pas
    get_connection,  # ouvre la connexion MySQL
    get_or_create_company,  # id interne d'une société (table societes)
    get_or_create_source,  # id de la source "BVMT" (table sources)
    init_schema,  # crée/migre les tables si besoin
    save_document,  # enregistre les métadonnées d'un document (jamais le PDF)
    save_kpi_value,  # enregistre une valeur de KPI rattachée à un document
)

BASE_URL = "https://tunis-stockexchange.com"
EMETTEURS_URL = f"{BASE_URL}/emetteurs"  # page listant les sociétés cotées, filtrable par secteur
ESG_REPORTS_URL = f"{BASE_URL}/reporting-esg-societes-cotees"  # page listant les rapports ESG par société
EDITIONS_STATISTIQUE_URL = f"{BASE_URL}/editions-statistique"  # archive des bulletins officiels quotidiens
INSTRUMENT_URL_TEMPLATE = f"{BASE_URL}/bourse/instrument/{{isin}}"  # endpoint AJAX de cotation live par ISIN
# Identifiant du secteur "Assurance" dans le filtre de la page /emetteurs
# (voir la liste des <option> du filtre "Secteur" sur cette page).
SECTEUR_ASSURANCE_ID = 1938
# Premiere annee couverte par l'archive des bulletins officiels quotidiens
# (verifie manuellement : editions-statistique remonte au moins a fin 2015).
BULLETIN_START_YEAR = 2015

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}  # UA générique pour les requêtes

TITLE_LINK_RE = re.compile(r'views-field-title">\s*<a href="([^"]+)"[^>]*>([^<]+)</a>')  # capture (lien, nom) d'une ligne de liste
SOCIETE_OPTION_RE = re.compile(r'<option value="(\d+)">([^<]+)</option>')  # capture (id numérique, nom) d'un <option> de filtre
PDF_LINK_RE = re.compile(r'href="([^"]+\.pdf)"')  # tout lien se terminant par .pdf
# Une date JJ-MM-AAAA dans le nom de fichier (ex: "star-reporting-esg-
# 30-05-2025.pdf") donne l'année du rapport ; à défaut, on cherche une
# année isolée (ex: "Rapport ESG 2025.pdf").
DATE_IN_FILENAME_RE = re.compile(r"\d{2}-\d{2}-(20\d{2})")  # date complète JJ-MM-AAAA -> capture l'année
BARE_YEAR_RE = re.compile(r"(20\d{2})")  # repli : une année isolée 20XX n'importe où dans le texte

# Fiche société (page statique /node/xxxx) : Code ISIN. La cotation live
# (AJAX "bourse/instrument/{isin}") : MNEMO et Titres émis, absents de la
# page statique (voir CAS_PARTICULIERS_BVMT.md).
ISIN_RE = re.compile(r"<td><strong>Code ISIN</strong></td>\s*<td[^>]*>([^<]+)</td>")  # ligne de tableau "Code ISIN"
MNEMO_RE = re.compile(r"<td><strong>MNEMO</strong></td>\s*<td[^>]*>([^<]+)</td>")  # ligne de tableau "MNEMO"
TITRES_EMIS_RE = re.compile(r"<td><strong>Titres .mis</strong></td>\s*<td[^>]*>([^<]+)</td>")  # ligne "Titres émis" (accent tolérant)
# Bulletin officiel quotidien : nom de fichier "bullAAAAMMJJ.pdf" (ou
# "BullAAAAMMJJ.pdf"). Deux conventions de chemin coexistent selon
# l'ancienneté : archive consolidée "bulletin/pdf/bullAAAAMMJJ.pdf" (ex:
# 2015-2021) vs dossier mensuel "AAAA-MM/BullAAAAMMJJ.pdf" (récent) -> motif
# volontairement large sur le chemin, seul le nom de fichier est contraint.
BULLETIN_LINK_RE = re.compile(r'href="([^"]*[Bb]ull(\d{8})\.pdf)"')  # capture (lien complet, date AAAAMMJJ)


def _get_with_retries(url, params=None, retries=3, timeout=30):
    """Le site répond parfois par un simple timeout de lecture (observé de
    façon intermittente) : quelques nouvelles tentatives suffisent."""
    for attempt in range(1, retries + 1):  # jusqu'à `retries` tentatives
        try:
            response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=timeout)  # requête GET
            response.raise_for_status()  # lève une exception si code HTTP d'erreur
            return response  # succès, on renvoie la réponse
        except requests.RequestException as exc:
            if attempt == retries:
                raise  # dernière tentative épuisée, on remonte l'erreur
            print(f"  [WARN] Tentative {attempt}/{retries} echouee pour {url} : {exc}")
            time.sleep(1.5)  # pause avant de réessayer


def _fetch_listed_insurance_companies():
    """Renvoie [(nom_societe, chemin_profil), ...] pour les sociétés cotées
    du secteur Assurance, tel qu'affiché sur /emetteurs."""
    response = _get_with_retries(
        EMETTEURS_URL, params={"field_secteur_d_activite_target_id": SECTEUR_ASSURANCE_ID}  # filtre serveur par secteur
    )
    return [(name.strip(), path) for path, name in TITLE_LINK_RE.findall(response.text)]  # parse toutes les lignes de la liste


def _fetch_esg_societe_ids():
    """Renvoie {nom_societe: id} pour le filtre "societe" de la page de
    reporting ESG (toutes sociétés cotées, pas seulement Assurance)."""
    response = _get_with_retries(ESG_REPORTS_URL)  # page complète, sans filtre secteur
    # SOCIETE_OPTION_RE exige un id numerique : l'option "Toutes les
    # Societes" (value="All") ne matche jamais et est deja exclue de facto.
    return {name.strip(): int(societe_id) for societe_id, name in SOCIETE_OPTION_RE.findall(response.text)}  # dict nom -> id


def _fetch_esg_report_links(societe_id):
    """Renvoie les liens PDF des rapports ESG d'une société (URLs absolues)."""
    response = _get_with_retries(ESG_REPORTS_URL, params={"societe": societe_id})  # filtre serveur par société
    links = PDF_LINK_RE.findall(response.text)  # tous les liens .pdf de la page filtrée
    return [link if link.startswith("http") else BASE_URL + link for link in links]  # normalise en URLs absolues


def _report_year(pdf_url):
    match = DATE_IN_FILENAME_RE.search(pdf_url) or BARE_YEAR_RE.search(pdf_url)  # date complète, sinon année isolée
    return int(match.group(1)) if match else None  # None si aucune année détectable


def _matched_insurance_companies():
    """Sociétés du secteur Assurance cotées en bourse, reconnues dans le
    registre CMF : [(code, nom_sur_bvmt, chemin_profil), ...]."""
    matched = []
    for name, path in _fetch_listed_insurance_companies():  # toutes les sociétés Assurance listées sur BVMT
        code = find_code_by_name(name)  # tente de faire correspondre au registre CMF
        if code:
            matched.append((code, name, path))  # société reconnue, on la garde
        else:
            print(f"  [WARN] Societe BVMT non reconnue dans le registre CMF : {name}")  # société ignorée (pas dans le registre)
    return matched


def sync_status_cotation():
    """Enregistre le KPI "Status de cotation" = "Cotée" pour chaque société
    du secteur Assurance présente dans la liste des sociétés cotées BVMT."""
    ensure_database()  # crée la base si besoin
    conn = get_connection()  # ouvre la connexion
    init_schema(conn)  # crée/migre les tables
    source_id = get_or_create_source(conn, "BVMT", BASE_URL)  # id de la source "BVMT"

    companies = _matched_insurance_companies()  # découverte dynamique des sociétés cotées reconnues
    print(f"[STEP] {len(companies)} societe(s) d'assurance cotees reconnues sur BVMT")

    year = datetime.datetime.now().year  # année courante, utilisée comme année du document de traçabilité
    saved = 0
    for code, name, path in companies:  # une itération par société reconnue
        cmf_id = get_or_create_company(conn, code, name)  # id interne de la société
        profile_url = path if path.startswith("http") else BASE_URL + path  # URL absolue de la fiche société
        document_id = save_document(conn, source_id, cmf_id, f"{code}_profil_bvmt", year, profile_url)  # document de traçabilité
        save_kpi_value(
            conn, document_id, "BVMT - Liste des societes cotees", "Status de cotation", valeur_texte="Cotée"  # valeur fixe, pas extraite d'un PDF
        )
        saved += 1
        print(f"  [OK] {code} : Cotee ({profile_url})")

    conn.close()  # ferme la connexion
    print(f"[INFO] {saved} statut(s) de cotation enregistre(s) en base\n")
    return saved


def sync_esg_documents():
    """Enregistre un document par rapport ESG trouve, pour chaque societe
    d'assurance cotee reconnue."""
    ensure_database()  # crée la base si besoin
    conn = get_connection()  # ouvre la connexion
    init_schema(conn)  # crée/migre les tables
    source_id = get_or_create_source(conn, "BVMT", BASE_URL)  # id de la source "BVMT"

    companies = _matched_insurance_companies()  # sociétés Assurance reconnues
    societe_ids = _fetch_esg_societe_ids()  # dict nom -> id de filtre ESG (toutes sociétés cotées)

    saved = 0
    for code, name, _path in companies:  # une itération par société reconnue
        societe_id = societe_ids.get(name)  # id de filtre correspondant à cette société
        if societe_id is None:
            print(f"  [WARN] Pas d'identifiant de filtre ESG trouve pour {name}")
            continue  # société sans filtre ESG connu, on l'ignore
        cmf_id = get_or_create_company(conn, code, name)  # id interne de la société
        links = _fetch_esg_report_links(societe_id)  # tous les rapports ESG trouvés pour cette société
        for link in links:  # une itération par rapport PDF
            year = _report_year(link)  # année déduite du nom de fichier
            if year is None:
                print(f"  [WARN] Annee introuvable dans le nom du rapport, ignore : {link}")
                continue  # rapport sans année identifiable, ignoré
            nom_pdf = f"{code}_ESG_{year}.pdf"  # nom de fichier construit (pas de téléchargement)
            save_document(conn, source_id, cmf_id, nom_pdf, year, link)  # enregistre les métadonnées du rapport
            saved += 1
            print(f"  [OK] {code} {year} : {link}")

    conn.close()  # ferme la connexion
    print(f"[INFO] {saved} rapport(s) ESG enregistre(s) en base\n")
    return saved


def _bulletin_links_in_range(date_min, date_max):
    """Renvoie [(date_str "AAAAMMJJ", url_absolue), ...] des bulletins
    officiels publiés entre `date_min` et `date_max` (AAAA-MM-JJ), triés du
    plus ancien au plus récent."""
    response = _get_with_retries(EDITIONS_STATISTIQUE_URL, params={"date[min]": date_min, "date[max]": date_max})  # filtre serveur par plage de dates
    matches = {(date_str, path) for path, date_str in BULLETIN_LINK_RE.findall(response.text)}  # set pour dédupliquer les liens identiques
    return sorted((date_str, path if path.startswith("http") else BASE_URL + path) for date_str, path in matches)  # tri chronologique croissant


def _last_bulletin_of_year(year, today):
    """Bulletin du dernier jour de bourse de `year` (fenêtre de recherche en
    décembre, élargie si aucun bulletin n'y est trouvé — jours fériés
    groupés en fin d'année certaines années). Pour l'année en cours
    (`today.year`), cherche plutôt le bulletin le plus récent disponible
    (décembre n'existe pas encore)."""
    if year < today.year:  # année révolue : on cherche en fin d'année
        windows = [(f"{year}-12-15", f"{year}-12-31"), (f"{year}-12-01", f"{year}-12-31"), (f"{year}-01-01", f"{year}-12-31")]  # fenêtres de + en + larges
    else:  # année en cours : décembre pas encore atteint
        windows = [((today - datetime.timedelta(days=30)).isoformat(), today.isoformat())]  # 30 derniers jours jusqu'à aujourd'hui
    for date_min, date_max in windows:  # essaie chaque fenêtre jusqu'à en trouver une non vide
        links = _bulletin_links_in_range(date_min, date_max)  # bulletins trouvés dans cette fenêtre
        if links:
            return links[-1]  # le plus récent de la fenêtre (liste triée croissant)
    return None, None  # aucun bulletin trouvé dans aucune fenêtre


def sync_market_data():
    """Pour chaque société d'assurance cotée reconnue, enregistre sur son
    document de profil (même document que sync_status_cotation) :
      - "Mnemo (BVMT)" et "Denomination (BVMT)" : nécessaires à
        extraction.bvmt_bulletin_kpi_extractor pour reconnaître les lignes
        des bulletins (voir CAS_PARTICULIERS_BVMT.md — une simple
        correspondance de nom confondrait par exemple BH ASSURANCE avec BH
        BANK, deux sociétés distinctes cotées séparément) ;
      - "Nombre d'actions (BVMT)" : nombre de titres émis actuel, utilisé en
        repli par extraction.calculated_kpi_extractor quand le "Nombre
        d'actions" par année (source CMF) n'est pas disponible (~4% de
        couverture seulement, voir CAS_PARTICULIERS_PRESENTATION.md).

    Enregistre aussi un document par année (BULLETIN_START_YEAR à
    aujourd'hui), sans société associée (comme CGA/FTUSA), pointant vers le
    bulletin officiel du dernier jour de bourse de cette année-là : un seul
    bulletin couvre toutes les sociétés, l'extraction du cours de clôture par
    société se fait dans extraction/kpi_extraction_pipeline.py."""
    ensure_database()  # crée la base si besoin
    conn = get_connection()  # ouvre la connexion
    init_schema(conn)  # crée/migre les tables
    source_id = get_or_create_source(conn, "BVMT", BASE_URL)  # id de la source "BVMT"

    companies = _matched_insurance_companies()  # sociétés Assurance reconnues
    year_now = datetime.datetime.now().year  # année courante (document de profil + borne haute des bulletins)
    company_kpis_saved = 0
    for code, name, path in companies:  # une itération par société reconnue
        profile_url = path if path.startswith("http") else BASE_URL + path  # URL absolue de la fiche société
        try:
            profile_response = _get_with_retries(profile_url)  # récupère la page statique de la fiche
        except requests.RequestException as exc:
            print(f"  [WARN] Fiche BVMT injoignable pour {code} : {exc}")
            continue  # fiche inaccessible, société ignorée pour ce cycle
        isin_match = ISIN_RE.search(profile_response.text)  # cherche le code ISIN dans la fiche statique
        if not isin_match:
            print(f"  [WARN] Code ISIN introuvable sur la fiche BVMT de {code}")
            continue  # sans ISIN, impossible d'interroger la cotation live
        isin = isin_match.group(1).replace(" ", "").strip()  # nettoie les espaces éventuels dans l'ISIN

        try:
            instrument_response = _get_with_retries(INSTRUMENT_URL_TEMPLATE.format(isin=isin))  # endpoint AJAX de cotation live
            instrument_html = instrument_response.json().get("html", "")  # réponse JSON contenant un fragment HTML
        except (requests.RequestException, ValueError) as exc:
            print(f"  [WARN] Cotation live BVMT injoignable pour {code} ({isin}) : {exc}")
            continue  # cotation live inaccessible, société ignorée pour ce cycle

        cmf_id = get_or_create_company(conn, code, name)  # id interne de la société
        document_id = save_document(conn, source_id, cmf_id, f"{code}_profil_bvmt", year_now, profile_url)  # même document que sync_status_cotation

        save_kpi_value(conn, document_id, "BVMT - Marche", "Denomination (BVMT)", valeur_texte=name)  # nom affiché sur BVMT
        company_kpis_saved += 1

        mnemo_match = MNEMO_RE.search(instrument_html)  # cherche le MNEMO dans le fragment de cotation live
        if mnemo_match:
            save_kpi_value(conn, document_id, "BVMT - Marche", "Mnemo (BVMT)", valeur_texte=mnemo_match.group(1).strip())  # code court de la société
            company_kpis_saved += 1

        titres_match = TITRES_EMIS_RE.search(instrument_html)  # cherche le nombre de titres émis
        titres_digits = re.sub(r"\D", "", titres_match.group(1)) if titres_match else ""  # ne garde que les chiffres (retire espaces/séparateurs)
        if titres_digits:
            save_kpi_value(
                conn, document_id, "BVMT - Marche", "Nombre d'actions (BVMT)", valeur_nombre=float(titres_digits)  # converti en nombre
            )
            company_kpis_saved += 1

        print(f"  [OK] {code} : ISIN={isin}, mnemo={mnemo_match.group(1).strip() if mnemo_match else '?'}")

    print(f"[INFO] {company_kpis_saved} valeur(s) Mnemo/Denomination/Nombre d'actions enregistree(s)\n")

    today = datetime.date.today()  # date du jour, utilisée pour la fenêtre de l'année en cours
    bulletins_saved = 0
    for year in range(BULLETIN_START_YEAR, year_now + 1):  # une itération par année couverte par l'archive
        date_str, bulletin_url = _last_bulletin_of_year(year, today)  # dernier bulletin de bourse de cette année
        if not bulletin_url:
            print(f"  [WARN] Aucun bulletin trouve pour {year}")
            continue  # aucun bulletin trouvé pour cette année, ignorée
        save_document(conn, source_id, None, f"bulletin_{year}.pdf", year, bulletin_url)  # document sans société associée (sectoriel)
        bulletins_saved += 1
        print(f"  [OK] Bulletin {year} ({date_str}) : {bulletin_url}")

    conn.close()  # ferme la connexion
    print(f"[INFO] {bulletins_saved} bulletin(s) annuel(s) enregistre(s) en base\n")
    return {"company_kpis_saved": company_kpis_saved, "bulletins_saved": bulletins_saved}


def sync_all():
    cotation_saved = sync_status_cotation()  # volet 1 : statut de cotation (présence dans la liste Assurance)
    esg_saved = sync_esg_documents()  # volet 2 : documents ESG (rapports PDF par société)
    market = sync_market_data()  # volet 3 : données de marché (profil + bulletins officiels annuels)
    return cotation_saved + esg_saved + market["company_kpis_saved"] + market["bulletins_saved"]  # total agrégé des 3 volets


if __name__ == "__main__":
    import sys  # accès à stdout pour forcer l'encodage

    sys.stdout.reconfigure(encoding="utf-8")  # évite les erreurs d'affichage des accents dans la console
    sync_all()  # exécute les 3 volets à la suite
