# -*- coding: utf-8 -*-
"""Tableaux Annexe 12 (Résultat technique par catégorie d'assurance Vie)
saisis À LA MAIN et vérifiés — même contrat que extraction/annexe13_verified.py
(voir son en-tête pour le principe général), pour les documents dont la
page est un SCAN que l'OCR ne lit pas de façon fiable, ou dont l'extraction
automatique (camelot) échoue de façon récurrente.

`process_one_document` (api/services/tableau_pipeline_service_annexe12.py)
consulte ce module AVANT de tenter l'extraction automatique : si le couple
(code, année) y figure, la grille vérifiée est stockée telle quelle
(normalisée exactement comme les autres — mêmes libellés canoniques de
ligne/colonne, même ordre, mêmes règles de validation), et l'extraction
automatique n'est pas tentée.

Pour ajouter une année vérifiée : compléter `VERIFIED` avec la même
structure (valeurs telles qu'imprimées dans le PDF, `None` = tiret « néant »
ou cellule vide)."""

from extraction.annexe12_pipeline import (
    CANONICAL_ROWS_VIE as _R_VIE,
    normalize_table_vie,
    validate_table_vie,
)


def _grid(cols, page, matrix, rows=_R_VIE):
    """matrix : liste de lignes (alignée sur `rows`), chacune = liste de
    valeurs alignée sur `cols` (None = néant/vide). -> grille {"colonnes",
    "lignes"} (cellules None omises), prête pour `normalize_table_vie`."""
    lignes = {}
    for label, vals in zip(rows, matrix):
        cells = {c: v for c, v in zip(cols, vals) if v is not None}
        if cells:
            lignes[label] = cells
    return {"page": page, "colonnes": list(cols), "lignes": lignes}


VERIFIED = {
}


def has(code, annee):
    return (code, int(annee)) in VERIFIED


def build_result(code, annee):
    """Renvoie le dict résultat au MÊME contrat que
    `annexe12_pipeline.process_annexe12` (page, colonnes, lignes,
    non_reconnues, colonnes_non_reconnues, validations) — normalisé et
    validé exactement comme la voie d'extraction normale, pour un stockage
    homogène."""
    grid = VERIFIED[(code, int(annee))]
    normalized = normalize_table_vie({"colonnes": grid["colonnes"], "lignes": grid["lignes"]})
    validations = validate_table_vie(normalized["lignes"], normalized["colonnes"])
    return {
        "page": grid["page"],
        "colonnes": normalized["colonnes"],
        "lignes": normalized["lignes"],
        "non_reconnues": normalized["non_reconnues"],
        "colonnes_non_reconnues": normalized["colonnes_non_reconnues"],
        "validations": validations,
    }
