# FTUSA — extraction pleine grille : suivi des cas particuliers

Pendant "grille complète" (par opposition à `ftusa_kpi_extractor.py`, qui
n'extrait que 3 lignes ciblées + leur ventilation Vie/Non-Vie) pour
l'annexe "Compte d'exploitation par branche & par entreprise (Affaires
Directes & Acceptations)". Voir `extraction/ftusa_full_extractor.py` pour
le code et les commentaires de conception.

## 2026-09-14 — construction (demande utilisateur : grille complète pour les dashboards)

**Contexte différent de CMF** : un document FTUSA est UNIQUE par année,
agrégé pour le marché entier — aucune société associée (voir
`kpi_extraction_pipeline.py::_run_ftusa`). La grille produite EST
directement la donnée finale, pas une ventilation par société. Stockée
dans `tableau_cellules` sous `tableau='ftusa_branche'`, `document_id` =
celui du document FTUSA de cette année.

**Réutilise** les primitives déjà éprouvées de `ftusa_kpi_extractor.py` :
dérotation des caractères (le texte de cette annexe est tourné à 90° —
matrice de police à coefficients a=d=0, pas une rotation de page) et
détection des colonnes par ANCRE de position plutôt que par lecture
d'en-tête (l'en-tête s'étale sur 3 lignes physiques à cause du retour à
la ligne, peu fiable à parser directement) — la ligne de DONNÉES la plus
complète sert de référence, l'ordre de ses positions x0 gauche->droite
correspondant à l'ordre FIXE et connu des 12 colonnes de ce gabarit
institutionnel unique (jamais réordonné d'une année sur l'autre).

**Étendu** : les 9 colonnes déjà nommées par l'extraction KPI narrow (8
branches Non-Vie + "Ass. Vie") + les 3 colonnes de synthèse jamais
utilisées par elle ("Total (Aff. Directes)", "Acceptations", "Total
(Aff. Dir+Acc)") — 12 au total. Capture TOUTES les lignes du tableau
(~22 postes comptables, "Primes acquises" → "Solde de réassurance"), pas
seulement les 3 lignes KPI ciblées — chaque ligne devient une clé de
`tableau_cellules` nommée d'après son libellé normalisé (pas de code
réglementaire ici, contrairement à CMF/AC-PA-CP).

**Résultat mesuré** : 16/23 documents disponibles exploités (2005-2024,
quelques années manquantes : 2000, 2002, 2004, 2009, 2010, 2012, 2018 —
probablement un gabarit de page différent ces années-là, pas encore
diagnostiqué). ~22 lignes × 12 colonnes par année trouvée.

**Limite connue, non résolue** : quelques libellés de ligne sont abîmés
par un retour à la ligne du texte source qui fait déborder le numéro de
poste suivant ou un fragment du libellé précédent dans le libellé courant
(ex. "charges de prestations 104-1" au lieu de juste "charges de
prestations" ; "ncier" au lieu de "solde financier", ayant aussi perdu sa
valeur "Automobile" au passage). Cosmétique dans la plupart des cas — les
VALEURS des colonnes restent correctes pour l'immense majorité des
lignes, vérifiées manuellement contre le texte source (FTUSA 2024). Une
correspondance floue à une liste canonique de ~22 libellés (sur le modèle
d'`annexe13_pipeline.normalize_table`) résoudrait ce résidu si nécessaire
plus tard.

**Pas encore fait** : aucune règle de validation métier (pas d'identité
comptable établie côté FTUSA, contrairement à Bilan/Annexe 12/13) ;
branchement dans Correction manuelle (qui ne gère aujourd'hui que les
documents CMF société+année — ce document SANS société est un chantier
séparé, décidé explicitement avec l'utilisateur : extraction + stockage
d'abord, UI ensuite) ; diagnostic des 7 années manquantes.
