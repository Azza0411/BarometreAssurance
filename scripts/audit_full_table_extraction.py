"""Audit de couverture de extraction/full_table_extractor.py sur Annexe 13
(Résultat technique Non-Vie), toutes sociétés x années disponibles.

Outil de diagnostic réutilisable (comme scripts/ocr_repair_validated.py ou
api/services/pipeline_audit.py) — pas un script jetable. Usage :
    python scripts/audit_full_table_extraction.py [--years N] [--code CODE]

Écrit un résumé sur stdout et le détail complet dans
scripts/audit_full_table_extraction_report.json (pour reprise du travail
société par société sans tout relancer)."""

import argparse
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pdfplumber

from extraction.annexe13_kpi_extractor import _is_target_page, RACCORDEMENT_RE, KPI_PATTERNS
from extraction.full_table_extractor import locate_and_extract_full_table, relaxed_is_annexe13_page

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cmf")

# Sociétés hors périmètre de l'Annexe 13 (Non-Vie) par nature du modèle
# métier, pas par échec d'extraction — exclues du taux de couverture pour
# ne pas fausser le chiffre (voir CAS_PARTICULIERS_FULL_TABLE.md).
VIE_ONLY = {"GAT_VIE", "LLOYD_VIE", "MAGHREBIA_VIE", "CARTE_VIE", "HAYETT"}
TAKAFUL = {"AL_AMANAH_TAKAFUL", "AT_TAKAFULIA", "ZITOUNA_TAKAFUL"}


def audit_one(code, annee):
    path = os.path.join(DATA_DIR, code, f"{code}_{annee}.pdf")
    if not os.path.isfile(path):
        return {"statut": "pas_de_pdf"}
    try:
        with pdfplumber.open(path) as pdf:
            page_num, result = locate_and_extract_full_table(
                pdf, _is_target_page, KPI_PATTERNS, RACCORDEMENT_RE,
                extra_page_predicate=relaxed_is_annexe13_page,
            )
    except Exception as exc:
        return {"statut": "erreur", "detail": str(exc)}
    if result is None:
        return {"statut": "echec"}
    return {
        "statut": "ok", "page": page_num,
        "n_colonnes": len(result["colonnes"]), "n_lignes": len(result["lignes"]),
        "colonnes": result["colonnes"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, default=10, help="nombre d'années récentes à tester (défaut 10)")
    parser.add_argument("--code", type=str, default=None, help="limiter à une société")
    parser.add_argument("--last-year", type=int, default=2025, help="dernière année testée (défaut 2025)")
    args = parser.parse_args()

    years = list(range(args.last_year, args.last_year - args.years, -1))
    codes = sorted(
        d for d in os.listdir(DATA_DIR)
        if os.path.isdir(os.path.join(DATA_DIR, d)) and d not in VIE_ONLY and d not in TAKAFUL
    )
    if args.code:
        codes = [args.code]

    report = {}
    n_ok = n_fail = n_no_pdf = n_err = 0
    for code in codes:
        report[code] = {}
        for annee in years:
            r = audit_one(code, annee)
            report[code][annee] = r
            statut = r["statut"]
            if statut == "ok":
                n_ok += 1
            elif statut == "echec":
                n_fail += 1
            elif statut == "pas_de_pdf":
                n_no_pdf += 1
            else:
                n_err += 1
        ok_years = [a for a, r in report[code].items() if r["statut"] == "ok"]
        fail_years = [a for a, r in report[code].items() if r["statut"] == "echec"]
        print(f"{code:20s} OK={len(ok_years):2d} ECHEC={len(fail_years):2d}  "
              f"(OK: {sorted(ok_years)})")

    total_tentes = n_ok + n_fail + n_err
    print()
    print(f"TOTAL — documents existants testés : {total_tentes}")
    print(f"  OK    : {n_ok} ({100*n_ok/total_tentes:.0f}%)" if total_tentes else "  OK: 0")
    print(f"  ECHEC : {n_fail}")
    print(f"  ERREUR: {n_err}")
    print(f"  (PDF absent, hors calcul du taux) : {n_no_pdf}")

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit_full_table_extraction_report.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nDétail complet : {out_path}")


if __name__ == "__main__":
    main()
