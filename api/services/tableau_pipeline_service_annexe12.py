"""Orchestration de la pipeline complète Annexe 12 (Résultat technique par
catégorie d'assurance Vie) — pendant Vie de tableau_pipeline_service.py
(Annexe 13 Non-Vie), dont ce module reprend exactement le même schéma
(localisation + extraction + normalisation + validation, voir
extraction/annexe12_pipeline.py, puis stockage en base sous une clé de
tableau distincte "annexe12" — même table `tableau_cellules` /
`tableau_validations`, voir database/schema.sql).

Fichier SÉPARÉ de tableau_pipeline_service.py (plutôt qu'un paramètre
`tableau` sur ses fonctions) pour ne prendre AUCUN risque de régression sur
la route existante (api/routes/gestion_donnees.py) qui l'appelle déjà en
production pour l'Annexe 13."""

import os

from database.repository import get_connection, save_tableau_result
from extraction.annexe12_kpi_extractor import _is_target_page, _RACCORDEMENT_RE, KPI_PATTERNS
from extraction.annexe12_pipeline import process_annexe12, ANNEXE12_VIE_EXCLUSIONS
from extraction.full_table_extractor import relaxed_is_annexe12_page
from extraction import annexe12_verified
from api.services.data_management import local_pdf_path

TABLEAU_KEY = "annexe12"


def _annee_de(nom_pdf):
    """Année (int) déduite du nom de fichier `CODE_AAAA.pdf`, ou None."""
    base = os.path.splitext(os.path.basename(nom_pdf or ""))[0]
    part = base.rsplit("_", 1)[-1]
    return int(part) if part.isdigit() and len(part) == 4 else None


def _cmf_documents(conn, codes=None, annees=None):
    """(document_id, code, nom_pdf) pour les documents CMF correspondant aux
    filtres — même schéma que tableau_pipeline_service._cmf_documents, mais
    exclusion Vie (`ANNEXE12_VIE_EXCLUSIONS`, uniquement Takaful à ce
    stade — voir son commentaire : contrairement à l'Annexe 13, aucune
    société n'est présumée hors périmètre Vie a priori)."""
    query = """
        SELECT d.id, c.code, d.nom_pdf
        FROM documents d
        JOIN sources s ON s.id = d.source_id
        JOIN societes c ON c.id = d.cmf_id
        WHERE s.nom = 'CMF'
    """
    params = []
    if ANNEXE12_VIE_EXCLUSIONS:
        query += f" AND c.code NOT IN ({','.join(['%s'] * len(ANNEXE12_VIE_EXCLUSIONS))})"
        params.extend(sorted(ANNEXE12_VIE_EXCLUSIONS))
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
    """Traite un document pour l'Annexe 12 : extraction + normalisation +
    validation, puis stockage. Renvoie le statut ('ok' | 'ok_verifie' |
    'page_introuvable' | 'pdf_absent'). Même court-circuit "saisie vérifiée"
    que tableau_pipeline_service.process_one_document (voir son
    docstring) — voir extraction/annexe12_verified.py."""
    annee = _annee_de(nom_pdf)
    if annee is not None and annexe12_verified.has(code, annee):
        save_tableau_result(conn, document_id, TABLEAU_KEY,
                            annexe12_verified.build_result(code, annee))
        return "ok_verifie"

    pdf_path = local_pdf_path("CMF", code, nom_pdf)
    if not pdf_path or not os.path.isfile(pdf_path):
        return "pdf_absent"
    result = process_annexe12(
        pdf_path, _is_target_page, KPI_PATTERNS, _RACCORDEMENT_RE, relaxed_is_annexe12_page,
    )
    if result is None:
        return "page_introuvable"
    save_tableau_result(conn, document_id, TABLEAU_KEY, result)
    return "ok"


def process_all(codes=None, annees=None, progress_callback=None):
    """Traite tous les documents CMF correspondant aux filtres (par défaut :
    tous). `progress_callback(done, total)` est appelé après chaque document
    si fourni. Renvoie un résumé {"total", "ok", "ok_verifie",
    "page_introuvable", "pdf_absent", "erreur"}."""
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
                print(f"[tableau_pipeline_service_annexe12] {code} {nom_pdf} : {exc}")
            if progress_callback:
                progress_callback(i, len(docs))
        return summary
    finally:
        conn.close()
