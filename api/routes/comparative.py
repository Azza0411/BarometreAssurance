"""Routes /api/analyse-comparative et /api/classement-compagnies."""

from flask import Blueprint, jsonify
from database.repository import (
    get_connection, get_kpi_values_for_document, list_documents_by_source
)
from api.utils.formatters import PRIMES_UNIT_DIVISOR, round1, required_year_arg, kpis_by_year
from api.services.kpi_builder import build_company_row
from api.services.quality import PROBLEMATIC_CODES
from extraction.kpi_definitions import filter_reliable

bp = Blueprint("comparative", __name__)

# Une compagnie n'est retenue que si AU MOINS une de ces valeurs existe —
# sans ça, elle apparaîtrait dans le sélecteur sans une seule case
# exploitable derrière. Initialement restreint aux 4 indicateurs de primes/
# ratios techniques : ATTIJARI 2024 a un document CMF avec Résultat Net,
# Capitaux propres, Total actif et ROE/ROA correctement extraits (23 KPI au
# total), mais aucun des 4 KPI de primes — elle disparaissait donc
# entièrement du comparateur alors qu'elle a de vraies données de
# solvabilité/rentabilité à montrer (retour utilisateur du 2026-08-09).
_KEY_KPIS = {
    "Primes émises par assurance", "Ratio combiné (%)",
    "Ratio de frais de gestion (%)", "Part de marché (%)",
    "ROE (%)", "ROA (%)", "Total actif", "Capitaux propres",
}

# row_key (sortie de build_company_row) -> nom KPI affiché sur Qualité Data,
# pour appliquer le même filtre de plausibilité (filter_reliable) : sans ça,
# une valeur que Qualité Data flague "aberrante" pouvait quand même
# s'afficher normalement ici, sans aucune indication qu'elle est douteuse.
_ROW_KEY_TO_KPI = {
    "ratio_combine": "Ratio combiné (%)",
    "ratio_sp":      "Ratio de sinistralité (%)",
    "ratio_frais":   "Ratio de frais de gestion (%)",
    "pdm":           "Part de marché (%)",
    "roe":           "ROE (%)",
    "roa":           "ROA (%)",
    "dette_cp":      "Dettes/Capitaux propres (%)",
    "dette_actif":   "Dettes/Actif (%)",
    "actions_actif": "Actions/Actif (%)",
    "placements_cp": "Placements/Capitaux propres (%)",
}

# Réutilise la liste unique de quality.py (raison documentée par société)
# au lieu d'un doublon local — ce doublon existait mais n'était en fait
# jamais appliqué comme filtre ici (variable déclarée, jamais lue), ce qui
# laissait passer des valeurs connues comme non fiables (ex. Takaful) dans
# ce tableau de comparaison sans aucune indication pour l'utilisateur.
PROBLEMATIC_COMPANIES = set(PROBLEMATIC_CODES.keys())


@bp.route("/api/analyse-comparative")
def analyse_comparative():
    annee = required_year_arg()
    conn  = get_connection()
    try:
        ftusa_kpis  = kpis_by_year(conn, "FTUSA").get(annee, {})
        total_ftusa = ftusa_kpis.get("Total Primes émises")

        # Primes année précédente pour calcul croissance YoY
        primes_prev_year = {}
        for _doc_id_p, _cmf_id_p, code_p, doc_annee_p in list_documents_by_source(conn, "CMF"):
            if doc_annee_p != annee - 1 or not code_p:
                continue
            kpis_p  = get_kpi_values_for_document(conn, _doc_id_p)
            pnv_p   = kpis_p.get("Primes émises Non-Vie par assurance")
            pv_p    = kpis_p.get("Primes émises Vie par assurance")
            pr_p    = kpis_p.get("Primes émises par assurance")
            if pv_p and pv_p > 1_000 and pnv_p and pnv_p > 1_000:
                primes_prev_year[code_p] = pv_p + pnv_p
            elif pr_p and pr_p > 1_000:
                primes_prev_year[code_p] = pr_p

        result = {}
        for document_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF"):
            if doc_annee != annee or not code or code in PROBLEMATIC_COMPANIES:
                continue
            kpis = get_kpi_values_for_document(conn, document_id)
            if not any(kpis.get(k) is not None for k in _KEY_KPIS):
                continue

            row = build_company_row(kpis, primes_prev_year, total_ftusa, code)
            # Retirer les champs de diagnostic internes avant d'envoyer au frontend
            clean = {k: v for k, v in row.items() if not k.startswith("_")}
            # Cohérence avec Qualité Data : une valeur qu'elle flague aberrante
            # ne doit pas s'afficher normalement ici sans avertissement.
            for row_key, kpi_name in _ROW_KEY_TO_KPI.items():
                if row_key in clean:
                    clean[row_key] = filter_reliable(kpi_name, clean[row_key])
            result[code] = clean

        return jsonify(result)
    finally:
        conn.close()


@bp.route("/api/classement-compagnies")
def classement_compagnies():
    annee = required_year_arg()
    conn  = get_connection()
    try:
        rows = []
        for document_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF"):
            if doc_annee != annee or not code or code in PROBLEMATIC_COMPANIES:
                continue
            kpis      = get_kpi_values_for_document(conn, document_id)
            pdm       = filter_reliable("Part de marché (%)", kpis.get("Part de marché (%)"))
            if pdm is None:
                continue
            total_actif = kpis.get("Total actif")
            if total_actif is not None and total_actif < 10_000:
                total_actif = None
            total_actif = filter_reliable("Total actif", total_actif)
            rows.append({"entreprise": code, "pdm_pct": round1(pdm), "total_actif": total_actif})
        rows.sort(key=lambda r: r["pdm_pct"], reverse=True)
        return jsonify(rows)
    finally:
        conn.close()
