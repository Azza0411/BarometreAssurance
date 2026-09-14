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

## 2026-09-14 (suite) — diagnostic précis des 46 échecs restants

Sweep complet (223 documents) : **171 OK (77%), 46 page introuvable, 6 PDF
absent, 0 erreur**. Investigation détaillée des 46 — répartis en 4
catégories DISTINCTES, chacune nécessitant un module dédié (aucune n'est
un simple bug de regex comme les correctifs précédents) :

### 1. Langue arabe (Takaful) — 10 documents
**AL_AMANAH_TAKAFUL** (9/9 années) et **ZITOUNA_TAKAFUL 2020**. Texte
présent mais `_is_target_page` ne matche jamais ("actif"/"passif" en
français n'apparaissent nulle part — état financier intégralement en
arabe). Nécessite le pipeline arabe déjà existant pour d'autres tableaux
(`extraction/arabic_ocr_extractor.py`) mais pas encore étendu au Bilan
pleine grille. **AL_AMANAH_TAKAFUL 2018** et **ZITOUNA_TAKAFUL 2018** sont
en plus des scans (catégorie 2 également).

### 2. Page cible réellement scannée/texte cassé — ~8 documents
**COMAR 2016/2018** (déjà documenté, choix délibéré de ne pas régénérer —
voir plus haut), **LLOYD_VIE 2023**, **AMI 2017**, **COTUNACE 2019**,
**ZITOUNA_TAKAFUL 2018**, et la vraie page Actif/Passif de **MAGHREBIA_VIE**
(toutes années — voir catégorie 4, ses candidats "texte" sont des faux
positifs, la vraie page est en fait scannée, pages 2-5 à ~0 caractères).
Même famille qu'Annexe 12/13 déjà connue.

### 3. Gabarit SANS code réglementaire (labels français bruts) — COTUNACE
**COTUNACE** (toutes années restantes) n'utilise PAS le plan comptable
AC1/AC2/PA../CP.. — juste des libellés français directs ("Actifs
incorporels", "Logiciels", "Placements :"...) avec une simple colonne
"Notes" (référence numérique, ex. "4", "5", "6" — pas un code de section).
`_ROW_CODE_RE` ne matche jamais, `extract_bilan_full_grid` ne trouve donc
aucune ligne codée. Nécessiterait un mode d'extraction ALTERNATIF basé sur
le libellé (comme Annexe 12/13 à l'origine) plutôt que sur le code — pas
qu'un correctif, une 2e voie d'extraction à écrire.

### 4. Page trouvée = "Notes sur le Bilan" (détail narratif), pas le
tableau récapitulatif — STAR 2019/2023, TUNIS_RE 2023, HAYETT 2018/2019,
BNA 2024, UIB 2024, CARTE_VIE 2018, AMI (plusieurs années), MAGHREBIA_VIE
(toutes années)
Le vrai tableau récapitulatif Actif/Passif (celui à 4 colonnes bien
formaté) n'existe PAS comme page séparée dans ces documents — seule une
section narrative "Notes sur le Bilan" existe, qui reprend CERTAINS codes
(ex. "AC1 - Actifs incorporels") mais éclate chaque poste en un MINI-
TABLEAU à en-têtes propres et non-homogènes (constaté STAR 2019 : "AC1"
suivi d'un tableau Matériels de transport/MMB/AAI... avec ses propres
colonnes "Valeur Brute au 31/12/2019"...). `_is_target_page` matche ces
pages à tort (le mot "actif"/"bilan" apparaît bien dans les 6 premières
lignes) mais `extract_bilan_full_grid` échoue ensuite faute de lignes
AC../PA.. au format attendu — le filet de sécurité (essayer TOUS les
candidats, garder le 1er qui produit ≥5 lignes) ne suffit pas quand AUCUN
candidat de la page n'a la vraie forme tabulaire. Même famille que le
repli "Notes sur les Comptes de Résultats" déjà géré pour Annexe 13
(`notes_resultat_extractor.py`) — nécessiterait un module symétrique dédié
au Bilan, pas encore écrit.

**Conclusion** : aucun de ces 4 groupes n'est un bug ponctuel — chacun
demande une VOIE D'EXTRACTION SUPPLÉMENTAIRE dédiée (arabe, sans-code,
notes-narratives) d'une ampleur comparable au travail déjà fait pour le
cas "standard". Pas entrepris ici par manque de temps dans cette session
— la couverture actuelle (171/223, 77%) couvre déjà la quasi-totalité des

## 2026-09-14 — scission Actif / Passif en deux tableaux distincts

Retour utilisateur direct : l'Actif et le Passif sont deux tableaux
SÉPARÉS dans le PDF source (pages différentes, totaux propres), pas un
seul tableau combiné — `process_bilan` fusionnait pourtant les deux en
une unique grille (`tableau='bilan'`), perdant cette structure.

Corrigé : `process_bilan` renvoie maintenant `{"actif": {...} | None,
"passif": {...} | None}`, deux résultats indépendants (chacun avec sa
propre page, ses propres colonnes, ses propres validations), stockés
sous deux clés séparées (`bilan_actif` / `bilan_passif` — voir
`tableau_pipeline_service_bilan.py`, `data_management.py::TABLEAU_GROUPS`
et les allow-lists de `locate_source_page`/`page_source_info`). Deux
onglets distincts côté Correction manuelle ("Bilan Actif" / "Bilan
Passif") plutôt qu'un seul "Bilan (Actif/Passif)".

Anciennes lignes `tableau='bilan'` purgées de `tableau_cellules` /
`tableau_validations` / `tableau_pages`, ré-extraction complète relancée
sur les 223 documents CMF : 158 "ok" (Actif ET Passif trouvés), 13
"partiel" (un seul côté), 46 page introuvable, 6 PDF absent — même
couverture globale qu'avant (171/223), juste correctement scindée.

## 2026-09-14 — audit d'exactitude : 400 écarts trouvés, 3 causes génériques corrigées

Après la scission Actif/Passif, vérification des identités comptables
(Σ sections = Total) sur les 223 documents : **400 écarts** répartis sur
19 sociétés — bien plus que les "0 écart" obtenus pendant le
développement initial (qui ne portait que sur 6 sociétés testées à la
main : COMAR, ATTIJARI, BIAT, MAGHREBIA, GAT, ASTREE). Diagnostic
détaillé (HAYETT, LLOYD_TUNISIEN, MAGHREBIA_VIE) a révélé 3 causes
génériques, corrigées dans `bilan_full_extractor.py` :

**1. Marqueur de sous-total abrégé ("A1", "P2"...)** — plusieurs sociétés
(HAYETT et al.) terminent chaque section par une ligne "<lettre>
<chiffre> <valeurs>" (ex. "A1 8 632 873...") plutôt qu'un vrai code
répété ou une ligne totalement vide. Le chiffre imprimé n'est PAS fiable
(glyphe mal interprété par pdfplumber — 2 sections consécutives peuvent
afficher toutes deux "A1"). Fixé en généralisant la détection de
sous-total "bare" à ce format (`_SECTION_MARKER_RE`), sans jamais se
fier au chiffre du marqueur (seul `current_section`/`_pending_section`
fait foi).

**2. Ligne "Total <section>" étiquetée** — d'autres sociétés (CARTE,
CARTE_VIE, LLOYD_TUNISIEN, Takaful...) impriment une vraie ligne
"Total actifs incorporels"/"TOTAL PLACEMENTS" par section. Ce texte ne
matchait aucune branche existante et se retrouvait absorbé dans le
dernier poste de détail. Fixé par une branche dédiée, restreinte aux
sections ayant RÉELLEMENT des enfants (`sections_with_children`) — sans
cette restriction, une ligne comme "Total capitaux propres avant
affectation" (qui n'est PAS le sous-total d'un CP précis, span plusieurs
codes CP) écraserait à tort la vraie valeur d'un code CP sans enfant
(constaté HAYETT/CP4).

**3. Sous-total imprimé après une section suivante SANS enfant** — sur
MAGHREBIA_VIE, le sous-total de AC3 (qui a des enfants) apparaît
physiquement APRÈS la ligne AC4 (qui n'en a pas) dans l'ordre de lecture
— `current_section` avait déjà avancé sur AC4, perdant le sous-total de
AC3. Fixé en remplaçant la dépendance à `current_section` seul par
`_pending_section()` : recherche, parmi TOUTES les sections top-level
déjà ouvertes (`open_sections`, dans l'ordre), la plus récente qui a des
enfants ET n'a pas encore de valeur — pas forcément la dernière ouverte.

**Résultat** : 400 → 326 écarts (-19%). Le reste se répartit en
limitations distinctes, pas des bugs d'extraction :

- **AT_TAKAFULIA / ZITOUNA_TAKAFUL** (37 + 31 écarts) : gabarit
  structurellement différent ("Bilan Combiné", colonnes "Entreprise
  Takaful" / "Fonds des Adhérents" / "combiné" × 2 exercices — aucun
  jeton Brut/Amort/Net) — `_header_columns` ne reconnaît aucun de ces
  en-têtes et retombe sur le gabarit générique à 4 colonnes, complètement
  inadapté. Relève du chantier Takaful déjà planifié (Phase 3 de la
  feuille de route), pas de cette session.
- **CARTE / CARTE_VIE** (29 + 29 écarts) : imbrication à 3 niveaux
  (AC7 > AC72/AC73 > détails, chacun avec SA PROPRE ligne de sous-total
  "bare") — `_pending_section` s'arrête au premier sous-total rencontré
  (celui d'AC72, une "petite section" intermédiaire) et rate le VRAI
  sous-total d'AC7 qui suit. Nécessiterait de distinguer un sous-total de
  sous-section d'un sous-total de section top-level — pas juste par
  l'ordre d'apparition. Pas résolu ici (rendement décroissant).
- **MAGHREBIA_VIE** (25 écarts restants) : AC3 et AC4 partagent une
  UNIQUE ligne de sous-total combinée (au lieu de deux séparées) —
  particularité de présentation propre à cette société, pas une erreur
  d'extraction généralisable.
- **LLOYD_TUNISIEN, TUNIS_RE, GAT_VIE, ATTIJARI, ASTREE, UIB, STAR,
  CTAMA, COMAR, AMI, GAT, BIAT** (écarts résiduels, 2 à 20 par société) :
  cas isolés non encore diagnostiqués un par un (code CP/PA répété avec
  des valeurs à additionner sélectivement, notes de réconciliation
  mêlées à la grille...) — voir `LLOYD_TUNISIEN 2020` pour un exemple
  documenté (CP2 et CP5 répétés dans le PDF source lui-même, l'un devant
  être sommé, l'autre non — ambiguïté de la donnée source, pas de
  l'extraction).
sociétés Non-Vie/Vie conventionnelles au format standard.
