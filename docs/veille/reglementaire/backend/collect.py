import requests
from config import HEADERS, CGA_PAGES, FTUSA_TEXTES_URL, FTUSA_CODE_URL


def get(url, timeout=10):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None


def fetch_cga_pages():
    results = []
    for page_id in CGA_PAGES:
        url = f"https://www.cga.gov.tn/index.php?id={page_id}&L=0"
        r = get(url)
        if r:
            results.append(r.content)
    return results


def fetch_ftusa_textes():
    r = get(FTUSA_TEXTES_URL)
    return r.text if r else None


def fetch_ftusa_code():
    r = get(FTUSA_CODE_URL)
    return r.text if r else None
