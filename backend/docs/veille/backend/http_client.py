import requests as req
from config import HEADERS


def get(url, timeout=10):
    try:
        r = req.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None
