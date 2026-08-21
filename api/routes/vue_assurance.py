"""Routes /api/vue-assurance/* — profil, bilan, évolution d'une compagnie."""

from flask import Blueprint, jsonify, request
from database.repository import (
    get_connection, get_kpi_values_for_document, list_documents_by_source
)
from api.utils.formatters import PRIMES_UNIT_DIVISOR, round1
from api.routes.comparative import PROBLEMATIC_COMPANIES, _ROW_KEY_TO_KPI
from api.services.kpi_builder import build_company_row, compute_solvabilite_investissement
from extraction.kpi_definitions import filter_reliable

bp = Blueprint("vue_assurance", __name__)

_KEY_KPIS_PROFIL = {
    "Primes émises par assurance", "Résultat Net", "Total actif",
    "ROA (%)", "ROE (%)", "Résultat technique (TND)",
}


@bp.route("/api/vue-assurance/companies")
def vue_assurance_companies():
    conn = get_connection()
    try:
        codes = sorted({
            code for _, _, code, _ in list_documents_by_source(conn, "CMF")
            if code and code not in PROBLEMATIC_COMPANIES
        })
        return jsonify(codes)
    finally:
        conn.close()


@bp.route("/api/vue-assurance/annees")
def vue_assurance_annees():
    code = request.args.get("code", "")
    conn = get_connection()
    try:
        annees = []
        for doc_id, _, c, annee in list_documents_by_source(conn, "CMF"):
            if c != code or not annee:
                continue
            kpis = get_kpi_values_for_document(conn, doc_id)
            if any(kpis.get(k) is not None for k in _KEY_KPIS_PROFIL):
                annees.append(annee)
        # Contrairement à apercu_marche.py/qualite.py, aucun plafond figé ici
        # (pas de "2014-2024" validé avec l'utilisateur pour cette page) :
        # exclure silencieusement une année réellement disponible (ex: 2025)
        # causait un décalage label/donnée confirmé en test manuel — le
        # frontend affichait "2024" (dernière année de cette liste) alors que
        # /api/vue-assurance/profil, non plafonné, renvoyait déjà 2025.
        return jsonify(sorted(set(annees)))
    finally:
        conn.close()


@bp.route("/api/vue-assurance/profil")
def vue_assurance_profil():
    code = request.args.get("code", "")
    annee_requested = request.args.get("annee", type=int)
    conn = get_connection()
    try:
        docs_desc = sorted(
            (d for d in list_documents_by_source(conn, "CMF") if d[2] == code),
            key=lambda x: x[3], reverse=True,
        )

        def _first_with_key_kpis(docs):
            for doc_id, _, _, doc_annee in docs:
                candidate = get_kpi_values_for_document(conn, doc_id)
                if any(candidate.get(k) is not None for k in _KEY_KPIS_PROFIL):
                    return candidate, doc_annee
            return {}, None

        # Priorité au document de l'année demandée par le frontend (s'il a au
        # moins un KPI clé) ; à défaut (paramètre absent, ou ce document
        # précis n'a rien d'exploitable), repli sur le plus récent
        # disponible. Avant ce correctif, `annee_requested` était totalement
        # ignoré : la fiche affichait toujours la dernière année en base,
        # quelle que soit l'année réellement sélectionnée côté frontend — un
        # décalage confirmé en test manuel (bandeau "2024" affichant en
        # réalité les chiffres 2025, `/api/vue-assurance/annees` plafonnant
        # artificiellement à 2024 — voir correctif associé).
        kpis, annee_cmf = ({}, None)
        if annee_requested is not None:
            kpis, annee_cmf = _first_with_key_kpis(
                d for d in docs_desc if d[3] == annee_requested
            )
        if annee_cmf is None:
            kpis, annee_cmf = _first_with_key_kpis(docs_desc)

        agences_region = {}
        total_agences  = None
        annee_cga      = None
        prefix    = f"Nombre d'agences de la compagnie par région - {code} - "
        total_key = f"Nombre d'agences par assureur - {code}"
        for doc_id, _, _, doc_annee in sorted(
                list_documents_by_source(conn, "CGA"), key=lambda x: x[3], reverse=True):
            cga         = get_kpi_values_for_document(conn, doc_id)
            region_data = {k[len(prefix):]: int(v) for k, v in cga.items() if k.startswith(prefix)}
            if region_data:
                agences_region = region_data
                total_agences  = int(cga[total_key]) if total_key in cga else sum(region_data.values())
                annee_cga      = doc_annee
                break

        pdm      = filter_reliable("Part de marché (%)", kpis.get("Part de marché (%)"))
        annee_pdm = annee_cmf
        if pdm is None:
            primes = kpis.get("Primes émises par assurance")
            if primes:
                for doc_id, _, _, doc_annee in sorted(
                        list_documents_by_source(conn, "FTUSA"), key=lambda x: x[3], reverse=True):
                    ftusa = get_kpi_values_for_document(conn, doc_id)
                    total = ftusa.get("Total Primes émises")
                    if total:
                        pdm       = primes / total * 100
                        annee_pdm = doc_annee
                        break

        def fmt(v, divisor=1):
            return round(v / divisor, 1) if v is not None else None

        # Cohérence avec Qualité Data : une valeur qu'elle flague aberrante
        # (hors plage métier, ou zéro structurellement impossible pour Total
        # actif/Capitaux propres/Primes émises) ne doit pas s'afficher
        # normalement ici sans avertissement.
        def rel(kpi_name):
            return filter_reliable(kpi_name, kpis.get(kpi_name))

        # Ratio combiné/sinistralité/frais : passer par build_company_row
        # (même repli de calcul qu'Analyse Comparative — reconstruction à
        # partir des Charges de prestations/Charges d'acquisition/Primes
        # émises brutes quand le KPI direct n'a pas été extrait) plutôt que
        # `rel()` seul, qui ne fait qu'une lecture brute sans repli. Avant ce
        # correctif, les deux pages pouvaient afficher des valeurs
        # différentes pour la même société/année (ex: UIB 2024, AMI 2018 —
        # Analyse Comparative retrouvait une valeur qu'ici on affichait N/D)
        # — signalé par l'utilisateur le 2026-08-17.
        annee_prev = (annee_cmf - 1) if annee_cmf else None
        primes_prev_year = {}
        if annee_prev is not None:
            for doc_id, _, c_p, doc_annee_p in list_documents_by_source(conn, "CMF"):
                if c_p != code or doc_annee_p != annee_prev:
                    continue
                kpis_p = get_kpi_values_for_document(conn, doc_id)
                pnv_p, pv_p, pr_p = (kpis_p.get("Primes émises Non-Vie par assurance"),
                                      kpis_p.get("Primes émises Vie par assurance"),
                                      kpis_p.get("Primes émises par assurance"))
                if pv_p and pv_p > 1_000 and pnv_p and pnv_p > 1_000:
                    primes_prev_year[code] = pv_p + pnv_p
                elif pr_p and pr_p > 1_000:
                    primes_prev_year[code] = pr_p
                break

        total_ftusa = None
        for doc_id, _, _, doc_annee in sorted(
                list_documents_by_source(conn, "FTUSA"), key=lambda x: x[3], reverse=True):
            if annee_cmf is not None and doc_annee != annee_cmf:
                continue
            total_ftusa = get_kpi_values_for_document(conn, doc_id).get("Total Primes émises")
            break

        built_row = build_company_row(kpis, primes_prev_year, total_ftusa, code)
        ratio_combine = filter_reliable("Ratio combiné (%)", built_row["ratio_combine"])
        ratio_sp      = filter_reliable("Ratio de sinistralité (%)", built_row["ratio_sp"])
        ratio_frais   = filter_reliable("Ratio de frais de gestion (%)", built_row["ratio_frais"])

        # S4/S5/I1/I2 (dette_cp, dette_actif, actions_actif, placements_cp) :
        # même filtre de fiabilité que sur Analyse Comparative — voir
        # api/services/kpi_builder.py::compute_solvabilite_investissement.
        solvab = {
            k: filter_reliable(_ROW_KEY_TO_KPI[k], v)
            for k, v in compute_solvabilite_investissement(kpis).items()
        }

        return jsonify({
            "code":      code,
            "annee":     annee_cmf,
            "annee_cga": annee_cga,
            "annee_pdm": annee_pdm,
            "siege_social":         kpis.get("Siège social"),
            "primes_emises":        fmt(rel("Primes émises par assurance"), 1_000_000),
            "resultat_net":         fmt(rel("Résultat Net"),                1_000_000),
            "total_actif":          fmt(rel("Total actif"),                 1_000_000),
            "capitaux_propres":     fmt(rel("Capitaux propres"),            1_000_000),
            "resultat_technique":   fmt(rel("Résultat technique (TND)"),    1_000_000),
            "cours_action":         fmt(kpis.get("Cours de l'action")),
            "capitalisation":       fmt(kpis.get("Capitalisation Boursière")),
            "pdm":           round1(pdm),
            "ratio_combine": round1(ratio_combine),
            "ratio_frais":   round1(ratio_frais),
            "ratio_sp":      round1(ratio_sp),
            "roa":           round1(rel("ROA (%)")),
            "roe":           round1(rel("ROE (%)")),
            "dette_cp":       solvab["dette_cp"],
            "dette_actif":    solvab["dette_actif"],
            "actions_actif":  solvab["actions_actif"],
            "placements_cp":  solvab["placements_cp"],
            # Fonds des Participants (Takaful uniquement — voir
            # extraction/takaful_kpi_extractor.py::extract_fonds_participants_kpis) :
            # None pour toute compagnie conventionnelle, ces KPI n'étant
            # jamais extraits pour elle.
            "surplus_familial":      fmt(kpis.get("Surplus du Fonds Takaful Familial (TND)"), 1_000_000),
            "surplus_general":       fmt(kpis.get("Surplus du Fonds Takaful Général (TND)"),  1_000_000),
            "actifs_nets_adherents": fmt(kpis.get("Total actifs nets des adhérents (TND)"),    1_000_000),
            "provisions_adherents":  fmt(kpis.get("Provisions techniques du Fonds des Adhérents (TND)"), 1_000_000),
            "commission_wakala":     fmt(kpis.get("Commission Wakala (TND)"),     1_000_000),
            "commission_moudharaba": fmt(kpis.get("Commission Moudharaba (TND)"), 1_000_000),
            "agences_region": agences_region,
            "total_agences":  total_agences,
            "sinistres_payes": fmt(kpis.get("Charge de sinistres"), 1_000_000),
        })
    finally:
        conn.close()


@bp.route("/api/vue-assurance/bilan")
def vue_assurance_bilan():
    code  = request.args.get("code", "")
    annee = request.args.get("annee", type=int)
    conn  = get_connection()
    try:
        target_doc = None
        for doc_id, _, c, doc_annee in sorted(
                list_documents_by_source(conn, "CMF"), key=lambda x: x[3] or 0, reverse=True):
            if c != code:
                continue
            if annee is None or doc_annee == annee:
                kpis = get_kpi_values_for_document(conn, doc_id)
                if kpis.get("Total actif") or kpis.get("Placements"):
                    target_doc = (doc_annee, kpis)
                    break

        if not target_doc:
            return jsonify({"annee": annee, "actif": [], "passif": [], "placements": [],
                            "total_actif": None, "total_passif": None, "total_placements": None})

        doc_annee, kpis = target_doc

        def m(v):
            if v is None or (isinstance(v, float) and abs(v) < 1000):
                return None
            return round(v / 1_000_000, 2)

        total_actif  = m(filter_reliable("Total actif", kpis.get("Total actif")))
        total_passif = total_actif  # identité bilan

        actif_items = [
            {"label": "Placements",                          "value": m(kpis.get("Placements"))},
            {"label": "Placements prov. techniques",         "value": m(kpis.get("Placements représentant des provisions techniques"))},
            {"label": "Créances",                            "value": m(kpis.get("Créances"))},
            {"label": "Autres éléments d'actifs",            "value": m(kpis.get("Autres éléments d'actifs"))},
            {"label": "Actifs corporels",                    "value": m(kpis.get("Actifs corporels"))},
            {"label": "Actifs incorporels",                  "value": m(kpis.get("Actifs incorporels"))},
        ]
        passif_items = [
            {"label": "Provisions techniques brutes",        "value": m(kpis.get("Provisions techniques brutes"))},
            {"label": "Capitaux propres",                    "value": m(filter_reliable("Capitaux propres", kpis.get("Capitaux propres")))},
            {"label": "Part réassureurs / provisions tech.", "value": m(kpis.get("Part des réassureurs dans les provisions techniques"))},
            {"label": "Provisions pour primes non acquises", "value": m(kpis.get("Provisions pour Primes non acquises"))},
            {"label": "Provisions d'assurance",              "value": m(kpis.get("Provisions d'assurance"))},
            {"label": "Autres passifs",                      "value": m(kpis.get("Autres passifs"))},
        ]
        placements_items = [
            {"label": "Obligations",                         "value": m(kpis.get("Obligations"))},
            {"label": "OPCVM",                               "value": m(kpis.get("OPCVM"))},
            {"label": "Actions & titres participation",      "value": m(kpis.get("Actions et titres de participation"))},
            {"label": "Dépôts et liquidités",                "value": m(kpis.get("Dépôts et liquidité"))},
        ]

        total_placements_raw = sum(it["value"] for it in placements_items if it["value"] is not None)
        total_placements = round(total_placements_raw, 2) if total_placements_raw else m(kpis.get("Placements"))

        return jsonify({
            "annee":            doc_annee,
            "total_actif":      total_actif,
            "total_passif":     total_passif,
            "total_placements": total_placements,
            "actif":      [it for it in actif_items     if it["value"] is not None],
            "passif":     [it for it in passif_items    if it["value"] is not None],
            "placements": [it for it in placements_items if it["value"] is not None],
        })
    finally:
        conn.close()


@bp.route("/api/vue-assurance/evolution")
def vue_assurance_evolution():
    code = request.args.get("code", "")
    conn = get_connection()
    try:
        ftusa_total_by_year = {}
        for doc_id, _, _, doc_annee in list_documents_by_source(conn, "FTUSA"):
            if doc_annee and doc_annee not in ftusa_total_by_year:
                ftusa_data = get_kpi_values_for_document(conn, doc_id)
                total = ftusa_data.get("Total Primes émises")
                if total:
                    ftusa_total_by_year[doc_annee] = total

        def _fmtM(v):
            if v is None or abs(v) < 1000:
                return None
            return round1(v / 1_000_000)

        # Docs de la société, triés par année — nécessaire pour reconstruire
        # les primes de l'année N-1 (même repli de calcul qu'Analyse
        # Comparative pour Ratio combiné/sinistralité/frais, voir profil()
        # ci-dessus).
        company_docs = sorted(
            (d for d in list_documents_by_source(conn, "CMF") if d[2] == code and d[3]),
            key=lambda d: d[3],
        )
        primes_by_year = {}
        for doc_id, _, _, annee in company_docs:
            k = get_kpi_values_for_document(conn, doc_id)
            pnv, pv, pr = (k.get("Primes émises Non-Vie par assurance"),
                           k.get("Primes émises Vie par assurance"),
                           k.get("Primes émises par assurance"))
            if pv and pv > 1_000 and pnv and pnv > 1_000:
                primes_by_year[annee] = pv + pnv
            elif pr and pr > 1_000:
                primes_by_year[annee] = pr

        series = {}
        for doc_id, _, c, annee in company_docs:
            kpis = get_kpi_values_for_document(conn, doc_id)
            pdm  = round1(filter_reliable("Part de marché (%)", kpis.get("Part de marché (%)")))
            if pdm is None:
                primes_raw = kpis.get("Primes émises par assurance")
                if primes_raw and abs(primes_raw) >= 1000 and annee in ftusa_total_by_year:
                    pdm = round1(primes_raw / ftusa_total_by_year[annee] * 100)

            def rel(kpi_name, _kpis=kpis):
                return filter_reliable(kpi_name, _kpis.get(kpi_name))

            built_row = build_company_row(
                kpis, {code: primes_by_year.get(annee - 1)}, ftusa_total_by_year.get(annee), code)

            series[annee] = {
                "primes_emises": _fmtM(rel("Primes émises par assurance")),
                "resultat_net":  _fmtM(rel("Résultat Net")),
                "total_actif":   _fmtM(rel("Total actif")),
                "roa":           round1(rel("ROA (%)")),
                "roe":           round1(rel("ROE (%)")),
                "ratio_combine": round1(filter_reliable("Ratio combiné (%)", built_row["ratio_combine"])),
                "ratio_frais":   round1(filter_reliable("Ratio de frais de gestion (%)", built_row["ratio_frais"])),
                "pdm":           pdm,
            }
        return jsonify(dict(sorted(series.items())))
    finally:
        conn.close()
