"""Orchestration de la pipeline complète FTUSA "Compte d'exploitation par
branche & par entreprise" — même finalité que
tableau_pipeline_service_bilan.py (extraction pleine grille + stockage
tableau_cellules), mais pour une source SANS société associée : un seul
document par ANNÉE, agrégé pour le marché entier (voir
extraction/ftusa_full_extractor.py et
extraction/kpi_extraction_pipeline.py::_run_ftusa pour le contexte).

Étape volontairement limitée à l'extraction + le stockage (voir
CAS_PARTICULIERS_FTUSA.md) : la page Correction manuelle ne gère pour
l'instant que les documents CMF (triplet société/année/tableau) — brancher
ce tableau sans société y est un chantier séparé, pas entrepris ici.
Aucune règle de validation métier encore écrite pour ce tableau (pas de
formule d'identité comptable établie côté FTUSA) : `validations` reste une
liste vide."""

import os

import pdfplumber

from database.repository import get_connection, save_tableau_result
from extraction.ftusa_full_extractor import extract_ftusa_full_grid

TABLEAU_KEY = "ftusa_branche"

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "ftusa",
)


def _ftusa_documents(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.annee
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            WHERE s.nom = 'FTUSA'
            ORDER BY d.annee
            """
        )
        return cur.fetchall()


def process_one_document(conn, document_id, annee):
    """Traite un document FTUSA (une année) : extraction + stockage.
    Renvoie le statut ('ok' | 'page_introuvable' | 'pdf_absent')."""
    path = os.path.join(DATA_DIR, f"FTUSA_{annee}.pdf")
    if not os.path.isfile(path):
        return "pdf_absent"
    with pdfplumber.open(path) as pdf:
        result = extract_ftusa_full_grid(pdf)
    if result is None:
        return "page_introuvable"
    save_tableau_result(conn, document_id, TABLEAU_KEY, {**result, "validations": []})
    return "ok"


def process_all():
    """Traite tous les documents FTUSA disponibles. Renvoie un résumé
    {"total", "ok", "page_introuvable", "pdf_absent", "erreur"}."""
    conn = get_connection()
    try:
        docs = _ftusa_documents(conn)
        summary = {"total": len(docs), "ok": 0, "page_introuvable": 0, "pdf_absent": 0, "erreur": 0}
        for document_id, annee in docs:
            try:
                statut = process_one_document(conn, document_id, annee)
                summary[statut] += 1
            except Exception as exc:
                summary["erreur"] += 1
                print(f"[tableau_pipeline_service_ftusa] {annee} : {exc}")
        return summary
    finally:
        conn.close()
