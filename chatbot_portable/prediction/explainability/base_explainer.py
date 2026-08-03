"""Interface abstraite commune à tous les explaineurs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ExplanationResult:
    """Sortie standardisée de l'explainabilité."""
    model_name: str
    method: str                      # "shap" | "prophet_decomposition"
    drivers: list[dict]              # [{"label": str, "impact": float, "direction": str}]
    summary_text: str                # texte brut pour le LLM
    metadata: dict = field(default_factory=dict)


class BaseExplainer(ABC):
    """
    Contrat commun à ProphetExplainer et ShapExplainer.
    La Factory crée le bon explaineur automatiquement.
    """

    @abstractmethod
    def explain(self, horizon: int = 1) -> ExplanationResult:
        """
        Génère l'explication du modèle.

        Args:
            horizon: nombre d'années prédites (pour contextualiser)

        Returns:
            ExplanationResult avec les drivers et le texte résumé
        """
