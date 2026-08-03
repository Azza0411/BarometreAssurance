"""
Implémentation Prophet pour séries temporelles annuelles.
Prophet gère nativement les tendances et les changements de régime.
Adapté pour des séries courtes (5-15 points) avec saisonnalité annuelle.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from prediction.models.base_model import BaseModel, PredictionOutput, TrainingMetrics
from prediction.config.settings import CONFIG

logger = logging.getLogger(__name__)


class ProphetModel(BaseModel):
    """
    Wrapper Prophet calibré pour des séries financières annuelles tunisiennes.

    Configuration :
    - Saisonnalité annuelle uniquement (pas hebdo / quotidienne)
    - Mode multiplicatif (mieux pour des KPIs qui croissent exponentiellement)
    - changepoint_prior_scale faible (évite le surapprentissage sur séries courtes)
    - Intervalles de confiance à 80%
    """

    def __init__(self):
        self._model = None
        self._fitted = False
        self._history: pd.DataFrame | None = None
        self._forecast_df: pd.DataFrame | None = None
        self._cfg = CONFIG.prophet

    @property
    def name(self) -> str:
        return "prophet"

    def is_fitted(self) -> bool:
        return self._fitted

    def fit(self, df: pd.DataFrame) -> None:
        """
        Entraîne Prophet sur la série historique.

        Args:
            df: DataFrame avec colonnes [annee, valeur]
        """
        try:
            from prophet import Prophet
        except ImportError:
            raise ImportError(
                "Prophet non installé. Exécutez: pip install prophet"
            )

        df = df.sort_values("annee").copy()
        self._history = df.copy()

        # Prophet attend des colonnes 'ds' (date) et 'y' (valeur)
        prophet_df = pd.DataFrame({
            "ds": pd.to_datetime(df["annee"].astype(str) + "-01-01"),
            "y": df["valeur"].values,
        })

        # Vérification des valeurs négatives (mode multiplicatif incompatible)
        has_negatives = (df["valeur"] <= 0).any()
        seasonality_mode = (
            "additive" if has_negatives else self._cfg.seasonality_mode
        )

        self._model = Prophet(
            yearly_seasonality=self._cfg.yearly_seasonality,
            weekly_seasonality=False,
            daily_seasonality=False,
            seasonality_mode=seasonality_mode,
            changepoint_prior_scale=self._cfg.changepoint_prior_scale,
            interval_width=self._cfg.interval_width,
        )

        self._model.fit(prophet_df)
        self._fitted = True
        logger.info(
            f"Prophet entraîné: {len(df)} points, mode={seasonality_mode}"
        )

    def predict(self, horizon: int) -> PredictionOutput:
        """
        Prédit les prochaines années.

        Args:
            horizon: nombre d'années futures à prédire

        Returns:
            PredictionOutput avec valeurs + intervalles de confiance
        """
        if not self._fitted:
            raise RuntimeError("Modèle non entraîné. Appelez fit() d'abord.")

        last_year = int(self._history["annee"].max())
        future_years = list(range(last_year + 1, last_year + horizon + 1))

        future_df = pd.DataFrame({
            "ds": pd.to_datetime(
                [str(y) + "-01-01" for y in future_years]
            )
        })

        self._forecast_df = self._model.predict(future_df)

        values = self._forecast_df["yhat"].tolist()
        lower = self._forecast_df["yhat_lower"].tolist()
        upper = self._forecast_df["yhat_upper"].tolist()

        return PredictionOutput(
            years=future_years,
            values=values,
            lower_bound=lower,
            upper_bound=upper,
            confidence_level=self._cfg.interval_width,
            model_name=self.name,
            metadata={
                "seasonality_mode": self._model.seasonality_mode,
                "changepoint_prior_scale": self._cfg.changepoint_prior_scale,
                "n_history_points": len(self._history),
            },
        )

    def get_fitted_values(self) -> pd.DataFrame:
        """Valeurs ajustées sur l'historique (in-sample predictions)."""
        if not self._fitted:
            raise RuntimeError("Modèle non entraîné.")

        history_df = pd.DataFrame({
            "ds": pd.to_datetime(
                self._history["annee"].astype(str) + "-01-01"
            )
        })
        forecast = self._model.predict(history_df)

        return pd.DataFrame({
            "annee": self._history["annee"].values,
            "valeur_reelle": self._history["valeur"].values,
            "valeur_ajustee": forecast["yhat"].values,
        })

    def get_decomposition(self) -> dict[str, list[float]]:
        """
        Décompose la prévision en composantes (pour l'explainabilité).

        Returns:
            Dict avec clés: trend, yearly, residual (si disponibles)
        """
        if not self._fitted or self._forecast_df is None:
            raise RuntimeError(
                "predict() doit être appelé avant get_decomposition()."
            )

        result = {}
        if "trend" in self._forecast_df.columns:
            result["trend"] = self._forecast_df["trend"].tolist()
        if "yearly" in self._forecast_df.columns:
            result["yearly"] = self._forecast_df["yearly"].tolist()

        return result

    def get_historical_decomposition(self) -> pd.DataFrame:
        """
        Décomposition sur l'historique — utile pour l'interprétation des drivers.

        Returns:
            DataFrame avec colonnes [annee, trend, yearly, yhat]
        """
        if not self._fitted:
            raise RuntimeError("Modèle non entraîné.")

        history_df = pd.DataFrame({
            "ds": pd.to_datetime(
                self._history["annee"].astype(str) + "-01-01"
            )
        })
        forecast = self._model.predict(history_df)

        cols = {"ds": "ds", "trend": "trend", "yhat": "yhat"}
        if "yearly" in forecast.columns:
            cols["yearly"] = "yearly"

        result = forecast[list(cols.keys())].copy()
        result["annee"] = self._history["annee"].values
        return result

    def get_model_object(self) -> Any:
        return self._model
