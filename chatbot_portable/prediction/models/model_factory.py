"""
Factory pour l'instanciation des modèles et la sélection des explaineurs.

Pattern Factory : le chatbot (et le reste du pipeline) n'a jamais besoin
d'importer ProphetModel ou XGBoostModel directement.
Ajouter un nouveau modèle = créer une classe + l'enregistrer ici.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from prediction.models.base_model import BaseModel
from prediction.models.prophet_model import ProphetModel
from prediction.models.xgboost_model import XGBoostModel

if TYPE_CHECKING:
    from prediction.explainability.base_explainer import BaseExplainer

logger = logging.getLogger(__name__)

# Registre : nom_modèle → classe
_MODEL_REGISTRY: dict[str, type[BaseModel]] = {
    "prophet": ProphetModel,
    "xgboost": XGBoostModel,
}

# KPIs pour lesquels Prophet est préféré par défaut
# (séries longues, tendance structurelle dominante)
_PROPHET_PREFERRED_KPIS: set[str] = {
    "Total Primes émises",
    "Primes émises Vie",
    "Primes émises Non-Vie",
    "Taux de pénétration",
    "Densité de l'assurance",
    "Population Totale",
    "Produit Interieur Brut (PIB)",
}

# KPIs pour lesquels XGBoost est préféré (ratios financiers plus volatils)
_XGBOOST_PREFERRED_KPIS: set[str] = {
    "Ratio combiné (%)",
    "Ratio de sinistralité (%)",
    "Ratio de frais de gestion (%)",
    "ROE (%)",
    "ROA (%)",
    "Part de marché (%)",
}


class ModelFactory:
    """
    Crée les instances de modèles et les explaineurs associés.

    Usage:
        factory = ModelFactory()
        model = factory.create_model("prophet")
        explainer = factory.create_explainer(model)
    """

    def create_model(self, model_name: str) -> BaseModel:
        """
        Instancie un modèle par son nom.

        Args:
            model_name: 'prophet' | 'xgboost'

        Returns:
            Instance du modèle (non entraîné)

        Raises:
            ValueError: si le nom est inconnu
        """
        model_name = model_name.lower().strip()
        if model_name not in _MODEL_REGISTRY:
            available = list(_MODEL_REGISTRY.keys())
            raise ValueError(
                f"Modèle inconnu : '{model_name}'. Disponibles : {available}"
            )
        model = _MODEL_REGISTRY[model_name]()
        logger.debug(f"ModelFactory: instancié {model_name}")
        return model

    def get_candidate_models(self, kpi: str, n_points: int) -> list[str]:
        """
        Retourne les modèles candidats pour un KPI donné.

        Logique :
        - Si < 7 points → Prophet uniquement (XGBoost manque de données pour lags)
        - Si KPI préféré Prophet → tester Prophet en premier
        - Si KPI préféré XGBoost → tester XGBoost en premier
        - Sinon → tester les deux (le meilleur est sélectionné par l'évaluateur)

        Args:
            kpi: nom canonique du KPI
            n_points: nombre de points historiques disponibles

        Returns:
            Liste ordonnée de noms de modèles à tester
        """
        if n_points < 7:
            # XGBoost ne peut pas construire suffisamment de lags
            logger.info(
                f"Seulement {n_points} points → Prophet uniquement pour '{kpi}'"
            )
            return ["prophet"]

        if kpi in _PROPHET_PREFERRED_KPIS:
            return ["prophet", "xgboost"]
        elif kpi in _XGBOOST_PREFERRED_KPIS:
            return ["xgboost", "prophet"]
        else:
            # Tester les deux, laisser l'évaluateur décider
            return ["prophet", "xgboost"]

    def create_explainer(self, model: BaseModel) -> "BaseExplainer":
        """
        Crée l'explaineur approprié selon le type de modèle.

        Factory pour l'explainabilité :
        - ProphetModel → ProphetExplainer (décomposition trend/saisonnalité)
        - XGBoostModel → ShapExplainer (SHAP values)

        Args:
            model: instance de modèle entraîné

        Returns:
            Explaineur correspondant au modèle

        Raises:
            ValueError: si le type de modèle n'est pas reconnu
        """
        # Import différé pour éviter circularité
        from prediction.explainability.prophet_explainer import ProphetExplainer
        from prediction.explainability.shap_explainer import ShapExplainer

        if isinstance(model, ProphetModel):
            explainer = ProphetExplainer(model)
            logger.debug("ModelFactory: explaineur → ProphetExplainer")
            return explainer
        elif isinstance(model, XGBoostModel):
            explainer = ShapExplainer(model)
            logger.debug("ModelFactory: explaineur → ShapExplainer")
            return explainer
        else:
            raise ValueError(
                f"Aucun explaineur pour le type de modèle : {type(model).__name__}"
            )

    def list_available_models(self) -> list[str]:
        """Retourne la liste des modèles disponibles."""
        return list(_MODEL_REGISTRY.keys())

    @staticmethod
    def get_default_model_for_kpi(kpi: str) -> str:
        """
        Modèle par défaut (sans cross-validation) pour un KPI donné.
        Utilisé uniquement en mode dégradé (pas assez de données pour CV).
        """
        if kpi in _PROPHET_PREFERRED_KPIS:
            return "prophet"
        return "xgboost"
