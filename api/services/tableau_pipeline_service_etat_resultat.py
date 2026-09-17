"""Orchestration de la pipeline complète État de résultat — même schéma
que `tableau_pipeline_service_bilan.py` (extraction + stockage en base
tableau_cellules/tableau_validations via `save_tableau_result`). Voir
`extraction/resultat_full_extractor.py::process_resultat` pour
l'extraction elle-même.

Contrairement à Annexe 13, aucune exclusion par société : l'État de
résultat concerne toutes les compagnies CMF (Vie et Non-Vie, chacune
avec sa propre variante de codes — voir resultat_full_extractor.py).
Pas encore de repli AL_AMANAH_TAKAFUL (arabe) : ce document publie ses
états en arabe pour ce tableau aussi, hors périmètre pour l'instant
(même limitation que les grilles Takaful Surplus/Ventilation, voir
CAS_PARTICULIERS_TAKAFUL_SURPLUS.md)."""

import os

from database.repository import save_tableau_result, save_cached_tableau_page
from extraction.resultat_full_extractor import process_resultat
from api.services.data_management import local_pdf_path

TABLEAU_KEY = "etat_resultat"


def _cmf_documents(conn, codes=None, annees=None):
    query = """
        SELECT d.id, c.code, d.nom_pdf
        FROM documents d
        JOIN sources s ON s.id = d.source_id
        JOIN societes c ON c.id = d.cmf_id
        WHERE s.nom = 'CMF' AND c.code != 'AL_AMANAH_TAKAFUL'
    """
    params = []
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
    """Traite un document : extraction + stockage. Renvoie le statut
    ('ok' | 'page_introuvable' | 'pdf_absent')."""
    pdf_path = local_pdf_path("CMF", code, nom_pdf)
    if not pdf_path or not os.path.isfile(pdf_path):
        return "pdf_absent"
    result = process_resultat(pdf_path)
    if result is None:
        return "page_introuvable"
    save_tableau_result(conn, document_id, TABLEAU_KEY, result)
    if result.get("page"):
        save_cached_tableau_page(conn, document_id, TABLEAU_KEY, result["page"])
    return "ok"


def process_all(codes=None, annees=None, progress_callback=None):
    """Traite tous les documents CMF correspondant aux filtres (par défaut :
    tous, hors AL_AMANAH_TAKAFUL — arabe, hors périmètre). Renvoie
    {"total", "ok", "page_introuvable", "pdf_absent", "erreur"}."""
    from database.repository import get_connection

    conn = get_connection()
    try:
        docs = _cmf_documents(conn, codes, annees)
        summary = {"total": len(docs), "ok": 0, "page_introuvable": 0, "pdf_absent": 0, "erreur": 0}
        for i, (document_id, code, nom_pdf) in enumerate(docs, 1):
            try:
                statut = process_one_document(conn, document_id, code, nom_pdf)
                summary[statut] += 1
            except Exception as exc:
                summary["erreur"] += 1
                print(f"[tableau_pipeline_service_etat_resultat] {code} {nom_pdf} : {exc}")
            if progress_callback:
                progress_callback(i, len(docs))
        return summary
    finally:
        conn.close()
