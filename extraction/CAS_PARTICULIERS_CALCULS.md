# Cas particuliers — KPI calculés (extraction/calculated_kpi_extractor.py)

Ces KPI ne viennent pas d'un PDF : ils sont calculés à partir des KPI déjà
stockés dans `kpi_values`, selon les formules de "Calcul interne.docx".
Trois familles de calcul, chacune sur son propre périmètre de documents
(voir docstring du module) : par document CMF, par année (secteur
FTUSA x INS), par année (réseau d'agences CGA).

## Résolu

- **Convention de signe des charges** : les tableaux Annexe 12/13 (CMF) et
  FTUSA notent les charges (prestations, acquisition) en **négatif**
  (déductions dans un compte de résultat), alors que "Charge de sinistres"
  (résultat_kpi_extractor) est en **positif**. Sans correction, "Ratio
  combiné"/"Ratio de sinistralité"/"Ratio de frais"/"Ratio S/P" ressortaient
  négatifs (ex: -110% au lieu de +110%). Corrigé en prenant la valeur
  absolue des composantes de charge dans ces ratios uniquement — les KPI
  "somme" (Charges de prestations, Charge de sinistres...) gardent leur
  signe d'origine tel qu'extrait.
- **"Primes acquises" (par société)** = somme de "Primes acquises Vie"
  (nouvellement extrait, voir plus bas) et "Primes acquises" (Non-Vie,
  déjà existant) — écrase la valeur Non-Vie-seule précédemment stockée
  sous ce même nom une fois la partie Vie disponible.
- **Nouveau KPI extrait "Primes acquises Vie"** (Annexe 12) : certaines
  sociétés libellent la ligne "Primes émises" (ex: STAR — dans ce cas
  "Primes acquises Vie" reste introuvable pour elles), d'autres "Primes
  acquises" (ex: GAT). Couverture réelle : 34/222 documents — cohérent
  avec les autres KPI Vie de l'Annexe 12 (une société sur deux environ n'a
  pas d'activité Vie propre, gérée par une filiale distincte).
- **Mapping gouvernorat -> grande région** : découpage INS standard en 7
  régions (voir config/region_mapping.py), confirmé par l'utilisateur.
- **Bug de rapprochement société découvert en testant les calculs CGA** :
  "EL AMANA TAKAFUL" (orthographe CGA) se rapprochait à tort de "AMI"
  (alias "El Ittihad" — le seul mot commun "EL" suffisait à gagner, un mot
  connecteur sans valeur distinctive). Corrigé dans
  `config/company_registry.py` via une liste de mots vides (EL, AL, DE,
  DU...) exclus du rapprochement, plus l'ajout des alias réels observés
  ("EL AMANA TAKAFUL", "ATTAKAFULIA") directement dans le registre. A
  entraîné un nettoyage ponctuel des lignes `kpi_values` orphelines
  (libellés bruts "ATTAKAFULIA"/"aTTaKaFulia" non résolus, remplacés par le
  code correct une fois le registre corrigé) — vérifié par cohérence
  Total agences == somme des "Nombre d'agences par région" sur les 10
  années CGA.
- **KPI de classement/comparaison volontairement NON stockés** :
  "Classement des assurances selon le nombre d'agences", "Classement des
  assurances", "Rang par primes émises", "Classement région par nombre
  d'agences de la compagnie", "Écart de performance" dépendent d'un choix
  de l'utilisateur (quel ratio ? quelle référence de comparaison ?) ou d'un
  tri qui devient obsolète dès qu'une nouvelle donnée arrive — recommandé
  de les calculer à la demande (frontend/API) à partir des KPI stockés,
  pas en base.
- **"Réseau d'agences en Tunisie"** : pas un KPI à calculer, un concept
  d'affichage (probablement une carte) réutilisant "Répartition des
  agences par gouvernorat" déjà stockée.

## Non résolu / limitations connues

- **"Capitalisation boursière"** : bloqué, "Cours de l'action" n'est
  disponible sur aucune source actuelle (BVMT expose la gouvernance et le
  statut de cotation, pas de cours boursier).
- **"Primes émises par branche" / "Part des primes émises par branche"** :
  jamais extrait (FTUSA ne garde que les totaux sectoriels, pas le détail
  par branche, choix confirmé par l'utilisateur lors de l'implémentation
  FTUSA).
- **Ratio combiné / sinistralité manquant pour certaines sociétés** : trois niveaux de fallback dans `api/app.py → analyse_comparative()` :
  1. Si 2 des 3 ratios sont présents, compléter par calcul (`RC = RSP + RF`, `RSP = RC − RF`, `RF = RC − RSP`). Exemples en 2024 : ASTREE/BH (pas de RC brut), LLOYD/MAGHREBIA (pas de RSP brut).
  2. Si le résultat < 2 % (ex. COMAR/CARTE : RC = RF → RSP = 0 %), l'invalider (None) et recalculer depuis les charges brutes : `RSP = |Charge de sinistres| / Primes`, `RF = |Charges d'acquisition| / Primes`. Exemples en 2024 : COMAR RSP = 56.1 %, CARTE RSP = 45.9 %.
  3. Si RC < RSP (incohérence mathématique — RC était extrait du même champ ambigu que RF), recalculer RC = RSP + RF. Exemples : COMAR RC = 82.9 %, CARTE RC = 64.0 %.

- **ATTIJARI** : aucun ratio (combiné, sinistralité, frais) dans le document CMF 2024 — PDM = 0.1 %, primes = 3.5 MDT. Calcul impossible sans données sources ; affiché N/D.

- **BIAT** : `Primes émises par assurance` = 110.7 MDT correspond uniquement aux primes Non-Vie. `Charge de sinistres` = 132.6 MDT inclut Vie + Non-Vie (Vie ≈ 132.6 MDT, Non-Vie ≈ 0 MDT). RSP calculé = 119.8 % est donc gonflé artificiellement (dénominateur Non-Vie seulement, numérateur total). Les primes Vie BIAT ne sont pas extraites du PDF ; à corriger si elles deviennent disponibles.

- **COTUNACE** : `Primes émises par assurance` = 19 TND (numéro de ligne capturé). Corrigé côté API par fallback sur `Primes acquises` = 13.3 MDT. Ratios absents ou aberrants (> 1 000 % → filtrés par `_ratio`).

- **ZITOUNA_TAKAFUL** : RC = 12.1 %, RSP = 8.2 %, RF = 3.9 % — cohérents avec les charges brutes. Faibles par rapport aux assureurs classiques car la structure Takaful sépare le fonds des adhérents du fonds de la société (provisions techniques de 20.9 MDT non incluses dans les charges de prestations retenues pour le calcul).

- **ASTREE 2016-2017, AMI 2018 : Ratio de frais < 2 %** (0.73 %, 1.38 %, 1.66 % respectivement — physiologiquement impossibles pour un assureur). L'extracteur a capté un sous-total de ligne au lieu du total "Charges d'acquisition et de gestion nettes". Filtrés côté API (`_ratio` : v < 2 % → None).

- **CARTE et COMAR : "Ratio combiné (%)" = "Ratio de frais de gestion (%)"** (même valeur pour les deux KPI en 2023 et 2024). Probablement une ligne identique dans leur rapport CMF, ou un intitulé de ligne ambigu. Les valeurs (18 % / 27 %) sont physiologiquement impossibles pour un vrai ratio combiné (qui inclut sinistralité + frais, donc > 50 % en pratique) — à investiguer sur les PDF CMF correspondants si cette donnée devient critique.

- **"Ratio combiné" au niveau macro (DASH-FS-INS-01-A)** : la formule
  d'origine ne définit qu'une version par compagnie (dénominateur "Primes
  émises par assurance"). Le "Ratio combiné" sectoriel utilise par analogie
  "Total Primes émises" (FTUSA) comme dénominateur — à confirmer si c'est
  bien l'intention.
