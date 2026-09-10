"""Orchestration de la pipeline complète par annexe (Phase 1, 2026-09-08) :
traite les documents CMF (extraction + normalisation + validation, voir
extraction/annexe13_pipeline.py) et stocke le résultat en base
(tableau_cellules / tableau_validations, database/schema.sql).

Séparé de data_management.py (qui reste responsable de la liste des
documents / l'export Excel) pour garder ce fichier concentré sur UNE
responsabilité : faire tourner la pipeline et écrire son résultat. Suit le
même schéma que gestion_donnees.py::_run_pipeline_background pour la
collecte — un traitement potentiellement long ne doit jamais tourner de
façon synchrone dans une requête HTTP."""

import os

from database.repository import get_connection, save_tableau_result
from extraction.annexe13_kpi_extractor import _is_target_page, RACCORDEMENT_RE, KPI_PATTERNS
from extraction.annexe13_pipeline import process_annexe13, ANNEXE13_NON_VIE_EXCLUSIONS
from extraction.full_table_extractor import relaxed_is_annexe13_page
from extraction import annexe13_verified
from api.services.data_management import local_pdf_path

TABLEAU_KEY = "annexe13"


def _annee_de(nom_pdf):
    """Année (int) déduite du nom de fichier `CODE_AAAA.pdf`, ou None."""
    base = os.path.splitext(os.path.basename(nom_pdf or ""))[0]
    part = base.rsplit("_", 1)[-1]
    return int(part) if part.isdigit() and len(part) == 4 else None


def _cmf_documents(conn, codes=None, annees=None):
    """(document_id, code, nom_pdf) pour les documents CMF correspondant aux
    filtres — mêmes filtres optionnels (codes/années) que l'export flexible.
    Exclut toujours les sociétés hors périmètre Non-Vie
    (`ANNEXE13_NON_VIE_EXCLUSIONS` — Vie exclusivement/Takaful) : tenter
    l'extraction pour elles ne peut au mieux rien trouver (page absente) et
    au pire tomber par accident sur une page de raccordement VIE qui passe
    le contrôle de vraisemblance (constaté sur ATTIJARI — voir CAS_
    PARTICULIERS_FULL_TABLE.md) et pollue la base avec des cellules
    mal-étiquetées "Non-Vie" alors qu'elles sont Vie."""
    query = """
        SELECT d.id, c.code, d.nom_pdf
        FROM documents d
        JOIN sources s ON s.id = d.source_id
        JOIN societes c ON c.id = d.cmf_id
        WHERE s.nom = 'CMF'
    """
    params = []
    if ANNEXE13_NON_VIE_EXCLUSIONS:
        query += f" AND c.code NOT IN ({','.join(['%s'] * len(ANNEXE13_NON_VIE_EXCLUSIONS))})"
        params.extend(sorted(ANNEXE13_NON_VIE_EXCLUSIONS))
    if codes:
        query += f" AND c.code IN ({','.join(['%s'] * len(codes))})"
        params.extend(codes)
    if annees:
        query += f" AND d.annee IN ({','.join(['%s'] * len(annees))})"
        params.extend(annees)
    query += " ORDER BY c.code, d.annee"
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def process_one_document(conn, document_id, code, nom_pdf):
    """Traite un document : extraction + normalisation + validation, puis
    stockage. Renvoie le statut ('ok' | 'ok_verifie' | 'page_introuvable' |
    'pdf_absent').

    Court-circuit : pour les documents dont la page Annexe 13 est un SCAN que
    l'OCR ne lit pas de façon fiable (AMI 2019/2020/2023, COTUNACE 2017/2019/
    2023), une grille saisie à la main et recoupée par les identités
    comptables est fournie par `extraction/annexe13_verified.py`. On la
    stocke telle quelle — normalisée et validée EXACTEMENT comme la voie
    d'extraction normale — et on ne tente pas l'OCR : une revalidation
    ultérieure ne peut donc jamais écraser ces valeurs par du bruit OCR."""
    annee = _annee_de(nom_pdf)
    if annee is not None and annexe13_verified.has(code, annee):
        save_tableau_result(conn, document_id, TABLEAU_KEY,
                            annexe13_verified.build_result(code, annee))
        return "ok_verifie"

    pdf_path = local_pdf_path("CMF", code, nom_pdf)
    if not pdf_path or not os.path.isfile(pdf_path):
        return "pdf_absent"
    result = process_annexe13(
        pdf_path, _is_target_page, KPI_PATTERNS, RACCORDEMENT_RE, relaxed_is_annexe13_page,
    )
    if result is None:
        return "page_introuvable"
    save_tableau_result(conn, document_id, TABLEAU_KEY, result)
    return "ok"


def process_all(codes=None, annees=None, progress_callback=None):
    """Traite tous les documents CMF correspondant aux filtres (par défaut :
    tous). `progress_callback(done, total)` est appelé après chaque document
    si fourni — permet à l'appelant (route de fond) d'exposer une
    progression interrogeable par polling. Renvoie un résumé
    {"total", "ok", "page_introuvable", "pdf_absent", "erreur"}."""
    conn = get_connection()
    try:
        docs = _cmf_documents(conn, codes, annees)
        summary = {"total": len(docs), "ok": 0, "ok_verifie": 0,
                   "page_introuvable": 0, "pdf_absent": 0, "erreur": 0}
        for i, (document_id, code, nom_pdf) in enumerate(docs, 1):
            try:
                statut = process_one_document(conn, document_id, code, nom_pdf)
                summary[statut] += 1
            except Exception as exc:
                summary["erreur"] += 1
                print(f"[tableau_pipeline_service] {code} {nom_pdf} : {exc}")
            if progress_callback:
                progress_callback(i, len(docs))
        return summary
    finally:
        conn.close()
