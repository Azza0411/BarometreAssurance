"""
Interface abstraite commune à tous les modèles de prévision.
Principe SOLID — Open/Closed : ajouter un modèle = créer une sous-classe,
sans toucher au reste du pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class TrainingMetrics:
    """Métriques produites lors de la validation chronologique."""
    mae: float
    rmse: float
    mape: float
    n_folds: int
    model_name: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        """Score composite pour comparer les modèles (MAPE pondéré + RMSE)."""
        # MAPE = métrique principale, RMSE = tie-breaker
        # Normalisé pour être comparable entre KPIs d'échelles différentes
        return self.mape * 0.7 + (self.rmse / max(self.mae, 1e-9)) * 0.3

    def __str__(self) -> str:
        return (
            f"{self.model_name} | MAE={self.mae:.3f} "
            f"RMSE={self.rmse:.3f} MAPE={self.mape:.2f}%"
        )


@dataclass
class PredictionOutput:
    """Sortie standardisée d'une prévision."""
    years: list[int]
    values: list[float]
    lower_bound: list[float]
    upper_bound: list[float]
    confidence_level: float          # ex: 0.80
    model_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseModel(ABC):
    """
    Contrat commun à Prophet et XGBoost.
    Toute nouvelle implémentation doit hériter de cette classe.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identifiant du modèle : 'prophet' | 'xgboost'."""

    @abstractmethod
    def fit(self, df: pd.DataFrame) -> None:
        """
        Entraîne le modèle sur la série historique complète.

        Args:
            df: DataFrame avec colonnes [annee, valeur]
        """

    @abstractmethod
    def predict(self, horizon: int) -> PredictionOutput:
        """
        Génère les prévisions pour les prochaines années.

        Args:
            horizon: nombre d'années à prédire

        Returns:
            PredictionOutput avec valeurs + intervalles de confiance
        """

    @abstractmethod
    def get_fitted_values(self) -> pd.DataFrame:
        """
        Retourne les valeurs ajustées sur l'historique (pour diagnostics).

        Returns:
            DataFrame avec colonnes [annee, valeur_reelle, valeur_ajustee]
        """

    @abstractmethod
    def get_model_object(self) -> Any:
        """Retourne l'objet modèle natif (Prophet model ou XGBoost Booster)."""

    @abstractmethod
    def is_fitted(self) -> bool:
        """True si le modèle a été entraîné."""
