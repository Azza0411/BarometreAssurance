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

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraping.cmf_portal_scraper import CMFPortalScraper
from config.company_registry import COMPANY_REGISTRY
from extraction.kpi_extraction_pipeline import run as run_kpi_extraction


def sync_documents(headless=True):
    print("\n===== ETAPE 1 : SYNCHRONISATION CMF -> BASE =====\n")

    summary = {}
    scraper = CMFPortalScraper(COMPANY_REGISTRY, headless=headless)

    try:
        for company_key in COMPANY_REGISTRY:
            print(f"\n===== TRAITEMENT : {company_key} =====")
            try:
                nb_nouveaux = scraper.run(company_key)
                summary[company_key] = nb_nouveaux
            except Exception as exc:
                print(f"[ERROR] Echec du scraping pour {company_key} : {exc}")
                summary[company_key] = 0
    finally:
        scraper.close()

    print("\n===== RESUME SYNCHRONISATION =====")
    total = 0
    for company_key, count in summary.items():
        print(f"  {company_key:20s} : {count} nouveau(x) document(s) enregistre(s) en base")
        total += count
    print(f"\nTOTAL : {total} nouveau(x) document(s) enregistre(s) sur {len(summary)} societe(s)\n")

    return summary


def main(headless=True):
    print("\n===== DEBUT DU PIPELINE CMF =====\n")
    sync_summary = sync_documents(headless=headless)
    kpi_summary = run_kpi_extraction()
    return {"sync": sync_summary, "kpi": kpi_summary}


if __name__ == "__main__":
    main()
