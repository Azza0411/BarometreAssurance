"""
Orchestration complète de l'entraînement.

Le Trainer combine :
  DataLoader → Preprocessor → ModelSelector → (storage)

C'est le point d'entrée du pipeline d'entraînement.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from prediction.data.data_loader import DataLoader
from prediction.data.preprocessing import Preprocessor, PreprocessingReport
from prediction.training.model_selector import ModelSelector, SelectionResult
from prediction.models.base_model import BaseModel

logger = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    """Résultat complet d'un cycle d'entraînement."""
    kpi: str
    company: str | None
    model: BaseModel
    model_name: str
    selection: SelectionResult
    preprocessing_report: PreprocessingReport
    n_history_points: int
    trained_at: str          # ISO datetime
    unit: str


class Trainer:
    """
    Orchestre le pipeline complet d'entraînement pour un KPI / compagnie.

    Usage:
        trainer = Trainer(conn)
        result = trainer.train(kpi="Primes émises par assurance",
                               company="STAR")
    """

    def __init__(self, conn: sqlite3.Connection):
        self._loader = DataLoader(conn)
        self._preprocessor = Preprocessor()
        self._selector = ModelSelector()

    def train(
        self, kpi: str, company: str | None = None
    ) -> TrainingResult:
        """
        Exécute le pipeline complet : chargement → prétraitement → sélection → entraînement.

        Args:
            kpi: KPI canonique
            company: code compagnie ou None (marché)

        Returns:
            TrainingResult avec le modèle entraîné et tous les métriques

        Raises:
            ValueError: si les données sont insuffisantes
        """
        logger.info(f"[Trainer] Début entraînement: kpi={kpi!r} company={company!r}")

        # 1. Chargement
        ts_result = self._loader.load(kpi, company)
        if ts_result.n_points == 0:
            raise ValueError(
                f"Aucune donnée disponible pour kpi={kpi!r} company={company!r}"
            )

        # 2. Prétraitement
        clean_df, prep_report = self._preprocessor.process(ts_result)

        logger.info(
            f"[Trainer] Données: {prep_report.original_n}→{prep_report.final_n} pts, "
            f"outliers={prep_report.outliers_removed}, gaps={prep_report.gaps_filled}"
        )

        # 3. Sélection + entraînement final
        selection = self._selector.select(kpi, clean_df)

        result = TrainingResult(
            kpi=kpi,
            company=company,
            model=selection.winner_model,
            model_name=selection.winner_name,
            selection=selection,
            preprocessing_report=prep_report,
            n_history_points=prep_report.final_n,
            trained_at=datetime.now().isoformat(),
            unit=ts_result.unit,
        )

        logger.info(
            f"[Trainer] Entraînement terminé: "
            f"modèle={selection.winner_name} "
            f"MAPE={selection.winner_metrics.mape:.2f}%"
        )

        return result

    def get_available_companies(self) -> list[str]:
        return self._loader.list_available_companies()
