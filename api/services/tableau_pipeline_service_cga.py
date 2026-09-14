"""Orchestration de la pipeline complète CGA "Distribution géographique des
agents d'assurance" (Annexe 2) — même schéma que
tableau_pipeline_service_ftusa.py : un seul document par ANNÉE (source
CGA, sans société associée au document lui-même — voir
extraction/cga_full_extractor.py), stocké sous `tableau_cellules`
(`tableau='cga_agences'`), chaque LIGNE étant une compagnie différente
(+ "TOTAL" marché) plutôt qu'un poste comptable fixe.

Étape volontairement limitée à l'extraction + le stockage (comme FTUSA,
voir CAS_PARTICULIERS_CGA.md) : Correction manuelle ne gère pour
l'instant que les documents CMF société+année. Aucune règle de validation
métier écrite (validations = liste vide)."""

import os

import pdfplumber

from database.repository import get_connection, save_tableau_result
from extraction.cga_full_extractor import extract_cga_agences_full_grid

TABLEAU_KEY = "cga_agences"

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cga",
)


def _cga_documents(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.annee
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            WHERE s.nom = 'CGA'
            ORDER BY d.annee
            """
        )
        return cur.fetchall()


def process_one_document(conn, document_id, annee):
    """Traite un document CGA (une année) : extraction + stockage.
    Renvoie le statut ('ok' | 'page_introuvable' | 'pdf_absent')."""
    path = os.path.join(DATA_DIR, f"CGA_{annee}.pdf")
    if not os.path.isfile(path):
        return "pdf_absent"
    with pdfplumber.open(path) as pdf:
        result = extract_cga_agences_full_grid(pdf)
    if result is None:
        return "page_introuvable"
    save_tableau_result(conn, document_id, TABLEAU_KEY, {**result, "validations": []})
    return "ok"


def process_all():
    """Traite tous les documents CGA disponibles. Renvoie un résumé
    {"total", "ok", "page_introuvable", "pdf_absent", "erreur"}."""
    conn = get_connection()
    try:
        docs = _cga_documents(conn)
        summary = {"total": len(docs), "ok": 0, "page_introuvable": 0, "pdf_absent": 0, "erreur": 0}
        for document_id, annee in docs:
            try:
                statut = process_one_document(conn, document_id, annee)
                summary[statut] += 1
            except Exception as exc:
                summary["erreur"] += 1
                print(f"[tableau_pipeline_service_cga] {annee} : {exc}")
        return summary
    finally:
        conn.close()
