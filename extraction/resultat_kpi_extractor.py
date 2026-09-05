"""
Extraction ciblée de 3 KPI répartis sur 3 tableaux distincts (résumés de
résultat, pas les annexes par catégorie déjà traitées ailleurs) :

  - Ligne "Charges de sinistres" codée CHV1 (Vie) -> KPI "Charge de
    sinistres Vie" / codée CHNV1 (Non-Vie) -> KPI "Charge de sinistres
    Non-Vie", colonne "Opérations nettes" de l'année en cours. Désambiguïsée
    par le CODE de ligne (CHV.../CHNV...), pas par le titre de la page : ce
    dernier varie trop d'un document à l'autre pour être fiable (5
    formulations différentes rencontrées — voir CAS_PARTICULIERS_RESULTAT.md
    et _find_sinistres_value).
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
    _is_plausible,
    _label_text,
    _normalizer,
    _page_lines,
    _select_column_value,
)

MAX_PAGES_SCANNED = 15
FORWARD_SCAN_WINDOW = 6

CHARGES_SINISTRES_RE = re.compile(r"charges? de sin(is|si)tres")
RESULTAT_NET_RE = re.compile(r"r\s?esultat net\b")

TECH_TITLE_PREFIX_RE = re.compile(r"resultat (technique )?de l assurance(.{0,40}?)vie\b")
RESULTAT_GLOBAL_TITLE_RE = re.compile(
    r"etat de resultat(?!.{0,20}(technique|categorie|assurance (non )?vie))"
)


def _page_title(page, lines_checked=8):
    text = (page.extract_text() or "").strip()
    if not text:
        return ""
    return _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))


def _is_resultat_global_page(page):
    return bool(RESULTAT_GLOBAL_TITLE_RE.search(_page_title(page)))


LINE_CODE_RE = re.compile(r"^([a-z]{2,5})\s*(\d+)")


def _line_code(label):
    """Code de ligne (ex: "chnv1", "chnv11") en tête d'un libellé, ou None."""
    m = LINE_CODE_RE.match(label) if label else None
    return m.group(1) + m.group(2) if m else None


def _find_first_column_value(pdf, page_filter, pattern, max_pages=MAX_PAGES_SCANNED):
    """Cherche la ligne `pattern` sur la page validée par `page_filter`, et
    renvoie la valeur de la première colonne (= année en cours) de cette
    même ligne.

    Contrairement à `_find_sinistres_value` (et à `_find_total_value` dans
    annexe12/13_kpi_extractor.py), cette fonction ne vérifiait PAS
    `_is_plausible` sur la valeur trouvée — découvert le 2026-08-06 sur
    TUNIS_RE 2024 : "Résultat Net" = 2 (fragment de nombre scindé par le PDF,
    voir CAS_PARTICULIERS_RESULTAT.md) passait tel quel jusqu'à l'affichage
    ("0.0 M TND", indistinguable d'un vrai résultat quasi nul) au lieu de
    redevenir `None`/anomalie détectée comme les autres KPI "montant".

    Certains documents (ex: ATTIJARI 2015/2017/2019) ont DEUX lignes
    distinctes matchant `pattern` sur la même page : "Résultat net de
    l'exercice" (un sous-total intermédiaire, toujours à 0 dans ces PDF)
    suivie de "...après modifications comptables" (la vraie valeur finale).
    Retourner la première ligne trouvée capturait donc systématiquement ce
    faux zéro. Une ligne contenant "après modifications comptables" est
    désormais toujours préférée si elle existe sur la page ; sinon, on
    retombe sur la première ligne plausible rencontrée (comportement
    inchangé pour les documents n'ayant que la forme simple)."""
    fallback = None
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
            if not clusters or not _is_plausible(clusters[0][0]):
                continue
            if "apres modifications comptables" in label:
                return clusters[0][0]
            if fallback is None:
                fallback = clusters[0][0]
    return fallback


def _find_sinistres_value(pdf, code_prefix, max_pages=MAX_PAGES_SCANNED):
    """Cherche la ligne "Charges de sinistres" dont le CODE DE LIGNE (CHV1 =
    Vie, CHNV1 = Non-Vie — code standard CMF, cf. docstring du module) commence
    par `code_prefix`, et renvoie sa valeur "année en cours" (même logique
    d'accumulation en avant que l'ancien _find_multi_column_value).

    Le titre de page (ex-`_is_tech_vie_page`/`_is_tech_non_vie_page`) n'est
    plus le signal PRINCIPAL de désambiguïsation Vie/Non-Vie : l'audit du
    2026-08-06 (Vue par assurance, année 2024) a trouvé 5 formulations de
    titre différentes qui échappaient toutes à l'ancien motif unique
    (LLOYD_TUNISIEN : format "Annexe 3/4" sans "de l'assurance" ; LLOYD_VIE :
    "technique VIE DE Lloyd Vie" ; MAGHREBIA : "de l'assurance ET DE LA
    RÉASSURANCE" repousse "vie" hors de la fenêtre ; MAGHREBIA_VIE : société
    mono-branche, aucun marqueur vie/non-vie dans son titre ; TUNIS_RE :
    "technique - vie" avec un tiret). Le code de ligne CHV/CHNV est le signal
    PRIORITAIRE désormais — voir CAS_PARTICULIERS_RESULTAT.md. Mais GAT_VIE
    n'a AUCUN code sur cette ligne précise ("charge de sinistres note", le mot
    "note" n'est pas un code de ligne) : dans ce cas seulement, on retombe sur
    le titre de page (ancien motif), toujours fiable quand le code manque."""
    for page in pdf.pages[:max_pages]:
        lines = _page_lines(page)
        if not lines:
            continue
        page_title_match = None
        for i, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not CHARGES_SINISTRES_RE.search(label):
                continue
            target_code = _line_code(label)
            if target_code:
                if not target_code.startswith(code_prefix):
                    continue
            else:
                if page_title_match is None:
                    page_title_match = TECH_TITLE_PREFIX_RE.search(_page_title(page)) or False
                if not page_title_match:
                    continue
                is_vie_page = "non" not in page_title_match.group(2)
                if is_vie_page != (code_prefix == "chv"):
                    continue
            header_clusters = _extract_numeric_clusters(line)
            if len(header_clusters) >= 2:
                return _select_column_value(header_clusters, lines, line[0]["top"], header_token="net")
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
    return None


KPI_NAMES = ["Charge de sinistres Vie", "Charge de sinistres Non-Vie", "Résultat Net"]


def extract_resultat_kpis(pdf):
    """Renvoie {"Charge de sinistres Vie", "Charge de sinistres Non-Vie",
    "Résultat Net"} -> valeur|None."""
    return {
        "Charge de sinistres Vie": _find_sinistres_value(pdf, "chv"),
        "Charge de sinistres Non-Vie": _find_sinistres_value(pdf, "chnv"),
        "Résultat Net": _find_first_column_value(
            pdf, _is_resultat_global_page, RESULTAT_NET_RE
        ),
    }


def extract_resultat_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait les 3 KPI ci-dessus."""
    import pdfplumber

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_resultat_kpis(pdf)
