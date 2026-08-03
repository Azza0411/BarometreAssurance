"""
Source INS (Institut National de la Statistique).

Deux sources complementaires :

1. Portail API dataportal.ins.tn (serie principale)
   - Population au 1er Juillet  -> KPI "Population Totale"
   - PIB aux prix du marche     -> KPI "Produit Interieur Brut (PIB)"

2. Page HTML ins.tn/statistiques/111 (fallback pour les annees recentes)
   - Tableau "Population au 1er Janvier" : colonnes = annees, ligne = total
   - Utilise uniquement pour les annees absentes de la serie principale.
"""

import datetime
import re
import time

import requests

from database.repository import (
    ensure_database,
    get_connection,
    get_or_create_source,
    init_schema,
    save_document,
    save_kpi_value,
)

PORTAL_PAGE_URL = "http://dataportal.ins.tn/fr/DataAnalysis?lWAcF5hGHkStY9XWRfYgzQ"
API_BASE_URL    = "http://dataportal.ins.tn/WebApi/GetData"
INS_STATS_POP_URL = "https://www.ins.tn/statistiques/111"
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; InsuranceKPIBot/1.0)"}

PERIOD_FROM   = "1.1.2000"
PERIOD_FINISH = f"1.1.{datetime.datetime.now().year + 1}"

POPULATION_QUERY = f"""
<QueryMessage SourceId='C_NSO'>
    <Period From='{PERIOD_FROM}' To='{PERIOD_FINISH}' Frequency='Y'></Period>
    <DataWhere>
        <Dimension Id='RDS_DICT_INDICATORS_NSO'><Element>22269316</Element></Dimension>
        <Dimension Id='RDS_DICT_REGIONS_NSO'><Element>0</Element></Dimension>
    </DataWhere>
</QueryMessage>
"""

PIB_QUERY = f"""
<QueryMessage SourceId='OBJ11288479'>
    <Period From='{PERIOD_FROM}' To='{PERIOD_FINISH}' Frequency='Y'></Period>
    <DataWhere>
        <Dimension Id='OBJ11288499'><Element>28757929</Element></Dimension>
    </DataWhere>
</QueryMessage>
"""

YEAR_SET_RE = re.compile(r'Period="YEARS:(\d{4})"[^>]*>([\d.\-]+)</Set>')


def _get_with_retries(url, timeout=30, retries=3):
    """Meme approche que bvmt_scraper/ftusa_scraper/cga_scraper : le site peut
    echouer ponctuellement (timeout, 5xx passager), quelques tentatives suffisent."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=REQUEST_HEADERS, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            print(f"  [WARN] Tentative {attempt}/{retries} echouee pour {url} : {exc}")
            time.sleep(1.5)


def _post_with_retries(url, headers, data, timeout=30, retries=3):
    """Meme logique que _get_with_retries, pour l'appel POST vers l'API INS."""
    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, headers=headers, data=data, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            print(f"  [WARN] Tentative {attempt}/{retries} echouee pour {url} : {exc}")
            time.sleep(1.5)


def _fetch_series(query_xml):
    response = _post_with_retries(
        API_BASE_URL,
        headers={**REQUEST_HEADERS, "Content-Type": "application/xml"},
        data=query_xml,
        timeout=30,
    )
    return {int(year): float(value) for year, value in YEAR_SET_RE.findall(response.text)}


def _fetch_population_jan():
    """Scrape ins.tn/statistiques/111 : tableau 'Population au 1er Janvier'
    dont les annees sont en colonnes (<thead>) et la population totale en <tbody>.
    Renvoie {annee: population}."""
    resp = _get_with_retries(INS_STATS_POP_URL, timeout=30)
    html = resp.text

    # Annees en colonnes dans le <thead>
    thead_m = re.search(r'<thead[^>]*>(.*?)</thead>', html, re.DOTALL)
    if not thead_m:
        return {}
    th_years = [int(y) for y in re.findall(r'<th[^>]*>\s*(20\d{2})\s*</th>', thead_m.group(1))]
    if not th_years:
        return {}

    # Premiere ligne de donnees du second <tbody> (apres le thead)
    after_thead = html[html.find('<thead'):]
    tbody_m = re.search(r'<tbody>(.*?)</tbody>', after_thead, re.DOTALL)
    if not tbody_m:
        return {}

    td_values = re.findall(r'<td[^>]*>\s*(\d[\d\s]*)\s*</td>', tbody_m.group(1))

    result = {}
    for year, raw in zip(th_years, td_values):
        try:
            val = float(re.sub(r'\s', '', raw))
            if val > 1_000_000:
                result[year] = val
        except ValueError:
            pass
    return result


def sync_all():
    """Recupere Population Totale et PIB pour toutes les annees disponibles."""
    ensure_database()
    conn = get_connection()
    init_schema(conn)
    source_id = get_or_create_source(conn, "INS", PORTAL_PAGE_URL)

    population_by_year = _fetch_series(POPULATION_QUERY)
    pib_by_year        = _fetch_series(PIB_QUERY)

    # Fallback : population au 1er janvier pour les annees recentes manquantes
    try:
        pop_jan = _fetch_population_jan()
        added = sum(
            1 for year, pop in pop_jan.items()
            if year not in population_by_year and not population_by_year.update({year: pop})
        )
        print(f"[STEP] Population 1er Janvier (fallback) : {added} annee(s) depuis {INS_STATS_POP_URL}")
    except Exception as e:
        print(f"[WARN] Impossible de scraper {INS_STATS_POP_URL} : {e}")

    print(f"[STEP] Population Totale : {len(population_by_year)} annee(s) ; PIB : {len(pib_by_year)} annee(s)")

    saved = 0
    for year in sorted(set(population_by_year) | set(pib_by_year)):
        document_id = save_document(conn, source_id, None, f"INS_{year}", year, PORTAL_PAGE_URL)
        if year in population_by_year:
            save_kpi_value(
                conn, document_id, "INS - Base de donnees socioeconomique",
                "Population Totale", valeur_nombre=population_by_year[year],
            )
            saved += 1
        if year in pib_by_year:
            save_kpi_value(
                conn, document_id, "INS - Principaux agregats (2015)",
                "Produit Interieur Brut (PIB)", valeur_nombre=pib_by_year[year],
            )
            saved += 1
        print(f"  [OK] {year} : population={population_by_year.get(year)}, pib={pib_by_year.get(year)}")

    conn.close()
    print(f"[INFO] {saved} valeur(s) enregistree(s)\n")
    return saved


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    sync_all()
