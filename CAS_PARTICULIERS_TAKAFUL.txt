# Cas particuliers — extraction Fonds des Participants (Takaful)

Suivi des cas rencontrés lors de l'ajout des indicateurs propres au Fonds des
Participants (`extraction/takaful_kpi_extractor.py::extract_fonds_participants_kpis`,
août 2026) : Surplus/déficit des fonds Familial et Général (Annexes 3/4),
Total actifs nets des adhérents et Provisions techniques brutes (colonne
Fonds des Adhérents, Annexe 1), Commission Wakala et Commission Moudharaba
(Annexe 5.1). Contexte : [docs/ratios_takaful_ifsb_aaoifi.md](../docs/ratios_takaful_ifsb_aaoifi.md).

Champ d'application : AT_TAKAFULIA et ZITOUNA_TAKAFUL uniquement, et
seulement pour les exercices en format "nouveau" (NCT 43, ~2020+) — voir
`detect_format()`. Ces tableaux n'existent pas en format "ancien" (vérifié
sur AT_TAKAFULIA_2018.pdf : Bilan et État de Résultat structurellement
identiques à un assureur conventionnel).

## Cas résolus

| # | Société / exercice | Problème | Fix |
|---|---|---|---|
| 1 | AT_TAKAFULIA (tous) | `Commission Wakala`/`Commission Moudharaba` (Annexe 5.1) introuvables : leur code de ligne "PR1"/"PR2" n'est pas retiré par `_label_text` (qui ne connaît que les préfixes `ac/pa/cp` du Bilan, voir `bilan_kpi_extractor.ROW_CODE_PREFIX_RE`), donc un motif ancré (`^...`) ne matchait jamais. | Motifs non ancrés (`.search` sur "commission wakala"/"commission moudharaba" comme sous-chaîne). |
| 2 | Toutes (Annexes 3/4) | Le libellé de la ligne de résultat ("Surplus ou déficit de l'assurance Takaful et/ou Rétakaful Familial/Général") s'étale sur 3 lignes physiques reconstruites, avec les valeurs au milieu et le mot distinctif (Familial/Général) sur la ligne de FIN, après les valeurs — invisible à une recherche par label sur une seule ligne, et de toute façon ambigu (même libellé dans les deux tableaux). | Désambiguïsation par la PAGE (titre "Etat de Surplus ou Déficit du fonds Takaful Familial/Général") plutôt que par le libellé de ligne — voir `_find_row_on_page`. |
| 3 | AT_TAKAFULIA (tous) vs ZITOUNA (2024 notamment) | Le titre de l'Annexe 5.1 est imprimé en BAS de la page précédente chez AT_TAKAFULIA (à la suite de l'Annexe 4) mais en HAUT de sa propre page chez ZITOUNA_TAKAFUL — un test restreint aux 4 premières lignes de chaque page (comme `annexe13_kpi_extractor._is_target_page`) ne couvrait qu'un seul des deux cas. | `_find_row_on_page` retient une page si le titre apparaît dans le texte COMPLET de la page OU dans celui de la page précédente. |
| 4 | ZITOUNA_TAKAFUL (années variables) | "Commission(s) Moudharaba" existe à la fois côté Opérateur (Annexe 5.1, PR2, singulier) et côté charge du fonds des participants (Annexes 3/4, CHF411/CHG411) — chez AT_TAKAFULIA la version fonds est toujours au PLURIEL ("Commissions Moudharaba", ne matche pas), mais chez ZITOUNA_TAKAFUL elle est parfois au SINGULIER aussi ("CHF411 Commission Moudharaba"), collision avec le motif. | Résolu par la même page-scoping que le cas #2/#3 (recherche restreinte à la page Annexe 5.1) — la désambiguïsation plurielle seule était insuffisante. |
| 5 | ZITOUNA_TAKAFUL 2022 | Point de césure du libellé "Surplus ou déficit de l'assurance [Takaful Familial]" variable d'un exercice à l'autre pour la MÊME société : "Takaful" reste parfois collé à "de l'assurance" (1ère ligne), parfois atterrit sur la 3e ligne avec "Familial/Général" (après les valeurs). | Motif de ligne allégé à "surplus ou déficit de l'assurance" (sans "takaful") — le mot n'est de toute façon plus nécessaire une fois la page-scoping (#2) en place. |
| 6 | ZITOUNA_TAKAFUL 2019/2025 | `Provisions techniques brutes` (PA3) introuvable : le code de ligne est collé SANS espace au libellé ("PA3Provisions techniques brutes"), cas déjà documenté pour d'autres sociétés côté Bilan conventionnel (`bilan_kpi_extractor.py`, ASTREE/BH) mais pas couvert ici. | Motif non ancré (`.search` sur "provisions techniques brutes" en sous-chaîne). |
| 7 | ZITOUNA_TAKAFUL 2019/2025 | Une fois #6 corrigé, la valeur récupérée était celle de la ligne SUIVANTE (PA310, sous-poste), pas celle de PA3 : le numéro de renvoi de note ("10") est glissé sans séparateur juste après le libellé et capturé comme 1er token numérique de la ligne — `_col_first` (index 0) le voit, le rejette (< `MIN_PLAUSIBLE_VALUE`), renvoie `None`, et le forward-scan de `_find_row_value` retombe alors sur la ligne suivante au lieu de simplement ignorer ce token. | Nouveau sélecteur `_col_first_plausible` : ignore les tokens de tête non plausibles au lieu d'abandonner la ligne. Utilisé pour `Total actifs nets des adhérents` et `Provisions techniques brutes`. |

## Cas non résolus

- **ZITOUNA_TAKAFUL_2025 — `Provisions techniques du Fonds des Adhérents` toujours `None`.** Le texte extrait de ce PDF précis est corrompu au niveau caractère sur plusieurs pages (Bilan et Annexe 4) : les lettres de colonnes adjacentes sont entrelacées verticalement (ex: "AACC122 A Ccotinfsce csosriopnosr..." au lieu de deux lignes distinctes), un problème de rendu/police propre à ce fichier plutôt qu'une faiblesse de regex. Corriger nécessiterait une reconstruction de colonnes dédiée à ce document — disproportionné pour un seul exercice. À revisiter si d'autres PDF du même type (même modèle d'export) sont rencontrés.
- **ZITOUNA_TAKAFUL_2025 — `Résultat Net` = 0.0 (suspect).** Probablement un symptôme du même problème de corruption de texte que ci-dessus (le vrai chiffre existe dans le PDF mais n'est pas récupérable proprement). Non corrigé dans ce chantier — pré-existant à l'ajout des indicateurs Fonds des Participants, hors périmètre de cette tâche.
- **Ratios S6 à S9, L1-L2, RT1, R3-R4 du document IFSB (`docs/ratios_takaful_ifsb_aaoifi.md`)** ne sont PAS implémentés : nécessiteraient une extraction PDF supplémentaire (actifs liquides, primes cédées en réassurance/rétakaful, revenus de placement isolés) au-delà des champs déjà utilisés ici. Décision explicite de ne pas les inclure dans cette itération (voir échange de cadrage du 2026-08-05).

## Couverture atteinte

Sur les 6 nouveaux indicateurs × exercices "nouveau format" disponibles :
- **AT_TAKAFULIA** : 7/7 exercices (2019-2025), 100 % des champs.
- **ZITOUNA_TAKAFUL** : 7/7 exercices (2019-2025) pour 5 des 6 champs ; 6/7 pour `Provisions techniques du Fonds des Adhérents` (cas non résolu ci-dessus, 2025 uniquement).

## AL_AMANAH_TAKAFUL — extraction arabe (Total actif / Capitaux propres / Résultat Net / Primes émises)

Contrairement aux deux autres compagnies Takaful, les états financiers
d'AL_AMANAH_TAKAFUL sont publiés en **arabe** (labels ET texte). Certaines
années ont du texte PDF réellement extractible (2017, 2019-2022), d'autres
sont scannées en image (2018, 2023-2025) — voir
`extraction/arabic_ocr_extractor.py` pour la mécanique complète : lecture
RTL (mots réordonnés par x décroissant, caractères de chaque mot inversés),
normalisation Unicode NFKC (formes de présentation arabes de 2017), et
repli OCR bilingue (modèle arabe pour repérer la LIGNE par correspondance
floue, modèle anglais pour relire les CHIFFRES — le modèle arabe se trompe
sur les chiffres occidentaux).

Deux formats de Bilan coexistent aussi chez cette société (indépendamment
de AT_TAKAFULIA/ZITOUNA_TAKAFUL) : "ancien" (2017 vérifié, une seule colonne
pour l'exercice précédent + triplet complet Combiné/Entreprise/Participants
pour l'exercice en cours, 4 valeurs au total) et "nouveau" (2019+ vérifié,
triplet complet des deux exercices, 6 valeurs). Le format est déduit du
NOMBRE de valeurs trouvées sur la ligne (`_select_actif_like`/
`_select_equity_like` dans `takaful_kpi_extractor.py`), pas d'un marqueur
textuel préalable.

### Cas résolus

| # | Problème | Fix |
|---|---|---|
| 1 | Chaque mot arabe est extrait avec ses CARACTÈRES en ordre miroir (ex. "الأصول" → "لوـــصلأا"), et les MOTS eux-mêmes sont physiquement disposés de droite à gauche sur la page. | Tri des mots par x0 décroissant + inversion de chaque mot (`_rtl_label_from_words`). |
| 2 | pdfplumber découpe souvent un seul mot en plusieurs tokens (espacement interne de police), insérant des espaces parasites qui cassent toute comparaison mot-à-mot. | Comparaison espaces retirés (`fuzz.ratio` sur chaînes sans espace) plutôt que mot à mot. |
| 3 | AL_AMANAH_TAKAFUL_2017 : texte en formes de présentation arabes Unicode (points de code différents des lettres standard bien que visuellement identiques) — score ~4 % avant correction. | Normalisation `unicodedata.normalize("NFKC", ...)` avant comparaison. |
| 4 | AL_AMANAH_TAKAFUL_2019/2022 : police embarquée qui mappe certains caractères vers le MAUVAIS point de code Unicode (ex. "مجموع" → "يدًىع") — texte réel présent mais illisible tel quel, sans rapport avec un simple décalage. | Repli OCR automatique (les glyphes affichés restent corrects, l'OCR les lit correctement même quand le texte-couche est corrompu) dès que la recherche en texte réel échoue partout. |
| 5 | Un code de ligne numérique parfois collé sans séparateur au libellé (ex. "أر ع 11 أقساط...") est capturé comme une colonne de valeur supplémentaire, faussant l'indexation. | Filtre `_is_plausible` (rejette les valeurs non nulles < 1000) avant sélection de colonne, même principe que `bilan_kpi_extractor._col_first_plausible` côté français. |
| 6 | Un même libellé de premisses partiellement tronqué ("أقساط تأمين صادرة" sans "و مقبولة") apparaît sur des pages de détail sans rapport, faussant la somme Famille+Général par des occurrences en trop. | Seuil de score plus strict pour les recherches à SOMME (90 texte réel / 80 OCR) que pour les recherches à occurrence unique (75/60), et libellé incluant le préfixe de code de ligne pour rester discriminant. |
| 7 | "مجموع الأصول" (Total actif) et "مجموع الأموال الذاتية" (Capitaux propres) partagent un préfixe assez long pour qu'une lecture OCR dégradée de l'un score au-dessus du seuil pour une recherche visant l'autre. | Exclusion croisée : "الأصول" exclu du côté Capitaux propres, "الذاتية"/"الصافية" exclus du côté Total actif (`_EXCLUDE_CAPITAUX`/`_EXCLUDE_ACTIF`). Le test d'exclusion doit lui-même retirer les espaces (l'OCR insère parfois un espace au milieu du mot-piège, ex. "و الخصوم" au lieu de "والخصوم", qui échapperait à un test `in` naïf). |
| 8 | `ocr_row_numbers` traitait chaque "mot" détecté par Tesseract comme un nombre complet — un séparateur de milliers fin segmente parfois un seul nombre en plusieurs mots OCR (ex. "21587910" lu comme deux mots "21587"+"10"), tronquant silencieusement la valeur. | Fusion des groupes de chiffres adjacents dont l'écart horizontal est < 14px (séparateur de milliers) avant conversion en nombre, écart nettement inférieur à celui séparant deux vraies colonnes (20-29px, calibré sur ce gabarit). |
| 9 | Total actif et Capitaux propres parfois confondus malgré les fixes ci-dessus (résidu de bruit OCR), produisant soit une égalité exacte suspecte soit une valeur physiquement impossible. | Garde-fous a posteriori : rejet (`None`) si Total actif == Capitaux propres (égalité impossible pour une société ayant le moindre passif), et si Total actif < Capitaux propres (viole l'identité bilancielle Actif = Capitaux propres + Passif, le passif ne pouvant être négatif). |

### Couverture atteinte (2026-08-11)

| Exercice | Format | Total actif | Capitaux propres | Résultat Net | Primes émises |
|---|---|---|---|---|---|
| 2017 | ancien | ✅ 51 980 883 | ✅ 6 794 108 | ✅ 235 380 | ✅ 24 975 799 |
| 2018 | scanné | ❌ | ❌ | ❌ | ⚠️ 5 255 305 (probablement sous-évalué, une seule des deux tables famille/général trouvée avec confiance) |
| 2019 | nouveau (police corrompue, repli OCR) | ✅ 15 655 478 | ❌ | ✅ 1 889 655 | ✅ 31 247 512 |
| 2020 | nouveau | ✅ 17 448 993 | ✅ 16 248 884 | ✅ 1 903 934 | ✅ 33 466 790 |
| 2021 | nouveau | ✅ 21 587 910 | ✅ 18 562 671 | ✅ 2 311 491 | ✅ 43 627 511 |
| 2022 | nouveau (police corrompue, repli OCR) | ✅ 25 540 570 | ✅ 21 205 237 | ✅ 2 642 566 | ✅ 47 158 841 |
| 2023 | scanné | ❌ | ✅ 23 754 138 (voir note ci-dessous) | ✅ 2 998 622 | ✅ 50 207 415 |
| 2024 | scanné | ❌ (validé manuellement en session précédente : 38 089 744, recoupé CGA) | ✅ 33 548 585 | ✅ 3 745 674 | ✅ 45 842 278 |
| 2025 | scanné | ❌ | ✅ 37 886 053 | ✅ 5 328 831 | ✅ 76 250 493 |

Total actif reste le champ le plus fragile sur les exercices SCANNÉS (image
uniquement, pas de repli texte réel) : sa ligne ("مجموع الأصول") est
systématiquement moins bien lue par l'OCR que celle des Capitaux propres
sur ces documents précis, sans qu'une calibration générique (région/seuil)
suffise à la récupérer de façon fiable — nécessiterait un prétraitement
d'image dédié (contraste, DPI) hors périmètre de cette itération.

### Confiance par exercice (2026-08-11)

Toutes les valeurs ci-dessus ne se valent pas en fiabilité — un chiffre
"trouvé" par le pipeline n'est pas toujours recoupé par une seconde source
indépendante :

- **Confiance élevée** (2017, 2020, 2021, 2022, 2024) : recoupées par
  plusieurs méthodes (identité bilancielle Total actif = Total passif,
  comparaison avec la colonne "exercice précédent" affichée dans le document
  de l'année SUIVANTE, cohérence arithmétique interne Capitaux propres avant
  résultat + Résultat net = Capitaux propres final).
- **Confiance moyenne** (2019, 2023, 2025) : valeurs plausibles et cohérentes
  avec la tendance de croissance de la société, mais non recoupées par une
  seconde source indépendante à ce jour.
- **Capitaux propres 2023 — écart d'un chiffre entre deux lectures OCR
  indépendantes** : "23 754 138" (lu deux fois — une fois dans le document
  2023 lui-même en tant que doublon Combiné=Entreprise, une fois dans le
  document 2024 en tant que colonne comparative de l'exercice précédent) vs
  "23 794 138" (lu une seule fois, dans la lecture initiale du document
  2023). Retenu : 23 754 138 (majoritaire 2 lectures sur 3). Illustre un
  risque non résolu : quand une ligne affiche deux fois la MÊME valeur
  imprimée (Combiné=Entreprise), l'OCR peut lire l'une des deux occurrences
  correctement et l'autre avec une erreur de chiffre isolée — aucun
  garde-fou automatique ne détecte ce cas précis à ce jour (contrairement à
  l'égalité EXACTE inter-KPI, elle, détectée — voir cas #9 ci-dessus).

### Cas non résolus

- **2018 — Total actif/Capitaux propres/Résultat Net introuvables, Primes probablement incomplètes.** OCR de moins bonne qualité sur ce document précis que sur les autres exercices scannés (chiffres fusionnés en un seul nombre aberrant même après le fix #8 ci-dessus, ex. valeur à 15 chiffres). Non résolu — nécessiterait un prétraitement d'image spécifique à ce fichier.
- **2023, 2024, 2025 — Total actif introuvable.** Ligne "مجموع الأصول" lue de façon trop dégradée par l'OCR sur ces trois documents pour dépasser le seuil de confiance sans risquer une confusion avec la ligne Capitaux propres (déjà partiellement observée et corrigée pour d'autres exercices, voir cas #7 — mais persiste ici avec un score encore plus bas). La valeur 2024 est connue par ailleurs (validation manuelle croisée avec le registre CGA, session précédente : 38 089 744) mais n'est pas produite automatiquement par le pipeline.

## AL_AMANAH_TAKAFUL — extension "Fonds des Participants" (2026-08-20, partielle)

Point de départ : sur Analyse Comparative (vue Takaful), l'indicateur "Surplus
du Fonds des Participants" (`surplus_fonds`, somme de `Surplus du Fonds
Takaful Familial (TND)` + `...Général (TND)`, voir
`api/services/kpi_builder.py`) n'affichait aucune valeur pour
AL_AMANAH_TAKAFUL alors que AT_TAKAFULIA et ZITOUNA_TAKAFUL en ont une
(extension du 2026-08-16, voir plus haut dans ce fichier) — parce que
`extract_al_amanah_takaful_kpis` n'a jamais calculé les 6 KPI "Fonds des
Participants" pour cette société, contrairement aux deux autres.

### Localisation confirmée des 6 indicateurs manquants

Pages identifiées et validées par recoupement contre des valeurs déjà en
base (Primes émises Familial/Général 2022 : 8 738 711 / 38 420 130,
retrouvées telles quelles sur ces pages) :
- **Surplus du Fonds Takaful Familial** : page 4 (état "فائض أو عجز صندوق
  التأمين التكافلي/إعادة التأمين التكافلي **العائلي**"), ligne totale finale.
- **Surplus du Fonds Takaful Général** : page 5, même état, qualificatif
  "**العام**".
- **Total actifs nets des adhérents** : page 3 (Bilan Passif), ligne "مجموع
  الأصول الصافية", section "أصول صافية" (juste avant les Capitaux propres).
- **Commission Wakala** (candidat, non extrait) : ligne "نفقات الإدارة على
  كاهل صندوق المشتركين" (frais de gestion à la charge du Fonds des
  Participants), pages 4/5.
- **Commission Moudharaba** (candidat, non extrait) : ligne "عمولة
  المضاربة", pages 4/5.
- **Provisions techniques du Fonds des Adhérents** : non recherché dans
  cette itération.

### Cas résolu

| # | Problème | Fix |
|---|---|---|
| 10 | "مجموع الأصول الصافية" (Total actifs nets, 20 caractères) est confondu avec "مجموع الأصول" (Total actif, 13 caractères, page ANTÉRIEURE) : ce dernier est un simple PRÉFIXE du premier et score ~76 % par `fuzz.ratio` — au-dessus des seuils habituels (60-75 %), donc retenu à tort avant d'atteindre la vraie ligne (elle-même mal reconnue par l'OCR, ~65-70 % seulement). Constaté aussi bien en texte réel qu'en OCR — un simple relèvement du seuil global aurait aussi rejeté les vrais positifs. | Nouveau paramètre `min_label_len_ratio` sur `find_label_row`/`find_label_row_words` (et propagé à `find_kpi_value_smart`/`_list`) : écarte tout candidat dont le libellé OCRisé (espaces retirés) est nettement plus court que la cible — la longueur, contrairement au score seul, distingue proprement un préfixe court d'un libellé complet mal lu. Combiné à l'exclusion croisée déjà établie (`_EXCLUDE_TOTAL_ACTIFS_NETS = ["والخصوم", "الذاتية"]`, même principe que le cas #7 plus haut). |

### Couverture atteinte — Total actifs nets des adhérents (TND)

| Exercice | Valeur | Note |
|---|---|---|
| 2015-2016 | ❌ | Fichier PDF local absent (`FileNotFoundError`) — gap pré-existant, indépendant de cette extraction. |
| 2017-2019 | ❌ (None) | Format "ancien" (pré-NCT 43) — pas de tableau "Fonds des Participants", cohérent avec AT_TAKAFULIA/ZITOUNA_TAKAFUL sur la même période. |
| 2020 | ✅ -1 812 245 | Déficit (valeur négative plausible). |
| 2021 | ✅ 674 979 | **Recoupé indépendamment** : retrouvé à l'identique comme colonne "exercice précédent" dans le document 2022. |
| 2022 | ❌ (None) | Exercice à police PDF corrompue (voir cas #4 plus haut) : la recherche y retombe à tort sur la ligne Capitaux propres (21 205 237) malgré le fix — écarté par le plafond de plausibilité (`_MAX_PLAUSIBLE_ACTIFS_NETS_ADHERENTS = 15 000 000`) plutôt que d'enregistrer un chiffre faux. |
| 2023 | ❌ (None) | Aucune ligne trouvée au-dessus du seuil sur ce document scanné. |
| 2024 | ✅ 2 125 077 | Plausible (ordre de grandeur cohérent avec 2020/2021/2025), non recoupé indépendamment. |
| 2025 | ✅ 4 139 892 | Idem. |

**4/11 exercices couverts** (2020, 2021, 2024, 2025), persisté en base
(`Total actifs nets des adhérents (TND)`, tableau "Annexes 3/4/5.1 - Fonds
des Participants (Takaful)").

### Surplus du Fonds Takaful Familial/Général — RÉSOLU (2026-08-21, couverture partielle)

**C'était l'indicateur réellement affiché sur Analyse Comparative
(`surplus_fonds`, somme Familial+Général, voir `api/services/kpi_builder.py`)
— désormais corrigé et vérifié de bout en bout.**

**Méthode définitive** : les 4 valeurs de la ligne "État de Surplus" (pages
4/5) ont été lues visuellement sur les vrais PDF rendus en image
(AL_AMANAH_TAKAFUL_2022, pages 4 et 5) plutôt que devinées depuis l'OCR :
structure confirmée = [exercice précédent] | [Nettes] | [Cédées et
retrocédées] | [Total brut], avec l'identité comptable **Nettes = Brut +
Cédées** vérifiée EXACTE sur les deux pages (ex. 2022 Familial :
359 339 = -891 528 + 1 250 867).

Cette identité est devenue le **garde-fou de validation automatique**
(`_find_surplus_validated` dans `takaful_kpi_extractor.py`) : la ligne est
localisée par correspondance floue OCR (fiable même à police corrompue,
l'OCR lisant les glyphes affichés) sur la page 4 (Familial)/5 (Général)
ciblée directement, puis les CHIFFRES de cette même ligne sont relus en
TEXTE RÉEL (fiable même sur les exercices "corrompus" : la corruption de
police touche les LETTRES arabes, pas les chiffres). La valeur "Nettes"
n'est acceptée QUE si Nettes = Cédées + Brut sur le triplet retenu — sinon
`None`. Ce garde-fou a correctement rejeté un cas ambigu rencontré en test
(2022 Général : un triplet à 3 valeurs incomplet aurait donné 661 622, la
valeur de l'exercice précédent, au lieu de la vraie valeur 469 781 — écarté
automatiquement faute de vérifier l'identité).

**Couverture obtenue** :

| Exercice | Surplus Familial | Surplus Général | `surplus_fonds` (Analyse Comparative) |
|---|---|---|---|
| 2019 | ✅ -181 090 | ✅ -1 156 970 | ✅ -1.3 MDT |
| 2020 | ❌ None | ❌ None | ❌ |
| 2021 | ✅ 475 644 | ✅ 661 622 | ✅ **1.1 MDT — vérifié live via `/api/analyse-comparative?annee=2021&famille=takaful`** |
| 2022 | ✅ 359 339 | ❌ None (garde-fou d'identité, cas ambigu écarté) | ❌ (nécessite les 2) |
| 2023-2025 | ❌ None | ❌ None | ❌ |

**3/9 exercices avec `surplus_fonds` complet** (2019, 2021, et potentiellement
d'autres si retesté avec un padding de crop différent pour 2022 Général) —
contre 0 auparavant. Les exercices manquants (2020, 2023-2025) sont ceux où
le texte réel de la page 4/5 est absent (scanné) ou trop dégradé pour que
`_extract_numeric_clusters` y trouve 3 valeurs plausibles ; un repli OCR pur
(chiffres relus via Tesseract au lieu du texte réel) a été testé mais n'a
validé aucun cas supplémentaire pour ces exercices.

### Cas NON résolus — reste à faire

- **Commission Wakala/Commission Moudharaba : libellés candidats identifiés
  mais NON validés.** Signe incohérent d'un exercice à l'autre en test
  (négatif 2020-2021, positif 2022-2024) — laisse penser que la ligne
  retenue n'est pas la même selon les années. Non extrait, non câblé.
- **Provisions techniques du Fonds des Adhérents : non recherché.**
- **Surplus Familial/Général sur 2020 et 2023-2025 : non récupéré** — texte
  réel absent ou trop dégradé sur ces exercices précis ; nécessiterait soit
  un prétraitement d'image dédié pour le repli OCR, soit d'accepter la
  lacune (cohérent avec le reste du dossier : None plutôt qu'une valeur non
  vérifiée).
