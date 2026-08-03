"""
Localise une cellule (ligne × colonne) dans un tableau PDF et retourne
ses coordonnées en système PDF (origine bas-gauche, points).

Stratégie (indépendante de l'indexation plate des cellules) :
  1. Extraire tous les mots de la page (extract_words).
  2. Regrouper les mots par ligne Y → trouver la ligne contenant `ligne`.
  3. Trouver le mot d'en-tête le plus à droite contenant `colonne`.
  4. Croiser le centre Y de la ligne cible et le centre X de la colonne
     avec les bounding-boxes des cellules détectées par pdfplumber.

Cette approche évite toute hypothèse sur l'ordre ou le nombre de cellules
dans tbl.cells, ce qui était la cause des erreurs précédentes.
"""

import os
import re
import unicodedata
import pdfplumber

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cmf"
)

_cache: dict = {}
_ROW_TOL = 4   # points — tolérance pour regrouper des mots sur la même ligne


def _norm(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(text))
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_str.lower()).strip()


def _word_rows(words: list) -> list[tuple]:
    """
    Regroupe les mots par ligne (position Y similaire).
    Retourne [(top_y, bottom_y, [words]), ...] trié par top_y.
    """
    groups: list[list] = []          # [[top_y, bottom_y, [words]]]
    for w in sorted(words, key=lambda x: x["top"]):
        placed = False
        for g in groups:
            if abs(w["top"] - g[0]) <= _ROW_TOL:
                g[2].append(w)
                g[1] = max(g[1], w["bottom"])
                placed = True
                break
        if not placed:
            groups.append([w["top"], w["bottom"], [w]])
    return [(g[0], g[1], g[2]) for g in groups]


def _row_has_digit(words) -> bool:
    return any(any(ch.isdigit() for ch in w["text"]) for w in words)


def _pick_shortest(candidates):
    """candidates: [(length, top_y, bot_y, has_digit), ...].

    Parmi les lignes correspondant au libellé, préfère celles qui portent au
    moins un chiffre (une vraie ligne de données) avant d'appliquer la règle
    "la plus courte gagne" : sans ce tri préalable, un titre de section sans
    montant (ex: une ligne "PRIMES ACQUISES" en gras, sans chiffres, isolée
    du tableau de données) est plus court que la vraie ligne de données
    ("Primes acquises 14 579 683") et gagnait donc à tort — on surlignait
    alors le libellé au lieu de la valeur. Repli sur toutes les candidates
    si aucune n'a de chiffre (colonne textuelle légitime, ex: Siège social)."""
    with_digit = [c for c in candidates if c[3]]
    pool = with_digit if with_digit else candidates
    _, top_y, bot_y, _ = min(pool, key=lambda c: c[0])
    return top_y, bot_y


def _find_row_y(rows: list[tuple], ligne_norm: str):
    """
    Cherche la ligne contenant `ligne_norm`.
    Accepte une correspondance partielle (sous-chaîne).
    Retourne (top_y, bottom_y) ou None.

    Un libellé court (ex: "Créances") apparaît souvent aussi comme fragment
    d'une phrase plus longue ailleurs sur la page (ex: "Créances pour espèces
    déposées auprès des entreprises cédantes", un sous-élément d'une AUTRE
    section) : prendre la PREMIÈRE ligne trouvée dans l'ordre de lecture
    peut donc pointer sur la mauvaise ligne. On préfère la ligne dont le
    texte total est le plus court parmi toutes les correspondances portant
    un chiffre (voir _pick_shortest) — un vrai titre de section/ligne de
    tableau est presque toujours juste son libellé (+ code), alors qu'un
    fragment noyé dans une phrase est plus long (même heuristique que
    _section_starts_for_page côté extraction)."""
    # Passe 1 : correspondance exacte en sous-chaîne (ligne entière concaténée)
    candidates = []
    for top_y, bot_y, words in rows:
        full = _norm(" ".join(w["text"] for w in words))
        if ligne_norm in full:
            candidates.append((len(full), top_y, bot_y, _row_has_digit(words)))
    if candidates:
        return _pick_shortest(candidates)

    # Passe 2 : correspondance partielle sur chaque mot individuellement
    # (pour les libellés coupés sur plusieurs mots)
    tokens = ligne_norm.split()
    candidates = []
    for top_y, bot_y, words in rows:
        word_norms = [_norm(w["text"]) for w in words]
        # Vérifier que tous les tokens sont présents quelque part dans la ligne
        if all(any(t in wn for wn in word_norms) for t in tokens):
            row_len = sum(len(wn) for wn in word_norms)
            candidates.append((row_len, top_y, bot_y, _row_has_digit(words)))
    if candidates:
        return _pick_shortest(candidates)

    return None


def _in_bbox(word, bbox, margin=2) -> bool:
    bx0, btop, bx1, bbottom = bbox
    return (bx0 - margin <= word["x0"] and word["x1"] <= bx1 + margin
            and btop - margin <= word["top"] <= bbottom + margin)


def _find_col_x(rows: list[tuple], colonne_norm: str, above_y: float, table_bbox=None):
    """
    Cherche le mot d'en-tête le plus à DROITE contenant `colonne_norm`
    parmi les lignes situées AU-DESSUS de `above_y` (= les en-têtes).
    Si rien trouvé au-dessus, cherche dans toute la page.
    Retourne le centre X du mot trouvé, ou None.

    Si `table_bbox` (x0, top, x1, bottom) est fourni, ne considère que les
    mots situés DANS cette table : sans cette contrainte, un en-tête d'un
    AUTRE tableau empilé plus haut sur la même page (ex: Annexe 12/13 —
    sous-tableaux Vie individuelle / Vie collective / Total) peut être capté
    à tort et décaler la colonne trouvée. Repli sans contrainte si rien
    n'est trouvé à l'intérieur de la table (mieux vaut un résultat
    potentiellement décalé qu'aucun résultat).
    """
    best_x = None
    best_x0 = -1

    for source_rows in (
        [r for r in rows if r[0] < above_y],   # en-têtes au-dessus
        rows,                                    # toute la page si vide
    ):
        for _, _, words in source_rows:
            for w in words:
                if colonne_norm in _norm(w["text"]) and (table_bbox is None or _in_bbox(w, table_bbox)):
                    mid_x = (w["x0"] + w["x1"]) / 2
                    if w["x0"] > best_x0:
                        best_x0 = w["x0"]
                        best_x = mid_x
        if best_x is not None:
            break                                # trouvé dans les en-têtes

    if best_x is None and table_bbox is not None:
        return _find_col_x(rows, colonne_norm, above_y, table_bbox=None)

    return best_x


def _cell_at(all_cells: list, y_mid: float, x_mid: float):
    """
    Retourne la cellule (x0, top, x1, bottom) contenant le point (x_mid, y_mid).
    Si aucune correspondance exacte, retourne la cellule de la bonne ligne
    dont le centre X est le plus proche de x_mid.
    """
    # Correspondance exacte
    for (cx0, ctop, cx1, cbottom) in all_cells:
        if ctop <= y_mid <= cbottom and cx0 <= x_mid <= cx1:
            return (cx0, ctop, cx1, cbottom)

    # Fallback : même ligne (Y), X le plus proche
    row_cells = [c for c in all_cells if c[1] <= y_mid <= c[3]]
    if row_cells:
        return min(row_cells, key=lambda c: abs((c[0] + c[2]) / 2 - x_mid))

    return None


def get_cell_coords(code: str, annee: int, page_num: int,
                    ligne: str, colonne: str) -> tuple[dict | None, str | None]:
    """
    Retourne les coordonnées PDF de la cellule (ligne, colonne) sur la page donnée.

    Coordonnées (système PDF, origine coin bas-gauche) :
        { x0, y0, x1, y1, page_width, page_height }

    Renvoie (coords, None) si trouvé, (None, raison) sinon — la raison
    ("pdf_manquant"/"page_invalide"/"page_vide"/"ligne_introuvable"/
    "colonne_introuvable"/"erreur") permet à l'appelant (voir
    api/routes/qualite.py, frontend/src/pages/KpiDetail.jsx) d'afficher un
    message précis plutôt qu'un surlignage manquant sans explication."""
    cache_key = (code.upper(), int(annee), int(page_num), _norm(ligne), _norm(colonne))
    if cache_key in _cache:
        return _cache[cache_key]

    path = os.path.join(DATA_DIR, code.upper(), f"{code.upper()}_{annee}.pdf")
    if not os.path.isfile(path):
        return None, "pdf_manquant"

    ligne_norm   = _norm(ligne)
    colonne_norm = _norm(colonne)

    result = None
    reason = "erreur"
    try:
        with pdfplumber.open(path) as pdf:
            if page_num < 1 or page_num > len(pdf.pages):
                _cache[cache_key] = (None, "page_invalide")
                return _cache[cache_key]
            page   = pdf.pages[page_num - 1]
            page_w = float(page.width)
            page_h = float(page.height)

            # ── 1. Toutes les cellules PDF de la page ────────────────────────
            tables = page.find_tables()
            all_cells = []
            for tbl in tables:
                for cell in tbl.cells:
                    if cell is not None:
                        all_cells.append(cell)

            # ── 2. Mots de la page groupés par ligne ─────────────────────────
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                _cache[cache_key] = (None, "page_vide")
                return _cache[cache_key]
            rows = _word_rows(words)

            # ── 3. Trouver la ligne cible (Y) ────────────────────────────────
            row_y = _find_row_y(rows, ligne_norm)
            if row_y is None:
                _cache[cache_key] = (None, "ligne_introuvable")
                return _cache[cache_key]
            top_y, bot_y = row_y
            y_mid = (top_y + bot_y) / 2

            # Table contenant la ligne cible, pour restreindre la recherche
            # d'en-tête (étape 4) à cette même table plutôt qu'à toute la page.
            table_bbox = None
            for tbl in tables:
                tx0, ttop, tx1, tbottom = tbl.bbox
                if ttop - 2 <= y_mid <= tbottom + 2:
                    table_bbox = (tx0, ttop, tx1, tbottom)
                    break

            # ── 4. Trouver la colonne (X) ─────────────────────────────────────
            x_mid = _find_col_x(rows, colonne_norm, above_y=top_y, table_bbox=table_bbox)
            if x_mid is None:
                _cache[cache_key] = (None, "colonne_introuvable")
                return _cache[cache_key]

            # ── 5. Croiser avec les cellules ──────────────────────────────────
            if all_cells:
                cell = _cell_at(all_cells, y_mid, x_mid)
            else:
                cell = None

            if cell:
                cx0, ctop, cx1, cbottom = cell
                # Certains tableaux (ex: sections du Bilan sans quadrillage
                # interne) sont détectés par pdfplumber comme UNE cellule
                # fusionnée couvrant plusieurs lignes visuelles. Si la
                # cellule est nettement plus haute que la ligne de texte
                # réellement trouvée, on restreint le surlignage à cette
                # ligne (avec une petite marge) plutôt qu'à toute la cellule.
                row_height = bot_y - top_y
                if (cbottom - ctop) > row_height * 1.8:
                    ctop = max(ctop, top_y - 2)
                    cbottom = min(cbottom, bot_y + 2)
                result = {
                    "x0": float(cx0),
                    "y0": float(page_h - cbottom),
                    "y1": float(page_h - ctop),
                    "x1": float(cx1),
                    "page_width":  page_w,
                    "page_height": page_h,
                }
                reason = None
            else:
                # Aucune cellule tableau — retourner la bbox du texte de la ligne
                # à l'X de la colonne (meilleure approximation possible)
                line_words = [
                    w for w in words
                    if top_y - _ROW_TOL <= w["top"] <= bot_y + _ROW_TOL
                ]
                if line_words:
                    result = {
                        "x0": float(x_mid - 20),
                        "y0": float(page_h - bot_y),
                        "y1": float(page_h - top_y),
                        "x1": float(x_mid + 20),
                        "page_width":  page_w,
                        "page_height": page_h,
                    }
                    reason = None
                else:
                    reason = "cellule_introuvable"

    except Exception as exc:
        # Log pour diagnostic
        import sys
        print(f"[pdf_cell_coords] ERROR {code} {annee} p{page_num}: {exc}", file=sys.stderr)
        reason = "erreur"

    _cache[cache_key] = (result, None if result else reason)
    return _cache[cache_key]
