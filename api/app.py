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
  api/services/kpi_builder.py  → calcul RC/RSP/RF par compagnie
  api/services/quality.py      → detection d'anomalies
  api/utils/formatters.py      → round1, growth_pct, required_year_arg, kpis_by_year
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify
from flask_cors import CORS

from api.routes import apercu_marche, comparative, vue_assurance, enquete, veille, qualite, export, notifications
from database.repository import ensure_database, get_connection, init_schema

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


@app.errorhandler(ValueError)
def _handle_value_error(exc):
    return jsonify({"error": str(exc)}), 400


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
