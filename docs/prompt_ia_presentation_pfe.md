# Prompt complet à copier-coller dans une nouvelle conversation IA

---

Voici un dossier complet sur un projet de plateforme logicielle — mon PFE (Projet de Fin d'Études, ingénieur informatique, ESPRIT, en partenariat avec EY Tunisie) — pour que tu en aies une connaissance approfondie : contexte métier, marché cible, architecture technique, fonctionnalités, logique de données, IA/ML, méthodologie de travail, et travaux déjà réalisés.

## 1. Contexte métier et problématique

Ce n'est **pas** un produit qu'EY publie ou vend à ses clients externes : c'est un **outil interne**, destiné aux **consultants du département Financial Services Transformation (FST) d'EY Tunisie**. Ces consultants réalisent en interne des analyses du marché tunisien de l'assurance (positionnement concurrentiel, suivi de ratios prudentiels, veille réglementaire, benchmarking) — des analyses qui nourrissent ensuite leurs missions et livrables, mais l'outil lui-même reste un instrument de travail interne à l'équipe, pas un produit EY livré au marché.

Aujourd'hui ce travail est **majoritairement manuel** : les consultants FST téléchargent un par un les rapports financiers PDF publiés par chaque compagnie sur le portail du CMF, en extraient les chiffres à la main ou via des feuilles Excel ad hoc, recalculent les ratios, et surveillent séparément les sites d'actualité et le site du régulateur pour ne rien manquer. Ce processus est lent, source d'erreurs de saisie, difficile à mettre à jour (24 compagnies × jusqu'à 11 exercices), et ne laisse aucune trace de "d'où vient ce chiffre" une fois le PDF refermé.

**Problématique** : comment construire, pour les consultants FST d'EY Tunisie, une plateforme interne qui automatise la collecte, l'extraction et le calcul des indicateurs du marché tunisien de l'assurance, tout en garantissant la fiabilité et la traçabilité de chaque chiffre jusqu'à sa source, et en apportant une couche d'intelligence (détection d'anomalies, prévision, assistant conversationnel) qu'un tableur ne peut pas offrir ?

**Valeur ajoutée pour l'équipe FST** : gain de temps sur la collecte/consolidation avant chaque mission, réduction du risque d'erreur humaine, mise à jour continue (pipeline planifié) sans veille manuelle quotidienne, un point d'entrée unique pour l'analyse du marché au lieu de dizaines de PDF et fichiers Excel dispersés entre consultants, et une explicabilité (chaque KPI est "cliquable" jusqu'à sa cellule source dans le PDF d'origine) qui permet de citer un chiffre dans un livrable client en toute confiance.

## 2. Le marché tunisien de l'assurance — contexte spécifique à connaître

- Marché régulé par le **CGA** (Comité Général des Assurances), avec une fédération professionnelle, la **FTUSA**, et des publications financières obligatoires déposées auprès du **CMF** (Conseil du Marché Financier) pour les sociétés faisant appel public à l'épargne.
- **24 compagnies d'assurance actives** suivies par la plateforme, dont **21-22 conventionnelles** et **2 compagnies Takaful "pures"** (AT-Takafulia, Zitouna Takaful) qui publient en français, plus **1 compagnie Takaful supplémentaire** (AL_AMANAH_TAKAFUL) dont les rapports sont **exclusivement en arabe** — un cas particulier traité par un pipeline d'extraction dédié (voir section 6).
- Le segment Takaful (assurance participative conforme à la Charia) est **minoritaire mais réglementairement distinct** : cadre comptable propre (norme NCT 43 — Bilan Combiné à 3 colonnes Fonds des Adhérents / Entreprise / Combiné, États de Surplus séparés par fonds), modèle économique différent (contrats Wakala/Moudharaba, Fonds des Participants séparé du fonds de l'opérateur), et des ratios prudentiels normés par l'IFSB (Islamic Financial Services Board) plutôt que par les référentiels conventionnels classiques. Un assureur Takaful ne peut pas être comparé à un assureur conventionnel avec les mêmes formules de ratios sans introduire un biais.
- Autres sources de contexte marché intégrées : cotations boursières (BVMT) pour les compagnies cotées, indicateurs macroéconomiques (PIB, population — INS) pour calculer taux de pénétration et densité d'assurance, et une **enquête de satisfaction client** (Grand public & Entreprises) menée en parallèle du projet.

## 3. Utilisateurs cibles et besoins

Tous les utilisateurs sont **internes à EY Tunisie**, au sein (ou au service) du département **Financial Services Transformation** — ce n'est pas un outil client.

- **Consultants FST** (utilisateur principal) : besoin de benchmarker rapidement une compagnie vs le marché ou vs ses pairs, de vérifier la fiabilité d'un chiffre avant de le citer dans un livrable de mission, de suivre les nouveautés réglementaires et de marché sans veille manuelle quotidienne.
- **Managers/associés FST** : besoin d'une vue macro synthétique du marché (structure, tendances, positionnement) pour préparer des présentations ou des due diligences internes à une mission.
- **Équipe data/tech interne au projet** : besoin de surveiller la qualité et la fraîcheur des données extraites (page Qualité des Données, Anomalies Système, Rapport Pipeline) pour garder confiance dans la plateforme dans la durée.
- Point commun à tous les profils : **confiance dans le chiffre affiché**, d'où l'exigence de traçabilité systématique jusqu'à la source PDF, plutôt qu'une "boîte noire" qui affiche des valeurs sans preuve — un chiffre non vérifiable ne peut pas être repris dans un livrable client.

## 4. Architecture technique

```
BarometreAssurance/
├── api/              # Backend Flask (Python) — API REST, 8 blueprints de routes
├── frontend/         # Frontend React 18 + Vite
│   └── src/
│       ├── pages/    # 13 dashboards (ApercuMarche, AnalyseComparative, ...)
│       ├── components/ # Composants partagés (Chatbot, NavbarPartagée, NotificationBell, ...)
│       └── utils/    # kpiMeta (dictionnaire de métadonnées KPI), famille (logique Conventionnel/Takaful), chartTheme
├── config/           # Registre des compagnies, config DB
├── database/         # Connecteur MySQL + repository (accès données)
├── extraction/       # Extracteurs KPI par source/type de document (CMF, FTUSA, CGA, bilan, résultat, annexes, Takaful)
├── scraping/         # Scrapers web (CMF, BVMT, ilboursa, Atlas Magazine, CGA, FTUSA)
├── analysis/         # Moteur de calcul des KPI dérivés
├── chatbot_portable/ # Sous-système IA : RAG + module de prévision ML (voir section 7)
├── data/              # Données extraites (CSV), enquête marché (xlsx)
└── pipelines/         # Orchestration : run_pipeline.py (planifié, hebdomadaire)
```

**Stack** : Backend Python 3.11 / Flask / MySQL 8 (base `MarketInsurance`) ; Frontend React 18 / Vite / ApexCharts / React Router ; Design System EY (police Barlow, jaune #FFE600, gris foncé #2E2E38) ; scraping via Selenium/Requests ; OCR via Tesseract (documents arabes/scannés) ; automatisation via tâche planifiée Windows (pipeline hebdomadaire, dimanche 2h).

**Pipeline de données (bout en bout)** :
1. **Collecte** — scraping des 5 sources (CMF, FTUSA, CGA, BVMT, INS) + veille (actualités, réglementation).
2. **Extraction** — parsing PDF texte réel + OCR pour les documents scannés ou en arabe, extraction ciblée cellule par cellule avec gestion des cas particuliers par compagnie (libellés qui varient, tableaux qui s'étalent sur 2 pages, singulier/pluriel, etc.).
3. **Cleaning data / Modélisation des KPI** — calcul des ratios dérivés (ex. ratio de sinistralité = charges de prestations / primes émises), gestion différenciée Conventionnel vs Takaful.
4. **Qualité & anomalies** — audit systématique post-extraction (voir section 8).
5. **Restitution** — 13 pages/dashboards, chatbot IA, module de prévision, exports, notifications.

## 5. Les 13 pages de la plateforme (routes)

| Route | Rôle |
|---|---|
| `/apercu-marche` | Vue macro du marché — primes totales, structure du portefeuille, évolution, positionnement géographique |
| `/positionnement` | Positionnement concurrentiel des compagnies |
| `/geographie` | Répartition géographique de l'activité |
| `/fiches` | Fiche détaillée par compagnie (Vue par Assurance), adaptée spécifiquement pour les compagnies Takaful |
| `/analyse-comparative` | Benchmarking des ratios techniques entre compagnies, filtre Conventionnelle/Takaful/Toutes |
| `/enquete-marche` | Analyse de l'enquête de satisfaction client (Grand public & Entreprises) |
| `/veille-reglementaire` | Textes CGA/FTUSA — lois, décrets, circulaires, depuis 1980 |
| `/actualites-seminaires` | Agrégation live de presse et événements sectoriels (scraping IlBoursa + Atlas Magazine) |
| `/qualite-donnees` | Grille croisant chaque KPI × chaque société avec son statut (Extrait/Calculé/Non extrait/Aberrant) et accès direct à la source PDF |
| `/kpi-detail` | Vue "zoom" sur un KPI précis, avec surlignage de la cellule source dans le PDF |
| `/rapport-pipeline` | Audit technique de chaque exécution du pipeline de collecte |
| `/anomalies-systeme` | Détection automatique d'anomalies avec diagnostic de cause et recommandation |
| `/accueil` | Page d'accueil / hub de navigation |

*(Remarque honnête : je n'ai pas de module "simulateur what-if" actif dans le code actuel malgré une trace dans mes notes d'un développement antérieur — ne pas le mentionner comme fonctionnalité livrée sauf si je te le confirme explicitement.)*

## 6. Logique KPI — Conventionnel vs Takaful (point technique et métier central du projet)

Point de départ : la plateforme traitait initialement les 2 assureurs Takaful conventionnels exactement comme les 22 conventionnels — mêmes ratios, mêmes formules, aucune adaptation au modèle économique différent. Un incident opérationnel (application accidentelle de l'extracteur conventionnel à une compagnie Takaful) a révélé le besoin d'une séparation plus stricte.

**Démarche suivie** :
1. Recherche documentaire sourcée sur les référentiels IFSB (Compilation Guide on PSIFIs, IFSB-8/11/14, GN-10) et un article académique peer-reviewed — 33 ratios/indicateurs Takaful identifiés et documentés (formule, variables, différence vs conventionnel, fiabilité de la source). AAOIFI confirmé inaccessible (paywall) — limite documentée plutôt que contournée.
2. Vérification empirique sur les PDF réels des 2 compagnies (formats 2018 à 2025) avant d'écrire une seule ligne de code, pour confirmer la structure comptable exacte (Bilan Combiné, États de Surplus séparés par fonds).
3. Priorisation par faisabilité réelle : sur les 33 ratios documentés, sélection d'un sous-ensemble calculable sans nouvelle extraction (ratios déjà en base, réinterprétés) + un sous-ensemble nécessitant une extraction ciblée à fort contenu métier (Fonds des Participants).
4. Extraction ciblée avec cycle audit-correction : 7 cas d'erreur réels corrigés (préfixes de ligne collés au libellé, numéros de note contaminant une valeur, titres de tableau à cheval sur deux pages, ambiguïté singulier/pluriel entre deux tableaux).

**Ce qui a été livré** :
- Filtre "Toutes / Conventionnelles / Takaful" sur les pages de comparaison.
- 4 nouveaux ratios de solvabilité/investissement pour toutes les compagnies, sans coût d'extraction additionnel.
- Une fiche individuelle Takaful réellement adaptée (pas un simple masquage) : notes d'interprétation sur les ratios existants + une section "Fonds des Participants" exposant pour la première fois le Surplus mutualisé, les provisions du fonds, et la rémunération de l'Opérateur (Wakala/Moudharaba).
- Variantes Takaful spécifiques pour les 3 ratios techniques les plus utilisés (Ratio combiné, Ratio de sinistralité, Ratio de frais de gestion) — formule adaptée à la structure comptable Takaful plutôt qu'une formule conventionnelle appliquée telle quelle.

**Chiffres clés** : 33 ratios Takaful sourcés (base de référence réutilisable) ; 6 nouveaux indicateurs "Fonds des Participants" par société/exercice, jamais disponibles auparavant ; 100% de couverture sur AT-Takafulia (7/7 exercices depuis la réforme comptable de 2020), ~98% sur Zitouna Takaful ; 90/90 tests existants toujours au vert après implémentation — aucune régression sur les 22 compagnies conventionnelles.

**Correction systémique connexe** : un bug affectant le Ratio de sinistralité sur ~10 compagnies (numérateur/dénominateur non cohérents entre eux) a été identifié et corrigé à la source dans l'extracteur, réduisant mesurablement le nombre d'anomalies détectées par le système de qualité.

## 7. Intelligence artificielle / Machine Learning (dans `chatbot_portable/`)

**Assistant conversationnel (RAG)** : chatbot connecté à l'API Claude, avec une architecture RAG (Retrieval-Augmented Generation) — les réponses sont ancrées sur les données réelles de la plateforme (`rag_ingest.py` indexe le contenu, `rag_module.py` orchestre la récupération + génération) plutôt que sur la seule connaissance générale du modèle, pour éviter les hallucinations sur des chiffres métier précis.

**Module de prévision** : pipeline complet de modélisation avec sélection automatique entre modèles **Prophet** (séries temporelles, saisonnalité) et **XGBoost** (gradient boosting, features tabulaires), pipeline d'entraînement/évaluation dédié (`prediction/training/`), et **explicabilité** via **SHAP** pour justifier chaque prévision plutôt que de livrer un chiffre "boîte noire" — avec génération automatique d'un **narratif en langage naturel** expliquant les facteurs qui influencent la prévision (cohérent avec l'exigence de traçabilité qui structure tout le projet, y compris côté extraction de données).

## 8. Qualité des données, anomalies et notifications

- **Page Qualité des Données** : matrice KPI × compagnie avec statut (Extrait / Calculé / Non extrait / Aberrant) et lien direct vers la cellule source dans le PDF d'origine (surlignage visuel).
- **Audit systématique de traçabilité** : script d'audit automatisé testant, pour chaque compagnie × chaque KPI, si la fonctionnalité "localiser dans le PDF" fonctionne réellement (pas seulement si une valeur s'affiche à l'écran), avec catégorisation des causes d'échec.
- **Anomalies Système** : détection automatique (variations YoY implausibles, déséquilibres de bilan, écarts sectoriels, échecs d'extraction), avec diagnostic de cause probable et recommandation d'action.
- **Notifications** : cloche in-app signalant 3 types de nouveautés — nouveaux documents ajoutés (toutes les 5 sources désormais, contre CMF seul auparavant), nouvelles actualités, nouveaux textes réglementaires. Déclenchée automatiquement par le pipeline planifié, avec persistance minimale ciblée (2 tables dédiées à la seule détection de "déjà vu") et un garde-fou anti-avalanche au premier lancement (pas de notification massive au déploiement initial). Vérifiée à 5 niveaux jusqu'au vrai chemin d'exécution du pipeline planifié (Windows Task Scheduler, hebdomadaire).
- **Extraction PDF en arabe (AL_AMANAH_TAKAFUL)** : pipeline dédié combinant lecture de texte réel (quand disponible) et OCR (Tesseract, modèle arabe) avec correspondance floue de libellés en RTL, capable de localiser et surligner la cellule source exacte y compris pour des valeurs qui sont en réalité des sommes sur 2 pages distinctes (Fonds Familial + Fonds Général) — vérifié pixel par pixel contre le PDF source.

## 9. Veille réglementaire et veille d'actualité

- **Veille Réglementaire** : agrégation des textes CGA/FTUSA (lois, décrets, circulaires) depuis 1980, avec proxy de téléchargement PDF.
- **Actualités & Séminaires** : agrégation live par scraping (IlBoursa + Atlas Magazine), présentation en carrousel avec filtres, dont un filtre par compagnie.
- Ces deux modules alimentent désormais le système de notifications, avec une logique de diff "déjà vu / nouveau" pour éviter le bruit.

## 10. Exports

Génération de rapports **PDF et Excel** stylés (logo compagnie, mise en forme EY) pour les fiches et analyses, avec positionnement précis des cellules et gestion du contraste logo/fond.

## 11. Travaux techniques réalisés depuis (deuxième vague — à connaître aussi)

Après tout ce qui précède, plusieurs chantiers supplémentaires ont été menés. Ils sont moins "gros" individuellement que la séparation Takaful, mais ensemble ils illustrent bien la méthode de travail du projet (vérification empirique systématique, préférence pour l'échec honnête plutôt que la donnée fausse, correction incrémentale documentée) — du bon matériau pour une slide "démarche" ou "résultats".

**Fiabilisation des notifications.** Constat : des actualités publiées le jour même ne généraient aucune notification. Investigation : la tâche planifiée Windows (déclencheur unique du système) n'avait **jamais tourné une seule fois** depuis son enregistrement (mode "Interactive uniquement", nécessite une session active pile au bon moment — limite qui avait été identifiée en théorie mais dont l'impact réel n'avait jamais été mesuré). Corrigé en déplaçant le déclenchement **à l'intérieur du process Flask lui-même** (thread de fond, vérification au démarrage puis toutes les 30 minutes) — indépendant de tout planificateur externe. Vérifié : une vraie notification générée en direct pour un article venant d'être publié.

**Extension Takaful arabe — Surplus du Fonds des Participants (Al Amanah Takaful).** L'indicateur "Surplus du Fonds des Participants" manquait pour la 3ᵉ compagnie Takaful (rapports en arabe) sur Analyse Comparative. Méthode : lecture visuelle directe des PDF réels (image rendue) pour repérer la structure exacte de la ligne recherchée, puis **utilisation d'une identité comptable (Net = Brut + Cédées) comme garde-fou de validation automatique** — une valeur n'est acceptée que si elle vérifie cette équation, ce qui a permis de détecter et d'écarter un cas ambigu plutôt que d'afficher un chiffre faux. Couverture obtenue : 2 exercices complets sur 9 (le reste reste `None`, honnêtement, faute de texte source exploitable) — un bon exemple de "mieux vaut une couverture partielle fiable qu'une couverture totale non vérifiée".

**Fiabilisation du surlignage PDF (traçabilité).** Plusieurs bugs en cascade sur la fonctionnalité "Localiser dans le PDF", découverts et corrigés un par un par vérification empirique à chaque étape :
1. Un canvas d'affichage qui restait bloqué à sa taille par défaut au lieu de suivre la taille réelle de la page rendue.
2. Une page pivotée à 90° dans le PDF (tableau imprimé en paysage) : la librairie d'extraction et la librairie d'affichage n'utilisaient pas le même repère de coordonnées pour une page pivotée — **confirmé et corrigé par un test direct avec la vraie librairie de rendu PDF (pdf.js) en dehors du navigateur**, plutôt que par déduction seule.
3. Un faux positif où le **titre de la page** ("Annexe N°13 : Résultat technique...") était surligné à la place de la vraie ligne de données, quand celle-ci était introuvable.
4. Une page à l'encodage de police corrompu (texte vectoriel réel, mais illisible par l'extraction standard) obligeant un repli sur la reconnaissance optique (OCR) — avec ses propres limites documentées plutôt que masquées.

**Correction d'un bug de fond sur l'Enquête de Marché.** Le sélecteur de compagnie sur la page "Fiche client entreprise" ne changeait en réalité **aucun chiffre affiché** — la fonction de calcul ignorait silencieusement le paramètre de compagnie et renvoyait toujours les statistiques du marché entier. Corrigé en exploitant des colonnes du fichier source jusque-là inutilisées (l'assureur réel de chaque répondant). Découverte annexe : l'échantillon par compagnie est très réduit (quelques répondants seulement) — affiché désormais avec un indicateur "échantillon restreint" plutôt que caché.

**Cohérence de l'interface.** Unification définitive de la barre de navigation sur toutes les pages, filtre par compagnie de la page Actualités étendu aux 3 compagnies Takaful (absentes jusque-là), corrections d'affichage (carte de densité géographique, densité de la page Enquête de Marché).

