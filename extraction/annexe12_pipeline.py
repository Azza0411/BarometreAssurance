"""Pipeline complète Annexe 12 (Résultat technique par catégorie
d'assurance Vie) — pendant Vie de l'Annexe 13 Non-Vie (voir
extraction/annexe13_pipeline.py pour la Phase 1 originale, dont ce module
réutilise le moteur de normalisation/validation en le PARAMÉTRANT plutôt
qu'en le dupliquant : `normalize_row_label`, `normalize_table`,
`validate_table` acceptent toutes un vocabulaire de lignes/règles en
paramètre — voir leur docstring).

Vocabulaire de LIGNE (postes comptables) distinct du Non-Vie : l'Annexe 12
Vie n'a PAS la scission "Primes acquises = Primes émises + Variation" (une
seule ligne "Primes"), porte une ligne "Ajustement ACAV" propre aux contrats
en unités de compte, et sa ligne de provisions techniques est "Charges des
provisions d'assurance vie et des autres provisions techniques" (au lieu de
"... pour prestations diverses"). Construit par relevé croisé sur AMI, BH
et COMAR (2026-09-11) — même méthode que le vocabulaire Non-Vie (jamais une
seule société).

Vocabulaire de COLONNE (branches) : PARTAGÉ avec le Non-Vie
(`annexe13_pipeline.CANONICAL_COLUMNS`/`normalize_column_label`), étendu des
branches Vie observées (Temporaire décès, Capital différé, Mixte, Rente...)
— pas de collision possible avec les branches Non-Vie, donc pas de liste
séparée."""

from extraction.annexe13_pipeline import (
    normalize_row_label as _normalize_row_label,
    normalize_table as _normalize_table,
    validate_table as _validate_table,
)
from config.company_registry import TAKAFUL_CODES

# ── Sociétés hors périmètre de l'Annexe 12 (Résultat technique Vie) ────────
# Contrairement à l'Annexe 13, aucune exclusion n'est présumée a priori : le
# marché tunisien sépare Vie/Non-Vie en ENTITÉS JURIDIQUES DISTINCTES pour
# certains groupes (GAT/GAT_VIE, CARTE/CARTE_VIE, LLOYD_TUNISIEN/LLOYD_VIE,
# MAGHREBIA/MAGHREBIA_VIE — le code "_VIE" a son propre dépôt CMF et EST déjà
# l'Annexe Vie de ce groupe), alors que d'autres publient Vie ET Non-Vie dans
# le MÊME document (AMI, BH, COMAR, STAR, BIAT, TUNIS_RE, BNA, ASTREE...).
# Seul le Takaful (Annexes 14/15 spécifiques, cadre réglementaire différent)
# est exclu d'emblée, par cohérence avec ANNEXE13_NON_VIE_EXCLUSIONS. Le
# reste de la liste des exclusions réelles (sociétés purement Non-Vie sans
# aucune ligne Vie dans leur dépôt — ex. COTUNACE, Crédit-Caution) se
# construit EMPIRIQUEMENT au fil des extractions, comme pour l'Annexe 13
# (voir CAS_PARTICULIERS_FULL_TABLE.md) plutôt que d'être devinée ici.
ANNEXE12_VIE_EXCLUSIONS = set(TAKAFUL_CODES)

# ── Normalisation des libellés de ligne (Vie) ───────────────────────────────
CANONICAL_ROWS_VIE = [
    "Primes",
    "Charges de prestations",
    "Charges des provisions d'assurance vie et des autres provisions techniques",
    "Ajustement ACAV (Assurance à Capital Variable)",
    "Solde de souscription",
    "Frais d'acquisition",
    # BH détaille séparément la reprise de frais reportés d'exercices
    # antérieurs — poste propre au gabarit Vie, absent du Non-Vie.
    "Variation des frais d'acquisition reportés",
    "Autres charges de gestion nettes",
    "Charges d'acquisition et de gestion nettes",
    "Produits nets de placements",
    # BH seul : "Charges de placements" est déduite séparément plutôt que
    # nette dans "Produits nets de placements" — voir CAS_PARTICULIERS
    # (Annexe 13) pour le même schéma déjà rencontré côté Non-Vie.
    "Charges de placements",
    "Participation aux résultats et intérêts techniques",
    "Solde financier",
    "Primes cédées et/ou rétrocédées",
    # Contrairement au Non-Vie (réassurance rattachée aux PRIMES acquises),
    # le gabarit Vie rattache le 1er poste de réassurance aux CHARGES DE
    # PRESTATIONS — confirmé convergent sur AMI/BH/COMAR.
    "Part des réassureurs dans les charges de prestations",
    "Part des réassureurs dans les charges de provisions",
    "Part des réassureurs dans la participation aux résultats",
    "Commissions reçues des réassureurs / rétrocessionnaires",
    "Solde de réassurance / rétrocession",
    "Résultat technique",
    # Informations complémentaires (bloc disclosure, pas de contrôle croisé).
    "Montant des rachats",
    "Intérêts techniques bruts de l'exercice",
    "Provisions techniques brutes à la clôture",
    "Provisions techniques brutes à l'ouverture",
    "Provisions devenues exigibles",
]

_MATCH_THRESHOLD_VIE = 0.55

# Variante récurrente (AMI, GAT — gabarit "raccordement") du libellé "Produits
# nets de placements" : trop longue/diluée pour que la correspondance floue
# (difflib, ratio global) la rattache correctement au poste canonique
# (beaucoup de mots en plus font chuter le ratio sous le seuil).
_KNOWN_PREFIXED_VARIANTS_VIE = {
    "produits alloues transferes a l etat de resultat non technique": "Produits nets de placements",
    "produits de placements alloues transferes de l etat de resultat": "Produits nets de placements",
    "produits de placements alloues transferes a l etat de resultat non technique": "Produits nets de placements",
}


def normalize_row_label_vie(raw_label):
    """Équivalent Vie de `annexe13_pipeline.normalize_row_label` : même
    moteur (correspondance floue), vocabulaire `CANONICAL_ROWS_VIE`."""
    return _normalize_row_label(raw_label, canonical_rows=CANONICAL_ROWS_VIE,
                                 threshold=_MATCH_THRESHOLD_VIE,
                                 known_prefixed_variants=_KNOWN_PREFIXED_VARIANTS_VIE)


def normalize_table_vie(grid):
    """Équivalent Vie de `annexe13_pipeline.normalize_table`."""
    return _normalize_table(grid, canonical_rows=CANONICAL_ROWS_VIE,
                             row_threshold=_MATCH_THRESHOLD_VIE,
                             known_prefixed_variants=_KNOWN_PREFIXED_VARIANTS_VIE)


# ── Validation par règles métier (Vie) ──────────────────────────────────────
# Identités observées (et vérifiées, écart nul) sur AMI/BH/COMAR : toutes les
# valeurs sont déjà SIGNÉES (charges négatives), chaque identité est une
# simple somme — même principe que le Non-Vie, formules adaptées au
# vocabulaire Vie (pas de scission primes acquises/émises côté Vie).
VALIDATION_RULES_VIE = [
    ("solde_souscription",
     "Solde de souscription = Primes + Charges de prestations + Charges des provisions d'assurance vie et des autres provisions techniques",
     "Solde de souscription",
     ["Primes", "Charges de prestations",
      "Charges des provisions d'assurance vie et des autres provisions techniques",
      "?Ajustement ACAV (Assurance à Capital Variable)"]),
    ("charges_acquisition_gestion",
     "Charges d'acquisition et de gestion nettes = Frais d'acquisition + Autres charges de gestion nettes",
     "Charges d'acquisition et de gestion nettes",
     ["Frais d'acquisition", "Autres charges de gestion nettes",
      "?Variation des frais d'acquisition reportés"]),
    ("solde_financier",
     "Solde financier = Produits nets de placements + Participation aux résultats et intérêts techniques",
     "Solde financier",
     ["Produits nets de placements", "Participation aux résultats et intérêts techniques",
      "?Charges de placements"]),
    ("solde_reassurance",
     "Solde de réassurance / rétrocession = Primes cédées et/ou rétrocédées "
     "+ Part des réassureurs dans les charges de prestations + Part des réassureurs dans "
     "les charges de provisions + Part des réassureurs dans la participation aux résultats "
     "+ Commissions reçues des réassureurs / rétrocessionnaires",
     "Solde de réassurance / rétrocession",
     ["?Primes cédées et/ou rétrocédées",
      "Part des réassureurs dans les charges de prestations",
      "Part des réassureurs dans les charges de provisions",
      "?Part des réassureurs dans la participation aux résultats",
      "Commissions reçues des réassureurs / rétrocessionnaires",
      # BIAT (comme côté Non-Vie, voir CAS_PARTICULIERS_FULL_TABLE.md) loge
      # les intérêts servis aux réassureurs dans son bloc réassurance, en
      # déduction du Solde de réassurance — vérifié 2026-09-11, BIAT_2015.
      "?Intérêts techniques bruts de l'exercice"]),
    ("resultat_technique",
     "Résultat technique = Solde de souscription + Charges d'acquisition et de gestion nettes "
     "+ Solde financier + Solde de réassurance / rétrocession",
     "Résultat technique",
     ["Solde de souscription", "Charges d'acquisition et de gestion nettes",
      "Solde financier", "Solde de réassurance / rétrocession"]),
]


def validate_table_vie(normalized_lignes, columns):
    """Équivalent Vie de `annexe13_pipeline.validate_table`."""
    return _validate_table(normalized_lignes, columns, rules=VALIDATION_RULES_VIE)


def process_annexe12(pdf_path, is_target_page, kpi_patterns, raccordement_re, relaxed_page_predicate,
                      use_ocr_fallback=True):
    """Pipeline complète pour un document, symétrique de
    `annexe13_pipeline.process_annexe13` : localise + extrait la grille
    (full_table_extractor, sans le repli "notes narratives" — construit
    spécifiquement pour le gabarit Non-Vie), normalise et valide avec le
    vocabulaire Vie. Renvoie None si aucune page valide n'a été trouvée.
    `use_ocr_fallback=False` saute le repli OCR (lent, plusieurs minutes par
    document) — utile pour un audit rapide de couverture avant de s'attaquer
    aux documents scannés un par un (saisie manuelle vérifiée, voir
    extraction/annexe12_verified.py, plutôt que l'OCR)."""
    from extraction.full_table_extractor import locate_and_extract_full_table

    page_num, grid = locate_and_extract_full_table(
        pdf_path, is_target_page, kpi_patterns, raccordement_re,
        extra_page_predicate=relaxed_page_predicate, use_notes_fallback=False,
        use_ocr_fallback=use_ocr_fallback, ocr_vie_mode=True,
    )
    if grid is None:
        return None

    normalized = normalize_table_vie(grid)
    validations = validate_table_vie(normalized["lignes"], normalized["colonnes"])
    return {
        "page": page_num,
        "colonnes": normalized["colonnes"],
        "lignes": normalized["lignes"],
        "non_reconnues": normalized["non_reconnues"],
        "colonnes_non_reconnues": normalized["colonnes_non_reconnues"],
        "validations": validations,
    }
