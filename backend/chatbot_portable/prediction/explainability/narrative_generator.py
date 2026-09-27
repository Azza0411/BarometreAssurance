"""
Génération de narratif textuel à partir de l'explication.

Ce module transforme l'ExplanationResult (technique) en un texte
lisible par le LLM Groq pour reformulation finale vers l'utilisateur.

Règle absolue : ce module ne calcule RIEN.
Il formate uniquement des résultats déjà calculés.
"""

from __future__ import annotations

from prediction.explainability.base_explainer import ExplanationResult
from prediction.models.base_model import PredictionOutput


class NarrativeGenerator:
    """
    Génère un narratif structuré combinant prévision + explication.
    Le texte produit est passé au LLM Groq pour reformulation.
    """

    def generate(
        self,
        kpi: str,
        company: str | None,
        prediction: PredictionOutput,
        explanation: ExplanationResult,
        unit: str,
    ) -> str:
        """
        Combine prévision + explication en un bloc texte pour le LLM.

        Args:
            kpi: nom canonique du KPI
            company: code compagnie ou None (marché)
            prediction: sortie du modèle (années + valeurs + intervalles)
            explanation: sortie de l'explainabilité (drivers)
            unit: unité (MDT, %, etc.)

        Returns:
            Texte structuré prêt pour le LLM
        """
        subject = company if company else "le marché"
        lines = [
            f"=== Prévision : {kpi} — {subject} ===",
            "",
            "Valeurs prévues :",
        ]

        for year, val, lo, hi in zip(
            prediction.years,
            prediction.values,
            prediction.lower_bound,
            prediction.upper_bound,
        ):
            lines.append(
                f"  • {year} : {val:.2f} {unit} "
                f"[intervalle {int(prediction.confidence_level*100)}% : "
                f"{lo:.2f} – {hi:.2f}]"
            )

        lines += [
            "",
            f"Modèle utilisé : {prediction.model_name}",
            f"Méthode d'explication : {explanation.method}",
            "",
            "Principaux facteurs explicatifs :",
        ]

        for driver in explanation.drivers[:3]:
            arrow = "↑" if driver.get("direction") in ("hausse", "accélération") else (
                "↓" if driver.get("direction") in ("baisse", "décélération") else "↔"
            )
            lines.append(f"  {arrow} {driver['label']} : {driver['description']}")

        lines += ["", explanation.summary_text]

        return "\n".join(lines)

    def generate_short(
        self,
        kpi: str,
        company: str | None,
        prediction: PredictionOutput,
        unit: str,
    ) -> str:
        """
        Version courte sans explication (pour réponses rapides).
        Utilisée quand l'explication n'est pas demandée.
        """
        subject = company if company else "le marché"
        parts = [f"Prévision {kpi} pour {subject} :"]
        for year, val in zip(prediction.years, prediction.values):
            parts.append(f"{year} → {val:.2f} {unit}")
        return " | ".join(parts)
