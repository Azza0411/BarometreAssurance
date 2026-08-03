"""Routes /api/apercu-marche/* — données sectorielles FTUSA/CGA/INS."""

from flask import Blueprint, jsonify, request
from database.repository import get_connection, list_documents_by_source
from api.utils.formatters import (
    PRIMES_UNIT_DIVISOR, round1, growth_pct, required_year_arg, kpis_by_year
)

bp = Blueprint("apercu_marche", __name__)

CGA_BRANCH_TO_FIELD = {
    "Automobile": "automobile",
    "Groupe Maladie": "groupe",
    "Incendie et Risques Divers": "incendie",
    "Transport": "transport",
}
FTUSA_BRANCH_TO_FIELD = {
    "Automobile": "automobile",
    "Groupe Maladie": "groupe",
    "Incendie": "incendie",
    "Transport": "transport",
    "Risques Divers": "risques_divers",
}
_CGA_REGION_TO_ID = {
    "Grand Tunis":  "grand-tunis",
    "Nord Est":     "nord-est",
    "Nord Ouest":   "nord-ouest",
    "Centre Est":   "centre-est",
    "Centre Ouest": "centre-ouest",
    "Sud Est":      "sud-est",
    "Sud Ouest":    "sud-ouest",
}


def _branches_non_vie(ftusa, cga):
    branches = {field: None for field in ("automobile", "groupe", "incendie", "transport", "risques_divers")}
    for branch_name, field in CGA_BRANCH_TO_FIELD.items():
        value = cga.get(f"Primes émises par branche - {branch_name}")
        if value is not None:
            branches[field] = value
    for branch_name, field in FTUSA_BRANCH_TO_FIELD.items():
        value = ftusa.get(f"Primes émises par branche (FTUSA) - {branch_name}")
        if value is not None:
            branches[field] = value / PRIMES_UNIT_DIVISOR
    return branches


def _map_level(pct):
    if pct is None:  return "vide"
    if pct >= 25:    return "haute"
    if pct >= 15:    return "forte"
    if pct >= 8:     return "moyenne"
    return "faible"


@bp.route("/api/apercu-marche/annees")
def apercu_marche_annees():
    conn = get_connection()
    try:
        ftusa_years = set(kpis_by_year(conn, "FTUSA").keys())
        ins_years   = set(kpis_by_year(conn, "INS").keys())
        # Plage validée avec l'utilisateur : 2014-2024 (années plus récentes
        # pas encore jugées fiables/complètes pour affichage sur ce tableau).
        years = [y for y in sorted(ftusa_years | ins_years, reverse=True) if 2014 <= y <= 2024]
        return jsonify(years)
    finally:
        conn.close()


@bp.route("/api/apercu-marche/evolution")
def apercu_marche_evolution():
    nb_annees = int(request.args.get("nb_annees", 8))
    conn = get_connection()
    try:
        ftusa_by_year = kpis_by_year(conn, "FTUSA")
        rows = []
        for annee in sorted(ftusa_by_year):
            kpis = ftusa_by_year[annee]
            vie     = kpis.get("Primes émises Vie")
            non_vie = kpis.get("Primes émises Non-Vie")
            total   = kpis.get("Total Primes émises")
            rows.append({
                "annee":   annee,
                "vie":     vie     / PRIMES_UNIT_DIVISOR if vie     is not None else None,
                "non_vie": non_vie / PRIMES_UNIT_DIVISOR if non_vie is not None else None,
                "total":   total   / PRIMES_UNIT_DIVISOR if total   is not None else None,
            })
        return jsonify(rows[-nb_annees:])
    finally:
        conn.close()


@bp.route("/api/apercu-marche/ratios-evolution")
def apercu_marche_ratios_evolution():
    nb_annees = int(request.args.get("nb_annees", 8))
    conn = get_connection()
    try:
        ftusa_by_year = kpis_by_year(conn, "FTUSA")
        rows = []
        for annee in sorted(ftusa_by_year):
            kpis = ftusa_by_year[annee]
            rows.append({
                "annee":          annee,
                "vie_sp":         round1(kpis.get("Ratio S/P Vie")),
                "vie_frais":      round1(kpis.get("Ratio de frais Vie")),
                "vie_combine":    round1(kpis.get("Ratio combiné Vie")),
                "non_vie_sp":     round1(kpis.get("Ratio S/P Non-Vie")),
                "non_vie_frais":  round1(kpis.get("Ratio de frais Non-Vie")),
                "non_vie_combine":round1(kpis.get("Ratio combiné Non-Vie")),
                "total_sp":       round1(kpis.get("Ratio S/P")),
                "total_frais":    round1(kpis.get("Ratio de frais")),
                "total_combine":  round1(kpis.get("Ratio combiné")),
            })
        return jsonify(rows[-nb_annees:])
    finally:
        conn.close()


@bp.route("/api/apercu-marche/profil-pays")
def apercu_marche_profil_pays():
    annee = required_year_arg()
    conn  = get_connection()
    try:
        ftusa_by_year = kpis_by_year(conn, "FTUSA")
        ins_by_year   = kpis_by_year(conn, "INS")
        cga_by_year   = kpis_by_year(conn, "CGA")

        ftusa      = ftusa_by_year.get(annee, {})
        ftusa_prev = ftusa_by_year.get(annee - 1, {})
        ins        = ins_by_year.get(annee, {})
        cga        = cga_by_year.get(annee, {})

        total     = ftusa.get("Total Primes émises")
        vie       = ftusa.get("Primes émises Vie")
        non_vie   = ftusa.get("Primes émises Non-Vie")
        total_prev    = ftusa_prev.get("Total Primes émises")
        vie_prev      = ftusa_prev.get("Primes émises Vie")
        non_vie_prev  = ftusa_prev.get("Primes émises Non-Vie")

        taux_penetration      = ftusa.get("Taux de pénétration")
        taux_penetration_prev = ftusa_prev.get("Taux de pénétration")
        densite               = ftusa.get("Densité de l'assurance")
        population            = ins.get("Population Totale")
        if densite is None and total is not None and population:
            densite = total / population
        densite_prev   = ftusa_prev.get("Densité de l'assurance")
        population_prev = ins_by_year.get(annee - 1, {}).get("Population Totale")
        if densite_prev is None and total_prev is not None and population_prev:
            densite_prev = total_prev / population_prev

        nb_assureurs = cga.get("Nombre d'assureurs")
        if nb_assureurs is None:
            cmf_docs = list_documents_by_source(conn, "CMF")
            nb_assureurs = len({code for _id, _cmf_id, code, doc_annee in cmf_docs
                                if doc_annee == annee and code}) or None

        return jsonify({
            "population":                population,
            "pib_mdt":                   ins.get("Produit Interieur Brut (PIB)"),
            "taux_penetration_pct":      taux_penetration,
            "var_penetration":           growth_pct(taux_penetration, taux_penetration_prev),
            "densite_assurance_dt":      densite,
            "var_densite":               growth_pct(densite, densite_prev),
            "nb_assureurs":              nb_assureurs,
            "total_primes_emises_mdt":   total   / PRIMES_UNIT_DIVISOR if total   is not None else None,
            "primes_vie_mdt":            vie     / PRIMES_UNIT_DIVISOR if vie     is not None else None,
            "primes_non_vie_mdt":        non_vie / PRIMES_UNIT_DIVISOR if non_vie is not None else None,
            "part_vie_pct":              ftusa.get("Part des primes émises Vie"),
            "part_non_vie_pct":          ftusa.get("Part des primes émises Non-vie"),
            "croissance_primes_pct":     growth_pct(total,   total_prev),
            "croissance_vie_pct":        growth_pct(vie,     vie_prev),
            "croissance_non_vie_pct":    growth_pct(non_vie, non_vie_prev),
            "branches_non_vie":          _branches_non_vie(ftusa, cga),
        })
    finally:
        conn.close()


@bp.route("/api/apercu-marche/ratios")
def apercu_marche_ratios():
    annee = required_year_arg()
    conn  = get_connection()
    try:
        ftusa = kpis_by_year(conn, "FTUSA").get(annee, {})
        return jsonify({
            "vie":     {"ratio_sp_pct": round1(ftusa.get("Ratio S/P Vie")),
                        "ratio_frais_pct": round1(ftusa.get("Ratio de frais Vie")),
                        "ratio_combine_pct": round1(ftusa.get("Ratio combiné Vie"))},
            "non_vie": {"ratio_sp_pct": round1(ftusa.get("Ratio S/P Non-Vie")),
                        "ratio_frais_pct": round1(ftusa.get("Ratio de frais Non-Vie")),
                        "ratio_combine_pct": round1(ftusa.get("Ratio combiné Non-Vie"))},
            "total":   {"ratio_sp_pct": round1(ftusa.get("Ratio S/P")),
                        "ratio_frais_pct": round1(ftusa.get("Ratio de frais")),
                        "ratio_combine_pct": round1(ftusa.get("Ratio combiné"))},
        })
    finally:
        conn.close()


@bp.route("/api/apercu-marche/distribution-agences")
def apercu_marche_distribution_agences():
    annee = required_year_arg()
    conn  = get_connection()
    try:
        cga_by_year = kpis_by_year(conn, "CGA")
        if annee not in cga_by_year and cga_by_year:
            annee_cga = max(cga_by_year)
        else:
            annee_cga = annee
        kpis = cga_by_year.get(annee_cga, {})

        total_agences = kpis.get("Total agences")
        moyenne       = kpis.get("Nombre moyen d'agences par assureur")
        leader        = kpis.get("Assurance avec le plus d'agences")
        region_top    = kpis.get("Région la plus concentrée")
        region_top_pct = (
            round1(kpis.get(f"Répartition des agences par grande région - {region_top}"))
            if region_top else None
        )

        gov_raw = {
            name.rsplit(" - ", 1)[1]: value
            for name, value in kpis.items()
            if name.startswith("Répartition des agences par gouvernorat - ")
        }
        gov_sorted  = sorted(gov_raw.items(), key=lambda x: x[1], reverse=True)
        total_gouv  = sum(v for _, v in gov_sorted) or 1
        top9        = gov_sorted[:9]
        autres_n    = sum(v for _, v in gov_sorted[9:])
        gouvernorats = [
            {"nom": nom.upper(), "n": int(n), "pct": round1(n / total_gouv * 100)}
            for nom, n in top9
        ]
        if autres_n:
            gouvernorats.append({"nom": "Autres", "n": int(autres_n),
                                  "pct": round1(autres_n / total_gouv * 100)})

        regions = {}
        for cga_name, map_id in _CGA_REGION_TO_ID.items():
            n   = kpis.get(f"Nombre d'agences par région - {cga_name}")
            pct = kpis.get(f"Répartition des agences par grande région - {cga_name}")
            regions[map_id] = {
                "label": cga_name,
                "n":     int(n) if n is not None else None,
                "pct":   round1(pct),
                "level": _map_level(pct),
            }

        codes_agences = {
            name.rsplit(" - ", 1)[1]: value
            for name, value in kpis.items()
            if name.startswith("Nombre d'agences par assureur - ")
        }
        classement = sorted(codes_agences.items(), key=lambda x: x[1], reverse=True)
        classement_list = [
            {"rang": i+1, "code": code, "n": int(n),
             "pct": round1(kpis.get(f"Part de marché réseau (%) - {code}"))}
            for i, (code, n) in enumerate(classement)
        ]

        return jsonify({
            "annee_cga":          annee_cga,
            "total_agences":      int(total_agences) if total_agences is not None else None,
            "moyenne_agences":    round1(moyenne),
            "leader_reseau":      leader,
            "region_concentree":  region_top,
            "region_concentree_pct": region_top_pct,
            "gouvernorats":       gouvernorats,
            "regions":            regions,
            "classement":         classement_list,
        })
    finally:
        conn.close()
