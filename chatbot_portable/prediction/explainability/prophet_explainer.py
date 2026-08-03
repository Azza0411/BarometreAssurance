"""
Explainabilité pour Prophet : décomposition trend + saisonnalité.

Approche :
- Prophet décompose la prévision en composantes : trend, yearly, residual
- On mesure la contribution relative de chaque composante
- On identifie les points de changement (changepoints) significatifs
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from prediction.explainability.base_explainer import BaseExplainer, ExplanationResult

if TYPE_CHECKING:
    from prediction.models.prophet_model import ProphetModel

logger = logging.getLogger(__name__)


class ProphetExplainer(BaseExplainer):
    """
    Explique les prévisions Prophet via décomposition en composantes.

    Drivers produits :
    - Tendance structurelle (trend) : direction générale de la série
    - Saisonnalité annuelle         : variation cyclique récurrente
    - Momentum récent               : accélération/décélération récente
    """

    def __init__(self, model: "ProphetModel"):
        self._model = model

    def explain(self, horizon: int = 1) -> ExplanationResult:
        """
        Analyse les composantes de la prévision Prophet.

        Args:
            horizon: nombre d'années prédites

        Returns:
            ExplanationResult avec les drivers et un texte résumé
        """
        if not self._model.is_fitted():
            raise RuntimeError("Le modèle Prophet doit être entraîné avant l'explication.")

        # Décomposition sur l'historique
        hist_decomp = self._model.get_historical_decomposition()

        # Décomposition sur les prévisions futures
        try:
            future_decomp = self._model.get_decomposition()
        except RuntimeError:
            # predict() pas encore appelé
            self._model.predict(horizon=horizon)
            future_decomp = self._model.get_decomposition()

        drivers = self._compute_drivers(hist_decomp, future_decomp)
        summary = self._build_summary(drivers, hist_decomp)

        return ExplanationResult(
            model_name="prophet",
            method="prophet_decomposition",
            drivers=drivers,
            summary_text=summary,
            metadata={
                "n_history_points": len(hist_decomp),
                "components": list(future_decomp.keys()),
            },
        )

    def _compute_drivers(
        self,
        hist_decomp: pd.DataFrame,
        future_decomp: dict[str, list[float]],
    ) -> list[dict]:
        """Calcule la contribution relative de chaque composante."""
        drivers = []

        # Driver 1 : Tendance (trend)
        if "trend" in future_decomp and len(future_decomp["trend"]) > 0:
            trend_values = future_decomp["trend"]
            trend_mean = float(np.mean(trend_values))

            # Pente de la tendance sur l'historique
            if "trend" in hist_decomp.columns and len(hist_decomp) >= 2:
                hist_trend = hist_decomp["trend"].values
                slope = (hist_trend[-1] - hist_trend[-3]) / 2 if len(hist_trend) >= 3 else hist_trend[-1] - hist_trend[-2]
                direction = "hausse" if slope > 0 else "baisse"
                pct_change = abs(slope / max(abs(hist_trend[-1]), 1e-9)) * 100
            else:
                direction = "stable"
                pct_change = 0.0

            drivers.append({
                "label": "Tendance structurelle",
                "impact": round(abs(trend_mean), 3),
                "direction": direction,
                "description": f"La tendance de fond indique une {direction} "
                               f"d'environ {pct_change:.1f}% par an.",
                "weight": 0.6,
            })

        # Driver 2 : Saisonnalité annuelle (yearly)
        if "yearly" in future_decomp and len(future_decomp["yearly"]) > 0:
            yearly = future_decomp["yearly"]
            yearly_amplitude = float(np.max(yearly) - np.min(yearly))

            drivers.append({
                "label": "Saisonnalité annuelle",
                "impact": round(yearly_amplitude, 3),
                "direction": "cyclique",
                "description": f"La composante saisonnière représente "
                               f"une variation d'amplitude {yearly_amplitude:.2f}.",
                "weight": 0.2,
            })

        # Driver 3 : Momentum récent (accélération sur les 3 dernières années)
        if "yhat" in hist_decomp.columns and len(hist_decomp) >= 4:
            recent = hist_decomp["yhat"].values[-4:]
            growth_rates = np.diff(recent) / np.maximum(np.abs(recent[:-1]), 1e-9) * 100
            avg_growth = float(np.mean(growth_rates))
            direction_mom = "accélération" if avg_growth > 0 else "décélération"

            drivers.append({
                "label": "Momentum récent",
                "impact": round(abs(avg_growth), 3),
                "direction": direction_mom,
                "description": f"Sur les 3 dernières années observées, "
                               f"la croissance moyenne est de {avg_growth:.1f}% par an.",
                "weight": 0.2,
            })

        # Trier par impact décroissant
        drivers.sort(key=lambda d: d["impact"] * d["weight"], reverse=True)
        return drivers

    def _build_summary(
        self,
        drivers: list[dict],
        hist_decomp: pd.DataFrame,
    ) -> str:
        """Construit un texte résumé structuré pour le LLM."""
        lines = ["=== Analyse Prophet ==="]

        for d in drivers:
            arrow = "↑" if d["direction"] in ("hausse", "accélération") else (
                "↓" if d["direction"] in ("baisse", "décélération") else "↔"
            )
            lines.append(f"• {d['label']} {arrow} : {d['description']}")

        if not drivers:
            lines.append("• Aucune composante significative identifiée.")

        lines.append(
            f"\nBasé sur {len(hist_decomp)} points historiques. "
            "Le modèle Prophet modélise la tendance et la saisonnalité annuelle."
        )

        return "\n".join(lines)
