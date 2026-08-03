"""
Prétraitement des séries temporelles.
Responsabilité : nettoyer, imputer, détecter les anomalies.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from prediction.data.data_loader import TimeSeriesResult

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingReport:
    """Rapport de prétraitement pour traçabilité."""
    original_n: int
    final_n: int
    outliers_removed: list[int]      # années supprimées
    gaps_filled: list[int]           # années interpolées
    warnings: list[str]


class Preprocessor:
    """
    Nettoie et prépare une série temporelle pour l'entraînement.

    Opérations appliquées dans l'ordre :
    1. Suppression des valeurs nulles ou négatives impossibles
    2. Détection et traitement des outliers (IQR)
    3. Combler les trous (interpolation linéaire)
    4. Validation de la longueur minimale
    """

    def __init__(self, min_points: int = 5, outlier_iqr_factor: float = 3.0):
        """
        Args:
            min_points: nombre minimum de points requis après nettoyage
            outlier_iqr_factor: facteur IQR pour détection outliers (3.0 = conservateur)
        """
        self._min_points = min_points
        self._iqr_factor = outlier_iqr_factor

    def process(self, result: TimeSeriesResult) -> tuple[pd.DataFrame, PreprocessingReport]:
        """
        Nettoie la série temporelle.

        Args:
            result: TimeSeriesResult brut du DataLoader

        Returns:
            (DataFrame nettoyé avec colonnes [annee, valeur], rapport)

        Raises:
            ValueError: si la série est trop courte après nettoyage
        """
        df = result.data.copy()
        report = PreprocessingReport(
            original_n=len(df),
            final_n=0,
            outliers_removed=[],
            gaps_filled=[],
            warnings=[],
        )

        if df.empty:
            raise ValueError(
                f"Série vide pour kpi={result.kpi!r} company={result.company!r}"
            )

        # 1. Supprimer valeurs nulles
        df = df.dropna(subset=["valeur"])

        # 2. Supprimer valeurs aberrantes selon le type de KPI
        df, removed = self._remove_impossible_values(df, result.kpi, result.unit)
        report.outliers_removed.extend(removed)

        # 3. Outliers statistiques (IQR) — seulement si série suffisamment longue
        if len(df) >= 6:
            df, removed_iqr = self._remove_iqr_outliers(df)
            report.outliers_removed.extend(removed_iqr)
            if removed_iqr:
                report.warnings.append(
                    f"Outliers IQR supprimés pour années {removed_iqr}"
                )

        # 4. Combler les trous (années manquantes entre min et max)
        if len(df) >= 2:
            df, filled = self._fill_gaps(df)
            report.gaps_filled.extend(filled)

        # 5. Vérification longueur minimale
        if len(df) < self._min_points:
            raise ValueError(
                f"Série trop courte ({len(df)} points) après nettoyage "
                f"pour kpi={result.kpi!r}. Minimum requis : {self._min_points}."
            )

        df = df.sort_values("annee").reset_index(drop=True)
        report.final_n = len(df)

        logger.info(
            f"Prétraitement: {report.original_n}→{report.final_n} points, "
            f"outliers={report.outliers_removed}, gaps={report.gaps_filled}"
        )
        return df, report

    def _remove_impossible_values(
        self, df: pd.DataFrame, kpi: str, unit: str
    ) -> tuple[pd.DataFrame, list[int]]:
        """Supprime les valeurs physiquement impossibles selon le KPI."""
        mask = pd.Series(True, index=df.index)

        if unit == "%":
            # Pourcentages : entre -200% et 500% (permet pertes importantes)
            mask = (df["valeur"] >= -200) & (df["valeur"] <= 500)
        elif unit in ("MDT", "TND/hab"):
            # Montants : doit être positif
            mask = df["valeur"] > 0
        elif unit == "habitants":
            mask = df["valeur"] > 0

        removed_years = df.loc[~mask, "annee"].tolist()
        return df[mask].copy(), removed_years

    def _remove_iqr_outliers(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[int]]:
        """Détecte et supprime les outliers par méthode IQR."""
        q1 = df["valeur"].quantile(0.25)
        q3 = df["valeur"].quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            return df, []

        lower = q1 - self._iqr_factor * iqr
        upper = q3 + self._iqr_factor * iqr
        mask = (df["valeur"] >= lower) & (df["valeur"] <= upper)

        removed = df.loc[~mask, "annee"].tolist()
        return df[mask].copy(), removed

    def _fill_gaps(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[int]]:
        """Interpole linéairement les années manquantes."""
        all_years = range(int(df["annee"].min()), int(df["annee"].max()) + 1)
        full_index = pd.DataFrame({"annee": list(all_years)})
        merged = full_index.merge(df, on="annee", how="left")

        missing_years = merged.loc[merged["valeur"].isna(), "annee"].tolist()
        if missing_years:
            merged["valeur"] = merged["valeur"].interpolate(method="linear")

        return merged.dropna(subset=["valeur"]), missing_years
