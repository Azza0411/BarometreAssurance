"""
Configuration de logging JSON Lines partagee par les orchestrateurs du
pipeline (pipelines/run_pipeline.py, extraction/kpi_extraction_pipeline.py) :
un seul fichier logs/pipeline.log (rotation quotidienne, 14 jours), un
evenement JSON par ligne, pour permettre un suivi/greppage uniforme de la
collecte et de l'extraction sans avoir a regarder uniquement la console.
"""

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")


def get_logger(name="pipeline"):
    """Renvoie un logger configure pour ecrire en JSON Lines dans
    logs/pipeline.log (+ console). Idempotent : n'ajoute les handlers
    qu'une seule fois par nom, meme si get_logger() est appele depuis
    plusieurs modules dans le meme processus (run_pipeline.py et
    kpi_extraction_pipeline.py utilisent tous deux le nom "pipeline")."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    os.makedirs(LOG_DIR, exist_ok=True)
    logger.setLevel(logging.INFO)
    file_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(LOG_DIR, "pipeline.log"), when="midnight", backupCount=14, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(console_handler)
    return logger


def log_json(logger, event, **fields):
    logger.info(json.dumps({"ts": datetime.now().isoformat(), "event": event, **fields}, ensure_ascii=False))
