"""Extraction des 5 tableaux Takaful spécifiques d'AL_AMANAH_TAKAFUL depuis
ses PDFs en arabe (texte réel, non scanné — `is_scanned_page` en garde-fou).

Tableaux extraits :
  - takaful_surplus_familial   : Annexe 3 — État surplus/déficit Takaful Familial
  - takaful_surplus_general    : Annexe 4 — État surplus/déficit Takaful Général
  - takaful_resultat_entreprise: Annexe 5.1 — État de résultat de l'entreprise
  - takaful_ventilation_familial: Annexe 14 — Ventilation par catégorie (Familial)
  - takaful_ventilation_general : Annexe 15 — Ventilation par catégorie (Général)

Les noms de colonnes et libellés de lignes sont conservés en arabe,
identiques au PDF original (contrairement aux extracteurs français qui
normalisent en français). L'export Excel produit donc des colonnes arabes
pour cette société uniquement.

Contrainte : certaines années (ex. 2018, 2023) ont leurs états financiers
principaux (Annexes 3/4/5.1) sous forme d'images scannées — ces pages
sont ignorées (renvoie None) ; les Annexes 14/15 restent en texte et
sont extraites normalement pour toutes les années disponibles."""

import re
import pdfplumber

from backend.extraction.arabic_ocr_extractor import _rtl_label_from_words, is_scanned_page

# ── Titres de détection (sous-chaînes en arabe) ──────────────────────────────
_TITLE_SURPLUS_FAM   = "يلئاعلا يلفاكتلا نيمأتلا"   # contient "يلئاعلا" → familial
_TITLE_SURPLUS_GEN   = "ماعلا يلفاكتلا نيمأتلا"       # contient "ماعلا" → général
_TITLE_RESULTAT      = "جئاتنلا ةمئاق"                 # "État de résultat"
_TITLE_VENTIL_14     = "14 ددع قحلملا"                 # Annexe 14
_TITLE_VENTIL_15     = "15 ددع قحلملا"                 # Annexe 15

# ── Paramètres communs ────────────────────────────────────────────────────────
_Y_ROW_TOLERANCE    = 4   # pixels — même y → même ligne
_MIN_DIGIT_LEN      = 1   # longueur min d'un fragment numérique
_MAX_PAGES          = 40  # nombre max de pages à scanner


# ── Utilitaires bas niveau ───────────────────────────────────────────────────

def _is_num_fragment(text):
    """Vrai si le token est un fragment numérique (chiffres, signe, virgule)."""
    stripped = text.replace(",", "").replace(".", "").replace("-", "").replace(" ", "")
    return len(stripped) >= _MIN_DIGIT_LEN and stripped.isdigit()


def _group_by_row(words, y_tol=_Y_ROW_TOLERANCE):
    """Regroupe les mots par ligne (y arrondi). Renvoie list[(y_centre, [mots])]."""
    rows = {}
    for w in words:
        y_key = round(w["top"] / y_tol) * y_tol
        rows.setdefault(y_key, []).append(w)
    return sorted(rows.items())


def _assemble_number(fragments):
    """Assemble des fragments numériques (triés par x croissant) en entier ou float.
    Ex : [('9', 226), ('182', 231), ('748', 245)] → 9182748."""
    # Trier par x croissant (plus à gauche = plus significatif pour les nombres)
    frags = sorted(fragments, key=lambda f: f[1])
    raw = "".join(f[0] for f in frags).strip()
    raw = raw.replace(",", "").replace(" ", "")
    try:
        return float(raw) if "." in raw else int(raw)
    except ValueError:
        return None


def _extract_grid_from_page(page, col_bands, label_x_min, note_band=None,
                             data_y_min=170):
    """Extrait une grille (colonnes + lignes) d'une page arabe.

    col_bands : liste de (x_lo, x_hi, col_name) — bandes x des colonnes
    label_x_min : x minimum pour les mots faisant partie du libellé de ligne
    note_band   : (x_lo, x_hi) à ignorer (colonne numéro de note) — optionnel
    data_y_min  : y minimum des lignes de données (ignore l'en-tête)
    """
    words = page.extract_words()
    if not words:
        return None

    colonnes = [cb[2] for cb in col_bands]
    lignes = {}

    for y_key, row_words in _group_by_row(words):
        if y_key < data_y_min:
            continue

        # Séparer mots-label et fragments numériques
        label_parts = []
        col_frags = {i: [] for i in range(len(col_bands))}

        for w in row_words:
            x = w["x0"]
            txt = w["text"]

            # Zone note (colonne de référence d'annexe) → ignorer
            if note_band and note_band[0] <= x <= note_band[1]:
                continue

            # Zone label (droite de la page)
            if x >= label_x_min:
                label_parts.append(w)
                continue

            # Tentative d'affectation à une colonne numérique
            assigned = False
            for i, (xlo, xhi, _) in enumerate(col_bands):
                if xlo <= x <= xhi and _is_num_fragment(txt):
                    col_frags[i].append((txt, x))
                    assigned = True
                    break

        if not any(col_frags[i] for i in range(len(col_bands))):
            continue  # ligne sans données numériques

        # Reconstituer le libellé (RTL)
        label = _rtl_label_from_words(label_parts) if label_parts else ""
        if not label:
            label = f"_row_y{y_key}"

        # Reconstituer les valeurs par colonne
        row_vals = {}
        for i, (_, _, col_name) in enumerate(col_bands):
            frags = col_frags[i]
            if frags:
                val = _assemble_number(frags)
                if val is not None:
                    row_vals[col_name] = val

        if row_vals:
            if label in lignes:
                label = f"{label}_{y_key}"
            lignes[label] = row_vals

    if not lignes:
        return None
    return {"colonnes": colonnes, "lignes": lignes}


# ── Détection de page ─────────────────────────────────────────────────────────

def _page_contains(page, keyword):
    text = (page.extract_text() or "")[:500]
    return keyword in text


# ── Surplus familial / général (Annexes 3/4) ─────────────────────────────────
# Structure : 4 colonnes
#   0. إجمالي العمليات (Total brut)          x ~ [210, 260]
#   1. العمليات المعادة (Rétrocessions)       x ~ [165, 210]
#   2. العمليات الصافية (Net N)              x ~ [110, 165]
#   3. العمليات الصافية ن-1 (Net N-1)        x ~ [60,  110]
# Note reference : x ~ [260, 300]
# Labels          : x > 310

_SURPLUS_COL_BANDS = [
    (210, 262, "إجمالي العمليات"),
    (165, 210, "العمليات المعادة"),
    (110, 165, "العمليات الصافية"),
    (60,  110, "العمليات الصافية (ن-1)"),
]
_SURPLUS_LABEL_X_MIN = 310
_SURPLUS_NOTE_BAND   = (262, 305)
_SURPLUS_DATA_Y_MIN  = 185
_SURPLUS_MIN_ROWS    = 8   # nb minimum de lignes pour valider (écarte les pages de notes)
_SURPLUS_MIN_MULTICOL = 5  # nb minimum de lignes avec ≥2 colonnes renseignées


def _is_valid_grid(grid, min_rows, min_multicol):
    """Vrai si la grille a suffisamment de lignes et de colonnes peuplées."""
    if not grid or len(grid["lignes"]) < min_rows:
        return False
    multicol = sum(1 for v in grid["lignes"].values() if len(v) >= 2)
    return multicol >= min_multicol


def extract_takaful_surplus_ar(pdf_path, side):
    """Extrait l'Annexe 3 (side='familial') ou 4 (side='general').
    Renvoie None si la page n'est pas trouvée ou est scannée."""
    title_kw = _TITLE_SURPLUS_FAM if side == "familial" else _TITLE_SURPLUS_GEN
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:_MAX_PAGES]):
            if is_scanned_page(page):
                continue
            text = page.extract_text() or ""
            # Titre DOIT contenir notre mot-clé + "قودنص" (fonds) ET être dans le 1er tiers
            # Cela exclut Annexes 16/17 ("طبر لودج" = tableau de liaison, sans "قودنص")
            top_text = " ".join(
                w["text"] for w in page.extract_words() if w["top"] < 120
            )
            if title_kw not in top_text:
                continue
            if "قودنص" not in top_text:  # doit contenir "fonds"
                continue
            if "ةمئاق" not in top_text and "ةمئاق" not in text[:300]:
                continue
            words = page.extract_words()
            nums = [w for w in words if _is_num_fragment(w["text"])]
            if len(nums) < 20:
                continue
            grid = _extract_grid_from_page(
                page,
                col_bands=_SURPLUS_COL_BANDS,
                label_x_min=_SURPLUS_LABEL_X_MIN,
                note_band=_SURPLUS_NOTE_BAND,
                data_y_min=_SURPLUS_DATA_Y_MIN,
            )
            if _is_valid_grid(grid, _SURPLUS_MIN_ROWS, _SURPLUS_MIN_MULTICOL):
                return {"page": i + 1, **grid}
    return None


# ── Résultat entreprise (Annexe 5.1) ─────────────────────────────────────────
# Structure : 2 colonnes (N et N-1)
#   0. العمليات الصافية (Net N)   x ~ [150, 200]
#   1. العمليات الصافية (Net N-1) x ~ [90,  130]
# Note reference : x ~ [195, 215]
# Labels          : x > 220

_RESULTAT_COL_BANDS = [
    (145, 200, "صافي العمليات (ن)"),
    (85,  145, "صافي العمليات (ن-1)"),
]
_RESULTAT_LABEL_X_MIN = 225
_RESULTAT_NOTE_BAND   = (195, 225)
_RESULTAT_DATA_Y_MIN  = 185


def extract_takaful_resultat_ar(pdf_path):
    """Extrait l'Annexe 5.1 (État de résultat de l'entreprise).
    Renvoie None si non trouvée ou scannée."""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:_MAX_PAGES]):
            if is_scanned_page(page):
                continue
            if not _page_contains(page, _TITLE_RESULTAT):
                continue
            words = page.extract_words()
            nums = [w for w in words if _is_num_fragment(w["text"])]
            if len(nums) < 5:
                continue
            grid = _extract_grid_from_page(
                page,
                col_bands=_RESULTAT_COL_BANDS,
                label_x_min=_RESULTAT_LABEL_X_MIN,
                note_band=_RESULTAT_NOTE_BAND,
                data_y_min=_RESULTAT_DATA_Y_MIN,
            )
            if grid and len(grid["lignes"]) >= 3:
                return {"page": i + 1, **grid}
    return None


# ── Ventilation familiale (Annexe 14) ─────────────────────────────────────────
# Structure : 3 colonnes
#   0. التأمين على الحياة (Vie)      x ~ [205, 250]
#   1. تكوين الأموال (Épargne)       x ~ [145, 205]
#   2. مجموع (Total)                 x ~ [85,  145]
# Labels : x > 450

_VENTIL_FAM_COL_BANDS = [
    (205, 250, "التأمين على الحياة"),
    (145, 205, "تكوين الأموال"),
    (85,  145, "مجموع"),
]
_VENTIL_FAM_LABEL_X_MIN = 450
_VENTIL_FAM_DATA_Y_MIN  = 195


def extract_takaful_ventilation_fam_ar(pdf_path):
    """Extrait l'Annexe 14 (ventilation familiale). Renvoie None si non trouvée."""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:_MAX_PAGES]):
            if is_scanned_page(page):
                continue
            if not _page_contains(page, _TITLE_VENTIL_14):
                continue
            words = page.extract_words()
            nums = [w for w in words if _is_num_fragment(w["text"])]
            if len(nums) < 5:
                continue
            grid = _extract_grid_from_page(
                page,
                col_bands=_VENTIL_FAM_COL_BANDS,
                label_x_min=_VENTIL_FAM_LABEL_X_MIN,
                data_y_min=_VENTIL_FAM_DATA_Y_MIN,
            )
            if grid and len(grid["lignes"]) >= 3:
                return {"page": i + 1, **grid}
    return None


# ── Ventilation générale (Annexe 15) ─────────────────────────────────────────
# Structure : 9 colonnes (plusieurs branches + total)
# En-têtes à y ~ 128 dans le PDF 2023 :
#   (100)تارايسلا  x ~ [565, 595]
#   (2)لقنلا       x ~ [495, 520]
#   (300)قيرحلا    x ~ [435, 465]
#   (410+420)ءانبلا x ~ [380, 410]
#   (500+600+700)  x ~ [320, 355]
#   (900)ةدعاسملا  x ~ [265, 295]
#   (1200)ةحصلا   x ~ [210, 240]
#   (1500)ثداوحلا  x ~ [150, 185]
#   مجموع           x ~ [90,  125]
# Labels : x > 620

_VENTIL_GEN_COL_BANDS = [
    (560, 600, "(100) السيارات"),
    (490, 525, "(2) النقل"),
    (430, 468, "(300) الحريق"),
    (375, 415, "(410+420) البناء"),
    (315, 355, "(500+600+700) متنوعة"),
    (260, 298, "(900) المساعدة"),
    (205, 242, "(1200) الصحة"),
    (148, 183, "(1500) الحوادث الجسدية"),
    (88,  128, "مجموع"),
]
_VENTIL_GEN_LABEL_X_MIN = 625
_VENTIL_GEN_DATA_Y_MIN  = 145


def extract_takaful_ventilation_gen_ar(pdf_path):
    """Extrait l'Annexe 15 (ventilation générale). Renvoie None si non trouvée."""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:_MAX_PAGES]):
            if is_scanned_page(page):
                continue
            if not _page_contains(page, _TITLE_VENTIL_15):
                continue
            words = page.extract_words()
            nums = [w for w in words if _is_num_fragment(w["text"])]
            if len(nums) < 10:
                continue
            grid = _extract_grid_from_page(
                page,
                col_bands=_VENTIL_GEN_COL_BANDS,
                label_x_min=_VENTIL_GEN_LABEL_X_MIN,
                data_y_min=_VENTIL_GEN_DATA_Y_MIN,
            )
            if grid and len(grid["lignes"]) >= 3:
                return {"page": i + 1, **grid}
    return None


# ── Point d'entrée principal ──────────────────────────────────────────────────

def process_al_amanah_takaful(pdf_path, tableau_key):
    """Extrait le tableau désigné par `tableau_key` du PDF AL_AMANAH.
    Renvoie None si introuvable ou scannée.

    tableau_key in {
        'takaful_surplus_familial', 'takaful_surplus_general',
        'takaful_resultat_entreprise',
        'takaful_ventilation_familial', 'takaful_ventilation_general'
    }"""
    if tableau_key == "takaful_surplus_familial":
        return extract_takaful_surplus_ar(pdf_path, "familial")
    if tableau_key == "takaful_surplus_general":
        return extract_takaful_surplus_ar(pdf_path, "general")
    if tableau_key == "takaful_resultat_entreprise":
        return extract_takaful_resultat_ar(pdf_path)
    if tableau_key == "takaful_ventilation_familial":
        return extract_takaful_ventilation_fam_ar(pdf_path)
    if tableau_key == "takaful_ventilation_general":
        return extract_takaful_ventilation_gen_ar(pdf_path)
    raise ValueError(f"tableau_key inconnu : {tableau_key!r}")
