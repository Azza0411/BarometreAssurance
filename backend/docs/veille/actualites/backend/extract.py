import re
from bs4 import BeautifulSoup, Tag
from config import COMPANIES


def _match_company(title, default):
    tl = title.lower()
    for co in COMPANIES:
        if any(k in tl for k in co["keys"]):
            return co["name"]
    return default


def from_ilboursa(html, default_company):
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find("div", class_="lh25")
    if not container:
        return []

    items = []
    seen = set()
    pending_date = ""

    for child in container.children:
        if not isinstance(child, Tag):
            continue
        if child.name == "span" and "sp1" in (child.get("class") or []):
            pending_date = child.get_text(strip=True)
        elif child.name == "a":
            href = child.get("href", "")
            if not re.search(r"/marches/.+_\d+$", href):
                continue
            if not href.startswith("http"):
                href = "https://www.ilboursa.com" + href
            if href in seen:
                continue
            titre = child.get_text(strip=True)
            if len(titre) < 15:
                continue
            seen.add(href)
            items.append({
                "titre":    titre,
                "url":      href,
                "date_raw": pending_date,
                "company":  _match_company(titre, default_company),
                "src":      "ILBOURSA",
            })
            pending_date = ""

    return items


def from_atlas(html):
    soup = BeautifulSoup(html, "html.parser")
    cards = [
        c for c in soup.find_all("div", class_="card")
        if "sidebar" not in " ".join(c.parent.get("class", []))
    ]

    items = []
    seen = set()

    for card in cards:
        title_tag = card.find("h5") or card.find(["h2", "h3", "h4"])
        titre = title_tag.get_text(strip=True) if title_tag else ""
        if len(titre) < 8:
            continue

        href = None
        for a in card.find_all("a", href=True):
            if "/fr/articles/" in a["href"]:
                href = a["href"]
                if not href.startswith("http"):
                    href = "https://www.atlas-mag.net" + href
                break
        if not href or href in seen:
            continue

        time_tag = card.find("time")
        date_raw = ""
        if time_tag:
            date_raw = time_tag.get("datetime", "") or time_tag.get_text(strip=True)

        seen.add(href)
        items.append({
            "titre":    titre,
            "url":      href,
            "date_raw": date_raw,
            "company":  _match_company(titre, "—"),
            "src":      "ATLAS MAGAZINE",
        })

    return items
