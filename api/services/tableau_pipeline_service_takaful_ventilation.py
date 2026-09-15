"""Orchestration de la pipeline complète Takaful Annexes 14/15
("Ventilation du Surplus ou déficit par catégorie d'assurance") — même
schéma que `tableau_pipeline_service_takaful_surplus.py` : Familial et
Général sous deux clés séparées (structures de colonnes différentes —
Prévoyance/Épargne côté Familial, branches d'assurance côté Général)."""

import os

from database.repository import get_connection, save_tableau_result, save_cached_tableau_page
from extraction.takaful_ventilation_full_extractor import process_takaful_ventilation
from api.services.data_management import local_pdf_path
from api.services.tableau_pipeline_service_takaful_surplus import _takaful_documents

TABLEAU_KEY_FAMILIAL = "takaful_ventilation_familial"
TABLEAU_KEY_GENERAL = "takaful_ventilation_general"


def process_one_document(conn, document_id, code, nom_pdf):
    """Traite un document : extraction + stockage du Familial ET du
    Général SÉPARÉMENT. Renvoie 'ok' (les deux) | 'partiel' (un seul) |
    'page_introuvable' (aucun) | 'pdf_absent'."""
    pdf_path = local_pdf_path("CMF", code, nom_pdf)
    if not pdf_path or not os.path.isfile(pdf_path):
        return "pdf_absent"

    trouve = 0
    for cle, side in ((TABLEAU_KEY_FAMILIAL, "familial"), (TABLEAU_KEY_GENERAL, "general")):
        result = process_takaful_ventilation(pdf_path, side)
        if result is None:
            continue
        trouve += 1
        save_tableau_result(conn, document_id, cle, result)
        if result.get("page"):
            save_cached_tableau_page(conn, document_id, cle, result["page"])
    if trouve == 0:
        return "page_introuvable"
    return "ok" if trouve == 2 else "partiel"


def process_all(codes=None, annees=None, progress_callback=None):
    """Même contrat que `tableau_pipeline_service_takaful_surplus.process_all`."""
    conn = get_connection()
    try:
        docs = _takaful_documents(conn, codes, annees)
        summary = {"total": len(docs), "ok": 0, "partiel": 0, "page_introuvable": 0,
                   "pdf_absent": 0, "erreur": 0}
        for i, (document_id, code, nom_pdf) in enumerate(docs, 1):
            try:
                statut = process_one_document(conn, document_id, code, nom_pdf)
                summary[statut] += 1
            except Exception as exc:
                summary["erreur"] += 1
                print(f"[tableau_pipeline_service_takaful_ventilation] {code} {nom_pdf} : {exc}")
            if progress_callback:
                progress_callback(i, len(docs))
        return summary
    finally:
        conn.close()
