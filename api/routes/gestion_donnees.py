"""Routes /api/gestion-donnees/* — page "Gestion de base de données" :
déclenchement de la collecte, liste des documents scrapés, export Excel
flexible (n'importe quelle combinaison Tableau × Société × Année).

Le pipeline complet (pipelines/run_pipeline.py::main, ~5 sources, retries
inclus) est un traitement long — il ne doit jamais tourner de façon
synchrone dans une requête HTTP (bloquerait le worker Flask, timeout côté
navigateur). Même schéma que le watcher de veille dans api/app.py : un
thread de fond dans le process Flask, statut interrogé par polling."""

import json
import os
import threading
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from database.repository import get_connection
from api.services.data_management import (
    list_documents_for_ui, get_local_pdf_path_for_document,
    get_filter_options, build_flexible_export_xlsx, get_reliability_stats,
)
from api.services import tableau_pipeline_service

bp = Blueprint("gestion_donnees", __name__)

_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "logs", "pipeline.log",
)

# État de la collecte, partagé par tout le process Flask (un seul worker en
# dev — voir app.py::app.run(..., use_reloader=False) — donc un simple
# verrou en mémoire suffit ; pas conçu pour un déploiement multi-worker).
_collecte_lock = threading.Lock()
_collecte_state = {"en_cours": False, "demarree_le": None, "annulation_demandee": False}


def _last_pipeline_end_from_log():
    """Relit la dernière ligne d'événement "pipeline_end" du journal JSON
    Lines (logs/pipeline.log) pour reconstituer le statut de la dernière
    exécution même après un redémarrage du serveur API (l'état en mémoire
    ci-dessus repart sinon toujours à zéro)."""
    if not os.path.isfile(_LOG_PATH):
        return None
    last = None
    try:
        with open(_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                except ValueError:
                    continue
                if evt.get("event") == "pipeline_end":
                    last = evt
    except OSError:
        return None
    return last


def _run_pipeline_background():
    from pipelines.run_pipeline import main as pipeline_main
    try:
        pipeline_main()
    except Exception as exc:
        print(f"[gestion_donnees] échec collecte manuelle : {exc}")
    finally:
        with _collecte_lock:
            _collecte_state["en_cours"] = False
            _collecte_state["annulation_demandee"] = False


@bp.route("/api/gestion-donnees/lancer-collecte", methods=["POST"])
def lancer_collecte():
    with _collecte_lock:
        if _collecte_state["en_cours"]:
            return jsonify({"lancee": False, "raison": "deja_en_cours"}), 409
        _collecte_state["en_cours"] = True
        _collecte_state["demarree_le"] = datetime.now().isoformat(timespec="seconds")
        _collecte_state["annulation_demandee"] = False
    threading.Thread(target=_run_pipeline_background, daemon=True).start()
    return jsonify({"lancee": True})


@bp.route("/api/gestion-donnees/annuler-collecte", methods=["POST"])
def annuler_collecte():
    """Demande l'annulation de la collecte en cours — coopérative, pas
    immédiate (voir pipelines/control.py) : le pipeline s'arrête au
    prochain point de contrôle (entre deux sociétés ou deux documents),
    quelques secondes à quelques dizaines de secondes au plus, jamais
    instantané (aucun moyen propre d'interrompre un thread Python au
    milieu d'un appel réseau/IO sans risquer un état à moitié écrit)."""
    from pipelines.control import request_cancel
    with _collecte_lock:
        if not _collecte_state["en_cours"]:
            return jsonify({"annulee": False, "raison": "aucune_collecte_en_cours"}), 409
        _collecte_state["annulation_demandee"] = True
    request_cancel()
    return jsonify({"annulee": True})


@bp.route("/api/gestion-donnees/statut-collecte")
def statut_collecte():
    with _collecte_lock:
        en_cours = _collecte_state["en_cours"]
        demarree_le = _collecte_state["demarree_le"]
        annulation_demandee = _collecte_state.get("annulation_demandee", False)
    derniere = _last_pipeline_end_from_log()
    return jsonify({
        "en_cours": en_cours,
        "demarree_le": demarree_le,
        "annulation_demandee": annulation_demandee,
        "derniere_execution": derniere,
    })


# État de la pipeline de validation Annexe 13 (extraction + normalisation +
# règles métier, voir extraction/annexe13_pipeline.py) — même schéma
# thread + verrou que la collecte ci-dessus, sur un état séparé (les deux
# traitements sont indépendants et peuvent tourner l'un sans l'autre).
_validation_lock = threading.Lock()
_validation_state = {"en_cours": False, "demarree_le": None, "progression": None, "derniere": None}


def _run_validation_background(codes, annees):
    def _progress(done, total):
        with _validation_lock:
            _validation_state["progression"] = {"fait": done, "total": total}
    try:
        summary = tableau_pipeline_service.process_all(codes, annees, progress_callback=_progress)
        with _validation_lock:
            _validation_state["derniere"] = {
                **summary, "terminee_le": datetime.now().isoformat(timespec="seconds"),
            }
    except Exception as exc:
        print(f"[gestion_donnees] échec validation Annexe 13 : {exc}")
    finally:
        with _validation_lock:
            _validation_state["en_cours"] = False
            _validation_state["progression"] = None


@bp.route("/api/gestion-donnees/valider-annexe13", methods=["POST"])
def valider_annexe13():
    """Lance (en tâche de fond) l'extraction complète + normalisation +
    validation Annexe 13 pour les documents CMF filtrés (tous par défaut) et
    stocke le résultat en base (tableau_cellules/tableau_validations) — un
    passage nécessaire avant que l'export Excel puisse servir ces documents
    depuis la base plutôt que re-parser leur PDF à chaque requête."""
    codes = request.args.getlist("societe") or None
    annees_raw = request.args.getlist("annee")
    try:
        annees = [int(a) for a in annees_raw] or None
    except ValueError:
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400

    with _validation_lock:
        if _validation_state["en_cours"]:
            return jsonify({"lancee": False, "raison": "deja_en_cours"}), 409
        _validation_state["en_cours"] = True
        _validation_state["demarree_le"] = datetime.now().isoformat(timespec="seconds")
        _validation_state["progression"] = None
    threading.Thread(target=_run_validation_background, args=(codes, annees), daemon=True).start()
    return jsonify({"lancee": True})


@bp.route("/api/gestion-donnees/statut-validation-annexe13")
def statut_validation_annexe13():
    with _validation_lock:
        return jsonify(dict(_validation_state))


@bp.route("/api/gestion-donnees/documents")
def documents():
    conn = get_connection()
    try:
        return jsonify(list_documents_for_ui(conn))
    finally:
        conn.close()


@bp.route("/api/gestion-donnees/documents/<int:document_id>/pdf")
def document_pdf(document_id):
    conn = get_connection()
    try:
        path = get_local_pdf_path_for_document(conn, document_id)
    finally:
        conn.close()
    if not path:
        return jsonify({"error": "Aucun fichier local pour ce document"}), 404
    return send_file(path, mimetype="application/pdf", as_attachment=False,
                      download_name=os.path.basename(path))


@bp.route("/api/gestion-donnees/filtres")
def filtres():
    conn = get_connection()
    try:
        return jsonify(get_filter_options(conn))
    finally:
        conn.close()


@bp.route("/api/gestion-donnees/fiabilite")
def fiabilite():
    conn = get_connection()
    try:
        return jsonify(get_reliability_stats(conn))
    finally:
        conn.close()


@bp.route("/api/gestion-donnees/export.xlsx")
def export_xlsx():
    tableaux = request.args.getlist("tableau")
    codes = request.args.getlist("societe")
    annees_raw = request.args.getlist("annee")
    try:
        annees = [int(a) for a in annees_raw]
    except ValueError:
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400

    buffer = build_flexible_export_xlsx(
        tableau_keys=tableaux or None, codes=codes or None, annees=annees or None,
    )
    return send_file(
        buffer, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True, download_name="Export_donnees.xlsx",
    )
