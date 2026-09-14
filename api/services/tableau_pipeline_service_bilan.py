"""Orchestration de la pipeline complète Bilan Actif/Passif — même schéma
que `tableau_pipeline_service.py` (Annexe 13) : extraction + validation
(voir extraction/bilan_full_extractor.py::process_bilan) puis stockage en
base (tableau_cellules/tableau_validations). Fichier séparé (comme pour
Annexe 12) pour garder chaque pipeline concentrée sur UNE responsabilité.

Actif et Passif sont deux tableaux DISTINCTS du PDF source (pas une seule
grille fusionnée) : stockés sous deux clés séparées, TABLEAU_KEY_ACTIF et
TABLEAU_KEY_PASSIF, chacune avec sa propre page repérée et ses propres
validations — voir process_bilan.

Contrairement à Annexe 13, aucune exclusion par société : le Bilan
concerne TOUTES les compagnies CMF (Vie, Non-Vie, Takaful confondues).
Pas encore de module `bilan_verified.py` (aucun document n'a encore
nécessité de saisie manuelle) — si besoin plus tard, même court-circuit
que `tableau_pipeline_service.process_one_document`."""

import os

from database.repository import get_connection, save_tableau_result, save_cached_tableau_page
from extraction.bilan_full_extractor import process_bilan
from api.services.data_management import local_pdf_path

TABLEAU_KEY_ACTIF = "bilan_actif"
TABLEAU_KEY_PASSIF = "bilan_passif"


def _cmf_documents(conn, codes=None, annees=None):
    query = """
        SELECT d.id, c.code, d.nom_pdf
        FROM documents d
        JOIN sources s ON s.id = d.source_id
        JOIN societes c ON c.id = d.cmf_id
        WHERE s.nom = 'CMF'
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
    """Traite un document : extraction + validation, puis stockage de
    l'Actif ET du Passif SÉPARÉMENT (chacun sous sa propre clé, voir
    module docstring). Renvoie le statut ('ok' si les deux côtés sont
    trouvés | 'partiel' si un seul | 'page_introuvable' si aucun |
    'pdf_absent')."""
    pdf_path = local_pdf_path("CMF", code, nom_pdf)
    if not pdf_path or not os.path.isfile(pdf_path):
        return "pdf_absent"
    result = process_bilan(pdf_path)
    if result is None:
        return "page_introuvable"

    trouve = 0
    for cle, cote in ((TABLEAU_KEY_ACTIF, result.get("actif")), (TABLEAU_KEY_PASSIF, result.get("passif"))):
        if cote is None:
            continue
        trouve += 1
        save_tableau_result(conn, document_id, cle, cote)
        if cote.get("page"):
            save_cached_tableau_page(conn, document_id, cle, cote["page"])
    return "ok" if trouve == 2 else "partiel"


def process_all(codes=None, annees=None, progress_callback=None):
    """Même contrat que `tableau_pipeline_service.process_all`."""
    conn = get_connection()
    try:
        docs = _cmf_documents(conn, codes, annees)
        summary = {"total": len(docs), "ok": 0, "partiel": 0, "page_introuvable": 0,
                   "pdf_absent": 0, "erreur": 0}
        for i, (document_id, code, nom_pdf) in enumerate(docs, 1):
            try:
                statut = process_one_document(conn, document_id, code, nom_pdf)
                summary[statut] += 1
            except Exception as exc:
                summary["erreur"] += 1
                print(f"[tableau_pipeline_service_bilan] {code} {nom_pdf} : {exc}")
            if progress_callback:
                progress_callback(i, len(docs))
        return summary
    finally:
        conn.close()
