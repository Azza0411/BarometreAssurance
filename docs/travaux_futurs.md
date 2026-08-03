# Travaux futurs — FS Market Intelligence

Liste de travail volontairement tenue à part de la documentation technique
(`docs/documentation_technique_pfe.docx`) : ce qui reste à faire, décidé
mais pas encore construit, pour ne pas le perdre entre deux sessions.

## Pipeline dédié — Assurances islamiques (Takaful)

**Constat (août 2026)** : 3 sociétés (`AL_AMANAH_TAKAFUL`, `AT_TAKAFULIA`,
`ZITOUNA_TAKAFUL`) publient un bilan structuré différemment du modèle
standard — comptes « Fonds des Adhérents » et « Entreprise » séparés,
au lieu d'un bilan unique. Le pipeline d'extraction actuel (Bilan, Annexe
12/13, État de résultat) suppose la structure standard : pour ces 3
sociétés, quasi tout ressort "non extrait"/"non calculé", ce qui n'est pas
une anomalie de leur part mais un pipeline qui ne les couvre pas encore.

**Décision** : retirées de l'affichage de la page Qualité Data (elles
polluaient la vue en mélangeant "vraie anomalie" et "pipeline manquant"),
avec une note explicite sur la page. Elles restent dans
`api/services/quality.py::PROBLEMATIC_CODES` (et donc exclues aussi de
`/api/analyse-comparative` et `/api/classement-compagnies`, voir plus bas).

**À faire** : concevoir un extracteur dédié à la structure comptable
Takaful (tableaux/lignes propres, cf. `extraction/CAS_PARTICULIERS.md` pour
le détail déjà documenté par société), puis les réintégrer normalement une
fois ce pipeline validé.

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
