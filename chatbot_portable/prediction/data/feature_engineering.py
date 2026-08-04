"""
Feature Engineering pour XGBoost.
Prophet utilise directement ds/y — pas besoin de features manuelles.
XGBoost nécessite des features temporelles explicites.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class FeatureEngineer:
    """
    Construit les features pour XGBoost à partir d'une série temporelle annuelle.

    Features produites :
    - lag_1, lag_2, lag_3       : valeurs passées
    - rolling_mean_3             : moyenne glissante 3 ans
    - rolling_std_3              : écart-type glissant 3 ans
    - yoy_growth                 : croissance annuelle (%)
    - trend_index                : indice de position temporelle normalisé
    - cagr_3                     : CAGR sur 3 ans
    """

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Construit le DataFrame de features.

        Args:
            df: DataFrame avec colonnes [annee, valeur], trié par année

        Returns:
            DataFrame avec features + target, sans NaN
        """
        df = df.sort_values("annee").copy()
        df = df.reset_index(drop=True)

        # Lags
        df["lag_1"] = df["valeur"].shift(1)
        df["lag_2"] = df["valeur"].shift(2)
        df["lag_3"] = df["valeur"].shift(3)

        # Moyennes et volatilité glissantes
        df["rolling_mean_3"] = df["valeur"].shift(1).rolling(3).mean()
        df["rolling_std_3"] = df["valeur"].shift(1).rolling(3).std().fillna(0)

        # Croissance YoY (0.0 si valeur précédente nulle, pour éviter les +/-inf
        # qu'XGBoost rejette — même convention que build_future() ci-dessous)
        df["yoy_growth"] = (df["valeur"].pct_change() * 100).replace(
            [np.inf, -np.inf], 0.0
        )

        # CAGR 3 ans : (V_t / V_{t-3})^(1/3) - 1
        df["cagr_3"] = (
            (df["valeur"] / df["valeur"].shift(3)) ** (1 / 3) - 1
        ) * 100
        df["cagr_3"] = df["cagr_3"].replace([np.inf, -np.inf], 0.0)

        # Indice temporel normalisé (0 → 1)
        min_year = df["annee"].min()
        max_year = df["annee"].max()
        span = max(max_year - min_year, 1)
        df["trend_index"] = (df["annee"] - min_year) / span

        # Supprimer les lignes avec NaN (dues aux lags)
        feature_cols = [
            "lag_1", "lag_2", "lag_3",
            "rolling_mean_3", "rolling_std_3",
            "yoy_growth", "cagr_3", "trend_index",
        ]
        df = df.dropna(subset=feature_cols).reset_index(drop=True)

        return df

    @staticmethod
    def get_feature_columns() -> list[str]:
        """Retourne la liste ordonnée des colonnes features."""
        return [
            "lag_1", "lag_2", "lag_3",
            "rolling_mean_3", "rolling_std_3",
            "yoy_growth", "cagr_3", "trend_index",
        ]

    def build_future(self, df: pd.DataFrame, horizon: int) -> pd.DataFrame:
        """
        Construit les features pour les années futures (inférence).
        Utilise une approche récursive : chaque prévision devient un lag pour la suivante.

        Args:
            df: historique complet (avec features déjà calculées)
            horizon: nombre d'années à prédire

        Returns:
            DataFrame des features pour les années futures
        """
        history = df.copy()
        future_rows = []

        last_year = int(history["annee"].max())
        values = history["valeur"].tolist()

        for step in range(horizon):
            next_year = last_year + step + 1
            n = len(values)

            lag1 = values[-1] if n >= 1 else np.nan
            lag2 = values[-2] if n >= 2 else np.nan
            lag3 = values[-3] if n >= 3 else np.nan

            rm3 = np.mean(values[-3:]) if n >= 3 else np.mean(values)
            rs3 = np.std(values[-3:]) if n >= 3 else 0.0

            yoy = ((values[-1] / values[-2]) - 1) * 100 if n >= 2 and values[-2] != 0 else 0.0
            cagr = (
                ((values[-1] / values[-4]) ** (1 / 3) - 1) * 100
                if n >= 4 and values[-4] != 0 else yoy
            )

            min_year = int(history["annee"].min())
            max_future_year = last_year + horizon
            trend = (next_year - min_year) / max(max_future_year - min_year, 1)

            row = {
                "annee": next_year,
                "lag_1": lag1,
                "lag_2": lag2,
                "lag_3": lag3,
                "rolling_mean_3": rm3,
                "rolling_std_3": rs3,
                "yoy_growth": yoy,
                "cagr_3": cagr,
                "trend_index": trend,
            }
            future_rows.append(row)

            # La valeur prédite sera ajoutée par le Predictor
            # Pour l'instant on utilise la dernière valeur comme proxy
            values.append(values[-1])

        return pd.DataFrame(future_rows)
