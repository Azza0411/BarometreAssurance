"""
Pipeline complet CMF, en deux étapes :

  1. Synchronisation : pour chaque société du registre, recherche les états
     financiers annuels au 31/12 des 10 dernières années et enregistre les
     métadonnées manquantes (nom, année, lien) en base MySQL (tables `cmf`
     et `documents` — aucun PDF n'est téléchargé sur disque à cette étape).
  2. Extraction KPI : pour chaque document en base, extrait "Capitaux
     propres" et "Total actif" du tableau Bilan et écrit un CSV par document
     réussi (data/kpis/), en journalisant les échecs dans un rapport Excel.

Chaque société est traitée indépendamment lors de la synchronisation, et les
erreurs sont capturées pour ne pas interrompre le pipeline global.
"""

import sys
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraping.cmf_portal_scraper import CMFPortalScraper
from config.company_registry import COMPANY_REGISTRY
from extraction.kpi_extraction_pipeline import run as run_kpi_extraction
from pipelines.control import is_cancel_requested
from pipelines.progress import set_phase

# Nombre de navigateurs Chrome headless lancés en parallèle pour la
# synchronisation CMF (24 sociétés) — chacun traite un sous-ensemble
# indépendant du registre, sur sa propre instance CMFPortalScraper (son
# propre driver + sa propre connexion base). Diviser le temps total par
# ~CMF_WORKERS (retour utilisateur direct 2026-09-15 : "ça prend trop de
# temps à collecter les pdfs" — la synchronisation CMF, strictement
# séquentielle jusqu'ici, était le principal goulot du premier lancement).
# Relevé à 6 le 2026-09-16 (retour utilisateur : encore trop lent) — reste
# raisonnable au regard des 24 sociétés à répartir (4 par navigateur en
# moyenne) sans multiplier excessivement les requêtes simultanées vers le
# portail CMF (risque de blocage/rate-limit à un nombre plus élevé).
CMF_WORKERS = 6

# Délai maximal accordé à UNE société avant abandon. Sans cette borne, un
# Chrome qui plante silencieusement en cours de route bloque le thread pour
# toujours, sans lever d'exception (constaté 2026-09-15 : 15+ minutes de
# silence total, aucun processus Chrome restant, aucune erreur journalisée —
# voir aussi set_page_load_timeout/set_script_timeout dans
# cmf_portal_scraper.py, qui réduisent mais n'éliminent pas totalement le
# risque si chromedriver lui-même meurt).
COMPANY_HARD_TIMEOUT_S = 120


def _run_company_with_watchdog(scraper, company_key, timeout=COMPANY_HARD_TIMEOUT_S):
    """Exécute scraper.run(company_key) avec un délai maximal strict.

    Renvoie (nb_nouveaux, timed_out). En cas de dépassement, le thread bloqué
    est ABANDONNÉ : Python ne peut pas tuer proprement un thread coincé dans
    un appel réseau, et attendre sa fin reviendrait à réintroduire le
    blocage qu'on cherche à éviter. Thread `daemon=True` (pas
    ThreadPoolExecutor, dont les threads internes ne sont PAS daemon —
    piège vérifié le 2026-09-15 : un future abandonné via `shutdown(wait=
    False)` laisse quand même le process entier bloqué à la fin du script,
    l'interpréteur attendant que TOUS les threads non-daemon se terminent,
    ce qu'un thread coincé pour toujours ne fera jamais). Un thread daemon
    fantôme n'empêche jamais le process de se terminer, et disparaît avec
    lui si le driver ne répond jamais."""
    result_q = queue.Queue(maxsize=1)

    def _target():
        try:
            result_q.put(("ok", scraper.run(company_key)))
        except Exception as exc:
            result_q.put(("error", exc))

    threading.Thread(target=_target, daemon=True).start()
    try:
        kind, value = result_q.get(timeout=timeout)
    except queue.Empty:
        print(f"[ERROR] {company_key} : delai de {timeout}s depasse, abandon (navigateur probablement plante).")
        return 0, True
    if kind == "error":
        print(f"[ERROR] Echec du scraping pour {company_key} : {value}")
        return 0, False
    return value, False


def _sync_worker(company_keys, headless, worker_id):
    """Traite séquentiellement un sous-ensemble de sociétés sur UNE instance
    CMFPortalScraper (un seul navigateur) — plusieurs workers tournent en
    parallèle (voir sync_documents), chacun sur son propre sous-ensemble."""
    summary = {}
    scraper = CMFPortalScraper(COMPANY_REGISTRY, headless=headless)
    try:
        for company_key in company_keys:
            if is_cancel_requested():
                print(f"[ANNULE][worker {worker_id}] Collecte annulée — synchronisation interrompue.")
                break
            print(f"\n===== TRAITEMENT : {company_key} (worker {worker_id}) =====")
            nb_nouveaux, timed_out = _run_company_with_watchdog(scraper, company_key)
            summary[company_key] = nb_nouveaux
            if timed_out:
                # Le driver est probablement dans un état mort/incohérent
                # (c'est justement pourquoi l'appel n'est jamais revenu) : on
                # ferme (best-effort, en tache de fond — close() elle-même
                # peut bloquer sur un driver deja mort) et on en relance un
                # neuf plutot que de continuer a l'utiliser.
                dead_scraper = scraper
                threading.Thread(target=lambda: _safe_close(dead_scraper), daemon=True).start()
                scraper = CMFPortalScraper(COMPANY_REGISTRY, headless=headless)
    finally:
        _safe_close(scraper)
    return summary


def _safe_close(scraper):
    try:
        scraper.close()
    except Exception:
        pass


def sync_documents(headless=True):
    print("\n===== ETAPE 1 : SYNCHRONISATION CMF -> BASE =====\n")

    company_keys = list(COMPANY_REGISTRY)
    workers = min(CMF_WORKERS, len(company_keys))
    # Répartition round-robin (pas par tranches contiguës) : équilibre mieux
    # la charge si certaines sociétés voisines dans le registre partagent
    # des caractéristiques qui les rendent systématiquement plus lentes/
    # plus sujettes aux retries (repli sur le <select> natif, etc.).
    chunks = [company_keys[i::workers] for i in range(workers)]

    summary = {}
    started_at = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_sync_worker, chunk, headless, i) for i, chunk in enumerate(chunks)]
        for future in futures:
            summary.update(future.result())
    duration = time.monotonic() - started_at

    print("\n===== RESUME SYNCHRONISATION =====")
    total = 0
    for company_key, count in summary.items():
        print(f"  {company_key:20s} : {count} nouveau(x) document(s) enregistre(s) en base")
        total += count
    print(f"\nTOTAL : {total} nouveau(x) document(s) enregistre(s) sur {len(summary)} societe(s) en {duration:.0f}s\n")

    return summary


def main(headless=True):
    print("\n===== DEBUT DU PIPELINE CMF =====\n")
    set_phase("scraping")
    sync_summary = sync_documents(headless=headless)
    if is_cancel_requested():
        return {"sync": sync_summary, "kpi": None}
    set_phase("extraction_kpi")
    kpi_summary = run_kpi_extraction()
    return {"sync": sync_summary, "kpi": kpi_summary}


if __name__ == "__main__":
    main()
