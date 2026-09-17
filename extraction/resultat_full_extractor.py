"""Grille complète de l'État de résultat (technique / global) — même
principe que `bilan_full_extractor.py::extract_bilan_full_grid` (grille
complète, pas seulement le sous-ensemble de KPI utilisé par les
dashboards), pour le tableau distinct "État de résultat" (voir
`extraction/resultat_kpi_extractor.py` pour l'extraction narrow déjà en
place et `api/services/pdf_sections.py` pour la détection de page
"etat_resultat").

4 colonnes de valeurs — vérifié en conditions réelles sur STAR/ATTIJARI/
COMAR 2024 : "Opérations brutes", "Cessions et/ou rétrocessions",
"Opérations nettes" (exercice courant), "Opérations nettes" (exercice
précédent). Codes de ligne réels : RTNV/RTV (résultat technique repris
depuis l'Annexe 13/12), PRNV*/CHNV* (Non-Vie), PRV*/CHV* (Vie)."""

import re

from extraction.bilan_kpi_extractor import _cluster_lines, _extract_numeric_clusters, NUMERIC_TOKEN_RE
from utils.text_normalizer import TextNormalizer

_normalizer = TextNormalizer()

_ROW_CODE_RE = re.compile(r"^(RTNV|RTV|PRNV\d*|CHNV\d*|PRV\d*|CHV\d*)\b", re.IGNORECASE)
# Code de SECTION top-level (1 seul chiffre après le préfixe, ex. PRNV1,
# CHV4) — une ligne de sous-total de section arrive souvent SANS code
# répété, juste les 4 valeurs seules (constaté STAR : la ligne
# "374 430 627 46 129 514 328 301 113 311 192 818" qui totalise
# PRNV11+PRNV12, sans aucun texte). Même piège déjà résolu côté Bilan
# (`_pending_section`) — repris ici à l'identique.
_TOP_SECTION_RE = re.compile(r"^(RTNV|RTV|PRNV|CHNV|PRV|CHV)\d$", re.IGNORECASE)

_TITLE_HINT_RE = re.compile(r"etat\s+de\s+resultat", re.IGNORECASE)

_COLONNES = ["Opérations brutes", "Cessions et/ou rétrocessions", "Opérations nettes (N)", "Opérations nettes (N-1)"]

MIN_ROWS = 5


def _is_target_page(page):
    text = _normalizer.clean(page.extract_text() or "")
    return bool(_TITLE_HINT_RE.search(text))


def extract_resultat_full_grid(page, min_rows=MIN_ROWS):
    """Reconstruit la grille complète (tous les postes, 4 colonnes) de
    l'État de résultat visible sur `page`. Renvoie {"colonnes": [...],
    "lignes": {libelle_affiche: {colonne: valeur}}} ou None si la page ne
    ressemble pas assez à ce tableau."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)

    lignes = {}
    label_by_key = {}
    order = []  # ordre d'apparition des clés, pour l'affichage
    pending_label_words = []
    current_section = None  # dernier code de section top-level rencontré
                             # (ex. "PRNV1") — cible d'une ligne de
                             # sous-total SANS code répété.
    n_rows_found = 0
    first_code_seen = False  # tout texte AVANT le premier code reconnu
                              # (titre de page, "(chiffres arrondis...)",
                              # ligne d'en-tête des colonnes) est du bruit,
                              # jamais un vrai libellé wrappé — sans ce
                              # garde-fou, il polluait le libellé du 1er
                              # poste de la page (constaté STAR/ATTIJARI).

    for line in lines:
        first_word = line[0]["text"] if line else ""
        m = _ROW_CODE_RE.match(first_word)
        if m:
            first_code_seen = True
        values = _extract_numeric_clusters(line)

        if not values:
            if first_code_seen:
                non_numeric = [w["text"] for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
                if non_numeric:
                    pending_label_words.extend(non_numeric)
            continue
        if not first_code_seen:
            # Valeurs numériques rencontrées avant tout code reconnu —
            # presque toujours la ligne d'en-tête elle-même (ex. "31/12/
            # 2024 31/12/2023" lue comme 2 fausses "valeurs") : ignorée.
            continue

        label_words = [w["text"] for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]
        combined = " ".join(pending_label_words + label_words)
        label = _normalizer.clean(combined)
        pending_label_words = []

        if m:
            code = m.group(1).upper()
            # Retire le code du DÉBUT du libellé (une seule occurrence).
            label = _normalizer.clean(re.sub(r"^" + re.escape(m.group(0)), "", label, count=1))
            key = code
            if _TOP_SECTION_RE.match(code):
                current_section = code
        elif not label and current_section and current_section not in lignes:
            # Ligne purement numérique (4 valeurs, aucun texte) : sous-total
            # de la section top-level ouverte la plus récente, pas encore
            # résolue — jamais si cette section a déjà sa propre valeur
            # (évite d'écraser une vraie ligne à code par un sous-total
            # sans rapport rencontré plus loin).
            key = current_section
        else:
            key = label or f"ligne_{len(lignes) + 1}"

        row_values = {_COLONNES[i]: v for i, (v, _x0) in enumerate(values[:4])}
        if key not in lignes:
            lignes[key] = row_values
            label_by_key[key] = label
            order.append(key)
        else:
            lignes[key].update(row_values)
        n_rows_found += 1

    if n_rows_found < min_rows:
        return None

    lignes_affichage = {}
    for key in order:
        label = label_by_key.get(key) or ""
        display = f"{key} — {label}" if (label and label != key) else (label or key)
        lignes_affichage[display] = lignes[key]
    # "validations" : liste vide (pas de garde-fou métier encore défini
    # pour ce tableau, contrairement à Bilan/Annexe 13 — voir
    # save_tableau_result, qui l'exige même vide).
    return {"colonnes": _COLONNES, "lignes": lignes_affichage, "validations": []}


def process_resultat(pdf_path, max_pages=15):
    """Cherche la page 'État de résultat' dans les `max_pages` premières
    pages et renvoie la grille (avec sa page ajoutée sous `"page"`) ou
    None — même contrat de sortie que `bilan_full_extractor.process_bilan`
    (voir `api/services/tableau_pipeline_service_etat_resultat.py`)."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            if not _is_target_page(page):
                continue
            grid = extract_resultat_full_grid(page)
            if grid:
                grid["page"] = i + 1
                return grid
    return None
