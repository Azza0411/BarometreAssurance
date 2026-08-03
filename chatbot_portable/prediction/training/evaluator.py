"""
Évaluation chronologique des modèles.

Deux stratégies de validation :
1. TimeSeriesSplit   — plusieurs folds, rapide, bonne estimation moyenne
2. Walk-Forward      — simule le déploiement réel (entraîne sur tout le passé,
                       prédit 1 an en avant, glisse)

La combinaison des deux donne un score robuste sur des séries courtes (5-15 pts).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from prediction.models.base_model import BaseModel, TrainingMetrics
from prediction.training.metrics import all_metrics, composite_score

logger = logging.getLogger(__name__)


@dataclass
class FoldResult:
    """Résultat d'un fold de validation."""
    fold_idx: int
    train_years: list[int]
    test_years: list[int]
    y_true: list[float]
    y_pred: list[float]
    mae: float
    rmse: float
    mape: float


@dataclass
class EvaluationReport:
    """Rapport complet d'évaluation d'un modèle."""
    model_name: str
    strategy: str           # "timeseries_split" | "walk_forward" | "combined"
    folds: list[FoldResult]
    avg_mae: float
    avg_rmse: float
    avg_mape: float
    score: float            # score composite (plus bas = meilleur)
    n_folds: int
    warnings: list[str] = field(default_factory=list)

    def to_training_metrics(self) -> TrainingMetrics:
        return TrainingMetrics(
            mae=self.avg_mae,
            rmse=self.avg_rmse,
            mape=self.avg_mape,
            n_folds=self.n_folds,
            model_name=self.model_name,
            details={
                "strategy": self.strategy,
                "score": self.score,
                "warnings": self.warnings,
            },
        )


class TimeSeriesEvaluator:
    """
    Évalue un modèle par validation chronologique.

    La stratégie choisie dépend du nombre de points :
    - < 8 points  → Walk-Forward uniquement (pas assez pour TimeSeriesSplit)
    - ≥ 8 points  → Combined (TimeSeriesSplit + Walk-Forward, moyennés)

    Usage:
        evaluator = TimeSeriesEvaluator(n_splits=3, test_size=2)
        report = evaluator.evaluate(model_class, df)
    """

    def __init__(self, n_splits: int = 3, test_size: int = 2, min_train: int = 4):
        """
        Args:
            n_splits: nombre de folds TimeSeriesSplit
            test_size: taille de la fenêtre de test (années)
            min_train: taille minimale du train set
        """
        self._n_splits = n_splits
        self._test_size = test_size
        self._min_train = min_train

    def evaluate(
        self,
        model_class: type[BaseModel],
        df: pd.DataFrame,
    ) -> EvaluationReport:
        """
        Évalue un modèle sur la série temporelle.

        Args:
            model_class: classe du modèle (non instancié)
            df: DataFrame [annee, valeur] complet

        Returns:
            EvaluationReport avec métriques agrégées
        """
        df = df.sort_values("annee").reset_index(drop=True)
        n = len(df)

        if n < self._min_train + self._test_size:
            raise ValueError(
                f"Série trop courte pour l'évaluation : {n} points. "
                f"Minimum requis : {self._min_train + self._test_size}."
            )

        warnings = []

        if n < 8:
            folds = self._walk_forward(model_class, df)
            strategy = "walk_forward"
            if not folds:
                raise ValueError("Walk-forward n'a produit aucun fold valide.")
        else:
            ts_folds = self._timeseries_split(model_class, df)
            wf_folds = self._walk_forward(model_class, df)
            folds = ts_folds + wf_folds
            strategy = "combined"
            if not ts_folds:
                warnings.append("TimeSeriesSplit n'a produit aucun fold valide.")
            if not wf_folds:
                warnings.append("Walk-Forward n'a produit aucun fold valide.")

        if not folds:
            raise ValueError("Aucun fold valide produit lors de l'évaluation.")

        maes = [f.mae for f in folds]
        rmses = [f.rmse for f in folds]
        mapes = [f.mape for f in folds]

        avg_mae = float(np.mean(maes))
        avg_rmse = float(np.mean(rmses))
        avg_mape = float(np.mean(mapes))
        score = composite_score(avg_mae, avg_rmse, avg_mape)

        model_name = model_class().name

        logger.info(
            f"Évaluation {model_name} ({strategy}): "
            f"MAE={avg_mae:.3f} RMSE={avg_rmse:.3f} MAPE={avg_mape:.2f}% "
            f"score={score:.4f} ({len(folds)} folds)"
        )

        return EvaluationReport(
            model_name=model_name,
            strategy=strategy,
            folds=folds,
            avg_mae=avg_mae,
            avg_rmse=avg_rmse,
            avg_mape=avg_mape,
            score=score,
            n_folds=len(folds),
            warnings=warnings,
        )

    def _timeseries_split(
        self, model_class: type[BaseModel], df: pd.DataFrame
    ) -> list[FoldResult]:
        """
        TimeSeriesSplit : découpe la série en folds chronologiques.
        Train : [0..split_end], Test : [split_end..split_end+test_size]
        """
        n = len(df)
        folds = []
        step = max(1, (n - self._min_train - self._test_size) // self._n_splits)

        for i in range(self._n_splits):
            train_end = self._min_train + i * step
            test_end = train_end + self._test_size

            if test_end > n:
                break

            train_df = df.iloc[:train_end].copy()
            test_df = df.iloc[train_end:test_end].copy()

            fold = self._run_fold(
                model_class, train_df, test_df, fold_idx=i, prefix="ts"
            )
            if fold:
                folds.append(fold)

        return folds

    def _walk_forward(
        self, model_class: type[BaseModel], df: pd.DataFrame
    ) -> list[FoldResult]:
        """
        Walk-Forward : entraîne sur [0..t], prédit t+1, avance d'un pas.
        Simule exactement le déploiement en production.
        """
        n = len(df)
        folds = []
        start_test = self._min_train

        for t in range(start_test, n - 1):
            train_df = df.iloc[:t].copy()
            test_df = df.iloc[t:t + 1].copy()

            fold = self._run_fold(
                model_class, train_df, test_df,
                fold_idx=t - start_test, prefix="wf"
            )
            if fold:
                folds.append(fold)

        return folds

    def _run_fold(
        self,
        model_class: type[BaseModel],
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        fold_idx: int,
        prefix: str,
    ) -> FoldResult | None:
        """Entraîne et évalue sur un fold. Retourne None si erreur."""
        try:
            model = model_class()
            model.fit(train_df)
            out = model.predict(horizon=len(test_df))

            y_true = test_df["valeur"].tolist()
            y_pred = out.values[:len(y_true)]

            m = all_metrics(y_true, y_pred)

            return FoldResult(
                fold_idx=fold_idx,
                train_years=train_df["annee"].tolist(),
                test_years=test_df["annee"].tolist(),
                y_true=y_true,
                y_pred=y_pred,
                mae=m["mae"],
                rmse=m["rmse"],
                mape=m["mape"],
            )

        except Exception as exc:
            logger.warning(
                f"Fold {prefix}-{fold_idx} échoué "
                f"({model_class.__name__}): {exc}"
            )
            return None
