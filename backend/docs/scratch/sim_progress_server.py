"""Serveur de SIMULATION (test visuel du bandeau de collecte) : expose la vraie
route /api/gestion-donnees/statut-collecte et pilote le vrai module
pipelines.progress à travers un run complet accéléré. N'écrit rien dans la
vraie base ni dans logs/phase_durations.json."""
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from flask import Flask
from flask_cors import CORS
import pipelines.progress as p
p._DURATIONS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sim_phase_durations.json")
from backend.routes import gestion_donnees as g

app = Flask(__name__)
CORS(app)
app.register_blueprint(g.bp)
SOURCE = sys.argv[1] if len(sys.argv) > 1 else "premier_lancement"
SLOW = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8012
_sleep = time.sleep
time.sleep = lambda x: _sleep(x * SLOW)


def sim():
    time.sleep(6)
    with g._collecte_lock:
        g._collecte_state.update(en_cours=True, demarree_le="2026-09-23T22:00:00", annulation_demandee=False, source=SOURCE)
    p.set_plan(p.FULL_PLAN, kind="full")
    p.set_phase("scraping"); p.reset_progress(24, "portail CMF")
    for i in range(24):
        time.sleep(1.4); p.bump_progress(["STAR", "COMAR", "GAT", "BIAT", "BH", "AMI"][i % 6])
    p.enter_phase_if_planned("rattrapage_pdf")  # comme cmf_pipeline.main() : run() gère ensuite ses sous-étapes
    p.drop_from_plan("rattrapage_pdf")          # rien à rattraper -> passe seule à extraction_kpi
    p.enter_phase_if_planned("extraction_kpi")
    p.reset_progress(60)
    for i in range(60):
        time.sleep(0.6); p.set_progress(i + 1, detail=f"{['STAR','COMAR','GAT','BIAT'][i % 4]} {2020 + i % 6}")
    p.set_phase("sources_prioritaires"); p.reset_progress(4)
    for n in ("FTUSA", "CGA", "INS", "BVMT"):
        time.sleep(3); p.bump_progress(f"{n} terminé")
    p.mark_quick_ready()
    p.set_phase("grilles"); p.reset_progress(7)
    for i in range(7):
        time.sleep(3); p.bump_progress(f"grille {i + 1} terminée")
    p.set_phase("qualite"); time.sleep(6)
    p.set_phase("veille"); time.sleep(6)
    p.clear_phase()
    with g._collecte_lock:
        g._collecte_state["en_cours"] = False


threading.Thread(target=sim, daemon=True).start()
app.run(port=PORT, debug=False, use_reloader=False)
