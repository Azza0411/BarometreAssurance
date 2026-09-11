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

### Prochaine étape (pas encore faite)

Comme pour l'Annexe 13 : saisie manuelle vérifiée (`annexe12_verified.py`)
des documents où l'automatique échoue (page scannée, texte corrompu) —
AMI (7/9 manquants, cohérent avec les années scannées déjà identifiées côté
Annexe 13), COTUNACE/TUNIS_RE/CARTE/MAGHREBIA restants à vérifier au cas
par cas (certains sont de vrais zéros structurels, pas tous). Non entamée
dans cette session — l'audit automatique seul a déjà consommé le temps
disponible ; à reprendre sur demande.
