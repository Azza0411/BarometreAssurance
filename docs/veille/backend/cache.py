import time
from config import CACHE_TTL

_STORE: dict = {}


def get(key, fn, ttl=CACHE_TTL):
    now = time.time()
    if key in _STORE:
        ts, data = _STORE[key]
        if now - ts < ttl:
            return data
    data = fn()
    _STORE[key] = (now, data)
    return data


def invalidate(key):
    _STORE.pop(key, None)
