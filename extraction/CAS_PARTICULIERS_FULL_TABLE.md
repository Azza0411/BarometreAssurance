# Cas particuliers — extraction "grille complète" (extraction/full_table_extractor.py)

## 2026-09-10 — 5ᵉ catégorie de défaut : signe négatif perdu (TUNIS_RE)

Trouvé en vérifiant TUNIS_RE 2020 valeur par valeur contre le PDF (audit
demandé par l'utilisatrice sur un export Excel réel, pas seulement les
noms). **Le plus dangereux des défauts trouvés jusqu'ici** : la valeur
extraite est un nombre plausible, juste du mauvais signe — rien ne le
trahit sans recalculer une identité comptable.

Deux variantes du même défaut source, sur la même page :
1. **Signe détaché dans une cellule camelot séparée** : "Variation des
   PPNA" colonne "Vie" — camelot renvoie `"-"` seul dans une colonne et
   `"1 954 323"` dans la colonne suivante, au lieu de fusionner les deux
   comme il le fait pour les autres colonnes de la même ligne. Fix :
   détection par COLONNE (jamais par cellule isolée, pour ne pas confondre
   avec un vrai "néant") — une colonne dont TOUTES les valeurs sur la plage
   de données sont soit vides soit exactement "-" est une colonne
   "fantôme" porte-signe, fusionnée dans la colonne suivante.
2. **Signe détaché par un retour à la ligne DANS la même cellule** :
   `"-    \n71 142 408"` — `_CELL_NUMERIC_RE` exigeait le chiffre
   immédiatement après le signe (`-?\d`), sans espace/saut de ligne
   toléré entre les deux ; ratait donc silencieusement la cellule entière
   (`_looks_numeric_cell` renvoyait `False`) plutôt que juste le signe.
   Fix : `\s*` ajouté entre le signe optionnel et le premier chiffre.

**Résultat vérifié** : TUNIS_RE 2020 "Solde de souscription" — les 4
colonnes qui manquaient entièrement (Incendie, Total non marines, Total,
Total général) sont réapparues avec le bon signe, correspondant exactement
au PDF. Sweep de régression sur STAR/BIAT/GAT/CARTE/COMAR/CTAMA : 0 écart,
0 colonne non étiquetée, aucun changement — ces deux fixes n'affectent que
les documents qui avaient réellement ce défaut de rendu.

**Note méthodologique découverte au passage** : plusieurs sociétés (LLOYD_
TUNISIEN, TUNIS_RE) présentent "Charges de prestations" en valeur NON
signée (positive) dans leur PDF, alors que `VALIDATION_RULES` (`annexe13_
pipeline.py`) suppose que toutes les charges sont déjà négatives (simple
somme). Ce n'est PAS un bug d'extraction — les valeurs extraites
correspondent exactement au PDF — mais ça fait remonter des "écarts" de
validation qui sont en réalité des faux positifs de l'outil de diagnostic,
pas de vraies erreurs de données. Piste pour plus tard : détecter la
convention de signe par document (ex. si "Charges de prestations" a plus
de valeurs positives que négatives sur l'ensemble du tableau, soustraire
au lieu d'additionner dans `validate_table`) plutôt que de supposer une
convention unique pour toutes les sociétés.

## 2026-09-09 — 4ᵉ catégorie de défaut : titre "lettres espacées" invisible à la détection de page

Trouvé en revérifiant l'année 2020 sur demande utilisateur. **CARTE 2020**
donnait 4 colonnes "(colonne N)" toutes non étiquetées — en apparence le
même symptôme que GAT 2023 (bandeau tronqué), mais la cause est en fait
différente et plus fondamentale : `page.extract_text()` rend le TITRE de
page lui-même avec une lettre par mot séparée d'un espace ("E t a t d e r é
s u l t a t t e c h n i q u e..." au lieu de "Etat de résultat
technique...") — même artefact déjà documenté pour ASTREE, mais jamais
corrigé au niveau de la DÉTECTION DE PAGE elle-même. Conséquence : ni
`_is_target_page` ni `relaxed_is_annexe13_page` ne reconnaissent le titre
(le motif regex ne peut pas matcher un texte avec un espace entre chaque
lettre) → la page n'apparaît même pas comme candidate → le pipeline retombe
sur le repli "Notes" (`notes_resultat_extractor.py`, qui détecte la page
autrement, par les codes internes PRNV/CHNV) dont la reconstruction de
colonnes est moins robuste sur ce gabarit précis → colonnes non étiquetées.

**Fix général** : `_reconstructed_page_head_text()` (nouveau, `extraction/
full_table_extractor.py`) reconstruit le texte des premières lignes de page
à partir de `page.extract_words()` + regroupement par ligne (`_cluster_lines`,
déjà utilisé ailleurs dans le projet) puis par écart horizontal entre mots
consécutifs — mesuré empiriquement sur CARTE : ~0-0.3pt entre lettres d'un
même mot rendu espacé, ~3pt entre deux mots réels. Un texte non affecté par
le défaut traverse cette reconstruction inchangé (le seuil n'est jamais
franchi entre deux vrais mots). Utilisé par `relaxed_is_annexe13_page` à la
place de `page.extract_text()` brut.

**Bonus, même détour** : `_COLUMN_YEAR_SUFFIX_RE` (`annexe13_pipeline.py`)
ne retirait que la date en suffixe ("brutes au 31/12/2020" → "brutes au",
qui ne matche aucun alias) — élargi pour retirer aussi le "au" qui précède
souvent la date dans ce gabarit ("X au DATE" = "X à la date de...").

**Résultat vérifié** : CARTE 2020 passe de 4/4 colonnes non étiquetées à
0/4 ("Opérations brutes", "Cessions et/ou rétrocessions", "Opérations
nettes" ×2) — colonnes ET libellé de page désormais corrects. Sweep 10 ans
en cours pour confirmer l'absence de régression sur l'ensemble du
portefeuille.

**Non résolu, cas différent identifié dans la foulée** : ASTREE 2020 garde
6/17 colonnes non étiquetées même après ce fix — pas un problème de titre
de page (la page EST bien trouvée) mais un désalignement/chevauchement des
colonnes elles-mêmes au niveau de la reconstruction camelot sur ce gabarit
précis (ex. "risques agricoles autr" — fragment mêlant 2 libellés de
colonnes voisines). AMI 2020 reste gravement corrompu au niveau du texte
source lui-même (libellés de ligne avec des chiffres collés dedans, ex.
"primes embes -235s701") — relève de la même famille que les limites déjà
documentées pour AMI (qualité de scan/OCR à la source), pas d'un problème
de dictionnaire. BH reste en échec total sur cette page (gabarit non couvert
par les voies actuelles). Ni l'un ni l'autre ne sont corrigés ici.

## 2026-09-09 — voie OCR pour les documents scannés / à couche texte cassée (`extraction/scanned_table_extractor.py`)

Suite à l'entrée « audit de QUALITÉ » ci-dessous, qui isolait **COTUNACE
(7/11 échecs) et AMI (5/9)** comme un problème de *qualité du document
source* (scan intégral, pas un bloc de pages scannées isolé comme
STAR 2025 / ASTREE 2023). Deux corrections :

### 1. `_clean_cell_value` — format de nombre américain (`13,531,056.575`)

Bug d'extraction réel, **général**, corrigé. `extract_full_table_camelot`
convertissait toute cellule numérique en float par un `.replace(",", ".")`
brut, qui casse le format « virgule = séparateur de milliers, point =
décimale » (`13,531,056.575` → `13.531.056.575`, rejeté par `float` → la
grille entière ressortait vide). Le choix virgule/point est désormais
délégué à `bilan_kpi_extractor._parse_number` (déjà utilisé, validé, par
l'extraction 7-KPI sur les mêmes documents). **COTUNACE 2021 : ÉCHEC → OK**
(page native propre, seul le parsing bloquait ; 26 lignes, colonne
« Crédit-Caution »). Aucune régression sur les documents déjà OK (mêmes
valeurs sur les formats français).

### 2. Nouveau module `extraction/scanned_table_extractor.py` (voie OCR, dernier recours)

Branché dans `locate_and_extract_full_table` **après** la voie camelot ET
le repli « Notes », et seulement si `document_needs_ocr()` confirme qu'une
page de la zone a une couche texte inutilisable (peu de `chars`, `(cid:N)`
en masse, ou texte présent mais illisible). Filtré par le **même**
`_sanity_ok` que les autres voies → régression structurellement impossible
sur les documents déjà OK (voie jamais atteinte). Méthode : rendu image
(PyMuPDF) → retrait du quadrillage (morphologie OpenCV, indispensable pour
les tableaux encadrés type AMI) → `image_to_data` (fra, `--psm 6`) →
lignes = groupage natif Tesseract, **colonnes = position X** des cellules
numériques (même principe que `full_table_extractor`) → contrat de sortie
identique. Localisation de la page par score de titre flou (`_title_score`,
tolérant au bruit), avec rejet franc d'une page « Annexe N°X, X ≠ 13 »
(piège AMI : l'« Annexe 3 — État de résultat technique … Non Vie » agrégée
supplantait sinon la vraie page Annexe 13 par branche). Sociétés
mono-branche à colonne imprimée deux fois (COTUNACE) : les deux lectures
sont fusionnées en gardant la plus complète cellule par cellule
(`_reconcile_doubled_columns`).

**Résultat par année (audit `scripts/audit_full_table_extraction.py`
`--code COTUNACE`/`--code AMI`, 11/9 ans) :**

| Société | Avant | Après | Détail |
|---|---|---|---|
| **AMI** | 3/8 OK | **8/9 OK** | **2016, 2017** : recouvrées, scans propres, grille 7 branches (Incendie/Transport/Risq.Divers/Risq.Spx/Automobile/Groupe/Total) fidèle — 2-3 cellules signalées `ecart` par les identités comptables (erreurs de groupement OCR isolées : `742` pour `742 000`, `7233142` pour `233 142`). **2020, 2023** : vraie page Annexe 13 trouvée (p47/p55) mais scan très dégradé → grille partielle, ~moitié des cellules exploitables, le reste en `ecart`. **2019** : reste ÉCHEC — scan trop dégradé, aucune grille fiable. **2015** inchangé (déjà OK avant via camelot sur la page de réconciliation p4). |
| **COTUNACE** | 4/10 OK | **6/11 OK** | **2019** : recouvrée par OCR, scan propre, 26 lignes, colonne « Crédit-Caution ». Profil de validation **identique** aux années natives 2021/2024 (mêmes 4-5 `ecart` sur `primes_acquises`/`solde_souscription`/`solde_financier`/`resultat_technique`) → l'extraction OCR est aussi fidèle que l'extraction native ; les `ecart` viennent d'une convention COTUNACE (charges imprimées en magnitude positive, sans signe — les identités signées du pipeline ne tiennent pas), **pas de l'OCR**. **2021** : recouvrée par le fix nº1 (format de nombre). |

**Années NON recouvrées, honnêtement (limite du document source, hors périmètre d'un correctif d'extraction latin) :**

- **COTUNACE 2015, 2016, 2017** : états financiers **en arabe** (police
  embarquée cassée en 2015/2016 : `page.extract_text()` = `(cid:N)` ; scan
  en 2017). La page « Résultat technique par catégorie NON-VIE » latine
  n'existe pas ces années-là — l'OCR latin ne peut rien en tirer. Piste :
  une voie OCR arabe (le projet a `extraction/arabic_ocr_extractor.py`,
  câblé pour les KPI Takaful, pas pour la grille par branche).
- **COTUNACE 2022** : couche texte présente mais **corrompue à la source**
  par un mauvais OCR (`Pt.imes acaui8es`, `R6sultat tochnlauo` — déjà
  documenté `api/services/quality.py::PROBLEMATIC_CODES["COTUNACE"]`). Le
  rendu image + ré-OCR passe le titre mais la reconstruction de colonnes
  reste trop bruitée pour franchir le contrôle de vraisemblance.
- **COTUNACE 2023** : scan lisible à l'œil mais filets de tableau épais +
  artefacts de reliure ; le retrait de quadrillage mange du contenu,
  l'OCR ne produit pas de grille plausible. Non recouvrée.
- **AMI 2019** : scan de l'Annexe 13 (p59) trop dégradé — libellés et
  chiffres illisibles même après prétraitement.

**Généralisation** : la voie OCR n'est PAS spécifique à COTUNACE/AMI. Le
même `document_needs_ocr` + `ocr_locate_and_extract` récupère aussi, au
passage, des cas d'autres sociétés que le sweep complet remonte —
**STAR 2023, CARTE 2020, COMAR 2018, LLOYD_TUNISIEN 2018**. Tout document
futur présentant ce motif (couche texte inexploitable sur la zone
Annexe 13) en bénéficiera sans code dédié. Cas volontairement laissé à la
tâche de fond « OCR fallback for scanned Annexe 13 pages » (bloc scanné
isolé, filigrane « Projet ») : **ASTREE 2023** — ses annexes scannées sont
titrées « Annexe 11 » à « Annexe 15 », que `_title_score` écarte
(règle « Annexe N°X, X ≠ 13 » qui protège du piège page-4 d'AMI).

**Sweep complet 10 ans (`scripts/audit_full_table_extraction.py --years 10
--last-year 2025`, sans `--code`)** : **95/114 OK (83 %) avant → 105/114 OK
(92 %) après**, **0 régression** — le décompte OK de CHAQUE société est ≥ à
celui d'avant (la voie OCR n'est jamais atteinte quand la voie camelot
réussit déjà ; elle ne peut qu'ajouter des documents, jamais en retirer).
Gains : AMI 3→7, COTUNACE 4→6, STAR 9→10, CARTE 9→10, COMAR 8→9,
LLOYD_TUNISIEN 8→9. Runtime ~26 min (l'OCR n'est tenté que sur les
documents déjà en échec par les autres voies).

## 2026-09-09 — 3ᵉ catégorie de défaut : en-tête de colonnes tronqué par camelot (bandeau coloré)

Trouvé en vérifiant GAT 2023 sur demande utilisateur (après STAR 2023/BIAT
2023). **Différent des cas "page scannée" (STAR/ASTREE)** : la page existe
bien en texte natif, mais **9 des 16 colonnes de branche ressortent
non-étiquetées** (`(colonne N)`) — grille numériquement complète mais
branches non identifiables. (NB : les 2 écarts d'identité comptable de GAT
2023, initialement soupçonnés d'être liés à ce défaut, se sont révélés
indépendants — voir « Reste non résolu » plus bas.)

**Cause identifiée précisément** : sur GAT 2023, l'en-tête de colonnes est
rendu dans un **bandeau violet coloré**, replié sur 2-3 sous-lignes visuelles
(ex. "Automobile" tient sur 1 ligne, "Responsabilité civile" sur 2,
"Autres dommages aux biens" sur 3). Vérifié directement sur l'objet
`camelot.Table` : **la toute première sous-ligne du bandeau (celle qui
porte "Automobile", "Transport", "Incendie"... et le début des libellés
composés) n'est même PAS incluse dans le tableau détecté par camelot** —
`tables.n == 1` (une seule table trouvée, pas de 2ᵉ table candidate à
récupérer), et son `df` (24, 17) démarre directement à la 2ᵉ sous-ligne du
bandeau ("civile", "agricole", "corporels"...). Ce n'est donc pas un
problème de FENÊTRE de capture côté `full_table_extractor.py`
(`header_start:first_data_idx`) — le mot n'existe nulle part dans les
données que camelot renvoie pour cette page ; seul `pdfplumber` (accès mot
par mot indépendant de la détection de tableau) peut encore le voir.

**Prévalence réelle mesurée** (relevé sur les 84 documents déjà classés
"grille complète" par l'audit de qualité précédent — donc un souci
INVISIBLE à ce premier audit, qui ne comptait que le NOMBRE de colonnes,
jamais si elles étaient nommées) :

- **25 / 84 (30 %)** ont au moins 1 colonne `(colonne N)` non étiquetée.
- **2 cas extrêmes à 100 % non étiqueté** : ASTREE 2019 (17/17) et ASTREE
  2020 (17/17) — la grille est numériquement complète mais AUCUNE branche
  n'est identifiable, résultat inutilisable tel quel malgré un statut
  "réussi".
- Sociétés touchées à des degrés divers : ASTREE (le plus touché, 7
  exercices), MAGHREBIA (3), GAT, CARTE, COMAR, BH, BIAT, TUNIS_RE (1-2
  chacune).

**Correctif implémenté (2026-09-09)** — `extraction/full_table_extractor.py` :

1. `_find_table_camelot` renvoie désormais l'objet `camelot.core.Table`
   entier (plus seulement `t.df`) : ses `.cols` (bornes X natives par
   colonne) et `.rows` (bornes Y natives) étaient jusque-là jetés.
2. Nouvelle fonction `_recover_truncated_column_headers()` : ouvre la même
   page avec `pdfplumber`, prend les mots dont le CENTRE vertical est dans
   une bande étroite (`_HEADER_RECOVERY_MARGIN = 36 pt`) juste au-dessus de
   la 1re ligne captée par camelot (`table.rows[0][0]`), les rattache à la
   colonne de valeur par recoupement des bornes X (`table.cols`), et
   renvoie `{index_colonne_df: texte}`. Le texte récupéré est PRÉFIXÉ aux
   fragments d'en-tête que camelot a bien captés (jamais en remplacement,
   jamais de token dupliqué).
   - **Repère de coordonnées** (vérifié empiriquement sur GAT 2023, un mot
     connu : `Automobile` à `pdfplumber top=145.7` ↔ `camelot y≈446`) :
     `y_camelot = page.height − pdfplumber_top` (pdfplumber = origine
     haut-gauche `top` vers le bas ; camelot = PDF natif, origine
     bas-gauche, y vers le haut).
3. **Garde-fous pour ne jamais dégrader un document déjà correct** :
   - **taux de capture camelot** : on ne récupère QUE si camelot a lui-même
     étiqueté < 50 % des colonnes de valeur (`_HEADER_RECOVERY_MAX_CAPTURED`).
     Écarte d'office les ~59 documents corrects, les gabarits à
     sur-découpage de colonnes (CARTE 2021, COMAR 2024, TUNIS_RE…) et les
     fusions de colonnes (BIAT 2019, BH 2024) — tous inchangés.
   - **filtre de contenu** : un token portant un chiffre, ou dont un
     sous-mot (coupé sur tiret/apostrophe) est du vocabulaire de titre
     (`annexe`, `resultat`, `technique`, `jusqu`, `d'assurance`,
     `Non-Vie`…) est rejeté — le titre de page, plus haut, ne fuit pas dans
     les libellés même collé au bandeau.
   - **filtre de plausibilité** (`_recovered_label_ok`) : on ne garde qu'un
     libellé qui est une abréviation courte ("a.t.", "r.c"), qui se
     rattache à une branche connue (`normalize_column_label`), ou qui est
     1 mot plein (5-12 lettres) / ≤ 3 mots de ≥ 3 lettres. Un texte long,
     morcelé ou en bribes de 1-2 lettres (glyphes espacés d'ASTREE) est
     rejeté au profit d'un placeholder propre.

**Résultats mesurés** — sweep sur la base `origin/ThirdVersion` juste après
la voie OCR (`scripts/audit_full_table_extraction.py --years 10
--last-year 2025` pour l'OK/ÉCHEC ; comptage des `(colonne N)` parmi les
grilles ≥ 5 colonnes pour la prévalence) :

| Métrique | Avant (base seule) | Après (base + ce correctif) |
|---|---|---|
| Sweep OK / ÉCHEC (114 docs testés) | 105 OK / 9 ÉCHEC | **105 OK / 9 ÉCHEC** (0 régression : 0 cellule de statut changée, 0 `n_colonnes` changé) |
| Documents « grille ≥ 5 col » avec ≥ 1 `(colonne N)` | 25 / 80 | **21 / 80** |
| Colonnes `(colonne N)` au total (toutes grilles ≥ 5 col) | 121 | **60** (−50 %) |

**Cas du défaut « bandeau tronqué » spécifiquement :**

| Document | Avant | Après |
|---|---|---|
| GAT 2023 p35 | 9 / 16 non étiquetées | **0 / 16** — les 16 branches correctes (Automobile … Montant) |
| MAGHREBIA 2022 / 2023 / 2025 | 10 / 11 chacun | **0 / 11** chacun |
| ASTREE 2019 p39 | 17 / 17 | **6 / 17** — 11 branches récupérées (Auto, Transport, Aviation, Incendie, Maladie, Invalidité, Individuelle, Total, Acceptations, Total 2, +1) |
| ASTREE 2020 p37 | 17 / 17 | **6 / 17** |

**Reste non résolu, honnêtement :**

- **ASTREE 2019 / 2020, ~6 colonnes du milieu** (Responsabilité
  Décennale/Civile, Risques Agricoles, Autres Dommages, Assistance A.E.A,
  Assurance Crédit) : le texte source de ces colonnes est rendu en glyphes
  individuellement espacés/entremêlés ("literesp biliterisques il",
  "ass ta nce") — même famille de corruption que celle déjà documentée
  pour ASTREE (approche pdfplumber d'origine). Ni camelot ni le repérage
  mot-à-mot ne peuvent en tirer un libellé fiable ; le filtre de
  plausibilité les laisse donc en placeholder plutôt que d'injecter du
  bruit. 2-3 colonnes ressortent avec un libellé approximatif mais qui se
  normalise correctement en aval ("re incendie" → Incendie,
  "risques agricoles autr" → Risques agricoles).
- **ASTREE 2021 / 2024 / 2025, GAT 2016/2017/2024/2025, CARTE, COMAR,
  TUNIS_RE, BH 2024, BIAT 2019** (les 21 documents résiduels) : ce ne sont
  PAS des bandeaux tronqués — camelot y étiquette > 50 % des colonnes,
  mais **sur-découpe** une colonne (crée une colonne vide `(colonne N)`
  sans donnée ni en-tête, ex. le `(colonne 16)` de GAT entre "autres" et
  "montant") ou **fusionne** deux colonnes voisines ("incendie
  construction", "transport maladie"). Défaut distinct, non traité par ce
  correctif (le garde-fou « taux de capture » l'exclut volontairement pour
  ne pas risquer d'injecter par-dessus des libellés déjà corrects).
- **GAT 2023 — les 2 écarts d'identité comptable NE passent PAS à 0.**
  Vérifié en profondeur : ils portent sur la colonne **Total** (pas sur
  une branche) et étaient **identiques avant le correctif** (sur
  `(colonne 16)` à l'époque). Les valeurs extraites correspondent
  caractère pour caractère au texte du PDF : GAT imprime lui-même
  `Charges d'acquisition et de gestion nettes` Total = (60 801 200) alors
  que ses composantes (`Frais d'acquisition` (47 868 499) +
  `Autres charges de gestion nettes` (12 688 407)) somment à (60 556 906),
  avec un ±244 295 miroir sur `Solde Financier`. C'est une **incohérence
  réelle de la source GAT** dans sa colonne Total, pas un défaut
  d'extraction ni d'attribution de branche (l'attribution de branche, elle,
  est maintenant entièrement correcte). Fabriquer une autre valeur pour
  satisfaire l'identité serait faux.
- **MAGHREBIA 2022 / 2023 / 2025 — apparition d'écarts après le correctif.**
  Avant, ces documents n'avaient qu'1 colonne étiquetée donc quasiment
  tout tombait en `donnees_manquantes` ; les 11 colonnes désormais
  nommées, la validation les couvre et révèle un décalage de l'identité
  `charges_acquisition_gestion` **présent aussi sur MAGHREBIA 2024**
  (année « correcte », non touchée par ce correctif) — c'est donc une
  particularité de présentation comptable propre à MAGHREBIA, pas une
  régression. À noter aussi : l'alias `"r.s"` → *Responsabilité civile*
  dans `annexe13_pipeline._COLUMN_ALIASES` est erroné pour MAGHREBIA (R.S =
  *Risques spéciaux*) et fusionne `r.s`/`r.c` en une colonne dédupliquée —
  bug d'alias préexistant, hors périmètre de ce correctif, à corriger
  séparément.

## 2026-09-09 — audit de QUALITÉ (pas seulement de couverture), toutes sociétés/années

Suite à STAR 2025/ASTREE 2023 (audit binaire OK/ÉCHEC insuffisant — voir
entrée du dessous), nouvel audit qui distingue 3 issues au lieu de 2 :
**grille complète par branche** (≥5 colonnes, le résultat idéal) vs
**repli dégradé** (résultat valide mais peu de colonnes — gabarit
réconciliation/Notes) vs **échec**. Signale aussi, pour tout document qui
N'est PAS en grille complète, si une page proche (≤60 premières) a un texte
quasi vide ET une image — signal "scan potentiellement manqué".

**Résultat (124 documents, 14 sociétés conventionnelles) :**

| Statut | N | % |
|---|---|---|
| Grille complète par branche | 84 | 68 % |
| Repli dégradé (valide, moins riche) | 20 | 16 % |
| Échec | 20 | 16 % |

**Sociétés à 100% grille complète : BIAT, GAT, MAGHREBIA, TUNIS_RE.**

**Nuance importante sur les 20 "dégradés"** : 4 sont en réalité de FAUX
positifs de ce script — COTUNACE (2018/2020/2024/2025), mono-branche
"Crédit-Caution" (voir entrée dédiée plus bas), produit à raison une grille
à 1 seule colonne que le seuil `≥5 colonnes` classe à tort "dégradé". Une
fois retirés : **16 dégradations réelles**, concentrées sur BH (5 années sur
7 utilisent le gabarit réconciliation, pas un défaut — semble être le format
que BH publie réellement la plupart des années) et CTAMA (2/2, même
gabarit). Aucun signal "scan manqué" sur ces cas — ce n'est pas la même
famille de problème que STAR/ASTREE.

> **MISE À JOUR 2026-09-09 (voir entrée en tête de fichier)** : la voie OCR
> `extraction/scanned_table_extractor.py` a été construite. Résultat :
> **AMI 3→7 OK** (2016/2017 grille 7 branches fidèle ; 2020/2023 partielles ;
> 2019 reste échec), **COTUNACE 4→6 OK** (2019 par OCR, 2021 par le fix du
> format de nombre). Restent non recouvrées : COTUNACE 2015/2016/2017
> (états financiers en arabe), COTUNACE 2022 (couche texte corrompue à la
> source), COTUNACE 2023 & AMI 2019 (scan trop dégradé). Sweep complet
> 95→105/114.

**Les 20 échecs sont concentrés sur 2 sociétés**, pas répartis uniformément :
**COTUNACE (7/11) et AMI (5/9)**. Ce ne sont PAS des échecs "page introuvable"
isolés comme STAR 2025 — le signal "scan manqué" touche pour ces deux
sociétés un très grand nombre de pages du document entier (jusqu'à 50-60
pages sur COTUNACE 2017/2019/2023, 10-50 pages sur AMI) : le document
SOURCE entier semble être un scan de mauvaise qualité (déjà documenté pour
COTUNACE — `api/services/quality.py::PROBLEMATIC_CODES["COTUNACE"]`, "texte
corrompu par un OCR de mauvaise qualité à la source" ; AMI n'avait qu'un
"probablement... pages scannées" non confirmé jusqu'ici). **Différent du cas
STAR/ASTREE** (un bloc de quelques pages scannées au milieu d'un document
par ailleurs natif) — ici c'est potentiellement le document ENTIER,
nécessitant un OCR plus large que le simple repli ciblé en cours de
développement (tâche de fond "OCR fallback for scanned Annexe 13 pages").

**Bilan honnête** : sur les 14 sociétés conventionnelles éligibles, 4 sont
fiables à 100% (grille complète), 8 autres ont un taux de réussite solide
avec quelques années isolées en dégradé/échec, et 2 (COTUNACE, AMI) ont un
problème structurel de qualité de document source qui dépasse le périmètre
d'un correctif d'extraction — nécessiteraient un OCR complet du document,
pas seulement de la page Annexe 13.

## 2026-09-09 — le cas "page scannée" (STAR 2025) N'EST PAS isolé : confirmé sur ASTREE 2023

Vérification demandée par l'utilisatrice sur un 2e exemple (ASTREE 2023,
captures d'écran export vs PDF réel) : même symptôme que STAR 2025, cause
identique confirmée. `ASTREE_2023.pdf` n'a AUCUNE page candidate détectée
titrée "Annexe 13" — seule la page 4 ("Annexe n°3 — Etat de résultat
technique... Non-Vie", gabarit réconciliation 4 colonnes) est trouvée. Les
vraies Annexes 11 à 15 (pages 35-40, juste après l'Annexe 10 page 34) sont
un bloc de **6 pages scannées avec filigrane "Projet"** — `page.chars` entre
13 et 28 par page, texte extractible réduit au seul mot "Projet". Le
pipeline se rabat donc, comme pour STAR 2025, sur la page de réconciliation
— mais ASTREE cumule un 2e défaut propre à ce gabarit précis : les libellés
de ligne reconstruits sont partiellement corrompus, des fragments de valeurs
numériques se retrouvant collés au texte du libellé (ex. "AUTRES CHARGES
TECHNIQUES 523 2 523 7 335" au lieu de "Autres charges techniques") — à
creuser séparément de la cause "page scannée" elle-même, propre à la
reconstruction de lignes de `extract_full_table_camelot` sur ce gabarit à 4
colonnes quand le texte source est lui-même dense/fragmenté.

**Conclusion révisée** : le filigrane "Projet" suggère qu'au moins certains
documents CMF contiennent, pour leurs annexes 11-15, un bloc scanné depuis
une version BROUILLON plutôt que la version finale native — un défaut du
DOCUMENT SOURCE tel que collecté, pas un artefact ponctuel. Le sweep de
couverture actuel (`scripts/audit_full_table_extraction.py`) ne peut PAS
détecter ce cas par construction (il vérifie seulement qu'UNE page candidate
produit un tableau plausible, jamais que c'est la MEILLEURE page du
document) — un audit dédié est nécessaire : pour chaque document marqué
"OK", vérifier si une page de la zone Annexe 11-15 a `page.chars` quasi nul
ET `page.images` non vide alors qu'aucune page candidate valide n'a été
trouvée par ailleurs. Confié à une tâche de fond séparée (voir suggestion
"OCR fallback for scanned Annexe 13 pages") — étendue par cette découverte à
un audit de PRÉVALENCE du phénomène sur l'ensemble du portefeuille, pas
seulement STAR 2025.

**3ᵉ confirmation (même jour, sur demande explicite "vérifie STAR 2023")** :
`STAR_2023.pdf` page 36 — `page.chars=3`, `page.images=2`, texte extractible
= 0 — pile entre l'Annexe 11 (page 35) et l'Annexe 14 (page 37), là où la
vraie grille Non-Vie par branche devrait être. **Corrige un diagnostic
antérieur, faux** : ce cas était attribué (avant la découverte du schéma
"page scannée", et avant la migration camelot) à un "gabarit raccordement à
1 colonne" — voir l'entrée "Nouveau cas identifié, non traité" plus bas,
annotée en conséquence plutôt que supprimée. Aucune régression détectée
par l'audit de couverture précisément parce que ce type de défaut échappe
par construction à un contrôle binaire OK/ÉCHEC (voir §5 de la phase
documentée dans `docs/pfe_phase_documentation.md`).

## 2026-09-09 — deux bugs trouvés sur retour utilisateur ("le tableau STAR 2025 est incomplet")

### 1. STAR 2025 : la vraie page Annexe 13 est un SCAN (pas de couche texte)

Constaté en creusant l'export réel (5 lignes × 4 colonnes livré au lieu des
~25 lignes × 9 colonnes attendues) : `locate_and_extract_full_table` sur
`STAR_2025.pdf` ne trouve QUE 2 pages candidates — page 4 (ancienne page de
réconciliation agrégée, 4 colonnes) et page 48 ("Annexe n°16 : Tableau de
raccordement... Non-Vie", échoue). **La vraie page Annexe 13 par branche
n'apparaît JAMAIS dans les candidats.** Inspection directe : `pdfplumber`
extrait `page.chars` = 3 caractères, `page.extract_text()` = chaîne vide,
mais `page.images` = 1 — la page 45 est un **SCAN inséré tel quel** (aucune
couche de texte), pas un rendu natif. Ni `pdfplumber` (détection de page) ni
`camelot` (reconstruction, repose sur la couche texte) ne peuvent la lire.

Cause probable : contrairement aux autres années, cette page précise du
document 2025 de STAR a été insérée comme image (signature scannée,
correction tardive, export PDF différent pour cette page seule...) — à
vérifier société par société si le même symptôme est isolé ou récurrent.
**Pas corrigible par un correctif d'algorithme** — nécessiterait de l'OCR
(le projet en a déjà pour d'autres cas, ex. `scripts/ocr_repair_validated.py`
mentionné ailleurs) sur cette page précise avant extraction. Le pipeline
actuel se rabat silencieusement sur la page 4 (réconciliation, 4 colonnes)
qui passe le contrôle de vraisemblance — un résultat VALIDE mais NETTEMENT
moins complet que la vraie grille par branche, présenté sans distinction
comme "réussi" dans les statistiques de fiabilité actuelles. Limite connue
de la mesure actuelle : "réussi" veut dire "une page candidate lisible a
produit un tableau plausible", pas "la MEILLEURE page du document a été
utilisée" — les deux se confondent silencieusement dans ce cas précis. Non
corrigé ici (nouveau chantier, hors périmètre de cette session) — piste
naturelle : OCR ciblé quand aucune page candidate en texte natif n'est
trouvée mais qu'une page image existe dans la zone attendue (juste après
l'Annexe 12).

### 2. ATTIJARI (et 3 autres sociétés Vie/Takaful) : données mal-étiquetées stockées en base

En vérifiant pourquoi ATTIJARI apparaissait comme ayant des données Annexe 13
alors qu'elle est répertoriée Vie exclusivement (`ANNEXE13_NON_VIE_
EXCLUSIONS`), découvert que **le référentiel d'exclusion n'était appliqué
qu'au SCRIPT D'AUDIT et à `get_reliability_stats()`, jamais à la pipeline de
stockage réelle** (`api/services/tableau_pipeline_service.py::_cmf_documents`
n'avait aucun filtre) — chaque revalidation continuait donc à (re)tenter
l'extraction pour ATTIJARI/UIB/GAT_VIE/etc. Pour ATTIJARI spécifiquement,
2021-2023 retombent sur la même page de raccordement Vie mal titrée déjà
diagnostiquée (codes internes PRV1/CHV1 = Vie, mais page non qualifiée "Vie"
dans son titre — passe le contrôle de vraisemblance par accident) et
produisaient un résultat "réussi" mais garbage (ex. un unique nom de colonne
de 90 caractères concaténant tout l'en-tête). **Vérifié en base : 6
documents contaminés au total** — ATTIJARI (3), AT_TAKAFULIA (1), GAT_VIE
(1), ZITOUNA_TAKAFUL (1) — supprimés de `tableau_cellules`/
`tableau_validations`. Fix définitif : `_cmf_documents` exclut désormais
`ANNEXE13_NON_VIE_EXCLUSIONS` à la source (jamais retenté), donc plus de
recontamination possible aux prochaines revalidations.

**Nuance restante, non traitée** : l'ANCIEN extracteur 7-KPI
(`annexe13_kpi_extractor.py`, alimente les dashboards, jamais touché dans
cette session par consigne explicite) a le MÊME bug de fond — il tague
aussi à tort des valeurs Vie d'ATTIJARI 2021-2023 sous le libellé brut
"Annexe 13 - Resultat technique Non-Vie" dans `kpi_values` (racine commune :
la page de raccordement d'ATTIJARI ne contient pas le mot "vie" dans ses 4
premières lignes, seul signal utilisé par `_is_target_page`). Cette table
`kpi_values` n'a pas été nettoyée (hors périmètre — sert aux dashboards) ;
un export "tous les tableaux" ou "Annexe 12" pourrait donc encore afficher
ces valeurs contaminées via le repli narrow (`_write_narrow_fallback_block`).
Le nouveau garde-fou `societes_par_tableau` (voir `get_filter_options`) évite
au moins qu'un utilisateur sélectionne ATTIJARI pour un export Annexe 13
depuis l'interface — mais ne corrige pas la donnée source. Piste pour plus
tard, si priorisé : élargir `_is_target_page`/`PAGE_TITLE_RE` (module
partagé narrow) pour détecter les codes internes PRV/CHV en plus du titre de
page, comme fait ici côté grille complète.

## 2026-09-09 (bilan) — couverture Annexe 13 2024, toutes sociétés conventionnelles

Après le fix COTUNACE (ce fichier, entrée du dessous) et le repli "Notes sur
les Comptes de Résultats" pour BNA/AMI (tâche de fond séparée, voir commit
`4bee905`, module `extraction/notes_resultat_extractor.py`), vérifié en base
(`tableau_cellules`) : **plus AUCUNE société "conventionnelle" éligible à
l'Annexe 13 Non-Vie ne manque pour l'exercice 2024.** Les seules sociétés
sans résultat 2024 sont, sans exception, celles structurellement hors
périmètre (`annexe13_pipeline.ANNEXE13_NON_VIE_EXCLUSIONS` : Vie
exclusivement + Takaful) ou sans document 2024 du tout côté collecte (AMI,
qui a cessé de publier sous ce nom après son renommage en BNA — pas un trou
d'extraction). Fiabilité extraction globale (toutes années confondues,
societes eligibles) : 107/124 documents (86,3 %) — voir `get_reliability_
stats()` dans `api/services/data_management.py` pour la mesure à jour.

Petit correctif cosmétique fait dans la foulée : le module de repli "Notes"
nomme sa colonne de cessions "Cessions 2024" (année en suffixe direct, pas
"et/ou rétrocessions...") — alias `"cessions"` ajouté à `_COLUMN_ALIASES`
pour la couvrir aussi.

## 2026-09-09 (suite) — dictionnaire de normalisation LIGNES + COLONNES, toutes sociétés

Déclencheur : retour utilisateur explicite ("préparer une liste de noms de
colonnes et de noms de lignes... qui regroupe tous les noms utilisés sur
toutes les entreprises... et non pas uniquement les noms de STAR").
`CANONICAL_ROWS`/`normalize_row_label` existaient déjà mais avaient été
construits en observant surtout STAR/GAT/BIAT ; aucune normalisation
n'existait pour les COLONNES (branches).

**Méthode** : relevé exhaustif (pas un échantillon) — `locate_and_extract_
full_table` + `normalize_table` rejoués sur les 101 documents extraits avec
succès, TOUTES sociétés conventionnelles Non-Vie confondues, tous exercices
disponibles (2015-2025). Script de relevé conservé dans le scratchpad de
session (non versionné — à reproduire au besoin en rejouant `scripts/
audit_full_table_extraction.py` + `normalize_table` sur son rapport JSON).

**Colonnes (`CANONICAL_COLUMNS`/`normalize_column_label`, nouveau)** :
contrairement aux lignes (vocabulaire comptable réglementaire commun à
toutes les sociétés), les colonnes sont les BRANCHES réellement vendues par
chaque société — un ensemble qui varie légitimement (TUNIS_RE, réassureur,
n'a pas les mêmes colonnes qu'un assureur direct). La normalisation ne
fusionne donc jamais deux branches différentes, seulement les variantes
d'orthographe/abréviation d'une même branche (ex. "AUTO" vs "AUTOMOBILE",
"R DIVERS"/"RISQ. DIVERS" vs "RISQUES DIVERS", "ACCTRAV"/"A.TRAVAIL" vs
"ACCIDENTS DU TRAVAIL"...) — ~30 branches canoniques + dictionnaire d'alias
explicite (une abréviation courte n'a pas assez de lettres communes avec sa
forme longue pour qu'une correspondance floue la retrouve de façon fiable,
contrairement aux lignes). Gère aussi : les libellés numérotés par certaines
sociétés ("1-Auto", "2-Transport" — CARTE), le gabarit "raccordement"
(Brut/Cessions/Net, avec année en suffixe variable retirée avant
comparaison), et les doublons déjà désambiguïsés en amont par
`full_table_extractor.py` (suffixe " (2)" réappliqué après résolution de
l'alias plutôt que de faire échouer la correspondance).

**Lignes (`CANONICAL_ROWS`, complété)** : 4 nouveaux postes réellement
récurrents détectés (pas des artefacts ponctuels — présents sur PLUSIEURS
exercices d'une même société) : "Intérêts servis" (BIAT, 11 occurrences),
"Primes cédées aux réassureurs" (LLOYD_TUNISIEN, 8), "Provisions
mathématiques de rente" et "Prévisions de recours à encaisser" (COMAR).
"Provisions pour égalisation et équilibrage" ajouté en cours de route après
avoir détecté qu'il se faisait FAUSSEMENT rattacher à "Prévisions de recours
à encaisser" par la correspondance floue (score suffisant par accident,
aucun des deux postes n'étant alors assez proche) — corrigé en lui donnant
sa propre entrée canonique plutôt qu'en resserrant le seuil global (qui
aurait pu casser d'autres correspondances légitimes).

**Piège trouvé et corrigé en cours de route (perte de données silencieuse)** :
COMAR distingue plusieurs postes (provisions/prévisions) par EXERCICE sur 2
lignes physiques séparées ("... Année N" / "... Année N-1"), avec des
valeurs par branche RÉELLEMENT DIFFÉRENTES sur chacune. Les fusionner sous
un même libellé canonique (première tentative) faisait perdre silencieusement
la moitié des valeurs — `normalize_table` ne fait qu'un `setdefault` par
colonne en cas de collision de libellé de ligne (comportement préexistant,
volontaire pour ne jamais perdre une valeur en cas de VRAI doublon). Vérifié
concrètement sur COMAR 2020 : "Provisions mathématiques de rente" fusionnée
donnait un total de 13 825 704 (année N seule) au lieu de deux lignes
distinctes 13 825 704 / 13 335 550. Fix : ces postes gardent 2 entrées
canoniques distinctes ("... (exercice N)" / "... (exercice N-1)") — le
marqueur d'exercice est détecté dans le libellé brut et réinjecté après
correspondance plutôt que fusionné (`_YEAR_MARKER_RE` dans
`normalize_row_label`), sans toucher au comportement des postes qui n'ont
jamais ce marqueur (la quasi-totalité des lignes).

**Limitations restantes, non traitées** (documentées pour ne pas les
re-découvrir) :
- CARTE 2024 : plusieurs en-têtes de colonnes fusionnés en une seule chaîne
  par camelot (ex. "7-dommages aux bi8-credit et caution9-assistance") — un
  vrai bug de RECONSTRUCTION de colonnes (limite de la détection de tableau
  par blancs sur cette page précise), pas un problème de vocabulaire ; aucun
  dictionnaire ne peut le corriger, il faudrait revoir la détection de
  colonnes de camelot pour cette page.
- ASTREE : une grappe de libellés de ligne fragmentés autour des rentes/
  provisions d'invalidité ("- Arrérages de rentes à payer 19 644"...) inclut
  parfois un MONTANT à l'intérieur même du libellé (pas juste le texte) —
  suggère une sous-table de détail (notes) qui déborde sur la grille
  principale plutôt qu'un problème de normalisation ; non investigué plus
  avant (déjà présent avant ce chantier).
- TUNIS_RE : vocabulaire de réassurance non couvert par le dictionnaire
  ("Wakala", quelques lignes de change/devises) — spécifique à l'activité de
  réassurance, volontairement laissé non normalisé plutôt que d'étirer le
  dictionnaire pour une seule société.
- Une douzaine de libellés à occurrence UNIQUE, visiblement des fusions de
  plusieurs lignes physiques du PDF en une seule chaîne (ex. AMI 2015, COMAR
  2017) — bug de RECONSTRUCTION de lignes propre à ces pages, même famille
  que le cas CARTE ci-dessus, pas de vocabulaire.

## 2026-09-09 — généralisation Annexe 13 2024 à toutes les sociétés conventionnelles

Déclencheur : retour utilisateur explicite ("assurez-vous que toutes les
assurances conventionnelles soient fonctionnelles pour l'annexe treize pour
l'année deux-mille-vingt-quatre"). Diagnostic société par société des 4
échecs 2024 identifiés (`scripts/audit_full_table_extraction.py --years 1
--last-year 2024`), en repartant du texte brut du PDF (pas seulement du
comportement de l'extracteur) pour chacun :

| Société | Diagnostic 2024 | Traitement |
|---|---|---|
| **COTUNACE** | **Bug d'extraction réel, corrigé.** Deux causes cumulées : (1) le PDF source répète chaque en-tête ET chaque valeur DEUX FOIS côte à côte dans le flux de texte (probable artefact de génération du document — vérifié par dump du texte brut pdfplumber : "Crédit-Caution Crédit-Caution" / "13 301 587,065 13 301 587,065"), ce que camelot restituait donc comme 2 colonnes strictement identiques ; (2) COTUNACE est mono-branche (une seule colonne "Crédit-Caution" au lieu des 4-16 colonnes des gabarits multi-branches) — `MIN_DATA_CELLS=4` (seuil global) ne détectait jamais la première ligne de données sur un tableau aussi étroit. Deux fixes généraux (pas spécifiques à COTUNACE) : seuil de détection adaptatif `effective_min_data_cells = min(MIN_DATA_CELLS, n_cols_total - 1)`, et déduplication de colonnes adjacentes dont l'en-tête ET la totalité des valeurs sont identiques caractère pour caractère (un vrai doublon Brut/Net n'a jamais des valeurs identiques sur TOUTES les lignes — collision improbable). Vérifié : COTUNACE 2024 extrait maintenant 26 lignes, 1 colonne "Crédit-Caution", valeurs correctes. Sweep 10 ans sans régression (95/130 OK, contre 89/130 avant, hors doublons ATTIJARI ci-dessous). |
| **ATTIJARI** | **Pas un bug — société structurellement Vie exclusivement**, mal classée. Objet social confirmé en page 9 du PDF 2024 : "la pratique des opérations d'assurance et de réassurance **sur la vie et la capitalisation**". Le document ne contient AUCUNE annexe Non-Vie (8, 9, 10, 11, 14 présentes — toutes Vie). Les "OK" 2021-2023 obtenus avant ce correctif étaient en réalité des **faux positifs** : la page trouvée était le tableau de raccordement VIE (codes PRV1/CHV1/CHV2), dont la reconstruction produisait un unique libellé de colonne illisible (`"total raccordement ... prv1 1ere colonne ... chv1 1ere colonne..."`), jamais une vraie grille par branche Non-Vie. Ajoutée à `annexe13_pipeline.ANNEXE13_NON_VIE_EXCLUSIONS`. |
| **UIB** | **Pas un bug — société structurellement Vie exclusivement**, mal classée. Objet social confirmé en page 8 du PDF 2024 : "a pour objet toutes opérations d'assurances **sur la vie**...". Ses annexes sont numérotées 8, 9, 12 (Vie), 14, 15 (Vie) — aucune Annexe 13 Non-Vie, à aucune année (0/6 sur tout l'historique disponible). Ajoutée à `annexe13_pipeline.ANNEXE13_NON_VIE_EXCLUSIONS`. |
| **BNA** | **Limitation réelle du document source 2024, non généralisable sans un module dédié.** BNA a bien une vraie Annexe 13 Non-Vie multi-branches (Incendie/Transport/Risques divers/Risques SPX/Automobile/Groupe) — **confirmé en extrayant 2025 avec succès** (26 lignes, 7 colonnes). Mais son document 2024 ne contient PAS cette page : les mêmes données existent, mais éclatées en une dizaine de petits tableaux séparés à l'intérieur d'une section narrative "V - Notes sur les Comptes de Résultats" (ex. "PRNV1- Primes acquises" page 28, "CHV1- Charges de sinistres" page 29, chacun son propre petit tableau Brut/Cessions/Net), jamais assemblés en une grille unique. Rapprocher ces petits tableaux en une seule grille demanderait un module d'extraction dédié à ce gabarit "Notes" (structure radicalement différente d'une page Annexe unique) — hors périmètre d'un correctif ponctuel, noté comme piste future. **Explication probable du contexte** : `config/company_registry.py` indique "BNA Assurances (**ex** : ASSURANCE MUTUELLE EL ITTIHAD - AMI -)" — BNA est la société **AMI renommée/restructurée à partir de 2024** (BNA n'a des documents CMF que depuis 2024 ; AMI, sous son ancien nom, n'en a plus après 2023) — cohérent avec un changement de gabarit de reporting au moment de la bascule. |

**Gaps de COLLECTE (pas d'extraction) identifiés en marge** — AMI n'a pas de
PDF 2024/2025 (dernier exercice disponible : 2023, cohérent avec le
renommage en BNA ci-dessus — probablement plus rien à collecter sous ce nom)
; CTAMA n'a que 2018 et 2020 (aucun PDF 2024 trouvé lors de la dernière
collecte). Ce ne sont pas des échecs d'extraction — le PDF n'existe tout
simplement pas en local. Voir `get_reliability_stats()` dans
`api/services/data_management.py` pour la mesure du taux de collecte réel
(par société, sur sa plage d'exercices connue).

**Référentiel unique des exclusions Non-Vie** : `ANNEXE13_NON_VIE_EXCLUSIONS`
(`extraction/annexe13_pipeline.py`) centralise désormais la liste (sociétés
Vie exclusivement + Takaful), importée à la fois par le script d'audit et
par `get_reliability_stats()` — pour ne plus jamais diverger entre les deux
sur "qui est censé avoir une Annexe 13 Non-Vie".

### 2026-09-09 (suite) — RÉSOLU : chemin de repli « Notes sur les Comptes de Résultats » (`extraction/notes_resultat_extractor.py`)

La « piste future » notée dans la ligne BNA ci-dessus a été implémentée. Le
gabarit « éclaté » n'est PAS propre à BNA 2024 : le sweep complet montre que
**AMI 2021 et AMI 2022** (AMI = ancien nom de BNA, mêmes équipes/même
reporting) utilisent exactement le même format — une section narrative
« V - Notes sur les Comptes de Résultats » où chaque poste Non-Vie a son
propre petit tableau de réconciliation à 4 colonnes (Opérations brutes N /
Cessions / Opérations nettes N / Opérations nettes N-1), précédé de son code
de rubrique (`PRNV1- Primes acquises`, `CHNV1- Charges de sinistres`,
`CHNV4- Frais d'exploitation`, `CHNV5- Autres charges techniques non-vie`…),
le tout intercalé dans de la prose.

**Nouveau module `extraction/notes_resultat_extractor.py`** —
`assemble_non_vie_grid_from_notes(pdf_path)` :
1. localise la section par son titre (`notes sur les comptes de resultats`,
   singulier/pluriel), bornée à la section romaine suivante (`VI - Notes sur…`) ;
2. machine à états sur les lignes clusterisées (pdfplumber, briques de
   `bilan_kpi_extractor`) : suit le dernier code de rubrique vu, n'ouvre un
   petit tableau que sous un préfixe **Non-Vie** (`PRNV` / `CHNV` / `RTNV` —
   les rubriques Vie `PRV`/`CHV`/`RTV` et non-techniques `PRNT`/`CHNT` sont
   ignorées), sur détection de l'en-tête « Opérations … Cessions … » ;
3. découpe chaque ligne de données en 4 cellules par **bord droit (x1)** des
   tokens (montants alignés à droite → x1 stable ; un tiret isolé « - » est
   une cellule « néant » explicite, ce qui lève l'ambiguïté des lignes à 3
   valeurs où la colonne vide peut être Brut *ou* Cessions) ; alignement
   final sur les bords droits de la ligne « Total en DT » du sous-tableau
   (toujours complète) ;
4. renomme la ligne « Total en DT » de chaque sous-tableau par le libellé de
   sa rubrique (`Primes acquises`, `Charges de sinistres`, `Frais
   d'exploitation`…) pour éviter la collision de clés et rendre les totaux
   exploitables ;
5. renvoie le **contrat identique** à `extract_full_table_camelot`
   (`{"colonnes": [...], "lignes": {...}}`), colonnes/lignes normalisées.

**Branchement** : `full_table_extractor.locate_and_extract_full_table` essaie
d'abord la page « Annexe N°13 » unique (voie normale, camelot) ; si et
seulement si elle échoue (`best is None`), il tente ce repli, filtré par le
**même** `_sanity_ok` (≥ 2 postes comptables reconnus). Aucune page unique
valide n'est jamais remplacée par le repli → régression structurellement
impossible sur les documents déjà OK. `process_annexe13` en hérite (il
appelle `locate_and_extract_full_table`).

**Vérification** :
- **BNA 2024** : ECHEC → OK. Page 28, grille 4 colonnes / 12 lignes.
  `process_annexe13` : identité `primes_acquises` (Primes acquises = Primes
  émises + Variation des primes non acquises) validée **sur les 4 colonnes,
  0 écart** ; les autres règles ressortent en `donnees_manquantes` (ce
  gabarit ne publie que 3-4 sous-tableaux, pas tous les postes canoniques —
  inhérent à la source, pas un défaut d'extraction).
- **BNA 2025** : inchangé — garde sa vraie page Annexe 13 multi-branches
  (page 45, 7 colonnes / 26 lignes) ; le repli n'est jamais atteint.
- **AMI 2021, AMI 2022** : ECHEC → OK en ricochet (même gabarit). Totaux
  internes recoupés (Primes acquises = Primes émises + Var. PPNA ; Charges de
  sinistres = Sinistres payés + Var. PSAP + PREC ; Frais d'exploitation =
  Frais d'acq. + Var. frais d'acq. reportés + Frais d'admin. + Commissions
  reçues des réassureurs) — cohérents au dinar près.
- **AMI 2023** : reste ECHEC — pas de section « Notes sur les Comptes de
  Résultats » exploitable dans ce document (structure différente) ; non
  régressé, non traité.
- **Sweep complet `scripts/audit_full_table_extraction.py --years 10
  --last-year 2025`** : **92/114 OK (81%) → 95/114 OK (83%)**. Diff cellule
  par cellule (avant/après) : exactement **3 passages ECHEC→OK (BNA 2024,
  AMI 2021, AMI 2022), 0 régression** (aucun OK→ECHEC), sur toute la
  plateforme.

**Limites connues du repli (documentées, non bloquantes)** :
- Grille **sans ventilation par branche** — le document ne la fournit pas
  cette année-là ; les 4 colonnes sont Brut/Cessions/Net-N/Net-N-1, comme une
  page « raccordement » (déjà couverte par le pipeline 7-KPI via
  `annexe13_kpi_extractor`).
- Postes présentés **uniquement en prose** (pas de petit tableau) non
  capturés : `RTNV- Résultat technique non-vie` (le total « bénéfice de
  18 825 105 DT » est une phrase, en plus coupé par un retour à la ligne),
  et les rubriques dont le document ne donne que le net en prose. Conséquence
  : la ligne « Résultat technique » est absente de la grille → règle
  `resultat_technique` en `donnees_manquantes` (pas en écart).
- `normalize_row_label` (`annexe13_pipeline`) ne rattache pas encore
  « Variation de la PPNA » → « Variation des primes non acquises » ni
  « Sinistres payés »/« PREC » à un poste canonique : ces libellés restent
  bruts dans `non_reconnues` (jamais perdus). Amélioration possible du
  vocabulaire de normalisation — hors périmètre de ce correctif (contrat de
  sortie inchangé, aucun code aval touché).

## 2026-09-09 — migration du moteur d'extraction : pdfplumber → camelot

Suite à un retour utilisateur montrant un script de référence (camelot,
dossier `FS_Market_Intelligence`) dont la sortie STAR était nettement plus
propre : comparaison côte à côte sur GAT (16 colonnes/branche), STAR (page
"Annexe 13" réelle ET page agrégée à libellés repliés), BIAT et ASTREE.
Résultat sans ambiguïté en faveur de camelot :

- **GAT, STAR, BIAT** : grille correctement reconstruite nativement, **0
  écart** sur les 7 identités comptables de validation (`annexe13_pipeline.
  VALIDATION_RULES`), toutes colonnes/branches confondues — alors que
  l'approche pdfplumber nécessitait une pile de correctifs (regroupement de
  centres de colonnes par tolérance `COL_GAP`, marge gauche d'en-tête,
  dédoublement de colonnes, ancre "en dinar"...) pour arriver au même
  résultat.
- **ASTREE** : camelot **résout** le bug de rendu texte à lettres
  individuellement espacées ("s p o n s a b i e c e n n a l e" →
  "Responsabilité" lisible) que l'approche pdfplumber n'avait pas réussi à
  corriger. Quelques colonnes restent sans libellé détecté
  ("(colonne N)") et quelques écarts de validation subsistent sur cette
  société précise — amélioration nette mais pas encore parfaite, non
  creusé plus avant (voir tableau de couverture ci-dessous).

**Le module a été entièrement réécrit autour de camelot** (voir docstring
en tête de fichier) : `extract_full_table_camelot()` remplace l'ancien
`extract_full_table()` (positions X pdfplumber). Toute la couche en aval
(normalisation, validation, stockage, export — `annexe13_pipeline.py`,
`tableau_pipeline_service.py`, `data_management.py`) n'a pas eu besoin de
changer : le contrat de sortie (`{"colonnes": [...], "lignes": {...}}`)
reste identique.

**Couverture brute (sweep 10 ans, `scripts/audit_full_table_extraction.py`)
: 86/130 (66%) contre 89/130 (68%) avec pdfplumber — légère baisse en
apparence, mais pas une vraie régression.** Vérifié cas par cas : les
documents perdus sont soit (a) des pages où l'ancienne heuristique
"réussissait" par accident sur la MAUVAISE page (même symptôme que le bug
BIAT documenté plus bas — un dédoublement de colonnes gonflait
artificiellement le score de vraisemblance sur une page qui n'est pas le
vrai tableau), soit (b) des documents dont la vraie page Annexe 13 n'est,
de toute façon, trouvable par AUCUN moteur (le titre recherché n'existe
tout simplement pas dans le document cette année-là — ex. ASTREE 2022/2023,
BH 2020 dont la seule page candidate est un tableau de raccordement à 1
colonne, en plus OCR-corrompu). Camelot refuse honnêtement ces pages plutôt
que de produire un résultat plausible mais faux — un résultat plus
correct, même si le chiffre de couverture brute baisse légèrement.

## 2026-09-08 (Phase 1 — pipeline complète) — colonnes homonymes

En branchant l'extraction complète à `extraction/annexe13_pipeline.py`
(normalisation + validation + stockage `tableau_cellules`, voir plus bas) et
en traitant TOUS les documents, un cas jusque-là invisible est apparu :
`Duplicate entry '...-primes_acquises-31/12/2018'` au stockage, sur les
années STAR encore sur le gabarit agrégé (page 4, pas de vraie page Annexe
13 — ex. 2015, 2017, 2018, 2025). Cause : 2-3 centres de colonnes distincts,
déjà connus pour se scinder (dédoublement documenté plus bas), pouvaient en
plus se voir attribuer le MÊME libellé nettoyé ("31/12/2018" apparaissant
sur 2-3 fragments d'en-tête wrappé), invisible tant que rien ne dépendait de
l'unicité des noms de colonnes (l'export direct depuis le PDF les affichait
juste côte à côte). Fix : les noms de colonnes dupliqués sont désormais
désambiguïsés par suffixe (" (2)", " (3)"...) — même principe déjà appliqué
aux libellés de ligne dupliqués.

Suivi des cas rencontrés en construisant l'extraction complète des tableaux
annexes (toutes lignes × toutes colonnes) — démarrée le 2026-09-08 sur
demande explicite de l'utilisateur (la page Gestion de données ne doit pas
se limiter aux 7 KPI déjà extraits pour les dashboards — voir
annexe13_kpi_extractor.py::KPI_PATTERNS).

## 2026-09-08 (suite) — mauvaise page sélectionnée pour plusieurs sociétés

Déclencheur : l'utilisatrice a fourni un script de référence (camelot,
`C:\Users\HP\Music\AzzaStage25-26\FS_Market_Intelligence\A.py`/`B.py`) dont
la sortie pour STAR/2024/Annexe13 est une grille propre à 9 colonnes
(GROUPE, A.TRAVAIL, INCENDIE, RISQUES DIVERS, TRANSPORT, AVIATION,
AUTOMOBILE, ACCEPTATION, TOTAL) — très différente du résultat produit par ce
module (page 4, table de réconciliation brut/cessions/net à 4 colonnes,
libellés fragmentés). En comparant : la page 4 ("L'état de résultat
technique de l'assurance non-vie...") n'est PAS l'Annexe 13 — c'est une
table de réconciliation différente qui satisfait accidentellement le motif
de titre existant. La vraie page Annexe 13 de STAR (page 32, titrée "Annexe
N°13 : Résultat technique de la catégorie d'Assurance Non-Vie") était
invisible au localisateur de page. Deux bugs de localisation/reconstruction
trouvés et corrigés (généraux, pas spécifiques à STAR) :

| Bug | Cause | Fix |
|---|---|---|
| Titre "Annexe 13" de STAR non reconnu comme page cible | Le titre dit "Résultat technique **DE LA** catégorie" — le motif existant (partagé avec le pipeline 7-KPI, `annexe13_kpi_extractor.PAGE_TITLE_RE`) n'accepte que "**PAR** catégorie". Les 7 KPI dashboard restent corrects malgré tout (même total, présenté en Brut sur les deux pages) donc le module partagé n'a pas été touché — un motif de titre local et élargi (`_FULL_TABLE_PAGE_TITLE_RE`) a été créé pour ce module uniquement. | Connecteur "par" OU "de la" accepté entre "résultat technique" et "catégorie". |
| Ancre d'en-tête "en dinars" absente sur la vraie page Annexe 13 de STAR | Cette page dit "(Exprimé en dinar tunisien)" — SINGULIER, sans "s" — alors que l'ancre ne reconnaissait que "en dinars" (pluriel). Sans ancre trouvée, le repli incluait le titre de page entier comme "en-tête", polluant les libellés de colonnes. | Ancre élargie à "en dinar" (sans "s") — sous-ensemble de "en dinars", ne perd aucun cas déjà couvert. |
| Colonnes fantômes vides ("(colonne N)") | Un centre de colonne déduit des valeurs peut n'avoir AUCUN mot d'en-tête à portée (même symptôme que le dédoublement de colonnes déjà documenté pour STAR page 4) — laissait des entrées vides inutiles dans la liste de colonnes. | Colonnes au libellé placeholder supprimées après coup (garde-fou : jamais si ça viderait tout). |
| BIAT : page correcte trouvée mais mauvaise page RETENUE | `locate_and_extract_full_table` départageait uniquement sur "le plus de colonnes" — une page de sommaire non pertinente pouvait produire PLUS de colonnes (fragmentées, inexploitables : 49) que la vraie page Annexe 13 (15 colonnes propres) et gagnait donc à tort. | Départage en 2 temps : d'abord la page réellement titrée "Annexe..." (signal robuste, indépendant de la reconstruction), puis seulement le nombre de colonnes parmi des candidats à égalité sur ce premier critère. |
| BIAT : page Annexe 13 sans AUCUNE ligne d'unité monétaire | Le titre enchaîne directement sur l'en-tête de colonnes ("ANNEXE N°13 : ..." / "Total" / "AUTO TRANSPORT INCENDIE...") — aucune ancre "en dinar" à trouver, donc repli sur l'ancienne heuristique positionnelle qui incluait le titre. | Nouveau repli intermédiaire : si aucune ancre monétaire, chercher la ligne de TITRE elle-même (même motif que la détection de page) et démarrer l'en-tête juste après. |

**Résultat** : GAT (déjà correct) inchangé ; STAR passe de la mauvaise page
(4, réconciliation) à la vraie page (32, grille par branche) — valeurs
vérifiées ligne par ligne identiques au script de référence de
l'utilisatrice ; BIAT passe de la mauvaise page (23, sommaire, 49 colonnes
fragmentées) à la vraie page (33, 12 colonnes propres). Sweep complet
(10 ans) : toujours 89/130 (68%) — le taux OK/ECHEC ne bouge pas (ces
sociétés passaient déjà `_sanity_ok`, juste avec la MAUVAISE page/des
colonnes cassées), mais la qualité structurelle du résultat est
nettement meilleure pour les documents concernés.

**Nouveau cas identifié, non résolu** : ASTREE — la page correcte est bien
trouvée (39, "annexe" dans le titre) mais le texte d'en-tête de certaines
colonnes est rendu par le PDF avec des lettres individuellement espacées et
entremêlées ("s p o n s a b i e c e n n a l e" pour un texte qui devrait
être "RESPONSABILITE CIVILE..."), cassant la reconstruction mot-par-mot.
Ressemble à un artefact de rendu/police plutôt qu'à un problème de logique —
non creusé plus avant (limite du PDF source, catégorie déjà rencontrée pour
d'autres sociétés/pages ailleurs dans le projet).

## Principe validé

Colonnes déduites de la position X des VALEURS numériques des lignes de
données (fiable, une seule ligne visuelle) plutôt que des libellés d'en-tête
(souvent repliés sur 2-3 lignes visuelles). Chaque mot d'en-tête est ensuite
rattaché à la colonne la plus proche (x0), triés par position verticale pour
restituer l'ordre de lecture d'un libellé replié. La page cible est
localisée en réutilisant le prédicat déjà validé de l'extracteur 7-KPI
correspondant (`annexe13_kpi_extractor._is_target_page`, etc.) plutôt qu'une
détection indépendante — `locate_and_extract_full_table()` essaie TOUTES
les pages candidates et retient celle dont la grille passe un contrôle de
vraisemblance (au moins 2 lignes reconnues par les regex KPI existantes) et
compte le plus de colonnes.

## Couverture réelle — Annexe 13 (Non-Vie), 10 derniers exercices (2016-2025), 15 sociétés testées (hors Vie-only/Takaful/PDF absent)

Suivi via `scripts/audit_full_table_extraction.py --years 10 --last-year 2025`
(sweep complet reproductible, détail par société/année dans
`scripts/audit_full_table_extraction_report.json`).

**Dernier relevé (2026-09-08, après le fix STAR décrit plus bas) : 89/130
documents existants OK (68%)**, contre 82/130 (63%) juste avant. Aucune
régression sur aucune société entre les deux relevés.

| Société | OK / testés | Années en échec |
|---|---|---|
| ASTREE | 10/10 | — |
| BIAT | 10/10 | — |
| GAT | 10/10 | — |
| TUNIS_RE | 10/10 | — |
| BH | 7/7 (PDF dispo depuis 2019) | — |
| STAR | 9/10 | 2023 (gabarit différent — voir ci-dessous) |
| CARTE | 9/10 | 1 année isolée |
| COMAR | 8/10 | 2 années isolées |
| MAGHREBIA | 6/6 (PDF dispo depuis 2018) | — |
| LLOYD_TUNISIEN | 6/9 | 3 années isolées |
| CTAMA | 2/2 (PDF dispo 2018, 2020) | — |
| AMI | 1/8 | 7 années |
| BNA | 1/2 (PDF dispo depuis 2024) | 1 année |
| ATTIJARI | 0/10 | toutes |
| COTUNACE | 0/10 | toutes |
| UIB | 0/6 | toutes |

**Échecs systématiques (toute la société), chacun diagnostiqué individuellement :**

| Société | Cause diagnostiquée | Piste |
|---|---|---|
| ATTIJARI | Le document 2024 ne contient une page "résultat technique" que côté **Vie**, aucune page Non-Vie trouvée sur les 8 premières pages — cohérent avec le commentaire déjà présent dans `api/routes/comparative.py` ("ATTIJARI 2024... aucun des 4 KPI de primes") : limite déjà connue du document source, pas de l'extraction. | Vérifier si l'annexe Non-Vie existe plus loin dans le document avant de conclure à une absence totale. |
| COTUNACE | Page trouvée (68) mais 45 "colonnes" détectées au lieu de ~16 — texte natif corrompu à la source (déjà documenté : `api/services/quality.py::PROBLEMATIC_CODES["COTUNACE"]`, "texte corrompu par un OCR de mauvaise qualité à la source"). Limite pré-existante du document, pas de ce module. | Aucune (société déjà exclue par le reste de la plateforme pour la même raison). |
| UIB | Titre de page contient un artefact d'encodage brut `(cid 4666)`/`(cid 4667)` à la place des parenthèses — casse la détection de page. | Nettoyer/ignorer les séquences `(cid N)` avant normalisation ; à vérifier si ce même artefact affecte d'autres sociétés. |
| AMI | Échec sur 7/8 années testées (seule 2018 passe) — pattern pas encore investigué en détail (probablement gabarit distinct comme STAR, ou pages scannées comme BNA). | À investiguer si l'utilisateur priorise cette société. |
| BNA | Aucune occurrence de "résultat technique" trouvée sur les documents anciens (texte natif) — cohérent avec les pages scannées déjà documentées pour BNA ailleurs dans le projet. | Repli OCR (déjà exploré pour d'autres sociétés dans `bilan_kpi_extractor.py`) — non tenté ici. |

**Cas résolus depuis le premier relevé (8/14 → 89/130) :**

| Cas | Symptôme | Fix |
|---|---|---|
| LLOYD_TUNISIEN | La vraie page (33, confirmée manuellement — en-têtes de branches bien présents : "Acceptation, Acc R.D, Auto, Acctrav, Incendie, Transport, Grêle...") est intitulée par le document "IV.7 **Notes sur** le résultat technique par catégorie..." — exclue par `annexe13_kpi_extractor._is_target_page` via `NOTES_SECTION_RE` (`\bnotes sur\b`), une exclusion volontaire du module existant. | `relaxed_is_annexe13_page()` — prédicat parallèle sans cette exclusion, passé en `extra_page_predicate` à `locate_and_extract_full_table` (union avec `_is_target_page`, jamais un remplacement) ; `_is_target_page` reste inchangé pour ne pas risquer de régression sur le pipeline 7-KPI existant. |
| STAR (2022, 2024, 2025 + gains BH/CARTE/CTAMA en ricochet) | Page trouvée mais gabarit à libellé replié sur 2 lignes visuelles avec les valeurs intercalées au milieu (ex. "Variation de la provision pour" / [valeurs] / "primes non acquises"). Une première fusion "toujours consommer la ligne suivante comme suffixe" corrigeait ce cas MAIS fusionnait aussi à tort deux postes comptables bien DISTINCTS quand la ligne de valeurs avait déjà son propre libellé complet (ex. "Primes émises et acceptées" + [valeurs] absorbait à tort le début du poste suivant "Variation de la provision pour..."). | Le suffixe n'est désormais consommé QUE si le libellé propre de la ligne de valeurs est vide/junk (symbole isolé "+"/"-"/"+/-") — sinon la ligne suivante est traitée comme le début du poste logique suivant, jamais comme la suite du poste courant. |
| Vraisemblance (`_sanity_ok`) trop stricte pour les gabarits à formulation différente | Les regex étroites de l'extracteur 7-KPI (ancrées en tout début de libellé, ex. `^primes emises\b`) ne matchaient qu'1 ligne sur 18 pour STAR 2024 même une fois le tableau correctement reconstruit, faute de correspondre à des formulations légèrement différentes ("Variation de la provision pour primes non acquises" vs "Provisions pour primes non acquises" attendu par le dashboard). | Vocabulaire générique additionnel propre au tableau résultat technique (`_GENERIC_LINE_ITEM_TERMS` — "primes emises", "charge de sinistres", "commissions", "resultat technique"...), utilisé en complément des regex étroites (jamais à leur place) ; conserve le filtrage des pages de prose (ex. faux positif GAT déjà documenté) car ce vocabulaire reste spécifique au poste comptable, pas des mots génériques. |

**Branchement à l'export Excel (2026-09-08) et bugs trouvés en le testant "en
vrai" sur `api/services/data_management.py::build_flexible_export_xlsx`** —
jusqu'ici la grille complète n'était que testée en script, jamais rendue
dans un vrai fichier téléchargé : deux défauts invisibles au simple contrôle
de vraisemblance (compte de lignes/colonnes) sont apparus à l'ouverture du
fichier réel :

| Défaut | Symptôme | Fix |
|---|---|---|
| Valeurs négatives entre parenthèses fuyant dans le libellé | `_label_text` du module partagé (annexe13_kpi_extractor) ne reconnaît comme "numérique" qu'un mot-token *entièrement* chiffres — un token scindé par pdfplumber avec sa parenthèse ("(4", "562)") lui échappe et reste dans le libellé. Invisible sur les gabarits à 1 seule colonne de valeurs sur la ligne du libellé, mais sur GAT (16 colonnes/branche, toutes les valeurs de la ligne — donc jusqu'à 16 nombres entre parenthèses — sur la même ligne physique que le libellé) ça produisait des libellés illisibles du type "Variation des primes non acquises (4 562) (246 203) (75 965)...". | `_label_text` local à `full_table_extractor.py` (ne touche pas le module partagé) avec un filtre élargi aux fragments entre parenthèses (`_BRACKET_NUMERIC_RE`) — généralisable à tout gabarit à valeurs négatives entre parenthèses, pas propre à GAT. |
| Ligne de sous-titre de section confondue avec l'en-tête de colonnes | Sur STAR, la ligne "PRNV1 Primes acquises" (intitulé de section sans valeur propre, juste avant "PRNV11 Primes émises et acceptées + [valeurs]") tombe dans la plage de lignes considérée comme "en-tête" (entre l'ancre "en dinars" et la première ligne de données) — ses mots ("PRNV1", "Primes", "acquises") polluaient les libellés de colonnes déduits. | Les mots d'en-tête ne sont retenus que s'ils sont positionnés à droite du début réel des colonnes de données (`HEADER_LEFT_MARGIN`) — un intitulé de section démarre dans la zone du libellé de ligne (tout à gauche), pas au-dessus des valeurs. |

**Essai infructueux, annulé (documenté pour ne pas le retenter à l'identique) :**
le dédoublement de colonnes de STAR (voir cas non résolu ci-dessous) semblait
venir d'un seuil de regroupement de colonnes (`COL_GAP=6pt`) trop strict pour
un gabarit à colonnes larges alignées à droite (une même colonne peut avoir
des x0 différents de ~17pt selon le nombre de chiffres de la valeur). Élargir
`COL_GAP` à 20pt corrigeait bien STAR mais fusionnait à tort de VRAIES
colonnes voisines distinctes sur le gabarit à 16 colonnes/branche (ex. GAT :
"Automobile"/"Transport" fusionnées en une seule colonne) — un seuil global
unique ne peut pas satisfaire les deux gabarits à la fois. Remis à 6pt.

**Nouveau cas identifié, non traité (gabarit distinct, pas un bug) :**

| Société/année | Constat |
|---|---|
| STAR 2023 | ⚠️ **Diagnostic corrigé le 2026-09-09 (voir entrée "audit de qualité" plus haut) — ce qui suit est l'ANCIEN diagnostic, faux, gardé pour mémoire.** À l'époque (pré-camelot), attribué à un gabarit "raccordement" à 1 seule colonne (page 38, "Annexe n°16"). Re-vérifié après la découverte du schéma "page scannée" sur STAR 2025/ASTREE 2023 : **page 36 du même document a `page.chars=3`, `page.images=2`, texte extractible = 0** — exactement entre l'Annexe 11 (page 35) et l'Annexe 14 (page 37), là où la vraie grille par branche Non-Vie (Annexe 12/13) devrait se trouver. C'est un **3ᵉ cas confirmé du même défaut** (page scannée sans couche de texte), pas un "gabarit différent" — la page 38 trouvée par l'algorithme n'est qu'un repli (Annexe n°16, une reconciliation séparée), pas la vraie source. Concerné par le chantier OCR en cours (tâche de fond "OCR fallback for scanned Annexe 13 pages"). |
| STAR (années "OK") — dédoublement de colonnes | Le gabarit STAR (4 colonnes larges, valeurs alignées à droite) attend 4 colonnes ("Opérations brutes", "Cessions et/ou rétrocessions", "Opérations nettes 2024", "Opérations nettes 2023") mais l'extraction en produit jusqu'à 7-8 : une même colonne logique se scinde en 2 quand ses valeurs, d'une ligne à l'autre, ont des nombres de chiffres différents (donc des x0 différents une fois alignées à droite) au-delà de la tolérance `COL_GAP`. **Les VALEURS restent correctement rattachées à des colonnes cohérentes** (rien n'est perdu ni mal assigné) — seul le REGROUPEMENT des libellés d'en-tête en une colonne unique par concept est imparfait. Un correctif global (`COL_GAP` élargi) a été essayé et rejeté car il casse le gabarit à 16 colonnes/branche (voir "Essai infructueux" ci-dessus) ; accepté comme limitation connue plutôt que de risquer une régression sur le gabarit majoritaire. |

## Cas résolus en cours de route (pour mémoire)

| Cas | Symptôme | Fix |
|---|---|---|
| Ancrage d'en-tête trop strict | "exprimé en dinars tunisiens" (GAT) n'est qu'une des variantes ("chiffres arrondis en dinars" STAR, "unité en dinars" BH/BIAT...) | Ancrage relâché sur la sous-chaîne commune "en dinars" |
| GAT — faux positif page "F.2.6 Tableaux de raccordement... sont présentés au niveau de..." (prose citant le titre recherché) | Cette page de sommaire satisfaisait `_is_target_page` et produisait assez de colonnes/lignes pour paraître valide | `locate_and_extract_full_table()` essaie toutes les pages candidates et vérifie que ≥2 lignes matchent une regex KPI réellement attendue avant d'accepter |
| COMAR — ligne société/date (3 nombres : jour + mois + année) prise pour la première ligne de données | Seuil `MIN_DATA_CLUSTERS` trop bas (3) | Relevé à 4 |
| GAT — mot court "aux" ("Autres dommages **aux** biens") mal rattaché | Rattachement par centre du mot plutôt que par bord gauche (x0) | Rattachement par x0 |
| GAT — colonne "Autres" totalement vide sur la page (aucune donnée nulle part) | Mot d'en-tête sans centre de colonne déductible, disparaissait silencieusement | Réinséré comme colonne à part entière (valeurs = None) à sa position x réelle |
| STAR — libellé et valeurs d'une même ligne logique séparés en 2 lignes visuelles | `_cluster_lines` scinde parfois libellé et valeurs si leur alignement vertical diffère légèrement | Version finale (voir tableau "Cas résolus depuis le premier relevé" ci-dessus) : le suffixe n'est consommé que si le libellé propre de la ligne de valeurs est vide/junk, pour ne jamais fusionner deux postes distincts |

Ce fichier doit être mis à jour à chaque société/tableau diagnostiqué, comme les autres CAS_PARTICULIERS*.txt du projet. Prochaine étape naturelle une fois Annexe 13 stabilisée : appliquer le même module à Annexe 12 (Vie), puis Bilan (structure différente — Brut/Amortissement/Net, pas de branches — non couvert par l'algorithme actuel).

## 2026-09-10 — TUNIS_RE : en-têtes de groupe fusionnés à tort + collision d'alias "Total"

Retour utilisateur sur `Export_donnees (64).xlsx` (TUNIS_RE) : "les trois colonnes
incendie ARD risque technique [...] doivent être fusionnées dans une seule nom
de colonne qui s'appelle non marine [...] on a la colonne totale qui a dans son
nom le numéro deux à côté, ce qui n'est pas logique". Vérifié directement sur
`TUNIS_RE_2020.pdf` page 67 (dump `camelot.read_pdf(flavor='stream')` brut) :

```
row 3: ['RUBRIQUES','','NON MARINES','','TOTAL NON','','MARINES','TOTAL','TOTAL','','VIE','TOTAL']
row 4: ['','INCENDIE','ARD','RISQUE TECH','MARINES','TRANSPORT','AVIATION','MARINES','NON VIE','','','GENERAL']
```

**Défaut n°1 — en-tête de GROUPE rattaché à une seule sous-colonne.** Le PDF
fait chapeauter "NON MARINES" sur 3 sous-colonnes (Incendie/ARD/Risque Tech) et
"MARINES" sur 3 autres (Transport/Aviation/Total Marines) — un intitulé
partagé, pas le nom d'UNE colonne. Camelot l'assigne pourtant à une seule
cellule de son DataFrame (empiriquement la plus proche du centre visuel du
span). La concaténation verticale existante (`reconstruct_grid_from_rows`)
fusionnait alors ce texte dans le libellé propre de cette seule sous-colonne :
"NON MARINES" + "ARD" → **"NON MARINES ARD"** au lieu de "ARD" ; "MARINES" +
"AVIATION" → **"MARINES AVIATION"** au lieu de "AVIATION".

Fix généralisable (donc appliqué à toute société/gabarit similaire, pas
seulement TUNIS_RE) : le PDF fait TOUJOURS figurer, dans le même bloc
d'en-tête, une colonne "Total \<Groupe\>" dont le libellé complet reconstruit
se termine exactement par les mots du groupe (ex. "TOTAL"+"MARINES" →
"Total Marines", qui se termine bien par "Marines"). Un texte de cellule
d'en-tête qui est la fin EXACTE (mots entiers, pas une sous-chaîne) du libellé
— strictement plus long — d'une AUTRE colonne du même tableau est donc reconnu
comme un intitulé de groupe partagé et exclu de la concaténation de sa colonne
d'atterrissage. Restreint aux lignes d'en-tête AUTRES que la dernière ligne
propre à chaque colonne (son libellé "feuille" juste au-dessus des données)
pour ne jamais retirer par erreur la 2ᵉ moitié d'un VRAI libellé replié sur 2
lignes ("MARINES" en dernière ligne de la colonne "Total Marines" doit rester —
ce n'est pas un en-tête de groupe, seul son homonyme de la ligne du DESSUS
l'est). Implémenté dans `extraction/full_table_extractor.py::
reconstruct_grid_from_rows` (juste avant la boucle de construction de
`col_names`).

**Défaut n°2 — collision d'alias "Total".** `_COLUMN_ALIASES["total non vie"]`
pointait vers le même nom canonique bare `"Total"` que `"total general"` —
TUNIS_RE ayant les DEUX colonnes dans le même tableau ("Total Non Vie" ET
"Total Général"), `normalize_table` les distinguait par le suffixe de
désambiguïsation générique " (2)", produisant l'illogique **"Total (2)"**
signalé par l'utilisatrice. Fix : nouveau nom canonique distinct "Total non
vie" dans `CANONICAL_COLUMNS`, alias "total non vie" repointé vers lui au lieu
de "Total" (`extraction/annexe13_pipeline.py`).

**Défauts mineurs corrigés dans la foulée (même diagnostic, même société) :**
"ARD" (branche réassurance Non Marines) absente de `CANONICAL_COLUMNS`/
`_COLUMN_ALIASES` — restait en minuscules non normalisée ; ajoutée (distincte
de "Risques divers", branche assureur direct sans rapport, jamais fusionnées).
"Wakala" comme LIBELLÉ DE LIGNE (poste de commissions propre aux contrats
Takaful, distinct de "Wakala" déjà connu comme nom de COLONNE/branche) absente
de `CANONICAL_ROWS` — mot de 6 lettres, sous le seuil de correspondance floue
`_MATCH_THRESHOLD`, finissait en "non reconnu" ; ajoutée telle quelle.

**Vérifié** — grille TUNIS_RE 2020 page 67, 23/23 lignes reconnues, colonnes
`['Incendie','ARD','Risques techniques','Total non marines','Transport',
'Aviation','Total marines','Total non vie','(colonne 9)','Vie','Total']`
(la colonne 9 sans nom est une VRAIE colonne vide dans le PDF source — aucune
valeur nulle part, ni en-tête — pas un défaut d'extraction). Rejoué sur les 11
années disponibles (2015-2025) : **2019-2025 (7 ans) structure identique et
propre**, confirmant que le fix se généralise dans le temps pour cette société,
pas seulement 2020. Écarts `validate_table` restants (règle
"solde_souscription") = faux positifs déjà documentés (convention de signe
"Charges de prestations" non négée chez TUNIS_RE — la règle générique ADDITIONNE
en supposant un signe déjà négatif).

**Cas différent, NON traité ici (gabarit distinct des années 2015-2018) :**
2015-2018 ont un découpage de colonnes différent (ex. "Non marines" reste une
colonne agrégée non éclatée en Incendie/ARD/Risque Tech certaines années,
"Transport"/"Aviation" fusionnées en "transport aviation" ou "marines aviation"
d'autres années, "Total (2)"/"Total non vie (2)" toujours en collision, 2017
laisse fuir une date "31/12/2017" dans un libellé de colonne) — semble être un
gabarit de page réellement différent pour ces exercices plus anciens (pas une
régression du fix ci-dessus, qui n'a aucun effet quand la table source n'a pas
la même structure de span). Diagnostic à reprendre séparément si ces
années sont dans le périmètre demandé.

## 2026-09-10 — AMI : colonnes OCR effondrées en 1 seule ("(colonne 1)")

Passage à AMI (méthode "une société à la fois, validée avec l'utilisatrice
entre deux") après TUNIS_RE. AMI_2020.pdf page 47 est un SCAN IMAGE pur
(`page.chars`=4, aucune couche texte) — voie OCR (`scanned_table_extractor.
py`). Avant correction : `locate_and_extract_full_table` renvoyait une
grille à une seule colonne `['(colonne 1)']`, alors que le PDF (vérifié par
rendu image, `pdfplumber.to_image`) montre clairement 7 colonnes nettes
Incendie/Transport/Risq. Divers/Risq. Spx/Automobile/Groupe/Total, dans un
tableau quadrillé bien imprimé (pas un scan dégradé).

**Cause racine.** `_column_bands` déduisait les colonnes en regroupant les
CENTRES des cellules numériques lues par l'OCR (tolérance 4,5 % de la
largeur de page). Sur un tableau à 7 colonnes étroites, un seul chiffre
tronqué ou deux cellules voisines qui se touchent presque suffit à décaler
le centre apparent d'une cellule et à faire fusionner à tort plusieurs
vraies colonnes en une seule bande — ce qui s'est produit ici de façon quasi
totale.

**Fix généralisable (`_detect_column_lines`, nouveau)** : le tableau est
QUADRILLÉ dans le PDF — ses filets verticaux, imprimés par le document
lui-même, donnent la frontière EXACTE entre colonnes, indépendamment de ce
que l'OCR a lu dans chacune. Détectés par la même morphologie OpenCV que
`_remove_rules` (qui les efface pour la lecture OCR) mais en CAPTURANT leurs
positions X avant effacement. `_column_bands` les utilise en priorité :
chaque bande = le milieu entre deux filets consécutifs, gardée seulement si
elle reçoit réellement ≥ 3 centres de cellule numérique (repli sur
l'ancien regroupement de centres si le quadrillage est absent/mal détecté).
`_row_label_and_cells` bloque aussi la fusion de deux tokens numériques
proches dès qu'un VRAI filet de colonne les sépare, même si l'écart en
pixels est petit. Vérifié sur AMI_2020 p.47 : filets détectés à
[457,1855,2056,2258,2462,2664,2868,3070,3272,3720] (repère du scan à 340
dpi) → 7 bandes exactement alignées sur les 7 colonnes réelles.

**Régression détectée et corrigée en cours de route (COTUNACE 2019).** Le
seuil de "support" minimal pour garder une bande fondée sur le quadrillage
était `≥ 1` centre de cellule — trop permissif : un unique artefact OCR en
bord de page (au-delà du dernier filet réel) tombait par hasard dans sa
marge de tolérance et créait une 3ᵉ bande fantôme, cassant la fusion des 2
colonnes "Crédit-Caution" dupliquées (`_reconcile_doubled_columns`, qui
n'agit que si `len(colonnes) == 2` après dédoublonnage) — sortie passée de
`['Crédit-Caution']` (correct) à `['Crédit-Caution', 'Crédit-Caution (2)',
'(colonne)']` (cassé). Relevé le seuil à `≥ 3` : re-vérifié, COTUNACE 2019
revient à `['Crédit-Caution']`.

**En-têtes de colonne toujours mal lus malgré la structure correcte.**
Même avec les 7 bonnes bandes, les noms de branche restaient méconnaissables
("lnmnflic", "-trlmpurl", "rkq. dm mi"...) — l'OCR page entière (Tesseract
--psm 6) lit mal les mots courts de l'en-tête, noyés dans le bloc de tableau
complet. `_header_names` gagne un repli `reocr_fn` : une fois la ligne
d'en-tête identifiée (par vocabulaire de branche si possible, sinon par
POSITION — dernière ligne à ≥ 6 lettres juste au-dessus de la 1re ligne de
données, nouveau repli lui aussi générique), elle est RE-OCRisée seule, sa
bande horizontale isolée du reste du tableau — Tesseract segmente et lit
nettement mieux une ligne isolée qu'au sein d'un bloc entier. Résultat sur
AMI 2020 : "lnmnflic/-trlmpurl/rkq. dm mi/autorehbite/cmltycl" →
"kmcendie/trampor/fiq.piver/automebile/grope" — toujours imparfait mais
désormais lisible/reconnaissable pour un francophone (contre illisible
avant), et bien préférable à un "(colonne k)" muet.

**État final AMI 2020** : 7 colonnes correctement délimitées et nommées
(imparfaitement mais lisiblement), 20/23 lignes reconnues (3 non reconnues :
"Annexe" et "Arnexes aux états financiers..." = bruit de bas de page capté
à tort comme lignes de données — préambule/pied de page, pas des postes du
tableau ; "Commissions reçues..." reste non reconnue car son propre libellé
est trop dégradé par l'OCR pour matcher). 1 seul écart de validation
(`charges_acquisition_gestion`, colonne Total) contre de nombreux avant —
dû à un chiffre encore mal fusionné par l'OCR sur cette cellule précise
(limite résiduelle de qualité de lecture, pas de structure).

**Limite reconnue, non résolue ici** : contrairement à TUNIS_RE (bug de
logique pur,100 % corrigible), AMI_2020 reste un scan image et certaines
cellules individuelles restent mal lues par Tesseract (chiffres fusionnés
entre eux, ex. "9853" + "-10484" recollés en un seul mot OCR AVANT même
d'atteindre notre logique de colonnes — la faute vient de la segmentation
de mot de Tesseract lui-même, pas de notre code). Documenté comme limite de
qualité de scan/OCR, dans la même famille que les cas déjà connus
(COTUNACE 2023 filets épais, STAR/ASTREE pages scannées).

## 2026-09-10 (suite) — AMI 2019/2020/2023 + COTUNACE 2017/2019/2023 : saisie manuelle vérifiée

L'OCR de ces 6 pages Annexe 13 scannées plafonne à ~70 % de cellules exactes
(voir plus haut) — insuffisant pour l'objectif « presque idéal ». Ces 6
tableaux ont donc été **transcrits à la main depuis les PDF source** et
recoupés par les identités comptables de chaque document (chaque identité
tombe juste, écart ≤ 1 millime), puis figés dans
`extraction/annexe13_verified.py` (dict `VERIFIED`, structure = matrice
24 lignes × colonnes, `None` = tiret « néant »).

`api/services/tableau_pipeline_service.py::process_one_document` consulte ce
module AVANT camelot/OCR : si `(code, année)` y figure, la grille vérifiée
est normalisée + validée EXACTEMENT comme la voie normale
(`normalize_table` + `validate_table`) puis stockée (`save_tableau_result`),
et l'OCR n'est pas tenté (statut `ok_verifie`). Une revalidation ultérieure
ne peut donc jamais écraser ces valeurs par du bruit OCR. Résultat : ces 6
années apparaissent dans l'export et les tableaux exactement comme les
autres (mêmes libellés canoniques, même ordre de colonnes).

Points d'attention :
- **AMI 2020, Résultat technique / colonne Total = 5 880 087** alors que la
  somme des 6 branches vaut 10 264 890 : anomalie DANS LE PDF source (les 7
  colonnes se recoupent entre elles, seule cette cellule ne cadre pas).
  Valeur laissée telle qu'imprimée.
- **COTUNACE 2017** : dépôt CMF EN ARABE, présente un « État de résultat
  technique » (Brut/Cessions/Net) et NON une Annexe 13 « par catégorie ».
  Seules les lignes qui correspondent sont reportées (colonne NET 2017,
  page 4) ; les sous-totaux propres à l'Annexe 13 (Solde de souscription,
  Solde financier, Solde de réassurance) et le détail « Part des
  réassureurs » n'existent pas sous cette forme dans ce dépôt.
- Écarts de validation résiduels sur AMI 2019/2020 et COTUNACE 2019/2023 :
  ce sont les **faux positifs de convention de signe déjà connus** (règle
  générique `VALIDATION_RULES` qui ADDITIONNE alors que ces documents
  soustraient « Charges de prestations » / « Participation aux résultats » /
  « Part des réassureurs dans les primes acquises »). Les VALEURS sont
  justes — mêmes écarts que ce que produisent déjà LLOYD_TUNISIEN et
  TUNIS_RE. AMI 2023 : 0 écart (ce dépôt-là utilise des valeurs déjà
  signées).
- Pour ajouter une autre année vérifiée : compléter `VERIFIED` dans
  `extraction/annexe13_verified.py` (candidats connus non encore traités :
  AMI 2016/2017, également scannés).

## 2026-09-10 (suite) — LLOYD_TUNISIEN 2020-2024

Gabarit Annexe 13 « par catégorie » (IV.7) à 9 branches : Acceptation | Acc R.D |
Auto | AccTrav | Incendie | Transport | Grêle | Groupe | TOTAL. Convention de
signe identique à TUNIS_RE (« Charges de prestations » et « Charges d'acquisition
et de gestion nettes » en valeur positive, SOUSTRAITES) → 25 écarts de validation
= faux positifs de convention (règle générique qui ADDITIONNE), valeurs justes.

- **2020, 2023, 2024** : page IV.7 avec couche texte → extraction camelot
  correcte. Corrigé au passage :
  - `_COLUMN_ALIASES` : « Acc R.D » / « acc rd » → **ARD** (= « Accidents et
    Risques Divers », même canonique que le « ARD » de TUNIS_RE).
  - `CANONICAL_ROWS` : ajout de « Autres provisions techniques (clôture) » et
    « (réouverture) » — ces 2 postes matchaient à tort « Provisions pour
    sinistres à payer (clôture)/(réouverture) » (difflib) et leurs valeurs
    étaient perdues par collision.
  - `normalize_table` : `_SECTION_SEPARATOR_LABELS` — les lignes de séparation
    « Informations complémentaires » / « A déduire : », parfois captées avec
    une valeur résiduelle (Total = 0), sont ignorées.
- **2021, 2022** : page IV.7 SCANNÉE (image, `page.chars` ≈ 88), l'extraction
  retombait sur la page de raccordement (Annexe 16, `total raccordement`).
  Transcrites à la main + recoupées par les identités (toutes justes),
  figées dans `extraction/annexe13_verified.py` (`_R_LLOYD` = ordre de lignes
  propre à LLOYD, avec « Primes cédées aux réassureurs » intercalée après
  « Solde financier »).
- **2025** : pas de PDF dans le dépôt (2015-2024 seulement).

## 2026-09-10 (suite) — COMAR : la plus grosse société (11 ans, 3 gabarits, 7 scannés/introuvables)

Gabarit propre à COMAR, différent du standard :
- **pas de ligne « Primes acquises » ni « Charges de prestations »** à part (ce
  sont des en-têtes de section, sans valeurs) — les identités correspondantes
  ne peuvent pas se valider (`donnees_manquantes`), c'est normal ;
- **« Solde financier » détaillé en « Produits de placements » + « Autres
  produits techniques »** (2 lignes) au lieu de « Produits nets de
  placements » + « Participation aux résultats » ;
- **3 lignes « Part des réassureurs »** seulement (pas de « participation aux
  résultats ») + « Commissions reçues » ;
- ligne finale « **RESULTAT TECHNIQUE NON VIE** » ;
- bloc « informations complémentaires » **par exercice N / N-1**, avec 2
  postes de plus que le standard (« participations aux bénéfices »,
  « risques en cours »).

`CANONICAL_ROWS` complété (généralisable) : « Autres produits techniques »,
« Provisions pour participations aux bénéfices (exercice N)/(N-1) »,
« Provisions pour risques en cours (exercice N)/(N-1) ».

Répartition des 11 années :
| Années | Gabarit | Page Annexe 13 | État |
|---|---|---|---|
| **2019** | 8 branches, texte natif | p.33 | ✅ **transcrite main + figée** (`annexe13_verified.py`). L'extraction native décalait les libellés de ligne (en-têtes de section « Charges de Prestations » sans valeurs → la ligne suivante prenait ce libellé ; « RESULTAT TECHNIQUE NON VIE » mappé à tort sur « Autres produits techniques »). |
| **2017** | 8 branches, texte natif | p.13 | ⏳ à traiter (mêmes décalages de libellés probables) |
| **2023, 2025** | 15 branches, texte natif | p.35 / p.39 | ⏳ à traiter |
| **2020, 2021, 2022, 2024** | 15 branches, page IV.7 SCANNÉE (titre texte, tableau image) | p.33 / p.36 / p.35 / p.37 | ⏳ transcription main (grosses tables ~14 branches × ~34 lignes ; scans lisibles) |
| **2015** | gabarit « raccordement » (Brut/Cessions/Net) | — | ⏳ à traiter séparément |
| **2016, 2018** | page introuvable (scan ?) | — | ⏳ localiser puis transcrire |

COMAR reste à finir sur plusieurs passes (année par année) — c'est de loin la
société la plus lourde du portefeuille.

## 2026-09-10 (suite) — COMAR 2017 + 2023 figées ; branches 15-colonnes gérées

- **2017** (8 branches, page 13, texte natif) — transcrite via reconstruction
  géométrique (`page.extract_words` + bornes de colonne issues de l'en-tête)
  puis recoupée par les identités (toutes justes). Figée.
- **2023** (15 branches, page 35, texte natif) — idem. Gabarit COMAR élargi :
  colonnes Incendie/Accidents du travail/Responsabilité civile/Automobile/
  Transport/Groupe/Autres dommages aux biens/Risques agricoles/Construction/
  **Perte d'exploitation**/Crédit-Caution/Assistance/Accidents corporels/
  Acceptation/Total. Bloc réassurance à 7 sous-lignes (dont « … dans la
  variation des primes non acquises » et « … dans les charges des autres
  provisions techniques »). Informations complémentaires par branche (et
  plus seulement Total). Figée.

Pipeline complété (généralisable) :
- `CANONICAL_COLUMNS` + alias : « Perte d'exploitation » (branche COMAR).
- `CANONICAL_ROWS` : « Part des réassureurs dans la variation des primes non
  acquises » et « … dans les charges des autres provisions techniques » —
  matchaient à tort « … dans les primes acquises » (difflib).

Reste COMAR : **2025** (15 branches, texte natif mais bloc réassurance à ~9
sous-lignes, la reconstruction auto décale libellés/valeurs — passe dédiée) ;
**2020, 2021, 2022, 2024** (15 branches, pages IV.7 SCANNÉES) ; **2015**
(raccordement) ; **2016, 2018** (page introuvable).

## 2026-09-10 (suite) — COMAR 2025 figée (passe soignée signes)

COMAR 2025 (15 branches, page 39, texte natif) : le PDF note d'un simple
« - » AUSSI BIEN une cellule vide qu'un signe négatif. Reconstruction
géométrique (positions de colonne) pour l'assignation + les valeurs ;
signes recoupés/corrigés par les identités comptables (les colonnes Total
des lignes-sommes « Solde financier », « Part des réassureurs dans les
prestations payées », « Commissions reçues » avaient un signe faux dans la
lecture auto → re-signées d'après la somme des composantes). Toutes les
identités principales (Solde souscription, Charges d'acq. et gestion,
Solde financier, Résultat technique) tombent juste ; 4 branches mineures
(Risques agricoles, Construction, Perte d'exploitation, Crédit-Caution)
ont un résidu de 250-1700 dinars sur le seul « Solde de réassurance »
(détail réassurance à 9 sous-lignes) — valeur PRINTÉE du PDF conservée.

`CANONICAL_ROWS` complété : « Autres charges techniques », et 3 lignes
« Part des réassureurs dans les frais reportés / … frais d'acquisition /
… autres charges techniques » (bloc réassurance détaillé de COMAR 2025).

**Bilan COMAR : 4/11 années figées** (2017, 2019, 2023, 2025). Restent
2020/2021/2022/2024 (pages IV.7 SCANNÉES, 15 branches) ; 2015
(raccordement) ; 2016/2018 (page introuvable).

## 2026-09-10 (suite) — COMAR 2020, 2021, 2022, 2024 figées

Découverte : ces 4 pages ne sont PAS scannées, elles ont une couche texte
(pdfplumber : 4500-5300 caractères). Extraites par reconstruction géométrique
(bords droits des 15 colonnes, dérivés d'une ligne pleine) + recoupement
systématique par les identités comptables COMAR (SS = PE+VAR+PFP+CPP,
CAG = FA+ACG, SF = PdtsPlacements+AutresPdtsTech, SR = Σ parts réassureurs,
RT = SS+CAG+SF+SR, et Σ 14 branches = colonne Total). Toutes les identités
tombent juste (écart ≤ 1 millime, arrondi source).

- **2020** : signe « moins » = ‐ U+2010 préfixe collé au nombre (NON ambigu),
  cellule vide = « 0 ». Bloc réassurance à 4 lignes (pas de « participation
  aux résultats ») → gabarit `_R_COMAR` (31 lignes) + `_CM_COLS_15`.
- **2021, 2022** : idem 2020 mais bloc réassurance à 5 lignes (ajout
  « Part des réassureurs dans la participation aux résultats ») → nouveau
  gabarit `_R_COMAR_21` = `_R_COMAR` + cette ligne (32 lignes).
- **2024** : le ‐ U+2010 marque AUSSI BIEN une cellule vide qu'un signe
  « moins », avec une espace insérée (« ‐ 18 668 065 ») → ambigu comme 2025.
  Reconstruction géométrique des magnitudes + CHAQUE signe et CHAQUE valeur
  manquante déduits/recoupés par les identités (dont plusieurs artefacts de
  rendu résolus par le calcul : « 20 306 475 » = en réalité RC 20 306 +
  Auto 475 ; « ‐ 81 704 129 745 183 » = Auto ‐81 704 129 + Transport
  745 183 ; « ‐ 3 7 663 671 » = ‐37 663 671). Bloc réassurance à 7 lignes
  avec « … frais reportés » (mais SANS « … charges des autres provisions
  techniques » ni « Autres charges techniques ») → nouveau gabarit
  `_R_COMAR_24` = `_R_COMAR_15` avec « frais reportés » à la place de
  « charges des autres provisions techniques » (34 lignes).

Nouvelle ligne canonique : « Part des réassureurs dans la participation aux
résultats » était déjà dans `_R` / `_R_COMAR_15` — rien à ajouter au pipeline.

Stockées via `process_one_document` (statut `ok_verifie`, docs 25/26/27/29),
`build_result` → normalize_table + validate_table : 0 règle en échec sur les
4 (105 règles chacune pour 2021/2022/2024, 105 pour 2020).

**Bilan COMAR : 8/11 années figées** (2017, 2019, 2020, 2021, 2022, 2023,
2024, 2025). Restent 2015 (raccordement de format) ; 2016, 2018 (page
Annexe 13 introuvable dans le dépôt CMF).

## 2026-09-10 (suite) — COTUNACE 2020, 2021, 2024, 2025 figées

Contrairement à 2017/2019/2023 (dépôts SCANNÉS, transcrits), les pages
« Résultat technique par catégorie d'assurance NON-VIE » de 2020, 2021,
2024 et 2025 ont une COUCHE TEXTE native (millimes, 3 décimales) —
transcription directe.

Gabarit COTUNACE `_R_COT` = `_R` (24 lignes) + « Autres provisions
techniques (clôture) / (réouverture) » (= provision d'équilibrage, note
13-3) → 26 lignes. Les 4 nouvelles années portent ces 2 lignes ; 2019/2023
restent à 24 lignes (les scans les portent aussi mais n'avaient pas été
transcrites — backfill possible plus tard).

Valeurs telles qu'imprimées : charges en MAGNITUDE positive (pas signé) →
`validate_table` (ADD génériques) signale Solde de souscription / Solde
financier / Solde de réassurance / Résultat technique en écart : faux
positif de présentation (déjà le cas 2019/2023). Identités réelles
vérifiées à la main sur les 4 années (écart nul) :
`Charges prest. = Prest. payés + Ch. provisions` ; `SS = PA − Charges` ;
`CAG = FA + Autres ch. gestion` ; `SF = Produits placements − Participation` ;
`SR = −RA(primes) + RA(prest.) + RA(ch.prov.) + RA(participation) + Commissions` ;
`RT = SS − CAG + SF + SR`.

Le signe imprimé de « Variation des primes non acquises » est INCOHÉRENT
d'un millésime à l'autre dans le dépôt COTUNACE : 2024/2025 vérifient
`PA = PE + Var`, mais 2019/2020/2021 vérifient `PA = PE − Var`. Valeur
conservée telle qu'imprimée dans chaque PDF. Continuité inter-exercices
confirmée (PPNA/PSAP/APT ouverture N = clôture N−1).

Stockées via `process_one_document` (statut `ok_verifie`, docs
209/210/213/214). Pages : 2020 p.64, 2021 p.66, 2024 p.67, 2025 p.67.

**Bilan COTUNACE : 7/11 années figées** (2017, 2019, 2020, 2021, 2023,
2024, 2025). Restent 2015, 2016, 2018, 2022 (extraction live / sous-ensemble
dashboards pour l'instant).

## 2026-09-10 (suite) — MAGHREBIA Annexe 13 2018/2021/2022/2023/2024/2025 figées

Pages « Résultat technique par catégorie d'assurance » en COUCHE TEXTE
native. 11 colonnes : Accidents du travail (« A.T. ACCIDENT »), Incendie,
Automobile, Individuelle accident (« INDIVIDUEL »), Vol, Maladie, Risques
spéciaux (« R.S »), Responsabilité civile (« R.C »), Transport (« MARITIME »),
Acceptation, Total. Valeurs SIGNÉES → modèle additif comme COMAR
(SS = Primes acquises + Charges de prestations, etc.).

Reconstruction géométrique (bord droit des colonnes dérivé de la ligne
« Primes émises »), fusion des libellés de ligne multi-lignes, et
ré-agrégation du **Total** quand il est rendu ~0.2-0.3 pt plus bas que le
reste de la ligne (clustering `top` à pas 2.0 : assez fin pour laisser
ISOLÉE la ligne « orpheline » sans libellé, ~3.4 pt sous le Solde de
souscription en 2021/2022, qui n'appartient à aucune identité et est
ignorée). Toutes les identités tombent juste (écart nul) : PA, CP, SS, CAG,
SF, SR (y compris « … dans les provisions pour égalisation et
équilibrage »), RT, et Σ 10 branches = Total.

Pipeline complété (généralisable) :
- `_COLUMN_ALIASES` : « r.s » → **Risques spéciaux** (était rattaché à tort à
  « Responsabilité civile », qui entrait alors en collision avec « R.C » —
  suffixe « (2) ») ; « a.t. accident », « individuel », « maritime » ajoutés.
- `CANONICAL_ROWS` : « Part des réassureurs dans les provisions pour
  égalisation et équilibrage » (bloc réassurance MAGHREBIA — sinon rabattu
  par difflib sur « … dans les charges de provisions pour prestations ») ;
  « Provisions mathématiques (clôture) / (réouverture) ».
- `validate_table` : les postes source d'une règle peuvent être préfixés
  « ? » (FACULTATIFS : absents → comptés 0, sans « données manquantes »).
  La règle `solde_reassurance` prend ainsi « … égalisation et équilibrage »
  en poste optionnel — 0 régression sur les 129 faux positifs pré-existants
  (AMI/COTUNACE/LLOYD : convention de signe ; COMAR : couverture de formule).

2018 : bloc « informations complémentaires » à structure différente (postes
imbriqués à libellés dupliqués sous « Autres provisions techniques ») — 27
lignes retenues (21 principales + PPNA/PSAP clôture/ouverture + Autres
provisions techniques clôture/ouverture) ; le détail imbriqué 2018 reste du
ressort de l'extracteur standard. 2021-2025 : 31 lignes.

Stockées via `process_one_document` (statut `ok_verifie`, docs
103/104/105/106/107/108). `build_result` → normalize_table + validate_table :
0 ligne/colonne non reconnue, 0 règle en échec sur les 6 millésimes.

**Bilan MAGHREBIA : 6/6 années figées.**
