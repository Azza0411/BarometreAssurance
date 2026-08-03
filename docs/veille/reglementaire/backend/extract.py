import hashlib
import re
from bs4 import BeautifulSoup
from config import FTUSA_TEXTES_URL, FTUSA_CODE_URL


def from_cga(html_bytes):
    soup = BeautifulSoup(html_bytes, "html.parser")
    docs = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "fileadmin" not in href or ".pdf" not in href.lower():
            continue
        if not href.startswith("http"):
            href = "https://www.cga.gov.tn/" + href.lstrip("/")

        fname = href.split("/")[-1].lower()
        if fname in seen:
            continue
        seen.add(fname)

        container = a_tag.parent
        for _ in range(5):
            if container is None:
                break
            if getattr(container, "name", None) in ("li", "p", "td", "article"):
                break
            container = getattr(container, "parent", None)
        if container is None:
            container = a_tag.parent

        titre = re.sub(r"\s+", " ", container.get_text(separator=" ", strip=True)).strip()
        if not titre or len(titre) < 5:
            titre = a_tag.get_text(strip=True) or fname.replace("_", " ").replace(".pdf", "")
        if len(titre) > 200:
            titre = titre[:200].rsplit(" ", 1)[0] + "…"

        docs.append({
            "id":      hashlib.md5(fname.encode()).hexdigest()[:12],
            "src":     "CGA",
            "titre":   titre,
            "url":     href,
            "pdf_url": href,
        })

    return docs


def from_ftusa_textes(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["nav", "header", "footer"]):
        tag.decompose()

    docs = []
    seen = set()
    keywords = ["loi ", "décret", "decret", "arrêté", "arrete",
                "ordonnance", "code des", "décision", "règlement"]

    for container in soup.find_all(["li", "p"]):
        text = re.sub(r"\s+", " ", container.get_text(separator=" ", strip=True)).strip()
        if not text or len(text) < 8 or len(text) > 300:
            continue
        if not any(k in text.lower() for k in keywords):
            continue

        a_tag = container.find("a", href=True)
        if a_tag:
            href = a_tag["href"]
            if not href.startswith("http"):
                href = "https://www.ftusanet.org" + (href if href.startswith("/") else "/" + href)
        else:
            href = FTUSA_TEXTES_URL

        if href in seen:
            continue
        seen.add(href)

        docs.append({
            "id":      hashlib.md5((text[:80] + href).encode()).hexdigest()[:12],
            "src":     "FTUSA",
            "titre":   text if len(text) <= 200 else text[:200].rsplit(" ", 1)[0] + "…",
            "url":     href,
            "pdf_url": href if href.lower().endswith(".pdf") else None,
        })

    return docs


def from_ftusa_code(html):
    if not html:
        return [{
            "id":      "ftusa_code_ass",
            "src":     "FTUSA",
            "titre":   "Code des assurances (Loi n°92-24 du 9 mars 1992 et textes modificatifs)",
            "url":     FTUSA_CODE_URL,
            "pdf_url": None,
        }]

    soup = BeautifulSoup(html, "html.parser")
    heading = soup.find(["h1", "h2", "h3"])
    titre = heading.get_text(strip=True) if heading else ""
    if len(titre) < 5:
        titre = "Code des assurances (Loi n°92-24 du 9 mars 1992)"

    pdf_url = None
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            pdf_url = a["href"]
            if not pdf_url.startswith("http"):
                pdf_url = "https://www.ftusanet.org" + pdf_url
            break

    return [{
        "id":      "ftusa_code_ass",
        "src":     "FTUSA",
        "titre":   titre,
        "url":     FTUSA_CODE_URL,
        "pdf_url": pdf_url,
    }]
