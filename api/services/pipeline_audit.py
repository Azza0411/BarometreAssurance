"""
Audit rapide du pipeline extraction → KPI.

Stratégie sans re-scan PDF (évite les timeouts) :
  - Les valeurs en base sont la source de vérité sur ce qui a été extrait.
  - Si certaines valeurs d'une section sont présentes → la section était accessible.
  - Si aucune valeur d'une section → probable échec de détection.
  - L'existence physique du PDF est vérifiée par os.path.isfile (rapide).

Étapes auditées :
  1  PDF local absent
  2  Section PDF probablement non détectée (aucune valeur de cette section en base)
  3  Composante manquante (section présente mais valeur spécifique non extraite)
  4  KPI calculé recalculé via kpi_builder
  5  KPI final manquant (pas de composantes, pas de valeur brute)
  6  Valeur aberrante (hors plage métier)
  7  Anomalie détectée à l'extraction (déséquilibre Bilan, variation YoY
     implausible — voir extraction/kpi_extraction_pipeline.py::_check_balance
     et extraction/data_cleaning.py::check_yoy_consistency). Contrairement
     aux étapes 1-6 (recalculées à chaque requête à partir des valeurs en
     base), l'étape 7 relit des constats déjà persistés au moment de
     l'extraction (table anomalies_detectees) : c'est le seul lien entre ce
     rapport et logs/pipeline.log, auparavant invisibles l'un de l'autre.
  8  Doublure RC ≈ RF (même ligne du PDF lue deux fois pour deux KPI
     distincts) — détecté par api/services/quality.py, réutilisé ici pour
     que ce type d'anomalie apparaisse aussi dans Anomalies Système (avant
     août 2026, il n'existait que côté rapport Qualité Data, invisible ici).
  9  Écart sectoriel important (valeur individuellement plausible mais très
     éloignée de la moyenne du secteur même année) — également détecté par
     quality.py, même raison de ré-utilisation que l'étape 8.
"""

import os
from database.repository import (
    get_anomalies, get_kpi_values_for_document, list_documents_by_source, get_document_meta,
)
from api.services.kpi_builder import build_company_row
from api.services.quality import build_quality_report
from api.utils.formatters import kpis_by_year
from extraction.kpi_definitions import (
    KPI_PLAGES_PLAUSIBLES, ZERO_SUSPECT_KPIS, SOURCE_PAR_KPI, get_context, get_formule,
)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cmf",
)

# ── KPIs bruts par section ────────────────────────────────────────────────────
# On utilise ces listes pour inférer si une section était accessible en base
_KPI_PAR_SECTION: dict[str, list[str]] = {
    "annexe12": [
        "Primes émises Vie par assurance",
        "Charges de prestations Vie",
        "Charges d'acquisition et de gestion nettes Vie",
        "Résultat technique Vie",
    ],
    "annexe13": [
        "Primes émises Non-Vie par assurance",
        "Charges de prestations Non-Vie",
        "Charges d'acquisition et de gestion nettes Non-Vie",
        "Résultat technique Non-Vie",
        "Primes acquises",
    ],
    "bilan": [
        "Total actif",
        "Capitaux propres",
    ],
    "etat_resultat": [
        "Résultat Net",
    ],
}

# ── KPIs finaux attendus par contexte ─────────────────────────────────────────
_KPIS_MIXTE = [
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
_KPIS_VIE = [
    "Primes émises Vie par assurance",
    "ROE (%)", "ROA (%)", "Résultat Net", "Total actif", "Capitaux propres",
]

# ── Plages métier ─────────────────────────────────────────────────────────────
# Source de vérité partagée avec api/services/quality.py : voir
# extraction.kpi_definitions.KPI_PLAGES_PLAUSIBLES.
_PLAGES = KPI_PLAGES_PLAUSIBLES

# Alias local — source de vérité unique : extraction.kpi_definitions.ZERO_SUSPECT_KPIS.
_ZERO_SUSPECT_KPIS = ZERO_SUSPECT_KPIS

# ── Section source par KPI ────────────────────────────────────────────────────
_SECTION_PAR_KPI: dict[str, str] = {
    k: v["section"] for k, v in SOURCE_PAR_KPI.items() if "section" in v
}


def _pdf_ok(code: str, annee: int) -> bool:
    return os.path.isfile(os.path.join(DATA_DIR, code.upper(), f"{code.upper()}_{annee}.pdf"))


def _sections_inferees(kpis: dict) -> dict[str, bool]:
    """
    Infère quelles sections étaient accessibles en base
    en vérifiant si au moins un KPI brut de la section est présent.
    """
    return {
        sec: any(kpis.get(k) is not None for k in kpi_list)
        for sec, kpi_list in _KPI_PAR_SECTION.items()
    }


def _audit_one(conn, doc_id: int, code: str, annee: int,
               total_ftusa) -> list[dict]:
    ctx  = get_context(code)
    kpis = get_kpi_values_for_document(conn, doc_id)
    nom_pdf, lien_cmf = get_document_meta(conn, code, annee)

    pdf_local = _pdf_ok(code, annee)
    sections  = _sections_inferees(kpis)   # dict {section: bool}  — rapide, pas de PDF scan

    row_calc = build_company_row(kpis, {}, total_ftusa, code)

    kpis_attendus = _KPIS_VIE if ctx == "vie" else _KPIS_MIXTE
    problemes = []

    def _add(kpi, etape, etape_label, raison, details="",
             gravite="erreur", valeur=None, composantes_manquantes=None):
        problemes.append({
            "code":    code,
            "annee":   annee,
            "kpi":     kpi,
            "etape":   etape,
            "etape_label": etape_label,
            "raison":  raison,
            "details": details,
            "gravite": gravite,
            "valeur":  valeur,
            "composantes_manquantes": composantes_manquantes or [],
            "pdf_local": pdf_local,
            "pdf_nom":   nom_pdf,
            "pdf_lien":  lien_cmf,
            "sections_accessibles": {s: ok for s, ok in sections.items() if ok},
        })

    for kpi in kpis_attendus:
        valeur_db = kpis.get(kpi)
        formule   = get_formule(kpi, code)

        # ── Étape 1 : PDF local ─────────────────────────────────────────────
        if not pdf_local:
            _add(kpi, 1, "PDF manquant",
                 f"Le fichier {code}_{annee}.pdf est absent de data/cmf/{code}/.",
                 "Le PDF n'a pas été téléchargé depuis le portail CMF, "
                 "ou n'est pas disponible pour cette année.",
                 gravite="critique")
            continue

        # ── Étape 6 : Valeur aberrante ──────────────────────────────────────
        if valeur_db is not None:
            plage = _PLAGES.get(kpi)
            if plage:
                lo, hi = plage
                if not (lo <= valeur_db <= hi):
                    src = SOURCE_PAR_KPI.get(kpi, {})
                    _add(kpi, 6, "Valeur aberrante",
                         f"Valeur {round(valeur_db, 2)} hors plage [{lo} – {hi}].",
                         f"Ref. : {src.get('reference', '')}. "
                         f"Cause probable : décalage de colonne dans le tableau PDF "
                         f"ou cellule fusionnée mal interprétée.",
                         gravite="avertissement",
                         valeur=round(valeur_db, 2))
            elif kpi in _ZERO_SUSPECT_KPIS and valeur_db == 0:
                _add(kpi, 6, "Valeur aberrante",
                     f"Valeur nulle suspecte pour « {kpi} ».",
                     "Un montant structurellement non-nul pour une compagnie en activité "
                     "est ressorti à 0 — probable cellule PDF mal lue (décalage de colonne "
                     "tombant sur une case vide) plutôt qu'une réalité économique.",
                     gravite="avertissement",
                     valeur=0)
            continue   # Valeur présente (et dans la plage, ou sans plage définie) → OK

        # Valeur absente — chercher la cause

        # ── Étape 2 : Section PDF inaccessible ──────────────────────────────
        # Infère la section nécessaire depuis la formule ou depuis SOURCE_PAR_KPI
        section_req = _SECTION_PAR_KPI.get(kpi)
        if not section_req and formule:
            comps = formule.get("composantes", [])
            sections_comps = {_SECTION_PAR_KPI.get(c) for c in comps} - {None}
            section_req = next(iter(sections_comps), None)

        if section_req and not sections.get(section_req, False):
            # Aucune valeur de cette section n'est en base → section probablement absente
            _add(kpi, 2, "Section PDF probablement non extraite",
                 f"Aucune valeur de la section « {section_req} » n'est en base pour {code} {annee}.",
                 f"L'extracteur n'a peut-être pas détecté la page {section_req} dans le PDF, "
                 f"ou la mise en page du rapport CMF {annee} diffère du format attendu. "
                 f"Vérifier les patterns de détection dans api/services/pdf_sections.py.",
                 gravite="erreur")
            continue

        # ── Étape 3 : Composantes manquantes ────────────────────────────────
        if formule and formule.get("composantes"):
            comps = formule["composantes"]
            manquantes = [c for c in comps if kpis.get(c) is None]

            if manquantes:
                key_map = {
                    "Ratio combiné (%)":             "ratio_combine",
                    "Ratio de sinistralité (%)":     "ratio_sp",
                    "Ratio de frais de gestion (%)": "ratio_frais",
                }
                row_key = key_map.get(kpi)
                recalc  = row_calc.get(row_key) if row_key else None

                if recalc is not None:
                    _add(kpi, 4, "Recalculé (composantes partielles)",
                         f"Valeur recalculée à {round(recalc, 2)} malgré {len(manquantes)} composante(s) manquante(s).",
                         f"Composantes absentes : {manquantes}. "
                         f"Formule : {formule.get('expr', '')}",
                         gravite="info",
                         valeur=round(recalc, 2),
                         composantes_manquantes=manquantes)
                else:
                    for c in manquantes:
                        src = SOURCE_PAR_KPI.get(c, {})
                        sec = src.get("section", "")
                        sec_ok = sections.get(sec, False)

                        if sec and sec_ok:
                            raison = (
                                f"Composante « {c} » absente malgré la section "
                                f"« {sec} » accessible."
                            )
                            details = (
                                f"Ref. : {src.get('reference', '')}. "
                                f"L'extracteur a trouvé la section mais pas ce libellé précis. "
                                f"Vérifier la normalisation du texte (accents, retours à la ligne, "
                                f"variantes orthographiques) dans l'extracteur Python correspondant."
                            )
                        elif sec:
                            raison = (
                                f"Composante « {c} » absente — "
                                f"section source « {sec} » inaccessible."
                            )
                            details = (
                                f"Aucune valeur de la section {sec} n'est en base. "
                                f"Formule complète : {formule.get('expr', '')}"
                            )
                        else:
                            raison = f"Composante « {c} » manquante (source non documentée)."
                            details = f"Formule : {formule.get('expr', '')}"

                        _add(kpi, 3, "Composante manquante",
                             raison, details,
                             gravite="erreur",
                             composantes_manquantes=[c])
            continue

        # ── Étape 5 : Valeur brute manquante ────────────────────────────────
        src = SOURCE_PAR_KPI.get(kpi, {})
        sec = src.get("section", "")
        sec_ok = sections.get(sec, False)

        if sec and sec_ok:
            raison = f"Valeur manquante malgré la section « {sec} » accessible."
            details = (
                f"Ref. : {src.get('reference', '')}. "
                f"La section a été trouvée dans le PDF mais le libellé exact de la ligne "
                f"ou l'indice de colonne n'a pas été reconnu par l'extracteur."
            )
        else:
            raison = "Valeur brute absente — source non détectable."
            details = (
                f"Le KPI « {kpi} » n'est pas documenté dans SOURCE_PAR_KPI "
                f"ou la section requise ({sec or 'inconnue'}) est absente."
            )

        _add(kpi, 5, "Extraction échouée",
             raison, details, gravite="erreur")

    return problemes


_ETAPE7_LABELS = {
    "extraction_balance": "Déséquilibre Bilan (Actif ≠ Capitaux propres + Passif)",
    "extraction_yoy":     "Variation année sur année implausible",
}


def _persisted_anomalies_as_problemes(conn, annee: int) -> list[dict]:
    """Convertit les anomalies persistées (table anomalies_detectees,
    détectées pendant l'extraction — voir docstring du module, étape 7) au
    même format que les problèmes calculés par _audit_one, pour qu'elles
    s'agrègent naturellement dans le même rapport plutôt que de rester
    invisibles dans logs/pipeline.log."""
    problemes = []
    pdf_meta_cache: dict[str, tuple] = {}
    for a in get_anomalies(conn, annee=annee):
        if a["source"] not in _ETAPE7_LABELS:
            continue
        code = a["code"]
        if code not in pdf_meta_cache:
            pdf_meta_cache[code] = get_document_meta(conn, code, annee) if code else (None, None)
        nom_pdf, lien_cmf = pdf_meta_cache[code]
        details = a.get("details") or {}
        if a["source"] == "extraction_balance":
            raison = f"Total actif ≠ Capitaux propres + Passif (écart {details.get('ecart', '?'):,.0f} TND)" \
                if isinstance(details.get("ecart"), (int, float)) else "Déséquilibre du Bilan détecté à l'extraction."
        else:
            raison = (
                f"{a['kpi']} : {details.get('valeur_precedente', '?')} ({details.get('annee_precedente', '?')}) "
                f"→ {details.get('valeur_actuelle', '?')} ({annee}) [{details.get('variation_pct', '?')}%]"
            )
        problemes.append({
            "code": code, "annee": annee, "kpi": a["kpi"] or "(bilan)",
            "etape": 7, "etape_label": _ETAPE7_LABELS[a["source"]],
            "raison": raison,
            "details": f"Détecté le {a['detected_at']} lors de l'extraction (source={a['source']}).",
            "gravite": a["gravite"],
            "valeur": details.get("ecart") or details.get("valeur_actuelle"),
            "composantes_manquantes": [],
            "pdf_local": _pdf_ok(code, annee) if code else False,
            "pdf_nom": nom_pdf, "pdf_lien": lien_cmf,
            "sections_accessibles": {},
        })
    return problemes


_ETAPE_PAR_TYPE_QUALITE = {"doublure": 8, "ecart_sectoriel": 9}
_ETAPE8_9_LABELS = {8: "Doublure RC ≈ RF", 9: "Écart sectoriel important"}


def _quality_only_problemes(conn, annee: int) -> list[dict]:
    """Convertit les anomalies "doublure"/"ecart_sectoriel" du rapport
    Qualité Data (api/services/quality.py — seul endroit où elles sont
    détectées) au même format "problème" que le reste de cet audit, pour
    qu'elles apparaissent aussi dans Anomalies Système au lieu d'y être
    invisibles. Ne réimplémente pas la détection : réutilise directement
    build_quality_report, qui reste l'unique source de vérité pour ces deux
    contrôles."""
    problemes = []
    try:
        rapport = build_quality_report(conn, annee)
    except Exception:
        return problemes
    for a in rapport.get("anomalies", []):
        etape = _ETAPE_PAR_TYPE_QUALITE.get(a.get("type"))
        if etape is None:
            continue
        problemes.append({
            "code": a.get("code"), "annee": annee, "kpi": a.get("kpi"),
            "etape": etape, "etape_label": _ETAPE8_9_LABELS[etape],
            "raison": a.get("raison", ""),
            "details": "",
            "gravite": "avertissement",
            "valeur": a.get("valeur"),
            "composantes_manquantes": [],
            "pdf_local": a.get("pdf_local", False),
            "pdf_nom": a.get("pdf_nom"), "pdf_lien": a.get("pdf_lien"),
            "sections_accessibles": {},
        })
    return problemes


def build_pipeline_audit(conn, annee: int) -> dict:
    """Audit complet pour une année — rapide (pas de re-scan PDF)."""
    ftusa_kpis  = kpis_by_year(conn, "FTUSA").get(annee, {})
    total_ftusa = ftusa_kpis.get("Total Primes émises")

    company_docs = [
        (doc_id, code)
        for doc_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF")
        if doc_annee == annee and code
    ]

    tous_problemes = []
    for doc_id, code in company_docs:
        try:
            tous_problemes.extend(_audit_one(conn, doc_id, code, annee, total_ftusa))
        except Exception as exc:
            tous_problemes.append({
                "code": code, "annee": annee, "kpi": "(audit)",
                "etape": 0, "etape_label": "Erreur interne d'audit",
                "raison": str(exc), "details": "",
                "gravite": "critique",
                "valeur": None,
                "composantes_manquantes": [],
                "pdf_local": False, "pdf_nom": None, "pdf_lien": None,
                "sections_accessibles": {},
            })

    tous_problemes.extend(_persisted_anomalies_as_problemes(conn, annee))
    tous_problemes.extend(_quality_only_problemes(conn, annee))

    by_gravite, by_etape, by_kpi, by_code = {}, {}, {}, {}
    for p in tous_problemes:
        by_gravite[p["gravite"]]       = by_gravite.get(p["gravite"], 0) + 1
        by_etape[p["etape_label"]]     = by_etape.get(p["etape_label"], 0) + 1
        by_kpi[p["kpi"]]               = by_kpi.get(p["kpi"], 0) + 1
        by_code[p["code"]]             = by_code.get(p["code"], 0) + 1

    companies = sorted({p["code"] for p in tous_problemes})

    return {
        "annee":       annee,
        "n_problemes": len(tous_problemes),
        "n_compagnies_affectees": len(companies),
        "compagnies_affectees":   companies,
        "par_gravite":   by_gravite,
        "par_etape":     by_etape,
        "par_kpi":       by_kpi,
        "par_compagnie": by_code,
        "problemes":     tous_problemes,
    }
