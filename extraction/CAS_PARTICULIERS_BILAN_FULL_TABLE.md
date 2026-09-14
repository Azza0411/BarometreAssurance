# Bilan Actif/Passif — extraction pleine grille : suivi des cas particuliers

Symétrique de `CAS_PARTICULIERS_FULL_TABLE.md` (Annexe 12/13), pour le
tableau Bilan Actif/Passif. Voir `extraction/bilan_full_extractor.py` pour
le code et les commentaires de conception.

## 2026-09-14 — démarrage : architecture + validation sur COMAR 2023

**Pourquoi pas camelot (contrairement à Annexe 12/13)** : le tableau Bilan
n'a pas de quadrillage horizontal entre ses lignes de détail — camelot
(flavor lattice) fusionne alors toutes les lignes d'une section en une
seule cellule multi-lignes par colonne. Vérifié sur COMAR 2023 : le nombre
de lignes internes diffère d'une colonne à l'autre dès qu'une cellule est
vide sur certaines lignes (ex. colonne "Amort & Prov" : 46 lignes contre 51
pour les autres colonnes) — un zip par index désynchronise tout après la
première case blanche. `full_table_extractor.py` (le moteur camelot
d'Annexe 12/13) n'est donc pas réutilisable ici tel quel.

**Approche retenue** : reconstruction par position des mots
(`page.extract_words()` + `_cluster_lines`, primitives déjà éprouvées de
`bilan_kpi_extractor.py` pour l'extraction ciblée 5-KPI existante), pas
camelot. Chaque ligne du Bilan porte un CODE réglementaire standardisé
(AC1, AC12, PA310, CP1...) — identique chez toutes les sociétés (plan
comptable CMF) — utilisé comme clé canonique plutôt que le libellé
français (bien plus fragile, comme vu sur Annexe 12/13). Colonnes
assignées par proximité à la position x0 de l'en-tête correspondant
(Brut/Amort/Net/Net N-1 côté Actif, Net/Net N-1 côté Passif) — jamais par
ordre pur, pour ne pas décaler les valeurs suivantes quand une cellule est
vide au milieu de la ligne.

**2 bugs génériques corrigés au passage** (bénéficient aussi à l'extraction
KPI existante, pas seulement à ce nouveau module) :
1. `_words_with_bracket_negatives_resolved` (bilan_kpi_extractor.py) :
   une parenthèse contenant du texte non numérique ("(vie)", "(non vie)")
   laissait l'état "négatif en attente" actif jusqu'au PROCHAIN vrai
   nombre de la ligne, le négativant à tort (ex. AC530 "Provisions pour
   sinistres (vie)" ressortait à -810930 au lieu de 810930). Corrigé :
   l'attente est annulée dès qu'un mot alphabétique est rencontré.

**Validé sur COMAR 2023** : Actif (44 lignes codées, page 2) et Passif (26
lignes, page 3) — Σ des 6 sections de premier niveau (AC1+AC2+AC3+AC5+
AC6+AC7) = Total de l'actif EXACTEMENT (1 043 627 038), Σ des 5 sections
Passif (PA23+PA3+PA5+PA6+PA7 — recodées CP/PA selon le document) = Total
du passif EXACTEMENT (739 207 359), et Total Actif = Capitaux propres +
Total Passif EXACTEMENT. Aucun écart.

**Pas encore généralisé** : testé rapidement sur ATTIJARI/MAGHREBIA/GAT
2023 — extraction structurelle réussie (25-44 lignes trouvées) mais Σ des
sections ≠ Total sur ces 3 (mismatch), signe de variations de gabarit par
société (codes de section différents — ATTIJARI a des CP3/CP5/PA4 absents
chez COMAR — ou en-têtes de colonnes positionnés différemment) qui n'ont
PAS encore été investiguées une par une. Attendu : ce même travail
d'itération société par société qu'Annexe 12/13 a demandé sur plusieurs
sessions (voir CAS_PARTICULIERS_FULL_TABLE.md) sera nécessaire ici aussi
avant une couverture large et fiable. Pas de pipeline `process_bilan_*`
ni de branchement `tableau_pipeline_service`/route API encore écrit — le
module d'extraction est la première brique, pas encore connecté au
stockage `tableau_cellules` ni à l'UI.

**Prochaines étapes suggérées** : (1) lister les codes de section réels
observés par société (comme AC1..AC7 ne sont pas garantis universels —
ATTIJARI en est la preuve), pour bâtir une liste canonique plus complète
et une règle de validation Total robuste malgré ces variations ; (2)
écrire `normalize_table`/`validate_table` + `process_bilan_actif`/
`process_bilan_passif` sur le modèle d'`annexe13_pipeline.py` ; (3)
brancher `tableau_pipeline_service` (tableau='bilan_actif'/'bilan_passif')
et la route `/api/gestion-donnees/valider-*` correspondante ; (4) sweep
complet du portefeuille pour mesurer la couverture réelle avant tout
travail de correction cas par cas.
