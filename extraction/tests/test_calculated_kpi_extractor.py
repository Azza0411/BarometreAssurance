"""Tests unitaires des KPI calculés (extraction/calculated_kpi_extractor.py) :
opère uniquement sur des dicts {kpi: valeur} déjà en base, aucune dépendance
PDF/DB — pas de fixtures conftest nécessaires ici."""

from extraction.calculated_kpi_extractor import (
    RATIO_MAX_PLAUSIBLE,
    RATIO_MIN_PLAUSIBLE,
    _compute_bvmt_kpis_for_document,
    _compute_cga_kpis,
    _compute_cmf_kpis_for_document,
    _compute_sector_kpis,
    _finalize,
    _safe_ratio,
    _safe_sum,
    _valid_ratio,
)


# ─── _safe_ratio / _safe_sum ────────────────────────────────────────────────

def test_safe_ratio_none_numerator():
    assert _safe_ratio(None, 100) is None


def test_safe_ratio_none_or_zero_denominator():
    assert _safe_ratio(50, None) is None
    assert _safe_ratio(50, 0) is None


def test_safe_ratio_normal():
    assert _safe_ratio(50, 200, 100) == 25.0


def test_safe_sum_all_none():
    assert _safe_sum(None, None) is None


def test_safe_sum_partial():
    assert _safe_sum(10, None, 5) == 15


# ─── _valid_ratio ────────────────────────────────────────────────────────────

def test_valid_ratio_none_passthrough():
    assert _valid_ratio(None) is None


def test_valid_ratio_rejects_too_small():
    # ex: ligne de sous-total captée à la place du total (ASTREE/AMI, voir
    # CAS_PARTICULIERS_CALCULS.md)
    assert _valid_ratio(RATIO_MIN_PLAUSIBLE - 0.1) is None


def test_valid_ratio_rejects_too_large():
    # ex: numéro de page capturé à la place du vrai montant
    assert _valid_ratio(RATIO_MAX_PLAUSIBLE + 1) is None


def test_valid_ratio_accepts_in_range():
    assert _valid_ratio(72.4) == 72.4
    assert _valid_ratio(RATIO_MIN_PLAUSIBLE) == RATIO_MIN_PLAUSIBLE
    assert _valid_ratio(RATIO_MAX_PLAUSIBLE) == RATIO_MAX_PLAUSIBLE


# ─── _finalize ───────────────────────────────────────────────────────────────

def test_finalize_keeps_present_value():
    result = _finalize({"A": 10.0}, ("A", "B"))
    assert result == {"A": 10.0, "__delete__B": True}


def test_finalize_marks_missing_as_delete():
    result = _finalize({}, ("A",))
    assert result == {"__delete__A": True}


def test_finalize_passes_through_unrelated_keys():
    # ex: KPI dynamiques nommés par société (familles CGA), non couverts par
    # known_names — ne doivent jamais être marqués __delete__ par erreur.
    result = _finalize({"Part de marché réseau (%) - STAR": 12.0}, ("A",))
    assert result == {"Part de marché réseau (%) - STAR": 12.0, "__delete__A": True}


# ─── _compute_cmf_kpis_for_document ─────────────────────────────────────────

def _base_kpis(**overrides):
    kpis = {
        "Charges de prestations Vie": -1000.0,
        "Charges de prestations Non-Vie": -2000.0,
        "Charges d'acquisition et de gestion nettes Vie": -300.0,
        "Charges d'acquisition et de gestion nettes Non-Vie": -600.0,
        "Charge de sinistres Vie": 1000.0,
        "Charge de sinistres Non-Vie": 2000.0,
        "Primes émises Vie par assurance": 5000.0,
        "Primes émises Non-Vie par assurance": 5000.0,
        "Primes acquises Vie": 5000.0,
        "Primes acquises": 5000.0,
        "Résultat Net": 500.0,
        "Total actif": 50000.0,
        "Capitaux propres": 10000.0,
    }
    kpis.update(overrides)
    return kpis


def test_cmf_normal_case_computes_all_ratios():
    computed = _compute_cmf_kpis_for_document(_base_kpis(), None)
    assert computed["Ratio combiné (%)"] == (3000.0 + 900.0) / 10000.0 * 100
    assert computed["Ratio de sinistralité (%)"] == 3000.0 / 10000.0 * 100
    assert computed["Ratio de frais de gestion (%)"] == 900.0 / 10000.0 * 100
    assert computed["ROA (%)"] == 500.0 / 50000.0 * 100
    assert computed["ROE (%)"] == 500.0 / 10000.0 * 100


def test_cmf_segment_mismatch_invalidates_rc_rsp_rf():
    # Charges Vie présentes mais Primes émises Vie absentes (> 10% du poids
    # des charges) : RC, RSP et RF doivent tous être invalidés (voir cas
    # BIAT documenté dans CAS_PARTICULIERS_CALCULS.md).
    kpis = _base_kpis(**{"Primes émises Vie par assurance": None, "Primes acquises Vie": None})
    computed = _compute_cmf_kpis_for_document(kpis, None)
    assert computed["__delete__Ratio combiné (%)"] is True
    assert computed["__delete__Ratio de sinistralité (%)"] is True
    assert computed["__delete__Ratio de frais de gestion (%)"] is True


def test_cmf_implausible_ratio_rejected():
    # Primes emises quasi nulles -> ratio combine hors bornes plausibles.
    kpis = _base_kpis(**{
        "Primes émises Vie par assurance": 1.0,
        "Primes émises Non-Vie par assurance": 1.0,
    })
    computed = _compute_cmf_kpis_for_document(kpis, None)
    assert computed["__delete__Ratio combiné (%)"] is True


def test_cmf_part_de_marche_only_when_sector_totals_present():
    computed_without = _compute_cmf_kpis_for_document(_base_kpis(), None)
    assert "Part de marché (%)" not in computed_without
    assert "__delete__Part de marché (%)" not in computed_without

    computed_with = _compute_cmf_kpis_for_document(
        _base_kpis(), {"Total Primes émises": 100000.0}
    )
    assert computed_with["Part de marché (%)"] == 10000.0 / 100000.0 * 100


# ─── _compute_sector_kpis ────────────────────────────────────────────────────

def test_sector_penetration_and_densite_require_ins():
    ftusa_kpis = {"Total Primes émises": 2_000_000_000.0}
    computed_without_ins = _compute_sector_kpis(ftusa_kpis, None)
    assert "Taux de pénétration" not in computed_without_ins

    ins_kpis = {"Produit Interieur Brut (PIB)": 100_000.0, "Population Totale": 12_000_000.0}
    computed_with_ins = _compute_sector_kpis(ftusa_kpis, ins_kpis)
    # PIB en MDT, primes en TND brut -> conversion en MDT avant le ratio.
    assert computed_with_ins["Taux de pénétration"] == (2_000_000_000.0 / 1_000_000) / 100_000.0 * 100


def test_sector_ratio_combine_uses_abs_charges():
    ftusa_kpis = {
        "Total Primes émises": 1000.0,
        "Total Charges de prestations": -600.0,
        "Total Charges d'acquisition et de gestion nettes": -100.0,
    }
    computed = _compute_sector_kpis(ftusa_kpis, None)
    assert computed["Ratio combiné"] == 70.0


# ─── _compute_cga_kpis ───────────────────────────────────────────────────────

def test_cga_total_agences_and_part_de_marche_reseau():
    kpis = {
        "Nombre d'agences par assureur - STAR": 40,
        "Nombre d'agences par assureur - COMAR": 60,
        "Nombre d'assureurs": 2,
    }
    computed = _compute_cga_kpis(kpis)
    assert computed["Total agences"] == 100
    assert computed["Nombre moyen d'agences par assureur"] == 50.0
    assert computed["Assurance avec le plus d'agences"] == "COMAR"
    assert computed["Part de marché réseau (%) - STAR"] == 40.0
    assert computed["Part de marché réseau (%) - COMAR"] == 60.0


def test_cga_empty_kpis_returns_empty():
    assert _compute_cga_kpis({}) == {}


# ─── _compute_bvmt_kpis_for_document ────────────────────────────────────────

def test_bvmt_normal_case_computes_cours_and_capitalisation():
    bulletin = {2024: {"Cours de l'action - STAR": 12.5}}
    computed = _compute_bvmt_kpis_for_document(
        {"Nombre d'actions": 40_000_000}, "STAR", 2024, bulletin, {}
    )
    assert computed["Cours de l'action"] == 12.5
    assert computed["Capitalisation Boursière"] == 12.5 * 40_000_000 / 1_000_000


def test_bvmt_falls_back_to_bvmt_share_count_when_cmf_missing():
    bulletin = {2024: {"Cours de l'action - STAR": 12.5}}
    computed = _compute_bvmt_kpis_for_document(
        {}, "STAR", 2024, bulletin, {"STAR": 40_000_000}
    )
    assert computed["Capitalisation Boursière"] == 12.5 * 40_000_000 / 1_000_000


def test_bvmt_no_bulletin_for_year_returns_empty():
    # Pas coté / bulletin de cette annee pas encore scrape -> ni Cours ni
    # Capitalisation ne doivent être marqués __delete__ (voir commentaire de
    # la fonction : evite un DELETE inutile pour chaque societe non cotee,
    # sur chaque document, a chaque execution).
    computed = _compute_bvmt_kpis_for_document({}, "AMI", 2024, {}, {})
    assert computed == {}


def test_bvmt_cours_present_but_no_share_count_invalidates_capitalisation():
    bulletin = {2024: {"Cours de l'action - STAR": 12.5}}
    computed = _compute_bvmt_kpis_for_document({}, "STAR", 2024, bulletin, {})
    assert computed["Cours de l'action"] == 12.5
    assert computed["__delete__Capitalisation Boursière"] is True
