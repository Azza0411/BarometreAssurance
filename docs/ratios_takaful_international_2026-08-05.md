# Ratios et indicateurs Takaful — panorama réglementaire international (complément)

**Date** : 2026-08-05
**Objectif** : compléter [docs/ratios_takaful_ifsb_aaoifi.md](ratios_takaful_ifsb_aaoifi.md) (33 ratios, sourcé IFSB Compilation Guide + IFSB-11 + Abdou et al. 2014) par une recherche élargie à l'échelle mondiale, à la demande explicite de l'utilisatrice : *"quels pourraient être les ratios/indicateurs dans le monde des assurances islamiques ?"*. Ce document ne remplace pas le premier — il l'étend avec des sources non couvertes le 05/08 (régulateurs nationaux, standard de divulgation IFSB-25, benchmarks sectoriels réels, littérature académique sur les déterminants de solvabilité).

**Méthode** : PDF officiels téléchargés puis extraits en texte (pdfplumber), pas de contenu inventé. Sources consultées intégralement listées en §8. Aucune formule n'est citée sans l'avoir lue dans le document source.

---

## 1. Ce que cette recherche ajoute par rapport au document du 05/08

Le document initial s'appuyait presque exclusivement sur le **Compilation Guide on PSIFIs** de l'IFSB (niveau "indicateur statistique sectoriel", proche de l'esprit CARAMEL/FSI du FMI) et un seul article académique. Il manquait :

- **Les formules prudentielles RÉELLES d'un régulateur national** — le Compilation Guide décrit des indicateurs de suivi statistique, pas la mécanique réglementaire de calcul du capital exigé compagnie par compagnie. La Malaisie (Bank Negara Malaysia) est la seule juridiction pour laquelle j'ai pu consulter intégralement le texte réglementaire détaillé (75 pages), donnant des formules précises et des **seuils numériques réels** — chose qui manquait presque partout dans le document initial ("Valeur cible / seuil : Non spécifié" pour la quasi-totalité des 33 ratios).
- **Des seuils réglementaires chiffrés dans d'autres juridictions** (UAE : plafond de commission Wakala/Moudharaba à 35 % ; Malaisie : seuil de capital à 130 %).
- **La norme de divulgation IFSB-25** (déc. 2020), non consultée le 05/08, qui ajoute un ratio absent du premier document (*operating ratio*) et précise une méthodologie (brut vs net de rétakaful) qui change l'interprétation des ratios déjà documentés.
- **Des valeurs de référence sectorielles réelles** (pas juste des formules) par pays, via un rapport actuariel commercial (Milliman).
- **La littérature académique sur les déterminants de solvabilité**, plus récente et plus large que l'unique étude malaisienne de 2014 déjà citée.
- **Une mise à jour du statut AAOIFI** : les normes consultées en vain le 05/08 (FAS 12/13/19) ont en fait été **remplacées** par FAS 42 et FAS 43 (applicables depuis le 1er janvier 2025) — toujours inaccessibles en texte intégral (même mur d'inscription), mais la mise à jour du numéro de norme elle-même est une information nouvelle.

---

## 2. Malaisie — Bank Negara Malaysia, *Risk-Based Capital Framework for Takaful Operators* (17 déc. 2018)

**Source consultée intégralement** (75 pages extraites). C'est la formalisation prudentielle la plus détaillée et la plus rigoureuse trouvée pour un marché Takaful mature — la Malaisie est, avec l'Arabie Saoudite, l'un des deux plus grands marchés Takaful au monde.

### 2.1 Ratio d'adéquation des fonds propres (CAR)

> « A licensed takaful operator shall compute the CAR as follows: CAR = Total Capital Available / Total Capital Required × 100% »

- **Seuil réglementaire minimal (STCL — Supervisory Target Capital Level) : 130 %.** C'est un chiffre réel, contrairement à la quasi-totalité des seuils du document du 05/08 marqués "non spécifié".
- Chaque opérateur doit en outre définir son propre **ITCL** (Internal Target Capital Level), supérieur au STCL — tout franchissement déclenche des mesures correctives graduées (plan de remédiation, restriction des dividendes).

### 2.2 Structure du calcul — spécifique Takaful

Contrairement à un assureur conventionnel (une seule exigence de capital), le CAR malaisien **sépare structurellement le Fonds Takaful (PRF/PIF) et le Fonds des Actionnaires** — même logique de ségrégation que documentée le 05/08, mais ici formalisée avec des formules complètes :

- **TCR (Total Capital Required)** = Σ par fonds Takaful *i* de `Max(SVCC, Capital Requis_Fonds_i)` + `Max(SVCC, Capital Requis_Actionnaires)`, où :
  - `Capital Requis_Fonds Takaful` = risque de crédit + risque de marché + **risque des engagements Takaful** (composante propre au PRF, absente côté actionnaires) ;
  - `Capital Requis_Fonds Actionnaires` = risque de crédit + risque de marché + **risque des engagements de charges (ECC)** + **risque opérationnel (ORCC)**.
- **TCA (Total Capital Available)** = Capital disponible du Fonds Actionnaires + Σ `Min(Capital disponible_Fonds_i, 130 % × Max(SVCC, Capital Requis_Fonds_i))`. Le plafonnement à 130 % du capital d'un fonds Takaful pris en compte dans le TCA illustre concrètement la règle « le surplus d'un fonds appartient aux participants, pas aux actionnaires » déjà énoncée le 05/08 : au-delà de 130 % de son exigence propre, l'excédent d'un fonds Takaful n'est **pas** comptabilisé comme capital disponible du groupe.

### 2.3 Charges de capital individuelles (composantes du TCR)

| Charge | Formule (citée) | Portée |
|---|---|---|
| **ORCC** (risque opérationnel) | *« ORCC = 1% of total assets of takaful business »* (§16.1) — actif total incluant Fonds des Participants + Fonds d'Investissement + Fonds des Actionnaires | Fonds Actionnaires |
| **GCC** (risque des engagements Takaful général) | Vise la sous-estimation des provisions générales au-delà du niveau de confiance à 75 % | PRF (Takaful général) |
| **FCC** (risque des engagements Takaful famille) | `FCC = V* − Valeur des engagements Takaful famille`, où V* = meilleure estimation ajustée par facteurs de stress (Annexe V) | PRF (Takaful famille) |
| **ECC** (risque des engagements de charges) | `ECC = Max[0, (Ve* − Provision pour risque de charges non expiré)]` — **variante spécifique Takaful** : si l'opérateur détient une provision pour *frais de Wakala non acquis* comme provision de charges, une formule allégée s'applique (§15.2) | Fonds Actionnaires |
| **SVCC** (risque de rachat) | `SVCC = Max[0, (valeur de rachat cumulée en vigueur − provision pour engagements)]` | Fonds Actionnaires + Takaful famille |

**Point notable pour l'implémentation Tunisie** : l'ECC allégée pour « frais de Wakala non acquis » (§15.2 ci-dessus) est une reconnaissance réglementaire explicite que **la commission Wakala fonctionne comptablement comme une prime de gestion à étaler dans le temps**, pas un revenu immédiat — un éclairage direct sur la ligne "Commission Wakala" déjà extraite pour AT_TAKAFULIA/ZITOUNA_TAKAFUL (voir Tâche 1, 05/08/2026).

**Référence** : Bank Negara Malaysia (2018), *Risk-Based Capital Framework for Takaful Operators*, §7-17, p.5-17.

---

## 3. Émirats Arabes Unis — Réglementation financière Takaful (Décisions 25/2014 et 26/2014)

- Alignement explicite sur les principes **Solvency II européens** pour le calcul du capital de solvabilité requis (SCR) — les Takaful Operators émiratis sont soumis au même référentiel de solvabilité que les assureurs conventionnels, avec un fonds de garantie minimal ≥ 1/3 du SCR.
- **Plafond réglementaire chiffré sur les frais Wakala/Moudharaba** : *« determined as a percentage not exceeding 35% of gross written contributions and participants investment revenues accrued »* — c'est le seul **seuil numérique officiel trouvé sur le ratio Wakala fee / Cotisations** dans l'ensemble de cette recherche (le document du 05/08 n'en citait aucun).
- Séparation obligatoire des comptes Fonds des Participants / Fonds des Actionnaires, distribution du surplus encadrée par la même décision.

**Limite** : source secondaire (cabinets d'avocats, Lexology/Mondaq/HFW), pas le texte réglementaire officiel lui-même consulté directement (non trouvé en accès direct lors de cette recherche) — fiabilité ⭐⭐⭐ (citation de juristes spécialisés, non recoupée avec le texte source), pas ⭐⭐⭐⭐⭐.

---

## 4. Bahreïn et Pakistan — juridictions identifiées, non creusées en détail

Deux juridictions supplémentaires confirmées comme ayant un cadre prudentiel Takaful dédié, mais dont le contenu chiffré n'a **pas** pu être extrait dans le temps de cette recherche (limite explicitement posée plutôt que contournée) :

- **Bahreïn** — Central Bank of Bahrain (CBB) Rulebook Volume 3, module *Capital Adequacy* dédié aux fonds Takaful, avec règles de transition pour les fonds nouvellement créés. Le CBB a par ailleurs annoncé (couverture presse GlobalCapital) un projet de renforcement de ce cadre de solvabilité — pas de formule chiffrée récupérée.
- **Pakistan** — SECP (Securities and Exchange Commission of Pakistan), *Takaful Rules 2012* et *Takaful Accounting Regulations 2019*. Structure de **fonds statutaires** par catégorie (Individual Family, Group Family, Group Health) pour le Takaful famille — un niveau de granularité des fonds plus fin que la simple dichotomie Familial/Général déjà documentée pour la Tunisie. Pas de formule de ratio chiffrée récupérée.

Ces deux entrées sont volontairement laissées "à developper" plutôt que meublées d'une formule non vérifiée.

---

## 5. IFSB-25 — *Disclosures to Promote Transparency and Market Discipline for Takāful/Retakāful Undertakings* (déc. 2020)

**Source consultée intégralement** (63 pages). Non lue le 05/08 (identifiée mais explicitement écartée par manque de temps). Trois apports concrets :

### 5.1 Un 4e ratio technique : le *ratio opérationnel* (operating ratio)

Le document du 05/08 documentait Ratio de sinistralité, Ratio de frais, Ratio combiné (T3/T5/T6). IFSB-25 ajoute un 4e ratio dans la même famille de divulgation :

> « (i) claims ratio; (ii) expense ratio; (iii) combined ratio; and (iv) operating ratio. » (§115)

L'*operating ratio* n'est pas défini formule par formule dans ce paragraphe, mais dans la pratique actuarielle standard (hors Takaful) il se calcule comme `Ratio combiné − Ratio de revenu de placement`, c'est-à-dire le ratio combiné corrigé de l'effet des revenus d'investissement — pertinent puisque le document du 05/08 documentait déjà séparément un "Ratio de revenu d'investissement" (R3) sans jamais le relier au ratio combiné.

### 5.2 Méthodologie brut vs net — une précision qui change l'interprétation

> « These ratios should be calculated from the profit and loss account of the reporting year and be gross of retakāful/reinsurance in order to neutralise the effect of mitigation tools on the technical performance of the direct business. [...] If the net ratios are materially different from the gross ratios, then both ratios should be disclosed. » (§116)

Autrement dit : la norme recommande de calculer sinistralité/frais/combiné/opérationnel **avant** cession en rétakaful par défaut (pas après, comme c'est actuellement fait pour la Tunisie où le pipeline utilise systématiquement les primes/charges nettes). Ce n'est pas une "meilleure" méthode dans l'absolu, mais une convention de transparence différente — à noter comme limite documentée si jamais la question se pose de pourquoi les ratios tunisiens diffèrent d'un ratio publié brut ailleurs.

### 5.3 Indicateurs additionnels non présents dans le document du 05/08

- **Fréquence de sinistres** = nombre de sinistres survenus / nombre moyen de contrats en vigueur sur la période (§120-ii).
- **Coût moyen des sinistres** = coût total des sinistres survenus / nombre de sinistres (§120-i).
- **Ratio de concentration des cessions** = cotisations cédées aux plus gros rétakafuleurs / cotisations cédées totales — indicateur de risque de concentration de la réassurance (§79).
- **Impact de la nouvelle affaire** (Takaful famille) = cotisation reçue − (charges liées à la conclusion du contrat + nouvelles provisions techniques constituées à la signature) — métrique de type "embedded value", propre à l'assurance vie/famille de long terme (§122).
- **Sensibilité au taux de profit** = variation des ressources en % de l'actif total pour un choc de 100 points de base sur le taux de profit — équivalent Takaful d'une duration de taux d'intérêt (§897, contexte gestion actif-passif).

**Référence** : IFSB (2020), *IFSB-25: Disclosures to Promote Transparency and Market Discipline for Takāful/Retakāful Undertakings*, §78-123.

---

## 6. Repères sectoriels réels par pays — Milliman, *Global Takaful Report* (2017)

**Source consultée intégralement** (56 pages). Contrairement aux sections précédentes (formules), cette source donne des **valeurs moyennes de marché réellement observées**, utiles comme points de comparaison (pas comme cible pour la Tunisie, marchés non comparables en taille/maturité) :

| Marché | Ratio de commission (% cotisations brutes) | Ratio de frais | Ratio de rétakaful/réassurance | Ratio de sinistralité | ROE |
|---|---|---|---|---|---|
| Malaisie (composite) | 12–13 % | 14–16 % | — | — | — |
| Malaisie (Takaful général) | — | — | 26–28 % | 49–53 % | — |
| Indonésie (Takaful général, fonds tabarru') | 16–19 % | 12–15 % | 10–11 % | 41–56 % | 7–9 % |
| GCC hors Arabie Saoudite (Takaful général) | 11–12 % | 11–17 % | 42–44 % | 64–86 % | — |
| Arabie Saoudite (marché assurance consolidé, ~100 % Sharia-compliant) | 6 % | 11–12 % | 17–27 % | 80–93 % | (15)–7 % |

**Lecture** : le ratio de rétakaful est nettement plus élevé dans le GCC (42-44 %) qu'en Asie du Sud-Est (10-28 %) — cohérent avec un marché de la rétakaful/retrocession plus développé au Moyen-Orient. Le ratio de sinistralité saoudien (80-93 %) est structurellement élevé, tiré par l'assurance santé/motor obligatoire. Aucune valeur tunisienne comparable n'existe dans cette source (hors périmètre géographique du rapport).

**Référence** : Milliman (2017), *Global Takaful Report 2017: Market Trends in Family and General Takaful*, p.20-30 (sections "Financial Ratio Analysis" par pays).

---

## 7. Littérature académique — déterminants de la solvabilité et de la rentabilité Takaful

Deux études (au-delà d'Abdou et al. 2014 déjà cité le 05/08), identifiées par titre/résumé (texte intégral non accessible — paywalls académiques), donc fiabilité ⭐⭐ (résumé/couverture presse académique uniquement, pas le texte intégral lu) :

- **"Solvency determinants: evidence from the Takaful insurance industry"** (*The Geneva Papers on Risk and Insurance*, 2021) — données de 52 compagnies Takaful, GCC + Malaisie, 2011-2016. Conclusion rapportée : la **taille de la compagnie** et les **frais de Wakala** réduisent significativement la solvabilité ; le ratio de rétention de risque et le ratio de revenu d'investissement ne sont pas des déterminants significatifs.
- **Thèse de doctorat, University of Portsmouth**, "The determinants of solvency and profitability of Takaful firms in the GCC and Malaysian markets" — identifie comme déterminants statistiquement significatifs : la **croissance des cotisations**, le **levier Takaful** (*Takaful leverage* — a priori Total actif/Capitaux propres, à confirmer si le texte intégral devient accessible), les **frais de Wakala**, les **commissions versées**, les **charges de gestion** et le **ratio de rétention de risque** — selon le marché (déterminants différents en GCC vs Malaisie).

**Point méthodologique important** : ces études utilisent le ROE/ROA de l'Opérateur (pas un résultat consolidé) comme mesure de rentabilité — cohérent avec la vérification déjà faite le 05/08 sur l'extracteur `takaful_kpi_extractor.py` (le "Résultat Net" extrait correspond bien au périmètre Opérateur, Wakala+Moudharaba).

---

## 8. AAOIFI — mise à jour du statut (toujours inaccessible, mais normes identifiées)

Le 05/08, la conclusion était : "aucune norme AAOIFI Takaful accessible, mur d'inscription". Cette recherche apporte une précision : les anciennes normes visées (FAS 12 *General Presentation and Disclosure*, FAS 13 *Disclosure of Bases for Determining and Allocating Surplus/Deficit*, FAS 15 *Provisions and Reserves*, FAS 19 *Contributions*) ont été **officiellement remplacées** par :

- **FAS 42** — *Presentation and Disclosures in the Financial Statements of Takaful Institutions*
- **FAS 43** — *Accounting for Takaful: Recognition and Measurement*

Applicables aux exercices ouverts à partir du **1er janvier 2025** — donc en principe déjà en vigueur pour les états financiers 2025 d'AT_TAKAFULIA et ZITOUNA_TAKAFUL actuellement dans le pipeline. Le texte intégral reste derrière le même mur d'inscription qu'en 05/08 (confirmé à nouveau, pas de tentative de contournement). **Limite documentée, pas contournée.**

**Conséquence pratique à vérifier** (pas fait dans cette recherche, piste pour la suite) : si FAS 42/43 changent la présentation des états financiers Takaful à partir de l'exercice 2025, cela pourrait expliquer — ou aggraver — des variations de structure déjà observées dans les PDF CMF 2025 (ex. le cas de corruption de texte trouvé sur ZITOUNA_TAKAFUL_2025.pdf, voir [extraction/CAS_PARTICULIERS_TAKAFUL.md](../extraction/CAS_PARTICULIERS_TAKAFUL.md)) — pure hypothèse, non vérifiée, à ne pas traiter comme un fait.

---

## 9. Synthèse — nouveaux ratios/indicateurs identifiés (absents du document du 05/08)

| # | Ratio/indicateur | Source | Seuil/valeur chiffrée trouvée ? | Calculable avec les données CMF Tunisie déjà extraites ? |
|---|---|---|---|---|
| N1 | CAR malaisien complet (TCA/TCR avec composantes GCC/FCC/ECC/ORCC/SVCC) | BNM RBCT | Oui — STCL 130 % | **Non** — nécessite une granularité de provisions par risque que les Bilans CMF tunisiens ne publient pas |
| N2 | Ratio Wakala+Moudharaba / (Cotisations + revenus de placement du fonds) avec plafond | UAE Financial Regulations | Oui — plafond 35 % | **Oui, partiellement** — Commission Wakala et Commission Moudharaba déjà extraites (Tâche 1) ; le dénominateur (cotisations + revenus de placement du fonds) est calculable à partir des KPI déjà en base |
| N3 | Operating ratio (combiné − revenu de placement) | IFSB-25 | Non | **Oui** — Ratio combiné déjà calculé, revenu de placement du fonds à extraire (déjà partiellement fait pour Commission Wakala/Moudharaba, pas pour "Revenus des placements" du fonds lui-même) |
| N4 | Fréquence de sinistres, coût moyen des sinistres | IFSB-25 | Non | **Non** — nécessite le nombre de sinistres/contrats, jamais publié dans les Bilans CMF |
| N5 | Ratio de concentration des cessions rétakaful | IFSB-25 | Non | **Non** — nécessite le détail des cessionnaires, non publié |
| N6 | Impact de la nouvelle affaire (embedded value simplifiée) | IFSB-25 | Non | **Non** — nécessite des données actuarielles non publiées dans les états CMF |
| N7 | Ratios de marché sectoriels comparatifs (commission/frais/rétakaful/sinistralité par pays) | Milliman 2017 | Oui (valeurs 2013-2015) | Sans objet — contexte comparatif international, pas un ratio à calculer pour une compagnie tunisienne |
| N8 | Takaful leverage, croissance des cotisations comme déterminants de solvabilité | Littérature académique GCC/Malaisie | Non (relation statistique, pas seuil) | **Oui** — Total actif/Capitaux propres déjà calculé (Tâche 1, S4/S5) ; croissance des cotisations déjà utilisée ailleurs dans l'app (YoY) |

**Sur les 8 nouveaux éléments identifiés, seuls N2, N3 et N8 sont raisonnablement implémentables avec les données déjà extraites pour la Tunisie** (ou une extraction marginale supplémentaire — "Revenus des placements" du fonds pour N3, déjà visible dans les PDF Annexes 3/4 mais pas encore capturé). N1, N4, N5, N6 exigeraient une granularité de données que les états financiers CMF tunisiens ne publient tout simplement pas — à documenter comme limite structurelle plutôt qu'à forcer une extraction qui échouerait silencieusement.

---

## 10. Sources consultées (bibliographie de ce complément)

- Bank Negara Malaysia (2018). *Risk-Based Capital Framework for Takaful Operators*. Consulté intégralement (75 pages extraites via pdfplumber). https://www.bnm.gov.my/documents/20124/948107/Risk-Based+Capital+Framework+for+Takaful+Operators_17+Dec+2018.pdf
- Islamic Financial Services Board (2020). *IFSB-25: Disclosures to Promote Transparency and Market Discipline for Takāful/Retakāful Undertakings*. Consulté intégralement (63 pages extraites). https://www.ifsb.org/wp-content/uploads/2023/10/IFSB-25_En.pdf
- Milliman (2017). *Global Takaful Report 2017: Market Trends in Family and General Takaful*. Consulté intégralement (56 pages extraites). https://www.milliman.com/en/insight/global-takaful-report-2017-market-trends-in-family-and-general-takaful
- Insurance Authority UAE, Board of Directors' Decisions 25/2014 et 26/2014 (Financial Regulations) — consulté via sources secondaires juristes (Lexology, Mondaq, HFW), texte réglementaire officiel non trouvé en accès direct.
- Central Bank of Bahrain, *Rulebook Volume 3 — Insurance, Capital Adequacy Module* — identifié, contenu chiffré non extrait (limite posée).
- SECP Pakistan, *Takaful Rules 2012* et *Takaful Accounting Regulations 2019* — identifiés, contenu chiffré non extrait (limite posée).
- AAOIFI, *FAS 42* et *FAS 43* (2025) — identifiées par annonce officielle AAOIFI, texte intégral inaccessible (mur d'inscription, déjà documenté le 05/08, reconfirmé).
- Diaz-Serrano & al. (2021), "Solvency determinants: evidence from the Takaful insurance industry", *The Geneva Papers on Risk and Insurance*. Résumé/couverture uniquement, texte intégral payant non consulté.
- Thèse de doctorat, University of Portsmouth, "The determinants of solvency and profitability of Takaful firms in the GCC and Malaysian markets". Résumé uniquement, texte intégral non consulté.
