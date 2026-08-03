"""
Tests du Module 3 : prediction/training/
Couvre : metrics, evaluator (TimeSeriesSplit + Walk-Forward), model_selector, trainer
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import sqlite3
import pytest
import numpy as np
import pandas as pd

from prediction.training.metrics import mae, rmse, mape, all_metrics, composite_score
from prediction.training.evaluator import TimeSeriesEvaluator
from prediction.training.model_selector import ModelSelector
from prediction.models.prophet_model import ProphetModel
from prediction.models.xgboost_model import XGBoostModel


# ---- Helpers ----

def make_series(n=12, start_year=2012, trend=100.0, growth=5.0, noise=1.0):
    rng = np.random.default_rng(42)
    years = list(range(start_year, start_year + n))
    values = [trend + i * growth + rng.normal(0, noise) for i in range(n)]
    return pd.DataFrame({"annee": years, "valeur": values})


def make_sqlite_db() -> sqlite3.Connection:
    """Crée une base SQLite in-memory avec des données de test."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE sources (id INTEGER PRIMARY KEY, nom TEXT);
        CREATE TABLE cmf (id INTEGER PRIMARY KEY, code TEXT);
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY, annee INTEGER,
            source_id INTEGER, cmf_id INTEGER
        );
        CREATE TABLE kpi_values (
            id INTEGER PRIMARY KEY, document_id INTEGER,
            kpi TEXT, valeur_nombre REAL
        );

        INSERT INTO sources VALUES (1, 'CMF'), (2, 'FTUSA');
        INSERT INTO cmf VALUES (1, 'STAR');
    """)

    # 12 années de données pour STAR / Primes émises par assurance
    for i, year in enumerate(range(2013, 2025)):
        val = (80 + i * 8) * 1_000_000  # en TND → sera converti en MDT
        conn.execute(
            "INSERT INTO documents VALUES (?, ?, 1, 1)", (i + 1, year)
        )
        conn.execute(
            "INSERT INTO kpi_values VALUES (?, ?, ?, ?)",
            (i + 1, i + 1, "Primes émises par assurance", val),
        )

    conn.commit()
    return conn


# ---- Tests metrics ----

class TestMetrics:

    def test_mae_perfect(self):
        assert mae([1, 2, 3], [1, 2, 3]) == pytest.approx(0.0)

    def test_mae_simple(self):
        assert mae([0, 10], [5, 5]) == pytest.approx(5.0)

    def test_rmse_perfect(self):
        assert rmse([1, 2, 3], [1, 2, 3]) == pytest.approx(0.0)

    def test_rmse_penalises_large_errors(self):
        # RMSE > MAE quand erreurs inégales
        assert rmse([0, 10], [0, 0]) > mae([0, 10], [0, 0])

    def test_mape_returns_percentage(self):
        result = mape([100], [110])
        assert result == pytest.approx(10.0, rel=1e-3)

    def test_mape_zero_denominator(self):
        # epsilon évite la division par zéro
        result = mape([0, 100], [10, 90])
        assert np.isfinite(result)

    def test_all_metrics_keys(self):
        m = all_metrics([10, 20], [11, 19])
        assert set(m.keys()) == {"mae", "rmse", "mape"}
        assert all(v >= 0 for v in m.values())

    def test_composite_score_lower_is_better(self):
        good = composite_score(1.0, 1.0, 2.0)
        bad = composite_score(5.0, 5.0, 20.0)
        assert good < bad


# ---- Tests TimeSeriesEvaluator ----

class TestTimeSeriesEvaluator:

    def test_evaluate_prophet(self):
        ev = TimeSeriesEvaluator(n_splits=2, test_size=1, min_train=4)
        df = make_series(n=10)
        report = ev.evaluate(ProphetModel, df)
        assert report.model_name == "prophet"
        assert report.n_folds > 0
        assert report.avg_mae >= 0
        assert report.avg_mape >= 0
        assert np.isfinite(report.score)

    def test_evaluate_xgboost(self):
        ev = TimeSeriesEvaluator(n_splits=2, test_size=1, min_train=4)
        df = make_series(n=12)
        report = ev.evaluate(XGBoostModel, df)
        assert report.model_name == "xgboost"
        assert report.n_folds > 0

    def test_short_series_walk_forward_only(self):
        """< 8 points → Walk-Forward uniquement."""
        ev = TimeSeriesEvaluator(n_splits=2, test_size=1, min_train=4)
        df = make_series(n=7)
        report = ev.evaluate(ProphetModel, df)
        assert report.strategy == "walk_forward"

    def test_long_series_combined(self):
        """≥ 8 points → stratégie combinée."""
        ev = TimeSeriesEvaluator(n_splits=2, test_size=1, min_train=4)
        df = make_series(n=10)
        report = ev.evaluate(ProphetModel, df)
        assert report.strategy == "combined"

    def test_too_short_raises(self):
        ev = TimeSeriesEvaluator(n_splits=2, test_size=1, min_train=4)
        df = make_series(n=3)
        with pytest.raises(ValueError):
            ev.evaluate(ProphetModel, df)

    def test_folds_chronological(self):
        """Les années de test ne doivent jamais précéder le train."""
        ev = TimeSeriesEvaluator(n_splits=2, test_size=1, min_train=4)
        df = make_series(n=10)
        report = ev.evaluate(ProphetModel, df)
        for fold in report.folds:
            assert max(fold.train_years) < min(fold.test_years), \
                f"Fuite temporelle détectée: train={fold.train_years}, test={fold.test_years}"

    def test_to_training_metrics(self):
        ev = TimeSeriesEvaluator(n_splits=2, test_size=1, min_train=4)
        df = make_series(n=10)
        report = ev.evaluate(ProphetModel, df)
        tm = report.to_training_metrics()
        assert tm.mae == pytest.approx(report.avg_mae)
        assert tm.mape == pytest.approx(report.avg_mape)
        assert tm.model_name == "prophet"


# ---- Tests ModelSelector ----

class TestModelSelector:

    def test_select_returns_result(self):
        selector = ModelSelector()
        df = make_series(n=12)
        result = selector.select("Primes émises par assurance", df)
        assert result.winner_name in ("prophet", "xgboost")
        assert result.winner_model.is_fitted()
        assert result.winner_metrics is not None

    def test_winner_model_fitted(self):
        """Le modèle gagnant est entraîné sur la série complète."""
        selector = ModelSelector()
        df = make_series(n=12)
        result = selector.select("ROE (%)", df)
        # Le modèle doit pouvoir prédire immédiatement
        pred = result.winner_model.predict(horizon=2)
        assert len(pred.years) == 2

    def test_select_short_series_prophet_only(self):
        """Série courte → Prophet sélectionné par défaut (seul candidat)."""
        selector = ModelSelector()
        df = make_series(n=5)
        result = selector.select("Taux de pénétration", df)
        assert result.winner_name == "prophet"

    def test_all_reports_populated(self):
        """Les rapports de tous les candidats sont présents."""
        selector = ModelSelector()
        df = make_series(n=12)
        result = selector.select("Part de marché (%)", df)
        # Au moins un rapport disponible
        assert len(result.all_reports) >= 1

    def test_reason_is_string(self):
        selector = ModelSelector()
        df = make_series(n=12)
        result = selector.select("Charge de sinistres", df)
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


# ---- Test Trainer (avec DB in-memory) ----

class TestTrainer:

    def test_train_full_pipeline(self):
        """Pipeline complet DataLoader → Preprocessor → ModelSelector."""
        from prediction.training.trainer import Trainer
        conn = make_sqlite_db()
        trainer = Trainer(conn)
        result = trainer.train("Primes émises par assurance", company="STAR")

        assert result.model_name in ("prophet", "xgboost")
        assert result.model.is_fitted()
        assert result.n_history_points >= 5
        assert result.kpi == "Primes émises par assurance"
        assert result.company == "STAR"
        assert result.unit == "MDT"

    def test_train_no_data_raises(self):
        from prediction.training.trainer import Trainer
        conn = make_sqlite_db()
        trainer = Trainer(conn)
        with pytest.raises(ValueError, match="Aucune donnée"):
            trainer.train("Primes émises par assurance", company="UNKNOWN")

    def test_trained_model_can_predict(self):
        from prediction.training.trainer import Trainer
        conn = make_sqlite_db()
        trainer = Trainer(conn)
        result = trainer.train("Primes émises par assurance", company="STAR")
        pred = result.model.predict(horizon=3)
        assert len(pred.years) == 3
        assert all(np.isfinite(v) for v in pred.values)


if __name__ == "__main__":
    import subprocess
    subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=os.path.join(os.path.dirname(__file__), "..", ".."),
    )
