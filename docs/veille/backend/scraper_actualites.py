import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from bs4 import BeautifulSoup, NavigableString, Tag

import http_client
from config import INSURANCE_COMPANIES
from normalizer import normalize_date, categorize_article


def _article_image(url):
    r = http_client.get(url, timeout=8)
    if not r:
        return None, ""
    soup = BeautifulSoup(r.text, "html.parser")
    desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
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
                    domain = re.match(r'https?://[^/]+', url)
                    src = (domain.group() if domain else "") + src
                return src, desc
    return None, desc


def scrape_ilboursa():
    ILBOURSA_TICKERS = [
        ("cotation_STAR",  "STAR Assurances"),
        ("cotation_ASSMA", "Maghrebia"),
        ("cotation_AMV",   "Maghrebia"),
        ("cotation_BHASS", "BH Assurance"),
        ("cotation_BNASS", "BNA Assurances"),
        ("cotation_AST",   "Astree Assurances"),
        ("cotation_TRE",   "Tunis Re"),
    ]

    articles = []
    seen_urls = set()
    article_links = []

    for ticker, compagnie_default in ILBOURSA_TICKERS:
        r = http_client.get(f"https://www.ilboursa.com/marches/{ticker}")
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        container = soup.find("div", class_="lh25")
        if not container:
            continue

        pending_date = ""
        for child in container.children:
            if isinstance(child, Tag) and child.name == "span" and "sp1" in (child.get("class") or []):
                pending_date = child.get_text(strip=True)
            elif isinstance(child, Tag) and child.name == "a":
                href = child.get("href", "")
                if not re.search(r"/marches/.+_\d+$", href):
                    continue
                if not href.startswith("http"):
                    href = "https://www.ilboursa.com" + href
                if href in seen_urls:
                    continue
                titre = child.get_text(strip=True)
                if len(titre) < 15:
                    continue
                seen_urls.add(href)
                titre_l = titre.lower()
                compagnie = compagnie_default
                for co in INSURANCE_COMPANIES:
                    if any(k in titre_l for k in co["keys"]):
                        compagnie = co["name"]
                        break
                article_links.append((titre, href, pending_date, compagnie))
                pending_date = ""

    def fetch_one(item):
        titre, href, date_str, compagnie = item
        img, resume = _article_image(href)
        if re.match(r"\d{1,2}/\d{1,2}/\d{2}$", date_str):
            parts = date_str.split("/")
            parts[2] = "20" + parts[2]
            date_str = "/".join(parts)
        return {
            "src":       "ILBOURSA",
            "titre":     titre,
            "url":       href,
            "date":      normalize_date(date_str),
            "categorie": categorize_article(titre),
            "compagnie": compagnie,
            "resume":    resume,
            "image":     img,
            "pdf_url":   None,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_one, item): item for item in article_links[:50]}
        for future in as_completed(futures):
            try:
                articles.append(future.result())
            except Exception:
                pass

    return articles


def scrape_atlas():
    articles = []
    seen_urls = set()
    cutoff_year = datetime.now().year - 5
    article_links = []

    for pg in range(4):
        url = "https://www.atlas-mag.net/fr/news/tunisia" + (f"?page={pg}" if pg > 0 else "")
        r = http_client.get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")

        main_cards = [
            c for c in soup.find_all("div", class_="card")
            if "sidebar" not in " ".join(c.parent.get("class", []))
        ]

        for card in main_cards:
            title_tag = card.find("h5")
            if not title_tag:
                title_tag = card.find(["h2", "h3", "h4"])
            titre = title_tag.get_text(strip=True) if title_tag else ""

            href = None
            for a in card.find_all("a", href=True):
                h = a["href"]
                if "/fr/articles/" in h:
                    if not h.startswith("http"):
                        h = "https://www.atlas-mag.net" + h
                    href = h
                    break

            if not href or not titre or len(titre) < 8:
                continue
            if href in seen_urls:
                continue

            time_tag = card.find("time")
            date_str = ""
            if time_tag:
                date_str = time_tag.get("datetime", "") or time_tag.get_text(strip=True)

            norm_date = normalize_date(date_str)
            import re
            yr = re.search(r'\b(20\d{2})\b', norm_date)
            if yr and int(yr.group()) < cutoff_year:
                continue

            titre_l = titre.lower()
            compagnie = "—"
            for co in INSURANCE_COMPANIES:
                if any(k in titre_l for k in co["keys"]):
                    compagnie = co["name"]
                    break

            seen_urls.add(href)
            article_links.append((titre, href, norm_date, compagnie))

    def fetch_atlas_one(item):
        titre, href, norm_date, compagnie = item
        img, resume = _article_image(href)
        cat = categorize_article(titre)
        return {
            "src":       "ATLAS MAGAZINE",
            "titre":     titre,
            "url":       href,
            "date":      norm_date,
            "categorie": cat if cat != "Actualité" else "Publication",
            "compagnie": compagnie,
            "resume":    resume,
            "image":     img,
            "pdf_url":   None,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(fetch_atlas_one, item): item for item in article_links}
        for future in as_completed(futures):
            try:
                articles.append(future.result())
            except Exception:
                pass

    return articles


def build_actualites():
    results = scrape_ilboursa() + scrape_atlas()
    seen = set()
    deduped = []
    for a in results:
        k = a["url"]
        if k not in seen:
            seen.add(k)
            deduped.append(a)

    def sort_key(a):
        p = a["date"].split("/")
        if len(p) == 3:
            return f"{p[2]}{p[1]}{p[0]}"
        return a["date"] + "0101"

    deduped.sort(key=sort_key, reverse=True)
    return deduped
