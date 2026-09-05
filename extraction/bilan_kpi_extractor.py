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

TOTAL_ACTIF_RE = re.compile(r"^total (de l |des )?actifs?\b")
TOTAL_CAPITAUX_PROPRES_AFFECTATION_RE = re.compile(r"^total (des )?(capitaux propres|cp) av(ant)? affectation\b")
TOTAL_CAPITAUX_PROPRES_RE = re.compile(r"^total (des )?(capitaux propres|cp) av(ant)? resultat\b")
TOTAL_PASSIF_RE = re.compile(r"^total (du |des )?passifs?\b")
OBLIGATIONS_RE = re.compile(r"obligations et autres titres")
ACTIONS_PARTICIPATION_RE = re.compile(r"actions,? ?autres titres a revenu variable")
OPCVM_RE = re.compile(r"autres placements financiers")
DEPOTS_LIQUIDITE_RE = re.compile(r"avoirs en banques?,? ?ccp,? ?ch[eè]ques")

ACTIF_PAGE_TITLE_RE = re.compile(r"\bactifs?\b")
PASSIF_PAGE_TITLE_RE = re.compile(r"\bpassifs?\b")
SECTION_CODE_RE = re.compile(r"^(ac|pa)([1-7])\b")
ROW_CODE_PREFIX_RE = re.compile(r"^(ac|pa|cp|prv|prnv|chv|chnv)\d+\s+")

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

MAX_PAGES_SCANNED = 12
BILAN_TOTAL_MAX_PAGES = 4
Y_TOLERANCE = 5
NUMBER_GAP_THRESHOLD = 4
MINUS_CHARS = "‐‑‒–—−"
NUMERIC_TOKEN_RE = re.compile(rf"^[-{MINUS_CHARS}]?\d+(?:,\d+)*(?:\.\d+)*$")
_MINUS_NORMALIZE_RE = re.compile(f"[{MINUS_CHARS}]")
_GLUED_NEGATIVE_RE = re.compile(rf"^(\d+)([-{MINUS_CHARS}]\d+(?:,\d+)?)$")
_GLUED_CLOSE_PAREN_RE = re.compile(r"^(\d+(?:,\d+)?)\)(\d+)$")
_PERIOD_THOUSANDS_CONTINUATION_RE = re.compile(r"^\.\d{3}(?:\.\d{3})*$")
_LEADING_DIGIT_GROUP_RE = re.compile(rf"^[-{MINUS_CHARS}]?\d{{1,3}}$")
MAX_PLAUSIBLE_VALUE = 50_000_000_000
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


def _merged_period_thousands(line, gap_threshold=NUMBER_GAP_THRESHOLD):
    """Recolle un mot "8" suivi (à moins de gap_threshold) d'un mot
    ".671.061" en un seul mot "8671061" — voir _PERIOD_THOUSANDS_CONTINUATION_RE
    plus haut pour le contexte (TUNIS_RE 2024)."""
    merged, i = [], 0
    while i < len(line):
        w = line[i]
        nxt = line[i + 1] if i + 1 < len(line) else None
        if (nxt is not None and _LEADING_DIGIT_GROUP_RE.match(w["text"])
                and _PERIOD_THOUSANDS_CONTINUATION_RE.match(nxt["text"])
                and (nxt["x0"] - w["x1"]) < gap_threshold):
            merged.append({**w, "text": w["text"] + nxt["text"].replace(".", ""), "x1": nxt["x1"]})
            i += 2
            continue
        merged.append(w)
        i += 1
    return merged


def _extract_numeric_clusters(line, gap_threshold=NUMBER_GAP_THRESHOLD):
    """Regroupe les tokens numériques consécutifs d'une ligne (séparateur de
    milliers = espace) en nombres complets, dans l'ordre d'apparition
    (gauche à droite = colonnes du tableau). Renvoie une liste de
    (valeur, x0_premier_token)."""
    line = _merged_period_thousands(line, gap_threshold)
    line = _words_with_bracket_negatives_resolved(line)
    once_split = [split_word for w in line for split_word in _split_glued_negative(w, gap_threshold)]
    expanded = [
        split_word for w in once_split for split_word in _split_glued_close_paren(w, gap_threshold)
    ]
    numeric_words = [w for w in expanded if NUMERIC_TOKEN_RE.match(w["text"])]
    clusters, current_tokens, prev_x1 = [], [], None
    for w in numeric_words:
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
            value = float(num_str.replace(",", ""))
        elif "," in num_str:
            value = float(num_str.replace(",", "."))
        elif num_str.count(".") >= 2:
            value = float(num_str.replace(".", ""))
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


_OCR_MIN_NATIVE_CHARS = 20


def _ocr_words(page, resolution=300):
    """Rend `page` en image et en extrait les mots via OCR, au même format
    que `page.extract_words()` de pdfplumber. Renvoie [] si pytesseract/
    tesseract n'est pas installé (dépendance optionnelle) ou en cas d'échec
    du rendu/OCR — dégradation silencieuse vers le comportement précédent
    (page traitée comme vide)."""
    try:
        import pytesseract
        from pytesseract import Output
    except ImportError:
        return []
    try:
        img = page.to_image(resolution=resolution).original
        data = pytesseract.image_to_data(img, lang="fra", config="--psm 6", output_type=Output.DICT)
    except Exception:
        return []
    scale = resolution / 72.0
    words = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        if not text:
            continue
        left, top, width, height = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        words.append({
            "text": text,
            "x0": left / scale,
            "x1": (left + width) / scale,
            "top": top / scale,
            "bottom": (top + height) / scale,
        })
    return words


class _OcrFallbackPage:
    """Enveloppe transparente d'une page pdfplumber : se comporte comme la
    page native tant que celle-ci contient du texte exploitable, et ne
    déclenche l'OCR (coûteux) que si extract_text()/extract_words() natifs
    sont vides ou quasi vides. Tout attribut/méthode non redéfini est
    délégué à la page pdfplumber d'origine (__getattr__).

    `force=True` (utilisé par extract_all_bilan_kpis en 2e passe, seulement
    si la 1ère n'a rien trouvé pour Total actif/Capitaux propres) ignore le
    texte natif même non vide et impose l'OCR — couvre le cas BH (2020) où
    le texte natif existe mais est gravement corrompu par l'encodage police
    ("3992 196 2r9o 892 rSol 3o4" — lettres et chiffres mêlés), donc trop
    long pour déclencher le seuil _OCR_MIN_NATIVE_CHARS mais inexploitable
    par le parsing numérique. L'OCR relit l'image de la page, indépendant de
    la couche texte corrompue."""

    def __init__(self, page, force=False):
        self._page = page
        self._force = force
        self._ocr_cache = None

    def _ocr(self):
        if self._ocr_cache is None:
            self._ocr_cache = _ocr_words(self._page)
        return self._ocr_cache

    def extract_words(self, **kwargs):
        if self._force:
            return self._ocr() or self._page.extract_words(**kwargs)
        native = self._page.extract_words(**kwargs)
        return native if native else self._ocr()

    def extract_text(self):
        native = (self._page.extract_text() or "").strip()
        if not self._force and len(native) >= _OCR_MIN_NATIVE_CHARS:
            return native
        ocr_words = self._ocr()
        if not ocr_words:
            return native
        return "\n".join(" ".join(w["text"] for w in line) for line in _cluster_lines(ocr_words))

    def __getattr__(self, name):
        return getattr(self._page, name)


class _PdfPagesProxy:
    """Objet minimal exposant `.pages` (seul attribut de `pdf` utilisé dans
    ce module) — permet d'injecter des pages avec repli OCR partout où le
    code existant fait `pdf.pages[:max_pages]`, sans toucher chacun de ces
    sites d'appel."""

    def __init__(self, pages):
        self.pages = pages


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
    sur la mauvaise page.

    `_is_plausible` (découvert manquant ici le 2026-08-06, sur "Résultat
    Net"/resultat_kpi_extractor.py où le même trou existait) : sans ce
    filtre, un fragment de nombre scindé par le PDF (ex: TUNIS_RE 2024,
    séparateur de milliers en points — voir CAS_PARTICULIERS_RESULTAT.md)
    ressortirait tel quel (valeur absurdement petite) au lieu de redevenir
    `None`/anomalie détectée."""
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
                if value is not None and _is_plausible(value):
                    return value
    return None


def _is_actif_page(page, lines_checked=20):
    """Une page est considérée comme la page "Actif" du Bilan si le mot
    "actif(s)" apparaît dans l'un de ses premiers titres (ex: "ACTIF",
    "Actifs du Bilan", "Annexe 1 : ACTIF"), sans que "passif" y apparaisse
    aussi (pour ne pas confondre avec la page combinée Capitaux propres et
    Passif qui peut mentionner "actif" en passant). lines_checked=20 (au
    lieu de 10, lui-même déjà élargi depuis 5) : certains documents (ex:
    BIAT 2025) ont un bandeau d'en-tête de 5 lignes ("Assurances X / Bilan /
    Arrêté au... / Unité... / dates") avant la ligne "ACTIFS Brut Amort. Net
    Net" elle-même. D'autres (ex: STAR/BIAT/CARTE/ASTREE 2015, gabarit "AVIS
    DES SOCIÉTÉS" avec préambule narratif de 8 lignes avant "BILAN AU
    .../ACTIF") poussent le titre à la 12e ligne, hors de la fenêtre à 10 —
    découvert le 2026-08-17 en auditant Vue par Assurance ("Total actif"/
    "ROA" manquants ensemble sur plusieurs sociétés en 2015, motif récurrent
    au lieu d'un cas isolé). Sans risque de faux positif : le titre Bilan
    est toujours en tout début de SA page, jamais enfoui dans un corps de
    texte, quelle que soit la longueur du préambule."""
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    for line in text.split("\n")[:lines_checked]:
        normalized = _normalizer.clean(line)
        if ACTIF_PAGE_TITLE_RE.search(normalized) and "passif" not in normalized:
            return True
    return False


def _is_passif_page(page, lines_checked=20):
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
    text_patterns = ACTIF_SECTION_TEXT_PATTERNS if side_prefix == "ac" else PASSIF_SECTION_TEXT_PATTERNS
    best_by_code = {}
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
        total_line_indices = [
            i for i, line in enumerate(lines)
            if (label := _label_text(line)) and label.startswith("total")
        ]
        for idx, (line_idx, found_code) in enumerate(section_starts):
            if found_code != code:
                continue
            end_idx = section_starts[idx + 1][0] if idx + 1 < len(section_starts) else len(lines) - 1
            next_total = next((i for i in total_line_indices if i > line_idx), None)
            if next_total is not None:
                end_idx = min(end_idx, next_total)
            header_clusters = _extract_numeric_clusters(lines[line_idx])
            if len(header_clusters) >= 2:
                return _select_column_value(header_clusters, lines, lines[line_idx][0]["top"], header_token)
            value = None
            for j in range(line_idx + 1, end_idx):
                clusters = _extract_numeric_clusters(lines[j])
                if len(clusters) < 2:
                    continue
                candidate = _select_column_value(clusters, lines, lines[j][0]["top"], header_token)
                if candidate is not None and (value is None or candidate > value):
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


_ACTIF_COMPONENT_KPIS = [
    "Actifs incorporels", "Actifs corporels", "Placements", "Créances",
    "Autres éléments d'actifs", "Part des réassureurs dans les provisions techniques",
    "Obligations", "Actions et titres de participation", "OPCVM",
    "Dépôts et liquidité", "Placements représentant des provisions techniques",
]


def _apply_composition_consistency_guard(results):
    """Un poste de l'Actif ne peut jamais dépasser le Total actif (une
    partie ne peut être plus grande que le tout) : découvert le 2026-08-18
    sur STAR 2025, dont la page Actif du Bilan est une image scannée
    (0 mot de texte natif -> repli OCR, voir _OcrFallbackPage) — l'OCR de
    cette page précise a mal lu la section "OPCVM", produisant 8,9 Md TND
    pour un Total actif de 1,66 Md TND. Filet de sécurité générique
    (jamais spécifique à une compagnie) plutôt qu'un correctif OCR ciblé,
    l'amélioration de la qualité OCR elle-même étant hors de portée ici.

    Piste explorée puis abandonnée : comparer "Placements" (AC3) à la somme
    de ses "sous-éléments" Obligations/Actions/OPCVM/Dépôts et liquidité.
    Invalidée sur ASTREE 2015 (vérification manuelle ligne par ligne du
    PDF) : "OPCVM" matche en réalité le sous-total AC33 "Autres placements
    financiers", qui englobe DÉJÀ Obligations et Actions (pas des lignes
    sœurs indépendantes) ; "Dépôts et liquidité" matche AC71 (Autres
    éléments d'actif), une section différente d'AC3. Ces 4 KPI ne sont pas
    des parts mutuellement exclusives d'AC3 -> aucune relation d'inégalité
    fiable entre eux et le total de section ne peut être posée en règle
    générale (le test faisait remonter ~90 faux positifs, dont la quasi-
    totalité des années ASTREE/GAT/GAT_VIE, où Placements est en réalité
    correct).

    Ne s'applique que si `Total actif` lui-même est plausible (>= 1M TND,
    même seuil que `kpi_builder._MIN_TOTAL_ACTIF_PLAUSIBLE`) : plusieurs
    documents (ex: BH 2020, UIB 2020) ont un "Total actif" déjà erroné et
    minuscule (20 TND, 2041 TND — un fragment de nombre, pas un vrai total)
    -> comparer des composantes par ailleurs correctes à CE total casserait
    des valeurs valides au lieu de détecter une vraie incohérence."""
    total_actif = results.get("Total actif")
    if total_actif is not None and abs(total_actif) >= 1_000_000:
        for name in _ACTIF_COMPONENT_KPIS:
            value = results.get(name)
            if value is not None and abs(value) > total_actif:
                results[name] = None


def _extract_all_bilan_kpis_impl(pdf, force_ocr=False):
    results = {}
    wrapped = _PdfPagesProxy([_OcrFallbackPage(p, force=force_ocr) for p in pdf.pages[:MAX_PAGES_SCANNED]])
    for definition in KPI_DEFINITIONS:
        name, kind = definition[0], definition[1]
        if kind == "special":
            results[name] = definition[2](wrapped)
        elif kind == "direct":
            _, _, pattern_re, header_token, page_filter = definition
            results[name] = _find_row_value(wrapped, pattern_re, header_token=header_token, page_filter=page_filter)
        elif kind == "section":
            _, _, side_prefix, code, header_token = definition
            results[name] = _find_section_total(wrapped, side_prefix, code, header_token)
    _apply_composition_consistency_guard(results)
    return results


def extract_all_bilan_kpis(pdf):
    """Renvoie {nom_kpi: valeur|None} pour tous les KPI de KPI_DEFINITIONS,
    à partir du tableau Bilan du PDF ouvert `pdf` (objet pdfplumber.PDF).

    2 passes : la 1ère utilise le texte natif, avec repli OCR uniquement sur
    les pages vides (_OcrFallbackPage, voir commentaire au-dessus de
    _ocr_words) — coût nul sur l'immense majorité des documents. Si "Total
    actif" OU "Capitaux propres" est introuvable à l'issue de cette 1ère
    passe (page trouvée mais texte natif inexploitable, ex: encodage police
    corrompu — cas BH 2020, où seule la page Actif est corrompue et Capitaux
    propres/Passif s'extrait normalement — un déclencheur "ET" raterait ce
    cas), une 2e passe force l'OCR sur toutes les pages scannées ; ses
    résultats ne comblent que les trous de la 1ère passe (jamais
    d'écrasement d'une valeur déjà trouvée)."""
    results = _extract_all_bilan_kpis_impl(pdf, force_ocr=False)
    if results.get("Total actif") is None or results.get("Capitaux propres") is None:
        forced = _extract_all_bilan_kpis_impl(pdf, force_ocr=True)
        for name, value in forced.items():
            if results.get(name) is None and value is not None:
                results[name] = value
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
    import pdfplumber

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_all_bilan_kpis(pdf)


def extract_bilan_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait les KPI du Bilan (compatibilité, voir extract_bilan_kpis)."""
    import pdfplumber

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_bilan_kpis(pdf)
