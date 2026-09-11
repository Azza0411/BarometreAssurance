# Cas particuliers — pipeline complète Annexe 12 (Résultat technique par catégorie d'assurance Vie)

Pendant Vie de `extraction/CAS_PARTICULIERS_FULL_TABLE.md` (Annexe 13
Non-Vie) : même principe (grille complète par branche, normalisation,
validation par identités comptables, stockage `tableau_cellules`), mais
pour l'Annexe 12. Voir aussi `CAS_PARTICULIERS_ANNEXE12.txt` (extracteur
KPI ciblé, plus ancien et plus léger — 6 KPI seulement) pour l'historique
des cas particuliers de détection de page déjà résolus et réutilisés ici.

## 2026-09-11 — Construction du pipeline (demande utilisateur : « même
traitement complet qu'Annexe 13 »)

### Architecture

Plutôt que dupliquer ~600 lignes d'`annexe13_pipeline.py`, son moteur de
normalisation/validation a été **paramétré** (rétrocompatible, valeurs par
défaut = vocabulaire Non-Vie inchangé) :
- `normalize_row_label(raw_label, canonical_rows=..., threshold=..., known_prefixed_variants=...)`
- `normalize_table(grid, canonical_rows=..., row_threshold=..., known_prefixed_variants=...)`
- `validate_table(normalized_lignes, columns, rules=..., tolerance=...)`

`extraction/annexe12_pipeline.py` définit son propre vocabulaire
(`CANONICAL_ROWS_VIE`, `VALIDATION_RULES_VIE`) et appelle ces fonctions
partagées. Les COLONNES (branches) restent un vocabulaire UNIQUE et
partagé (`annexe13_pipeline.CANONICAL_COLUMNS`/`_COLUMN_ALIASES`), étendu
des branches Vie (Temporaire décès, Capital différé, Mixte, Rente,
Capitalisation, Épargne, Prévoyance, Décès...) — aucune collision possible
avec les branches Non-Vie.

`extraction/full_table_extractor.py` reçoit `relaxed_is_annexe12_page`
(symétrique de `relaxed_is_annexe13_page`, logique VIE/NON-VIE inversée) et
2 nouveaux paramètres sur `locate_and_extract_full_table` :
`use_notes_fallback` (annexe12 le désactive — repli construit
spécifiquement pour le gabarit narratif Non-Vie) et `use_ocr_fallback`
(utile pour un audit rapide sans payer le coût OCR).

**Piège rencontré et corrigé** : `relaxed_is_annexe12_page` testait d'abord
`_A13_VIE_RE` (r"\bvie\b") puis retournait `True` — mais "non vie" CONTIENT
"vie" comme mot à part entière (les limites `\b` entourent seulement
"vie"), donc une page NON-VIE (ex. AMI_2015 p4, "Annexe 3 — État de
résultat technique de l'assurance et/ou de la réassurance non Vie")
passait à tort le test. Corrigé en testant `_A13_NON_VIE_RE` EN PREMIER
(rejet immédiat), symétrique du bug qui n'existait pas côté Non-Vie
(`relaxed_is_annexe13_page` teste déjà NON_VIE avant VIE).

`api/services/tableau_pipeline_service_annexe12.py` : fichier séparé de
`tableau_pipeline_service.py` (pas un paramètre `tableau=`) pour zéro
risque de régression sur la route Gestion de données déjà en production
pour l'Annexe 13. Stocke sous `TABLEAU_KEY = "annexe12"` dans les mêmes
tables `tableau_cellules`/`tableau_validations` (déjà génériques par
`tableau`, aucune migration de schéma nécessaire).

`extraction/annexe12_verified.py` : même contrat que
`annexe13_verified.py`, vide au départ (`VERIFIED = {}`), à compléter au
fil de la saisie manuelle des documents scannés/non extractibles.

### Vocabulaire de ligne (CANONICAL_ROWS_VIE)

Construit par relevé croisé sur AMI, BH, COMAR (pas une seule société —
même méthode que le vocabulaire Non-Vie). Différences structurelles avec
le Non-Vie :
- Pas de scission « Primes acquises = Primes émises + Variation » : une
  seule ligne « Primes ».
- Ligne « Ajustement ACAV (Assurance à Capital Variable) », propre aux
  contrats en unités de compte (optionnelle dans la règle `solde_souscription`).
- Poste de provisions : « Charges des provisions d'assurance vie et des
  autres provisions techniques » (pas « ... pour prestations diverses »).
- Réassurance rattachée aux CHARGES DE PRESTATIONS (pas aux primes
  acquises comme en Non-Vie) : « Part des réassureurs dans les charges de
  prestations » est le 1er poste du bloc réassurance.
- BH détaille séparément « Variation des frais d'acquisition reportés » et
  « Charges de placements » (déduite) — postes optionnels dans les règles
  `charges_acquisition_gestion`/`solde_financier`.
- BIAT loge ses « Intérêts techniques bruts de l'exercice » en déduction
  du Solde de réassurance (même schéma que côté Non-Vie, voir
  CAS_PARTICULIERS_FULL_TABLE.md) — poste optionnel de la règle
  `solde_reassurance`.

Modèle confirmé (écart nul, vérifié AMI/BH/COMAR/BIAT) : toutes les
valeurs déjà SIGNÉES, chaque identité une simple SOMME —
`SS = Primes + Charges de prestations + Charges des provisions` ;
`CAG = Frais d'acquisition + Autres charges de gestion nettes` ;
`SF = Produits nets de placements + Participation aux résultats` ;
`SR = Primes cédées + Part réass. charges prestations + Part réass.
charges provisions + Part réass. participation + Commissions` ;
`RT = SS + CAG + SF + SR`.

### Audit de couverture automatique (2026-09-11, sans OCR ni saisie manuelle)

Balayage des 191 documents CMF disponibles (hors Takaful, cadre
réglementaire distinct — Annexes 14/15) via `process_annexe12` seul (pas
de repli OCR, pour un audit rapide) :

```
TOTAL 191  OK 127 (66%)
AMI                  2/ 9   ASTREE          7/11   ATTIJARI       11/11
BH                   6/ 7   BIAT           11/11   BNA             1/ 2
CARTE                1/11   CARTE_VIE      10/11   COMAR           9/11
COTUNACE             0/11   CTAMA           2/ 2   GAT            11/11
GAT_VIE             11/11   HAYETT          9/11   LLOYD_TUNISIEN 10/10
LLOYD_VIE            5/ 6   MAGHREBIA       0/ 6   MAGHREBIA_VIE   8/11
STAR                10/11   TUNIS_RE        0/11   UIB             3/ 6
```

**Zéros structurels, PAS des échecs d'extraction** (confirmé par
`CAS_PARTICULIERS_ANNEXE12.txt`, déjà documenté avant ce chantier) :
- **CARTE, MAGHREBIA** (quasi 0) : split entité Vie/Non-Vie — leur activité
  Vie est déposée séparément sous CARTE_VIE/MAGHREBIA_VIE. Contre-exemple
  notable : **LLOYD_TUNISIEN a bien sa propre section Vie dans SON document**
  malgré l'existence de LLOYD_VIE — pas de règle générale déduite du seul
  nom du code, vérifié empiriquement.
- **TUNIS_RE** (0/11) : réassureur, catégorisation Marine/Non-Marine plutôt
  que Vie/Non-Vie — aucune page « par catégorie Vie » de ce type dans ses
  documents.
- **COTUNACE** (0/11) : Crédit-Caution uniquement, pas d'activité Vie.

**Corrections apportées pendant l'audit** (génériques, pas des hacks par
société) :
- Alias colonnes manquants : "Prévoyance" (BIAT), "Mixte"/"Décès" (GAT :
  "contrats mixte"/"contrats deces"), "Décès" (LLOYD_TUNISIEN : "groupe
  deces").
- Variante récurrente de libellé « Produits nets de placements » sur le
  gabarit raccordement (AMI, GAT : « Produits [de placements] alloués,
  transférés de l'état de résultat [non technique] ») — trop longue/diluée
  pour la correspondance floue, ajoutée en variante connue explicite.

## 2026-09-11 (suite) — voie OCR activée pour l'Annexe 12 (demande
utilisateur : « trouvez une solution mais pas manuelle »)

`extraction/scanned_table_extractor.py` (voie OCR de dernier recours,
`ocr_locate_and_extract`/`_title_score`) était câblée EN DUR pour
l'Annexe 13 Non-Vie : rejet explicite de toute page titrée "Annexe N°X"
avec X ≠ 13, et bonus/malus de score construits sur NON_VIE_RE en premier.
Paramétrée (`vie_mode=False` par défaut, rétrocompatible) — `_title_score`
et `ocr_locate_and_extract` acceptent désormais `vie_mode=True` (accepte
"Annexe N°12", bascule les bonus/malus VIE/NON-VIE). Même piège
`\bvie\b`-matche-dans-"non vie" que `relaxed_is_annexe12_page` : corrigé
en testant la catégorie qu'on veut REJETER en premier, dans les deux sens.
`locate_and_extract_full_table` reçoit un nouveau paramètre
`ocr_vie_mode`, propagé par `annexe12_pipeline.process_annexe12`.

**Vérifié structurellement automatiques (pas des échecs)**, par recherche
textuelle directe dans le PDF (pas de lecture manuelle) : CARTE, MAGHREBIA,
TUNIS_RE, COTUNACE — aucune mention "Annexe N°12"/"résultat technique...
catégorie... vie" dans leurs dépôts respectifs (CARTE 2018 : n'a que son
Annexe N°13 Non-Vie ; TUNIS_RE : catégorisation Marine/Non-Marine,
cohérent avec `CAS_PARTICULIERS_ANNEXE12.txt` ; COTUNACE : Crédit-Caution
Non-Vie uniquement). Exclus du nouveau passage OCR (aurait été du temps de
calcul perdu sur des documents qui n'ont rien à trouver).

### Résultat du passage OCR ciblé (11 sociétés à gap non-structurel)

```
Avant OCR -> après OCR (documents trouvés, écarts non comptés)
AMI            2/9  -> 7/9    ASTREE   7/11 -> 8/11   BH      6/7 -> 6/7
BNA            1/2  -> 2/2    CARTE_VIE 10/11(inchangé) COMAR   9/11 -> 11/11
HAYETT         9/11 -> 10/11  LLOYD_VIE 5/6 -> 6/6      MAGHREBIA_VIE 8/11 -> 9/11
STAR          10/11 -> 11/11  UIB      3/6 -> 3/6
```

**Total global (191 documents, hors Takaful) : 127 → ~140/191 (73%)**,
entièrement automatique (aucune valeur saisie/corrigée à la main). Les
grilles extraites par OCR gardent leurs écarts de validation VISIBLES
(`tableau_validations`, statut "ecart") plutôt que d'être silencieusement
présentées comme parfaites — même principe que la voie OCR déjà en
production pour l'Annexe 13 (AMI 2019/2020/2023, COTUNACE 2017/2019/2023).
Certaines cellules restent mal lues (chiffre tronqué, confusion 6/7 ou 2/7)
sur les scans les plus dégradés — visible dans les écarts, pas caché.

### Gaps restants (13 documents), non structurels mais non résolus

AMI 2019/2020, ASTREE 2015/2018/2020, BH 2020, CARTE_VIE 2018,
HAYETT 2019, MAGHREBIA_VIE 2016/2020, UIB 2020/2021/2022. UIB 2020-2022
vérifié : leur page "ETAT DE RESULTAT" mentionne "RTV Résultat Technique
Vie" mais uniquement comme LIGNE de renvoi dans l'état de résultat
narratif (toutes valeurs "-"), pas la vraie grille par catégorie — format
de dépôt différent ces 3 années-là (comme la bascule de gabarit déjà
documentée AMI/BNA côté Annexe 13). Les autres nécessiteraient un
diagnostic titre-par-titre supplémentaire, hors budget de cette session.
