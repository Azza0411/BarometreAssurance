"""
Routes veille : /api/actualites, /api/veille-reglementaire, /api/pdf-proxy, /api/cache/clear.
Contient tout le code de scraping (IlBoursa, Atlas Magazine, CGA, FTUSA).
"""

import re
import time
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as req
from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, request, Response

bp = Blueprint("veille", __name__)

_SCRAPE_CACHE: dict = {}
_CACHE_TTL = 3600

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

INSURANCE_COMPANIES = [
    {"name": "STAR Assurances",    "ticker": "STAR",  "keys": ["star"]},
    {"name": "COMAR Assurances",   "ticker": "COMAR", "keys": ["comar"]},
    {"name": "GAT Assurances",     "ticker": "GAT",   "keys": [" gat ", "gat ass"]},
    {"name": "Astree Assurances",  "ticker": "ASTRE", "keys": ["astree"]},
    {"name": "Carte Assurances",   "ticker": "CARTE", "keys": ["carte ass"]},
    {"name": "Lloyd Tunisien",     "ticker": "LLOYD", "keys": ["lloyd"]},
    {"name": "Maghrebia",          "ticker": "MGBP",  "keys": ["maghrebia"]},
    {"name": "BH Assurance",       "ticker": "BHASS", "keys": ["bh assurance", "bh-assur"]},
    {"name": "BNA Assurances",     "ticker": "BNASS", "keys": ["bna assur"]},
    {"name": "AMI Assurances",     "ticker": "AMII",  "keys": ["ami assur"]},
    {"name": "Attijari Assurance", "ticker": "ATT",   "keys": ["attijari"]},
    {"name": "Tunis Re",           "ticker": "TUNRE", "keys": ["tunis re", "tunis-re", "tunisre"]},
    {"name": "CGA",                "ticker": "CGA",   "keys": ["comité général des assur", " cga "]},
]

MOIS_FR = {
    "janvier":"01","février":"02","mars":"03","avril":"04","mai":"05","juin":"06",
    "juillet":"07","août":"08","septembre":"09","octobre":"10","novembre":"11","décembre":"12",
    "jan":"01","fév":"02","mar":"03","avr":"04","jun":"06","jul":"07","aoû":"08",
    "sep":"09","oct":"10","nov":"11","déc":"12",
}

ASSURANCE_KEYS = [
    "assur", "cga", "prime", "sinistre", "takaful", "réassur", "reassur",
    "star ass", "comar", " gat ", "astree", "carte ass", "lloyd", "maghrebia",
    "bh ass", "bna ass", "ami ass", "compagnie d'assur",
]


# ── Helpers communs ────────────────────────────────────────────────────────────

def _cached(key, fn, ttl=_CACHE_TTL):
    now = time.time()
    if key in _SCRAPE_CACHE:
        ts, data = _SCRAPE_CACHE[key]
        if now - ts < ttl:
            return data
    data = fn()
    _SCRAPE_CACHE[key] = (now, data)
    return data


def _get(url, timeout=6):
    try:
        r = req.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception:
        return None


def _normalize_date(date_str):
    current_year = str(datetime.now().year)
    if not date_str:
        return current_year
    date_str = date_str.strip()
    if re.match(r'\d{2}/\d{2}/\d{4}', date_str):
        return date_str
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = re.search(r'(\d{1,2})\s+([a-zéûôàâùè]+)\s+(\d{4})', date_str.lower())
    if m:
        day   = m.group(1).zfill(2)
        month = MOIS_FR.get(m.group(2)[:3], "01")
        return f"{day}/{month}/{m.group(3)}"
    m = re.search(r'\b(20\d{2})\b', date_str)
    if m:
        return m.group(1)
    return current_year


def _categorize(titre):
    t = titre.lower()
    if any(k in t for k in ["résultat", "chiffre", "prime", "bénéfice", "profit",
                             "sinistre", "ratio", "bilan", "performance", "financier"]):
        return "Résultats financiers"
    if any(k in t for k in ["gouvern", "conseil", "assemblée", "nomination", "direction"]):
        return "Gouvernance"
    if any(k in t for k in ["partenariat", "accord", "convention", "protocole", "collaboration"]):
        return "Partenariat"
    if any(k in t for k in ["digital", "numéri", "application", "plateforme", "technolog", "ia ", "intelligence"]):
        return "Digital"
    if any(k in t for k in ["innov", "borne", "électrique", "développement durable", "énergie", "verte"]):
        return "Innovation"
    if any(k in t for k in ["règlement", "loi", "décret", "circulaire", "obligation", "réglementaire"]):
        return "Réglementation"
    return "Actualité"


def _article_image(url):
    r = _get(url, timeout=8)
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


# ── Scraping IlBoursa ──────────────────────────────────────────────────────────

def _scrape_ilboursa():
    # Ces 7 tickers couvrent l'integralite des compagnies d'assurance
    # effectivement cotees a la BVMT (verifie via
    # scraping.bvmt_scraper._fetch_listed_insurance_companies : 7 societes
    # trouvees, correspondance exacte) -> pas une liste partielle, IlBoursa
    # n'a structurellement pas de page pour une societe non cotee. A
    # completer seulement si une nouvelle compagnie d'assurance s'introduit
    # en bourse (le pipeline BVMT le detecterait le premier).
    ILBOURSA_TICKERS = [
        ("cotation_STAR",  "STAR Assurances"),
        ("cotation_ASSMA", "Maghrebia"),
        ("cotation_AMV",   "Maghrebia"),
        ("cotation_BHASS", "BH Assurance"),
        ("cotation_BNASS", "BNA Assurances"),
        ("cotation_AST",   "Astree Assurances"),
        ("cotation_TRE",   "Tunis Re"),
    ]

    articles     = []
    seen_urls    = set()
    article_links = []

    for ticker, compagnie_default in ILBOURSA_TICKERS:
        r = _get(f"https://www.ilboursa.com/marches/{ticker}")
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        container = soup.find("div", class_="lh25")
        if not container:
            continue

        pending_date = ""
        for child in container.children:
            from bs4 import NavigableString, Tag
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
                titre_l    = titre.lower()
                compagnie  = compagnie_default
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
            "date":      _normalize_date(date_str),
            "categorie": _categorize(titre),
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


# ── Scraping Atlas Magazine ────────────────────────────────────────────────────

def _scrape_atlas():
    articles     = []
    seen_urls    = set()
    cutoff_year  = datetime.now().year - 5
    article_links = []

    for pg in range(4):
        url = "https://www.atlas-mag.net/fr/news/tunisia" + (f"?page={pg}" if pg > 0 else "")
        r   = _get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        main_cards = [
            c for c in soup.find_all("div", class_="card")
            if "sidebar" not in " ".join(c.parent.get("class", []))
        ]
        for card in main_cards:
            title_tag = card.find("h5") or card.find(["h2", "h3", "h4"])
            titre = title_tag.get_text(strip=True) if title_tag else ""

            href = None
            for a in card.find_all("a", href=True):
                h = a["href"]
                if "/fr/articles/" in h:
                    if not h.startswith("http"):
                        h = "https://www.atlas-mag.net" + h
                    href = h
                    break

            if not href or not titre or len(titre) < 8 or href in seen_urls:
                continue

            time_tag = card.find("time")
            date_str = ""
            if time_tag:
                date_str = time_tag.get("datetime", "") or time_tag.get_text(strip=True)

            norm_date = _normalize_date(date_str)
            yr = re.search(r'\b(20\d{2})\b', norm_date)
            if yr and int(yr.group()) < cutoff_year:
                continue

            titre_l   = titre.lower()
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
        cat = _categorize(titre)
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


# ── Scraping Veille Réglementaire ─────────────────────────────────────────────

def _detect_type(text):
    t = text.lower()
    if "règlement" in t or "reglement" in t: return "Règlement"
    if "décision"  in t or "decision"  in t: return "Décision"
    if "circulaire" in t:                     return "Circulaire"
    if "avenant"    in t:                     return "Avenant"
    if "communiqué" in t or "avis" in t:      return "Communiqué"
    if "arrêté"     in t or "arrete" in t:    return "Arrêté"
    if "décret"     in t or "decret" in t:    return "Décret"
    if "loi"        in t:                     return "Loi"
    if "code"       in t:                     return "Code"
    return "Texte"


def _extract_date_from_title(titre):
    t = titre.lower()
    m = re.search(r'\bdu\s+(\d{1,2})(?:er)?\s+([a-zéûôàâùè]+)\s+(\d{4})', t)
    if m:
        day   = m.group(1).zfill(2)
        month = MOIS_FR.get(m.group(2)[:3], None) or MOIS_FR.get(m.group(2)[:4], "01")
        return f"{day}/{month}/{m.group(3)}", int(m.group(3))
    m = re.search(r'\b(\d{4})\b', titre)
    if m:
        return m.group(1), int(m.group(1))
    return "", None


def _scrape_cga_page(page_id):
    url = f"https://www.cga.gov.tn/index.php?id={page_id}&L=0"
    r   = _get(url)
    if not r:
        return []
    soup     = BeautifulSoup(r.content, "html.parser")
    docs     = []
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

        type_      = _detect_type(titre)
        date, annee = _extract_date_from_title(titre)
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


def _scrape_ftusa_textes():
    url = "https://www.ftusanet.org/cadre-institutionnel/les-textes-legislatifs-et-reglementaires/"
    r   = _get(url)
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
        type_ = _detect_type(text)
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

        is_pdf      = href.lower().endswith(".pdf")
        date, annee = _extract_date_from_title(text)
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


def _scrape_ftusa_code():
    url = "https://www.ftusanet.org/cadre-institutionnel/code-des-assurances/"
    r   = _get(url)
    if not r:
        return [{
            "id": "ftusa_code_ass", "src": "FTUSA", "type": "Code",
            "titre": "Code des assurances (Loi n°92-24 du 9 mars 1992 et textes modificatifs)",
            "url": url, "pdf_url": None, "date": "09/03/1992", "annee": 1992,
        }]

    soup    = BeautifulSoup(r.text, "html.parser")
    heading = soup.find(["h1", "h2", "h3"])
    titre   = heading.get_text(strip=True) if heading else "Code des assurances"
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
        "id": "ftusa_code_ass", "src": "FTUSA", "type": "Code",
        "titre": titre if len(titre) > 8 else "Code des assurances (Loi n°92-24 du 9 mars 1992)",
        "url": url, "pdf_url": pdf_url, "date": "09/03/1992", "annee": 1992,
    }]


def _build_veille():
    # Scraping en parallèle pour éviter les timeouts cumulatifs
    scrapers = [
        lambda: _scrape_cga_page(33),
        lambda: _scrape_cga_page(30),
        lambda: _scrape_ftusa_code(),
        lambda: _scrape_ftusa_textes(),
    ]
    all_docs = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = [ex.submit(fn) for fn in scrapers]
        for fut in as_completed(futures, timeout=20):
            try:
                all_docs.extend(fut.result())
            except Exception:
                pass

    seen_keys = set()
    deduped   = []
    for d in all_docs:
        title_key = re.sub(r'\s+', ' ', d["titre"].lower().strip())[:80]
        key       = d.get("id") or d["url"]
        if key not in seen_keys and title_key not in seen_keys:
            seen_keys.add(key)
            seen_keys.add(title_key)
            deduped.append(d)

    def sort_key(d):
        date  = d.get("date", "")
        parts = date.split("/")
        if len(parts) == 3:
            return f"{parts[2]}{parts[1]}{parts[0]}"
        annee = d.get("annee")
        return str(annee) if annee else "0000"

    deduped.sort(key=sort_key, reverse=True)
    return deduped


# ── Endpoints ──────────────────────────────────────────────────────────────────

@bp.route("/api/actualites", methods=["GET"])
def get_actualites():
    def _scrape():
        results = _scrape_ilboursa() + _scrape_atlas()
        seen    = set()
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

    return jsonify(_cached("actualites", _scrape))


@bp.route("/api/veille-reglementaire", methods=["GET"])
def get_veille_reglementaire():
    return jsonify(_cached("veille_reglementaire", _build_veille))


@bp.route("/api/veille-reglementaire/refresh", methods=["POST"])
def refresh_veille_reglementaire():
    _SCRAPE_CACHE.pop("veille_reglementaire", None)
    data = _cached("veille_reglementaire", _build_veille)
    return jsonify({"ok": True, "count": len(data)})


@bp.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    _SCRAPE_CACHE.clear()
    return jsonify({"ok": True, "message": "Cache vidé"})


@bp.route("/api/pdf-proxy", methods=["GET"])
def pdf_proxy():
    url = request.args.get("url", "")
    if not url or not url.startswith("http"):
        return jsonify({"error": "url invalide"}), 400
    allowed = ["cga.gov.tn", "ftusanet.org", "atlas-mag.net"]
    if not any(d in url for d in allowed):
        return jsonify({"error": "domaine non autorisé"}), 403
    try:
        r = req.get(url, headers=HEADERS, timeout=15, stream=True)
        r.raise_for_status()
        cd    = r.headers.get("Content-Disposition", "")
        fname = ""
        m     = re.search(r'filename="?([^";\n]+)"?', cd)
        if m:
            fname = m.group(1)
        if not fname:
            fname = url.split("/")[-1].split("?")[0] or "document.pdf"
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
