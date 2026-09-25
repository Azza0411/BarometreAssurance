"""Point d'entrée UNIQUE pour l'exécutable compilé (PyInstaller) — voir
docs/packaging_portable.md. Contrairement à `start_platform.py` (qui
lance l'API et le chatbot comme des PROCESS PYTHON séparés via
`sys.executable`), tout tourne ici DANS CE MÊME PROCESSUS, en threads :
un exécutable PyInstaller "onedir" n'a plus de `python.exe` séparé à
appeler — `sys.executable` y désigne l'exécutable lui-même, pas un
interpréteur générique.

Composants démarrés, dans l'ordre :
  1. Vérification qu'un MySQL est déjà accessible (127.0.0.1:3306 par
     défaut, voir config/db_config.py) — décision explicite du
     2026-09-16 : ne plus télécharger/gérer de MariaDB portable
     (l'ancien launcher/portable_mysql.py, retiré), au profit d'une
     dépendance directe à un MySQL déjà installé sur la machine (ex:
     XAMPP) et démarré PAR L'UTILISATEUR avant de lancer cet exécutable.
     Message d'erreur clair si injoignable, plutôt qu'un téléchargement
     silencieux ou un plantage.
  2. L'API Flask (api/app.py) — importée puis servie via werkzeug
     `make_server` dans un thread (pas `app.run()`, qui bloquerait).
  3. Le chatbot IA (chatbot_portable/app.py) — même principe, best-effort
     (une erreur ici ne bloque jamais le reste, voir docstring plus bas).
  4. Navigateur ouvert sur http://localhost:8002.

`_resolve_base_dir()` : sous PyInstaller (`sys.frozen`), les chemins
relatifs bruts semés dans le code (`os.path.join("data", "kpis")` par
ex.) ne doivent plus être résolus depuis un `__file__` qui pointerait
dans le dossier temporaire d'extraction interne à PyInstaller — un
`os.chdir()` vers le dossier RÉEL de l'exécutable, fait UNE FOIS ici au
tout début, avant tout autre import, corrige ça pour tout le programme
sans devoir auditer chaque usage de chemin relatif du code existant."""

import os
import re
import sys
import threading
import time
import webbrowser


def _resolve_base_dir():
    if getattr(sys, "frozen", False):
        # PyInstaller onedir : le dossier contenant l'exécutable lui-même
        # (PAS sys._MEIPASS, qui est le dossier temporaire de RESSOURCES
        # embarquées en onefile — non utilisé ici, voir --onedir).
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = _resolve_base_dir()
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

API_PORT = 8002
CHATBOT_PORT = 5001


def _run_flask_app_in_thread(app, port, name):
    """Sert `app` (objet Flask) via werkzeug, dans un thread démon —
    `app.run()` bloquerait le thread appelant indéfiniment, ce qui ne
    marche que pour LE DERNIER service démarré ; `make_server` donne un
    objet qu'on peut lancer dans un thread pendant qu'on continue à faire
    autre chose (démarrer le service suivant, ouvrir le navigateur...)."""
    from werkzeug.serving import make_server

    server = make_server("0.0.0.0", port, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name=name)
    thread.start()
    return thread


def _is_port_open(port, host="127.0.0.1", timeout=0.5):
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wait_for_mysql(host, port, max_wait_seconds=30):
    """Attend qu'un MySQL réponde sur host:port — un utilisateur qui vient
    juste de cliquer sur "Démarrer" dans le panneau XAMPP a besoin de
    quelques secondes avant que le service soit réellement prêt ; on
    retente poliment plutôt que d'échouer sur la première tentative."""
    deadline = time.monotonic() + max_wait_seconds
    while time.monotonic() < deadline:
        if _is_port_open(port, host=host, timeout=1.0):
            return True
        time.sleep(1)
    return False


def _auto_seed():
    """Si la base MarketInsurance est vide et qu'un fichier data/seed/initial_data.sql
    est présent (distribué avec l'exécutable), l'importe automatiquement — les pages
    Aperçu marché, Profil pays, etc. sont ainsi disponibles dès le premier lancement,
    sans attendre une collecte complète (~30-60 min)."""
    seed_path = os.path.join(BASE_DIR, "data", "seed", "initial_data.sql")
    if not os.path.exists(seed_path):
        return

    try:
        import pymysql
        from config.db_config import DB_CONFIG
        from database.repository import ensure_database, init_schema

        ensure_database()
        conn = pymysql.connect(**DB_CONFIG)
        try:
            init_schema(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM kpi_values")
                count = cur.fetchone()[0]
            if count > 0:
                print(f"  Base déjà peuplée ({count} valeurs KPI) — import initial ignoré.")
                return

            print("  Base vide — import des données initiales...")
            # utf-8-sig absorbe le BOM éventuel (Out-File PowerShell)
            with open(seed_path, "r", encoding="utf-8-sig") as f:
                sql = re.sub(r"--[^\n]*", "", f.read())

            # Le dump utilise des INSERTs groupés (multi-lignes) : 4 requêtes
            # seulement pour 900+ lignes → import en < 5 secondes en transaction
            # unique (autocommit=False, un seul commit à la fin).
            conn.autocommit(False)
            with conn.cursor() as cur:
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        try:
                            cur.execute(stmt)
                        except Exception:
                            pass
            conn.commit()
            print("  Données initiales importées — pages disponibles immédiatement.")
        finally:
            conn.close()
    except Exception as exc:
        print(f"  [avertissement] Import initial ignoré : {exc}")


def main():
    print("FS Market Intelligence — démarrage de la plateforme...")
    print(f"  Dossier de l'application : {BASE_DIR}")

    # Dépendance directe à un MySQL déjà installé (ex: XAMPP) — décision
    # explicite du 2026-09-16 (voir docstring en tête de fichier) : plus
    # de MariaDB portable téléchargée automatiquement. L'utilisateur DOIT
    # démarrer MySQL lui-même avant de lancer cet exécutable.
    db_host = os.environ.get("DB_HOST", "127.0.0.1")
    db_port = int(os.environ.get("DB_PORT", "3306"))
    print(f"  Vérification de MySQL ({db_host}:{db_port})...")
    if not _wait_for_mysql(db_host, db_port):
        print(
            f"\n  [ERREUR] MySQL n'est pas accessible sur {db_host}:{db_port}.\n"
            "  Démarrez MySQL (par exemple via le panneau de contrôle XAMPP,\n"
            "  bouton \"Start\" sur la ligne MySQL) puis relancez cette application.\n"
        )
        input("Appuyez sur Entrée pour fermer...")
        return 1
    print("  MySQL accessible.")
    _auto_seed()

    if not _is_port_open(API_PORT):
        print(f"  Démarrage de l'API (port {API_PORT})...")
        import api.app as api_app
        _run_flask_app_in_thread(api_app.app, API_PORT, "api")
    else:
        print(f"  API déjà en cours d'exécution (port {API_PORT}).")

    if not _is_port_open(CHATBOT_PORT):
        # Best-effort : le chatbot a ses propres dépendances lourdes
        # (prophet, xgboost — voir chatbot_portable/requirements.txt) pas
        # encore validées dans le paquet compilé (voir
        # docs/packaging_portable.md) ; un échec ici ne doit jamais
        # empêcher le reste de la plateforme de s'ouvrir.
        try:
            print(f"  Démarrage du chatbot IA (port {CHATBOT_PORT})...")
            # Import qualifié (chatbot_portable.app), PAS "import app" via
            # bidouille de sys.path : ce dernier nom est ambigu (pourrait
            # entrer en collision avec un autre module "app") et surtout
            # invisible à l'analyse statique de PyInstaller au moment de
            # la compilation - seul un import normal est détecté et
            # embarqué. chatbot_portable/app.py résout déjà ses propres
            # chemins via __file__ (pas le répertoire courant), donc
            # aucun os.chdir() n'est nécessaire ici.
            import chatbot_portable.app as chatbot_app
            _run_flask_app_in_thread(chatbot_app.app, CHATBOT_PORT, "chatbot")
        except Exception as exc:
            print(f"  [avertissement] Chatbot IA non démarré : {exc}")
    else:
        print(f"  Chatbot IA déjà en cours d'exécution (port {CHATBOT_PORT}).")

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline and not _is_port_open(API_PORT):
        time.sleep(0.5)

    url = f"http://localhost:{API_PORT}"
    print(f"  Ouverture du navigateur sur {url} ...")
    webbrowser.open(url)
    print(
        "\nLa plateforme est lancée. Cette fenêtre doit rester ouverte tant que vous "
        "utilisez la plateforme — la fermer arrête tout (API, chatbot, base de données)."
    )

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Arrêt demandé.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
