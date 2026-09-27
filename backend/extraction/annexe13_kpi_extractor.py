"""
Extraction ciblée du tableau "Résultat technique par catégorie d'assurance
Non-Vie" (Annexe N°13) : récupère la valeur de la colonne "Total" (dernière
colonne, qui additionne toutes les branches/catégories d'assurance) pour les
7 KPI définis dans KPI_DEFINITIONS.

Réutilise les briques bas-niveau de bilan_kpi_extractor (reconstruction de
lignes par position des mots, regroupement des tokens numériques) : ce
tableau n'a pas la complexité brut/amortissements/net du Bilan, la colonne
cible est simplement la DERNIÈRE valeur numérique de la ligne trouvée.

Voir extraction/CAS_PARTICULIERS_ANNEXE13.md pour l'historique des cas
particuliers rencontrés.
"""

import io
import re

import requests

from extraction.bilan_kpi_extractor import (
    NUMERIC_TOKEN_RE,
    ROW_CODE_PREFIX_RE,
    USER_AGENT,
    _cluster_lines,
    _extract_numeric_clusters,
    _is_plausible,
    _normalizer,
)

MAX_PAGES_SCANNED = 120

PAGE_TITLE_RE = re.compile(
    r"resultat technique (?:non.?vie |vie )?par categorie"
    r"|resultat technique (?:non.?vie|vie) de\b"
    r"|raccordement du resultat technique"
    r"|etat de resultat technique de l.?assurance"
)
RACCORDEMENT_RE = re.compile(r"raccordement")
NON_VIE_RE = re.compile(r"non.?vie")
VIE_RE = re.compile(r"\bvie\b")

NOTES_SECTION_RE = re.compile(r"\bnotes sur\b")

PRIOR_YEAR_EXCLUSION_RE = re.compile(r"n-1|ouverture|precedent|anterieur")
NOTE_REFERENCE_RE = re.compile(r"\bnote\b")

KPI_PATTERNS = {
    "Provisions pour Primes non acquises": re.compile(r"provisions pour primes non acquises"),
    "Charges des provisions pour prestations diverses": re.compile(
        r"charges des provisions pour prestations"
    ),
    "Primes émises Non-Vie par assurance": re.compile(r"^primes emises\b"),
    "Primes acquises": re.compile(r"^primes acquises\b"),
    "Charges de prestations Non-Vie": re.compile(r"^charges de prestations?\b"),
    "Charges d'acquisition et de gestion nettes Non-Vie": re.compile(
        r"charges d acquisition et de gestion"
    ),
    "Résultat technique Non-Vie": re.compile(r"^resultat technique\b(?!.*(categorie|assurance))"),
}


_LEADING_BULLET_RE = re.compile(r"^-\s*")


def _label_text(line):
    label_words = [w for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
    if not label_words:
        return None
    label = _normalizer.clean(" ".join(w["text"] for w in label_words))
    label = _LEADING_BULLET_RE.sub("", label)
    return ROW_CODE_PREFIX_RE.sub("", label, count=1)


def _page_lines(page):
    words = page.extract_words()
    if not words:
        return []
    return _cluster_lines(words)


def _is_target_page(page, lines_checked=4):
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    if NOTES_SECTION_RE.search(normalized):
        return False
    if not PAGE_TITLE_RE.search(normalized):
        return False
    if NON_VIE_RE.search(normalized):
        return True
    return not VIE_RE.search(normalized)


_SECTION_STOP_RE = re.compile(
    r"^(solde|frais d acquisition|charges d acquisition et de gestion|"
    r"produits|resultat technique|part des reassureurs|retrocessionn|"
    r"provisions pour primes non acquises|participations aux benefices|commissions)"
)
_FORWARD_SCAN_WINDOW = 6


def _find_total_value(pdf, pattern, max_pages=MAX_PAGES_SCANNED):
    """Cherche, sur les pages "Résultat technique par catégorie... Non Vie"
    (ou table combinée), la première ligne dont le libellé correspond à
    `pattern`, et renvoie la DERNIÈRE valeur numérique de cette ligne.

    Les pages "raccordement" (colonne unique = total direct) sont scannées
    EN PREMIER pour éviter de lire une colonne de branche dans les tableaux
    multi-colonnes sans colonne "Total" explicite (ex: GAT).

    Si la ligne correspondante n'a pas de valeur inline (en-tête de section
    sans total, ex: COMAR/CARTE), on accumule les sous-lignes suivantes
    jusqu'au prochain marqueur de section."""
    target_pages = []
    for page in pdf.pages[:max_pages]:
        if not _is_target_page(page):
            continue
        norm = _normalizer.clean((page.extract_text() or "")[:300])
        target_pages.append((not RACCORDEMENT_RE.search(norm), page))

    target_pages.sort(key=lambda x: x[0])

    for _, page in target_pages:
        lines = _page_lines(page)
        if not lines:
            continue
        for idx, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not pattern.search(label):
                continue
            if PRIOR_YEAR_EXCLUSION_RE.search(label):
                continue
            if NOTE_REFERENCE_RE.search(label):
                continue
            clusters = _extract_numeric_clusters(line)
            value = _pick_current_year_value(clusters)
            if value is not None and _is_plausible(value):
                return value
            total = None
            last_seen = None
            for j in range(idx + 1, min(idx + 1 + _FORWARD_SCAN_WINDOW, len(lines))):
                nxt_label = _label_text(lines[j])
                if nxt_label and _SECTION_STOP_RE.search(nxt_label):
                    break
                nxt_clusters = _extract_numeric_clusters(lines[j])
                nxt_value = _pick_current_year_value(nxt_clusters)
                if nxt_value is not None and _is_plausible(nxt_value):
                    if last_seen is not None and abs(nxt_value - last_seen) < 0.01:
                        continue
                    total = (total or 0) + nxt_value
                    last_seen = nxt_value
            if total is not None:
                return total
    return None


def _pick_current_year_value(clusters):
    """Même ambiguïté que côté Annexe 12 (voir
    annexe12_kpi_extractor._pick_current_year_value pour le détail) : sur
    les pages "par catégorie" à 4 colonnes (Brut/Cessions/Net-N/Net-N-1),
    `clusters[-1]` est l'année précédente, pas l'année en cours."""
    if not clusters:
        return None
    if len(clusters) == 4:
        return clusters[-2][0]
    return clusters[-1][0]


def _apply_primes_emises_fallback(kpis):
    """Repli symétrique de annexe12_kpi_extractor._apply_primes_emises_fallback
    (voir sa note pour le détail du cas GAT_VIE) - même risque côté Non-Vie
    si une société étiquette sa page raccordement "Primes Acquises" plutôt
    que "Primes émises"."""
    if kpis.get("Primes émises Non-Vie par assurance") is None and kpis.get("Primes acquises") is not None:
        kpis["Primes émises Non-Vie par assurance"] = kpis["Primes acquises"]
    return kpis


def extract_annexe13_kpis(pdf):
    """Renvoie {nom_kpi: valeur|None} pour les 7 KPI de l'Annexe N°13."""
    kpis = {name: _find_total_value(pdf, pattern) for name, pattern in KPI_PATTERNS.items()}
    return _apply_primes_emises_fallback(kpis)


def extract_annexe13_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait les KPI de l'Annexe N°13."""
    import pdfplumber

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_annexe13_kpis(pdf)
