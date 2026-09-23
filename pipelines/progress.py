"""Phase actuelle du pipeline de collecte, partagée entre les modules
pipelines/* (jamais l'inverse d'un import api/ — même contrainte que
pipelines/control.py, pour éviter un import circulaire avec api/routes)
et l'API (api/routes/gestion_donnees.py, via statut_collecte()).

But : donner à l'utilisateur un message PRÉCIS pendant l'initialisation
("Récupération des documents...", "Calcul des indicateurs...") plutôt
qu'un simple "collecte en cours" opaque qui ne dit rien de la progression
réelle — retour utilisateur direct 2026-09-16 : "on voit que le scraping
a commencé, ensuite on voit que le calcul des KPI a également commencé,
jusqu'à ce que toute la plateforme soit fonctionnelle".

Depuis 2026-09-23 (retour du responsable pro : "on ne sait pas où en est le
scraping"), ce module expose aussi :
  - l'avancement chiffré de la phase courante (x sur y + élément en cours),
  - la liste des ÉTAPES du run (terminée / en cours / à venir),
  - un pourcentage global pondéré,
  - une ESTIMATION du temps restant, auto-calibrée : la durée réellement
    observée de chaque phase est mémorisée (logs/phase_durations.json) et
    sert d'a priori au run suivant ; au sein d'un run, la vitesse observée
    corrige l'estimation des phases restantes."""

import json
import os
import threading
import time

_lock = threading.Lock()
_phase = {"code": None, "started": None}
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

# Libellés COURTS pour la frise d'étapes du bandeau + unité de comptage.
PHASE_SHORT = {
    "scraping": "Documents CMF",
    "rattrapage_pdf": "PDF locaux",
    "extraction_kpi": "Calcul des KPI",
    "sources_prioritaires": "Sources sectorielles",
    "grilles": "Tableaux détaillés",
    "qualite": "Contrôle qualité",
    "veille": "Actualités",
}
PHASE_UNITS = {
    "scraping": "sociétés",
    "rattrapage_pdf": "PDF",
    "extraction_kpi": "documents",
    "sources_prioritaires": "sources",
    "grilles": "sources",
}

# ── Avancement chiffré (x/y) de la phase courante ──────────────────────────
_counter = {"done": 0, "total": 0, "detail": None}
_plan = {"phases": []}
_run = {"kind": None, "started": None, "done": [], "observed": {}}

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

# A priori de durée (secondes) tant qu'aucun run n'a encore été mesuré sur
# cette machine — calibrés sur les anciens pipelines complets de 12 à 30 min
# (logs/pipeline.log, event pipeline_end). Remplacés dès le 1er run terminé
# par la durée réellement observée (voir _save_observed).
DEFAULT_PRIOR_S = {
    "full": {"scraping": 240, "rattrapage_pdf": 120, "extraction_kpi": 420,
             "sources_prioritaires": 150, "grilles": 300, "qualite": 20, "veille": 20},
    "catchup": {"rattrapage_pdf": 120, "extraction_kpi": 30},
}

_DURATIONS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "phase_durations.json",
)


def _load_observed():
    try:
        with open(_DURATIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_observed(kind, code, seconds):
    """Mémorise la durée réelle d'une phase terminée (meilleure-effort : une
    erreur d'écriture ne doit jamais gêner la collecte)."""
    if not kind or seconds is None or seconds < 1:
        return
    try:
        data = _load_observed()
        data.setdefault(kind, {})[code] = round(float(seconds), 1)
        os.makedirs(os.path.dirname(_DURATIONS_PATH), exist_ok=True)
        tmp = _DURATIONS_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, _DURATIONS_PATH)
    except Exception:
        pass


def _cancel_requested():
    try:
        from pipelines.control import is_cancel_requested
        return bool(is_cancel_requested())
    except Exception:
        return False


def set_plan(phases, kind="full"):
    """Déclare les phases qui vont s'enchaîner pour CE run (dans l'ordre) et
    son type ("full" = collecte complète, "catchup" = rattrapage au
    démarrage) ; démarre le chronomètre du run."""
    observed = _load_observed()
    with _lock:
        _plan["phases"] = list(phases)
        _run["kind"] = kind
        _run["started"] = time.monotonic()
        _run["done"] = []
        _run["observed"] = observed


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


def _prior(kind, code):
    observed = _run["observed"].get(kind, {}) if kind else {}
    return float(observed.get(code) or DEFAULT_PRIOR_S.get(kind, {}).get(code) or 60)


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _estimate_remaining(now):
    """Secondes restantes estimées (None tant qu'on n'a pas assez de recul).
    Appelée avec `_lock` tenu."""
    code, phases, kind = _phase["code"], _plan["phases"], _run["kind"]
    if code not in phases or _run["started"] is None or _phase["started"] is None:
        return None
    if now - _run["started"] < 15:
        return None  # trop tôt : "estimation en cours…"
    idx = phases.index(code)
    cur_elapsed = now - _phase["started"]
    prior_cur = _prior(kind, code)
    done, total = _counter["done"], _counter["total"]

    # Vitesse relative de CE run par rapport à l'a priori, mesurée sur les
    # phases déjà terminées : corrige aussi l'estimation des phases à venir.
    obs = sum(s for c, s in _run["done"] if c in phases)
    pri = sum(_prior(kind, c) for c, _s in _run["done"] if c in phases)
    factor = _clamp(obs / pri, 0.4, 3.0) if obs > 0 and pri > 0 else None

    if total > 0 and (done >= 2 or (done >= 1 and cur_elapsed > 10)):
        cur_total = cur_elapsed * total / done
        cur_remaining = max(cur_total - cur_elapsed, 0.0)
        if factor is None:
            factor = _clamp(cur_total / prior_cur, 0.4, 3.0)
    else:
        expected = prior_cur * (factor or 1.0)
        cur_remaining = max(expected - cur_elapsed, expected * 0.25)

    future = sum(_prior(kind, p) for p in phases[idx + 1:]) * (factor or 1.0)
    return cur_remaining + future


def get_progress():
    """Avancement complet du run en cours — voir la docstring du module.
    `pourcentage` est global (0-100, ou None si aucun plan n'est déclaré /
    phase hors plan) ; `etapes` liste les phases du run avec leur statut ;
    `reste_s` est l'estimation du temps restant (None = pas encore calculable)."""
    now = time.monotonic()
    with _lock:
        code = _phase["code"]
        done, total, detail = _counter["done"], _counter["total"], _counter["detail"]
        phases = list(_plan["phases"])
        kind = _run["kind"]
        finished = dict(_run["done"])
        started = _run["started"]
        reste = _estimate_remaining(now)
    pct = None
    etapes = []
    etape_index = None
    if code in phases:
        total_weight = sum(PHASE_WEIGHTS.get(c, 0) for c in phases) or 1
        before = sum(PHASE_WEIGHTS.get(c, 0) for c in phases[: phases.index(code)])
        frac = min(done / total, 1.0) if total > 0 else 0.0
        pct = round(100 * (before + PHASE_WEIGHTS.get(code, 0) * frac) / total_weight)
        # Jamais 100 % tant que le run tourne : la fin d'une boucle de documents
        # est suivie d'étapes (sources sectorielles, KPI calculés...) — le 100 %
        # n'apparaît que par la disparition du bandeau (collecte terminée).
        pct = min(pct, 99)
        cur_idx = phases.index(code)
        etape_index = cur_idx + 1
        for i, c in enumerate(phases):
            statut = "terminee" if i < cur_idx else ("en_cours" if i == cur_idx else "a_venir")
            etapes.append({
                "code": c, "label": PHASE_SHORT.get(c, c), "statut": statut,
                "duree_s": round(finished[c]) if c in finished else None,
            })
    return {
        "done": done, "total": total, "detail": detail, "pourcentage": pct,
        "type": kind,
        "unite": PHASE_UNITS.get(code),
        "restantes": max(total - done, 0) if total > 0 else None,
        "etapes": etapes,
        "etape_index": etape_index,
        "etapes_total": len(phases),
        "ecoule_s": round(now - started) if started is not None else None,
        "reste_s": round(reste) if reste is not None else None,
    }


def set_phase(code):
    save = None
    with _lock:
        prev, now = _phase["code"], time.monotonic()
        if prev is not None and prev != code and _phase["started"] is not None:
            secs = now - _phase["started"]
            _run["done"].append((prev, secs))
            save = (_run["kind"], prev, secs)
        if prev != code:
            _phase["started"] = now
        _phase["code"] = code
        # Chaque nouvelle phase repart d'un compteur vierge : sans ça, le
        # "42/224" de la phase précédente resterait affiché.
        _counter["done"], _counter["total"], _counter["detail"] = 0, 0, None
    if save and not _cancel_requested():
        _save_observed(*save)


def drop_from_plan(code):
    """Retire une phase du plan quand on sait qu'elle n'aura rien à faire
    (ex. aucun PDF local manquant à rattraper) : le pourcentage global ne
    doit pas sauter d'emblée de son poids comme si elle avait été faite.
    Si c'est la phase COURANTE, on passe aussitôt à la suivante du plan."""
    with _lock:
        phases = _plan["phases"]
        if code not in phases:
            return
        idx = phases.index(code)
        phases.remove(code)
        if _phase["code"] == code:
            nxt = phases[idx] if idx < len(phases) else None
            _phase["code"] = nxt
            _phase["started"] = time.monotonic() if nxt else None
            _counter["done"], _counter["total"], _counter["detail"] = 0, 0, None


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
    """Fin du run : mémorise la durée de la dernière phase (sauf annulation)
    et efface tout l'état d'avancement."""
    save = None
    with _lock:
        if _phase["code"] is not None and _phase["started"] is not None:
            save = (_run["kind"], _phase["code"], time.monotonic() - _phase["started"])
        _phase["code"], _phase["started"] = None, None
        _counter["done"], _counter["total"], _counter["detail"] = 0, 0, None
        _plan["phases"] = []
        _run["kind"], _run["started"], _run["done"] = None, None, []
    if save and not _cancel_requested():
        _save_observed(*save)


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
