# Travaux futurs — FS Market Intelligence

Liste de travail volontairement tenue à part de la documentation technique
(`docs/documentation_technique_pfe.docx`) : ce qui reste à faire, décidé
mais pas encore construit, pour ne pas le perdre entre deux sessions.

## Pipeline dédié — Assurances islamiques (Takaful)

**Résolu (août 2026) pour 2 des 3 sociétés** : `AT_TAKAFULIA` et
`ZITOUNA_TAKAFUL` ont désormais un extracteur dédié
(`extraction/takaful_kpi_extractor.py`), réintégrées dans Qualité Data,
Analyse Comparative, Aperçu Marché et Vue par Assurance.

Investigation (voir aussi `api/services/quality.py::PROBLEMATIC_CODES`) :
les 3 sociétés Takaful ne partagent PAS un format uniforme —
- `AL_AMANAH_TAKAFUL` : documents publiés en **arabe (RTL)** — reste exclue,
  non extractible avec l'approche par position de mots utilisée ici (besoin
  d'OCR ou d'un parseur RTL dédié — non fait).
- `AT_TAKAFULIA` / `ZITOUNA_TAKAFUL` : documents en français, texte natif
  (non scanné), mais **deux formats réglementaires successifs** :
  - jusqu'à l'exercice ~2019 : structure conventionnelle (un seul jeu de
    comptes, sans distinction Fonds/Entreprise) ;
  - à partir de l'exercice ~2020 (réforme réglementaire) : "Bilan Combiné"
    à 3 colonnes par exercice (Fonds des Adhérents / Entreprise Takaful
    et/ou Rétakaful / Combiné). On retient la colonne "Entreprise" seule
    pour rester comparable aux assureurs conventionnels (le Fonds des
    Adhérents appartient aux assurés, pas à la compagnie).

**KPI extraits** : Total actif, Capitaux propres, Résultat Net, Primes
émises par assurance — sous les mêmes noms canoniques que les assureurs
conventionnels, donc le reste de l'application (KPI calculés : ROE, ROA,
Part de marché...) fonctionne sans modification. Ratio combiné / Ratio de
sinistralité restent non extraits (nécessiteraient Charges de
prestations/Charge de sinistres, pas encore extraites pour ces 2 sociétés).

**Couverture réelle (backfill août 2026)** : 15 documents/17 disponibles
(2015-2025 selon la société). Deux gaps documentés, non liés au format —
défauts du PDF source lui-même :
- `ZITOUNA_TAKAFUL_2018.pdf` : PDF scanné, aucun texte extractible.
- `ZITOUNA_TAKAFUL_2020.pdf` : encodage de police corrompu à la source
  (texte extrait illisible dès la 2e page).

Les deux nécessiteraient de l'OCR pour être récupérés — non fait, backlog.

**À faire, si repris** : extraction Arabe/RTL pour `AL_AMANAH_TAKAFUL` ; OCR
pour les 2 documents ci-dessus ; extraction Ratio combiné/sinistralité pour
compléter la couverture KPI d'AT_TAKAFULIA/ZITOUNA_TAKAFUL.

## Résolu (août 2026) — valeurs non fiables affichées sans avertissement ailleurs

**Constat** : `api/routes/comparative.py` déclarait déjà une liste des 8
sociétés problématiques (les 3 Takaful + 5 autres à souci OCR/scan) mais ne
l'appliquait jamais comme filtre — `/api/analyse-comparative` et
`/api/classement-compagnies` affichaient donc des valeurs pour ces sociétés
sans aucune indication qu'elles sont connues comme non fiables côté Qualité
Data. Un consultant pouvait voir un chiffre propre sur Analyse Comparative
ou Aperçu Marché, puis découvrir plus tard sur Qualité Data qu'il n'est pas
sûr — incohérent et pas professionnel.

**Fixé** : le filtre est maintenant réellement appliqué (et unifié avec
`quality.py::PROBLEMATIC_CODES`, une seule liste au lieu de deux copies
divergentes). `AnalyseComparative.jsx` excluait déjà ces sociétés de ses
propres graphiques côté frontend (liste `SANS_DONNEES`) — c'est la donnée
brute renvoyée par l'API qui ne suivait pas encore la même règle.
