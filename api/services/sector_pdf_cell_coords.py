"""
Localisation de cellule dans les PDF sectoriels (FTUSA/CGA) pour le "Voir le
document source" des KPI sectoriels affichés sur Aperçu Marché — même esprit
que pdf_cell_coords.py (CMF, par société), mais avec une détection de PAGE en
plus (le frontend ne connaît pas à l'avance la page pour ces documents,
contrairement au flux CMF où /api/pdf-sections la fournit séparément).

Réutilise sans les dupliquer :
- La reconstruction de texte tourné à 90° (`_derotate_page_words`) et la
  correspondance de titre de page, déjà validées par
  extraction/ftusa_kpi_extractor.py et extraction/cga_kpi_extractor.py — le
  vrai tableau chiffré de ces deux rapports est toujours tourné, un titre
  homonyme apparaissant aussi tel quel en texte narratif normal (sommaire,
  page d'annexes) ailleurs dans le document (constaté le 2026-08-19 sur
  FTUSA_2024.pdf : "Compte d'exploitation par branche" matche aussi le
  sommaire en page 3 ET la page d'index des annexes en page 81 — ni l'une ni
  l'autre n'est le vrai tableau).
- La recherche de ligne/colonne générique de pdf_cell_coords.py (_word_rows,
  _find_row_y, _find_col_x) : ces fonctions ne font aucune hypothèse propre
  au CMF, elles opèrent sur n'importe quelle liste de mots positionnés.

Ajouté le 2026-08-19 sur demande explicite de l'utilisateur : le surlignage
réel (pas seulement "ouvrir le PDF entier") doit fonctionner pour les KPI
sectoriels comme pour les KPI société.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pdfplumber

from extraction.bilan_kpi_extractor import _cluster_lines, _normalizer
from extraction.ftusa_kpi_extractor import _derotate_page_words, TITLE_RE as _FTUSA_TITLE_RE
from extraction.cga_kpi_extractor import ANNEXE2_TITLE_RE as _CGA_AGENCES_TITLE_RE
from api.services.pdf_cell_coords import _word_rows, _find_row_y, _NUMERIC_TOKEN_RE, _GAP_TOL_NUMERIC, _norm


def _numeric_col_group_bboxes(row_words: list) -> list[tuple]:
    """Comme pdf_cell_coords._numeric_col_groups, mais renvoie la bbox
    (x0, x1) réelle de chaque groupe plutôt que son seul centre — nécessaire
    ici pour dimensionner correctement le rectangle de surlignage après
    inversion de la dérotation (une marge symétrique arbitraire autour du
    centre, suffisante en repère non tourné, donne une bbox mal proportionnée
    une fois convertie en repère natif tourné à 90°)."""
    numeric = [
        w for w in sorted(row_words, key=lambda w: w["x0"])
        if _NUMERIC_TOKEN_RE.match(w["text"]) and any(ch.isdigit() for ch in w["text"])
    ]
    groups: list[list] = []
    for w in numeric:
        if groups and (w["x0"] - groups[-1][-1]["x1"]) <= _GAP_TOL_NUMERIC:
            groups[-1].append(w)
        else:
            groups.append([w])
    return [(min(w["x0"] for w in g), max(w["x1"] for w in g)) for g in groups]

DATA_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)

# Un seul tableau cible par source pour l'instant (celui qui couvre tous les
# KPI sectoriels actuellement affichés sur Aperçu Marché — voir
# frontend/src/utils/kpiMeta.js "KPI sectoriels"). À étendre avec d'autres
# title_re si de nouveaux KPI sectoriels sont ajoutés depuis d'autres
# tableaux du même rapport.
_TITLE_RE_BY_SOURCE = {
    "FTUSA": _FTUSA_TITLE_RE,
    "CGA": _CGA_AGENCES_TITLE_RE,
}

_MAX_PAGES_SCANNED = 100
_cache: dict = {}


def _find_target_page(pdf, title_re, max_pages=_MAX_PAGES_SCANNED):
    """Renvoie (page_num_1_indexed, mots_de_la_page, page_tournee) pour la
    première page dont le titre (parmi ses 4 premières lignes reconstruites,
    dérotées si nécessaire) correspond à `title_re`, sinon (None, None, None)."""
    for i, page in enumerate(pdf.pages[:max_pages]):
        words = _derotate_page_words(page)
        rotated = words is not None
        if not rotated:
            words = page.extract_words()
        if not words:
            continue
        lines = _cluster_lines(words, y_tolerance=5)
        if not lines:
            continue
        title = _normalizer.clean(" ".join(w["text"] for line in lines[:4] for w in line))
        if title_re.search(title):
            return i + 1, words, rotated
    return None, None, None


def _derotated_to_native(bbox, page_height):
    """Convertit une bbox (top, bottom, x0, x1) exprimée dans le repère
    "dérotée" (voir _derotate_page_words) vers le repère NATIF de la page
    (celui que pdf.js utilise pour le rendu, et celui qu'attend déjà le
    frontend — même convention que pdf_cell_coords.get_cell_coords).
    Inverse exact de la transformation appliquée par _derotate_page_words :
        derot.x0  = native_height - native.bottom
        derot.x1  = native_height - native.top
        derot.top = native.x0
        derot.bottom = native.x1
    """
    top, bottom, x0, x1 = bbox
    native_x0 = top
    native_x1 = bottom
    native_top = page_height - x1
    native_bottom = page_height - x0
    return native_x0, native_top, native_x1, native_bottom


def get_sector_cell_coords(source: str, annee: int, ligne: str, colonne: str):
    """Équivalent sectoriel de pdf_cell_coords.get_cell_coords : trouve la
    page ET la cellule en un seul appel (le frontend ne connaît pas la page
    à l'avance pour ces documents). Renvoie (résultat, raison) :
      - résultat = {x0,y0,x1,y1,page_width,page_height,page} si trouvé
      - résultat = None sinon, raison ∈ {pdf_manquant, source_non_prise_en_charge,
        page_introuvable, ligne_introuvable, colonne_introuvable}
        (+ `page` inclus dans la raison quand la page a pu être déterminée,
        pour que le frontend affiche au moins la bonne page même sans
        surlignage précis)."""
    source = source.upper()
    title_re = _TITLE_RE_BY_SOURCE.get(source)
    if title_re is None:
        return None, {"reason": "source_non_prise_en_charge", "page": None}

    path = os.path.join(DATA_ROOT, source.lower(), f"{source}_{annee}.pdf")
    if not os.path.isfile(path):
        return None, {"reason": "pdf_manquant", "page": None}

    ligne_candidates = [c.strip() for c in ligne.split(" || ") if c.strip()]
    colonne_candidates = [_norm(c) for c in colonne.split(" || ") if c.strip()]
    cache_key = (source, int(annee), tuple(ligne_candidates), tuple(colonne_candidates))
    if cache_key in _cache:
        return _cache[cache_key]

    result = None
    reason = {"reason": "erreur", "page": None}
    try:
        with pdfplumber.open(path) as pdf:
            page_num, words, rotated = _find_target_page(pdf, title_re)
            if page_num is None:
                reason = {"reason": "page_introuvable", "page": None}
            else:
                native_page = pdf.pages[page_num - 1]
                page_w = float(native_page.width)
                page_h = float(native_page.height)

                rows = _word_rows(words)
                row_y = None
                for cand in ligne_candidates:
                    row_y = _find_row_y(rows, _norm(cand))
                    if row_y is not None:
                        break
                if row_y is None:
                    reason = {"reason": "ligne_introuvable", "page": page_num}
                else:
                    top_y, bot_y = row_y
                    # Pas de recherche d'en-tête par texte ici : ce tableau tourné
                    # à 90° n'a pas de "TOTAL (AFF. DIR + ACC)" fiablement
                    # repérable comme mot d'en-tête (confirmé le 2026-08-19 sur
                    # FTUSA_2024.pdf p.85), et l'extraction elle-même
                    # (extraction/ftusa_kpi_extractor.py::_extract_row_totals) ne
                    # s'appuie pas non plus sur le texte d'en-tête : elle prend
                    # directement le DERNIER cluster numérique de la ligne comme
                    # "Total" (`data_clusters[-1]`). On applique la même
                    # convention ici, en gardant la bbox RÉELLE du cluster (pas
                    # une marge arbitraire) — nécessaire pour un rectangle bien
                    # proportionné une fois reconverti en repère natif tourné.
                    target_words = next((ws for t, _, ws in rows if t == top_y), [])
                    col_groups = _numeric_col_group_bboxes(target_words)
                    if not col_groups:
                        reason = {"reason": "colonne_introuvable", "page": page_num}
                    else:
                        col_x0, col_x1 = col_groups[-1]
                        bbox = (top_y, bot_y, col_x0, col_x1)
                        if rotated:
                            nx0, ntop, nx1, nbottom = _derotated_to_native(bbox, page_h)
                        else:
                            ntop, nbottom, nx0, nx1 = top_y, bot_y, col_x0, col_x1
                        result = {
                            "x0": float(nx0),
                            "y0": float(page_h - nbottom),
                            "y1": float(page_h - ntop),
                            "x1": float(nx1),
                            "page_width": page_w,
                            "page_height": page_h,
                            "page": page_num,
                        }
    except Exception as exc:
        reason = {"reason": "erreur", "page": None, "detail": str(exc)}

    out = (result, None) if result is not None else (None, reason)
    _cache[cache_key] = out
    return out
