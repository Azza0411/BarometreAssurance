# Base documentaire — Ratios financiers et prudentiels applicables au Takaful

**Objectif** : fournir une base documentaire sourcée (normes IFSB, littérature académique, tentatives AAOIFI/ONU/Scribd) pour adapter les ratios financiers actuellement appliqués de façon identique aux compagnies conventionnelles et aux deux compagnies Takaful du périmètre (AT_TAKAFULIA, ZITOUNA_TAKAFUL), avant toute implémentation dans le pipeline d'extraction/KPI.

**Date de production** : 2026-08-05
**Périmètre** : 33 ratios/indicateurs, regroupés en 8 catégories.

---

## 1. Limites et sources non accessibles

Consultation réelle effectuée via WebFetch/WebSearch le 2026-08-05. Le détail par source :

| Source demandée | Statut | Détail / compensation |
|---|---|---|
| **IFSB — Compilation Guide on PSIFIs (déc. 2019)** | ✅ Consulté intégralement (PDF récupéré puis extrait en texte via `pdftotext`, 9921 lignes lues) | Source principale : chapitre 7 dédié aux "Takaful/Retakaful Indicators", avec définitions et formules officielles. |
| **IFSB-11 — Standard on Solvency Requirements for Takaful Undertakings (déc. 2010)** | ✅ Consulté intégralement (1873 lignes extraites) | Formules de l'exigence de solvabilité (§62) et structure à deux niveaux (PRF/TO) récupérées. |
| **IFSB-8 — Guiding Principles on Governance for Takaful Undertakings (déc. 2009)** | ✅ Consulté intégralement (2221 lignes extraites) | Utilisé pour le contexte gouvernance/Wakala/surplus ; aucune formule chiffrée de ratio nouveau trouvée au-delà de ce qui figure dans le Compilation Guide. |
| **IFSB-14 — Standard on Risk Management for Takaful Undertakings (déc. 2013)** | ✅ Consulté intégralement (2807 lignes extraites) | Contenu essentiellement qualitatif (risques de concentration, retakaful) ; aucune formule de ratio supplémentaire chiffrée trouvée. |
| **GN-10 — Guidance Note on Recovery and Resolution for Takaful Undertakings (juill. 2025)** | ✅ Consulté intégralement (1451 lignes extraites) | Utilisé pour la structure à deux/trois fonds (SHF/PRF/PIF) et le mécanisme de Qard ; pas de formule de ratio chiffrée (indicateurs d'alerte décrits qualitativement : fréquence/montant du Qard). |
| **IFSB-25 (disclosures Takaful)** | ⚠️ Non consulté en détail | Identifié comme "Disclosures to Promote Transparency and Market Discipline for Takāful/Retakāful" — non ouvert faute de ratio chiffré attendu au-delà des exigences de publication ; non nécessaire pour atteindre les 30 ratios. |
| **AAOIFI — e-standards / accounting standards** | ❌ Paywall confirmé | La page `aaoifi.com/e-standards/` affiche un accès nécessitant inscription/abonnement ("Access Standards" derrière un formulaire de connexion). Aucun numéro de norme FAS Takaful ni contenu chiffré n'a pu être lu. **Compensation** : aucune formule AAOIFI n'est donc citée dans ce document — cela est noté explicitement plutôt que d'inventer un numéro de standard ou une page. |
| **Document ONU (unstats.un.org, IF1_GN_Islamic_Finance_ENG.pdf)** | ✅ Récupéré et lu (3246 lignes extraites) | Document de méthodologie de comptabilité nationale (Islamic Finance Task Team, mise à jour SNA 2008/BPM6). Confirme le rôle de l'IFSB PSIFI Compilation Guide comme référence pour les indicateurs Takaful (§109, note 7) mais **ne définit aucune formule de ratio propre** — utilisé uniquement comme source de corroboration contextuelle, pas comme source de ratio. |
| **Article Abdou, Ali & Lister (2014)** | ✅ Consulté intégralement (version accessible en libre accès via le dépôt institutionnel University of Huddersfield, `eprints.hud.ac.uk`, le lien businessperspectives.org d'origine renvoyant une erreur 403) | Section méthodologie (13 ratios calculés, 7 retenus après traitement de la multicolinéarité) intégralement lue. |
| **Scribd — "Assurance Islamique"** | ❌ Non accessible | La page Scribd ne restitue que l'interface de navigation (titre, métadonnées, compteur de vues) ; le contenu du PDF est chargé dynamiquement en JavaScript et n'a pas pu être extrait via WebFetch. **Aucun contenu de cette source n'est donc utilisé** dans le tableau ci-dessous — conformément à la consigne de ne jamais inventer un contenu non lu. |

**Conséquence méthodologique** : la quasi-totalité des ratios ci-dessous provient de sources IFSB de premier rang (⭐⭐⭐⭐⭐) directement consultées, complétées par l'article académique Abdou et al. (2014, ⭐⭐⭐) pour la validation croisée et pour des ratios de solvabilité non couverts par l'IFSB (primes/surplus). Aucun ratio AAOIFI n'a pu être sourcé directement — c'est la limite principale de cette base.

---

## 2. Légende de fiabilité

- ⭐⭐⭐⭐⭐ = norme officielle IFSB directement consultée (texte intégral lu et cité)
- ⭐⭐⭐⭐ = régulateur officiel (CMF, banque centrale...) — non utilisé dans ce document (aucune source régulateur tunisien Takaful trouvée dans le périmètre demandé)
- ⭐⭐⭐ = article scientifique peer-reviewed directement consulté
- ⭐⭐ = source secondaire non vérifiée par ailleurs — non utilisé (source Scribd inaccessible)

Quand un ratio est confirmé par **au moins deux sources indépendantes**, cela est indiqué explicitement dans le champ « Référence ».

---

## 3. Sommaire par catégorie

| Catégorie | Nombre de ratios |
|---|---|
| Rentabilité | 4 |
| Solvabilité / Adéquation des fonds propres | 9 |
| Liquidité | 2 |
| Technique / Souscription | 6 |
| Gestion / Efficience | 5 |
| Réassurance / Retakaful | 1 |
| Investissement et qualité des actifs | 4 |
| Performance macroéconomique / sectorielle | 2 |
| **Total** | **33** |

---

## 4. Contexte structurel Takaful (à lire avant le tableau de ratios)

D'après IFSB-11 (§10-12, p.3) et GN-10 (p.23-24), un Takaful Undertaking (TU) repose sur une structure **à deux acteurs et jusqu'à trois fonds** :

- **Takaful Operator (TO)**, société commerciale détenue par des actionnaires, qui gère le régime pour le compte des participants (souscription, gestion des sinistres, investissement) et se rémunère par des frais de Wakala et/ou une part Mudharaba des revenus d'investissement.
- **Shareholders' Fund (SHF)** : capitaux propres des actionnaires, couvre les charges opérationnelles du TO.
- **Participants' Risk Fund (PRF)** : reçoit les contributions (Tabarru') des participants et sert à payer les sinistres ; propriété collective des participants, gérée par le TO.
- **Participants' Investment Fund (PIF)**, quand il existe (Takaful familial), pour l'épargne/investissement des participants.

Cette **ségrégation des fonds** est la différence structurelle majeure avec l'assurance conventionnelle : en assurance conventionnelle, un seul bilan et un seul résultat net appartiennent à l'assureur. En Takaful, le résultat technique (surplus/déficit du PRF) appartient collectivement aux participants, et non aux actionnaires — ce qui change le sens économique de nombreux ratios de rentabilité et de solvabilité repris tels quels du conventionnel (voir la colonne « Différences avec le conventionnel » de chaque ratio). Le mécanisme du **Qard** (prêt sans intérêt du SHF vers le PRF en cas de déficit, remboursable sur surplus futurs) est spécifique au Takaful et n'a pas d'équivalent conventionnel (IFSB-11 §12, IFSB-8 §88, GN-10 §24-27).

---

## 5. Catégorie : RENTABILITÉ

### 5.1 Tableau de synthèse

| # | Ratio (FR) | Ratio (EN) | Formule (résumé) | Sens | Fiabilité |
|---|---|---|---|---|---|
| R1 | Rendement des capitaux propres | Return on Equity (ROE) | Résultat net de l'Opérateur / Fonds des actionnaires | Plus élevé = meilleur | ⭐⭐⭐⭐⭐ |
| R2 | Rendement de l'actif | Return on Assets (ROA) | Résultat net de l'Opérateur × 100 / Actif total | Plus élevé = meilleur | ⭐⭐⭐⭐⭐ |
| R3 | Ratio de revenu d'investissement (sur primes/contributions) | Investment income ratio | Revenu d'investissement / Contributions nettes (primes acquises) | Plus élevé = meilleur | ⭐⭐⭐⭐⭐ |
| R4 | Revenu d'investissement sur actifs investis | Investment income / Investment assets | Revenu d'investissement / Actifs investis | Plus élevé = meilleur | ⭐⭐⭐⭐⭐ |

### 5.2 Fiches détaillées

#### R1. Rendement des capitaux propres (Return on Equity, ROE)

| Champ | Contenu |
|---|---|
| Catégorie | Rentabilité |
| Formule | ROE = Résultat net de l'Opérateur Takaful / Fonds des actionnaires (Shareholders' fund) |
| Variables | *Résultat net de l'Opérateur* : résultat avant éléments extraordinaires, zakat et impôts, annualisé pour l'année en cours ; *Fonds des actionnaires* : capitaux propres financiers et non financiers totaux, moyenne début/fin de période. |
| Signification économique | Mesure la capacité de l'Opérateur Takaful à générer un profit à partir des capitaux apportés par ses actionnaires, distinct du surplus technique des participants. |
| Sens d'interprétation | Plus élevé = meilleur (rentabilité de l'actionnaire) |
| Valeur cible / seuil | Non spécifié dans les sources consultées |
| Applicabilité au Takaful | Adapté du conventionnel — la formule est identique dans sa forme, mais le numérateur ne couvre que le résultat de l'Opérateur (frais de Wakala + part Mudharaba), pas le résultat technique du PRF qui appartient aux participants |
| Différences avec le conventionnel | En assurance conventionnelle, le résultat net inclut le résultat technique de souscription. En Takaful, le résultat technique (surplus/déficit du PRF) appartient aux participants ; le ROE du TO ne reflète donc que la rémunération de gestion (Wakala/Mudharaba), pas la performance de souscription globale (IFSB-11 §10, p.3) |
| Référence bibliographique | IFSB (2019), *Compilation Guide on PSIFIs*, ratio TP18, p.95-96 ; confirmé par une seconde source indépendante : Abdou, Ali & Lister (2014), p.8-9, qui définissent ROE = profit after tax / equity capital |
| Citation page/paragraphe | « ROE is calculated as the takful/retakful operator's net income divided by the common shareholders' fund » — IFSB PSIFI Compilation Guide, p.95 |
| Fiabilité | ⭐⭐⭐⭐⭐ (norme IFSB directement lue, corroborée par article académique) |

#### R2. Rendement de l'actif (Return on Assets, ROA)

| Champ | Contenu |
|---|---|
| Catégorie | Rentabilité |
| Formule | ROA = (Résultat net de l'Opérateur × 100) / Actif total moyen |
| Variables | *Résultat net de l'Opérateur* : avant éléments extraordinaires, zakat et impôts ; *Actif total moyen* : moyenne du stock d'actifs totaux sur la période de référence. |
| Signification économique | Mesure l'efficacité d'utilisation des actifs pour générer du profit ; standard de comparaison entre systèmes Takaful de différents pays. |
| Sens d'interprétation | Plus élevé = meilleur |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel, même réserve que ROE sur le périmètre du numérateur (résultat de l'Opérateur uniquement) |
| Différences avec le conventionnel | Idem ROE : périmètre du résultat net restreint à l'Opérateur, exclusion du résultat technique participants |
| Référence bibliographique | IFSB (2019), *Compilation Guide on PSIFIs*, ratio TP19, p.96 ; corroboré par Abdou, Ali & Lister (2014), p.8 : ROA = profit after tax / total assets |
| Citation page/paragraphe | « The ROA is a profitability ratio that measures the ability of a takful/retakful operator to generate profits from its shareholders' fund » — IFSB PSIFI Compilation Guide, p.96 |
| Fiabilité | ⭐⭐⭐⭐⭐ (source IFSB + validation croisée académique) |

#### R3. Ratio de revenu d'investissement sur contributions (Investment income ratio)

| Champ | Contenu |
|---|---|
| Catégorie | Rentabilité |
| Formule | Ratio = Revenu d'investissement / Contribution nette (prime acquise) |
| Variables | *Revenu d'investissement* : revenus tirés des placements du TO/des fonds ; *Contribution nette* : portion de la contribution reconnue en produit sur la période. |
| Signification économique | Compare les revenus tirés de l'activité de placement à ceux tirés de l'activité d'assurance/Takaful elle-même. |
| Sens d'interprétation | Plus élevé = meilleur (indique une bonne capacité à faire fructifier les excédents) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel dans sa forme, mais les placements doivent être Sharia-compliant (exclusion des instruments à intérêt, du gharar et du maysir) |
| Différences avec le conventionnel | Univers d'investissement restreint aux actifs conformes à la Sharia (Sukuk, actions filtrées, Murabaha, Ijarah) — cf. IFSB-11 Figure 2, p.16-17, sur les risques de marché spécifiques (Salam, Sukuk, Murabaha, Ijarah) |
| Référence bibliographique | IFSB (2019), ratio TP15, p.95 ; corroboré par Abdou, Ali & Lister (2014), p.8 : « Investment income ratio = investment income / premium earned » |
| Citation page/paragraphe | « The investment income ratio is the ratio of an insurance company's net investment income to its earned premiums » — IFSB PSIFI Compilation Guide, p.95 |
| Fiabilité | ⭐⭐⭐⭐⭐ (source IFSB + validation croisée académique) |

#### R4. Revenu d'investissement sur actifs investis

| Champ | Contenu |
|---|---|
| Catégorie | Rentabilité |
| Formule | Ratio = Revenu d'investissement / Actifs investis (Investment assets) |
| Variables | *Actifs investis* : actions, Sukuk, biens immobiliers de placement. |
| Signification économique | Mesure le rendement direct du portefeuille de placements, indépendamment du volume de contributions. |
| Sens d'interprétation | Plus élevé = meilleur |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel (ratio réservé au Takaful familial selon la source) |
| Différences avec le conventionnel | Univers d'investissement Sharia-compliant uniquement |
| Référence bibliographique | IFSB (2019), ratio TP16, p.95 — une seule source trouvée pour cette formulation précise |
| Citation page/paragraphe | « The indicator compares the income that a TO brings in from its investment activities, rather than from its operations » — IFSB PSIFI Compilation Guide, p.95 |
| Fiabilité | ⭐⭐⭐⭐⭐ (norme IFSB, une seule source) |

---

## 6. Catégorie : SOLVABILITÉ / ADÉQUATION DES FONDS PROPRES

### 6.1 Tableau de synthèse

| # | Ratio (FR) | Ratio (EN) | Formule (résumé) | Sens | Fiabilité |
|---|---|---|---|---|---|
| S1 | Ratio d'adéquation des fonds propres fondé sur le risque | Risk-based Capital Adequacy Ratio (CAR/SCR) | Ressources de capital éligibles / Exigence minimale de capital | Plus élevé = meilleur | ⭐⭐⭐⭐⭐ |
| S2 | Exigence de solvabilité du Fonds des Participants | Solvency Requirement (SR) for PRF | Somme des composantes de risque (provisionnement, souscription, crédit, marché, opérationnel) | Plus faible = meilleur (moins de capital requis) | ⭐⭐⭐⭐⭐ |
| S3 | Exigence de capital de l'Opérateur Takaful | Capital Requirement (CR) for TO | Somme des composantes de risque (crédit, marché, opérationnel) | Plus faible = meilleur | ⭐⭐⭐⭐⭐ |
| S4 | Dettes totales sur capitaux propres | Total liabilities to shareholders' equity | Total des dettes / Capitaux propres | Plus faible = meilleur | ⭐⭐⭐⭐⭐ |
| S5 | Dettes totales sur actif total | Total liabilities to total assets | Total des dettes / Actif total | Plus faible = meilleur (>100% = alerte) | ⭐⭐⭐⭐⭐ |
| S6 | Actifs admissibles sur actif total | Admissible assets to total assets | Actifs admissibles / Actif total | Plus élevé = meilleur | ⭐⭐⭐⭐⭐ |
| S7 | Ratio prime/surplus (branche vie/famille) | Premium to surplus ratio (family) | Primes émises / Surplus (famille) | Plus faible = meilleur | ⭐⭐⭐ |
| S8 | Ratio prime/surplus (global) | Premium to surplus ratio (overall) | Primes émises / Surplus (global) | Plus faible = meilleur | ⭐⭐⭐ |
| S9 | Actif total sur contributions nettes | Total assets to net contributions | Actif total / Contributions nettes émises | Plus élevé = meilleur | ⭐⭐⭐ |

### 6.2 Fiches détaillées

#### S1. Ratio d'adéquation des fonds propres fondé sur le risque

| Champ | Contenu |
|---|---|
| Catégorie | Solvabilité |
| Formule | CAR = Ressources de capital éligibles (Tier 1 + Tier 2, déductions faites) / Exigence minimale de capital |
| Variables | *Tier 1* : actions ordinaires libérées, primes d'émission, actions préférentielles non cumulatives, réserves, résultats non distribués, surplus de réévaluation des fonds Takaful ; *Tier 2* : actions préférentielles cumulatives, dettes subordonnées, réserves de réévaluation, **Qard du fonds des actionnaires** ; *Exigence minimale de capital* : montant fixé par le superviseur selon une méthode fondée sur le risque. |
| Signification économique | Vérifie que le capital disponible du Takaful Operator/Fonds couvre l'exigence réglementaire minimale calculée selon le profil de risque. |
| Sens d'interprétation | Plus élevé = meilleur ; en dessous du seuil réglementaire = intervention du superviseur |
| Valeur cible / seuil | Seuil fixé par chaque autorité de supervision nationale (non chiffré dans la norme elle-même — laissé à la discrétion du régulateur local) |
| Applicabilité au Takaful | Spécifique Takaful dans sa composition (le Qard du fonds des actionnaires comme élément de Tier 2 est propre au Takaful) |
| Différences avec le conventionnel | Le Tier 2 inclut le **Qard from shareholders' fund**, mécanisme sans équivalent en assurance conventionnelle ; note de bas de page de la source : certaines juridictions utilisent alternativement un « solvency ratio » = actifs nets admissibles / exigence minimale de capital |
| Référence bibliographique | IFSB (2019), *Compilation Guide on PSIFIs*, ratio TP01, p.90-91 |
| Citation page/paragraphe | « The total capital available considers the capital available in the shareholders' fund that is fully available to support the risks of the business or to give a qard to the participants' risk funds when needed » — p.90 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### S2. Exigence de solvabilité du Fonds des Participants (Solvency Requirement, SR)

| Champ | Contenu |
|---|---|
| Catégorie | Solvabilité |
| Formule | SR = RCPR + RCUR + RCCR + RCMR + RCOR |
| Variables | RCPR = composante de risque de provisionnement/réserves ; RCUR = composante de risque de souscription ; RCCR = composante de risque de crédit ; RCMR = composante de risque de marché ; RCOR = composante de risque opérationnel (tous appliqués au Participants' Risk Fund) |
| Signification économique | Détermine le montant de capital que le PRF doit détenir pour couvrir, avec une probabilité définie (ex. 99,5 % sur 1 an), l'ensemble des risques auxquels le fonds des participants est exposé. |
| Sens d'interprétation | Plus l'exigence calculée est élevée, plus le fonds doit être capitalisé (via réserves ou Qard) ; ce n'est pas un ratio au sens strict mais une décomposition additive de l'exigence de capital |
| Valeur cible / seuil | Non spécifié — la probabilité cible (ex. 99,5 % à horizon 1 an) est donnée à titre d'exemple, pas comme seuil obligatoire |
| Applicabilité au Takaful | **Spécifique Takaful sans équivalent conventionnel direct** — décomposition propre à la structure à deux fonds |
| Différences avec le conventionnel | Un assureur conventionnel calcule une seule exigence de solvabilité pour l'ensemble de l'entité ; le Takaful calcule **deux exigences séparées** (PRF et TO), reflet de la ségrégation des fonds (IFSB-11 §11, p.3) |
| Référence bibliographique | IFSB (2010), *IFSB-11 — Standard on Solvency Requirements for Takaful (Islamic Insurance) Undertakings*, §62, p.16-17 |
| Citation page/paragraphe | « the general formulae for the solvency requirements for a Takful undertaking could be as follows: For PRF: SR = RCPR + RCUR + RCCR + RCMR + RCOR » — IFSB-11, §62, p.16-17 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### S3. Exigence de capital de l'Opérateur Takaful (Capital Requirement, CR)

| Champ | Contenu |
|---|---|
| Catégorie | Solvabilité |
| Formule | CR = RCCR + RCMR + RCOR |
| Variables | Mêmes composantes que S2 (crédit, marché, opérationnel) mais appliquées au Takaful Operator/Shareholders' Fund ; le risque de provisionnement/souscription (RCPR, RCUR) n'est pas inclus car il relève du PRF, pas du TO. |
| Signification économique | Détermine le capital que l'Opérateur doit détenir pour ses propres risques (hors risque technique porté par les participants). |
| Sens d'interprétation | Idem S2 — exigence additive, pas un ratio de division |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Spécifique Takaful sans équivalent conventionnel direct |
| Différences avec le conventionnel | L'absence de composante de risque de souscription dans le CR de l'Opérateur illustre que le risque technique est supporté par les participants (PRF), pas par les actionnaires — différence fondamentale avec un assureur conventionnel où l'actionnaire porte l'intégralité du risque technique |
| Référence bibliographique | IFSB (2010), IFSB-11, §62, p.17 |
| Citation page/paragraphe | « For Takful operator: CR = RCCR + RCMR + RCOR » — IFSB-11, §62, p.17 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### S4. Dettes totales sur capitaux propres (leverage)

| Champ | Contenu |
|---|---|
| Catégorie | Solvabilité / Levier |
| Formule | Ratio = Total des dettes (liabilities) / Capitaux propres (Shareholders' equity) |
| Variables | *Total des dettes* : ensemble des engagements du Takaful/Retakaful Operator ; *Capitaux propres* : fonds des actionnaires. |
| Signification économique | Mesure la proportion de dettes portée par l'entité par rapport à ses fonds propres. |
| Sens d'interprétation | Plus faible = meilleur (moins de risque de ne pas honorer les engagements à long terme) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel — même logique comptable, périmètre limité aux actifs/passifs de l'opérateur Takaful/Retakaful (domestique ou succursale) |
| Différences avec le conventionnel | Le périmètre exclut les « fenêtres Takaful » (Takaful windows) d'assureurs conventionnels, qui doivent être déclarées séparément selon la norme |
| Référence bibliographique | IFSB (2019), ratio TS12, p.100 |
| Citation page/paragraphe | « This ratio measures the proportion of liabilities a company is carrying relative to its equity. A lower value suggests that there is a lower risk... » — p.100 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### S5. Dettes totales sur actif total

| Champ | Contenu |
|---|---|
| Catégorie | Solvabilité / Levier |
| Formule | Ratio = Total des dettes / Actif total |
| Variables | Idem S4, dénominateur = actif total. |
| Signification économique | Mesure la proportion de l'actif financée par des dettes plutôt que par des fonds propres. |
| Sens d'interprétation | Plus faible = meilleur ; une valeur >100 % signale que les dettes dépassent les actifs couvrables |
| Valeur cible / seuil | Seuil implicite : 100 % (au-delà, alerte explicite dans la source) |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Même remarque que S4 sur le périmètre (hors fenêtres Takaful) |
| Référence bibliographique | IFSB (2019), ratio TS13, p.100-101 |
| Citation page/paragraphe | « A value greater than 100% indicates a company has more liabilities than can be covered by the assets » — p.100 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### S6. Actifs admissibles sur actif total

| Champ | Contenu |
|---|---|
| Catégorie | Solvabilité |
| Formule | Ratio = Actifs admissibles (Admissible assets) / Actif total |
| Variables | *Actifs admissibles* : actifs jugés de haute qualité et suffisamment liquides par le superviseur national pour couvrir les sinistres attendus (hypothèques, créances, Sukuk, certificats conformes à la Sharia) ; la définition varie selon les juridictions. |
| Signification économique | Indique la part des actifs jugés fiables pour couvrir les engagements techniques. |
| Sens d'interprétation | Plus élevé = meilleur |
| Valeur cible / seuil | Non spécifié (dépend de la définition nationale des « actifs admissibles ») |
| Applicabilité au Takaful | Adapté du conventionnel, avec composition d'actifs admissibles Sharia-compliant (Sukuk notamment) |
| Différences avec le conventionnel | Composition des actifs admissibles restreinte aux instruments conformes à la Sharia |
| Référence bibliographique | IFSB (2019), ratio TS14, p.101 |
| Citation page/paragraphe | « Admitted assets often include mortgages, accounts receivable, sukuk and Shariah-compliant certificates » — p.101 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### S7 / S8. Ratio prime/surplus (famille et global)

| Champ | Contenu |
|---|---|
| Catégorie | Solvabilité |
| Formule | (f) Ratio = Primes émises (branche famille/vie) / Surplus (famille) ; (o) Ratio = Primes émises (toutes branches) / Surplus (global secteur) |
| Variables | *Primes émises* : montant des primes/contributions écrites ; *Surplus* : excédent statutaire (actif moins passif) du secteur ou de la compagnie. |
| Signification économique | Mesure le niveau de capital-surplus nécessaire pour soutenir le volume de primes écrites ; une compagnie doit avoir un bilan suffisamment pourvu en actifs pour honorer les sinistres. |
| Sens d'interprétation | Plus faible = meilleur (plus grande solidité financière) |
| Valeur cible / seuil | Non spécifié dans l'article — la source donne des exemples illustratifs (95 % vs 102 %) sans fixer de seuil réglementaire |
| Applicabilité au Takaful | Adapté du conventionnel — ratio appliqué identiquement aux deux industries dans l'étude empirique malaisienne, sans reformulation Takaful-spécifique documentée |
| Différences avec le conventionnel | **Aucune définition Takaful officielle trouvée dans les sources IFSB consultées** pour ce ratio précis — il est directement importé de la pratique actuarielle conventionnelle par les auteurs de l'article ; la notion de « surplus » en Takaful devrait en toute rigueur être précisée (surplus du PRF vs capitaux propres du SHF), mais l'article ne fait pas cette distinction |
| Référence bibliographique | Abdou, H. A., Ali, K., & Lister, R. J. (2014). *A comparative study of Takaful and conventional insurance: empirical evidence from the Malaysian market*. Insurance Markets and Companies, 5(1), 22-34, p.8-9. Une seule source trouvée pour cette formulation précise. |
| Citation page/paragraphe | « Premium to surplus ratio (f) = premium written / surplus (family/life)... A lower ratio in this case is indicative of a company having greater financial strength » — p.8-9 |
| Fiabilité | ⭐⭐⭐ (source académique unique, non recoupée avec une norme IFSB/AAOIFI) |

#### S9. Actif total sur contributions nettes

| Champ | Contenu |
|---|---|
| Catégorie | Solvabilité |
| Formule | Ratio = Actif total / Contributions nettes (primes écrites) |
| Variables | *Contributions nettes* : primes/contributions nettes écrites, utilisées comme proxy du risque assumé plutôt que le montant total assuré. |
| Signification économique | Mesure la taille du capital de la compagnie relativement au volume d'affaires souscrit ; mesure basique de solidité financière. |
| Sens d'interprétation | Plus élevé = meilleur (plus solvable) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel — appliqué identiquement dans l'étude comparative |
| Différences avec le conventionnel | Aucune adaptation Takaful documentée dans la source ; ratio d'assurance générale appliqué tel quel |
| Référence bibliographique | Abdou, Ali & Lister (2014), p.9. Une seule source trouvée. |
| Citation page/paragraphe | « Total assets to total net contribution ratio examines the size of insurance company's capital relative to the premiums written » — p.9 |
| Fiabilité | ⭐⭐⭐ |

---

## 7. Catégorie : LIQUIDITÉ

### 7.1 Tableau de synthèse

| # | Ratio (FR) | Ratio (EN) | Formule (résumé) | Sens | Fiabilité |
|---|---|---|---|---|---|
| L1 | Ratio de liquidité générale | Current ratio | Actifs courants / Passifs courants | Plus élevé = meilleur | ⭐⭐⭐ |
| L2 | Actifs liquides sur passifs courants | Liquid assets to current liabilities | Actifs liquides / Passifs courants | Plus élevé = meilleur | ⭐⭐⭐⭐⭐ |

### 7.2 Fiches détaillées

#### L1. Ratio de liquidité générale (Current ratio)

| Champ | Contenu |
|---|---|
| Catégorie | Liquidité |
| Formule | Ratio = Actifs courants / Passifs courants |
| Variables | Non détaillées dans le corps du texte consulté — seul le nom de l'indicateur (« Current ratio ») figure dans la table des matières et le tableau récapitulatif (Table 7.1) de la source ; sa formule usuelle en comptabilité générale a été retenue par défaut. |
| Signification économique | Teste la capacité à honorer les engagements à court terme avec les actifs courants disponibles. |
| Sens d'interprétation | Plus élevé = meilleur |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Aucune différence documentée dans les sources consultées pour ce ratio précis |
| Référence bibliographique | IFSB (2019), indicateur TP22 (catégorie Liquidité), listé p.xix et Table 7.1, p.88 — **formule non explicitée dans le corps de texte consulté**, contrairement aux autres ratios de ce document |
| Citation page/paragraphe | « 6. LIQUIDITY — TP22 Current ratio » — table des matières, p.xix (aucun développement trouvé au chapitre 7.4) |
| Fiabilité | ⭐⭐⭐ (nom confirmé par une norme IFSB, mais formule non retrouvée explicitement dans le texte consulté — abaissé par prudence, à vérifier auprès d'IFSB si besoin) |

#### L2. Actifs liquides sur passifs courants

| Champ | Contenu |
|---|---|
| Catégorie | Liquidité |
| Formule | Ratio = Actifs liquides (Liquid assets) / Passifs courants (Current liabilities) |
| Variables | *Actifs liquides* : trésorerie et équivalents, placements rapidement mobilisables. |
| Signification économique | Teste la suffisance des actifs liquides pour couvrir les obligations à court terme. |
| Sens d'interprétation | Plus élevé = meilleur |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel — indicateur repris à la fois dans la liste « Prudential » (TP23) et « Additional Prudential » (TA08/TA10) du même document |
| Différences avec le conventionnel | Aucune différence de fond documentée, mais le calcul doit exclure les actifs non Sharia-compliant du périmètre « actifs liquides » |
| Référence bibliographique | IFSB (2019), ratios TP23 / TA08, p.98 |
| Citation page/paragraphe | « The ratio tests how sufficient the company's liquid assets are to meet the company's obligations in the short term. A higher value is preferred » — p.98 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

---

## 8. Catégorie : TECHNIQUE / SOUSCRIPTION

### 8.1 Tableau de synthèse

| # | Ratio (FR) | Ratio (EN) | Formule (résumé) | Sens | Fiabilité |
|---|---|---|---|---|---|
| T1 | Ratio des réserves techniques | Technical reserves ratio | Réserves de primes / Réserves de sinistres | Non spécifié (indicateur d'équilibre) | ⭐⭐⭐⭐⭐ |
| T2 | Ratio de survie (sinistres) | Survival ratio (claims) | Réserve technique / Moyenne des sinistres payés (3 ans) | Plus élevé = meilleur | ⭐⭐⭐⭐⭐ |
| T3 | Ratio de sinistralité | Loss ratio | Sinistres encourus / Contributions nettes | Plus faible = meilleur | ⭐⭐⭐⭐⭐ |
| T4 | Ratio de sinistres payés | Claims ratio | Total sinistres payés / Contributions nettes acquises | Plus faible = meilleur | ⭐⭐⭐⭐⭐ |
| T5 | Ratio de charges (sur contribution brute) | Expense ratio | Charges / Contribution brute | Plus faible = meilleur | ⭐⭐⭐⭐⭐ |
| T6 | Ratio combiné | Combined ratio | Ratio de sinistralité + Ratio de charges d'exploitation | <100 % = souscription profitable | ⭐⭐⭐⭐⭐ |

### 8.2 Fiches détaillées

#### T1. Ratio des réserves techniques

| Champ | Contenu |
|---|---|
| Catégorie | Technique |
| Formule | Ratio = Réserves de primes (Premium liabilities) / Réserves de sinistres (Claims liabilities) |
| Variables | *Réserves de primes* : calculées à partir des réserves de primes non acquises (unearned premium reserves) ; *Réserves de sinistres* : provisions pour sinistres à payer et frais afférents. |
| Signification économique | Indique le montant mis de côté sur les contributions pour couvrir les sinistres attendus des participants. |
| Sens d'interprétation | Non spécifié explicitement (indicateur d'équilibre entre les deux types de réserves plutôt qu'un sens univoque) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel — réservé au Takaful familial selon la source |
| Différences avec le conventionnel | Les réserves techniques sont détenues au niveau du PRF, propriété collective des participants, non des actionnaires |
| Référence bibliographique | IFSB (2019), ratio TP02, p.91-92 |
| Citation page/paragraphe | « Technical reserves are the amounts that the takful/retakful companies set aside from premiums to cover claims for takful participants » — p.91 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### T2. Ratio de survie (claims)

| Champ | Contenu |
|---|---|
| Catégorie | Technique |
| Formule | Ratio = Réserve technique / Moyenne des sinistres payés sur les 3 dernières années |
| Variables | *Réserve technique* : voir T1 ; *Moyenne des sinistres payés* : moyenne arithmétique des paiements de sinistres des 3 exercices précédents. |
| Signification économique | Indique combien d'années de sinistres moyens la réserve technique actuelle pourrait couvrir. |
| Sens d'interprétation | Plus élevé = meilleur (plus grande marge de sécurité) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel — réservé au Takaful familial |
| Différences avec le conventionnel | Aucune différence de fond documentée |
| Référence bibliographique | IFSB (2019), ratio TP08, p.93 |
| Citation page/paragraphe | « The survival ratio is defined as held technical reserves divided by average of claims paid » — p.93 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### T3. Ratio de sinistralité (Loss ratio)

| Champ | Contenu |
|---|---|
| Catégorie | Technique |
| Formule | Ratio = Sinistres encourus (Loss incurred) / Contributions nettes |
| Variables | *Sinistres encourus* : charge de sinistres de la période ; *Contributions nettes* : portion de la contribution reconnue en produit sur la période écoulée du contrat. |
| Signification économique | Indique dans quelle mesure la tarification des contrats Takaful correspond aux risques effectivement pris en charge. |
| Sens d'interprétation | Plus faible = meilleur (mais un ratio trop bas peut aussi signaler une tarification excessive) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel — même construction que le loss ratio classique |
| Différences avec le conventionnel | La contribution est un don mutuel (Tabarru'), non une prime d'échange commercial ; le ratio mesure in fine l'équilibre du fonds mutuel des participants (PRF), pas la rentabilité de l'assureur |
| Référence bibliographique | IFSB (2019), ratio TP12, p.94 (réservé au Takaful général) |
| Citation page/paragraphe | « This ratio refers to the ratio of loss incurred to net contributions. The ratio gives an indication of how well the pricing... matches risks taken » — p.94 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### T4. Ratio de sinistres payés (Claims ratio)

| Champ | Contenu |
|---|---|
| Catégorie | Technique |
| Formule | Ratio = Total des sinistres payés / Contributions nettes acquises |
| Variables | *Total des sinistres payés* : décaissements effectifs aux participants sur la période ; *Contributions nettes acquises* : contributions nettes reconnues en produit sur la même période. |
| Signification économique | Mesure la part des contributions acquises reversée aux participants sous forme de sinistres. |
| Sens d'interprétation | Plus faible = meilleur |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel, formule confirmée par deux sources indépendantes |
| Différences avec le conventionnel | Idem T3 — reflète l'équilibre du fonds mutuel des participants |
| Référence bibliographique | IFSB (2019), ratio TP13, p.94, **corroboré par une seconde source** : Abdou, Ali & Lister (2014), p.8, qui définissent un ratio conceptuellement identique : « Net claims incurred / net contribution » |
| Citation page/paragraphe | « It measures the total claims paid out to policyholders by the takful company as a percentage of net earned contributions » — IFSB PSIFI Compilation Guide, p.94 |
| Fiabilité | ⭐⭐⭐⭐⭐ (double source : IFSB + article académique) |

#### T5. Ratio de charges (sur contribution brute) (Expense ratio)

| Champ | Contenu |
|---|---|
| Catégorie | Technique |
| Formule | Ratio = Charges (Expense) / Contribution brute (Gross contribution) |
| Variables | *Charges* : frais liés à l'acquisition, la souscription et la gestion des primes (publicité, salaires, etc.) ; *Contribution brute* : contributions totales du TO avant retakaful. |
| Signification économique | Mesure de rentabilité calculée en rapportant les charges d'acquisition/souscription/gestion au volume brut d'affaires. |
| Sens d'interprétation | Plus faible = meilleur |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Distinct du ratio de charges d'exploitation (G1, dénominateur = contributions nettes) — l'IFSB définit les deux séparément, à ne pas confondre |
| Référence bibliographique | IFSB (2019), ratio TP14, p.95 |
| Citation page/paragraphe | « The expense ratio in the takful industry is a measure of profitability calculated by dividing the expenses... by gross contribution » — p.95 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### T6. Ratio combiné (Combined ratio)

| Champ | Contenu |
|---|---|
| Catégorie | Technique |
| Formule | Ratio combiné = Ratio de sinistralité (T3) + Ratio de charges d'exploitation (G1) |
| Variables | Somme du loss ratio (TP12) et de l'operating expense ratio (TP09), tous deux exprimés en % des contributions. |
| Signification économique | Mesure globale de la rentabilité de la souscription, combinant coût des sinistres et coût de gestion. |
| Sens d'interprétation | Plus faible = meilleur ; un ratio combiné inférieur à 100 % indique une souscription techniquement profitable avant résultat financier |
| Valeur cible / seuil | Seuil implicite : 100 % (usage standard du secteur, non chiffré explicitement comme obligation réglementaire dans la source IFSB) |
| Applicabilité au Takaful | Adapté du conventionnel — réservé au Takaful général selon la source |
| Différences avec le conventionnel | La profitabilité mesurée est celle du fonds mutuel des participants (PRF), pas celle de l'actionnaire ; un ratio combiné favorable au Takaful ne se traduit pas mécaniquement en profit actionnarial comme en conventionnel |
| Référence bibliographique | IFSB (2019), ratio TP17, p.95 |
| Citation page/paragraphe | « The combined ratio is a reflection of the underwriting expenses as well as operating expenses structure of the TO » — p.95 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

---

## 9. Catégorie : GESTION / EFFICIENCE

### 9.1 Tableau de synthèse

| # | Ratio (FR) | Ratio (EN) | Formule (résumé) | Sens | Fiabilité |
|---|---|---|---|---|---|
| G1 | Ratio de charges d'exploitation | Operating expense ratio | Charges / Contributions nettes | Plus faible = meilleur | ⭐⭐⭐⭐⭐ |
| G2 | Contributions à recevoir sur contributions émises | Contribution receivable to written contribution | Contributions à recevoir / Contributions émises | Plus faible = meilleur | ⭐⭐⭐⭐⭐ |
| G3 | Prime brute par employé | Gross premium / Number of employees | Contribution brute / Effectif | Plus élevé = meilleur (productivité) | ⭐⭐⭐⭐⭐ |
| G4 | Actif par employé | Assets per employee | Actif total / Effectif | Plus élevé = meilleur (productivité) | ⭐⭐⭐⭐⭐ |
| G5 | Revenus d'exploitation sur résultat technique | Operating revenues / Underwriting profit | (Revenus totaux − plus/moins-values réalisées et latentes) / Résultat technique | Non spécifié | ⭐⭐⭐⭐⭐ |

### 9.2 Fiches détaillées

#### G1. Ratio de charges d'exploitation (Operating expense ratio)

| Champ | Contenu |
|---|---|
| Catégorie | Gestion |
| Formule | Ratio = Charges d'exploitation / Contributions nettes |
| Variables | *Charges d'exploitation* : personnel, administration, loyers, achats de biens/services, amortissements, provisions, hors charges financières ; *Contributions nettes* : contributions nettes de commissions, au taux net facturé aux clients. |
| Signification économique | Reflète l'efficacité opérationnelle de l'Opérateur Takaful/Retakaful. |
| Sens d'interprétation | Plus faible = meilleur |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel — distinct du ratio de charges T5 (dénominateur brut vs net) |
| Différences avec le conventionnel | Aucune différence de fond documentée au-delà de la terminologie (contribution vs prime) |
| Référence bibliographique | IFSB (2019), ratio TP09, p.93-94 |
| Citation page/paragraphe | « This is the ratio of operating expenses over net premium contributions. Expense ratio reflects the efficiency of takful/retakful undertakings » — p.93 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### G2. Contributions à recevoir sur contributions émises

| Champ | Contenu |
|---|---|
| Catégorie | Gestion |
| Formule | Ratio = Contributions à recevoir (Contribution receivable) / Contributions émises (Written contribution) |
| Variables | *Contributions à recevoir* : contributions facturées mais non encore encaissées. |
| Signification économique | Mesure la part des contributions émises non encore recouvrées par la compagnie. |
| Sens d'interprétation | Plus faible = meilleur (meilleur taux de recouvrement) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Aucune différence de fond documentée |
| Référence bibliographique | IFSB (2019), ratio TP06, p.92-93 |
| Citation page/paragraphe | « This ratio measures how much of the written contribution is not yet received by the company. A lower ratio is preferred » — p.92 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### G3. Prime brute par employé

| Champ | Contenu |
|---|---|
| Catégorie | Gestion / Performance |
| Formule | Ratio = Contribution brute directe / Nombre d'employés du Takaful Operator |
| Variables | Effectif = nombre d'employés à temps plein en fin de période. |
| Signification économique | Mesure l'efficacité relative de l'industrie Takaful nationale rapportée au nombre d'employés. |
| Sens d'interprétation | Plus élevé = meilleur (productivité) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Aucune différence de fond documentée |
| Référence bibliographique | IFSB (2019), ratio TP10, p.94 |
| Citation page/paragraphe | « This ratio indicates that the relative efficiency of a national takful industry is calculated by dividing the direct gross premiums by the number of employees » — p.94 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### G4. Actif par employé

| Champ | Contenu |
|---|---|
| Catégorie | Gestion / Performance |
| Formule | Ratio = Actif total / Nombre d'employés à temps plein |
| Variables | Idem G3 pour l'effectif. |
| Signification économique | Mesure la taille d'actifs gérés par employé. |
| Sens d'interprétation | Plus élevé = meilleur (productivité) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Aucune différence de fond documentée |
| Référence bibliographique | IFSB (2019), ratio TP11, p.94 |
| Citation page/paragraphe | « This is the ratio of total assets divided by the number of full-time employees at the end of the reporting period » — p.94 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### G5. Revenus d'exploitation sur résultat technique

| Champ | Contenu |
|---|---|
| Catégorie | Gestion / Performance |
| Formule | Ratio = (Revenus totaux − plus/moins-values réalisées et latentes) / Résultat technique (Underwriting profit) |
| Variables | *Revenus totaux* : total des produits hors gains/pertes en capital réalisés et latents (« other comprehensive income ») ; *Résultat technique* : prime acquise nette après sinistres et charges administratives. |
| Signification économique | Rapporte le volume de revenus d'exploitation générés au résultat technique de souscription dégagé. |
| Sens d'interprétation | Non spécifié explicitement dans la source |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Le résultat technique appartient in fine au PRF/aux participants ; ce ratio, appliqué à l'Opérateur, doit être interprété avec prudence quant à la propriété économique du résultat |
| Référence bibliographique | IFSB (2019), ratio TA01, p.96-97 |
| Citation page/paragraphe | « Underwriting profit consists of the earned premium remaining after losses have been paid and administrative expenses have been deducted » — p.96 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

---

## 10. Catégorie : RÉASSURANCE / RETAKAFUL

### 10.1 Tableau de synthèse

| # | Ratio (FR) | Ratio (EN) | Formule (résumé) | Sens | Fiabilité |
|---|---|---|---|---|---|
| RT1 | Taux de rétention du risque | Risk retention ratio | Contribution nette / Contribution brute | Ni trop haut ni trop bas — dépend du marché | ⭐⭐⭐⭐⭐ |

### 10.2 Fiche détaillée

#### RT1. Taux de rétention du risque (Risk retention ratio)

| Champ | Contenu |
|---|---|
| Catégorie | Réassurance / Retakaful |
| Formule | Ratio = Contribution nette (contributions brutes moins contributions cédées en retakaful) / Contribution brute totale |
| Variables | *Contribution nette* : montant net après déduction des contributions rendues et des paiements liés au retakaful cédé ; *Contribution brute* : contributions totales avant cession. |
| Signification économique | Mesure le niveau de risque conservé par l'Opérateur Takaful plutôt que transféré à des compagnies de retakaful. |
| Sens d'interprétation | Ni « plus élevé » ni « plus faible » n'est intrinsèquement meilleur : un niveau normal varie selon les branches et les conditions de marché ; un niveau faible ou en baisse peut signaler une infrastructure de retakaful inadéquate ou des difficultés financières des Opérateurs primaires |
| Valeur cible / seuil | Non spécifié (niveaux « normaux » variables selon branche et marché, non chiffrés) |
| Applicabilité au Takaful | Spécifique Takaful dans sa dénomination (Retakaful plutôt que réassurance), formule identique au ratio de rétention conventionnel |
| Différences avec le conventionnel | Le retakaful doit lui-même être structuré selon des principes Sharia-compliant (partage mutuel des risques) ; IFSB-14 (§28, p.660-690) discute par ailleurs des conditions dans lesquelles le recours à la réassurance conventionnelle peut être toléré à titre exceptionnel (absence d'offre retakaful suffisante), question sans équivalent en assurance conventionnelle |
| Référence bibliographique | IFSB (2019), ratio TP07, p.93 ; contexte complémentaire : IFSB (2013), *IFSB-14 — Standard on Risk Management for Takaful Undertakings*, §28 |
| Citation page/paragraphe | « The risk retention ratio measures the risk that is not passed on to retakful companies. It indicates the level of risks retained by the TO » — IFSB PSIFI Compilation Guide, p.93 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

---

## 11. Catégorie : INVESTISSEMENT ET QUALITÉ DES ACTIFS

### 11.1 Tableau de synthèse

| # | Ratio (FR) | Ratio (EN) | Formule (résumé) | Sens | Fiabilité |
|---|---|---|---|---|---|
| I1 | Actions sur actif total | Equities to total assets | Actions / Actif total | Non spécifié (indicateur de structure) | ⭐⭐⭐⭐⭐ |
| I2 | Actifs investis totaux sur capitaux propres | Total investment assets to shareholders' equity | Actifs investis / Capitaux propres | Indicateur de levier — non univoque | ⭐⭐⭐⭐⭐ |
| I3 | (Immobilier + actions non cotées + débiteurs) / actif total | (Real estate + unquoted equities + debtors) / total assets | Somme de 3 postes risqués / Actif total | Plus faible = moins de risque de conflit d'intérêt | ⭐⭐⭐⭐⭐ |
| I4 | Créances > 180 jours sur capitaux propres | Receivables due over 180 days to shareholders' equity | Créances en souffrance >180j / Capitaux propres | Plus faible = meilleur | ⭐⭐⭐⭐⭐ |

### 11.2 Fiches détaillées

#### I1. Actions sur actif total

| Champ | Contenu |
|---|---|
| Catégorie | Investissement / Qualité des actifs |
| Formule | Ratio = Actions (Equities) / Actif total |
| Variables | *Actions* : participations et titres de capital détenus par le Takaful Operator. |
| Signification économique | Mesure la part de l'actif financée par les investisseurs et non par de l'endettement. |
| Sens d'interprétation | Non explicitement univoque dans la source (indicateur de structure du bilan, à examiner avec le contexte) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel, avec restriction Sharia sur les actions éligibles (filtrage sectoriel et financier) |
| Différences avec le conventionnel | Filtrage Sharia des actions détenues (exclusion des sociétés à activité ou endettement non conformes) |
| Référence bibliographique | IFSB (2019), ratio TP05, p.92 |
| Citation page/paragraphe | « This ratio measures how much of the TO's assets are owned by investors and are not leveraged » — p.92 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### I2. Actifs investis totaux sur capitaux propres

| Champ | Contenu |
|---|---|
| Catégorie | Investissement / Levier |
| Formule | Ratio = Actifs investis totaux / Capitaux propres |
| Variables | *Actifs investis totaux* : investissements en actions, Sukuk et immobilier de placement (hors actifs non financiers d'exploitation). |
| Signification économique | Mesure du levier financier lié à l'activité d'investissement. |
| Sens d'interprétation | Non univoque — un ratio élevé indique une forte exposition aux placements relativement aux fonds propres, à interpréter selon le contexte |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Univers de placement Sharia-compliant (Sukuk plutôt qu'obligations classiques) |
| Référence bibliographique | IFSB (2019), ratio TP20, p.96 |
| Citation page/paragraphe | « This is a ratio of total invested assets to takful/retakful companies' shareholders' equity. The indicator is a measurement of financial leverage » — p.96 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### I3. (Immobilier + actions non cotées + débiteurs) / actif total

| Champ | Contenu |
|---|---|
| Catégorie | Investissement / Qualité des actifs |
| Formule | Ratio = (Immobilier + actions non cotées + débiteurs) / Actif total |
| Variables | Trois catégories d'actifs jugées à risque particulier par l'IFSB en raison de leur faible liquidité et du risque de conflit d'intérêt associé. |
| Signification économique | Évalue la qualité des actifs à partir du poids des catégories d'actifs les plus risquées/les moins liquides. |
| Sens d'interprétation | Plus faible = meilleur (moins d'exposition à des actifs à risque particulier) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel |
| Différences avec le conventionnel | Aucune différence de fond documentée |
| Référence bibliographique | IFSB (2019), ratio TP03, p.92 |
| Citation page/paragraphe | « The certain types of investments (e.g. real estate, unquoted equities, debtors) involve special risks and may raise a conflict of interest » — p.92 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### I4. Créances > 180 jours sur capitaux propres

| Champ | Contenu |
|---|---|
| Catégorie | Investissement / Qualité des actifs |
| Formule | Ratio = Créances en souffrance depuis plus de 180 jours / Capitaux propres |
| Variables | *Créances en souffrance >180 jours* : montants dus non recouvrés depuis plus de 6 mois. |
| Signification économique | Indique l'ampleur des créances très en retard rapportée à la solidité financière (fonds propres) de la compagnie. |
| Sens d'interprétation | Plus faible = meilleur (moins de risque de défaut) |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel — réservé au Takaful familial selon la source |
| Différences avec le conventionnel | Aucune différence de fond documentée |
| Référence bibliographique | IFSB (2019), ratio TP04, p.92 |
| Citation page/paragraphe | « A high ratio would indicate that the company must speed up its collection process and there is a high chance of default from receivables long overdue » — p.92 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

---

## 12. Catégorie : PERFORMANCE MACROÉCONOMIQUE / SECTORIELLE

### 12.1 Tableau de synthèse

| # | Ratio (FR) | Ratio (EN) | Formule (résumé) | Sens | Fiabilité |
|---|---|---|---|---|---|
| M1 | Taux de pénétration Takaful | Takaful penetration rate | Contributions Takaful annuelles / PIB | Plus élevé = marché plus développé | ⭐⭐⭐⭐⭐ |
| M2 | Taux de densité Takaful | Takaful density rate | Contributions Takaful annuelles / Population totale | Plus élevé = marché plus développé | ⭐⭐⭐⭐⭐ |

### 12.2 Fiches détaillées

#### M1. Taux de pénétration Takaful

| Champ | Contenu |
|---|---|
| Catégorie | Performance macroéconomique |
| Formule | Taux = Contributions Takaful annuelles / PIB |
| Variables | *Contributions Takaful annuelles* : total des contributions collectées dans l'année par le secteur. |
| Signification économique | Indique le niveau de développement du secteur Takaful dans un pays donné, en proportion de la richesse nationale. |
| Sens d'interprétation | Plus élevé = marché plus développé/mature |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel (équivalent direct du taux de pénétration de l'assurance classique) |
| Différences avec le conventionnel | Aucune différence de calcul ; seule la population de référence change (marché Takaful vs marché assurance globale) |
| Référence bibliographique | IFSB (2019), ratio TA06, p.97 |
| Citation page/paragraphe | « The penetration rate is measured as the ratio of contributions in a particular year to the GDP » — p.97 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

#### M2. Taux de densité Takaful

| Champ | Contenu |
|---|---|
| Catégorie | Performance macroéconomique |
| Formule | Taux = Contributions Takaful annuelles / Population totale |
| Variables | Alternative possible : dénominateur restreint à la population musulmane estimée du pays (à mentionner en métadonnée si utilisé selon la source). |
| Signification économique | Mesure le degré d'usage du Takaful rapporté à la population. |
| Sens d'interprétation | Plus élevé = marché plus développé |
| Valeur cible / seuil | Non spécifié |
| Applicabilité au Takaful | Adapté du conventionnel (équivalent direct de la densité d'assurance classique) |
| Différences avec le conventionnel | Possibilité de calcul alternatif sur la population musulmane uniquement — nuance propre au contexte Takaful |
| Référence bibliographique | IFSB (2019), ratio TA07, p.97-98 |
| Citation page/paragraphe | « Alternatively, the ratio can be measured for the estimated total Moslem population in a country » — p.97 |
| Fiabilité | ⭐⭐⭐⭐⭐ |

---

## 13. Ratios explicitement écartés faute de formule officielle trouvée

Conformément à la consigne de ne jamais inventer de formule, les éléments suivants ont été identifiés dans les sources comme des concepts Takaful importants mais **sans formule chiffrée officiellement définie** dans les documents consultés — ils sont documentés ici pour mémoire plutôt qu'inclus dans le tableau de 33 ratios :

- **Frais de Wakala (Wakalah fee)** — IFSB (2019) le liste comme indicateur TA03 (« Wakalah fee (value) ») mais uniquement comme **valeur absolue**, pas comme ratio (pas de dénominateur associé dans la source). Un ratio du type « frais de Wakala / contributions » serait plausible mais n'est **pas explicitement défini** dans le Compilation Guide ni dans IFSB-8 — toute formule de ce type serait une invention et n'est donc pas incluse.
- **Indicateur de dépendance au Qard** — GN-10 (§16-25, p.4-6) recommande de surveiller « la fréquence et le montant du Qard requis » comme signal d'alerte précoce, mais ne fournit **aucune formule de ratio chiffrée** (ex. Qard/PRF assets) — présenté uniquement comme critère qualitatif de surveillance.
- **Ratio de surplus (surplus ratio)** — IFSB-8 (§86.vii, p.22-23) mentionne « the surplus ratio and weightings for the distribution of surplus » dans le contexte de la politique de distribution du surplus aux participants, mais il s'agit d'une **politique de répartition interne**, non d'une formule de ratio prudentiel définie.

---

## 14. Bibliographie (APA 7) — sources effectivement consultées

Islamic Financial Services Board. (2009). *Guiding principles on governance for Takāful (Islamic insurance) undertakings* (IFSB-8). https://www.ifsb.org/wp-content/uploads/2023/10/IFSB-8-December-2009_En.pdf

Islamic Financial Services Board. (2010). *Standard on solvency requirements for Takāful (Islamic insurance) undertakings* (IFSB-11). https://www.ifsb.org/wp-content/uploads/2023/10/IFSB-11-Standard-on-Solvency-Requirements-for-Takaful-Islamic-Insurance-Undertakings.pdf

Islamic Financial Services Board. (2013). *Standard on risk management for Takāful (Islamic insurance) undertakings* (IFSB-14). https://islamicbankers.center/wp-content/uploads/2014/11/ifsb14-risk-management-for-takc481ful-undertakings_dec-2013-2.pdf

Islamic Financial Services Board. (2019). *The IFSB compilation guide on prudential and structural Islamic financial indicators (PSIFIs): Guidance on compilation and dissemination of prudential and structural Islamic financial indicators for institutions offering Islamic financial services (IIFS)*. https://www.ifsb.org/wp-content/uploads/2023/11/Revised-Compilation-Guide-on-PSIFIs-2019_En.pdf

Islamic Financial Services Board. (2025). *Guidance note on recovery and resolution for Takāful undertakings* (GN-10). https://www.ifsb.org/wp-content/uploads/2025/07/GN-10-Recovery-and-Resolution-for-Takaful-Undertakings.pdf

Abdou, H. A., Ali, K., & Lister, R. J. (2014). A comparative study of Takaful and conventional insurance: Empirical evidence from the Malaysian market. *Insurance Markets and Companies: Analyses and Actuarial Computations*, *5*(1), 22–34. https://eprints.hud.ac.uk/id/eprint/20445/ (version en libre accès consultée ; le lien businessperspectives.org d'origine retourne une erreur HTTP 403)

Joint Islamic Finance Task Team, Intersecretariat Working Group on National Accounts. (s.d.). *Islamic finance in the national accounts and external sector statistics* [Note d'orientation]. United Nations Statistics Division. https://unstats.un.org/unsd/nationalaccount/RAdocs/IF1_GN_Islamic_Finance_ENG.pdf (consulté comme source de corroboration contextuelle uniquement — ne contient pas de formule de ratio propre)

### Sources listées dans la demande mais non exploitables (non citées ci-dessus)

- AAOIFI. *E-standards / Accounting standards*. https://aaoifi.com/e-standards/ — page consultée, accès aux normes complètes bloqué par un mur d'inscription/abonnement ; aucun contenu chiffré récupéré.
- *Assurance Islamique* [Document]. Scribd. https://fr.scribd.com/document/784935215/Assurance-Islamique — page consultée, contenu du document non accessible (chargement JavaScript dynamique non restitué par l'outil de récupération).

---

## 15. Synthèse pour usage pipeline (note pratique)

Pour AT_TAKAFULIA et ZITOUNA_TAKAFUL, ce document permet d'identifier concrètement où le pipeline `extraction/bilan_kpi_extractor.py` applique aujourd'hui des formules conventionnelles qui **devraient a minima être ré-étiquetées ou recalculées avec un périmètre Takaful ajusté** :

- **ROE / ROA** (déjà présents dans le pipeline très probablement) : le numérateur « résultat net » doit être vérifié — s'agit-il du résultat de l'Opérateur seul (Wakala + Mudharaba), ou d'un résultat consolidé TO+PRF ? Voir fiches R1/R2 et le contexte §4.
- **Ratio combiné / loss ratio / claims ratio** : conceptuellement transposables (fiches T3/T4/T6), mais leur interprétation doit être resituée comme mesure de l'équilibre du fonds des participants (PRF), non de la rentabilité actionnariale.
- **Ratio d'adéquation des fonds propres** : nécessite de vérifier si les états financiers publiés distinguent Tier 1/Tier 2 avec le Qard du SHF comme le prévoit IFSB-11/PSIFI (fiche S1) — probablement non disponible dans les états financiers publics tunisiens, à documenter comme limitation si confirmé.
- Aucune règle CMF tunisienne spécifique au Takaful n'a été trouvée dans le périmètre de cette recherche (non demandée explicitement) — à investiguer séparément si nécessaire avant implémentation.
