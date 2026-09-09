"""Signal de contrôle partagé pour un pipeline de collecte lancé depuis
l'interface web (page Gestion de données) — permet à l'utilisateur
d'ANNULER une collecte en cours sans tuer le process serveur Flask.

Module séparé (pas dans api/routes/gestion_donnees.py) : les fonctions du
pipeline (pipelines/run_pipeline.py, pipelines/cmf_pipeline.py,
extraction/kpi_extraction_pipeline.py) doivent pouvoir vérifier ce signal
sans jamais importer quoi que ce soit sous api/ (ça créerait un import
circulaire — api/routes importe déjà les pipelines, pas l'inverse).

Vérifié de façon COOPÉRATIVE aux points de contrôle naturels du pipeline
(entre deux sociétés, entre deux documents) — jamais une interruption
forcée : Python ne permet pas de tuer proprement un thread au milieu d'un
appel réseau/IO sans risquer un état PDF/DB à moitié écrit. Le pipeline
s'arrête donc au prochain point de contrôle, pas instantanément — en
pratique quelques secondes au plus (durée d'un document/société)."""

import threading

_cancel_event = threading.Event()


def request_cancel():
    _cancel_event.set()


def clear_cancel():
    _cancel_event.clear()


def is_cancel_requested():
    return _cancel_event.is_set()
