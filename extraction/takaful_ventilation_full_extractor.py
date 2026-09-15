"""Extraction PLEINE GRILLE des Annexes 14/15 Takaful ("Ventilation du
Surplus ou déficit par catégorie d'assurance") — Annexe 14 = Fonds
Familial (colonnes Prévoyance/Épargne/Total, PAS de branches : structure
DVRB, pas de ventilation par branche côté Familial), Annexe 15 = Fonds
Général (colonnes = branches d'assurance + Total à la fin). Source du KPI
narrow existant "Charges de prestations"/"Charges d'acquisition et de
gestion nettes"/contributions par branche (voir extraction/
takaful_kpi_extractor.py::_extract_ventilation_charges_kpis et
extract_branches_ventilation_kpis). Stockée dans `tableau_cellules` sous
'takaful_ventilation_familial'/'takaful_ventilation_general'.

Aucune ligne ne porte de code réglementaire ici (contrairement aux
Annexes 1-5.1) : chaque ligne est un simple libellé comptable en toutes
lettres ("Primes", "Charges de prestations", "Solde de souscription"...).

Côté Général, l'en-tête des branches s'étale sur PLUSIEURS lignes
physiques ET se replie de façon incohérente d'un fragment à l'autre (ex.
AT_TAKAFULIA : "Rubriques Automobile Transport Incendie Groupe Santé, Inc
& Invalidité Maladie Ind/Groupe. RC I.A Assitance RDS Acceptation Total"
sur une ligne, PUIS un fragment orphelin "(Inc/Inv) prévoyance (Inc/Inv)"
sur la ligne suivante) — le lire directement est peu fiable. Comme pour
FTUSA (voir `ftusa_full_extractor.py`), on utilise donc la ligne de
DONNÉES la plus complète comme ANCRE : ses positions x0, triées gauche à
droite, donnent l'ordre réel des colonnes. Seules les 3 premières
colonnes (Automobile/Transport/Incendie) et la dernière (Total) ont un
nom fiable et constant d'une société à l'autre (confirmé sur AT_TAKAFULIA
ET ZITOUNA_TAKAFUL, voir takaful_kpi_extractor.py::_extract_branches_positional)
— les colonnes intermédiaires (variables en nombre ET en ordre exact
selon le document) reçoivent un nom générique "Branche N" : LIMITATION
CONNUE, voir CAS_PARTICULIERS_TAKAFUL_VENTILATION.md.

Signe négatif détaché : ce tableau imprime parfois le signe "‐" comme un
TOKEN SÉPARÉ (espace avant le chiffre, ex. "‐ 941 736"), que
`_extract_numeric_clusters` ignore silencieusement car `NUMERIC_TOKEN_RE`
n'accepte un signe que COLLÉ à des chiffres — le nombre serait sinon
positif à tort. `_merge_detached_minus_signs` réattache ce signe au
premier chiffre du nombre qui suit avant tout calcul de cluster."""

import re

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters, _normalizer,
    _words_with_bracket_negatives_resolved, NUMERIC_TOKEN_RE, MINUS_CHARS,
    _OcrFallbackPage,
)

_DASH_ONLY_RE = re.compile(f"^[{MINUS_CHARS}-]$")
_DASH_PLACEHOLDER_RE = re.compile(f"^[{MINUS_CHARS}-]+$")

_TITLE_RE = {
    "familial": re.compile(r"ventilation.*surplus.*deficit.*categorie.*assurance.*familial"),
    "general": re.compile(r"ventilation.*surplus.*deficit.*categorie.*assurance.*general"),
}

_TITLE_LINE_RE = re.compile(r"^annexe\b|^rubriques?\b")

_FAMILIAL_COLUMNS = ["Prévoyance", "Épargne", "Total"]
_GENERAL_FIXED_PREFIX = ["Automobile", "Transport", "Incendie"]
_GENERAL_FIXED_SUFFIX = "Total"

_MIN_ROWS = 5


def _is_target_page(page, side, lines_checked=4):
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    return bool(_TITLE_RE[side].search(normalized))


def _merge_detached_minus_signs(line):
    """Réattache un token "‐" isolé (espacé du chiffre qui suit) comme
    signe du nombre suivant, plutôt que de le laisser disparaître comme
    non-numérique. Un "‐" qui n'est PAS suivi d'un token numérique reste
    un vrai placeholder "néant" (converti en 0 par l'appelant)."""
    out = []
    i = 0
    while i < len(line):
        w = line[i]
        if _DASH_ONLY_RE.match(w["text"]) and i + 1 < len(line) and NUMERIC_TOKEN_RE.match(line[i + 1]["text"]) \
                and not line[i + 1]["text"].startswith(("-",) + tuple(MINUS_CHARS)):
            nxt = line[i + 1]
            out.append({**nxt, "text": "-" + nxt["text"], "x0": w["x0"]})
            i += 2
            continue
        out.append(w)
        i += 1
    return out


def _resolved_words(line):
    resolved = _words_with_bracket_negatives_resolved(line)
    resolved = _merge_detached_minus_signs(resolved)
    return [{**w, "text": "0"} if _DASH_PLACEHOLDER_RE.match(w["text"]) else w for w in resolved]


def _reference_clusters(lines):
    """Ligne de données la plus complète (le plus de clusters numériques)
    — ses positions x0 gauche->droite donnent l'ordre réel des colonnes,
    l'en-tête étant peu fiable à parser directement (voir docstring)."""
    best = []
    for line in lines:
        label_words = [w for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
        label = _normalizer.clean(" ".join(w["text"] for w in label_words))
        if _TITLE_LINE_RE.match(label):
            continue
        resolved = _resolved_words(line)
        clusters = _extract_numeric_clusters(resolved)
        if len(clusters) > len(best):
            best = clusters
    return sorted(best, key=lambda item: item[1])


def _match_column_value(clusters, anchor_x0, max_distance=40):
    if anchor_x0 is None or not clusters:
        return None
    value, x0 = min(clusters, key=lambda item: abs(item[1] - anchor_x0))
    return value if abs(x0 - anchor_x0) <= max_distance else None


def _column_names(side, n_cols):
    if side == "familial":
        return _FAMILIAL_COLUMNS[:n_cols] if n_cols <= len(_FAMILIAL_COLUMNS) else (
            _FAMILIAL_COLUMNS[:-1] + [f"Colonne {i}" for i in range(1, n_cols - 1)] + [_FAMILIAL_COLUMNS[-1]]
        )
    if n_cols <= len(_GENERAL_FIXED_PREFIX) + 1:
        return (_GENERAL_FIXED_PREFIX + [_GENERAL_FIXED_SUFFIX])[:n_cols]
    n_middle = n_cols - len(_GENERAL_FIXED_PREFIX) - 1
    return _GENERAL_FIXED_PREFIX + [f"Branche {i}" for i in range(1, n_middle + 1)] + [_GENERAL_FIXED_SUFFIX]


def extract_takaful_ventilation_grid(page, side, min_rows=_MIN_ROWS):
    """Reconstruit la grille complète de l'Annexe 14 (side='familial') ou
    15 (side='general') visible sur `page`. Renvoie {"colonnes": [...],
    "lignes": {libellé: {colonne: valeur}}}, ou None si trop peu de
    lignes reconnues."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)
    reference = _reference_clusters(lines)
    n_cols = len(reference)
    if n_cols < 2:
        return None
    colonnes = _column_names(side, n_cols)
    anchors = [x0 for _v, x0 in reference]

    lignes = {}
    for line in lines:
        label_words = [w for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
        label = _normalizer.clean(" ".join(w["text"] for w in label_words)).strip()
        if not label or _TITLE_LINE_RE.match(label):
            continue
        resolved = _resolved_words(line)
        clusters = _extract_numeric_clusters(resolved)
        if not clusters:
            continue
        row = {
            colonnes[i]: value
            for i, anchor_x0 in enumerate(anchors)
            for value in [_match_column_value(clusters, anchor_x0)]
            if value is not None
        }
        if not row:
            continue
        key, n = label, 2
        while key in lignes:
            key = f"{label} ({n})"
            n += 1
        lignes[key] = row

    if len(lignes) < min_rows:
        return None
    return {"colonnes": colonnes, "lignes": lignes}


def locate_and_extract_takaful_ventilation(pdf_path, side, max_pages=45):
    """Parcourt les pages de `pdf_path` à la recherche de l'Annexe 14
    (side='familial') ou 15 (side='general') et en extrait la grille
    complète. Enveloppe chaque page avec `_OcrFallbackPage`. Renvoie
    (numero_page_1_indexe, grille) ou (None, None)."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            ocr_page = _OcrFallbackPage(page)
            if not _is_target_page(ocr_page, side):
                continue
            grid = extract_takaful_ventilation_grid(ocr_page, side)
            if grid is not None:
                return i + 1, grid
    return None, None


def process_takaful_ventilation(pdf_path, side):
    """Pipeline complète pour un côté (side='familial'|'general') : localise
    + extrait, renvoie {"page", "colonnes", "lignes", "validations"} au
    même contrat que les autres pipelines `process_*`, ou None si
    introuvable. Validation : Σ colonnes de branche = colonne "Total",
    ligne par ligne (identité imprimée par la société elle-même)."""
    page, grid = locate_and_extract_takaful_ventilation(pdf_path, side)
    if grid is None:
        return None
    validations = []
    colonnes = grid["colonnes"]
    total_col = colonnes[-1]
    branch_cols = colonnes[:-1]
    for label, vals in grid["lignes"].items():
        if total_col not in vals:
            continue
        attendu = sum(vals.get(c, 0) for c in branch_cols)
        trouve = vals[total_col]
        ecart = round(trouve - attendu, 2)
        validations.append({"regle_code": "takaful_ventilation_total", "regle": "Σ branches = Total",
                             "colonne": label, "attendu": round(attendu, 2), "trouve": round(trouve, 2),
                             "ecart": ecart, "statut": "ok" if abs(ecart) <= 2 else "ecart"})
    return {"page": page, "colonnes": colonnes, "lignes": grid["lignes"], "validations": validations}
