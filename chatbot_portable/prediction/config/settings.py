"""
Configuration globale du module prediction.
Tous les paramètres sont ici — aucun magic string ailleurs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ── Chemins ──────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent.parent.parent   # racine projet
PREDICTION_DIR = ROOT_DIR / "prediction"
STORAGE_DIR = PREDICTION_DIR / "storage" / "models"
CACHE_DIR = PREDICTION_DIR / "storage" / "cache"
REGISTRY_PATH = PREDICTION_DIR / "storage" / "registry.json"
LOG_DIR = ROOT_DIR / "logs"

# Créer les dossiers si absents
for _d in (STORAGE_DIR, CACHE_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── KPIs supportés ───────────────────────────────────────────────────────────

# KPI exact tel que stocké dans kpi_values.kpi
SUPPORTED_KPIS: list[str] = [
    "Primes émises par assurance",
    "Part de marché (%)",
    "Résultat Net",
    "Total actif",
    "Capitaux propres",
    "Ratio combiné (%)",
    "Ratio de sinistralité (%)",
    "Ratio de frais de gestion (%)",
    "ROE (%)",
    "ROA (%)",
    "Charge de sinistres",
    # Marché FTUSA
    "Total Primes émises",
    "Taux de pénétration",
    "Densité de l'assurance",
    "Primes émises Vie",
    "Primes émises Non-Vie",
]

# Synonymes → KPI canonique (pour la détection d'intention)
KPI_ALIASES: dict[str, str] = {
    "primes": "Primes émises par assurance",
    "primes émises": "Primes émises par assurance",
    "chiffre d'affaires": "Primes émises par assurance",
    "pdm": "Part de marché (%)",
    "part de marché": "Part de marché (%)",
    "résultat": "Résultat Net",
    "résultat net": "Résultat Net",
    "bénéfice": "Résultat Net",
    "actif": "Total actif",
    "bilan": "Total actif",
    "capitaux propres": "Capitaux propres",
    "fonds propres": "Capitaux propres",
    "ratio combiné": "Ratio combiné (%)",
    "ratio s/p": "Ratio de sinistralité (%)",
    "sinistralité": "Ratio de sinistralité (%)",
    "roe": "ROE (%)",
    "roa": "ROA (%)",
    "sinistres": "Charge de sinistres",
    "primes marché": "Total Primes émises",
    "total primes": "Total Primes émises",
    "pénétration": "Taux de pénétration",
    "densité": "Densité de l'assurance",
}


# ── Paramètres modèles ────────────────────────────────────────────────────────

@dataclass
class ProphetConfig:
    yearly_seasonality: bool = True
    weekly_seasonality: bool = False
    daily_seasonality: bool = False
    seasonality_mode: str = "multiplicative"   # adapté aux séries financières
    changepoint_prior_scale: float = 0.05       # flexibilité de la tendance
    seasonality_prior_scale: float = 10.0
    interval_width: float = 0.80                # intervalle de confiance 80%
    uncertainty_samples: int = 500


@dataclass
class XGBoostConfig:
    n_estimators: int = 200
    max_depth: int = 4
    learning_rate: float = 0.05
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    min_child_weight: int = 2
    reg_alpha: float = 0.1
    reg_lambda: float = 1.0
    random_state: int = 42
    n_jobs: int = -1


@dataclass
class TrainingConfig:
    min_data_points: int = 5          # minimum pour entraîner
    test_size: int = 2                # années pour validation finale
    n_splits: int = 3                 # folds TimeSeriesSplit
    retrain_on_new_data: bool = True
    max_horizon: int = 5              # prévision max en années


@dataclass
class PredictionConfig:
    prophet: ProphetConfig = field(default_factory=ProphetConfig)
    xgboost: XGBoostConfig = field(default_factory=XGBoostConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    cache_ttl_hours: int = 24


# Instance globale (singleton)
CONFIG = PredictionConfig()
