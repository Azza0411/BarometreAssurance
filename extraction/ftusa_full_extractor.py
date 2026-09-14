"""Extraction PLEINE GRILLE de l'annexe FTUSA "Compte d'exploitation par
branche & par entreprise" (par opposition à ftusa_kpi_extractor.py, qui
n'extrait que 3 lignes ciblées + leur ventilation Vie/Non-Vie) — toutes
les lignes (~22 postes comptables, de "Primes acquises" à "Résultat
technique"), 12 colonnes (8 branches Non-Vie + Ass. Vie + Total Aff.
Directes + Acceptations + Total Aff. Dir+Acc), pour le stockage
`tableau_cellules` — même finalité que `bilan_full_extractor.py`/
`annexe13_pipeline.py` pour les documents CMF, mais ici l'entrée reste au
niveau "document" (pas de correction manuelle branchée dans cette
première étape, voir CAS_PARTICULIERS_FTUSA.md).

Contrairement à un document CMF (un par société ET par année), le
document FTUSA est UNIQUE par année : c'est un rapport SECTORIEL agrégé
pour le marché entier (aucune société associée, voir
extraction/kpi_extraction_pipeline.py::_run_ftusa). La grille produite ici
EST directement la donnée finale — pas une ventilation par société.

Réutilise les primitives déjà éprouvées de ftusa_kpi_extractor.py
(dérotation des caractères — le texte de cette page est tourné à 90°,
voir sa docstring —, position des colonnes par ANCRE plutôt que par
lecture d'en-tête : l'en-tête s'étale sur 3 lignes physiques ("Assurance
... Assurance" / "Groupe Risques Risques Accidents ASS. VIE
ACCEPTATIONS..." / "Automobile Maladie Divers Incendie..."), peu fiable
à parser directement — la ligne de DONNÉES la plus complète sert de
référence, ses positions x0 de gauche à droite correspondant à l'ordre
FIXE et connu des 12 colonnes de ce gabarit institutionnel unique)."""

from extraction.bilan_kpi_extractor import _cluster_lines, _extract_numeric_clusters, _label_text
from extraction.ftusa_kpi_extractor import (
    _derotate_page_words, _page_title, TITLE_RE, COLUMN_ORDER, BRANCH_DISPLAY_NAMES,
    MAX_PAGES_SCANNED, MAX_COLUMN_MATCH_DISTANCE,
)

# Les 9 premières colonnes (8 branches Non-Vie + "vie") sont déjà nommées
# par ftusa_kpi_extractor.COLUMN_ORDER/BRANCH_DISPLAY_NAMES — complétées
# ici des 3 colonnes de synthèse (jamais utilisées par l'extraction KPI
# narrow, qui ne s'intéresse qu'aux branches) pour couvrir le tableau EN
# ENTIER.
_EXTRA_COLUMNS = ["total_aff_directes", "acceptations", "total_aff_dir_acc"]
_EXTRA_DISPLAY_NAMES = {
    "total_aff_directes": "Total (Aff. Directes)",
    "acceptations": "Acceptations",
    "total_aff_dir_acc": "Total (Aff. Dir+Acc)",
}
_FULL_COLUMN_ORDER = COLUMN_ORDER + _EXTRA_COLUMNS
_FULL_DISPLAY_NAMES = {**BRANCH_DISPLAY_NAMES, "vie": "Ass. Vie", **_EXTRA_DISPLAY_NAMES}

_MIN_ROWS = 5


def _column_anchors_full(lines):
    """Même principe que `ftusa_kpi_extractor._column_anchors`, étendu aux
    12 colonnes complètes (pas seulement les 9 utilisées par l'extraction
    KPI narrow) : la ligne de DONNÉES la plus complète (le plus de
    clusters numériques) sert de référence — ses positions x0, triées
    gauche->droite, correspondent dans l'ordre à `_FULL_COLUMN_ORDER`.
    `clusters[1:]` : le tout premier cluster de chaque ligne est le NUMÉRO
    de ligne du document (1, 2, 3...22 — imprimé en tête de chaque poste
    comptable), jamais une donnée de colonne."""
    data_rows = []
    for line in lines:
        clusters = _extract_numeric_clusters(line)
        if len(clusters) > 1:
            data_rows.append(clusters[1:])
    if not data_rows:
        return {}
    reference = sorted(max(data_rows, key=len), key=lambda item: item[1])
    return {key: x0 for key, (_v, x0) in zip(_FULL_COLUMN_ORDER, reference)}


def _match_column_value(clusters, anchor_x0, max_distance=MAX_COLUMN_MATCH_DISTANCE):
    if anchor_x0 is None or not clusters:
        return None
    value, x0 = min(clusters, key=lambda item: abs(item[1] - anchor_x0))
    return value if abs(x0 - anchor_x0) <= max_distance else None


def extract_ftusa_full_grid(pdf, max_pages=MAX_PAGES_SCANNED):
    """Reconstruit la grille complète de l'annexe "Compte d'exploitation
    par branche & par entreprise". Renvoie {"page": n° (1-indexé),
    "colonnes": [...], "lignes": {libellé: {colonne: valeur}}}, ou None si
    l'annexe est introuvable ou trop peu exploitable (< `_MIN_ROWS`
    lignes reconnues)."""
    for page_idx, page in enumerate(pdf.pages[:max_pages]):
        words = _derotate_page_words(page)
        if not words:
            continue
        lines = _cluster_lines(words, y_tolerance=5)
        if not lines or not TITLE_RE.search(_page_title(lines)):
            continue

        anchors = _column_anchors_full(lines)
        if not anchors:
            continue
        colonnes = [_FULL_DISPLAY_NAMES[k] for k in _FULL_COLUMN_ORDER if k in anchors]

        lignes = {}
        for line in lines:
            label = _label_text(line)
            clusters = _extract_numeric_clusters(line)
            data_clusters = clusters[1:]  # [0] = numéro de ligne, voir _column_anchors_full
            if not label or not data_clusters:
                # Ligne de continuation (libellé replié sur 2 lignes, sans
                # aucune valeur propre — ex. "...primes non / acquises") :
                # ignorée plutôt que traitée comme un nouveau poste vide.
                continue
            row = {
                _FULL_DISPLAY_NAMES[key]: value
                for key in _FULL_COLUMN_ORDER
                if key in anchors
                for value in [_match_column_value(data_clusters, anchors[key])]
                if value is not None
            }
            if not row:
                continue
            key_name, n = label, 2
            while key_name in lignes:
                key_name = f"{label} ({n})"
                n += 1
            lignes[key_name] = row

        if len(lignes) < _MIN_ROWS:
            continue
        return {"page": page_idx + 1, "colonnes": colonnes, "lignes": lignes}
    return None
