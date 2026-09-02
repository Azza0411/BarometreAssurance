# Compréhension technique du projet — Baromètre Assurance TN

> Document de référence pour la préparation de la soutenance PFE. Compilé le 2026-09-02 à partir d'une lecture systématique du code source (pas de reconstruction depuis la mémoire de sessions passées). Chemins absolus depuis `C:\Users\HP\Desktop\SCRAPING`.

## Sommaire

0. [Points de vigilance avant la soutenance](#0-points-de-vigilance-avant-la-soutenance)
1. [Vue d'ensemble](#1-vue-densemble)
2. [Scraping](#2-scraping-scraping)
3. [Base de données](#3-base-de-données-database)
4. [Pipeline d'orchestration](#4-pipeline-dorchestration-pipelinesrun_pipelinepy)
5. [Extraction PDF — le cœur technique](#5-extraction-pdf--le-cœur-technique-extraction)
6. [Backend API Flask](#6-backend-api-flask-api)
7. [Frontend React](#7-frontend-react-frontend)
8. [IA / Machine Learning](#8-ia--machine-learning-chatbot_portable)
9. [Limitations connues — synthèse consolidée](#9-limitations-connues--synthèse-consolidée)

---

## 0. Points de vigilance avant la soutenance

Des écarts entre l'ancienne documentation de passation (`docs/prompt_handoff_ia_technique.md`) et le code réel ont été détectés lors de cette exploration. À corriger dans le discours avant que le jury ne les découvre :

1. **LLM utilisé = Groq, pas Claude.** Tout le sous-système IA (`chatbot_portable/`) appelle l'API **Groq** (modèle `openai/gpt-oss-120b`), pas l'API Anthropic/Claude. Aucune clé `ANTHROPIC_API_KEY` nulle part dans le dépôt. Le frontend affiche d'ailleurs littéralement "Groq LLM" dans le pied du widget Chatbot.
2. **Le RAG n'utilise pas d'embeddings.** Pas de base vectorielle (FAISS/Chroma/pgvector), pas de modèle d'embedding. Le retrieval est un **TF-IDF fait main** (`math.log`, pas scikit-learn malgré ce que suggère un docstring).
3. **"SHAP" = TreeSHAP natif XGBoost, pas la librairie `shap`.** Le calcul se fait via `booster.predict(dmat, pred_contribs=True)`, la lib `shap` n'est même pas dans `requirements.txt`.
4. **La synchronisation SQLite du chatbot (`sync_db.py`) est 100 % manuelle** — aucun scheduler ne l'appelle (contrairement à la veille, qui tourne en thread de fond). Risque de dérive silencieuse déjà survenu une fois en production.
5. **Frontend : plusieurs pages/composants morts ou non finalisés** :
   - `/positionnement` est un **stub non fonctionnel** (KPI codés en dur, texte placeholder "Contenu du tableau ici…"), inaccessible depuis la navbar.
   - `/geographie` fonctionne **entièrement sur des données mock** (`data/mockData.js`), aucun appel API.
   - `components/Sidebar.jsx`, `PageHeader.jsx`, `KpiCard.jsx`, `components/Positionnement.jsx` : code mort, non utilisés dans le rendu.
   - `pages/CarteAfrique.jsx`, `EtatGeneral.jsx`, `FicheEntreprise.jsx` (singulier) : pages orphelines, non routées.
   - `/positionnement`, `/kpi-detail`, `/rapport-pipeline` ne figurent dans aucun lien de la navbar (accès uniquement par URL directe ou navigation programmatique).
6. **Design system EY non centralisé** : la palette (`#FFE600`/`#2E2E38`) est redéfinie manuellement dans ~10 fichiers différents plutôt que dans un thème unique. `tailwind.config.js` déclare une police `Inter` jamais utilisée (Barlow est chargée et appliquée manuellement partout ailleurs).
7. **`react-simple-maps` est une dépendance inutilisée** — la carte de Tunisie est en réalité un SVG statique parsé/manipulé à la main (`TunisiaMap.jsx`).

Point positif à mettre en avant : le code contient un volume inhabituel de **commentaires narratifs justifiant chaque garde-fou par un cas réel** (date, société, symptôme observé) — bon argument pour démontrer la rigueur et l'itération empirique du projet.

---

## 1. Vue d'ensemble

**Baromètre Assurance TN / FS Market Intelligence** — outil interne EY Tunisie (dépt. Financial Services Transformation) qui automatise la collecte, l'extraction, le calcul et la restitution d'indicateurs financiers pour **24 compagnies d'assurance tunisiennes** (21-22 conventionnelles + 3 Takaful) à partir de 5 sources (CMF, FTUSA, CGA, BVMT, INS), avec traçabilité systématique jusqu'à la cellule source du PDF.

```
BarometreAssurance/
├── api/            Backend Flask (routes + services)
├── frontend/       React 19 + Vite + ApexCharts
├── extraction/     Extracteurs KPI par table PDF
├── scraping/       Scrapers par source
├── config/         Registre des 24 compagnies
├── database/       Accès MySQL (repository.py, schema.sql)
├── pipelines/      Orchestration planifiée
├── chatbot_portable/  RAG + prévisions ML (microservice séparé)
└── docs/
```

**Stack** : Python 3.11 / Flask / MySQL 8 (`MarketInsurance`) ; React 19 / Vite / ApexCharts / React Router v7 ; Selenium/requests (scraping) ; Tesseract OCR (`fra`/`ara`/`eng`) ; `rapidfuzz` (correspondance floue) ; Prophet + XGBoost (prévision) ; Groq (LLM).

**Aucune authentification** sur l'API — toutes les routes `/api/*` sont ouvertes (CORS sans restriction d'origine). Seule clé secrète en jeu : `GROQ_API_KEY`, utilisée côté serveur uniquement.

---

## 2. Scraping (`scraping/`)

5 scrapers de collecte KPI, chacun avec sa propre méthode adaptée au site cible :

| Scraper | Source | Méthode | Particularité notable |
|---|---|---|---|
| `cmf_portal_scraper.py` | Portail CMF | **Selenium** (widget JS dynamique) | 3 tentatives avec **relance complète** (pas juste l'étape en échec) ; filtre les états annuels au 31/12 sur ~10-11 ans glissants |
| `bvmt_scraper.py` | tunis-stockexchange.com | `requests` + regex | Découvre dynamiquement les sociétés cotées (secteur Assurance id=1938) ; 3 sous-fonctions (statut cotation, ESG, données marché) ; bulletin boursier annuel unique partagé par toutes les sociétés |
| `cga_scraper.py` | cga.gov.tn | `requests` + regex | Suit une chaîne de liens (page news → Google Drive) pour les rapports 2023+ |
| `ftusa_scraper.py` | ftusanet.org | `requests` + `pdfplumber` | Année **lue dans le contenu** du PDF (pas le nom de fichier, jugé trop peu fiable) ; garde la 1ʳᵉ occurrence d'une année (gère les republications) |
| `ins_scraper.py` | dataportal.ins.tn | API POST XML + repli HTML | Fallback HTML seulement pour les années absentes de l'API |

**Important** : les scrapers "Atlas Magazine"/"IlBoursa" ne sont **pas** dans `scraping/` — ils vivent dans `api/routes/veille.py` et alimentent le module Actualités/Réglementation (distinct du pipeline KPI), avec un cache mémoire TTL 1h.

**Déduplication** : chaque scraper vérifie l'existence en base avant d'enregistrer (clé `(source_id, cmf_id, annee)`), aucun re-téléchargement inutile.

**`config/company_registry.py`** — `COMPANY_REGISTRY` (24 sociétés, `{cmf_name, aliases}`), `TAKAFUL_CODES` (3 codes), `find_code_by_name()` : rapprochement par **similarité de Jaccard pondérée** (les mots rares comme "VIE" pèsent plus qu'un mot générique comme "ASSURANCES") avec liste de stopwords français — corrige un bug réel où "El Amana Takaful" matchait à tort "AMI".

---

## 3. Base de données (`database/`)

**Schéma** (6 tables, `database/schema.sql`) :
- `sources` (CMF/FTUSA/CGA/INS/BVMT)
- `cmf` (référentiel société : id, code, nom)
- `documents` (source_id, cmf_id **nullable** pour sources sectorielles, annee, lien) — clé unique `(source_id, cmf_id, annee)`
- `kpi_values` (document_id, **tableau**, kpi, valeur_nombre/valeur_texte) — clé unique `(document_id, tableau, kpi)` : `tableau` fait partie de la clé pour qu'un même nom de KPI produit par deux tableaux différents ne s'écrase jamais silencieusement
- `anomalies_detectees` (aussi utilisée comme journal d'instantanés du score qualité pour l'historique de tendance)
- `notifications`, `actualites_vues`, `reglementation_vues` (déduplication veille)

**`repository.py`** — accès direct `pymysql`, pas d'ORM. Points clés :
- `init_schema()` : migrations idempotentes basées sur `information_schema` (jamais de `DROP TABLE`), appelées à chaque démarrage de Flask.
- `save_document()` fait un upsert manuel (pas `ON DUPLICATE KEY`) car MySQL n'impose pas l'unicité entre plusieurs `cmf_id NULL`.
- `get_kpi_values_for_document(..., exclude_tableaux=...)` : le paramètre existe pour éviter une **corruption auto-référentielle** documentée (bug réel ASTREE 2025 : une valeur calculée relue comme donnée brute lors d'un recalcul suivant, 2,86 milliards TND au lieu de ~148M).
- Principe central répété partout : **aucune valeur manquante n'est jamais reconstituée** (pas d'interpolation, pas de report d'année précédente, pas de moyenne sectorielle).

---

## 4. Pipeline d'orchestration (`pipelines/run_pipeline.py`)

- `main()` exécute les 5 sources avec **retry 3 tentatives, backoff exponentiel 2/4/8s**, une source en échec n'interrompt pas les autres.
- `_check_quality()` calcule et **persiste un instantané** du score qualité (historique de tendance, ajouté juillet 2026).
- `_run_veille()` détecte les nouveautés actualités/réglementation.
- `_save_notifications()` alimente la cloche in-app.
- `_write_html_report()` génère un rapport HTML par run.
- Webhook Slack optionnel (`PIPELINE_ALERT_WEBHOOK`) en cas d'échec.

**Déclenchement** : Windows Task Scheduler, hebdomadaire (dimanche 2h).

**Problème réel découvert (2026-08-22)** : cette tâche planifiée n'avait **jamais tourné une seule fois** depuis son enregistrement (mode "Interactive uniquement", nécessite une session active). **Solution retenue** : `check_and_notify_veille()` — une version allégée (juste la veille, pas la collecte CMF complète) exécutée par un **thread de fond dans le process Flask lui-même** (`api/app.py::_start_veille_watcher`), toutes les 30 minutes, lancé automatiquement à l'import du module. La tâche planifiée Windows reste uniquement pour la collecte CMF complète (plus lourde).

---

## 5. Extraction PDF — le cœur technique (`extraction/`)

C'est la partie la plus complexe et différenciante du projet : extraire des données fiables de PDF hétérogènes (natifs, scannés, pivotés, en arabe).

### 5.1 Principe fondateur

Jamais `pdfplumber.extract_tables()` (jugé peu fiable) — reconstruction manuelle des lignes/colonnes à partir de `page.extract_words()` : `_cluster_lines()` regroupe les mots par proximité verticale (`Y_TOLERANCE=5pt`), `_extract_numeric_clusters()` regroupe les tokens numériques en colonnes.

**Règle d'or répétée dans tout le code** : "aucune donnée plutôt qu'une donnée fausse" — un garde-fou de plausibilité (`MIN/MAX_PLAUSIBLE_VALUE`) rejette toute valeur suspecte plutôt que de la renvoyer.

### 5.2 `_OcrFallbackPage` — bascule texte natif ↔ OCR

Enveloppe transparente autour d'une page pdfplumber :
- Bascule sur OCR si le texte natif est vide, ou (mode `force=True`, 2ᵉ passe) si des KPI-clés manquent encore après la 1ʳᵉ passe.
- **Piège découvert** : une page peut avoir du texte vectoriel réel mais un **encodage de police corrompu** (ex. BH 2020 : "3992 196 2r9o 892 rSol 3o4") — assez long pour ne pas déclencher le seuil de bascule automatique (20 caractères), mais inexploitable. D'où le mode `force`.
- OCR : `pytesseract`, résolution **300 dpi**, `lang="fra"`, `--psm 6` (mode "bloc de texte uniforme" — le mode par défaut fusionnait des mots adjacents sur les tableaux denses).

### 5.3 Extracteurs spécialisés par tableau

- **`bilan_kpi_extractor.py`** — Bilan Actif/Passif. Deux modes de repérage : "direct" (proche du libellé) et "section" (codes réglementaires AC1-AC7/PA1-PA7 comme ancres fiables, valeur = dernière ligne à chiffres ou maximum de la plage).
- **`annexe12/13_kpi_extractor.py`** — Résultat technique Vie/Non-Vie. Bug corrigé (2026-08-17) : sur les pages à 4 colonnes, la dernière colonne est l'année **précédente**, pas courante (114 valeurs changées lors de la régression).
- **`resultat_kpi_extractor.py`** — désambiguïsation Vie/Non-Vie par **code de ligne** (CHV/CHNV) plutôt que titre de page (5 formulations de titre différentes selon la société).
- **`cga_kpi_extractor.py`** — gère du texte tourné à 90° via une **matrice de police** (pas l'attribut `/Rotate` du PDF).
- **`calculated_kpi_extractor.py`** — ratios dérivés depuis les valeurs déjà en base (formules : ROA=RN/Actif×100, ROE=RN/CP×100, RSP=|charges prestations|/primes×100, RF=|charges acquisition|/primes×100, RC=RSP+RF). Garde-fou `segment_mismatch` (numérateur/dénominateur doivent couvrir le même segment Vie/Non-Vie).
- **`takaful_kpi_extractor.py`** — deux fonctions distinctes :
  - `extract_all_takaful_kpis` (AT_TAKAFULIA, ZITOUNA_TAKAFUL, français) : détecte format "ancien" vs "nouveau" (Bilan Combiné NCT 43, 3 sous-colonnes Fonds Adhérents/Entreprise/Combiné — seule "Entreprise" est retenue pour rester comparable au conventionnel).
  - `extract_al_amanah_takaful_kpis` (arabe) : s'appuie sur `arabic_ocr_extractor.py`.

### 5.4 `arabic_ocr_extractor.py` — extraction bilingue arabe

- Principe : l'OCR arabe repère bien les **libellés** (RTL) mais lit mal les **montants** → une fois la ligne localisée, la cellule est relue avec le modèle **anglais** (chiffres uniquement).
- Deux défauts RTL corrigés : chaque mot stocké en ordre miroir (inversion caractère par caractère) + mots eux-mêmes disposés droite→gauche sur la page (tri par x0 décroissant).
- Normalisation **NFKC** : certains exercices encodent en "Arabic Presentation Forms" (score de correspondance passé de ~4% à 100% sur le cas vérifié).
- Correspondance floue `rapidfuzz.fuzz.ratio` (similarité **globale**, pas `partial_ratio` — évite qu'un long suffixe générique partagé entre deux libellés différents fausse le score).

### 5.5 `api/services/pdf_cell_coords.py` — localisation pour le surlignage

Ne calcule pas de KPI, localise la **bbox** d'une cellule pour le surlignage frontend. **4 passes successives** dans `_find_row_y()` :

1. **Sous-chaîne exacte** sur la ligne entière.
2. **Mot-par-mot** (libellé coupé sur plusieurs mots).
3. **Titres repliés sur 2 lignes** (`_merge_wrapped_titles`) — fusionne les lignes sans chiffre avec leurs continuations immédiates.
4. **Correspondance floue** (`rapidfuzz`, seuil **82%**, sur mots non numériques uniquement) — dernier repli, nécessaire sur les pages OCRisées.

Toutes les passes excluent d'abord les **lignes de titre de page/annexe** (`_TITLE_ROW_RE = r"^annexe\s*n\s*\d"`) — un faux positif systémique découvert sur STAR 2025 Annexe 13, où le titre contient presque toujours le nom du KPI cherché.

`_resolve_title_row()` : si la ligne trouvée est un titre sans chiffre propre, descend jusqu'à la vraie ligne de total — **volontairement pas appliqué après la Passe 4** (sur une page OCR, un libellé peut être séparé de ses chiffres pour de simples raisons de mise en page, pas parce que c'est un vrai titre).

**Rotation de page** (`/Rotate 90`) — `_rotate_to_native()` : pdfplumber travaille en coordonnées **visuelles post-rotation**, mais pdf.js côté frontend attend des coordonnées **natives** (pré-rotation, car c'est lui qui applique sa propre rotation via le viewport). Sans cette conversion, le surlignage tombait au mauvais endroit sur les pages pivotées. Vérifié en simulant la séquence exacte `getViewport()`/`convertToViewportPoint()` en Node.js avec la vraie librairie `pdfjs-dist`, pas seulement en Python.

Modules apparentés : `arabic_pdf_cell_coords.py` (AL_AMANAH_TAKAFUL, badge "somme sur 2 pages" pour les valeurs Fonds Familial+Général réparties sur 2 pages), `sector_pdf_cell_coords.py` (FTUSA/CGA, la page n'est pas connue à l'avance côté frontend).

### 5.6 Documentation des cas particuliers (`extraction/CAS_PARTICULIERS*.md`)

11 fichiers, ~1080 lignes, structurés en tableaux Cas résolus / Cas non résolus. Exemples de limitations non résolues confirmées :
- **TUNIS_RE 2023** : PDF probablement rasterisé (espacement extrême caractère par caractère).
- **COTUNACE** : OCR de mauvaise qualité à la source (texte natif déjà corrompu) — seule société encore totalement exclue (`PROBLEMATIC_CODES`).
- **BH 2020** : Total actif introuvable même en OCR forcé (image trop dégradée).
- **STAR 2025, Annexe 13** : 2 lignes de données introuvables même à 400 dpi.

---

## 6. Backend API Flask (`api/`)

### 6.1 `app.py`

- `init_schema()` appelé à chaque démarrage (idempotent).
- 8 blueprints enregistrés : `apercu_marche`, `comparative`, `vue_assurance`, `enquete`, `veille`, `qualite`, `export`, `notifications`.
- `CORS(app)` global, gestionnaire d'erreur `ValueError → 400 JSON`.
- `app.run(port=8002, debug=True, use_reloader=False)` — le reloader plante la connexion MySQL au redémarrage sur cette machine Windows (cause exacte non identifiée, 100% reproductible) → **redémarrage manuel obligatoire** après toute modification backend.
- Thread de fond `_start_veille_watcher` (voir §4).

### 6.2 Inventaire des routes (par blueprint)

| Blueprint | Endpoints clés |
|---|---|
| `apercu_marche` | `/annees`, `/evolution`, `/ratios-evolution`, `/profil-pays`, `/ratios`, `/distribution-agences` — données sectorielles FTUSA/CGA/INS/Takaful |
| `comparative` | `/analyse-comparative`, `/classement-compagnies` — benchmarking inter-compagnies |
| `vue_assurance` | `/companies`, `/annees`, `/profil`, `/bilan`, `/evolution` — fiche détaillée par compagnie |
| `enquete` | `/companies`, `/data` — données d'enquête Excel (STAR seulement) |
| `veille` | `/actualites`, `/veille-reglementaire(+refresh)`, `/pdf-proxy`, `/cache/clear` — scraping live actualités |
| `qualite` | `/rapport-qualite`, `/sector-kpi-value`, `/pdf-local`, `/kpi-definition`, `/pdf-sections`, `/pdf-cell-coords`, `/sector-pdf-cell`, `/arabic-pdf-cell`, `/anomalies-systeme`, `/rapport-ia`, `/rapport-pipeline` |
| `export` | `/fiche-compagnie`, `/analyse-comparative` (PDF + xlsx), `/apercu-marche` |
| `notifications` | `/notifications`, `/unread-count`, `/<id>/read`, `/read-all` |

### 6.3 Services (`api/services/`)

- **`kpi_builder.py::build_company_row`** — fonction centrale réutilisée par comparative/vue_assurance/qualite/pipeline_audit/exports. Chaîne de règles de repli documentées (primes émises, PDM, RC/RSP/RF avec détection de "doublure" et recalcul depuis charges brutes, résultat technique, surplus Takaful).
- **`quality.py`** — `PROBLEMATIC_CODES` (seule entrée active : COTUNACE ; 4 autres retirées le 2026-08-17 après vérification). `build_quality_report()` : présence des 11 KPI attendus, plausibilité, doublure RC≈RF, écart sectoriel vs pairs.
- **`anomalies_service.py::build_anomalies_systeme`** — catégorise en 9 types d'anomalies (PDF absent, section non détectée, composante manquante, recalcul partiel, extraction échouée, valeur aberrante, déséquilibre bilan/YoY, doublure, écart sectoriel). `generate_rapport_ia()` : appelle Groq avec un **garde-fou anti-hallucination** (`_check_grounding` — rejette tout nombre cité par le LLM non présent dans les faits fournis, repli sur un template 100% déterministe).
- **`pipeline_audit.py::build_pipeline_audit`** — diagnostique la cause probable de chaque KPI manquant/aberrant sans re-scanner les PDF.
- **`pdf_export.py`** — réutilise directement les fonctions-vues Flask existantes (`test_request_context`) pour que l'export PDF affiche exactement les mêmes chiffres que l'écran (aucune règle métier dupliquée).
- **`excel_export.py`** — écrit de vraies **formules Excel** pour les KPI simples (PDM, ROE, ROA, RF), mais des **valeurs figées** pour RC/RSP (trop de règles de repli pour être reproduites fidèlement en formule tableur).

---

## 7. Frontend React (`frontend/`)

React 19 + Vite + `react-router-dom` v7 + `react-apexcharts` + `pdfjs-dist`. Pas de design system centralisé (voir §0).

### 7.1 Coquille applicative (`App.jsx`)

- `AppNavbar` réellement partagée entre toutes les pages (y compris Accueil) — corrige une ancienne divergence où une copie manuelle sur Accueil avait dérivé.
- 8 modules dans la navbar sur 13 routes existantes — `/positionnement`, `/kpi-detail`, `/rapport-pipeline` non liés (accès direct par URL uniquement).
- Page `/accueil` : hero 6 slides rotatifs (7s), chaque slide pointe vers une route différente.

### 7.2 Les 13 pages

| Route | État | Résumé |
|---|---|---|
| `/accueil` | ✅ | Hero 6 slides |
| `/apercu-marche` | ✅ | Profil Pays + Distribution agences, `TunisiaMap` |
| `/positionnement` | ⚠️ stub | Données codées en dur, non fonctionnel, non lié |
| `/geographie` | ⚠️ mock | Données 100% statiques (`mockData.js`), carte SVG maison différente de `TunisiaMap` |
| `/fiches` | ✅ | Vue par Assurance — fiche compagnie complète |
| `/analyse-comparative` | ✅ | Benchmarking multi-compagnies, tiers Leader/Challenger/Follower |
| `/enquete-marche` | ✅ | 2 onglets (Échantillon / Fiche client), Excel STAR |
| `/veille-reglementaire` | ✅ | Table filtrable CGA/FTUSA, bouton refresh live |
| `/actualites-seminaires` | ✅ | Flux IlBoursa/Atlas Magazine |
| `/qualite-donnees` | ✅ | Matrice Compagnie×KPI, 2 modes (entreprise/sectoriel) |
| `/kpi-detail` | ✅ | Zoom + surlignage PDF (voir §7.3), non lié dans navbar |
| `/rapport-pipeline` | ✅ | Audit pipeline par société/étape, non lié dans navbar |
| `/anomalies-systeme` | ✅ | Table + bouton "Rapport IA" (génération à la demande) |

### 7.3 `KpiDetail.jsx` — mécanisme zoom + surlignage PDF

- Rendu via `pdfjs-dist`, deux canvas superposés (rendu PDF + overlay de surlignage transparent aux événements souris).
- Cache du document parsé (`pdfDocCacheRef`) — seul un changement de société/année reparse le PDF ; zoom/page ne fait que `page.getViewport()`.
- **Synchronisation overlay** : le canvas overlay doit être redimensionné aux mêmes dimensions que le canvas PDF **au moment même du rendu**, pas seulement dans l'effet séparé de dessin — sinon reste bloqué à 300×150 par défaut (bug corrigé le 2026-08-22).
- Conversion de coordonnées : `viewportRef.current.convertToViewportPoint(x0,y0)` — API native pdf.js, gère automatiquement échelle **et** rotation.
- 3 endpoints selon le cas : `pdf-cell-coords` (standard), `sector-pdf-cell` (FTUSA/CGA, page déterminée côté backend), `arabic-pdf-cell` (AL_AMANAH_TAKAFUL, ni ligne ni colonne fournies).
- Badge bleu "somme sur 2 pages" ⟷ champ `note` renvoyé uniquement par `arabic_pdf_cell_coords.py` (cas Fonds Familial+Général) ; badge rouge sinon.

### 7.4 Composants et utilitaires transverses

- **`Chatbot.jsx`** — widget FAB flottant, backend **séparé** (`:5001`, distinct de l'API principale `:8002`). Contenu riche selon `render` (`table`/`ranking`/`evolution`/`kpi_cards`/texte). Intégration croisée : `KpiOptionsMenu` déclenche un event DOM `kpi:ask-chatbot` écouté par le Chatbot pour poser automatiquement "Pourquoi {KPI} de {société} est à {valeur} en {année} ?".
- **`NotificationBell.jsx`** — polling 60s sur le compteur non-lu uniquement.
- **`TunisiaMap.jsx`** — SVG statique parsé/manipulé à la main (pas `react-simple-maps`, dépendance inutilisée), 24 gouvernorats → 7 régions CGA.
- **`KpiOptionsMenu.jsx`** — menu "i" sur chaque KPI (3 actions : qualité, source PDF, expliquer via chatbot), monté en `createPortal`.
- **`utils/kpiMeta.js`** — source de vérité de la formule + localisation PDF de chaque KPI (arbre récursif `extrait`/`calcule`/`externe`), alimente `KpiDetail` et la classification qualité.
- **`utils/famille.js`** — miroir front-end de `TAKAFUL_CODES` (duplication volontaire documentée).

---

## 8. IA / Machine Learning (`chatbot_portable/`)

Microservice Flask **indépendant** (port 5001), lit sa propre copie SQLite (portabilité Docker sans dépendance MySQL directe).

### 8.1 Chatbot RAG

- Retrieval **TF-IDF fait main** (pas d'embeddings) : `_tokenize()` + `_tfidf_score()` codés à la main.
- Corpus hybride : 12 fiches réglementaires rédigées à la main (`CORPUS`) + corpus "extra" ingéré automatiquement depuis les rapports CGA (`rag_ingest.py`, pipeline batch manuel, filtrage anti-corruption OCR `>1% caractères de remplacement → page ignorée`, chunking par paragraphes 400-1000 caractères).
- Génération via Groq, prompt système strict "réponds uniquement à partir des documents fournis", fallback sans LLM = renvoi direct du contexte brut si Groq échoue.

### 8.2 Module de prévision (`prediction/`)

Architecture Factory/Strategy, point d'entrée `ForecastService.predict()` :
1. Validation (alias KPI, horizon max 5 ans) → 2. Chargement SQLite → 3. Prétraitement (rejet valeurs impossibles, IQR×3, interpolation) → 4. **Sélection automatique** → 5. Prévision → 6. Explicabilité → 7. Narratif.

**Sélection Prophet vs XGBoost** — vrai AutoML léger par **cross-validation chronologique** (TimeSeriesSplit + Walk-Forward combinés), score composite `MAPE×0.7 + (RMSE/MAE)×0.3`, le plus bas gagne. Préférence a priori par nature de KPI (Prophet pour séries à tendance structurelle type primes/PIB, XGBoost pour ratios volatils type ROE/sinistralité) qui détermine seulement l'ordre de test, pas le résultat final.

**Explicabilité** :
- XGBoost → TreeSHAP natif (pas la lib `shap`), calculé sur le dernier point historique, 8 features (`lag_1/2/3`, `rolling_mean_3/std_3`, `yoy_growth`, `cagr_3`, `trend_index`).
- Prophet → décomposition trend (poids 0.6) / saisonnalité (0.2) / momentum récent (0.2).

**Narratif** : "ce module ne calcule RIEN, il formate uniquement" — texte structuré passé au LLM Groq pour reformulation. Prompt anti-hallucination renforcé après un incident réel (2026-08-18) où le LLM inventait des événements fictifs (fusion de compagnies, cadre réglementaire inexistant).

**Fallback complet** : si `prediction/` échoue (Prophet/XGBoost absents, données insuffisantes), bascule sur une régression linéaire OLS simple, explicitement étiquetée comme telle.

### 8.3 `sync_db.py`

Reconstruction **complète** (DELETE + ré-INSERT intégral, pas de diff incrémental — volume jugé trop faible pour justifier la complexité). **Déclenchement entièrement manuel**, aucun scheduler ne l'appelle — un incident réel (copie datée d'un mois, faussant les prévisions) est documenté directement dans le code.

### 8.4 Intégration

- Endpoints : `POST /api/chatbot`, `/greet`, `/reset`, `GET /history`, `/status`.
- `prediction/` n'est importé nulle part ailleurs que par le chatbot (`_handle_forecast()`).

---

## 9. Limitations connues — synthèse consolidée

| Domaine | Limitation | Statut |
|---|---|---|
| Bilan | COTUNACE : OCR corrompu à la source | Non résolu, société exclue |
| Bilan | BH 2020 : Total actif introuvable (image trop dégradée) | Non résolu |
| Annexe 12/13 | COMAR 2018 : PDF entièrement scanné, 0 caractère sur 45 pages | Non résolu |
| Annexe 13 | STAR 2025 : 2 lignes introuvables même à 400 dpi | Non résolu, documenté |
| Résultat | TUNIS_RE 2024 : séparateur milliers scindant un nombre en 2 tokens | Cause identifiée, correctif non appliqué (portée jugée trop large) |
| Takaful | AL_AMANAH_TAKAFUL : Surplus Familial/Général incomplet (5/9 exercices) | Non résolu |
| Takaful | Commissions Wakala/Moudharaba | Jamais câblées (signe incohérent en test) |
| Takaful | ZITOUNA_TAKAFUL 2025 : texte corrompu au niveau caractère | Non résolu, jugé disproportionné |
| Sync ML | Copie SQLite chatbot peut dériver silencieusement | Pas de garde-fou automatique |
| Frontend | `/positionnement`, `/geographie` non fonctionnels/mock | À finaliser ou retirer avant la soutenance |
| Traçabilité | Priorisation des sociétés à approfondir pour l'audit `/kpi-detail` | Jamais tranchée par l'utilisateur |

---

*Document généré par exploration parallèle du code (5 agents dédiés : scraping/BDD/pipeline, extraction PDF, backend API, frontend, IA/ML). Pour le détail exhaustif fichier-par-fichier de chaque module, voir les rapports complets dans l'historique de session du 2026-09-02.*
