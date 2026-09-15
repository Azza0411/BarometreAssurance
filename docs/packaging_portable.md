# Packaging portable + auto-scraping — plan et état d'avancement

Objectif exprimé par l'utilisateur (2026-09-15) : l'utilisateur final doit
pouvoir ouvrir la plateforme **sans dépendance à installer et sans
commande à taper** — double-clic sur un seul fichier, et si la base de
données est vide, la collecte se relance d'elle-même. Décision actée :
un **lanceur local** (tout tourne sur la machine de l'utilisateur, aucune
donnée ne sort) plutôt qu'un hébergement cloud avec une URL fixe.

## Ce qui existait déjà (avant ce chantier, vérifié en l'inspectant)

- **Packaging Docker complet** : `docker-compose.yml` (MySQL + API +
  chatbot + frontend/Nginx), `Dockerfile.api`, `frontend/Dockerfile`
  (multi-stage, build Vite → Nginx), `chatbot_portable/Dockerfile`
  (SQLite, autonome). Fonctionnel pour un déploiement "un technicien lance
  `docker compose up`" — mais ça reste une commande à taper et nécessite
  Docker installé, donc ne répond PAS au besoin "zéro commande, zéro
  dépendance" exprimé ici.
- **Auto-scraping planifié** : `pipelines/run_pipeline.py` (orchestrateur
  complet — CMF/FTUSA/CGA/INS/BVMT, retry+backoff, isolation par source,
  logs JSON Lines, rapport HTML, alerte Slack), `run_pipeline.bat`/`.sh`
  (enregistrement Task Scheduler/cron documenté en tête de fichier). Très
  mature, mais c'est une tâche PLANIFIÉE (hebdomadaire) — pas déclenchée
  par l'ouverture de la plateforme elle-même.

## Gaps trouvés et corrigés (2026-09-15)

1. **Aucun code ne persistait les PDF CMF localement.** Les pipelines
   "grille complète" (Bilan, Annexe 12/13, les 5 pipelines Takaful) lisent
   le PDF depuis `api.services.data_management.local_pdf_path` plutôt que
   de le retélécharger — mais RIEN ne l'écrivait jamais là automatiquement
   (seuls FTUSA/CGA, sources sectorielles, avaient leur propre
   `_save_sectoral_pdf`). Un document CMF tout juste synchronisé restait
   donc invisible pour ces pipelines jusqu'à une intervention manuelle.
   **Corrigé** : `extraction/kpi_extraction_pipeline.py::_save_cmf_pdf_local`
   — écrit sur disque le PDF déjà téléchargé pour l'extraction KPI narrow
   (zéro coût réseau supplémentaire), sans jamais écraser un fichier déjà
   présent.
2. **Les pipelines grille complète n'étaient jamais rejoués
   automatiquement.** Ajoutés à `pipelines/run_pipeline.py::SOURCES`
   (6 nouvelles entrées, juste après "CMF", même schéma retry/isolation
   que FTUSA/CGA/INS/BVMT) : Bilan, Annexe 12, Annexe 13, Takaful Surplus,
   Takaful Résultat entreprise, Takaful Ventilation.
3. **Dépendances manquantes pour le packaging** : `requirements-api.txt`
   ne listait ni `rapidfuzz` ni `pytesseract` (ajoutés aujourd'hui pour
   l'extraction Arabe AL_AMANAH_TAKAFUL) ; `Dockerfile.api` n'installait
   ni `tesseract-ocr` (binaire requis par pytesseract) ni `ghostscript`
   (requis par camelot-py flavor='stream', gap préexistant). **Corrigés**
   dans les deux fichiers. Non vérifié par un build Docker réel : Docker
   Desktop n'était pas démarré sur cette machine (voir section
   "Vérifications restantes").

## Le lanceur local — construit et testé aujourd'hui

**Principe** : un seul processus Flask (`api/app.py`) sert À LA FOIS
l'API et le frontend buildé (`frontend/dist/`, produit une fois par
`npm run build`) — plus besoin de Node/Nginx à l'exécution. Un deuxième
processus optionnel (`chatbot_portable/app.py`, déjà autonome/SQLite) est
démarré à côté. `LancerPlateforme.bat` → `launcher/start_platform.py` :
démarre les deux processus s'ils ne tournent pas déjà, attend que l'API
réponde, ouvre le navigateur par défaut sur `http://localhost:8002`.

**Auto-scraping au premier lancement** : `api/app.py` vérifie au démarrage
si la base de données est vide (aucun document) — si oui, lance
`pipelines/run_pipeline.py::main()` dans un thread de fond (même principe
déjà utilisé pour la veille actualités/réglementation, voir
`_start_veille_watcher`). La plateforme reste utilisable pendant ce
temps (pages vides jusqu'à l'arrivée des premières données) plutôt que de
retarder l'ouverture du navigateur de plusieurs dizaines de minutes.

**Vérifié en conditions réelles** (ce poste, aujourd'hui) : double appel
de `LancerPlateforme.bat`-équivalent → API + chatbot démarrés, navigateur
ouvert sur `http://localhost:8002`, page d'accueil ET routes profondes
(`/enquete-marche`) fonctionnelles, widget chatbot connecté et
répondant — tout via UN SEUL point d'entrée.

## Ce qu'il reste à faire pour un "zéro dépendance" complet

Aujourd'hui, le lanceur suppose encore que Python, une base MySQL
joignable, et un build frontend existent déjà sur la machine — ce qui
convient pour un poste de développement, pas encore pour un utilisateur
final sans rien d'installé. Deux chantiers restants, dans l'ordre de
priorité :

1. **MySQL portable (zéro installation)** — remplacer la dépendance à un
   MySQL déjà installé par une instance MariaDB "zip" (distribution
   officielle sans installeur, `mysqld.exe` lancé directement avec un
   `--datadir` local bundlé à côté de l'application, sur un port dédié
   pour ne jamais entrer en conflit avec un MySQL déjà présent). AUCUN
   changement de code applicatif nécessaire : `config/db_config.py` est
   déjà piloté par variables d'environnement (`DB_HOST`/`DB_PORT`) — seul
   `launcher/start_platform.py` doit apprendre à démarrer/initialiser ce
   `mysqld.exe` avant l'API, et positionner ces variables en conséquence.
2. **Compilation en un seul exécutable (PyInstaller)** — pour que
   l'utilisateur final n'ait ni Python ni pip à installer. Complexité
   spécifique à anticiper : les binaires externes (Tesseract, Ghostscript,
   le futur `mysqld.exe` portable) ne sont PAS embarqués par PyInstaller
   (qui ne bundle que les dépendances Python) — il faudra les livrer comme
   fichiers additionnels à côté de l'exécutable généré (`--add-data`), pas
   comme un simple `pip install`.
3. **Build Docker à valider** une fois Docker Desktop disponible (les
   correctifs de dépendances ci-dessus n'ont été vérifiés que
   statiquement) — pertinent si un déploiement serveur est un jour
   envisagé en parallèle du lanceur local, pas bloquant pour celui-ci.

## Vérifications restantes

- Tester `LancerPlateforme.bat` sur une machine SANS venv déjà préparé
  (actuellement testé uniquement via l'interpréteur du venv de
  développement).
- Construire réellement la brique MySQL portable (téléchargement du zip
  MariaDB, script d'initialisation, test de démarrage à froid).
- Une fois PyInstaller en place, tester le lancement sur une machine
  Windows "propre" (sans Python/Node/MySQL/Tesseract déjà présents) —
  seul test qui validera vraiment le "zéro dépendance".
