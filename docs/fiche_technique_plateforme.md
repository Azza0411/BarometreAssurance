# Fiche technique — Baromètre Assurance TN

## PARTIE 1 — ARCHITECTURE GÉNÉRALE ET STACK TECHNIQUE

### Structure des dossiers

![Structure des dossiers du projet](diagrams/folder_structure.png)

### Flux de la donnée

![Flux de la donnée, du site source à l'écran](diagrams/data_flow.png)

### Stack technique — l'essentiel

| Brique | Outil | Pourquoi (résumé) |
|---|---|---|
| Backend | Python + Flask | Léger, même langage que l'extraction |
| Base de données | MySQL | Données très relationnelles |
| Scraping | Selenium (CMF) + requests (reste) | Selenium seulement si JS dynamique |
| Extraction PDF | pdfplumber + Tesseract OCR | Position exacte des mots + OCR gratuit fr/ar |
| Frontend | React + Vite | Rechargement rapide en dev |
| Graphiques | ApexCharts | Beaucoup de types, peu de code |
| IA générative | Groq | Rapide, peu coûteux |
| Prévision | Prophet + XGBoost | Complémentaires, sélection auto du meilleur |
| Déploiement | Docker | Isole les services, reproductible |

**Règle générale** : l'outil le plus simple qui couvre le besoin réel, pas le plus sophistiqué.

---

## PARTIE 2 — SCRAPING — LA COLLECTE DES DONNÉES

**8 sources d'origine.** CGA et FTUSA servent chacune 2 usages (rapports KPI + veille réglementaire), mais restent 1 source chacune.

![Schéma de la couche de scraping](diagrams/scraping_architecture.png)

| Méthode | Sources | Pourquoi (résumé) |
|---|---|---|
| Selenium | CMF | Menu JS dynamique — une requête simple ne suffit pas |
| `requests` + regex | FTUSA, CGA, BVMT, INS, Atlas Magazine, IlBoursa | Pages HTML statiques, plus simple |
| Fichier local | ENQUETE | Excel fourni, pas un site web |

### Déroulé complet — cas CMF (le plus complexe, donc représentatif)

![Déroulé complet du scraper CMF](diagrams/cmf_workflow.png)

En cas d'échec à n'importe quelle étape : relance complète (×3), jamais une reprise partielle — un plantage en cours de route laisse le navigateur dans un état difficile à récupérer.

**scraping/cmf_portal_scraper.py — lignes 310 à 328 — mécanisme de nouvelle tentative**

![Code réel du mécanisme de nouvelle tentative](diagrams/code_scraping_retry.png)

---

![Zoom filtrage](diagrams/banner_zoom_filtrage.png)

Parmi tous les documents qu'une source propose, ne garder que ceux qui sont réellement pertinents — le critère exact dépend de la source. Exemple concret CMF :

![Exemple de filtrage — cas du scraper CMF](diagrams/filtrage_exemple_cmf.png)

---

![Zoom déduplication](diagrams/banner_zoom_dedup.png)

Avant d'enregistrer un document, vérifier qu'il n'existe pas déjà en base (société + source + année) :

![Exemple de déduplication — cas du scraper CMF](diagrams/dedup_exemple_cmf.png)

**scraping/cmf_portal_scraper.py — lignes 281 à 298 — déduplication et enregistrement**

![Code réel de la déduplication et de l'enregistrement](diagrams/code_scraping_dedup.png)

---

### À savoir par source

![À savoir par source](diagrams/a_savoir_par_source.png)

### Reconnaissance automatique des sociétés

![Reconnaissance automatique des sociétés](diagrams/reconnaissance_societes.png)
