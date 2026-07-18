"""
Paramètres de connexion MySQL, lus depuis les variables d'environnement
(avec des valeurs par défaut adaptées à une instance MySQL locale).

Variables reconnues : DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME.
"""

import os

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "MarketInsurance"),
}
