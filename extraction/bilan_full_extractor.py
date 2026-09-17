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
    _OcrFallbackPage,
)

# "AN" (Actifs Nets des adhérents) : préfixe propre aux sociétés Takaful,
# section du Bilan Passif qui n'existe que pour elles (fonds mutualisé des
# assurés, distinct des Capitaux propres des actionnaires — voir
# extraction/takaful_kpi_extractor.py pour le contexte réglementaire).
_ROW_CODE_RE = re.compile(r"^(AC|PA|CP|AN)\s?(\d+)(?:,\d+)*", re.IGNORECASE)

# Ligne de TOTAL général — jamais préfixée d'un code réglementaire (contrairement
# à toutes les autres lignes), donc invisible à _ROW_CODE_RE : traitée à part,
# jamais rattachée par erreur au dernier code rencontré (voir extract_bilan_full_grid).
_TOTAL_ACTIF_RE = re.compile(r"^total(\s+(de\s+l['\s]|des\s+)?actifs?)?$")
_TOTAL_PASSIF_RE = re.compile(r"^total(\s+(du\s+|des\s+)?passifs?)?$")
# Certains documents (ex. BIAT) n'imprimment JAMAIS de "Total du Passif"
# isolé (hors capitaux propres) — seulement le total général combiné
# ("Total capitaux propres et passifs" = Total de l'Actif). Reconnu à
# part (clé "TOTAL_GENERAL", pas "TOTAL") pour ne jamais le confondre
# avec un vrai "Total du Passif" lors d'une validation future : ce total
# combiné n'est PAS comparable à la somme des seules sections PA/CP2..7.
_TOTAL_GENERAL_RE = re.compile(r"^total\s+(des\s+)?capitaux\s+propres\s+et\s+(des\s+|du\s+)?passifs?$")
# "Total capitaux propres AVANT AFFECTATION" (ou juste "Total capitaux
# propres" seul) — la vraie ligne IMPRIMÉE dans le PDF pour le sous-total
# Capitaux propres complet (CP1..CP6 inclus), déjà utilisée comme source
# du KPI narrow "Capitaux propres" (voir kpi_definitions.py) — constaté
# STAR : sans la capturer comme SA PROPRE ligne, une correction manuelle
# sur une cellule CP1..CP6 individuelle ne peut jamais se répercuter sur
# ce KPI (qui vaut leur SOMME, jamais une seule cellule) puisque la
# propagation par valeur (voir database/repository.py::
# _propagate_correction_to_kpi) compare une correction à UNE valeur de
# KPI, pas à une formule. À NE PAS confondre avec "Total capitaux propres
# AVANT RÉSULTAT de l'exercice" (sous-total intermédiaire, EXCLUT CP6) —
# le mot suivant "avant" doit être "affectation", pas "resultat".
_TOTAL_CP_RE = re.compile(r"^total\s+(des\s+)?capitaux\s+propres(\s+avant\s+affectation)?$")
# "Total des Actifs Nets des adhérents" — même principe que _TOTAL_CP_RE,
# mais pour la section "AN" (Actifs Nets des adhérents, propre aux
# sociétés Takaful) : sous-total propre, jamais rattaché au dernier code
# AN rencontré.
_TOTAL_AN_RE = re.compile(r"^total\s+(des\s+)?actifs?\s+nets?\s+des\s+adherents?$")

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

# Gabarit Takaful ("Bilan Combiné", à partir de ~2020, voir
# takaful_kpi_extractor.py) : colonnes "Entreprise (Takaful et/ou
# Rétakaful)" / "Fonds des Adhérents" / "...combiné" PAR EXERCICE, aucun
# des jetons Brut/Amort/Net/VB attendus par `_header_columns`. Détecté par
# ce simple indice de vocabulaire plutôt que par société (générique : une
# société non-Takaful n'a aucune raison d'employer ces mots). Le
# comptage habituel par occurrence de jeton (`_header_columns`) n'est PAS
# fiable ici : l'en-tête s'étale sur PLUSIEURS lignes PHYSIQUES à cause du
# retour à la ligne (repéré : "Entreprise" apparaît jusqu'à 4 fois pour 2
# vraies colonnes) — le nombre de colonnes est donc déduit du nombre de
# valeurs sur une VRAIE ligne de données (voir `_takaful_column_names`),
# pas du nombre de mots d'en-tête reconnus.
_TAKAFUL_HEADER_HINT_RE = re.compile(r"entreprise\s+takaful|fonds\s+des\s+adherents|\bcombine\b")
_TAKAFUL_COLUMN_GROUP = ["Entreprise", "Fonds des adhérents", "Combiné"]


def _takaful_column_names(n_cols):
    """Noms de colonnes pour un Bilan Combiné Takaful : le triplet
    Entreprise/Fonds des adhérents/Combiné, répété une fois par exercice
    (suffixe "(N-k)" à partir du 2e). None si `n_cols` n'est pas un
    multiple de 3 (gabarit différent de ce qui est attendu — mieux vaut
    laisser le repli générique plutôt que d'imposer des noms qui ne
    correspondent à rien)."""
    if not n_cols or n_cols % 3 != 0:
        return None
    names = []
    for r in range(n_cols // 3):
        suffix = "" if r == 0 else f" (N-{r})"
        names.extend(g + suffix for g in _TAKAFUL_COLUMN_GROUP)
    return names


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
_DASH_PLACEHOLDER_RE = re.compile(r"^[-‐‑–—]+$")


def _assign_columns(clusters, header_x, n_cols):
    """Affecte chaque valeur numérique trouvée sur la ligne (`clusters`,
    liste de (valeur, x0) triée gauche->droite) à l'index de colonne dont
    l'en-tête est le plus proche en x0 — jamais par position ordinale pure,
    pour ne pas décaler les colonnes suivantes quand une cellule est vide.
    Repli sur l'ordre d'apparition si les en-têtes n'ont pas pu être
    localisés (`header_x` vide).

    Repli POSITIONNEL (i-ème cluster -> i-ème colonne) quand le nombre de
    clusters trouvés égale exactement le nombre de colonnes attendues —
    découvert le 2026-09-17 (ATTIJARI, ligne de sous-total AC5 : Amort.=0,
    Net=1 105 004) : le rapprochement par x0 compare le bord GAUCHE de
    chaque cluster (`_extract_numeric_clusters`, x0 du 1er jeton) à celui
    de l'en-tête ; un très GRAND nombre juste après une colonne à "0" (donc
    bien plus large que sa voisine de gauche) démarre visuellement plus à
    gauche que sa propre colonne et se retrouve alors plus proche, en x0,
    de l'en-tête voisin — décalant 2 colonnes l'une sur l'autre alors
    qu'aucune cellule n'est vide. Quand le compte de clusters correspond
    exactement au nombre de colonnes, l'ordre de lecture gauche->droite
    suffit et ne peut pas se tromper ; le rapprochement par x0 reste le
    seul recours quand une cellule EST vraiment vide (compte différent)."""
    if not header_x:
        return {i: v for i, (v, _x0) in enumerate(clusters) if i < n_cols}
    if len(clusters) == len(header_x):
        return {i: v for i, (v, _x0) in enumerate(clusters)}
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
    colonnes, header_x = [], []
    if any(_TAKAFUL_HEADER_HINT_RE.search(_normalizer.clean(" ".join(w["text"] for w in line)))
           for line in lines[:25]):
        # Gabarit Takaful (voir _TAKAFUL_HEADER_HINT_RE) : le nombre de
        # colonnes vient du nombre de valeurs sur une VRAIE ligne de
        # détail (code AC/PA/CP/AN reconnu en tête), pas du comptage de
        # mots d'en-tête (peu fiable ici, voir le commentaire sur
        # `_TAKAFUL_HEADER_HINT_RE`).
        max_clusters = 0
        for line in lines:
            first = _normalizer.clean(line[0]["text"]) if line else ""
            if line and _ROW_CODE_RE.match(first):
                resolved = _words_with_bracket_negatives_resolved(line)
                no_notes = [w for w in resolved if not _NOTE_REF_TOKEN_RE.match(w["text"])]
                max_clusters = max(max_clusters, len(_extract_numeric_clusters(no_notes)))
        colonnes = _takaful_column_names(max_clusters) or []
    if not colonnes:
        colonnes, header_x = _header_columns(lines, side)
    if len(colonnes) < 2:
        # Repli si l'en-tête n'a pas pu être localisé de façon fiable (page
        # non conforme au gabarit attendu, OU en-tête bien présente mais mal
        # lue par l'OCR sur une page scannée — un seul jeton reconnu,
        # ex. "Amort" seul, sur les 3-4 attendus — constaté STAR 2025 :
        # TOUTES les valeurs de la page se retrouvaient alors assignées à
        # cette unique colonne, `_assign_columns` n'ayant qu'une position
        # possible). Nombre de colonnes générique, valeurs affectées par
        # ORDRE D'APPARITION plutôt que par proximité à un en-tête peu
        # fiable (voir `_assign_columns`, header_x vide) — dépend de l'ordre
        # X des cellules de la ligne de données elle-même, pas de la
        # qualité de lecture de la ligne d'en-tête.
        colonnes = (
            ["Brut", "Amortissements et provisions", "Net", "Net (N-1)"] if side == "actif"
            else ["Net", "Net (N-1)"]
        )
        header_x = []
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
    _TOP_SECTION_RE = re.compile(r"^(AC|PA|CP|AN)\d$")
    # Marqueur de sous-total de section abrégé ("A1", "A2"... côté Actif,
    # "P1", "P2"... côté Passif) SANS le préfixe complet AC/PA/CP — constaté
    # HAYETT, où chaque section se termine par une ligne "<lettre><chiffre>
    # <valeurs>" plutôt qu'un vrai code répété. Le chiffre imprimé n'est PAS
    # fiable (glyphe mal interprété par pdfplumber sur au moins un cas
    # constaté : 2 sections consécutives affichent toutes deux "A1") — on ne
    # s'appuie donc jamais sur lui, seulement sur le fait que la ligne n'est
    # QUE ce marqueur (`current_section`, déjà suivi indépendamment, fait foi).
    _SECTION_MARKER_RE = re.compile(r"^[a-z]\d{0,2}$")
    total_re = _TOTAL_ACTIF_RE if side == "actif" else _TOTAL_PASSIF_RE
    open_sections = []  # tous les codes de section top-level rencontrés, DANS
                         # L'ORDRE — sert à retrouver, pour une ligne de
                         # sous-total ambiguë (bare/marqueur), la section
                         # encore non résolue la plus récente PLUTÔT que
                         # `current_section` seul (voir plus bas et
                         # `sections_with_children`) : constaté MAGHREBIA_VIE,
                         # où le sous-total de AC3 (qui a des enfants) est
                         # imprimé APRÈS la ligne de AC4 (qui n'en a pas) —
                         # `current_section` a déjà avancé sur AC4 à ce
                         # moment, donc s'y fier seul perdrait le sous-total
                         # de AC3 en le laissant tomber dans la continuation.
    sections_with_children = set()  # une section top-level SANS aucun enfant
                         # (ex. CP1, CP2, CP4, CP6 — jamais de "CP12") porte
                         # déjà sa valeur réelle sur SA PROPRE ligne de code ;
                         # `_pending_section` ne la propose donc JAMAIS comme
                         # cible d'une ligne "Total ..."/"bare" (elle serait
                         # un cumul intermédiaire sans rapport, span plusieurs
                         # codes — écraserait à tort la vraie valeur de la
                         # section, constaté HAYETT/CP4).

    def _pending_section():
        for code in reversed(open_sections):
            if code in sections_with_children and code not in lignes:
                return code
        return None

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
        # Titre de section top-level SANS aucun numéro accolé, collé
        # directement au libellé ("ACActifs incorporels", constaté ASTREE
        # — contrairement à ses propres sous-postes, glués mais AVEC
        # numéro : "AC11,12,13Investissements..."). Le numéro de la section
        # apparaît ailleurs sur la même ligne comme une référence de note
        # séparée ("...incorporels A 1 3 089 682...") : une lettre isolée
        # reprenant l'initiale du préfixe, suivie du numéro (partie entière
        # seule si décimale, ex. "A 3.1" -> 3). Repéré puis recollé au
        # préfixe pour que le reste du traitement (identique à toutes les
        # autres lignes) le retrouve comme un vrai code "AC1".
        _bare_m = re.match(r"^(AC|PA|CP)([A-ZÀ-Ý].*)$", line[0]["text"])
        if _bare_m:
            initiale = _bare_m.group(1)[0]
            for i in range(1, len(line) - 1):
                if line[i]["text"] == initiale and re.match(r"^\d+(?:\.\d+)?$", line[i + 1]["text"]):
                    section_num = line[i + 1]["text"].split(".")[0]
                    line = [
                        {**line[0], "text": _bare_m.group(1) + section_num + _bare_m.group(2)},
                        *line[1:i], *line[i + 2:],
                    ]
                    break
        # Résolution des négatifs entre parenthèses/chevrons AVANT de
        # distinguer libellé/valeurs — sinon "(95" et "277)" (fragments
        # d'un "(95 854 277)" comptable) ne matchent ni l'un ni l'autre et
        # se retrouvent inclus à tort dans le libellé reconstruit (constaté
        # sur la ligne "Total des actifs" de GAT : le résidu "(95 277)"
        # dans le texte empêchait sa reconnaissance comme ligne de total).
        resolved_line = _words_with_bracket_negatives_resolved(line)
        # Un "-" isolé (case "néant" placeholder, très fréquent dans ces
        # tableaux — ex. "AC540... - - -") ne matche pas NUMERIC_TOKEN_RE
        # (qui exige au moins 1 chiffre) et se retrouvait donc à tort dans
        # le libellé reconstruit — un sous-total de section fait seulement
        # de chiffres ET de "-" isolés (Amort/Net non ventilé) ressortait
        # alors avec un texte non vide ("-"), ratant la détection "ligne
        # de sous-total sans libellé" (constaté BIAT/AC5).
        label_words = [
            w for w in resolved_line
            if not NUMERIC_TOKEN_RE.match(w["text"]) and not _DASH_PLACEHOLDER_RE.match(w["text"])
        ]
        line_no_notes = [w for w in resolved_line if not _NOTE_REF_TOKEN_RE.match(w["text"])]
        if not header_x:
            # Repli ordinal (header_x vide, voir `_assign_columns`) : un "-"
            # isolé (placeholder "néant") doit compter comme un ZÉRO
            # explicite à SA position, sinon `_extract_numeric_clusters`
            # l'ignore silencieusement (ne matche pas NUMERIC_TOKEN_RE) et
            # décale toutes les valeurs suivantes d'une colonne vers la
            # gauche — constaté Takaful (AT_TAKAFULIA) : une ligne à 6
            # colonnes attendues n'en produisait que 4 dès qu'un "-"
            # apparaissait au milieu ("... ‐ 394 477 394 477 ‐ 488 919
            # 488 919"). Sans effet en mode position (l'affectation par
            # proximité à l'en-tête, voir `_assign_columns`, ne dépend
            # jamais d'un compte ordinal).
            line_no_notes = [
                {**w, "text": "0"} if _DASH_PLACEHOLDER_RE.match(w["text"]) else w
                for w in line_no_notes
            ]
        clusters = _extract_numeric_clusters(line_no_notes)
        text_norm = _normalizer.clean(" ".join(w["text"] for w in label_words))
        if side == "passif" and _TOTAL_CP_RE.match(text_norm):
            # "Total capitaux propres (avant affectation)" — sous-total
            # imprimé CP1..CP6 inclus (voir _TOTAL_CP_RE) : jamais rattaché
            # au dernier code CP rencontré (comme les autres lignes de
            # total), pour rester disponible comme SA PROPRE cellule
            # ("TOTAL_CP") — but NE PERTURBE PAS la détection ultérieure de
            # "Total capitaux propres et passifs" (_TOTAL_GENERAL_RE, texte
            # different) ni de "Total (du passif)" bare (total_re).
            _flush()
            current_code = None
            lignes["TOTAL_CP"] = _assign_columns(clusters, header_x, n_cols)
            label_by_code["TOTAL_CP"] = text_norm
            continue
        if side == "passif" and _TOTAL_AN_RE.match(text_norm):
            # "Total des Actifs Nets des adhérents" (Takaful) — même
            # traitement que TOTAL_CP ci-dessus, pour la section AN.
            _flush()
            current_code = None
            lignes["TOTAL_AN"] = _assign_columns(clusters, header_x, n_cols)
            label_by_code["TOTAL_AN"] = text_norm
            continue
        if total_re.match(text_norm) or (side == "passif" and _TOTAL_GENERAL_RE.match(text_norm)):
            # Ligne de TOTAL général — jamais préfixée d'un code, traitée à
            # part pour ne jamais se retrouver fusionnée avec la dernière
            # section rencontrée (sinon ses valeurs, arrivant après que
            # cette section ait déjà les siennes, seraient silencieusement
            # ignorées par le `setdefault` de la branche "continuation").
            _flush()
            current_code = None
            key = "TOTAL" if total_re.match(text_norm) else "TOTAL_GENERAL"
            values = _assign_columns(clusters, header_x, n_cols)
            if side == "passif" and key == "TOTAL":
                # Ligne "Total (du passif)" parfois en réalité le total
                # GÉNÉRAL (Capitaux propres + Passif) sans que le libellé le
                # précise (juste "Total" tout court, constaté
                # LLOYD_TUNISIEN — même absence de vrai "Total du Passif"
                # isolé que BIAT/ASTREE, mais sans le libellé combiné
                # explicite qui permettrait de le détecter par le texte).
                # Désambiguïsé par la VALEUR plutôt que par le texte : les CP
                # précèdent toujours les PA dans le document, donc Σ CP et Σ
                # PA déjà rencontrés à ce stade sont comparés à cette ligne —
                # on garde l'hypothèse la plus proche numériquement.
                sum_pa, sum_cp = {}, {}
                for code, vals in lignes.items():
                    target = sum_pa if _TOP_PASSIF_RE.match(code) else sum_cp if _TOP_CP_RE.match(code) else None
                    if target is not None:
                        for i, v in vals.items():
                            target[i] = target.get(i, 0) + v
                diff_pa = sum(abs(values.get(i, 0) - sum_pa.get(i, 0)) for i in values)
                diff_general = sum(abs(values.get(i, 0) - sum_pa.get(i, 0) - sum_cp.get(i, 0)) for i in values)
                if diff_general < diff_pa:
                    key = "TOTAL_GENERAL"
            lignes[key] = values
            label_by_code[key] = text_norm
            continue
        m = _ROW_CODE_RE.match(text_norm)
        if m:
            _flush()
            current_code = f"{m.group(1).upper()}{m.group(2)}"
            if _TOP_SECTION_RE.match(current_code):
                current_section = current_code
                open_sections.append(current_code)
            elif current_section and current_code != current_section and current_code.startswith(current_section):
                sections_with_children.add(current_section)
            rest = text_norm[m.end():].strip()
            if rest and current_code not in label_by_code:
                label_by_code[current_code] = rest
            current_values = _assign_columns(clusters, header_x, n_cols)
        elif ((not text_norm or _SECTION_MARKER_RE.match(text_norm))
              and _pending_section() is not None
              and len(clusters) >= max(2, n_cols - 1)):
            # Ligne de sous-total de section SANS code complet : soit
            # totalement "bare" (juste des chiffres), soit portant un
            # marqueur abrégé façon "A1"/"P2" (constaté HAYETT — voir
            # _SECTION_MARKER_RE) — rattachée à la section ENCORE NON
            # RÉSOLUE la plus récente (`_pending_section`, pas forcément
            # `current_section` : voir MAGHREBIA_VIE, où le sous-total de
            # AC3 est imprimé après la ligne AC4), seulement si (a) une telle
            # section existe et a RÉELLEMENT des enfants (sinon sa propre
            # ligne de code porte déjà la valeur, voir plus bas), (b) elle
            # n'a pas encore sa propre valeur, ET (c) la ligne porte (presque)
            # autant de valeurs que de colonnes attendues (`n_cols - 1` au
            # minimum) : un sous-total légitime remplit toutes les colonnes,
            # alors qu'une VRAIE ligne de détail sans
            # libellé récupéré (rare, ex. une valeur "0" esseulée constatée
            # sur MAGHREBIA/AC64) n'en a typiquement qu'une — la prendre pour
            # le sous-total aurait perdu le vrai total, arrivant juste après,
            # en le trouvant déjà "pris".
            lignes[_pending_section()] = _assign_columns(clusters, header_x, n_cols)
        elif text_norm.startswith("total") and _pending_section() is not None:
            # Sous-total de SECTION avec libellé explicite ("Total actifs
            # incorporels", "TOTAL PLACEMENTS"...), à distinguer du cas
            # juste au-dessus (ligne "bare", sans aucun texte). Gabarit très
            # fréquent (constaté HAYETT, MAGHREBIA_VIE, CARTE, CARTE_VIE,
            # LLOYD_TUNISIEN, Takaful...) où chaque section a sa PROPRE
            # ligne de sous-total, distincte de tous ses postes de détail —
            # sans cette branche, ce texte ne matche ni un code
            # (_ROW_CODE_RE) ni la ligne "bare" (text_norm non vide ici), et
            # se retrouvait absorbé à tort dans le DERNIER code de détail
            # rencontré (branche "continuation" ci-dessous, via
            # `setdefault`) — perdant silencieusement le sous-total de
            # section (Σ sections ≠ Total, constaté sur ~19 sociétés).
            section = _pending_section()
            if section == current_section:
                _flush()
                current_code = None
            lignes[section] = _assign_columns(clusters, header_x, n_cols)
            label_by_code[section] = text_norm
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
    grille complète. Renvoie (numero_page_1_indexe, grille) ou (None, None).

    Chaque page est enveloppée par `_OcrFallbackPage` (déjà construit et
    éprouvé pour l'extracteur KPI narrow — voir bilan_kpi_extractor.py, et
    son commentaire sur STAR 2025 : Bilan Actif = page image pure, aucun
    texte natif) : transparent tant que le texte natif de la page suffit,
    et ne déclenche l'OCR (coûteux) QUE si `extract_text()`/`extract_words()`
    natifs sont vides — donc sans coût sur les documents déjà natifs.
    `_is_target_page` (repérage) ET `extract_bilan_full_grid` (extraction)
    en profitent tous les deux sans aucune modification : ils appellent
    seulement `page.extract_text()`/`page.extract_words()`, peu importe
    d'où vient réellement le texte."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            ocr_page = _OcrFallbackPage(page)
            if not _is_target_page(ocr_page, side):
                continue
            grid = extract_bilan_full_grid(ocr_page, side)
            if grid is not None:
                return i + 1, grid
    return None, None


# Codes de section TOP-LEVEL par côté (1 seul chiffre après le préfixe,
# ex. AC1, PA3) — utilisés pour les 3 identités comptables de base
# vérifiées ci-dessous. Volontairement peu ambitieux pour une 1ère
# version (voir CAS_PARTICULIERS_BILAN_FULL_TABLE.md) : suffisant pour
# détecter une extraction structurellement cassée (Σ sections ≠ Total),
# pas une vérification exhaustive poste par poste comme Annexe 12/13.
_TOP_ACTIF_RE = re.compile(r"^AC\d$")
_TOP_PASSIF_RE = re.compile(r"^PA\d$")
_TOP_CP_RE = re.compile(r"^CP\d$")


def _bilan_validations(grid_actif, grid_passif):
    """3 identités de contrôle, même contrat que
    `annexe13_pipeline.validate_table` ({regle_code, regle, colonne,
    attendu, trouve, ecart, statut}) : Σ sections Actif = Total Actif,
    Σ sections Passif = Total du Passif (si imprimé séparément), et
    Σ (Capitaux propres + Passif) = Total général (Actif ou combiné)."""
    results = []

    def _add(rule_code, rule_desc, colonne, attendu, trouve):
        if attendu is None or trouve is None:
            results.append({"regle_code": rule_code, "regle": rule_desc, "colonne": colonne,
                             "attendu": None, "trouve": None, "ecart": None,
                             "statut": "donnees_manquantes"})
            return
        ecart = round(trouve - attendu, 2)
        results.append({"regle_code": rule_code, "regle": rule_desc, "colonne": colonne,
                         "attendu": round(attendu, 2), "trouve": round(trouve, 2),
                         "ecart": ecart, "statut": "ok" if abs(ecart) <= 2 else "ecart"})

    if grid_actif:
        total = grid_actif["lignes"].get("TOTAL") or grid_actif["lignes"].get("TOTAL_GENERAL")
        top = {c: v for c, v in grid_actif["lignes"].items() if _TOP_ACTIF_RE.match(c)}
        for col in grid_actif["colonnes"]:
            attendu = sum(v.get(col, 0) for v in top.values()) if top else None
            _add("bilan_actif_total", "Σ sections Actif = Total de l'actif", col,
                 attendu, total.get(col) if total else None)

    if grid_passif:
        top_pa = {c: v for c, v in grid_passif["lignes"].items() if _TOP_PASSIF_RE.match(c)}
        total_pa = grid_passif["lignes"].get("TOTAL")
        if total_pa:  # certains documents n'imprimment jamais ce total isolé (BIAT, ASTREE)
            for col in grid_passif["colonnes"]:
                attendu = sum(v.get(col, 0) for v in top_pa.values()) if top_pa else None
                _add("bilan_passif_total", "Σ sections Passif = Total du passif", col,
                     attendu, total_pa.get(col))

        total_general = grid_passif["lignes"].get("TOTAL_GENERAL") or (
            grid_actif["lignes"].get("TOTAL") if grid_actif else None
        )
        if total_general:
            top_cp = {c: v for c, v in grid_passif["lignes"].items() if _TOP_CP_RE.match(c)}
            for col in grid_passif["colonnes"]:
                attendu = (sum(v.get(col, 0) for v in top_pa.values()) if top_pa else 0) + \
                          (sum(v.get(col, 0) for v in top_cp.values()) if top_cp else 0)
                _add("bilan_general_total", "Capitaux propres + Total du passif = Total général", col,
                     attendu or None, total_general.get(col))

    return results


def process_bilan(pdf_path):
    """Pipeline complète pour un document : localise + extrait l'Actif ET
    le Passif (voir `locate_and_extract_bilan`). Renvoie DEUX résultats
    INDÉPENDANTS — {"actif": {...} | None, "passif": {...} | None}, chacun
    au même contrat que `annexe13_pipeline.process_annexe13`
    ({page, colonnes, lignes, validations}) — plutôt qu'une grille
    fusionnée : le Bilan Actif et le Bilan Passif sont deux tableaux
    distincts dans le PDF source (souvent des pages différentes, chacun
    avec son propre total), stockés sous deux clés séparées
    (tableau='bilan_actif' / 'bilan_passif') pour préserver cette
    structure plutôt que de la masquer derrière un seul tableau combiné.
    Renvoie None (au lieu du dict) seulement si NI l'Actif NI le Passif
    n'ont pu être extraits (ex. pages scannées/texte cassé — voir
    CAS_PARTICULIERS_BILAN_FULL_TABLE.md)."""
    page_actif, grid_actif = locate_and_extract_bilan(pdf_path, "actif")
    page_passif, grid_passif = locate_and_extract_bilan(pdf_path, "passif")
    if grid_actif is None and grid_passif is None:
        return None

    validations = _bilan_validations(grid_actif, grid_passif)
    validations_actif = [v for v in validations if v["regle_code"] == "bilan_actif_total"]
    validations_passif = [v for v in validations if v["regle_code"] != "bilan_actif_total"]

    def _build(page, grid, validations_cote):
        if not grid:
            return None
        lignes = {}
        for code, vals in grid["lignes"].items():
            libelle = vals.get("libelle") or code
            key = f"{code} — {libelle.capitalize()}" if libelle != code else code
            lignes[key] = {c: v for c, v in vals.items() if c != "libelle"}
        return {"page": page, "colonnes": grid["colonnes"], "lignes": lignes,
                "validations": validations_cote}

    return {
        "actif": _build(page_actif, grid_actif, validations_actif),
        "passif": _build(page_passif, grid_passif, validations_passif),
    }
