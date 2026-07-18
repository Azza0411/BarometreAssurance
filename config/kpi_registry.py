"""
Table de correspondance use case -> liste de KPI, pour structurer la
récupération des données par page/dashboard côté frontend.

Ceci n'est PAS une nouvelle table de stockage : `kpi_values` reste la
source unique de vérité. Ce registre sert uniquement de filtre au moment de
la requête (voir database.repository.get_kpi_values_by_use_case) — il
évite de dupliquer les valeurs de KPI par use case.

Les noms ci-dessous sont ceux RÉELLEMENT stockés dans `kpi_values` (corrigés
par rapport à la liste d'origine fournie : accents/apostrophes normalisés,
noms alignés sur ceux produits par les extracteurs). Certains KPI (ex:
"Nombre d'agences par assureur") sont stockés sous une forme éclatée par
entité, ex: "Nombre d'agences par assureur - STAR" : get_kpi_values_by_use_case
les retrouve par préfixe automatiquement, pas besoin de lister chaque société
ici.

"Capitalisation boursière" et "Cours de l'action" (voir
extraction/CAS_PARTICULIERS_BVMT.md) : "Cours de l'action" est copié depuis
le bulletin officiel de la cote BVMT du dernier jour de bourse de chaque
année (2015 à aujourd'hui) ; "Capitalisation boursière" (MDT) = Nombre
d'actions x Cours de l'action, calculé dans
extraction/calculated_kpi_extractor.py (compute_bvmt_market_kpis). Le Nombre
d'actions vient en priorité de CMF (ligne "Capital social", ~4% de
couverture seulement), avec repli sur le nombre de titres émis ACTUEL de
BVMT (une seule valeur, appliquée à toutes les années par approximation —
imprécis en cas d'augmentation de capital passée non reflétée).

"Primes émises par branche" et "Part des primes émises par branche" (voir
extraction/CAS_PARTICULIERS_CGA.md) : extraites de l'Annexe 4-1 du rapport
CGA (nomenclature propre à CGA, volontairement non reconciliée avec les
branches FTUSA sur décision de l'utilisateur — stockées à part).

Non disponible :
  - "Spécialité" : présent dans l'Annexe 1 CGA (colonne du tableau, pas un
    KPI nommé) — pas stocké tel quel pour l'instant.

Volontairement NON stockés (classements/comparaisons dépendant du contexte
d'affichage, à calculer à la volée côté frontend/API à partir des KPI
ci-dessous plutôt que figés en base) :
  - "Classement des assurances selon le nombre d'agences", "Classement des
    assurances", "Rang par primes émises", "Classement région par nombre
    d'agences de la compagnie", "Écart de performance", "Réseau d'agences
    en Tunisie" (concept d'affichage, pas un KPI).
"""

KPI_REGISTRY = {
    "DASH-FS-INS-01-A": [
        "Population Totale",
        "Produit Interieur Brut (PIB)",
        "Taux de pénétration",
        "Densité de l'assurance",
        "Total Primes émises",
        "Primes émises Vie",
        "Primes émises Non-Vie",
        "Part des primes émises Vie",
        "Part des primes émises Non-vie",
        "Total Charges de prestations",
        "Ratio S/P",
        "Total Charges d'acquisition et de gestion nettes",
        "Ratio de frais",
        "Ratio combiné",
        "Nombre d'assureurs",
    ],
    "DASH-FS-INS-01-C": [
        "Total agences",
        "Nombre d'assureurs",
        "Nombre moyen d'agences par assureur",
        "Nombre d'agences par assureur",  # éclaté par compagnie
        "Assurance avec le plus d'agences",
        "Nombre d'agences par région",  # éclaté par grande région
        "Région la plus concentrée",
        "Répartition des agences par gouvernorat",  # éclaté par gouvernorat
        "Répartition des agences par grande région",  # éclaté par grande région
        "Nombre d'agences par compagnie",  # éclaté par compagnie
        "Part de marché réseau (%)",  # éclaté par compagnie
    ],
    "DASH-FS-INS-02": [
        "Part de marché (%)",
        "Total Primes émises",
        "Primes émises par assurance",
        "Primes émises Vie par assurance",
        "Primes émises Non-Vie par assurance",
        "Ratio de sinistralité (%)",
        "Charge de sinistres",
        "Charge de sinistres Vie",
        "Charge de sinistres Non-Vie",
        "Primes acquises",
        "Ratio combiné (%)",
        "Charges de prestations",
        "Charges d'acquisition et de gestion nettes",
        "Charges de prestations Vie",
        "Charges de prestations Non-Vie",
        "Charges d'acquisition et de gestion nettes Vie",
        "Charges d'acquisition et de gestion nettes Non-Vie",
        "Ratio de frais de gestion (%)",
        "ROE (%)",
        "Résultat Net",
        "Capitaux propres",
        "Total actif",
        "ROA (%)",
        "Résultat technique (TND)",
        "Résultat technique Vie",
        "Résultat technique Non-Vie",
    ],
    "DASH-FS-INS-03-A": [
        "Date de création",
        "Siège social",
        "Primes émises par assurance",
        "Primes émises Vie par assurance",
        "Primes émises Non-Vie par assurance",
        "Status de cotation",
        "Capitalisation boursière",
        "Cours de l'action",
        "Nombre d'actions",
        "Part de marché (%)",
        "Total Primes émises",
        "Effectif",
        "Nombre d'agences par assureur",
        "Nombre d'agences de la compagnie par région",  # éclaté par compagnie x région
        "Répartition des agences par gouvernorat",
        "Directeur général",
        "Président du Conseil d'Administration",
        "Résultat Net",
        "Ratio de sinistralité (%)",
        "Ratio combiné (%)",
        "Ratio de frais de gestion (%)",
        "Charge de sinistres",
        "Charge de sinistres Vie",
        "Charge de sinistres Non-Vie",
        "Primes acquises",
        "Charges de prestations",
        "Charges d'acquisition et de gestion nettes",
        "Charges de prestations Vie",
        "Charges de prestations Non-Vie",
        "Charges d'acquisition et de gestion nettes Vie",
        "Charges d'acquisition et de gestion nettes Non-Vie",
    ],
    "DASH-FS-INS-03-B": [
        "Résultat Net",
        "Total actif",
        "Total Passif",
        "ROA (%)",
        "ROE (%)",
        "Capitaux propres",
        "Actifs incorporels",
        "Actifs corporels",
        "Placements",
        "Créances",
        "Autres éléments d'actifs",
        "Autres passifs",
        "Part des réassureurs dans les provisions techniques",
        "Provisions pour Primes non acquises",
        "Provisions d'assurance",
        "Charges des provisions d'assurance vie et des autres provisions techniques",
        "Charges des provisions pour prestations diverses",
        "Provisions techniques brutes",
        "Obligations",
        "Actions et titres de participation",
        "OPCVM",
        "Dépôts et liquidité",
        "Placements représentant des provisions techniques",
    ],
}
