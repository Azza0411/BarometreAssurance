"""Utilitaires partagés entre toutes les routes : conversions, arrondis, helpers Flask."""

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from flask import request
from database.repository import get_kpi_values_for_document, list_documents_by_source

PRIMES_UNIT_DIVISOR = 1_000_000  # FTUSA stocke les primes en TND brut ; le frontend attend des MDT.


def round1(value):
    return round(value, 1) if value is not None else None


def growth_pct(current, previous):
    if current is None or not previous:
        return None
    return (current - previous) / previous * 100


def required_year_arg():
    raw = request.args.get("annee")
    if raw is None:
        raise ValueError("Le paramètre 'annee' est requis")
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Le paramètre 'annee' doit être un entier, reçu : {raw!r}")


def kpis_by_year(conn, source_nom):
    """{annee: {kpi: valeur}} pour tous les documents sectoriels d'une source (FTUSA, CGA, INS)."""
    result = {}
    for document_id, _cmf_id, _code, annee in list_documents_by_source(conn, source_nom):
        result[annee] = get_kpi_values_for_document(conn, document_id)
    return result
