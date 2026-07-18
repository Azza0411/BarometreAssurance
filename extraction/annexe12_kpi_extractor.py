"""
Extraction ciblée du tableau "Résultat technique par catégorie d'assurance
Vie" (Annexe N°12) : pendant "Vie" de l'Annexe N°13 (Non-Vie), même logique
d'extraction (voir annexe13_kpi_extractor et bilan_kpi_extractor pour les
briques bas-niveau réutilisées).

La colonne cible (dernière colonne de la ligne) n'est pas toujours nommée
"Total" littéralement (ex: "Montant" chez GAT) : on prend systématiquement
la dernière valeur numérique de la ligne, quel que soit l'intitulé exact de
l'en-tête de colonne.

Voir extraction/CAS_PARTICULIERS_ANNEXE12.md pour l'historique des cas
particuliers rencontrés (notamment : COMAR n'a pas d'activité Vie propre,
gérée par sa filiale HAYETT — plusieurs KPI y sont donc légitimement absents).
"""

import io
import re

import requests

from extraction.bilan_kpi_extractor import USER_AGENT
from extraction.annexe13_kpi_extractor import _extract_numeric_clusters, _label_text, _page_lines, _normalizer

# Cette annexe peut se trouver très loin dans le document (voir Annexe 13).
MAX_PAGES_SCANNED = 120

# Titre de page : "Résultat technique par catégorie d'assurance Vie" ou
# "Tableau de raccordement du résultat technique par catégorie
# d'assurance..." — dans les deux cas, on exige la présence du mot "vie" et
# l'ABSENCE de "non vie"/"non-vie" pour ne pas confondre avec l'Annexe 13.
PAGE_TITLE_RE = re.compile(r"resultat technique (?:par|de la?) categorie|raccordement du resultat technique")
VIE_RE = re.compile(r"\bvie\b")
NON_VIE_RE = re.compile(r"non.?vie")

PRIOR_YEAR_EXCLUSION_RE = re.compile(r"n-1|ouverture|precedent|anterieur")

KPI_PATTERNS = {
    "Charges des provisions d'assurance vie et des autres provisions techniques": re.compile(
        r"charges des provisions d assurance vie et des autres provisions"
    ),
    "Primes émises Vie par assurance": re.compile(r"^primes emises\b"),
    "Primes acquises Vie": re.compile(r"^primes acquises\b"),
    "Charges de prestations Vie": re.compile(r"^charges de prestations?\b"),
    "Charges d'acquisition et de gestion nettes Vie": re.compile(
        r"charges d acquisition et de gestion"
    ),
    "Résultat technique Vie": re.compile(r"^resultat technique\b(?!.*(categorie|assurance))"),
}


def _is_target_page(page, lines_checked=4):
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    if not PAGE_TITLE_RE.search(normalized):
        return False
    if NON_VIE_RE.search(normalized):
        return False
    return bool(VIE_RE.search(normalized))


_RACCORDEMENT_RE = re.compile(r"raccordement")


def _find_total_value(pdf, pattern, max_pages=MAX_PAGES_SCANNED):
    """Cherche, sur les pages "Résultat technique par catégorie... Vie", la
    première ligne dont le libellé correspond à `pattern`, et renvoie la
    DERNIÈRE valeur numérique de cette ligne.

    Les pages "raccordement" (colonne unique) sont scannées EN PREMIER pour
    éviter de lire une colonne de branche dans les tableaux multi-colonnes."""
    target_pages = []
    for page in pdf.pages[:max_pages]:
        if not _is_target_page(page):
            continue
        norm = _normalizer.clean((page.extract_text() or "")[:300])
        target_pages.append((not _RACCORDEMENT_RE.search(norm), page))

    target_pages.sort(key=lambda x: x[0])

    for _, page in target_pages:
        lines = _page_lines(page)
        if not lines:
            continue
        for line in lines:
            label = _label_text(line)
            if label is None or not pattern.search(label):
                continue
            if PRIOR_YEAR_EXCLUSION_RE.search(label):
                continue
            clusters = _extract_numeric_clusters(line)
            if clusters:
                return clusters[-1][0]
    return None


def extract_annexe12_kpis(pdf):
    """Renvoie {nom_kpi: valeur|None} pour les 6 KPI de l'Annexe N°12."""
    return {name: _find_total_value(pdf, pattern) for name, pattern in KPI_PATTERNS.items()}


def extract_annexe12_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait les KPI de l'Annexe N°12."""
    import pdfplumber  # import local pour éviter la dépendance si non utilisé

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_annexe12_kpis(pdf)
