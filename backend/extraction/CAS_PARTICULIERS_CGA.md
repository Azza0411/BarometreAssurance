# CGA — extraction pleine grille : suivi des cas particuliers

Pendant "grille complète" (par opposition à `cga_kpi_extractor.py`, qui
génère déjà une kyrielle de KPI nommés dynamiquement mais sans jamais les
organiser en grille) pour l'Annexe 2 "Distribution géographique des
agents d'assurance". Voir `extraction/cga_full_extractor.py`.

## 2026-09-14 — construction (demande utilisateur : grille complète pour les dashboards)

**Contexte** : comme FTUSA, un document CGA est UNIQUE par année, mais
ICI chaque LIGNE de la grille est une COMPAGNIE différente (+ la ligne
"TOTAL" du marché entier) — pas un poste comptable fixe. 24 gouvernorats
en colonnes + "Grand Tunis" (sous-total Tunis+Ariana+Ben Arous+Manouba,
jamais utilisé par l'extraction KPI narrow — capturé ici pour la
complétude, la grille reflétant EXACTEMENT le tableau imprimé) + "Total"
— 26 colonnes en tout.

**Réutilise** les primitives déjà éprouvées de `cga_kpi_extractor.py`
(dérotation des caractères, même cause que FTUSA — matrice de police à
coefficients a=d=0) et `config.company_registry.find_code_by_name` pour
rattacher chaque raison sociale (ex. "STAR SOCIETE TUNISIENNE
D'ASSURANCES ET DE REASSURANCES") au code canonique de la compagnie —
fallback sur le libellé brut si non reconnu, jamais un code deviné.

**Résultat mesuré (CGA 2024)** : 16 compagnies + ligne TOTAL, 26 colonnes
toutes peuplées. Identité de contrôle immédiate déjà vérifiée à la main
(pas une règle automatisée) : Grand Tunis = Tunis+Ariana+Ben Arous+Manouba
pour chaque ligne (ex. STAR : 36+17+13+6=72 ✓), et la ligne TOTAL = somme
des compagnies par gouvernorat (ex. Tunis : 331 = somme des 16
compagnies).

**Pas encore fait** : diagnostic des années plus anciennes (2013-2019,
gabarit de page potentiellement différent — pas testé) ; aucune règle de
validation métier automatisée (l'identité Grand Tunis / TOTAL n'est pas
encore vérifiée par le code, seulement à la main) ; branchement dans
Correction manuelle (même limitation que FTUSA — chantier séparé,
décidé explicitement avec l'utilisateur).
