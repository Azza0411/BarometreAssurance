"""Extraction PLEINE GRILLE des Annexes 3/4 Takaful "État de Surplus ou
Déficit du fonds Takaful Familial/Général" — l'équivalent Takaful
d'Annexe 12/13 (résultat technique) pour les assureurs conventionnels :
même finalité (grille complète, pas seulement les quelques KPI ciblés de
extraction/takaful_kpi_extractor.py::extract_fonds_participants_kpis),
stockée dans `tableau_cellules` sous 'takaful_surplus_familial'/
'takaful_surplus_general'.

Chaque ligne porte un code réglementaire — PRF/CHF (Fonds Familial,
Annexe 3) ou PRG/CHG (Fonds Général, Annexe 4), même principe que AC/PA/CP
pour le Bilan mais SANS structure de sections imbriquées (pas de
"sous-total AC1" qui regroupe AC11/AC12...) : chaque code est une ligne
indépendante. Le code partagé "CH8" (Impôt sur le résultat) est commun
aux deux fonds, sans suffixe numérique — traité à part de
`_ROW_CODE_RE`. Les seuls sous-totaux sont des lignes "Sous total N"
totalement BARE (sans code), numérotées dans l'ordre du document plutôt
que rattachées à un code de section — capturées comme leurs propres
lignes (clé "SOUS_TOTAL_N"). Le numéro qui suit immédiatement "Sous
total" est un INDEX DE SECTION, pas une valeur : s'il n'est pas retiré
avant le calcul des clusters numériques, il se glisse comme 1re valeur et
décale toutes les colonnes réelles d'une position (constaté sur
AT_TAKAFULIA 2023 lors du premier jet de cet extracteur).

4 colonnes par ligne : Opérations brutes / Cessions et/ou rétrocessions /
Opération nettes (exercice courant) / Opération nettes (exercice
précédent) — en-tête étalée sur plusieurs lignes physiques (comme le
Bilan Combiné Takaful, voir bilan_full_extractor.py
::_TAKAFUL_HEADER_HINT_RE), donc le nombre de colonnes est déduit du
nombre de valeurs sur la ligne de DONNÉES la plus complète plutôt que du
texte d'en-tête. De nombreuses lignes n'ont PAS toutes leurs colonnes
peuplées, et une colonne vide n'a souvent AUCUN token imprimé (pas même
un tiret) : la seule ancre fiable est que "Opération nettes (exercice
précédent)" est TOUJOURS la DERNIÈRE valeur présente et "Opération
nettes (exercice courant)" l'AVANT-DERNIÈRE, quel que soit le nombre de
colonnes effectivement présentes avant elles — même convention que
`takaful_kpi_extractor.py::_col_nettes_courantes`, réutilisée ici pour
TOUTES les colonnes (voir `_assign_columns`) plutôt qu'une position
strictement ordinale gauche→droite qui casserait dès qu'une colonne du
milieu (typiquement "Cessions") est absente.

La ligne finale "Surplus ou déficit de l'assurance Takaful et/ou
Rétakaful {Familial|Général}" (et sa variante "...après modification
comptable") s'étale elle aussi sur 2-3 lignes physiques, et les valeurs
peuvent atterrir sur N'IMPORTE LAQUELLE de ces lignes selon le document
(sur la même ligne que "Surplus..." pour AT_TAKAFULIA, mais sur la ligne
de continuation "et/ou Rétakaful ... après modification" pour la 2e
variante) — un simple `regex.match` sur le texte d'une seule ligne
clusterisée la rate systématiquement. Détection par une regex "ancre"
plus lâche (juste le début de la phrase) suivie d'un balayage sur les 2-3
lignes suivantes pour le texte complet (distinguer la variante) ET les
valeurs numériques — même principe que
`takaful_kpi_extractor.py::_find_row_on_page` (déjà conçu pour ce
problème de libellé étalé sur plusieurs lignes)."""

import re

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters, _normalizer,
    _words_with_bracket_negatives_resolved, NUMERIC_TOKEN_RE,
    _OcrFallbackPage,
)

_ROW_CODE_RE = re.compile(r"^(PRF|CHF|PRG|CHG)\s?(\d+)(?:,\d+)*", re.IGNORECASE)
_CH8_RE = re.compile(r"^ch8\b")
_SOUS_TOTAL_RE = re.compile(r"^sous\s*total\b")
_SURPLUS_ANCHOR_RE = re.compile(r"^surplus\s+ou\s+deficit\s+de\s+l.?assurance\s+takaful\b")
_SURPLUS_APRES_RE = re.compile(r"apres\s+modification\s+comptable")
_SECTION_NUM_RE = re.compile(r"^\d{1,2}$")
_DASH_PLACEHOLDER_RE = re.compile(r"^[-‐‑–—]+$")
_SIGN_TOKEN_RE = re.compile(r"^[+\-‐‑–—]$")
_NOTE_NUM_RE = re.compile(r"^\d{1,2}$")

_COLUMN_NAMES = ["Opérations brutes", "Cessions et/ou rétrocessions", "Opérations nettes", "Opérations nettes (N-1)"]

_TITLE_RE = {
    "familial": re.compile(r"surplus ou deficit du fonds takaful familial"),
    "general": re.compile(r"surplus ou deficit du fonds takaful general"),
}

_MIN_ROWS = 5
_SURPLUS_SCAN_WINDOW = 3


def _is_target_page(page, side, lines_checked=6):
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    return bool(_TITLE_RE[side].search(normalized))


def _strip_note_column(line):
    """Retire le couple (signe +/‐ isolé, numéro de note 1-2 chiffres)
    imprimé juste après le libellé sur les lignes de section — colonne
    "Note" (renvoi vers l'annexe correspondante), PAS une valeur — avant
    tout le reste du traitement. Découvert le 2026-09-17 sur
    ZITOUNA_TAKAFUL/AT_TAKAFULIA : "PRF1 Primes + 15 34 896 720 1 774 304
    33 122 416 28 952 957" (le "15" est le numéro de note) et "CHF3 Frais
    d'exploitation ‐ 18 3 219 836 ...". Fait AVANT `_resolved_words` (donc
    avant que le "‐" isolé ne soit lu comme un placeholder "néant" et
    converti en un faux "0") : sinon ce signe de section, distinct d'un
    vrai tiret "néant", introduisait sa propre valeur fantôme en plus du
    numéro de note, cassant `_assign_columns` de 2 colonnes à la fois
    (constaté ZITOUNA/CHF3). Seul le signe SUIVI IMMÉDIATEMENT d'un nombre
    à 1-2 chiffres LUI-MÊME suivi d'autres valeurs (donc jamais le dernier
    token de la ligne) correspond à ce gabarit — un vrai "‐" isolé de fin
    de ligne (cellule vide) n'est jamais touché."""
    for i in range(len(line) - 1):
        if _SIGN_TOKEN_RE.match(line[i]["text"]) and _NOTE_NUM_RE.match(line[i + 1]["text"]):
            return line[:i] + line[i + 2:]
    return line


def _resolved_words(line):
    """Mots de la ligne, négatifs entre parenthèses résolus, et tout
    placeholder tiret ("néant") converti en "0" explicite — sinon un "-"
    isolé disparaît silencieusement de `_extract_numeric_clusters` au lieu
    de compter comme un zéro à sa position, décalant les colonnes
    suivantes."""
    resolved = _words_with_bracket_negatives_resolved(_strip_note_column(line))
    return [{**w, "text": "0"} if _DASH_PLACEHOLDER_RE.match(w["text"]) else w for w in resolved]


def _strip_leading_section_number(resolved):
    """Pour une ligne "Sous total N ...", retire le token "N" (numéro de
    section, PAS une valeur) de la liste de mots avant tout calcul de
    clusters numériques. Renvoie (resolved_sans_le_numero, numero_ou_None).

    Détecté sur les 3 premiers mots BRUTS de `resolved` (pas sur un texte
    déjà nettoyé des jetons numériques, qui exclurait justement "N" et
    empêcherait toute détection) — bug constaté le 2026-09-17 sur
    AT_TAKAFULIA : "Sous total 3 V‐3 ‐1 690 029 ..." affichait le "3" à la
    place de la vraie valeur "Opérations brutes" (‐1 690 029), la
    reconnaissance d'origine (basée sur un texte déjà sans chiffres) ne se
    déclenchant jamais."""
    cleaned = [_normalizer.clean(w["text"]) for w in resolved]
    if len(cleaned) < 3 or cleaned[0] != "sous" or cleaned[1] != "total" or not _SECTION_NUM_RE.match(cleaned[2]):
        return resolved, None
    return resolved[:2] + resolved[3:], cleaned[2]


def _column_count(lines):
    """Nombre de colonnes réellement présentes : le plus grand nombre de
    clusters numériques trouvé sur une ligne de DONNÉES (code PRF/CHF/PRG/
    CHG reconnu en tête)."""
    max_cols = 0
    for line in lines:
        first = _normalizer.clean(line[0]["text"]) if line else ""
        if not line or not _ROW_CODE_RE.match(first):
            continue
        resolved = _resolved_words(line)
        max_cols = max(max_cols, len(_extract_numeric_clusters(resolved)))
    return min(max_cols, len(_COLUMN_NAMES))


def _assign_columns(clusters, n_cols):
    """Op.nettes (N-1) = TOUJOURS la dernière valeur présente, Op.nettes
    (courant) = l'avant-dernière, Op.brutes puis Cessions comblées dans
    l'ordre depuis le début avec ce qui reste — voir le docstring du
    module pour pourquoi une correspondance ordinale simple casse dès
    qu'une colonne du milieu est absente sans même un tiret imprimé."""
    result = {}
    n = len(clusters)
    if n == 0:
        return result
    if n == 1:
        result[0] = clusters[0][0]
        return result
    result[n_cols - 1] = clusters[-1][0]
    result[n_cols - 2] = clusters[-2][0]
    for i, (v, _x0) in enumerate(clusters[:-2]):
        if i < n_cols - 2:
            result[i] = v
    return result


def extract_takaful_surplus_grid(page, side, min_rows=_MIN_ROWS):
    """Reconstruit la grille complète de l'Annexe 3 (side='familial') ou 4
    (side='general') visible sur `page`. Renvoie {"colonnes": [...],
    "lignes": {code_ou_libelle: {colonne: valeur}}}, ou None si trop peu
    de lignes reconnues."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)
    n_cols = _column_count(lines)
    if n_cols < 2:
        return None
    colonnes = _COLUMN_NAMES[:n_cols]

    # Pré-calcule texte normalisé + clusters numériques de chaque ligne
    # (le numéro de section d'un "Sous total N" est retiré ICI, avant tout
    # calcul de cluster, pour ne jamais polluer les valeurs).
    prepared = []
    for line in lines:
        resolved = _resolved_words(line)
        resolved, sous_total_num = _strip_leading_section_number(resolved)
        label_words0 = [w for w in resolved if not NUMERIC_TOKEN_RE.match(w["text"])]
        text_norm = _normalizer.clean(" ".join(w["text"] for w in label_words0))
        label_words = label_words0
        clusters = _extract_numeric_clusters(resolved)
        # Colonne "Notes" (renvoi vers l'annexe) : quand le signe +/‐ qui
        # la précède habituellement a disparu à la lecture (glyphe non
        # natif, constaté CHF1/CHF4/CH8 sur ZITOUNA_TAKAFUL — mêmes lignes
        # que celles avec signe, mais sans lui), `_strip_note_column`
        # (basé sur ce signe) ne peut pas la retirer en amont : repli
        # générique ici — un unique jeton isolé (< 100, jamais fusionné
        # avec les vraies valeurs à cause de l'écart de position) EN TROP
        # par rapport aux colonnes attendues ne peut être qu'elle.
        if len(clusters) == n_cols + 1 and 0 <= clusters[0][0] < 100:
            clusters = clusters[1:]
        prepared.append({
            "text_norm": text_norm,
            "label": " ".join(w["text"] for w in label_words),
            "clusters": clusters,
            "sous_total_num": sous_total_num,
        })

    lignes, label_by_key = {}, {}
    sous_total_seq = 0
    consumed_until = -1
    for i, p in enumerate(prepared):
        if i <= consumed_until:
            continue
        text_norm = p["text_norm"]

        m = _ROW_CODE_RE.match(text_norm)
        ch8_m = _CH8_RE.match(text_norm)
        sous_total_m = _SOUS_TOTAL_RE.match(text_norm)
        surplus_m = _SURPLUS_ANCHOR_RE.match(text_norm)

        if m:
            code = f"{m.group(1).upper()}{m.group(2)}"
            rest = text_norm[m.end():].strip()
            if rest and code not in label_by_key:
                label_by_key[code] = rest
            if p["clusters"]:
                lignes[code] = _assign_columns(p["clusters"], n_cols)
        elif ch8_m:
            rest = text_norm[ch8_m.end():].strip()
            if rest and "CH8" not in label_by_key:
                label_by_key["CH8"] = rest
            if p["clusters"]:
                lignes["CH8"] = _assign_columns(p["clusters"], n_cols)
        elif sous_total_m:
            sous_total_seq += 1
            num = p["sous_total_num"] or str(sous_total_seq)
            key = f"SOUS_TOTAL_{num}"
            label_by_key[key] = text_norm
            if p["clusters"]:
                lignes[key] = _assign_columns(p["clusters"], n_cols)
        elif surplus_m:
            # Le libellé s'étale sur 2-3 lignes physiques et les valeurs
            # peuvent être sur n'importe laquelle : on regarde une fenêtre
            # de quelques lignes pour a) distinguer la variante "après
            # modification comptable" b) trouver les valeurs.
            window = prepared[i:i + _SURPLUS_SCAN_WINDOW]
            window_text = " ".join(w["text_norm"] for w in window)
            key = "SURPLUS_APRES_MODIF" if _SURPLUS_APRES_RE.search(window_text) else "SURPLUS"
            label_by_key[key] = window_text
            for j, wp in enumerate(window):
                if wp["clusters"]:
                    lignes[key] = _assign_columns(wp["clusters"], n_cols)
                    consumed_until = max(consumed_until, i + j)
                    break
            consumed_until = max(consumed_until, i + len(window) - 1)
        elif text_norm.startswith("ch9") or text_norm.startswith("pr5"):
            # "CH9/PR5 Effet des modifications comptables" — préfixe
            # propre, jamais confondu avec une autre ligne.
            label_by_key["CH9_PR5"] = text_norm
            if p["clusters"]:
                lignes["CH9_PR5"] = _assign_columns(p["clusters"], n_cols)

    if len(lignes) < min_rows:
        return None
    lignes_out = {
        key: {"libelle": label_by_key.get(key, key), **{
            colonnes[i]: v for i, v in vals.items() if i < n_cols
        }}
        for key, vals in lignes.items()
    }
    return {"colonnes": colonnes, "lignes": lignes_out}


def locate_and_extract_takaful_surplus(pdf_path, side, max_pages=20):
    """Parcourt les premières pages de `pdf_path` à la recherche de
    l'Annexe 3 (side='familial') ou 4 (side='general') et en extrait la
    grille complète. Enveloppe chaque page avec `_OcrFallbackPage` (repli
    OCR si le texte natif est vide — même mécanisme que Bilan). Renvoie
    (numero_page_1_indexe, grille) ou (None, None)."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            ocr_page = _OcrFallbackPage(page)
            if not _is_target_page(ocr_page, side):
                continue
            grid = extract_takaful_surplus_grid(ocr_page, side)
            if grid is not None:
                return i + 1, grid
    return None, None


def _surplus_validations(grid):
    """Identité comptable générique, valable pour Familial ET Général (voir
    docstring du module) : Σ des "Sous total N" + CH8 (impôt) = SURPLUS, et
    SURPLUS + CH9/PR5 (effet des modifications comptables) = SURPLUS après
    modification comptable — vérifiée colonne par colonne."""
    results = []
    lignes = grid["lignes"]
    sous_totaux = {k: v for k, v in lignes.items() if k.startswith("SOUS_TOTAL_")}
    surplus = lignes.get("SURPLUS")
    surplus_modif = lignes.get("SURPLUS_APRES_MODIF")
    ch8 = lignes.get("CH8", {})
    ch9 = lignes.get("CH9_PR5", {})

    def _add(rule_code, rule_desc, colonne, attendu, trouve):
        if attendu is None or trouve is None:
            return
        ecart = round(trouve - attendu, 2)
        results.append({"regle_code": rule_code, "regle": rule_desc, "colonne": colonne,
                         "attendu": round(attendu, 2), "trouve": round(trouve, 2),
                         "ecart": ecart, "statut": "ok" if abs(ecart) <= 2 else "ecart"})

    if surplus and sous_totaux:
        for col in grid["colonnes"]:
            attendu = sum(v.get(col, 0) for v in sous_totaux.values()) + ch8.get(col, 0)
            _add("takaful_surplus_sous_totaux", "Σ Sous-totaux + Impôt (CH8) = Surplus/Déficit",
                 col, attendu, surplus.get(col))

    if surplus and surplus_modif:
        for col in grid["colonnes"]:
            attendu = surplus.get(col, 0) + ch9.get(col, 0)
            _add("takaful_surplus_modif_comptable", "Surplus + Effet modifications comptables = Surplus après modification",
                 col, attendu, surplus_modif.get(col))

    return results


def process_takaful_surplus(pdf_path, side):
    """Pipeline complète pour un côté (side='familial'|'general') : localise
    + extrait, renvoie {"page", "colonnes", "lignes", "validations"} au
    même contrat que `bilan_full_extractor.py::process_bilan` (clé de
    ligne = "CODE — Libellé" quand un libellé a pu être capturé, sinon le
    code seul), ou None si introuvable."""
    page, grid = locate_and_extract_takaful_surplus(pdf_path, side)
    if grid is None:
        return None
    validations = _surplus_validations(grid)
    lignes = {}
    for code, vals in grid["lignes"].items():
        libelle = vals.get("libelle") or code
        key = f"{code} — {libelle.capitalize()}" if libelle != code else code
        lignes[key] = {c: v for c, v in vals.items() if c != "libelle"}
    return {"page": page, "colonnes": grid["colonnes"], "lignes": lignes, "validations": validations}
