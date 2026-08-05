"""
Extraction ciblée du tableau "Bilan" (état financier annuel au 31/12) d'un
PDF CMF : récupère, pour l'année en cours, l'ensemble des KPI définis dans
KPI_DEFINITIONS (Total actif, Capitaux propres, Total Passif, et les
sections/lignes du Bilan Actif et Passif — voir extraction/CAS_PARTICULIERS.md
pour l'historique des cas particuliers rencontrés).

Les tableaux des PDF CMF sont mis en page de façon incohérente d'une société
à l'autre (cellules fusionnées, alignements variables, libellé de la ligne
totale parfois réduit à "Total", nombre de sous-colonnes brut/amortissements
variable) : `extract_tables()` de pdfplumber échoue sur plusieurs documents
réels testés. On reconstruit donc les lignes visuelles à partir de la
position des mots (`extract_words`), et on résout la colonne cible à partir
des en-têtes ("Net" le plus à gauche = année en cours côté Actif ; sinon la
colonne la plus à gauche = année en cours côté Passif) plutôt que par une
position fixe dans la ligne.

Deux façons de repérer la valeur d'un KPI, selon sa nature :
  - "direct" : la valeur est sur la même ligne que le libellé (ou sur l'une
    des 2 lignes suivantes, en cas de libellé replié sur plusieurs lignes) —
    utilisé pour les totaux généraux et les lignes de détail (ex: AC331
    "Actions, autres titres à revenu variable").
  - "section" : le libellé est un titre de section de premier niveau du plan
    comptable réglementaire (AC1..AC7 côté Actif, PA1..PA7 côté Passif) —
    ces codes sont standardisés par la réglementation tunisienne et
    identiques chez toutes les sociétés, ce qui permet de les utiliser comme
    ancres fiables. La valeur de la section est la DERNIÈRE ligne portant des
    chiffres avant le début de la section suivante (gère aussi bien le cas
    où le total est sur la ligne de titre elle-même, sur une ligne juste en
    dessous, ou après plusieurs sous-totaux imbriqués).
"""

import io
import re

import requests

from utils.text_normalizer import TextNormalizer

_normalizer = TextNormalizer()

# Motifs recherchés (après normalisation : minuscules, sans accents, sans
# ponctuation), sous forme de regex pour tolérer les variantes constatées
# d'une société à l'autre (article "des"/"de l'" optionnel, singulier/pluriel).
TOTAL_ACTIF_RE = re.compile(r"^total (de l |des )?actifs?\b")
# "Total capitaux propres avant résultat de l'exercice" est une ligne
# INTERMÉDIAIRE (avant d'ajouter le résultat de l'exercice en cours) —
# presque tous les documents ont ensuite une ligne "avant affectation", le
# vrai total final. Chercher "av(ant)? resultat" sans distinction faisait
# remonter la valeur intermédiaire chez des sociétés qui ont les deux lignes
# (ex: BIAT 2025 : 103,1M extraits au lieu de 128,8M, sous-estimant les
# capitaux propres — donc surestimant le ROE affiché — exactement du montant
# du résultat de l'exercice). Voir _find_capitaux_propres : la ligne "avant
# affectation" est maintenant cherchée en priorité.
TOTAL_CAPITAUX_PROPRES_AFFECTATION_RE = re.compile(r"^total (des )?(capitaux propres|cp) av(ant)? affectation\b")
TOTAL_CAPITAUX_PROPRES_RE = re.compile(r"^total (des )?(capitaux propres|cp) av(ant)? resultat\b")
TOTAL_PASSIF_RE = re.compile(r"^total (du |des )?passifs?\b")
# Pas de \b/^ en tête : comme pour les sections, le code de ligne (ex:
# "AC332") est parfois collé sans séparateur au libellé (ex: "ac33autres
# placements financiers" chez ASTREE) — on cherche donc une sous-chaîne
# (voir _find_row_value, qui utilise .search() et non .match()).
OBLIGATIONS_RE = re.compile(r"obligations et autres titres")
ACTIONS_PARTICIPATION_RE = re.compile(r"actions,? ?autres titres a revenu variable")
OPCVM_RE = re.compile(r"autres placements financiers")
# S'arrête avant "et caisse" : ce libellé se coupe parfois sur 2 lignes juste
# avant ce mot (ex: STAR), le reste du motif restant intact sur la 1ère ligne.
DEPOTS_LIQUIDITE_RE = re.compile(r"avoirs en banques?,? ?ccp,? ?ch[eè]ques")

ACTIF_PAGE_TITLE_RE = re.compile(r"\bactifs?\b")
PASSIF_PAGE_TITLE_RE = re.compile(r"\bpassifs?\b")
# Codes de section de premier niveau du plan comptable réglementaire tunisien
# des assurances (ex: "AC3 Placements", "PA7 Autres passifs") : un chiffre
# unique après le préfixe (le \b empêche de matcher "AC31", "AC331"...).
SECTION_CODE_RE = re.compile(r"^(ac|pa)([1-7])\b")
# Les libellés de lignes de détail sont souvent précédés du code de la ligne
# (ex: "AC332 Obligations..." -> "ac332 obligations...") : on l'enlève avant
# de comparer aux motifs, pour ne pas avoir à répéter tous les codes possibles
# dans chaque motif.
ROW_CODE_PREFIX_RE = re.compile(r"^(ac|pa|cp)\d+\s+")

# Repli utilisé quand le code de section (AC1..AC7/PA1..PA7) n'est pas
# détectable tel quel dans le texte extrait (ex: chiffre du code absent ou
# collé sans espace au libellé — constaté chez ASTREE, BH) : on identifie
# alors directement les titres de section par leur texte, dans l'ordre où le
# plan comptable réglementaire les présente. Les motifs excluent
# explicitement les libellés de sous-éléments qui contiennent le même mot
# (ex: "AC34 Créances pour espèces déposées..." est un sous-élément de
# Placements/AC3, pas le début de la section Créances/AC6).
# Pas de \b en début de motif : le code de ligne est parfois collé sans
# aucun séparateur au libellé (ex: "ac3placements", "acactifs incorporels"
# chez ASTREE) — un chiffre ou une lettre collés juste avant empêchent une
# frontière de mot regex de s'y trouver. On recherche donc une simple
# sous-chaîne, et c'est l'heuristique "libellé le plus court" (voir
# _section_starts_for_page) qui distingue le titre de section de ses
# sous-éléments contenant le même mot.
ACTIF_SECTION_TEXT_PATTERNS = [
    ("1", re.compile(r"actifs incorporels")),
    ("2", re.compile(r"actifs corporels")),
    ("3", re.compile(r"placements")),
    ("4", re.compile(r"placements representant")),
    ("5", re.compile(r"parts? des reassureurs dans les provisions")),
    ("6", re.compile(r"creances")),
    ("7", re.compile(r"autres elements d actifs?")),
]
PASSIF_SECTION_TEXT_PATTERNS = [
    ("3", re.compile(r"provisions techniques brutes")),
    ("7", re.compile(r"autres passifs")),
]

MAX_PAGES_SCANNED = 12   # le Bilan se trouve systématiquement en tête de document
# Fenêtre restreinte pour les recherches spécifiquement filtrées par
# _is_actif_page/_is_passif_page (Total actif, Total Passif, et leurs replis).
# Sur l'ensemble des 186 PDF CMF locaux, la page "Actif" du Bilan est TOUJOURS
# en position 0-2 (indexée à partir de 0) et la page "Passif" toujours en
# position 0-3 ; tout ce qui se présente comme "page actif/passif" au-delà
# (constaté en positions 5 à 9) est un faux positif : une page d'annexe/notes
# mentionnant "actif"/"passif" en passant dans une phrase (ex: "Tableau des
# engagements reçus et donnés" contient "...actifs acquis avec engagement de
# revente"). Avec la fenêtre large MAX_PAGES_SCANNED=12, un tel faux positif
# pouvait faire remonter une valeur erronée (ex: MAGHREBIA_VIE 2018/2020,
# Total actif=0 capté sur une ligne "TOTAL 0 0" sans rapport, au lieu de
# rester introuvable/None) via _find_actif_bare_total_fallback. Découvert en
# comparant l'extraction avant/après sur l'ensemble du corpus après
# l'élargissement de lines_checked (5->10, voir _is_actif_page) fait pour
# BIAT 2025.
BILAN_TOTAL_MAX_PAGES = 4
Y_TOLERANCE = 5          # tolérance (pt) pour regrouper les mots d'une même ligne visuelle
# Écart horizontal entre deux tokens numériques consécutifs : ~1-2.3pt à
# l'intérieur d'un même nombre (séparateur de milliers), ~8-45pt entre deux
# colonnes distinctes (constaté sur plusieurs PDF réels, la valeur basse de
# 8pt provenant d'un document aux colonnes resserrées) : 4 sépare proprement
# les deux cas avec une marge confortable des deux côtés.
NUMBER_GAP_THRESHOLD = 4
# Un token numérique peut porter une partie décimale séparée par une virgule
# (ex: "113,026" chez certaines sociétés qui expriment les millimes).
# Le signe négatif n'est pas toujours le tiret ASCII standard : certains
# documents (ex: COMAR) utilisent le caractère Unicode HYPHEN (U+2010) ou des
# variantes de tiret similaires — on les tolère toutes, puis on les
# normalise en "-" ASCII avant conversion en nombre (voir _extract_numeric_clusters).
MINUS_CHARS = "‐‑‒–—−"
# Format virgule-décimale : "113,026" (un seul groupe → millimes tunisiens).
# Format américain multi-groupes : "13,966,819.225" (virgule = milliers, point
# = décimale) — rencontré dans les PDF COTUNACE 2021 et similaires.
NUMERIC_TOKEN_RE = re.compile(rf"^[-{MINUS_CHARS}]?\d+(?:,\d+)*(?:\.\d+)?$")
_MINUS_NORMALIZE_RE = re.compile(f"[{MINUS_CHARS}]")
# Deux nombres consécutifs sans aucun espace entre eux, le second étant
# négatif (ex: "104-1" = fin de "...350 104" suivi du début de "-1 144...")
# : rencontré dans les tableaux très denses (ex: FTUSA). Un seul mot PDF
# porte alors les deux nombres, ce qui ne correspond à aucun NUMERIC_TOKEN_RE
# valide (le signe n'est pas en tête) -> _extract_numeric_clusters l'exclut
# et les deux nombres sont perdus si on ne le sépare pas explicitement.
_GLUED_NEGATIVE_RE = re.compile(rf"^(\d+)([-{MINUS_CHARS}]\d+(?:,\d+)?)$")
# Fin d'un montant entre parenthèses (colonne Amortissements/Provisions)
# collée sans espace au début du nombre suivant (ex: "769,278)426" = fin de
# "(66 442 769,278)" + début de "426 512 304,411" — rencontré chez GAT 2018).
# Un seul mot PDF porte alors la fin d'un nombre, la parenthèse fermante, et
# le début du nombre suivant : ni NUMERIC_TOKEN_RE (la ")" au milieu ne
# correspond à aucun format valide) ni _words_with_bracket_negatives_resolved
# (qui ne traite que les mots commençant par "(" ou finissant par ")", pas
# les deux à la fois avec du texte après) ne le gèrent -> le mot est perdu
# tel quel, ce qui décale aussi le regroupement des colonnes suivantes.
_GLUED_CLOSE_PAREN_RE = re.compile(r"^(\d+(?:,\d+)?)\)(\d+)$")
# Aucune société d'assurance tunisienne n'approche cet ordre de grandeur (en
# dinars) : une valeur qui le dépasse trahit une erreur d'extraction (nombres
# fusionnés) plutôt qu'un vrai montant — on la rejette plutôt que de renvoyer
# un chiffre faux.
MAX_PLAUSIBLE_VALUE = 50_000_000_000
# Symétriquement : aucune ligne du Bilan/Annexe/État de résultat (totaux
# généraux, totaux de section, lignes de détail) ne descend légitimement en
# dessous de ce seuil (en dinars) — un chiffre non-nul plus petit trahit
# presque toujours un renvoi de note ou un numéro de page/ligne capturé par
# erreur à la place du vrai montant (cas documentés dans CAS_PARTICULIERS*.md :
# COTUNACE "Charges de prestations" = 20.0, TUNIS_RE 2024 = 2.0 partout à
# cause du format "." comme séparateur de milliers). Un vrai zéro (section
# légitimement vide, ex: pas de contrats en unités de compte) reste accepté.
MIN_PLAUSIBLE_VALUE = 1000


def _is_plausible(value):
    """Filtre symétrique à MAX_PLAUSIBLE_VALUE : rejette les valeurs non
    nulles trop petites pour être un vrai montant (voir MIN_PLAUSIBLE_VALUE),
    sans jamais rejeter un vrai zéro."""
    if value is None:
        return True
    return value == 0 or MIN_PLAUSIBLE_VALUE <= abs(value) <= MAX_PLAUSIBLE_VALUE

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _cluster_lines(words, y_tolerance=Y_TOLERANCE):
    """Regroupe les mots d'une page en lignes visuelles selon leur position
    verticale (deux mots dont le 'top' diffère de moins de y_tolerance sont
    considérés comme faisant partie de la même ligne)."""
    words_sorted = sorted(words, key=lambda w: w["top"])
    lines, current, current_top = [], [], None
    for w in words_sorted:
        if current_top is None or abs(w["top"] - current_top) <= y_tolerance:
            current.append(w)
            current_top = current_top if current_top is not None else w["top"]
        else:
            lines.append(current)
            current, current_top = [w], w["top"]
    if current:
        lines.append(current)
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return lines


def _words_with_bracket_negatives_resolved(line):
    """Certains documents notent les valeurs négatives entre chevrons
    ("< 2 094 225>", ex: ASTREE) ou entre parenthèses ("(84 334 072)",
    convention comptable courante — ex: GAT). Dans les deux cas, le premier
    groupe de chiffres suivant le symbole ouvrant est préfixé d'un "-",
    et les symboles eux-mêmes sont retirés."""
    resolved = []
    pending_negative = False
    for w in line:
        text = w["text"]
        changed = False
        if text.startswith("<") or text.startswith("("):
            text = text[1:]
            changed = True
            if not text:
                pending_negative = True
                continue
            pending_negative = True
        if text.endswith(">") or text.endswith(")"):
            text = text[:-1]
            changed = True
        if pending_negative and re.match(r"^\d", text):
            text = "-" + text
            pending_negative = False
            changed = True
        resolved.append({**w, "text": text} if changed else w)
    return resolved


def _split_glued_negative(word, gap_threshold=NUMBER_GAP_THRESHOLD):
    """Sépare un mot comme "104-1" en deux tokens numériques distincts (voir
    _GLUED_NEGATIVE_RE). Le point de coupe (x0/x1) est arbitraire à
    l'intérieur du mot d'origine, mais l'écart entre les deux moitiés est
    fixé au-delà de gap_threshold pour forcer la clôture du cluster en
    cours ; les bornes externes (x0 du premier, x1 du second) restent
    celles du mot d'origine pour ne pas fausser les écarts avec leurs
    véritables voisins."""
    m = _GLUED_NEGATIVE_RE.match(word["text"])
    if not m:
        return [word]
    mid = (word["x0"] + word["x1"]) / 2
    first = {**word, "text": m.group(1), "x1": mid}
    second = {**word, "text": m.group(2), "x0": mid + gap_threshold + 1}
    return [first, second]


def _split_glued_close_paren(word, gap_threshold=NUMBER_GAP_THRESHOLD):
    """Sépare un mot comme "769,278)426" en deux tokens numériques distincts
    (voir _GLUED_CLOSE_PAREN_RE). Même logique de découpe que
    _split_glued_negative ; la parenthèse fermante est simplement retirée
    (le signe négatif du montant entre parenthèses a déjà été posé sur le
    mot ouvrant "(..." par _words_with_bracket_negatives_resolved, qui
    s'exécute avant cette fonction)."""
    m = _GLUED_CLOSE_PAREN_RE.match(word["text"])
    if not m:
        return [word]
    mid = (word["x0"] + word["x1"]) / 2
    first = {**word, "text": m.group(1), "x1": mid}
    second = {**word, "text": m.group(2), "x0": mid + gap_threshold + 1}
    return [first, second]


def _extract_numeric_clusters(line, gap_threshold=NUMBER_GAP_THRESHOLD):
    """Regroupe les tokens numériques consécutifs d'une ligne (séparateur de
    milliers = espace) en nombres complets, dans l'ordre d'apparition
    (gauche à droite = colonnes du tableau). Renvoie une liste de
    (valeur, x0_premier_token)."""
    line = _words_with_bracket_negatives_resolved(line)
    once_split = [split_word for w in line for split_word in _split_glued_negative(w, gap_threshold)]
    expanded = [
        split_word for w in once_split for split_word in _split_glued_close_paren(w, gap_threshold)
    ]
    numeric_words = [w for w in expanded if NUMERIC_TOKEN_RE.match(w["text"])]
    clusters, current_tokens, prev_x1 = [], [], None
    for w in numeric_words:
        # >= et non > : un ecart EXACTEMENT egal au seuil (ex: GAT 2018, 4.0pt
        # pile) doit encore etre traite comme une frontiere de colonne, pas
        # comme un chevauchement a l'interieur d'un meme nombre.
        if prev_x1 is not None and (w["x0"] - prev_x1) >= gap_threshold:
            clusters.append(current_tokens)
            current_tokens = []
        current_tokens.append(w)
        prev_x1 = w["x1"]
    if current_tokens:
        clusters.append(current_tokens)

    values = []
    for tokens in clusters:
        raw = _MINUS_NORMALIZE_RE.sub("-", "".join(w["text"] for w in tokens))
        num_str = raw.lstrip("-")
        if "." not in num_str and num_str.count(",") > 1:
            # Plusieurs nombres au format tunisien (une seule virgule chacun)
            # colles dans le meme cluster : l'ecart entre deux colonnes est
            # plus etroit que gap_threshold pour ce document precis (ex: GAT,
            # CARTE 2018 — colonnes Net courant/Net precedent tres resserrees)
            # et n'a donc pas ete detecte comme une frontiere. Chaque token
            # contenant une virgule termine un nombre distinct : on resegmente
            # plutot que d'abandonner tout le cluster (perte des 2 valeurs).
            sub_start = 0
            for i, w in enumerate(tokens):
                if "," in w["text"]:
                    _append_parsed_value(values, tokens[sub_start:i + 1])
                    sub_start = i + 1
            continue
        value = _parse_number(num_str, negative=raw.startswith("-"))
        if value is None:
            continue
        values.append((value, tokens[0]["x0"]))
    return values


def _parse_number(num_str, negative):
    """Convertit `num_str` (deja debarrasse d'un eventuel signe en tete) en
    float selon la convention detectee (americain point-decimal, tunisien
    virgule-decimale, ou entier simple). Renvoie None si invalide ou hors
    plage plausible (voir MAX_PLAUSIBLE_VALUE)."""
    try:
        if "." in num_str and "," in num_str:
            # Format américain : "13,966,819.225" — virgule = milliers, point = décimale
            value = float(num_str.replace(",", ""))
        elif "," in num_str:
            # Format tunisien/français : "113,026" — virgule = décimale
            value = float(num_str.replace(",", "."))
        else:
            value = float(num_str)
    except ValueError:
        return None
    if negative:
        value = -value
    return value if abs(value) <= MAX_PLAUSIBLE_VALUE else None


def _append_parsed_value(values, tokens):
    raw = _MINUS_NORMALIZE_RE.sub("-", "".join(w["text"] for w in tokens))
    value = _parse_number(raw.lstrip("-"), negative=raw.startswith("-"))
    if value is not None:
        values.append((value, tokens[0]["x0"]))


def _label_text(line):
    """Texte normalisé des mots non-numériques d'une ligne, sans le préfixe
    de code de ligne éventuel (ex: "AC332 Obligations..." -> "obligations...").
    Renvoie None si la ligne ne contient aucun mot non-numérique."""
    label_words = [w for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
    if not label_words:
        return None
    normalized = _normalizer.clean(" ".join(w["text"] for w in label_words))
    return ROW_CODE_PREFIX_RE.sub("", normalized, count=1)


def _section_code(line):
    """Renvoie ("ac"|"pa", "1".."7") si la ligne est un titre de section de
    premier niveau (le code n'est PAS retiré ici, contrairement à
    _label_text, car c'est justement ce qu'on cherche à identifier).
    Exige du texte après le code : certains documents (ex: COMAR) répètent
    le code seul ("AC1") sur la ligne de total de la section, ce qui ne doit
    pas être pris pour le début d'une NOUVELLE section (sinon la plage de la
    section précédente est coupée avant d'atteindre son propre total)."""
    label_words = [w for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
    if not label_words:
        return None
    normalized = _normalizer.clean(" ".join(w["text"] for w in label_words))
    m = SECTION_CODE_RE.match(normalized)
    if not m or not normalized[m.end():].strip():
        return None
    return (m.group(1), m.group(2))


def _leftmost_header_x(lines, target_top, token_normalized):
    """Parmi les lignes situées au-dessus de `target_top` (en-têtes),
    renvoie la position x0 la plus à gauche d'un mot dont le texte normalisé
    est exactement `token_normalized` (ex: "net")."""
    positions = []
    for line in lines:
        if line[0]["top"] >= target_top:
            continue
        for w in line:
            if _normalizer.clean(w["text"]) == token_normalized:
                positions.append(w["x0"])
    return min(positions) if positions else None


def _select_column_value(clusters, lines, target_top, header_token):
    """Sélectionne, parmi les colonnes numériques trouvées sur la ligne,
    celle correspondant à l'année en cours :
      - côté Passif (header_token=None) : toujours la première colonne, la
        plus à gauche (les tableaux Passif/Capitaux propres n'ont pas de
        ventilation brut/amortissements, l'année en cours y est toujours en
        premier) ;
      - côté Actif (header_token="net") : par convention du modèle CMF,
        l'avant-dernière colonne est le "net" de l'année en cours (les
        colonnes précédentes forment la ventilation brut/amortissements/net
        de l'année en cours, la dernière étant le "net" de l'année
        précédente) — fiable tant qu'il y a au plus 4 colonnes. Au-delà (une
        poignée de documents ventilent aussi brut/amortissements pour
        l'année précédente, soit 6 colonnes), la position ordinale devient
        ambiguë : on résout alors via la position du premier en-tête "net"
        rencontré, plus fiable dans ce cas précis.

    Le résultat passe par le filtre _is_plausible avant d'être renvoyé : un
    renvoi de note ou un numéro de page/ligne capturé par erreur (trop petit
    pour être un vrai montant) est rejeté (None) plutôt que renvoyé tel quel
    (voir MIN_PLAUSIBLE_VALUE)."""
    if not clusters:
        return None
    if not header_token:
        # Certains bilans (ex: COTUNACE) insèrent un numéro de note de bas de
        # page (petit entier ≤ 50) en première colonne avant les montants.
        # Si le premier cluster est un entier ≤ 50 et qu'il en existe un
        # second, on l'ignore pour prendre la vraie valeur de l'année en cours.
        start = 0
        if (len(clusters) >= 2
                and clusters[0][0] <= 50
                and clusters[0][0] == int(clusters[0][0])):
            start = 1
        value = clusters[start][0]
    elif len(clusters) <= 4:
        value = clusters[-2][0] if len(clusters) >= 2 else clusters[-1][0]
    else:
        ref_x = _leftmost_header_x(lines, target_top, header_token)
        value = clusters[-2][0] if ref_x is None else min(clusters, key=lambda c: abs(c[1] - ref_x))[0]
    return value if _is_plausible(value) else None


def _page_lines(page):
    words = page.extract_words()
    if not words:
        return []
    return _cluster_lines(words)


def _find_row_value(pdf, pattern_re, header_token=None, max_pages=MAX_PAGES_SCANNED,
                     page_filter=None, forward_scan=2):
    """Cherche, dans les premières pages, la première ligne dont le libellé
    normalisé correspond à `pattern_re`, et renvoie la valeur numérique
    correspondant à la colonne "année en cours" :
      - si `header_token` est fourni (ex: "net"), on prend la colonne dont le
        x0 est le plus proche de l'en-tête `header_token` le plus à gauche
        trouvé au-dessus de cette ligne (gère les tableaux avec plusieurs
        sous-colonnes brut/amortissements/net par année) ;
      - sinon, on prend la colonne la plus à gauche (les tableaux simples
        Passif présentent toujours l'année en cours en première colonne).
    Si le libellé correspondant n'a pas de chiffres sur sa propre ligne (ex:
    libellé replié sur 2 lignes dans le PDF source), on regarde jusqu'à
    `forward_scan` lignes suivantes pour trouver les chiffres associés.
    `page_filter`, si fourni, restreint la recherche aux pages qu'il valide
    (ex: _is_actif_page) — utile pour éviter de matcher un libellé similaire
    sur la mauvaise page."""
    for page in pdf.pages[:max_pages]:
        if page_filter and not page_filter(page):
            continue
        lines = _page_lines(page)
        if not lines:
            continue
        for i, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not pattern_re.search(label):
                continue
            for j in range(i, min(i + 1 + forward_scan, len(lines))):
                clusters = _extract_numeric_clusters(lines[j])
                if not clusters:
                    continue
                value = _select_column_value(clusters, lines, lines[j][0]["top"], header_token)
                if value is not None:
                    return value
    return None


def _is_actif_page(page, lines_checked=10):
    """Une page est considérée comme la page "Actif" du Bilan si le mot
    "actif(s)" apparaît dans l'un de ses premiers titres (ex: "ACTIF",
    "Actifs du Bilan", "Annexe 1 : ACTIF"), sans que "passif" y apparaisse
    aussi (pour ne pas confondre avec la page combinée Capitaux propres et
    Passif qui peut mentionner "actif" en passant). lines_checked=10 (au
    lieu de 5) : certains documents (ex: BIAT 2025) ont un bandeau d'en-tête
    de 5 lignes ("Assurances X / Bilan / Arrêté au... / Unité... / dates")
    avant la ligne "ACTIFS Brut Amort. Net Net" elle-même — avec
    lines_checked=5 elle tombait juste hors fenêtre, la page entière était
    ignorée et "Total actif" ressortait introuvable."""
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    for line in text.split("\n")[:lines_checked]:
        normalized = _normalizer.clean(line)
        if ACTIF_PAGE_TITLE_RE.search(normalized) and "passif" not in normalized:
            return True
    return False


def _is_passif_page(page, lines_checked=10):
    """Une page est considérée comme la page "Passif" (ou "Capitaux propres
    et Passif") du Bilan si le mot "passif(s)" apparaît dans l'un de ses
    premiers titres. Même marge élargie que _is_actif_page, pour la même
    raison (bandeau d'en-tête variable selon les documents)."""
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    for line in text.split("\n")[:lines_checked]:
        normalized = _normalizer.clean(line)
        if PASSIF_PAGE_TITLE_RE.search(normalized):
            return True
    return False


def _section_starts_for_page(lines, side_prefix):
    """Position (index de ligne, code) de chaque titre de section de premier
    niveau sur la page. Essaie d'abord le code réglementaire (AC1..AC7,
    PA1..PA7) ; si aucun n'est détecté sur toute la page (code non extrait
    correctement du PDF), se rabat sur la reconnaissance par texte de
    section (voir ACTIF_SECTION_TEXT_PATTERNS / PASSIF_SECTION_TEXT_PATTERNS)."""
    section_starts = [
        (i, sc[1]) for i, line in enumerate(lines)
        if (sc := _section_code(line)) and sc[0] == side_prefix
    ]
    if section_starts:
        return section_starts
    # Repli par texte : le mot-clé d'une section apparaît aussi dans ses
    # propres sous-éléments détaillés (ex: "Créances" (AC6, en-tête) vs
    # "Créances nées d'opérations d'assurance directe" (AC61, sous-élément)).
    # Le VRAI titre de section est systématiquement beaucoup plus court que
    # ces sous-éléments (souvent juste le code + le mot-clé) : on ne garde,
    # pour chaque code, que la correspondance au libellé le plus court.
    text_patterns = ACTIF_SECTION_TEXT_PATTERNS if side_prefix == "ac" else PASSIF_SECTION_TEXT_PATTERNS
    best_by_code = {}  # code -> (index, longueur_libellé)
    for i, line in enumerate(lines):
        label = _label_text(line)
        if not label:
            continue
        for code, pattern in text_patterns:
            if pattern.search(label):
                if code not in best_by_code or len(label) < best_by_code[code][1]:
                    best_by_code[code] = (i, len(label))
                break
    return sorted((i, code) for code, (i, _) in best_by_code.items())


def _find_section_total(pdf, side_prefix, code, header_token, max_pages=MAX_PAGES_SCANNED):
    """Renvoie la valeur "année en cours" d'une section de premier niveau du
    plan comptable réglementaire (ex: side_prefix="ac", code="3" pour "AC3
    Placements"). La valeur est la DERNIÈRE ligne portant des chiffres avant
    le début de la section suivante (AC/PA de même niveau) : ce simple critère
    couvre, sans distinction de cas, les 3 mises en page réelles rencontrées —
    total sur la ligne de titre elle-même, sur une ligne juste en dessous, ou
    après plusieurs sous-totaux imbriqués (voir CAS_PARTICULIERS.md)."""
    page_filter = _is_actif_page if side_prefix == "ac" else _is_passif_page
    for page in pdf.pages[:max_pages]:
        if not page_filter(page):
            continue
        lines = _page_lines(page)
        if not lines:
            continue
        section_starts = _section_starts_for_page(lines, side_prefix)
        # Bornes de fin supplémentaires : la dernière section (ex: AC7, PA7)
        # n'a pas de section suivante pour la délimiter — sans ça, sa plage
        # engloberait la ligne de total général qui la suit (ex: "Total de
        # l'actif" ou "Total des capitaux propres et du passif"), qui a
        # elle-même des chiffres et serait donc prise à tort pour le total de
        # la section.
        total_line_indices = [
            i for i, line in enumerate(lines)
            if (label := _label_text(line)) and label.startswith("total")
        ]
        for idx, (line_idx, found_code) in enumerate(section_starts):
            if found_code != code:
                continue
            # Repli si aucune ligne "Total..." n'existe (ex: BH, la page se
            # termine directement par une ligne de total général SANS
            # libellé) : on exclut par défaut la toute dernière ligne de la
            # page de la plage, en supposant qu'il s'agit du total général
            # qui suit systématiquement la dernière section.
            end_idx = section_starts[idx + 1][0] if idx + 1 < len(section_starts) else len(lines) - 1
            next_total = next((i for i in total_line_indices if i > line_idx), None)
            if next_total is not None:
                end_idx = min(end_idx, next_total)
            # Certaines sociétés (ex: GAT) inscrivent directement le total de
            # la section sur sa ligne de titre ; les sous-éléments détaillés
            # ensuite (même à 0) ne doivent alors pas l'écraser. D'autres
            # (ex: STAR, COMAR) laissent le titre sans chiffres et placent le
            # total sur la DERNIÈRE ligne à chiffres de la plage. On exige au
            # moins 2 colonnes sur la ligne de titre pour la traiter comme un
            # vrai total (brut/amortissements/net...) : un seul chiffre isolé
            # est presque toujours un renvoi de note collé au libellé (ex:
            # "Actifs incorporels (1)" chez BH), pas un montant.
            header_clusters = _extract_numeric_clusters(lines[line_idx])
            if len(header_clusters) >= 2:
                return _select_column_value(header_clusters, lines, lines[line_idx][0]["top"], header_token)
            value = None
            for j in range(line_idx + 1, end_idx):
                clusters = _extract_numeric_clusters(lines[j])
                # même garde-fou que ci-dessus : un renvoi de note isolé
                # (souvent celui de la section suivante, incluse par erreur
                # en bord de plage) ne doit pas être pris pour une valeur.
                if len(clusters) < 2:
                    continue
                candidate = _select_column_value(clusters, lines, lines[j][0]["top"], header_token)
                if candidate is not None:
                    value = candidate
            return value
    return None


def _find_actif_bare_total_fallback(pdf, max_pages=BILAN_TOTAL_MAX_PAGES):
    """Repli pour les documents où la ligne totale de l'Actif n'a pas de
    libellé explicite ("Total" seul, ex: ATTIJARI) : on se restreint aux
    pages dont le texte commence par "actif"/"actifs", et on prend la
    DERNIÈRE ligne libellée exactement "Total" (le total général est
    toujours en bas de tableau, après d'éventuels sous-totaux non libellés).
    max_pages=BILAN_TOTAL_MAX_PAGES (pas MAX_PAGES_SCANNED) : ce repli
    cherche n'importe quelle ligne "Total" nue sur une page "actif", un motif
    trop générique pour être scanné au-delà des toutes premières pages sans
    risquer de capter un faux total sur une page d'annexe (voir
    BILAN_TOTAL_MAX_PAGES)."""
    for page in pdf.pages[:max_pages]:
        if not _is_actif_page(page):
            continue
        lines = _page_lines(page)
        if not lines:
            continue
        candidates = [line for line in lines if _label_text(line) == "total"]
        if not candidates:
            continue
        target_line = candidates[-1]
        clusters = _extract_numeric_clusters(target_line)
        if not clusters:
            continue
        value = _select_column_value(clusters, lines, target_line[0]["top"], header_token="net")
        if value is not None:
            return value
    return None


def _find_actif_unlabeled_total_fallback(pdf, max_pages=BILAN_TOTAL_MAX_PAGES):
    """Second repli pour les documents où même le mot "Total" est absent
    (ex: BH, la dernière ligne du tableau Actif n'est composée que de
    nombres) : on prend la dernière ligne entièrement numérique de la page
    Actif comme total général.

    On ignore les lignes n'ayant qu'un seul cluster de valeur absolue ≤ 9
    (numéros de notes de bas de page comme "1", "2", "(*)"). max_pages
    restreint (voir _find_actif_bare_total_fallback/BILAN_TOTAL_MAX_PAGES) :
    motif encore plus générique (n'importe quelle ligne 100% numérique), donc
    encore plus sensible au même risque de faux positif sur une page d'annexe."""
    for page in pdf.pages[:max_pages]:
        if not _is_actif_page(page):
            continue
        lines = _page_lines(page)
        numeric_only_lines = [line for line in lines if _label_text(line) is None]
        if not numeric_only_lines:
            continue
        # Filtrer les lignes-note (un seul cluster, valeur ≤ 9)
        substantive = [
            line for line in numeric_only_lines
            if not (
                len(_extract_numeric_clusters(line)) == 1
                and abs(_extract_numeric_clusters(line)[0][0]) <= 9
            )
        ]
        if not substantive:
            continue
        target_line = substantive[-1]
        clusters = _extract_numeric_clusters(target_line)
        if not clusters:
            continue
        value = _select_column_value(clusters, lines, target_line[0]["top"], header_token="net")
        if value is not None:
            return value
    return None


def _find_total_actif(pdf):
    value = _find_row_value(pdf, TOTAL_ACTIF_RE, header_token="net", page_filter=_is_actif_page,
                             max_pages=BILAN_TOTAL_MAX_PAGES)
    if value is None:
        value = _find_actif_bare_total_fallback(pdf)
    if value is None:
        value = _find_actif_unlabeled_total_fallback(pdf)
    return value


def _find_total_passif(pdf):
    """Wrapper dédié (plutôt qu'une entrée "direct" dans KPI_DEFINITIONS) :
    même raisonnement que _find_total_actif, restreint à
    BILAN_TOTAL_MAX_PAGES plutôt que MAX_PAGES_SCANNED par précaution
    symétrique (le motif "^total ... passifs?" reste générique)."""
    return _find_row_value(pdf, TOTAL_PASSIF_RE, header_token=None, page_filter=_is_passif_page,
                            max_pages=BILAN_TOTAL_MAX_PAGES)


def _find_capitaux_propres(pdf):
    """Cherche en priorité "Total capitaux propres avant affectation" (le
    vrai total final, incluant le résultat de l'exercice en cours) ; se
    rabat sur "...avant résultat" seulement si la ligne "avant affectation"
    est absente du document (voir TOTAL_CAPITAUX_PROPRES_AFFECTATION_RE)."""
    value = _find_row_value(pdf, TOTAL_CAPITAUX_PROPRES_AFFECTATION_RE, header_token=None)
    if value is None:
        value = _find_row_value(pdf, TOTAL_CAPITAUX_PROPRES_RE, header_token=None)
    return value


# Définition de chaque KPI :
#   - "direct" : (fonction_speciale) OU (motif_regex, header_token, page_filter)
#   - "section" : (prefixe "ac"/"pa", code "1".."7", header_token)
KPI_DEFINITIONS = [
    ("Total actif", "special", _find_total_actif),
    ("Capitaux propres", "special", _find_capitaux_propres),
    ("Total Passif", "special", _find_total_passif),
    ("Actifs incorporels", "section", "ac", "1", "net"),
    ("Actifs corporels", "section", "ac", "2", "net"),
    ("Placements", "section", "ac", "3", "net"),
    ("Créances", "section", "ac", "6", "net"),
    ("Autres éléments d'actifs", "section", "ac", "7", "net"),
    ("Autres passifs", "section", "pa", "7", None),
    ("Part des réassureurs dans les provisions techniques", "section", "ac", "5", "net"),
    ("Provisions techniques brutes", "section", "pa", "3", None),
    ("Obligations", "direct", OBLIGATIONS_RE, "net", _is_actif_page),
    ("Actions et titres de participation", "direct", ACTIONS_PARTICIPATION_RE, "net", _is_actif_page),
    ("OPCVM", "direct", OPCVM_RE, "net", _is_actif_page),
    ("Dépôts et liquidité", "direct", DEPOTS_LIQUIDITE_RE, "net", _is_actif_page),
    ("Placements représentant des provisions techniques", "section", "ac", "4", "net"),
]


def extract_all_bilan_kpis(pdf):
    """Renvoie {nom_kpi: valeur|None} pour tous les KPI de KPI_DEFINITIONS,
    à partir du tableau Bilan du PDF ouvert `pdf` (objet pdfplumber.PDF)."""
    results = {}
    for definition in KPI_DEFINITIONS:
        name, kind = definition[0], definition[1]
        if kind == "special":
            results[name] = definition[2](pdf)
        elif kind == "direct":
            _, _, pattern_re, header_token, page_filter = definition
            results[name] = _find_row_value(pdf, pattern_re, header_token=header_token, page_filter=page_filter)
        elif kind == "section":
            _, _, side_prefix, code, header_token = definition
            results[name] = _find_section_total(pdf, side_prefix, code, header_token)
    return results


def extract_bilan_kpis(pdf):
    """Compatibilité : renvoie uniquement les 2 premiers KPI historiques
    ({"capitaux_propres": ..., "total_actif": ...}). Préférer
    extract_all_bilan_kpis pour les nouveaux usages."""
    all_kpis = extract_all_bilan_kpis(pdf)
    return {
        "capitaux_propres": all_kpis["Capitaux propres"],
        "total_actif": all_kpis["Total actif"],
    }


def extract_all_bilan_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait tous les KPI du Bilan."""
    import pdfplumber  # import local pour éviter la dépendance si non utilisé

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_all_bilan_kpis(pdf)


def extract_bilan_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait les KPI du Bilan (compatibilité, voir extract_bilan_kpis)."""
    import pdfplumber  # import local pour éviter la dépendance si non utilisé

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_bilan_kpis(pdf)
