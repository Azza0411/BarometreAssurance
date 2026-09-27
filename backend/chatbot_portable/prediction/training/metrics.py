"""
Métriques d'évaluation pour la sélection automatique de modèles.
MAE, RMSE, MAPE — calculées sur les prévisions hors-échantillon.
"""

from __future__ import annotations

import numpy as np


def mae(y_true: list[float], y_pred: list[float]) -> float:
    """Mean Absolute Error."""
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: list[float], y_pred: list[float]) -> float:
    """Root Mean Squared Error."""
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true: list[float], y_pred: list[float], epsilon: float = 1e-9) -> float:
    """
    Mean Absolute Percentage Error.

    Args:
        epsilon: plancher pour éviter la division par zéro sur les séries
                 qui passent par 0 (ROE, résultat net)

    Returns:
        MAPE en pourcentage (ex: 5.2 pour 5.2%)
    """
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = np.maximum(np.abs(y_true), epsilon)
    return float(np.mean(np.abs(y_true - y_pred) / denom) * 100)


def all_metrics(
    y_true: list[float], y_pred: list[float]
) -> dict[str, float]:
    """Calcule MAE, RMSE et MAPE en une seule passe."""
    return {
        "mae": mae(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
        "mape": mape(y_true, y_pred),
    }


def composite_score(mae_val: float, rmse_val: float, mape_val: float) -> float:
    """
    Score composite pour comparer deux modèles.
    Même formule que TrainingMetrics.score (cohérence garantie).

    Score plus bas = meilleur modèle.
    """
    return mape_val * 0.7 + (rmse_val / max(mae_val, 1e-9)) * 0.3
