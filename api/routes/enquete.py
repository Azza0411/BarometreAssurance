"""Routes /api/enquete-marche/* — données enquête depuis fichier Excel."""

import json as _json
import os
from datetime import datetime

from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

bp = Blueprint("enquete", __name__)

_REQUIRED_SHEETS = ("BDD Retail", "BDD Corporate")


def _json_or(v, default):
    if v is None:
        return default
    try:
        return _json.loads(v)
    except Exception:
        return default


@bp.route("/api/enquete-marche/companies")
def enquete_companies():
    try:
        from extraction.enquete_extractor import list_survey_companies
        return jsonify(list_survey_companies())
    except Exception:
        return jsonify([])


@bp.route("/api/enquete-marche/data")
def enquete_data():
    code = request.args.get("code", "STAR")
    try:
        from extraction.enquete_extractor import compute_stats
        data = compute_stats(code)
        if data is None:
            return jsonify(None)
        return jsonify(data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@bp.route("/api/enquete-marche/upload", methods=["POST"])
def enquete_upload():
    """Ajoute un nouveau fichier Excel source pour l'enquête de marché —
    permet de mettre à jour la donnée localement (même format attendu que
    le fichier actuel : feuilles "BDD Retail" et "BDD Corporate") sans
    repasser par un scraping. N'écrase JAMAIS l'ancien fichier en place
    (voir extraction/enquete_extractor.py::_find_xlsx, qui sert désormais
    le .xlsx "survey" le plus récemment déposé) — un nom horodaté unique
    évite tout remplacement d'un fichier potentiellement encore ouvert
    (verrou OneDrive/antivirus sous Windows, constaté en test : un
    remplacement en place échouait de façon persistante avec
    PermissionError malgré plusieurs réessais). L'ancien fichier reste
    disponible tel quel comme historique/secours. Le cache de
    `compute_stats` est vidé pour que les prochains appels relisent bien
    le nouveau fichier."""
    file = request.files.get("file")
    if file is None or not file.filename:
        return jsonify({"error": "Aucun fichier reçu."}), 400
    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".xlsx"):
        return jsonify({"error": "Le fichier doit être au format .xlsx."}), 400

    import pandas as pd
    from extraction.enquete_extractor import _DATA_DIR, compute_stats, list_survey_companies

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(filename)
    new_path = os.path.join(_DATA_DIR, f"survey_{stamp}_{base}{ext}")
    file.save(new_path)
    try:
        with pd.ExcelFile(new_path) as xls:
            sheet_names = xls.sheet_names
        missing = [s for s in _REQUIRED_SHEETS if s not in sheet_names]
        if missing:
            os.remove(new_path)
            return jsonify({"error": f"Feuille(s) manquante(s) dans le fichier : {', '.join(missing)}."}), 400
    except Exception as e:
        if os.path.isfile(new_path):
            os.remove(new_path)
        return jsonify({"error": f"Fichier illisible : {e}"}), 400

    compute_stats.cache_clear()
    return jsonify({"ok": True, "companies": list_survey_companies()})
