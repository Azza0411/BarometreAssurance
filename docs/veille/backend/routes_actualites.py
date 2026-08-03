from flask import Blueprint, jsonify

import cache
from scraper_actualites import build_actualites

bp = Blueprint("actualites", __name__)


@bp.route("/api/actualites", methods=["GET"])
def get_actualites():
    return jsonify(cache.get("actualites", build_actualites))
