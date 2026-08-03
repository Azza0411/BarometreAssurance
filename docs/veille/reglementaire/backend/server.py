import re
import time
import requests
from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from transform import build_docs
from config import CACHE_TTL, PORT, HEADERS, PDF_PROXY_DOMAINS

app = Flask(__name__)
CORS(app)

_cache = {}


def cached(key, fn):
    now = time.time()
    if key in _cache:
        ts, data = _cache[key]
        if now - ts < CACHE_TTL:
            return data
    data = fn()
    _cache[key] = (now, data)
    return data


@app.route("/api/veille-reglementaire")
def get_veille():
    return jsonify(cached("veille", build_docs))


@app.route("/api/veille-reglementaire/refresh", methods=["POST"])
def refresh_veille():
    _cache.pop("veille", None)
    data = cached("veille", build_docs)
    return jsonify({"ok": True, "count": len(data)})


@app.route("/api/pdf-proxy")
def pdf_proxy():
    url = request.args.get("url", "")
    if not url or not url.startswith("http"):
        return jsonify({"error": "url invalide"}), 400
    if not any(d in url for d in PDF_PROXY_DOMAINS):
        return jsonify({"error": "domaine non autorisé"}), 403
    try:
        r = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        r.raise_for_status()
        m = re.search(r'filename="?([^";\n]+)"?', r.headers.get("Content-Disposition", ""))
        fname = m.group(1) if m else url.split("/")[-1].split("?")[0] or "document.pdf"
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


if __name__ == "__main__":
    app.run(port=PORT, debug=True)
