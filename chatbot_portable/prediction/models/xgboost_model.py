"""
Implémentation XGBoost pour séries temporelles avec feature engineering.
XGBoost est plus robuste sur les séries avec ruptures structurelles ou
relations non-linéaires entre variables économiques.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from prediction.models.base_model import BaseModel, PredictionOutput, TrainingMetrics
from prediction.data.feature_engineering import FeatureEngineer
from prediction.config.settings import CONFIG

logger = logging.getLogger(__name__)


class XGBoostModel(BaseModel):
    """
    XGBoost calibré pour séries financières annuelles.

    Features utilisées (construites par FeatureEngineer) :
    - lag_1, lag_2, lag_3          : valeurs passées
    - rolling_mean_3, rolling_std_3 : statistiques glissantes
    - yoy_growth                   : croissance YoY
    - cagr_3                       : CAGR sur 3 ans
    - trend_index                  : position normalisée dans le temps

    Intervalles de confiance : quantile regression (quantile 10% / 90%)
    """

    def __init__(self):
        self._model = None
        self._model_lower = None    # modèle pour borne basse (quantile 10%)
        self._model_upper = None    # modèle pour borne haute (quantile 90%)
        self._fitted = False
        self._history: pd.DataFrame | None = None
        self._features_df: pd.DataFrame | None = None
        self._engineer = FeatureEngineer()
        self._cfg = CONFIG.xgboost
        self._feature_cols = FeatureEngineer.get_feature_columns()

    @property
    def name(self) -> str:
        return "xgboost"

    def is_fitted(self) -> bool:
        return self._fitted

    def fit(self, df: pd.DataFrame) -> None:
        """
        Construit les features et entraîne XGBoost.

        Args:
            df: DataFrame avec colonnes [annee, valeur]
        """
        try:
            import xgboost as xgb
        except ImportError:
            raise ImportError(
                "XGBoost non installé. Exécutez: pip install xgboost"
            )

        df = df.sort_values("annee").copy()
        self._history = df.copy()

        # Construction des features
        self._features_df = self._engineer.build(df)

        if len(self._features_df) < 2:
            raise ValueError(
                f"Trop peu de points après feature engineering : "
                f"{len(self._features_df)}. Minimum requis : 2."
            )

        X = self._features_df[self._feature_cols].values
        y = self._features_df["valeur"].values

        common_params = {
            "n_estimators": self._cfg.n_estimators,
            "max_depth": self._cfg.max_depth,
            "learning_rate": self._cfg.learning_rate,
            "subsample": self._cfg.subsample,
            "colsample_bytree": self._cfg.colsample_bytree,
            "random_state": 42,
            "n_jobs": -1,
        }

        # Modèle principal (régression standard)
        self._model = xgb.XGBRegressor(objective="reg:squarederror", **common_params)
        self._model.fit(X, y)

        # Modèles pour intervalles de confiance (quantile regression)
        self._model_lower = xgb.XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=0.10, **common_params
        )
        self._model_lower.fit(X, y)

        self._model_upper = xgb.XGBRegressor(
            objective="reg:quantileerror", quantile_alpha=0.90, **common_params
        )
        self._model_upper.fit(X, y)

        self._fitted = True
        logger.info(
            f"XGBoost entraîné: {len(self._features_df)} points "
            f"({len(self._feature_cols)} features)"
        )

    def predict(self, horizon: int) -> PredictionOutput:
        """
        Prédit de façon récursive les prochaines années.

        Approche récursive : la prévision de l'année N devient le lag_1
        pour l'année N+1.

        Args:
            horizon: nombre d'années futures à prédire
        """
        if not self._fitted:
            raise RuntimeError("Modèle non entraîné. Appelez fit() d'abord.")

        import xgboost as xgb

        last_year = int(self._history["annee"].max())
        future_years = list(range(last_year + 1, last_year + horizon + 1))

        # Construction des features futures (récursif)
        future_features_df = self._engineer.build_future(
            self._features_df, horizon
        )

        X_future = future_features_df[self._feature_cols].values

        values = self._model.predict(X_future).tolist()
        lower = self._model_lower.predict(X_future).tolist()
        upper = self._model_upper.predict(X_future).tolist()

        # Mise à jour récursive des lags dans FeatureEngineer.build_future
        # Les valeurs prédites sont injectées dans les lags via rebuild
        values, lower, upper = self._recursive_predict(horizon)

        return PredictionOutput(
            years=future_years,
            values=values,
            lower_bound=lower,
            upper_bound=upper,
            confidence_level=0.80,
            model_name=self.name,
            metadata={
                "n_estimators": self._cfg.n_estimators,
                "max_depth": self._cfg.max_depth,
                "learning_rate": self._cfg.learning_rate,
                "n_history_points": len(self._history),
                "n_features": len(self._feature_cols),
            },
        )

    def _recursive_predict(
        self, horizon: int
    ) -> tuple[list[float], list[float], list[float]]:
        """
        Prévision récursive : chaque prédiction nourrit les lags suivants.
        Évite la dérive des lags qui fausserait les prévisions à long terme.
        """
        values_predicted = []
        lower_predicted = []
        upper_predicted = []

        # Copie de l'historique pour construction récursive
        history_values = self._history["valeur"].tolist()
        history_years = self._history["annee"].tolist()
        last_year = int(max(history_years))

        # Paramètres pour trend_index récursif
        min_year = int(min(history_years))
        max_future_year = last_year + horizon

        for step in range(horizon):
            next_year = last_year + step + 1
            n = len(history_values)

            lag1 = history_values[-1] if n >= 1 else 0.0
            lag2 = history_values[-2] if n >= 2 else lag1
            lag3 = history_values[-3] if n >= 3 else lag2

            rm3 = float(np.mean(history_values[-3:])) if n >= 3 else float(np.mean(history_values))
            rs3 = float(np.std(history_values[-3:])) if n >= 3 else 0.0

            yoy = (
                ((history_values[-1] / history_values[-2]) - 1) * 100
                if n >= 2 and history_values[-2] != 0 else 0.0
            )
            cagr = (
                ((history_values[-1] / history_values[-4]) ** (1 / 3) - 1) * 100
                if n >= 4 and history_values[-4] != 0 else yoy
            )

            trend = (next_year - min_year) / max(max_future_year - min_year, 1)

            row = np.array([[lag1, lag2, lag3, rm3, rs3, yoy, cagr, trend]])

            pred = float(self._model.predict(row)[0])
            pred_low = float(self._model_lower.predict(row)[0])
            pred_high = float(self._model_upper.predict(row)[0])

            # S'assurer que lower ≤ pred ≤ upper
            pred_low = min(pred_low, pred)
            pred_high = max(pred_high, pred)

            values_predicted.append(pred)
            lower_predicted.append(pred_low)
            upper_predicted.append(pred_high)

            # Utiliser la valeur prédite comme prochain lag
            history_values.append(pred)

        return values_predicted, lower_predicted, upper_predicted

    def get_fitted_values(self) -> pd.DataFrame:
        """Valeurs ajustées sur l'historique."""
        if not self._fitted:
            raise RuntimeError("Modèle non entraîné.")

        X = self._features_df[self._feature_cols].values
        fitted = self._model.predict(X)

        return pd.DataFrame({
            "annee": self._features_df["annee"].values,
            "valeur_reelle": self._features_df["valeur"].values,
            "valeur_ajustee": fitted,
        })

    def get_feature_importances(self) -> dict[str, float]:
        """
        Importances des features pour l'explainabilité (SHAP ou gain).

        Returns:
            Dict {feature_name: importance_score}
        """
        if not self._fitted:
            raise RuntimeError("Modèle non entraîné.")

        importances = self._model.feature_importances_
        return dict(zip(self._feature_cols, importances.tolist()))

    def get_model_object(self) -> Any:
        return self._model

    def get_features_dataframe(self) -> pd.DataFrame:
        """Retourne le DataFrame de features (utilisé par ShapExplainer)."""
        if not self._fitted:
            raise RuntimeError("Modèle non entraîné.")
        return self._features_df.copy()
