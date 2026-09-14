# Bilan Actif/Passif — extraction pleine grille : suivi des cas particuliers

Symétrique de `CAS_PARTICULIERS_FULL_TABLE.md` (Annexe 12/13), pour le
tableau Bilan Actif/Passif. Voir `extraction/bilan_full_extractor.py` pour
le code et les commentaires de conception.

## 2026-09-14 — démarrage : architecture + validation sur COMAR 2023

**Pourquoi pas camelot (contrairement à Annexe 12/13)** : le tableau Bilan
n'a pas de quadrillage horizontal entre ses lignes de détail — camelot
(flavor lattice) fusionne alors toutes les lignes d'une section en une
seule cellule multi-lignes par colonne. Vérifié sur COMAR 2023 : le nombre
de lignes internes diffère d'une colonne à l'autre dès qu'une cellule est
vide sur certaines lignes (ex. colonne "Amort & Prov" : 46 lignes contre 51
pour les autres colonnes) — un zip par index désynchronise tout après la
première case blanche. `full_table_extractor.py` (le moteur camelot
d'Annexe 12/13) n'est donc pas réutilisable ici tel quel.

**Approche retenue** : reconstruction par position des mots
(`page.extract_words()` + `_cluster_lines`, primitives déjà éprouvées de
`bilan_kpi_extractor.py` pour l'extraction ciblée 5-KPI existante), pas
camelot. Chaque ligne du Bilan porte un CODE réglementaire standardisé
(AC1, AC12, PA310, CP1...) — identique chez toutes les sociétés (plan
comptable CMF) — utilisé comme clé canonique plutôt que le libellé
français (bien plus fragile, comme vu sur Annexe 12/13). Colonnes
assignées par proximité à la position x0 de l'en-tête correspondant
(Brut/Amort/Net/Net N-1 côté Actif, Net/Net N-1 côté Passif) — jamais par
ordre pur, pour ne pas décaler les valeurs suivantes quand une cellule est
vide au milieu de la ligne.

**2 bugs génériques corrigés au passage** (bénéficient aussi à l'extraction
KPI existante, pas seulement à ce nouveau module) :
1. `_words_with_bracket_negatives_resolved` (bilan_kpi_extractor.py) :
   une parenthèse contenant du texte non numérique ("(vie)", "(non vie)")
   laissait l'état "négatif en attente" actif jusqu'au PROCHAIN vrai
   nombre de la ligne, le négativant à tort (ex. AC530 "Provisions pour
   sinistres (vie)" ressortait à -810930 au lieu de 810930). Corrigé :
   l'attente est annulée dès qu'un mot alphabétique est rencontré.

**Validé sur COMAR 2023** : Actif (44 lignes codées, page 2) et Passif (26
lignes, page 3) — Σ des 6 sections de premier niveau (AC1+AC2+AC3+AC5+
AC6+AC7) = Total de l'actif EXACTEMENT (1 043 627 038), Σ des 5 sections
Passif (PA23+PA3+PA5+PA6+PA7 — recodées CP/PA selon le document) = Total
du passif EXACTEMENT (739 207 359), et Total Actif = Capitaux propres +
Total Passif EXACTEMENT. Aucun écart.

**Pas encore généralisé** : testé rapidement sur ATTIJARI/MAGHREBIA/GAT
2023 — extraction structurelle réussie (25-44 lignes trouvées) mais Σ des
sections ≠ Total sur ces 3 (mismatch), signe de variations de gabarit par
société (codes de section différents — ATTIJARI a des CP3/CP5/PA4 absents
chez COMAR — ou en-têtes de colonnes positionnés différemment) qui n'ont
PAS encore été investiguées une par une. Attendu : ce même travail
d'itération société par société qu'Annexe 12/13 a demandé sur plusieurs
sessions (voir CAS_PARTICULIERS_FULL_TABLE.md) sera nécessaire ici aussi
avant une couverture large et fiable. Pas de pipeline `process_bilan_*`
ni de branchement `tableau_pipeline_service`/route API encore écrit — le
module d'extraction est la première brique, pas encore connecté au
stockage `tableau_cellules` ni à l'UI.

**Prochaines étapes suggérées** : (1) lister les codes de section réels
observés par société (comme AC1..AC7 ne sont pas garantis universels —
ATTIJARI en est la preuve), pour bâtir une liste canonique plus complète
et une règle de validation Total robuste malgré ces variations ; (2)
écrire `normalize_table`/`validate_table` + `process_bilan_actif`/
`process_bilan_passif` sur le modèle d'`annexe13_pipeline.py` ; (3)
brancher `tableau_pipeline_service` (tableau='bilan_actif'/'bilan_passif')
et la route `/api/gestion-donnees/valider-*` correspondante ; (4) sweep
complet du portefeuille pour mesurer la couverture réelle avant tout
travail de correction cas par cas.

## 2026-09-14 (suite) — durcissement société par société : 4/4 sociétés testées à 0 écart

Poursuite immédiate de l'entrée précédente. **COMAR, ATTIJARI, MAGHREBIA,
GAT** (2023, Actif + Passif) passent maintenant à 0 écart (Σ sections =
Total, exact ou à l'arrondi près) après une série de correctifs
GÉNÉRIQUES (aucun ne cible une société en particulier) :

1. **Nombre de colonnes détecté dynamiquement** — certaines sociétés (ex.
   ATTIJARI) ventilent aussi Brut/Amortissements pour l'année précédente
   (6 colonnes numériques), pas seulement l'année courante (4 colonnes,
   le cas le plus fréquent). Un nombre de colonnes supposé fixe faisait
   ressortir Amort/Net/Net(N-1) entièrement vides.
2. **Alias de colonne "VB"** (Valeur Brute, MAGHREBIA) reconnu comme
   variante de "Brut" — sinon toute la colonne Brut restait vide.
3. **Références de note filtrées** ("3.1", "3.1.1"...) — un UNIQUE mot
   avec point, jamais un vrai montant (toujours des dinars entiers dans
   ces tableaux) ; se glissaient sinon dans la colonne la plus proche et
   en corrompaient la valeur. Une 1ère tentative par marge de position x0
   s'est révélée peu fiable (colonnes alignées à droite : un montant large
   démarre plus à gauche que son en-tête, court) — remplacée par ce test
   sur la FORME du jeton lui-même, robuste indépendamment de l'alignement.
4. **Ligne de sous-total de section sans code ni libellé** (répandu :
   "AC1 Actifs incorporels" en en-tête, enfants AC11/AC12/AC13, puis une
   ligne de chiffres SEULE = le sous-total AC1) — rattachée au code de
   section ouvert, mais seulement si elle porte assez de valeurs pour
   être un sous-total plausible (≥ n_cols-1) ; sinon une valeur isolée
   parasite (ex. un "0" esseulé constaté MAGHREBIA/AC64) aurait "consommé"
   la place et fait perdre le VRAI sous-total arrivant juste après.
5. **Ligne de TOTAL général réduite au seul mot "Total"** (ATTIJARI) —
   le motif exigeait auparavant "total (de l'actif|des actifs)" et
   ratait ce cas.
6. **Parenthèses de négatif résolues avant la reconstruction du libellé**
   (pas seulement avant l'extraction des valeurs) — un résidu comme
   "(95 277)" issu d'un montant entre parenthèses mal séparé restait sinon
   dans le texte du libellé et empêchait par exemple la ligne de TOTAL de
   GAT ("Total des actifs (95 854 277) ...") d'être reconnue comme telle.
7. **Code réglementaire séparé de son numéro par une espace** ("AC 71" au
   lieu de "AC71", constaté ATTIJARI et BIAT) — fusionné en un seul jeton
   avant tout traitement, sinon le numéro seul ("71") était indiscernable
   d'une vraie valeur et disparaissait du libellé avant même la détection
   du code.

**Pas encore couvert** (constaté en élargissant le test à 8 sociétés
supplémentaires) :
- **STAR, BH, TUNIS_RE, AMI** : page Actif introuvable pour au moins un
  des deux côtés — même famille que les cas déjà documentés dans
  `CAS_PARTICULIERS_FULL_TABLE.md` (page scannée/couche texte cassée,
  parfois seul un côté Actif OU Passif est concerné selon le document).
  Pas une nouvelle catégorie de bug — la même voie OCR/saisie manuelle
  qu'Annexe 12/13 s'appliquera si besoin, pas encore branchée ici.
- **ASTREE** : convention différente — code SANS espace ET collé au
  libellé ("ACActifs incorporels"), sous-lignes regroupant plusieurs codes
  sur une seule ligne ("AC11,12,13..."). Pas traité.
- **BIAT** : une ligne de sous-total (AC5) montre un artefact de rendu où
  le premier chiffre se détache du reste du nombre ("2 4 775 196" au lieu
  de "24 775 196"), faisant échouer son rattachement à la section. Cas
  isolé constaté sur une seule ligne, pas généralisé, pas corrigé.

**Statut** : 4/4 sociétés testées avec un gabarit "normal" (texte natif
exploitable) sont maintenant parfaites. Les cas restants relèvent soit de
limitations déjà connues (scan), soit de conventions différentes non
encore rencontrées — prochaine étape naturelle : élargir le sweep à
davantage de sociétés/années pour mesurer la couverture réelle avant de
continuer au cas par cas.

## 2026-09-14 (suite) — ASTREE et BIAT : 6/6 sociétés testées à 0 écart

Poursuite immédiate. **ASTREE et BIAT** rejoignent COMAR/ATTIJARI/
MAGHREBIA/GAT — tous à 0 écart maintenant (Actif ET Passif), avec 3
correctifs supplémentaires, tous génériques :

1. **"-" isolé exclu du libellé** (placeholder "néant", ex. "AC540... -
   - -") : ne matchait pas `NUMERIC_TOKEN_RE` (exige ≥1 chiffre) et se
   retrouvait donc dans le texte du libellé — une ligne de sous-total
   faite seulement de chiffres et de "-" isolés (Amort/Net non ventilé
   sur cette ligne) ressortait alors avec un libellé non vide ("-"),
   ratant la détection "ligne de sous-total sans libellé" (constaté
   BIAT/AC5).
2. **Total combiné "Capitaux propres et Passifs"** reconnu comme variante
   valide de ligne de total (clé séparée `TOTAL_GENERAL`, jamais confondue
   avec `TOTAL` = Total du Passif seul) — certains documents (BIAT, ASTREE)
   n'imprimment JAMAIS de "Total du Passif" isolé, seulement ce total
   combiné (= Total de l'Actif).
3. **Code réglementaire collé au libellé, AVEC numéro** ("AC11,12,13Inves-
   tissements...", "AC2Actifs...", constaté ASTREE) : `_ROW_CODE_RE`
   n'exigeait plus de séparateur après le numéro (`\b` retiré) — capture
   aussi les listes de codes séparées par virgule (garde le premier).
4. **Code top-level collé, SANS aucun numéro** ("ACActifs incorporels",
   ASTREE) : le numéro de section apparaît ailleurs sur la MÊME ligne
   comme référence de note isolée (lettre reprenant l'initiale du préfixe
   + numéro, ex. "...incorporels A 1 3 089 682..." -> section 1). Repéré
   et recollé au préfixe avant tout le reste du traitement (partie
   décimale ignorée si présente, ex. "A 3.1" -> 3, non pertinent ici car
   ce marqueur n'apparaît que sur les lignes de section top-level, jamais
   sur un sous-poste qui a déjà son propre code explicite).

**6/6 sociétés testées avec un texte natif exploitable sont maintenant
parfaites** (COMAR, ATTIJARI, MAGHREBIA, GAT, BIAT, ASTREE — Actif et
Passif, 12/12 côtés). Restent, comme avant : STAR/BH/TUNIS_RE/AMI (pages
scannées/texte cassé, catégorie déjà connue).
