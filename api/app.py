"""
API HTTP (Flask) exposant les KPI déjà extraits/calculés en base MySQL au
frontend React (frontend/). Un seul module pour l'instant, couvrant
uniquement la page "Aperçu marché" (frontend/src/pages/ApercuMarche.jsx) —
le contrat des 5 endpoints ci-dessous (URL, paramètres, forme du JSON) était
déjà fixé côté frontend avant que ce backend n'existe (voir le `fetch(...)`
de chaque section de ApercuMarche.jsx) : ce module s'y conforme plutôt que
d'inventer sa propre convention.

Ne duplique aucun calcul déjà fait par extraction/calculated_kpi_extractor.py
— lit uniquement `kpi_values` (éventuellement en combinant plusieurs
documents/sources pour un même KPI dérivé propre à l'affichage, ex: la
croissance YoY qui compare l'année sélectionnée à l'année précédente).

Lancement : `python api/app.py` (port 8002, cf. frontend/src/pages/
ApercuMarche.jsx : `const API = "http://localhost:8002"`).
"""

import os
import sys
import re
import json
import time
import hashlib
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as req
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.repository import get_connection, get_kpi_values_for_document, list_documents_by_source

app = Flask(__name__)
CORS(app)

PRIMES_UNIT_DIVISOR = 1_000_000  # FTUSA stocke les primes en TND brut, le frontend attend des MDT.

# Branches -> clés attendues par le frontend (branches_non_vie). Deux
# sources concurrentes pour la même donnée (voir
# extraction/ftusa_kpi_extractor.py et extraction/CAS_PARTICULIERS_CGA.md) :
#   - CGA (Annexe 4-1) : fusionne "Incendie" et "Risques Divers" en une
#     seule ligne -> pas de valeur distincte pour "risques_divers", et
#     couverture arrêtée à 2022.
#   - FTUSA (Compte d'exploitation par branche) : distingue "Risques
#     Divers" d'"Incendie", et couvre jusqu'à l'année en cours -> préférée
#     quand disponible (voir _branches_non_vie), CGA en repli uniquement
#     pour combler une année où FTUSA manquerait une branche donnée.
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


def _branches_non_vie(ftusa, cga):
    """CGA stocke déjà ses "Primes émises par branche" en MDT, FTUSA en TND
    brut (comme le reste de ses KPI) -> conversion nécessaire uniquement
    côté FTUSA avant de fusionner les deux dans la même unité."""
    branches = {field: None for field in ("automobile", "groupe", "incendie", "transport", "risques_divers")}
    for branch_name, field in CGA_BRANCH_TO_FIELD.items():
        value = cga.get(f"Primes émises par branche - {branch_name}")
        if value is not None:
            branches[field] = value
    # FTUSA a priorite sur CGA : couverture plus large (jusqu'a l'annee en
    # cours) et distingue Risques Divers d'Incendie.
    for branch_name, field in FTUSA_BRANCH_TO_FIELD.items():
        value = ftusa.get(f"Primes émises par branche (FTUSA) - {branch_name}")
        if value is not None:
            branches[field] = value / PRIMES_UNIT_DIVISOR
    return branches


def _kpis_by_year(conn, source_nom):
    """{annee: {kpi: valeur}} pour tous les documents sectoriels (cmf_id
    NULL) d'une source (FTUSA, CGA, INS) — une seule ligne par année pour
    ces trois sources."""
    result = {}
    for document_id, _cmf_id, _code, annee in list_documents_by_source(conn, source_nom):
        result[annee] = get_kpi_values_for_document(conn, document_id)
    return result


def _growth_pct(current, previous):
    if current is None or not previous:
        return None
    return (current - previous) / previous * 100


def _round1(value):
    """Certains champs (pdm_pct, ratios) sont affichés bruts côté frontend
    (pas de .toFixed()) -> arrondir ici pour éviter les décimales à rallonge
    d'un ratio calculé (ex: 9.8641716837...)."""
    return round(value, 1) if value is not None else None


def _required_year_arg():
    """Lève une erreur 400 propre (pas une 500 générique) si `annee` est
    absent ou non numérique, plutôt que de laisser `int(...)` planter."""
    raw = request.args.get("annee")
    if raw is None:
        raise ValueError("Le paramètre 'annee' est requis")
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Le paramètre 'annee' doit être un entier, reçu : {raw!r}")


@app.errorhandler(ValueError)
def _handle_value_error(exc):
    return jsonify({"error": str(exc)}), 400


@app.route("/api/apercu-marche/annees")
def apercu_marche_annees():
    conn = get_connection()
    try:
        ftusa_years = set(_kpis_by_year(conn, "FTUSA").keys())
        ins_years   = set(_kpis_by_year(conn, "INS").keys())
        all_years   = sorted(ftusa_years | ins_years, reverse=True)
        # Limiter à 2014–2024 uniquement
        years = [y for y in all_years if 2014 <= y <= 2024]
        return jsonify(years)
    finally:
        conn.close()


@app.route("/api/apercu-marche/evolution")
def apercu_marche_evolution():
    nb_annees = int(request.args.get("nb_annees", 8))
    conn = get_connection()
    try:
        ftusa_by_year = _kpis_by_year(conn, "FTUSA")
        rows = []
        for annee in sorted(ftusa_by_year):
            kpis = ftusa_by_year[annee]
            vie = kpis.get("Primes émises Vie")
            non_vie = kpis.get("Primes émises Non-Vie")
            total = kpis.get("Total Primes émises")
            rows.append(
                {
                    "annee": annee,
                    "vie": vie / PRIMES_UNIT_DIVISOR if vie is not None else None,
                    "non_vie": non_vie / PRIMES_UNIT_DIVISOR if non_vie is not None else None,
                    "total": total / PRIMES_UNIT_DIVISOR if total is not None else None,
                }
            )
        return jsonify(rows[-nb_annees:])
    finally:
        conn.close()


@app.route("/api/apercu-marche/ratios-evolution")
def apercu_marche_ratios_evolution():
    """Serie historique des ratios techniques (contrepartie de /ratios, qui
    ne renvoie qu'une seule annee) -> alimente le graphique "Evolution des
    ratios" de ApercuMarche.jsx, jusque-la branche sur des donnees toujours
    nulles (voir CAS_PARTICULIERS_API.md)."""
    nb_annees = int(request.args.get("nb_annees", 8))
    conn = get_connection()
    try:
        ftusa_by_year = _kpis_by_year(conn, "FTUSA")
        rows = []
        for annee in sorted(ftusa_by_year):
            kpis = ftusa_by_year[annee]
            rows.append(
                {
                    "annee": annee,
                    "vie_sp": _round1(kpis.get("Ratio S/P Vie")),
                    "vie_frais": _round1(kpis.get("Ratio de frais Vie")),
                    "vie_combine": _round1(kpis.get("Ratio combiné Vie")),
                    "non_vie_sp": _round1(kpis.get("Ratio S/P Non-Vie")),
                    "non_vie_frais": _round1(kpis.get("Ratio de frais Non-Vie")),
                    "non_vie_combine": _round1(kpis.get("Ratio combiné Non-Vie")),
                    "total_sp": _round1(kpis.get("Ratio S/P")),
                    "total_frais": _round1(kpis.get("Ratio de frais")),
                    "total_combine": _round1(kpis.get("Ratio combiné")),
                }
            )
        return jsonify(rows[-nb_annees:])
    finally:
        conn.close()


@app.route("/api/apercu-marche/profil-pays")
def apercu_marche_profil_pays():
    annee = _required_year_arg()
    conn = get_connection()
    try:
        ftusa_by_year = _kpis_by_year(conn, "FTUSA")
        ins_by_year = _kpis_by_year(conn, "INS")
        cga_by_year = _kpis_by_year(conn, "CGA")

        ftusa = ftusa_by_year.get(annee, {})
        ftusa_prev = ftusa_by_year.get(annee - 1, {})
        ins = ins_by_year.get(annee, {})
        cga = cga_by_year.get(annee, {})

        total = ftusa.get("Total Primes émises")
        vie = ftusa.get("Primes émises Vie")
        non_vie = ftusa.get("Primes émises Non-Vie")
        total_prev = ftusa_prev.get("Total Primes émises")
        vie_prev = ftusa_prev.get("Primes émises Vie")
        non_vie_prev = ftusa_prev.get("Primes émises Non-Vie")

        taux_penetration = ftusa.get("Taux de pénétration")
        taux_penetration_prev = ftusa_prev.get("Taux de pénétration")
        densite = ftusa.get("Densité de l'assurance")
        # Fallback : calculer densité = primes totales (DT) / population quand FTUSA ne la publie pas
        population = ins.get("Population Totale")
        if densite is None and total is not None and population:
            densite = total / population
        densite_prev = ftusa_prev.get("Densité de l'assurance")
        population_prev = ins_by_year.get(annee - 1, {}).get("Population Totale")
        if densite_prev is None and total_prev is not None and population_prev:
            densite_prev = total_prev / population_prev

        nb_assureurs = cga.get("Nombre d'assureurs")
        if nb_assureurs is None:
            # CGA ne couvre pas encore les annees les plus recentes -> repli
            # sur le nombre de societes CMF ayant publie un document cette
            # annee-la (proxy, documente ici plutot que renvoye vide).
            cmf_docs = list_documents_by_source(conn, "CMF")
            nb_assureurs = len({code for _id, _cmf_id, code, doc_annee in cmf_docs if doc_annee == annee and code}) or None

        branches_non_vie = _branches_non_vie(ftusa, cga)

        payload = {
            "population": population,
            "pib_mdt": ins.get("Produit Interieur Brut (PIB)"),
            "taux_penetration_pct": taux_penetration,
            "var_penetration": _growth_pct(taux_penetration, taux_penetration_prev),
            "densite_assurance_dt": densite,
            "var_densite": _growth_pct(densite, densite_prev),
            "nb_assureurs": nb_assureurs,
            "total_primes_emises_mdt": total / PRIMES_UNIT_DIVISOR if total is not None else None,
            "primes_vie_mdt": vie / PRIMES_UNIT_DIVISOR if vie is not None else None,
            "primes_non_vie_mdt": non_vie / PRIMES_UNIT_DIVISOR if non_vie is not None else None,
            "part_vie_pct": ftusa.get("Part des primes émises Vie"),
            "part_non_vie_pct": ftusa.get("Part des primes émises Non-vie"),
            "croissance_primes_pct": _growth_pct(total, total_prev),
            "croissance_vie_pct": _growth_pct(vie, vie_prev),
            "croissance_non_vie_pct": _growth_pct(non_vie, non_vie_prev),
            "branches_non_vie": branches_non_vie,
        }
        return jsonify(payload)
    finally:
        conn.close()


@app.route("/api/apercu-marche/ratios")
def apercu_marche_ratios():
    annee = _required_year_arg()
    conn = get_connection()
    try:
        ftusa = _kpis_by_year(conn, "FTUSA").get(annee, {})
        payload = {
            "vie": {
                "ratio_sp_pct": _round1(ftusa.get("Ratio S/P Vie")),
                "ratio_frais_pct": _round1(ftusa.get("Ratio de frais Vie")),
                "ratio_combine_pct": _round1(ftusa.get("Ratio combiné Vie")),
            },
            "non_vie": {
                "ratio_sp_pct": _round1(ftusa.get("Ratio S/P Non-Vie")),
                "ratio_frais_pct": _round1(ftusa.get("Ratio de frais Non-Vie")),
                "ratio_combine_pct": _round1(ftusa.get("Ratio combiné Non-Vie")),
            },
            "total": {
                "ratio_sp_pct": _round1(ftusa.get("Ratio S/P")),
                "ratio_frais_pct": _round1(ftusa.get("Ratio de frais")),
                "ratio_combine_pct": _round1(ftusa.get("Ratio combiné")),
            },
        }
        return jsonify(payload)
    finally:
        conn.close()


# Mapping région CGA (nom complet) → clé kebab-case attendue par TunisiaMap
_CGA_REGION_TO_ID = {
    "Grand Tunis":   "grand-tunis",
    "Nord Est":      "nord-est",
    "Nord Ouest":    "nord-ouest",
    "Centre Est":    "centre-est",
    "Centre Ouest":  "centre-ouest",
    "Sud Est":       "sud-est",
    "Sud Ouest":     "sud-ouest",
}


def _map_level(pct):
    """Densité relative → niveau de couleur pour TunisiaMap."""
    if pct is None:
        return "vide"
    if pct >= 25:
        return "haute"
    if pct >= 15:
        return "forte"
    if pct >= 8:
        return "moyenne"
    return "faible"


@app.route("/api/apercu-marche/distribution-agences")
def apercu_marche_distribution_agences():
    annee = _required_year_arg()
    conn = get_connection()
    try:
        cga_by_year = _kpis_by_year(conn, "CGA")

        # CGA peut ne pas couvrir l'année demandée (ex: 2023/2024 pas encore
        # publiés) → repli silencieux sur la dernière année disponible.
        if annee not in cga_by_year and cga_by_year:
            annee_cga = max(cga_by_year)
        else:
            annee_cga = annee
        kpis = cga_by_year.get(annee_cga, {})

        # ── KPI cards ────────────────────────────────────────────────────────
        total_agences = kpis.get("Total agences")
        moyenne = kpis.get("Nombre moyen d'agences par assureur")
        leader = kpis.get("Assurance avec le plus d'agences")
        region_top = kpis.get("Région la plus concentrée")
        region_top_pct = (
            _round1(kpis.get(f"Répartition des agences par grande région - {region_top}"))
            if region_top else None
        )

        # ── Gouvernorats (top 9 + Autres) ────────────────────────────────────
        gov_raw = {
            name.rsplit(" - ", 1)[1]: value
            for name, value in kpis.items()
            if name.startswith("Répartition des agences par gouvernorat - ")
        }
        gov_sorted = sorted(gov_raw.items(), key=lambda x: x[1], reverse=True)
        total_gouv = sum(v for _, v in gov_sorted) or 1
        top9 = gov_sorted[:9]
        autres_n = sum(v for _, v in gov_sorted[9:])
        gouvernorats = [
            {"nom": nom.upper(), "n": int(n), "pct": _round1(n / total_gouv * 100)}
            for nom, n in top9
        ]
        if autres_n:
            gouvernorats.append({"nom": "Autres", "n": int(autres_n),
                                  "pct": _round1(autres_n / total_gouv * 100)})

        # ── Régions (donut + carte) ───────────────────────────────────────────
        regions = {}
        for cga_name, map_id in _CGA_REGION_TO_ID.items():
            n = kpis.get(f"Nombre d'agences par région - {cga_name}")
            pct = kpis.get(f"Répartition des agences par grande région - {cga_name}")
            regions[map_id] = {
                "label": cga_name,
                "n": int(n) if n is not None else None,
                "pct": _round1(pct),
                "level": _map_level(pct),
            }

        # ── Classement compagnies par réseau ──────────────────────────────────
        codes_agences = {
            name.rsplit(" - ", 1)[1]: value
            for name, value in kpis.items()
            if name.startswith("Nombre d'agences par assureur - ")
        }
        classement = sorted(codes_agences.items(), key=lambda x: x[1], reverse=True)
        classement_list = [
            {
                "rang": i + 1,
                "code": code,
                "n": int(n),
                "pct": _round1(kpis.get(f"Part de marché réseau (%) - {code}")),
            }
            for i, (code, n) in enumerate(classement)
        ]

        payload = {
            "annee_cga": annee_cga,
            "total_agences": int(total_agences) if total_agences is not None else None,
            "moyenne_agences": _round1(moyenne),
            "leader_reseau": leader,
            "region_concentree": region_top,
            "region_concentree_pct": region_top_pct,
            "gouvernorats": gouvernorats,
            "regions": regions,
            "classement": classement_list,
        }
        return jsonify(payload)
    finally:
        conn.close()


@app.route("/api/analyse-comparative")
def analyse_comparative():
    annee = _required_year_arg()
    conn = get_connection()
    try:
        _KEY_KPIS = {"Primes émises par assurance", "Ratio combiné (%)",
                     "Ratio de frais de gestion (%)", "Part de marché (%)"}
        def _ratio(v):
            # < 2 % : sous-total capté par erreur
            # > 1 000 % : numéro de page capté par erreur (ex. COTUNACE 2024)
            if v is None or v < 2 or v > 1_000:
                return None
            return _round1(v)

        # Total FTUSA de l'année → dénominateur commun pour le calcul de PDM
        # (doc DVRB : PDM = Primes compagnie / Total primes FTUSA × 100)
        ftusa_kpis = _kpis_by_year(conn, "FTUSA").get(annee, {})
        total_ftusa = ftusa_kpis.get("Total Primes émises")  # en TND brut

        result = {}
        for document_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF"):
            if doc_annee != annee or not code:
                continue
            kpis = get_kpi_values_for_document(conn, document_id)
            if not any(kpis.get(k) is not None for k in _KEY_KPIS):
                continue

            # ── Primes émises = Vie + Non-Vie (doc DVRB §3-4-5) ─────────────
            primes_nv  = kpis.get("Primes émises Non-Vie par assurance")
            primes_vie = kpis.get("Primes émises Vie par assurance")
            primes_raw = kpis.get("Primes émises par assurance")

            # Reconstruire le total quand Vie et Non-Vie sont tous les deux dispo
            if (primes_vie is not None and primes_vie > 1_000 and
                    primes_nv is not None and primes_nv > 1_000):
                primes_raw = primes_vie + primes_nv

            # Fallback si valeur directe aberrante (< 1 000 TND, ex. COTUNACE)
            primes_raw_is_bad = primes_raw is None or primes_raw < 1_000
            if primes_raw_is_bad:
                primes_raw = kpis.get("Primes acquises") or kpis.get("Total Primes émises")

            # ── PDM = Primes compagnie / Total FTUSA × 100 (doc DVRB §1) ────
            if primes_raw and not primes_raw_is_bad and total_ftusa and total_ftusa > 0:
                pdm = primes_raw / total_ftusa * 100
            else:
                # Fallback : valeur auto-déclarée CMF si FTUSA indisponible
                pdm = None if primes_raw_is_bad else kpis.get("Part de marché (%)")

            # ── Ratios extraits du PDF, filtrage valeurs aberrantes ──────────
            def _raw(v):
                return v if (v is not None and 2 <= v <= 1_000) else None

            rc  = _raw(kpis.get("Ratio combiné (%)"))
            rsp = _raw(kpis.get("Ratio de sinistralité (%)"))
            rf  = _raw(kpis.get("Ratio de frais de gestion (%)"))

            # Invalider RC quand RC ≈ RF : même ligne lue deux fois (bug extraction)
            # ex. COMAR 2023, CARTE — RC réel >> RF.
            if rc is not None and rf is not None and abs(rc - rf) < 0.5:
                rc = None

            # ── Recalcul depuis les charges brutes ───────────────────────────
            # RSP  = Charges de sinistres / Primes acquises × 100   (doc DVRB §6)
            # RF   = Charges d'acq. et gestion nettes / Primes émises × 100 (doc §18)
            # RC   = (Charges de prestations + Charges d'acq. et gestion) / Primes émises × 100 (doc §11)
            # RC ≠ RSP + RF (dénominateurs différents : Primes acquises vs Primes émises)
            primes_brutes_raw = kpis.get("Primes émises par assurance")
            primes_for_rc_rf = (
                primes_raw if (primes_brutes_raw is None or primes_brutes_raw < 1_000)
                else primes_brutes_raw
            )
            # Guard : si primes_acquises > 2× primes_emises, c'est une réserve
            # mathématique Vie mal extraite (ex. ASTREE 2024 : 1080 MDT vs 176 MDT).
            # Dans ce cas, la RSP extraite du PDF (calculée avec ce mauvais dénominateur)
            # est aussi invalide → on l'annule pour forcer le recalcul depuis les charges.
            primes_acquises = kpis.get("Primes acquises")
            rsp_extracted_unreliable = False
            if (primes_acquises and primes_acquises > 1_000
                    and primes_for_rc_rf and primes_for_rc_rf > 0
                    and primes_acquises > primes_for_rc_rf * 2):
                primes_acquises = None           # valeur aberrante — ignorée
                rsp_extracted_unreliable = True  # RSP du PDF basé sur ce mauvais dénominateur
            denom_rsp = (
                primes_acquises if (primes_acquises and primes_acquises > 1_000)
                else primes_for_rc_rf
            )

            if primes_for_rc_rf and primes_for_rc_rf > 0:
                charge_sin      = kpis.get("Charge de sinistres")
                charge_sin_nv   = kpis.get("Charge de sinistres Non-Vie")
                charge_sin_vie  = kpis.get("Charge de sinistres Vie")
                charge_prest    = kpis.get("Charges de prestations")
                charge_prest_nv = kpis.get("Charges de prestations Non-Vie")
                charge_prest_vie= kpis.get("Charges de prestations Vie")
                charge_frais    = kpis.get("Charges d'acquisition et de gestion nettes")

                # nv_only : société dont les primes ≈ entièrement Non-Vie
                nv_only = (
                    primes_nv is not None and primes_nv > 1_000 and
                    abs(primes_nv - primes_for_rc_rf) / max(primes_nv, primes_for_rc_rf) < 0.01
                )

                if rsp is None and denom_rsp and denom_rsp > 0:
                    # Numérateur RSP : Charge de sinistres (doc DVRB §6-7-8-9)
                    if nv_only:
                        if charge_sin_nv is not None:
                            candidate = abs(charge_sin_nv) / denom_rsp * 100
                            rsp = candidate if candidate >= 2 else None
                        if rsp is None and charge_prest_nv is not None:
                            rsp = abs(charge_prest_nv) / denom_rsp * 100
                    else:
                        sin_total = None
                        if charge_sin_vie is not None and charge_sin_nv is not None:
                            sin_total = abs(charge_sin_vie) + abs(charge_sin_nv)
                        elif charge_sin is not None:
                            sin_total = abs(charge_sin)
                        if sin_total is not None:
                            rsp = sin_total / denom_rsp * 100
                        elif charge_prest is not None:
                            rsp = abs(charge_prest) / denom_rsp * 100

                if rf is None and charge_frais is not None:
                    rf = abs(charge_frais) / primes_for_rc_rf * 100

                # RC depuis les charges : uniquement si la RSP extraite était basée
                # sur des primes_acquises aberrantes (cas ASTREE : RSP+RF serait faux)
                if rc is None and rsp_extracted_unreliable and charge_frais is not None:
                    prest_total = None
                    if charge_prest_vie is not None and charge_prest_nv is not None:
                        prest_total = abs(charge_prest_vie) + abs(charge_prest_nv)
                    elif charge_prest is not None:
                        prest_total = abs(charge_prest)
                    elif charge_sin_vie is not None and charge_sin_nv is not None:
                        prest_total = abs(charge_sin_vie) + abs(charge_sin_nv)
                    elif charge_sin is not None:
                        prest_total = abs(charge_sin)
                    if prest_total is not None:
                        rc = (prest_total + abs(charge_frais)) / primes_for_rc_rf * 100

            # Fallback 1 (algébrique) : compléter si deux des trois ratios sont connus
            # RSP extrait mais non fiable → on ne l'utilise pas pour RC
            rsp_for_fallback = None if rsp_extracted_unreliable else rsp
            if rc is None and rsp_for_fallback is not None and rf is not None:
                rc = rsp_for_fallback + rf
            if rsp is None and rc is not None and rf is not None:
                rsp = rc - rf
            if rf is None and rc is not None and rsp is not None:
                rf = rc - rsp

            # Fallback 2 (charges) : RC encore inconnu → recalcul depuis les charges
            if primes_for_rc_rf and primes_for_rc_rf > 0:
                if rc is None:
                    charge_frais = kpis.get("Charges d'acquisition et de gestion nettes")
                    if charge_frais is not None:
                        prest_total = None
                        if charge_prest_vie is not None and charge_prest_nv is not None:
                            prest_total = abs(charge_prest_vie) + abs(charge_prest_nv)
                        elif charge_prest is not None:
                            prest_total = abs(charge_prest)
                        elif charge_sin_vie is not None and charge_sin_nv is not None:
                            prest_total = abs(charge_sin_vie) + abs(charge_sin_nv)
                        elif charge_sin is not None:
                            prest_total = abs(charge_sin)
                        if prest_total is not None:
                            rc = (prest_total + abs(charge_frais)) / primes_for_rc_rf * 100

            # Deuxième passe de validation
            if rsp is not None and rsp < 2: rsp = None
            if rf is not None and rf < 2:   rf  = None

            result[code] = {
                "pdm":           _round1(pdm),
                "primes":        _round1(primes_raw / PRIMES_UNIT_DIVISOR) if primes_raw else None,
                "ratio_combine": _ratio(rc),
                "ratio_sp":      _ratio(rsp),
                "ratio_frais":   _ratio(rf),
            }
        return jsonify(result)
    finally:
        conn.close()


@app.route("/api/classement-compagnies")
def classement_compagnies():
    annee = _required_year_arg()
    conn = get_connection()
    try:
        rows = []
        for document_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF"):
            if doc_annee != annee or not code:
                continue
            kpis = get_kpi_values_for_document(conn, document_id)
            pdm = kpis.get("Part de marché (%)")
            if pdm is None:
                continue
            total_actif = kpis.get("Total actif")
            # Seuil : un total actif < 10 000 TND est manifestement un numéro
            # de page ou de ligne capté par erreur (cf. TUNIS_RE 2024).
            if total_actif is not None and total_actif < 10_000:
                total_actif = None
            rows.append({"entreprise": code, "pdm_pct": _round1(pdm), "total_actif": total_actif})
        rows.sort(key=lambda r: r["pdm_pct"], reverse=True)
        return jsonify(rows)
    finally:
        conn.close()


@app.route("/api/vue-assurance/companies")
def vue_assurance_companies():
    conn = get_connection()
    try:
        codes = sorted({
            code for _, _, code, _ in list_documents_by_source(conn, "CMF") if code
        })
        return jsonify(codes)
    finally:
        conn.close()


@app.route("/api/vue-assurance/annees")
def vue_assurance_annees():
    """Retourne uniquement les années où la compagnie a au moins un KPI financier réel extrait."""
    code = request.args.get("code", "")
    conn = get_connection()
    _KEY_KPIS = {
        "Primes émises par assurance", "Résultat Net", "Total actif",
        "ROA (%)", "ROE (%)", "Résultat technique (TND)",
    }
    try:
        annees = []
        for doc_id, _, c, annee in list_documents_by_source(conn, "CMF"):
            if c != code or not annee:
                continue
            kpis = get_kpi_values_for_document(conn, doc_id)
            if any(kpis.get(k) is not None for k in _KEY_KPIS):
                annees.append(annee)
        return jsonify(sorted(a for a in set(annees) if 2014 <= a <= 2024))
    finally:
        conn.close()


@app.route("/api/vue-assurance/profil")
def vue_assurance_profil():
    """Profil d'une compagnie : KPIs CMF de la dernière année disponible,
    agences CGA de la dernière année CGA disponible pour cette compagnie,
    PDM recalculée depuis FTUSA de la dernière année FTUSA disponible."""
    code = request.args.get("code", "")
    conn = get_connection()
    try:
        # --- KPIs CMF : dernière année avec données réelles ---
        _KEY_KPIS = {"Primes émises par assurance", "Résultat Net", "Total actif",
                     "ROA (%)", "ROE (%)", "Résultat technique (TND)"}
        kpis = {}
        annee_cmf = None
        for doc_id, _, c, doc_annee in sorted(
                list_documents_by_source(conn, "CMF"), key=lambda x: x[3], reverse=True):
            if c != code:
                continue
            candidate = get_kpi_values_for_document(conn, doc_id)
            if any(candidate.get(k) is not None for k in _KEY_KPIS):
                kpis = candidate
                annee_cmf = doc_annee
                break

        # --- Agences : dernière année CGA où cette compagnie a des données ---
        agences_region = {}
        total_agences  = None
        annee_cga      = None
        prefix = f"Nombre d'agences de la compagnie par région - {code} - "
        total_key = f"Nombre d'agences par assureur - {code}"
        for doc_id, _, _, doc_annee in sorted(
                list_documents_by_source(conn, "CGA"), key=lambda x: x[3], reverse=True):
            cga = get_kpi_values_for_document(conn, doc_id)
            region_data = {k[len(prefix):]: int(v) for k, v in cga.items() if k.startswith(prefix)}
            if region_data:
                agences_region = region_data
                total_agences  = int(cga[total_key]) if total_key in cga else sum(region_data.values())
                annee_cga = doc_annee
                break

        # --- PDM : depuis les KPIs CMF (déjà calculée) ou recalcul depuis FTUSA ---
        pdm = kpis.get("Part de marché (%)")
        annee_pdm = annee_cmf
        if pdm is None:
            primes = kpis.get("Primes émises par assurance")
            if primes:
                for doc_id, _, _, doc_annee in sorted(
                        list_documents_by_source(conn, "FTUSA"), key=lambda x: x[3], reverse=True):
                    ftusa = get_kpi_values_for_document(conn, doc_id)
                    total = ftusa.get("Total Primes émises")
                    if total:
                        pdm = primes / total * 100
                        annee_pdm = doc_annee
                        break

        def fmt(v, divisor=1):
            return round(v / divisor, 1) if v is not None else None

        return jsonify({
            "code":      code,
            "annee":     annee_cmf,
            "annee_cga": annee_cga,
            "annee_pdm": annee_pdm,
            # Identité
            "siege_social": kpis.get("Siège social"),
            # Indicateurs financiers
            "primes_emises":      fmt(kpis.get("Primes émises par assurance"), 1_000_000),
            "resultat_net":       fmt(kpis.get("Résultat Net"),                1_000_000),
            "total_actif":        fmt(kpis.get("Total actif"),                 1_000_000),
            "capitaux_propres":   fmt(kpis.get("Capitaux propres"),            1_000_000),
            "resultat_technique": fmt(kpis.get("Résultat technique (TND)"),    1_000_000),
            "cours_action":       fmt(kpis.get("Cours de l'action")),
            "capitalisation":     fmt(kpis.get("Capitalisation Boursière")),
            # Ratios
            "pdm":           _round1(pdm),
            "ratio_combine": _round1(kpis.get("Ratio combiné (%)")),
            "ratio_frais":   _round1(kpis.get("Ratio de frais de gestion (%)")),
            "ratio_sp":      _round1(kpis.get("Ratio de sinistralité (%)")),
            "roa":           _round1(kpis.get("ROA (%)")),
            "roe":           _round1(kpis.get("ROE (%)")),
            # Réseau
            "agences_region": agences_region,
            "total_agences":  total_agences,
            # Indicateurs supplémentaires
            "sinistres_payes": fmt(kpis.get("Charge de sinistres"), 1_000_000),
        })
    finally:
        conn.close()


@app.route("/api/vue-assurance/bilan")
def vue_assurance_bilan():
    """Structure du bilan (actif/passif) et composition des placements pour une compagnie/année."""
    code  = request.args.get("code", "")
    annee = request.args.get("annee", type=int)
    conn  = get_connection()
    try:
        # Trouver le document CMF pour cette compagnie/année (ou la plus récente si non spécifiée)
        target_doc = None
        for doc_id, _, c, doc_annee in sorted(
                list_documents_by_source(conn, "CMF"), key=lambda x: x[3] or 0, reverse=True):
            if c != code:
                continue
            if annee is None or doc_annee == annee:
                kpis = get_kpi_values_for_document(conn, doc_id)
                # Vérifier qu'il y a des données de bilan
                if kpis.get("Total actif") or kpis.get("Placements"):
                    target_doc = (doc_annee, kpis)
                    break

        if not target_doc:
            return jsonify({"annee": annee, "actif": [], "passif": [], "placements": [], "total_actif": None, "total_passif": None, "total_placements": None})

        doc_annee, kpis = target_doc
        def m(v):
            if v is None or (isinstance(v, float) and abs(v) < 1000): return None
            return round(v / 1_000_000, 2)

        total_actif = m(kpis.get("Total actif"))
        total_passif = m(kpis.get("Total actif"))  # total actif = total passif par définition

        actif_items = [
            {"label": "Placements",                               "value": m(kpis.get("Placements"))},
            {"label": "Placements prov. techniques",              "value": m(kpis.get("Placements représentant des provisions techniques"))},
            {"label": "Créances",                                 "value": m(kpis.get("Créances"))},
            {"label": "Autres éléments d'actifs",                 "value": m(kpis.get("Autres éléments d'actifs"))},
            {"label": "Actifs corporels",                         "value": m(kpis.get("Actifs corporels"))},
            {"label": "Actifs incorporels",                       "value": m(kpis.get("Actifs incorporels"))},
        ]
        passif_items = [
            {"label": "Provisions techniques brutes",             "value": m(kpis.get("Provisions techniques brutes"))},
            {"label": "Capitaux propres",                         "value": m(kpis.get("Capitaux propres"))},
            {"label": "Part réassureurs / provisions tech.",      "value": m(kpis.get("Part des réassureurs dans les provisions techniques"))},
            {"label": "Provisions pour primes non acquises",      "value": m(kpis.get("Provisions pour Primes non acquises"))},
            {"label": "Provisions d'assurance",                   "value": m(kpis.get("Provisions d'assurance"))},
            {"label": "Autres passifs",                           "value": m(kpis.get("Autres passifs"))},
        ]
        placements_items = [
            {"label": "Obligations",                              "value": m(kpis.get("Obligations"))},
            {"label": "OPCVM",                                    "value": m(kpis.get("OPCVM"))},
            {"label": "Actions & titres participation",           "value": m(kpis.get("Actions et titres de participation"))},
            {"label": "Dépôts et liquidités",                     "value": m(kpis.get("Dépôts et liquidité"))},
        ]

        total_placements_raw = sum(it["value"] for it in placements_items if it["value"] is not None)
        total_placements = round(total_placements_raw, 2) if total_placements_raw else m(kpis.get("Placements"))

        return jsonify({
            "annee":            doc_annee,
            "total_actif":      total_actif,
            "total_passif":     total_passif,
            "total_placements": total_placements,
            "actif":            [it for it in actif_items  if it["value"] is not None],
            "passif":           [it for it in passif_items if it["value"] is not None],
            "placements":       [it for it in placements_items if it["value"] is not None],
        })
    finally:
        conn.close()


@app.route("/api/vue-assurance/evolution")
def vue_assurance_evolution():
    """Série temporelle pour les sparklines : tous les KPIs d'une compagnie sur toutes les années."""
    code = request.args.get("code", "")
    conn = get_connection()
    try:
        # Pré-charger les totaux FTUSA par année (pour recalcul PDM)
        ftusa_total_by_year = {}
        for doc_id, _, _, doc_annee in list_documents_by_source(conn, "FTUSA"):
            if doc_annee and doc_annee not in ftusa_total_by_year:
                ftusa_data = get_kpi_values_for_document(conn, doc_id)
                total = ftusa_data.get("Total Primes émises")
                if total:
                    ftusa_total_by_year[doc_annee] = total

        def _fmtM(v):
            # Filtre les valeurs anormalement basses (< 1000 TND = extraction corrompue)
            if v is None or abs(v) < 1000:
                return None
            return _round1(v / 1_000_000)

        series = {}
        for doc_id, _, c, annee in list_documents_by_source(conn, "CMF"):
            if c != code or not annee:
                continue
            kpis = get_kpi_values_for_document(conn, doc_id)

            # PDM : depuis CMF ou recalcul FTUSA
            pdm = _round1(kpis.get("Part de marché (%)"))
            if pdm is None:
                primes_raw = kpis.get("Primes émises par assurance")
                if primes_raw and abs(primes_raw) >= 1000 and annee in ftusa_total_by_year:
                    pdm = _round1(primes_raw / ftusa_total_by_year[annee] * 100)

            series[annee] = {
                "primes_emises":  _fmtM(kpis.get("Primes émises par assurance")),
                "resultat_net":   _fmtM(kpis.get("Résultat Net")),
                "total_actif":    _fmtM(kpis.get("Total actif")),
                "roa":            _round1(kpis.get("ROA (%)")),
                "roe":            _round1(kpis.get("ROE (%)")),
                "ratio_combine":  _round1(kpis.get("Ratio combiné (%)")),
                "ratio_frais":    _round1(kpis.get("Ratio de frais de gestion (%)")),
                "pdm":            pdm,
            }
        return jsonify(dict(sorted(series.items())))
    finally:
        conn.close()


import json as _json

# ── Helpers enquête ────────────────────────────────────────────────────────────
def _json_or(v, default):
    if v is None:
        return default
    try:
        return _json.loads(v)
    except Exception:
        return default


@app.route("/api/enquete-marche/companies")
def enquete_companies():
    """Liste les compagnies ayant des données d'enquête de marché."""
    conn = get_connection()
    try:
        rows = list_documents_by_source(conn, "ENQUETE")
        codes = sorted({c for _, _, c, _ in rows if c})
        return jsonify(codes)
    finally:
        conn.close()


@app.route("/api/enquete-marche/data")
def enquete_data():
    """Retourne toutes les données d'enquête pour une compagnie donnée."""
    code = request.args.get("code", "")
    conn = get_connection()
    try:
        doc_id = None
        for d_id, _, c, _ in sorted(
                list_documents_by_source(conn, "ENQUETE"), key=lambda x: (x[3] or 0), reverse=True):
            if c == code:
                doc_id = d_id
                break

        if doc_id is None:
            return jsonify(None)

        kpis = get_kpi_values_for_document(conn, doc_id)

        def num(k):
            v = kpis.get(k)
            return int(v) if v is not None else None

        def txt(k, default=None):
            return _json_or(kpis.get(k), default)

        def seg(key):
            p = f"Segment {key}"
            return {
                "genre":      txt(f"{p} - genre",       [0, 0]),
                "age":        txt(f"{p} - age",          [0]*6),
                "typePro":    txt(f"{p} - typePro",      []),
                "vehicule":   num(f"{p} - vehicule"),
                "proprio":    num(f"{p} - proprio"),
                "professions":txt(f"{p} - professions",  []),
                "revFam":     txt(f"{p} - revFam",       {"labs": [], "vals": []}),
                "revInd":     txt(f"{p} - revInd",       {"labs": [], "vals": []}),
            }

        return jsonify({
            "code": code,
            "counts": {
                "particuliers":  num("Comptage - Particuliers"),
                "professionnels":num("Comptage - Professionnels"),
                "tre":           num("Comptage - TRE"),
                "etudiants":     num("Comptage - Étudiants"),
                "retraites":     num("Comptage - Retraités"),
            },
            "segments": {
                "all":           seg("all"),
                "particuliers":  seg("particuliers"),
                "professionnels":seg("professionnels"),
                "etudiants":     seg("etudiants"),
                "tre":           seg("tre"),
                "retraites":     seg("retraites"),
            },
            "entreprises": {
                "secteurs": txt("Entreprises - secteurs", []),
                "employes": txt("Entreprises - employes", {"labs": [], "vals": []}),
                "ca":       txt("Entreprises - ca",       {"labs": [], "vals": []}),
            },
        })
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING — Veille d'actualités & Veille réglementaire
# ─────────────────────────────────────────────────────────────────────────────

_SCRAPE_CACHE: dict = {}   # { cache_key: (timestamp, data) }
_CACHE_TTL = 3600           # 1 heure

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def _cached(key, fn, ttl=_CACHE_TTL):
    """Wrapper de cache en mémoire simple (évite de re-scraper à chaque appel)."""
    now = time.time()
    if key in _SCRAPE_CACHE:
        ts, data = _SCRAPE_CACHE[key]
        if now - ts < ttl:
            return data
    data = fn()
    _SCRAPE_CACHE[key] = (now, data)
    return data


def _get(url, timeout=10):
    try:
        r = req.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None


# ── Compagnies d'assurance tunisiennes (IlBoursa) ────────────────────────────

INSURANCE_COMPANIES = [
    {"name": "STAR Assurances",     "ticker": "STAR",  "keys": ["star"]},
    {"name": "COMAR Assurances",    "ticker": "COMAR", "keys": ["comar"]},
    {"name": "GAT Assurances",      "ticker": "GAT",   "keys": [" gat ", "gat ass"]},
    {"name": "Astree Assurances",   "ticker": "ASTRE", "keys": ["astree"]},
    {"name": "Carte Assurances",    "ticker": "CARTE", "keys": ["carte ass"]},
    {"name": "Lloyd Tunisien",      "ticker": "LLOYD", "keys": ["lloyd"]},
    {"name": "Maghrebia",           "ticker": "MGBP",  "keys": ["maghrebia"]},
    {"name": "BH Assurance",        "ticker": "BHASS", "keys": ["bh assurance", "bh-assur"]},
    {"name": "BNA Assurances",      "ticker": "BNASS", "keys": ["bna assur"]},
    {"name": "AMI Assurances",      "ticker": "AMII",  "keys": ["ami assur"]},
    {"name": "Attijari Assurance",  "ticker": "ATT",   "keys": ["attijari"]},
    {"name": "Tunis Re",            "ticker": "TUNRE", "keys": ["tunis re", "tunis-re", "tunisre"]},
    {"name": "CGA",                 "ticker": "CGA",   "keys": ["comité général des assur", " cga "]},
]

MOIS_FR = {
    "janvier":"01","février":"02","mars":"03","avril":"04","mai":"05","juin":"06",
    "juillet":"07","août":"08","septembre":"09","octobre":"10","novembre":"11","décembre":"12",
    "jan":"01","fév":"02","mar":"03","avr":"04","jun":"06","jul":"07","aoû":"08",
    "sep":"09","oct":"10","nov":"11","déc":"12",
}


def _normalize_date(date_str):
    """Normalise une date quelconque vers dd/mm/yyyy."""
    if not date_str:
        return "2026"
    date_str = date_str.strip()
    if re.match(r'\d{2}/\d{2}/\d{4}', date_str):
        return date_str
    # ISO : 2025-06-13 ou 2025-06-13T...
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    # Français : "12 juin 2025" ou "12 juin 2025 à 10:30"
    m = re.search(r'(\d{1,2})\s+([a-zéûôàâùè]+)\s+(\d{4})', date_str.lower())
    if m:
        day = m.group(1).zfill(2)
        month = MOIS_FR.get(m.group(2)[:3], "01")
        return f"{day}/{month}/{m.group(3)}"
    # Juste une année
    m = re.search(r'\b(20\d{2})\b', date_str)
    if m:
        return m.group(1)
    return "2026"


def _categorize(titre):
    t = titre.lower()
    if any(k in t for k in ["résultat", "chiffre", "prime", "bénéfice", "profit",
                             "sinistre", "ratio", "bilan", "performance", "financier"]):
        return "Résultats financiers"
    if any(k in t for k in ["gouvern", "conseil", "assemblée", "nomination", "direction"]):
        return "Gouvernance"
    if any(k in t for k in ["partenariat", "accord", "convention", "protocole", "collaboration"]):
        return "Partenariat"
    if any(k in t for k in ["digital", "numéri", "application", "plateforme", "technolog", "ia ", "intelligence"]):
        return "Digital"
    if any(k in t for k in ["innov", "borne", "électrique", "développement durable", "énergie", "verte"]):
        return "Innovation"
    if any(k in t for k in ["règlement", "loi", "décret", "circulaire", "obligation", "réglementaire"]):
        return "Réglementation"
    return "Actualité"


def _article_image(url):
    """Extrait l'image principale d'une page d'article (og:image en priorité)."""
    r = _get(url, timeout=8)
    if not r:
        return None, ""
    soup = BeautifulSoup(r.text, "html.parser")
    # og:description
    desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name":"description"})
    desc = (desc_tag.get("content", "") if desc_tag else "").strip()
    # og:image
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"], desc
    for sel in ["article img", ".article-content img", "figure img", ".entry-content img", ".post img"]:
        img = soup.select_one(sel)
        if img:
            src = img.get("src") or img.get("data-src", "")
            if src and not src.endswith(".gif"):
                if not src.startswith("http"):
                    domain = re.match(r'https?://[^/]+', url)
                    src = (domain.group() if domain else "") + src
                return src, desc
    return None, desc


# ── Scraping IlBoursa ────────────────────────────────────────────────────────

ASSURANCE_KEYS = [
    "assur", "cga", "prime", "sinistre", "takaful", "réassur", "reassur",
    "star ass", "comar", " gat ", "astree", "carte ass", "lloyd", "maghrebia",
    "bh ass", "bna ass", "ami ass", "compagnie d'assur",
]

def _scrape_ilboursa():
    """
    Scraping par pages compagnies : /marches/cotation_TICKER
    Dates inline : texte DD/MM/YY précédant chaque lien article dans div.lh25
    """
    # Tickers des compagnies d'assurance listées sur IlBoursa
    ILBOURSA_TICKERS = [
        ("cotation_STAR",  "STAR Assurances"),
        ("cotation_ASSMA", "Maghrebia"),
        ("cotation_AMV",   "Maghrebia"),
        ("cotation_BHASS", "BH Assurance"),
        ("cotation_BNASS", "BNA Assurances"),
        ("cotation_AST",   "Astree Assurances"),
        ("cotation_TRE",   "Tunis Re"),
    ]

    articles = []
    seen_urls = set()
    article_links = []

    date_inline_re = re.compile(r"^(\d{1,2}/\d{1,2}/\d{2,4})$")

    for ticker, compagnie_default in ILBOURSA_TICKERS:
        r = _get(f"https://www.ilboursa.com/marches/{ticker}")
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        # Les articles sont dans div.lh25
        # Dates : <span class="sp1">DD/MM/YY</span> suivi de <a>titre</a>
        container = soup.find("div", class_="lh25")
        if not container:
            continue

        pending_date = ""
        for child in container.children:
            from bs4 import NavigableString, Tag
            if isinstance(child, Tag) and child.name == "span" and "sp1" in (child.get("class") or []):
                pending_date = child.get_text(strip=True)
            elif isinstance(child, Tag) and child.name == "a":
                href = child.get("href", "")
                if not re.search(r"/marches/.+_\d+$", href):
                    continue
                if not href.startswith("http"):
                    href = "https://www.ilboursa.com" + href
                if href in seen_urls:
                    continue
                titre = child.get_text(strip=True)
                if len(titre) < 15:
                    continue
                seen_urls.add(href)
                # Compagnie : affiner par titre si possible
                titre_l = titre.lower()
                compagnie = compagnie_default
                for co in INSURANCE_COMPANIES:
                    if any(k in titre_l for k in co["keys"]):
                        compagnie = co["name"]
                        break
                article_links.append((titre, href, pending_date, compagnie))
                pending_date = ""

    def fetch_one(item):
        titre, href, date_str, compagnie = item
        img, resume = _article_image(href)
        # Convertir DD/MM/YY → DD/MM/YYYY
        if re.match(r"\d{1,2}/\d{1,2}/\d{2}$", date_str):
            parts = date_str.split("/")
            parts[2] = "20" + parts[2]
            date_str = "/".join(parts)
        return {
            "src":       "ILBOURSA",
            "titre":     titre,
            "url":       href,
            "date":      _normalize_date(date_str),
            "categorie": _categorize(titre),
            "compagnie": compagnie,
            "resume":    resume,
            "image":     img,
            "pdf_url":   None,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_one, item): item for item in article_links[:50]}
        for future in as_completed(futures):
            try:
                articles.append(future.result())
            except Exception:
                pass

    return articles


# ── Scraping Atlas Magazine — Tunisie ─────────────────────────────────────────

def _scrape_atlas():
    """
    URL source : atlas-mag.net/fr/news/tunisia
    Structure : div.card dans featured-news-card (exclure sidebar-content qui contient news monde entier)
    Date : <time datetime="2026-07-17T...">
    Pagination : ?page=0..3 (8 articles/page)
    """
    articles = []
    seen_urls = set()
    cutoff_year = datetime.now().year - 5
    article_links = []

    for pg in range(4):
        url = "https://www.atlas-mag.net/fr/news/tunisia" + (f"?page={pg}" if pg > 0 else "")
        r = _get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        # Sélectionner uniquement les cards de la zone principale (pas sidebar)
        main_cards = [
            c for c in soup.find_all("div", class_="card")
            if "sidebar" not in " ".join(c.parent.get("class", []))
        ]

        for card in main_cards:
            # Titre : h5
            title_tag = card.find("h5")
            if not title_tag:
                title_tag = card.find(["h2", "h3", "h4"])
            titre = title_tag.get_text(strip=True) if title_tag else ""

            # Lien article
            href = None
            for a in card.find_all("a", href=True):
                h = a["href"]
                if "/fr/articles/" in h:
                    if not h.startswith("http"):
                        h = "https://www.atlas-mag.net" + h
                    href = h
                    break

            if not href or not titre or len(titre) < 8:
                continue
            if href in seen_urls:
                continue

            # Date via <time datetime="...">
            time_tag = card.find("time")
            date_str = ""
            if time_tag:
                date_str = time_tag.get("datetime", "") or time_tag.get_text(strip=True)

            norm_date = _normalize_date(date_str)
            yr = re.search(r'\b(20\d{2})\b', norm_date)
            if yr and int(yr.group()) < cutoff_year:
                continue

            # Compagnie
            titre_l = titre.lower()
            compagnie = "—"
            for co in INSURANCE_COMPANIES:
                if any(k in titre_l for k in co["keys"]):
                    compagnie = co["name"]
                    break

            seen_urls.add(href)
            article_links.append((titre, href, norm_date, compagnie))

    # Récupérer og:image en parallèle pour tous les articles Atlas
    def fetch_atlas_one(item):
        titre, href, norm_date, compagnie = item
        img, resume = _article_image(href)
        cat = _categorize(titre)
        return {
            "src":       "ATLAS MAGAZINE",
            "titre":     titre,
            "url":       href,
            "date":      norm_date,
            "categorie": cat if cat != "Actualité" else "Publication",
            "compagnie": compagnie,
            "resume":    resume,
            "image":     img,
            "pdf_url":   None,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_atlas_one, item): item for item in article_links}
        for future in as_completed(futures):
            try:
                articles.append(future.result())
            except Exception:
                pass

    return articles


def _scrape_atlas_OLD():
    """Old version — kept for reference."""
    articles = []
    seen_urls = set()
    cutoff_year = datetime.now().year - 5

    page_urls = [
        "https://www.atlas-mag.net/fr/news/tunisia",
        "https://www.atlas-mag.net/fr/news/tunisia?page=1",
    ]

    for page_url in page_urls:
        r = _get(page_url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        cards = soup.find_all("div", class_="card")

        for card in cards:
            img_tag = card.find("img")
            img = None
            if img_tag:
                src = img_tag.get("src", "") or img_tag.get("data-src", "")
                if src:
                    if not src.startswith("http"):
                        src = "https://www.atlas-mag.net" + src
                    img = src

            title_tag = card.find(["h2", "h3", "h4", "h5"])
            titre = title_tag.get_text(strip=True) if title_tag else ""

            all_links = card.find_all("a", href=True)
            href = None
            date_str = ""
            for a in all_links:
                h = a["href"]
                if not h.startswith("http"):
                    h = "https://www.atlas-mag.net" + h
                if "/fr/articles/" in h or "/fr/news/" in h:
                    href = h
                    link_text = a.get_text(strip=True)
                    date_m = re.match(r'^(\w+\s+\d+,\s+\d{4})', link_text)
                    if date_m:
                        date_str = date_m.group(1)
                        if not titre:
                            titre = link_text[len(date_str):].strip()
                    break

            if not href or not titre or len(titre) < 8:
                continue
            if href in seen_urls:
                continue

            norm_date = _normalize_date(date_str)
            yr = re.search(r'\b(20\d{2})\b', norm_date)
            if yr and int(yr.group()) < cutoff_year:
                continue

            seen_urls.add(href)

    return articles


@app.route("/api/actualites", methods=["GET"])
def get_actualites():
    """Agrège les actualités scrapées depuis IlBoursa et Atlas Magazine (sans CGA)."""
    def _scrape():
        results = _scrape_ilboursa() + _scrape_atlas()
        seen = set()
        deduped = []
        for a in results:
            k = a["url"]
            if k not in seen:
                seen.add(k)
                deduped.append(a)
        # Trier : articles avec date complète en premier
        def sort_key(a):
            p = a["date"].split("/")
            if len(p) == 3:
                return f"{p[2]}{p[1]}{p[0]}"
            return a["date"] + "0101"
        deduped.sort(key=sort_key, reverse=True)
        return deduped

    data = _cached("actualites", _scrape)
    return jsonify(data)


# ── Scraping Veille Réglementaire ────────────────────────────────────────────

def _detect_type(text):
    t = text.lower()
    if "règlement" in t or "reglement" in t:
        return "Règlement"
    if "décision" in t or "decision" in t:
        return "Décision"
    if "circulaire" in t:
        return "Circulaire"
    if "avenant" in t:
        return "Avenant"
    if "communiqué" in t or "avis" in t:
        return "Communiqué"
    if "arrêté" in t or "arrete" in t:
        return "Arrêté"
    if "décret" in t or "decret" in t:
        return "Décret"
    if "loi" in t:
        return "Loi"
    if "code" in t:
        return "Code"
    return "Texte"


def _extract_date_from_title(titre):
    """Extrait date et année depuis un titre du type '...du 15 Septembre 2023' ou '...du 19 JUIN 2020'."""
    t = titre.lower()
    m = re.search(r'\bdu\s+(\d{1,2})(?:er)?\s+([a-zéûôàâùè]+)\s+(\d{4})', t)
    if m:
        day = m.group(1).zfill(2)
        month = MOIS_FR.get(m.group(2)[:3], None) or MOIS_FR.get(m.group(2)[:4], "01")
        year = m.group(3)
        return f"{day}/{month}/{year}", int(year)
    m = re.search(r'\b(\d{4})\b', titre)
    if m:
        return m.group(1), int(m.group(1))
    return "", None


def _scrape_cga_page(page_id):
    """Scrape une page CGA (id=30 ou id=33) et retourne des entrées documentaires."""
    url = f"https://www.cga.gov.tn/index.php?id={page_id}&L=0"
    r = _get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.content, "html.parser")

    docs = []
    seen_pdfs = set()

    # Trouver tous les liens PDF
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "fileadmin" not in href or ".pdf" not in href.lower():
            continue

        # Normaliser l'URL
        if not href.startswith("http"):
            href = "https://www.cga.gov.tn/" + href.lstrip("/")

        fname = href.split("/")[-1].lower()
        if fname in seen_pdfs:
            continue
        seen_pdfs.add(fname)

        # Remonter au conteneur le plus proche (li, p, td) pour obtenir le titre complet
        container = a_tag.parent
        for _ in range(5):
            if container is None:
                break
            tag = getattr(container, "name", None)
            if tag in ("li", "p", "td", "article"):
                break
            container = getattr(container, "parent", None)

        if container is None:
            container = a_tag.parent

        # Texte complet du conteneur comme titre (nettoyé)
        titre = re.sub(r'\s+', ' ', container.get_text(separator=" ", strip=True)).strip()
        if not titre or len(titre) < 5:
            titre = a_tag.get_text(strip=True) or fname.replace("_", " ").replace(".pdf", "")

        # Tronquer les titres trop longs (peuvent contenir du texte de paragraphe entier)
        if len(titre) > 200:
            titre = titre[:200].rsplit(" ", 1)[0] + "…"

        type_ = _detect_type(titre)
        date, annee = _extract_date_from_title(titre)

        docs.append({
            "id": hashlib.md5(fname.encode()).hexdigest()[:12],
            "src": "CGA",
            "type": type_,
            "titre": titre,
            "url": href,
            "pdf_url": href,
            "date": date,
            "annee": annee,
        })

    return docs


def _scrape_ftusa_textes():
    """Scrape FTUSA — textes législatifs et réglementaires."""
    url = "https://www.ftusanet.org/cadre-institutionnel/les-textes-legislatifs-et-reglementaires/"
    r = _get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    docs = []
    seen = set()

    # Limiter au contenu principal (exclure nav, header, footer)
    for tag in soup.find_all(["nav", "header", "footer"]):
        tag.decompose()

    # Chercher uniquement dans les <li> et <p> (pas les <div> ni <article> qui capturent le menu)
    for container in soup.find_all(["li", "p"]):
        # Le container ne doit pas contenir d'autres li (éviter les listes imbriquées profondes)
        text = re.sub(r'\s+', ' ', container.get_text(separator=" ", strip=True)).strip()
        if not text or len(text) < 8 or len(text) > 300:
            continue

        text_l = text.lower()
        # Filtrer : garder uniquement les textes légaux
        if not any(k in text_l for k in ["loi ", "décret", "decret", "arrêté", "arrete",
                                          "ordonnance", "code des", "décision", "règlement"]):
            continue

        type_ = _detect_type(text)
        if type_ == "Texte":
            continue

        # Trouver un lien dans ce conteneur
        a_tag = container.find("a", href=True)
        if a_tag:
            href = a_tag["href"]
            if not href.startswith("http"):
                href = "https://www.ftusanet.org" + (href if href.startswith("/") else "/" + href)
        else:
            href = url  # lien vers la page source

        if href in seen:
            continue

        is_pdf = href.lower().endswith(".pdf")
        date, annee = _extract_date_from_title(text)

        seen.add(href)
        docs.append({
            "id": hashlib.md5((text[:80] + href).encode()).hexdigest()[:12],
            "src": "FTUSA",
            "type": type_,
            "titre": text if len(text) <= 200 else text[:200].rsplit(" ", 1)[0] + "…",
            "url": href,
            "pdf_url": href if is_pdf else None,
            "date": date,
            "annee": annee,
        })

    return docs


def _scrape_ftusa_code():
    """Retourne une entrée pour le Code des assurances (FTUSA)."""
    url = "https://www.ftusanet.org/cadre-institutionnel/code-des-assurances/"
    r = _get(url)
    if not r:
        # Fallback statique
        return [{
            "id": "ftusa_code_ass",
            "src": "FTUSA",
            "type": "Code",
            "titre": "Code des assurances (Loi n°92-24 du 9 mars 1992 et textes modificatifs)",
            "url": url,
            "pdf_url": None,
            "date": "09/03/1992",
            "annee": 1992,
        }]

    soup = BeautifulSoup(r.text, "html.parser")

    # Chercher l'intitulé principal H1/H2/H3
    heading = soup.find(["h1", "h2", "h3"])
    titre = heading.get_text(strip=True) if heading else "Code des assurances"
    if not titre or len(titre) < 5:
        titre = "Code des assurances"

    # PDF éventuellement lié
    pdf_url = None
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            pdf_url = a["href"]
            if not pdf_url.startswith("http"):
                pdf_url = "https://www.ftusanet.org" + pdf_url
            break

    return [{
        "id": "ftusa_code_ass",
        "src": "FTUSA",
        "type": "Code",
        "titre": titre if len(titre) > 8 else "Code des assurances (Loi n°92-24 du 9 mars 1992)",
        "url": url,
        "pdf_url": pdf_url,
        "date": "09/03/1992",
        "annee": 1992,
    }]


def _build_veille():
    """Scrape les 4 sources et déduplique."""
    all_docs = []
    all_docs += _scrape_cga_page(33)   # règlements & décisions CGA
    all_docs += _scrape_cga_page(30)   # publications & circulaires CGA
    all_docs += _scrape_ftusa_code()   # Code des assurances
    all_docs += _scrape_ftusa_textes() # textes législatifs FTUSA

    seen_keys = set()
    deduped = []
    for d in all_docs:
        # Déduplique par id ET par titre normalisé (évite les doublons de même texte dans différents <a>)
        title_key = re.sub(r'\s+', ' ', d["titre"].lower().strip())[:80]
        key = d.get("id") or d["url"]
        combined = f"{key}|{title_key}"
        if key not in seen_keys and title_key not in seen_keys:
            seen_keys.add(key)
            seen_keys.add(title_key)
            deduped.append(d)

    # Trier : plus récent en premier, sans date en dernier
    def sort_key(d):
        date = d.get("date", "")
        parts = date.split("/")
        if len(parts) == 3:
            return f"{parts[2]}{parts[1]}{parts[0]}"
        annee = d.get("annee")
        return str(annee) if annee else "0000"

    deduped.sort(key=sort_key, reverse=True)
    return deduped


@app.route("/api/veille-reglementaire", methods=["GET"])
def get_veille_reglementaire():
    """Retourne les textes réglementaires scrapés depuis CGA (id=30, id=33) et FTUSA."""
    data = _cached("veille_reglementaire", _build_veille)
    return jsonify(data)


@app.route("/api/veille-reglementaire/refresh", methods=["POST"])
def refresh_veille_reglementaire():
    """Vide le cache veille réglementaire et force un re-scraping."""
    _SCRAPE_CACHE.pop("veille_reglementaire", None)
    data = _cached("veille_reglementaire", _build_veille)
    return jsonify({"ok": True, "count": len(data)})


@app.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    _SCRAPE_CACHE.clear()
    return jsonify({"ok": True, "message": "Cache vidé"})


@app.route("/api/pdf-proxy", methods=["GET"])
def pdf_proxy():
    """Télécharge un PDF depuis l'URL fournie et le retourne en tant que pièce jointe.
    Paramètre : url (URL du PDF à télécharger)
    """
    url = request.args.get("url", "")
    if not url or not url.startswith("http"):
        return jsonify({"error": "url invalide"}), 400
    # Sécurité : uniquement CGA et FTUSA
    allowed = ["cga.gov.tn", "ftusanet.org", "atlas-mag.net"]
    if not any(d in url for d in allowed):
        return jsonify({"error": "domaine non autorisé"}), 403
    try:
        r = req.get(url, headers=HEADERS, timeout=15, stream=True)
        r.raise_for_status()
        # Nom de fichier
        cd = r.headers.get("Content-Disposition", "")
        fname = ""
        m = re.search(r'filename="?([^";\n]+)"?', cd)
        if m:
            fname = m.group(1)
        if not fname:
            fname = url.split("/")[-1].split("?")[0] or "document.pdf"
        if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
        content_type = r.headers.get("Content-Type", "application/pdf")
        return Response(
            r.iter_content(chunk_size=8192),
            headers={
                "Content-Disposition": f'attachment; filename="{fname}"',
                "Content-Type": content_type,
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(port=8002, debug=True)
