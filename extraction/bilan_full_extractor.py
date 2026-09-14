"""Extraction PLEINE GRILLE du Bilan Actif/Passif (par opposition à
bilan_kpi_extractor.py, qui n'extrait que quelques KPI ciblés) — pour le
stockage tableau_cellules / la page de correction manuelle, comme
Annexe 12/13 (extraction/annexe13_pipeline.py, full_table_extractor.py).

Réutilise les primitives de reconstruction de ligne déjà éprouvées de
bilan_kpi_extractor.py (mots repositionnés par `page.extract_words()`,
regroupés en lignes visuelles par position Y) plutôt que camelot : le
tableau Bilan n'a pas de quadrillage horizontal entre ses lignes de détail
— camelot (flavor "lattice") fusionne alors TOUTES les lignes de détail
d'une section en une seule cellule multi-lignes par colonne, rendant son
DataFrame inexploitable pour une reconstruction ligne-par-ligne fiable
(vérifié : le nombre de lignes internes diffère d'une colonne à l'autre
quand une cellule est vide sur certaines lignes, désynchronisant tout
zip par index dès la première case blanche).

Chaque ligne du Bilan porte un CODE réglementaire standardisé (AC1..AC7,
AC11, AC12... côté Actif ; CP1, CP2..., PA2, PA3, PA31... côté Passif) —
identique chez toutes les sociétés (plan comptable CMF), donc utilisé ici
comme clé canonique plutôt que le libellé français (qui varie/se déforme
bien plus facilement, comme vu sur Annexe 12/13 : OCR, abréviations,
libellés coupés). Colonnes assignées par position (x0 le plus proche de
l'en-tête correspondant), pas par ordre — une cellule vide (ex.
"Amortissements" sur une ligne sans amortissement) ne doit jamais décaler
les valeurs suivantes vers la colonne d'à côté."""

import re

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters, _normalizer,
    ACTIF_PAGE_TITLE_RE, PASSIF_PAGE_TITLE_RE, NUMERIC_TOKEN_RE,
)

_ROW_CODE_RE = re.compile(r"^(AC|PA|CP)(\d+)\b", re.IGNORECASE)

# Ligne de TOTAL général — jamais préfixée d'un code réglementaire (contrairement
# à toutes les autres lignes), donc invisible à _ROW_CODE_RE : traitée à part,
# jamais rattachée par erreur au dernier code rencontré (voir extract_bilan_full_grid).
_TOTAL_ACTIF_RE = re.compile(r"^total\s+(de\s+l['\s]|des\s+)?actifs?\b")
_TOTAL_PASSIF_RE = re.compile(r"^total\s+(du\s+|des\s+)?passifs?\b")

# En-têtes de colonnes recherchés, dans l'ordre gauche->droite attendu.
# Côté Actif : Brut / Amortissements et provisions / Net (année courante) /
# Net (année précédente). Côté Passif : pas de ventilation brut/amort, donc
# seulement les 2 colonnes "Net" (l'en-tête répète "Montant Net" 2 fois,
# distingué par sa position x0, pas par un texte différent).
_HEADER_TOKENS_ACTIF = ["brut", "amort", "net", "net"]
_HEADER_TOKENS_PASSIF = ["net", "net"]


def _is_target_page(page, side, lines_checked=6):
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    title_re = ACTIF_PAGE_TITLE_RE if side == "actif" else PASSIF_PAGE_TITLE_RE
    if not title_re.search(normalized):
        return False
    if side == "actif":
        return "passif" not in normalized
    return True


def _header_column_positions(lines, side):
    """Position x0 de chaque en-tête de colonne numérique, dans l'ordre
    gauche->droite — cherché sur les toutes premières lignes de la page
    (avant que les codes AC../PA../CP.. n'apparaissent). Renvoie une liste
    de x0 triée, de la même longueur que les jetons attendus pour ce côté
    (peut être plus courte si un en-tête n'a pas été retrouvé — le
    classement des valeurs se rabat alors sur l'ordre d'apparition)."""
    tokens = _HEADER_TOKENS_ACTIF if side == "actif" else _HEADER_TOKENS_PASSIF
    header_lines = []
    for line in lines:
        has_code = any(_ROW_CODE_RE.match(_normalizer.clean(w["text"])) for w in line)
        if has_code:
            break
        header_lines.append(line)
    positions = []
    seen = 0
    target = tokens[seen] if tokens else None
    for line in header_lines:
        for w in sorted(line, key=lambda w: w["x0"]):
            if target and _normalizer.clean(w["text"]) == target:
                positions.append(w["x0"])
                seen += 1
                target = tokens[seen] if seen < len(tokens) else None
    return positions


def _assign_columns(clusters, header_x, n_cols):
    """Affecte chaque valeur numérique trouvée sur la ligne (`clusters`,
    liste de (valeur, x0) triée gauche->droite) à l'index de colonne dont
    l'en-tête est le plus proche en x0 — jamais par position ordinale pure,
    pour ne pas décaler les colonnes suivantes quand une cellule est vide.
    Repli sur l'ordre d'apparition si les en-têtes n'ont pas pu être
    localisés (`header_x` vide)."""
    if not header_x:
        return {i: v for i, (v, _x0) in enumerate(clusters) if i < n_cols}
    result = {}
    for value, x0 in clusters:
        idx = min(range(len(header_x)), key=lambda i: abs(header_x[i] - x0))
        # Une valeur ne remplace jamais une déjà affectée à la même colonne
        # (2 clusters proches du même en-tête = vraisemblablement un
        # artefact de segmentation, on garde le premier rencontré).
        result.setdefault(idx, value)
    return result


def extract_bilan_full_grid(page, side, min_rows=5):
    """Reconstruit la grille complète (tous les postes, pas seulement les
    totaux) du Bilan Actif ou Passif visible sur `page`. Renvoie
    {"colonnes": [...], "lignes": {code: {colonne: valeur}}} ou None si la
    page ne ressemble pas assez à un tableau de Bilan exploitable (moins de
    `min_rows` lignes codées trouvées)."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)
    header_x = _header_column_positions(lines, side)
    colonnes = (
        ["Brut", "Amortissements et provisions", "Net", "Net (N-1)"] if side == "actif"
        else ["Net", "Net (N-1)"]
    )
    n_cols = len(colonnes)

    lignes = {}
    label_by_code = {}  # 1er libellé non vide rencontré par code — une ligne
                        # de sous-total répète souvent le code SEUL (sans
                        # libellé), qui ne doit jamais écraser le vrai
                        # libellé déjà vu sur la ligne de titre de section.
    current_code = None
    current_values = {}
    total_re = _TOTAL_ACTIF_RE if side == "actif" else _TOTAL_PASSIF_RE

    def _flush():
        if current_code and current_values:
            lignes[current_code] = {i: v for i, v in current_values.items()}

    for line in lines:
        label_words = [w for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
        clusters = _extract_numeric_clusters(line)
        text_norm = _normalizer.clean(" ".join(w["text"] for w in label_words))
        if total_re.match(text_norm):
            # Ligne de TOTAL général — jamais préfixée d'un code, traitée à
            # part pour ne jamais se retrouver fusionnée avec la dernière
            # section rencontrée (sinon ses valeurs, arrivant après que
            # cette section ait déjà les siennes, seraient silencieusement
            # ignorées par le `setdefault` de la branche "continuation").
            _flush()
            current_code = None
            lignes["TOTAL"] = _assign_columns(clusters, header_x, n_cols)
            label_by_code["TOTAL"] = text_norm
            continue
        m = _ROW_CODE_RE.match(text_norm)
        if m:
            _flush()
            current_code = f"{m.group(1).upper()}{m.group(2)}"
            rest = text_norm[m.end():].strip()
            if rest and current_code not in label_by_code:
                label_by_code[current_code] = rest
            current_values = _assign_columns(clusters, header_x, n_cols)
        elif current_code:
            # Ligne de continuation (libellé replié, ou valeurs arrivées
            # une ligne après un libellé trop long) — rattachée au dernier
            # code rencontré plutôt qu'ignorée.
            if text_norm and current_code not in label_by_code:
                label_by_code[current_code] = text_norm
            if clusters:
                for i, v in _assign_columns(clusters, header_x, n_cols).items():
                    current_values.setdefault(i, v)
    _flush()

    if len(lignes) < min_rows:
        return None
    lignes_out = {
        code: {"libelle": label_by_code.get(code, code), **{
            colonnes[i]: v for i, v in values.items() if i < n_cols
        }}
        for code, values in lignes.items()
    }
    return {"colonnes": colonnes, "lignes": lignes_out}


def locate_and_extract_bilan(pdf_path, side, max_pages=15):
    """Parcourt les premières pages de `pdf_path` à la recherche de la page
    Bilan Actif/Passif (`side` = 'actif' ou 'passif') et en extrait la
    grille complète. Renvoie (numero_page_1_indexe, grille) ou (None, None)."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            if not _is_target_page(page, side):
                continue
            grid = extract_bilan_full_grid(page, side)
            if grid is not None:
                return i + 1, grid
    return None, None
