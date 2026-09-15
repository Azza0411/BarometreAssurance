"""Orchestration de la pipeline complète Takaful Annexe 5.1 ("État de
résultat de l'entreprise d'assurance Takaful et/ou Rétakaful") — même
schéma que `tableau_pipeline_service_takaful_surplus.py` (une seule clé
`tableau_cellules` ici, ce tableau n'a pas de distinction Familial/
Général : c'est le compte de résultat de l'OPÉRATEUR).

Restreint aux sociétés Takaful dont le PDF est en français : AT_TAKAFULIA
et ZITOUNA_TAKAFUL (AL_AMANAH_TAKAFUL hors périmètre, voir
extraction/CAS_PARTICULIERS_TAKAFUL_SURPLUS.md)."""

import os

from database.repository import get_connection, save_tableau_result, save_cached_tableau_page
from extraction.takaful_resultat_full_extractor import process_takaful_resultat
from api.services.data_management import local_pdf_path
from api.services.tableau_pipeline_service_takaful_surplus import TAKAFUL_FR_COMPANIES, _takaful_documents

TABLEAU_KEY = "takaful_resultat_entreprise"


def process_one_document(conn, document_id, code, nom_pdf):
    """Traite un document : extraction + stockage. Renvoie 'ok' | 'page_introuvable' | 'pdf_absent'."""
    pdf_path = local_pdf_path("CMF", code, nom_pdf)
    if not pdf_path or not os.path.isfile(pdf_path):
        return "pdf_absent"

    result = process_takaful_resultat(pdf_path)
    if result is None:
        return "page_introuvable"

    save_tableau_result(conn, document_id, TABLEAU_KEY, result)
    if result.get("page"):
        save_cached_tableau_page(conn, document_id, TABLEAU_KEY, result["page"])
    return "ok"


def process_all(codes=None, annees=None, progress_callback=None):
    """Même contrat que `tableau_pipeline_service_takaful_surplus.process_all`."""
    conn = get_connection()
    try:
        docs = _takaful_documents(conn, codes, annees)
        summary = {"total": len(docs), "ok": 0, "page_introuvable": 0, "pdf_absent": 0, "erreur": 0}
        for i, (document_id, code, nom_pdf) in enumerate(docs, 1):
            try:
                statut = process_one_document(conn, document_id, code, nom_pdf)
                summary[statut] += 1
            except Exception as exc:
                summary["erreur"] += 1
                print(f"[tableau_pipeline_service_takaful_resultat] {code} {nom_pdf} : {exc}")
            if progress_callback:
                progress_callback(i, len(docs))
        return summary
    finally:
        conn.close()
