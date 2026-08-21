"""Routes /api/apercu-marche/* — données sectorielles FTUSA/CGA/INS."""

from flask import Blueprint, jsonify, request
from database.repository import get_connection, list_documents_by_source, get_kpi_values_for_document
from api.utils.formatters import (
    PRIMES_UNIT_DIVISOR, round1, growth_pct, required_year_arg, kpis_by_year
)
from api.services.quality import PROBLEMATIC_CODES
from config.company_registry import TAKAFUL_CODES

bp = Blueprint("apercu_marche", __name__)

# La FTUSA (rapport statistique sectoriel) ne publie aucune ventilation
# "Contributions Takaful" séparée : toutes les mentions de "takaful"/
# "contribution" dans ses rapports sont des références légales sans rapport
# (fonds de garantie, contribution sociale de solidarité...), pas un tableau
# statistique - vérifié sur data/ftusa/FTUSA_2024.pdf le 2026-08-06. Le
# PROMPT MAÎTRE suppose que la FTUSA fournit "Contributions Brutes/Family/
# General" comme pour les primes conventionnelles : ce n'est pas le cas dans
# la source réelle.
#
# Repli retenu (agrégation, pas invention) : sommer les données CMF déjà
# extraites par compagnie pour les opérateurs Takaful exploitables. Les 3
# opérateurs agréés (AT_TAKAFULIA, ZITOUNA_TAKAFUL, AL_AMANAH_TAKAFUL) ont
# désormais tous un extracteur dédié (AL_AMANAH_TAKAFUL depuis le 2026-08-11,
# voir extraction/CAS_PARTICULIERS_TAKAFUL.md) - une agrégation à cette
# échelle n'est pas un indicateur "marché" au même sens statistique que la
# FTUSA (223 documents, 10+ ans), donc affichée avec cette limite en tête.
USABLE_TAKAFUL_CODES = TAKAFUL_CODES - set(PROBLEMATIC_CODES)


def _takaful_sector_snapshot(conn, annee):
    """Agrège les KPI CMF des opérateurs Takaful exploitables pour `annee` :
    total des contributions (Primes émises par assurance), répartition
    Familial/Général (Primes émises Familial/Général (TND), voir
    extraction/takaful_kpi_extractor.py::extract_fonds_participants_kpis -
    ajoutée 2026-08-11, auparavant affichée "Données non publiées" faute
    d'une ventilation persistée), nombre d'opérateurs ayant déposé un
    document cette année-là, et les 3 ratios techniques sectoriels calculés
    UNIQUEMENT à partir des opérateurs ayant à la fois contributions ET
    charges disponibles (ex: AT_TAKAFULIA n'a aucune charge extraite en 2024
    - l'inclure au numérateur d'un ratio sans l'inclure au dénominateur
    reproduirait exactement le bug segment_mismatch déjà corrigé côté
    conventionnel, voir calculated_kpi_extractor.py)."""
    total = familial = general = None
    automobile = transport = incendie = divers = None
    nb_operateurs = nb_operateurs_familial = nb_operateurs_general = 0
    nb_operateurs_branches = 0
    charges_prestations_total = charges_acquisition_total = primes_ratio_total = 0
    ratio_coverage = 0
    for document_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF"):
        if code not in USABLE_TAKAFUL_CODES or doc_annee != annee:
            continue
        kpis = get_kpi_values_for_document(conn, document_id)
        primes = kpis.get("Primes émises par assurance")
        if primes is not None:
            total = (total or 0) + primes
            nb_operateurs += 1
        fam = kpis.get("Primes émises Familial (TND)")
        if fam is not None:
            familial = (familial or 0) + fam
            nb_operateurs_familial += 1
        gen = kpis.get("Primes émises Général (TND)")
        if gen is not None:
            general = (general or 0) + gen
            nb_operateurs_general += 1
        cp = kpis.get("Charges de prestations")
        ca = kpis.get("Charges d'acquisition et de gestion nettes")
        if primes is not None and cp is not None and ca is not None:
            charges_prestations_total += abs(cp)
            charges_acquisition_total += abs(ca)
            primes_ratio_total += primes
            ratio_coverage += 1
        # Ventilation par branche (Fonds Général uniquement, Annexe 15 - voir
        # extraction/takaful_kpi_extractor.py::extract_branches_ventilation_kpis
        # et extract_al_amanah_takaful_kpis) : les 4 KPI sont extraits
        # ENSEMBLE (même ligne source), donc soit tous présents pour un
        # opérateur/exercice donné, soit aucun - un seul suffit à valider la
        # présence des 4 pour ce document.
        auto = kpis.get("Contributions Automobile (TND)")
        if auto is not None:
            automobile = (automobile or 0) + auto
            transport = (transport or 0) + (kpis.get("Contributions Transport (TND)") or 0)
            incendie = (incendie or 0) + (kpis.get("Contributions Incendie (TND)") or 0)
            divers = (divers or 0) + (kpis.get("Contributions Divers (TND)") or 0)
            nb_operateurs_branches += 1

    # Découvert le 2026-08-07 : certaines années n'ont qu'UN SEUL des 2
    # opérateurs déposé (ex: 2017 = ZITOUNA seule à 44,5 M ; 2018 =
    # AT_TAKAFULIA seule à 22,7 M) - additionner un total partiel sans le
    # signaler donnait une fausse "chute de 50 %" du marché entre ces deux
    # années (artefact de couverture, pas une vraie évolution). Un total
    # n'est donc retenu QUE si TOUS les opérateurs exploitables ont une
    # valeur cette année-là ; sinon None (anomalie de couverture) plutôt
    # qu'un chiffre partiel qui se ferait passer pour un total de marché.
    # Même règle pour Familial/Général, chacun indépendamment : un opérateur
    # peut légitimement n'avoir aucune contribution Familial une année
    # donnée (ex: ZITOUNA_TAKAFUL 2025, confirmé sur le document source) sans
    # que ce soit une anomalie d'extraction - mais additionner son 0 implicite
    # avec les vrais totaux des deux autres reproduirait la même fausse chute.
    if nb_operateurs < len(USABLE_TAKAFUL_CODES):
        total = None
    if nb_operateurs_familial < len(USABLE_TAKAFUL_CODES):
        familial = None
    if nb_operateurs_general < len(USABLE_TAKAFUL_CODES):
        general = None
    # Même règle : la ventilation par branche n'est retenue au niveau
    # marché QUE si les 3 opérateurs exploitables l'ont tous les 4
    # (Automobile/Transport/Incendie/Divers), sinon un total partiel
    # afficherait une structure de portefeuille faussée (ex: 100% Auto si
    # un seul opérateur, très Auto-dominant, était seul disponible).
    if nb_operateurs_branches < len(USABLE_TAKAFUL_CODES):
        automobile = transport = incendie = divers = None

    ratio_sp = ratio_frais = ratio_combine = None
    if ratio_coverage and primes_ratio_total:
        ratio_sp     = round1(charges_prestations_total / primes_ratio_total * 100)
        ratio_frais  = round1(charges_acquisition_total / primes_ratio_total * 100)
        ratio_combine = round1((charges_prestations_total + charges_acquisition_total) / primes_ratio_total * 100)

    return {
        "total": total,
        "familial": familial,
        "general": general,
        "branche_automobile": automobile,
        "branche_transport": transport,
        "branche_incendie": incendie,
        "branche_divers": divers,
        "nb_operateurs": nb_operateurs or None,
        "ratio_sp": ratio_sp,
        "ratio_frais": ratio_frais,
        "ratio_combine": ratio_combine,
        # nb d'opérateurs couverts par le total/les ratios sur le nb exploitable
        # total (transparence pour un futur bandeau UI, pas encore affiché brut).
        "ratio_coverage": ratio_coverage,
        "coverage_complete": nb_operateurs >= len(USABLE_TAKAFUL_CODES),
    }


def _takaful_operateurs_detail(conn, annee):
    """Classement des opérateurs Takaful PAR RAPPORT AU MARCHÉ TAKAFUL
    lui-même (dénominateur = somme des contributions des opérateurs
    exploitables), PAS par rapport au marché national — demande explicite
    du 2026-08-07 : afficher 2,4 %/1,8 % (parts nationales) sur une page
    déjà filtrée "Takaful" n'a pas de sens, ces deux opérateurs représentent
    en réalité l'essentiel du (tout petit) marché Takaful.

    TAKAFUL_CODES - USABLE_TAKAFUL_CODES (= AL_AMANAH_TAKAFUL) est inclus
    dans la liste avec une part `None` plutôt qu'omis silencieusement : la
    Tunisie compte 3 opérateurs agréés (voir cga_kpi_extractor.py), le
    3ème doit apparaître comme "non exploitable", pas disparaître."""
    from config.company_registry import TAKAFUL_CODES

    rows_by_code = {}
    for document_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF"):
        if code not in USABLE_TAKAFUL_CODES or doc_annee != annee:
            continue
        kpis = get_kpi_values_for_document(conn, document_id)
        primes = kpis.get("Primes émises par assurance")
        if primes is not None:
            rows_by_code[code] = primes

    total = sum(rows_by_code.values()) or None
    rows = []
    for code in TAKAFUL_CODES:
        primes = rows_by_code.get(code)
        rows.append({
            "code": code,
            "contributions_mdt": round1(primes / PRIMES_UNIT_DIVISOR) if primes is not None else None,
            "pdm_intra_pct": round1(primes / total * 100) if (primes is not None and total) else None,
            "exploitable": code in USABLE_TAKAFUL_CODES,
        })
    rows.sort(key=lambda r: (r["pdm_intra_pct"] is None, -(r["pdm_intra_pct"] or 0)))
    return rows

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


def _takaful_years(conn):
    return sorted({doc_annee for _id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF")
                   if code in USABLE_TAKAFUL_CODES and doc_annee})


@bp.route("/api/apercu-marche/evolution")
def apercu_marche_evolution():
    nb_annees = int(request.args.get("nb_annees", 8))
    famille   = request.args.get("famille", "conventionnelle")
    conn = get_connection()
    try:
        if famille == "takaful":
            rows = []
            for annee in _takaful_years(conn):
                snap = _takaful_sector_snapshot(conn, annee)
                total, familial, general = snap["total"], snap["familial"], snap["general"]
                rows.append({
                    "annee":   annee,
                    "vie":     familial / PRIMES_UNIT_DIVISOR if familial is not None else None,
                    "non_vie": general  / PRIMES_UNIT_DIVISOR if general  is not None else None,
                    "total":   total    / PRIMES_UNIT_DIVISOR if total    is not None else None,
                })
            return jsonify(rows[-nb_annees:])

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
    famille   = request.args.get("famille", "conventionnelle")
    conn = get_connection()
    try:
        if famille == "takaful":
            rows = []
            for annee in _takaful_years(conn):
                snap = _takaful_sector_snapshot(conn, annee)
                rows.append({
                    "annee": annee,
                    "vie_sp": None, "vie_frais": None, "vie_combine": None,
                    "non_vie_sp": None, "non_vie_frais": None, "non_vie_combine": None,
                    "total_sp":      snap["ratio_sp"],
                    "total_frais":   snap["ratio_frais"],
                    "total_combine": snap["ratio_combine"],
                })
            return jsonify(rows[-nb_annees:])

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
    annee   = required_year_arg()
    famille = request.args.get("famille", "conventionnelle")
    conn    = get_connection()
    try:
        ins_by_year = kpis_by_year(conn, "INS")
        ins         = ins_by_year.get(annee, {})
        population  = ins.get("Population Totale")
        pib         = ins.get("Produit Interieur Brut (PIB)")

        if famille == "takaful":
            snap      = _takaful_sector_snapshot(conn, annee)
            snap_prev = _takaful_sector_snapshot(conn, annee - 1)
            total, total_prev = snap["total"], snap_prev["total"]
            familial, familial_prev = snap["familial"], snap_prev["familial"]
            general,  general_prev  = snap["general"],  snap_prev["general"]

            # KPI5 du PROMPT MAÎTRE ("Nombre d'opérateurs Takaful agréés") :
            # le mot "agréés" appelle le décompte RÉGLEMENTAIRE (CGA, 3
            # opérateurs en 2024 - voir cga_kpi_extractor.py), distinct du
            # nombre d'opérateurs ayant déposé un état financier EXPLOITABLE
            # cette année-là (snap["nb_operateurs"], ex: 2 en 2024 - El
            # Amana Takaful reste hors périmètre, PDF entièrement en arabe).
            nb_agrees = kpis_by_year(conn, "CGA").get(annee, {}).get("Nombre d'assureurs Takaful")
            population_prev = ins_by_year.get(annee - 1, {}).get("Population Totale")
            pib_prev        = ins_by_year.get(annee - 1, {}).get("Produit Interieur Brut (PIB)")

            # "pib_mdt" (INS/BCT) est déjà en MDT : total doit être ramené à
            # la même unité avant division (total est en TND brut, comme les
            # KPI CMF) — sinon le taux de pénétration ressort ×1 000 000.
            total_mdt      = total      / PRIMES_UNIT_DIVISOR if total      is not None else None
            total_prev_mdt = total_prev / PRIMES_UNIT_DIVISOR if total_prev is not None else None
            taux_penetration      = (total_mdt / pib * 100) if (total_mdt is not None and pib) else None
            taux_penetration_prev = (total_prev_mdt / pib_prev * 100) if (total_prev_mdt is not None and pib_prev) else None
            densite               = (total / population) if (total is not None and population) else None
            densite_prev          = (total_prev / population_prev) if (total_prev is not None and population_prev) else None

            return jsonify({
                "population":              population,
                "pib_mdt":                 pib,
                "taux_penetration_pct":    taux_penetration,
                "var_penetration":         growth_pct(taux_penetration, taux_penetration_prev),
                "densite_assurance_dt":    densite,
                "var_densite":             growth_pct(densite, densite_prev),
                "nb_assureurs":            nb_agrees if nb_agrees is not None else snap["nb_operateurs"],
                "total_primes_emises_mdt": total / PRIMES_UNIT_DIVISOR if total is not None else None,
                "primes_vie_mdt":          familial / PRIMES_UNIT_DIVISOR if familial is not None else None,
                "primes_non_vie_mdt":      general  / PRIMES_UNIT_DIVISOR if general  is not None else None,
                "part_vie_pct":            round1(familial / total * 100) if (familial is not None and total) else None,
                "part_non_vie_pct":        round1(general  / total * 100) if (general  is not None and total) else None,
                "croissance_primes_pct":   growth_pct(total, total_prev),
                "croissance_vie_pct":      growth_pct(familial, familial_prev),
                "croissance_non_vie_pct":  growth_pct(general, general_prev),
                # Ventilation Automobile/Transport/Incendie/Divers (Fonds
                # Général uniquement, Annexe 15) - shape DIFFÉRENTE de la
                # version conventionnelle (4 branches vs 5, pas de "Groupe
                # Maladie"/"Risques Divers" séparés : "Divers" les regroupe
                # déjà, voir mapping validé dans le DVRB). Le frontend
                # distingue les deux via le flag `takaful`.
                "branches_non_vie": {
                    "automobile": snap["branche_automobile"] / PRIMES_UNIT_DIVISOR if snap["branche_automobile"] is not None else None,
                    "transport":  snap["branche_transport"]  / PRIMES_UNIT_DIVISOR if snap["branche_transport"]  is not None else None,
                    "incendie":   snap["branche_incendie"]   / PRIMES_UNIT_DIVISOR if snap["branche_incendie"]   is not None else None,
                    "divers":     snap["branche_divers"]     / PRIMES_UNIT_DIVISOR if snap["branche_divers"]     is not None else None,
                },
                "classement_intra":        _takaful_operateurs_detail(conn, annee),
            })

        ftusa_by_year = kpis_by_year(conn, "FTUSA")
        cga_by_year   = kpis_by_year(conn, "CGA")

        ftusa      = ftusa_by_year.get(annee, {})
        ftusa_prev = ftusa_by_year.get(annee - 1, {})
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
        if densite is None and total is not None and population:
            densite = total / population
        densite_prev   = ftusa_prev.get("Densité de l'assurance")
        population_prev = ins_by_year.get(annee - 1, {}).get("Population Totale")
        if densite_prev is None and total_prev is not None and population_prev:
            densite_prev = total_prev / population_prev

        # "Nombre d'assureurs" (brut CGA) compte TOUTES les sociétés de la
        # section "Sociétés d'Assurance Directe", Takaful comprises (3 sur
        # 23 en 2024 : ZITOUNA TAKAFUL, ATTAKAFULIA, EL AMANA TAKAFUL -
        # vérifié le 2026-08-07 sur CGA_2024.pdf) : l'afficher tel quel sur
        # la version Conventionnelle mélangerait les deux référentiels
        # (règle métier n°1). Préférer le sous-total déjà séparé par
        # l'extracteur (voir cga_kpi_extractor.py::_extract_nombre_assureurs).
        nb_assureurs = cga.get("Nombre d'assureurs Conventionnelle")
        if nb_assureurs is None:
            nb_assureurs = cga.get("Nombre d'assureurs")
        if nb_assureurs is None:
            cmf_docs = list_documents_by_source(conn, "CMF")
            nb_assureurs = len({code for _id, _cmf_id, code, doc_annee in cmf_docs
                                if doc_annee == annee and code and code not in TAKAFUL_CODES}) or None

        return jsonify({
            "population":                population,
            "pib_mdt":                   pib,
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
    annee   = required_year_arg()
    famille = request.args.get("famille", "conventionnelle")
    conn    = get_connection()
    try:
        if famille == "takaful":
            snap = _takaful_sector_snapshot(conn, annee)
            vide = {"ratio_sp_pct": None, "ratio_frais_pct": None, "ratio_combine_pct": None}
            return jsonify({
                "vie":     vide,
                "non_vie": vide,
                "total":   {"ratio_sp_pct": snap["ratio_sp"],
                            "ratio_frais_pct": snap["ratio_frais"],
                            "ratio_combine_pct": snap["ratio_combine"]},
            })

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
