"""Pipeline complète Annexe 13 (Phase 1, 2026-09-08) : extraction de la
grille complète (full_table_extractor.py) → normalisation des libellés de
ligne contre une liste canonique → validation par règles métier (identités
comptables du tableau) → structure prête pour stockage en base et export
Excel.

Contrairement aux extracteurs narrow existants (annexe13_kpi_extractor.py,
utilisés par les dashboards), cette pipeline ne se limite pas à 7 KPI et
ajoute une boucle de validation — inspirée d'un script de référence fourni
par l'utilisatrice (C:\\Users\\HP\\Music\\AzzaStage25-26\\FS_Market_Intelligence
\\B.py, fonctions normalize_excel/validate_excel) qui applique le même
principe (normalisation par correspondance floue + contrôles croisés C1-C9)
sur un cas particulier (STAR uniquement, valeurs de colonnes fixes). Ici,
généralisée à TOUTES les sociétés (les libellés de ligne sont un vocabulaire
réglementaire commun à toutes ; les colonnes/branches, elles, varient
réellement d'une société à l'autre selon ses lignes de produits — pas de
liste de colonnes fixe).

Décision explicite (voir échange utilisateur du 2026-09-08) : cette pipeline
reste SÉPARÉE des extracteurs narrow existants pour l'instant (Phase 1).
Les dashboards ne sont pas branchés dessus — seule la page "Gestion de
données" l'utilise. Une Phase 2, plus tard, migrera éventuellement les
dashboards vers les valeurs validées en base, une fois cette pipeline
éprouvée sur l'ensemble des sociétés.
"""

import difflib
import re

from extraction.bilan_kpi_extractor import _normalizer
from config.company_registry import TAKAFUL_CODES

# ── Sociétés hors périmètre de l'Annexe 13 (Résultat technique Non-Vie) ────
# Par nature du modèle métier — pas des échecs d'extraction. Référentiel
# UNIQUE (2026-09-09) : importé à la fois par le script d'audit de
# couverture (scripts/audit_full_table_extraction.py) et par le calcul des
# indicateurs de fiabilité (api/services/data_management.py::get_reliability_
# stats) pour ne jamais diverger sur "qui est censé avoir une Annexe 13
# Non-Vie". ATTIJARI et UIB vérifiés le 2026-09-09 : leur propre objet
# social ("opérations d'assurances sur la vie... et de capitalisation")
# confirme des sociétés Vie exclusivement — aucune page Annexe 13 Non-Vie
# dans leurs documents CMF, à aucune année (les rares résultats obtenus
# avant ce correctif étaient des faux positifs sur la page de raccordement
# Vie, codes PRV1/CHV1/CHV2). Takaful (Annexes 14/15 spécifiques) réutilise
# TAKAFUL_CODES du registre société plutôt que de le redéfinir ici.
VIE_ONLY_CODES = {
    "GAT_VIE", "LLOYD_VIE", "MAGHREBIA_VIE", "CARTE_VIE", "HAYETT",
    "ATTIJARI", "UIB",
}
ANNEXE13_NON_VIE_EXCLUSIONS = VIE_ONLY_CODES | TAKAFUL_CODES

# ── Normalisation des libellés de ligne ─────────────────────────────────────
# Vocabulaire réglementaire commun à toutes les sociétés (poste comptable du
# tableau "Résultat technique par catégorie d'assurance Non-Vie") — construit
# par union des libellés réellement observés sur plusieurs sociétés (STAR,
# GAT, BIAT) plutôt que copié d'une seule société, et recoupé avec la liste
# EXPECTED_ROWS du script de référence fourni par l'utilisatrice (résultat
# quasi identique, qui confirme qu'il s'agit bien du même vocabulaire
# standard, pas d'une liste propre à STAR).
CANONICAL_ROWS = [
    "Primes acquises",
    "Primes émises",
    "Variation des primes non acquises",
    "Charges de prestations",
    "Prestations et frais payés",
    "Charges des provisions pour prestations diverses",
    "Solde de souscription",
    "Frais d'acquisition",
    "Autres charges de gestion nettes",
    "Charges d'acquisition et de gestion nettes",
    "Produits nets de placements",
    "Participation aux résultats",
    "Solde financier",
    "Part des réassureurs dans les primes acquises",
    "Part des réassureurs dans les prestations payées",
    "Part des réassureurs dans les charges de provisions pour prestations",
    "Part des réassureurs dans la participation aux résultats",
    "Commissions reçues des réassureurs / rétrocessionnaires",
    "Solde de réassurance / rétrocession",
    "Résultat technique",
    "Provisions pour primes non acquises (clôture)",
    "Provisions pour primes non acquises (réouverture)",
    "Provisions pour sinistres à payer (clôture)",
    "Provisions pour sinistres à payer (réouverture)",
]

# Score minimal (difflib.SequenceMatcher.ratio, 0-1) pour accepter une
# correspondance — en-dessous, le libellé brut est gardé tel quel plutôt que
# rattaché à tort à un poste canonique qui n'est pas le sien (mieux vaut un
# libellé non normalisé visible que silencieusement faux).
_MATCH_THRESHOLD = 0.55

_CANONICAL_NORMALIZED = [(label, _normalizer.clean(label)) for label in CANONICAL_ROWS]

# Une ligne de repli fragmentée sur 2 libellés bruts consécutifs (ex. le
# tableau écrit la "part des réassureurs" en 4 sous-lignes commençant par
# "les..."/"la..." — voir full_table_extractor.py, cas STAR) : ces préfixes,
# une fois isolés, ne matcheraient RIEN d'assez proche seuls ("les prestations
# payes" est trop court/générique) — on les rattache explicitement à leur
# poste "Part des réassureurs..." correspondant avant le score flou.
_KNOWN_PREFIXED_VARIANTS = {
    "les prestations payes": "Part des réassureurs dans les prestations payées",
    "les charges de provi. pour prestations": "Part des réassureurs dans les charges de provisions pour prestations",
    "les charges de provisions pour prestations": "Part des réassureurs dans les charges de provisions pour prestations",
    "la participation aux resultats": "Part des réassureurs dans la participation aux résultats",
}


def normalize_row_label(raw_label):
    """Rattache un libellé de ligne brut extrait du PDF au poste comptable
    canonique correspondant (`CANONICAL_ROWS`), par correspondance floue —
    tolère les variantes de formulation déjà rencontrées entre sociétés
    ("Charges de prestation" vs "Charges de prestations", "Primes émises et
    acceptées" vs "Primes émises"...). Renvoie (libelle_normalise, matched)
    où `matched` est False si aucun poste canonique n'est assez proche (le
    libellé brut original est alors renvoyé tel quel, jamais perdu)."""
    norm = _normalizer.clean(raw_label)
    if norm in _KNOWN_PREFIXED_VARIANTS:
        return _KNOWN_PREFIXED_VARIANTS[norm], True

    best_label, best_score = None, 0.0
    for canonical, canonical_norm in _CANONICAL_NORMALIZED:
        # Un préfixe exact (ex. "primes acquises" contenu dans "primes
        # acquises brutes 31/12/2024") est un signal plus fort qu'un simple
        # ratio de similarité de chaînes — priorité absolue s'il existe.
        if norm.startswith(canonical_norm) or canonical_norm.startswith(norm):
            score = 0.9 + 0.1 * (len(canonical_norm) / max(len(norm), len(canonical_norm)))
        else:
            score = difflib.SequenceMatcher(None, norm, canonical_norm).ratio()
        if score > best_score:
            best_label, best_score = canonical, score

    if best_score >= _MATCH_THRESHOLD:
        return best_label, True
    return raw_label.strip().capitalize(), False


def normalize_table(grid):
    """Applique `normalize_row_label` à toutes les lignes d'une grille issue
    de `full_table_extractor.extract_full_table` / `locate_and_extract_full_table`.
    Renvoie {"colonnes": [...], "lignes": {libelle_normalise: {colonne: valeur}},
    "non_reconnues": [libelles_bruts_non_rattaches...]}. Deux libellés bruts
    distincts qui se normalisent vers le MÊME poste canonique (rare — ne
    devrait pas arriver sur une page bien reconstruite) sont fusionnés en
    gardant la valeur non-nulle si l'une des deux est vide, pour ne perdre
    aucune donnée plutôt que d'écraser silencieusement."""
    lignes_normalisees = {}
    non_reconnues = []
    for raw_label, values in grid["lignes"].items():
        normalized, matched = normalize_row_label(raw_label)
        if not matched:
            non_reconnues.append(raw_label)
        if normalized in lignes_normalisees:
            existing = lignes_normalisees[normalized]
            for col, val in values.items():
                existing.setdefault(col, val)
        else:
            lignes_normalisees[normalized] = dict(values)
    return {
        "colonnes": grid["colonnes"],
        "lignes": lignes_normalisees,
        "non_reconnues": non_reconnues,
    }


# ── Validation par règles métier ────────────────────────────────────────────
# Identités comptables réelles du tableau "Résultat technique" (pas propres à
# une société — ce sont des définitions du plan comptable des assurances,
# valables branche par branche ET sur la colonne Total). Toutes les valeurs
# sont déjà SIGNÉES (les charges/sorties sont négatives dans les données
# extraites), donc chaque identité s'exprime comme une simple SOMME — à la
# différence du script de référence fourni par l'utilisatrice, dont certaines
# formules (C4, C6) soustrayaient un poste censé s'additionner ; ces identités
# sont ré-établies ici depuis la logique comptable elle-même plutôt que
# recopiées telles quelles.
_TOLERANCE = 5  # ecart (en unite monetaire du tableau, generalement le dinar) tolere avant signalement — arrondis/dinarisation

VALIDATION_RULES = [
    ("primes_acquises",
     "Primes acquises = Primes émises + Variation des primes non acquises",
     "Primes acquises", ["Primes émises", "Variation des primes non acquises"]),
    ("charges_prestations",
     "Charges de prestations = Prestations et frais payés + Charges des provisions pour prestations diverses",
     "Charges de prestations", ["Prestations et frais payés", "Charges des provisions pour prestations diverses"]),
    ("solde_souscription",
     "Solde de souscription = Primes acquises + Charges de prestations",
     "Solde de souscription", ["Primes acquises", "Charges de prestations"]),
    ("charges_acquisition_gestion",
     "Charges d'acquisition et de gestion nettes = Frais d'acquisition + Autres charges de gestion nettes",
     "Charges d'acquisition et de gestion nettes", ["Frais d'acquisition", "Autres charges de gestion nettes"]),
    ("solde_financier",
     "Solde financier = Produits nets de placements + Participation aux résultats",
     "Solde financier", ["Produits nets de placements", "Participation aux résultats"]),
    ("solde_reassurance",
     "Solde de réassurance / rétrocession = Part des réassureurs dans les primes acquises "
     "+ Part des réassureurs dans les prestations payées + Part des réassureurs dans les charges "
     "de provisions pour prestations + Part des réassureurs dans la participation aux résultats "
     "+ Commissions reçues des réassureurs / rétrocessionnaires",
     "Solde de réassurance / rétrocession",
     ["Part des réassureurs dans les primes acquises", "Part des réassureurs dans les prestations payées",
      "Part des réassureurs dans les charges de provisions pour prestations",
      "Part des réassureurs dans la participation aux résultats",
      "Commissions reçues des réassureurs / rétrocessionnaires"]),
    ("resultat_technique",
     "Résultat technique = Solde de souscription + Charges d'acquisition et de gestion nettes "
     "+ Solde financier + Solde de réassurance / rétrocession",
     "Résultat technique",
     ["Solde de souscription", "Charges d'acquisition et de gestion nettes",
      "Solde financier", "Solde de réassurance / rétrocession"]),
]


def validate_table(normalized_lignes, columns):
    """Applique `VALIDATION_RULES` colonne par colonne (chaque branche, plus
    Total). Renvoie une liste de résultats {regle, colonne, attendu, trouve,
    ecart, statut} — statut 'ok' (écart ≤ tolérance), 'ecart' (dépassement,
    signale un souci d'extraction ou une vraie incohérence du document
    source) ou 'donnees_manquantes' (un des postes de la règle est absent de
    cette grille — rien à valider)."""
    results = []
    for rule_code, rule_desc, target, sources in VALIDATION_RULES:
        target_row = normalized_lignes.get(target)
        source_rows = [normalized_lignes.get(s) for s in sources]
        for col in columns:
            base = {"regle_code": rule_code, "regle": rule_desc, "colonne": col}
            if target_row is None or any(r is None for r in source_rows):
                results.append({**base, "attendu": None, "trouve": None,
                                 "ecart": None, "statut": "donnees_manquantes"})
                continue
            found = target_row.get(col)
            source_vals = [r.get(col) for r in source_rows]
            if found is None or any(v is None for v in source_vals):
                results.append({**base, "attendu": None, "trouve": found,
                                 "ecart": None, "statut": "donnees_manquantes"})
                continue
            expected = sum(source_vals)
            ecart = round(found - expected, 2)
            statut = "ok" if abs(ecart) <= _TOLERANCE else "ecart"
            results.append({**base, "attendu": round(expected, 2),
                             "trouve": round(found, 2), "ecart": ecart, "statut": statut})
    return results


def process_annexe13(pdf_path, is_target_page, kpi_patterns, raccordement_re, relaxed_page_predicate):
    """Pipeline complète pour un document : localise + extrait la grille
    (full_table_extractor), normalise les libellés de ligne, valide par
    règles métier. Renvoie None si aucune page valide n'a été trouvée, sinon
    {"page", "colonnes", "lignes", "non_reconnues", "validations"}."""
    from extraction.full_table_extractor import locate_and_extract_full_table

    page_num, grid = locate_and_extract_full_table(
        pdf_path, is_target_page, kpi_patterns, raccordement_re,
        extra_page_predicate=relaxed_page_predicate,
    )
    if grid is None:
        return None

    normalized = normalize_table(grid)
    validations = validate_table(normalized["lignes"], normalized["colonnes"])
    return {
        "page": page_num,
        "colonnes": normalized["colonnes"],
        "lignes": normalized["lignes"],
        "non_reconnues": normalized["non_reconnues"],
        "validations": validations,
    }
