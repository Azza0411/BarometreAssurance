"""
Validation des entrées utilisateur avant de lancer le pipeline.
Fail-fast : erreur claire dès le début, pas au milieu du pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass

from prediction.config.settings import SUPPORTED_KPIS, KPI_ALIASES, CONFIG


@dataclass
class ValidationResult:
    is_valid: bool
    kpi: str | None          # KPI canonique résolu
    company: str | None
    horizon: int
    errors: list[str]
    warnings: list[str]


class InputValidator:
    """Valide et normalise les paramètres d'une requête de prévision."""

    def __init__(self, available_companies: list[str]):
        self._companies = {c.upper() for c in available_companies}

    def validate(
        self,
        kpi: str,
        company: str | None,
        horizon: int,
    ) -> ValidationResult:
        """
        Valide et normalise les entrées.

        Args:
            kpi: KPI demandé (peut être un alias)
            company: code compagnie ou None (marché)
            horizon: nombre d'années de prévision

        Returns:
            ValidationResult avec le KPI résolu et les erreurs éventuelles
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Résolution du KPI
        resolved_kpi = self._resolve_kpi(kpi)
        if resolved_kpi is None:
            errors.append(
                f"KPI inconnu : '{kpi}'. "
                f"KPIs supportés : {', '.join(SUPPORTED_KPIS[:5])}..."
            )

        # Validation compagnie
        resolved_company = None
        if company:
            resolved_company = company.upper()
            if resolved_company not in self._companies:
                errors.append(
                    f"Compagnie inconnue : '{company}'. "
                    f"Exemples : STAR, COMAR, AMI, GAT, MAGHREBIA"
                )

        # Validation horizon
        max_h = CONFIG.training.max_horizon
        if horizon < 1:
            errors.append("L'horizon doit être d'au moins 1 an.")
        elif horizon > max_h:
            warnings.append(
                f"Horizon limité à {max_h} ans pour la fiabilité. "
                f"Demandé : {horizon} ans."
            )
            horizon = max_h

        return ValidationResult(
            is_valid=len(errors) == 0,
            kpi=resolved_kpi,
            company=resolved_company,
            horizon=horizon,
            errors=errors,
            warnings=warnings,
        )

    def _resolve_kpi(self, kpi: str) -> str | None:
        """Résout un alias vers le KPI canonique."""
        # Match exact
        if kpi in SUPPORTED_KPIS:
            return kpi
        # Alias normalisé
        normalized = kpi.lower().strip()
        if normalized in KPI_ALIASES:
            return KPI_ALIASES[normalized]
        # Recherche partielle dans les alias
        for alias, canonical in KPI_ALIASES.items():
            if alias in normalized or normalized in alias:
                return canonical
        return None
