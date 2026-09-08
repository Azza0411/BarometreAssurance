# Cas particuliers — extraction "grille complète" (extraction/full_table_extractor.py)

Suivi des cas rencontrés en construisant l'extraction complète des tableaux
annexes (toutes lignes × toutes colonnes par branche), démarrée le
2026-09-08 sur demande explicite de l'utilisateur (la page Gestion de
données ne doit pas se limiter aux 7 KPI déjà extraits pour les
dashboards — voir annexe13_kpi_extractor.py::KPI_PATTERNS).

## Principe validé

Colonnes déduites de la position X des VALEURS numériques des lignes de
données (fiable, une seule ligne visuelle) plutôt que des libellés d'en-tête
(souvent repliés sur 2-3 lignes visuelles). Chaque mot d'en-tête est ensuite
rattaché à la colonne la plus proche (x0), triés par position verticale pour
restituer l'ordre de lecture d'un libellé replié.

**Validé le 2026-09-08 sur GAT_2024.pdf, Annexe 13 (page 34, table "par
catégorie", 16 colonnes/branches, 21 lignes)** : toutes les valeurs
recoupées avec la capture d'écran déjà utilisée pour l'audit du Ratio
Combiné dans cette même session (Primes émises Total = 256 808 761,
Automobile = 112 362 101, etc.) — exactes au chiffre près.

## Cas résolus

| Société / cas | Problème | Solution |
|---|---|---|
| GAT — préambule confondu avec des colonnes | La ligne "Société GAT... / Annexe N°13 / titre / (exprimé en dinars tunisiens)" se mêlait aux vraies colonnes (première version, avant ancrage explicite) | Ancrage sur le marqueur "exprimé en dinars" (présent sur tous les gabarits Annexe/Bilan/Résultat rencontrés jusqu'ici) pour délimiter précisément le bloc d'en-tête |
| GAT — mot court "aux" mal rattaché ("Autres dommages **aux** biens") | Rattachement par CENTRE du mot ambigu entre 2 colonnes proches | Rattachement par x0 (bord gauche) du mot plutôt que son centre — corrige ce cas sans heuristique dédiée |
| GAT — colonne "Autres" totalement vide (aucune valeur nulle part sur la page) | Sans données, aucun centre de colonne déductible → le mot d'en-tête restait "non assigné" et disparaissait | Les mots d'en-tête non assignés sont réinsérés comme colonne à part entière (valeurs = None) à leur position x réelle |

## Cas non résolus (à reprendre)

| Société / cas | Problème | Piste envisageable |
|---|---|---|
| **Localisation de la bonne page — problème central, bloque la généralisation** | La page "Annexe 13 par catégorie" (titre + tableau réel) n'est pas la seule à contenir la phrase "par catégorie" + "non-vie" dans son texte : des pages de sommaire/notes ("F.2 Informations diverses...", "F.2.6 Tableaux de raccordement... sont présentés au niveau de...") la contiennent aussi en prose, sans être le tableau. Un ancrage strict sur le préambule "état(s) financiers au ... / Annexe N°X" en tout début de page (premiers ~120 caractères) élimine les faux positifs mais est **trop strict** : passé de "OK" sur 6 sociétés testées (ASTREE, BH, BIAT, CARTE, GAT, LLOYD_TUNISIEN) à seulement 2 (GAT, CARTE) une fois l'ancrage resserré — signe que le libellé exact du préambule varie légèrement d'une société à l'autre (ordre des mots, ponctuation...), comme documenté partout ailleurs dans CAS_PARTICULIERS*.txt pour les 7 KPI déjà extraits. | Élargir l'ancrage avec plusieurs variantes de préambule connues (comme PAGE_TITLE_RE le fait déjà pour les 7 KPI), société par société si besoin — travail itératif, pas un correctif générique unique. |
| STAR — pas de page "par catégorie" du tout pour Non-Vie | STAR (et vraisemblablement d'autres sociétés) ne publie dans son PDF que le tableau AGRÉGÉ "État de résultat technique de l'assurance Non-Vie" (4 colonnes : Opérations brutes / Cessions et/ou rétrocessions / Opérations nettes N / Opérations nettes N-1), sans détail par branche — ce n'est pas une limite de l'extraction, la donnée par branche n'existe simplement pas dans ce document source. | Traiter ce gabarit agrégé comme une variante légitime de "grille complète" pour ces sociétés (4 colonnes au lieu de 16), pas comme un échec — mais voir cas suivant, ce gabarit a son propre problème d'alignement. |
| STAR — libellé de ligne et ses valeurs sur 2 lignes visuelles distinctes | Sur le tableau agrégé 4 colonnes, `_cluster_lines` sépare parfois le libellé ("Primes acquises") et sa ligne de valeurs numériques en deux "lignes" visuelles différentes (décalage vertical > tolérance) — la ligne de libellé seule (0 valeur) et la ligne de valeurs seule (label=None) ne se recollent pas avec l'algorithme actuel, qui suppose libellé+valeurs sur la même ligne. | Fusionner une ligne sans libellé (values only) avec la ligne de libellé la plus proche juste au-dessus, si celle-ci n'a elle-même aucune valeur — même famille de correctif que `_words_with_bracket_negatives_resolved`/`_split_glued_negative` déjà présents dans bilan_kpi_extractor.py pour d'autres écarts de mise en page. |
| COMAR, COTUNACE, TUNIS_RE — page candidate trouvée mais extraction rejetée (< 6 colonnes ou < 5 lignes) | Non diagnostiqué en détail — probablement un gabarit encore différent (nombre de branches différent, ou tableau scindé sur 2 pages) | Inspecter manuellement `data/cmf/<CODE>/<CODE>_2024.pdf` à la page candidate identifiée par le scan (COMAR: 37/39, COTUNACE: 67/68, TUNIS_RE: 15/92) |
| ATTIJARI, BNA, MAGHREBIA, UIB | Aucune page candidate trouvée du tout (même le tableau agrégé n'a pas été repéré) | À investiguer — possible troisième gabarit non couvert par PAGE_TITLE_RE (annexe13_kpi_extractor.py), ou annexe simplement absente du PDF déposé cette année-là (cas déjà documenté ailleurs pour d'autres sociétés/années) |

## Couverture réelle au 2026-09-08 (Annexe 13 Non-Vie, exercice 2024, 19 sociétés conventionnelles hors Vie-only/Takaful)

- **Grille complète extraite avec confiance (16 colonnes validées) : GAT, CARTE** (2/19)
- **Page localisée mais extraction rejetée (à déboguer) : COMAR, COTUNACE, TUNIS_RE** (3/19)
- **Aucune page candidate trouvée avec l'ancrage actuel (probablement présente mais phrasée différemment, ou gabarit agrégé sans "par catégorie") : ASTREE, ATTIJARI, BH, BIAT, BNA, LLOYD_TUNISIEN, MAGHREBIA, STAR, UIB** (9/19)

Ce fichier de suivi doit être mis à jour à chaque société diagnostiquée, comme les autres CAS_PARTICULIERS*.txt du projet.
