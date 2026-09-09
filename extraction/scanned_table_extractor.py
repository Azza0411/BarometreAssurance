"""Voie d'extraction "grille complète" par OCR, pour les documents CMF dont
la couche texte est inexploitable sur toute la zone de l'Annexe 13 —
contrairement au cas d'un seul bloc de pages scannées au milieu d'un
document par ailleurs natif (STAR 2025 / ASTREE 2023, traité ailleurs), ici
c'est le document SOURCE lui-même qui est dégradé de bout en bout :

  - scan image sans aucune couche texte : COTUNACE 2017/2019/2023,
    AMI 2016/2017/2019/2020/2023 (10 à 68 pages/document avec `page.chars`
    quasi nul et une image) ;
  - police embarquée cassée (glyphes corrects à l'écran mais aucune table
    ToUnicode → `page.extract_text()` ne renvoie que des `(cid:NNN)`) :
    COTUNACE 2015/2016 (par ailleurs en arabe — non couvertes par cette
    voie, qui est latine ; voir CAS_PARTICULIERS_FULL_TABLE.md) ;
  - couche texte présente mais corrompue à la source par un mauvais OCR
    ("Pt.imes acaui8es", "R6sultat tochnlauo") : COTUNACE 2022 — déjà
    documenté dans `api/services/quality.py::PROBLEMATIC_CODES["COTUNACE"]`.

Dans tous ces cas la page reste lisible à l'œil. La méthode :

  1. LOCALISATION (passe rapide) : rendu basse résolution de chaque page
     (PyMuPDF), OCR `image_to_string` (fra, --psm 6), score de titre flou
     (`_title_score`, tolérant au bruit — même principe que la localisation
     de `extraction/arabic_ocr_extractor.py`) ; on ne retient que les
     quelques pages les mieux notées.
  2. RECONSTRUCTION (pleine résolution) : rendu 340 dpi niveaux de gris,
     retrait du quadrillage par morphologie OpenCV (indispensable pour les
     tableaux encadrés type AMI — sans ça Tesseract lit les filets comme du
     texte et rend des lignes entières en charabia), puis `image_to_data`
     pour récupérer les BOÎTES de mots. Les lignes viennent du groupage
     natif de Tesseract (block/par/line) ; les colonnes sont déduites de la
     position X des cellules numériques (même principe que
     `full_table_extractor` : position des valeurs, pas des en-têtes). Un
     écart < 2,5 % de la largeur entre deux tokens numériques = même nombre ;
     au-delà = colonne distincte. Le format des nombres est délégué à
     `bilan_kpi_extractor._parse_number` (américain/tunisien).
  3. Pour les sociétés mono-branche dont l'unique colonne est imprimée deux
     fois (COTUNACE — "Crédit-Caution" × 2), `_reconcile_doubled_columns`
     fusionne les deux lectures en gardant la plus complète cellule par
     cellule (l'OCR tronque parfois les chiffres de tête d'une des deux).

La sortie est le contrat `{"colonnes": [...], "lignes": {...}}` — identique
à `extract_full_table_camelot` — de sorte que `locate_and_extract_full_table`
/ `process_annexe13` n'ont pas à changer. Cette voie n'est essayée qu'en
tout dernier recours (voie camelot normale ET repli "Notes" épuisés) et
uniquement si `document_needs_ocr` confirme qu'une page de la zone a bien
une couche texte inutilisable.

Limite connue : sur un scan très dégradé (COTUNACE 2023 : filets épais +
artefacts de reliure) ou un tableau multi-branche, quelques cellules
peuvent rester mal lues (chiffre de tête perdu, signe manqué). Les
identités comptables de `annexe13_pipeline.VALIDATION_RULES` (déjà
appliquées par `process_annexe13`) signalent alors ces lignes en `ecart` —
la grille reste livrée, jamais rejetée en silence. Voir
CAS_PARTICULIERS_FULL_TABLE.md pour l'état par société/année.
"""

import re

from extraction.bilan_kpi_extractor import _normalizer, _parse_number, NUMERIC_TOKEN_RE
from extraction.full_table_extractor import _FULL_TABLE_PAGE_TITLE_RE
from extraction.annexe13_kpi_extractor import NON_VIE_RE as _NON_VIE_RE, VIE_RE as _VIE_RE

RENDER_DPI = 340
_FRA_CONFIG = "-l fra --psm 6"
_LEFT_MARGIN_CROP = 0.035  # binder-hole / reliure artefacts sur le bord gauche du scan

# ── Détection "couche texte inexploitable" ─────────────────────────────────
_CID_RE = re.compile(r"\(cid:\d+\)")
_WORD_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
_MIN_USABLE_CHARS = 120
_MIN_WELLFORMED_RATIO = 0.55  # sous ce ratio de "mots" bien formés, le texte est du
# charabia (COTUNACE 2022 : "CoMp^GNm TUNlslENh'E po uR I,'AssuRAhcE")


def _text_is_garbled(text):
    tokens = text.split()
    if len(tokens) < 8:
        return False
    wellformed = sum(
        1 for t in tokens
        if NUMERIC_TOKEN_RE.match(t) or _WORD_RE.fullmatch(t.strip(".,:;()[]%/-'\""))
    )
    return wellformed / len(tokens) < _MIN_WELLFORMED_RATIO


def page_text_is_unusable(page):
    """Vrai si le corps de `page` n'a pas de texte réellement exploitable :
    trop peu de caractères, police cassée (`(cid:NNN)` en masse), ou texte
    présent mais illisible (mauvais OCR à la source)."""
    text = page.extract_text() or ""
    if len(page.chars) < _MIN_USABLE_CHARS:
        return True
    if len(_CID_RE.findall(text)) >= 5:
        return True
    return _text_is_garbled(text)


def document_needs_ocr(pdf_path, max_pages=120):
    """Vrai si au moins une page de la zone explorée a une couche texte
    inexploitable — condition d'entrée dans la voie OCR (qui n'est de toute
    façon atteinte que si la voie camelot normale a déjà échoué). Évite au
    moins de lancer l'OCR sur un document natif propre qui a échoué pour une
    raison sans rapport (vraie page absente). Le coût sur un document déjà en
    échec mais sans page scannée reste borné : `ocr_locate_and_extract`
    n'ira pas au bout si aucune page ne passe le score de titre."""
    import pdfplumber

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:max_pages]:
                if page_text_is_unusable(page):
                    return True
    except Exception:
        return False
    return False


# ── Rendu + redressement + suppression du quadrillage ─────────────────────
def _render_gray(pdf_path, page_index, dpi=RENDER_DPI):
    import fitz
    import numpy as np

    doc = fitz.open(pdf_path)
    try:
        pix = doc[page_index].get_pixmap(
            matrix=fitz.Matrix(dpi / 72, dpi / 72), colorspace=fitz.csGRAY
        )
        arr = np.frombuffer(pix.samples, dtype="uint8").reshape(pix.height, pix.width).copy()
    finally:
        doc.close()
    w = arr.shape[1]
    return arr[:, int(w * _LEFT_MARGIN_CROP):]  # retire la bande reliure


def _remove_rules(gray):
    """Retire les traits longs (horizontaux ET verticaux) du quadrillage :
    sans ça Tesseract confond les filets de cellule avec du texte et rend des
    lignes entières en charabia (constaté sur AMI 2017 — seule la lecture
    APRÈS retrait du quadrillage donne des chiffres exploitables). Sans effet
    notable sur un tableau non quadrillé."""
    import cv2
    import numpy as np

    bw = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, 10
    )
    h, w = bw.shape
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 40), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h // 40)))
    rules = cv2.bitwise_or(
        cv2.morphologyEx(bw, cv2.MORPH_OPEN, h_kernel),
        cv2.morphologyEx(bw, cv2.MORPH_OPEN, v_kernel),
    )
    rules = cv2.dilate(rules, np.ones((3, 3), "uint8"))
    return cv2.bitwise_not(cv2.bitwise_and(bw, cv2.bitwise_not(rules)))


def _prep(pdf_path, page_index, dpi=RENDER_DPI):
    from PIL import Image

    # Pas de deskew : sur ces scans le gauchissement est faible et
    # Tesseract (--psm 6) regroupe deja bien les lignes ; une rotation
    # bicubique floute les chiffres et degrade la lecture (verifie sur
    # COTUNACE 2019 : "8 810 252,618" lu "S 577..." apres rotation).
    return Image.fromarray(_remove_rules(_render_gray(pdf_path, page_index, dpi)))


def _ocr_text(pil_img, config=_FRA_CONFIG):
    import pytesseract

    return pytesseract.image_to_string(pil_img, config=config)


# == Reconstruction geometrique de la grille (boites de mots Tesseract) ==
# La reconstruction par simple texte de ligne echoue sur les tableaux
# multi-branches (AMI) : l'OCR groupe irregulierement les milliers
# ("2 786 704" lu "2786 704"), ce qui casse toute regex de nombre. On
# repart donc des BOITES de mots (image_to_data) : lignes = groupage natif
# de Tesseract (block/par/line, fiable ici -- meme groupage que
# image_to_string), colonnes = position X (ecart entre deux tokens
# numeriques < ~2,5 % de la largeur = meme nombre ; au-dela = colonne
# distincte).
_TOKEN_NUM_RE = re.compile(r"^[-\u2013\u2014=\u00ab\u00bb(]?\d[\d.,]*\)?$")
_HEADER_HINT_RE = re.compile(r"libell", re.IGNORECASE)
_BRANCH_HEADER_RE = re.compile(
    r"incendie|transport|automobile|risq|groupe|accept|aviation|maladie|"
    r"credit|caution|\btotal\b|travail|divers|marine|construction|transp|"
    r"individ|assistance|responsab|agricole|grele",
    re.IGNORECASE,
)
_LABEL_ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)
_MIN_VALUE_ROWS = 6  # sous ~6 lignes de valeurs reconstruites : faux positif /
# page trop degradee pour etre exploitee.


def _tok_is_num(t):
    return bool(_TOKEN_NUM_RE.match(t)) or t in ("-", "\u2013", "\u2014", "0")


def _ocr_rows(pil_img, config=_FRA_CONFIG):
    """[(y_center, [(x0, x1, text), ...]), ...] -- une entree par ligne
    detectee par Tesseract, tokens tries par X."""
    import pytesseract

    data = pytesseract.image_to_data(
        pil_img, config=config, output_type=pytesseract.Output.DICT
    )
    rows = {}
    for i in range(len(data["text"])):
        t = data["text"][i].strip()
        if not t:
            continue
        try:
            if float(data["conf"][i]) < 0:
                continue
        except (TypeError, ValueError):
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x, y, w, h = (data["left"][i], data["top"][i], data["width"][i], data["height"][i])
        rows.setdefault(key, []).append((x, x + w, y + h / 2, t))
    out = []
    for toks in rows.values():
        toks.sort()
        yc = sum(t[2] for t in toks) / len(toks)
        out.append((yc, [(a, b, txt) for a, b, _y, txt in toks]))
    out.sort(key=lambda r: r[0])
    return out


def _row_label_and_cells(tokens, page_width):
    """Separe le libelle (tokens de gauche) des cellules numeriques ; fusionne
    les tokens numeriques proches (ecart < 2,5 % de la largeur) en un nombre,
    un ecart plus grand ouvrant une colonne."""
    merge_gap = page_width * 0.025
    label_parts, cells = [], []
    cur_txt, cur_x0, cur_x1 = "", None, None
    seen_number = False
    for x0, x1, txt in tokens:
        if _tok_is_num(txt):
            seen_number = True
            if cur_txt and (x0 - cur_x1) <= merge_gap:
                cur_txt += "" if txt in ("-", "\u2013", "\u2014") else txt
                cur_x1 = x1
            else:
                if cur_txt:
                    cells.append((cur_x0, cur_x1, cur_txt))
                cur_txt, cur_x0, cur_x1 = txt, x0, x1
        elif not seen_number:
            label_parts.append(txt)
        # un mot non numerique APRES le 1er nombre = bruit OCR : ignore
    if cur_txt:
        cells.append((cur_x0, cur_x1, cur_txt))
    return " ".join(label_parts), cells


def _cell_value(text):
    sign = -1.0 if text[:1] in ("-", "\u2013", "\u2014", "=", "\u00ab", "\u00bb") else 1.0
    body = text.strip("-\u2013\u2014=\u00ab\u00bb()")
    val = _parse_number(body, negative=False)
    return None if val is None else sign * val


def _column_bands(rows_cells, page_width):
    """Bandes X des colonnes de valeurs, deduites des centres des cellules
    numeriques des lignes de donnees (>= 2 cellules)."""
    centers = []
    for cells in rows_cells:
        if len(cells) >= 2:
            centers.extend((a + b) / 2 for a, b, _ in cells)
    if not centers:
        for cells in rows_cells:
            centers.extend((a + b) / 2 for a, b, _ in cells)
    if not centers:
        return []
    centers.sort()
    gap = page_width * 0.045
    bands = [[centers[0]]]
    for c in centers[1:]:
        if c - bands[-1][-1] <= gap:
            bands[-1].append(c)
        else:
            bands.append([c])
    strong = [b for b in bands if len(b) >= 3]
    chosen = strong or bands
    return [sum(b) / len(b) for b in chosen]


def _header_names(rows, bands, page_width):
    """Libelles de colonne : sur la ligne d'en-tete (la plus riche en
    mots-branches, hors titre), chaque mot est rattache a la bande X la plus
    proche. Placeholder "(colonne k)" si une bande ne recoit aucun mot."""
    best_row, best_hits = None, 0
    for _yc, toks in rows[:14]:
        joined = _normalizer.clean(" ".join(t[2] for t in toks))
        if _FULL_TABLE_PAGE_TITLE_RE.search(joined):
            continue
        hits = len(_BRANCH_HEADER_RE.findall(joined)) + (2 if _HEADER_HINT_RE.search(joined) else 0)
        if hits > best_hits:
            best_row, best_hits = toks, hits
    names = ["(colonne %d)" % (i + 1) for i in range(len(bands))]
    if best_row and best_hits >= 2:
        buckets = [[] for _ in bands]
        for x0, x1, txt in best_row:
            if _HEADER_HINT_RE.fullmatch(txt) or _tok_is_num(txt):
                continue
            c = (x0 + x1) / 2
            k = min(range(len(bands)), key=lambda i: abs(bands[i] - c))
            if abs(bands[k] - c) <= page_width * 0.07:
                buckets[k].append(txt)
        for i, words in enumerate(buckets):
            if words:
                names[i] = _normalizer.clean(" ".join(words))
    seen, out = {}, []
    for nm in names:
        nm = nm or "(colonne)"
        n = seen.get(nm, 0) + 1
        seen[nm] = n
        out.append(nm if n == 1 else "%s (%d)" % (nm, n))
    return out


_ANNEXE13_HEAD_RE = re.compile(r"annexe\s*n?.?\s*13\b")
_ANNEXE_NUM_HEAD_RE = re.compile(r"annexe\s*n?\s*[°ºo]?\s*(\d{1,2})\b")


def _title_score(ocr_text):
    """Score de vraisemblance qu'une page OCR soit la page "Annexe 13 —
    Résultat technique Non-Vie" : titre (motif partagé
    `_FULL_TABLE_PAGE_TITLE_RE`), mention "Annexe N°13", "Non-Vie", présence
    conjointe de "primes acquises"/"résultat technique". Rejette franchement
    (score très négatif) une page qui se dit explicitement "Annexe N°X" avec
    X ≠ 13 : sur les documents AMI, l'"Annexe 3" ("État de résultat technique
    de l'assurance et/ou de la réassurance Non Vie", réconciliation agrégée)
    satisfait sinon le motif de titre et supplantait la vraie page Annexe 13
    par branche (même piège que la voie camelot, page 4)."""
    lines = ocr_text.splitlines()
    head = _normalizer.clean(" ".join(lines[:8]))
    full = _normalizer.clean(ocr_text)
    nums = _ANNEXE_NUM_HEAD_RE.findall(head)
    if nums and "13" not in nums:
        return -5
    score = 0
    if _FULL_TABLE_PAGE_TITLE_RE.search(head):
        score += 3
    elif _FULL_TABLE_PAGE_TITLE_RE.search(full):
        score += 1
    if _ANNEXE13_HEAD_RE.search(head):
        score += 3
    if _NON_VIE_RE.search(head):
        score += 1
    if "primes acquises" in full and "resultat technique" in full:
        score += 1
    if _VIE_RE.search(head) and not _NON_VIE_RE.search(head):
        score -= 2
    return score


def _page_grid(pdf_path, page_index, dpi=RENDER_DPI):
    rows = _ocr_rows(_prep(pdf_path, page_index, dpi))
    if len(rows) < 8:
        return None
    page_width = max((t[1] for _yc, toks in rows for t in toks), default=0)
    if not page_width:
        return None

    parsed = []  # (label, [(x0, x1, text), ...])
    for _yc, toks in rows:
        label, cells = _row_label_and_cells(toks, page_width)
        if cells and len(_LABEL_ALPHA_RE.findall(label)) >= 3:
            parsed.append((label, cells))
    if len(parsed) < _MIN_VALUE_ROWS:
        return None

    bands = _column_bands([c for _l, c in parsed], page_width)
    if not bands:
        return None
    n_cols = len(bands)
    col_names = _header_names(rows, bands, page_width)

    lignes = {}
    for label, cells in parsed:
        norm_label = _normalizer.clean(label)
        if not norm_label or norm_label.isdigit():
            continue
        row = {}
        for x0, x1, txt in cells:
            val = _cell_value(txt)
            if val is None:
                continue
            c = (x0 + x1) / 2
            k = min(range(n_cols), key=lambda i: abs(bands[i] - c))
            row.setdefault(col_names[k], val)
        if row:
            key, k = norm_label, 2
            while key in lignes:
                key = "%s (%d)" % (norm_label, k)
                k += 1
            lignes[key] = row
    if len(lignes) < _MIN_VALUE_ROWS:
        return None
    # Garde-fou anti-page-fantôme : une VRAIE page Annexe 13 a des montants en
    # dinars (≥ 5 chiffres). Une page mal choisie — reconciliation VIE (AMI
    # p4), sommaire — reconstruite depuis du bruit OCR ne produit que des
    # miettes ("1.0", "10.0", numéros de note). On exige donc assez de lignes
    # portant au moins une valeur de magnitude réaliste.
    big = sum(
        1 for row in lignes.values()
        if any(abs(v) >= 10000 for v in row.values())
    )
    if big < _MIN_VALUE_ROWS:
        return None
    col_names, lignes = _reconcile_doubled_columns(col_names, lignes)
    return {"colonnes": col_names, "lignes": lignes}


_DEDUP_SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")


def _reconcile_doubled_columns(col_names, lignes):
    """Certaines sociétés mono-branche (COTUNACE : uniquement "Crédit-Caution")
    impriment leur unique colonne de valeurs DEUX FOIS côte à côte. L'OCR lit
    donc chaque nombre deux fois — souvent l'une des deux tronquée (chiffres
    de tête perdus : "5 577 887,125" lu "577 887,125"). Quand les 2 colonnes
    portent le même libellé de base, on les fusionne en gardant, cellule par
    cellule, la lecture la plus complète (la plus grande en magnitude quand
    l'autre en est un suffixe numérique, sinon celle de la 1re colonne — la
    mieux lue en général). Sans effet si le tableau a de vraies colonnes
    distinctes."""
    if len(col_names) != 2:
        return col_names, lignes
    base = [_DEDUP_SUFFIX_RE.sub("", c) for c in col_names]
    if base[0] != base[1] or base[0].startswith("(colonne"):
        return col_names, lignes
    merged_name = base[0]
    merged = {}
    for label, row in lignes.items():
        a, b = row.get(col_names[0]), row.get(col_names[1])
        if a is None and b is None:
            continue
        if a is None:
            merged[label] = {merged_name: b}
        elif b is None:
            merged[label] = {merged_name: a}
        else:
            hi, lo = (a, b) if abs(a) >= abs(b) else (b, a)
            digits_hi = str(int(abs(hi)))
            digits_lo = str(int(abs(lo)))
            if digits_hi.endswith(digits_lo) or abs(lo) == 0 or abs(hi) / max(abs(lo), 1) > 50:
                merged[label] = {merged_name: hi}
            else:
                merged[label] = {merged_name: a}  # égalité de fiabilité → 1re colonne
    return [merged_name], merged


def ocr_locate_and_extract(pdf_path, kpi_patterns, sanity_check, max_pages=120,
                            min_sanity_matches=2, **_unused):
    """Localise la page "Annexe 13 — Résultat technique Non-Vie" par OCR
    (titre flou), reconstruit la grille ligne par ligne, et renvoie
    `(numero_page_1_indexe, grille)` au même contrat que
    `extract_full_table_camelot` — ou `(None, None)`.

    `sanity_check(lignes) -> bool` : le MÊME `_sanity_ok` que la voie normale
    (≥ `min_sanity_matches` postes comptables reconnus), passé par l'appelant
    pour ne pas dupliquer le vocabulaire."""
    import fitz
    from PIL import Image

    doc = fitz.open(pdf_path)
    n_pages = min(len(doc), max_pages)
    doc.close()

    # Passe de localisation RAPIDE : rendu basse résolution, sans retrait de
    # quadrillage (le titre est du gros texte, lisible même dégradé) —
    # l'OCR pleine résolution est réservé aux quelques pages candidates.
    scored = []
    for idx in range(n_pages):
        try:
            img = Image.fromarray(_render_gray(pdf_path, idx, dpi=150))
            text = _ocr_text(img)
        except Exception:
            continue
        s = _title_score(text)
        if s >= 3:
            head = _normalizer.clean(" ".join(text.splitlines()[:8]))
            scored.append((s, idx, bool(_ANNEXE13_HEAD_RE.search(head))))
    scored.sort(reverse=True)

    best = None
    for _score, idx, head_annexe13 in scored[:6]:  # ≤ 6 pages en extraction complète
        try:
            grid = _page_grid(pdf_path, idx)
        except Exception:
            continue
        if not grid or len(grid["lignes"]) < min_sanity_matches:
            continue
        if not sanity_check(grid["lignes"]):
            continue
        # Une grille aux colonnes "Opérations brutes / Cessions / Opérations
        # nettes" est un tableau de RÉCONCILIATION. C'est une forme légitime
        # de l'Annexe 13 pour quelques sociétés — mais seulement si la page
        # est bien titrée "Annexe N°13". Sinon (AMI : "Annexe 3 — État de
        # résultat technique … Non Vie", agrégée) c'est la mauvaise page.
        cols_norm = " ".join(grid["colonnes"])
        is_raccordement = "operations" in cols_norm or "cessions" in cols_norm
        if is_raccordement and not head_annexe13:
            continue
        n_named = sum(1 for c in grid["colonnes"] if not c.startswith("(colonne"))
        rank = (head_annexe13, n_named, len(grid["lignes"]))
        if best is None or rank > best[2]:
            best = (idx, grid, rank)
    if best is None:
        return None, None
    return best[0] + 1, best[1]
