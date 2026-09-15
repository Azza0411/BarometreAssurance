"""Point d'entrée UNIQUE pour l'exécutable compilé (PyInstaller) — voir
docs/packaging_portable.md. Contrairement à `start_platform.py` (qui
lance l'API et le chatbot comme des PROCESS PYTHON séparés via
`sys.executable`), tout tourne ici DANS CE MÊME PROCESSUS, en threads :
un exécutable PyInstaller "onedir" n'a plus de `python.exe` séparé à
appeler — `sys.executable` y désigne l'exécutable lui-même, pas un
interpréteur générique.

Composants démarrés, dans l'ordre :
  1. Base de données portable (launcher/portable_mysql.py) — process
     externe (mysqld.exe), inchangé par rapport à start_platform.py.
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


def main():
    print("FS Market Intelligence — démarrage de la plateforme...")
    print(f"  Dossier de l'application : {BASE_DIR}")

    sys.path.insert(0, os.path.join(BASE_DIR, "launcher"))
    import portable_mysql
    try:
        portable_mysql.start_portable_mysql()
        os.environ["DB_HOST"] = portable_mysql.HOST
        os.environ["DB_PORT"] = str(portable_mysql.PORT)
    except Exception as exc:
        print(f"  [ERREUR] Base de données portable indisponible : {exc}")
        input("Appuyez sur Entrée pour fermer...")
        return 1

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
