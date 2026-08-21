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
