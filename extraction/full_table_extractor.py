"""Extraction "grille complète" d'un tableau annexe (toutes les lignes,
toutes les colonnes par branche) — contrairement à annexe12_kpi_extractor.py
et annexe13_kpi_extractor.py qui ne récupèrent QUE les 7 lignes/1 colonne
("Montant" total) dont les dashboards ont besoin.

Motivation (retour utilisateur, page Gestion de données) : l'export Excel
doit pouvoir montrer le tableau annexe tel qu'il existe réellement dans le
PDF source (toutes les branches — Automobile, Transport, Incendie...), pas
seulement le sous-ensemble déjà utilisé par les dashboards.

Principe (vérifié manuellement le 2026-09-08 sur GAT_2024.pdf, Annexe 13 —
16 colonnes par branche, valeurs recoupées avec la capture d'écran déjà
utilisée pour l'audit du Ratio Combiné dans cette session) :
  1. Repérer les positions X des VALEURS NUMÉRIQUES de toutes les lignes de
     données (fiables : une seule ligne de texte, jamais scindées sur
     plusieurs lignes visuelles) → ce sont les vrais centres de colonnes.
     Bien plus robuste que de partir des libellés d'en-tête, qui eux sont
     souvent repliés sur 2-3 lignes visuelles ("Responsabilité" / "civile",
     "Autres" / "dommages" / "aux" / "biens"...).
  2. Rattacher chaque MOT de l'en-tête (qui peut être réparti sur plusieurs
     lignes visuelles) à la colonne dont le centre est le plus proche de son
     x0, puis reconstituer le libellé de chaque colonne en triant ses mots
     par position verticale (haut → bas) — restitue l'ordre de lecture réel
     d'un libellé replié sur 2-3 lignes.
  3. Toute colonne du tableau totalement vide sur cette page (aucune valeur
     nulle part, ex. "Autres" chez GAT) n'a pas de centre déductible de
     l'étape 1 — son mot d'en-tête reste alors "non assigné" ; il est
     réinséré comme colonne à part entière (toutes valeurs = None) à sa
     position x réelle, pour ne pas la faire disparaître silencieusement du
     tableau restitué.

Limite connue : cette heuristique cible la mise en page des tableaux
Annexe 12/13 (et gabarits proches — même préambule "Société... / Annexe
N°X / titre / (exprimé en dinars tunisiens)" observé aussi sur les pages
"raccordement"/Etat de résultat technique). Le Bilan (Brut/Amortissement/
Net/Net N-1, pas de branches) et les tableaux Takaful (Annexes 14/15) ont
une structure différente et ne sont pas couverts par ce module pour
l'instant."""

import re

from extraction.bilan_kpi_extractor import _cluster_lines, _extract_numeric_clusters, _normalizer, ROW_CODE_PREFIX_RE
from extraction.annexe13_kpi_extractor import (
    PAGE_TITLE_RE as _A13_PAGE_TITLE_RE,
    NON_VIE_RE as _A13_NON_VIE_RE, VIE_RE as _A13_VIE_RE,
    _LEADING_BULLET_RE as _A13_LEADING_BULLET_RE,
)

# Un mot-token pdfplumber purement numérique entre parenthèses (notation
# comptable standard des montants négatifs) — ex. "(4" et "562)" quand la
# valeur "(4 562)" est scindée en 2 tokens par un espace interne. Le filtre
# NUMERIC_TOKEN_RE du module partagé (annexe13_kpi_extractor._label_text) ne
# reconnaît pas ces fragments (il n'admet pas la parenthèse), ce qui les
# laissait fuiter dans le libellé de ligne reconstruit sur les gabarits où
# TOUTES les valeurs (plusieurs branches) sont sur la même ligne physique que
# le libellé (ex. GAT, 16 colonnes/branche — "Variation des primes non
# acquises (4 562) (246 203)..." au lieu du libellé seul). Ce n'est pas un
# cas isolé à GAT : tout gabarit à valeurs négatives entre parenthèses sur la
# ligne de libellé est concerné, d'où un filtre local plus large plutôt qu'un
# correctif propre à une société.
_BRACKET_NUMERIC_RE = re.compile(r"^\(?[+\-]?\d[\d.,]*\)?$")


def _label_text(line):
    """Variante locale (module "grille complète") de
    annexe13_kpi_extractor._label_text — même logique (retire les tokens
    numériques, le tiret de tête, le préfixe de code de ligne) mais avec un
    filtre numérique élargi aux fragments entre parenthèses. Volontairement
    séparée du module partagé pour ne jamais risquer de régression sur le
    pipeline 7-KPI existant."""
    label_words = [w for w in line if not _BRACKET_NUMERIC_RE.match(w["text"])]
    if not label_words:
        return None
    label = _normalizer.clean(" ".join(w["text"] for w in label_words))
    label = _A13_LEADING_BULLET_RE.sub("", label)
    label = ROW_CODE_PREFIX_RE.sub("", label, count=1)
    # Symboles de signe isolés ("-", "+", "+/-") résiduels en fin de libellé
    # — vestiges de la colonne "signe" typographique du tableau source
    # (visible entre le libellé et les valeurs), sans valeur informative une
    # fois le libellé reconstruit.
    return re.sub(r"(?:\s+[+\-/]+)+$", "", label).strip() or None


def relaxed_is_annexe13_page(page, lines_checked=4):
    """Variante de annexe13_kpi_extractor._is_target_page SANS l'exclusion
    "notes sur" (NOTES_SECTION_RE) — cette règle reste nécessaire au
    pipeline 7-KPI existant (non modifiée), mais exclut à tort la page
    réelle d'au moins une société (LLOYD_TUNISIEN, dont l'annexe est
    titrée "Notes sur le résultat technique par catégorie..."). À utiliser
    UNIQUEMENT comme `extra_page_predicate` de `locate_and_extract_full_table`
    (le contrôle de vraisemblance qui suit absorbe le risque de faux
    positifs supplémentaires)."""
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    if not _A13_PAGE_TITLE_RE.search(normalized):
        return False
    if _A13_NON_VIE_RE.search(normalized):
        return True
    return not _A13_VIE_RE.search(normalized)

_JUNK_LABEL_RE = re.compile(r"^[+\-/\s]+$")

MIN_DATA_CLUSTERS = 4   # une vraie ligne de donnees a au moins 4 colonnes remplies (la
# ligne société/date du préambule ("Société X, États financiers au 31
# décembre 2024") peut déjà contenir jusqu'à 3 nombres — jour, mois si
# chiffré, année — sans être une ligne de données, ex. COMAR 2024).
COL_GAP = 6             # tolerance (pt) pour regrouper des x0 de valeurs en une colonne —
# volontairement étroit : élargi (essayé jusqu'à 20pt) pour absorber le
# dédoublement de colonne observé sur le gabarit à 4 colonnes larges de
# STAR (une même colonne alignée à droite ayant des x0 différents d'une
# ligne à l'autre selon le nombre de chiffres), mais ça fusionnait à tort de
# VRAIES colonnes voisines distinctes sur le gabarit à 16 colonnes/branche
# (ex. GAT : "Automobile"/"Transport" fusionnées) — remis à 6pt, la marge de
# sécurité pour ce gabarit majoritaire est trop faible pour un seuil global
# unique. Voir CAS_PARTICULIERS_FULL_TABLE.md : le dédoublement de colonne
# de STAR (4 colonnes attendues, jusqu'à 8 obtenues) reste un défaut connu,
# non traité — les VALEURS restent correctement assignées à des colonnes
# cohérentes, seul le regroupement de libellés d'en-tête en est affecté.
ASSIGN_MAX_DIST = 25    # distance max (pt) pour rattacher un mot d'entete a une colonne


def _find_column_centers(lines, data_start_idx, gap=COL_GAP):
    all_x0 = []
    for line in lines[data_start_idx:]:
        for _val, x0 in _extract_numeric_clusters(line):
            all_x0.append(x0)
    all_x0.sort()
    centers, current = [], []
    for x in all_x0:
        if current and abs(x - current[-1]) <= gap:
            current.append(x)
        else:
            if current:
                centers.append(sum(current) / len(current))
            current = [x]
    if current:
        centers.append(sum(current) / len(current))
    return centers


def _nearest_index(x, centers, max_dist):
    best_i, best_d = None, max_dist + 1
    for i, c in enumerate(centers):
        d = abs(x - c)
        if d < best_d:
            best_d, best_i = d, i
    return best_i if best_d <= max_dist else None


def _build_columns(header_words, data_centers, max_dist=ASSIGN_MAX_DIST):
    """Rattache chaque mot d'en-tête à une colonne (centres déduits des
    données), reconstitue le libellé de chaque colonne, réinsère les
    colonnes sans aucune donnée (mot d'en-tête non assigné) à leur position
    réelle. Renvoie [(x_centre, libelle), ...] trié de gauche à droite."""
    from collections import defaultdict
    assigned = defaultdict(list)
    unassigned = []
    for w in header_words:
        idx = _nearest_index(w["x0"], data_centers, max_dist)
        if idx is not None:
            assigned[idx].append(w)
        else:
            unassigned.append(w)

    columns = []
    for i, c in enumerate(data_centers):
        ws = sorted(assigned.get(i, []), key=lambda w: (w["top"], w["x0"]))
        label = _normalizer.clean(" ".join(w["text"] for w in ws)) if ws else f"(colonne {i + 1})"
        columns.append((c, label))
    for w in unassigned:
        columns.append((w["x0"], _normalizer.clean(w["text"])))
    columns.sort(key=lambda t: t[0])
    return columns


def extract_full_table(page, min_data_clusters=MIN_DATA_CLUSTERS):
    """Extrait la grille complète (toutes lignes × toutes colonnes) d'une
    page de tableau annexe. Renvoie {"colonnes": [labels...], "lignes":
    {libelle_ligne: {colonne: valeur, ...}, ...}} ou None si la page ne
    ressemble pas à ce gabarit (aucune ligne multi-colonnes trouvée)."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)

    first_data_idx = None
    for idx, line in enumerate(lines):
        if len(_extract_numeric_clusters(line)) >= min_data_clusters:
            first_data_idx = idx
            break
    if first_data_idx is None or first_data_idx == 0:
        return None

    # Bloc d'en-tête = les lignes juste avant la première ligne de données,
    # en excluant le préambule fixe (société/date, "Annexe N°X", titre,
    # unité) — sans quoi ses mots ("Annexe", "13", "exprime", "dinars"...)
    # se mêlent aux vraies colonnes. Ce préambule se termine de façon très
    # régulière par la ligne d'unité "(exprimé en dinars tunisiens)",
    # identique sur tous les gabarits Annexe/Bilan/Etat de résultat déjà
    # rencontrés — ancre bien plus fiable qu'une heuristique positionnelle
    # (la ligne société/date contient elle-même 2 nombres — jour + année —
    # qu'un simple "recule tant qu'il n'y a pas de nombre" confond avec une
    # frontière de tableau). Repli sur l'ancienne heuristique positionnelle
    # si ce marqueur, jamais garanti à 100%, est absent d'un gabarit non
    # encore rencontré.
    # "en dinars" (pas la phrase complète "exprimé en dinars tunisiens") :
    # ancre volontairement plus large — variantes déjà rencontrées "chiffres
    # arrondis en dinars" (STAR), "unité en dinars" (BH/BIAT), "chiffres en
    # dinars tunisiens" (ASTREE). Toutes contiennent "en dinars".
    header_start = None
    for idx in range(min(first_data_idx, 6)):
        norm = _normalizer.clean(" ".join(w["text"] for w in lines[idx]))
        if "en dinars" in norm:
            header_start = idx + 1
            break
    if header_start is None:
        header_start = 0
        for idx in range(first_data_idx - 1, -1, -1):
            if len(_extract_numeric_clusters(lines[idx])) >= min_data_clusters:
                header_start = idx + 1
                break
    data_centers = _find_column_centers(lines, first_data_idx)
    if not data_centers:
        return None

    # Une ligne entre l'en-tête et la première ligne de données peut être un
    # sous-titre de section SANS valeur plutôt qu'une suite de l'en-tête de
    # colonnes (ex. STAR : "PRNV1 Primes acquises" juste avant "PRNV11
    # Primes émises et acceptées + [valeurs]" — un intitulé de poste, pas un
    # libellé de colonne). Un tel intitulé démarre dans la zone de la
    # colonne de LIBELLÉ (même x0 que les libellés de ligne, tout à gauche),
    # pas au-dessus des colonnes de valeurs — on ne garde donc, comme mots
    # d'en-tête de colonnes, que ceux positionnés à droite du début réel des
    # colonnes de données (avec une marge, l'en-tête étant souvent aligné à
    # gauche de sa colonne alors que les centres ci-dessus viennent des
    # valeurs, plutôt centrées/alignées à droite).
    HEADER_LEFT_MARGIN = 80
    header_left_bound = min(data_centers) - HEADER_LEFT_MARGIN
    header_words = [
        w for line in lines[header_start:first_data_idx] for w in line
        if w["x0"] >= header_left_bound
    ]

    columns = _build_columns(header_words, data_centers)
    col_names = [name for _x, name in columns]
    col_centers_final = [x for x, _name in columns]

    # Un libellé de ligne trop long pour tenir sur une seule ligne physique
    # se replie sur 2 (parfois 3) lignes visuelles, avec les VALEURS
    # verticalement centrées entre les deux moitiés du libellé (constaté sur
    # STAR, gabarit agrégé 4 colonnes : "Variation de la provision pour" /
    # [valeurs] / "primes non acquises") — la ligne de valeurs porte alors
    # elle-même un "libellé" qui n'est en réalité qu'un symbole de colonne
    # isolé ("+", "+/-", "-", une 3e colonne à part sur ce gabarit précis),
    # pas du texte de contenu. Reconstruction : les lignes sans aucune
    # valeur numérique sont accumulées comme préfixe ; à la première ligne
    # avec des valeurs, son propre "libellé" n'est retenu que s'il n'est pas
    # un symbole isolé ; la ligne suivante, si elle n'a elle-même aucune
    # valeur, est consommée comme suffixe (un seul niveau de repli après —
    # un repli plus long resterait partiellement reconstruit, cas connu et
    # documenté plutôt que traité ici).
    def _own_label_or_empty(line):
        lbl = _label_text(line)
        if lbl is None or _JUNK_LABEL_RE.match(lbl):
            return ""
        return lbl

    data_lines = list(lines[first_data_idx:])
    merged_rows = []  # [(label, [line, ...]), ...]
    prefix_words = []
    i = 0
    while i < len(data_lines):
        line = data_lines[i]
        clusters_now = _extract_numeric_clusters(line)
        if not clusters_now:
            prefix_words.append(_label_text(line))
            i += 1
            continue
        parts = [p for p in prefix_words if p]
        own = _own_label_or_empty(line)
        if own:
            parts.append(own)
        prefix_words = []
        value_lines = [line]
        # Un suffixe n'est consommé QUE si cette ligne de valeurs n'a
        # elle-même aucun libellé exploitable (le cas "libellé replié avec
        # les valeurs au milieu") — sinon la ligne suivante appartient à la
        # ligne logique SUIVANTE, pas à celle-ci (ex. STAR : "Primes émises
        # et acceptées" est déjà un libellé complet sur une seule ligne ;
        # la ligne suivante "Variation de la provision pour" est le début
        # du POSTE SUIVANT, pas sa suite — les y confondre fusionnerait à
        # tort deux lignes différentes du document).
        if not own and i + 1 < len(data_lines) and not _extract_numeric_clusters(data_lines[i + 1]):
            suffix = _label_text(data_lines[i + 1])
            if suffix:
                parts.append(suffix)
            i += 1
        label = _normalizer.clean(" ".join(parts)) if parts else None
        merged_rows.append((label, value_lines))
        i += 1

    rows = {}
    for label, value_lines in merged_rows:
        clusters = [c for vl in value_lines for c in _extract_numeric_clusters(vl)]
        if not clusters:
            continue
        if not label:
            continue
        row_values = {}
        for val, x0 in clusters:
            idx = _nearest_index(x0, col_centers_final, ASSIGN_MAX_DIST)
            if idx is not None:
                row_values[col_names[idx]] = val
        if row_values:
            # Deux lignes de libellé identique (rare, ex. sous-totaux
            # répétés) : la seconde écraserait la première — suffixée pour
            # ne perdre aucune ligne réelle du document.
            key = label
            n = 2
            while key in rows:
                key = f"{label} ({n})"
                n += 1
            rows[key] = row_values

    return {"colonnes": [c for c in col_names if c.strip()], "lignes": rows}


# Vocabulaire générique d'un tableau "résultat technique"/Annexe, en plus
# des regex étroites (ancrées en début de libellé) de l'extracteur 7-KPI —
# celles-ci ratent des lignes réelles dont la formulation diffère légèrement
# de la ligne utilisée par les dashboards (ex. STAR 2022-2025 : "Variation
# de la provision pour primes non acquises" plutôt que "Provisions pour
# primes non acquises"). Termes volontairement propres au vocabulaire
# assurantiel du tableau (pas une liste de mots génériques) pour continuer
# à exclure une page de prose qui ne fait que CITER le titre recherché
# (ex. GAT "F.2.6 Tableaux de raccordement... sont présentés au niveau
# de...", qui ne contient aucun de ces termes de poste comptable).
_GENERIC_LINE_ITEM_TERMS = (
    "primes emises", "primes acquises", "primes non acquises",
    "charge de sinistres", "charges de sinistres", "provision pour sinistres",
    "commissions", "frais d acquisition", "frais d administration",
    "resultat technique", "produits de placements", "provision pour primes",
    "cessions retrocessions", "charges techniques", "frais d exploitation",
)


def _sanity_ok(rows, kpi_patterns, min_matches=2):
    """Vérifie qu'au moins `min_matches` lignes extraites correspondent à un
    libellé de poste comptable réellement attendu sur ce tableau — d'abord
    via les regex étroites déjà validées de l'extracteur 7-KPI existant,
    puis via un vocabulaire plus large (`_GENERIC_LINE_ITEM_TERMS`) pour les
    variantes de formulation qu'elles ne couvrent pas. Filtre les pages qui
    satisfont le titre recherché mais sont en réalité une page de sommaire/
    notes mentionnant ce titre en prose (ex: GAT "F.2.6 Tableaux de
    raccordement... sont présentés au niveau de..."), pas le vrai tableau."""
    n = 0
    for label in rows:
        norm = _normalizer.clean(label)
        matched = any(pat.search(norm) for pat in kpi_patterns.values())
        if not matched:
            matched = any(term in norm for term in _GENERIC_LINE_ITEM_TERMS)
        if matched:
            n += 1
            if n >= min_matches:
                return True
    return False


def locate_and_extract_full_table(pdf, is_target_page, kpi_patterns, raccordement_re=None,
                                   max_pages=120, min_data_clusters=MIN_DATA_CLUSTERS, min_sanity_matches=2,
                                   extra_page_predicate=None):
    """Localise la bonne page dans `pdf` (réutilise le prédicat
    `is_target_page` déjà validé par l'extracteur 7-KPI correspondant —
    ex. annexe13_kpi_extractor._is_target_page — plutôt qu'une détection de
    page indépendante) puis y extrait la grille complète. Essaie TOUTES les
    pages candidates (une page peut à tort sembler correspondre — sommaire,
    notes en prose citant le même titre) et retient celle dont la grille
    extraite est la plus riche (le plus de colonnes) parmi celles qui
    passent le contrôle de vraisemblance (`_sanity_ok`). Renvoie
    (numero_page_1_indexe, grille) ou (None, None) si aucune page valide.

    `extra_page_predicate`, si fourni, est essayé EN PLUS de `is_target_page`
    (union des deux, pas remplacement) — sert à récupérer des pages qu'une
    règle volontaire du prédicat partagé exclut à tort pour cet usage précis
    (ex. LLOYD_TUNISIEN : sa page réelle est titrée "Notes sur le résultat
    technique par catégorie...", exclue par `NOTES_SECTION_RE` dans
    `annexe13_kpi_extractor._is_target_page` — une règle qui reste
    nécessaire pour le pipeline 7-KPI existant, donc non modifiée ici).
    Le contrôle de vraisemblance ci-dessous protège contre les faux positifs
    supplémentaires qu'un prédicat plus permissif pourrait introduire."""
    candidates = []
    for i, page in enumerate(pdf.pages[:max_pages]):
        if is_target_page(page) or (extra_page_predicate and extra_page_predicate(page)):
            candidates.append((i, page))
    if raccordement_re is not None:
        def _norm_head(page):
            return _normalizer.clean((page.extract_text() or "")[:300])
        candidates.sort(key=lambda t: bool(raccordement_re.search(_norm_head(t[1]))))

    best = None
    for i, page in candidates:
        result = extract_full_table(page, min_data_clusters=min_data_clusters)
        if not result or len(result["colonnes"]) < 3 or len(result["lignes"]) < min_sanity_matches:
            continue
        if not _sanity_ok(result["lignes"], kpi_patterns, min_sanity_matches):
            continue
        if best is None or len(result["colonnes"]) > len(best[1]["colonnes"]):
            best = (i, result)
    if best is None:
        return None, None
    return best[0] + 1, best[1]
