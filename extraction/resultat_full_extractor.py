"""Grille complète de l'État de résultat (technique / global) — même
principe que `bilan_full_extractor.py::extract_bilan_full_grid` (grille
complète, pas seulement le sous-ensemble de KPI utilisé par les
dashboards), pour le tableau distinct "État de résultat" (voir
`extraction/resultat_kpi_extractor.py` pour l'extraction narrow déjà en
place et `api/services/pdf_sections.py` pour la détection de page
"etat_resultat").

Le NOMBRE de colonnes de valeurs varie réellement d'une société à
l'autre — découvert le 2026-09-17 (retour utilisateur : "pour attijari
[...] les noms de colonnes sont fausses") : STAR/COMAR publient 4
colonnes ("Opérations brutes", "Cessions et/ou rétrocessions",
"Opérations nettes" exercice courant/précédent), mais ATTIJARI n'en a
que 2 ("Montant 2024", "Montant 2023") — en-tête réel "DESIGNATION
Montant 2024 Montant 2023", pas de ventilation Brut/Cessions du tout.
Détecté dynamiquement par le nombre de valeurs trouvées sur la
PREMIÈRE ligne à code reconnu (même principe que le gabarit Takaful du
Bilan, voir `bilan_full_extractor.py` : le nombre de colonnes vient du
nombre de valeurs sur une vraie ligne de détail, pas d'un marqueur
textuel peu fiable), plutôt que fixé en dur pour toutes les sociétés.
Codes de ligne réels : RTNV/RTV (résultat technique repris depuis
l'Annexe 13/12), PRNV*/CHNV* (Non-Vie), PRV*/CHV* (Vie)."""

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

# Noms de colonnes par nombre de valeurs réellement trouvées (voir
# docstring du module) — 3 n'a pas encore été observé en pratique mais
# reste couvert par prudence (Brut/Net courant/Net précédent, sans
# cessions séparées).
_COLONNES_PAR_NB = {
    2: ["Exercice N", "Exercice N-1"],
    3: ["Brut", "Net (N)", "Net (N-1)"],
    4: ["Opérations brutes", "Cessions et/ou rétrocessions", "Opérations nettes (N)", "Opérations nettes (N-1)"],
}

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
    colonnes = None  # déterminé dynamiquement (voir docstring module) au
                      # nombre de valeurs de la PREMIÈRE ligne à code

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
        if colonnes is None:
            colonnes = _COLONNES_PAR_NB.get(len(values), [f"Valeur {i + 1}" for i in range(len(values))])

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

        row_values = {colonnes[i]: v for i, (v, _x0) in enumerate(values[:len(colonnes)])}
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
    return {"colonnes": colonnes, "lignes": lignes_affichage, "validations": []}


def process_resultat(pdf_path, code=None, annee=None, max_pages=15):
    """Renvoie la grille (avec sa page ajoutée sous `"page"`) ou None —
    même contrat de sortie que `bilan_full_extractor.process_bilan` (voir
    `api/services/tableau_pipeline_service_etat_resultat.py`).

    Si `code`/`annee` sont fournis, réutilise DIRECTEMENT la page déjà
    repérée par `api.services.pdf_sections.get_pdf_sections()` — ne
    refait PAS sa propre recherche par titre. Découvert le 2026-09-17
    (retour utilisateur : "pour attijari [...] les noms de colonnes sont
    fausses") : plusieurs pages d'un même document peuvent contenir la
    sous-chaîne "état de résultat" (ex. ATTIJARI 2024 — page 4 "état de
    résultat TECHNIQUE VIE", en réalité la page des sinistres Vie donnée
    à `resultat_kpi_extractor.py`, ET page 5, la vraie page globale/
    canonique) ; une recherche par titre seule tombait à tort sur la
    première (mauvais nombre de colonnes, mauvais code de ligne). Repli
    sur l'ancienne recherche par titre uniquement si `code`/`annee` ne
    sont pas fournis (usage direct/test sans base de données)."""
    import pdfplumber
    if code and annee:
        from api.services.pdf_sections import get_pdf_sections
        page_num = get_pdf_sections(code, annee).get("etat_resultat")
        if not page_num:
            return None
        with pdfplumber.open(pdf_path) as pdf:
            if page_num > len(pdf.pages):
                return None
            grid = extract_resultat_full_grid(pdf.pages[page_num - 1])
        if grid:
            grid["page"] = page_num
        return grid

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            if not _is_target_page(page):
                continue
            grid = extract_resultat_full_grid(page)
            if grid:
                grid["page"] = i + 1
                return grid
    return None
