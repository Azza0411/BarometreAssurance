"""
KPI calculés à partir des KPI déjà extraits (pas d'extraction PDF ici) :
voir "Calcul interne.docx" pour les formules d'origine. Quatre familles,
chacune lisant/écrivant dans son propre périmètre de documents :

  - `compute_cmf_derived_kpis` : par société et par année (un document CMF
    à la fois) — sommes Vie+Non-Vie, ROA/ROE, ratios, Part de marché
    (celle-ci croise avec le total sectoriel FTUSA de la même année).
  - `compute_sector_derived_kpis` : par année, à partir des totaux
    sectoriels FTUSA et des indicateurs macro INS (PIB, Population) de la
    même année.
  - `compute_cga_derived_kpis` : par année, à partir des KPI déjà éclatés
    par compagnie/gouvernorat dans un même document CGA (moyenne, classement
    implicite via argmax, agrégation par grande région).
  - `compute_bvmt_market_kpis` : par société et par année — "Cours de
    l'action" (copié depuis le bulletin BVMT de l'année) et "Capitalisation
    Boursière" (= Nombre d'actions x Cours de l'action), voir
    CAS_PARTICULIERS_BVMT.md pour le détail des sources et approximations.

Les KPI de classement/comparaison pur (Classement des assurances, Rang par
primes émises, Écart de performance...) ne sont volontairement PAS stockés
ici : ce sont des tris/comparaisons dépendant du contexte d'affichage,
mieux calculés à la demande à partir des KPI déjà stockés plutôt que figés
en base. Voir extraction/CAS_PARTICULIERS_CALCULS.md.
"""

from config.region_mapping import GOVERNORATE_TO_REGION, REGIONS
from database.repository import (
    delete_kpi_value,
    get_kpi_values_for_document,
    list_documents_by_source,
    save_kpi_value,
)

TABLEAU_LABEL = "Calcul interne"


def _safe_ratio(numerator, denominator, multiplier=1):
    if numerator is None or not denominator:
        return None
    return numerator / denominator * multiplier


def _safe_sum(*values):
    present = [v for v in values if v is not None]
    return sum(present) if present else None


RATIO_MIN_PLAUSIBLE = 2
RATIO_MAX_PLAUSIBLE = 1_000


def _valid_ratio(value):
    if value is None or not (RATIO_MIN_PLAUSIBLE <= value <= RATIO_MAX_PLAUSIBLE):
        return None
    return value


def _finalize(computed, known_names):
    """Garantit qu'un nom de `known_names` absent ou invalide (None) de
    `computed` devienne un marqueur "__delete__" plutôt que d'être simplement
    omis : sans ça, une valeur calculée lors d'une exécution précédente mais
    devenue incalculable (ou invalide) aujourd'hui resterait indéfiniment
    périmée en base (aucune étape ne la retire jamais). Les clés hors
    `known_names` (KPI dynamiques nommés par société/branche/gouvernorat,
    ex: familles CGA) passent inchangées."""
    result = {k: v for k, v in computed.items() if k not in known_names}
    for name in known_names:
        value = computed.get(name)
        if value is not None:
            result[name] = value
        else:
            result[f"__delete__{name}"] = True
    return result



_CMF_COMPUTED_KPI_NAMES = (
    "Charges de prestations",
    "Charges d'acquisition et de gestion nettes",
    "Charge de sinistres",
    "Primes émises par assurance",
    "Résultat technique (TND)",
    "Primes acquises",
    "Provisions d'assurance",
    "ROA (%)",
    "ROE (%)",
    "Ratio de sinistralité (%)",
    "Ratio de frais de gestion (%)",
    "Ratio combiné (%)",
)


def _compute_cmf_kpis_for_document(kpis, sector_totals_for_year):
    """`kpis` : dict des KPI déjà stockés pour ce document (Bilan, Annexes
    12/13, résultat...). `sector_totals_for_year` : dict FTUSA de la même
    année (pour Part de marché), ou None si absent."""
    computed = {}

    charges_prestations = _safe_sum(kpis.get("Charges de prestations Vie"), kpis.get("Charges de prestations Non-Vie"))
    charges_acquisition = _safe_sum(
        kpis.get("Charges d'acquisition et de gestion nettes Vie"),
        kpis.get("Charges d'acquisition et de gestion nettes Non-Vie"),
    )
    charge_sinistres = _safe_sum(kpis.get("Charge de sinistres Vie"), kpis.get("Charge de sinistres Non-Vie"))
    primes_emises = _safe_sum(kpis.get("Primes émises Vie par assurance"), kpis.get("Primes émises Non-Vie par assurance"))
    resultat_technique = _safe_sum(kpis.get("Résultat technique Vie"), kpis.get("Résultat technique Non-Vie"))
    primes_acquises_raw = kpis.get("Primes acquises")
    primes_acquises_vie = kpis.get("Primes acquises Vie")
    primes_emises_vie   = kpis.get("Primes émises Vie par assurance")
    charge_sin_vie      = kpis.get("Charge de sinistres Vie")
    primes_acquises = _safe_sum(primes_acquises_vie, primes_acquises_raw)
    provisions_assurance = _safe_sum(
        kpis.get("Charges des provisions d'assurance vie et des autres provisions techniques"),
        kpis.get("Charges des provisions pour prestations diverses"),
    )

    if charges_prestations is not None:
        computed["Charges de prestations"] = charges_prestations
    if charges_acquisition is not None:
        computed["Charges d'acquisition et de gestion nettes"] = charges_acquisition

    charges_prestations_ratios = charges_prestations if charges_prestations is not None else kpis.get("Charges de prestations")
    charges_acquisition_ratios = charges_acquisition if charges_acquisition is not None else kpis.get("Charges d'acquisition et de gestion nettes")

    if charge_sinistres is not None:
        computed["Charge de sinistres"] = charge_sinistres
    if primes_emises is not None:
        computed["Primes émises par assurance"] = primes_emises
    if resultat_technique is not None:
        computed["Résultat technique (TND)"] = resultat_technique
    if primes_acquises is not None:
        computed["Primes acquises"] = primes_acquises
    if provisions_assurance is not None:
        computed["Provisions d'assurance"] = provisions_assurance

    abs_charge_sinistres = abs(charge_sinistres) if charge_sinistres is not None else None
    abs_charges_prestations = abs(charges_prestations_ratios) if charges_prestations_ratios is not None else None
    abs_charges_acquisition = abs(charges_acquisition_ratios) if charges_acquisition_ratios is not None else None

    computed["ROA (%)"] = _safe_ratio(kpis.get("Résultat Net"), kpis.get("Total actif"), 100)
    computed["ROE (%)"] = _safe_ratio(kpis.get("Résultat Net"), kpis.get("Capitaux propres"), 100)

    vie_charges_present = (
        kpis.get("Charges de prestations Vie") is not None
        or kpis.get("Charges d'acquisition et de gestion nettes Vie") is not None
    )
    nv_charges_present = (
        kpis.get("Charges de prestations Non-Vie") is not None
        or kpis.get("Charges d'acquisition et de gestion nettes Non-Vie") is not None
    )
    vie_primes_present = kpis.get("Primes émises Vie par assurance") is not None
    nv_primes_present = kpis.get("Primes émises Non-Vie par assurance") is not None

    vie_charges_abs = abs(kpis.get("Charges de prestations Vie") or 0) + abs(
        kpis.get("Charges d'acquisition et de gestion nettes Vie") or 0
    )
    nv_charges_abs = abs(kpis.get("Charges de prestations Non-Vie") or 0) + abs(
        kpis.get("Charges d'acquisition et de gestion nettes Non-Vie") or 0
    )
    total_charges_abs = (abs_charges_prestations or 0) + (abs_charges_acquisition or 0)

    primes_emises_ratios = primes_emises if primes_emises is not None else kpis.get("Primes émises par assurance")
    total_primes_abs = abs(primes_emises_ratios) if primes_emises_ratios else 0

    def _segment_weight(seg_charges_abs, seg_primes_abs):
        if seg_primes_abs and total_primes_abs:
            return seg_primes_abs / total_primes_abs
        if seg_charges_abs and total_charges_abs:
            return seg_charges_abs / total_charges_abs
        return 0

    vie_mismatch = (vie_charges_present != vie_primes_present) and _segment_weight(
        vie_charges_abs, abs(kpis.get("Primes émises Vie par assurance") or 0)
    ) > 0.10
    nv_mismatch = (nv_charges_present != nv_primes_present) and _segment_weight(
        nv_charges_abs, abs(kpis.get("Primes émises Non-Vie par assurance") or 0)
    ) > 0.10
    segment_mismatch = vie_mismatch or nv_mismatch

    primes_for_rsp = primes_acquises
    if (primes_acquises_vie is None and primes_emises_vie is not None
            and charge_sin_vie is not None):
        primes_for_rsp = primes_emises
    if primes_for_rsp is None:
        primes_for_rsp = primes_emises_ratios

    if segment_mismatch:
        computed["Ratio de sinistralité (%)"] = None
        computed["Ratio de frais de gestion (%)"] = None
        computed["Ratio combiné (%)"] = None
    else:
        abs_charge_sinistres_for_rsp = abs_charges_prestations if abs_charges_prestations is not None else abs_charge_sinistres
        denom_rsp = primes_emises_ratios if primes_emises_ratios is not None else primes_for_rsp
        computed["Ratio de sinistralité (%)"] = _valid_ratio(
            _safe_ratio(abs_charge_sinistres_for_rsp, denom_rsp, 100)
        )
        computed["Ratio de frais de gestion (%)"] = _valid_ratio(
            _safe_ratio(abs_charges_acquisition, primes_emises_ratios, 100)
        )
        computed["Ratio combiné (%)"] = _valid_ratio(_safe_ratio(
            _safe_sum(abs_charges_prestations, abs_charges_acquisition), primes_emises_ratios, 100
        ))

    known_names = _CMF_COMPUTED_KPI_NAMES
    if sector_totals_for_year:
        primes_pour_pdm = primes_emises if primes_emises is not None else kpis.get("Primes émises par assurance")
        computed["Part de marché (%)"] = _safe_ratio(
            primes_pour_pdm, sector_totals_for_year.get("Total Primes émises"), 100
        )
        known_names = _CMF_COMPUTED_KPI_NAMES + ("Part de marché (%)",)

    return _finalize(computed, known_names)


def compute_cmf_derived_kpis(conn):
    """Calcule les KPI dérivés pour chaque document CMF, en réutilisant le
    total sectoriel FTUSA de la même année pour "Part de marché (%)"."""
    ftusa_docs = list_documents_by_source(conn, "FTUSA")
    sector_totals_by_year = {
        annee: get_kpi_values_for_document(conn, doc_id) for doc_id, _cmf_id, _code, annee in ftusa_docs
    }

    cmf_docs = list_documents_by_source(conn, "CMF")
    saved = documents_updated = 0
    for document_id, _cmf_id, code, annee in cmf_docs:
        kpis = get_kpi_values_for_document(conn, document_id, exclude_tableaux=(TABLEAU_LABEL,))
        computed = _compute_cmf_kpis_for_document(kpis, sector_totals_by_year.get(annee))
        touched = False
        for name, value in computed.items():
            if name.startswith("__delete__"):
                delete_kpi_value(conn, document_id, TABLEAU_LABEL, name[len("__delete__"):])
            else:
                save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_nombre=value)
                saved += 1
            touched = True
        if touched:
            documents_updated += 1

    print(f"[CMF] {documents_updated} document(s) mis a jour, {saved} valeur(s) de KPI calculees")
    return {"documents_updated": documents_updated, "kpi_values_saved": saved}



_SECTOR_COMPUTED_KPI_NAMES = (
    "Part des primes émises Vie",
    "Part des primes émises Non-vie",
    "Ratio S/P",
    "Ratio de frais",
    "Ratio combiné",
    "Ratio S/P Vie",
    "Ratio de frais Vie",
    "Ratio combiné Vie",
    "Ratio S/P Non-Vie",
    "Ratio de frais Non-Vie",
    "Ratio combiné Non-Vie",
)


def _compute_sector_kpis(ftusa_kpis, ins_kpis):
    computed = {}
    total = ftusa_kpis.get("Total Primes émises")
    total_vie = ftusa_kpis.get("Primes émises Vie")
    total_non_vie = ftusa_kpis.get("Primes émises Non-Vie")
    charges_prestations = ftusa_kpis.get("Total Charges de prestations")
    charges_acquisition = ftusa_kpis.get("Total Charges d'acquisition et de gestion nettes")

    if ins_kpis:
        total_mdt = total / 1_000_000 if total is not None else None
        computed["Taux de pénétration"] = _safe_ratio(total_mdt, ins_kpis.get("Produit Interieur Brut (PIB)"), 100)
        computed["Densité de l'assurance"] = _safe_ratio(total, ins_kpis.get("Population Totale"))

    abs_charges_prestations = abs(charges_prestations) if charges_prestations is not None else None
    abs_charges_acquisition = abs(charges_acquisition) if charges_acquisition is not None else None

    computed["Part des primes émises Vie"] = _safe_ratio(total_vie, total, 100)
    computed["Part des primes émises Non-vie"] = _safe_ratio(total_non_vie, total, 100)
    computed["Ratio S/P"] = _valid_ratio(_safe_ratio(abs_charges_prestations, total, 100))
    computed["Ratio de frais"] = _valid_ratio(_safe_ratio(abs_charges_acquisition, total, 100))
    computed["Ratio combiné"] = _valid_ratio(_safe_ratio(
        _safe_sum(abs_charges_prestations, abs_charges_acquisition), total, 100
    ))

    abs_charges_prestations_vie = abs(ftusa_kpis["Charges de prestations Vie"]) if ftusa_kpis.get("Charges de prestations Vie") is not None else None
    abs_charges_acquisition_vie = abs(ftusa_kpis["Charges d'acquisition et de gestion nettes Vie"]) if ftusa_kpis.get("Charges d'acquisition et de gestion nettes Vie") is not None else None
    abs_charges_prestations_non_vie = abs(ftusa_kpis["Charges de prestations Non-Vie"]) if ftusa_kpis.get("Charges de prestations Non-Vie") is not None else None
    abs_charges_acquisition_non_vie = abs(ftusa_kpis["Charges d'acquisition et de gestion nettes Non-Vie"]) if ftusa_kpis.get("Charges d'acquisition et de gestion nettes Non-Vie") is not None else None

    computed["Ratio S/P Vie"] = _valid_ratio(_safe_ratio(abs_charges_prestations_vie, total_vie, 100))
    computed["Ratio de frais Vie"] = _valid_ratio(_safe_ratio(abs_charges_acquisition_vie, total_vie, 100))
    computed["Ratio combiné Vie"] = _valid_ratio(_safe_ratio(
        _safe_sum(abs_charges_prestations_vie, abs_charges_acquisition_vie), total_vie, 100
    ))
    computed["Ratio S/P Non-Vie"] = _valid_ratio(_safe_ratio(abs_charges_prestations_non_vie, total_non_vie, 100))
    computed["Ratio de frais Non-Vie"] = _valid_ratio(_safe_ratio(abs_charges_acquisition_non_vie, total_non_vie, 100))
    computed["Ratio combiné Non-Vie"] = _valid_ratio(_safe_ratio(
        _safe_sum(abs_charges_prestations_non_vie, abs_charges_acquisition_non_vie), total_non_vie, 100
    ))

    known_names = _SECTOR_COMPUTED_KPI_NAMES
    if ins_kpis:
        known_names = _SECTOR_COMPUTED_KPI_NAMES + ("Taux de pénétration", "Densité de l'assurance")
    return _finalize(computed, known_names)


def compute_sector_derived_kpis(conn):
    """Calcule les KPI sectoriels (marche entier) par annee, a partir des
    totaux FTUSA et des indicateurs macro INS de la meme annee."""
    ftusa_docs = list_documents_by_source(conn, "FTUSA")
    ins_docs = list_documents_by_source(conn, "INS")
    ins_kpis_by_year = {}
    for doc_id, _cmf_id, _code, annee in ins_docs:
        ins_kpis_by_year.setdefault(annee, {}).update(get_kpi_values_for_document(conn, doc_id))

    saved = years_updated = 0
    for document_id, _cmf_id, _code, annee in ftusa_docs:
        ftusa_kpis = get_kpi_values_for_document(conn, document_id)
        computed = _compute_sector_kpis(ftusa_kpis, ins_kpis_by_year.get(annee))
        touched = False
        for name, value in computed.items():
            if name.startswith("__delete__"):
                delete_kpi_value(conn, document_id, TABLEAU_LABEL, name[len("__delete__"):])
            else:
                save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_nombre=value)
                saved += 1
            touched = True
        if touched:
            years_updated += 1

    print(f"[Secteur] {years_updated} annee(s) mise(s) a jour, {saved} valeur(s) de KPI calculees")
    return {"years_updated": years_updated, "kpi_values_saved": saved}



def _company_codes_from_kpis(kpis, prefix):
    """Codes de compagnie distincts trouves dans les noms de KPI de la
    forme "{prefix} - {code}" (ex: "Nombre d'agences par assureur -
    STAR")."""
    codes = set()
    marker = f"{prefix} - "
    for name in kpis:
        if name.startswith(marker):
            codes.add(name[len(marker):])
    return codes


def _compute_cga_kpis(kpis):
    computed = {}

    per_company_total = {
        code: kpis[f"Nombre d'agences par assureur - {code}"]
        for code in _company_codes_from_kpis(kpis, "Nombre d'agences par assureur")
    }
    if per_company_total:
        total_agences = sum(per_company_total.values())
        computed["Total agences"] = total_agences

        nombre_assureurs = kpis.get("Nombre d'assureurs")
        computed["Nombre moyen d'agences par assureur"] = _safe_ratio(total_agences, nombre_assureurs)

        best_code = max(per_company_total, key=per_company_total.get)
        computed["Assurance avec le plus d'agences"] = best_code

        for code, value in per_company_total.items():
            computed[f"Part de marché réseau (%) - {code}"] = _safe_ratio(value, total_agences, 100)

    governorate_totals = {
        name.rsplit(" - ", 1)[1]: value
        for name, value in kpis.items()
        if name.startswith("Répartition des agences par gouvernorat - ")
    }
    if governorate_totals:
        region_totals = {region: 0 for region in REGIONS}
        for governorate, value in governorate_totals.items():
            region = GOVERNORATE_TO_REGION.get(governorate)
            if region:
                region_totals[region] += value
        total_marche = sum(region_totals.values())
        for region, value in region_totals.items():
            computed[f"Nombre d'agences par région - {region}"] = value
            part = _safe_ratio(value, total_marche, 100)
            if part is not None:
                computed[f"Répartition des agences par grande région - {region}"] = part
        if region_totals:
            computed["Région la plus concentrée"] = max(region_totals, key=region_totals.get)

    per_company_region_totals = {}
    marker = "Répartition des agences de la compagnie par gouvernorat - "
    for name, value in kpis.items():
        if not name.startswith(marker):
            continue
        code, governorate = name[len(marker):].rsplit(" - ", 1)
        region = GOVERNORATE_TO_REGION.get(governorate)
        if not region:
            continue
        per_company_region_totals.setdefault(code, {r: 0 for r in REGIONS})[region] += value
    for code, region_totals in per_company_region_totals.items():
        for region, value in region_totals.items():
            computed[f"Nombre d'agences de la compagnie par région - {code} - {region}"] = value

    branch_premiums = {
        name[len("Primes émises par branche - "):]: value
        for name, value in kpis.items()
        if name.startswith("Primes émises par branche - ")
    }
    if branch_premiums:
        total_premiums = sum(branch_premiums.values())
        for branch, value in branch_premiums.items():
            part = _safe_ratio(value, total_premiums, 100)
            if part is not None:
                computed[f"Part des primes émises par branche - {branch}"] = part

    known_names = ("Total agences", "Nombre moyen d'agences par assureur", "Assurance avec le plus d'agences")
    return _finalize(computed, known_names) if per_company_total else computed


def compute_cga_derived_kpis(conn):
    """Calcule les KPI dérivés du réseau d'agences (CGA), par année."""
    cga_docs = list_documents_by_source(conn, "CGA")
    saved = years_updated = 0
    for document_id, _cmf_id, _code, annee in cga_docs:
        kpis = get_kpi_values_for_document(conn, document_id)
        computed = _compute_cga_kpis(kpis)
        touched = False
        for name, value in computed.items():
            if name.startswith("__delete__"):
                delete_kpi_value(conn, document_id, TABLEAU_LABEL, name[len("__delete__"):])
            elif isinstance(value, str):
                save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_texte=value)
                saved += 1
            else:
                save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_nombre=value)
                saved += 1
            touched = True
        if touched:
            years_updated += 1

    print(f"[CGA] {years_updated} annee(s) mise(s) a jour, {saved} valeur(s) de KPI calculees")
    return {"years_updated": years_updated, "kpi_values_saved": saved}



def _compute_bvmt_kpis_for_document(kpis, code, annee, bvmt_bulletin_by_year, bvmt_fallback_actions):
    computed = {}
    cours = bvmt_bulletin_by_year.get(annee, {}).get(f"Cours de l'action - {code}")
    if cours is None:
        return computed
    computed["Cours de l'action"] = cours

    nombre_actions = kpis.get("Nombre d'actions")
    if nombre_actions is None:
        nombre_actions = bvmt_fallback_actions.get(code)
    if nombre_actions is not None:
        computed["Capitalisation Boursière"] = cours * nombre_actions / 1_000_000

    return _finalize(computed, ("Capitalisation Boursière",))


def compute_bvmt_market_kpis(conn):
    """Calcule "Cours de l'action" et "Capitalisation Boursière" (MDT) pour
    chaque document CMF d'une société cotée, à partir des bulletins BVMT
    (documents sectoriels, cmf_id NULL) et du Nombre d'actions (CMF ou repli
    BVMT, voir _compute_bvmt_kpis_for_document)."""
    bvmt_docs = list_documents_by_source(conn, "BVMT")
    bvmt_bulletin_by_year = {}
    bvmt_fallback_actions = {}
    for document_id, cmf_id, code, annee in bvmt_docs:
        kpis = get_kpi_values_for_document(conn, document_id)
        if cmf_id is None:
            bvmt_bulletin_by_year[annee] = kpis
        elif code:
            nombre_actions = kpis.get("Nombre d'actions (BVMT)")
            if nombre_actions is not None:
                bvmt_fallback_actions[code] = nombre_actions

    cmf_docs = list_documents_by_source(conn, "CMF")
    saved = documents_updated = 0
    for document_id, _cmf_id, code, annee in cmf_docs:
        kpis = get_kpi_values_for_document(conn, document_id)
        computed = _compute_bvmt_kpis_for_document(kpis, code, annee, bvmt_bulletin_by_year, bvmt_fallback_actions)
        touched = False
        for name, value in computed.items():
            if name.startswith("__delete__"):
                delete_kpi_value(conn, document_id, TABLEAU_LABEL, name[len("__delete__"):])
            else:
                save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_nombre=value)
                saved += 1
            touched = True
        if touched:
            documents_updated += 1

    print(f"[BVMT] {documents_updated} document(s) mis a jour, {saved} valeur(s) de KPI calculees")
    return {"documents_updated": documents_updated, "kpi_values_saved": saved}


def run(conn):
    cmf_stats = compute_cmf_derived_kpis(conn)
    sector_stats = compute_sector_derived_kpis(conn)
    cga_stats = compute_cga_derived_kpis(conn)
    bvmt_stats = compute_bvmt_market_kpis(conn)
    return {"cmf": cmf_stats, "sector": sector_stats, "cga": cga_stats, "bvmt": bvmt_stats}


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    from database.repository import get_connection

    _conn = get_connection()
    run(_conn)
    _conn.close()
