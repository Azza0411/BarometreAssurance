"""
Extraction de 5 KPI issus du rapport annuel CGA (Comité Général des
Assurances) :
  - "Nombre d'assureurs" (Annexe 1 - Structure du marché d'assurance &
    son activité) : compte les sociétés de la section "Sociétés
    d'Assurance Directe" uniquement (pas les sociétés de réassurance ni
    les succursales/bureaux de représentation non-résidents, qui sont des
    sections distinctes du même tableau).
  - "Nombre d'agences par assureur" et "Nombre d'agences par compagnie"
    (Annexe 2 - Distribution Géographique des Agents d'Assurance) :
    strictement la même valeur (la colonne TOTAL de la ligne de la
    compagnie), simplement décrite par l'utilisateur via deux références
    différentes (somme des 24 colonnes de gouvernorats vs colonne TOTAL
    déjà présente) -> les deux KPI sont enregistrés avec cette même valeur.
  - "Répartition des agences par gouvernorat" (ligne TOTAL, marché
    entier) : une valeur par gouvernorat (24 valeurs).
  - "Répartition des agences de la compagnie par gouvernorat" (par
    compagnie) : une valeur par gouvernorat et par compagnie (jusqu'à
    24 x nb_compagnies valeurs).

Annexe 2 a la même particularité que le tableau FTUSA "Compte
d'exploitation par branche" : son texte est tourné à 90° dans la page
(même cause : matrice de police à coefficients a=d=0, pas un
page.rotation) -> réutilise _derotate_page_words de ftusa_kpi_extractor.

Voir extraction/CAS_PARTICULIERS_CGA.md.
"""

import re
import unicodedata

from config.company_registry import find_code_by_name
from extraction.bilan_kpi_extractor import _cluster_lines, _extract_numeric_clusters, _normalizer
from extraction.ftusa_kpi_extractor import _derotate_page_words

MAX_PAGES_SCANNED = 60

# Le libelle exact varie d'une annee a l'autre (ex: "marche d'assurance"
# en 2022 vs "marche des assurances" en 2020 ; "distribution geographique
# des agents d'assurance" en 2022 vs "... des intermediaires en assurance"
# (avec "agents d'assurance" comme sous-section) en 2020) -> motifs
# tolerants plutot qu'une correspondance exacte.
ANNEXE1_TITLE_RE = re.compile(r"structure du marche d.{1,4}assurances?")
ANNEXE2_TITLE_RE = re.compile(r"distribution geographique des (agents d.assurance|intermediaires)")
# "evolution des primes nettes" seul matche aussi une page narrative
# d'introduction sur le marche mondial de l'assurance vie, rendue en mode
# normal (pas tournee) ; le vrai tableau chiffre, lui, est TOUJOURS tourne
# a 90 degres (voir _find_page_lines(..., require_rotated=True) plus bas) —
# discriminant plus fiable que le contenu du titre, qui varie trop d'une
# annee a l'autre ("evolution des primes nettes" en 2022, "evolution du
# chiffre d affaires par categories d assurance" en 2017/2020...).
ANNEXE4_1_TITLE_RE = re.compile(r"evolution d.{1,4}(primes nettes|chiffre d.affaires)")
DIRECT_SECTION_RE = re.compile(r"^societes d.assurance directe$")
TOTAL_LINE_RE = re.compile(r"^total\b")

# Nom de KPI (stable) -> motif reconnaissant la ligne de branche
# correspondante dans l'Annexe 4-1 ("Primes émises par branche" est
# volontairement propre à CGA, sans tentative de correspondance avec les
# branches FTUSA : les deux nomenclatures ne se recoupent pas exactement,
# ex: CGA regroupe Incendie et Risques Divers en une seule ligne — voir
# CAS_PARTICULIERS_CGA.md).
# Pas d'ancrage "^" : les lignes de sous-branche commencent par une puce
# ("ــ" tatweel arabe, retiree par la normalisation, mais aussi parfois un
# simple tiret ASCII "-" qui lui SURVIT a la normalisation - donc "ass..."
# n'est pas toujours en tout debut de chaine normalisee).
BRANCH_ROW_PATTERNS = {
    "Vie et Capitalisation": re.compile(r"ass\.? ?vie.{0,3}capitalisation"),
    "Automobile": re.compile(r"ass\w* automobile"),
    "Groupe Maladie": re.compile(r"ass\.? ?groupe maladie"),
    "Transport": re.compile(r"assurance transport"),
    "Incendie et Risques Divers": re.compile(r"ass\.? ?incendie.{0,3}risques divers"),
    "Exportations et Credits": re.compile(r"ass\.? ?exportations.{0,3}credits"),
    "Grele et Mortalite du Betail": re.compile(r"ass\.? ?grele.{0,3}mortalite du betail"),
    "Accidents de Travail": re.compile(r"ass\.? ?accidents de travail"),
    "Operations Acceptees": re.compile(r"ass\.? ?operations acceptees"),
}

# Ordre fixe des colonnes de gouvernorats de l'Annexe 2 (liste officielle,
# stable d'une annee sur l'autre) : "Grand Tunis" (position 5) est un
# sous-total (Tunis+Ariana+Ben Arous+Manouba), pas un gouvernorat -> None,
# ignore lors du mappage. La colonne finale (TOTAL) est traitee a part
# (dernier cluster de la ligne).
GOVERNORATE_ORDER = [
    "Tunis", "Ariana", "Ben Arous", "Manouba", None,
    "Sfax", "Sousse", "Nabeul", "Monastir", "Médenine", "Bizerte", "Gabès",
    "Mahdia", "Béja", "Jendouba", "Gafsa", "Kairouan", "Tataouine",
    "Sidi Bouzid", "Zaghouan", "Tozeur", "Kébili", "Le Kef", "Kasserine", "Siliana",
]


def _strip_accents(text):
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _row_label(line):
    """Texte (casse d'origine, pour find_code_by_name) des mots non
    numeriques d'une ligne, ou None si la ligne n'a aucun mot texte."""
    from extraction.bilan_kpi_extractor import NUMERIC_TOKEN_RE

    words = [w["text"] for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
    return " ".join(words) if words else None


def _find_page_lines(pdf, title_re, max_pages=MAX_PAGES_SCANNED, require_rotated=False):
    """Cherche, parmi les MAX_PAGES_SCANNED premieres pages, la page dont
    le titre correspond a `title_re` (en tenant compte du texte tourne a
    90 degres eventuel), et renvoie ses lignes reconstituees (derotation
    appliquee si necessaire). `require_rotated=True` ignore les pages non
    tournees : utile quand le titre recherche apparait aussi tel quel dans
    une page de texte narratif (rendu en mode normal, pas tourne) en plus
    du vrai tableau chiffre (toujours tourne pour ce rapport) — voir
    ANNEXE4_1_TITLE_RE."""
    for page in pdf.pages[:max_pages]:
        words = _derotate_page_words(page)
        rotated = words is not None
        if require_rotated and not rotated:
            continue
        if not rotated:
            words = page.extract_words()
        lines = _cluster_lines(words, y_tolerance=5)
        if not lines:
            continue
        # Le titre peut ne pas etre la toute premiere ligne reconstituee
        # (ex: "Rapport Annuel 2022" precede "ANNEXE 1 STRUCTURE DU
        # MARCHE...") -> on cherche sur les premieres lignes, pas juste la
        # premiere.
        title = _normalizer.clean(" ".join(w["text"] for line in lines[:4] for w in line))
        if title_re.search(title):
            return lines
    return None


def _extract_nombre_assureurs(pdf):
    """Compte les lignes de la section "Sociétés d'Assurance Directe" de
    l'Annexe 1 (entre son en-tête et la prochaine ligne "TOTAL")."""
    lines = _find_page_lines(pdf, ANNEXE1_TITLE_RE)
    if not lines:
        return None
    in_section = False
    count = 0
    for line in lines:
        label = _row_label(line)
        if label is None:
            continue
        normalized = _normalizer.clean(label)
        if DIRECT_SECTION_RE.match(normalized):
            in_section = True
            continue
        if in_section:
            if TOTAL_LINE_RE.match(normalized):
                break
            count += 1
    return count or None


def _extract_annexe2_rows(pdf):
    """Renvoie {libelle_ligne_brut: [(valeur, x0), ...]} pour chaque ligne
    de donnees (compagnies + ligne TOTAL) de l'Annexe 2, ou {} si
    l'annexe est introuvable."""
    lines = _find_page_lines(pdf, ANNEXE2_TITLE_RE)
    if not lines:
        return {}
    rows = {}
    for line in lines:
        clusters = _extract_numeric_clusters(line)
        if len(clusters) != len(GOVERNORATE_ORDER) + 1:  # +1 pour la colonne TOTAL
            continue
        label = _row_label(line)
        if label:
            rows[label.strip()] = clusters
    return rows


def _governorate_breakdown(clusters):
    """{gouvernorat: valeur} pour une ligne de donnees complete de
    l'Annexe 2 (24 gouvernorats, sous-total "Grand Tunis" ignore)."""
    return {
        name: value
        for name, (value, _x0) in zip(GOVERNORATE_ORDER, clusters)
        if name is not None
    }


def _extract_branch_premiums(pdf):
    """Renvoie {nom_branche: valeur_annee_en_cours} pour l'Annexe 4-1
    (Évolution des primes nettes) : la ligne a toujours 6 colonnes
    "année" (ex: 2017 à 2022), suivies des colonnes "Part"/"Tx
    d'évolution" en pourcentage. Ces dernières sont normalement en dehors
    des clusters numériques (le "%" collé au nombre empêche
    NUMERIC_TOKEN_RE de matcher), SAUF certaines années (ex: rapport 2017)
    où un espace sépare le nombre du "%" ("21,2 %") : le nombre seul est
    alors pris pour un cluster valide, ce qui décale `clusters[-1]` vers
    une colonne de pourcentage au lieu de l'année en cours. Prendre
    directement l'index 5 (la 6e valeur, toujours l'année en cours vu que
    les 6 colonnes année sont toujours les 6 premières) est fiable dans
    les deux cas."""
    lines = _find_page_lines(pdf, ANNEXE4_1_TITLE_RE, require_rotated=True)
    if not lines:
        return {}
    branches = {}
    for line in lines:
        label = _row_label(line)
        if label is None:
            continue
        normalized = _normalizer.clean(label)
        for branch_name, pattern in BRANCH_ROW_PATTERNS.items():
            if branch_name in branches or not pattern.search(normalized):
                continue
            clusters = _extract_numeric_clusters(line)
            if len(clusters) >= 6:
                branches[branch_name] = clusters[5][0]
    return branches


def extract_cga_kpis(pdf):
    """Renvoie un dict KPI -> valeur : "Nombre d'assureurs", "Primes émises
    par branche - {branche}" (Annexe 4-1), plus les KPI par compagnie et
    par gouvernorat generes dynamiquement a partir des lignes trouvees dans
    l'Annexe 2 (noms de KPI variables d'un document a l'autre, contrairement
    aux autres extracteurs du projet)."""
    result = {"Nombre d'assureurs": _extract_nombre_assureurs(pdf)}

    for branch_name, value in _extract_branch_premiums(pdf).items():
        result[f"Primes émises par branche - {branch_name}"] = value

    rows = _extract_annexe2_rows(pdf)
    for label, clusters in rows.items():
        normalized = _normalizer.clean(label)
        total_value = clusters[-1][0]
        if TOTAL_LINE_RE.match(normalized):
            for governorate, value in _governorate_breakdown(clusters).items():
                result[f"Répartition des agences par gouvernorat - {governorate}"] = value
            continue
        code = find_code_by_name(label) or label
        result[f"Nombre d'agences par assureur - {code}"] = total_value
        result[f"Nombre d'agences par compagnie - {code}"] = total_value
        for governorate, value in _governorate_breakdown(clusters).items():
            result[f"Répartition des agences de la compagnie par gouvernorat - {code} - {governorate}"] = value

    return result
