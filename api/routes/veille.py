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

_SCRAPE_CACHE: dict = {}  # cache mémoire process : clé -> (timestamp, données)
_CACHE_TTL = 3600  # durée de vie du cache en secondes (1 heure)

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
    # Compagnies Takaful — absentes jusqu'ici (constaté 2026-08-21, retour
    # utilisateur : le filtre par compagnie d'Actualités & Séminaires ne les
    # proposait pas). Non cotées à la BVMT (voir _scrape_ilboursa ci-dessous),
    # donc jamais un compagnie_default de ticker, mais un article Atlas
    # Magazine/IlBoursa les mentionnant nommément doit être tagué comme tel
    # plutôt que de rester "—" ou hérité à tort du ticker de la page.
    {"name": "AT-Takafulia",       "ticker": None,    "keys": ["takafulia", "at-takafulia"]},
    {"name": "Zitouna Takaful",    "ticker": None,    "keys": ["zitouna takaful", "zitouna assur"]},
    {"name": "El Amana Takaful",   "ticker": None,    "keys": ["el amana takaful", "al amana takaful", "amana takaful"]},
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
    now = time.time()  # horodatage courant (secondes epoch)
    if key in _SCRAPE_CACHE:  # entrée déjà présente en cache
        ts, data = _SCRAPE_CACHE[key]  # timestamp de mise en cache + données stockées
        if now - ts < ttl:  # encore valide (moins d'1h) ?
            return data  # renvoie le résultat en cache, pas de re-scraping
    data = fn()  # cache expiré/absent -> exécute le scraping réel
    _SCRAPE_CACHE[key] = (now, data)  # met à jour le cache avec le nouvel horodatage
    return data


def _get(url, timeout=6):
    try:
        r = req.get(url, headers=HEADERS, timeout=timeout)  # requête HTTP GET avec User-Agent navigateur
        r.raise_for_status()  # lève une exception si code HTTP d'erreur (4xx/5xx)
        return r  # réponse OK
    except Exception:
        return None  # échec silencieux (timeout, 404, site down...) -> appelant doit gérer None


def _normalize_date(date_str):
    current_year = str(datetime.now().year)  # valeur de repli si date illisible
    if not date_str:
        return current_year  # pas de date fournie -> année courante par défaut
    date_str = date_str.strip()  # retire les espaces superflus
    if re.match(r'\d{2}/\d{2}/\d{4}', date_str):
        return date_str  # déjà au format JJ/MM/AAAA, rien à faire
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)  # format ISO AAAA-MM-JJ
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"  # reconverti en JJ/MM/AAAA
    m = re.search(r'(\d{1,2})\s+([a-zéûôàâùè]+)\s+(\d{4})', date_str.lower())  # format "12 janvier 2024"
    if m:
        day   = m.group(1).zfill(2)  # jour sur 2 chiffres
        month = MOIS_FR.get(m.group(2)[:3], "01")  # nom de mois FR -> numéro (via table MOIS_FR)
        return f"{day}/{month}/{m.group(3)}"
    m = re.search(r'\b(20\d{2})\b', date_str)  # au moins une année 20xx trouvée dans le texte
    if m:
        return m.group(1)  # renvoie juste l'année en dernier recours
    return current_year  # rien trouvé -> année courante


def _categorize(titre):
    # Classement heuristique par mots-clés présents dans le titre (aucun NLP)
    t = titre.lower()  # comparaison insensible à la casse
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
    return "Actualité"  # aucune catégorie détectée -> valeur par défaut


def _article_image(url):
    # Va chercher l'image + le résumé d'un article en visitant sa page (2e requête HTTP)
    r = _get(url, timeout=8)
    if not r:
        return None, ""  # page inaccessible -> pas d'image ni de résumé
    soup = BeautifulSoup(r.text, "html.parser")  # parse le HTML de la page article
    desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})  # meta description (og ou standard)
    desc = (desc_tag.get("content", "") if desc_tag else "").strip()  # texte du résumé, vide si absent
    og = soup.find("meta", property="og:image")  # image Open Graph (miniature officielle du site)
    if og and og.get("content"):
        return og["content"], desc  # priorité à l'image og:image si présente
    for sel in ["article img", ".article-content img", "figure img", ".entry-content img", ".post img"]:
        img = soup.select_one(sel)  # sinon, tente plusieurs sélecteurs CSS courants
        if img:
            src = img.get("src") or img.get("data-src", "")  # src classique ou lazy-load (data-src)
            if src and not src.endswith(".gif"):  # exclut les gifs (souvent icônes/pubs)
                if not src.startswith("http"):
                    domain = re.match(r'https?://[^/]+', url)  # extrait le domaine de la page source
                    src = (domain.group() if domain else "") + src  # reconstruit une URL absolue
                return src, desc
    return None, desc  # aucune image trouvée, on garde quand même le résumé


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
        ("cotation_STAR",  "STAR Assurances"),   # une page IlBoursa par ticker coté
        ("cotation_ASSMA", "Maghrebia"),
        ("cotation_AMV",   "Maghrebia"),
        ("cotation_BHASS", "BH Assurance"),
        ("cotation_BNASS", "BNA Assurances"),
        ("cotation_AST",   "Astree Assurances"),
        ("cotation_TRE",   "Tunis Re"),
    ]

    articles     = []  # résultat final (articles enrichis avec image/résumé)
    seen_urls    = set()  # anti-doublon inter-tickers (même actu citée sur 2 pages)
    article_links = []  # liste brute (titre, url, date, compagnie) avant enrichissement

    for ticker, compagnie_default in ILBOURSA_TICKERS:
        r = _get(f"https://www.ilboursa.com/marches/{ticker}")  # page "cotation" de la société
        if not r:
            continue  # page injoignable -> on passe au ticker suivant
        soup = BeautifulSoup(r.text, "html.parser")  # parse le HTML de la page
        container = soup.find("div", class_="lh25")  # bloc contenant la liste d'actualités liées
        if not container:
            continue  # structure inattendue -> rien à extraire ici

        pending_date = ""  # date "en attente" : IlBoursa met la date avant le lien, pas dans le lien
        for child in container.children:  # parcourt les enfants directs du bloc (span date, puis lien)
            from bs4 import NavigableString, Tag
            if isinstance(child, Tag) and child.name == "span" and "sp1" in (child.get("class") or []):
                pending_date = child.get_text(strip=True)  # mémorise la date du prochain lien
            elif isinstance(child, Tag) and child.name == "a":
                href = child.get("href", "")
                if not re.search(r"/marches/.+_\d+$", href):
                    continue  # pas un lien d'actualité (motif attendu : .../marches/xxx_123)
                if not href.startswith("http"):
                    href = "https://www.ilboursa.com" + href  # complète en URL absolue
                if href in seen_urls:
                    continue  # déjà vu via un autre ticker -> évite le doublon
                titre = child.get_text(strip=True)
                if len(titre) < 15:
                    continue  # titre trop court, probablement pas un vrai article
                seen_urls.add(href)
                titre_l    = titre.lower()
                compagnie  = compagnie_default  # compagnie par défaut = celle du ticker consulté
                for co in INSURANCE_COMPANIES:
                    if any(k in titre_l for k in co["keys"]):
                        compagnie = co["name"]  # réaffecte si une autre compagnie est nommée dans le titre
                        break
                article_links.append((titre, href, pending_date, compagnie))
                pending_date = ""  # consommée, on réinitialise pour le lien suivant

    def fetch_one(item):
        # Enrichit un article brut : visite sa page pour récupérer image + résumé
        titre, href, date_str, compagnie = item
        img, resume = _article_image(href)  # 2e requête HTTP (une par article)
        if re.match(r"\d{1,2}/\d{1,2}/\d{2}$", date_str):
            parts = date_str.split("/")
            parts[2] = "20" + parts[2]  # complète l'année à 2 chiffres (24 -> 2024)
            date_str = "/".join(parts)
        return {
            "src":       "ILBOURSA",
            "titre":     titre,
            "url":       href,
            "date":      _normalize_date(date_str),  # normalise au format JJ/MM/AAAA
            "categorie": _categorize(titre),  # catégorie déduite par mots-clés
            "compagnie": compagnie,
            "resume":    resume,
            "image":     img,
            "pdf_url":   None,  # IlBoursa ne fournit pas de PDF (contrairement à CGA/FTUSA)
        }

    with ThreadPoolExecutor(max_workers=8) as executor:  # 8 requêtes d'enrichissement en parallèle
        futures = {executor.submit(fetch_one, item): item for item in article_links[:50]}  # limite à 50 articles
        for future in as_completed(futures):  # récupère les résultats au fur et à mesure
            try:
                articles.append(future.result())
            except Exception:
                pass  # un échec individuel ne doit pas casser tout le scraping
    return articles


# ── Scraping Atlas Magazine ────────────────────────────────────────────────────

def _scrape_atlas():
    articles     = []  # résultat final enrichi
    seen_urls    = set()  # anti-doublon inter-pages
    cutoff_year  = datetime.now().year - 5  # ignore les articles vieux de plus de 5 ans
    article_links = []  # liste brute avant enrichissement (image/résumé)

    for pg in range(4):  # parcourt les 4 premières pages de la liste d'actus Tunisie
        url = "https://www.atlas-mag.net/fr/news/tunisia" + (f"?page={pg}" if pg > 0 else "")  # pagination ?page=N
        r   = _get(url)
        if not r:
            continue  # page injoignable -> passe à la suivante
        soup = BeautifulSoup(r.text, "html.parser")
        main_cards = [
            c for c in soup.find_all("div", class_="card")  # toutes les "cartes" d'articles
            if "sidebar" not in " ".join(c.parent.get("class", []))  # exclut les cartes de la sidebar (hors sujet)
        ]
        for card in main_cards:
            title_tag = card.find("h5") or card.find(["h2", "h3", "h4"])  # titre dans un des niveaux de titre HTML
            titre = title_tag.get_text(strip=True) if title_tag else ""

            href = None
            for a in card.find_all("a", href=True):
                h = a["href"]
                if "/fr/articles/" in h:  # ne garde que les liens pointant vers un vrai article
                    if not h.startswith("http"):
                        h = "https://www.atlas-mag.net" + h  # complète en URL absolue
                    href = h
                    break

            if not href or not titre or len(titre) < 8 or href in seen_urls:
                continue  # carte incomplète, titre trop court ou déjà vu

            time_tag = card.find("time")  # balise <time> HTML5 pour la date de publication
            date_str = ""
            if time_tag:
                date_str = time_tag.get("datetime", "") or time_tag.get_text(strip=True)  # attribut datetime prioritaire

            norm_date = _normalize_date(date_str)  # normalise au format JJ/MM/AAAA
            yr = re.search(r'\b(20\d{2})\b', norm_date)
            if yr and int(yr.group()) < cutoff_year:
                continue  # article trop ancien (fenêtre de 5 ans), on l'ignore

            titre_l   = titre.lower()
            compagnie = "—"  # pas de compagnie par défaut ici (contrairement à IlBoursa qui a un ticker)
            for co in INSURANCE_COMPANIES:
                if any(k in titre_l for k in co["keys"]):
                    compagnie = co["name"]  # tag la compagnie si son nom apparaît dans le titre
                    break

            seen_urls.add(href)
            article_links.append((titre, href, norm_date, compagnie))

    def fetch_atlas_one(item):
        # Enrichit un article brut : image + résumé + catégorie
        titre, href, norm_date, compagnie = item
        img, resume = _article_image(href)  # 2e requête HTTP (visite la page article)
        cat = _categorize(titre)
        return {
            "src":       "ATLAS MAGAZINE",
            "titre":     titre,
            "url":       href,
            "date":      norm_date,
            "categorie": cat if cat != "Actualité" else "Publication",  # Atlas = magazine -> "Publication" par défaut
            "compagnie": compagnie,
            "resume":    resume,
            "image":     img,
            "pdf_url":   None,
        }

    with ThreadPoolExecutor(max_workers=8) as executor:  # enrichissement en parallèle (8 threads)
        futures = {executor.submit(fetch_atlas_one, item): item for item in article_links}
        for future in as_completed(futures):
            try:
                articles.append(future.result())
            except Exception:
                pass  # un échec individuel n'interrompt pas les autres
    return articles


# ── Scraping Veille Réglementaire ─────────────────────────────────────────────

def _detect_type(text):
    # Devine le type de texte réglementaire à partir de mots-clés dans son titre
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
    return "Texte"  # type non reconnu -> générique


def _extract_date_from_title(titre):
    # Les textes réglementaires portent leur date dans le titre (ex: "...du 12 mars 2020")
    t = titre.lower()
    m = re.search(r'\bdu\s+(\d{1,2})(?:er)?\s+([a-zéûôàâùè]+)\s+(\d{4})', t)  # motif "du JJ(er) mois AAAA"
    if m:
        day   = m.group(1).zfill(2)  # jour sur 2 chiffres
        month = MOIS_FR.get(m.group(2)[:3], None) or MOIS_FR.get(m.group(2)[:4], "01")  # nom mois -> numéro
        return f"{day}/{month}/{m.group(3)}", int(m.group(3))  # date complète + année en int
    m = re.search(r'\b(\d{4})\b', titre)  # sinon, cherche juste une année isolée
    if m:
        return m.group(1), int(m.group(1))
    return "", None  # aucune date trouvée


def _scrape_cga_page(page_id):
    # Scrape une page du site CGA (Comité Général des Assurances) identifiée par son id
    # (page_id 33 et 30 sont deux rubriques différentes, appelées séparément par _build_veille)
    url = f"https://www.cga.gov.tn/index.php?id={page_id}&L=0"
    r   = _get(url)
    if not r:
        return []  # page injoignable -> aucun document pour cette rubrique
    soup     = BeautifulSoup(r.content, "html.parser")  # r.content (bytes) : laisse BS4 gérer l'encodage
    docs     = []
    seen_pdfs = set()  # anti-doublon par nom de fichier PDF

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "fileadmin" not in href or ".pdf" not in href.lower():
            continue  # ne garde que les liens vers des PDF hébergés dans fileadmin (docs officiels)
        if not href.startswith("http"):
            href = "https://www.cga.gov.tn/" + href.lstrip("/")  # complète en URL absolue
        fname = href.split("/")[-1].lower()  # nom de fichier seul, utilisé comme clé de dédoublonnage
        if fname in seen_pdfs:
            continue  # déjà traité (même PDF référencé plusieurs fois sur la page)
        seen_pdfs.add(fname)

        container = a_tag.parent  # remonte dans le DOM pour trouver un bloc contenant le titre complet
        for _ in range(5):  # au plus 5 niveaux de remontée
            if container is None:
                break
            tag = getattr(container, "name", None)
            if tag in ("li", "p", "td", "article"):
                break  # trouvé un conteneur "logique" (élément de liste, paragraphe...)
            container = getattr(container, "parent", None)
        if container is None:
            container = a_tag.parent  # repli : le parent direct du lien

        titre = re.sub(r'\s+', ' ', container.get_text(separator=" ", strip=True)).strip()  # texte du bloc, espaces normalisés
        if not titre or len(titre) < 5:
            titre = a_tag.get_text(strip=True) or fname.replace("_", " ").replace(".pdf", "")  # repli sur le texte du lien ou le nom de fichier
        if len(titre) > 200:
            titre = titre[:200].rsplit(" ", 1)[0] + "…"  # tronque proprement (coupe au dernier mot entier)

        type_      = _detect_type(titre)  # type de texte déduit du titre (Loi, Décret, Circulaire...)
        date, annee = _extract_date_from_title(titre)  # date/année extraites du titre si présentes
        docs.append({
            "id":      hashlib.md5(fname.encode()).hexdigest()[:12],  # id stable basé sur le nom de fichier
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
    # Scrape la page FTUSA listant les textes législatifs/réglementaires (pas que des PDF,
    # contrairement à CGA : peut aussi lister de simples entrées textuelles avec ou sans lien)
    url = "https://www.ftusanet.org/cadre-institutionnel/les-textes-legislatifs-et-reglementaires/"
    r   = _get(url)
    if not r:
        return []  # page injoignable -> rien à renvoyer
    soup = BeautifulSoup(r.text, "html.parser")
    docs = []
    seen = set()  # anti-doublon par URL

    for tag in soup.find_all(["nav", "header", "footer"]):
        tag.decompose()  # supprime le menu/en-tête/pied de page pour ne pas les parcourir par erreur

    for container in soup.find_all(["li", "p"]):  # chaque entrée de texte = un <li> ou <p>
        text = re.sub(r'\s+', ' ', container.get_text(separator=" ", strip=True)).strip()  # texte normalisé
        if not text or len(text) < 8 or len(text) > 300:
            continue  # trop court (bruit) ou trop long (probablement pas une entrée de liste)
        text_l = text.lower()
        if not any(k in text_l for k in ["loi ", "décret", "decret", "arrêté", "arrete",
                                          "ordonnance", "code des", "décision", "règlement"]):
            continue  # ne ressemble pas à un texte réglementaire -> ignoré
        type_ = _detect_type(text)
        if type_ == "Texte":
            continue  # type non reconnu malgré le filtre précédent -> écarté par prudence

        a_tag = container.find("a", href=True)  # lien éventuel vers le document (pas systématique)
        if a_tag:
            href = a_tag["href"]
            if not href.startswith("http"):
                href = "https://www.ftusanet.org" + (href if href.startswith("/") else "/" + href)  # URL absolue
        else:
            href = url  # pas de lien direct -> renvoie vers la page listant le texte

        if href in seen:
            continue  # déjà traité
        is_pdf      = href.lower().endswith(".pdf")  # certains liens pointent directement vers un PDF
        date, annee = _extract_date_from_title(text)  # date/année extraites du texte de l'entrée
        seen.add(href)
        docs.append({
            "id":      hashlib.md5((text[:80] + href).encode()).hexdigest()[:12],  # id basé sur texte+url (pas de fname stable ici)
            "src":     "FTUSA",
            "type":    type_,
            "titre":   text if len(text) <= 200 else text[:200].rsplit(" ", 1)[0] + "…",
            "url":     href,
            "pdf_url": href if is_pdf else None,  # None si le lien ne mène pas directement à un PDF
            "date":    date,
            "annee":   annee,
        })
    return docs


def _scrape_ftusa_code():
    # Scrape la page dédiée au Code des assurances (un seul document, id fixe "ftusa_code_ass")
    url = "https://www.ftusanet.org/cadre-institutionnel/code-des-assurances/"
    r   = _get(url)
    if not r:
        # page injoignable -> renvoie une entrée de repli avec les infos connues à l'avance
        return [{
            "id": "ftusa_code_ass", "src": "FTUSA", "type": "Code",
            "titre": "Code des assurances (Loi n°92-24 du 9 mars 1992 et textes modificatifs)",
            "url": url, "pdf_url": None, "date": "09/03/1992", "annee": 1992,
        }]

    soup    = BeautifulSoup(r.text, "html.parser")
    heading = soup.find(["h1", "h2", "h3"])  # titre de la page (premier gros titre trouvé)
    titre   = heading.get_text(strip=True) if heading else "Code des assurances"
    if not titre or len(titre) < 5:
        titre = "Code des assurances"  # repli si titre vide/trop court

    pdf_url = None
    for a in soup.find_all("a", href=True):
        if ".pdf" in a["href"].lower():
            pdf_url = a["href"]  # premier lien PDF trouvé sur la page
            if not pdf_url.startswith("http"):
                pdf_url = "https://www.ftusanet.org" + pdf_url  # complète en URL absolue
            break

    return [{
        "id": "ftusa_code_ass", "src": "FTUSA", "type": "Code",
        "titre": titre if len(titre) > 8 else "Code des assurances (Loi n°92-24 du 9 mars 1992)",
        "url": url, "pdf_url": pdf_url, "date": "09/03/1992", "annee": 1992,  # date de la loi fondatrice, codée en dur
    }]


def _build_veille():
    # Agrège les 4 sources réglementaires (2 rubriques CGA + code FTUSA + textes FTUSA)
    # Scraping en parallèle pour éviter les timeouts cumulatifs
    scrapers = [
        lambda: _scrape_cga_page(33),
        lambda: _scrape_cga_page(30),
        lambda: _scrape_ftusa_code(),
        lambda: _scrape_ftusa_textes(),
    ]
    all_docs = []
    with ThreadPoolExecutor(max_workers=4) as ex:  # une source par thread (4 sources max)
        futures = [ex.submit(fn) for fn in scrapers]
        for fut in as_completed(futures, timeout=20):  # 20s max pour l'ensemble des 4 sources
            try:
                all_docs.extend(fut.result())
            except Exception:
                pass  # une source en échec n'empêche pas les autres de remonter leurs résultats

    seen_keys = set()  # dédoublonnage combiné : par id/url ET par début de titre
    deduped   = []
    for d in all_docs:
        title_key = re.sub(r'\s+', ' ', d["titre"].lower().strip())[:80]  # empreinte du titre (80 premiers car.)
        key       = d.get("id") or d["url"]
        if key not in seen_keys and title_key not in seen_keys:
            seen_keys.add(key)
            seen_keys.add(title_key)
            deduped.append(d)  # même texte publié sur 2 sources -> gardé une seule fois

    def sort_key(d):
        # Construit une clé de tri chronologique AAAAMMJJ (ou juste l'année si date incomplète)
        date  = d.get("date", "")
        parts = date.split("/")
        if len(parts) == 3:
            return f"{parts[2]}{parts[1]}{parts[0]}"  # JJ/MM/AAAA -> AAAAMMJJ (tri lexicographique correct)
        annee = d.get("annee")
        return str(annee) if annee else "0000"  # aucune info de date -> tri en dernier

    deduped.sort(key=sort_key, reverse=True)  # du plus récent au plus ancien
    return deduped


# ── Endpoints ──────────────────────────────────────────────────────────────────

def sync_new_items():
    """Scrape actualités + veille réglementaire et diffe contre les tables
    *_vues (database.repository) pour détecter ce qui est réellement
    nouveau depuis le dernier passage. Appelé UNIQUEMENT par
    pipelines/run_pipeline.py (jamais par une route HTTP) : /api/actualites
    et /api/veille-reglementaire restent des scrapes live à cache 1h,
    inchangés - cette fonction alimente seulement la cloche de notification.
    Renvoie {"actualites": [...nouvelles...], "reglementation": [...nouveaux...]}."""
    from database.repository import get_connection, diff_and_mark_actualites, diff_and_mark_reglementation  # import local pour éviter une dépendance circulaire au chargement du module

    conn = get_connection()  # ouvre une connexion DB dédiée à cette synchronisation
    try:
        actus = _scrape_ilboursa() + _scrape_atlas()  # re-scrape complet des 2 sources d'actualités (pas de cache ici)
        nouvelles_actus = diff_and_mark_actualites(conn, actus)  # compare à la table actualites_vues, marque les nouveaux

        regls = _build_veille()  # re-scrape complet des 4 sources réglementaires
        nouveaux_regls = diff_and_mark_reglementation(conn, regls)  # compare à la table reglementation_vues, marque les nouveaux

        return {"actualites": nouvelles_actus, "reglementation": nouveaux_regls}
    finally:
        conn.close()  # ferme la connexion même en cas d'exception


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
