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

## MySQL portable — construit et vérifié (2026-09-15)

`launcher/portable_mysql.py` : au premier lancement, télécharge la
distribution ZIP officielle MariaDB pour Windows (~90 Mo, aucun
installeur — https://archive.mariadb.org), l'initialise avec un
répertoire de données LOCAL au projet (`portable_runtime/`, jamais
committé), puis démarre `mysqld.exe` sur le port DÉDIÉ 3307 (jamais 3306,
pour ne jamais entrer en conflit avec un MySQL déjà installé sur la
machine — l'instance portable ignore volontairement tout MySQL
préexistant). AUCUN changement de code applicatif n'a été nécessaire :
`config/db_config.py` était déjà piloté par variables d'environnement.

**Vérifié en conditions réelles, de A à Z, sur ce poste** : suppression
de toute trace précédente → lancement → téléchargement automatique →
extraction → initialisation → démarrage de `mysqld.exe` → connexion
réussie de l'API → base de données VRAIMENT vide au départ (aucune trace
d'un run précédent) → **le thread d'auto-scraping au démarrage
(api/app.py::_start_first_run_scrape) s'est déclenché seul et a rempli la
base (0 → 38 documents en quelques minutes, pipeline toujours en cours
pour le reste) sans AUCUNE intervention manuelle** → page d'accueil
accessible et fonctionnelle pendant toute la durée de la collecte.

## Ce qu'il reste pour un "zéro dépendance" complet

Un seul chantier restant : **compiler en un seul exécutable
(PyInstaller)**, pour que l'utilisateur final n'ait même plus besoin de
Python installé. Complexité à anticiper : les binaires externes
(Tesseract, Ghostscript, MariaDB) ne sont PAS embarqués par PyInstaller
(qui ne bundle que les dépendances Python pures) — il faudra les livrer
comme fichiers additionnels à côté de l'exécutable généré (`--add-data`),
pas comme un `pip install`. Tesseract/Ghostscript ne bloquent pas la
plateforme (dégradation gracieuse pour les seules fonctionnalités qui en
dépendent — extraction Arabe OCR, camelot) ; MariaDB, en revanche, est
strictement nécessaire — mais son mécanisme de téléchargement/extraction
étant déjà un script Python autonome (`portable_mysql.py`), il continuera
de fonctionner identiquement une fois ce script lui-même compilé.

**Build Docker à valider** une fois Docker Desktop disponible (les
correctifs de dépendances requirements-api.txt/Dockerfile.api n'ont été
vérifiés que statiquement) — pertinent si un déploiement serveur est un
jour envisagé en parallèle du lanceur local, pas bloquant pour celui-ci.

## Vérifications restantes

- MySQL portable et auto-scraping au démarrage : **fait, voir section
  ci-dessus**.
- Tester `LancerPlateforme.bat` sur une machine SANS venv Python déjà
  préparé (actuellement testé uniquement via l'interpréteur du venv de
  développement — Python lui-même reste nécessaire jusqu'à la
  compilation PyInstaller).
- Une fois PyInstaller en place, tester le lancement sur une machine
  Windows "propre" (sans Python/Node/MySQL/Tesseract déjà présents) —
  SEUL test qui validera vraiment le "zéro dépendance" complet promis à
  l'utilisateur final.
