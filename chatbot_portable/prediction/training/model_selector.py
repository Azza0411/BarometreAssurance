"""
Sélection automatique du meilleur modèle pour un KPI donné.

Processus :
1. ModelFactory fournit la liste des candidats selon le KPI et le nb de points
2. TimeSeriesEvaluator évalue chaque candidat
3. Le modèle avec le score composite le plus bas est sélectionné
4. Fallback : si tous les candidats échouent → modèle par défaut sans CV
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from prediction.models.base_model import BaseModel, TrainingMetrics
from prediction.models.model_factory import ModelFactory
from prediction.training.evaluator import TimeSeriesEvaluator, EvaluationReport
from prediction.config.settings import CONFIG

logger = logging.getLogger(__name__)


@dataclass
class SelectionResult:
    """Résultat de la sélection automatique."""
    winner_name: str
    winner_model: BaseModel          # instance entraînée sur la série complète
    winner_metrics: TrainingMetrics
    all_reports: dict[str, EvaluationReport]   # {model_name: report}
    was_fallback: bool               # True si sélection par défaut (CV impossible)
    reason: str                      # explication lisible de la décision


class ModelSelector:
    """
    Sélectionne automatiquement le meilleur modèle par cross-validation.

    Usage:
        selector = ModelSelector()
        result = selector.select(kpi="Primes émises par assurance",
                                 df=df_historique)
        best_model = result.winner_model  # déjà entraîné
    """

    def __init__(self):
        self._factory = ModelFactory()
        self._evaluator = TimeSeriesEvaluator(
            n_splits=CONFIG.training.n_splits,
            test_size=CONFIG.training.test_size,
            min_train=CONFIG.training.min_data_points,
        )

    def select(self, kpi: str, df: pd.DataFrame) -> SelectionResult:
        """
        Évalue tous les modèles candidats et retourne le meilleur.

        Args:
            kpi: KPI canonique
            df: DataFrame [annee, valeur] prétraité

        Returns:
            SelectionResult avec le modèle gagnant entraîné sur df complet
        """
        n_points = len(df)
        candidates = self._factory.get_candidate_models(kpi, n_points)

        logger.info(
            f"Sélection pour '{kpi}' ({n_points} pts) "
            f"→ candidats : {candidates}"
        )

        reports: dict[str, EvaluationReport] = {}
        errors: dict[str, str] = {}

        # Évaluation de chaque candidat
        for model_name in candidates:
            try:
                model_class = type(self._factory.create_model(model_name))
                report = self._evaluator.evaluate(model_class, df)
                reports[model_name] = report
                logger.info(f"  {model_name}: score={report.score:.4f} "
                            f"MAPE={report.avg_mape:.2f}%")
            except Exception as exc:
                errors[model_name] = str(exc)
                logger.warning(f"  {model_name}: ÉCHEC — {exc}")

        # Sélection du gagnant
        if reports:
            winner_name = min(reports, key=lambda k: reports[k].score)
            report = reports[winner_name]
            reason = self._build_reason(winner_name, reports, errors)
            was_fallback = False
        else:
            # Tous les modèles ont échoué → fallback par défaut
            winner_name = self._factory.get_default_model_for_kpi(kpi)
            report = None
            reason = (
                f"Tous les candidats ont échoué ({errors}). "
                f"Fallback : {winner_name} sans cross-validation."
            )
            was_fallback = True
            logger.warning(f"Fallback activé pour '{kpi}': {reason}")

        # Entraînement final sur la série complète
        winner_model = self._factory.create_model(winner_name)
        winner_model.fit(df)

        metrics = (
            report.to_training_metrics()
            if report
            else TrainingMetrics(
                mae=float("nan"),
                rmse=float("nan"),
                mape=float("nan"),
                n_folds=0,
                model_name=winner_name,
                details={"fallback": True, "reason": reason},
            )
        )

        logger.info(
            f"Modèle sélectionné pour '{kpi}': {winner_name} "
            f"(fallback={was_fallback})"
        )

        return SelectionResult(
            winner_name=winner_name,
            winner_model=winner_model,
            winner_metrics=metrics,
            all_reports=reports,
            was_fallback=was_fallback,
            reason=reason,
        )

    def _build_reason(
        self,
        winner: str,
        reports: dict[str, EvaluationReport],
        errors: dict[str, str],
    ) -> str:
        """Construit un message lisible expliquant la décision."""
        if len(reports) == 1:
            r = reports[winner]
            return (
                f"{winner} sélectionné (seul candidat valide). "
                f"MAPE={r.avg_mape:.2f}% sur {r.n_folds} folds."
            )

        lines = []
        for name, r in sorted(reports.items(), key=lambda x: x[1].score):
            marker = "✓" if name == winner else " "
            lines.append(
                f"{marker} {name}: MAPE={r.avg_mape:.2f}% "
                f"RMSE={r.avg_rmse:.3f} score={r.score:.4f}"
            )
        if errors:
            for name, err in errors.items():
                lines.append(f"✗ {name}: ÉCHEC ({err[:60]})")
        return "\n".join(lines)
