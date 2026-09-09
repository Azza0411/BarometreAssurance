# Documentation des phases — support de présentation PFE

Contenu prêt à intégrer dans le deck "FS Market Intelligence" (template EY dark/jaune #FFE600, section "Proposed Solution" A-F). Une section par phase validée, ajoutée au fil de l'eau.

---

## Phase : Séparation Conventionnel / Takaful (2026-08-05)

### Pourquoi

La plateforme traitait jusqu'ici les 2 assureurs participatifs tunisiens (AT-Takafulia, Zitouna Takaful) exactement comme les 22 assureurs conventionnels — mêmes ratios, mêmes formules, aucune mention du modèle économique différent (Wakala/Moudharaba, Fonds des Participants séparé). Un incident opérationnel (application accidentelle de l'extracteur conventionnel à une compagnie Takaful) a révélé le besoin d'une séparation plus stricte, à la fois dans les données et dans l'affichage.

### Méthode

1. **Recherche documentaire sourcée** : 33 ratios/indicateurs Takaful identifiés et documentés (formule, variables, différence vs conventionnel, fiabilité de la source) à partir des normes IFSB (Compilation Guide on PSIFIs, IFSB-8/11/14, GN-10) et d'un article académique peer-reviewed — AAOIFI confirmé inaccessible (paywall), limite documentée plutôt que contournée.
2. **Vérification empirique avant implémentation** : ouverture directe des PDF réels (AT-Takafulia, Zitouna Takaful, formats 2018 à 2025) pour confirmer la structure comptable exacte (NCT 43 : Bilan Combiné à 3 colonnes Fonds des Adhérents/Entreprise/Combiné, États de Surplus séparés par fonds) avant d'écrire une seule ligne de code.
3. **Priorisation par faisabilité réelle** : sur les 33 ratios documentés, sélection d'un sous-ensemble calculable sans nouvelle extraction PDF (ratios déjà en base, réinterprétés) + un sous-ensemble nécessitant une extraction ciblée mais à fort contenu métier (Fonds des Participants) — écarté ce qui exigerait une extraction disproportionnée pour la valeur ajoutée.
4. **Extraction ciblée avec cycle audit-correction** : 7 cas d'erreur réels identifiés et corrigés sur les 2 sociétés (préfixes de ligne collés au libellé, numéros de note contaminant une valeur, titres de tableau à cheval sur deux pages, ambiguïté singulier/pluriel entre deux tableaux) — méthode reproductible documentée pour tout nouveau cas futur.

### Ce qui a été livré

- Un filtre "Toutes / Conventionnelles / Takaful" sur les pages de comparaison (Analyse Comparative, Aperçu Marché).
- 4 nouveaux ratios de solvabilité/investissement pour toutes les compagnies, sans coût d'extraction additionnel.
- Une fiche individuelle Takaful réellement adaptée (pas un simple masquage) : notes d'interprétation sur les ratios existants + une section "Fonds des Participants" exposant pour la première fois le Surplus mutualisé, les provisions du fonds, et la rémunération de l'Opérateur (Wakala/Moudharaba).

### Chiffres clés

- **33** ratios Takaful sourcés et documentés (base de référence réutilisable).
- **6** nouveaux indicateurs "Fonds des Participants" extraits par société/exercice, jamais disponibles auparavant.
- **100 %** de couverture sur AT-Takafulia (7/7 exercices depuis la réforme comptable de 2020), **~98 %** sur Zitouna Takaful.
- **90/90** tests existants toujours au vert après implémentation — aucune régression sur les 22 compagnies conventionnelles.

---

## Phase : Notifications de nouveautés (2026-08-20)

### Pourquoi

La plateforme collectait déjà silencieusement de nouvelles données (rapports CMF, articles, textes réglementaires) sans jamais le signaler à l'utilisateur — il fallait revisiter chaque page manuellement pour découvrir un changement. Une cloche de notification existait, mais limitée aux nouveaux documents CMF ; Actualités et Veille réglementaire n'avaient aucune mémoire de ce qui avait déjà été vu (scrape à la volée, cache d'1h, zéro persistance) — donc structurellement impossible d'y détecter une nouveauté.

### Méthode

1. **Audit de l'existant avant d'ajouter quoi que ce soit** : la cloche (UI + API + table `notifications`) était déjà fonctionnelle bout-en-bout — réutilisée telle quelle plutôt que reconstruite.
2. **Persistance minimale ciblée** : 2 nouvelles tables (`actualites_vues`, `reglementation_vues`), clé unique = URL/identifiant de la source — servent uniquement à la détection de nouveauté ; les pages elles-mêmes restent des scrapes en direct inchangés.
3. **Garde-fou anti-avalanche** : le tout premier passage peuple les tables sans générer de notification (sinon "82 nouvelles actualités" dès le premier lancement après déploiement).
4. **Intégration au pipeline planifié existant** plutôt qu'un nouveau système séparé — même cadence, même mécanisme de notification déjà en place pour les autres événements (nouveau document, échec source, score qualité faible).
5. **Vérification à 5 niveaux**, jusqu'au vrai chemin de code de `main()` (pas une réimplémentation) : diff correct dans les deux sens (aucun faux positif, détection exacte d'un item réinjecté), garde-fou premier lancement, écriture/lecture via l'API réelle consommée par la cloche, câblage complet testé en cas négatif ET positif.

### Ce qui a été livré

- Notifications automatiques pour 3 nouvelles sources d'événements : nouvelles actualités, nouveaux textes réglementaires, et nouveau document étendu à **toutes** les sources (CMF, FTUSA, CGA, INS, BVMT) au lieu de CMF seul auparavant.
- Tâche planifiée Windows enregistrée (hebdomadaire, dimanche 2h) — le pipeline, et donc les notifications, se déclenchent désormais sans intervention manuelle.

### Chiffres clés

- **2** nouvelles tables de persistance, **0** nouvelle infrastructure (réutilise le pipeline planifié et la cloche déjà existants).
- **5 sources** désormais couvertes par une notification "nouveau contenu" contre **1 seule** (CMF) avant.
- **82 + 21** actualités/textes réglementaires indexés comme référence de départ au premier passage.
- **5 niveaux de vérification**, du plus isolé (fonction de diff seule) au plus réaliste (le vrai `main()` du pipeline, cas négatif et positif).

### Limite assumée

La tâche planifiée créée est en mode "Interactive uniquement" (nécessite une session utilisateur active au moment prévu) — suffisant pour une démonstration ou un déploiement local, mais une mise en production réelle demanderait une tâche "exécuter que l'utilisateur soit connecté ou non" (identifiants stockés, élévation admin) — limite documentée plutôt que dissimulée.

---

## Phase : Pipeline Annexe 13 complet — extraction, normalisation, validation, export (2026-09-09)

### Pourquoi

Les extracteurs existants (`annexe13_kpi_extractor.py`) ne récupèrent que 7 KPI/1 colonne "Total" par annexe — suffisant pour les dashboards, mais la page "Gestion de données" doit pouvoir exporter le tableau **tel qu'il existe réellement dans le PDF source** (toutes les branches — Automobile, Transport, Incendie... — pas seulement le sous-ensemble déjà utilisé). Décision explicite avec l'utilisatrice de traiter ça comme une pipeline séparée en 2 phases (extraction+validation d'abord, migration des dashboards ensuite, non commencée), annexe par annexe, en commençant par l'Annexe 13 (Résultat technique Non-Vie) sur les 15 sociétés conventionnelles.

### Méthode

1. **Comparaison rigoureuse avant adoption d'un nouveau moteur** : un script de référence fourni par l'utilisatrice (camelot + Selenium) a motivé une comparaison côte à côte GAT/STAR/BIAT/ASTREE entre l'ancien moteur (pdfplumber, repositionnement de mots) et camelot (détection de tableau native) — résultat sans ambiguïté en faveur de camelot (0 écart sur les 7 identités comptables de validation, contre une pile d'heuristiques fragiles côté pdfplumber) → **réécriture complète du module d'extraction** autour de camelot, sans toucher aux extracteurs 7-KPI des dashboards.
2. **Normalisation par dictionnaire canonique, construite sur TOUTES les sociétés** (pas seulement STAR) : relevé exhaustif des libellés de lignes ET de colonnes réellement extraits sur les 101 documents disponibles, puis construction de 2 référentiels — `CANONICAL_ROWS` (postes comptables, vocabulaire réglementaire commun) et `CANONICAL_COLUMNS` (branches d'assurance, ~30 entrées + dictionnaire d'alias pour les abréviations/orthographes variables d'une société à l'autre). Un piège de perte de données silencieuse a été trouvé et corrigé en cours de route (COMAR distingue certains postes par exercice N/N-1 sur 2 lignes réellement différentes — fusionner à tort sous le même libellé canonique aurait effacé la moitié des valeurs).
3. **Validation par identités comptables réelles** (7 règles du plan comptable des assurances — Primes acquises = Primes émises + Variation, Résultat technique = Solde de souscription + ..., etc.), appliquées par branche ET sur la colonne Total, stockées avec statut ok/écart/donnée-manquante par société/année/règle.
4. **Cycle audit-correction sur la couverture réelle**, avec diagnostic individuel plutôt que correctif générique aveugle : bug réel corrigé (COTUNACE — duplication de texte dans le flux PDF source + société mono-branche, seuil de détection adapté à la largeur du tableau) ; reclassification correcte de 2 sociétés à tort comptées en échec (ATTIJARI, UIB — Vie exclusivement par objet social, vérifié sur le texte même du PDF, pas un défaut d'extraction) ; contamination de données trouvée et nettoyée (le référentiel d'exclusion n'était appliqué qu'au script d'audit, jamais à la pipeline de stockage réelle — 6 documents mal-étiquetés supprimés de la base).
5. **Audit de QUALITÉ, pas seulement de couverture** : un audit binaire "OK/ÉCHEC" masque une vraie dégradation silencieuse — un document peut produire un tableau "plausible" (passe le contrôle de vraisemblance) tout en étant tombé sur une page de repli bien moins riche que la vraie grille par branche, parce que celle-ci est un scan sans couche de texte (page image insérée dans un document par ailleurs natif). Découvert sur retour utilisateur (comparaison directe export vs PDF réel), confirmé sur un 2ᵉ cas indépendant, distingué depuis en 3 issues (grille complète / repli dégradé / échec) plutôt que 2 — audit OCR de la prévalence du phénomène lancé en tâche de fond.
6. **Métriques de fiabilité corrigées 2 fois sur retour utilisateur direct** : la 1ʳᵉ version mesurait "% de documents déjà en base" (jamais < 95 % par construction, un document non découvert n'y apparaissant jamais) — corrigée pour comparer au véritable univers attendu par société (1ʳᵉ à dernière année connue, pas une plage fixe identique pour toutes) ; la fiabilité d'extraction est passée d'une mesure par règle comptable individuelle à une mesure par document.

### Ce qui a été livré

- Export Excel réel du tableau annexe complet (toutes branches, pas 7 KPI) pour l'Annexe 13, avec repli automatique sur re-extraction live si la validation de fond n'est pas encore passée sur un document — plafonné pour rester utilisable sur une sélection large (un cas réel d'export qui ne se terminait jamais a été corrigé).
- Page "Gestion de données" restructurée (maquette validée avant implémentation) : indicateurs de fiabilité réels, sélection multiple société/année/tableau, accès direct au PDF source, et un sélecteur qui désactive automatiquement une société sans aucune donnée pour le tableau choisi plutôt que de laisser produire un export vide.
- 2 référentiels de normalisation réutilisables pour les prochaines annexes (lignes + colonnes), documentés et versionnés dans le code plutôt qu'implicites.

### Chiffres clés

- **95/130 → couverture stabilisée** sur le sweep 10 ans (2016-2025) après les corrections de cette phase, contre 82/130 au premier relevé.
- **107/124 documents (86 %)** extraits avec succès parmi les sociétés réellement éligibles à l'Annexe 13 Non-Vie (hors Vie exclusivement/Takaful).
- **Audit de qualité** : sur ces 124 documents, **68 % grille complète par branche** (le résultat idéal), 16 % repli dégradé (valide mais moins riche), 16 % échec — dont la majorité concentrée sur 2 sociétés (COTUNACE, AMI) dont le document source semble scanné sur de larges portions, pas juste la page Annexe 13.
- **4 sociétés à 100 % de grille complète** sur toutes leurs années disponibles : BIAT, GAT, MAGHREBIA, TUNIS_RE.

### Limite assumée

Toutes les sociétés conventionnelles éligibles ont désormais un résultat pour l'exercice 2024, mais la QUALITÉ de ce résultat varie — un sous-ensemble (COTUNACE, AMI, et ponctuellement STAR/ASTREE) repose sur des pages sources scannées sans couche de texte, hors de portée de l'extraction actuelle (pdfplumber/camelot) sans un passage OCR dédié. Deux chantiers OCR sont en cours (page isolée pour STAR/ASTREE ; document potentiellement scanné dans sa quasi-totalité pour COTUNACE/AMI) plutôt que masqués comme une couverture à 100 %.
