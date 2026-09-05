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
import re  # regex sur HTML brut
import time  # pause entre tentatives

import requests  # requêtes HTTP

from config.company_registry import find_code_by_name  # nom BVMT -> code CMF
from database.repository import (
    ensure_database,  # crée la base
    get_connection,  # connexion MySQL
    get_or_create_company,  # id société
    get_or_create_source,  # id source BVMT
    init_schema,  # tables à jour
    save_document,  # enregistre métadonnées
    save_kpi_value,  # enregistre une valeur KPI
)

BASE_URL = "https://tunis-stockexchange.com"
EMETTEURS_URL = f"{BASE_URL}/emetteurs"  # page des sociétés cotées
ESG_REPORTS_URL = f"{BASE_URL}/reporting-esg-societes-cotees"  # page des rapports ESG
EDITIONS_STATISTIQUE_URL = f"{BASE_URL}/editions-statistique"  # archive des bulletins
INSTRUMENT_URL_TEMPLATE = f"{BASE_URL}/bourse/instrument/{{isin}}"  # AJAX cotation live
# Identifiant du secteur "Assurance" dans le filtre de la page /emetteurs
# (voir la liste des <option> du filtre "Secteur" sur cette page).
SECTEUR_ASSURANCE_ID = 1938
# Premiere annee couverte par l'archive des bulletins officiels quotidiens
# (verifie manuellement : editions-statistique remonte au moins a fin 2015).
BULLETIN_START_YEAR = 2015

REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}  # UA générique

TITLE_LINK_RE = re.compile(r'views-field-title">\s*<a href="([^"]+)"[^>]*>([^<]+)</a>')  # capture (lien, nom)
SOCIETE_OPTION_RE = re.compile(r'<option value="(\d+)">([^<]+)</option>')  # capture (id, nom)
PDF_LINK_RE = re.compile(r'href="([^"]+\.pdf)"')  # tout lien .pdf
# Une date JJ-MM-AAAA dans le nom de fichier (ex: "star-reporting-esg-
# 30-05-2025.pdf") donne l'année du rapport ; à défaut, on cherche une
# année isolée (ex: "Rapport ESG 2025.pdf").
DATE_IN_FILENAME_RE = re.compile(r"\d{2}-\d{2}-(20\d{2})")  # date JJ-MM-AAAA -> année
BARE_YEAR_RE = re.compile(r"(20\d{2})")  # repli : année isolée

# Fiche société (page statique /node/xxxx) : Code ISIN. La cotation live
# (AJAX "bourse/instrument/{isin}") : MNEMO et Titres émis, absents de la
# page statique (voir CAS_PARTICULIERS_BVMT.md).
ISIN_RE = re.compile(r"<td><strong>Code ISIN</strong></td>\s*<td[^>]*>([^<]+)</td>")  # ligne "Code ISIN"
MNEMO_RE = re.compile(r"<td><strong>MNEMO</strong></td>\s*<td[^>]*>([^<]+)</td>")  # ligne "MNEMO"
TITRES_EMIS_RE = re.compile(r"<td><strong>Titres .mis</strong></td>\s*<td[^>]*>([^<]+)</td>")  # ligne "Titres émis"
# Bulletin officiel quotidien : nom de fichier "bullAAAAMMJJ.pdf" (ou
# "BullAAAAMMJJ.pdf"). Deux conventions de chemin coexistent selon
# l'ancienneté : archive consolidée "bulletin/pdf/bullAAAAMMJJ.pdf" (ex:
# 2015-2021) vs dossier mensuel "AAAA-MM/BullAAAAMMJJ.pdf" (récent) -> motif
# volontairement large sur le chemin, seul le nom de fichier est contraint.
BULLETIN_LINK_RE = re.compile(r'href="([^"]*[Bb]ull(\d{8})\.pdf)"')  # capture (lien, date AAAAMMJJ)


# ------------------------------------------------------------------ #
# Requêtes réseau
# ------------------------------------------------------------------ #

# Utilité : requête GET générique avec 3 tentatives
def _get_with_retries(url, params=None, retries=3, timeout=30):
    """Le site répond parfois par un simple timeout de lecture (observé de
    façon intermittente) : quelques nouvelles tentatives suffisent."""
    for attempt in range(1, retries + 1):  # jusqu'à retries tentatives
        try:
            response = requests.get(url, params=params, headers=REQUEST_HEADERS, timeout=timeout)  # requête GET
            response.raise_for_status()  # lève si erreur HTTP
            return response  # succès
        except requests.RequestException as exc:
            if attempt == retries:
                raise  # dernière tentative, on relève
            print(f"  [WARN] Tentative {attempt}/{retries} echouee pour {url} : {exc}")
            time.sleep(1.5)  # pause avant nouvel essai


# ------------------------------------------------------------------ #
# Découverte des sociétés (partagée par les 3 volets)
# ------------------------------------------------------------------ #

# Utilité : découvre les sociétés cotées du secteur Assurance
def _fetch_listed_insurance_companies():
    """Renvoie [(nom_societe, chemin_profil), ...] pour les sociétés cotées
    du secteur Assurance, tel qu'affiché sur /emetteurs."""
    response = _get_with_retries(
        EMETTEURS_URL, params={"field_secteur_d_activite_target_id": SECTEUR_ASSURANCE_ID}  # filtre par secteur
    )
    return [(name.strip(), path) for path, name in TITLE_LINK_RE.findall(response.text)]  # parse la liste


# Utilité : récupère les identifiants de filtre ESG par société
def _fetch_esg_societe_ids():
    """Renvoie {nom_societe: id} pour le filtre "societe" de la page de
    reporting ESG (toutes sociétés cotées, pas seulement Assurance)."""
    response = _get_with_retries(ESG_REPORTS_URL)  # page complète, sans filtre
    # SOCIETE_OPTION_RE exige un id numerique : l'option "Toutes les
    # Societes" (value="All") ne matche jamais et est deja exclue de facto.
    return {name.strip(): int(societe_id) for societe_id, name in SOCIETE_OPTION_RE.findall(response.text)}  # nom -> id


# Utilité : récupère les liens PDF des rapports ESG d'une société
def _fetch_esg_report_links(societe_id):
    """Renvoie les liens PDF des rapports ESG d'une société (URLs absolues)."""
    response = _get_with_retries(ESG_REPORTS_URL, params={"societe": societe_id})  # filtre par société
    links = PDF_LINK_RE.findall(response.text)  # liens .pdf trouvés
    return [link if link.startswith("http") else BASE_URL + link for link in links]  # URLs absolues


# Utilité : déduit l'année d'un rapport depuis son nom de fichier
def _report_year(pdf_url):
    match = DATE_IN_FILENAME_RE.search(pdf_url) or BARE_YEAR_RE.search(pdf_url)  # date, sinon année isolée
    return int(match.group(1)) if match else None  # None si rien trouvé


# Utilité : relie les sociétés BVMT au registre des sociétés (find_code_by_name)
def _matched_insurance_companies():
    """Sociétés du secteur Assurance cotées en bourse, reconnues dans le
    registre CMF : [(code, nom_sur_bvmt, chemin_profil), ...]."""
    matched = []
    for name, path in _fetch_listed_insurance_companies():  # sociétés Assurance listées
        code = find_code_by_name(name)  # correspondance au registre CMF
        if code:
            matched.append((code, name, path))  # société reconnue
        else:
            print(f"  [WARN] Societe BVMT non reconnue dans le registre CMF : {name}")  # ignorée
    return matched


# ------------------------------------------------------------------ #
# Volet 1 : statut de cotation
# ------------------------------------------------------------------ #

# Utilité : volet 1 — enregistre le statut "Cotée" par société
def sync_status_cotation():
    """Enregistre le KPI "Status de cotation" = "Cotée" pour chaque société
    du secteur Assurance présente dans la liste des sociétés cotées BVMT."""
    ensure_database()  # crée la base
    conn = get_connection()  # connexion base
    init_schema(conn)  # tables à jour
    source_id = get_or_create_source(conn, "BVMT", BASE_URL)  # id source BVMT

    companies = _matched_insurance_companies()  # sociétés cotées reconnues
    print(f"[STEP] {len(companies)} societe(s) d'assurance cotees reconnues sur BVMT")

    year = datetime.datetime.now().year  # année du document de traçabilité
    saved = 0
    for code, name, path in companies:  # par société reconnue
        cmf_id = get_or_create_company(conn, code, name)  # id interne société
        profile_url = path if path.startswith("http") else BASE_URL + path  # URL absolue fiche
        document_id = save_document(conn, source_id, cmf_id, f"{code}_profil_bvmt", year, profile_url)  # traçabilité
        save_kpi_value(
            conn, document_id, "BVMT - Liste des societes cotees", "Status de cotation", valeur_texte="Cotée"  # valeur fixe
        )
        saved += 1
        print(f"  [OK] {code} : Cotee ({profile_url})")

    conn.close()  # ferme la connexion
    print(f"[INFO] {saved} statut(s) de cotation enregistre(s) en base\n")
    return saved


# ------------------------------------------------------------------ #
# Volet 2 : rapports ESG
# ------------------------------------------------------------------ #

# Utilité : volet 2 — enregistre les rapports ESG par société
def sync_esg_documents():
    """Enregistre un document par rapport ESG trouve, pour chaque societe
    d'assurance cotee reconnue."""
    ensure_database()  # crée la base
    conn = get_connection()  # connexion base
    init_schema(conn)  # tables à jour
    source_id = get_or_create_source(conn, "BVMT", BASE_URL)  # id source BVMT

    companies = _matched_insurance_companies()  # sociétés reconnues
    societe_ids = _fetch_esg_societe_ids()  # nom -> id de filtre ESG

    saved = 0
    for code, name, _path in companies:  # par société reconnue
        societe_id = societe_ids.get(name)  # id de filtre correspondant
        if societe_id is None:
            print(f"  [WARN] Pas d'identifiant de filtre ESG trouve pour {name}")
            continue  # pas de filtre ESG connu
        cmf_id = get_or_create_company(conn, code, name)  # id interne société
        links = _fetch_esg_report_links(societe_id)  # rapports ESG trouvés
        for link in links:  # par rapport PDF
            year = _report_year(link)  # année du nom de fichier
            if year is None:
                print(f"  [WARN] Annee introuvable dans le nom du rapport, ignore : {link}")
                continue  # année inconnue, ignoré
            nom_pdf = f"{code}_ESG_{year}.pdf"  # nom construit, pas téléchargé
            save_document(conn, source_id, cmf_id, nom_pdf, year, link)  # enregistre métadonnées
            saved += 1
            print(f"  [OK] {code} {year} : {link}")

    conn.close()  # ferme la connexion
    print(f"[INFO] {saved} rapport(s) ESG enregistre(s) en base\n")
    return saved


# ------------------------------------------------------------------ #
# Volet 3 : données de marché (cours, ISIN, bulletin)
# ------------------------------------------------------------------ #

# Utilité : récupère les bulletins publiés dans une plage de dates
def _bulletin_links_in_range(date_min, date_max):
    """Renvoie [(date_str "AAAAMMJJ", url_absolue), ...] des bulletins
    officiels publiés entre `date_min` et `date_max` (AAAA-MM-JJ), triés du
    plus ancien au plus récent."""
    response = _get_with_retries(EDITIONS_STATISTIQUE_URL, params={"date[min]": date_min, "date[max]": date_max})  # filtre par dates
    matches = {(date_str, path) for path, date_str in BULLETIN_LINK_RE.findall(response.text)}  # déduplique
    return sorted((date_str, path if path.startswith("http") else BASE_URL + path) for date_str, path in matches)  # tri croissant


# Utilité : trouve le dernier bulletin boursier d'une année
def _last_bulletin_of_year(year, today):
    """Bulletin du dernier jour de bourse de `year` (fenêtre de recherche en
    décembre, élargie si aucun bulletin n'y est trouvé — jours fériés
    groupés en fin d'année certaines années). Pour l'année en cours
    (`today.year`), cherche plutôt le bulletin le plus récent disponible
    (décembre n'existe pas encore)."""
    if year < today.year:  # année révolue
        windows = [(f"{year}-12-15", f"{year}-12-31"), (f"{year}-12-01", f"{year}-12-31"), (f"{year}-01-01", f"{year}-12-31")]  # fenêtres élargies
    else:  # année en cours
        windows = [((today - datetime.timedelta(days=30)).isoformat(), today.isoformat())]  # 30 derniers jours
    for date_min, date_max in windows:  # jusqu'à trouver un résultat
        links = _bulletin_links_in_range(date_min, date_max)  # bulletins trouvés
        if links:
            return links[-1]  # le plus récent de la fenêtre
    return None, None  # rien trouvé


# Utilité : volet 3 — cours, ISIN, nombre d'actions, bulletin annuel
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
    ensure_database()  # crée la base
    conn = get_connection()  # connexion base
    init_schema(conn)  # tables à jour
    source_id = get_or_create_source(conn, "BVMT", BASE_URL)  # id source BVMT

    companies = _matched_insurance_companies()  # sociétés reconnues
    year_now = datetime.datetime.now().year  # année courante
    company_kpis_saved = 0
    for code, name, path in companies:  # par société reconnue
        profile_url = path if path.startswith("http") else BASE_URL + path  # URL absolue fiche
        try:
            profile_response = _get_with_retries(profile_url)  # page statique de la fiche
        except requests.RequestException as exc:
            print(f"  [WARN] Fiche BVMT injoignable pour {code} : {exc}")
            continue  # fiche inaccessible
        isin_match = ISIN_RE.search(profile_response.text)  # code ISIN dans la fiche
        if not isin_match:
            print(f"  [WARN] Code ISIN introuvable sur la fiche BVMT de {code}")
            continue  # sans ISIN, pas de cotation live
        isin = isin_match.group(1).replace(" ", "").strip()  # nettoie les espaces

        try:
            instrument_response = _get_with_retries(INSTRUMENT_URL_TEMPLATE.format(isin=isin))  # AJAX cotation live
            instrument_html = instrument_response.json().get("html", "")  # fragment HTML dans le JSON
        except (requests.RequestException, ValueError) as exc:
            print(f"  [WARN] Cotation live BVMT injoignable pour {code} ({isin}) : {exc}")
            continue  # cotation live inaccessible

        cmf_id = get_or_create_company(conn, code, name)  # id interne société
        document_id = save_document(conn, source_id, cmf_id, f"{code}_profil_bvmt", year_now, profile_url)  # même document que le volet 1

        save_kpi_value(conn, document_id, "BVMT - Marche", "Denomination (BVMT)", valeur_texte=name)  # nom affiché
        company_kpis_saved += 1

        mnemo_match = MNEMO_RE.search(instrument_html)  # MNEMO dans le fragment
        if mnemo_match:
            save_kpi_value(conn, document_id, "BVMT - Marche", "Mnemo (BVMT)", valeur_texte=mnemo_match.group(1).strip())  # code court
            company_kpis_saved += 1

        titres_match = TITRES_EMIS_RE.search(instrument_html)  # nombre de titres émis
        titres_digits = re.sub(r"\D", "", titres_match.group(1)) if titres_match else ""  # ne garde que les chiffres
        if titres_digits:
            save_kpi_value(
                conn, document_id, "BVMT - Marche", "Nombre d'actions (BVMT)", valeur_nombre=float(titres_digits)  # converti en nombre
            )
            company_kpis_saved += 1

        print(f"  [OK] {code} : ISIN={isin}, mnemo={mnemo_match.group(1).strip() if mnemo_match else '?'}")

    print(f"[INFO] {company_kpis_saved} valeur(s) Mnemo/Denomination/Nombre d'actions enregistree(s)\n")

    today = datetime.date.today()  # date du jour
    bulletins_saved = 0
    for year in range(BULLETIN_START_YEAR, year_now + 1):  # par année couverte
        date_str, bulletin_url = _last_bulletin_of_year(year, today)  # dernier bulletin de l'année
        if not bulletin_url:
            print(f"  [WARN] Aucun bulletin trouve pour {year}")
            continue  # rien trouvé pour cette année
        save_document(conn, source_id, None, f"bulletin_{year}.pdf", year, bulletin_url)  # sans société, sectoriel
        bulletins_saved += 1
        print(f"  [OK] Bulletin {year} ({date_str}) : {bulletin_url}")

    conn.close()  # ferme la connexion
    print(f"[INFO] {bulletins_saved} bulletin(s) annuel(s) enregistre(s) en base\n")
    return {"company_kpis_saved": company_kpis_saved, "bulletins_saved": bulletins_saved}


# ------------------------------------------------------------------ #
# Orchestration globale
# ------------------------------------------------------------------ #

# Utilité : orchestre les 3 volets indépendants
def sync_all():
    cotation_saved = sync_status_cotation()  # volet 1 : statut de cotation
    esg_saved = sync_esg_documents()  # volet 2 : documents ESG
    market = sync_market_data()  # volet 3 : données de marché
    return cotation_saved + esg_saved + market["company_kpis_saved"] + market["bulletins_saved"]  # total des 3 volets


if __name__ == "__main__":
    import sys  # accès à stdout

    sys.stdout.reconfigure(encoding="utf-8")  # évite erreurs d'affichage
    sync_all()  # exécute les 3 volets
