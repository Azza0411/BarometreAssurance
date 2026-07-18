"""
Extraction ciblée de 3 KPI répartis sur 3 tableaux distincts (résumés de
résultat, pas les annexes par catégorie déjà traitées ailleurs) :

  - "L'état de résultat technique de l'assurance vie" : ligne "Charges de
    sinistres" (code CHV1) / colonne "Opérations nettes" de l'année en
    cours -> KPI "Charge de sinistres Vie".
  - "L'état de résultat technique de l'assurance non-vie" : même ligne,
    même colonne (code CHNV1) -> KPI "Charge de sinistres Non-Vie".
  - "L'état de résultat arrêté au [date]" (résultat global, pas technique) :
    ligne "Résultat net de l'exercice" / colonne de l'année en cours ->
    KPI "Résultat Net".

Les deux premiers tableaux ont la même structure à 4 colonnes (Opérations
brutes / Cessions et rétrocessions / Opérations nettes année en cours /
Opérations nettes année précédente) que l'on retrouve aussi dans les Annexes
12/13 : on réutilise donc _select_column_value de bilan_kpi_extractor (même
convention : avant-dernière colonne = année en cours). Comme pour le Bilan,
le total de la ligne recherchée est parfois inscrit directement sur sa ligne
de titre, parfois sur une ligne séparée juste en dessous (y compris sous la
forme d'un code répété seul, ex: "CHV1" chez COMAR) — mêmes règles que
_find_section_total.

Voir extraction/CAS_PARTICULIERS_RESULTAT.md pour l'historique des cas
particuliers rencontrés.
"""

import io
import re

import requests

from extraction.bilan_kpi_extractor import (
    USER_AGENT,
    _extract_numeric_clusters,
    _label_text,
    _normalizer,
    _page_lines,
    _select_column_value,
)

MAX_PAGES_SCANNED = 15  # ces tableaux se trouvent systématiquement en tête de document
# Fenêtre de lignes explorées après le titre de la ligne recherchée, pour y
# trouver le total (cas où il est sur une ligne séparée plutôt qu'inline).
FORWARD_SCAN_WINDOW = 6

# Pas de \b/^ en tête : le code de ligne (CHNV1, CHV1...) est parfois collé
# sans espace au libellé (ex: "chnv1charge de sinistres" chez STAR) — comme
# pour les autres tableaux, on cherche une sous-chaîne (voir _find_*_value
# qui utilisent .search() et non .match()).
# "sin(is|si)tres" tolère la faute de frappe "sinsitres" (lettres
# transposées) trouvée dans le document source de GAT.
CHARGES_SINISTRES_RE = re.compile(r"charges? de sin(is|si)tres")
# Racine commune aux variantes rencontrées : "Résultat net de l'exercice",
# "...après modifications comptables", ou juste "Résultat net après
# modifications comptables" (sans "de l'exercice", ex: ASTREE).
RESULTAT_NET_RE = re.compile(r"resultat net\b")

# Titre "résumé" du résultat technique (PAS l'annexe par catégorie, qui a un
# titre différent contenant "categorie" — voir annexe12/13_kpi_extractor) :
# "resultat [technique] de l assurance <texte optionnel> vie". Le texte
# optionnel entre "assurance" et "vie" varie (absent, "non", ou même "et/ou
# de la réassurance non" chez BH) : on le capture pour vérifier ensuite s'il
# contient "non", plutôt que d'exiger un enchaînement direct fragile.
TECH_TITLE_PREFIX_RE = re.compile(r"resultat (technique )?de l assurance(.{0,40}?)vie\b")
# Résultat global : "etat de resultat" SANS "technique"/"catégorie" dans les
# 15 caractères qui suivent (contrairement aux tableaux techniques ci-dessus
# et aux annexes 12/13, dont le titre contient "technique de l'assurance
# vie/non-vie" ou "par catégorie" juste après "résultat").
RESULTAT_GLOBAL_TITLE_RE = re.compile(
    r"etat de resultat(?!.{0,20}(technique|categorie|assurance (non )?vie))"
)


def _page_title(page, lines_checked=8):
    text = (page.extract_text() or "").strip()
    if not text:
        return ""
    return _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))


def _is_tech_vie_page(page):
    m = TECH_TITLE_PREFIX_RE.search(_page_title(page))
    return bool(m) and "non" not in m.group(2)


def _is_tech_non_vie_page(page):
    m = TECH_TITLE_PREFIX_RE.search(_page_title(page))
    return bool(m) and "non" in m.group(2)


def _is_resultat_global_page(page):
    return bool(RESULTAT_GLOBAL_TITLE_RE.search(_page_title(page)))


# Un espace optionnel peut séparer le préfixe et le chiffre (ex: "chnv 2"
# chez BH, au lieu de "chnv2" chez GAT/COMAR).
LINE_CODE_RE = re.compile(r"^([a-z]{2,5})\s*(\d+)")


def _line_code(label):
    """Code de ligne (ex: "chnv1", "chnv11") en tête d'un libellé, ou None."""
    m = LINE_CODE_RE.match(label) if label else None
    return m.group(1) + m.group(2) if m else None


def _find_multi_column_value(pdf, page_filter, pattern, max_pages=MAX_PAGES_SCANNED):
    """Cherche la ligne `pattern` sur la page validée par `page_filter`, et
    renvoie la valeur "année en cours" (avant-dernière colonne, cf.
    _select_column_value) — inline sur la ligne de titre si présente (>= 2
    colonnes), sinon sur la DERNIÈRE ligne à >= 2 colonnes trouvée avant la
    prochaine ligne dont le code (ex: "chnv2") ne descend pas du code de la
    ligne recherchée (ex: "chnv1") : le total suit toujours ses
    sous-éléments (eux-mêmes codés "chnv11", "chnv12"...), jamais l'inverse
    — même principe que _find_section_total pour le Bilan."""
    for page in pdf.pages[:max_pages]:
        if not page_filter(page):
            continue
        lines = _page_lines(page)
        if not lines:
            continue
        for i, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not pattern.search(label):
                continue
            header_clusters = _extract_numeric_clusters(line)
            if len(header_clusters) >= 2:
                return _select_column_value(header_clusters, lines, line[0]["top"], header_token="net")
            target_code = _line_code(label)
            value = None
            for j in range(i + 1, min(i + 1 + FORWARD_SCAN_WINDOW, len(lines))):
                next_label = _label_text(lines[j])
                next_code = _line_code(next_label)
                if target_code and next_code and not next_code.startswith(target_code):
                    break
                clusters = _extract_numeric_clusters(lines[j])
                if len(clusters) >= 2:
                    value = _select_column_value(clusters, lines, lines[j][0]["top"], header_token="net")
            if value is not None:
                return value
        # la ligne recherchée n'est pas sur cette page : une autre page peut
        # aussi correspondre à `page_filter` (ex: faux positif de titre) —
        # on continue plutôt que d'abandonner.
    return None


def _find_first_column_value(pdf, page_filter, pattern, max_pages=MAX_PAGES_SCANNED):
    """Cherche la ligne `pattern` sur la page validée par `page_filter`, et
    renvoie la valeur de la première colonne (= année en cours) de cette
    même ligne."""
    for page in pdf.pages[:max_pages]:
        if not page_filter(page):
            continue
        lines = _page_lines(page)
        if not lines:
            continue
        for line in lines:
            label = _label_text(line)
            if label is None or not pattern.search(label):
                continue
            clusters = _extract_numeric_clusters(line)
            if clusters:
                return clusters[0][0]
        # la ligne recherchée n'est pas sur cette page : une autre page peut
        # aussi correspondre à `page_filter` (ex: faux positif de titre) —
        # on continue plutôt que d'abandonner.
    return None


KPI_NAMES = ["Charge de sinistres Vie", "Charge de sinistres Non-Vie", "Résultat Net"]


def extract_resultat_kpis(pdf):
    """Renvoie {"Charge de sinistres Vie", "Charge de sinistres Non-Vie",
    "Résultat Net"} -> valeur|None."""
    return {
        "Charge de sinistres Vie": _find_multi_column_value(
            pdf, _is_tech_vie_page, CHARGES_SINISTRES_RE
        ),
        "Charge de sinistres Non-Vie": _find_multi_column_value(
            pdf, _is_tech_non_vie_page, CHARGES_SINISTRES_RE
        ),
        "Résultat Net": _find_first_column_value(
            pdf, _is_resultat_global_page, RESULTAT_NET_RE
        ),
    }


def extract_resultat_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait les 3 KPI ci-dessus."""
    import pdfplumber  # import local pour éviter la dépendance si non utilisé

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_resultat_kpis(pdf)
