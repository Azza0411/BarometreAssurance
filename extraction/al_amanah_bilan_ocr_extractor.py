"""Extraction PLEINE GRILLE du Bilan Combiné AL_AMANAH_TAKAFUL pour les
documents SCANNÉS (images, pas de texte réel — voir `is_scanned_page`) :
2023, 2024, 2025 à ce jour, PAR OPPOSITION à
`al_amanah_bilan_full_extractor.py` (texte réel, 2017/2020/2021/2022).
Mêmes clés `tableau_cellules` ('bilan_actif'/'bilan_passif'), même
contrat de sortie — utilisé en REPLI par
`tableau_pipeline_service_bilan.py` quand l'extracteur texte réel ne
trouve rien pour AL_AMANAH_TAKAFUL.

Principe (deux passes OCR indépendantes par ligne, même stratégie que
`arabic_ocr_extractor.py::extract_cell` pour les KPI ciblés, étendue ici
à TOUTES les lignes plutôt qu'à quelques libellés connus) :
  1. OCR modèle ARABE (`_ocr_lines`) pour repérer chaque ligne du tableau
     et son texte approximatif — fiable pour la PRÉSENCE et la POSITION
     (y_range) d'une ligne, PAS pour ses chiffres (le modèle arabe de
     Tesseract les confond fréquemment, ex. "150933537" lu de travers,
     voir arabic_ocr_extractor.py pour l'exemple documenté).
  2. OCR modèle ANGLAIS chiffres-seuls (`ocr_row_numbers`) sur la ZONE
     NUMÉRIQUE de cette même ligne (toujours à GAUCHE du bloc de libellé,
     même mise en page que la version texte réel) pour lire les valeurs —
     bien plus fiable, vérifié par recoupement : sur la ligne "Total
     actif" d'AL_AMANAH_TAKAFUL_2023, cette 2e passe redonne EXACTEMENT
     les mêmes 6 valeurs que celles visibles (à l'œil) dans le texte
     OCR arabe de la même ligne, sauf 1 chiffre isolé (arrondi/erreur
     mineure) — largement suffisant pour une grille exploitable.

Le numéro de code de chaque ligne ("أصل 12", "خصم 31"...) N'EST PAS
reconstruit ici (contrairement à la version texte réel) : le repérer
fiablement demanderait une 3e passe OCR ciblée par ligne, hors de portée
raisonnable pour ce premier jet. Les lignes sont donc numérotées
SÉQUENTIELLEMENT dans l'ordre d'apparition (AC_1, AC_2...) — le libellé
(issu de l'OCR arabe, imparfait mais lisible) reste la clé d'identification
principale pour l'utilisateur en Correction manuelle. Conséquence : pas de
validation Σ postes = Total ici (elle dépendait des codes réglementaires
pour distinguer les lignes "de section" [valeur = déjà une somme] des
lignes de détail, voir bilan_full_extractor.py) — seule la ligne "Total"
elle-même est capturée et fiable."""

import re

from extraction.arabic_ocr_extractor import render_page, _ocr_lines, ocr_row_numbers, is_scanned_page
from extraction.bilan_kpi_extractor import MAX_PLAUSIBLE_VALUE

_AC_PATTERN_RE = re.compile(r"صل")   # "أصل" (Actif) — le hamza initial "أ" est souvent perdu/déformé par l'OCR, "صل" reste le fragment le plus stable
_PA_PATTERN_RE = re.compile(r"خصم|خصو")  # "خصم" (Passif, ligne de détail) / "خصوم" (dans "مجموع الخصوم")
_AN_PATTERN_RE = re.compile(r"صافية")     # "أصول صافية" (Actifs nets)
_CP_PATTERN_RE = re.compile(r"ذاتي")      # "مال ذاتي" (Capitaux propres)
_TOTAL_PATTERN_RE = re.compile(r"مجموع")  # "مجموع..." (toute ligne de total)

_COLUMN_NAMES = [
    "Combiné (N-1)", "Entreprise (N-1)", "Fonds des adhérents (N-1)",
    "Combiné", "Entreprise", "Fonds des adhérents",
]

_MIN_ROWS = 5
_VALUE_ZONE_FRACTION = 0.5  # la zone numérique occupe grossièrement la moitié gauche de la page (voir docstring)


def _row_kind(text):
    """Classe une ligne OCR selon le motif arabe reconnu dans son texte
    (le hamza initial de "أصل" est instable à l'OCR, d'où des motifs
    volontairement courts/tolérants plutôt qu'un préfixe exact)."""
    if _TOTAL_PATTERN_RE.search(text):
        return "total"
    if _AN_PATTERN_RE.search(text):
        return "AN"
    if _CP_PATTERN_RE.search(text):
        return "CP"
    if _PA_PATTERN_RE.search(text):
        return "PA"
    if _AC_PATTERN_RE.search(text):
        return "AC"
    return None


def _extract_side_grid(image, side, min_rows=_MIN_ROWS):
    """Reconstruit la grille complète (Actif ou Passif) depuis l'image
    d'une page scannée. `side` filtre le TYPE de lignes acceptées comme
    lignes de détail ('actif' -> AC uniquement, 'passif' -> AN/CP/PA)."""
    lines = _ocr_lines(image)
    if not lines:
        return None
    value_x_range = (0, int(image.width * _VALUE_ZONE_FRACTION))

    wanted_kinds = {"AC"} if side == "actif" else {"AN", "CP", "PA"}
    lignes, last_detail_y = {}, 0
    total_candidates, unclassified = [], []
    seq = {"AC": 0, "AN": 0, "CP": 0, "PA": 0}
    for text, box in lines:
        kind = _row_kind(text)
        y_range = (box[1], box[3])
        values = ocr_row_numbers(image, y_range, value_x_range)
        # Un groupe de chiffres mal segmenté par l'OCR peut fusionner
        # plusieurs valeurs en un seul nombre absurde (ex. 16 chiffres) —
        # écarté plutôt que stocké tel quel.
        row = {
            _COLUMN_NAMES[i]: v for i, v in enumerate(values)
            if i < len(_COLUMN_NAMES) and v is not None and abs(v) <= MAX_PLAUSIBLE_VALUE
        }

        if kind == "total" and row:
            # Une page Passif porte PLUSIEURS lignes "مجموع..." distinctes
            # et sémantiquement différentes (Total Actifs nets, Total
            # Capitaux propres, Total Passif, Total général) — les garder
            # TOUTES plutôt que de n'en choisir qu'une "au plus large
            # nombre de colonnes" : ce choix s'est révélé FAUX en pratique
            # (constaté sur AL_AMANAH_TAKAFUL_2023 : la ligne retenue à
            # tort était "Total Actifs nets", pas le total attendu, alors
            # que "Total Capitaux propres" — la bonne réponse, recoupée
            # avec le KPI narrow déjà validé, 23 794 138 — avait
            # simplement une colonne de moins reconnue par l'OCR).
            total_candidates.append((box[1], row))
            continue
        if kind in wanted_kinds and row:
            seq[kind] += 1
            key = f"{kind}_{seq[kind]}"
            row["libelle"] = text.strip()
            lignes[key] = row
            last_detail_y = max(last_detail_y, box[1])
        elif kind is None and row:
            # Non classée par le motif arabe (ex: "مجموع..." parfois
            # totalement méconnaissable après OCR, voir docstring) —
            # candidate de repli pour un total manqué : ligne suffisamment
            # peuplée après la DERNIÈRE ligne de détail classée (un total
            # est toujours en bas de tableau, après tous les postes).
            unclassified.append((box[1], row))

    if not total_candidates:
        total_candidates = [(y, row) for y, row in unclassified if y >= last_detail_y and len(row) >= 4]

    if len(lignes) < min_rows:
        return None
    for i, (_y, row) in enumerate(sorted(total_candidates, key=lambda item: item[0]), 1):
        key = "TOTAL" if len(total_candidates) == 1 else f"TOTAL_{i}"
        lignes[key] = {**row, "libelle": "Total" if key == "TOTAL" else f"Total {i}"}
    return {"colonnes": _COLUMN_NAMES, "lignes": lignes}


def locate_and_extract_al_amanah_bilan_ocr(pdf_path, side, max_pages=10):
    """Parcourt les premières pages SCANNÉES de `pdf_path` (pages à texte
    réel ignorées — couvertes par `al_amanah_bilan_full_extractor.py`) à
    la recherche du Bilan Actif/Passif. Renvoie (numero_page_1_indexe,
    grille) ou (None, None)."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            if not is_scanned_page(page):
                continue
            image = render_page(page)
            grid = _extract_side_grid(image, side)
            if grid is not None:
                return i + 1, grid
    return None, None


def process_al_amanah_bilan_ocr(pdf_path):
    """Pipeline complète pour un document scanné : localise + extrait
    l'Actif ET le Passif. Renvoie {"actif": {...}|None, "passif":
    {...}|None}, chacun au contrat {page, colonnes, lignes, validations}
    (validations toujours vide, voir docstring du module). None si ni
    l'un ni l'autre n'a pu être extrait."""
    page_actif, grid_actif = locate_and_extract_al_amanah_bilan_ocr(pdf_path, "actif")
    page_passif, grid_passif = locate_and_extract_al_amanah_bilan_ocr(pdf_path, "passif")
    if grid_actif is None and grid_passif is None:
        return None

    def _build(page, grid):
        if not grid:
            return None
        lignes = {}
        for code, vals in grid["lignes"].items():
            libelle = vals.get("libelle") or code
            key = code if code == "TOTAL" or libelle == code else f"{code} — {libelle}"
            lignes[key] = {c: v for c, v in vals.items() if c != "libelle"}
        return {"page": page, "colonnes": grid["colonnes"], "lignes": lignes, "validations": []}

    return {"actif": _build(page_actif, grid_actif), "passif": _build(page_passif, grid_passif)}
