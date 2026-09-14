"""Extraction PLEINE GRILLE du Bilan Actif/Passif (par opposition à
bilan_kpi_extractor.py, qui n'extrait que quelques KPI ciblés) — pour le
stockage tableau_cellules / la page de correction manuelle, comme
Annexe 12/13 (extraction/annexe13_pipeline.py, full_table_extractor.py).

Réutilise les primitives de reconstruction de ligne déjà éprouvées de
bilan_kpi_extractor.py (mots repositionnés par `page.extract_words()`,
regroupés en lignes visuelles par position Y) plutôt que camelot : le
tableau Bilan n'a pas de quadrillage horizontal entre ses lignes de détail
— camelot (flavor "lattice") fusionne alors TOUTES les lignes de détail
d'une section en une seule cellule multi-lignes par colonne, rendant son
DataFrame inexploitable pour une reconstruction ligne-par-ligne fiable
(vérifié : le nombre de lignes internes diffère d'une colonne à l'autre
quand une cellule est vide sur certaines lignes, désynchronisant tout
zip par index dès la première case blanche).

Chaque ligne du Bilan porte un CODE réglementaire standardisé (AC1..AC7,
AC11, AC12... côté Actif ; CP1, CP2..., PA2, PA3, PA31... côté Passif) —
identique chez toutes les sociétés (plan comptable CMF), donc utilisé ici
comme clé canonique plutôt que le libellé français (qui varie/se déforme
bien plus facilement, comme vu sur Annexe 12/13 : OCR, abréviations,
libellés coupés). Colonnes assignées par position (x0 le plus proche de
l'en-tête correspondant), pas par ordre — une cellule vide (ex.
"Amortissements" sur une ligne sans amortissement) ne doit jamais décaler
les valeurs suivantes vers la colonne d'à côté."""

import re

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters, _normalizer,
    _words_with_bracket_negatives_resolved,
    ACTIF_PAGE_TITLE_RE, PASSIF_PAGE_TITLE_RE, NUMERIC_TOKEN_RE,
)

_ROW_CODE_RE = re.compile(r"^(AC|PA|CP)\s?(\d+)\b", re.IGNORECASE)

# Ligne de TOTAL général — jamais préfixée d'un code réglementaire (contrairement
# à toutes les autres lignes), donc invisible à _ROW_CODE_RE : traitée à part,
# jamais rattachée par erreur au dernier code rencontré (voir extract_bilan_full_grid).
_TOTAL_ACTIF_RE = re.compile(r"^total(\s+(de\s+l['\s]|des\s+)?actifs?)?$")
_TOTAL_PASSIF_RE = re.compile(r"^total(\s+(du\s+|des\s+)?passifs?)?$")

# En-têtes de colonnes numériques recherchés côté Actif ; côté Passif,
# seulement "Net" (pas de ventilation brut/amortissements sur ce côté).
# Le NOMBRE de colonnes n'est PAS fixe : la plupart des sociétés ne
# détaillent que l'année courante (Brut/Amort/Net N, puis un unique "Net"
# N-1 — 4 colonnes), mais certaines (ex. ATTIJARI) répètent le triplet
# Brut/Amort/Net EN ENTIER pour l'année précédente (6 colonnes). Détecté
# dynamiquement par `_header_token_sequence` plutôt que supposé — un
# nombre de colonnes codé en dur ferait dérailler l'alignement de toutes
# les valeurs sur les documents à 6 colonnes (constaté : la totalité de
# "Amort", "Net" et "Net (N-1)" ressortait vide sur ATTIJARI 2023).
_WANTED_TOKENS_ACTIF = {"brut", "vb", "amort", "net"}
_WANTED_TOKENS_PASSIF = {"net"}
# "VB" (Valeur Brute) : abréviation alternative de "Brut" pour cette même
# colonne (constaté MAGHREBIA) — mêmes noms de colonnes en sortie quel que
# soit l'intitulé réellement imprimé.
_LABEL_BY_TOKEN = {"brut": "Brut", "vb": "Brut", "amort": "Amortissements et provisions", "net": "Net"}


def _is_target_page(page, side, lines_checked=6):
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    title_re = ACTIF_PAGE_TITLE_RE if side == "actif" else PASSIF_PAGE_TITLE_RE
    if not title_re.search(normalized):
        return False
    if side == "actif":
        return "passif" not in normalized
    return True


def _header_columns(lines, side):
    """Détecte les colonnes numériques réellement présentes sur cette page
    — nom + position x0 — en repérant CHAQUE occurrence des jetons d'en-
    tête voulus (Brut/Amort/Net côté Actif, Net côté Passif) dans les
    lignes situées avant le premier code AC../PA../CP.., dans l'ordre de
    lecture gauche->droite. Le nombre de colonnes ressort de ce qui est
    RÉELLEMENT trouvé (4 ou 6 côté Actif selon que l'année précédente est
    aussi ventilée Brut/Amort/Net ou réduite à un "Net" — voir le
    commentaire sur `_WANTED_TOKENS_ACTIF`), jamais supposé fixe. La 2e
    occurrence d'un même jeton (et les suivantes) reçoit un suffixe
    "(N-k)". Renvoie (noms_de_colonnes, positions_x0) — listes parallèles."""
    wanted = _WANTED_TOKENS_ACTIF if side == "actif" else _WANTED_TOKENS_PASSIF
    header_lines = []
    for line in lines:
        has_code = any(_ROW_CODE_RE.match(_normalizer.clean(w["text"])) for w in line)
        if has_code:
            break
        header_lines.append(line)
    counts = {}
    names, positions = [], []
    for line in header_lines:
        for w in sorted(line, key=lambda w: w["x0"]):
            # startswith, pas égalité stricte : "Amort." (COMAR/ATTIJARI),
            # "Amortissements" (en toutes lettres ailleurs) partagent le même
            # préfixe mais pas le même jeton nettoyé exact (le point final
            # de l'abréviation n'est pas retiré par le normaliseur).
            raw = _normalizer.clean(w["text"])
            token = next((t for t in wanted if raw.startswith(t)), None)
            if token is None:
                continue
            counts[token] = counts.get(token, 0) + 1
            suffix = "" if counts[token] == 1 else f" (N-{counts[token] - 1})"
            names.append(_LABEL_BY_TOKEN[token] + suffix)
            positions.append(w["x0"])
    return names, positions


# Référence de note ("3.1", "3.1.1"...) : toujours un UNIQUE mot-jeton
# contenant un point (contrairement à un vrai montant, dont les groupes de
# milliers sont des mots SÉPARÉS par un espace — "75 000 000" est 3 jetons,
# jamais 1 seul avec point). Les chiffres de ces tableaux sont toujours des
# dinars entiers ("chiffres arrondis") : aucune vraie valeur n'a de point
# décimal, donc ce test ne peut pas rejeter à tort un vrai montant. Une
# marge de position x0 avait été tentée d'abord mais s'est révélée peu
# fiable (colonnes alignées à DROITE : un montant large comme "75 000 000"
# démarre bien plus à gauche que le mot d'en-tête court "Net" qui le
# surmonte, faisant rejeter à tort de vraies valeurs).
_NOTE_REF_TOKEN_RE = re.compile(r"^\d+(?:\.\d+)+$")


def _assign_columns(clusters, header_x, n_cols):
    """Affecte chaque valeur numérique trouvée sur la ligne (`clusters`,
    liste de (valeur, x0) triée gauche->droite) à l'index de colonne dont
    l'en-tête est le plus proche en x0 — jamais par position ordinale pure,
    pour ne pas décaler les colonnes suivantes quand une cellule est vide.
    Repli sur l'ordre d'apparition si les en-têtes n'ont pas pu être
    localisés (`header_x` vide)."""
    if not header_x:
        return {i: v for i, (v, _x0) in enumerate(clusters) if i < n_cols}
    result = {}
    for value, x0 in clusters:
        idx = min(range(len(header_x)), key=lambda i: abs(header_x[i] - x0))
        # Une valeur ne remplace jamais une déjà affectée à la même colonne
        # (2 clusters proches du même en-tête = vraisemblablement un
        # artefact de segmentation, on garde le premier rencontré).
        result.setdefault(idx, value)
    return result


def extract_bilan_full_grid(page, side, min_rows=5):
    """Reconstruit la grille complète (tous les postes, pas seulement les
    totaux) du Bilan Actif ou Passif visible sur `page`. Renvoie
    {"colonnes": [...], "lignes": {code: {colonne: valeur}}} ou None si la
    page ne ressemble pas assez à un tableau de Bilan exploitable (moins de
    `min_rows` lignes codées trouvées)."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)
    colonnes, header_x = _header_columns(lines, side)
    if not colonnes:
        # Repli si aucun en-tête n'a pu être localisé (page non conforme au
        # gabarit attendu) : nombre de colonnes générique, valeurs affectées
        # par ordre d'apparition (voir `_assign_columns`, header_x vide).
        colonnes = (
            ["Brut", "Amortissements et provisions", "Net", "Net (N-1)"] if side == "actif"
            else ["Net", "Net (N-1)"]
        )
    n_cols = len(colonnes)

    lignes = {}
    label_by_code = {}  # 1er libellé non vide rencontré par code — une ligne
                        # de sous-total répète souvent le code SEUL (sans
                        # libellé), qui ne doit jamais écraser le vrai
                        # libellé déjà vu sur la ligne de titre de section.
    current_code = None
    current_values = {}
    current_section = None  # dernier code de section top-level (1 seul chiffre,
                             # ex. AC1, AC2) — une ligne de SOUS-TOTAL de section
                             # arrive souvent SANS aucun code ni libellé (juste
                             # des chiffres, après tous ses postes de détail) ;
                             # elle doit lui revenir, pas au dernier enfant
                             # rencontré (ex. AC12), qui a déjà ses propres
                             # valeurs et les garderait (via `setdefault`),
                             # perdant silencieusement le total de la section.
    _TOP_SECTION_RE = re.compile(r"^(AC|PA|CP)\d$")
    total_re = _TOTAL_ACTIF_RE if side == "actif" else _TOTAL_PASSIF_RE

    def _flush():
        if current_code and current_values:
            lignes[current_code] = {i: v for i, v in current_values.items()}

    for line in lines:
        # Code réglementaire séparé de son numéro par une espace ("AC 71"
        # au lieu de "AC71", constaté ATTIJARI) : fusionné en un seul mot
        # AVANT tout le reste, sinon "71" seul seul est indiscernable d'une
        # vraie valeur numérique de la ligne — il serait retiré du libellé
        # par le filtre `NUMERIC_TOKEN_RE` avant même que `_ROW_CODE_RE`
        # n'ait eu la chance de reconnaître le code sur le texte complet.
        if (len(line) >= 2 and re.match(r"^(AC|PA|CP)$", line[0]["text"], re.IGNORECASE)
                and re.match(r"^\d+$", line[1]["text"])):
            line = [{**line[0], "text": line[0]["text"] + line[1]["text"]}, *line[2:]]
        # Résolution des négatifs entre parenthèses/chevrons AVANT de
        # distinguer libellé/valeurs — sinon "(95" et "277)" (fragments
        # d'un "(95 854 277)" comptable) ne matchent ni l'un ni l'autre et
        # se retrouvent inclus à tort dans le libellé reconstruit (constaté
        # sur la ligne "Total des actifs" de GAT : le résidu "(95 277)"
        # dans le texte empêchait sa reconnaissance comme ligne de total).
        resolved_line = _words_with_bracket_negatives_resolved(line)
        label_words = [w for w in resolved_line if not NUMERIC_TOKEN_RE.match(w["text"])]
        line_no_notes = [w for w in resolved_line if not _NOTE_REF_TOKEN_RE.match(w["text"])]
        clusters = _extract_numeric_clusters(line_no_notes)
        text_norm = _normalizer.clean(" ".join(w["text"] for w in label_words))
        if total_re.match(text_norm):
            # Ligne de TOTAL général — jamais préfixée d'un code, traitée à
            # part pour ne jamais se retrouver fusionnée avec la dernière
            # section rencontrée (sinon ses valeurs, arrivant après que
            # cette section ait déjà les siennes, seraient silencieusement
            # ignorées par le `setdefault` de la branche "continuation").
            _flush()
            current_code = None
            lignes["TOTAL"] = _assign_columns(clusters, header_x, n_cols)
            label_by_code["TOTAL"] = text_norm
            continue
        m = _ROW_CODE_RE.match(text_norm)
        if m:
            _flush()
            current_code = f"{m.group(1).upper()}{m.group(2)}"
            if _TOP_SECTION_RE.match(current_code):
                current_section = current_code
            rest = text_norm[m.end():].strip()
            if rest and current_code not in label_by_code:
                label_by_code[current_code] = rest
            current_values = _assign_columns(clusters, header_x, n_cols)
        elif (not text_norm and current_section and current_section not in lignes
              and len(clusters) >= max(2, n_cols - 1)):
            # Ligne de sous-total de section SANS code ni libellé (voir plus
            # haut) : rattachée au code de section ouvert plutôt qu'au
            # dernier enfant — seulement si cette section n'a pas encore sa
            # propre valeur, ET que la ligne porte (presque) autant de
            # valeurs que de colonnes attendues (`n_cols - 1` au minimum) :
            # un sous-total légitime remplit toutes les colonnes, alors
            # qu'une VRAIE ligne de détail sans libellé récupéré (rare, ex.
            # une valeur "0" esseulée constatée sur MAGHREBIA/AC64) n'en a
            # typiquement qu'une — la prendre pour le sous-total aurait
            # perdu le vrai total, arrivant juste après, en le trouvant déjà
            # "pris".
            lignes[current_section] = _assign_columns(clusters, header_x, n_cols)
        elif current_code:
            # Ligne de continuation (libellé replié, ou valeurs arrivées
            # une ligne après un libellé trop long) — rattachée au dernier
            # code rencontré plutôt qu'ignorée.
            if text_norm and current_code not in label_by_code:
                label_by_code[current_code] = text_norm
            if clusters:
                for i, v in _assign_columns(clusters, header_x, n_cols).items():
                    current_values.setdefault(i, v)
    _flush()

    if len(lignes) < min_rows:
        return None
    lignes_out = {
        code: {"libelle": label_by_code.get(code, code), **{
            colonnes[i]: v for i, v in values.items() if i < n_cols
        }}
        for code, values in lignes.items()
    }
    return {"colonnes": colonnes, "lignes": lignes_out}


def locate_and_extract_bilan(pdf_path, side, max_pages=15):
    """Parcourt les premières pages de `pdf_path` à la recherche de la page
    Bilan Actif/Passif (`side` = 'actif' ou 'passif') et en extrait la
    grille complète. Renvoie (numero_page_1_indexe, grille) ou (None, None)."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            if not _is_target_page(page, side):
                continue
            grid = extract_bilan_full_grid(page, side)
            if grid is not None:
                return i + 1, grid
    return None, None
