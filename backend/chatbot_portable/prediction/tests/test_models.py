"""
Tests du Module 2 : prediction/models/
Couvre : ProphetModel, XGBoostModel, ModelFactory
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import sqlite3
import pytest
import pandas as pd
import numpy as np

from prediction.models.base_model import PredictionOutput, TrainingMetrics
from prediction.models.prophet_model import ProphetModel
from prediction.models.xgboost_model import XGBoostModel
from prediction.models.model_factory import ModelFactory


# ---- Données de test synthétiques ----

def make_series(n=12, start_year=2012, trend=50.0, noise=2.0) -> pd.DataFrame:
    """Série temporelle synthétique avec tendance linéaire + bruit."""
    years = list(range(start_year, start_year + n))
    values = [trend + i * 5 + np.random.normal(0, noise) for i in range(n)]
    return pd.DataFrame({"annee": years, "valeur": values})


def make_short_series(n=6) -> pd.DataFrame:
    """Série courte (limite minimale)."""
    return make_series(n=n)


# ---- Tests ProphetModel ----

class TestProphetModel:

    def test_instantiation(self):
        m = ProphetModel()
        assert m.name == "prophet"
        assert not m.is_fitted()

    def test_fit_predict(self):
        m = ProphetModel()
        df = make_series(n=10)
        m.fit(df)
        assert m.is_fitted()

        out = m.predict(horizon=3)
        assert isinstance(out, PredictionOutput)
        assert len(out.years) == 3
        assert len(out.values) == 3
        assert len(out.lower_bound) == 3
        assert len(out.upper_bound) == 3
        assert out.model_name == "prophet"
        assert out.confidence_level == 0.80

        # Intervalles cohérents
        for lo, val, hi in zip(out.lower_bound, out.values, out.upper_bound):
            assert lo <= val <= hi, f"Interval incohérent: {lo} <= {val} <= {hi}"

    def test_future_years_correct(self):
        m = ProphetModel()
        df = make_series(n=10, start_year=2012)
        m.fit(df)
        out = m.predict(horizon=3)
        assert out.years == [2022, 2023, 2024]

    def test_fitted_values(self):
        m = ProphetModel()
        df = make_series(n=10)
        m.fit(df)
        fitted = m.get_fitted_values()
        assert "annee" in fitted.columns
        assert "valeur_reelle" in fitted.columns
        assert "valeur_ajustee" in fitted.columns
        assert len(fitted) == 10

    def test_predict_without_fit_raises(self):
        m = ProphetModel()
        with pytest.raises(RuntimeError):
            m.predict(3)

    def test_negative_values_additive_mode(self):
        """Valeurs négatives → Prophet passe en mode additif automatiquement."""
        m = ProphetModel()
        df = pd.DataFrame({
            "annee": list(range(2012, 2022)),
            "valeur": [-5, -3, 2, 5, 8, -1, 3, 7, 10, 15]
        })
        m.fit(df)  # ne doit pas lever d'exception
        assert m.is_fitted()

    def test_decomposition(self):
        m = ProphetModel()
        df = make_series(n=10)
        m.fit(df)
        m.predict(3)
        decomp = m.get_decomposition()
        assert "trend" in decomp
        assert len(decomp["trend"]) == 3

    def test_short_series(self):
        m = ProphetModel()
        df = make_short_series(n=6)
        m.fit(df)
        out = m.predict(2)
        assert len(out.years) == 2


# ---- Tests XGBoostModel ----

class TestXGBoostModel:

    def test_instantiation(self):
        m = XGBoostModel()
        assert m.name == "xgboost"
        assert not m.is_fitted()

    def test_fit_predict(self):
        m = XGBoostModel()
        df = make_series(n=12)
        m.fit(df)
        assert m.is_fitted()

        out = m.predict(horizon=3)
        assert isinstance(out, PredictionOutput)
        assert len(out.years) == 3
        assert len(out.values) == 3
        assert out.model_name == "xgboost"
        assert out.confidence_level == 0.80

    def test_future_years_correct(self):
        m = XGBoostModel()
        df = make_series(n=10, start_year=2013)
        m.fit(df)
        out = m.predict(horizon=2)
        assert out.years == [2023, 2024]

    def test_intervals_monotone(self):
        """lower ≤ value ≤ upper pour chaque prévision."""
        m = XGBoostModel()
        df = make_series(n=12)
        m.fit(df)
        out = m.predict(horizon=3)
        for lo, val, hi in zip(out.lower_bound, out.values, out.upper_bound):
            assert lo <= val <= hi, f"Interval incohérent: {lo} <= {val} <= {hi}"

    def test_fitted_values(self):
        m = XGBoostModel()
        df = make_series(n=12)
        m.fit(df)
        fitted = m.get_fitted_values()
        assert len(fitted) > 0
        assert "valeur_reelle" in fitted.columns
        assert "valeur_ajustee" in fitted.columns

    def test_feature_importances(self):
        m = XGBoostModel()
        df = make_series(n=12)
        m.fit(df)
        imp = m.get_feature_importances()
        assert len(imp) == 8  # 8 features définies dans FeatureEngineer
        assert all(v >= 0 for v in imp.values())
        # La somme doit être proche de 1 (gain normalisé)
        total = sum(imp.values())
        assert 0.99 <= total <= 1.01, f"Somme importances = {total}"

    def test_predict_without_fit_raises(self):
        m = XGBoostModel()
        with pytest.raises(RuntimeError):
            m.predict(3)

    def test_too_short_raises(self):
        """Série trop courte pour construire les lags → ValueError."""
        m = XGBoostModel()
        df = pd.DataFrame({"annee": [2020, 2021], "valeur": [100.0, 110.0]})
        with pytest.raises(ValueError):
            m.fit(df)


# ---- Tests ModelFactory ----

class TestModelFactory:

    def test_create_prophet(self):
        f = ModelFactory()
        m = f.create_model("prophet")
        assert isinstance(m, ProphetModel)

    def test_create_xgboost(self):
        f = ModelFactory()
        m = f.create_model("xgboost")
        assert isinstance(m, XGBoostModel)

    def test_unknown_model_raises(self):
        f = ModelFactory()
        with pytest.raises(ValueError):
            f.create_model("lstm")

    def test_candidates_short_series(self):
        f = ModelFactory()
        candidates = f.get_candidate_models("Primes émises par assurance", n_points=5)
        assert candidates == ["prophet"]

    def test_candidates_prophet_preferred(self):
        f = ModelFactory()
        candidates = f.get_candidate_models("Total Primes émises", n_points=12)
        assert candidates[0] == "prophet"
        assert "xgboost" in candidates

    def test_candidates_xgboost_preferred(self):
        f = ModelFactory()
        candidates = f.get_candidate_models("ROE (%)", n_points=10)
        assert candidates[0] == "xgboost"

    def test_create_explainer_prophet(self):
        f = ModelFactory()
        df = make_series(n=10)
        m = ProphetModel()
        m.fit(df)
        # L'explaineur ne doit pas lever d'exception à l'instanciation
        # (la création SHAP/Prophet est lazy)
        try:
            explainer = f.create_explainer(m)
            from prediction.explainability.prophet_explainer import ProphetExplainer
            assert isinstance(explainer, ProphetExplainer)
        except ImportError:
            pytest.skip("Module explainability pas encore implémenté")

    def test_create_explainer_xgboost(self):
        f = ModelFactory()
        df = make_series(n=12)
        m = XGBoostModel()
        m.fit(df)
        try:
            explainer = f.create_explainer(m)
            from prediction.explainability.shap_explainer import ShapExplainer
            assert isinstance(explainer, ShapExplainer)
        except ImportError:
            pytest.skip("Module explainability pas encore implémenté")

    def test_list_models(self):
        f = ModelFactory()
        models = f.list_available_models()
        assert "prophet" in models
        assert "xgboost" in models


if __name__ == "__main__":
    # Exécution directe pour test rapide
    import subprocess
    subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short",
         "--ignore-glob=*test_explainer*"],
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
    )
