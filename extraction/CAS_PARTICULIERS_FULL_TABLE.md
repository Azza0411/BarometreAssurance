# Cas particuliers — extraction "grille complète" (extraction/full_table_extractor.py)

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
