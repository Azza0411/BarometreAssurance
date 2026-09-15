# Cas particuliers — Takaful Annexes 3/4 (État de Surplus ou Déficit des fonds Takaful Familial/Général)

## 2026-09-15 — Création du module `takaful_surplus_full_extractor.py`

Contexte : demande explicite de l'utilisateur — identifier TOUTES les
annexes utilisées pour extraire des KPI Takaful et leur donner l'extraction
grille complète, comme déjà fait pour les conventionnels (Bilan, Annexe
12/13). Catalogue établi à partir de `takaful_kpi_extractor.py` (637
lignes) : Bilan Combiné (Annexes 1/2, déjà fait), **Annexe 3** (Surplus/
Déficit Familial), **Annexe 4** (Surplus/Déficit Général), Annexe 5.1
(État de résultat de l'entreprise), Annexes 14/15 (ventilation par
branche). Ce module traite Annexe 3 et 4 — équivalent Takaful d'Annexe
12/13 pour les conventionnels.

### Structure du tableau

Chaque ligne porte un code réglementaire (PRF/CHF côté Familial, PRG/CHG
côté Général), à l'exception de "CH8" (Impôt sur le résultat, code
partagé sans suffixe numérique) et des lignes "Sous total N" (sans code,
numérotées séquentiellement dans le document, pas rattachées à une
section comme pour le Bilan). 4 colonnes : Opérations brutes / Cessions
et/ou rétrocessions / Opérations nettes (exercice courant) / Opérations
nettes (exercice précédent).

### Bugs trouvés et corrigés pendant le développement (AT_TAKAFULIA 2023)

1. **Numéro de section "Sous total N" comptabilisé comme une valeur** —
   "Sous total 1 14 349 094 ..." : le "1" après "total" matche
   `NUMERIC_TOKEN_RE` comme n'importe quel autre nombre, donc se glissait
   comme 1er élément de `_extract_numeric_clusters`, décalant TOUTES les
   colonnes réelles d'une position. Corrigé par
   `_strip_leading_section_number` : retire ce token AVANT tout calcul de
   cluster, dès qu'une ligne commence par "sous total" suivi d'un entier
   de 1-2 chiffres.
2. **Ligne "Surplus ou déficit..." jamais capturée** — le libellé s'étale
   sur 2-3 lignes physiques ("Surplus ou déficit de l'assurance Takaful" /
   "et/ou Rétakaful Familial"), et les valeurs peuvent atterrir sur
   N'IMPORTE LAQUELLE de ces lignes selon la variante (sur la ligne
   "Surplus..." elle-même pour la 1re occurrence, sur la ligne de
   continuation "...après modification" pour la 2e). Une regex de
   correspondance exacte sur une seule ligne ratait donc systématiquement
   ce résultat — pourtant le plus important de tout le tableau. Corrigé
   par une détection en 2 temps : ancre lâche (`_SURPLUS_ANCHOR_RE`, juste
   le début de la phrase) + balayage d'une fenêtre de 3 lignes pour a)
   distinguer la variante "après modification comptable" via le texte
   concatené de la fenêtre b) trouver les valeurs sur la première ligne de
   la fenêtre qui en a — même principe que
   `takaful_kpi_extractor.py::_find_row_on_page`, déjà conçu pour ce
   problème.
3. **Correspondance colonne ordinale naïve** — une 1re version mappait
   `clusters[i] -> colonnes[i]` directement, ce qui casse dès qu'une
   colonne du MILIEU (typiquement "Cessions") est absente SANS même un
   tiret imprimé (contrairement au Bilan, où un "-" explicite marque
   presque toujours une cellule vide) : les valeurs suivantes remontaient
   dans les colonnes précédentes. Remplacé par `_assign_columns`, qui
   reprend la convention déjà utilisée par
   `takaful_kpi_extractor.py::_col_nettes_courantes` pour le KPI narrow :
   "Opérations nettes (N-1)" = TOUJOURS la dernière valeur présente,
   "Opérations nettes (courant)" = l'avant-dernière, "Opérations brutes"
   puis "Cessions" comblées dans l'ordre avec ce qui reste.

### Validation (identité comptable)

Deux règles génériques, vérifiées colonne par colonne :
- Σ("Sous total N") + CH8 (impôt) = Surplus ou déficit
- Surplus + CH9/PR5 (effet des modifications comptables) = Surplus après modification comptable

Sur AT_TAKAFULIA 2023 (Familial) : les colonnes "Opérations nettes" et
"Opérations nettes (N-1)" reconcilient exactement (écart 0 ou 1 dinar,
arrondi) — ce sont les colonnes réellement utilisées par le pipeline KPI
narrow existant (`_col_nettes_courantes`). Les colonnes "Opérations
brutes" et "Cessions" montrent des écarts significatifs : conséquence
directe de la limite ci-dessous (colonne du milieu souvent absente sans
marqueur), pas une erreur de calcul — le KPI narrow historique ne s'est
jamais appuyé sur ces deux colonnes non plus.

### Limitations connues (acceptées, non bloquantes)

- **Colonnes "Opérations brutes"/"Cessions" moins fiables que "Opérations
  nettes"** pour les lignes où plusieurs colonnes intermédiaires sont
  vides sans tiret imprimé — `_assign_columns` ne peut ancrer avec
  certitude que les 2 dernières valeurs présentes.
- **ZITOUNA_TAKAFUL — numéro de note collé sans marqueur distinctif** :
  contrairement à AT_TAKAFULIA (notes "V-1", "V-2"... avec préfixe
  lettré, filtrées comme texte de libellé), ZITOUNA_TAKAFUL imprime le
  numéro de note comme un token NU juste après le signe "+"/"‐" de la
  ligne (ex: "PRF1 Primes + 15 30 680 585 ..." où "15" est le numéro de
  note, pas une valeur) — indiscernable d'une vraie valeur par le seul
  motif du texte. Même famille de problème que le "note-number glued"
  déjà documenté pour le Bilan Takaful de cette société — accepté comme
  limitation plutôt que traité par une heuristique fragile (numéro
  toujours "petit" ? pas garanti sur tous les documents/années).
  ZITOUNA_TAKAFUL n'a donc PAS de grille fiable pour l'instant sur ce
  tableau, malgré un statut technique "ok" (page trouvée, lignes
  extraites) — à revoir si le besoin business se précise.
- **Format "ancien" (pré-réforme) non couvert** : `page_introuvable` sur
  AT_TAKAFULIA 2018 et ZITOUNA_TAKAFUL 2017/2018/2020 — ces documents ne
  publient pas le gabarit "Bilan Combiné" / titres "...Familial"/
  "...Général" ciblés par `_TITLE_RE`. Même distinction "ancien"/
  "nouveau" que `takaful_kpi_extractor.py::detect_format`, non traitée
  ici (portée non demandée pour l'instant).
- **AL_AMANAH_TAKAFUL (arabe) hors périmètre**, comme pour le Bilan
  Takaful — extracteur texte français uniquement.

### Résultat (pipeline `tableau_pipeline_service_takaful_surplus.py`)

13/21 documents (AT_TAKAFULIA + ZITOUNA_TAKAFUL, toutes années
disponibles localement) stockés avec succès (Familial ET Général) sous
`tableau_cellules.tableau = 'takaful_surplus_familial'` /
`'takaful_surplus_general'`. 4 `page_introuvable` (format ancien, voir
ci-dessus), 4 `pdf_absent` (documents non téléchargés localement, 2015/
2016). Route déclenchable manuellement : `POST /api/gestion-donnees/
valider-takaful-surplus` (même schéma que `/valider-bilan`).

### Portée restante (même instruction utilisateur, "allez y")

- Annexe 5.1 (État de résultat de l'entreprise Takaful et/ou Rétakaful) —
  pas encore construite.
- Annexes 14/15 (Ventilation par branche/catégorie) — pas encore
  construites.
- Correction manuelle UI / propagation dashboards pour ces nouvelles clés
  `tableau_cellules` — pas encore branchée (`TABLEAU_GROUPS` dans
  `api/services/data_management.py` ne les référence pas encore),
  cohérent avec la décision déjà prise plus tôt dans la session de
  prioriser "Extraction + stockage d'abord" pour les nouvelles sources.

## 2026-09-15 — Audit de couverture conventionnels (demande explicite utilisateur)

Vérification que TOUS les tableaux utilisés pour l'extraction KPI des
assureurs conventionnels ont déjà leur extraction pleine grille :
- Bilan Actif/Passif → `bilan_full_extractor.py` ✓
- Annexe 12 (Résultat technique Vie) → `full_table_extractor.py` ✓
- Annexe 13 (Résultat technique Non-Vie) → `full_table_extractor.py` ✓
  + repli `notes_resultat_extractor.py` (documents sans page Annexe 13
  unique, ex. BNA) ✓

"État de résultat" (résumé, une seule valeur "Résultat net de
l'exercice"), "Ratios calculés" (dérivés, pas une source brute) et
"Présentation de la société" (paragraphe narratif, pas un tableau à
branches) sont volontairement exclus du concept de grille complète — ce
sont des filtres retirés du sélecteur `TABLEAU_GROUPS` le 2026-09-09 sur
retour utilisateur direct (voir `api/services/data_management.py`), pas
un oubli. **Conclusion : couverture conventionnels déjà complète.**
