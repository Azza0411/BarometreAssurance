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
import sys
import unicodedata
import pdfplumber
from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from extraction.bilan_kpi_extractor import _OcrFallbackPage

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cmf"
)

_cache: dict = {}
_ROW_TOL = 4   # points — tolérance pour regrouper des mots sur la même ligne
_NUMERIC_TOKEN_RE = re.compile(r"^[\d\s.,()\-]+$")


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
    """Vrai si la ligne porte un VRAI nombre (token composé uniquement de
    chiffres/espaces/ponctuation) — PAS seulement un code de ligne
    alphanumérique comme "AC5"/"CHV1"/"PRV11" (lettres + chiffres collés),
    qui contient bien un caractère chiffre mais n'est pas une donnée. Sans
    cette distinction, un titre de section portant son propre code (ex: "AC5
    Part des réassureurs dans les provisions") était à tort classé comme
    "ligne à chiffres" — découvert le 2026-08-18 sur STAR, où cela empêchait
    de détecter que ce titre est replié sur 2 lignes (voir _find_row_y
    Passe 3 / _merge_wrapped_titles)."""
    return any(_NUMERIC_TOKEN_RE.match(w["text"]) and any(ch.isdigit() for ch in w["text"]) for w in words)


def _count_numeric_tokens(words) -> int:
    return sum(1 for w in words if _NUMERIC_TOKEN_RE.match(w["text"]) and any(ch.isdigit() for ch in w["text"]))


def _pick_shortest(candidates):
    """candidates: [(length, top_y, bot_y, words), ...].

    Parmi les lignes correspondant au libellé, préfère d'abord celles qui
    portent le PLUS de montants (nombre de tokens numériques) — pas
    seulement "au moins un chiffre" : un titre de page portant son propre
    numéro d'annexe en token isolé (ex: "Annexe N° 13 : Résultat technique
    de la catégorie d'Assurance Non-Vie au 31/12/2024") a lui aussi un
    chiffre, mais un SEUL, alors que la vraie ligne de données en a
    plusieurs (une colonne par branche/catégorie) — sans ce tri par
    NOMBRE de chiffres, le titre (court) battait à tort la ligne de
    données (rendue longue par tous ses propres montants en texte) sur le
    seul critère de longueur — découvert le 2026-08-18 sur STAR 2024,
    Annexe 13. À nombre de chiffres égal, la plus courte gagne (ex: une
    ligne "PRIMES ACQUISES" en gras, sans chiffres, isolée du tableau de
    données, est plus courte que la vraie ligne de données et gagnait déjà
    à tort avant ce correctif). Repli sur toutes les candidates si aucune
    n'a de chiffre (colonne textuelle légitime, ex: Siège social)."""
    with_digit = [c for c in candidates if _count_numeric_tokens(c[3]) > 0]
    if with_digit:
        max_count = max(_count_numeric_tokens(c[3]) for c in with_digit)
        pool = [c for c in with_digit if _count_numeric_tokens(c[3]) == max_count]
    else:
        pool = candidates
    best = min(pool, key=lambda c: c[0])
    return best[1], best[2]


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
            candidates.append((len(full), top_y, bot_y, words))
    if candidates:
        return _resolve_title_row(rows, _pick_shortest(candidates))

    # Passe 2 : correspondance partielle sur chaque mot individuellement
    # (pour les libellés coupés sur plusieurs mots)
    tokens = ligne_norm.split()
    candidates = []
    for top_y, bot_y, words in rows:
        word_norms = [_norm(w["text"]) for w in words]
        # Vérifier que tous les tokens sont présents quelque part dans la ligne
        if all(any(t in wn for wn in word_norms) for t in tokens):
            row_len = sum(len(wn) for wn in word_norms)
            candidates.append((row_len, top_y, bot_y, words))
    if candidates:
        return _resolve_title_row(rows, _pick_shortest(candidates))

    # Passe 3 : titre de section REPLIÉ SUR 2 LIGNES (ex: "Part des
    # réassureurs dans les provisions" / "techniques" — le mot final déborde
    # sur la ligne suivante) — invisible aux passes 1/2 qui ne regardent
    # qu'UNE ligne à la fois. On fusionne chaque ligne SANS CHIFFRE avec ses
    # continuations immédiates (elles aussi sans chiffre, faible écart Y :
    # un vrai retour à la ligne dans le PDF, pas une nouvelle section) et on
    # ré-applique la correspondance par sous-chaîne sur ce texte fusionné —
    # découvert le 2026-08-18 sur STAR (plusieurs millésimes).
    merged = _merge_wrapped_titles(rows)
    candidates = []
    for top_y, bot_y, full, value_row in merged:
        if ligne_norm in full:
            candidates.append((len(full), top_y, bot_y, value_row))
    if candidates:
        top_y, bot_y, value_row = min(candidates, key=lambda c: c[0])[1:]
        if value_row is not None:
            return value_row
        return _resolve_title_row(rows, (top_y, bot_y))

    # Passe 4 : correspondance FLOUE (repli, uniquement si les passes 1-3
    # (toutes basées sur une correspondance EXACTE en sous-chaîne) échouent
    # totalement) - nécessaire sur les pages SCANNÉES (repli OCR, voir
    # _OcrFallbackPage) où l'OCR peut suffisamment dégrader un libellé pour
    # qu'aucune sous-chaîne exacte ne survive, même si le contenu reste
    # globalement reconnaissable (ex: "Charges d'acquisition et de gestion
    # nettes" lu "Chargesd'acqusion gestonnetes" par l'OCR - espaces et
    # lettres perdus, mais 86% de similarité globale - découvert le
    # 2026-08-22 sur STAR 2025, Annexe 13, retour utilisateur avec capture
    # d'écran montrant la ligne bien présente et lisible visuellement dans
    # le PDF alors que "ligne_introuvable" était renvoyé). Seuil élevé (82%)
    # pour rester sélectif : ce repli s'applique à TOUTES les recherches,
    # pas seulement celles sur page scannée, donc doit rester strict pour ne
    # pas accrocher à tort une ligne voisine sur une page à texte réel
    # propre (où les passes 1-3, plus précises, trouvent déjà tout ce qui
    # est légitimement trouvable).
    # Comparaison sur les mots NON numériques uniquement (comme
    # _row_has_digit/_count_numeric_tokens) : la plupart des lignes de
    # données ont leur libellé collé aux montants dans le même "mot" OCR
    # (ex: "Frais d'acquisition -16423 ..."), et un ratio global sur la
    # ligne ENTIÈRE serait faussé par cette longueur ajoutée - déjà le motif
    # documenté sur _pick_shortest, pour la même raison.
    target = ligne_norm.replace(" ", "")
    best_score, best_row = 82, None
    for top_y, bot_y, words in rows:
        label_words = [w for w in words if not _NUMERIC_TOKEN_RE.match(w["text"])]
        if not label_words:
            continue
        full = _norm(" ".join(w["text"] for w in label_words)).replace(" ", "")
        score = fuzz.ratio(full, target)
        if score > best_score:
            best_score, best_row = score, (top_y, bot_y)
    if best_row is not None:
        return _resolve_title_row(rows, best_row)

    return None


def _resolve_title_row(rows: list[tuple], row_y: tuple):
    """Si `row_y` correspond à une ligne de TITRE DE SECTION sans chiffre
    propre (ex: "AC1 Actifs incorporels", "AC5 Part des réassureurs..."),
    le vrai total de la section est une ligne SUIVANTE, sans libellé propre
    (ex: la somme AC12+AC13 apparaît seule, sans "Actifs incorporels" en
    préfixe) : on descend jusqu'à la ligne suivante qui commence un NOUVEAU
    titre de section (elle-même sans chiffre, après en avoir vu au moins une
    AVEC chiffres) et on retient la DERNIÈRE ligne à chiffres rencontrée dans
    l'intervalle (même convention que bilan_kpi_extractor._find_section_total
    : un total ≥ chacune de ses parties, donc la dernière ligne à chiffres
    avant la section suivante est la plus fiable). Si `row_y` porte déjà de
    vrais chiffres (ligne de donnée normale), la renvoie inchangée."""
    top_y, bot_y = row_y
    own_words = next((ws for t, _, ws in rows if t == top_y), [])
    if _row_has_digit(own_words):
        return row_y
    last_digit_row = None
    seen_digit = False
    for r_top, r_bot, r_words in sorted(rows, key=lambda r: r[0]):
        if r_top <= top_y:
            continue
        if _row_has_digit(r_words):
            last_digit_row = (r_top, r_bot)
            seen_digit = True
        elif seen_digit:
            break   # nouvelle ligne de titre sans chiffre = section suivante
        if r_top - top_y > 400:
            break   # garde-fou : ne pas parcourir toute la page
    return last_digit_row if last_digit_row is not None else row_y


def _merge_wrapped_titles(rows: list[tuple], max_gap=6, max_continuations=3) -> list[tuple]:
    """Fusionne chaque ligne SANS CHIFFRE avec ses continuations immédiates
    en un seul texte normalisé — voir _find_row_y Passe 3. Renvoie
    [(top_y, bot_y, texte, value_row), ...] UNIQUEMENT pour les blocs ainsi
    fusionnés (≥ 2 lignes) : les lignes normales (à chiffres, ou sans
    continuation) sont déjà couvertes par les passes 1/2.

    Tolère UNE ligne à chiffres intercalée entre les deux fragments du
    libellé (`value_row` porte alors sa position, sinon None) : certains
    tableaux CMF placent le libellé replié AUTOUR de sa propre valeur au
    lieu d'avant (ex: "charges des provisions d'assurance vie et des
    autres" / [ligne de chiffres] / "provisions techniques") — découvert le
    2026-08-18 sur STAR 2024, Annexe 12. Sans cette tolérance, le fragment
    de chiffres casse la fusion (vu comme une nouvelle section) et le
    libellé replié reste introuvable en un seul bloc."""
    ordered = sorted(rows, key=lambda r: r[0])
    merged = []
    i = 0
    while i < len(ordered):
        top_y, bot_y, words = ordered[i]
        if _row_has_digit(words):
            i += 1
            continue
        block_words = list(words)
        block_bot = bot_y
        value_row = None
        j = i + 1
        n_continuations = 0
        skipped_value = False
        while j < len(ordered) and n_continuations < max_continuations:
            n_top, n_bot, n_words = ordered[j]
            if (n_top - block_bot) > max_gap:
                break
            if _row_has_digit(n_words):
                if skipped_value:
                    break   # une seule ligne à chiffres tolérée
                # Les mots NON numériques présents sur cette ligne à chiffres
                # complètent le libellé replié — certains tableaux collent le
                # dernier fragment du libellé directement devant ses propres
                # valeurs plutôt que sur une ligne de texte pur (ex: BIAT
                # 2024, Annexe 13 : "Charges d'acquisition et de" / "gestion
                # nettes -12 236 460 ...", le fragment "gestion nettes" étant
                # sur LA MÊME ligne que les montants). Sans ce complément, la
                # fusion perdait ce fragment et le libellé restait
                # introuvable en un seul bloc — découvert le 2026-08-20.
                extra_label_words = [w for w in n_words if not _NUMERIC_TOKEN_RE.match(w["text"])]
                block_words += extra_label_words
                if extra_label_words:
                    n_continuations += 1   # compte comme fragment de libellé, sinon le bloc est jeté ci-dessous
                value_row = (n_top, n_bot)
                skipped_value = True
                j += 1
                continue    # ne pas avancer block_bot : le gap se mesure depuis le dernier fragment de LIBELLÉ
            block_words += n_words
            block_bot = n_bot
            n_continuations += 1
            j += 1
        if n_continuations > 0:
            full = _norm(" ".join(w["text"] for w in block_words))
            merged.append((top_y, block_bot, full, value_row))
        i += 1
    return merged


def _in_bbox(word, bbox, margin=2) -> bool:
    bx0, btop, bx1, bbottom = bbox
    return (bx0 - margin <= word["x0"] and word["x1"] <= bx1 + margin
            and btop - margin <= word["top"] <= bbottom + margin)


_COL_TOL = 15      # points — tolérance pour regrouper des phrases d'en-tête empilées sur la même colonne
_PHRASE_GAP_TOL = 5   # points — écart max entre 2 mots adjacents d'une même ligne pour les fondre en une seule phrase


def _row_phrases(words: list) -> list[dict]:
    """Regroupe les mots d'UNE MÊME ligne (déjà proches en Y) en phrases :
    deux mots consécutifs (triés par x0) appartiennent à la même phrase si
    l'écart entre eux est petit (mots d'un même libellé, ex: "Opérations"
    puis "nettes" séparés de ~2pt), et à des phrases différentes si l'écart
    est net (nouvelle colonne, ex: "nettes" puis la prochaine "Opérations"
    séparés de ~7pt) — découvert le 2026-08-18 sur STAR : l'en-tête
    "Opérations brutes Cessions et/ou Opérations nettes Opérations nettes"
    est entièrement sur UNE seule ligne, mots séparés (pas un seul token
    "Opérations nettes"), donc invisible à la fois pour la recherche
    mot-à-mot ET pour le regroupement vertical de _header_columns seul.
    Renvoie [{"words": [...], "x_sum": ..., "n": ..., "top": ...}, ...]
    trié par position X."""
    phrases: list[dict] = []
    current: list = []
    for w in sorted(words, key=lambda w: w["x0"]):
        if current and (w["x0"] - current[-1]["x1"]) > _PHRASE_GAP_TOL:
            phrases.append(current)
            current = []
        current.append(w)
    if current:
        phrases.append(current)
    return [
        {"words": p, "x_sum": sum((w["x0"] + w["x1"]) / 2 for w in p), "n": len(p), "top": p[0]["top"]}
        for p in phrases
    ]


_MAX_HEADER_SPAN = 140   # points — hauteur max de la zone d'en-tête (titre + libellés colonnes empilés)


def _header_columns(rows: list[tuple], above_y: float, table_bbox=None) -> list[tuple]:
    """Reconstruit un libellé de colonne à partir des lignes d'en-tête
    (au-dessus de `above_y`), en combinant deux dimensions d'éclatement
    rencontrées dans les PDF CMF :
      - HORIZONTAL (voir _row_phrases) : les mots d'un même libellé de
        colonne sont adjacents sur une même ligne mais restent des tokens
        pdfplumber séparés (ex: "Opérations" / "nettes").
      - VERTICAL : un même libellé de colonne est empilé sur PLUSIEURS
        lignes d'en-tête ("Opérations" sur une ligne, "Nettes" alignée en
        dessous — voir GAT, Annexe n°4).
    On reconstruit d'abord les phrases par ligne (horizontal), puis on
    regroupe ces phrases entre elles par proximité en X (vertical).
    Renvoie [(x_center, libellé_normalisé), ...] trié par x_center croissant.

    La zone d'en-tête est bornée à `_MAX_HEADER_SPAN` points sous le HAUT du
    TABLEAU (bbox si connue, sinon haut de la page) — pas seulement au-dessus
    de `above_y` : quand la ligne cible est tout en bas d'un grand tableau
    (ex: "Total de l'actif"), `above_y` couvre alors PRESQUE TOUTE la page,
    et regrouper toutes ces lignes de données comme "en-tête" produit des
    blobs de texte concaténé sur lesquels une recherche de sous-chaîne
    déclenche des faux positifs — découvert le 2026-08-18 sur STAR 2025
    (Bilan Actif scanné) : le blob fusionnait "...auxbénéfices..." et la
    recherche de la colonne "Net" y trouvait un faux "net" caché dans
    "bénéfices", pointant vers une colonne totalement hors sujet. On utilise
    le haut du TABLEAU (et non de la page) comme référence, pour ne pas
    casser la détection de l'en-tête d'un sous-tableau empilé plus bas sur la
    page (ex: Annexe 12/13 — Vie individuelle / Vie collective / Total,
    chacun avec son propre en-tête, pas forcément en haut de page)."""
    if rows:
        top_ref = table_bbox[1] if table_bbox is not None else min(top_y for top_y, _, _ in rows)
        above_y = min(above_y, top_ref + _MAX_HEADER_SPAN)

    phrases: list[dict] = []
    for top_y, _, words in rows:
        if top_y >= above_y:
            continue
        row_words = [w for w in words if table_bbox is None or _in_bbox(w, table_bbox)]
        if row_words:
            phrases.extend(_row_phrases(row_words))

    clusters: list[dict] = []
    for p in sorted(phrases, key=lambda p: p["top"]):
        mid_x = p["x_sum"] / p["n"]
        for c in clusters:
            if abs(mid_x - c["x_sum"] / c["n"]) <= _COL_TOL:
                c["words"].extend(p["words"])
                c["x_sum"] += p["x_sum"]
                c["n"] += p["n"]
                break
        else:
            clusters.append({"words": list(p["words"]), "x_sum": p["x_sum"], "n": p["n"]})

    columns = []
    for c in clusters:
        ordered = sorted(c["words"], key=lambda w: (w["top"], w["x0"]))
        label = _norm(" ".join(w["text"] for w in ordered))
        columns.append((c["x_sum"] / c["n"], label))
    return sorted(columns, key=lambda t: t[0])


def _find_combine_col_x(rows: list[tuple], annee: int, row_top_y: float, header_zone_end: float, table_bbox=None):
    """Bilan "Combiné" des sociétés Takaful françaises (AT_TAKAFULIA,
    ZITOUNA_TAKAFUL) : chaque exercice a 3 sous-colonnes (Fonds des
    Adhérents / Entreprise Takaful et/ou Rétakaful / combiné), le tout
    dupliqué pour l'exercice en cours ET le précédent — 6 sous-colonnes au
    total, sans qu'aucune ne porte le mot "Net" ni même l'année en clair
    (seul l'en-tête groupé "Exercice {année}" la porte). Ni la recherche
    mot-à-mot standard (aucun mot de sous-colonne ne contient l'année) ni le
    repli positionnel "Brut/Net" (calibré sur 4 colonnes, pas 6, et sans
    rapport avec ce gabarit) ne fonctionnent ici — découvert le 2026-08-19
    quand "Capitaux propres"/"Total actif" pointaient "ligne_introuvable" ou
    une sous-colonne incorrecte pour ces 2 sociétés.

    La colonne à cibler est "Entreprise" (PAS "combiné") : le pipeline
    d'extraction retient délibérément le Fonds des Adhérents à part (il
    appartient aux assurés, pas à la compagnie — voir docs/travaux_futurs.md,
    section Takaful) — vérifié le 2026-08-19 en recroisant contre les
    valeurs déjà persistées en base pour Total actif/Capitaux propres (4
    combinaisons société×KPI, dont 2 où "Entreprise" ≠ "combiné" faute de
    quoi l'écart passait inaperçu — piège dans lequel une première version
    de ce correctif était tombée en ciblant "combiné" par erreur).

    Plutôt que d'essayer de désambiguïser le libellé d'en-tête "Entreprise"
    (répété de façon incohérente sur plusieurs lignes empilées selon les
    documents), on lit directement les nombres de la LIGNE cible dans la
    zone horizontale de l'exercice visé et on retient l'AVANT-DERNIÈRE
    valeur — Entreprise précède toujours immédiatement combiné, que Fonds
    des Adhérents soit présent (3 valeurs) ou vide/tiret (2 valeurs) : même
    convention "avant-dernière colonne" que le repli Brut/Net des Bilans
    conventionnels (voir plus bas), donc robuste aux deux cas sans avoir
    besoin de les distinguer explicitement.

    Bornage de la zone horizontale : PAS via la position du libellé groupé
    "Exercice {année}" (centré sur tout le groupe de 3 sous-colonnes, donc
    trop à droite pour servir de bord GAUCHE, et pas assez pour servir de
    bord DROIT — vérifié le 2026-08-19 sur AT_TAKAFULIA/ZITOUNA_TAKAFUL,
    page Bilan Actifs : "Exercice 2023" à x≈489 empiétait sur les 2
    sous-colonnes de GAUCHE du groupe 2023 (Fonds/Entreprise, x≈422-475),
    faisant lire à tort la valeur "Fonds des Adhérents 2023" comme
    "Entreprise" de l'année en cours). Le bord gauche fiable est le mot
    "Fonds" (première sous-colonne, x0 quasi identique à la donnée en
    dessous — 1 occurrence par exercice, dans le même ordre gauche→droite
    que les groupes "Exercice"), le bord droit le mot "combiné" (dernière
    sous-colonne) + marge pour couvrir toute la largeur du nombre affiché
    (le nombre déborde souvent un peu à droite du libellé lui-même)."""
    header_rows = [(top_y, words) for top_y, _, words in rows if top_y < header_zone_end]
    if table_bbox is not None:
        header_rows = [(t, [w for w in ws if _in_bbox(w, table_bbox)]) for t, ws in header_rows]

    # Le libellé groupé par exercice n'est pas uniforme d'une société à
    # l'autre : AT_TAKAFULIA écrit "Exercice {année}" (année seule, avec
    # "Exercice" sur la même ligne), ZITOUNA_TAKAFUL écrit "{jj/mm/année}"
    # en un seul mot collé (ex: "31/12/2024"), sans aucun mot "Exercice" —
    # découvert le 2026-08-19 quand ZITOUNA_TAKAFUL retombait silencieusement
    # sur le repli générique Brut/Net (aucune "Exercice" détectée) et
    # pointait une colonne sans rapport avec l'année demandée. Les 2 formats
    # sont essayés.
    #
    # Le titre de page ("Actifs du Bilan Combiné arrêté au 31/12/2024" chez
    # ZITOUNA_TAKAFUL — 2 fois, en 2 variantes de casse) répète souvent le
    # mot "combiné" ET une date "jj/mm/année" glissée en un seul mot,
    # produisant de FAUX candidats "exercice"/"combiné" AU-DESSUS du
    # véritable en-tête tabulaire (découvert le 2026-08-19 : un faux
    # candidat "2024" du titre décalait tout l'index des groupes). On
    # cherche donc d'abord la LIGNE qui porte le PLUS d'années distinctes
    # (le vrai en-tête groupé les affiche toutes côte à côte, un titre n'en
    # a jamais qu'une) et on ignore tout ce qui est strictement au-dessus —
    # combiné à la même logique déjà en place pour ignorer tout ce qui est
    # strictement en dessous (repli Brut/Net d'un tableau conventionnel,
    # texte de ligne contenant le mot "fonds"...), la zone d'en-tête retenue
    # est donc bornée aux DEUX bouts, pas seulement en dessous.
    def _years_in_row(ws):
        """{année: x0} — x0 du mot lui-même, pour trier les groupes par
        position physique gauche→droite (l'ordre des années N'EST PAS
        forcément croissant : l'exercice en cours est toujours le groupe le
        plus à gauche, qu'il soit numériquement plus grand ou non)."""
        years = {}
        for w in ws:
            m = re.match(r"^(19|20)\d{2}$", w["text"])
            if m and any(_norm(o["text"]) == "exercice" for o in ws if abs(o["top"] - w["top"]) <= _ROW_TOL):
                years[int(w["text"])] = w["x0"]
                continue
            m2 = re.match(r"^\d{1,2}/\d{1,2}/((?:19|20)\d{2})$", w["text"])
            if m2:
                years[int(m2.group(1))] = w["x0"]
        return years

    year_row = max(header_rows, key=lambda tw: len(_years_in_row(tw[1])), default=None)
    years_here = _years_in_row(year_row[1]) if year_row is not None else {}
    has_year_labels = bool(years_here)
    if has_year_labels:
        year_row_top = year_row[0]
        header_rows = [(t, ws) for t, ws in header_rows if t >= year_row_top - _ROW_TOL]
        header_words = [w for _, ws in header_rows for w in ws]
    else:
        # Repli sans étiquette d'exercice du tout : certaines pages de
        # continuation (ex: AT_TAKAFULIA 2023, Bilan Passif — la suite du
        # Bilan Actif commencé page précédente) répètent les sous-en-têtes
        # "Fonds des Adhérents"/"Entreprise.../combiné" SANS reformuler
        # "Exercice {année}" ni aucune date, ce que le code ci-dessus ne
        # peut alors pas détecter — découvert le 2026-08-19. Dans ce cas on
        # suppose l'exercice DEMANDÉ (`annee`) présent en 1er groupe
        # (gauche), toujours vrai en usage réel : l'app ne demande jamais
        # la colonne comparative d'un exercice antérieur intégrée à un
        # AUTRE document (voir docstring de get_cell_coords), seulement
        # l'exercice propre du document consulté — donc toujours le groupe
        # le plus à gauche par convention de ces gabarits. Pas de bornage
        # "au-dessus" possible ici (aucune ligne repère) : on part du
        # principe que cette page de continuation n'a pas de titre parasite
        # (vérifié sur le cas connu) — seul le bornage "en dessous" via
        # "combiné" (ci-après) protège encore du texte de ligne parasite.
        years_here = {annee: 0.0}
        header_words = [w for _, ws in header_rows for w in ws]

    # Resserrement du bord BAS de la zone d'en-tête : `_MAX_HEADER_SPAN`
    # (140pt, partagé avec `_header_columns`/`_find_col_x` — volontairement
    # pas réduit ici pour ne pas risquer de régression sur d'autres pages)
    # laisse passer des lignes de DONNÉES situées juste sous le véritable
    # en-tête — ex: "AN2 Provisions d'Equilibrage du fonds des Adhérents"
    # contient le mot "fonds" en toutes lettres, faussement compté comme
    # une 3e sous-colonne "Fonds" — découvert le 2026-08-19 sur
    # AT_TAKAFULIA (Bilan Passif). "combiné" étant toujours la DERNIÈRE
    # ligne du véritable en-tête, on borne la zone à la ligne la plus basse
    # où "combiné" apparaît (à partir de `year_row_top`, donc sans les faux
    # candidats du titre) + une petite marge.
    combine_rows = [w["top"] for w in header_words if _norm(w["text"]) in ("combine", "combines")]
    if combine_rows:
        tight_end = max(combine_rows) + _ROW_TOL
        header_words = [w for w in header_words if w["top"] <= tight_end]

    exercice_spans = sorted(years_here.items(), key=lambda t: t[1])  # [(année, x0), ...] triés par position gauche→droite
    target_idx = next((i for i, (yr, _) in enumerate(exercice_spans) if yr == annee), None)
    if target_idx is None:
        return None

    all_fonds_x0s = sorted(w["x0"] for w in header_words if _norm(w["text"]) == "fonds")
    all_combine_x1s = sorted(w["x1"] for w in header_words if _norm(w["text"]) in ("combine", "combines"))
    if has_year_labels:
        # Repli additionnel : la 2e ligne de titre ("Actifs du Bilan Combiné
        # arrêté au...") tombe parfois EXACTEMENT sur la même ligne que les
        # en-têtes d'exercice chez ZITOUNA_TAKAFUL (coïncidence de rendu
        # PDF), donc invisible au bornage par ligne ci-dessus — mais son
        # "Combiné" de titre est toujours tout à GAUCHE (début de page),
        # donc si on trouve PLUS de "Fonds"/"combiné" que d'exercices
        # confirmés, on ne garde que les N plus à DROITE (les vraies
        # sous-colonnes, physiquement après la zone de titre) — découvert
        # le 2026-08-19.
        n = len(exercice_spans)
        fonds_x0s = all_fonds_x0s[-n:]
        combine_x1s = all_combine_x1s[-n:]
    else:
        # Repli sans étiquette (voir plus haut) : `exercice_spans` n'a
        # qu'une seule entrée ARTIFICIELLE (x0=0.0, qui ne représente RIEN
        # de physique) — on ne peut donc pas se fier à `target_idx` pour
        # indexer ces listes triées par position réelle. On prend
        # simplement le groupe le plus à GAUCHE (index 0), sans rogner :
        # pas de raison ici de soupçonner une contamination par un titre
        # (voir remarque ci-dessus).
        fonds_x0s, combine_x1s = all_fonds_x0s, all_combine_x1s
        target_idx = 0
    if not fonds_x0s or not combine_x1s or target_idx >= len(fonds_x0s) or target_idx >= len(combine_x1s):
        return None  # gabarit inattendu — pas de "Fonds"/"combiné" exploitable pour cet exercice

    zone_start = fonds_x0s[target_idx] - 4
    # Marge à droite volontairement modeste (8pt, pas 15) : le nombre
    # affiché déborde un peu du libellé "combiné" lui-même (ex: libellé
    # jusqu'à x=403.2, valeur jusqu'à x=408.1 — écart réel observé ~5pt),
    # mais le prochain groupe d'exercice peut démarrer TRÈS près derrière
    # (3,2pt d'écart observé sur ZITOUNA_TAKAFUL 2021) : une marge trop
    # généreuse absorbe alors à tort la 1ère sous-colonne de l'exercice
    # SUIVANT, décalant l'index "avant-dernière colonne" — découvert le
    # 2026-08-19 (Total actif retournait la valeur "combiné" au lieu
    # d'"Entreprise"). Bornée en plus par la position du prochain "Fonds"
    # (sous-colonne suivante) quand elle existe, jamais dépassée.
    next_fonds = min((x for x in fonds_x0s if x > fonds_x0s[target_idx]), default=None)
    zone_end = combine_x1s[target_idx] + 8
    if next_fonds is not None:
        zone_end = min(zone_end, next_fonds)

    row_words = next((ws for t, _, ws in rows if t == row_top_y), [])
    zone_words = [w for w in row_words if zone_start <= w["x0"] < zone_end]
    col_groups = _numeric_col_groups(zone_words, gap_tol=5)
    if len(col_groups) < 2:
        return None
    return col_groups[-2]


_GAP_TOL_NUMERIC = 8   # points — écart max entre 2 tokens numériques du même montant (regroupement de milliers)


def _numeric_col_groups(row_words: list, gap_tol: float = _GAP_TOL_NUMERIC) -> list[float]:
    """Regroupe les tokens PUREMENT numériques d'une ligne de données en
    "colonnes" (par écart X), en ignorant les tokens non numériques (libellé,
    séparateurs de grille mal reconnus par l'OCR comme "|" ou "_"). Renvoie
    les centres X de chaque colonne, triés de gauche à droite.

    `gap_tol` par défaut à `_GAP_TOL_NUMERIC` (8pt, calibré pour les Bilans
    conventionnels à 4 colonnes, plus espacées) — trop généreux pour les 6
    colonnes cramponnées du Bilan "Combiné" Takaful (voir
    `_find_combine_col_x`), où l'écart entre 2 colonnes DIFFÉRENTES peut
    descendre sous 8pt (7,3pt observé sur AT_TAKAFULIA 2022) tout en restant
    nettement supérieur à l'écart INTRA-nombre (regroupement de milliers,
    ~2pt) : fusionnait à tort "Entreprise"+"combiné" en un seul groupe,
    faussant l'index "avant-dernière colonne" — découvert le 2026-08-19."""
    numeric = [
        w for w in sorted(row_words, key=lambda w: w["x0"])
        if _NUMERIC_TOKEN_RE.match(w["text"]) and any(ch.isdigit() for ch in w["text"])
    ]
    groups: list[list] = []
    for w in numeric:
        if groups and (w["x0"] - groups[-1][-1]["x1"]) <= gap_tol:
            groups[-1].append(w)
        else:
            groups.append([w])
    return [sum((w["x0"] + w["x1"]) / 2 for w in g) / len(g) for g in groups]


def _find_col_x(rows: list[tuple], colonne_norm: str, above_y: float, table_bbox=None, annee: int | None = None):
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

    # Zone d'en-tête bornée à `_MAX_HEADER_SPAN` points sous le haut du
    # TABLEAU (bbox si connue, sinon haut de la page) — voir _header_columns
    # pour l'explication complète. Sans cette borne, un mot OCR mal reconnu
    # N'IMPORTE OÙ au-dessus de la ligne cible (tout le reste de la page,
    # quand la ligne cible est en bas d'un grand tableau) peut contenir
    # `colonne_norm` en sous-chaîne par pur artefact d'OCR et détourner le
    # match — découvert le 2026-08-18 sur STAR 2025 : "auxb...tces" (OCR de
    # "bénéfices") contient "net", loin de tout vrai en-tête. Volontairement
    # PAS de repli "zone complète non bornée" ensuite : un tel repli
    # réintroduirait exactement ce faux positif : mieux vaut retomber sur le
    # repli numérique ci-dessous (ou colonne_introuvable) qu'un mauvais match.
    header_zone_end = above_y
    if rows:
        top_ref = table_bbox[1] if table_bbox is not None else min(top_y for top_y, _, _ in rows)
        header_zone_end = min(above_y, top_ref + _MAX_HEADER_SPAN)

    # Bilan "Combiné" Takaful (voir _find_combine_col_x) : tentée EN PREMIER
    # quand `annee` est fournie — ne matche que si l'en-tête porte
    # effectivement des groupes "Exercice {année}", donc sans effet sur les
    # sociétés conventionnelles (aucun "Exercice" dans leurs Bilans).
    if annee is not None:
        combine_x = _find_combine_col_x(rows, annee, above_y, header_zone_end, table_bbox)
        if combine_x is not None:
            return combine_x

    for _, _, words in [r for r in rows if r[0] < header_zone_end]:
        for w in words:
            if colonne_norm in _norm(w["text"]) and (table_bbox is None or _in_bbox(w, table_bbox)):
                mid_x = (w["x0"] + w["x1"]) / 2
                if w["x0"] > best_x0:
                    best_x0 = w["x0"]
                    best_x = mid_x

    if best_x is None:
        # Repli : le libellé recherché est peut-être réparti sur plusieurs
        # lignes d'en-tête empilées (voir _header_columns) plutôt que porté
        # par un seul mot.
        for bbox in ((table_bbox,) if table_bbox is not None else ()) + (None,):
            matches = [x for x, label in _header_columns(rows, above_y, bbox) if colonne_norm in label]
            if matches:
                # Convention "avant-dernière colonne" = année en cours,
                # partagée par tout le pipeline d'extraction (voir
                # bilan_kpi_extractor._select_column_value) : ces tableaux
                # à en-tête empilé répètent le même libellé ("Opérations
                # Nettes") pour l'année en cours ET l'année précédente,
                # cette dernière toujours en dernière colonne. Prendre le
                # simple "plus à droite" (comme pour un match sur un seul
                # mot, jamais dupliqué ainsi) surlignerait à tort la valeur
                # de l'année précédente — découvert le 2026-08-18 sur GAT
                # (Charges de sinistres Vie : (2 011 072) attendu, colonne
                # -2 était (1 248 161), la valeur 2024 et non 2025).
                best_x = matches[-2] if len(matches) >= 2 else matches[-1]
                break

    if best_x is None and table_bbox is not None:
        return _find_col_x(rows, colonne_norm, above_y, table_bbox=None, annee=annee)

    if best_x is None and colonne_norm in ("net", "total"):
        # Dernier repli, uniquement pour "Net"/"Total" (positions structurelles
        # stables dans les tableaux CMF concernés) : si aucun en-tête n'a pu
        # être lu (OCR ayant totalement manqué la ligne d'en-tête — constaté
        # le 2026-08-18 sur STAR 2025 : Bilan Actif scanné sans "Brut"/"Net"
        # lisibles malgré un texte pourtant net à l'œil sur l'image, ET Annexe
        # 13 (p.45) où la ligne d'en-tête entière ("CATEGORIES GROUPE
        # A.TRAVAIL...TOTAL") est absente de l'OCR alors que les lignes de
        # données juste en dessous sont, elles, bien lues), on retrouve la
        # position de la colonne directement à partir des montants de la
        # ligne cible elle-même :
        #   - "net" : tableaux Bilan (Brut/Amortissements et provisions/
        #     Net-année en cours/Net-année précédente) → avant-dernière
        #     colonne (même convention que partout ailleurs dans le pipeline
        #     d'extraction) ;
        #   - "total" : tableaux Annexe 12/13 par catégorie (Vie/Décès/
        #     Mixte/Acceptation/Total, ou Groupe/branches.../Total) → "Total"
        #     est TOUJOURS la dernière colonne (confirmé sur tous les
        #     documents natifs examinés) → dernière colonne.
        # Garde-fou : n'appliquer ce repli que si la ligne cible ressemble
        # vraiment à une ligne de données à plusieurs colonnes, pas à un
        # faux positif comme le TITRE de page ("Annexe N° 13...") retenu
        # faute de mieux quand la vraie ligne de données est totalement
        # absente de l'OCR (constaté le 2026-08-18 sur STAR 2025, Annexe 13
        # p.45 : la ligne "Résultat technique" n'existe nulle part dans les
        # mots OCR, donc _find_row_y retombait sur le titre — qui porte lui
        # aussi UN chiffre isolé, le numéro d'annexe — et ce repli aurait pu
        # y "trouver" une fausse colonne). Sans cette vraie ligne de
        # données, mieux vaut "colonne_introuvable" (honnête) qu'un
        # surlignage trompeur.
        target_words = next((ws for t, _, ws in rows if t == above_y), [])
        col_groups = _numeric_col_groups(target_words)
        min_groups = 3 if colonne_norm == "total" else 2
        if len(col_groups) >= min_groups:
            if colonne_norm == "net":
                best_x = col_groups[-2]
            else:
                best_x = col_groups[-1]

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

    # `ligne` peut porter plusieurs libellés candidats séparés par " || " :
    # certaines lignes du DVRB n'ont pas un intitulé unique et stable d'une
    # compagnie à l'autre (ex: "Total capitaux propres avant affectation" vs
    # "...avant résultat de l'exercice" — les deux existent réellement selon
    # les PDF, parfois même TOUTES LES DEUX sur la même page comme 2 sous-
    # totaux distincts). On essaie chaque candidat dans l'ordre et on retient
    # le premier qui trouve une ligne — pas un texte hybride injecté tel quel
    # dans `ligne` (qui ne correspond alors à AUCUN texte réel du PDF et
    # échoue toujours en "ligne_introuvable", constaté le 2026-08-18).
    ligne_candidates = [c.strip() for c in ligne.split(" || ") if c.strip()]
    # `colonne` accepte le même mécanisme " || " : le format des tableaux
    # Annexe 12/13 a changé au fil du temps chez certaines compagnies (ex:
    # STAR avant ~2020 : colonnes "Opérations Brutes/Cessions/Opérations
    # Nettes(année)/Opérations Nettes(année-1)", SANS aucune colonne "Total" ;
    # à partir de ~2020 : colonnes par branche "Vie/Décès/Mixte/Acceptation/
    # Total"). Un même KPI du DVRB doit donc essayer plusieurs libellés de
    # colonne selon le millésime — découvert le 2026-08-18 sur STAR.
    colonne_candidates = [_norm(c) for c in colonne.split(" || ") if c.strip()]

    result = None
    reason = "erreur"
    page_rotation = 0
    try:
        with pdfplumber.open(path) as pdf:
            if page_num < 1 or page_num > len(pdf.pages):
                _cache[cache_key] = (None, "page_invalide")
                return _cache[cache_key]
            page   = pdf.pages[page_num - 1]
            page_w = float(page.width)
            page_h = float(page.height)
            page_rotation = page.rotation

            # ── 1. Toutes les cellules PDF de la page ────────────────────────
            tables = page.find_tables()
            all_cells = []
            for tbl in tables:
                for cell in tbl.cells:
                    if cell is not None:
                        all_cells.append(cell)

            # ── 2. Mots de la page groupés par ligne ─────────────────────────
            # Repli OCR (_OcrFallbackPage, coût nul sauf page réellement
            # scannée) : sans lui, une page de Bilan scannée (texte natif
            # vide) retournait "page_vide" alors que le PDF a bien une page
            # à ce numéro — constaté le 2026-08-18 sur STAR 2025, "Total
            # actif" (page 2, Bilan Actif scanné), affiché "Non surligné :
            # Aucun texte extractible sur cette page (page probablement
            # scannée)" alors que la valeur elle-même était correcte
            # (extraction/bilan_kpi_extractor.py a son propre repli OCR).
            words = _OcrFallbackPage(page).extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                _cache[cache_key] = (None, "page_vide")
                return _cache[cache_key]
            rows = _word_rows(words)

            # ── 3. Trouver la ligne cible (Y) ────────────────────────────────
            row_y = None
            for candidate in ligne_candidates:
                row_y = _find_row_y(rows, _norm(candidate))
                if row_y is not None:
                    break
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
            x_mid = None
            colonne_norm = colonne_candidates[0] if colonne_candidates else _norm(colonne)
            for candidate_norm in colonne_candidates:
                x_mid = _find_col_x(rows, candidate_norm, above_y=top_y, table_bbox=table_bbox, annee=int(annee))
                if x_mid is not None:
                    colonne_norm = candidate_norm
                    break
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

    if result is not None and page_rotation % 360 != 0:
        result = _rotate_to_native(result, page_rotation)

    _cache[cache_key] = (result, None if result else reason)
    return _cache[cache_key]


def _rotate_to_native(result, rotation):
    """pdfplumber applique /Rotate à `page.width`/`page.height` ET aux
    coordonnées des mots (elles sont donc déjà dans le repère "visuel"
    post-rotation, cohérent avec `page_width`/`page_height` tels que
    renvoyés ci-dessus) — mais pdf.js côté frontend (PDFPageProxy.
    getViewport()/convertToViewportPoint(), voir KpiDetail.jsx) attend des
    coordonnées dans le repère NATIF (avant rotation) : c'est lui qui
    applique la rotation via son propre viewport pour l'affichage. Sans
    cette conversion, une page pivotée (ex: Annexe 13 imprimée en paysage
    dans un document par ailleurs portrait, /Rotate 90) plaçait le
    surlignage à un endroit incorrect (ou hors champ), alors que la page
    non pivotée voisine (Annexe 12, /Rotate 0) fonctionnait déjà
    correctement avec exactement le même mécanisme côté frontend —
    constaté 2026-08-22 sur STAR 2025 (page 45 vs page 44), retour
    utilisateur avec capture d'écran comparative.

    `result["page_width"/"page_height"]` sont mis à jour en conséquence
    (dimensions natives, dimensions permutées pour 90°/270°) pour rester
    cohérents avec les coordonnées renvoyées, même si le frontend ne les
    utilise pas actuellement pour la conversion elle-même (il ne fait
    confiance qu'à son propre `viewport`, calculé indépendamment depuis le
    PDF)."""
    x0, y0, x1, y1 = result["x0"], result["y0"], result["x1"], result["y1"]
    page_w, page_h = result["page_width"], result["page_height"]
    rotation = rotation % 360
    if rotation == 90:
        nx0, ny0 = page_h - y0, x0
        nx1, ny1 = page_h - y1, x1
        native_w, native_h = page_h, page_w
    elif rotation == 270:
        nx0, ny0 = y0, page_w - x0
        nx1, ny1 = y1, page_w - x1
        native_w, native_h = page_h, page_w
    elif rotation == 180:
        nx0, ny0 = page_w - x0, page_h - y0
        nx1, ny1 = page_w - x1, page_h - y1
        native_w, native_h = page_w, page_h
    else:
        return result
    result["x0"], result["x1"] = min(nx0, nx1), max(nx0, nx1)
    result["y0"], result["y1"] = min(ny0, ny1), max(ny0, ny1)
    result["page_width"], result["page_height"] = native_w, native_h
    return result
