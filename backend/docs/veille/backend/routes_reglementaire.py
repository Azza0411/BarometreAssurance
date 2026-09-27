from flask import Blueprint, jsonify

import cache
from scraper_reglementaire import build_veille_reglementaire

bp = Blueprint("reglementaire", __name__)


@bp.route("/api/veille-reglementaire", methods=["GET"])
def get_veille_reglementaire():
    return jsonify(cache.get("veille_reglementaire", build_veille_reglementaire))


@bp.route("/api/veille-reglementaire/refresh", methods=["POST"])
def refresh_veille_reglementaire():
    cache.invalidate("veille_reglementaire")
    data = cache.get("veille_reglementaire", build_veille_reglementaire)
    return jsonify({"ok": True, "count": len(data)})
