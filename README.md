# Baromètre Assurance — FS Market Intelligence

Plateforme analytique du marché des assurances en Tunisie, développée par EY.

## Architecture

```
BarometreAssurance/
├── api/              # Backend Flask (Python) — API REST
├── frontend/         # Frontend React + Vite
│   └── src/
│       ├── pages/    # Dashboards (ApercuMarche, AnalyseComparative, ...)
│       ├── components/ # Composants partagés (Chatbot, Sidebar, ...)
│       └── utils/    # Utilitaires (chartTheme, logos, ...)
├── config/           # Configuration DB et registres
├── database/         # Connecteur MySQL
├── extraction/       # Extracteurs KPI par source (CMF, FTUSA, CGA, ...)
├── scraping/         # Scrapers web (CMF, BVMT, ilboursa, ...)
├── analysis/         # Moteur de calcul KPI
├── data/
│   ├── kpis/         # Données extraites (CSV)
│   └── Survey CX_...xlsx  # Enquête marché
└── pipelines/        # Pipelines d'ingestion
```

## Stack technique

| Couche | Technologie |
|--------|------------|
| Frontend | React 18, Vite, ApexCharts, React Router |
| Backend | Python 3.11, Flask, MySQL |
| Base de données | MySQL 8 (`MarketInsurance`) |
| Design | EY Design System (Barlow, #FFE600, #2E2E38) |

## Lancement

### Backend
```bash
cd api
pip install flask flask-cors mysql-connector-python
python app.py
# → http://localhost:8002
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

## Configuration base de données

Variables d'environnement (copier `.env.example` → `.env`) :
```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=MarketInsurance
```

## Chatbot IA

Pour activer les réponses avancées du chatbot, ajouter dans `frontend/.env` :
```
VITE_ANTHROPIC_KEY=votre_clé_claude_api
```

## Périmètre des données

- **Sources** : CMF, FTUSA, CGA, BVMT, INS
- **Période** : 2014 – 2024
- **Compagnies** : 24 assureurs actifs sur le marché tunisien

## Pages de la plateforme

| Route | Description |
|-------|-------------|
| `/apercu-marche` | Vue macro — KPIs pays, évolution primes, structure portefeuille |
| `/analyse-comparative` | Benchmarking ratios techniques entre compagnies |
| `/fiches` | Fiches détaillées par compagnie |
| `/enquete-marche` | Analyse de l'enquête CX (Grand public & Entreprises) |
| `/actualites-seminaires` | Veille presse et événements sectoriels |
| `/veille-reglementaire` | Textes CGA, lois et circulaires (1980–2024) |
