"""
Explainabilité XGBoost via SHAP (SHapley Additive exPlanations).

SHAP mesure la contribution marginale de chaque feature à la prédiction.
Contrairement aux importances Gini, SHAP est théoriquement fondé
(théorie des jeux de Shapley) et donne des explications par prédiction.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from prediction.explainability.base_explainer import BaseExplainer, ExplanationResult
from prediction.data.feature_engineering import FeatureEngineer

if TYPE_CHECKING:
    from prediction.models.xgboost_model import XGBoostModel

logger = logging.getLogger(__name__)

_FEATURE_LABELS = {
    "lag_1":          "Valeur année précédente (lag 1)",
    "lag_2":          "Valeur il y a 2 ans (lag 2)",
    "lag_3":          "Valeur il y a 3 ans (lag 3)",
    "rolling_mean_3": "Moyenne glissante 3 ans",
    "rolling_std_3":  "Volatilité 3 ans",
    "yoy_growth":     "Croissance annuelle (YoY %)",
    "cagr_3":         "CAGR sur 3 ans",
    "trend_index":    "Position dans le temps (tendance)",
}


class ShapExplainer(BaseExplainer):
    """
    Explique les prévisions XGBoost via SHAP values.

    SHAP est calculé sur le dernier point historique (le plus récent),
    ce qui explique la logique de la première prévision future.
    """

    def __init__(self, model: "XGBoostModel"):
        self._model = model
        self._feature_cols = FeatureEngineer.get_feature_columns()

    def explain(self, horizon: int = 1) -> ExplanationResult:
        """
        Calcule les SHAP values pour expliquer la prévision XGBoost.

        Args:
            horizon: non utilisé directement (SHAP explique le dernier point)

        Returns:
            ExplanationResult avec les drivers SHAP et un texte résumé
        """
        if not self._model.is_fitted():
            raise RuntimeError("Le modèle XGBoost doit être entraîné avant l'explication.")

        model_obj = self._model.get_model_object()
        features_df = self._model.get_features_dataframe()
        X = features_df[self._feature_cols].values

        try:
            import xgboost as xgb
            # pred_contribs = SHAP values natif XGBoost (TreeSHAP exact)
            # Dernière colonne = valeur de base (biais) → on l'exclut
            booster = model_obj.get_booster()
            dmat = xgb.DMatrix(X, feature_names=self._feature_cols)
            shap_matrix = booster.predict(dmat, pred_contribs=True)
            shap_values = shap_matrix[:, :-1]   # exclure le biais
            base_value = float(shap_matrix[0, -1])
        except Exception as e:
            logger.warning(f"SHAP natif XGBoost échoué ({e}), fallback Gini")
            return self._fallback_explanation()

        last_shap = shap_values[-1]
        last_feature_values = X[-1]

        drivers = self._build_drivers(last_shap, last_feature_values)
        summary = self._build_summary(drivers, shap_values, features_df)

        return ExplanationResult(
            model_name="xgboost",
            method="shap",
            drivers=drivers,
            summary_text=summary,
            metadata={
                "n_history_points": len(features_df),
                "base_value": base_value,
                "explained_point": "dernier point historique",
            },
        )

    def _build_drivers(
        self,
        shap_vals: np.ndarray,
        feature_vals: np.ndarray,
    ) -> list[dict]:
        """Construit la liste des drivers à partir des SHAP values."""
        drivers = []

        for i, feat_name in enumerate(self._feature_cols):
            shap_val = float(shap_vals[i])
            feat_val = float(feature_vals[i])
            direction = "hausse" if shap_val > 0 else "baisse"
            label = _FEATURE_LABELS.get(feat_name, feat_name)

            drivers.append({
                "label": label,
                "feature": feat_name,
                "shap_value": round(shap_val, 4),
                "feature_value": round(feat_val, 4),
                "impact": round(abs(shap_val), 4),
                "direction": direction,
                "description": (
                    f"{label} = {feat_val:.3f} → contribution {direction} "
                    f"de {abs(shap_val):.3f} sur la prévision."
                ),
            })

        # Trier par impact absolu décroissant
        drivers.sort(key=lambda d: d["impact"], reverse=True)
        return drivers

    def _build_summary(
        self,
        drivers: list[dict],
        shap_values: np.ndarray,
        features_df: pd.DataFrame,
    ) -> str:
        """Construit le texte résumé pour le LLM."""
        lines = ["=== Analyse SHAP (XGBoost) ==="]

        # Top 3 features les plus influentes
        top3 = drivers[:3]
        for d in top3:
            arrow = "↑" if d["direction"] == "hausse" else "↓"
            lines.append(f"• {d['label']} {arrow} : {d['description']}")

        # Impact global positif vs négatif
        positive = sum(d["shap_value"] for d in drivers if d["shap_value"] > 0)
        negative = sum(d["shap_value"] for d in drivers if d["shap_value"] < 0)
        lines.append(
            f"\nForces haussières : +{positive:.3f} | "
            f"Forces baissières : {negative:.3f}"
        )

        lines.append(
            f"\nBasé sur {len(features_df)} points historiques avec "
            f"{len(self._feature_cols)} features. "
            "Méthode SHAP (SHapley Additive exPlanations)."
        )

        return "\n".join(lines)

    def _fallback_explanation(self) -> ExplanationResult:
        """Fallback si SHAP n'est pas installé : importances Gini."""
        logger.warning("SHAP non installé — fallback sur importances Gini.")
        importances = self._model.get_feature_importances()

        drivers = []
        for feat_name, importance in sorted(
            importances.items(), key=lambda x: x[1], reverse=True
        ):
            label = _FEATURE_LABELS.get(feat_name, feat_name)
            drivers.append({
                "label": label,
                "feature": feat_name,
                "shap_value": importance,
                "feature_value": None,
                "impact": importance,
                "direction": "importance",
                "description": f"{label} : importance Gini = {importance:.4f}",
            })

        lines = ["=== Analyse XGBoost (importances Gini — SHAP non disponible) ==="]
        for d in drivers[:3]:
            lines.append(f"• {d['label']} : {d['description']}")

        return ExplanationResult(
            model_name="xgboost",
            method="gini_importance",
            drivers=drivers,
            summary_text="\n".join(lines),
            metadata={"shap_available": False},
        )
