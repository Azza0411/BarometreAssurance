"""
Scraper Selenium pour le portail CMF (Conseil du Marché Financier) :
https://www.cmf.tn/consultation-des-tats-financier-des-soci-t-s-faisant-ape

Automatise :
  1. la sélection d'une société via le widget dynamique "Chosen",
  2. le clic sur "Rechercher",
  3. l'extraction des lignes de résultats (année / type de document / lien PDF),
  4. le filtrage des états financiers annuels au 31/12 sur les 10 dernières années,
  5. l'enregistrement des métadonnées (nom, année, lien) en base MySQL
     (tables `societes` et `documents` — aucun PDF n'est téléchargé sur disque).
"""

import re  # extraire l'année et détecter le motif "31/12" dans le texte du site
import time  # pauses entre tentatives / polling du widget Chosen
from datetime import datetime  # calculer l'année en cours (fenêtre des 10-11 dernières années)

import requests  # vérifier qu'un lien PDF répond, sans passer par Selenium
from selenium import webdriver  # pilote le navigateur Chrome
from selenium.webdriver.common.by import By  # sélecteurs CSS pour retrouver les éléments
from selenium.webdriver.support.ui import Select, WebDriverWait  # <select> natif + attentes explicites
from selenium.webdriver.support import expected_conditions as EC  # conditions d'attente (élément présent, cliquable...)
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

from database.repository import (
    document_exists,       # vérifie qu'un document n'est pas déjà en base (déduplication)
    ensure_database,        # crée la base MySQL si elle n'existe pas
    get_connection,          # ouvre la connexion MySQL
    get_or_create_company,    # récupère ou crée l'id interne d'une société (table societes)
    get_or_create_source,      # récupère ou crée l'id de la source "CMF" (table sources)
    init_schema,                 # crée/met à jour les tables si besoin
    save_document,                 # enregistre les métadonnées d'un document (jamais le PDF)
    count_documents,                 # compte les documents déjà enregistrés pour une société
)

CMF_URL = "https://www.cmf.tn/consultation-des-tats-financier-des-soci-t-s-faisant-ape"
SELECT_FIELD_ID = "edit-field-societesape-value"  # id HTML natif du menu de sélection de société

# Le champ "période" contient par exemple "Etats financiers au 31/12" ou
# "Etats financiers intermédiaires au 30/06". On ne garde que les annuels au 31/12.
ANNUAL_31_12_PATTERN = re.compile(r"31\s*/\s*12")  # motif "31/12" (avec espaces optionnels)
INTERIM_KEYWORDS = ("intermédiaire", "intermediaire")  # mots qui excluent un document (pas annuel)

REQUEST_HEADERS = {
    # Certains serveurs bloquent les requêtes sans User-Agent de navigateur "normal"
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


class CMFPortalScraper:
    # Utilité : configure Chrome (headless), connecte la base, fixe la fenêtre 10-11 ans
    def __init__(self, company_registry, headless=True):
        self.registry = company_registry  # dict des 24 sociétés (config/company_registry.py)

        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")  # navigateur invisible (pas de fenêtre affichée)
        options.add_argument("--window-size=1400,1000")  # taille fixe, la page s'adapte en desktop
        options.add_argument("--disable-gpu")  # évite des erreurs GPU en mode headless
        options.add_argument("--no-sandbox")  # nécessaire dans certains environnements restreints
        options.add_argument("--disable-dev-shm-usage")  # évite un crash de mémoire partagée
        options.add_argument(f"user-agent={REQUEST_HEADERS['User-Agent']}")  # même UA que les requêtes HTTP

        self.driver = webdriver.Chrome(options=options)  # lance le navigateur Chrome piloté
        self.wait = WebDriverWait(self.driver, 20)  # attente explicite par défaut : 20s max

        # Fenêtre des "10 dernières années" : l'année en cours n'a en général pas
        # encore d'état financier publié (ex: en 2026, on part de 2015 pour
        # obtenir les 10 derniers exercices réellement disponibles, 2015-2025).
        current_year = datetime.now().year
        self.min_year = current_year - 11  # borne basse de la fenêtre de collecte
        self.max_year = current_year  # borne haute (année en cours incluse, rarement disponible)

        ensure_database()  # crée la base MySQL si elle n'existe pas déjà
        self.db_conn = get_connection()  # ouvre la connexion pour toute la durée du scraping
        init_schema(self.db_conn)  # crée/migre les tables si nécessaire (idempotent)
        self.source_id = get_or_create_source(self.db_conn, "CMF", CMF_URL)  # id de la source "CMF"

    # ------------------------------------------------------------------ #
    # Navigation
    # ------------------------------------------------------------------ #

    # Utilité : charge la page du portail CMF
    def open_page(self):
        print("[STEP] Ouverture de la page CMF...")
        self.driver.get(CMF_URL)  # charge la page du portail
        self.wait.until(EC.presence_of_element_located((By.ID, SELECT_FIELD_ID)))  # attend que le menu existe

    # Utilité : sélectionne la société (widget Chosen, repli <select> natif)
    def select_company(self, company_key):
        cmf_name = self.registry[company_key]["cmf_name"]  # nom exact attendu par le portail CMF
        print(f"[STEP] Sélection de la société : {cmf_name}")

        # Le module Drupal "Chosen" génère l'id du widget en remplaçant tous les
        # tirets de l'id d'origine par des underscores (ex: edit-field-x -> edit_field_x_chosen)
        chosen_id = SELECT_FIELD_ID.replace("-", "_") + "_chosen"
        try:
            container = self.wait.until(EC.presence_of_element_located((By.ID, chosen_id)))  # widget JS
            container.find_element(By.CSS_SELECTOR, ".chosen-single").click()  # ouvre le menu déroulant

            search_box = self.wait.until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, f"#{chosen_id} .chosen-search input")
                )
            )  # champ de recherche interne au widget
            search_box.clear()  # vide le champ avant de taper
            search_box.send_keys(cmf_name)  # tape le nom de la société pour filtrer les options

            options = self._wait_for_filtered_options(chosen_id)  # récupère les options filtrées visibles
            target = self._match_option(options, cmf_name)  # trouve l'option qui correspond exactement
            if target is None:
                # ferme le widget avant de basculer sur le repli natif
                container.find_element(By.CSS_SELECTOR, ".chosen-single").click()
                raise NoSuchElementException(cmf_name)

            target.click()  # sélectionne l'option trouvée
            print("[INFO] Société sélectionnée via le widget Chosen.")
            return
        except (TimeoutException, NoSuchElementException):
            print("[WARN] Widget Chosen indisponible, repli sur le <select> natif.")

        # Repli : le JS "Chosen" n'a pas chargé, on utilise le <select> natif.
        # Le <select> est display:none (masqué par Chosen), donc .text renvoie
        # une chaîne vide sur les <option> : il faut lire l'attribut "value"
        # (qui est identique au libellé pour ce champ Drupal).
        select_el = self.wait.until(EC.presence_of_element_located((By.ID, SELECT_FIELD_ID)))
        select = Select(select_el)  # wrapper Selenium pour un <select> HTML natif
        target_norm = cmf_name.strip().lower()  # normalise pour une comparaison insensible à la casse
        for option in select.options:
            value = (option.get_attribute("value") or "").strip()
            if value.lower() == target_norm:
                select.select_by_value(value)  # sélectionne l'option native correspondante
                print("[INFO] Société sélectionnée via le <select> natif.")
                return
        raise ValueError(f"Société introuvable dans le widget CMF : {cmf_name}")

    # Utilité : attend que le menu affiche les résultats filtrés
    def _wait_for_filtered_options(self, chosen_id, timeout=5):
        end_time = time.time() + timeout  # borne de temps pour arrêter le polling
        options = []
        while time.time() < end_time:
            raw = self.driver.find_elements(By.CSS_SELECTOR, f"#{chosen_id} li.active-result")  # options du menu
            options = [li for li in raw if li.is_displayed()]  # ne garde que celles visibles (filtrées)
            if options:
                break  # dès qu'il y a au moins une option filtrée, on arrête d'attendre
            time.sleep(0.2)  # petite pause avant de revérifier
        return options

    # Utilité : trouve l'option qui correspond exactement au nom cherché
    @staticmethod
    def _match_option(options, target_text):
        target_norm = " ".join(target_text.lower().split())  # normalise espaces + casse
        for opt in options:
            if " ".join(opt.text.strip().lower().split()) == target_norm:
                return opt  # correspondance exacte trouvée en premier
        for opt in options:
            if target_norm in " ".join(opt.text.strip().lower().split()):
                return opt  # sinon, repli sur une correspondance partielle
        return None  # aucune option ne correspond

    # Utilité : clique sur "Rechercher", attend le rechargement de la page
    def click_search(self):
        print("[STEP] Clic sur 'Rechercher'...")
        # Le formulaire de recherche déclenche un rechargement complet de la page
        # (GET classique) : on capture l'ancien contenu pour être sûr d'attendre
        # sa disparition avant de lire les nouveaux résultats (évite les
        # StaleElementReferenceException lors du parsing des lignes).
        old_content = self.driver.find_elements(By.CSS_SELECTOR, ".view-content")
        old_marker = old_content[0] if old_content else None  # référence à l'ancien contenu (avant clic)

        btn = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input.form-submit[value='Rechercher']"))
        )  # attend que le bouton soit cliquable
        btn.click()  # lance la recherche

        if old_marker is not None:
            try:
                self.wait.until(EC.staleness_of(old_marker))  # attend que l'ancien contenu disparaisse
            except TimeoutException:
                pass  # tolère l'absence de rechargement détecté, on vérifie la suite quand même

        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".view-content")))  # nouveau contenu chargé

    # ------------------------------------------------------------------ #
    # Extraction des résultats
    # ------------------------------------------------------------------ #

    # Utilité : lit les lignes de résultats affichées (année, période, lien PDF)
    def _parse_current_page(self):
        entries = []
        rows = self.driver.find_elements(By.CSS_SELECTOR, "div.views-row")  # une ligne par document affiché
        for row in rows:
            try:
                year_text = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-exercice .field-item"
                ).text.strip()  # texte de l'année (ex: "2022")
                period_text = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-p-riode .field-item"
                ).text.strip()  # texte de la période (ex: "Etats financiers au 31/12")
                pdf_url = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-pdf-cf a"
                ).get_attribute("href")  # lien du PDF
            except (NoSuchElementException, StaleElementReferenceException):
                continue  # ligne incomplète ou périmée, on l'ignore
            if not year_text or not pdf_url:
                continue  # ligne inexploitable sans année ou sans lien
            entries.append({"year": year_text, "period": period_text, "pdf_url": pdf_url})
        return entries

    # Utilité : passe à la page suivante des résultats, si elle existe
    def _go_to_next_page(self):
        next_links = self.driver.find_elements(By.CSS_SELECTOR, "li.pager-next a")  # lien "page suivante"
        if not next_links:
            return False  # pas de page suivante : dernière page atteinte
        current_rows = self.driver.find_elements(By.CSS_SELECTOR, "div.views-row")
        anchor = current_rows[0] if current_rows else None  # repère pour détecter le changement de page
        next_links[0].click()  # clique sur "page suivante"
        if anchor is not None:
            try:
                self.wait.until(EC.staleness_of(anchor))  # attend que l'ancienne page disparaisse
            except TimeoutException:
                pass
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".view-content")))  # nouvelle page chargée
        except TimeoutException:
            return False  # la page suivante n'a pas chargé à temps
        return True

    # Utilité : vérifie qu'un document est annuel et daté du 31/12
    @staticmethod
    def is_annual_statement_31_12(period_text):
        text = period_text.lower()
        if any(keyword in text for keyword in INTERIM_KEYWORDS):
            return False  # document intermédiaire, exclu
        return bool(ANNUAL_31_12_PATTERN.search(text))  # vrai seulement si "31/12" est présent

    # Utilité : parcourt toutes les pages, applique le filtre, garde 10-11 ans
    def collect_annual_statements(self, max_pages=30):
        """Parcourt toutes les pages de résultats et renvoie {annee: pdf_url}
        pour les états financiers annuels au 31/12 dans la fenêtre des 10
        dernières années."""
        collected = {}
        for _ in range(max_pages):  # garde-fou : ne boucle pas indéfiniment si la pagination est cassée
            for entry in self._parse_current_page():
                if not self.is_annual_statement_31_12(entry["period"]):
                    continue  # filtre : garde seulement les rapports annuels au 31/12
                match = re.search(r"\d{4}", entry["year"])
                if not match:
                    continue  # année illisible, on ignore la ligne
                year = int(match.group())
                if not (self.min_year <= year <= self.max_year):
                    continue  # filtre : hors fenêtre des 10-11 dernières années
                # garde la première occurrence rencontrée (la plus récemment publiée)
                collected.setdefault(year, entry["pdf_url"])
            if not self._go_to_next_page():
                break  # plus de page suivante, on arrête de parcourir
        return collected

    # ------------------------------------------------------------------ #
    # Vérification du lien et enregistrement en base
    # ------------------------------------------------------------------ #

    # Utilité : vérifie que le lien PDF répond (HEAD, repli GET)
    def _verify_pdf_link(self, url, retries=2, timeout=15):
        """Vérifie que le lien pointe bien vers un PDF accessible, sans
        conserver son contenu."""
        for attempt in range(1, retries + 1):
            try:
                response = requests.head(
                    url, headers=REQUEST_HEADERS, timeout=timeout, allow_redirects=True
                )  # requête légère : on ne veut pas télécharger le PDF, juste vérifier le lien
                if response.status_code == 200:
                    return True  # lien valide
                # Certains serveurs ne gèrent pas HEAD correctement -> repli GET
                response = requests.get(
                    url, headers=REQUEST_HEADERS, timeout=timeout, stream=True
                )  # stream=True : ne télécharge pas tout le contenu en mémoire
                ok = response.status_code == 200
                response.close()  # ferme la connexion sans lire le corps de la réponse
                return ok
            except requests.RequestException as exc:
                print(f"[WARN] Tentative {attempt}/{retries} échouée pour {url} : {exc}")
                time.sleep(1.5)  # pause avant de réessayer
        return False  # toutes les tentatives ont échoué

    # Utilité : déduplique et enregistre les métadonnées en base
    def extract_and_store(self, company_key):
        print("[STEP] Extraction des lignes et enregistrement en base (10 dernières années)...")
        statements = self.collect_annual_statements()  # {annee: pdf_url} déjà filtré

        cmf_name = self.registry[company_key]["cmf_name"]
        cmf_id = get_or_create_company(self.db_conn, company_key, cmf_name)  # id interne de la société

        saved = 0
        for year in sorted(statements):  # traite les années dans l'ordre chronologique
            pdf_url = statements[year]
            if document_exists(self.db_conn, self.source_id, cmf_id, year):
                print(f"[INFO] Déjà en base : {company_key} {year}")
                continue  # déduplication : on ne réenregistre pas un document déjà connu
            if not self._verify_pdf_link(pdf_url):
                print(f"[WARN] Lien PDF invalide, ignoré : {pdf_url}")
                continue  # lien mort, on n'enregistre rien pour cette année
            nom_pdf = f"{company_key}_{year}.pdf"  # nom de fichier construit, pas le fichier lui-même
            save_document(self.db_conn, self.source_id, cmf_id, nom_pdf, year, pdf_url)  # écrit les métadonnées
            saved += 1
            print(f"[OK] Enregistré en base : {nom_pdf}")

        total = count_documents(self.db_conn, cmf_id)  # total cumulé après ce passage
        print(f"[INFO] {saved} nouveau(x) document(s) pour {company_key} ({total} au total en base)")
        return saved

    # ------------------------------------------------------------------ #
    # Pipeline complet pour une société
    # ------------------------------------------------------------------ #

    # Utilité : orchestre tout le déroulé, relance ×3 en cas de timeout
    def run(self, company_key, retries=3):
        """Comme _verify_pdf_link : le portail CMF peut occasionnellement ne
        pas charger a temps (page lente, widget Chosen pas encore pret) ->
        on relance la sequence complete (page fraiche) plutot qu'une seule
        etape, car un TimeoutException en cours de route laisse le driver
        dans un etat intermediaire non reutilisable."""
        last_exc = None  # mémorise la dernière erreur pour la relever si tout échoue
        for attempt in range(1, retries + 1):
            try:
                self.open_page()  # étape 1 : charger la page
                self.select_company(company_key)  # étape 2 : sélectionner la société
                self.click_search()  # étape 3 : lancer la recherche
                return self.extract_and_store(company_key)  # étape 4 : filtrer + dédupliquer + enregistrer
            except TimeoutException as exc:
                last_exc = exc
                print(f"[WARN] Tentative {attempt}/{retries} echouee pour {company_key} (page CMF) : {exc}")
                if attempt < retries:
                    time.sleep(2)  # petite pause avant de relancer toute la séquence
        raise last_exc  # toutes les tentatives ont échoué, on remonte la dernière erreur

    # Utilité : ferme le navigateur Chrome
    def close(self):
        try:
            self.driver.quit()  # ferme le navigateur Chrome
        except Exception:
            pass  # déjà fermé ou jamais ouvert correctement, sans conséquence
        try:
            self.db_conn.close()  # ferme la connexion à la base
        except Exception:
            pass
