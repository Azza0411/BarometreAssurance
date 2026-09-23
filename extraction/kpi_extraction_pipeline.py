"""
Pipeline d'extraction des KPI pour chaque document déjà enregistré en base
MySQL (tables `cmf` / `documents`), à partir de quatre tableaux et d'un
paragraphe narratif :
  - le Bilan (voir bilan_kpi_extractor.KPI_DEFINITIONS : Total actif,
    Capitaux propres, Total Passif, et les sections/lignes détaillées du
    Bilan Actif et Passif) ;
  - l'Annexe N°13 "Résultat technique par catégorie d'assurance Non-Vie"
    (voir annexe13_kpi_extractor.KPI_PATTERNS) ;
  - l'Annexe N°12 "Résultat technique par catégorie d'assurance Vie"
    (voir annexe12_kpi_extractor.KPI_PATTERNS) ;
  - les résumés "État de résultat technique" (Vie/Non-Vie) et "État de
    résultat" (résultat global) (voir resultat_kpi_extractor.KPI_PATTERNS) ;
  - le paragraphe "Présentation de la société" (voir
    presentation_kpi_extractor.KPI_NAMES : Date de création, Nombre
    d'actions, Siège social, Effectif).

Pour chaque document :
  - télécharge le PDF en mémoire (aucune écriture du PDF lui-même sur disque) ;
  - extrait tous les KPI des trois tableaux ;
  - enregistre chaque KPI trouvé dans la table MySQL `kpi_values`
    (document_id, tableau, kpi, valeur_nombre ou valeur_texte selon le type
    du KPI) — réexécuter le pipeline met à jour les valeurs existantes sans
    les dupliquer ;
  - pour chaque KPI manquant, consigne l'échec dans un rapport Excel
    data/kpis/echecs_extraction.xlsx (un onglet par KPI, colonnes
    dimensionnées et en-tête figé pour la lisibilité), avec une cause
    best-effort (PDF scanné, document en arabe, structure Takaful, ou motif
    introuvable).
"""

import io
import os
import queue
import re
import sys
import threading
import time

import pdfplumber
import requests
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.repository import (
    clear_document_failures,
    ensure_database,
    get_connection,
    get_document_ids_with_kpi,
    get_documents_in_backoff,
    record_document_failures,
    get_kpi_values_for_document,
    init_schema,
    list_all_documents,
    save_anomaly,
    save_kpi_value,
)
from pipelines.control import is_cancel_requested
from extraction.annexe12_kpi_extractor import KPI_PATTERNS as ANNEXE12_KPI_PATTERNS
from extraction.annexe12_kpi_extractor import extract_annexe12_kpis
from extraction.annexe13_kpi_extractor import KPI_PATTERNS as ANNEXE13_KPI_PATTERNS
from extraction.annexe13_kpi_extractor import extract_annexe13_kpis
from extraction.bilan_kpi_extractor import KPI_DEFINITIONS as BILAN_KPI_DEFINITIONS
from extraction.bilan_kpi_extractor import (
    USER_AGENT,
    _find_row_value,
    _is_passif_page,
    _normalizer,
    extract_all_bilan_kpis,
)
from extraction.bvmt_bulletin_kpi_extractor import extract_bulletin_cloture
from extraction.bvmt_kpi_extractor import KPI_NAMES as BVMT_KPI_NAMES
from extraction.bvmt_kpi_extractor import extract_bvmt_kpis
from extraction.cga_kpi_extractor import extract_cga_kpis
from extraction.ftusa_kpi_extractor import KPI_NAMES as FTUSA_KPI_NAMES
from extraction.ftusa_kpi_extractor import extract_ftusa_kpis
from extraction.presentation_kpi_extractor import KPI_NAMES as PRESENTATION_KPI_NAMES
from extraction.presentation_kpi_extractor import extract_presentation_kpis
import extraction.calculated_kpi_extractor as calculated_kpi_extractor
from extraction.data_cleaning import check_yoy_consistency
from extraction.resultat_kpi_extractor import KPI_NAMES as RESULTAT_KPI_NAMES
from extraction.resultat_kpi_extractor import extract_resultat_kpis
from utils.pdf_utils import is_valid_pdf
from utils.pipeline_logging import get_logger, log_json

_logger = get_logger("pipeline")

OUTPUT_DIR = os.path.join("data", "kpis")

_DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _save_sectoral_pdf(source: str, annee, content: bytes) -> None:
    directory = os.path.join(_DATA_ROOT, source.lower())
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, f"{source.upper()}_{annee}.pdf"), "wb") as f:
        f.write(content)


def _save_cmf_pdf_local(code: str, nom_pdf: str, content: bytes) -> None:
    """Persiste sur disque (data/cmf/<code>/<nom_pdf>) le PDF déjà
    téléchargé pour l'extraction KPI narrow ci-dessous — zéro coût réseau
    supplémentaire, juste une écriture locale. Sans ça, AUCUN code n'écrit
    jamais ce fichier automatiquement (vérifié 2026-09-15) : les pipelines
    grille complète (bilan_full_extractor.py, annexe12/13_pipeline.py,
    tableau_pipeline_service_takaful_*.py...), qui lisent le PDF depuis
    `api.services.data_management.local_pdf_path` plutôt que de le
    retélécharger, ne trouvaient donc jamais aucun document NOUVEAU tant
    qu'il n'avait pas été déposé là manuellement au moins une fois. Ignore
    silencieusement un fichier déjà présent (jamais écrasé — un document
    déjà extrait avec succès par la grille complète ne doit pas être
    réécrit à chaque passage du pipeline planifié)."""
    from api.services.data_management import local_pdf_path

    path = local_pdf_path("CMF", code, nom_pdf)
    if not path or os.path.isfile(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(content)
FAILURE_REPORT_PATH = os.path.join(OUTPUT_DIR, "echecs_extraction.xlsx")

TAKAFUL_EXTRACTABLE_COMPANIES = {"AL_AMANAH_TAKAFUL", "AT_TAKAFULIA", "ZITOUNA_TAKAFUL"}
ARABIC_RE = re.compile(r"[؀-ۿ]")

BILAN_KPI_NAMES = [definition[0] for definition in BILAN_KPI_DEFINITIONS]
ANNEXE13_KPI_NAMES = list(ANNEXE13_KPI_PATTERNS.keys())
ANNEXE12_KPI_NAMES = list(ANNEXE12_KPI_PATTERNS.keys())
TAKAFUL_FONDS_PARTICIPANTS_KPI = [
    "Surplus du Fonds Takaful Familial (TND)",
    "Surplus du Fonds Takaful Général (TND)",
    "Total actifs nets des adhérents (TND)",
    "Provisions techniques du Fonds des Adhérents (TND)",
    "Commission Wakala (TND)",
    "Commission Moudharaba (TND)",
    "Primes émises Familial (TND)",
    "Primes émises Général (TND)",
]

TAKAFUL_VENTILATION_KPI = [
    "Charges de prestations",
    "Charges d'acquisition et de gestion nettes",
]
KPI_NAMES = (
    BILAN_KPI_NAMES
    + ANNEXE13_KPI_NAMES
    + ANNEXE12_KPI_NAMES
    + RESULTAT_KPI_NAMES
    + PRESENTATION_KPI_NAMES
    + ["Primes émises par assurance"]
    + TAKAFUL_FONDS_PARTICIPANTS_KPI
    + TAKAFUL_VENTILATION_KPI
)

KPI_TABLE_LABEL = {name: "Bilan" for name in BILAN_KPI_NAMES}
KPI_TABLE_LABEL.update(
    {name: "Annexe 13 - Resultat technique Non-Vie" for name in ANNEXE13_KPI_NAMES}
)
KPI_TABLE_LABEL.update(
    {name: "Annexe 12 - Resultat technique Vie" for name in ANNEXE12_KPI_NAMES}
)
KPI_TABLE_LABEL.update(
    {name: "Etat de resultat (technique / global)" for name in RESULTAT_KPI_NAMES}
)
KPI_TABLE_LABEL.update(
    {name: "Presentation de la societe" for name in PRESENTATION_KPI_NAMES}
)
KPI_TABLE_LABEL["Primes émises par assurance"] = "Etat de resultat (technique / global)"
KPI_TABLE_LABEL.update(
    {name: "Annexes 3/4/5.1 - Fonds des Participants (Takaful)" for name in TAKAFUL_FONDS_PARTICIPANTS_KPI}
)
KPI_TABLE_LABEL.update(
    {name: "Annexes 14/15 - Ventilation par categorie d'assurance (Takaful)" for name in TAKAFUL_VENTILATION_KPI}
)


# Nombre de telechargements de rattrapage menes en parallele (voir
# _backfill_missing_local_pdfs) - retour utilisateur direct 2026-09-16 :
# "paralleliser le rattrapage des PDF pour accelerer", ce rattrapage etant
# strictement sequentiel jusqu'ici (jusqu'a ~200 documents deja connus,
# certains PDF de plusieurs Mo, sans aucun parallelisme). Meme ordre de
# grandeur que CMF_WORKERS (pipelines/cmf_pipeline.py) : assez pour un vrai
# gain, pas assez pour risquer de faire reagir le serveur CMF.
BACKFILL_WORKERS = 8


def _backfill_one_document(code, annee, nom_pdf, lien):
    """Telecharge et sauvegarde localement UN document (sans reparser) —
    borne dans le temps via un thread daemon (meme motif que
    _process_one_document_with_watchdog) - constate en conditions reelles
    le 2026-09-16 : ce telechargement peut rester bloque bien au-dela des
    30s+3 tentatives attendues de _get_with_retries (ex: connexion qui ne
    repond jamais sans jamais expirer cote socket). Renvoie True si
    sauvegarde, False sinon (echec ou delai depasse - deja journalise)."""
    result_q = queue.Queue(maxsize=1)

    def _target():
        try:
            response = _get_with_retries(lien, timeout=30)
            _save_cmf_pdf_local(code, nom_pdf, response.content)
            result_q.put(("ok", None))
        except Exception as exc:
            result_q.put(("error", exc))

    threading.Thread(target=_target, daemon=True).start()
    try:
        kind, exc = result_q.get(timeout=DOCUMENT_HARD_TIMEOUT_S)
    except queue.Empty:
        print(f"  [WARN] Rattrapage PDF local : {code} {annee} delai de {DOCUMENT_HARD_TIMEOUT_S}s depasse, document saute.")
        return False
    if kind == "error":
        print(f"  [WARN] Rattrapage PDF local echoue pour {code} {annee} : {exc}")
        return False
    return True


def _missing_local_pdf_documents(conn, already_done):
    """Documents CMF déjà extraits (dans `already_done`) dont le PDF local manque."""
    from api.services.data_management import local_pdf_path

    documents = [
        doc for doc in list_all_documents(conn)
        if doc[1] == "CMF" and doc[0] in already_done
    ]
    return [
        doc for doc in documents
        if not (local_pdf_path("CMF", doc[2], doc[4]) and os.path.isfile(local_pdf_path("CMF", doc[2], doc[4])))
    ]


def has_missing_local_pdfs():
    """Vrai s'il y a des PDF locaux à rattraper — sert à ne PAS annoncer
    l'étape "PDF locaux" dans la frise d'un premier lancement (base vide :
    rien à rattraper), voir pipelines/run_pipeline.py::main."""
    conn = get_connection()
    try:
        return bool(_missing_local_pdf_documents(conn, get_document_ids_with_kpi(conn)))
    finally:
        conn.close()


def _backfill_missing_local_pdfs(conn, already_done):
    """Télécharge (SANS reparser) le PDF local manquant de tout document CMF
    déjà extrait avec succès (dans `already_done`) — pas seulement les
    documents traités par la boucle principale ci-dessous, qui SAUTE
    justement ces documents-là.

    Corrige un decalage constate le 2026-09-16 sur une base de donnees
    deja peuplee avant l'existence de `_save_cmf_pdf_local` (ajoutee le
    2026-09-15) : des centaines de documents avaient deja leurs valeurs de
    KPI en base (donc `already_done`, jamais retraites) mais AUCUN fichier
    PDF local — "PDF collectes" (api/services/data_management.
    get_reliability_stats) restait bloque a 0% indefiniment meme apres une
    collecte reussie, puisque cette metrique lit le disque, pas la base.
    Ne re-extrait rien (aucun appel a pdfplumber/aux extracteurs KPI) :
    juste un telechargement + ecriture fichier.

    Paralleliste sur BACKFILL_WORKERS threads (2026-09-16, retour
    utilisateur : cette etape, purement sequentielle jusqu'ici, dominait
    le temps total sur une base deja peuplee sans cache PDF local - chaque
    telechargement est independant, borne dans le temps (voir
    _backfill_one_document), donc sans risque a paralleliser comme la
    synchronisation CMF (pipelines/cmf_pipeline.py::CMF_WORKERS)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    missing = _missing_local_pdf_documents(conn, already_done)
    if not missing:
        from pipelines.progress import drop_from_plan
        drop_from_plan("rattrapage_pdf")  # rien à rattraper : ne pèse plus dans le pourcentage global
        return 0
    print(f"\n===== RATTRAPAGE PDF LOCAUX MANQUANTS : {len(missing)} document(s) deja extrait(s) =====\n")
    from pipelines.progress import enter_phase_if_planned, reset_progress, bump_progress
    enter_phase_if_planned("rattrapage_pdf")
    reset_progress(total=len(missing), detail="PDF locaux manquants")
    saved = 0
    workers = min(BACKFILL_WORKERS, len(missing))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for document_id, _source_nom, code, _nom_entreprise, nom_pdf, annee, lien in missing:
            if is_cancel_requested():
                print("[ANNULE] Rattrapage PDF locaux interrompu par l'utilisateur (nouvelles soumissions arretees).")
                break
            future = pool.submit(_backfill_one_document, code, annee, nom_pdf, lien)
            futures[future] = (code, annee)
        for future in as_completed(futures):
            code_f, annee_f = futures[future]
            bump_progress(f"{code_f} {annee_f}")
            if future.result():
                saved += 1
    print(f"===== RATTRAPAGE TERMINE : {saved}/{len(missing)} PDF local(aux) sauvegarde(s) =====\n")
    return saved


def _get_with_retries(url, timeout, retries=3):
    """Meme approche que les scrapers de collecte (ex: scraping/ftusa_scraper.py) :
    un blip reseau ponctuel ne doit pas faire perdre les KPI d'un document
    pour tout un cycle de pipeline avant la prochaine execution planifiee.

    Verifie aussi que le contenu recu est bien un PDF (`is_valid_pdf`) : un
    lien expire ou une redirection vers une page de login/erreur renvoie
    souvent un statut HTTP 200 avec du HTML au lieu du PDF attendu, ce que
    pdfplumber signalerait plus loin par une exception peu explicite. Tous
    les appels de cette fonction dans ce fichier telechargent un PDF a
    parser -> le controle est fait ici, pas chez l'appelant."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
            response.raise_for_status()
            if not is_valid_pdf(response.content):
                raise ValueError(f"Contenu recu non-PDF (probablement une page d'erreur) : {url}")
            return response
        except (requests.RequestException, ValueError):
            if attempt == retries:
                raise
            time.sleep(1.5)


BALANCE_CHECK_TOLERANCE = 1.0

TOTAL_CP_ET_PASSIF_RE = re.compile(r"^total (des )?capitaux propres et (du )?passifs?\b")


def _check_balance(pdf, kpis):
    """Verifie l'equilibre comptable Total actif = Capitaux propres + Passif.
    Contrairement au garde-fou de plausibilite (bilan_kpi_extractor._is_plausible),
    qui rejette une valeur individuelle implausible, ce controle porte sur la
    coherence entre deux valeurs chacune individuellement plausibles : on ne
    sait pas laquelle des deux est en cause (ou si les deux le sont), donc on
    ne rejette rien ici, on journalise seulement l'ecart pour investigation.
    Renvoie l'ecart absolu si superieur a la tolerance, 0.0 si equilibre,
    None si le controle ne s'applique pas (ligne combinee introuvable)."""
    actif = kpis.get("Total actif")
    if not isinstance(actif, (int, float)):
        return None
    combined_passif = _find_row_value(pdf, TOTAL_CP_ET_PASSIF_RE, header_token=None, page_filter=_is_passif_page)
    if not isinstance(combined_passif, (int, float)):
        return None
    ecart = abs(actif - combined_passif)
    return ecart if ecart > BALANCE_CHECK_TOLERANCE else 0.0


def _extract_all_kpis(pdf, company_code=None):
    if company_code == "AL_AMANAH_TAKAFUL":
        from extraction.takaful_kpi_extractor import extract_al_amanah_takaful_kpis
        return extract_al_amanah_takaful_kpis(pdf)
    if company_code in TAKAFUL_EXTRACTABLE_COMPANIES:
        from extraction.takaful_kpi_extractor import extract_all_takaful_kpis
        kpis = extract_all_takaful_kpis(pdf)
        kpis.pop("_takaful_format", None)
        return kpis
    kpis = extract_all_bilan_kpis(pdf)
    kpis.update(extract_annexe13_kpis(pdf))
    kpis.update(extract_annexe12_kpis(pdf))
    kpis.update(extract_resultat_kpis(pdf))
    kpis.update(extract_presentation_kpis(pdf))
    return kpis


def _classify_cause(pdf, company_code):
    """Diagnostic best-effort de la cause d'échec, pour orienter un
    traitement manuel ultérieur."""
    if company_code == "AL_AMANAH_TAKAFUL":
        return "Compagnie Takaful (etats financiers en arabe) : seuls Total actif/Capitaux propres/Resultat Net/Primes emises sont vises, et de facon incomplete sur certains exercices scannes en image - voir extraction/CAS_PARTICULIERS_TAKAFUL.md"
    if company_code in TAKAFUL_EXTRACTABLE_COMPANIES:
        return "Compagnie Takaful : seuls Total actif/Capitaux propres/Resultat Net/Primes emises (+ Fonds des Participants en format nouveau) sont extraits (structure comptable Fonds des Adherents/Entreprise, pas de detail par poste)"
    sample_text = ""
    for page in pdf.pages[:3]:
        sample_text += page.extract_text() or ""
    if ARABIC_RE.search(sample_text):
        return "Document en arabe"
    total_chars = sum(len(p.chars) for p in pdf.pages[:4])
    if total_chars < 50:
        return "PDF scanne / image (texte non extractible)"
    return "Motif introuvable, ligne absente du document, ou format non reconnu"


def _log_source_result(source, kpi_values_saved, documents_with_kpi, download_errors, **extra):
    """Journalise le resultat d'une sous-pipeline d'extraction dans
    logs/pipeline.log, avec la meme distinction ok/empty que
    pipelines/run_pipeline.py pour la collecte : 0 valeur de KPI enregistree
    n'est pas forcement une panne (aucun nouveau document ce cycle), mais
    doit rester visible separement d'un succes normal plutot que d'etre
    invisible entre deux print() console."""
    event = "kpi_extraction_empty" if kpi_values_saved == 0 else "kpi_extraction_ok"
    log_json(
        _logger, event, source=source, kpi_values_saved=kpi_values_saved,
        documents_with_kpi=documents_with_kpi, download_errors=download_errors, **extra,
    )


def _write_failure_report(failures):
    wb = Workbook()
    wb.remove(wb.active)
    headers = ["Code", "Entreprise", "Annee", "Nom PDF", "Lien", "Cause"]
    col_widths = [10, 45, 8, 30, 70, 55]
    for kpi_name in KPI_NAMES:
        ws = wb.create_sheet(title=kpi_name[:31])
        ws.append(headers)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        ws.freeze_panes = "A2"
        for col_idx, width in enumerate(col_widths, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width
        for row in failures[kpi_name]:
            ws.append(list(row))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    wb.save(FAILURE_REPORT_PATH)


def _run_ftusa(conn, already_done=None):
    """Pipeline separe pour les documents de la source FTUSA (sectorielle,
    pas de societe associee) : un seul tableau, l'annexe "Compte
    d'exploitation par branche & par entreprise" (voir
    ftusa_kpi_extractor.extract_ftusa_kpis). Beaucoup plus petit que le
    pipeline CMF (une dizaine de documents au lieu de centaines) : rapporte
    directement sur la console plutot que via un fichier Excel dedie.

    `already_done` (ensemble de document_id déjà extraits avec succès) :
    si fourni, ces documents sont sautés — voir `run(force=...)`."""
    documents = [doc for doc in list_all_documents(conn) if doc[1] == "FTUSA"]
    if already_done:
        documents = [doc for doc in documents if doc[0] not in already_done]
    print(f"\n===== EXTRACTION KPI FTUSA : {len(documents)} document(s), {len(FTUSA_KPI_NAMES)} KPI =====\n")

    kpi_values_saved = documents_with_kpi = download_errors = 0
    for document_id, _source_nom, _code, _nom_entreprise, nom_pdf, annee, lien in documents:
        if is_cancel_requested():
            print("[ANNULE] Extraction KPI FTUSA interrompue par l'utilisateur.")
            break
        print(f"[STEP] FTUSA {annee} : {lien}")
        try:
            response = _get_with_retries(lien, timeout=60)
            _save_sectoral_pdf("FTUSA", annee, response.content)
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                kpis = extract_ftusa_kpis(pdf)
        except Exception as exc:
            print(f"  [ERROR] Echec de telechargement/lecture : {exc}")
            download_errors += 1
            continue

        found_count = sum(1 for v in kpis.values() if v is not None)
        for name, value in kpis.items():
            if value is not None:
                save_kpi_value(conn, document_id, "FTUSA - Compte exploitation par branche", name, valeur_nombre=value)
                kpi_values_saved += 1
        if found_count > 0:
            documents_with_kpi += 1
        print(f"  [{'OK' if found_count else 'WARN'}] {found_count}/{len(FTUSA_KPI_NAMES)} KPI enregistres en base")

    print("\n===== RESUME EXTRACTION KPI FTUSA =====")
    print(f"  Documents avec au moins 1 KPI   : {documents_with_kpi}")
    print(f"  Valeurs de KPI enregistrees      : {kpi_values_saved}")
    print(f"  Erreurs telechargement/lecture  : {download_errors}\n")
    _log_source_result("FTUSA", kpi_values_saved, documents_with_kpi, download_errors)

    return {
        "documents_with_kpi": documents_with_kpi,
        "kpi_values_saved": kpi_values_saved,
        "download_errors": download_errors,
    }


def _run_bvmt(conn, already_done=None):
    """Pipeline separe pour les documents de la source BVMT : seuls les
    rapports ESG (PDF, nom_pdf se terminant par ".pdf") necessitent une
    extraction. Les documents de "Status de cotation" n'ont pas de PDF
    associe (nom_pdf sans extension) : leur KPI est deja enregistre pendant
    le scraping (voir scraping.bvmt_scraper.sync_status_cotation).

    `already_done` : voir `_run_ftusa`."""
    documents = [
        doc for doc in list_all_documents(conn) if doc[1] == "BVMT" and doc[4].lower().endswith(".pdf")
    ]
    if already_done:
        documents = [doc for doc in documents if doc[0] not in already_done]
    print(f"\n===== EXTRACTION KPI BVMT : {len(documents)} document(s), {len(BVMT_KPI_NAMES)} KPI =====\n")

    kpi_values_saved = documents_with_kpi = download_errors = 0
    for document_id, _source_nom, code, _nom_entreprise, nom_pdf, annee, lien in documents:
        if is_cancel_requested():
            print("[ANNULE] Extraction KPI BVMT interrompue par l'utilisateur.")
            break
        print(f"[STEP] BVMT {code} {annee} : {lien}")
        try:
            response = _get_with_retries(lien, timeout=60)
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                kpis = extract_bvmt_kpis(pdf)
        except Exception as exc:
            print(f"  [ERROR] Echec de telechargement/lecture : {exc}")
            download_errors += 1
            continue

        found_count = sum(1 for v in kpis.values() if v is not None)
        for name, value in kpis.items():
            if value is not None:
                save_kpi_value(conn, document_id, "BVMT - Gouvernance", name, valeur_texte=value)
                kpi_values_saved += 1
        if found_count > 0:
            documents_with_kpi += 1
        print(f"  [{'OK' if found_count else 'WARN'}] {found_count}/{len(BVMT_KPI_NAMES)} KPI enregistres en base")

    print("\n===== RESUME EXTRACTION KPI BVMT =====")
    print(f"  Documents avec au moins 1 KPI   : {documents_with_kpi}")
    print(f"  Valeurs de KPI enregistrees      : {kpi_values_saved}")
    print(f"  Erreurs telechargement/lecture  : {download_errors}\n")
    _log_source_result("BVMT", kpi_values_saved, documents_with_kpi, download_errors)

    return {
        "documents_with_kpi": documents_with_kpi,
        "kpi_values_saved": kpi_values_saved,
        "download_errors": download_errors,
    }


def _run_bvmt_bulletin(conn, already_done=None):
    """Pipeline separe pour les bulletins officiels de la cote BVMT
    (documents sectoriels, cmf_id NULL, un par annee, nom_pdf de la forme
    "bulletin_{annee}.pdf" -> voir scraping.bvmt_scraper.sync_market_data) :
    extrait "Cours de l'action - {code}" pour chaque societe cotee reconnue
    (voir bvmt_bulletin_kpi_extractor). Le MNEMO et la denomination BVMT de
    chaque societe, necessaires a cette reconnaissance, sont lus depuis les
    KPI deja enregistres sur son document de profil (cmf_id non NULL, meme
    source) plutot que re-scrapes ici.

    `already_done` : voir `_run_ftusa` — appliqué seulement aux bulletins
    (téléchargement + parsing), jamais à la recherche mnemo/dénomination
    (déjà une simple lecture DB, pas un coût à économiser)."""
    documents = list_all_documents(conn)
    company_docs = [doc for doc in documents if doc[1] == "BVMT" and doc[2] is not None]

    mnemo_to_code, name_to_code = {}, {}
    for document_id, _source_nom, code, _nom_entreprise, _nom_pdf, _annee, _lien in company_docs:
        kpis = get_kpi_values_for_document(conn, document_id)
        mnemo = kpis.get("Mnemo (BVMT)")
        if isinstance(mnemo, str):
            mnemo_to_code[mnemo] = code
        denomination = kpis.get("Denomination (BVMT)")
        if isinstance(denomination, str):
            name_to_code[_normalizer.clean(denomination)] = code

    bulletin_docs = [doc for doc in documents if doc[1] == "BVMT" and doc[2] is None and doc[4].startswith("bulletin_")]
    if already_done:
        bulletin_docs = [doc for doc in bulletin_docs if doc[0] not in already_done]
    print(f"\n===== EXTRACTION KPI BVMT - Bulletins : {len(bulletin_docs)} document(s) =====\n")

    kpi_values_saved = documents_with_kpi = download_errors = 0
    for document_id, _source_nom, _code, _nom_entreprise, _nom_pdf, annee, lien in bulletin_docs:
        if is_cancel_requested():
            print("[ANNULE] Extraction KPI BVMT bulletins interrompue par l'utilisateur.")
            break
        print(f"[STEP] BVMT bulletin {annee} : {lien}")
        try:
            response = _get_with_retries(lien, timeout=60)
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                cloture_by_code = extract_bulletin_cloture(pdf, mnemo_to_code, name_to_code)
        except Exception as exc:
            print(f"  [ERROR] Echec de telechargement/lecture : {exc}")
            download_errors += 1
            continue

        for code, value in cloture_by_code.items():
            save_kpi_value(
                conn, document_id, "BVMT - Bulletin officiel de la cote", f"Cours de l'action - {code}", valeur_nombre=value
            )
            kpi_values_saved += 1
        if cloture_by_code:
            documents_with_kpi += 1
        print(f"  [{'OK' if cloture_by_code else 'WARN'}] {len(cloture_by_code)} societe(s) trouvee(s)")

    print("\n===== RESUME EXTRACTION KPI BVMT - Bulletins =====")
    print(f"  Documents avec au moins 1 KPI   : {documents_with_kpi}")
    print(f"  Valeurs de KPI enregistrees      : {kpi_values_saved}")
    print(f"  Erreurs telechargement/lecture  : {download_errors}\n")
    _log_source_result("BVMT_BULLETIN", kpi_values_saved, documents_with_kpi, download_errors)

    return {
        "documents_with_kpi": documents_with_kpi,
        "kpi_values_saved": kpi_values_saved,
        "download_errors": download_errors,
    }


def _run_cga(conn, already_done=None):
    """Pipeline separe pour les documents de la source CGA (sectorielle,
    pas de societe associee dans `documents` : les compagnies apparaissent
    en tant que suffixe du nom de KPI, ex: "Nombre d'agences par assureur -
    STAR"). Contrairement aux autres extracteurs, le nombre et les noms des
    KPI varient d'un document a l'autre (une compagnie ou un gouvernorat
    absent d'une annee donnee ne genere simplement pas ce KPI-la) : pas de
    liste KPI_NAMES fixe, donc pas de rapport d'echecs Excel (un KPI
    "manquant" n'est pas necessairement une erreur ici).

    `already_done` : voir `_run_ftusa`."""
    documents = [doc for doc in list_all_documents(conn) if doc[1] == "CGA"]
    if already_done:
        documents = [doc for doc in documents if doc[0] not in already_done]
    print(f"\n===== EXTRACTION KPI CGA : {len(documents)} document(s) =====\n")

    kpi_values_saved = documents_with_kpi = download_errors = 0
    for document_id, _source_nom, _code, _nom_entreprise, nom_pdf, annee, lien in documents:
        if is_cancel_requested():
            print("[ANNULE] Extraction KPI CGA interrompue par l'utilisateur.")
            break
        print(f"[STEP] CGA {annee} : {lien}")
        try:
            response = _get_with_retries(lien, timeout=60)
            _save_sectoral_pdf("CGA", annee, response.content)
            with pdfplumber.open(io.BytesIO(response.content)) as pdf:
                kpis = extract_cga_kpis(pdf)
        except Exception as exc:
            print(f"  [ERROR] Echec de telechargement/lecture : {exc}")
            download_errors += 1
            continue

        found_count = 0
        for name, value in kpis.items():
            if value is not None:
                tableau = ("CGA - Annexe 1 - Structure du marche"
                           if name in ("Nombre d'assureurs", "Nombre d'assureurs Takaful", "Nombre d'assureurs Conventionnelle")
                           else "CGA - Annexe 2 - Distribution geographique des agents")
                save_kpi_value(conn, document_id, tableau, name, valeur_nombre=value)
                kpi_values_saved += 1
                found_count += 1
        if found_count > 0:
            documents_with_kpi += 1
        print(f"  [{'OK' if found_count else 'WARN'}] {found_count} KPI enregistres en base")

    print("\n===== RESUME EXTRACTION KPI CGA =====")
    print(f"  Documents avec au moins 1 KPI   : {documents_with_kpi}")
    print(f"  Valeurs de KPI enregistrees      : {kpi_values_saved}")
    print(f"  Erreurs telechargement/lecture  : {download_errors}\n")
    _log_source_result("CGA", kpi_values_saved, documents_with_kpi, download_errors)

    return {
        "documents_with_kpi": documents_with_kpi,
        "kpi_values_saved": kpi_values_saved,
        "download_errors": download_errors,
    }


DOCUMENT_HARD_TIMEOUT_S = 45

# AL_AMANAH_TAKAFUL (états financiers en arabe, voir
# extraction/takaful_kpi_extractor.py::extract_al_amanah_takaful_kpis) a
# régulièrement besoin d'un repli OCR (extraction/arabic_ocr_extractor.py,
# tesseract sur plusieurs pages) largement plus long que le cas général —
# mesuré en conditions réelles à plusieurs minutes par document (2026-09-17),
# contre quelques secondes pour un document CMF francophone en texte natif.
# Avec le délai commun de 45s, 2022 et 2024 étaient abandonnés à tort avant
# la fin d'une extraction qui aurait réussi (2023, elle, a réussi dans ce
# même délai — la marge est trop juste pour être fiable). Délai propre,
# nettement plus généreux, pour cette seule société plutôt que de relâcher
# la borne commune (qui protège justement contre un vrai blocage pour les
# ~130 autres documents, en texte natif rapide).
DOCUMENT_HARD_TIMEOUT_ARABIC_S = 240


def _process_one_document(conn, code, annee, nom_pdf, lien):
    """Télécharge + extrait les KPI d'UN document (partie risquée de la
    boucle de `run()`, isolée pour pouvoir être bornée dans le temps —
    voir l'appel via un thread daemon ci-dessous). Ne renvoie jamais
    d'exception : le résultat porte soit les données extraites, soit
    l'erreur, pour laisser l'appelant décider (compteurs, rapport
    d'échecs) sans dupliquer cette logique ici."""
    try:
        response = _get_with_retries(lien, timeout=30)
        _save_cmf_pdf_local(code, nom_pdf, response.content)
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            kpis = _extract_all_kpis(pdf, company_code=code)
            missing = [name for name in KPI_NAMES if kpis.get(name) is None]
            cause = _classify_cause(pdf, code) if missing else None
            ecart = _check_balance(pdf, kpis)
            yoy_flags = check_yoy_consistency(conn, code, annee, kpis)
        return {"ok": True, "kpis": kpis, "missing": missing, "cause": cause, "ecart": ecart, "yoy_flags": yoy_flags}
    except Exception as exc:
        return {"ok": False, "error": exc}


def _process_one_document_with_watchdog(conn, code, annee, nom_pdf, lien, timeout=DOCUMENT_HARD_TIMEOUT_S):
    """Borne `_process_one_document` dans le temps — un document (OCR sur
    un scan abîmé, PDF anormalement lourd...) qui bloque indéfiniment ne
    doit jamais geler tout le pipeline derrière lui, même dans la passe
    "rapide" (voir run(years=...)) où le but explicite est un délai total
    maîtrisé. Thread `daemon=True` + `queue` (pas ThreadPoolExecutor,
    dont les threads internes NE sont PAS daemon — piège déjà rencontré
    et documenté dans pipelines/cmf_pipeline.py::_run_company_with_watchdog,
    même remède ici)."""
    result_q = queue.Queue(maxsize=1)

    def _target():
        result_q.put(_process_one_document(conn, code, annee, nom_pdf, lien))

    threading.Thread(target=_target, daemon=True).start()
    try:
        return result_q.get(timeout=timeout), False
    except queue.Empty:
        return {"ok": False, "error": TimeoutError(f"delai de {timeout}s depasse")}, True


def _tail_candidate_ids(conn, skip):
    """document_id des documents que les extracteurs sectoriels (FTUSA, BVMT
    PDF/bulletins, CGA) vont tenter dans CE passage — mêmes filtres que
    `_run_ftusa`/`_run_bvmt`/`_run_cga` ci-dessous ; sert à savoir, à la fin,
    lesquels ont été tentés pour rien (voir `_update_failure_memory`)."""
    ids = set()
    for doc in list_all_documents(conn):
        if doc[0] in skip:
            continue
        source, nom_pdf = doc[1], doc[4]
        if source in ("FTUSA", "CGA") or (source == "BVMT" and nom_pdf.lower().endswith(".pdf")):
            ids.add(doc[0])
    return ids


def _update_failure_memory(conn, attempted_ids):
    """Après un passage complet : un document tenté qui n'a toujours AUCUN KPI
    est noté en échec (essai +1, prochain essai repoussé) ; un document tenté
    qui a fini par donner des KPI est oublié. Voir schema.sql::documents_echecs."""
    after = get_document_ids_with_kpi(conn)
    record_document_failures(conn, sorted(i for i in attempted_ids if i not in after))
    clear_document_failures(conn, sorted(i for i in attempted_ids if i in after))


def run(force=False, years=None, respect_backoff=False):
    """Lance l'extraction KPI pour tous les documents CMF déjà en base, puis
    les sous-pipelines FTUSA/BVMT/BVMT-bulletin/CGA et la modélisation.

    `force=False` (défaut, 2026-09-09 — retour utilisateur direct : la
    collecte re-téléchargeait et re-parsait les ~223 documents CMF déjà
    extraits À CHAQUE clic, plusieurs dizaines de minutes pour, la plupart
    du temps, 0 changement réel) : les documents ayant déjà AU MOINS une
    valeur de KPI enregistrée sont sautés — seuls les documents réellement
    NOUVEAUX (venant d'être synchronisés par `cmf_pipeline.sync_documents`)
    ou jamais traités avec succès sont (re)traités. `force=True` retraite
    tout l'historique sans exception (utile après une amélioration d'un
    extracteur, pour rattraper d'anciens échecs sur du contenu inchangé) —
    à déclencher explicitement, jamais par défaut.

    `years` (ensemble d'années, optionnel) : restreint aux documents de
    ces exercices seulement — utilisé par cmf_pipeline.main() pour une
    PREMIÈRE passe rapide (année la plus récente uniquement, ~24
    documents au lieu de ~223) avant de traiter tout l'historique en
    tâche de fond, pour que la plateforme devienne utilisable en
    quelques minutes plutôt qu'après le traitement complet (retour
    utilisateur direct 2026-09-16 : "le user n'attend que 5 minutes")."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ensure_database()
    conn = get_connection()
    init_schema(conn)
    already_done = set() if force else get_document_ids_with_kpi(conn)
    if already_done:
        _backfill_missing_local_pdfs(conn, already_done)
    # `respect_backoff=True` (rattrapage au démarrage, voir api/routes/
    # gestion_donnees.py::run_tracked_catchup) : les documents déjà tentés en
    # vain et dont le prochain essai n'est pas encore dû sont sautés — sinon
    # chaque ouverture de la plateforme retéléchargeait les mêmes PDF sans
    # KPI (retour du responsable pro, 2026-09-21). Une collecte lancée à la
    # main garde le comportement par défaut : tout est retenté.
    in_backoff = get_documents_in_backoff(conn) if (respect_backoff and not force) else set()
    if in_backoff:
        print(f"[INFO] {len(in_backoff)} document(s) en attente d'un nouvel essai (échecs précédents) : ignorés pour l'instant.")
    skip = already_done | in_backoff
    documents = [
        doc for doc in list_all_documents(conn)
        if doc[1] == "CMF" and doc[0] not in skip and (years is None or doc[5] in years)
    ]
    attempted_ids = {doc[0] for doc in documents} | _tail_candidate_ids(conn, skip)

    print(f"\n===== EXTRACTION KPI : {len(documents)} document(s) a traiter "
          f"({len(already_done)} deja extraits, sautes), {len(KPI_NAMES)} KPI =====\n")

    failures = {name: [] for name in KPI_NAMES}
    kpi_values_saved = documents_with_kpi = download_errors = balance_mismatches = yoy_anomalies = 0

    from pipelines.progress import enter_phase_if_planned, reset_progress, set_progress
    enter_phase_if_planned("extraction_kpi")
    reset_progress(total=len(documents))

    for idx, (document_id, _source_nom, code, nom_entreprise, nom_pdf, annee, lien) in enumerate(documents):
        set_progress(idx, detail=f"{code} {annee}")
        if is_cancel_requested():
            print("[ANNULE] Extraction KPI CMF interrompue par l'utilisateur.")
            break
        print(f"[STEP] {code} {annee} : {lien}")
        doc_timeout = DOCUMENT_HARD_TIMEOUT_ARABIC_S if code == "AL_AMANAH_TAKAFUL" else DOCUMENT_HARD_TIMEOUT_S
        result, timed_out = _process_one_document_with_watchdog(conn, code, annee, nom_pdf, lien, timeout=doc_timeout)
        if timed_out:
            print(f"  [ERROR] {code} {annee} : delai de {doc_timeout}s depasse, document saute.")
        if not result["ok"]:
            exc = result["error"]
            print(f"  [ERROR] Echec de telechargement/lecture : {exc}")
            download_errors += 1
            for name in KPI_NAMES:
                failures[name].append((code, nom_entreprise, annee, nom_pdf, lien, f"Erreur : {exc}"))
            continue

        kpis, missing, cause = result["kpis"], result["missing"], result["cause"]
        ecart = result["ecart"]
        if ecart:
            print(f"  [WARN] Desequilibre Bilan : Total actif != Capitaux propres + Passif (ecart={ecart:,.3f} TND)")
            details = {"total_actif": kpis.get("Total actif"), "ecart": round(ecart, 3)}
            log_json(_logger, "balance_check_failed", company=code, annee=annee, **details)
            save_anomaly(
                conn, source="extraction_balance", gravite="erreur",
                code=code, annee=annee, kpi="Total actif", details=details,
            )
            balance_mismatches += 1

        for flag in result["yoy_flags"]:
            print(
                f"  [WARN] Variation YoY suspecte {flag['kpi']} : "
                f"{flag['valeur_precedente']:,.0f} ({flag['annee_precedente']}) -> "
                f"{flag['valeur_actuelle']:,.0f} ({annee}) [{flag['variation_pct']:+.1f}%]"
            )
            log_json(_logger, "yoy_anomaly", company=code, annee=annee, **flag)
            save_anomaly(
                conn, source="extraction_yoy", gravite="avertissement",
                code=code, annee=annee, kpi=flag["kpi"], details=flag,
            )
            yoy_anomalies += 1

        for name in missing:
            failures[name].append((code, nom_entreprise, annee, nom_pdf, lien, cause))

        found_count = len(KPI_NAMES) - len(missing)
        if found_count > 0:
            for name in KPI_NAMES:
                value = kpis.get(name)
                if value is not None:
                    if isinstance(value, str):
                        save_kpi_value(conn, document_id, KPI_TABLE_LABEL[name], name, valeur_texte=value)
                    else:
                        save_kpi_value(conn, document_id, KPI_TABLE_LABEL[name], name, valeur_nombre=value)
                    kpi_values_saved += 1
            documents_with_kpi += 1
            print(f"  [OK] {found_count}/{len(KPI_NAMES)} KPI enregistres en base")
        else:
            print(f"  [WARN] Aucun KPI trouve ({cause})")

    # Rien de traité (rattrapage à vide) : ne pas écraser le dernier rapport
    # d'échecs d'une vraie collecte par un classeur vide.
    if documents:
        _write_failure_report(failures)
    set_progress(len(documents), detail="sources sectorielles et KPI calculés…")

    print("\n===== RESUME EXTRACTION KPI =====")
    print(f"  Documents avec au moins 1 KPI   : {documents_with_kpi}")
    print(f"  Valeurs de KPI enregistrees      : {kpi_values_saved}")
    print(f"  Erreurs telechargement/lecture  : {download_errors}")
    print(f"  Desequilibres Bilan (Actif!=Passif) : {balance_mismatches}")
    print(f"  Anomalies annee sur annee (YoY)  : {yoy_anomalies}")
    for name in KPI_NAMES:
        print(f"  Echecs {name:60s} : {len(failures[name])}")
    print(f"  Rapport d'echecs                : {FAILURE_REPORT_PATH}\n")
    _log_source_result(
        "CMF", kpi_values_saved, documents_with_kpi, download_errors,
        nb_documents=len(documents), nb_failures_total=sum(len(v) for v in failures.values()),
        balance_mismatches=balance_mismatches, yoy_anomalies=yoy_anomalies,
    )

    ftusa_stats = _run_ftusa(conn, already_done=skip)
    bvmt_stats = _run_bvmt(conn, already_done=skip)
    bvmt_bulletin_stats = _run_bvmt_bulletin(conn, already_done=skip)
    cga_stats = _run_cga(conn, already_done=skip)

    # Mémoire des échecs : seulement si le passage est allé au bout (une
    # annulation laisserait croire que des documents jamais tentés ont échoué).
    if not is_cancel_requested():
        _update_failure_memory(conn, attempted_ids)

    print("\n===== MODELISATION : KPI CALCULES =====\n")
    calculated_stats = calculated_kpi_extractor.run(conn)
    calculated_total_saved = sum(
        stats.get("kpi_values_saved", 0) for stats in calculated_stats.values()
    )
    log_json(_logger, "modelisation_done", **{
        family: stats.get("kpi_values_saved", 0) for family, stats in calculated_stats.items()
    })

    conn.close()

    return {
        "documents_with_kpi": documents_with_kpi,
        "kpi_values_saved": kpi_values_saved,
        "download_errors": download_errors,
        "balance_mismatches": balance_mismatches,
        "yoy_anomalies": yoy_anomalies,
        "failures": failures,
        "ftusa": ftusa_stats,
        "bvmt": bvmt_stats,
        "bvmt_bulletin": bvmt_bulletin_stats,
        "cga": cga_stats,
        "calculated": calculated_stats,
        "calculated_kpi_values_saved": calculated_total_saved,
    }


if __name__ == "__main__":
    run()
