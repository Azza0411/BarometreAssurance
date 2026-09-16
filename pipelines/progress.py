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
_quick_ready = {"value": False}

PHASE_LABELS = {
    "scraping": "Récupération des documents (scraping)…",
    "extraction_kpi": "Calcul des indicateurs (KPI) en cours — année la plus récente…",
    "extraction_kpi_historique": "Complément de l'historique en arrière-plan…",
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


# Bascule séparée de `_phase` ci-dessus : signale que les données de
# l'exercice le plus récent (toutes sociétés) sont déjà en base et que la
# plateforme est donc utilisable, MÊME SI le pipeline continue encore en
# tâche de fond (complément de l'historique 2015-2025, grilles complètes,
# autres sources — voir cmf_pipeline.py::main()). Sans cette distinction,
# l'utilisateur attendrait la fin de TOUT le pipeline (plusieurs heures
# avec l'historique complet + OCR) avant de considérer la plateforme
# prête, alors que l'essentiel (dernier exercice) est disponible en
# quelques minutes — retour utilisateur direct 2026-09-16 : "on doit
# trouver une solution pour que le user n'attende que 5 minutes".
def mark_quick_ready():
    with _lock:
        _quick_ready["value"] = True


def clear_quick_ready():
    with _lock:
        _quick_ready["value"] = False


def is_quick_ready():
    with _lock:
        return _quick_ready["value"]
