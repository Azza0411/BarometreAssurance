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

## 2026-09-15 — Annexe 5.1 (État de résultat de l'entreprise Takaful)

Nouveau module `extraction/takaful_resultat_full_extractor.py`. Tableau
BEAUCOUP plus simple qu'Annexes 3/4 : 2 colonnes seulement (exercice
courant / précédent), pas de distinction Brut/Cessions. Réutilise le même
correctif "Sous total N" qu'Annexes 3/4 (numéro de section à ne pas
confondre avec une valeur — ici certains sous-totaux portent un suffixe
lettré "1a", naturellement exclu des tokens numériques donc déjà sans
risque).

Les lignes de RÉSULTAT INTERMÉDIAIRE les plus importantes ("Produit net
sur activités de gestion des fonds Takaful", "Résultat d'exploitation
avant/après impôt", "Résultat extraordinaire", "Résultat net de
l'exercice") n'ont aucun code réglementaire — capturées génériquement par
leur texte normalisé plutôt que listées une à une (généralisation,
fonctionne aussi bien sur AT_TAKAFULIA que ZITOUNA_TAKAFUL malgré des
formulations légèrement différentes).

Bug trouvé et corrigé : la ligne d'en-tête "RUBRIQUE Notes 2023 2022" se
faisait capturer comme une fausse ligne de données (les millésimes
ressemblant à des valeurs plausibles à 4 chiffres) — exclue explicitement
via `_HEADER_LINE_RE`.

Validation (identité comptable en chaîne : avant impôt + CH7 = après
impôt ; après impôt + Résultat extraordinaire = Résultat net ; Résultat
net + CH9/PR7 = Résultat net après modification) : reconcilie exactement
sur la colonne "Exercice courant" de AT_TAKAFULIA 2023, mais PAS sur
"Exercice précédent" (écart constant de 386 099 entre plusieurs lignes en
cascade) — après vérification manuelle du texte source, les valeurs
extraites correspondent EXACTEMENT à ce qui est imprimé sur le PDF ; il
s'agit donc d'une incohérence du DOCUMENT source lui-même (chiffres
comparatifs 2022 possiblement restés d'une version antérieure/non
retraités), pas d'un bug d'extraction — la validation fait exactement son
travail en la signalant plutôt que la masquer.

Pipeline `tableau_pipeline_service_takaful_resultat.py` (clé
`takaful_resultat_entreprise`) : 12/21 documents stockés avec succès.
Route : `POST /api/gestion-donnees/valider-takaful-resultat`.

## 2026-09-15 — Annexes 14/15 (Ventilation du Surplus ou Déficit par catégorie d'assurance)

Nouveau module `extraction/takaful_ventilation_full_extractor.py`.
Annexe 14 (Familial) : colonnes FIXES "Prévoyance"/"Épargne"/"Total" (pas
de branches côté Familial — structure DVRB). Annexe 15 (Général) :
colonnes = branches d'assurance + "Total" à la fin, nombre ET ordre
variables selon la société (4 branches chez ZITOUNA_TAKAFUL, 10 chez
AT_TAKAFULIA).

Aucune ligne de ce tableau ne porte de code réglementaire (contrairement
aux Annexes 1-5.1) : libellés en toutes lettres uniquement.

Approche : en-tête des branches peu fiable à parser directement (étalé
sur plusieurs lignes physiques, replié de façon incohérente chez
AT_TAKAFULIA — un fragment orphelin "(Inc/Inv) prévoyance (Inc/Inv)" sur
sa propre ligne). Comme pour FTUSA (`ftusa_full_extractor.py`), la ligne
de DONNÉES la plus complète sert d'ANCRE : ses positions x0 donnent
l'ordre réel des colonnes. Seules les 3 premières colonnes (Automobile/
Transport/Incendie, ordre constant confirmé sur les 2 sociétés — voir
`takaful_kpi_extractor.py::_extract_branches_positional`) et la dernière
("Total") reçoivent un nom fiable ; les colonnes intermédiaires
(variables en nombre ET en ordre selon le document) reçoivent un nom
générique "Branche N".

Bug trouvé et corrigé : signe négatif DÉTACHÉ du chiffre qui suit (espace
entre le "‐" et le nombre, ex. "‐ 941 736") — `NUMERIC_TOKEN_RE` n'accepte
un signe que COLLÉ aux chiffres, donc ce genre de valeur devenait
silencieusement POSITIF. Corrigé par `_merge_detached_minus_signs` :
réattache un "‐" isolé au nombre qui le suit immédiatement, AVANT le
calcul des clusters — sans ce correctif, une bonne partie des valeurs
négatives d'Annexe 15 auraient été fausses.

Validation (Σ branches = Total, ligne par ligne) : **ZITOUNA_TAKAFUL
(4 branches, pas de repli d'en-tête) reconcilie proprement (0 écart sur
toutes les lignes testées 2023)**. **AT_TAKAFULIA (10 branches, en-tête
et labels fortement repliés sur plusieurs lignes) montre des écarts sur
~11/17 lignes** — cause identifiée : un libellé étalé sur 2 lignes
physiques dont les valeurs sont SUR LA SECONDE ligne (ex. "Part des
réassureurs ... dans les charges" / "de provisions [valeurs]") se fait
capturer comme sa propre ligne ("de provisions") plutôt que rattaché au
libellé complet — répartition des valeurs par colonne correcte, mais la
ligne resurgit sous un libellé tronqué, faussant la vérification Σ=Total
pour les lignes concernées. **Limitation acceptée** (pas de correctif de
recollement multi-lignes développé pour l'instant — le cas simple, sans
repli d'en-tête, fonctionne parfaitement et couvre déjà la majorité des
sociétés Takaful potentielles).

Pipeline `tableau_pipeline_service_takaful_ventilation.py` (clés
`takaful_ventilation_familial`/`takaful_ventilation_general`). Route :
`POST /api/gestion-donnees/valider-takaful-ventilation`.

## 2026-09-15 — Correction manuelle branchée sur les 5 nouvelles clés Takaful

`api/services/data_management.py::TABLEAU_GROUPS` étendu avec les 5 clés
(`takaful_surplus_familial`/`_general`, `takaful_resultat_entreprise`,
`takaful_ventilation_familial`/`_general`), avec leurs libellés `raws`
kpi_values correspondants (`extraction/kpi_extraction_pipeline.py
::KPI_TABLE_LABEL` — "Annexes 3/4/5.1 - Fonds des Participants (Takaful)"
et "Annexes 14/15 - Ventilation par categorie d'assurance (Takaful)",
chacun partagé par plusieurs clés `tableau_cellules`, même principe que
`bilan_actif`/`bilan_passif`). Libellés SANS " — " (même contrainte que
Bilan Actif/Passif : le frontend tronque sur ce séparateur pour le texte
d'onglet court, et les 5 libellés commencent tous par "Takaful").

3 points de câblage supplémentaires, nécessaires pour que la page
correction manuelle affiche correctement le PDF source à côté de la
grille (sinon un utilisateur y verrait par erreur le message "page de
raccordement", concept propre à Annexe 12/13) :
- `locate_source_page` : whitelist étendue (sinon retourne toujours
  `None`, pas de page affichée du tout — ces 5 clés bénéficient déjà d'un
  cache de page posé directement par leur pipeline d'extraction, voir
  `save_cached_tableau_page` dans chaque `tableau_pipeline_service_takaful_*.py`).
- `page_source_info` : ces 5 clés ajoutées à la liste "pas de concept de
  raccordement" (comme `bilan_actif`/`bilan_passif`).
- `get_filter_options` : requête supplémentaire directe sur
  `tableau_cellules` pour peupler `societes_par_tableau` (même raison que
  Bilan : le KPI narrow kpi_values peut diverger de ce que la grille
  complète contient réellement).

Vérifié bout en bout (`get_document_grid`, `page_source_info`) sur
AT_TAKAFULIA/2023/takaful_surplus_familial.

## 2026-09-15 — AL_AMANAH_TAKAFUL (documents en arabe) : Bilan Actif/Passif

Nouveau module `extraction/al_amanah_bilan_full_extractor.py` — jusqu'ici
AL_AMANAH_TAKAFUL n'avait AUCUNE grille complète (seulement quelques KPI
ciblés via recherche floue arabe/OCR, voir
`takaful_kpi_extractor.py::extract_al_amanah_takaful_kpis`). Réutilise les
mêmes clés `tableau_cellules` que le Bilan francophone
(`bilan_actif`/`bilan_passif`) — dispatché depuis
`tableau_pipeline_service_bilan.py::process_one_document` sur
`code == "AL_AMANAH_TAKAFUL"`, donc AUCUN branchement supplémentaire
nécessaire côté Correction manuelle/export (déjà générique).

**Portée** : Bilan Actif/Passif UNIQUEMENT, et UNIQUEMENT pour les
documents à texte réel (`arabic_ocr_extractor.is_scanned_page` en
garde-fou — une page scannée est ignorée). Annexes 3/4/5.1/14/15 pour
cette société restent HORS PÉRIMÈTRE (pas commencées).

**Difficultés rencontrées et résolues** (voir docstring du module pour le
détail complet) :
1. Texte arabe extrait par pdfplumber avec caractères parfois inversés et
   espaces internes parasites (kerning) — réutilise
   `arabic_ocr_extractor.py::_rtl_label_from_words` (déjà construite pour
   les KPI ciblés) pour reconstruire un libellé de ligne propre.
2. Le numéro de code de chaque ligne ("أصل 1", "أصل 12"...) n'est PAS
   collé au mot-préfixe — un token séparé, mêlé au bloc de libellé une
   fois le texte reconstruit. Repéré par POSITION (tout token numérique
   dont x0 tombe dans ou au-delà du début du bloc de libellé est un
   numéro de code/renvoi, jamais une valeur — les vraies valeurs sont
   TOUJOURS physiquement à gauche du libellé sur ce gabarit).
3. `TextNormalizer` (bilan_kpi_extractor._normalizer), taillé pour du
   texte latin/français, supprime purement et simplement les caractères
   arabes — inutilisable pour toute détection de page ; abandonnée au
   profit d'une localisation de page par CONTENU (essai d'extraction sur
   chaque page, pas de pré-filtre par titre).
4. Ordre des 6 colonnes DIFFÉRENT du gabarit francophone : [Combiné,
   Entreprise, Fonds des participants] PAR EXERCICE, exercice le plus
   ancien à gauche — découvert par recoupement arithmétique
   (Combiné = Entreprise + Fonds) et confirmé par la position x0 exacte
   du KPI narrow déjà validé ("Total actif" = 17 448 993 pour
   AL_AMANAH_TAKAFUL_2020).
5. Constantes de libellés arabes ("Total actif", "Total capitaux
   propres"...) : une frappe manuelle au clavier a introduit une erreur
   d'ordre de caractères invisible à l'œil (aucune correspondance de
   préfixe, aucune erreur explicite) — corrigé en copiant les chaînes
   EXACTES depuis la sortie réelle du pipeline plutôt qu'en les retapant.
6. Une ligne de sous-total intermédiaire ("Total Actifs nets + Capitaux
   propres") peut porter un renvoi de note mal filtré, gonflant son
   nombre de colonnes à tort (7 au lieu de 6) — la ligne de référence pour
   la position des colonnes est restreinte aux deux VRAIS totaux de page
   (Total Actif, Total Passif), jamais aux sous-totaux intermédiaires.

**Validation** (identité comptable Σ postes = Total, par section, +
identité générale Actifs nets + Capitaux propres + Passif = Total actif)
sur AL_AMANAH_TAKAFUL_2020 : Actif reconcilie EXACTEMENT (écart 0 ou 1
dinar d'arrondi sur les 6 colonnes) ; Capitaux propres et Actifs nets
reconcilient EXACTEMENT ; Passif seul montre un écart mineur (~0,1-0,2 %)
sur 5 des 6 colonnes — cause probable : une ligne au code mal concaténé
("PA76766", renvoi de note résiduel) ou une ligne manquante, pas
investiguée plus avant (l'identité GÉNÉRALE, qui est celle qui compte le
plus, reconcilie parfaitement malgré cet écart local). "Total actif" et
"Capitaux propres" recoupés EXACTEMENT avec le KPI narrow déjà validé
(`extract_al_amanah_takaful_kpis`) : 17 448 993 et 16 248 884
respectivement.

**Résultat initial** (texte réel seul) : 3/9 documents "ok".

## 2026-09-15 — AL_AMANAH_TAKAFUL : repli OCR pour les documents scannés

Retour utilisateur direct après vérification navigateur : 2023/2024/2025
ne montraient aucune donnée ("ça ne marche pas"). Diagnostic : les pages
du Bilan sont des IMAGES SCANNÉES pour ces 3 années (confirmé via
`is_scanned_page`), donc invisibles pour
`al_amanah_bilan_full_extractor.py` (texte réel uniquement) — pas un bug,
mais une portée non couverte jusque-là.

Nouveau module `extraction/al_amanah_bilan_ocr_extractor.py`, branché en
REPLI (côté par côté) dans `tableau_pipeline_service_bilan.py` quand le
texte réel ne trouve rien. Principe à DEUX passes OCR indépendantes par
ligne (même stratégie que `arabic_ocr_extractor.py::extract_cell` pour
les quelques KPI ciblés déjà existants, étendue ici à TOUTES les lignes) :

1. OCR modèle ARABE (`_ocr_lines`) pour repérer chaque ligne du tableau et
   son texte approximatif — fiable pour la PRÉSENCE/POSITION d'une ligne,
   PAS pour ses chiffres (le modèle arabe confond les chiffres, déjà
   documenté).
2. OCR modèle ANGLAIS chiffres-seuls (`ocr_row_numbers`) sur la ZONE
   NUMÉRIQUE de la même ligne (toujours à gauche du bloc de libellé, même
   mise en page que la version texte réel) pour lire les valeurs — bien
   plus fiable.

Classification des lignes par MOTIF COURT plutôt que préfixe exact : le
hamza initial de "أصل" est instable à l'OCR ("اصلق", "صل تجاري"...), donc
détecté via la présence du fragment "صل" n'importe où dans le texte
reconnu (idem "خصم"/"صافية"/"ذاتي" pour Passif/Actifs nets/Capitaux
propres) plutôt qu'un `startswith` strict.

**Numéro de code de ligne NON reconstruit** (contrairement à la version
texte réel) : le repérer fiablement demanderait une 3e passe OCR ciblée,
hors de portée raisonnable pour ce premier jet — les lignes sont
numérotées séquentiellement (AC_1, AC_2...), le libellé OCR (imparfait
mais lisible) restant la clé d'identification principale pour
l'utilisateur.

**Détection du Total** : le motif "مجموع" est lui-même parfois totalement
méconnaissable par l'OCR (ex. "مجموع الأصول" lu "امإفوعلأض ول" sur
AL_AMANAH_TAKAFUL_2023 — aucune correspondance possible, même floue).
Repli positionnel : la ligne la mieux peuplée (≥ 4 colonnes) parmi celles
qui suivent la DERNIÈRE ligne de détail classée est retenue comme Total,
sans dépendre de la reconnaissance de son libellé.

**Validation croisée** (AL_AMANAH_TAKAFUL_2023, ligne Total Actif) :
identité Entreprise + Fonds des adhérents = Combiné vérifiée EXACTEMENT
sur les 2 exercices (27 610 483 + 125 492 266 = 153 102 749 ; 25 540 570 +
112 493 110 = 138 033 680 ≈ 138 033 679, écart d'1 dinar d'arrondi) — la
même 2e passe (chiffres anglais) redonnant les valeurs correctes malgré
un OCR arabe très dégradé sur cette ligne précise.

**Limitation** : la zone numérique est bornée à la moitié gauche de la
page (seuil fixe, pas d'ancrage dynamique sur la position réelle du
bloc de libellé comme côté texte réel) — évite de capter le numéro de
code de ligne comme une fausse valeur, mais peut perdre la colonne la
plus à droite (Fonds des adhérents, exercice courant) sur certaines
lignes (constaté : Total Actif n'a que 5/6 valeurs sur 2023). Pas de
validation Σ postes = Total (dépendait des codes réglementaires réels,
absents ici).

**Résultat final** (`tableau_pipeline_service_bilan.py`, texte réel +
repli OCR, filtré sur AL_AMANAH_TAKAFUL) : **7/9 documents "ok"**
(2017, 2018, 2020, 2021, 2023, 2024, 2025), 1 "partiel" (2022, Actif
seul), 1 "page_introuvable" (2019 — format encore différent, ni texte
réel exploitable ni motif reconnu en OCR). Vérifié dans le navigateur
(Correction manuelle) sur 2023/2024/2025 : grille affichée, PDF source
ouvert à la bonne page.

## Bilan de la demande "chaque annexe utilisée pour un KPI Takaful"

Catalogue initial (5 annexes) : Bilan Combiné (1/2, déjà fait avant ce
tour), Annexe 3/4 (Surplus Familial/Général), Annexe 5.1 (État de
résultat de l'entreprise), Annexes 14/15 (Ventilation par catégorie).
**Toutes construites** au 2026-09-15. Reste hors périmètre de cette
tâche (déjà noté plus haut) : Correction manuelle UI / propagation
dashboards pour ces nouvelles clés (décision déjà prise : "Extraction +
stockage d'abord").
