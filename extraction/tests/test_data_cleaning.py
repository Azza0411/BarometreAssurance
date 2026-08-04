"""Tests unitaires de la logique pure de data_cleaning.py (_flag_variation).
check_yoy_consistency() lui-même dépend d'une connexion MySQL (conn) et
n'est pas testé ici — voir api/tests/test_quality.py pour la même
convention (seules les fonctions isolables du couplage DB sont testées)."""

from extraction.data_cleaning import _flag_variation, YOY_CHECKED_KPIS


def test_stable_value_not_flagged():
    assert _flag_variation("Total actif", 100_000, 105_000) is None


def test_big_drop_flagged():
    flag = _flag_variation("Total actif", 1_000, 500_000)
    assert flag is not None
    assert flag["variation_pct"] <= -95


def test_big_jump_flagged():
    flag = _flag_variation("Total actif", 21_000_000, 1_000_000)
    assert flag is not None
    assert flag["signe_inverse"] is False


def test_sign_flip_flagged_for_balance_sheet_kpi():
    flag = _flag_variation("Capitaux propres", -50_000, 2_000_000)
    assert flag is not None
    assert flag["signe_inverse"] is True


def test_micro_values_ignored():
    # Les deux valeurs sont sous YOY_MIN_ABS : le bruit d'arrondi y domine.
    assert _flag_variation("Total actif", 50, 900) is None


def test_previous_zero_ignored():
    assert _flag_variation("Total actif", 500_000, 0) is None


def test_non_numeric_ignored():
    assert _flag_variation("Total actif", None, 500_000) is None
    assert _flag_variation("Total actif", "N/D", 500_000) is None


def test_resultat_net_excluded_from_checked_kpis():
    # Régression : un résultat qui passe du bénéfice à la perte (ou
    # l'inverse) d'une année sur l'autre est un événement business normal,
    # pas un signe d'erreur d'extraction (voir AT_TAKAFULIA 2019 : -649994
    # -> +334356, une vraie sortie de perte confirmée manuellement). Ces
    # deux KPI ne doivent donc pas figurer dans YOY_CHECKED_KPIS.
    assert "Résultat Net" not in YOY_CHECKED_KPIS
    assert "Résultat technique (TND)" not in YOY_CHECKED_KPIS


def test_resultat_net_profit_to_loss_would_have_been_a_false_positive():
    # Documente le bug corrigé : si "Résultat Net" était encore vérifié,
    # cette transition légitime (TUNIS_RE 2018) aurait été signalée à tort.
    flag = _flag_variation("Résultat Net", -17_102_916, 12_285_742)
    assert flag is not None and flag["signe_inverse"] is True
    assert "Résultat Net" not in YOY_CHECKED_KPIS
