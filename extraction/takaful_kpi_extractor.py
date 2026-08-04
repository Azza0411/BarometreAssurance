"""Extraction des KPI pour les compagnies Takaful (assurance islamique) :
ZITOUNA_TAKAFUL et AT_TAKAFULIA. AL_AMANAH_TAKAFUL reste exclue — ses états
financiers sont publiés en arabe (RTL), non fiable avec l'approche
d'extraction par position de mots utilisée ici (voir docs/travaux_futurs.md).

Deux formats réglementaires coexistent sur l'historique CMF de ces deux
compagnies (voir investigation documentée dans le commit associé) :

  - Format ANCIEN (jusqu'à l'exercice 2019 environ) : structure très proche
    d'un assureur conventionnel — un seul jeu de comptes par exercice
    (colonnes Brut/Amortissement/Net/Net Retraité côté Actif, une seule
    colonne côté Capitaux propres/Passif), sans distinction Fonds des
    Adhérents / Entreprise. On n'utilise PAS bilan_kpi_extractor.py
    directement : ses filtres de page (_is_actif_page notamment) rejettent
    certains documents Takaful (page non reconnue comme "page Actif" alors
    que la donnée y est bien présente) — on réutilise seulement ses
    utilitaires bas niveau (parsing de nombres, regroupement de lignes) et on
    scanne toutes les pages sans filtre.

  - Format NOUVEAU (à partir de l'exercice ~2020, suite à une réforme
    réglementaire) : le Bilan devient un "Bilan Combiné" à 3 colonnes par
    exercice — Fonds des Adhérents (capitaux des assurés, mutualisés) /
    Entreprise Takaful et/ou Rétakaful (bilan propre de la compagnie,
    actionnaires) / Entreprise ... combiné (somme des deux). Pour rester
    comparable aux assureurs conventionnels (dont le bilan n'inclut PAS de
    fonds mutualisé séparé), on retient la colonne "Entreprise" seule — ni
    le Fonds des Adhérents (qui appartient aux assurés, pas à la compagnie),
    ni le total combiné (qui mélangerait les deux). C'est toujours la 2e
    colonne du groupe de 3 (index 1) formant l'exercice en cours.

Dans les deux formats, l'État de Résultat de l'entreprise reste à colonne
unique par exercice (le compte de résultat de la compagnie elle-même n'est
jamais scindé Fonds/Entreprise) : "Résultat net de l'exercice" s'extrait
avec la même logique quel que soit le format.

Capitaux propres : certains documents affichent une ligne intermédiaire
"Total capitaux propres avant résultat de l'exercice" AVANT la ligne finale
"Total capitaux propres avant affectation" (ex: AT_TAKAFULIA 2018) — on
recherche en priorité la ligne "avant affectation" (le vrai total final) sur
tout le document avant de se rabattre sur un "Total capitaux propres" plus
générique (ex: AT_TAKAFULIA 2024, qui n'a pas de ligne intermédiaire)."""

import re

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters, _label_text, _is_plausible,
)
from utils.text_normalizer import TextNormalizer

_normalizer = TextNormalizer()

MAX_PAGES_SCANNED = 20

TOTAL_ACTIF_RE = re.compile(r"^total (de l.?|des )?actifs?\b")
CAPITAUX_PROPRES_AFFECTATION_RE = re.compile(r"^total capitaux propres avant affectation\b")
CAPITAUX_PROPRES_RE = re.compile(r"^total capitaux propres\b")
RESULTAT_NET_RE = re.compile(r"resultat net de l.?exercice\b")
# Repli : certains documents (ex: ZITOUNA_TAKAFUL 2025) omettent le mot "net"
# sur la ligne CP6 du Bilan ("Résultat de l'exercice" au lieu de "Résultat
# net de l'exercice"). Ancré en tête pour ne PAS matcher "...avant résultat
# de l'exercice" (total intermédiaire, valeur différente — voir AT_TAKAFULIA
# 2018) : cette ligne-là est toujours précédée d'un mot ("avant"), jamais en
# début de libellé une fois le préfixe de code retiré par _label_text.
RESULTAT_EXERCICE_FALLBACK_RE = re.compile(r"^resultat de l.?exercice\b")
PRIMES_EMISES_RE = re.compile(r"primes emises et acceptees\b")
BILAN_COMBINE_MARKER_RE = re.compile(r"bilan combine")

# Bilan Combiné (format nouveau) : Fonds des Adhérents / Entreprise Takaful
# et/ou Rétakaful / Entreprise ... combiné, par exercice. La colonne
# "Entreprise" (celle qu'on retient) est toujours la 2e (index 1) du groupe
# de 3 le plus à gauche (exercice en cours) sur une ligne de total.
NOUVEAU_COLS_PER_EXERCICE = 3
NOUVEAU_ENTREPRISE_COL_INDEX = 1


def _page_lines(page):
    words = page.extract_words()
    if not words:
        return []
    return _cluster_lines(words)


def detect_format(pdf):
    """Renvoie "nouveau" si le Bilan Combiné (3 colonnes/exercice) est
    détecté sur les premières pages, "ancien" sinon."""
    for page in pdf.pages[:MAX_PAGES_SCANNED]:
        text = page.extract_text() or ""
        if BILAN_COMBINE_MARKER_RE.search(_normalizer.clean(text)):
            return "nouveau"
    return "ancien"


def _find_row_value(pdf, pattern_re, column_selector, max_pages=MAX_PAGES_SCANNED, forward_scan=2):
    """Cherche la première ligne (dans l'ordre du document) dont le libellé
    normalisé correspond à `pattern_re`, et renvoie `column_selector(clusters)`
    pour la première ligne (elle-même ou l'une des `forward_scan` suivantes)
    portant des valeurs numériques."""
    for page in pdf.pages[:max_pages]:
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
                value = column_selector(clusters)
                if value is not None:
                    return value
    return None


def _col_nouveau_entreprise(clusters):
    if len(clusters) < NOUVEAU_COLS_PER_EXERCICE:
        return None
    value = clusters[NOUVEAU_ENTREPRISE_COL_INDEX][0]
    return value if _is_plausible(value) else None


def _col_ancien_actif(clusters):
    """Côté Actif (Brut/Amortissement/Net/Net Retraité) : avant-dernière
    colonne = Net de l'exercice en cours — même convention que
    bilan_kpi_extractor.py pour un bilan conventionnel."""
    value = clusters[-2][0] if len(clusters) >= 2 else clusters[0][0]
    return value if _is_plausible(value) else None


def _col_first(clusters):
    """Côté Capitaux propres/Passif (une seule sous-colonne par exercice) et
    État de Résultat : première colonne = exercice en cours."""
    value = clusters[0][0]
    return value if _is_plausible(value) else None


def extract_all_takaful_kpis(pdf):
    """Renvoie {nom_kpi: valeur|None}, avec les mêmes noms canoniques que les
    assureurs conventionnels (Total actif, Capitaux propres, Résultat Net,
    Primes émises par assurance) — pour que le reste de l'application
    (kpi_builder.py, quality.py, comparative.py, vue_assurance.py...)
    fonctionne sans aucune modification sur les compagnies Takaful."""
    fmt = detect_format(pdf)

    if fmt == "nouveau":
        total_actif = _find_row_value(pdf, TOTAL_ACTIF_RE, _col_nouveau_entreprise)
        capitaux = _find_row_value(pdf, CAPITAUX_PROPRES_AFFECTATION_RE, _col_nouveau_entreprise)
        if capitaux is None:
            capitaux = _find_row_value(pdf, CAPITAUX_PROPRES_RE, _col_nouveau_entreprise)
    else:
        total_actif = _find_row_value(pdf, TOTAL_ACTIF_RE, _col_ancien_actif)
        capitaux = _find_row_value(pdf, CAPITAUX_PROPRES_AFFECTATION_RE, _col_first)
        if capitaux is None:
            capitaux = _find_row_value(pdf, CAPITAUX_PROPRES_RE, _col_first)

    resultat_net = _find_row_value(pdf, RESULTAT_NET_RE, _col_first)
    if resultat_net is None:
        resultat_net = _find_row_value(pdf, RESULTAT_EXERCICE_FALLBACK_RE, _col_first)

    primes_total = None
    for page in pdf.pages[:MAX_PAGES_SCANNED]:
        lines = _page_lines(page)
        for i, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not PRIMES_EMISES_RE.search(label):
                continue
            for j in range(i, min(i + 3, len(lines))):
                clusters = _extract_numeric_clusters(lines[j])
                if not clusters:
                    continue
                value = clusters[0][0]  # 1ère colonne = Opérations brutes
                if _is_plausible(value) and value:
                    primes_total = (primes_total or 0) + value
                break

    return {
        "Total actif": total_actif,
        "Capitaux propres": capitaux,
        "Résultat Net": resultat_net,
        "Primes émises par assurance": primes_total,
        "_takaful_format": fmt,
    }
