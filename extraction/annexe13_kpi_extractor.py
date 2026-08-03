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
    USER_AGENT,
    _cluster_lines,
    _extract_numeric_clusters,
    _is_plausible,
    _normalizer,
)

# Cette annexe peut se trouver très loin dans le document (ex: page 74 sur
# 101 chez TUNIS_RE, société de réassurance aux annexes très détaillées).
MAX_PAGES_SCANNED = 120

# Trois présentations rencontrées pour ce même tableau :
#  - "Résultat technique par catégorie d'assurance Non Vie" (STAR, COMAR...) :
#    une colonne par branche + une colonne "Total" ;
#  - "Tableau de raccordement du résultat technique..." (ASTREE, GAT...) :
#    une seule colonne (totaux directs, négatifs entre chevrons ou parenthèses) ;
#  - "Résultat technique par catégorie d'assurance" sans mention "Non Vie"
#    (MAGHREBIA...) : table combinée sans séparation Vie/Non-Vie.
# Les pages "raccordement" sont toujours scannées EN PREMIER car elles
# contiennent directement le total agrégé (une seule valeur par ligne),
# contrairement aux tableaux multi-colonnes où `clusters[-1]` peut être
# une colonne de branche plutôt que le Total.
PAGE_TITLE_RE = re.compile(r"resultat technique par categorie|raccordement du resultat technique")
RACCORDEMENT_RE = re.compile(r"raccordement")
NON_VIE_RE = re.compile(r"non.?vie")
VIE_RE = re.compile(r"\bvie\b")

# Dans la section "Informations complémentaires", certaines lignes existent en
# double : année en cours (ex: "clôture", "Année N") et année précédente (ex:
# "Réouverture"/"Ouverture", "Année N-1"). On exclut les variantes "année
# précédente" pour ne garder que l'année en cours.
PRIOR_YEAR_EXCLUSION_RE = re.compile(r"n-1|ouverture|precedent|anterieur")
# Labels contenant une référence de note de bas de page ("primes emises note n°19")
# sont des renvois de tableau, pas des lignes de données — à exclure.
NOTE_REFERENCE_RE = re.compile(r"\bnote\b")

KPI_PATTERNS = {
    "Provisions pour Primes non acquises": re.compile(r"provisions pour primes non acquises"),
    "Charges des provisions pour prestations diverses": re.compile(
        r"charges des provisions pour prestations"
    ),
    "Primes émises Non-Vie par assurance": re.compile(r"^primes emises\b"),
    "Primes acquises": re.compile(r"^primes acquises\b"),
    "Charges de prestations Non-Vie": re.compile(r"^charges de prestations?\b"),
    # S'arrête avant "nettes" : ce libellé se coupe parfois en fin de ligne
    # juste avant ce mot (ex: STAR : "...de gestion n"), comme "et caisse"
    # pour le Bilan (voir bilan_kpi_extractor.DEPOTS_LIQUIDITE_RE).
    "Charges d'acquisition et de gestion nettes Non-Vie": re.compile(
        r"charges d acquisition et de gestion"
    ),
    # Exclut la ligne de titre de la page elle-même ("Résultat technique par
    # catégorie d'assurance Non Vie..."), qui commence par les mêmes mots que
    # la ligne de total recherchée.
    "Résultat technique Non-Vie": re.compile(r"^resultat technique\b(?!.*(categorie|assurance))"),
}


def _label_text(line):
    label_words = [w for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
    if not label_words:
        return None
    return _normalizer.clean(" ".join(w["text"] for w in label_words))


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
    if not PAGE_TITLE_RE.search(normalized):
        return False
    # Accepter : explicitement "Non Vie", OU pas de mention "Vie" du tout
    # (table combinée sans séparation, ex: MAGHREBIA).
    # Rejeter : pages Vie pures (domaine de l'Annexe 12).
    if NON_VIE_RE.search(normalized):
        return True
    return not VIE_RE.search(normalized)


# Sections qui marquent la FIN d'un groupe "Charges de prestations" dans le
# forward scan.
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

    # Raccordement pages first (is_raccordement=True → sort key False → first)
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
            # Un renvoi de note ou un numéro de page/ligne capturé par erreur
            # (ex: COTUNACE "Charges de prestations" = 20.0) est rejeté par
            # _is_plausible : on retombe alors sur le forward scan des
            # sous-lignes plutôt que de renvoyer ce chiffre tel quel.
            if clusters and _is_plausible(clusters[-1][0]):
                return clusters[-1][0]
            # Ligne sans valeur inline (ou valeur inline implausible) :
            # forward scan des sous-lignes. Gère deux cas :
            #   1. Label seul + nombre sur la ligne suivante sans label (STAR 2023)
            #   2. En-tête de section + sous-lignes labelées (COMAR/CARTE)
            total = None
            for j in range(idx + 1, min(idx + 1 + _FORWARD_SCAN_WINDOW, len(lines))):
                nxt_label = _label_text(lines[j])
                if nxt_label and _SECTION_STOP_RE.search(nxt_label):
                    break
                nxt_clusters = _extract_numeric_clusters(lines[j])
                if nxt_clusters and _is_plausible(nxt_clusters[-1][0]):
                    total = (total or 0) + nxt_clusters[-1][0]
            if total is not None:
                return total
    return None


def extract_annexe13_kpis(pdf):
    """Renvoie {nom_kpi: valeur|None} pour les 7 KPI de l'Annexe N°13."""
    return {name: _find_total_value(pdf, pattern) for name, pattern in KPI_PATTERNS.items()}


def extract_annexe13_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait les KPI de l'Annexe N°13."""
    import pdfplumber  # import local pour éviter la dépendance si non utilisé

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_annexe13_kpis(pdf)
