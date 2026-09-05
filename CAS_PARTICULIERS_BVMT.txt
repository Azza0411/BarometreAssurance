# Cas particuliers — Source BVMT (Bourse de Tunis)

Modules : `scraping/bvmt_scraper.py`, `extraction/bvmt_kpi_extractor.py`,
`extraction/bvmt_bulletin_kpi_extractor.py`
KPI : Status de cotation, Directeur général, Président du Conseil
d'Administration, Cours de l'action, Capitalisation Boursière (calculée,
voir `extraction/calculated_kpi_extractor.py`).

## Sociétés concernées

Seules les sociétés d'assurance effectivement cotées en bourse sont
traitées (sous-ensemble des 24 sociétés suivies par CMF), déterminé
dynamiquement via le secteur "Assurance" de la page `/emetteurs` — pas de
liste codée en dur. Reconnaissance du nom BVMT -> code CMF via
`config.company_registry.find_code_by_name()` (similarité de Jaccard
pondérée sur les alias, voir ce fichier pour le détail : une simple
inclusion de sous-chaîne confondait "ASSURANCES MAGHREBIA" et "ASSURANCES
MAGHREBIA VIE").

7 sociétés reconnues au moment de l'implémentation : MAGHREBIA,
MAGHREBIA_VIE, ASTREE, BH, BNA, STAR, TUNIS_RE.

## Résolu

- **"Status de cotation" n'est pas extrait d'un document** : c'est un fait
  constaté pendant le scraping (présence dans la liste des sociétés cotées
  du secteur Assurance) -> la valeur ("Cotée") est enregistrée directement
  par `sync_status_cotation()`, avec un document de traçabilité (année du
  scraping, lien vers la fiche de la société) plutôt que via le pipeline
  d'extraction PDF habituel.
- **Format du tableau de gouvernance très variable d'une société à
  l'autre** (rapports non standardisés, contrairement à CMF/FTUSA) : 3
  formes rencontrées et gérées :
  1. STAR (2025) : table "Membres des comités/commission", une personne par
     ligne, rôle sur la même ligne (ou coupé sur la ligne précédente pour
     "Président du Conseil d'Administration").
  2. MAGHREBIA (2025) : simple liste "Informations clés" en page de garde,
     "Directeur Général M. Sébastien SANCHEZ" (rôle puis nom, sans ":").
  3. TUNIS RE (2025) : page "LA GOUVERNANCE", "Président du Conseil: Slah
     Kanoun" (rôle puis nom, avec ":", nom sans préfixe "M./Mme").

  Les 2 formes générales ("rôle d'abord" recherché sur toutes les pages,
  et "nom d'abord" façon table STAR) sont essayées pour chaque KPI, sans
  restreindre la recherche à une page au titre particulier.

## Cours de l'action / Capitalisation Boursière

Investigation initiale : le site expose un endpoint AJAX
`bourse/instrument/chart-data/{isin}?period=1A` (graphique de cours) qui
semblait prometteur pour l'historique, mais s'est révélé n'avoir de données
réelles que depuis fin décembre 2025 (~6 mois), quelle que soit la plage de
dates demandée (même `2020-01-01`→`2026-07-08` renvoie `cloture: null` avant
cette date) — pas exploitable pour un historique 2015-2024. Sur décision de
l'utilisateur, source abandonnée au profit des **bulletins officiels
quotidiens de la cote** (`/editions-statistique`, filtrable par date via
`date[min]`/`date[max]`), dont l'archive remonte au moins à fin 2015.

- **Deux conventions de chemin/casse pour le nom de fichier du bulletin
  selon l'ancienneté** : archive consolidée `bulletin/pdf/bullAAAAMMJJ.pdf`
  (minuscule, ex: 2015-2021) vs dossier mensuel
  `AAAA-MM/BullAAAAMMJJ.pdf` (majuscule initiale, récent) → motif de
  reconnaissance volontairement large sur le chemin
  (`scraping.bvmt_scraper.BULLETIN_LINK_RE`), seul le nom de fichier est
  contraint.
- **Dernier jour de bourse de l'année, pas le 31/12 systématiquement** :
  recherché par une fenêtre de dates (15-31 décembre, élargie si vide) sur
  `/editions-statistique`, le dernier bulletin trouvé dans la fenêtre étant
  retenu (jours fériés/week-ends fin d'année variables).
- **Format du tableau "COTE DE LA BOURSE : MARCHE PRINCIPAL DES TITRES DE
  CAPITAL" variable d'une époque à l'autre** : les bulletins récents
  ajoutent des colonnes ISIN/MNEMO/Cours de Réservation absentes des
  anciens, ce qui déplace la position de la colonne CLÔTURE dans l'ordre de
  lecture à plat du texte. Résolu en repérant la colonne par la position x0
  de son en-tête ("CLÔTURE") plutôt que par un index fixe, avec une
  tolérance (voir `extraction/bvmt_bulletin_kpi_extractor.py`).
- **Reconnaissance de société PAR MNEMO, pas par nom (contrairement au
  reste du projet)** : plusieurs sociétés d'assurance partagent un nom/sigle
  court avec une société cotée séparément d'un autre secteur — ex: "BH" est
  le ticker ET le premier mot du nom de "BH BANK", alors que BH ASSURANCE
  cote sous le mnemo "BHASS" ; "BNA" est le ticker de la banque, BNA
  ASSURANCES cote sous "BNASS". Une correspondance par nom
  (`find_code_by_name`) confondrait les deux. Le MNEMO (lu sur la fiche BVMT
  de chaque société, cf. `sync_market_data`) est exact et sans ambiguïté,
  mais absent des bulletins anciens (avant l'ajout de la colonne
  MNEMO) → repli sur la "Dénomination sociale" complète en toutes lettres
  (ex: "BH ASSURANCE" au lieu de juste "BH"), qui elle apparaît telle quelle
  même dans les bulletins anciens et ne souffre pas de la même ambiguïté
  (vérifié : la ligne BH Bank d'un bulletin 2020 affiche "BH BANK"/"BH
  LEASING", jamais la phrase complète "BH ASSURANCE").
- **MNEMO et "Titres émis" absents de la fiche société statique** (page
  `/node/xxxx`, qui n'a que le Code ISIN) : disponibles seulement via
  l'endpoint AJAX de cotation live `bourse/instrument/{isin}` → un second
  appel réseau par société dans `sync_market_data`.
- **Capitalisation Boursière = calcul interne (Nombre d'actions x Cours de
  l'action), pas une valeur BVMT directe** : décision explicite de
  l'utilisateur, car aucune source BVMT ne publie la capitalisation par
  société pour les années passées (le bulletin quotidien n'a que le cours,
  pas le nombre de titres ; le rapport annuel "Bilan de l'activité
  boursière" ne donne que des totaux marché/secteur). Le "Nombre d'actions"
  utilisé vient en priorité de CMF (ligne "Capital social", ~4% de
  couverture réelle sur les 222 documents — voir
  `CAS_PARTICULIERS_PRESENTATION.md`), avec repli sur le nombre de titres
  émis ACTUEL de BVMT (une seule valeur, faute de mieux, appliquée à toutes
  les années) → **imprécis pour une société ayant eu une augmentation de
  capital entre l'année concernée et aujourd'hui** : ex. STAR a un "Nombre
  d'actions" CMF de 2 307 693 pour 2024 mais 10 000 003 titres émis
  actuellement (BVMT) → Capitalisation Boursière 2024 nettement plus basse
  que les années voisines calculées avec la valeur de repli, discontinuité
  visible dans la série mais reflétant une vraie limite de la donnée
  source, pas un bug.

## Non résolu / limitations connues

- **Nombre de sociétés variable selon l'année, reflétant les dates réelles
  d'introduction en bourse** (pas une erreur d'extraction) : BNA ASSURANCES
  cotée seulement depuis le 14/08/2025 (absente de tout bulletin
  2015-2024) ; ASSURANCES MAGHREBIA depuis le 30/12/2020 ; ASSURANCES
  MAGHREBIA VIE depuis le 30/12/2022.
- **BH ASSURANCE absente du bulletin de fin 2015** alors que sa fiche BVMT
  indique une introduction en bourse "Avril 2010" : la société n'apparaît
  dans aucune ligne du tableau "Marché Principal des Titres de Capital" de
  ce bulletin (vérifié manuellement, seules "BH - Banque de l'Habitat" et
  des obligations BH y figurent) — probablement un changement de
  compartiment de cotation entretemps, cause exacte non creusée davantage.
  Réapparaît normalement dans les bulletins suivants testés (2020, 2026).
- **Rapports ESG 2024 de STAR et MAGHREBIA : gouvernance introuvable.**
  - STAR 2024 ("Rapport de durabilité 2023") : la table de gouvernance y
    est organisée différemment (les prénoms des membres apparaissent en
    ligne d'en-tête de colonnes plutôt qu'un nom complet par ligne) —
    format non géré par l'extracteur actuel.
  - MAGHREBIA 2024 : aucune mention de "Directeur" ni "Président du
    Conseil" trouvée dans le document (probablement absent de cette
    première édition du rapport, l'info étant peut-être uniquement dans un
    graphique/organigramme non extractible en texte).
  - Sur les 7 documents ESG en base, 5/7 sont complets (2/2 KPI) ; seuls
    STAR 2024 et MAGHREBIA 2024 sont à 0/2.
- **ASTREE, BH, BNA n'ont aucun rapport ESG publié** au moment du
  scraping (0 document trouvé via le filtre `societe` de la page de
  reporting ESG) — programme volontaire encore récent, pas une erreur de
  correspondance d'identifiant (vérifié individuellement pour BH : la
  page filtrée renvoie bien 0 résultat, pas une erreur).
