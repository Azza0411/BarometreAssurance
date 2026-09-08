# Cas particuliers — extraction "grille complète" (extraction/full_table_extractor.py)

Suivi des cas rencontrés en construisant l'extraction complète des tableaux
annexes (toutes lignes × toutes colonnes) — démarrée le 2026-09-08 sur
demande explicite de l'utilisateur (la page Gestion de données ne doit pas
se limiter aux 7 KPI déjà extraits pour les dashboards — voir
annexe13_kpi_extractor.py::KPI_PATTERNS).

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

**Nouveau cas identifié, non traité (gabarit distinct, pas un bug) :**

| Société/année | Constat |
|---|---|
| STAR 2023 | La page trouvée (38) est un "Tableau de raccordement du Résultat technique" à **UNE SEULE colonne de valeurs** (structure Libellé + 1 montant total), pas la grille 4 colonnes par branche des autres années. `extract_full_table()` cible spécifiquement les tableaux multi-colonnes (`MIN_DATA_CLUSTERS=4` valeurs numériques par ligne pour repérer le début des données) — une ligne de ce tableau raccordement n'a jamais que 1 valeur, donc aucune ligne de données n'est jamais détectée. Ce n'est pas un défaut de reconstruction comme le cas STAR ci-dessus : c'est un gabarit de tableau à une colonne, hors périmètre de l'algorithme actuel (conçu pour les grilles par branche). Piste pour plus tard : un chemin d'extraction séparé pour les tableaux "raccordement" à 1 colonne, plutôt que de complexifier `extract_full_table()` pour couvrir les deux formes. |

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
