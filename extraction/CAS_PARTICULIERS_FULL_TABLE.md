# Cas particuliers — extraction "grille complète" (extraction/full_table_extractor.py)

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
| STAR 2023 | La page trouvée (38) est un "Tableau de raccordement du Résultat technique" à **UNE SEULE colonne de valeurs** (structure Libellé + 1 montant total), pas la grille 4 colonnes par branche des autres années. `extract_full_table()` cible spécifiquement les tableaux multi-colonnes (`MIN_DATA_CLUSTERS=4` valeurs numériques par ligne pour repérer le début des données) — une ligne de ce tableau raccordement n'a jamais que 1 valeur, donc aucune ligne de données n'est jamais détectée. Ce n'est pas un défaut de reconstruction comme le cas STAR ci-dessus : c'est un gabarit de tableau à une colonne, hors périmètre de l'algorithme actuel (conçu pour les grilles par branche). Piste pour plus tard : un chemin d'extraction séparé pour les tableaux "raccordement" à 1 colonne, plutôt que de complexifier `extract_full_table()` pour couvrir les deux formes. |
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
