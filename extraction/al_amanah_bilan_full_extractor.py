"""Extraction PLEINE GRILLE du Bilan Combiné AL_AMANAH_TAKAFUL (documents
en ARABE, texte réel non scanné — voir `is_scanned_page`) — même clés
`tableau_cellules` ('bilan_actif'/'bilan_passif') que
`bilan_full_extractor.py`, pour que Correction manuelle et l'export
fonctionnent identiquement pour cette société sans branche spéciale côté
frontend/API.

AL_AMANAH_TAKAFUL est la seule compagnie Takaful dont les états financiers
sont publiés en arabe — jusqu'ici hors périmètre des extracteurs texte
français (voir extraction/takaful_kpi_extractor.py::extract_al_amanah_takaful_kpis,
qui ne récupère que quelques KPI ciblés via recherche floue OCR/texte, PAS
une grille complète). Ce module reconstruit la grille complète en
réutilisant le même gabarit "Bilan Combiné" que les Takaful francophones
(3 sous-colonnes Entreprise/Fonds des participants/Combiné × 2 exercices),
avec les particularités suivantes, propres au texte arabe :

1. **RTL et fragmentation de mots** : pdfplumber extrait le texte arabe de
   ce document avec des caractères parfois inversés PAR MOT et des espaces
   internes parasites (kerning) — déjà rencontré et résolu pour les KPI
   ciblés (voir `extraction/arabic_ocr_extractor.py::_rtl_label_from_words`,
   réutilisée ici telle quelle pour reconstruire un libellé de ligne
   propre).

2. **Numéro de code de ligne "hors bande"** : chaque ligne porte un code
   réglementaire arabe ("أصل" = Actif, "أصول صافية" = Actifs nets des
   adhérents, "مال ذاتي" = Capitaux propres, "خصم" = Passif) suivi d'un
   numéro (1, 12, 13...) — mais ce numéro n'est PAS collé au mot-préfixe
   (token séparé) et se retrouve mélangé aux mots du libellé une fois le
   texte reconstruit, comme les valeurs "Sous total N" chez les Takaful
   francophones (voir takaful_surplus_full_extractor.py). Repéré ici par
   POSITION plutôt que par forme : tout token numérique dont x0 tombe DANS
   ou AU-DELÀ du début du bloc de libellé (`label_min_x0`) est un numéro
   de code/renvoi, jamais une valeur — les vraies valeurs sont TOUJOURS
   physiquement à GAUCHE du bloc de libellé sur ce gabarit (mise en page
   bilingue chiffres-occidentaux/texte-arabe). Vérifié par recoupement
   direct avec le KPI narrow déjà validé ("Total actif" = 17 448 993 pour
   AL_AMANAH_TAKAFUL_2020, retrouvé exactement à la position attendue).

3. **Ordre des 6 colonnes DIFFÉRENT du gabarit francophone** : sur ce
   document, l'ordre gauche→droite est [Combiné, Entreprise, Fonds des
   participants] PAR EXERCICE, exercice le plus ANCIEN à gauche - alors
   que bilan_full_extractor.py (Takaful francophone) utilise [Entreprise,
   Fonds, Combiné], exercice COURANT en premier. Découvert par
   recoupement arithmétique (Combiné = Entreprise + Fonds sur chaque
   groupe de 3) et confirmé par la position x0 de "Total actif" ; comme le
   nombre de colonnes réellement peuplées varie ligne par ligne (colonnes
   vides SANS AUCUN token, pas même un tiret), l'affectation se fait par
   ANCRE (position x0 de la ligne de référence la plus complète), pas par
   position ordinale — même technique que ftusa_full_extractor.py /
   takaful_ventilation_full_extractor.py.

Portée actuelle : Bilan Actif/Passif uniquement, pour les DOCUMENTS AVEC
TEXTE RÉEL (pas scannés — `is_scanned_page` en garde-fou). Les Annexes
3/4/5.1/14/15 et les années scannées restent HORS PÉRIMÈTRE de ce module
— voir extraction/CAS_PARTICULIERS_TAKAFUL_SURPLUS.md pour le suivi."""

import re

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters,
    _words_with_bracket_negatives_resolved, NUMERIC_TOKEN_RE,
)
from extraction.arabic_ocr_extractor import _rtl_label_from_words, is_scanned_page

_AC_PREFIX = "أصل"
_AN_PREFIX = "أصولصافية"
_CP_PREFIX = "مالذاتي"
_PA_PREFIX = "خصم"

# Chaînes copiées EXACTEMENT depuis la sortie réelle de
# `_row_label_and_code` (voir CAS_PARTICULIERS_TAKAFUL_SURPLUS.md,
# section AL_AMANAH) plutôt que retapées à la main : une frappe manuelle de
# ces constantes arabes a produit un bug silencieux au premier jet (une
# lettre "ل"/"أ" mal ordonnée dans "الأصول", donc AUCUNE correspondance de
# préfixe, jamais une erreur explicite) — la reconstruction RTL
# (`_rtl_label_from_words`, normalisation NFKC incluse) ne produit pas
# toujours l'orthographe "attendue" au clavier.
_TOTAL_CP_PA = "مجموعاألموالالذاتيةوالخصوم"  # sous-total CP+Passif (PAS le total général)
_TOTAL_AN_CP = "مجموعاألصولالصافيةواألموالالذاتية"  # sous-total AN+CP (PAS le total général)
_TOTAL_CP = "مجموعاألموالالذاتية"
_TOTAL_PA = "مجموعالخصوم"
_TOTAL_AN = "مجموعاألصولالصافية"
_TOTAL_AC = "مجموعاألصول"

# Ordre confirmé par recoupement arithmétique + position x0 du KPI narrow
# déjà validé (voir docstring du module, point 3) : PAS le même ordre que
# le gabarit francophone.
_COLUMN_NAMES = [
    "Combiné (N-1)", "Entreprise (N-1)", "Fonds des adhérents (N-1)",
    "Combiné", "Entreprise", "Fonds des adhérents",
]

_MIN_ROWS = 5


def _strip_spaces(text):
    return text.replace(" ", "").replace(" ", "")




def _row_label_and_code(line):
    """Reconstruit le libellé propre (RTL, dé-fragmenté) et sépare les
    tokens numériques en (valeurs réelles, numéro de code de ligne) selon
    la règle de position décrite dans le docstring du module (§2). Renvoie
    (label_stripped, resolved_value_words, code_number_str_or_None) — le
    numéro de code (ex. "1", "12") est la concaténation, dans l'ordre x0
    croissant, des tokens numériques tombant DANS ou AU-DELÀ du bloc de
    libellé ; None si aucun (ex. la ligne "Total")."""
    label = _strip_spaces(_rtl_label_from_words(line))
    non_numeric = [w for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
    if not non_numeric:
        return label, line, None
    label_min_x0 = min(w["x0"] for w in non_numeric)
    value_words = [w for w in line if not (NUMERIC_TOKEN_RE.match(w["text"]) and w["x0"] >= label_min_x0)]
    code_words = sorted(
        (w for w in line if NUMERIC_TOKEN_RE.match(w["text"]) and w["x0"] >= label_min_x0),
        key=lambda w: w["x0"],
    )
    code = "".join(w["text"] for w in code_words) or None
    return label, value_words, code


_ANY_TOTAL_PREFIXES = (_TOTAL_CP_PA, _TOTAL_AN_CP, _TOTAL_CP, _TOTAL_PA, _TOTAL_AN, _TOTAL_AC)
# Seuls les DEUX vrais totaux de bas de page (Total Actif / Total Passif)
# se sont révélés fiables (toujours exactement 6 valeurs propres) — les
# sous-totaux intermédiaires (AN+CP, CP+Passif) peuvent porter un renvoi de
# note mal filtré par `_row_label_and_code`, gonflant leur nombre de
# clusters à tort (constaté : 7 au lieu de 6 sur "Total AN+CP" côté
# Passif). Restreindre l'ancre à ces deux-là évite ce piège.
_RELIABLE_TOTAL_PREFIXES = (_TOTAL_AC, _TOTAL_PA)


def _reference_anchors(lines):
    """Ligne de référence pour la position des colonnes : en PRIORITÉ un
    des deux VRAIS totaux de page (voir `_RELIABLE_TOTAL_PREFIXES`), repli
    sur la ligne de détail avec le plus de clusters numériques sinon (une
    ligne de détail peut aussi porter un renvoi de note mal filtré, donc
    moins fiable, mais reste le seul repli possible si aucun total n'est
    trouvé sur la page)."""
    best, best_total = [], []
    for line in lines:
        label, value_words, _code = _row_label_and_code(line)
        resolved = _words_with_bracket_negatives_resolved(value_words)
        clusters = _extract_numeric_clusters(resolved)
        # "مجموع الأصول الصافية" (Total AN, côté Passif) est un SUR-ensemble
        # de "مجموع الأصول" (_TOTAL_AC) une fois les espaces retirés — ne
        # jamais la laisser passer pour le total Actif fiable.
        is_reliable_total = any(label.startswith(p) for p in _RELIABLE_TOTAL_PREFIXES) and \
            not label.startswith(_TOTAL_AN)
        if is_reliable_total:
            if len(clusters) > len(best_total):
                best_total = clusters
        elif len(clusters) > len(best):
            best = clusters
    return sorted(best_total or best, key=lambda item: item[1])


def _match_column_value(clusters, anchor_x0, max_distance=25):
    if anchor_x0 is None or not clusters:
        return None
    value, x0 = min(clusters, key=lambda item: abs(item[1] - anchor_x0))
    return value if abs(x0 - anchor_x0) <= max_distance else None


def extract_al_amanah_bilan_grid(page, side, min_rows=_MIN_ROWS):
    """Reconstruit la grille complète du Bilan (side='actif'|'passif')
    visible sur `page`. Renvoie {"colonnes": [...], "lignes": {code:
    {"libelle":..., colonne: valeur}}}, ou None si trop peu de lignes
    reconnues."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)
    reference = _reference_anchors(lines)
    n_cols = len(reference)
    if n_cols < 2 or n_cols > len(_COLUMN_NAMES):
        # > 6 colonnes : ce n'est pas la page Bilan Combiné (gabarit fixe à
        # 6 colonnes) mais probablement une autre page numérique du
        # document (ex. Tableau des engagements) rencontrée en balayant
        # toutes les pages faute de détection de titre fiable en arabe
        # (voir docstring du module) — écartée plutôt que mal interprétée.
        return None
    colonnes = _COLUMN_NAMES[-n_cols:]
    anchors = [x0 for _v, x0 in reference]

    lignes = {}
    for line in lines:
        label, value_words, code = _row_label_and_code(line)
        if not label:
            continue
        resolved = _words_with_bracket_negatives_resolved(value_words)
        clusters = _extract_numeric_clusters(resolved)
        if not clusters:
            continue

        if side == "actif":
            if label.startswith(_TOTAL_AC):
                key, desc = "TOTAL", label
            elif label.startswith(_AC_PREFIX) and code:
                key, desc = "AC" + code, label[len(_AC_PREFIX):]
            else:
                continue
        else:
            if label.startswith(_TOTAL_CP_PA):
                key, desc = "TOTAL_CP_PA", label
            elif label.startswith(_TOTAL_AN_CP):
                key, desc = "TOTAL_AN_CP", label
            elif label.startswith(_TOTAL_CP):
                key, desc = "TOTAL_CP", label
            elif label.startswith(_TOTAL_PA):
                key, desc = "TOTAL", label
            elif label.startswith(_TOTAL_AN):
                key, desc = "TOTAL_AN", label
            elif label.startswith(_AN_PREFIX) and code:
                key, desc = "AN" + code, label[len(_AN_PREFIX):].lstrip("-")
            elif label.startswith(_CP_PREFIX) and code:
                key, desc = "CP" + code, label[len(_CP_PREFIX):]
            elif label.startswith(_PA_PREFIX) and code:
                key, desc = "PA" + code, label[len(_PA_PREFIX):]
            else:
                continue
        row = {
            colonnes[i]: value
            for i, anchor_x0 in enumerate(anchors)
            for value in [_match_column_value(clusters, anchor_x0)]
            if value is not None
        }
        if not row:
            continue
        row["libelle"] = desc
        n, base_key = 2, key
        while key in lignes:
            key = f"{base_key}_{n}"
            n += 1
        lignes[key] = row

    if len(lignes) < min_rows:
        return None
    return {"colonnes": colonnes, "lignes": lignes}


def locate_and_extract_al_amanah_bilan(pdf_path, side, max_pages=15):
    """Parcourt les premières pages de `pdf_path` (documents à texte réel
    UNIQUEMENT — une page scannée est ignorée, voir docstring du module)
    à la recherche du Bilan Actif/Passif et en extrait la grille complète.
    Renvoie (numero_page_1_indexe, grille) ou (None, None)."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            if is_scanned_page(page):
                continue
            grid = extract_al_amanah_bilan_grid(page, side)
            if grid is not None:
                return i + 1, grid
    return None, None


def process_al_amanah_bilan(pdf_path):
    """Pipeline complète pour un document : localise + extrait l'Actif ET
    le Passif. Renvoie {"actif": {...}|None, "passif": {...}|None}, chacun
    au contrat {page, colonnes, lignes, validations} (voir
    bilan_full_extractor.py::process_bilan). Renvoie None si ni l'un ni
    l'autre n'a pu être extrait."""
    page_actif, grid_actif = locate_and_extract_al_amanah_bilan(pdf_path, "actif")
    page_passif, grid_passif = locate_and_extract_al_amanah_bilan(pdf_path, "passif")
    if grid_actif is None and grid_passif is None:
        return None

    validations = []

    def _add(rule_code, rule_desc, colonne, attendu, trouve):
        if attendu is None or trouve is None:
            return
        ecart = round(trouve - attendu, 2)
        validations.append({"regle_code": rule_code, "regle": rule_desc, "colonne": colonne,
                             "attendu": round(attendu, 2), "trouve": round(trouve, 2),
                             "ecart": ecart, "statut": "ok" if abs(ecart) <= 2 else "ecart"})

    def _build(page, grid, side):
        if not grid:
            return None
        lignes = {}
        for code, vals in grid["lignes"].items():
            libelle = vals.get("libelle") or code
            key = f"{code} — {libelle.capitalize()}" if libelle != code else code
            lignes[key] = {c: v for c, v in vals.items() if c != "libelle"}
        return {"page": page, "colonnes": grid["colonnes"], "lignes": lignes}

    _top_ac_re = re.compile(r"^AC\d$")
    _top_an_re = re.compile(r"^AN\d$")
    _top_cp_re = re.compile(r"^CP\d$")
    _top_pa_re = re.compile(r"^PA\d$")

    if grid_actif:
        total = grid_actif["lignes"].get("TOTAL")
        top = {c: v for c, v in grid_actif["lignes"].items() if _top_ac_re.match(c)}
        for col in grid_actif["colonnes"]:
            attendu = sum(v.get(col, 0) for v in top.values()) if top else None
            _add("al_amanah_actif_total", "Σ postes Actif = Total de l'actif", col,
                 attendu, total.get(col) if total else None)

    if grid_passif:
        top_an = {c: v for c, v in grid_passif["lignes"].items() if _top_an_re.match(c)}
        for col in grid_passif["colonnes"]:
            attendu = sum(v.get(col, 0) for v in top_an.values()) if top_an else None
            trouve = grid_passif["lignes"].get("TOTAL_AN", {}).get(col)
            _add("al_amanah_an_total", "Σ postes Actifs nets = Total des actifs nets", col, attendu, trouve)

        top_cp = {c: v for c, v in grid_passif["lignes"].items() if _top_cp_re.match(c)}
        for col in grid_passif["colonnes"]:
            attendu = sum(v.get(col, 0) for v in top_cp.values()) if top_cp else None
            trouve = grid_passif["lignes"].get("TOTAL_CP", {}).get(col)
            _add("al_amanah_cp_total", "Σ postes Capitaux propres = Total des capitaux propres", col, attendu, trouve)

        top_pa = {c: v for c, v in grid_passif["lignes"].items() if _top_pa_re.match(c)}
        for col in grid_passif["colonnes"]:
            attendu = sum(v.get(col, 0) for v in top_pa.values()) if top_pa else None
            trouve = grid_passif["lignes"].get("TOTAL", {}).get(col)
            _add("al_amanah_passif_total", "Σ postes Passif = Total du passif", col, attendu, trouve)

    if grid_actif and grid_passif:
        total_actif = grid_actif["lignes"].get("TOTAL")
        total_an = grid_passif["lignes"].get("TOTAL_AN")
        total_cp = grid_passif["lignes"].get("TOTAL_CP")
        total_pa = grid_passif["lignes"].get("TOTAL")
        if total_actif and (total_an or total_cp or total_pa):
            for col in grid_actif["colonnes"]:
                attendu = (total_an or {}).get(col, 0) + (total_cp or {}).get(col, 0) + (total_pa or {}).get(col, 0)
                _add("al_amanah_general_total",
                     "Total Actifs nets + Total Capitaux propres + Total Passif = Total actif",
                     col, attendu or None, total_actif.get(col))

    validations_actif = [v for v in validations if v["regle_code"] == "al_amanah_actif_total"]
    validations_passif = [v for v in validations if v["regle_code"] != "al_amanah_actif_total"]

    result_actif = _build(page_actif, grid_actif, "actif")
    result_passif = _build(page_passif, grid_passif, "passif")
    if result_actif:
        result_actif["validations"] = validations_actif
    if result_passif:
        result_passif["validations"] = validations_passif
    return {"actif": result_actif, "passif": result_passif}
