"""
Scraper Selenium pour le portail CMF (Conseil du Marché Financier) :
https://www.cmf.tn/consultation-des-tats-financier-des-soci-t-s-faisant-ape

Automatise :
  1. la sélection d'une société via le widget dynamique "Chosen",
  2. le clic sur "Rechercher",
  3. l'extraction des lignes de résultats (année / type de document / lien PDF),
  4. le filtrage des états financiers annuels au 31/12 sur les 10 dernières années,
  5. l'enregistrement des métadonnées (nom, année, lien) en base MySQL
     (tables `cmf` et `documents` — aucun PDF n'est téléchargé sur disque).
"""

import re
import time
from datetime import datetime

import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

from database.repository import (
    document_exists,
    ensure_database,
    get_connection,
    get_or_create_company,
    get_or_create_source,
    init_schema,
    save_document,
    count_documents,
)

CMF_URL = "https://www.cmf.tn/consultation-des-tats-financier-des-soci-t-s-faisant-ape"
SELECT_FIELD_ID = "edit-field-societesape-value"

# Le champ "période" contient par exemple "Etats financiers au 31/12" ou
# "Etats financiers intermédiaires au 30/06". On ne garde que les annuels au 31/12.
ANNUAL_31_12_PATTERN = re.compile(r"31\s*/\s*12")
INTERIM_KEYWORDS = ("intermédiaire", "intermediaire")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


class CMFPortalScraper:
    def __init__(self, company_registry, headless=True):
        self.registry = company_registry

        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,1000")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"user-agent={REQUEST_HEADERS['User-Agent']}")

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 20)

        # Fenêtre des "10 dernières années" : l'année en cours n'a en général pas
        # encore d'état financier publié (ex: en 2026, on part de 2015 pour
        # obtenir les 10 derniers exercices réellement disponibles, 2015-2025).
        current_year = datetime.now().year
        self.min_year = current_year - 11
        self.max_year = current_year

        ensure_database()
        self.db_conn = get_connection()
        init_schema(self.db_conn)
        self.source_id = get_or_create_source(self.db_conn, "CMF", CMF_URL)

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #

    def open_page(self):
        print("[STEP] Ouverture de la page CMF...")
        self.driver.get(CMF_URL)
        self.wait.until(EC.presence_of_element_located((By.ID, SELECT_FIELD_ID)))

    def select_company(self, company_key):
        cmf_name = self.registry[company_key]["cmf_name"]
        print(f"[STEP] Sélection de la société : {cmf_name}")

        # Le module Drupal "Chosen" génère l'id du widget en remplaçant tous les
        # tirets de l'id d'origine par des underscores (ex: edit-field-x -> edit_field_x_chosen)
        chosen_id = SELECT_FIELD_ID.replace("-", "_") + "_chosen"
        try:
            container = self.wait.until(EC.presence_of_element_located((By.ID, chosen_id)))
            container.find_element(By.CSS_SELECTOR, ".chosen-single").click()

            search_box = self.wait.until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, f"#{chosen_id} .chosen-search input")
                )
            )
            search_box.clear()
            search_box.send_keys(cmf_name)

            options = self._wait_for_filtered_options(chosen_id)
            target = self._match_option(options, cmf_name)
            if target is None:
                # ferme le widget avant de basculer sur le repli natif
                container.find_element(By.CSS_SELECTOR, ".chosen-single").click()
                raise NoSuchElementException(cmf_name)

            target.click()
            print("[INFO] Société sélectionnée via le widget Chosen.")
            return
        except (TimeoutException, NoSuchElementException):
            print("[WARN] Widget Chosen indisponible, repli sur le <select> natif.")

        # Repli : le JS "Chosen" n'a pas chargé, on utilise le <select> natif.
        # Le <select> est display:none (masqué par Chosen), donc .text renvoie
        # une chaîne vide sur les <option> : il faut lire l'attribut "value"
        # (qui est identique au libellé pour ce champ Drupal).
        select_el = self.wait.until(EC.presence_of_element_located((By.ID, SELECT_FIELD_ID)))
        select = Select(select_el)
        target_norm = cmf_name.strip().lower()
        for option in select.options:
            value = (option.get_attribute("value") or "").strip()
            if value.lower() == target_norm:
                select.select_by_value(value)
                print("[INFO] Société sélectionnée via le <select> natif.")
                return
        raise ValueError(f"Société introuvable dans le widget CMF : {cmf_name}")

    def _wait_for_filtered_options(self, chosen_id, timeout=5):
        end_time = time.time() + timeout
        options = []
        while time.time() < end_time:
            raw = self.driver.find_elements(By.CSS_SELECTOR, f"#{chosen_id} li.active-result")
            options = [li for li in raw if li.is_displayed()]
            if options:
                break
            time.sleep(0.2)
        return options

    @staticmethod
    def _match_option(options, target_text):
        target_norm = " ".join(target_text.lower().split())
        for opt in options:
            if " ".join(opt.text.strip().lower().split()) == target_norm:
                return opt
        for opt in options:
            if target_norm in " ".join(opt.text.strip().lower().split()):
                return opt
        return None

    def click_search(self):
        print("[STEP] Clic sur 'Rechercher'...")
        # Le formulaire de recherche déclenche un rechargement complet de la page
        # (GET classique) : on capture l'ancien contenu pour être sûr d'attendre
        # sa disparition avant de lire les nouveaux résultats (évite les
        # StaleElementReferenceException lors du parsing des lignes).
        old_content = self.driver.find_elements(By.CSS_SELECTOR, ".view-content")
        old_marker = old_content[0] if old_content else None

        btn = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input.form-submit[value='Rechercher']"))
        )
        btn.click()

        if old_marker is not None:
            try:
                self.wait.until(EC.staleness_of(old_marker))
            except TimeoutException:
                pass

        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".view-content")))

    # ------------------------------------------------------------------ #
    # Extraction des résultats
    # ------------------------------------------------------------------ #

    def _parse_current_page(self):
        entries = []
        rows = self.driver.find_elements(By.CSS_SELECTOR, "div.views-row")
        for row in rows:
            try:
                year_text = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-exercice .field-item"
                ).text.strip()
                period_text = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-p-riode .field-item"
                ).text.strip()
                pdf_url = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-pdf-cf a"
                ).get_attribute("href")
            except (NoSuchElementException, StaleElementReferenceException):
                continue
            if not year_text or not pdf_url:
                continue
            entries.append({"year": year_text, "period": period_text, "pdf_url": pdf_url})
        return entries

    def _go_to_next_page(self):
        next_links = self.driver.find_elements(By.CSS_SELECTOR, "li.pager-next a")
        if not next_links:
            return False
        current_rows = self.driver.find_elements(By.CSS_SELECTOR, "div.views-row")
        anchor = current_rows[0] if current_rows else None
        next_links[0].click()
        if anchor is not None:
            try:
                self.wait.until(EC.staleness_of(anchor))
            except TimeoutException:
                pass
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".view-content")))
        except TimeoutException:
            return False
        return True

    @staticmethod
    def is_annual_statement_31_12(period_text):
        text = period_text.lower()
        if any(keyword in text for keyword in INTERIM_KEYWORDS):
            return False
        return bool(ANNUAL_31_12_PATTERN.search(text))

    def collect_annual_statements(self, max_pages=30):
        """Parcourt toutes les pages de résultats et renvoie {annee: pdf_url}
        pour les états financiers annuels au 31/12 dans la fenêtre des 10
        dernières années."""
        collected = {}
        for _ in range(max_pages):
            for entry in self._parse_current_page():
                if not self.is_annual_statement_31_12(entry["period"]):
                    continue
                match = re.search(r"\d{4}", entry["year"])
                if not match:
                    continue
                year = int(match.group())
                if not (self.min_year <= year <= self.max_year):
                    continue
                # garde la première occurrence rencontrée (la plus récemment publiée)
                collected.setdefault(year, entry["pdf_url"])
            if not self._go_to_next_page():
                break
        return collected

    # ------------------------------------------------------------------ #
    # Vérification du lien et enregistrement en base
    # ------------------------------------------------------------------ #

    def _verify_pdf_link(self, url, retries=2, timeout=15):
        """Vérifie que le lien pointe bien vers un PDF accessible, sans
        conserver son contenu."""
        for attempt in range(1, retries + 1):
            try:
                response = requests.head(
                    url, headers=REQUEST_HEADERS, timeout=timeout, allow_redirects=True
                )
                if response.status_code == 200:
                    return True
                # Certains serveurs ne gèrent pas HEAD correctement -> repli GET
                response = requests.get(
                    url, headers=REQUEST_HEADERS, timeout=timeout, stream=True
                )
                ok = response.status_code == 200
                response.close()
                return ok
            except requests.RequestException as exc:
                print(f"[WARN] Tentative {attempt}/{retries} échouée pour {url} : {exc}")
                time.sleep(1.5)
        return False

    def extract_and_store(self, company_key):
        print("[STEP] Extraction des lignes et enregistrement en base (10 dernières années)...")
        statements = self.collect_annual_statements()

        cmf_name = self.registry[company_key]["cmf_name"]
        cmf_id = get_or_create_company(self.db_conn, company_key, cmf_name)

        saved = 0
        for year in sorted(statements):
            pdf_url = statements[year]
            if document_exists(self.db_conn, self.source_id, cmf_id, year):
                print(f"[INFO] Déjà en base : {company_key} {year}")
                continue
            if not self._verify_pdf_link(pdf_url):
                print(f"[WARN] Lien PDF invalide, ignoré : {pdf_url}")
                continue
            nom_pdf = f"{company_key}_{year}.pdf"
            save_document(self.db_conn, self.source_id, cmf_id, nom_pdf, year, pdf_url)
            saved += 1
            print(f"[OK] Enregistré en base : {nom_pdf}")

        total = count_documents(self.db_conn, cmf_id)
        print(f"[INFO] {saved} nouveau(x) document(s) pour {company_key} ({total} au total en base)")
        return saved

    # ------------------------------------------------------------------ #
    # Pipeline complet pour une société
    # ------------------------------------------------------------------ #

    def run(self, company_key, retries=3):
        """Comme _verify_pdf_link : le portail CMF peut occasionnellement ne
        pas charger a temps (page lente, widget Chosen pas encore pret) ->
        on relance la sequence complete (page fraiche) plutot qu'une seule
        etape, car un TimeoutException en cours de route laisse le driver
        dans un etat intermediaire non reutilisable."""
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                self.open_page()
                self.select_company(company_key)
                self.click_search()
                return self.extract_and_store(company_key)
            except TimeoutException as exc:
                last_exc = exc
                print(f"[WARN] Tentative {attempt}/{retries} echouee pour {company_key} (page CMF) : {exc}")
                if attempt < retries:
                    time.sleep(2)
        raise last_exc

    def close(self):
        try:
            self.driver.quit()
        except Exception:
            pass
        try:
            self.db_conn.close()
        except Exception:
            pass
