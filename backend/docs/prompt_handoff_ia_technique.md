# Prompt de passation technique — à copier-coller dans une nouvelle conversation IA

---

Tu reprends le développement d'une plateforme sur laquelle j'ai déjà travaillé en profondeur avec une autre IA pendant de nombreuses sessions. Ce prompt te donne tout le contexte nécessaire pour être immédiatement opérationnel, comme si tu avais suivi tout le projet depuis le début. Lis-le entièrement avant de toucher au code.

## 1. Le projet en une phrase

**"Baromètre Assurance TN" / "FS Market Intelligence"** — un outil **interne** (pas un produit client) destiné aux consultants du département **Financial Services Transformation (FST) d'EY Tunisie**, qui automatise la collecte, l'extraction, le calcul et la restitution des indicateurs financiers de **24 compagnies d'assurance tunisiennes** (21-22 conventionnelles + 3 Takaful) à partir de 5 sources officielles (CMF, FTUSA, CGA, BVMT, INS), avec traçabilité systématique de chaque chiffre jusqu'à sa cellule source dans le PDF d'origine. C'est aussi mon **projet de fin d'études (PFE)**, ESPRIT, en partenariat avec EY — garde ça en tête pour le ton et les priorités (rigueur, documentation, démontrabilité).

## 2. Architecture technique

```
BarometreAssurance/
├── api/
│   ├── app.py                 # Point d'entrée Flask, enregistre les blueprints,
│   │                          # lance un thread de fond (_start_veille_watcher)
│   ├── routes/                # apercu_marche, comparative, vue_assurance, enquete,
│   │                          # veille, qualite, export, notifications
│   ├── services/               # kpi_builder, quality, pdf_cell_coords,
│   │                          # arabic_pdf_cell_coords, sector_pdf_cell_coords,
│   │                          # pdf_export, excel_export, pipeline_audit, anomalies_service
│   └── assets/                 # logos, images pour les exports PDF/Excel
├── frontend/                  # React 18 + Vite
│   └── src/
│       ├── pages/             # 13 pages (voir section 5)
│       ├── components/        # AppNavbar (dans App.jsx), NotificationBell, KpiOptionsMenu,
│       │                      # PageHeaderBar, TunisiaMap, Chatbot
│       └── utils/             # kpiMeta.js (métadonnées KPI), famille.js (Conventionnel/Takaful),
│                              # kpiCatalog.js, kpiStatus.js, logos.js
├── extraction/                 # Extracteurs KPI par source/type de tableau (section 7)
├── scraping/                   # Scrapers (CMF, BVMT, ilboursa, Atlas Magazine, CGA, FTUSA)
├── config/                     # company_registry.py (24 compagnies, TAKAFUL_CODES)
├── database/                   # repository.py (accès MySQL), schema.sql
├── pipelines/run_pipeline.py    # Orchestration planifiée (Windows Task Scheduler, peu fiable —
│                              # voir section 9) + check_and_notify_veille (thread in-process)
├── chatbot_portable/            # Sous-système IA : RAG + prévisions ML (section 8)
└── docs/                       # pfe_phase_documentation.md, prompts precedents, ratios Takaful
```

**Stack** : Python 3.11 / Flask / MySQL 8 (base `MarketInsurance`) ; React 18 / Vite / ApexCharts / React Router ; Design System EY (Barlow, #FFE600, #2E2E38) ; scraping Selenium/Requests ; OCR Tesseract (`pytesseract`, modèles `fra`/`ara`) ; correspondance floue `rapidfuzz`.

**Environnement Windows — pièges connus** :
- Le rechargeur automatique Flask (`use_reloader`) est **désactivé** (`app.run(port=8002, debug=True, use_reloader=False)`) — il plante la connexion MySQL au redémarrage sur cette machine. **Toute modification backend nécessite un redémarrage manuel du process Flask** (`taskkill` puis relancer `python api/app.py`) — sinon le code modifié n'est jamais exécuté, même si le fichier est sauvegardé.
- Le frontend (Vite) a le HMR activé, mais il arrive qu'il ne se déclenche pas correctement — si un correctif frontend ne semble "pas marcher", demander un **rechargement forcé (Ctrl+Shift+R)**, pas juste F5, avant de chercher un bug ailleurs.
- `curl` depuis Git Bash mange les caractères accentués dans les paramètres d'URL (ex: "é" mal encodé) — ça peut faire échouer un test alors que l'app réelle fonctionne. **Toujours tester les endpoints avec accents via Python `requests`, jamais `curl` directement.**
- Git : repo `Azza0411/BarometreAssurance`, branche de travail `ThirdVersion`. **Règle permanente : pousser sur GitHub (commit + push) à la fin de chaque modification**, sans attendre qu'on te le demande — mais toujours vérifier `git status` avant un `git add` large (des fichiers de debug/scratch traînent souvent à la racine : `*.txt`, `nul`, `market_intel.db`, `_originals_backup/` — à ne jamais committer).

## 3. Base de données — modèle central

- `cmf` (id, code, nom_entreprise) — une ligne par compagnie suivie.
- `documents` (id, source_id, societe_id, nom_pdf, annee, lien) — un PDF par compagnie/année/source.
- `kpis` (id, document_id, tableau, kpi, valeur_nombre, valeur_texte) — clé unique (document_id, tableau, kpi) : le `tableau` fait partie de la clé pour que deux tableaux différents produisant le même nom de KPI ne s'écrasent jamais en silence.
- `anomalies_detectees`, `notifications` (type, titre, message, gravite, lien, lu), `veille_actualites`, `veille_reglementaire` (diff "déjà vu/nouveau" pour les notifications).
- `config/company_registry.py::COMPANY_REGISTRY` = les 24 compagnies (clé = code court, ex: "STAR"), `TAKAFUL_CODES = {"AT_TAKAFULIA", "ZITOUNA_TAKAFUL", "AL_AMANAH_TAKAFUL"}`, `get_famille(code)` → "conventionnelle"/"takaful".

## 4. Philosophie de travail — À RESPECTER STRICTEMENT

Ces règles ne sont pas optionnelles, elles ont toutes été établies suite à des incidents réels :

1. **"Aucune donnée plutôt qu'une donnée fausse."** Si une valeur ne peut pas être extraite/localisée avec confiance, renvoyer `None`/"introuvable" — ne JAMAIS deviner ou renvoyer une valeur approximative silencieusement. Chaque extracteur applique des garde-fous de plausibilité (planchers/plafonds) plutôt que de faire confiance aveuglément à l'OCR ou au texte réel.
2. **Vérification empirique avant tout code.** Avant d'écrire un extracteur/motif de correspondance, ouvrir le VRAI PDF (render en image via `pdfplumber`, `page.to_image(resolution=...)`, puis `Read` l'image générée) pour confirmer visuellement la structure exacte — ne jamais deviner un format.
3. **Simplicité et généralisation** — préférer un correctif simple et généralisable à une branche spécifique par compagnie. Documenter les cas particuliers plutôt que les coder en dur partout.
4. **Documenter les cas particuliers par table d'extraction** : `extraction/CAS_PARTICULIERS*.md` (un fichier par table : Bilan, Annexe 12, Annexe 13, CGA, Calculs, Résultat, Takaful) — chaque cas résolu ET chaque limite non résolue y est consigné avec la société/l'année concernée et l'explication.
5. **Toujours donner le chemin complet** des fichiers/commandes référencés, jamais juste un nom de fichier.
6. **Documenter chaque phase validée pour la soutenance PFE** : après une phase significative, ajouter une section à `docs/pfe_phase_documentation.md` (format : Pourquoi / Méthode / Ce qui a été livré / Chiffres clés / Limite assumée).
7. **Toujours pousser sur GitHub** après chaque modification (voir section 2).
8. **Restaurer/mettre à jour la mémoire** si un fait mémorisé s'avère faux (ex: `SimulateurWhatIf.jsx` a été supprimé depuis, une ancienne mémoire le donnait encore comme "implémenté").

## 5. Les 13 pages du frontend (routes)

`/apercu-marche`, `/positionnement`, `/geographie`, `/fiches` (Vue par Assurance), `/analyse-comparative`, `/enquete-marche` (2 onglets : Analyse de l'échantillon / Fiche client entreprise), `/veille-reglementaire`, `/actualites-seminaires`, `/qualite-donnees`, `/kpi-detail` (zoom + surlignage PDF), `/rapport-pipeline`, `/anomalies-systeme`, `/accueil` (hero 6 slides tournants).

Navbar partagée : `AppNavbar` (définie dans `App.jsx`), utilisée PARTOUT y compris Accueil (ne JAMAIS dupliquer la navbar, ça a causé une divergence corrigée récemment) — inclut `NotificationBell`.

## 6. Logique Conventionnel vs Takaful — le cœur métier du projet

- **AT_TAKAFULIA** et **ZITOUNA_TAKAFUL** publient en **français**. Deux formats réglementaires coexistent : "ancien" (≤2019, structure proche du conventionnel) et "nouveau" (~2020+, "Bilan Combiné" NCT 43 à 3 colonnes Fonds des Adhérents/Entreprise/Combiné). Extracteur dédié : `extraction/takaful_kpi_extractor.py::extract_all_takaful_kpis`.
- **AL_AMANAH_TAKAFUL** publie en **arabe** — extracteur séparé `extract_al_amanah_takaful_kpis` (même fichier), s'appuyant sur `extraction/arabic_ocr_extractor.py` (lecture RTL, normalisation NFKC, repli OCR bilingue arabe/anglais pour les chiffres).
- 33 ratios Takaful documentés (sourcés IFSB) dans `docs/ratios_takaful_ifsb_aaoifi.md`. 6 indicateurs "Fonds des Participants" (Surplus Familial/Général, Total actifs nets des adhérents, Provisions techniques, Commissions Wakala/Moudharaba) ajoutés pour AT_TAKAFULIA/ZITOUNA_TAKAFUL ; **partiellement seulement** pour AL_AMANAH_TAKAFUL (voir section 9, limites connues).
- Frontend : `frontend/src/utils/famille.js` (`isTakaful(code)`, `famille(code)`), filtre "Toutes/Conventionnelles/Takaful" sur Analyse Comparative et Aperçu Marché.

## 7. Système d'extraction PDF — architecture et pièges

**Extracteurs par tableau source** : `bilan_kpi_extractor.py` (Bilan Actif/Passif), `annexe12_kpi_extractor.py` (Résultat technique Vie), `annexe13_kpi_extractor.py` (Résultat technique Non-Vie), `resultat_kpi_extractor.py` (État de résultat), `cga_kpi_extractor.py`, `calculated_kpi_extractor.py` (ratios dérivés : ROE, ROA, ratio combiné/sinistralité/frais), `takaful_kpi_extractor.py`, `enquete_extractor.py` (enquête CX, fichier Excel).

**`_OcrFallbackPage`** (dans `bilan_kpi_extractor.py`) : enveloppe transparente d'une page pdfplumber — utilise le texte natif si disponible, sinon bascule sur l'OCR (`_ocr_words`, Tesseract `--psm 6`, résolution 300 DPI, `lang="fra"`). **Piège découvert récemment** : une page peut avoir du texte vectoriel RÉEL (pas scannée) mais un encodage de police corrompu qui fait que `page.chars`/`extract_words()` natifs renvoient presque rien → bascule sur OCR même si l'image rendue est parfaitement nette. Dans ce cas, la qualité OCR devient le facteur limitant, PAS la qualité de scan.

**`api/services/pdf_cell_coords.py`** — localise la cellule source d'un KPI pour le surlignage (`KpiDetail.jsx`). `_find_row_y()` a **4 passes successives** :
1. Sous-chaîne exacte sur la ligne entière.
2. Correspondance mot-par-mot (libellé coupé sur plusieurs mots).
3. Titres de section repliés sur 2 lignes (`_merge_wrapped_titles`).
4. **Correspondance floue** (`rapidfuzz.fuzz.ratio`, seuil 82%, comparée aux mots NON numériques seulement) — dernier repli pour les pages OCRisées où le libellé peut être trop dégradé pour survivre en sous-chaîne exacte.

Pièges corrigés récemment (tous documentés en commentaire dans le fichier) :
- Les 4 passes **excluent désormais les lignes qui sont en fait le TITRE de la page/annexe** (motif `_TITLE_ROW_RE = r"^annexe\s*n\s*\d"`) — le titre contient presque toujours le nom du KPI cherché, un faux positif systémique.
- `_resolve_title_row()` (qui part du principe qu'une ligne sans chiffre propre est un titre dont le vrai total est plus bas) **ne doit PAS être appliqué après la passe 4** — sur une page OCR, un libellé peut être clustered séparément de ses propres chiffres pour de simples raisons de mise en page, pas parce que c'est un vrai titre de section.
- **Rotation de page (`/Rotate 90`, etc.)** : pdfplumber applique la rotation à `page.width`/`page.height` ET aux coordonnées des mots (déjà dans le repère "visuel" post-rotation), mais **pdf.js côté frontend attend des coordonnées NATIVES (pré-rotation)** — sa propre rotation est appliquée via le viewport pour l'affichage. `_rotate_to_native()` reconvertit les coordonnées avant de les renvoyer. **Vérifié et confirmé correct** via un test direct avec la vraie librairie `pdfjs-dist` en Node.js (pas seulement en Python) — méthode de vérification à retenir : simuler l'exacte séquence `page.getViewport()` + `convertToViewportPoint()` en Node pour trancher un doute, plutôt que deviner.
- Le canvas de surlignage (overlay) côté `KpiDetail.jsx` doit être resynchronisé en taille (`overlay.width/height = canvas.width/height`) **au moment même du rendu de la page PDF**, pas seulement dans l'effet séparé qui dessine le rectangle — sinon il peut rester bloqué à sa taille par défaut (300×150) alors que le vrai canvas est déjà correctement dimensionné.

**`arabic_pdf_cell_coords.py`** : même logique pour AL_AMANAH_TAKAFUL, avec en plus la gestion des valeurs "somme sur 2 pages" (Fonds Familial + Général) — badge bleu "Cellule surlignée — somme sur 2 pages" distinct du badge rouge normal côté frontend.

## 8. IA / Machine Learning (`chatbot_portable/`)

- **Chatbot RAG** connecté à l'API Claude (`rag_module.py`, `rag_ingest.py`) — ancré sur les données réelles de la plateforme, pas seulement la connaissance générale du modèle.
- **Module de prévision** : Prophet + XGBoost avec sélection automatique, explicabilité SHAP, narratif en langage naturel auto-généré (`prediction/`).
- Ce sous-système a sa **propre copie SQLite** (`chatbot_portable/MarketInsurance.db`) synchronisée depuis MySQL via `chatbot_portable/sync_db.py` — sans rafraîchissement régulier, cette copie dérive silencieusement de la base principale (découvert une fois : la copie datait de 3 semaines, faussant les prévisions ML bâties dessus).

## 9. Notifications — architecture et limite connue

Cloche in-app (`NotificationBell.jsx`, polling 60s) alimentée par 3 types d'événements : nouveau document (toutes sources), anomalie critique, nouvelle actualité/texte réglementaire.

**Important** : la tâche planifiée Windows (`schtasks`, pipeline complet hebdomadaire) s'est révélée **peu fiable** — constaté qu'elle n'avait jamais tourné une seule fois depuis son enregistrement (mode "Interactive uniquement", nécessite une session active pile au bon moment). **Solution actuelle** : un thread de fond DANS le process Flask lui-même (`api/app.py::_start_veille_watcher`, appelle `pipelines/run_pipeline.py::check_and_notify_veille()` au démarrage puis toutes les 30 min) — couvre uniquement la veille (actualités/réglementation), pas la collecte CMF complète (plus lourde, reste sur la tâche planifiée).

## 10. Qualité des données et anomalies

`api/services/quality.py::PROBLEMATIC_CODES` — liste des compagnies structurellement exclues des filtres (actuellement seulement COTUNACE ; UIB/HAYETT/CARTE_VIE/AMI en ont été retirées le 2026-08-17 après vérification que le motif d'exclusion ne décrivait plus la réalité). `api/services/anomalies_service.py::build_anomalies_systeme` — détection automatique (variations YoY implausibles, déséquilibres de bilan, échecs d'extraction).

## 11. Limitations connues / travaux non terminés (à ne pas re-découvrir de zéro)

- **AL_AMANAH_TAKAFUL, "Fonds des Participants"** : Surplus Familial/Général extrait seulement pour 2019 et 2021 complets, 2022 Familial seul — le reste (2020, 2023-2025) reste `None`, texte/OCR non fiable. Commission Wakala/Moudharaba : jamais câblées (signe incohérent en test). Voir `extraction/CAS_PARTICULIERS_TAKAFUL.md`.
- **STAR 2025, Annexe 13** : "Résultat technique" et une partie de "Charges d'acquisition et de gestion nettes" restent introuvables — page à police corrompue + OCR qui ne détecte tout simplement pas ces 2 lignes de données précises (testé même à 400 DPI). Limite documentée, pas un bug de code.
- **Audit systématique de traçabilité des sources** (quel KPI a un lien "Localiser dans le PDF" fonctionnel) : audit lancé, 2 bugs systémiques corrigés, mais la priorisation "quelles compagnies approfondir en premier" n'a jamais été tranchée par l'utilisateur — probablement à reprendre si le sujet revient.
- `SimulateurWhatIf.jsx` a été **supprimé** du projet (confirmé) malgré d'anciennes notes le donnant comme livré — ne pas s'y référer comme fonctionnalité existante.

## 12. Comment je veux qu'on travaille ensemble

- Quand tu modifies le backend, **redémarre Flask toi-même** et vérifie via un vrai appel HTTP (Python `requests`, pas `curl`) avant de me dire que c'est corrigé.
- Quand tu modifies le frontend, vérifie visuellement si possible (navigateur), et si un doute persiste sur un rendu PDF/canvas, **le rendre via une capture d'écran ou un crop d'image** plutôt que de deviner.
- Sois honnête sur ce qui est vérifié vs supposé — si tu ne peux pas vérifier visuellement, dis-le clairement plutôt que d'affirmer que c'est corrigé.
- Documente au fil de l'eau (CAS_PARTICULIERS, pfe_phase_documentation) plutôt qu'à la fin.
- Pousse sur GitHub après chaque changement validé.
- Si une hypothèse de bug ne se confirme pas après investigation, dis-le et explique ce que tu as vérifié — ne t'arrête pas à la première explication plausible sans preuve.
