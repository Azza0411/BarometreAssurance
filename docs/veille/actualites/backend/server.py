import time
from flask import Flask, jsonify
from flask_cors import CORS
from transform import build_feed
from config import CACHE_TTL, PORT

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


@app.route("/api/actualites")
def get_actualites():
    return jsonify(cached("actualites", build_feed))


if __name__ == "__main__":
    app.run(port=PORT, debug=True)
