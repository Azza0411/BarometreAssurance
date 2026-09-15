"""Orchestration de la pipeline complète Takaful Annexes 3/4 ("État de
Surplus ou Déficit du fonds Takaful Familial/Général") — même schéma que
`tableau_pipeline_service_bilan.py` : extraction + stockage
(tableau_cellules), Familial et Général sous deux clés séparées (comme
Actif/Passif pour le Bilan, pour les mêmes raisons — tableaux distincts du
PDF source, pages et totaux propres).

Restreint aux sociétés Takaful dont le PDF est en français : AT_TAKAFULIA
et ZITOUNA_TAKAFUL. AL_AMANAH_TAKAFUL publie ses états en arabe — hors
périmètre de cet extracteur texte français, comme déjà décidé pour le
Bilan Takaful (voir extraction/CAS_PARTICULIERS_BILAN_FULL_TABLE.md)."""

import os

from database.repository import get_connection, save_tableau_result, save_cached_tableau_page
from extraction.takaful_surplus_full_extractor import process_takaful_surplus
from api.services.data_management import local_pdf_path

TABLEAU_KEY_FAMILIAL = "takaful_surplus_familial"
TABLEAU_KEY_GENERAL = "takaful_surplus_general"

TAKAFUL_FR_COMPANIES = ("AT_TAKAFULIA", "ZITOUNA_TAKAFUL")


def _takaful_documents(conn, codes=None, annees=None):
    codes = [c for c in (codes or TAKAFUL_FR_COMPANIES) if c in TAKAFUL_FR_COMPANIES] or list(TAKAFUL_FR_COMPANIES)
    query = """
        SELECT d.id, c.code, d.nom_pdf
        FROM documents d
        JOIN sources s ON s.id = d.source_id
        JOIN societes c ON c.id = d.cmf_id
        WHERE s.nom = 'CMF' AND c.code IN (%s)
    """ % ",".join(["%s"] * len(codes))
    params = list(codes)
    if annees:
        query += f" AND d.annee IN ({','.join(['%s'] * len(annees))})"
        params.extend(annees)
    query += " ORDER BY c.code, d.annee"
    with conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def process_one_document(conn, document_id, code, nom_pdf):
    """Traite un document : extraction + stockage du Familial ET du
    Général SÉPARÉMENT (chacun sous sa propre clé). Renvoie le statut ('ok'
    si les deux côtés sont trouvés | 'partiel' si un seul | 'page_introuvable'
    si aucun | 'pdf_absent')."""
    pdf_path = local_pdf_path("CMF", code, nom_pdf)
    if not pdf_path or not os.path.isfile(pdf_path):
        return "pdf_absent"

    trouve = 0
    for cle, side in ((TABLEAU_KEY_FAMILIAL, "familial"), (TABLEAU_KEY_GENERAL, "general")):
        result = process_takaful_surplus(pdf_path, side)
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
    """Même contrat que `tableau_pipeline_service_bilan.process_all`."""
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
                print(f"[tableau_pipeline_service_takaful_surplus] {code} {nom_pdf} : {exc}")
            if progress_callback:
                progress_callback(i, len(docs))
        return summary
    finally:
        conn.close()
