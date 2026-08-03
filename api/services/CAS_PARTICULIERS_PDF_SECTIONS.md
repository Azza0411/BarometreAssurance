# Cas particuliers — Traçabilité PDF (pdf_sections.py, pdf_cell_coords.py)

Ce fichier suit le même principe que `extraction/CAS_PARTICULIERS*.md` et
`api/services/CAS_PARTICULIERS_QUALITE.md` : recense les limitations connues
et les décisions de conception pour la fonctionnalité de traçabilité PDF
(localisation de page + surlignage de cellule, utilisée par `KpiDetail.jsx`),
mise à jour au fil de l'eau.

## Résolu (août 2026 — audit surlignage PDF)

- **Surlignage du libellé au lieu de la valeur** : `_find_row_y` choisissait
  la ligne correspondante la plus courte, ce qui favorisait à tort une ligne-
  titre sans chiffres (ex. "Primes émises acceptées" sans montant sur la
  ligne visuelle) plutôt que la vraie ligne de données. **Fixé** : les lignes
  candidates contenant au moins un token numérique sont désormais préférées
  avant d'appliquer la règle "plus courte gagne" (`_row_has_digit`,
  `_pick_shortest`).
- **Mauvaise cellule sur les pages à plusieurs tableaux empilés** :
  `_find_col_x` cherchait l'en-tête de colonne "au-dessus de la ligne" sans
  tenir compte des limites de tableau, et pouvait capter l'en-tête d'un AUTRE
  tableau plus haut sur la page. **Fixé** : la bbox du tableau
  (`page.find_tables()`) contenant la ligne cible restreint désormais la
  recherche d'en-tête à ce même tableau, avec repli sur le comportement
  précédent si la ligne n'appartient à aucun tableau détecté.
- **Aucun diagnostic quand le surlignage échoue** : `get_cell_coords`
  renvoyait `None` silencieusement. **Fixé** : retourne désormais
  `(coords, reason)` avec une raison explicite (`pdf_manquant`,
  `page_invalide`, `page_vide`, `ligne_introuvable`, `colonne_introuvable`,
  `cellule_introuvable`, `erreur`), affichée dans `KpiDetail.jsx` au lieu de
  laisser l'absence de surlignage sans explication.
- **`_REQUIRED` mort pour annexe12/annexe13** : le pré-filtre imposait la
  présence de "vie individuelle" / "vie collective" dans la page — **cette
  catégorisation n'apparaît dans AUCUN des PDF CMF réels observés** (24
  sociétés, PDFs 2017-2025 confondus). La vraie catégorisation Vie varie par
  compagnie/vintage ("Vie Décès Mixte Acceptation" chez STAR/COMAR, "Vie
  Décès Mixte Capitalisation" chez ASTREE, etc.) — un pré-filtre sur les
  noms de catégories ne peut donc pas généraliser. Résultat concret avant
  correctif : le pré-filtre échouait systématiquement, la recherche
  retombait en mode "relâché" (scoring pleine page sans garde-fou), et pour
  les sociétés dont la page annexe12/13 ne dominait pas le score brut
  (ASTREE, BIAT, GAT — voir tableau ci-dessous), une AUTRE page contenant un
  vocabulaire proche (ex. "Annexe n°4 — État de résultat technique de
  l'Assurance VIE", qui parle aussi de "catégorie d'assurance Vie" et de
  "résultat technique") était sélectionnée à la place de la vraie page
  annexe12. **Fixé** : le `_REQUIRED` et un nouveau pattern à poids fort
  (5) reposent maintenant sur le TITRE de page lui-même
  (`annexe\s*n?\.?\s*12(?!\d)` / `...13...`), qui lui est un invariant réel
  du format CMF quelle que soit la société — vérifié sur "(annexe 12)"
  (STAR), "annexe n12 :" (ASTREE), "Annexe n°12" (GAT/BIAT/etc.).
- **`_REQUIRED` absent pour bilan/bilan_passif/etat_resultat** : ces 3
  sections n'avaient ni pré-filtre ni soustraction de score rival,
  contrairement à annexe12/13 — un score purement additif reste vulnérable
  à une page qui mentionne la section en passant. **Fixé** : ajout d'un
  `_REQUIRED` basé sur des libellés de ligne/total qui n'apparaissent en
  pratique que sur la page du tableau lui-même (ex. "total de l'actif",
  "capitaux propres et le passif").
- **Composite Vie+Non-Vie mal surligné** (`KpiDetail.jsx::handleChipClick`) :
  cliquer le chip d'une composante `calcule` (ex. "Charges de prestations"
  = Vie + Non-Vie) naviguait automatiquement vers le PDF du PREMIER sous-
  composant trouvé, même quand la valeur affichée est la somme des deux —
  résultat incohérent si l'utilisateur pensait consulter le Non-Vie.
  **Fixé** : le clic sur un chip composite n'auto-navigue plus ; `CalcDetail`
  affiche déjà chaque sous-composante avec son propre bouton "Localiser dans
  le PDF", laissant le choix explicite à l'utilisateur.

## Vérification empirique (8 sociétés × cas connus problématiques)

Script : recherche `get_pdf_sections` + `get_cell_coords` sur "Primes émises"
(annexe12/13), "PRIMES ACQUISES" (annexe13), "Charges d'acquisition et de
gestion nettes" (annexe13), avec contrôle visuel (mot le plus proche du
centre de la bbox retournée doit contenir un chiffre).

**Détection de PAGE (annexe12/13) — 8/8 sociétés correctes après correctif :**

| Société  | Avant correctif                                  | Après correctif |
|----------|---------------------------------------------------|------------------|
| STAR, COMAR | déjà correct (chance du scoring non filtré)     | correct (page confirmée par titre) |
| ASTREE   | annexe12 → page 5 ("Annexe n°4", **mauvaise page**), surlignait "acceptées" au lieu d'une valeur | annexe12 → page 36 (vraie page, titre "Annexe n°12 :") |
| BIAT     | annexe12 → page 5 (mauvaise page)                | annexe12 → page 30 (vraie page) |
| GAT      | annexe12 → page 5 (mauvaise page), annexe13 → page 19 (mauvaise page) | annexe12 → page 33, annexe13 → page 34 (vraies pages) |
| MAGHREBIA| annexe12 introuvable (`ligne_introuvable`)       | annexe12 absent **à raison** — cette entité ne déclare pas de résultat technique Vie séparé cette année-là (pas d'"Annexe n°12" dans le document ; seule "Annexe n°13" existe) — comportement correct, pas un bug |

**Détection de CELLULE (ligne × colonne), une fois la bonne page trouvée —
21/32 cas OK, 11 cas correctement signalés `ligne_introuvable`/
`colonne_introuvable` plutôt que de surligner une mauvaise cellule :**

- annexe13 (Non-Vie) : 8/8 — tous les cas testés sur toutes les sociétés
  fonctionnent (vocabulaire "Primes émises"/"PRIMES ACQUISES"/"Charges
  d'acquisition..." stable d'une compagnie à l'autre côté Non-Vie).
- annexe12 (Vie) : la ligne "Primes émises" échoue (`ligne_introuvable`)
  chez ASTREE, GAT, BIAT — **cause identifiée, pas un bug de code** : leur
  tableau Annexe n°12 utilise **"Primes Acquises"** comme unique libellé de
  prime côté Vie (pas de ligne "Primes émises" séparée), contrairement au
  gabarit STAR/COMAR qui a les deux lignes distinctes. Confirmé en lisant le
  texte brut de la page (ex. ASTREE p.36 : `"Primes Acquises 1 101 009
  16 309 989 ..."`, aucune occurrence de "Primes émises"). "Primes émises"
  et "Primes acquises" ne sont PAS la même quantité comptable (différence =
  variation de la provision pour primes non acquises) : un remplacement
  automatique par un synonyme produirait une valeur incorrecte dans un outil
  d'audit, donc **volontairement non "corrigé"** — le comportement actuel
  (`ligne_introuvable`, pas de surlignage, raison affichée) est le choix
  sûr. GAT présente en plus `colonne_introuvable` sur "Charges
  d'acquisition..." Vie pour la même raison de nomenclature différente.

## Limitation connue restante

- **Vocabulaire de ligne non uniforme entre compagnies pour l'Annexe n°12
  (Vie)** : voir ci-dessus — `KPI_META` cible `ligne: "Primes émises"` de
  façon uniforme, alors que certains gabarits (ASTREE, GAT, BIAT observés)
  n'ont que "Primes Acquises" à cet emplacement. Comportement actuel :
  échec sûr (`ligne_introuvable`), jamais de mauvaise valeur surlignée.
  Une vraie correction nécessiterait soit un mapping de libellés alternatifs
  par société dans `KPI_META`, soit de vérifier si "Primes émises" existe
  réellement dans la donnée extraite en base pour ces sociétés (si
  `extraction/annexe12_kpi_extractor.py` ne l'extrait pas non plus pour ces
  cas, le KPI concerné est probablement déjà `manquant` côté dashboard —
  cohérent avec le surlignage indisponible).
- **Noms de colonnes non uniformes selon le template** : `KPI_META`
  suppose `colonne: "Total"` pour la plupart des lignes extrait/annexe12/13.
  Si un gabarit utilise une colonne différente (ex. "Opérations nettes" au
  lieu de "Total"), `_find_col_x` renverra `colonne_introuvable` plutôt
  qu'une fausse cellule — comportement sûr mais pas de surlignage pour ce
  cas tant qu'un mapping colonne par template n'est pas ajouté.
