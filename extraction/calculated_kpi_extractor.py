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


# ------------------------------------------------------------------ #
# Par document CMF (société x année)
# ------------------------------------------------------------------ #

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
    primes_acquises_raw = kpis.get("Primes acquises")   # valeur brute Non-Vie extraite du PDF
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

    # Les tableaux Annexe 12/13 notent les charges en negatif (deductions
    # dans un compte de resultat), alors que le resultat_kpi_extractor
    # (Charge de sinistres) les note en positif : abs() rend le ratio
    # toujours positif quelle que soit la convention de signe de la source,
    # comme attendu pour un ratio de sinistralite/frais/combine.
    abs_charge_sinistres = abs(charge_sinistres) if charge_sinistres is not None else None
    abs_charges_prestations = abs(charges_prestations) if charges_prestations is not None else None
    abs_charges_acquisition = abs(charges_acquisition) if charges_acquisition is not None else None

    computed["ROA (%)"] = _safe_ratio(kpis.get("Résultat Net"), kpis.get("Total actif"), 100)
    computed["ROE (%)"] = _safe_ratio(kpis.get("Résultat Net"), kpis.get("Capitaux propres"), 100)
    # RSP : dénominateur = primes_acquises si complet (Vie+NV).
    # Si primes_acquises_vie manque mais que les charges sinistres incluent la Vie
    # (ex. STAR : Annexe 12 publie "Primes émises" seulement, pas "Primes acquises"),
    # utiliser primes_emises (Vie+NV) pour aligner numérateur et dénominateur.
    primes_for_rsp = primes_acquises
    if (primes_acquises_vie is None and primes_emises_vie is not None
            and charge_sin_vie is not None):
        primes_for_rsp = primes_emises  # Vie+NV déjà correctement sommés
    computed["Ratio de sinistralité (%)"] = _safe_ratio(abs_charge_sinistres, primes_for_rsp, 100)
    computed["Ratio de frais de gestion (%)"] = _safe_ratio(abs_charges_acquisition, primes_emises, 100)

    # Ratio combiné : valide uniquement si numérateur et dénominateur couvrent
    # les mêmes segments Vie / Non-Vie.  Si les charges Vie représentent plus
    # de 10 % du total des charges connues mais que les primes Vie sont
    # absentes, le ratio serait faussé (numérateur Vie + Non-Vie vs
    # dénominateur Non-Vie seulement).
    # Ex: ASTREE — charges Vie 163 M vs primes Non-Vie 176 M → 116 % erroné.
    vie_charges_abs = abs(kpis.get("Charges de prestations Vie") or 0) + abs(
        kpis.get("Charges d'acquisition et de gestion nettes Vie") or 0
    )
    total_charges_abs = (abs_charges_prestations or 0) + (abs_charges_acquisition or 0)
    vie_primes_missing = kpis.get("Primes émises Vie par assurance") is None
    vie_weight = vie_charges_abs / total_charges_abs if total_charges_abs else 0
    ratio_combine_valid = not (vie_primes_missing and vie_weight > 0.10)
    if ratio_combine_valid:
        computed["Ratio combiné (%)"] = _safe_ratio(
            _safe_sum(abs_charges_prestations, abs_charges_acquisition), primes_emises, 100
        )
    else:
        # Marque explicitement ce ratio comme invalide pour qu'il soit effacé
        # de la base (les anciennes valeurs erronées ne doivent pas rester).
        computed["__delete__Ratio combiné (%)"] = True

    if sector_totals_for_year:
        computed["Part de marché (%)"] = _safe_ratio(
            primes_emises, sector_totals_for_year.get("Total Primes émises"), 100
        )

    return {
        name: value
        for name, value in computed.items()
        if name.startswith("__delete__") or value is not None
    }


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
        kpis = get_kpi_values_for_document(conn, document_id)
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


# ------------------------------------------------------------------ #
# Par annee (secteur, FTUSA x INS)
# ------------------------------------------------------------------ #

def _compute_sector_kpis(ftusa_kpis, ins_kpis):
    computed = {}
    total = ftusa_kpis.get("Total Primes émises")
    total_vie = ftusa_kpis.get("Primes émises Vie")
    total_non_vie = ftusa_kpis.get("Primes émises Non-Vie")
    charges_prestations = ftusa_kpis.get("Total Charges de prestations")
    charges_acquisition = ftusa_kpis.get("Total Charges d'acquisition et de gestion nettes")

    if ins_kpis:
        # Le PIB (INS) est stocké en MDT (millions de TND) alors que les
        # primes émises (FTUSA) sont en TND brut -> conversion en MDT avant
        # le ratio, sinon le taux de pénétration ressort ~1 000 000x trop
        # grand (bug constaté : 2 390 847% au lieu de ~2,4%). La Population
        # Totale (INS), elle, est un effectif brut (~11,8M) directement
        # comparable aux primes en TND -> pas de conversion pour la densité.
        total_mdt = total / 1_000_000 if total is not None else None
        computed["Taux de pénétration"] = _safe_ratio(total_mdt, ins_kpis.get("Produit Interieur Brut (PIB)"), 100)
        computed["Densité de l'assurance"] = _safe_ratio(total, ins_kpis.get("Population Totale"))

    # FTUSA note ces charges en negatif (voir ftusa_kpi_extractor) : abs()
    # pour un ratio toujours positif, meme raison que compute_cmf_derived_kpis.
    abs_charges_prestations = abs(charges_prestations) if charges_prestations is not None else None
    abs_charges_acquisition = abs(charges_acquisition) if charges_acquisition is not None else None

    computed["Part des primes émises Vie"] = _safe_ratio(total_vie, total, 100)
    computed["Part des primes émises Non-vie"] = _safe_ratio(total_non_vie, total, 100)
    computed["Ratio S/P"] = _safe_ratio(abs_charges_prestations, total, 100)
    computed["Ratio de frais"] = _safe_ratio(abs_charges_acquisition, total, 100)
    computed["Ratio combiné"] = _safe_ratio(
        _safe_sum(abs_charges_prestations, abs_charges_acquisition), total, 100
    )

    # Meme decomposition Vie / Non-Vie que ci-dessus, mais par segment (les 3
    # ratios ci-dessus melangent Vie+Non-Vie) : necessaire pour le tableau de
    # bord "Aperçu marché" (onglet Ratios techniques, par segment).
    abs_charges_prestations_vie = abs(ftusa_kpis["Charges de prestations Vie"]) if ftusa_kpis.get("Charges de prestations Vie") is not None else None
    abs_charges_acquisition_vie = abs(ftusa_kpis["Charges d'acquisition et de gestion nettes Vie"]) if ftusa_kpis.get("Charges d'acquisition et de gestion nettes Vie") is not None else None
    abs_charges_prestations_non_vie = abs(ftusa_kpis["Charges de prestations Non-Vie"]) if ftusa_kpis.get("Charges de prestations Non-Vie") is not None else None
    abs_charges_acquisition_non_vie = abs(ftusa_kpis["Charges d'acquisition et de gestion nettes Non-Vie"]) if ftusa_kpis.get("Charges d'acquisition et de gestion nettes Non-Vie") is not None else None

    computed["Ratio S/P Vie"] = _safe_ratio(abs_charges_prestations_vie, total_vie, 100)
    computed["Ratio de frais Vie"] = _safe_ratio(abs_charges_acquisition_vie, total_vie, 100)
    computed["Ratio combiné Vie"] = _safe_ratio(
        _safe_sum(abs_charges_prestations_vie, abs_charges_acquisition_vie), total_vie, 100
    )
    computed["Ratio S/P Non-Vie"] = _safe_ratio(abs_charges_prestations_non_vie, total_non_vie, 100)
    computed["Ratio de frais Non-Vie"] = _safe_ratio(abs_charges_acquisition_non_vie, total_non_vie, 100)
    computed["Ratio combiné Non-Vie"] = _safe_ratio(
        _safe_sum(abs_charges_prestations_non_vie, abs_charges_acquisition_non_vie), total_non_vie, 100
    )

    return {name: value for name, value in computed.items() if value is not None}


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
        for name, value in computed.items():
            save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_nombre=value)
            saved += 1
        if computed:
            years_updated += 1

    print(f"[Secteur] {years_updated} annee(s) mise(s) a jour, {saved} valeur(s) de KPI calculees")
    return {"years_updated": years_updated, "kpi_values_saved": saved}


# ------------------------------------------------------------------ #
# Par annee (reseau d'agences, CGA)
# ------------------------------------------------------------------ #

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
            if total_marche:
                computed[f"Répartition des agences par grande région - {region}"] = value / total_marche * 100
        if region_totals:
            computed["Région la plus concentrée"] = max(region_totals, key=region_totals.get)

    # Les noms sont de la forme "{prefix} - {code} - {gouvernorat}" (deux
    # segments apres le prefixe) : on scinde sur le DERNIER " - " pour
    # separer le gouvernorat du code (le code ne contient jamais " - ").
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
        if total_premiums:
            for branch, value in branch_premiums.items():
                computed[f"Part des primes émises par branche - {branch}"] = value / total_premiums * 100

    return computed


def compute_cga_derived_kpis(conn):
    """Calcule les KPI dérivés du réseau d'agences (CGA), par année."""
    cga_docs = list_documents_by_source(conn, "CGA")
    saved = years_updated = 0
    for document_id, _cmf_id, _code, annee in cga_docs:
        kpis = get_kpi_values_for_document(conn, document_id)
        computed = _compute_cga_kpis(kpis)
        for name, value in computed.items():
            if isinstance(value, str):
                save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_texte=value)
            else:
                save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_nombre=value)
            saved += 1
        if computed:
            years_updated += 1

    print(f"[CGA] {years_updated} annee(s) mise(s) a jour, {saved} valeur(s) de KPI calculees")
    return {"years_updated": years_updated, "kpi_values_saved": saved}


# ------------------------------------------------------------------ #
# Par document CMF (société x année) : Cours de l'action / Capitalisation
# Boursière (BVMT)
# ------------------------------------------------------------------ #

def _compute_bvmt_kpis_for_document(kpis, code, annee, bvmt_bulletin_by_year, bvmt_fallback_actions):
    computed = {}
    cours = bvmt_bulletin_by_year.get(annee, {}).get(f"Cours de l'action - {code}")
    if cours is None:
        return computed
    computed["Cours de l'action"] = cours

    # Priorite au Nombre d'actions de l'annee (source CMF, tres faible
    # couverture ~4% -> voir CAS_PARTICULIERS_PRESENTATION.md), repli sur le
    # nombre de titres emis ACTUEL (BVMT, une seule valeur appliquee a
    # toutes les annees par approximation -> voir CAS_PARTICULIERS_BVMT.md).
    nombre_actions = kpis.get("Nombre d'actions")
    if nombre_actions is None:
        nombre_actions = bvmt_fallback_actions.get(code)
    if nombre_actions is not None:
        computed["Capitalisation Boursière"] = cours * nombre_actions / 1_000_000

    return computed


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
        for name, value in computed.items():
            save_kpi_value(conn, document_id, TABLEAU_LABEL, name, valeur_nombre=value)
            saved += 1
        if computed:
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
