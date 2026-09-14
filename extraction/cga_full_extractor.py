"""Extraction PLEINE GRILLE de l'Annexe 2 (CGA) "Distribution géographique
des agents d'assurance" — par opposition à cga_kpi_extractor.py, qui
génère déjà une kyrielle de KPI nommés dynamiquement (un par compagnie ×
par gouvernorat) mais SANS jamais les organiser en grille, et en écartant
la colonne "Grand Tunis" (sous-total intermédiaire Tunis+Ariana+Ben
Arous+Manouba, jamais utilisé par l'extraction KPI narrow).

Comme FTUSA (voir ftusa_full_extractor.py) : un document CGA est UNIQUE
par année, agrégé pour le marché entier — mais ICI chaque LIGNE de la
grille est une compagnie différente (+ la ligne "TOTAL" du marché), pas
un poste comptable fixe. La grille est directement la donnée finale,
stockée dans `tableau_cellules` avec `document_id` = celui du document
CGA de cette année (pas de société associée à CE document — chaque
COMPAGNIE apparaît comme une LIGNE, pas comme un document séparé).

Réutilise les primitives déjà éprouvées de cga_kpi_extractor.py (la page
est tournée à 90°, même cause que FTUSA — dérotation des caractères) et
`config.company_registry.find_code_by_name` pour rattacher chaque libellé
de ligne (raison sociale complète, ex. "STAR SOCIETE TUNISIENNE
D'ASSURANCES ET DE REASSURANCES") au code canonique de la compagnie
(fallback : le libellé brut si non reconnu, jamais un code deviné)."""

from config.company_registry import find_code_by_name
from extraction.bilan_kpi_extractor import _cluster_lines, _extract_numeric_clusters
from extraction.cga_kpi_extractor import (
    ANNEXE2_TITLE_RE, GOVERNORATE_ORDER, TOTAL_LINE_RE, MAX_PAGES_SCANNED,
    _derotate_page_words, _row_label, _normalizer,
)

# Ordre RÉEL des colonnes telles qu'imprimées sur la page — "Grand Tunis"
# (sous-total Tunis+Ariana+Ben Arous+Manouba) remplace le `None`
# placeholder de `GOVERNORATE_ORDER` (ignoré par l'extraction KPI narrow,
# mais bien présent dans le tableau source), et "Total" ferme la ligne.
_FULL_COLUMN_ORDER = [g if g else "Grand Tunis" for g in GOVERNORATE_ORDER] + ["Total"]
_MIN_ROWS = 3


def extract_cga_agences_full_grid(pdf, max_pages=MAX_PAGES_SCANNED):
    """Reconstruit la grille complète de l'Annexe 2 : une ligne par
    compagnie (code canonique si reconnu, sinon libellé brut) + une ligne
    "TOTAL" (marché entier), une colonne par gouvernorat (24, "Grand
    Tunis" inclus) + "Total". Renvoie {"page": n° (1-indexé), "colonnes":
    [...], "lignes": {ligne: {colonne: valeur}}}, ou None si l'annexe est
    introuvable ou trop peu exploitable (< `_MIN_ROWS` lignes reconnues)."""
    for page_idx, page in enumerate(pdf.pages[:max_pages]):
        words = _derotate_page_words(page)
        if words is None:
            words = page.extract_words()
        lines = _cluster_lines(words, y_tolerance=5)
        if not lines:
            continue
        title = _normalizer.clean(" ".join(w["text"] for line in lines[:4] for w in line))
        if not ANNEXE2_TITLE_RE.search(title):
            continue

        lignes = {}
        for line in lines:
            clusters = _extract_numeric_clusters(line)
            if len(clusters) != len(_FULL_COLUMN_ORDER):
                continue
            label = _row_label(line)
            if not label:
                continue
            normalized = _normalizer.clean(label)
            key = "TOTAL" if TOTAL_LINE_RE.match(normalized) else (find_code_by_name(label) or label.strip())
            row = {col: value for col, (value, _x0) in zip(_FULL_COLUMN_ORDER, clusters)}
            k, n = key, 2
            while k in lignes:
                k = f"{key} ({n})"
                n += 1
            lignes[k] = row

        if len(lignes) < _MIN_ROWS:
            continue
        return {"page": page_idx + 1, "colonnes": _FULL_COLUMN_ORDER, "lignes": lignes}
    return None
