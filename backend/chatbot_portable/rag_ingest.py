"""
Ingestion automatique du corpus RAG a partir des rapports annuels CGA
(reutilise scraping.cga_scraper pour la liste des rapports disponibles).

Pour chaque rapport :
  1. Telechargement du PDF,
  2. Extraction du texte par page (pdfplumber),
  3. Filtrage des pages sans texte exploitable (pages de couverture/diviseurs
     purement graphiques, ou dans de rares cas une page dont l'extraction
     echoue) : on ignore une page plutot que d'injecter du contenu vide ou
     illisible dans le corpus (contrainte projet : le RAG ne doit jamais
     servir de contenu fabrique ou incorrect au LLM),
  4. Chunking des pages propres en paragraphes (~500-1000 caracteres),
  5. Ecriture dans chatbot_portable/rag_corpus_extra.json, fusionne au
     chargement par rag_module.RegulationRAG avec le corpus statique.

Usage :
    python chatbot_portable/rag_ingest.py [--years 2022 2023] [--max-pages 20]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pdfplumber
import requests

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_corpus_extra.json")
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}

# Au-dela de ce ratio de caracteres de remplacement (U+FFFD) sur une page,
# on considere l'extraction inexploitable et on l'ignore (page sans texte,
# ou dans de rares cas un probleme d'extraction ponctuel).
CORRUPTION_RATIO_THRESHOLD = 0.01


def _corruption_ratio(text: str) -> float:
    if not text:
        return 1.0
    return text.count("�") / len(text)


def _chunk_text(text: str, min_len: int = 400, max_len: int = 1000) -> list[str]:
    """Decoupe un texte de page en paragraphes de taille raisonnable pour le RAG,
    en respectant les frontieres de phrases quand c'est possible."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buffer = ""
    for para in paragraphs:
        candidate = (buffer + " " + para).strip() if buffer else para
        if len(candidate) > max_len and buffer:
            chunks.append(buffer)
            buffer = para
        else:
            buffer = candidate
        if len(buffer) >= min_len:
            chunks.append(buffer)
            buffer = ""
    if buffer:
        chunks.append(buffer)
    return chunks


def ingest_report(year: int, url: str, max_pages: int) -> list[dict]:
    print(f"[INFO] Telechargement rapport CGA {year}...")
    resp = requests.get(url, headers=REQUEST_HEADERS, timeout=60)
    resp.raise_for_status()

    entries = []
    skipped_pages = 0
    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
        n_pages = min(max_pages, len(pdf.pages))
        for i in range(n_pages):
            text = pdf.pages[i].extract_text() or ""
            if _corruption_ratio(text) > CORRUPTION_RATIO_THRESHOLD:
                skipped_pages += 1
                continue
            for j, chunk in enumerate(_chunk_text(text)):
                entries.append({
                    "id": f"cga_rapport_{year}_p{i+1}_{j}",
                    "titre": f"Rapport annuel CGA {year} — page {i+1}",
                    "source": f"CGA — Rapport annuel {year}",
                    "date": str(year),
                    "texte": chunk,
                })

    if skipped_pages == n_pages:
        print(f"[WARN] Rapport CGA {year} : {n_pages} page(s) toutes corrompues (encodage), "
              f"aucun contenu ingere. Voir extraction/CAS_PARTICULIERS_RAG_CGA.md")
    else:
        print(f"[OK] Rapport CGA {year} : {len(entries)} extrait(s) ingere(s), "
              f"{skipped_pages}/{n_pages} page(s) ignoree(s) pour corruption d'encodage")
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, nargs="*", default=None,
                         help="Annees a ingerer (defaut : les 3 plus recentes disponibles)")
    parser.add_argument("--max-pages", type=int, default=20,
                         help="Nombre max de pages lues par rapport (defaut 20 : synthese/contexte, "
                              "pas les annexes chiffrees deja couvertes par le pipeline KPI)")
    args = parser.parse_args()

    from scraping.cga_scraper import _fetch_report_links

    by_year = _fetch_report_links()
    years = args.years or sorted(by_year, reverse=True)[:3]

    all_entries = []
    for year in years:
        if year not in by_year:
            print(f"[WARN] Rapport CGA {year} introuvable sur le site, ignore")
            continue
        try:
            all_entries.extend(ingest_report(year, by_year[year], args.max_pages))
        except Exception as exc:
            print(f"[ERROR] Echec ingestion rapport CGA {year} : {exc}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    print(f"\n[INFO] {len(all_entries)} extrait(s) au total ecrit(s) dans {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
