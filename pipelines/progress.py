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
    "rattrapage_pdf": "Téléchargement des PDF locaux manquants…",
    "scraping": "Récupération des documents (scraping)…",
    "extraction_kpi": "Calcul des indicateurs (KPI) en cours…",
    "sources_prioritaires": "Récupération des données sectorielles (FTUSA, CGA, INS, BVMT)…",
    "grilles": "Complément des tableaux détaillés en arrière-plan (Correction manuelle)…",
    "qualite": "Contrôle de la qualité des données…",
    "veille": "Vérification des actualités et textes réglementaires…",
}


# ── Avancement chiffré (x/y) de la phase courante ──────────────────────────
# Retour du responsable pro (2026-09-21) : "le scraping tourne indéfiniment
# et on ne sait pas où il en est". Le message de phase seul (ci-dessus) dit
# QUOI, pas COMBIEN : ce compteur dit "42 sur 224 documents, en ce moment
# STAR 2024", et `get_progress()` en déduit un pourcentage GLOBAL pondéré
# sur les phases prévues pour ce run (voir set_plan).
_counter = {"done": 0, "total": 0, "detail": None}
_plan = {"phases": []}

# Poids relatifs (durée typique observée) — seules les phases PRÉVUES pour
# le run en cours comptent (voir set_plan), le pourcentage global est donc
# toujours ramené à 100 même pour un rattrapage partiel au démarrage.
PHASE_WEIGHTS = {
    "rattrapage_pdf": 15,
    "scraping": 20,
    "extraction_kpi": 30,
    "sources_prioritaires": 15,
    "grilles": 20,
    "qualite": 5,
    "veille": 5,
}
FULL_PLAN = ["scraping", "rattrapage_pdf", "extraction_kpi", "sources_prioritaires", "grilles", "qualite", "veille"]
CATCHUP_PLAN = ["rattrapage_pdf", "extraction_kpi"]


def set_plan(phases):
    """Déclare les phases qui vont s'enchaîner pour CE run (dans l'ordre)."""
    with _lock:
        _plan["phases"] = list(phases)


def reset_progress(total=0, detail=None):
    """Nouveau compteur pour la phase courante (total inconnu -> 0)."""
    with _lock:
        _counter["done"] = 0
        _counter["total"] = int(total or 0)
        _counter["detail"] = detail


def set_progress(done, total=None, detail=None):
    with _lock:
        _counter["done"] = int(done)
        if total is not None:
            _counter["total"] = int(total)
        if detail is not None:
            _counter["detail"] = detail


def bump_progress(detail=None):
    """+1 fait (appelable depuis plusieurs threads en parallèle)."""
    with _lock:
        _counter["done"] += 1
        if detail is not None:
            _counter["detail"] = detail


def get_progress():
    """{"done","total","detail","pourcentage"} — `pourcentage` est global
    (0-100, ou None si aucun plan n'est déclaré / phase hors plan)."""
    with _lock:
        code = _phase["code"]
        done, total, detail = _counter["done"], _counter["total"], _counter["detail"]
        phases = list(_plan["phases"])
    pct = None
    if code in phases:
        total_weight = sum(PHASE_WEIGHTS.get(c, 0) for c in phases) or 1
        before = sum(PHASE_WEIGHTS.get(c, 0) for c in phases[: phases.index(code)])
        frac = min(done / total, 1.0) if total > 0 else 0.0
        pct = round(100 * (before + PHASE_WEIGHTS.get(code, 0) * frac) / total_weight)
        # Jamais 100 % tant que le run tourne : la fin d'une boucle de documents
        # est suivie d'étapes (sources sectorielles, KPI calculés...) — le 100 %
        # n'apparaît que par la disparition du bandeau (collecte terminée).
        pct = min(pct, 99)
    return {"done": done, "total": total, "detail": detail, "pourcentage": pct}


def set_phase(code):
    with _lock:
        _phase["code"] = code
        # Chaque nouvelle phase repart d'un compteur vierge : sans ça, le
        # "42/224" de la phase précédente resterait affiché.
        _counter["done"], _counter["total"], _counter["detail"] = 0, 0, None


def drop_from_plan(code):
    """Retire une phase du plan quand on sait qu'elle n'aura rien à faire
    (ex. aucun PDF local manquant à rattraper) : le pourcentage global ne
    doit pas sauter d'emblée de son poids comme si elle avait été faite."""
    with _lock:
        if code in _plan["phases"]:
            _plan["phases"].remove(code)


def enter_phase_if_planned(code):
    """Passe à `code` seulement s'il fait partie du plan du run en cours —
    permet à extraction/kpi_extraction_pipeline.py (appelé aussi bien par le
    pipeline complet que par le rattrapage au démarrage) de signaler ses
    sous-étapes sans jamais inventer une phase hors plan."""
    with _lock:
        planned = code in _plan["phases"]
    if planned:
        set_phase(code)
    return planned


def clear_phase():
    with _lock:
        _phase["code"] = None
        _counter["done"], _counter["total"], _counter["detail"] = 0, 0, None
        _plan["phases"] = []


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
