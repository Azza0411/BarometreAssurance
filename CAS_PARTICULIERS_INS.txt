# Cas particuliers — Source INS (Portail de données)

Module : `scraping/ins_scraper.py`
KPI (2) : Population Totale, Produit Intérieur Brut (PIB).

## Résolu

- **Pas de PDF, mais une vraie API REST/XML** : le portail (moteur
  "Prognoz") expose `http://dataportal.ins.tn/WebApi/GetData` (POST XML),
  documentée sur `http://dataportal.ins.tn/fr/API`. Découverte en cherchant
  le lien "API" du menu du site plutôt qu'en essayant de rejouer les
  requêtes AJAX internes de l'interface (protocole propriétaire minifié,
  bien plus complexe à déduire).
- **Identifiants trouvés via `GetStructure`/`GetDimensionElements`** (pas
  devinés) :
  - Population Totale : `SourceId='C_NSO'` ("Socio-économique", correspond
    à "Base de données socioéconomique"), `Dimension
    Id='RDS_DICT_INDICATORS_NSO'` avec `Element=22269316` ("Population au
    1er Juillet"), `Dimension Id='RDS_DICT_REGIONS_NSO'` avec `Element=0`
    (total national "Tunisie", pas une région précise).
  - PIB : `SourceId='OBJ11288479'` ("Principaux agrégats (2015)"),
    `Dimension Id='OBJ11288499'` avec `Element=28757929` ("PIB aux prix du
    marché").
- **Le nœud "Population" (clé 11919716) n'a pas de donnée propre** : c'est
  une catégorie/dossier ; la feuille réellement mise à jour est son enfant
  "Population au 1er Juillet" (clé 22269316, `TIMESTAMP` récent). Une
  requête sur le nœud parent renvoie `<Series State="Success"/>` (vide),
  sans erreur explicite — à surveiller si un autre indicateur du portail
  est ajouté un jour (toujours vérifier qu'on cible une feuille, pas une
  catégorie).
- **Étendue temporelle différente par KPI** : Population Totale remonte à
  2000 (24 valeurs), PIB seulement à 2015 (10 valeurs, cohérent avec le nom
  de la base "Principaux agrégats (2015)"). Un document est créé pour
  chaque année où AU MOINS un des deux KPI est disponible ; l'autre KPI
  reste simplement absent pour les années où il n'existe pas (pas de
  valeur fabriquée).

## Non résolu / limitations connues

- Aucune pour l'instant — les deux KPI sont extraits avec succès pour
  toutes les années disponibles (24/24 pour Population Totale, 10/10 pour
  PIB).
