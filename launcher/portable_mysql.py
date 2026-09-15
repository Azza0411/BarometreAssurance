"""Base de données portable (zéro installation) pour le lanceur "un clic"
— voir docs/packaging_portable.md. Télécharge (une seule fois, la
première fois que la plateforme s'ouvre) la distribution ZIP officielle
de MariaDB pour Windows (aucun installeur, juste des binaires — voir
https://archive.mariadb.org), l'initialise avec un répertoire de données
LOCAL au projet, et démarre `mysqld.exe` sur un port DÉDIÉ (3307, jamais
3306) pour ne jamais entrer en conflit avec un éventuel MySQL déjà
installé sur la machine — le lanceur ignore volontairement tout MySQL
préexistant et gère toujours sa PROPRE instance, pour un comportement
identique sur n'importe quelle machine (le but même de "portable").

Aucun changement de code applicatif nécessaire : `config/db_config.py`
lit déjà DB_HOST/DB_PORT depuis l'environnement — `start_platform.py`
positionne juste ces deux variables avant de démarrer l'API.

Contrainte connue : le tout premier lancement nécessite une connexion
Internet (téléchargement du ZIP, ~90 Mo) — les lancements suivants sont
entièrement hors-ligne (le ZIP et les données restent en local, sous
`portable_runtime/`, jamais committé au dépôt — voir .gitignore)."""

import os
import subprocess
import sys
import time
import urllib.request
import zipfile

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_DIR = os.path.join(BASE_DIR, "portable_runtime")
MARIADB_DIR = os.path.join(RUNTIME_DIR, "mariadb")
DATA_DIR = os.path.join(RUNTIME_DIR, "mariadb_data")
ZIP_PATH = os.path.join(RUNTIME_DIR, "mariadb.zip")

# Version épinglée (comme tout le reste du projet — jamais "latest") :
# vérifiée disponible et fonctionnelle le 2026-09-15 (voir
# CAS_PARTICULIERS_TAKAFUL_SURPLUS.md pour la convention équivalente côté
# extraction). Changer cette URL si la version doit être mise à jour.
MARIADB_URL = "https://archive.mariadb.org/mariadb-11.4.4/winx64-packages/mariadb-11.4.4-winx64.zip"
MARIADB_ZIP_ROOT = "mariadb-11.4.4-winx64"  # nom du dossier racine DANS le zip

PORT = 3307
HOST = "127.0.0.1"


def _bin(name):
    return os.path.join(MARIADB_DIR, "bin", name)


def _is_port_open(port, host=HOST, timeout=0.5):
    import socket
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _download_and_extract():
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    print(f"  [MySQL portable] Téléchargement de MariaDB (~90 Mo, une seule fois)...")
    urllib.request.urlretrieve(MARIADB_URL, ZIP_PATH)
    print(f"  [MySQL portable] Extraction...")
    with zipfile.ZipFile(ZIP_PATH) as z:
        z.extractall(RUNTIME_DIR)
    extracted = os.path.join(RUNTIME_DIR, MARIADB_ZIP_ROOT)
    os.rename(extracted, MARIADB_DIR)
    os.remove(ZIP_PATH)


def _ensure_downloaded():
    if os.path.isfile(_bin("mysqld.exe")):
        return
    _download_and_extract()


def _ensure_initialized():
    if os.path.isdir(DATA_DIR) and os.listdir(DATA_DIR):
        return
    print("  [MySQL portable] Initialisation de la base (première fois)...")
    os.makedirs(DATA_DIR, exist_ok=True)
    subprocess.run(
        [_bin("mariadb-install-db.exe"), f"--datadir={DATA_DIR}"],
        check=True, capture_output=True,
    )


def start_portable_mysql(max_wait_seconds=30):
    """Télécharge/initialise si besoin, puis démarre `mysqld.exe` en
    arrière-plan sur (HOST, PORT). Ne fait rien si un mysqld portable
    tourne déjà sur ce port (relance du lanceur alors que la plateforme
    est déjà ouverte). Renvoie le Popen du process (None si déjà démarré
    par un lancement précédent) ; lève une exception si le démarrage
    échoue après `max_wait_seconds`."""
    if _is_port_open(PORT):
        print(f"  [MySQL portable] Déjà en cours d'exécution (port {PORT}).")
        return None

    _ensure_downloaded()
    _ensure_initialized()

    print(f"  [MySQL portable] Démarrage (port {PORT})...")
    log_path = os.path.join(RUNTIME_DIR, "mysqld_launcher.log")
    log_file = open(log_path, "a", encoding="utf-8")
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(
        [
            _bin("mysqld.exe"),
            f"--datadir={DATA_DIR}",
            f"--port={PORT}",
            "--bind-address=127.0.0.1",
            # --skip-grant-tables : cette instance est strictement locale
            # (bind 127.0.0.1 uniquement, jamais exposée au réseau) et
            # dédiée à cette seule application — pas besoin de gestion de
            # comptes/mots de passe, juste d'être joignable par l'API sans
            # friction sur n'importe quelle machine.
            "--skip-grant-tables",
            "--skip-networking=0",
        ],
        cwd=MARIADB_DIR, stdout=log_file, stderr=log_file, creationflags=creationflags,
    )

    deadline = time.monotonic() + max_wait_seconds
    while time.monotonic() < deadline:
        if _is_port_open(PORT):
            print(f"  [MySQL portable] Prêt (port {PORT}).")
            return proc
        if proc.poll() is not None:
            raise RuntimeError(
                f"mysqld.exe s'est arrêté immédiatement (code {proc.returncode}) — voir {log_path}"
            )
        time.sleep(0.5)
    raise RuntimeError(f"mysqld.exe ne répond pas après {max_wait_seconds}s — voir {log_path}")


if __name__ == "__main__":
    start_portable_mysql()
    print("MySQL portable démarré. Ctrl+C pour arrêter ce script (le process mysqld continue en arrière-plan).")
    sys.exit(0)
