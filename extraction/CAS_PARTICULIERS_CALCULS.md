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

## Résolu (juillet 2026 — audit phase Modélisation)

- **`calculated_kpi_extractor.run()` jamais appelé automatiquement** : jusqu'ici seulement exécutable à la main (`python -m extraction.calculated_kpi_extractor`), donc jamais rafraîchi par les exécutions planifiées. Branché en fin de `extraction/kpi_extraction_pipeline.py::run()`, après les 5 sous-étapes (CMF, FTUSA, BVMT, BVMT bulletin, CGA) dont dépendent les 4 familles de calcul.
- **Garde-fou de cohérence Vie/Non-Vie généralisé** : `ratio_combine_valid` ne protégeait que "Ratio combiné (%)" — le cas BIAT ci-dessous (RSP gonflé à 119,8 % par le même motif : charges Vie incluses au numérateur, primes Vie absentes du dénominateur) montre que le même risque touche RSP et RF. Le garde-fou (renommé `segment_mismatch`) invalide désormais les 3 ratios ensemble.
- **Plancher/plafond de plausibilité (2 %–1 000 %) ajouté à l'écriture** (`_valid_ratio`, `RATIO_MIN_PLAUSIBLE`/`RATIO_MAX_PLAUSIBLE`) sur RC/RSP/RF dans `calculated_kpi_extractor.py` — même borne que `api/services/kpi_builder._raw_ratio`, mais appliquée en amont (à l'écriture en base) plutôt qu'uniquement à la lecture. **Les deux couches restent intentionnellement distinctes** : `calculated_kpi_extractor.py` garantit qu'une valeur stockée est toujours plausible pour tout consommateur (chatbot, futurs exports Excel/PDF...) ; `api/services/kpi_builder.py` va plus loin et tente un recalcul de repli (voir les 3 niveaux de fallback ci-dessous) quand la valeur en base est absente/invalide — une décision d'affichage, pas de calcul source, qui reste à sa place dans la couche API.
- **Invalidation `__delete__` généralisée** : ne couvrait que "Ratio combiné (%)". Toute valeur calculée par une exécution précédente mais devenue incalculable ou implausible aujourd'hui (dans les 4 familles CMF/secteur/CGA/BVMT) est maintenant explicitement supprimée de la base plutôt que laissée périmée indéfiniment (voir `_finalize`).

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

- **BIAT** — ~~RSP calculé = 119.8 % gonflé artificiellement~~ **Fixé (juillet 2026)** : `Primes émises par assurance` = 110.7 MDT (Non-Vie seule), `Charge de sinistres` = 132.6 MDT (Vie + Non-Vie) — exactement le motif que `segment_mismatch` détecte désormais, RC/RSP/RF sont maintenant tous les 3 invalidés (`None`/`__delete__`) plutôt que RSP seul gonflé silencieusement. Les primes Vie BIAT restent non extraites du PDF (cause racine non corrigée, seul le symptôme l'est) ; à réévaluer si elles deviennent disponibles.

- **COTUNACE** : `Primes émises par assurance` = 19 TND (numéro de ligne capturé). Corrigé côté API par fallback sur `Primes acquises` = 13.3 MDT. Ratios absents ou aberrants (> 1 000 % → filtrés par `_ratio`).

- **ZITOUNA_TAKAFUL** : RC = 12.1 %, RSP = 8.2 %, RF = 3.9 % — cohérents avec les charges brutes. Faibles par rapport aux assureurs classiques car la structure Takaful sépare le fonds des adhérents du fonds de la société (provisions techniques de 20.9 MDT non incluses dans les charges de prestations retenues pour le calcul).

- **ASTREE 2016-2017, AMI 2018 : Ratio de frais < 2 %** (0.73 %, 1.38 %, 1.66 % respectivement — physiologiquement impossibles pour un assureur). L'extracteur a capté un sous-total de ligne au lieu du total "Charges d'acquisition et de gestion nettes". Filtrés côté API (`_ratio` : v < 2 % → None).

- **CARTE et COMAR : "Ratio combiné (%)" = "Ratio de frais de gestion (%)"** (même valeur pour les deux KPI en 2023 et 2024). Probablement une ligne identique dans leur rapport CMF, ou un intitulé de ligne ambigu. Les valeurs (18 % / 27 %) sont physiologiquement impossibles pour un vrai ratio combiné (qui inclut sinistralité + frais, donc > 50 % en pratique) — à investiguer sur les PDF CMF correspondants si cette donnée devient critique.

- **"Ratio combiné" au niveau macro (DASH-FS-INS-01-A)** : la formule
  d'origine ne définit qu'une version par compagnie (dénominateur "Primes
  émises par assurance"). Le "Ratio combiné" sectoriel utilise par analogie
  "Total Primes émises" (FTUSA) comme dénominateur — à confirmer si c'est
  bien l'intention.
