"""
Extraction de 2 KPI textuels des rapports ESG BVMT : Directeur général et
Président du Conseil d'Administration -> nom de la personne occupant ce
rôle.

Contrairement aux autres sources (CMF, FTUSA), ces rapports ne suivent pas
un modèle standardisé : chaque société rédige le sien, et la présentation
de ces 2 rôles varie fortement d'une société à l'autre. Deux formes
observées :
  - "rôle d'abord" (le plus courant, ex: MAGHREBIA "Directeur Général M.
    Sébastien SANCHEZ", TUNIS RE "Président du Conseil: Slah Kanoun") : le
    nom suit directement le libellé du rôle sur la même ligne, avec ou sans
    ":", avec ou sans préfixe "M./Mme".
  - "nom d'abord" (ex: STAR, dans une table "Membres des comités/commission"
    où chaque ligne est une personne) : le nom précède le texte du rôle, qui
    peut même être coupé sur la ligne précédente par la mise en page du
    tableau (observé pour "Président du Conseil d'Administration" chez
    STAR : "Président du Conseil" sur sa propre ligne, "d'Administration"
    sur la ligne du nom).

Les deux formes sont recherchées sur TOUTES les pages (pas seulement celles
dont le titre évoquerait la gouvernance : chez MAGHREBIA, les 2 rôles sont
dans une simple liste "Informations clés" en page de garde).

Voir extraction/CAS_PARTICULIERS_BVMT.md.
"""

import re

from extraction.bilan_kpi_extractor import _cluster_lines, _normalizer

MAX_PAGES_SCANNED = 40

PLAUSIBLE_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ.\-' ]{2,60}$")

ROLE_INLINE_PATTERNS = {
    "Directeur général": re.compile(r"directeur\s+g[ée]n[ée]ral\.?\s*:?\s*(.+)", re.IGNORECASE),
    "Président du Conseil d'Administration": re.compile(
        r"pr[ée]sident\s+du\s+conseil(?:\s+d['’]administration)?\.?\s*:?\s*(.+)", re.IGNORECASE
    ),
}

NAME_LINE_RE = re.compile(r"^(m\.|mme)\s+")
DIRECTEUR_GENERAL_RE = re.compile(r"directeur g[ée]n[ée]ral")
PRESIDENT_CONSEIL_RE = re.compile(r"president du conseil")

KPI_NAMES = list(ROLE_INLINE_PATTERNS.keys())
ROLE_PATTERNS = dict(zip(KPI_NAMES, [DIRECTEUR_GENERAL_RE, PRESIDENT_CONSEIL_RE]))
NAME_STOP_WORDS = dict(zip(KPI_NAMES, [("directeur",), ("president", "administration")]))


def _line_text(line):
    return " ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"]))


def _find_inline_role_value(lines, pattern):
    """Forme "rôle d'abord" : cherche `pattern` sur chaque ligne et renvoie
    le texte qui suit, s'il ressemble à un nom (voir PLAUSIBLE_NAME_RE)."""
    for line in lines:
        match = pattern.search(_line_text(line))
        if match:
            candidate = match.group(1).strip()
            if PLAUSIBLE_NAME_RE.match(candidate):
                return candidate
    return None


def _extract_name_before_role(raw_text, stop_words):
    """Nom de la personne en tête de ligne (ex: "M. Hassène Feki" extrait de
    "M. Hassène Feki Directeur général 2026") : tout ce qui suit le préfixe
    "M."/"Mme" jusqu'au premier mot contenant l'un de `stop_words`, ou à
    défaut jusqu'au premier nombre (année d'échéance du mandat)."""
    words = raw_text.split()
    name_words = [words[0]]
    for word in words[1:]:
        normalized = _normalizer.clean(word)
        if normalized.isdigit() or any(stop in normalized for stop in stop_words):
            break
        name_words.append(word)
    return " ".join(name_words)


def _find_name_before_role(lines, role_pattern, stop_words, lookback=1):
    """Forme "nom d'abord" (ex: table de gouvernance STAR) : cherche une
    ligne "M./Mme <nom>" dont le rôle correspond à `role_pattern`, cherché
    sur cette ligne et/ou les `lookback` ligne(s) précédentes (jamais
    suivantes : un rôle coupé sur deux lignes a son début au-dessus du nom,
    jamais en dessous — une ligne suivante appartient déjà à la personne
    suivante). Renvoie le nom trouvé, ou None."""
    for i, line in enumerate(lines):
        raw_text = _line_text(line)
        if not NAME_LINE_RE.match(_normalizer.clean(raw_text)):
            continue
        neighborhood = " ".join(
            _normalizer.clean(_line_text(lines[j])) for j in range(max(0, i - lookback), i + 1)
        )
        if role_pattern.search(neighborhood):
            return _extract_name_before_role(raw_text, stop_words)
    return None


def extract_bvmt_kpis(pdf, max_pages=MAX_PAGES_SCANNED):
    """Renvoie {"Directeur général", "Président du Conseil d'Administration"}
    -> nom de la personne (texte) | None."""
    result = {name: None for name in KPI_NAMES}
    for page in pdf.pages[:max_pages]:
        words = page.extract_words()
        if not words:
            continue
        lines = _cluster_lines(words, y_tolerance=3)

        for kpi_name in KPI_NAMES:
            if result[kpi_name] is not None:
                continue
            result[kpi_name] = _find_inline_role_value(
                lines, ROLE_INLINE_PATTERNS[kpi_name]
            ) or _find_name_before_role(lines, ROLE_PATTERNS[kpi_name], NAME_STOP_WORDS[kpi_name])

        if all(v is not None for v in result.values()):
            break
    return result
