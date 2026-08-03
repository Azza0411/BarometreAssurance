import re

import requests as req
from flask import Blueprint, Response, jsonify, request

from config import HEADERS, PDF_PROXY_ALLOWED_DOMAINS

bp = Blueprint("pdf_proxy", __name__)


@bp.route("/api/pdf-proxy", methods=["GET"])
def pdf_proxy():
    url = request.args.get("url", "")
    if not url or not url.startswith("http"):
        return jsonify({"error": "url invalide"}), 400
    if not any(d in url for d in PDF_PROXY_ALLOWED_DOMAINS):
        return jsonify({"error": "domaine non autorisé"}), 403
    try:
        r = req.get(url, headers=HEADERS, timeout=15, stream=True)
        r.raise_for_status()
        cd = r.headers.get("Content-Disposition", "")
        fname = ""
        m = re.search(r'filename="?([^";\n]+)"?', cd)
        if m:
            fname = m.group(1)
        if not fname:
            fname = url.split("/")[-1].split("?")[0] or "document.pdf"
        if not fname.lower().endswith(".pdf"):
            fname += ".pdf"
        return Response(
            r.iter_content(chunk_size=8192),
            headers={
                "Content-Disposition": f'attachment; filename="{fname}"',
                "Content-Type": r.headers.get("Content-Type", "application/pdf"),
            },
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 502
