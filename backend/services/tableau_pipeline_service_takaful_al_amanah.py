"""Pipeline Takaful pour AL_AMANAH_TAKAFUL — PDFs en arabe.

Extrait les 5 tableaux Takaful (Annexes 3/4/5.1/14/15) depuis les PDFs
arabes d'AL_AMANAH_TAKAFUL et les stocke sous les mêmes clés que les
extracteurs français (takaful_surplus_familial, etc.), avec des libellés
en arabe identiques au PDF original.

Séparé des services français (tableau_pipeline_service_takaful_surplus,
_ventilation, _resultat) pour ne pas polluer leur logique de détection."""

import os

from backend.database.repository import get_connection, save_tableau_result, save_cached_tableau_page
from backend.extraction.al_amanah_takaful_extractor import process_al_amanah_takaful
from backend.services.data_management import local_pdf_path

AL_AMANAH_CODE = "AL_AMANAH_TAKAFUL"

TABLEAU_KEYS = [
    "takaful_surplus_familial",
    "takaful_surplus_general",
    "takaful_resultat_entreprise",
    "takaful_ventilation_familial",
    "takaful_ventilation_general",
]


def _al_amanah_documents(conn, annees=None):
    """Retourne (document_id, code, nom_pdf) pour AL_AMANAH_TAKAFUL."""
    query = """
        SELECT d.id, c.code, d.nom_pdf
        FROM documents_pdf d
        JOIN sources s ON s.id = d.source_id
        JOIN societes c ON c.id = d.societe_id
        WHERE s.nom = 'CMF' AND c.code = %s
    """
    params = [AL_AMANAH_CODE]
    if annees:
        query += f" AND d.annee IN ({','.join(['%s'] * len(annees))})"
        params.extend(annees)
    query += " ORDER BY d.annee"
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def process_one_document(conn, document_id, code, nom_pdf):
    """Extrait et stocke les 5 tableaux pour un document. Renvoie le statut :
    'ok' (≥1 tableau trouvé) | 'page_introuvable' | 'pdf_absent'."""
    pdf_path = local_pdf_path("CMF", code, nom_pdf)
    if not pdf_path or not os.path.isfile(pdf_path):
        return "pdf_absent"

    trouve = 0
    for cle in TABLEAU_KEYS:
        try:
            result = process_al_amanah_takaful(pdf_path, cle)
        except Exception as exc:
            print(f"[al_amanah_takaful] {cle} {nom_pdf} : {exc}")
            continue
        if result is None:
            continue
        trouve += 1
        save_tableau_result(conn, document_id, cle, result)
        if result.get("page"):
            save_cached_tableau_page(conn, document_id, cle, result["page"])

    return "ok" if trouve > 0 else "page_introuvable"


def process_all(annees=None, progress_callback=None):
    """Traite tous les documents AL_AMANAH_TAKAFUL. Renvoie un résumé."""
    conn = get_connection()
    try:
        docs = _al_amanah_documents(conn, annees)
        summary = {"total": len(docs), "ok": 0, "page_introuvable": 0,
                   "pdf_absent": 0, "erreur": 0}
        for i, (document_id, code, nom_pdf) in enumerate(docs, 1):
            try:
                statut = process_one_document(conn, document_id, code, nom_pdf)
                summary[statut] += 1
            except Exception as exc:
                summary["erreur"] += 1
                print(f"[al_amanah_takaful] {code} {nom_pdf} : {exc}")
            if progress_callback:
                progress_callback(i, len(docs))
        return summary
    finally:
        conn.close()
