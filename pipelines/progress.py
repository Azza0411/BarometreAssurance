"""Phase actuelle du pipeline de collecte, partagée entre les modules
pipelines/* (jamais l'inverse d'un import api/ — même contrainte que
pipelines/control.py, pour éviter un import circulaire avec api/routes)
et l'API (api/routes/gestion_donnees.py, via statut_collecte()).

But : donner à l'utilisateur un message PRÉCIS pendant l'initialisation
("Récupération des documents...", "Calcul des indicateurs...") plutôt
qu'un simple "collecte en cours" opaque qui ne dit rien de la progression
réelle — retour utilisateur direct 2026-09-16 : "on voit que le scraping
a commencé, ensuite on voit que le calcul des KPI a également commencé,
jusqu'à ce que toute la plateforme soit fonctionnelle"."""

import threading

_lock = threading.Lock()
_phase = {"code": None}

PHASE_LABELS = {
    "scraping": "Récupération des documents (scraping)…",
    "extraction_kpi": "Calcul des indicateurs (KPI) en cours…",
    "grilles": "Extraction des tableaux détaillés en cours…",
    "qualite": "Contrôle de la qualité des données…",
    "veille": "Vérification des actualités et textes réglementaires…",
}


def set_phase(code):
    with _lock:
        _phase["code"] = code


def clear_phase():
    with _lock:
        _phase["code"] = None


def get_phase():
    with _lock:
        code = _phase["code"]
    return {"code": code, "label": PHASE_LABELS.get(code)}
