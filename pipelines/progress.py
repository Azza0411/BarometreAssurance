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
    "extraction_kpi": "Calcul des indicateurs (KPI) en cours…",
    "sources_prioritaires": "Récupération des données sectorielles (FTUSA, CGA, INS, BVMT)…",
    "grilles": "Complément des tableaux détaillés en arrière-plan (Correction manuelle)…",
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


# Bascule séparée de `_phase` ci-dessus : signale que les sources
# PRIORITAIRES pour Aperçu marché/Analyse comparative/Vue par assurance —
# CMF (5 ans, narrow KPI, Takaful inclus) + FTUSA + CGA + INS + BVMT —
# sont là, et que la plateforme est donc utilisable pour ces 3 pages,
# MÊME SI le pipeline continue en tâche de fond (les 6 grilles complètes,
# qui n'alimentent que "Correction manuelle" — voir
# pipelines/run_pipeline.py::main(), PRIORITY_SOURCE_NAMES). Décision du
# 2026-09-16 : le bandeau de collecte reste affiché jusqu'à la fin RÉELLE
# (voir CollecteBanner.jsx) — ce flag ne masque plus rien côté UI, il ne
# sert plus qu'à distinguer, sur la page Gestion de données, "l'essentiel
# est prêt, il ne reste que le détail" de "rien n'est encore prêt".
def mark_quick_ready():
    with _lock:
        _quick_ready["value"] = True


def clear_quick_ready():
    with _lock:
        _quick_ready["value"] = False


def is_quick_ready():
    with _lock:
        return _quick_ready["value"]
