"""Repli pour les documents CMF SANS page "Annexe N°13" unique : réassemble
une grille "Résultat technique Non-Vie" à partir de la section narrative
« V - Notes sur les Comptes de Résultats ».

Contexte (voir extraction/CAS_PARTICULIERS_FULL_TABLE.md, entrée 2026-09-09
sur BNA) : certains documents ne publient pas la grille Annexe 13 par
branche. Les mêmes chiffres Non-Vie y sont présents mais éclatés en une
dizaine de petits tableaux, un par poste comptable, chacun précédé de son
code de rubrique ("PRNV1- Primes acquises", "CHNV1- Charges de sinistres",
"CHNV4- Frais d'exploitation"...) et intercalé dans de la prose. Chaque
petit tableau a les mêmes 4 colonnes de réconciliation : Opérations brutes N
/ Cessions / Opérations nettes N / Opérations nettes N-1.

Ce module repère la section (titre « Notes sur les Comptes de Résultats »),
extrait chaque petit tableau des rubriques Non-Vie (préfixes de code PRNV /
CHNV / RTNV — les rubriques Vie PRV/CHV/RTV et non-techniques PRNT/CHNT sont
ignorées) et les recolle en une seule grille au format exact de
extraction/full_table_extractor.extract_full_table_camelot
({"colonnes": [...], "lignes": {...}}), pour être branché en REPLI dans
full_table_extractor.locate_and_extract_full_table.

La grille obtenue n'a PAS de ventilation par branche (le document ne la
fournit pas) : ses colonnes sont les 4 colonnes Brut/Cessions/Net-N/Net-N-1,
comme une page « raccordement » (déjà couverte par le pipeline 7-KPI via
annexe13_kpi_extractor). Les identités comptables de validation
(annexe13_pipeline.VALIDATION_RULES) restent applicables colonne par colonne.

Rien ici n'est spécifique à une société : le gabarit « Notes sur les Comptes
de Résultats » et les codes de rubrique PRNV/CHNV/RTNV sont la nomenclature
réglementaire commune du plan comptable des assurances tunisien.
"""

import itertools
import re

from extraction.bilan_kpi_extractor import (
    NUMBER_GAP_THRESHOLD,
    NUMERIC_TOKEN_RE,
    ROW_CODE_PREFIX_RE,
    _MINUS_NORMALIZE_RE,
    _cluster_lines,
    _normalizer,
    _words_with_bracket_negatives_resolved,
)

# Titre de la section (après normalisation). Singulier/pluriel tolérés.
_SECTION_TITLE_RE = re.compile(r"notes sur les comptes de resultats?")

# Marqueur de la section SUIVANTE (chiffres romains VI et au-delà, suivis de
# "Note(s) sur") — sert à borner la fin de la section « V ». On ne liste pas
# "v" pour ne pas s'arrêter sur le titre de la section elle-même.
_NEXT_SECTION_RE = re.compile(r"\b(?:vi{1,3}|ix|xi{0,3})\s*[-–]\s*notes?\s+sur\b")

# Ligne de code de rubrique : un code en capitales + éventuels chiffres,
# suivi d'un tiret puis d'un libellé (ex. "PRNV1- Primes acquises",
# "CHNV41 - Frais d'acquisition non vie"). Testé sur le TEXTE BRUT (les codes
# sont littéralement en capitales dans le PDF), pas sur le texte normalisé.
_CODE_MARKER_RE = re.compile(r"^([A-Z]{2,5}\d{0,3})\s*[-–]\s+\S")

# Préfixes de rubrique retenus = Non-Vie technique uniquement.
#   PR = produits, CH = charges, RT = résultat technique ; NV = Non-Vie.
# Exclus : PRV/CHV/RTV (Vie), PRNT/CHNT (produits/charges NON techniques =
# placements alloués), PA*/AC*/CP* (postes de bilan).
_NON_VIE_PREFIXES = {"PRNV", "CHNV", "RTNV"}

# Ligne d'en-tête d'un petit tableau de réconciliation.
def _is_recon_header(norm):
    return (
        "operations" in norm
        and "cessions" in norm
        and ("brutes" in norm or "nettes" in norm or "designations" in norm)
    )


_DASH_CHARS = {"-", "‐", "‑", "‒", "–", "—", "−"}
_JUNK_LABEL_RE = re.compile(r"^[+\-/\s]+$")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_N_COLS = 4
# Une valeur d'un tableau résultat technique est un montant en dinars (≥ 4
# chiffres en pratique) : sert à distinguer une vraie ligne de données d'une
# ligne d'années d'en-tête ("... 2024 ... 2023 ...").
_MIN_REAL_VALUE = 3000


def _code_prefix(code):
    """"PRNV1" -> "PRNV", "CHNV41" -> "CHNV"."""
    m = re.match(r"^[A-Z]+", code)
    return m.group(0) if m else code


def _parse_reconciliation_row(line):
    """Découpe une ligne clusterisée en (libellé_normalisé, champs) où
    `champs` est la liste ordonnée gauche→droite des cellules de valeur
    après le libellé, sous forme de couples (bord_droit_x1, valeur|None) —
    un tiret isolé (« néant ») est une cellule explicitement vide.

    Le bord DROIT (x1 du dernier token) sert de position de colonne : les
    montants de ce gabarit sont alignés à droite, ce qui rend x1 bien plus
    stable que x0 (qui varie avec le nombre de chiffres)."""
    words = _words_with_bracket_negatives_resolved(line)
    fields = []          # (x1, valeur|None)
    cur = []             # tokens numériques en cours d'agrégation

    def flush():
        if not cur:
            return
        raw = _MINUS_NORMALIZE_RE.sub("-", "".join(t["text"] for t in cur))
        try:
            val = float(raw.replace(",", "."))
        except ValueError:
            val = None
        if val is not None:
            fields.append((cur[-1]["x1"], val))
        cur.clear()

    label_parts = []
    started = False
    for w in words:
        t = w["text"].strip()
        is_num = bool(NUMERIC_TOKEN_RE.match(t))
        is_dash = t in _DASH_CHARS
        if not started:
            if is_num or is_dash:
                started = True
            else:
                label_parts.append(w["text"])
                continue
        if is_num:
            if cur and (w["x0"] - cur[-1]["x1"]) > NUMBER_GAP_THRESHOLD:
                flush()
            cur.append(w)
        elif is_dash:
            flush()
            fields.append((w["x1"], None))
        else:
            # token non numérique tombé dans la zone des valeurs (fragment
            # de libellé replié sur la même ligne visuelle) — ignoré.
            flush()
    flush()

    label = _normalizer.clean(" ".join(label_parts))
    label = ROW_CODE_PREFIX_RE.sub("", label, count=1)
    # Un tiret « néant » traînant en fin de libellé (ex. "commissions recues
    # des -") : retiré, ce n'est pas du texte.
    label = re.sub(r"[\s‐-―−-]+$", "", label).strip()
    return label, fields


def _align_fields_to_columns(fields, ref_x1):
    """Associe chaque champ (bord droit x1) à l'une des `_N_COLS` colonnes,
    dont les bords droits de référence sont `ref_x1` (triés). Renvoie
    {index_colonne: valeur}. Si une cellule « néant » manque (3 champs pour
    4 colonnes), on cherche la combinaison de colonnes conservées qui
    minimise la distance totale — plus robuste qu'un simple placement
    positionnel."""
    fields = sorted(fields, key=lambda f: f[0])
    ref = sorted(ref_x1)
    n, m = len(fields), len(ref)
    if not ref or n >= m:
        return {k: fields[k][1] for k in range(min(n, m))}
    best, best_cost = None, None
    for kept in itertools.combinations(range(m), n):
        cost = sum(abs(fields[i][0] - ref[kept[i]]) for i in range(n))
        if best_cost is None or cost < best_cost:
            best_cost, best = cost, kept
    return {best[i]: fields[i][1] for i in range(n)}


class _SubTable:
    __slots__ = ("kpi_label", "year_n", "year_prev", "rows")

    def __init__(self, kpi_label):
        self.kpi_label = kpi_label
        self.year_n = None
        self.year_prev = None
        self.rows = []   # (libellé_normalisé, is_total, [(x1, val|None), ...])


def _collect_section_lines(pdf, max_pages, max_section_pages=8):
    """Localise la section « Notes sur les Comptes de Résultats » et renvoie
    (page_1_indexée_du_début, [lignes clusterisées de la section]) ou
    (None, []) si la section n'existe pas."""
    start = None
    for i, page in enumerate(pdf.pages[:max_pages]):
        head = _normalizer.clean((page.extract_text() or "")[:800])
        if _SECTION_TITLE_RE.search(head):
            start = i
            break
    if start is None:
        return None, []
    lines = []
    for page in pdf.pages[start:start + max_section_pages]:
        for ln in _cluster_lines(page.extract_words() or []):
            lines.append(ln)
    return start + 1, lines


def _iter_subtables(lines):
    """Machine à états qui parcourt les lignes de la section et produit les
    petits tableaux des rubriques Non-Vie (voir _NON_VIE_PREFIXES)."""
    current_prefix = None
    current_kpi_label = None
    sub = None                 # _SubTable en cours de remplissage
    expecting_year_line = False
    prefix_parts = []          # fragments de libellé value-less en attente

    i = 0
    while i < len(lines):
        line = lines[i]
        raw = " ".join(w["text"] for w in line).strip()
        norm = _normalizer.clean(raw)

        if _NEXT_SECTION_RE.search(norm):
            break

        m = _CODE_MARKER_RE.match(raw)
        if m:
            if sub is not None:
                yield sub
                sub = None
            code = m.group(1)
            current_prefix = _code_prefix(code)
            current_kpi_label = raw[m.end(1):].lstrip(" -–").strip()
            expecting_year_line = False
            prefix_parts = []
            i += 1
            continue

        if sub is None and current_prefix in _NON_VIE_PREFIXES and _is_recon_header(norm):
            sub = _SubTable(_normalizer.clean(current_kpi_label or ""))
            expecting_year_line = True
            prefix_parts = []
            i += 1
            continue

        if sub is None:
            i += 1
            continue

        # --- à l'intérieur d'un petit tableau ---
        label, fields = _parse_reconciliation_row(line)

        if expecting_year_line:
            yrs = [int(y) for y in _YEAR_RE.findall(raw)]
            big = [v for _, v in fields if v is not None and abs(v) >= _MIN_REAL_VALUE]
            expecting_year_line = False
            if yrs and not big:
                sub.year_n = max(yrs)
                sub.year_prev = min(yrs) if min(yrs) != max(yrs) else max(yrs) - 1
                i += 1
                continue
            # pas de ligne d'années dédiée : on enchaîne sur les données.

        if not fields:
            # ligne sans valeur : fragment de libellé pour la ligne SUIVANTE,
            # sauf si c'est de la prose (fin implicite du tableau).
            if label and len(label.split()) <= 6 and not _JUNK_LABEL_RE.match(label):
                prefix_parts.append(label)
                i += 1
                continue
            yield sub
            sub = None
            prefix_parts = []
            i += 1
            continue

        parts = list(prefix_parts)
        prefix_parts = []
        own = "" if _JUNK_LABEL_RE.match(label) else label
        if own:
            parts.append(own)
        # continuation traînante : ligne suivante sans valeur et courte
        # (ex. "reportés", "réassureurs" rejetés sous leur ligne de valeurs).
        if i + 1 < len(lines):
            nxt_label, nxt_fields = _parse_reconciliation_row(lines[i + 1])
            nxt_raw = " ".join(w["text"] for w in lines[i + 1]).strip()
            if (
                not nxt_fields
                and nxt_label
                and len(nxt_label.split()) <= 3
                and not _CODE_MARKER_RE.match(nxt_raw)
                and nxt_label != "total en dt"
            ):
                parts.append(nxt_label)
                i += 1

        full_label = " ".join(p for p in parts if p).strip()
        is_total = full_label.startswith("total en dt") or full_label == "total"
        key = sub.kpi_label if (is_total and sub.kpi_label) else full_label
        sub.rows.append((key, is_total, fields))
        i += 1
        if is_total:
            yield sub
            sub = None
            prefix_parts = []

    if sub is not None:
        yield sub


def assemble_non_vie_grid_from_notes(pdf_path, max_pages=120):
    """Réassemble une grille "Résultat technique Non-Vie" à partir de la
    section « Notes sur les Comptes de Résultats » de `pdf_path`.

    Renvoie (page_1_indexée_du_début_de_section, grille) au format
    {"colonnes": [...], "lignes": {libellé_normalisé: {colonne: valeur}}} —
    identique au contrat de full_table_extractor.extract_full_table_camelot —
    ou (None, None) si la section est absente ou ne contient aucun petit
    tableau Non-Vie exploitable."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        section_page, lines = _collect_section_lines(pdf, max_pages)
        if section_page is None:
            return None, None
        subtables = [s for s in _iter_subtables(lines) if s.rows]

    if not subtables:
        return None, None

    # Années : la première rubrique tabulée fait foi ; repli sur le nom de
    # fichier ("CODE_2024.pdf").
    year_n = year_prev = None
    for s in subtables:
        if s.year_n:
            year_n, year_prev = s.year_n, s.year_prev
            break
    if year_n is None:
        m = re.search(r"_(\d{4})\.pdf$", pdf_path)
        if m:
            year_n = int(m.group(1))
            year_prev = year_n - 1
    suffix_n = str(year_n) if year_n else "n"
    suffix_prev = str(year_prev) if year_prev else "n-1"
    col_names = [
        _normalizer.clean(f"Operations brutes {suffix_n}"),
        _normalizer.clean(f"Cessions {suffix_n}"),
        _normalizer.clean(f"Operations nettes {suffix_n}"),
        _normalizer.clean(f"Operations nettes {suffix_prev}"),
    ]

    lignes = {}
    for sub in subtables:
        # Bords droits de référence des 4 colonnes : la ligne du tableau qui
        # a le plus de champs (à égalité, la ligne « Total en DT », toujours
        # complète).
        ref_row = max(
            sub.rows,
            key=lambda r: (len(r[2]), 1 if r[1] else 0),
        )
        ref_x1 = sorted(x1 for x1, _ in ref_row[2])

        for label, _is_total, fields in sub.rows:
            assigned = _align_fields_to_columns(fields, ref_x1)
            values = {
                col_names[j]: v
                for j, v in assigned.items()
                if v is not None and j < _N_COLS
            }
            if not values:
                continue
            key, n = label, 2
            while key in lignes:
                key = f"{label} ({n})"
                n += 1
            lignes[key] = values

    if len(lignes) < 2:
        return None, None
    return section_page, {"colonnes": col_names, "lignes": lignes}
