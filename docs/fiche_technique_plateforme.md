# Fiche technique — Baromètre Assurance TN

## PARTIE 1 — ARCHITECTURE GÉNÉRALE ET STACK TECHNIQUE

### Structure des dossiers

```
BarometreAssurance/
├── api/              serveur backend
├── frontend/          site web
├── scraping/           robots de collecte
├── extraction/           lecture des PDF
├── database/              accès MySQL
├── config/                 registre des 24 compagnies
├── pipelines/               orchestration planifiée
└── chatbot_portable/         IA, serveur séparé
```

### Flux de la donnée

- Scraping → un PDF est repéré sur un site officiel
- Base de données → métadonnées notées (société, année, lien)
- Extraction → les chiffres sont lus dans le PDF
- Base de données → chiffres stockés
- Calcul → ratios déduits (rentabilité, sinistralité...)
- API → backend sert les données en JSON
- Frontend → affichage en graphiques/tableaux

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

**Déroulé CMF** (le plus complexe, donc représentatif) :
- Ouvrir un Chrome invisible
- Sélectionner la société
- Lancer la recherche
- **Filtrer** (voir schéma ci-dessous)
- Vérifier que le lien PDF répond
- **Dédupliquer** (voir schéma ci-dessous)
- Enregistrer les métadonnées seules — jamais le PDF
- En cas d'échec : relance complète (×3), jamais une reprise partielle

![Code réel du mécanisme de nouvelle tentative](diagrams/code_scraping_retry.png)

**Filtrage** — exemple concret CMF : annuel + daté du 31/12 + dans les 10-11 dernières années.

![Exemple de filtrage — cas du scraper CMF](diagrams/filtrage_exemple_cmf.png)

**Déduplication** — vérifie en base (société + source + année) avant d'enregistrer.

![Code réel de la déduplication et de l'enregistrement](diagrams/code_scraping_dedup.png)

**À savoir par source** :
- FTUSA : année lue dans le contenu du PDF, pas dans le nom du fichier
- BVMT : liste des sociétés cotées découverte dynamiquement
- CGA / FTUSA réglementaire : circuit séparé (veille), cache 1h
- Atlas Magazine / IlBoursa : BeautifulSoup en parallèle, alimentent les actualités

### Reconnaissance automatique des sociétés

- Problème : "Assurances Maghrebia Vie" → quel code interne ?
- Solution : score de ressemblance pondéré — un mot rare ("VIE") compte plus qu'un mot générique ("ASSURANCES")
- Bug corrigé : "El Amana Takaful" confondu avec "AMI" à cause du seul mot commun "EL"
