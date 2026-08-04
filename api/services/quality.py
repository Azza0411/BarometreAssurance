"""
Détection d'anomalies : KPIs manquants, aberrants, recalculés.
Fournit aussi les métadonnées PDF source et les formules de calcul.
"""

import os
from database.repository import (
    get_anomalies, get_kpi_values_for_document, list_documents_by_source, get_document_meta
)
from api.services.kpi_builder import build_company_row, _raw_ratio
from api.utils.formatters import PRIMES_UNIT_DIVISOR, kpis_by_year
from extraction.kpi_definitions import (
    KPI_PLAGES_PLAUSIBLES, ZERO_SUSPECT_KPIS, SOURCE_PAR_KPI, FORMULES, get_formule, get_context,
)

_EXPECTED_KPIS = [
    "Primes émises par assurance",
    "Ratio combiné (%)",
    "Ratio de sinistralité (%)",
    "Ratio de frais de gestion (%)",
    "Part de marché (%)",
    "ROE (%)",
    "ROA (%)",
    "Résultat Net",
    "Total actif",
    "Résultat technique (TND)",
    "Capitaux propres",
]

_EXPECTED_SECTORIELS = [
    "Total Primes émises",
    "Primes émises Vie",
    "Primes émises Non-Vie",
    "Ratio S/P",
    "Ratio de frais",
    "Ratio combiné",
    "Taux de pénétration",
    "Densité de l'assurance",
]

# Alias local — source de vérité unique : extraction.kpi_definitions
# (voir ZERO_SUSPECT_KPIS là-bas pour la justification et le contrôle
# "trop grand/trop petit" complémentaire, YOY_CHECKED_KPIS).
_ZERO_SUSPECT_KPIS = ZERO_SUSPECT_KPIS

# Raison précise par société (voir extraction/CAS_PARTICULIERS.md pour le
# détail de chaque cas) — avant juillet 2026, une seule raison générique
# ("PDF scanné / OCR corrompu / logique Takaful incompatible") était
# affichée pour les 8, sans dire laquelle s'appliquait à quelle société.
PROBLEMATIC_CODES: dict[str, str] = {
    "AL_AMANAH_TAKAFUL": "Document entièrement rédigé en arabe — motifs de recherche actuels non compatibles",
    "AMI":                "Pages scannées en image, aucun texte extractible (nécessite OCR)",
    "CARTE_VIE":          "Pages scannées en image, aucun texte extractible (nécessite OCR)",
    "UIB":                "Pages scannées en image, aucun texte extractible (nécessite OCR)",
    "HAYETT":             "Pages scannées en image, aucun texte extractible (nécessite OCR)",
    "COTUNACE":           "Texte corrompu par un OCR de mauvaise qualité à la source (fautes de caractères aléatoires)",
}

# Aliases locaux depuis kpi_definitions (importé en haut)
_SOURCE_PAR_KPI = SOURCE_PAR_KPI
_FORMULES       = FORMULES

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cmf"
)


def _local_pdf_exists(code, annee):
    path = os.path.join(DATA_DIR, code, f"{code}_{annee}.pdf")
    return os.path.isfile(path)


def _fmt(v):
    """Formate une valeur brute pour l'affichage dans les valeurs source."""
    if v is None:
        return None
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f} M TND"
    if abs(v) >= 1_000:
        return f"{v:,.0f} TND"
    return f"{v:.2f}"


def _valeurs_source(kpis, composantes):
    """Retourne liste [{nom, valeur, doc, section, utilise}] pour les composantes d'une formule."""
    result = []
    for c in composantes:
        v = kpis.get(c)
        src = _SOURCE_PAR_KPI.get(c, {})
        result.append({
            "nom":     c,
            "valeur":  _fmt(v) if v is not None else None,
            "utilise": v is not None,
            "doc":     src.get("doc", "PDF CMF"),
            "section": src.get("section", ""),
        })
    return result


# Ratio final (kpi_detail) -> nom d'affichage, pour la comparaison sectorielle.
_PEER_RATIOS = {
    "rc_final":  "Ratio combiné (%)",
    "rsp_final": "Ratio de sinistralité (%)",
    "rf_final":  "Ratio de frais de gestion (%)",
}
# Taille mini du groupe de pairs pour qu'une moyenne sectorielle soit
# significative (en dessous, une seule société atypique fausserait la
# moyenne elle-même) ; écart mini (x0,5 / x2 la moyenne) pour signaler.
_PEER_MIN_GROUP_SIZE = 5
_PEER_DEVIATION_RATIO = 2.0


def _sector_peer_anomalies(kpi_detail: dict, annee: int) -> list[dict]:
    """Compare chaque société à la moyenne du secteur (même année, mêmes
    sociétés déjà traitées dans `kpi_detail`) pour RC/RSP/RF. Signale une
    société dont la valeur est ≤ moyenne/2 ou ≥ moyenne×2 — un écart aussi
    large trahit soit une vraie spécificité (à documenter), soit une
    extraction encore fautive non détectée par les autres contrôles
    (individuellement plausible, mais très éloignée de ses pairs)."""
    anomalies = []
    for field, kpi_label in _PEER_RATIOS.items():
        values = [(code, d[field]) for code, d in kpi_detail.items() if d.get(field) is not None]
        if len(values) < _PEER_MIN_GROUP_SIZE:
            continue
        moyenne = sum(v for _, v in values) / len(values)
        if moyenne <= 0:
            continue
        for code, v in values:
            if v <= moyenne / _PEER_DEVIATION_RATIO or v >= moyenne * _PEER_DEVIATION_RATIO:
                anomalies.append({
                    "type":    "ecart_sectoriel",
                    "code":    code,
                    "kpi":     kpi_label,
                    "valeur":  round(v, 2),
                    "raison":  (
                        f"{round(v, 2)} % très éloigné de la moyenne du secteur "
                        f"({round(moyenne, 2)} %, {len(values)} sociétés) pour {annee}."
                    ),
                    "formule":        None,
                    "source_doc":     None,
                    "valeurs_source": None,
                    "pdf_local":      kpi_detail[code].get("pdf_local"),
                    "pdf_lien":       kpi_detail[code].get("pdf_lien"),
                    "pdf_nom":        kpi_detail[code].get("pdf_nom"),
                })
    return anomalies


def build_quality_report(conn, annee: int) -> dict:
    ftusa_kpis  = kpis_by_year(conn, "FTUSA").get(annee, {})
    total_ftusa = ftusa_kpis.get("Total Primes émises")

    kpi_detail = {}
    anomalies  = []
    kpi_counts = {k: 0 for k in _EXPECTED_KPIS}

    company_docs = [
        (doc_id, code)
        for doc_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF")
        if doc_annee == annee and code
    ]
    total_companies = len({code for _, code in company_docs})

    for doc_id, code in company_docs:
        kpis = get_kpi_values_for_document(conn, doc_id)

        # ── Métadonnées PDF ────────────────────────────────────────────────
        nom_pdf, lien_cmf = get_document_meta(conn, code, annee)
        pdf_local = _local_pdf_exists(code, annee)

        # ── Présence / absence / aberrance ────────────────────────────────
        present  = {}
        manquant = []
        aberrant = []

        for kpi in _EXPECTED_KPIS:
            v = kpis.get(kpi)
            if v is None:
                manquant.append(kpi)
                anomalie = {
                    "type":   "manquant",
                    "code":   code,
                    "kpi":    kpi,
                    "valeur": None,
                    "raison": "Non extrait du PDF",
                    "formule": _FORMULES.get(kpi, {}).get("expr"),
                    "source_doc": _FORMULES.get(kpi, {}).get("source_doc"),
                    "valeurs_source": None,
                    "pdf_local": pdf_local,
                    "pdf_lien":  lien_cmf,
                    "pdf_nom":   nom_pdf,
                }
                anomalies.append(anomalie)
            else:
                present[kpi] = v
                kpi_counts[kpi] += 1

                # Plage de plausibilité partagée avec pipeline_audit.py (voir
                # extraction.kpi_definitions.KPI_PLAGES_PLAUSIBLES) — avant
                # juillet 2026, ce fichier utilisait sa propre plage [2,1000]
                # pour RC/RSP/RF uniquement, différente de celle de
                # pipeline_audit.py pour les mêmes KPI.
                plage = KPI_PLAGES_PLAUSIBLES.get(kpi)
                if plage:
                    lo, hi = plage
                    if not (lo <= v <= hi):
                        aberrant.append(kpi)
                        anomalies.append({
                            "type":        "aberrant",
                            "code":        code,
                            "kpi":         kpi,
                            "valeur":      round(v, 2),
                            "raison":      f"Hors plage [{lo} %, {hi} %] — valeur brute : {round(v, 2)} %",
                            "formule":     None,
                            "source_doc":  f"{nom_pdf or 'PDF CMF'}",
                            "valeurs_source": None,
                            "pdf_local":   pdf_local,
                            "pdf_lien":    lien_cmf,
                            "pdf_nom":     nom_pdf,
                        })
                elif kpi in _ZERO_SUSPECT_KPIS and v == 0:
                    aberrant.append(kpi)
                    anomalies.append({
                        "type":        "aberrant",
                        "code":        code,
                        "kpi":         kpi,
                        "valeur":      0,
                        "raison":      f"Valeur nulle suspecte — « {kpi} » ne peut structurellement pas être 0 pour une compagnie en activité (probable cellule PDF mal lue).",
                        "formule":     None,
                        "source_doc":  f"{nom_pdf or 'PDF CMF'}",
                        "valeurs_source": None,
                        "pdf_local":   pdf_local,
                        "pdf_lien":    lien_cmf,
                        "pdf_nom":     nom_pdf,
                    })

                # Doublure RC ≈ RF
                if kpi == "Ratio combiné (%)":
                    rc = kpis.get("Ratio combiné (%)")
                    rf = kpis.get("Ratio de frais de gestion (%)")
                    if rc is not None and rf is not None and abs(rc - rf) < 0.5:
                        anomalies.append({
                            "type":   "doublure",
                            "code":   code,
                            "kpi":    "Ratio combiné (%)",
                            "valeur": round(rc, 2),
                            "raison": f"RC ≈ RF ({round(rc,2)} ≈ {round(rf,2)}) — même ligne lue deux fois dans le PDF",
                            "formule":      None,
                            "source_doc":   f"{nom_pdf or 'PDF CMF'}",
                            "valeurs_source": None,
                            "pdf_local":    pdf_local,
                            "pdf_lien":     lien_cmf,
                            "pdf_nom":      nom_pdf,
                        })

        # ── Recalcul via kpi_builder ────────────────────────────────────
        row = build_company_row(kpis, {}, total_ftusa, code)

        for kpi_name, row_key, composantes_key in [
            ("Ratio combiné (%)",          "ratio_combine", "Ratio combiné (%)"),
            ("Ratio de sinistralité (%)",  "ratio_sp",      "Ratio de sinistralité (%)"),
            ("Ratio de frais de gestion (%)","ratio_frais", "Ratio de frais de gestion (%)"),
        ]:
            val_final = row.get(row_key)
            if kpi_name in manquant and val_final is not None:
                meta = get_formule(composantes_key, code) or _FORMULES.get(composantes_key, {})
                anomalies.append({
                    "type":         "recalcule",
                    "code":         code,
                    "kpi":          kpi_name,
                    "valeur":       val_final,
                    "raison":       "Non extrait — recalculé depuis les charges brutes du PDF",
                    "formule":        meta.get("expr"),
                    "note":           meta.get("note"),
                    "valeurs_source": _valeurs_source(kpis, meta.get("composantes", [])),
                    "pdf_local":    pdf_local,
                    "pdf_lien":     lien_cmf,
                    "pdf_nom":      nom_pdf,
                    "contexte":     get_context(code),
                })

        # ── KPI detail par compagnie ───────────────────────────────────
        kpi_detail[code] = {
            "present":           list(present.keys()),
            "manquant":          manquant,
            "aberrant":          aberrant,
            "taux_remplissage":  round(len(present) / len(_EXPECTED_KPIS) * 100, 1),
            "rc_final":          row.get("ratio_combine"),
            "rsp_final":         row.get("ratio_sp"),
            "rf_final":          row.get("ratio_frais"),
            "pdf_local":         pdf_local,
            "pdf_lien":          lien_cmf,
            "pdf_nom":           nom_pdf,
            # valeurs brutes pour le panneau de traçabilité
            "kpis_raw": {
                k: (round(v, 2) if isinstance(v, float) else v)
                for k, v in kpis.items()
                if k in _EXPECTED_KPIS + [
                    "Charges de prestations",
                    "Charges de prestations Vie",
                    "Charges de prestations Non-Vie",
                    "Charges d'acquisition et de gestion nettes",
                    "Charges d'acquisition et de gestion nettes Vie",
                    "Charges d'acquisition et de gestion nettes Non-Vie",
                    "Charge de sinistres",
                    "Charge de sinistres Vie",
                    "Charge de sinistres Non-Vie",
                    "Primes acquises",
                    "Primes émises Vie par assurance",
                    "Primes émises Non-Vie par assurance",
                    "Résultat technique Vie",
                    "Résultat technique Non-Vie",
                ]
            },
        }

    # ── Comparaison sectorielle (nouvelle capacité) ─────────────────────
    # Contrairement à extraction/data_cleaning.py::check_yoy_consistency
    # (compare une société à elle-même dans le temps) et au garde-fou de
    # plausibilité (compare une valeur à une plage absolue fixe), ce
    # contrôle compare une société à ses pairs la même année : une société
    # individuellement plausible mais très éloignée de la moyenne du
    # secteur n'était jusqu'ici jamais signalée.
    anomalies.extend(_sector_peer_anomalies(kpi_detail, annee))

    # ── Couverture globale ─────────────────────────────────────────────
    coverage = {
        kpi: {
            "n":   kpi_counts[kpi],
            "pct": round(kpi_counts[kpi] / total_companies * 100, 1) if total_companies else 0,
        }
        for kpi in _EXPECTED_KPIS
    }

    # ── Sectoriels FTUSA ───────────────────────────────────────────────
    sectoriels_present  = [k for k in _EXPECTED_SECTORIELS if ftusa_kpis.get(k) is not None]
    sectoriels_manquant = [k for k in _EXPECTED_SECTORIELS if ftusa_kpis.get(k) is None]

    # ── Anomalies détectées à l'extraction (déséquilibre Bilan, variation
    # YoY implausible) — persistées en base (anomalies_detectees) au moment
    # de l'extraction, invisibles ici avant juillet 2026 (seulement dans
    # logs/pipeline.log). Fusionnées avec les anomalies recalculées ci-dessus.
    _RAISON_PAR_SOURCE = {
        "extraction_balance": "Déséquilibre du Bilan détecté à l'extraction (Total actif ≠ Capitaux propres + Passif)",
        "extraction_yoy":     "Variation année sur année implausible détectée à l'extraction",
    }
    for a in get_anomalies(conn, annee=annee):
        if a["source"] not in _RAISON_PAR_SOURCE:
            continue
        code = a["code"]
        nom_pdf, lien_cmf = get_document_meta(conn, code, annee) if code else (None, None)
        details = a.get("details") or {}
        anomalies.append({
            "type":           "extraction",
            "code":           code,
            "kpi":            a["kpi"] or "(bilan)",
            "valeur":         details.get("ecart") or details.get("valeur_actuelle"),
            "raison":         f"{_RAISON_PAR_SOURCE[a['source']]} (détecté le {a['detected_at']}).",
            "formule":        None,
            "source_doc":     f"{nom_pdf or 'PDF CMF'}",
            "valeurs_source": None,
            "pdf_local":      _local_pdf_exists(code, annee) if code else False,
            "pdf_lien":       lien_cmf,
            "pdf_nom":        nom_pdf,
        })

    return {
        "annee":           annee,
        "total_companies": total_companies,
        "kpi_detail":      kpi_detail,
        "anomalies":       anomalies,
        "coverage":        coverage,
        "sectoriels":      {"present": sectoriels_present, "manquant": sectoriels_manquant},
        "excluded":        [
            {"code": c, "raison": raison}
            for c, raison in PROBLEMATIC_CODES.items()
        ],
    }
