# Veille — Frontend & Backend

## Architecture

```
Frontend (React/Vite · port 5173)
  ├── VeilleActualites.jsx     →  GET  /api/actualites
  └── VeilleReglementaire.jsx  →  GET  /api/veille-reglementaire
                                   POST /api/veille-reglementaire/refresh
                                   GET  /api/pdf-proxy?url=<encoded>
Backend (Flask · port 8002)
  └── veille_api.py
       ├── /api/actualites
       ├── /api/veille-reglementaire
       ├── /api/veille-reglementaire/refresh
       └── /api/pdf-proxy
```

## Sources de données

| Source | URL | Contenu |
|--------|-----|---------|
| IlBoursa | `ilboursa.com/marches/cotation_<TICKER>` | Actualités par ticker boursier |
| Atlas Magazine | `atlas-mag.net/fr/news/tunisia` | Actualités assurance Tunisie |
| CGA id=33 | `cga.gov.tn/index.php?id=33` | Règlements & Décisions |
| CGA id=30 | `cga.gov.tn/index.php?id=30` | Publications & Circulaires |
| FTUSA textes | `ftusanet.org/cadre-institutionnel/les-textes-legislatifs...` | Textes législatifs |
| FTUSA code | `ftusanet.org/cadre-institutionnel/code-des-assurances/` | Code des assurances |

## Cache

Toutes les réponses sont mises en cache mémoire 1 heure (`_CACHE_TTL = 3600`).
`POST /api/veille-reglementaire/refresh` vide le cache réglementaire et force un re-scraping.

## Formats de données

**Actualité**
```json
{
  "src": "ILBOURSA",
  "titre": "...",
  "url": "https://...",
  "date": "dd/mm/yyyy",
  "categorie": "Innovation",
  "compagnie": "BNA Assurances",
  "resume": "...",
  "image": "https://...",
  "pdf_url": null
}
```

**Texte réglementaire**
```json
{
  "id": "abc123def456",
  "src": "CGA",
  "type": "Règlement",
  "titre": "...",
  "url": "https://...",
  "pdf_url": "https://...pdf",
  "date": "dd/mm/yyyy",
  "annee": 2023
}
```

## Démarrage

```bash
pip install flask flask-cors requests beautifulsoup4
python docs/veille/backend/veille_api.py
```

Le backend écoute sur `http://localhost:8002`.

```bash
cd frontend
npm install
npm run dev
```

Le frontend écoute sur `http://localhost:5173`.

## Structure des fichiers

```
docs/veille/
  backend/
    veille_api.py        Flask app — scraping + endpoints
  frontend/
    VeilleActualites.jsx    Page "Veille d'actualités"
    VeilleReglementaire.jsx Page "Veille réglementaire"
  README.md
```

## Logique de catégorisation (actualités)

Le backend attribue automatiquement une catégorie à chaque article via `_categorize(titre)` selon des mots-clés présents dans le titre :

| Catégorie | Mots-clés détectés |
|-----------|-------------------|
| Résultats financiers | résultat, chiffre, prime, bénéfice, bilan… |
| Gouvernance | gouvern, conseil, assemblée, nomination… |
| Partenariat | partenariat, accord, convention… |
| Digital | digital, numéri, application, plateforme… |
| Innovation | innov, borne, électrique, développement durable… |
| Réglementation | règlement, loi, décret, circulaire… |
| Actualité | (défaut) |

## Logique de détection du type réglementaire

`_detect_type(text)` inspecte le texte du titre pour détecter : Règlement, Décision, Circulaire, Avenant, Communiqué, Arrêté, Décret, Loi, Code.
