import re
import requests
from bs4 import BeautifulSoup
from config import HEADERS, ILBOURSA_TICKERS


def get(url, timeout=10):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None


def fetch_ilboursa_pages():
    pages = []
    for ticker, default_company in ILBOURSA_TICKERS:
        r = get(f"https://www.ilboursa.com/marches/{ticker}")
        if r:
            pages.append((r.text, default_company))
    return pages


def fetch_atlas_pages():
    pages = []
    for i in range(4):
        url = "https://www.atlas-mag.net/fr/news/tunisia" + (f"?page={i}" if i > 0 else "")
        r = get(url)
        if r:
            pages.append(r.text)
    return pages


def fetch_article_meta(url):
    r = get(url, timeout=8)
    if not r:
        return None, ""
    soup = BeautifulSoup(r.text, "html.parser")
    desc_tag = (
        soup.find("meta", property="og:description")
        or soup.find("meta", attrs={"name": "description"})
    )
    desc = (desc_tag.get("content", "") if desc_tag else "").strip()
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        return og["content"], desc
    for sel in ["article img", ".article-content img", "figure img", ".entry-content img", ".post img"]:
        img = soup.select_one(sel)
        if img:
            src = img.get("src") or img.get("data-src", "")
            if src and not src.endswith(".gif"):
                if not src.startswith("http"):
                    m = re.match(r"https?://[^/]+", url)
                    src = (m.group() if m else "") + src
                return src, desc
    return None, desc
