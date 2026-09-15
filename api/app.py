"""Point d'entrée Flask — enregistre tous les blueprints par responsabilité.

Structure :
  api/routes/apercu_marche.py  → /api/apercu-marche/*
  api/routes/comparative.py    → /api/analyse-comparative, /api/classement-compagnies
  api/routes/vue_assurance.py  → /api/vue-assurance/*
  api/routes/enquete.py        → /api/enquete-marche/*
  api/routes/veille.py         → /api/actualites, /api/veille-reglementaire*, /api/pdf-proxy
  api/routes/qualite.py        → /api/rapport-qualite (NEW)
  api/routes/export.py         → /api/export/* (PDF, Excel)
  api/routes/notifications.py  → /api/notifications/* (cloche in-app)
  api/routes/gestion_donnees.py → /api/gestion-donnees/* (collecte, liste PDF, export flexible)
  api/services/kpi_builder.py  → calcul RC/RSP/RF par compagnie
  api/services/quality.py      → detection d'anomalies
  api/utils/formatters.py      → round1, growth_pct, required_year_arg, kpis_by_year
"""

import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from api.routes import apercu_marche, comparative, vue_assurance, enquete, veille, qualite, export, notifications, gestion_donnees
from database.repository import ensure_database, get_connection, init_schema, list_all_documents

# Applique tout schema.sql/migration en attente au démarrage — sans ça, une
# table ajoutée par une session d'extraction (ex: anomalies_detectees,
# ajoutée juillet 2026) n'existe jamais pour ce process tant qu'il n'est pas
# explicitement migré à la main. Idempotent (CREATE TABLE IF NOT EXISTS +
# ALTER conditionnés sur SHOW INDEX/information_schema) : sans risque même
# appelé deux fois par le rechargeur Flask en mode debug.
ensure_database()
_startup_conn = get_connection()
init_schema(_startup_conn)
_startup_conn.close()

app = Flask(__name__)
CORS(app)

app.register_blueprint(apercu_marche.bp)
app.register_blueprint(comparative.bp)
app.register_blueprint(vue_assurance.bp)
app.register_blueprint(enquete.bp)
app.register_blueprint(veille.bp)
app.register_blueprint(qualite.bp)
app.register_blueprint(export.bp)
app.register_blueprint(notifications.bp)
app.register_blueprint(gestion_donnees.bp)


@app.errorhandler(ValueError)
def _handle_value_error(exc):
    return jsonify({"error": str(exc)}), 400


# ── Frontend statique (lanceur portable) ────────────────────────────────────
# En développement, le frontend tourne sur son propre serveur Vite (port
# 5173, npm run dev) — cette route ne s'active QUE si `frontend/dist/`
# existe (produit par `npm run build`), pour ne jamais gêner ce workflow.
# Sert la SPA directement depuis ce même process Flask (un seul programme à
# lancer, pas de Node/Nginx nécessaire à l'exécution) — pièce centrale du
# lanceur portable "un clic" : voir docs/packaging_portable.md.
_FRONTEND_DIST = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")

if os.path.isdir(_FRONTEND_DIST):
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def _serve_frontend(path):
        full_path = os.path.join(_FRONTEND_DIST, path)
        if path and os.path.isfile(full_path):
            return send_from_directory(_FRONTEND_DIST, path)
        # Route inconnue (ex: /apercu-marche, une route React Router) : on
        # retombe sur index.html, exactement comme nginx.conf `try_files
        # ... /index.html` — la SPA se charge et résout elle-même la route
        # côté client.
        return send_from_directory(_FRONTEND_DIST, "index.html")


# ── Veille (notifications actualités/réglementation) en tâche de fond ──────
# La tâche planifiée Windows (schtasks, pipeline complet hebdomadaire) reste
# en place pour la collecte CMF, mais s'est révélée peu fiable pour CE
# symptôme précis : constaté 2026-08-22 (retour utilisateur - des actualités
# publiées le jour même ne généraient aucune notification) qu'elle n'avait
# JAMAIS tourné une seule fois depuis son enregistrement (mode "Interactive
# uniquement", nécessite une session utilisateur active pile au moment
# prévu - voir docs/pfe_phase_documentation.md, limite déjà documentée mais
# dont l'impact réel n'avait pas été mesuré). Solution robuste : un thread
# de fond DANS le process Flask lui-même (donc actif dès que la plateforme
# tourne, sans dépendre d'un déclencheur OS externe fragile), qui vérifie
# les nouveautés au démarrage puis toutes les 30 minutes. Cache 1h déjà en
# place côté scraping (veille.py::_CACHE_TTL) → pas de sur-sollicitation
# réseau même à cette fréquence.
_VEILLE_CHECK_INTERVAL_SECONDS = 30 * 60


def _veille_watcher_loop():
    import time
    from pipelines.run_pipeline import check_and_notify_veille
    while True:
        try:
            check_and_notify_veille()
        except Exception as exc:
            print(f"[veille_watcher] erreur ignorée : {exc}")
        time.sleep(_VEILLE_CHECK_INTERVAL_SECONDS)


def _start_veille_watcher():
    threading.Thread(target=_veille_watcher_loop, daemon=True).start()


_start_veille_watcher()


# ── Auto-scraping au premier lancement (lanceur portable) ──────────────────
# Pièce centrale du lanceur "un clic, zéro commande" (voir
# docs/packaging_portable.md) : un utilisateur qui ouvre la plateforme sur
# une base de données toute neuve (aucun document CMF encore synchronisé)
# ne doit RIEN avoir à taper pour déclencher la collecte — elle démarre
# d'elle-même, en tâche de fond, dès que ce process Flask tourne. Ne se
# déclenche QUE si la base est réellement vide (pas à chaque redémarrage :
# un utilisateur qui relance l'appli après une collecte déjà réussie ne
# doit pas en relancer une autre à son insu — voir /gestion-donnees pour un
# rafraîchissement manuel explicite). Tourne en thread non-bloquant : la
# plateforme reste utilisable (avec des pages vides jusqu'à ce que les
# premières données arrivent) plutôt que de retarder le démarrage de
# plusieurs dizaines de minutes.
def _database_is_empty():
    conn = get_connection()
    try:
        return len(list_all_documents(conn)) == 0
    finally:
        conn.close()


def _first_run_scrape_loop():
    try:
        if not _database_is_empty():
            return
        print("[premier lancement] Base de données vide — démarrage automatique de la collecte...")
        # `ensure_pipeline_running` (pas un appel direct à
        # pipelines.run_pipeline.main) : partage le MÊME état que la
        # collecte déclenchée à la main depuis "Gestion de données", pour
        # que /api/gestion-donnees/statut-collecte (et le bandeau global
        # qui s'y abonne, voir CollecteBanner.jsx) reflète aussi CETTE
        # collecte automatique — sinon rien n'indiquait à l'utilisateur
        # qu'une collecte tournait après un premier lancement sur base
        # vide (retour utilisateur direct, 2026-09-15).
        from api.routes.gestion_donnees import ensure_pipeline_running
        ensure_pipeline_running(source="premier_lancement")
    except Exception as exc:
        print(f"[premier lancement] Échec de la collecte automatique : {exc}")


def _start_first_run_scrape():
    threading.Thread(target=_first_run_scrape_loop, daemon=True).start()


_start_first_run_scrape()


if __name__ == "__main__":
    # use_reloader=False : le rechargeur automatique de Werkzeug (watchdog)
    # respawn un processus enfant qui, sur certaines machines Windows,
    # echoue la connexion MySQL au redemarrage ("Access denied ... using
    # password: YES") alors que le processus initial se connecte sans
    # probleme (le mot de passe local est vide) - cause exacte non
    # identifiee (probablement liee a l'heritage des handles du processus
    # parent sous Windows), mais 100% reproductible. debug=True est conserve
    # (pages d'erreur Flask detaillees), seul le rechargement auto est
    # desactive : relancer manuellement apres une modification du code.
    app.run(port=8002, debug=True, use_reloader=False)
