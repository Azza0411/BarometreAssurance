"""Routes /api/enquete-marche/* — données enquête depuis fichier Excel."""

import json as _json
from flask import Blueprint, jsonify, request

bp = Blueprint("enquete", __name__)


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
        from extraction.enquete_extractor import _find_xlsx
        if _find_xlsx():
            return jsonify(["STAR"])
        return jsonify([])
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
