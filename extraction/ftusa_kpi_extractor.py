"""
Extraction de 9 KPI (Total / Vie / Non-Vie pour Primes émises, Charges de
prestations, Charges d'acquisition et de gestion nettes) + la ventilation
par branche Non-Vie de "Primes émises" (8 KPI, un par branche) à partir de
l'annexe FTUSA "Compte d'exploitation par branche & par entreprise
(Affaires Directes & Acceptations)".

La ventilation par branche ("Primes émises par branche (FTUSA) - {branche}")
est une source alternative à CGA (extraction/cga_kpi_extractor.py,
"Primes émises par branche - {branche}") pour le même besoin (KPI
"branches_non_vie" du tableau de bord "Aperçu marché") : nom délibérément
différent, PAS de fusion entre les deux (nomenclatures de branches
différentes, voir CAS_PARTICULIERS_CGA.md) -> à privilégier quand
disponible car FTUSA couvre plus d'années que CGA (jusqu'à l'année en cours
contre 2022 pour CGA) et distingue "Risques Divers" d'"Incendie" (CGA les
fusionne en une seule ligne).

Particularité de cette page : sa mise en page est un tableau au format
paysage inséré tel quel (donc tourné à 90°) dans une page portrait — le flux
de texte brut de pdfplumber en ressort donc caractère par caractère à
l'envers (ex: "ENTREPRISE" -> "ESIRPERTNE"). Ce n'est PAS un problème de
rotation de PAGE au sens PDF (page.rotation vaut 0 sur cette page), mais une
rotation appliquée aux caractères eux-mêmes (leur matrice de police a pour
coefficients a=d=0, cf. _derotate_page_words) : confirmé identique sur les
rapports 2022 et 2024, donc structurel à cette annexe plutôt qu'un accident
d'un seul document.

Solution : recalculer les coordonnées (x0/x1/top/bottom) de chaque
caractère tourné selon la rotation inverse, puis reconstruire les mots
(WordExtractor) et lignes (_cluster_lines) sur ces coordonnées corrigées —
le texte redevient alors lisible normalement, sans recours à l'OCR (le
texte reste du vrai texte vectoriel, pas une image scannée).

Colonnes du tableau : 8 branches Non-Vie (Automobile, Groupe Maladie,
Risques Divers, Incendie, Transport, Credit, Risques Agricoles, Accidents
du Travail), puis ASS. VIE, TOTAL (AFF. DIRECTES), ACCEPTATIONS, et enfin
TOTAL (AFF. DIR+ACC) — 12 colonnes en tout. Toutes les lignes n'ont pas
systématiquement une valeur dans chaque colonne (ex: "primes émises" n'a
pas de valeur "Accidents du Travail" dans le rapport 2024) : les valeurs
sont donc retrouvées par correspondance de position (x) avec l'en-tête, pas
par simple comptage de position dans la ligne.

Voir extraction/CAS_PARTICULIERS_FTUSA.md.
"""

import re

from pdfplumber.utils.text import WordExtractor

from extraction.bilan_kpi_extractor import (
    _cluster_lines,
    _extract_numeric_clusters,
    _label_text,
    _normalizer,
)

MAX_PAGES_SCANNED = 100  # cette annexe se trouve generalement en fin de rapport

# Tolere la faute de frappe "EXPLOIATATION" (lettre en trop) trouvee dans le
# titre de cette annexe sur plusieurs annees du rapport FTUSA. Chaque rapport
# contient AUSSI une annexe voisine similairement titree "... PAR BRANCHE EN
# [annee] (NON VIE ET VIE)", avec des colonnes agregees differentes (TOTAL
# NON VIE / TOTAL NON VIE & VIE, sans ACCEPTATIONS ni AFF. DIRECTES
# distincts) : "affaires directes" dans le titre cible specifiquement la
# bonne variante et exclut l'autre.
TITLE_RE = re.compile(r"compte d.?exploia?tation par branche.{0,40}affaires directes")

PRIMES_EMISES_RE = re.compile(r"^primes emises\b")
CHARGES_PRESTATIONS_RE = re.compile(r"^charges de prestations\b")
CHARGES_ACQUISITION_RE = re.compile(r"^charges d.?acquisition et de gestion nettes\b")

ROW_PATTERNS = [
    (PRIMES_EMISES_RE, "Primes émises"),
    (CHARGES_PRESTATIONS_RE, "Charges de prestations"),
    (CHARGES_ACQUISITION_RE, "Charges d'acquisition et de gestion nettes"),
]

# Distance horizontale max entre une valeur et l'ancre de colonne
# correspondante pour l'y associer (au-dela, la colonne est consideree vide
# pour cette ligne plutot que de rattacher une valeur au mauvais endroit).
MAX_COLUMN_MATCH_DISTANCE = 20


def _derotate_page_words(page):
    """Reconstruit les mots d'une page dont le texte est tourne a 90 degres
    (voir docstring du module). Renvoie None si la page ne contient aucun
    caractere tourne (page normale, annexe absente de cette page)."""
    rotated_chars = [c for c in page.chars if not c["upright"]]
    if not rotated_chars:
        return None
    page_height = float(page.height)
    new_chars = []
    for c in rotated_chars:
        nc = dict(c)
        nc["x0"] = page_height - c["bottom"]
        nc["x1"] = page_height - c["top"]
        nc["top"] = c["x0"]
        nc["bottom"] = c["x1"]
        nc["doctop"] = nc["top"]
        nc["upright"] = True
        new_chars.append(nc)
    return WordExtractor(x_tolerance=3, y_tolerance=3).extract_words(new_chars)


def _page_title(lines, lines_checked=3):
    text = " ".join(
        " ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"]))
        for line in lines[:lines_checked]
    )
    return _normalizer.clean(text)


# Ordre semantique fixe des colonnes de donnees du tableau (voir docstring
# du module) : les 8 branches Non-Vie, puis ASS. VIE, puis 2 colonnes
# agregees non utilisees pour ces KPI (sous-total "Affaires Directes" et
# "Acceptations"), puis le total general (traite separement, cf.
# _extract_row_totals). Le texte d'en-tete ("Automobile", "ASS. VIE"...)
# n'est PAS assez fiablement aligne en x avec sa colonne de donnees (un
# libelle court comme "VIE" peut retomber plus pres de la colonne suivante
# que de la sienne) pour servir d'ancre directe -> on utilise a la place les
# positions (x0) d'une ligne de donnees de reference, en supposant que
# l'ordre des colonnes est le meme d'une ligne a l'autre (verifie sur les
# lignes cibles).
COLUMN_ORDER = [
    "automobile", "maladie", "divers", "incendie",
    "transport", "credit", "agricoles", "travail", "vie",
]

# Nom d'affichage par branche Non-Vie, pour la ventilation de "Primes
# émises" (seule ligne ventilée par branche pour l'instant -> les charges
# ne le sont pas, faute de besoin identifié).
BRANCH_DISPLAY_NAMES = {
    "automobile": "Automobile",
    "maladie": "Groupe Maladie",
    "divers": "Risques Divers",
    "incendie": "Incendie",
    "transport": "Transport",
    "credit": "Credit",
    "agricoles": "Risques Agricoles",
    "travail": "Accidents du Travail",
}


def _column_anchors(lines):
    """Associe a chaque branche Non-Vie et a "vie" la position (x0) de sa
    colonne de donnees, deduite d'une ligne de reference complete (celle
    ayant le plus de valeurs, donc la moins susceptible d'avoir une colonne
    manquante comme "primes emises", qui n'a pas de valeur "accidents du
    travail")."""
    data_rows = [_extract_numeric_clusters(line)[1:] for line in lines if _extract_numeric_clusters(line)]
    if not data_rows:
        return {}
    reference = sorted(max(data_rows, key=len), key=lambda item: item[1])
    return {label: x0 for label, (_, x0) in zip(COLUMN_ORDER, reference)}


def _match_column_value(clusters, anchor_x0):
    """Valeur du cluster le plus proche de `anchor_x0`, ou None si aucun
    cluster n'est assez proche (colonne vide pour cette ligne, ex: valeur
    "Accidents du Travail" absente sur la ligne "primes émises")."""
    if anchor_x0 is None or not clusters:
        return None
    value, x0 = min(clusters, key=lambda item: abs(item[1] - anchor_x0))
    return value if abs(x0 - anchor_x0) <= MAX_COLUMN_MATCH_DISTANCE else None


def _extract_row_totals(lines, anchors, pattern):
    """Pour la ligne dont le libelle correspond a `pattern` : renvoie
    (total, vie, non_vie), ou (None, None, None) si la ligne est
    introuvable. `total` = dernier cluster de la ligne (colonne la plus a
    droite, "TOTAL (AFF. DIR+ACC)"). `non_vie` = somme des colonnes de
    branches trouvees sur la ligne (les colonnes absentes sont ignorees,
    pas comptees comme 0 ; None si aucune des 8 branches n'est trouvee)."""
    for line in lines:
        label = _label_text(line)
        if label is None or not pattern.search(label):
            continue
        clusters = _extract_numeric_clusters(line)
        data_clusters = clusters[1:]  # clusters[0] = numero de ligne
        if not data_clusters:
            continue
        total = data_clusters[-1][0]
        vie = _match_column_value(data_clusters, anchors.get("vie"))
        branch_values = [
            _match_column_value(data_clusters, anchors.get(keyword))
            for keyword in COLUMN_ORDER
            if keyword != "vie"
        ]
        found_branches = [v for v in branch_values if v is not None]
        non_vie = sum(found_branches) if found_branches else None
        return total, vie, non_vie
    return None, None, None


def _extract_branch_premiums(lines, anchors):
    """Ventilation par branche Non-Vie de la ligne "Primes émises" :
    {nom_affichage: valeur} pour les branches trouvées (une branche absente
    de cette ligne pour l'année en cours, ex: "Accidents du Travail" en
    2024, est simplement omise plutôt que mise à 0)."""
    for line in lines:
        label = _label_text(line)
        if label is None or not PRIMES_EMISES_RE.search(label):
            continue
        data_clusters = _extract_numeric_clusters(line)[1:]
        if not data_clusters:
            return {}
        result = {}
        for key, display_name in BRANCH_DISPLAY_NAMES.items():
            value = _match_column_value(data_clusters, anchors.get(key))
            if value is not None:
                result[display_name] = value
        return result
    return {}


KPI_NAMES = []
for _, row_name in ROW_PATTERNS:
    KPI_NAMES.append(f"Total {row_name}")
    KPI_NAMES.append(f"{row_name} Vie")
    KPI_NAMES.append(f"{row_name} Non-Vie")
KPI_NAMES.extend(f"Primes émises par branche (FTUSA) - {name}" for name in BRANCH_DISPLAY_NAMES.values())


def extract_ftusa_kpis(pdf, max_pages=MAX_PAGES_SCANNED):
    """Renvoie les 9 KPI de l'annexe "Compte d'exploitation par branche &
    par entreprise" + la ventilation par branche de "Primes émises" ->
    valeur|None."""
    result = {name: None for name in KPI_NAMES}

    for page in pdf.pages[:max_pages]:
        words = _derotate_page_words(page)
        if not words:
            continue
        lines = _cluster_lines(words, y_tolerance=5)
        if not lines or not TITLE_RE.search(_page_title(lines)):
            continue

        anchors = _column_anchors(lines)
        for pattern, row_name in ROW_PATTERNS:
            total, vie, non_vie = _extract_row_totals(lines, anchors, pattern)
            result[f"Total {row_name}"] = total
            result[f"{row_name} Vie"] = vie
            result[f"{row_name} Non-Vie"] = non_vie
        for display_name, value in _extract_branch_premiums(lines, anchors).items():
            result[f"Primes émises par branche (FTUSA) - {display_name}"] = value
        break  # page de l'annexe trouvee, inutile de continuer a chercher

    return result
