# Cas particuliers — Source CGA (Rapport annuel)

Module : `extraction/cga_kpi_extractor.py`
KPI : Nombre d'assureurs (Annexe 1), pour l'Annexe 2 (Distribution
Géographique des Agents d'Assurance) : Nombre d'agences par assureur,
Nombre d'agences par compagnie, Répartition des agences par gouvernorat
(marché entier), Répartition des agences de la compagnie par gouvernorat
(par compagnie), et pour l'Annexe 4-1 (Évolution des primes nettes /
Évolution du chiffre d'affaires par catégories d'assurance) : Primes
émises par branche — ces KPI générant un nom de KPI dynamique par
compagnie/gouvernorat/branche (ex: "Nombre d'agences par assureur -
STAR", "Primes émises par branche - Automobile").

## Résolu

- **Texte tourné à 90° sur l'Annexe 2** (même cause que le tableau FTUSA
  "Compte d'exploitation par branche" : matrice de police à coefficients
  a=d=0, pas un `page.rotation`) : réutilise directement
  `_derotate_page_words` de `ftusa_kpi_extractor.py`.
- **Libellés de titre variables d'une année à l'autre** :
  - Annexe 1 : "STRUCTURE DU MARCHE D'ASSURANCE" (2022) vs "STRUCTURE DU
    MARCHE DES ASSURANCES" (2020, pluriel + article différent) → motif
    tolérant `structure du marche d.{1,4}assurances?`.
  - Annexe 2 : "DISTRIBUTION GEOGRAPHIQUE DES AGENTS D'ASSURANCE" (2022)
    vs "DISTRIBUTION GEOGRAPHIQUE DES INTERMEDIAIRES EN ASSURANCE" avec
    "Agents d'assurance" comme sous-section (2020) → motif tolérant
    acceptant l'un ou l'autre.
- **"Nombre d'assureurs"** = comptage des lignes de la section "Sociétés
  d'Assurance Directe" de l'Annexe 1 uniquement (entre son en-tête et la
  ligne "TOTAL" suivante) : exclut délibérément la section "Sociétés de
  Réassurance" (Tunis-Re) et la section "Sociétés d'Assurance
  Non-Résidentes" (succursales/bureaux de représentation étrangers, dont
  la structure de colonnes est d'ailleurs différente — date de création
  au lieu de primes/taux d'évolution). Confirmé avec l'utilisateur.
- **"Nombre d'agences par assureur" et "Nombre d'agences par compagnie"
  sont la même valeur** (colonne TOTAL de la ligne de la compagnie),
  décrite par l'utilisateur via deux références différentes (somme des 24
  colonnes de gouvernorats vs colonne TOTAL déjà présente, les deux étant
  mathématiquement identiques) : les deux KPI sont enregistrés avec la
  même valeur, par choix explicite de l'utilisateur plutôt que d'en
  éliminer un comme redondant.
- **Colonne "Grand Tunis" (position 5)** dans l'Annexe 2 est un sous-total
  (Tunis+Ariana+Ben Arous+Manouba), pas un 25e gouvernorat : ignorée lors
  du mappage position -> nom de gouvernorat (`GOVERNORATE_ORDER`, avec
  `None` à cette position).
- **Rattachement des compagnies au registre CMF** : les noms de
  compagnies de l'Annexe 2 sont convertis en code court (ex: "STAR",
  "LLOYD_TUNISIEN") via `config.company_registry.find_code_by_name`
  (même fonction que pour BVMT) ; si aucune correspondance n'est trouvée,
  le nom brut du PDF est utilisé tel quel dans le nom du KPI.
- **Nombre de compagnies variable d'une année à l'autre** (310 à 389 KPI
  selon l'année) : reflète simplement le nombre réel de compagnies
  actives/listées dans l'Annexe 2 cette année-là, pas une erreur
  d'extraction — pas de KPI_NAMES fixe pour cette source (voir
  `kpi_extraction_pipeline._run_cga`), donc pas de rapport d'échecs Excel
  (un KPI "absent" une année donnée n'est pas nécessairement une anomalie).

- **"Primes émises par branche" (Annexe 4-1), volontairement propre à
  CGA** : sur demande explicite de l'utilisateur, aucune tentative de
  correspondance avec les branches FTUSA (déjà stockées séparément) — les
  deux nomenclatures ne se recoupent pas exactement (ex: CGA regroupe
  "Incendie" et "Risques Divers" en une seule ligne, FTUSA les sépare ;
  CGA a une branche "Exportations & Crédits" que FTUSA n'a pas). 9 KPI par
  année : Vie et Capitalisation, Automobile, Groupe Maladie, Transport,
  Incendie et Risques Divers, Exportations et Credits, Grele et Mortalite
  du Betail, Accidents de Travail (toujours à 0, branche transférée à la
  CNSS depuis 1995), Operations Acceptees.
- **Faux positif : une page narrative (pas tournée) contient aussi le
  titre recherché** : l'introduction du rapport sur le marché mondial de
  l'assurance vie a pour sous-titre "Évolution des primes nettes (en
  termes réels)", identique en substance au titre du vrai tableau chiffré
  (qui, lui, est toujours tourné à 90°, comme l'Annexe 2). Résolu en
  exigeant `require_rotated=True` pour cette recherche de page plutôt
  qu'en essayant d'affiner le texte du titre (essayé d'abord avec "doit
  contenir catégories d'assurance", mais ce complément de titre n'est pas
  présent tous les ans — ex: absent en 2022 — donc pas fiable).
- **Libellé de l'Annexe 4-1 variable d'une année à l'autre** :
  "Évolution des primes nettes" (2022) vs "Évolution du chiffre
  d'affaires par catégories d'assurance" (2017, 2020) → motif tolérant
  acceptant les deux, la structure du tableau (branches, 6 colonnes
  année) étant identique dans les deux cas.
- **Colonnes "Part"/"Tx d'évolution" parfois comptées à tort comme des
  valeurs d'année** : ces colonnes sont en pourcentage, normalement
  exclues des clusters numériques (le "%" collé au nombre empêche le
  match), sauf certaines années (ex: 2017) où un espace sépare le nombre
  du "%" ("21,2 %") — le nombre seul devient alors un cluster valide.
  Résolu en prenant systématiquement l'index 5 (la 6ᵉ valeur, toujours
  l'année en cours puisque les 6 colonnes année sont toujours les 6
  premières), plutôt que le dernier cluster de la ligne.

## Non résolu / limitations connues

- **8 compagnies jamais présentes dans l'Annexe 2, sur les 12 années
  disponibles (2013-2024)** : ATTIJARI, CARTE_VIE, COTUNACE, GAT_VIE,
  HAYETT, MAGHREBIA_VIE, TUNIS_RE, UIB. Vérifié le 2026-08-18 en listant
  les libellés bruts de ligne de chaque rapport CGA_20XX.pdf (pas de
  ligne contenant leur nom, sous aucune variante testée par
  `find_code_by_name`) — ce n'est PAS un échec de rattachement nom→code,
  la ligne est structurellement absente du tableau source. Explication
  probable par famille de cas (non confirmée avec le CGA, déduite de la
  nature de chaque société) :
  - **UIB, ATTIJARI** : filiales de bancassurance, distribuées via les
    agences de leur banque respective plutôt qu'un réseau d'agents
    d'assurance dédié — hors périmètre de ce tableau par construction.
  - **HAYETT** : compagnie Vie seule ; peut ne pas opérer de réseau
    d'agences physique au même sens que les compagnies Non-Vie/mixtes.
  - **CARTE_VIE, GAT_VIE, MAGHREBIA_VIE** : branche Vie d'un groupe dont
    la branche Non-Vie (CARTE/GAT/MAGHREBIA) est, elle, bien présente —
    cohérent avec un réseau d'agences unique par groupe, rapporté sous la
    marque non-Vie uniquement (cf. LLOYD_VIE, listé seul jusqu'en 2016
    puis remplacé par LLOYD_TUNISIEN à partir de 2017, signe d'une
    fusion/renommage de la structure déclarée).
  - **TUNIS_RE** : réassureur, ne traite pas directement avec des
    assurés/agences.
  - **COTUNACE** : assurance-crédit à l'export, structure de
    distribution spécialisée hors réseau d'agents classique.

  Conséquence côté application : `/api/vue-assurance/profil` renvoie
  `total_agences: null` pour ces 8 compagnies quelle que soit l'année
  demandée (le repli "année la plus récente disponible" déjà en place
  dans `vue_assurance.py` ne peut rien trouver puisqu'aucune année n'a de
  donnée) — la fiche masque désormais entièrement la carte "Réseau
  d'agences" plutôt que d'afficher un encart vide (retour utilisateur
  2026-08-18), au lieu de tenter une correction qui n'a pas de source à
  extraire.

- **2018 et 2021 : branche "Automobile" manquante** dans l'Annexe 4-1.
  Cause identifiée : le PDF source utilise un point comme séparateur
  décimal pour cette seule valeur au lieu d'une virgule (ex: "939.8" au
  lieu de "939,8" dans "Assrance Automobile 638,7 707,0 767,9 835,0 939.8
  980,4 ..."), ce qui casse la détection du nombre par
  `NUMERIC_TOKEN_RE` (qui n'accepte que la virgule comme séparateur
  décimal, partagé par tous les extracteurs du projet). Semble être une
  coquille isolée dans le document source plutôt qu'un problème
  structurel — pas corrigé pour ne pas fragiliser le parseur numérique
  partagé pour un cas aussi ponctuel.
