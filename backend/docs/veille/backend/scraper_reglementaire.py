import hashlib
import re

from bs4 import BeautifulSoup

import http_client
from normalizer import detect_doc_type, extract_date_from_title


def scrape_cga_page(page_id):
    url = f"https://www.cga.gov.tn/index.php?id={page_id}&L=0"
    r = http_client.get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.content, "html.parser")

    docs = []
    seen_pdfs = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "fileadmin" not in href or ".pdf" not in href.lower():
            continue

        if not href.startswith("http"):
            href = "https://www.cga.gov.tn/" + href.lstrip("/")

        fname = href.split("/")[-1].lower()
        if fname in seen_pdfs:
            continue
        seen_pdfs.add(fname)

        container = a_tag.parent
        for _ in range(5):
            if container is None:
                break
            tag = getattr(container, "name", None)
            if tag in ("li", "p", "td", "article"):
                break
            container = getattr(container, "parent", None)

        if container is None:
            container = a_tag.parent

        titre = re.sub(r'\s+', ' ', container.get_text(separator=" ", strip=True)).strip()
        if not titre or len(titre) < 5:
            titre = a_tag.get_text(strip=True) or fname.replace("_", " ").replace(".pdf", "")

        if len(titre) > 200:
            titre = titre[:200].rsplit(" ", 1)[0] + "…"

        type_ = detect_doc_type(titre)
        date, annee = extract_date_from_title(titre)

        docs.append({
            "id":      hashlib.md5(fname.encode()).hexdigest()[:12],
            "src":     "CGA",
            "type":    type_,
            "titre":   titre,
            "url":     href,
            "pdf_url": href,
            "date":    date,
            "annee":   annee,
        })

    return docs


def scrape_ftusa_textes():
    url = "https://www.ftusanet.org/cadre-institutionnel/les-textes-legislatifs-et-reglementaires/"
    r = http_client.get(url)
    if not r:
        return []
    soup = BeautifulSoup(r.text, "html.parser")

    docs = []
    seen = set()

    for tag in soup.find_all(["nav", "header", "footer"]):
        tag.decompose()

    for container in soup.find_all(["li", "p"]):
        text = re.sub(r'\s+', ' ', container.get_text(separator=" ", strip=True)).strip()
        if not text or len(text) < 8 or len(text) > 300:
            continue

        text_l = text.lower()
        if not any(k in text_l for k in ["loi ", "décret", "decret", "arrêté", "arrete",
                                          "ordonnance", "code des", "décision", "règlement"]):
            continue

        type_ = detect_doc_type(text)
        if type_ == "Texte":
            continue

        a_tag = container.find("a", href=True)
        if a_tag:
            href = a_tag["href"]
            if not href.startswith("http"):
                href = "https://www.ftusanet.org" + (href if href.startswith("/") else "/" + href)
        else:
            href = url

        if href in seen:
            continue

        is_pdf = href.lower().endswith(".pdf")
        date, annee = extract_date_from_title(text)

        seen.add(href)
        docs.append({
            "id":      hashlib.md5((text[:80] + href).encode()).hexdigest()[:12],
            "src":     "FTUSA",
            "type":    type_,
            "titre":   text if len(text) <= 200 else text[:200].rsplit(" ", 1)[0] + "…",
            "url":     href,
            "pdf_url": href if is_pdf else None,
            "date":    date,
            "annee":   annee,
        })

    return docs


def scrape_ftusa_code():
    url = "https://www.ftusanet.org/cadre-institutionnel/code-des-assurances/"
    r = http_client.get(url)
    if not r:
        return [{
            "id":      "ftusa_code_ass",
            "src":     "FTUSA",
            "type":    "Code",
            "titre":   "Code des assurances (Loi n°92-24 du 9 mars 1992 et textes modificatifs)",
            "url":     url,
            "pdf_url": None,
            "date":    "09/03/1992",
            "annee":   1992,
        }]

    soup = BeautifulSoup(r.text, "html.parser")
    heading = soup.find(["h1", "h2", "h3"])
    titre = heading.get_text(strip=True) if heading else "Code des assurances"
    if not titre or len(titre) < 5:
        titre = "Code des assurances"

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
        "type":    "Code",
        "titre":   titre if len(titre) > 8 else "Code des assurances (Loi n°92-24 du 9 mars 1992)",
        "url":     url,
        "pdf_url": pdf_url,
        "date":    "09/03/1992",
        "annee":   1992,
    }]


def build_veille_reglementaire():
    all_docs = []
    all_docs += scrape_cga_page(33)
    all_docs += scrape_cga_page(30)
    all_docs += scrape_ftusa_code()
    all_docs += scrape_ftusa_textes()

    seen_keys = set()
    deduped = []
    for d in all_docs:
        title_key = re.sub(r'\s+', ' ', d["titre"].lower().strip())[:80]
        key = d.get("id") or d["url"]
        if key not in seen_keys and title_key not in seen_keys:
            seen_keys.add(key)
            seen_keys.add(title_key)
            deduped.append(d)

    def sort_key(d):
        date = d.get("date", "")
        parts = date.split("/")
        if len(parts) == 3:
            return f"{parts[2]}{parts[1]}{parts[0]}"
        annee = d.get("annee")
        return str(annee) if annee else "0000"

    deduped.sort(key=sort_key, reverse=True)
    return deduped
