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

from database.repository import get_connection, get_document_id, apply_manual_corrections, CorrectionError
from api.services.data_management import (
    list_documents_for_ui, get_local_pdf_path_for_document,
    get_filter_options, build_flexible_export_xlsx, get_reliability_stats,
    get_document_grid, get_referentiel, page_source_info, kpi_raw_labels_for,
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
_collecte_state = {"en_cours": False, "demarree_le": None, "annulation_demandee": False, "source": None}


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
    from pipelines.progress import clear_phase
    try:
        pipeline_main()
    except Exception as exc:
        print(f"[gestion_donnees] échec collecte : {exc}")
    finally:
        # Filet de sécurité : main() efface déjà la phase à la fin de son
        # déroulement normal, mais une exception NON prévue avant ce point
        # (plutôt qu'une source individuelle en échec, déjà capturée par
        # run_with_retry) laisserait sinon le dernier message de phase
        # affiché pour toujours, alors que la collecte est bel et bien
        # terminée (en_cours repasse à False juste en dessous).
        clear_phase()
        with _collecte_lock:
            _collecte_state["en_cours"] = False
            _collecte_state["annulation_demandee"] = False


def ensure_pipeline_running(source="manuelle"):
    """Démarre le pipeline complet en tâche de fond s'il ne tourne pas déjà
    — factorisé hors de `lancer_collecte()` pour que le déclenchement
    AUTOMATIQUE au premier lancement (voir api/app.py::_first_run_scrape_loop)
    partage le MÊME état que celui déclenché à la main depuis "Gestion de
    données" : sans ça, `/api/gestion-donnees/statut-collecte` (et donc
    tout bandeau qui s'y abonne) ne reflétait jamais la collecte
    automatique — seul un clic manuel sur "Lancer une nouvelle collecte"
    la mettait à jour (constaté 2026-09-15, retour utilisateur direct :
    aucune indication visible qu'une collecte tournait après un premier
    lancement sur base vide). Renvoie True si une collecte a été démarrée
    par CET appel, False si une était déjà en cours (idempotent)."""
    with _collecte_lock:
        if _collecte_state["en_cours"]:
            return False
        _collecte_state["en_cours"] = True
        _collecte_state["demarree_le"] = datetime.now().isoformat(timespec="seconds")
        _collecte_state["annulation_demandee"] = False
        _collecte_state["source"] = source
    threading.Thread(target=_run_pipeline_background, daemon=True).start()
    return True


@bp.route("/api/gestion-donnees/lancer-collecte", methods=["POST"])
def lancer_collecte():
    if not ensure_pipeline_running(source="manuelle"):
        return jsonify({"lancee": False, "raison": "deja_en_cours"}), 409
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
    from pipelines.progress import get_phase, is_quick_ready
    with _collecte_lock:
        en_cours = _collecte_state["en_cours"]
        demarree_le = _collecte_state["demarree_le"]
        annulation_demandee = _collecte_state.get("annulation_demandee", False)
        source = _collecte_state.get("source")
    derniere = _last_pipeline_end_from_log()
    phase = get_phase() if en_cours else {"code": None, "label": None}
    return jsonify({
        "en_cours": en_cours,
        "demarree_le": demarree_le,
        "annulation_demandee": annulation_demandee,
        "source": source,
        "derniere_execution": derniere,
        "phase": phase["code"],
        "phase_label": phase["label"],
        # Vrai dès que les sources prioritaires pour Aperçu marché/Analyse
        # comparative/Vue par assurance (CMF + FTUSA/CGA/INS/BVMT) sont en
        # base, même si `en_cours` reste vrai (complément des grilles
        # complètes en arrière-plan, voir pipelines/run_pipeline.py::main(),
        # PRIORITY_SOURCE_NAMES). Ne masque plus le bandeau de collecte
        # (CollecteBanner.jsx reste affiché jusqu'à la fin réelle, décision
        # du 2026-09-16) — utilisé seulement par "Gestion de données" pour
        # nuancer son message pendant le complément.
        "sources_prioritaires_pretes": is_quick_ready(),
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


# État de la pipeline de validation Bilan (Actif/Passif) — même schéma
# thread + verrou que Annexe 13 ci-dessus, sur un état séparé (indépendant,
# peut tourner en même temps ou pas du tout).
_validation_bilan_lock = threading.Lock()
_validation_bilan_state = {"en_cours": False, "demarree_le": None, "progression": None, "derniere": None}


def _run_validation_bilan_background(codes, annees):
    from api.services import tableau_pipeline_service_bilan

    def _progress(done, total):
        with _validation_bilan_lock:
            _validation_bilan_state["progression"] = {"fait": done, "total": total}
    try:
        summary = tableau_pipeline_service_bilan.process_all(codes, annees, progress_callback=_progress)
        with _validation_bilan_lock:
            _validation_bilan_state["derniere"] = {
                **summary, "terminee_le": datetime.now().isoformat(timespec="seconds"),
            }
    except Exception as exc:
        print(f"[gestion_donnees] échec validation Bilan : {exc}")
    finally:
        with _validation_bilan_lock:
            _validation_bilan_state["en_cours"] = False
            _validation_bilan_state["progression"] = None


@bp.route("/api/gestion-donnees/valider-bilan", methods=["POST"])
def valider_bilan():
    """Lance (en tâche de fond) l'extraction + validation Bilan Actif/
    Passif pour les documents CMF filtrés (tous par défaut) — voir
    extraction/bilan_full_extractor.py::process_bilan. Même schéma que
    /valider-annexe13."""
    codes = request.args.getlist("societe") or None
    annees_raw = request.args.getlist("annee")
    try:
        annees = [int(a) for a in annees_raw] or None
    except ValueError:
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400

    with _validation_bilan_lock:
        if _validation_bilan_state["en_cours"]:
            return jsonify({"lancee": False, "raison": "deja_en_cours"}), 409
        _validation_bilan_state["en_cours"] = True
        _validation_bilan_state["demarree_le"] = datetime.now().isoformat(timespec="seconds")
        _validation_bilan_state["progression"] = None
    threading.Thread(target=_run_validation_bilan_background, args=(codes, annees), daemon=True).start()
    return jsonify({"lancee": True})


@bp.route("/api/gestion-donnees/statut-validation-bilan")
def statut_validation_bilan():
    with _validation_bilan_lock:
        return jsonify(dict(_validation_bilan_state))


# État de la pipeline de validation Takaful Annexes 3/4 (Surplus Familial/
# Général) — même schéma que Bilan ci-dessus, état indépendant.
_validation_takaful_surplus_lock = threading.Lock()
_validation_takaful_surplus_state = {"en_cours": False, "demarree_le": None, "progression": None, "derniere": None}


def _run_validation_takaful_surplus_background(codes, annees):
    from api.services import tableau_pipeline_service_takaful_surplus

    def _progress(done, total):
        with _validation_takaful_surplus_lock:
            _validation_takaful_surplus_state["progression"] = {"fait": done, "total": total}
    try:
        summary = tableau_pipeline_service_takaful_surplus.process_all(codes, annees, progress_callback=_progress)
        with _validation_takaful_surplus_lock:
            _validation_takaful_surplus_state["derniere"] = {
                **summary, "terminee_le": datetime.now().isoformat(timespec="seconds"),
            }
    except Exception as exc:
        print(f"[gestion_donnees] échec validation Takaful Surplus : {exc}")
    finally:
        with _validation_takaful_surplus_lock:
            _validation_takaful_surplus_state["en_cours"] = False
            _validation_takaful_surplus_state["progression"] = None


@bp.route("/api/gestion-donnees/valider-takaful-surplus", methods=["POST"])
def valider_takaful_surplus():
    """Lance (en tâche de fond) l'extraction + stockage des Annexes 3/4
    Takaful (Surplus Familial/Général) pour AT_TAKAFULIA et ZITOUNA_TAKAFUL
    — voir extraction/takaful_surplus_full_extractor.py. Même schéma que
    /valider-bilan."""
    codes = request.args.getlist("societe") or None
    annees_raw = request.args.getlist("annee")
    try:
        annees = [int(a) for a in annees_raw] or None
    except ValueError:
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400

    with _validation_takaful_surplus_lock:
        if _validation_takaful_surplus_state["en_cours"]:
            return jsonify({"lancee": False, "raison": "deja_en_cours"}), 409
        _validation_takaful_surplus_state["en_cours"] = True
        _validation_takaful_surplus_state["demarree_le"] = datetime.now().isoformat(timespec="seconds")
        _validation_takaful_surplus_state["progression"] = None
    threading.Thread(target=_run_validation_takaful_surplus_background, args=(codes, annees), daemon=True).start()
    return jsonify({"lancee": True})


@bp.route("/api/gestion-donnees/statut-validation-takaful-surplus")
def statut_validation_takaful_surplus():
    with _validation_takaful_surplus_lock:
        return jsonify(dict(_validation_takaful_surplus_state))


# État de la pipeline de validation Takaful Annexe 5.1 (État de résultat
# de l'entreprise) — même schéma que Bilan/Takaful Surplus ci-dessus.
_validation_takaful_resultat_lock = threading.Lock()
_validation_takaful_resultat_state = {"en_cours": False, "demarree_le": None, "progression": None, "derniere": None}


def _run_validation_takaful_resultat_background(codes, annees):
    from api.services import tableau_pipeline_service_takaful_resultat

    def _progress(done, total):
        with _validation_takaful_resultat_lock:
            _validation_takaful_resultat_state["progression"] = {"fait": done, "total": total}
    try:
        summary = tableau_pipeline_service_takaful_resultat.process_all(codes, annees, progress_callback=_progress)
        with _validation_takaful_resultat_lock:
            _validation_takaful_resultat_state["derniere"] = {
                **summary, "terminee_le": datetime.now().isoformat(timespec="seconds"),
            }
    except Exception as exc:
        print(f"[gestion_donnees] échec validation Takaful Résultat : {exc}")
    finally:
        with _validation_takaful_resultat_lock:
            _validation_takaful_resultat_state["en_cours"] = False
            _validation_takaful_resultat_state["progression"] = None


@bp.route("/api/gestion-donnees/valider-takaful-resultat", methods=["POST"])
def valider_takaful_resultat():
    """Lance (en tâche de fond) l'extraction + stockage de l'Annexe 5.1
    Takaful (État de résultat de l'entreprise) pour AT_TAKAFULIA et
    ZITOUNA_TAKAFUL — voir extraction/takaful_resultat_full_extractor.py.
    Même schéma que /valider-bilan."""
    codes = request.args.getlist("societe") or None
    annees_raw = request.args.getlist("annee")
    try:
        annees = [int(a) for a in annees_raw] or None
    except ValueError:
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400

    with _validation_takaful_resultat_lock:
        if _validation_takaful_resultat_state["en_cours"]:
            return jsonify({"lancee": False, "raison": "deja_en_cours"}), 409
        _validation_takaful_resultat_state["en_cours"] = True
        _validation_takaful_resultat_state["demarree_le"] = datetime.now().isoformat(timespec="seconds")
        _validation_takaful_resultat_state["progression"] = None
    threading.Thread(target=_run_validation_takaful_resultat_background, args=(codes, annees), daemon=True).start()
    return jsonify({"lancee": True})


@bp.route("/api/gestion-donnees/statut-validation-takaful-resultat")
def statut_validation_takaful_resultat():
    with _validation_takaful_resultat_lock:
        return jsonify(dict(_validation_takaful_resultat_state))


# État de la pipeline de validation Takaful Annexes 14/15 (Ventilation
# par catégorie d'assurance) — même schéma que les pipelines Takaful
# ci-dessus.
_validation_takaful_ventilation_lock = threading.Lock()
_validation_takaful_ventilation_state = {"en_cours": False, "demarree_le": None, "progression": None, "derniere": None}


def _run_validation_takaful_ventilation_background(codes, annees):
    from api.services import tableau_pipeline_service_takaful_ventilation

    def _progress(done, total):
        with _validation_takaful_ventilation_lock:
            _validation_takaful_ventilation_state["progression"] = {"fait": done, "total": total}
    try:
        summary = tableau_pipeline_service_takaful_ventilation.process_all(codes, annees, progress_callback=_progress)
        with _validation_takaful_ventilation_lock:
            _validation_takaful_ventilation_state["derniere"] = {
                **summary, "terminee_le": datetime.now().isoformat(timespec="seconds"),
            }
    except Exception as exc:
        print(f"[gestion_donnees] échec validation Takaful Ventilation : {exc}")
    finally:
        with _validation_takaful_ventilation_lock:
            _validation_takaful_ventilation_state["en_cours"] = False
            _validation_takaful_ventilation_state["progression"] = None


@bp.route("/api/gestion-donnees/valider-takaful-ventilation", methods=["POST"])
def valider_takaful_ventilation():
    """Lance (en tâche de fond) l'extraction + stockage des Annexes 14/15
    Takaful (Ventilation par catégorie d'assurance) pour AT_TAKAFULIA et
    ZITOUNA_TAKAFUL — voir extraction/takaful_ventilation_full_extractor.py.
    Même schéma que /valider-bilan."""
    codes = request.args.getlist("societe") or None
    annees_raw = request.args.getlist("annee")
    try:
        annees = [int(a) for a in annees_raw] or None
    except ValueError:
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400

    with _validation_takaful_ventilation_lock:
        if _validation_takaful_ventilation_state["en_cours"]:
            return jsonify({"lancee": False, "raison": "deja_en_cours"}), 409
        _validation_takaful_ventilation_state["en_cours"] = True
        _validation_takaful_ventilation_state["demarree_le"] = datetime.now().isoformat(timespec="seconds")
        _validation_takaful_ventilation_state["progression"] = None
    threading.Thread(target=_run_validation_takaful_ventilation_background, args=(codes, annees), daemon=True).start()
    return jsonify({"lancee": True})


@bp.route("/api/gestion-donnees/statut-validation-takaful-ventilation")
def statut_validation_takaful_ventilation():
    with _validation_takaful_ventilation_lock:
        return jsonify(dict(_validation_takaful_ventilation_state))


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


@bp.route("/api/gestion-donnees/cellules")
def cellules():
    """Grille de cellules déjà stockée pour UN document CMF (société +
    année + tableau) — sert la page de correction manuelle, qui permet de
    consulter (et bientôt corriger) les données avant de générer l'Excel,
    sans avoir à le télécharger d'abord. Pure lecture de `tableau_cellules`,
    aucune ré-extraction déclenchée ici."""
    code = request.args.get("societe")
    annee_raw = request.args.get("annee")
    tableau = request.args.get("tableau")
    if not code or not annee_raw or not tableau:
        return jsonify({"error": "Paramètres 'societe', 'annee' et 'tableau' requis"}), 400
    try:
        annee = int(annee_raw)
    except ValueError:
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400

    conn = get_connection()
    try:
        grille = get_document_grid(conn, code, annee, tableau)
    finally:
        conn.close()
    if grille is None:
        return jsonify({"error": "Aucun document CMF pour cette société/année"}), 404
    return jsonify(grille)


@bp.route("/api/gestion-donnees/corrections", methods=["POST"])
def enregistrer_corrections():
    """Enregistre en base une liste de corrections manuelles pour UN document
    CMF (société + année + tableau) — bouton "Enregistrer tout" de la page
    Correction manuelle. Corps JSON : {"societe", "annee", "tableau",
    "corrections": [{"kind": "valeur"|"ligne"|"colonne", "ligne", "colonne",
    "nouvelle"}, ...]}. Applique directement sur `tableau_cellules` (la
    grille affichée/exportée en repart aussitôt) et journalise chaque
    correction dans `tableau_cellules` — voir
    database/repository.py::apply_manual_corrections. Tout ou rien : une
    correction invalide (nom en doublon, valeur non numérique...) annule
    toute la liste plutôt que de laisser la base à moitié corrigée. Une
    correction de VALEUR est aussi répercutée dans `kpi_values` (KPI narrow
    utilisés par les autres dashboards — Aperçu marché, Analyse
    comparative...) quand elle y correspond de façon non ambiguë, voir
    `apply_manual_corrections`."""
    body = request.get_json(silent=True) or {}
    code = body.get("societe")
    annee_raw = body.get("annee")
    tableau = body.get("tableau")
    corrections = body.get("corrections")
    if not code or annee_raw is None or not tableau or not isinstance(corrections, list) or not corrections:
        return jsonify({"error": "Paramètres 'societe', 'annee', 'tableau' et 'corrections' (liste non vide) requis"}), 400
    try:
        annee = int(annee_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400
    for c in corrections:
        if not isinstance(c, dict) or c.get("kind") not in ("valeur", "ligne", "colonne") or not c.get("nouvelle"):
            return jsonify({"error": "Chaque correction doit avoir 'kind' (valeur|ligne|colonne) et 'nouvelle'"}), 400

    conn = get_connection()
    try:
        doc_id = get_document_id(conn, code, annee)
        if not doc_id:
            return jsonify({"error": "Aucun document CMF pour cette société/année"}), 404
        try:
            apply_manual_corrections(conn, doc_id, tableau, corrections, kpi_raw_labels=kpi_raw_labels_for(tableau))
        except CorrectionError as exc:
            return jsonify({"error": str(exc)}), 400
    finally:
        conn.close()
    return jsonify({"ok": True, "appliquees": len(corrections)})


@bp.route("/api/gestion-donnees/page-pdf")
def page_pdf():
    """Numéro de page du PDF source pour une combinaison société/année/
    tableau — sert à ouvrir directement la bonne page dans le visualiseur
    PDF affiché à côté de l'aperçu Excel (correction manuelle), pour aider
    l'utilisateur à repérer visuellement une faute d'extraction. `page: null`
    si le tableau n'a pas de pipeline de repérage dédié (bilan) ou si la
    page n'a pas pu être retrouvée — le front se rabat alors sur la page 1.
    `raccordement: true` si cette page réconcilie le résultat technique
    (1 colonne "Total") plutôt que de ventiler par branche — un repli
    parfois délibérément vérifié à la main (voir annexe13/12_verified.py)
    quand la vraie page par branche est un scan illisible, mais qui doit
    être signalé plutôt que montré comme si c'était la page attendue."""
    code = request.args.get("societe")
    annee_raw = request.args.get("annee")
    tableau = request.args.get("tableau")
    if not code or not annee_raw or not tableau:
        return jsonify({"error": "Paramètres 'societe', 'annee' et 'tableau' requis"}), 400
    try:
        annee = int(annee_raw)
    except ValueError:
        return jsonify({"error": "Paramètre 'annee' invalide"}), 400

    conn = get_connection()
    try:
        info = page_source_info(conn, code, annee, tableau)
    finally:
        conn.close()
    return jsonify(info)


@bp.route("/api/gestion-donnees/referentiel")
def referentiel():
    """Noms de ligne/colonne canoniques pour un tableau — alimente le menu
    déroulant de correction d'un NOM (par opposition à une valeur) sur la
    page de correction manuelle."""
    tableau = request.args.get("tableau")
    if not tableau:
        return jsonify({"error": "Paramètre 'tableau' requis"}), 400
    return jsonify(get_referentiel(tableau))
