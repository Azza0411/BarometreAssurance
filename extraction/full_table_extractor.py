"""Extraction "grille complète" d'un tableau annexe (toutes les lignes,
toutes les colonnes par branche) — contrairement à annexe12_kpi_extractor.py
et annexe13_kpi_extractor.py qui ne récupèrent QUE les 7 lignes/1 colonne
("Montant" total) dont les dashboards ont besoin.

Motivation (retour utilisateur, page Gestion de données) : l'export Excel
doit pouvoir montrer le tableau annexe tel qu'il existe réellement dans le
PDF source (toutes les branches — Automobile, Transport, Incendie...), pas
seulement le sous-ensemble déjà utilisé par les dashboards.

Moteur : camelot (flavor='stream'), pas pdfplumber (2026-09-08, remplace une
première version bâtie sur le repositionnement de mots pdfplumber — voir
historique git pour cette approche). Comparé côte à côte sur GAT (16
colonnes/branche), STAR (page "Annexe 13" réelle ET page agrégée à libellés
repliés), BIAT et ASTREE : camelot restitue une vraie grille alignée
nativement (détection de tableau par blancs/lignes, via Ghostscript) là où
l'approche pdfplumber nécessitait une pile d'heuristiques fragiles
(regroupement de centres de colonnes par tolérance, marge gauche d'en-tête,
dédoublement de colonnes...) et échouait encore sur certains gabarits — ex.
ASTREE, dont le texte d'en-tête était rendu par pdfplumber avec des lettres
individuellement espacées ("s p o n s a b i e c e n n a l e"), un problème
que camelot n'a simplement pas.

Principe :
  1. Repérer, sur la première ligne de données réelle (≥ MIN_DATA_CELLS
     cellules numériques), l'index de colonne où commencent les valeurs —
     tout ce qui précède est la zone "libellé" (parfois 1 seule colonne,
     parfois 2 quand le tableau porte un code de ligne interne en plus du
     libellé, ex. "PRNV11" — voir gabarit STAR agrégé ci-dessous).
  2. Construire le libellé de chaque colonne de valeur en concaténant
     verticalement ses cellules non vides dans les lignes d'en-tête (bien
     plus simple qu'un rattachement par position X : camelot aligne déjà
     chaque fragment d'en-tête replié dans la bonne colonne).
  3. Un libellé de LIGNE trop long pour tenir sur une seule ligne physique
     peut se replier sur 2 lignes avec les valeurs "sandwichées" entre les
     deux moitiés (gabarit STAR agrégé — page "Etat de résultat technique",
     PAS la vraie page Annexe 13) : les lignes sans aucune valeur sont
     accumulées comme préfixe ; si la ligne de valeurs n'a elle-même aucun
     libellé exploitable, la ligne suivante (si elle-même sans valeur) est
     consommée comme suffixe.

Limite connue : cette heuristique cible la mise en page des tableaux
Annexe 12/13 (et gabarits proches). Le Bilan (Brut/Amortissement/Net/
Net N-1, pas de branches) et les tableaux Takaful (Annexes 14/15) ont une
structure différente et ne sont pas couverts par ce module pour l'instant."""

import re

from extraction.bilan_kpi_extractor import _normalizer, ROW_CODE_PREFIX_RE
from extraction.annexe13_kpi_extractor import (
    NON_VIE_RE as _A13_NON_VIE_RE, VIE_RE as _A13_VIE_RE,
)

# Titre élargi par rapport à annexe13_kpi_extractor.PAGE_TITLE_RE (non
# modifié, partagé avec le pipeline 7-KPI existant) : accepte aussi le
# connecteur "de la catégorie" en plus de "par catégorie" entre "résultat
# technique" et "catégorie" — découvert sur STAR, dont la VRAIE page Annexe
# 13 (par branche : Groupe/A.Travail/Incendie/Risques Divers/Transport/
# Aviation/Automobile/Acceptation/Total, page 32 du document 2024) est
# titrée "Résultat technique DE LA catégorie d'Assurance Non-Vie" — un
# titre que le module partagé ne reconnaît pas (regex ancrée sur "par
# catégorie"), ce qui faisait retomber la localisation de page sur "L'état
# de résultat technique de l'assurance non-vie" (page 4), une page de
# RECONCILIATION brut/cessions/net à 4 colonnes agrégées, pas la vraie
# grille par branche demandée. Les 7 KPI du pipeline existant restent
# corrects dans les deux cas (même total, présenté différemment) donc le
# module partagé n'a pas besoin d'être touché ; mais pour la grille
# complète, seule la vraie page Annexe 13 a la bonne structure.
_FULL_TABLE_PAGE_TITLE_RE = re.compile(
    r"resultat technique (?:non.?vie |vie )?(?:par|de la) categorie"
    r"|resultat technique (?:non.?vie|vie) de\b"
    r"|raccordement du resultat technique"
    r"|etat de resultat technique de l.?assurance"
)


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
    if not _FULL_TABLE_PAGE_TITLE_RE.search(normalized):
        return False
    if _A13_NON_VIE_RE.search(normalized):
        return True
    return not _A13_VIE_RE.search(normalized)


_JUNK_LABEL_RE = re.compile(r"^[+\-/\s]+$")

MIN_DATA_CELLS = 4  # une vraie ligne de donnees a au moins 4 cellules numeriques (la
# ligne société/date du préambule peut déjà contenir jusqu'à 3 nombres —
# jour, mois si chiffré, année — sans être une ligne de données).

# Une cellule camelot entière (pas un mot-token pdfplumber) : "126 336 369",
# "(4 086 562)" (négatif comptable), "0", "-" (case vide/néant). Les espaces
# internes sont des séparateurs de milliers, jamais un espace de mise en
# page (camelot a déjà isolé chaque valeur dans sa propre cellule).
_CELL_NUMERIC_RE = re.compile(r"^\(?-?\d[\d\s.,]*\)?$")


def _looks_numeric_cell(text):
    text = (text or "").strip()
    if text in ("-", "–", "—"):
        return True  # case "néant" du tableau — compte comme une valeur structurelle
    return bool(_CELL_NUMERIC_RE.match(text))


def _clean_cell_value(text):
    """Convertit une cellule camelot en float, ou None si vide/non numérique
    (y compris un tiret seul "néant" — présent structurellement mais sans
    valeur). Parenthèses = négatif (notation comptable standard) ; espaces
    internes = séparateur de milliers."""
    text = (text or "").strip()
    if not text or text in ("-", "–", "—"):
        return None
    negative = text.startswith("(") and text.endswith(")")
    if not _CELL_NUMERIC_RE.match(text):
        return None
    # Espaces normaux ET insécables \xa0/  (courants dans les nombres au
    # format français rendus par certains PDF) : tous des séparateurs de
    # milliers, jamais un espace de mise en page (camelot isole déjà chaque
    # valeur dans sa propre cellule).
    core = re.sub(r"\s+", "", text.strip("()"), flags=re.UNICODE).replace(",", ".")
    try:
        value = float(core)
    except ValueError:
        return None
    return -value if negative else value


def _find_table_camelot(pdf_path, page_num):
    import camelot
    try:
        tables = camelot.read_pdf(pdf_path, flavor="stream", pages=str(page_num))
    except Exception:
        return None
    if tables.n == 0:
        return None
    # Une page peut produire plusieurs détections (légendes, notes de bas de
    # page...) — le vrai tableau est presque toujours celui qui a le plus de
    # lignes.
    return max((t.df for t in tables), key=lambda df: df.shape[0])


def extract_full_table_camelot(pdf_path, page_num, min_data_cells=MIN_DATA_CELLS):
    """Extrait la grille complète (toutes lignes × toutes colonnes) de la
    page `page_num` (1-indexée) via camelot. Renvoie {"colonnes":
    [labels...], "lignes": {libelle_ligne: {colonne: valeur, ...}, ...}} ou
    None si la page ne ressemble pas à ce gabarit."""
    df = _find_table_camelot(pdf_path, page_num)
    if df is None or df.empty:
        return None
    rows_raw = df.values.tolist()
    n_cols_total = df.shape[1]

    # Seuil de détection de la première ligne de données adapté à la largeur
    # réelle du tableau : une société mono-branche (ex. COTUNACE, uniquement
    # "Crédit-Caution") n'a que 1-2 colonnes de valeurs — le seuil global
    # (conçu pour les gabarits multi-branches à 4-16 colonnes) ne trouverait
    # jamais de ligne de données sur un tableau aussi étroit. Toujours borné
    # à au moins 1.
    effective_min_data_cells = min(min_data_cells, max(1, n_cols_total - 1))

    first_data_idx = None
    for idx, row in enumerate(rows_raw):
        if sum(1 for cell in row if _looks_numeric_cell(cell)) >= effective_min_data_cells:
            first_data_idx = idx
            break
    if first_data_idx is None or first_data_idx == 0:
        return None

    # Colonne à partir de laquelle commencent les VALEURS, déterminée sur la
    # première VRAIE ligne de données (fiable — une ligne d'en-tête repliée
    # sur plusieurs lignes physiques ne l'est pas). Tout ce qui précède est
    # la zone "libellé" — 1 seule colonne en général (GAT, BIAT, vraie page
    # Annexe 13 de STAR), 2 quand le tableau porte un code de ligne interne
    # à part du libellé (ex. "PRNV11", gabarit STAR agrégé).
    numeric_col_idxs = [i for i, cell in enumerate(rows_raw[first_data_idx]) if _looks_numeric_cell(cell)]
    if not numeric_col_idxs:
        return None
    label_col_end = min(numeric_col_idxs)

    # Ancre "en dinar" (sans le "s" final — variantes déjà rencontrées
    # "chiffres arrondis en dinars", "unité en dinars", "(Exprimé en dinar
    # tunisien)" singulier) : le préambule (société/date, "Annexe N°X",
    # titre, unité) se termine régulièrement par cette ligne, bien plus
    # fiable qu'une heuristique positionnelle pour délimiter le bloc d'en-tête.
    header_start = None
    for idx in range(min(first_data_idx, 6)):
        norm = _normalizer.clean(" ".join(rows_raw[idx]))
        if "en dinar" in norm:
            header_start = idx + 1
            break
    # Repli : certains gabarits (ex. BIAT, Annexe 13) n'ont AUCUNE ligne
    # d'unité monétaire — le titre de page enchaîne directement sur l'en-tête
    # de colonnes. On reconnaît alors le titre lui-même (même motif que celui
    # qui a servi à repérer la page) et démarre l'en-tête juste après.
    if header_start is None:
        for idx in range(min(first_data_idx, 4)):
            norm = _normalizer.clean(" ".join(rows_raw[idx]))
            if _FULL_TABLE_PAGE_TITLE_RE.search(norm):
                header_start = idx + 1
    if header_start is None:
        header_start = 0
        for idx in range(first_data_idx - 1, -1, -1):
            if sum(1 for cell in rows_raw[idx] if _looks_numeric_cell(cell)) >= effective_min_data_cells:
                header_start = idx + 1
                break

    # Colonne dupliquée telle-quelle dans le PDF source : constaté sur
    # COTUNACE (chaque libellé d'en-tête ET chaque valeur de la grille
    # "Crédit-Caution" est répété mot-pour-mot deux fois côte à côte dans le
    # flux de texte source — probablement un artefact de génération du PDF,
    # pas une vraie 2e colonne). Détecté ici plutôt que corrigé à la main
    # pour cette seule société : une colonne de valeur est écartée si son
    # en-tête brut ET la totalité de ses cellules de données sont identiques,
    # caractère pour caractère, à la colonne de valeur immédiatement
    # précédente déjà conservée — un vrai doublon (Brut/Net réellement
    # distincts) n'a jamais des valeurs identiques sur TOUTES les lignes.
    value_col_idxs = list(range(label_col_end, n_cols_total))
    kept_col_idxs = []
    for col_idx in value_col_idxs:
        header_raw = "".join(rows_raw[r][col_idx].strip() for r in range(header_start, first_data_idx))
        if kept_col_idxs:
            prev = kept_col_idxs[-1]
            prev_header_raw = "".join(rows_raw[r][prev].strip() for r in range(header_start, first_data_idx))
            same_header = header_raw == prev_header_raw
            same_values = all(
                rows_raw[r][col_idx].strip() == rows_raw[r][prev].strip()
                for r in range(first_data_idx, len(rows_raw))
            )
            if same_header and same_values:
                continue  # doublon exact du flux source — pas une colonne distincte
        kept_col_idxs.append(col_idx)

    # Libellé de chaque colonne de valeur = concaténation verticale de ses
    # cellules non vides dans les lignes d'en-tête (camelot aligne déjà
    # chaque fragment replié dans la bonne colonne — pas besoin de
    # rattachement par position).
    col_names = []
    for col_idx in kept_col_idxs:
        parts = [rows_raw[r][col_idx].strip() for r in range(header_start, first_data_idx) if rows_raw[r][col_idx].strip()]
        label = _normalizer.clean(" ".join(parts)) if parts else f"(colonne {col_idx})"
        col_names.append(label)

    # Deux colonnes peuvent se voir attribuer le même libellé nettoyé
    # (rare mais déjà rencontré) — distinguer par suffixe plutôt que de les
    # laisser se confondre en aval (silencieusement en Excel, ou en erreur
    # d'unicité au stockage).
    seen_names, deduped = {}, []
    for name in col_names:
        n = seen_names.get(name, 0) + 1
        seen_names[name] = n
        deduped.append(name if n == 1 else f"{name} ({n})")
    col_names = deduped

    def _row_own_label(row):
        cells = [c.strip() for c in row[:label_col_end] if c.strip()]
        text = _normalizer.clean(" ".join(cells)) if cells else ""
        text = ROW_CODE_PREFIX_RE.sub("", text, count=1)
        if not text or _JUNK_LABEL_RE.match(text):
            return ""
        return text

    def _row_has_values(row):
        return any(_looks_numeric_cell(cell) for cell in row[label_col_end:])

    # Un libellé de ligne trop long pour tenir sur une seule ligne physique
    # se replie sur 2 lignes, avec les VALEURS "sandwichées" entre les deux
    # moitiés (constaté sur le gabarit STAR agrégé — pas la vraie page
    # Annexe 13 : "Variation de la provision pour" / [valeurs] / "primes non
    # acquises"). Le suffixe n'est consommé QUE si la ligne de valeurs n'a
    # elle-même aucun libellé exploitable — sinon la ligne suivante est le
    # début du POSTE SUIVANT, pas la suite de celui-ci (les confondre
    # fusionnerait à tort deux postes distincts).
    merged_rows = []  # [(label, value_row), ...]
    prefix_parts = []
    i = first_data_idx
    while i < len(rows_raw):
        row = rows_raw[i]
        if not _row_has_values(row):
            own = _row_own_label(row)
            if own:
                prefix_parts.append(own)
            i += 1
            continue
        own = _row_own_label(row)
        parts = list(prefix_parts)
        if own:
            parts.append(own)
        prefix_parts = []
        if not own and i + 1 < len(rows_raw) and not _row_has_values(rows_raw[i + 1]):
            suffix = _row_own_label(rows_raw[i + 1])
            if suffix:
                parts.append(suffix)
            i += 1
        label = _normalizer.clean(" ".join(parts)) if parts else None
        merged_rows.append((label, row))
        i += 1

    rows = {}
    for label, value_row in merged_rows:
        if not label:
            continue
        row_values = {}
        for pos, col_idx in enumerate(kept_col_idxs):
            val = _clean_cell_value(value_row[col_idx])
            if val is not None:
                row_values[col_names[pos]] = val
        if row_values:
            # Deux lignes de libellé identique (rare, ex. sous-totaux
            # répétés) : la seconde écraserait la première — suffixée pour
            # ne perdre aucune ligne réelle du document.
            key, n = label, 2
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


_ANNEXE_TITLE_RE = re.compile(r"\bannexe\b")


def locate_and_extract_full_table(pdf_path, is_target_page, kpi_patterns, raccordement_re=None,
                                   max_pages=120, min_data_cells=MIN_DATA_CELLS, min_sanity_matches=2,
                                   extra_page_predicate=None):
    """Localise la bonne page dans le PDF `pdf_path` (réutilise le prédicat
    `is_target_page` déjà validé par l'extracteur 7-KPI correspondant —
    ex. annexe13_kpi_extractor._is_target_page — plutôt qu'une détection de
    page indépendante ; l'exploration des pages candidates se fait via
    pdfplumber, léger et déjà utilisé par ce prédicat) puis y extrait la
    grille complète via camelot. Essaie TOUTES les pages candidates (une
    page peut à tort sembler correspondre — sommaire, notes en prose citant
    le même titre) et retient celle dont la grille extraite est la plus
    riche (le plus de colonnes) parmi celles qui passent le contrôle de
    vraisemblance (`_sanity_ok`). Renvoie (numero_page_1_indexe, grille) ou
    (None, None) si aucune page valide.

    `extra_page_predicate`, si fourni, est essayé EN PLUS de `is_target_page`
    (union des deux, pas remplacement) — sert à récupérer des pages qu'une
    règle volontaire du prédicat partagé exclut à tort pour cet usage précis
    (ex. LLOYD_TUNISIEN : sa page réelle est titrée "Notes sur le résultat
    technique par catégorie...", exclue par `NOTES_SECTION_RE` dans
    `annexe13_kpi_extractor._is_target_page` — une règle qui reste
    nécessaire pour le pipeline 7-KPI existant, donc non modifiée ici).
    Le contrôle de vraisemblance ci-dessous protège contre les faux positifs
    supplémentaires qu'un prédicat plus permissif pourrait introduire."""
    import pdfplumber

    candidates = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            if is_target_page(page) or (extra_page_predicate and extra_page_predicate(page)):
                head = _normalizer.clean((page.extract_text() or "")[:300])
                candidates.append((i, head))

    if raccordement_re is not None:
        candidates.sort(key=lambda t: bool(raccordement_re.search(t[1])))

    # Une page effectivement titrée "Annexe N°X" est LA page officielle du
    # tableau — à préférer sur toute autre page qui se contente d'évoquer un
    # "résultat technique" en passant (ex. une page de sommaire/renvoi sans
    # rapport avec le tableau, qui pourrait produire par accident plus de
    # "colonnes" que la vraie page). On départage d'abord sur ce signal,
    # robuste car indépendant de la reconstruction elle-même, puis seulement
    # ensuite sur le nombre de colonnes.
    best = None
    for i, head in candidates:
        result = extract_full_table_camelot(pdf_path, i + 1, min_data_cells=min_data_cells)
        # Seuil de colonnes minimal abaissé à 1 (au lieu de 3) : une société
        # mono-branche (ex. COTUNACE — uniquement "Crédit-Caution") produit
        # une grille valide à une seule colonne de valeur. Le filtrage des
        # faux positifs reste assuré par `_sanity_ok` ci-dessous (labels de
        # poste comptable réellement attendus), pas par un compte de
        # colonnes qui pénaliserait injustement les petites sociétés.
        if not result or len(result["colonnes"]) < 1 or len(result["lignes"]) < min_sanity_matches:
            continue
        if not _sanity_ok(result["lignes"], kpi_patterns, min_sanity_matches):
            continue
        is_annexe_titled = bool(_ANNEXE_TITLE_RE.search(head))
        rank = (is_annexe_titled, len(result["colonnes"]))
        if best is None or rank > best[2]:
            best = (i, result, rank)
    if best is not None:
        return best[0] + 1, best[1]

    # Repli : aucune page "Annexe N°13" unique exploitable. Quelques
    # documents (ex. BNA 2024 = ex-AMI, année de bascule de gabarit — et
    # AMI 2021/2022 sous l'ancien nom, même format) éclatent les mêmes
    # chiffres Non-Vie dans la section narrative « Notes sur les Comptes de
    # Résultats », une dizaine de petits tableaux par poste. On tente de les
    # recoller en une grille au même contrat, filtrée par le MÊME contrôle de
    # vraisemblance que la voie normale.
    from extraction.notes_resultat_extractor import assemble_non_vie_grid_from_notes

    try:
        notes_page, notes_grid = assemble_non_vie_grid_from_notes(pdf_path, max_pages=max_pages)
    except Exception:
        # Ce chemin n'est atteint que sur des documents déjà en échec par la
        # voie normale : un plantage du repli ne doit pas être pire qu'un
        # échec franc.
        return None, None
    if (
        notes_grid
        and len(notes_grid["colonnes"]) >= 1
        and len(notes_grid["lignes"]) >= min_sanity_matches
        and _sanity_ok(notes_grid["lignes"], kpi_patterns, min_sanity_matches)
    ):
        return notes_page, notes_grid
    return None, None
