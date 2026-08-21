"""
ForecastService — point d'entrée unique du module prediction.

Le chatbot n'importe que cette classe.
Toute la complexité (chargement, prétraitement, sélection, explication) est cachée ici.

Usage:
    service = ForecastService(conn)
    result = service.predict("STAR", "primes", horizon=3)
    print(result.narrative_text)   # texte prêt pour le LLM
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from prediction.data.data_loader import DataLoader
from prediction.data.preprocessing import Preprocessor
from prediction.data.validation import InputValidator
from prediction.training.trainer import Trainer, TrainingResult
from prediction.models.base_model import PredictionOutput
from prediction.models.model_factory import ModelFactory
from prediction.explainability.base_explainer import ExplanationResult
from prediction.explainability.narrative_generator import NarrativeGenerator

logger = logging.getLogger(__name__)


@dataclass
class ForecastResult:
    """Résultat complet exposé au chatbot."""
    kpi: str
    company: str | None
    prediction: PredictionOutput
    explanation: ExplanationResult
    narrative_text: str          # texte structuré pour le LLM Groq
    model_name: str
    unit: str
    n_history_points: int
    was_fallback: bool
    model_comparison: str = ""   # comparatif lisible des candidats évalués (MAPE/RMSE/score)
    warnings: list[str] = field(default_factory=list)
    computed_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ForecastService:
    """
    Façade unique du module de prévision.

    Orchestre dans l'ordre :
    1. Validation des inputs
    2. Chargement + prétraitement des données
    3. Sélection automatique + entraînement du meilleur modèle
    4. Prévision sur l'horizon demandé
    5. Explication (SHAP ou décomposition Prophet)
    6. Génération du narratif pour le LLM

    Args:
        conn: connexion SQLite partagée avec le chatbot
    """

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._loader = DataLoader(conn)
        self._preprocessor = Preprocessor()
        self._factory = ModelFactory()
        self._narrator = NarrativeGenerator()

    def predict(
        self,
        company: str | None,
        kpi: str,
        horizon: int = 1,
    ) -> ForecastResult:
        """
        Prédit un KPI pour une compagnie sur un horizon donné.

        Args:
            company: code compagnie (ex: "STAR") ou None pour le marché
            kpi: KPI canonique ou alias (ex: "primes", "part de marché")
            horizon: nombre d'années futures (1 à 5)

        Returns:
            ForecastResult avec la prévision, l'explication et le texte narratif

        Raises:
            ValueError: si les inputs sont invalides ou les données insuffisantes
        """
        # 1. Validation
        available_companies = self._loader.list_available_companies()
        validator = InputValidator(available_companies)
        validation = validator.validate(kpi, company, horizon)

        if not validation.is_valid:
            raise ValueError(
                "Paramètres invalides : " + " | ".join(validation.errors)
            )

        resolved_kpi = validation.kpi
        resolved_company = validation.company
        resolved_horizon = validation.horizon
        warnings = list(validation.warnings)

        logger.info(
            f"[ForecastService] predict: kpi={resolved_kpi!r} "
            f"company={resolved_company!r} horizon={resolved_horizon}"
        )

        # 2. Chargement + prétraitement
        ts_result = self._loader.load(resolved_kpi, resolved_company)
        if ts_result.n_points == 0:
            raise ValueError(
                f"Aucune donnée historique disponible pour "
                f"'{resolved_kpi}' / '{resolved_company}'."
            )

        clean_df, prep_report = self._preprocessor.process(ts_result)
        if prep_report.warnings:
            warnings.extend(prep_report.warnings)

        # 3. Sélection + entraînement
        from prediction.training.model_selector import ModelSelector
        selector = ModelSelector()
        selection = selector.select(resolved_kpi, clean_df)
        if selection.was_fallback:
            warnings.append(
                f"Sélection par défaut (cross-validation impossible) : "
                f"{selection.winner_name}"
            )

        trained_model = selection.winner_model

        # 4. Prévision
        prediction = trained_model.predict(horizon=resolved_horizon)

        # 5. Explication via Factory
        explainer = self._factory.create_explainer(trained_model)
        explanation = explainer.explain(horizon=resolved_horizon)

        # 6. Narratif
        narrative = self._narrator.generate(
            kpi=resolved_kpi,
            company=resolved_company,
            prediction=prediction,
            explanation=explanation,
            unit=ts_result.unit,
        )

        logger.info(
            f"[ForecastService] terminé: modèle={selection.winner_name} "
            f"MAPE={selection.winner_metrics.mape:.2f}%"
        )

        return ForecastResult(
            kpi=resolved_kpi,
            company=resolved_company,
            prediction=prediction,
            explanation=explanation,
            narrative_text=narrative,
            model_name=selection.winner_name,
            unit=ts_result.unit,
            n_history_points=prep_report.final_n,
            was_fallback=selection.was_fallback,
            model_comparison=selection.reason,
            warnings=warnings,
        )

    def predict_text(
        self,
        company: str | None,
        kpi: str,
        horizon: int = 1,
    ) -> str:
        """
        Version simplifiée qui retourne uniquement le texte narratif.
        C'est ce que le chatbot utilise directement.

        Returns:
            Texte structuré prêt pour reformulation par le LLM Groq
        """
        result = self.predict(company, kpi, horizon)
        return result.narrative_text
