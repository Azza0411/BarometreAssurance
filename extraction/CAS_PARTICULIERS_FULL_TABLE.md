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

## Couverture réelle — Annexe 13 (Non-Vie), exercice 2024, 14 sociétés testées (hors Vie-only/Takaful/PDF absent)

**8/14 OK, grille complète extraite et vraisemblance vérifiée** : ASTREE,
BH, BIAT, CARTE, COMAR, GAT, MAGHREBIA, TUNIS_RE.

**6/14 en échec, chacun diagnostiqué individuellement :**

| Société | Cause diagnostiquée | Piste |
|---|---|---|
| ATTIJARI | Le document 2024 ne contient une page "résultat technique" que côté **Vie**, aucune page Non-Vie trouvée sur les 8 premières pages — cohérent avec le commentaire déjà présent dans `api/routes/comparative.py` ("ATTIJARI 2024... aucun des 4 KPI de primes") : limite déjà connue du document source, pas de l'extraction. | Vérifier si l'annexe Non-Vie existe plus loin dans le document avant de conclure à une absence totale. |
| BNA | Aucune occurrence de "résultat technique" nulle part dans les 54 pages du document (texte natif) — cohérent avec les pages scannées déjà documentées pour BNA ailleurs dans le projet. | Repli OCR (déjà exploré pour d'autres sociétés dans `bilan_kpi_extractor.py`) — non tenté ici. |
| COTUNACE | Page trouvée (68) mais 45 "colonnes" détectées au lieu de ~16 — texte natif corrompu à la source (déjà documenté : `api/services/quality.py::PROBLEMATIC_CODES["COTUNACE"]`, "texte corrompu par un OCR de mauvaise qualité à la source"). Limite pré-existante du document, pas de ce module. | Aucune (société déjà exclue par le reste de la plateforme pour la même raison). |
| UIB | Titre de page contient un artefact d'encodage brut `(cid 4666)`/`(cid 4667)` à la place des parenthèses — casse la détection de page. | Nettoyer/ignorer les séquences `(cid N)` avant normalisation ; à vérifier si ce même artefact affecte d'autres sociétés. |
| LLOYD_TUNISIEN | La vraie page (33, confirmée manuellement — en-têtes de branches bien présents : "Acceptation, Acc R.D, Auto, Acctrav, Incendie, Transport, Grêle...") est intitulée par le document "IV.7 **Notes sur** le résultat technique par catégorie..." — exclue par `annexe13_kpi_extractor._is_target_page` via `NOTES_SECTION_RE` (`\bnotes sur\b`), une exclusion volontaire du module existant (probablement ajoutée pour écarter un autre faux positif ailleurs dans le projet). | Ne pas toucher `_is_target_page` (partagé avec le pipeline 7-KPI existant, risque de régression) — construire un prédicat parallèle, légèrement moins strict, réservé à la localisation "grille complète". |
| STAR | Page trouvée (4) mais c'est un gabarit à structure plus complexe : chaque ligne "logique" (ex. "Charges de prestations") est en réalité éclatée sur PLUSIEURS lignes visuelles portant des codes internes (`chnv2`, `chnv3`, `chnv44`...) — la fusion actuelle (`full_table_extractor.py`, fusion libellé-seul + valeurs-seules sur 1 ligne suivante) ne couvre qu'un décalage simple de 2 lignes, pas une vraie hiérarchie multi-lignes. Un seul libellé sur 18 lignes matche une regex KPI connue. | Reconnaître les préfixes de code de ligne (`ac|pa|cp|prv|prnv|chv|chnv` + chiffres, déjà définis dans `ROW_CODE_PREFIX_RE`) pour regrouper les sous-lignes d'un même poste avant extraction — chantier à part, plus proche de la logique déjà présente dans `bilan_kpi_extractor.py` pour le Bilan que de l'algorithme actuel. |

## Cas résolus en cours de route (pour mémoire)

| Cas | Symptôme | Fix |
|---|---|---|
| Ancrage d'en-tête trop strict | "exprimé en dinars tunisiens" (GAT) n'est qu'une des variantes ("chiffres arrondis en dinars" STAR, "unité en dinars" BH/BIAT...) | Ancrage relâché sur la sous-chaîne commune "en dinars" |
| GAT — faux positif page "F.2.6 Tableaux de raccordement... sont présentés au niveau de..." (prose citant le titre recherché) | Cette page de sommaire satisfaisait `_is_target_page` et produisait assez de colonnes/lignes pour paraître valide | `locate_and_extract_full_table()` essaie toutes les pages candidates et vérifie que ≥2 lignes matchent une regex KPI réellement attendue avant d'accepter |
| COMAR — ligne société/date (3 nombres : jour + mois + année) prise pour la première ligne de données | Seuil `MIN_DATA_CLUSTERS` trop bas (3) | Relevé à 4 |
| GAT — mot court "aux" ("Autres dommages **aux** biens") mal rattaché | Rattachement par centre du mot plutôt que par bord gauche (x0) | Rattachement par x0 |
| GAT — colonne "Autres" totalement vide sur la page (aucune donnée nulle part) | Mot d'en-tête sans centre de colonne déductible, disparaissait silencieusement | Réinséré comme colonne à part entière (valeurs = None) à sa position x réelle |
| STAR — libellé et valeurs d'une même ligne logique séparés en 2 lignes visuelles | `_cluster_lines` scinde parfois libellé et valeurs si leur alignement vertical diffère légèrement | Fusion d'une ligne "libellé seul" avec la ligne suivante si celle-ci est "valeurs seules" (ne couvre qu'un décalage simple — voir cas STAR non résolu ci-dessus pour la structure plus complexe restante) |

Ce fichier doit être mis à jour à chaque société/tableau diagnostiqué, comme les autres CAS_PARTICULIERS*.txt du projet. Prochaine étape naturelle une fois Annexe 13 stabilisée : appliquer le même module à Annexe 12 (Vie), puis Bilan (structure différente — Brut/Amortissement/Net, pas de branches — non couvert par l'algorithme actuel).
