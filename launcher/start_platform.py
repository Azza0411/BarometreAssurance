"""Lanceur "un clic" de la plateforme — pièce centrale du packaging
portable (voir docs/packaging_portable.md pour le plan complet et l'état
d'avancement). Objectif : l'utilisateur double-clique un seul fichier
(LancerPlateforme.bat, qui appelle ce script), ne tape AUCUNE commande,
et se retrouve avec son navigateur ouvert sur la plateforme — les données
manquantes se (re)collectent d'elles-mêmes si besoin (voir
api/app.py::_start_first_run_scrape, déclenché automatiquement par le
process API lui-même dès qu'il démarre sur une base vide).

Ce script démarre, dans l'ordre :
  1. La base de données portable (launcher/portable_mysql.py) — sa PROPRE
     instance MariaDB, zéro installation, port dédié 3307 (jamais 3306,
     pour ne jamais entrer en conflit avec un MySQL déjà présent sur la
     machine). Télécharge/initialise au premier lancement uniquement.
  2. L'API Flask (api/app.py, port 8002), pointée vers cette base via
     DB_HOST/DB_PORT — sert AUSSI le frontend buildé (frontend/dist/, voir
     api/app.py) : un seul processus pour l'API et l'interface, pas besoin
     de Node/Nginx à l'exécution.
  3. Le chatbot IA (chatbot_portable/app.py, port 5001) — optionnel,
     autonome (SQLite, pas de dépendance MySQL) : une erreur ici ne doit
     jamais empêcher le reste de la plateforme de démarrer.
  4. Ouvre le navigateur par défaut sur http://localhost:8002 dès que
     l'API répond (polling court, quelques secondes max en pratique).

Suppose `frontend/dist/` déjà buildé (`npm run build`, une fois, au
moment de préparer le paquet distribuable — PAS à chaque lancement).
Reste (voir docs/packaging_portable.md) : compilation PyInstaller pour
que Python lui-même n'ait plus besoin d'être installé sur la machine
cible — ce script n'aura pas à changer, seul son mode d'exécution
(interprété -> exécutable) change."""

import os
import subprocess
import sys
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE_DIR)  # cohérent avec launcher/main.py — voir portable_mysql.BASE_DIR
API_PORT = 8002
CHATBOT_PORT = 5001
API_URL = f"http://localhost:{API_PORT}"


def _is_port_open(port, host="127.0.0.1", timeout=0.5):
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _start_background(script_relpath, cwd=None, extra_env=None):
    """Lance `script_relpath` (chemin relatif à BASE_DIR) en arrière-plan,
    avec le même interpréteur Python que ce lanceur (fonctionne aussi bien
    en venv qu'une fois ce script lui-même compilé par PyInstaller — voir
    docs/packaging_portable.md). Sortie redirigée vers un fichier de log
    (pas de console qui s'ouvre pour l'utilisateur final)."""
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_name = os.path.basename(script_relpath).replace(".py", ".log")
    log_path = os.path.join(log_dir, log_name)
    env = {**os.environ, **(extra_env or {})}
    log_file = open(log_path, "a", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, script_relpath)],
        cwd=cwd or BASE_DIR, env=env, stdout=log_file, stderr=log_file,
        creationflags=creationflags,
    )


def _wait_for_port(port, max_seconds=60):
    deadline = time.monotonic() + max_seconds
    while time.monotonic() < deadline:
        if _is_port_open(port):
            return True
        time.sleep(0.5)
    return False


def main():
    print("FS Market Intelligence — démarrage de la plateforme...")

    # Base de données portable — voir launcher/portable_mysql.py. Gère sa
    # PROPRE instance MariaDB (port dédié 3307, jamais 3306) plutôt que de
    # dépendre d'un MySQL déjà installé : comportement identique sur
    # n'importe quelle machine, aucune installation manuelle nécessaire.
    import portable_mysql  # module sœur (même dossier launcher/) — voir sys.path[0]
    try:
        portable_mysql.start_portable_mysql()
        db_env = {"DB_HOST": portable_mysql.HOST, "DB_PORT": str(portable_mysql.PORT)}
    except Exception as exc:
        print(f"  [ERREUR] Base de données portable indisponible : {exc}")
        return 1

    if not _is_port_open(API_PORT):
        print(f"  Démarrage de l'API (port {API_PORT})...")
        _start_background("api/app.py", extra_env=db_env)
    else:
        print(f"  API déjà en cours d'exécution (port {API_PORT}).")

    if not _is_port_open(CHATBOT_PORT):
        chatbot_script = os.path.join("chatbot_portable", "app.py")
        if os.path.isfile(os.path.join(BASE_DIR, chatbot_script)):
            print(f"  Démarrage du chatbot IA (port {CHATBOT_PORT})...")
            try:
                _start_background(chatbot_script, cwd=os.path.join(BASE_DIR, "chatbot_portable"))
            except Exception as exc:
                # Le chatbot est une fonctionnalité annexe : son échec au
                # démarrage ne doit jamais empêcher le reste de s'ouvrir.
                print(f"  [avertissement] Chatbot IA non démarré : {exc}")
    else:
        print(f"  Chatbot IA déjà en cours d'exécution (port {CHATBOT_PORT}).")

    print("  Attente de la disponibilité de l'API...")
    if not _wait_for_port(API_PORT, max_seconds=60):
        print(
            f"  [ERREUR] L'API ne répond toujours pas après 60s sur le port {API_PORT}. "
            f"Voir logs/app.log pour le détail (base de données inaccessible ? port déjà utilisé "
            f"par autre chose ?)."
        )
        return 1

    print(f"  Ouverture du navigateur sur {API_URL} ...")
    webbrowser.open(API_URL)
    print(
        "\nLa plateforme est lancée. Si aucune donnée ne s'affiche encore, la collecte "
        "automatique est probablement en cours en arrière-plan (premier lancement) — "
        "actualisez la page dans quelques minutes."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
