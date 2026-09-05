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

import re  # extraire année et motif 31/12
import time  # pauses entre tentatives
from datetime import datetime  # année en cours

import requests  # vérifie les liens PDF
from selenium import webdriver  # pilote le navigateur Chrome
from selenium.webdriver.common.by import By  # sélecteurs CSS
from selenium.webdriver.support.ui import Select, WebDriverWait  # <select> natif + attentes
from selenium.webdriver.support import expected_conditions as EC  # conditions d'attente
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

from database.repository import (
    document_exists,       # déduplication
    ensure_database,        # crée la base si besoin
    get_connection,          # ouvre la connexion MySQL
    get_or_create_company,    # id de la société
    get_or_create_source,      # id de la source
    init_schema,                 # crée les tables
    save_document,                 # enregistre les métadonnées
    count_documents,                 # compte les documents
)

CMF_URL = "https://www.cmf.tn/consultation-des-tats-financier-des-soci-t-s-faisant-ape"
SELECT_FIELD_ID = "edit-field-societesape-value"  # id du menu de sélection

# Le champ "période" contient par exemple "Etats financiers au 31/12" ou
# "Etats financiers intermédiaires au 30/06". On ne garde que les annuels au 31/12.
ANNUAL_31_12_PATTERN = re.compile(r"31\s*/\s*12")  # motif "31/12"
INTERIM_KEYWORDS = ("intermédiaire", "intermediaire")  # exclut les rapports intermédiaires

REQUEST_HEADERS = {
    # évite le blocage sans User-Agent de navigateur
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


class CMFPortalScraper:

    # ================================================================================== #
    # ÉTAPE 1 : INITIALISATION
    # ================================================================================== #

    # ------------------  Fonction 1 : configure Chrome, connecte la base, fixe la fenêtre d'années -------------------
    def __init__(self, company_registry, headless=True):
        self.registry = company_registry  # les 24 sociétés

        options = webdriver.ChromeOptions()  # options de lancement
        if headless:
            options.add_argument("--headless=new")  # navigateur invisible
        options.add_argument("--window-size=1400,1000")  # taille fixe
        options.add_argument("--disable-gpu")  # évite erreurs GPU
        options.add_argument("--no-sandbox")  # environnements restreints
        options.add_argument("--disable-dev-shm-usage")  # évite un crash mémoire
        options.add_argument(f"user-agent={REQUEST_HEADERS['User-Agent']}")  # même UA que requests

        self.driver = webdriver.Chrome(options=options)  # lance Chrome piloté
        self.wait = WebDriverWait(self.driver, 20)  # attente max 20s

        # Fenêtre des "10 dernières années" : l'année en cours n'a en général pas
        # encore d'état financier publié (ex: en 2026, on part de 2015 pour
        # obtenir les 10 derniers exercices réellement disponibles, 2015-2025).
        current_year = datetime.now().year  # année actuelle
        self.min_year = current_year - 11  # borne basse
        self.max_year = current_year  # borne haute

        ensure_database()  # crée la base si besoin
        self.db_conn = get_connection()  # ouvre la connexion
        init_schema(self.db_conn)  # crée/migre les tables
        self.source_id = get_or_create_source(self.db_conn, "CMF", CMF_URL)  # id de la source

    # ================================================================================== #
    # ÉTAPE 2 : NAVIGATION À LA PAGE WEB
    # ================================================================================== #

    # ------------------  Fonction 2 : charge la page du portail CMF -------------------
    def open_page(self):
        print("[STEP] Ouverture de la page CMF...")  # hedhi trace console
        self.driver.get(CMF_URL)  # charge la page
        self.wait.until(EC.presence_of_element_located((By.ID, SELECT_FIELD_ID)))  # menu chargé

    # ------------------  Fonction 3 : sélectionne la société (widget Chosen, repli <select> natif) -------------------
    def select_company(self, company_key):
        cmf_name = self.registry[company_key]["cmf_name"]  # nom attendu par CMF
        print(f"[STEP] Sélection de la société : {cmf_name}")  # hedhi zeda trace console

        # Le module Drupal "Chosen" génère l'id du widget en remplaçant tous les
        # tirets de l'id d'origine par des underscores (ex: edit-field-x -> edit_field_x_chosen)
        chosen_id = SELECT_FIELD_ID.replace("-", "_") + "_chosen"  # id du widget Chosen
        try:
            container = self.wait.until(EC.presence_of_element_located((By.ID, chosen_id)))  # widget JS
            container.find_element(By.CSS_SELECTOR, ".chosen-single").click()  # ouvre le menu

            search_box = self.wait.until(
                EC.visibility_of_element_located(
                    (By.CSS_SELECTOR, f"#{chosen_id} .chosen-search input")
                )
            )  # champ de recherche
            search_box.clear()  # vide le champ
            search_box.send_keys(cmf_name)  # tape le nom recherché

            options = self._wait_for_filtered_options(chosen_id)  # options filtrées
            target = self._match_option(options, cmf_name)  # option correspondante
            if target is None:
                # ferme le widget avant de basculer sur le repli natif
                container.find_element(By.CSS_SELECTOR, ".chosen-single").click()  # referme le menu
                raise NoSuchElementException(cmf_name)  # déclenche le repli

            target.click()  # sélectionne l'option
            print("[INFO] Société sélectionnée via le widget Chosen.")  # confirmation
            return  # sélection réussie
        except (TimeoutException, NoSuchElementException):
            print("[WARN] Widget Chosen indisponible, repli sur le <select> natif.")  # avertissement

        # Repli : le JS "Chosen" n'a pas chargé, on utilise le <select> natif.
        # Le <select> est display:none (masqué par Chosen), donc .text renvoie
        # une chaîne vide sur les <option> : il faut lire l'attribut "value"
        # (qui est identique au libellé pour ce champ Drupal).
        select_el = self.wait.until(EC.presence_of_element_located((By.ID, SELECT_FIELD_ID)))  # <select> natif
        select = Select(select_el)  # wrapper du select natif
        target_norm = cmf_name.strip().lower()  # normalise la casse
        for option in select.options:  # chaque option du menu
            value = (option.get_attribute("value") or "").strip()  # valeur brute
            if value.lower() == target_norm:
                select.select_by_value(value)  # sélectionne l'option
                print("[INFO] Société sélectionnée via le <select> natif.")  # confirmation
                return  # sélection réussie
        raise ValueError(f"Société introuvable dans le widget CMF : {cmf_name}")  # aucune correspondance

    # ------------------  Fonction 4 : attend que le menu affiche les résultats filtrés -------------------
    def _wait_for_filtered_options(self, chosen_id, timeout=5):
        end_time = time.time() + timeout  # borne de temps
        options = []  # options trouvées jusqu'ici
        while time.time() < end_time:  # avant expiration
            raw = self.driver.find_elements(By.CSS_SELECTOR, f"#{chosen_id} li.active-result")  # options du menu
            options = [li for li in raw if li.is_displayed()]  # garde les visibles
            if options:
                break  # arrête dès qu'il y en a
            time.sleep(0.2)  # pause avant retest
        return options  # résultat (peut être vide)

    # ------------------  Fonction 5 : trouve l'option qui correspond exactement au nom cherché -------------------
    @staticmethod
    def _match_option(options, target_text):
        target_norm = " ".join(target_text.lower().split())  # normalise espaces + casse
        for opt in options:  # 1ère passe : exacte
            if " ".join(opt.text.strip().lower().split()) == target_norm:
                return opt  # trouvé
        for opt in options:  # 2e passe : partielle
            if target_norm in " ".join(opt.text.strip().lower().split()):
                return opt  # trouvé (partiel)
        return None  # aucune correspondance

    # ------------------  Fonction 6 : clique sur "Rechercher", attend le rechargement de la page -------------------
    def click_search(self):
        print("[STEP] Clic sur 'Rechercher'...")  # trace console
        # Le formulaire de recherche déclenche un rechargement complet de la page
        # (GET classique) : on capture l'ancien contenu pour être sûr d'attendre
        # sa disparition avant de lire les nouveaux résultats (évite les
        # StaleElementReferenceException lors du parsing des lignes).
        old_content = self.driver.find_elements(By.CSS_SELECTOR, ".view-content")  # contenu avant clic
        old_marker = old_content[0] if old_content else None  # repère avant clic

        btn = self.wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input.form-submit[value='Rechercher']"))
        )  # bouton cliquable
        btn.click()  # lance la recherche

        if old_marker is not None:
            try:
                self.wait.until(EC.staleness_of(old_marker))  # ancien contenu disparu
            except TimeoutException:
                pass  # tolère, on vérifie ensuite

        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".view-content")))  # nouveau contenu chargé

    # ================================================================================== #
    # ÉTAPE 3 : EXTRACTION DES RÉSULTATS
    # ================================================================================== #

    # ------------------  Fonction 7 : lit les lignes de résultats affichées (année, période, lien PDF) -------------------
    def _parse_current_page(self):
        entries = []  # lignes exploitables
        rows = self.driver.find_elements(By.CSS_SELECTOR, "div.views-row")  # une ligne par document
        for row in rows:  # chaque ligne
            try:
                year_text = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-exercice .field-item"
                ).text.strip()  # texte de l'année
                period_text = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-p-riode .field-item"
                ).text.strip()  # texte de la période
                pdf_url = row.find_element(
                    By.CSS_SELECTOR, ".field-name-field-pdf-cf a"
                ).get_attribute("href")  # lien du PDF
            except (NoSuchElementException, StaleElementReferenceException):
                continue  # ligne invalide, ignorée
            if not year_text or not pdf_url:
                continue  # donnée manquante, ignorée
            entries.append({"year": year_text, "period": period_text, "pdf_url": pdf_url})  # ligne retenue
        return entries  # lignes de cette page

    # ------------------  Fonction 8 : passe à la page suivante des résultats, si elle existe -------------------
    def _go_to_next_page(self):
        next_links = self.driver.find_elements(By.CSS_SELECTOR, "li.pager-next a")  # lien page suivante
        if not next_links:
            return False  # dernière page atteinte
        current_rows = self.driver.find_elements(By.CSS_SELECTOR, "div.views-row")  # lignes actuelles
        anchor = current_rows[0] if current_rows else None  # repère de changement
        next_links[0].click()  # clique sur "page suivante"
        if anchor is not None:
            try:
                self.wait.until(EC.staleness_of(anchor))  # ancienne page disparue
            except TimeoutException:
                pass  # tolère, on vérifie ensuite
        try:
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".view-content")))  # nouvelle page chargée
        except TimeoutException:
            return False  # chargement trop lent
        return True  # page suivante chargée

    # ------------------  Fonction 9 : vérifie qu'un document est annuel et daté du 31/12 -------------------
    @staticmethod
    def is_annual_statement_31_12(period_text):
        text = period_text.lower()  # normalise la casse
        if any(keyword in text for keyword in INTERIM_KEYWORDS):
            return False  # document intermédiaire, exclu
        return bool(ANNUAL_31_12_PATTERN.search(text))  # vrai si "31/12" présent

    # ------------------  Fonction 10 : parcourt toutes les pages, applique le filtre, garde 10-11 ans -------------------
    def collect_annual_statements(self, max_pages=30):
        """Parcourt toutes les pages de résultats et renvoie {annee: pdf_url}
        pour les états financiers annuels au 31/12 dans la fenêtre des 10
        dernières années."""
        collected = {}  # résultat : année -> lien
        for _ in range(max_pages):  # garde-fou anti-boucle
            for entry in self._parse_current_page():  # lignes de la page
                if not self.is_annual_statement_31_12(entry["period"]):
                    continue  # garde annuels au 31/12
                match = re.search(r"\d{4}", entry["year"])  # année à 4 chiffres
                if not match:
                    continue  # année illisible, ignorée
                year = int(match.group())  # année en entier
                if not (self.min_year <= year <= self.max_year):
                    continue  # hors fenêtre d'années
                # garde la première occurrence rencontrée (la plus récemment publiée)
                collected.setdefault(year, entry["pdf_url"])  # n'écrase pas si déjà présent
            if not self._go_to_next_page():
                break  # fin de pagination
        return collected  # résultat final

    # ================================================================================== #
    # ÉTAPE 4 : VÉRIFICATION DU LIEN ET ENREGISTREMENT EN BASE
    # ================================================================================== #

    # ------------------  Fonction 11 : vérifie que le lien PDF répond (HEAD, repli GET) -------------------
    def _verify_pdf_link(self, url, retries=2, timeout=15):
        """Vérifie que le lien pointe bien vers un PDF accessible, sans
        conserver son contenu."""
        for attempt in range(1, retries + 1):  # jusqu'à `retries` tentatives
            try:
                response = requests.head(
                    url, headers=REQUEST_HEADERS, timeout=timeout, allow_redirects=True
                )  # vérifie sans télécharger
                if response.status_code == 200:
                    return True  # lien valide
                # Certains serveurs ne gèrent pas HEAD correctement -> repli GET
                response = requests.get(
                    url, headers=REQUEST_HEADERS, timeout=timeout, stream=True
                )  # ne charge pas tout en mémoire
                ok = response.status_code == 200  # réponse correcte ?
                response.close()  # ferme sans tout lire
                return ok  # résultat du repli GET
            except requests.RequestException as exc:
                print(f"[WARN] Tentative {attempt}/{retries} échouée pour {url} : {exc}")  # avertissement
                time.sleep(1.5)  # pause avant retry
        return False  # toutes les tentatives ont échoué

    # ------------------  Fonction 12 : déduplique et enregistre les métadonnées en base -------------------
    def extract_and_store(self, company_key):
        print("[STEP] Extraction des lignes et enregistrement en base (10 dernières années)...")  # trace console
        statements = self.collect_annual_statements()  # {annee: pdf_url} filtré

        cmf_name = self.registry[company_key]["cmf_name"]  # nom de la société
        cmf_id = get_or_create_company(self.db_conn, company_key, cmf_name)  # id de la société

        saved = 0  # compteur enregistrés
        for year in sorted(statements):  # ordre chronologique
            pdf_url = statements[year]  # lien du PDF
            if document_exists(self.db_conn, self.source_id, cmf_id, year):
                print(f"[INFO] Déjà en base : {company_key} {year}")  # info console
                continue  # déduplication
            if not self._verify_pdf_link(pdf_url):
                print(f"[WARN] Lien PDF invalide, ignoré : {pdf_url}")  # avertissement
                continue  # lien mort, ignoré
            nom_pdf = f"{company_key}_{year}.pdf"  # nom construit, pas le fichier
            save_document(self.db_conn, self.source_id, cmf_id, nom_pdf, year, pdf_url)  # écrit les métadonnées
            saved += 1  # +1 enregistré
            print(f"[OK] Enregistré en base : {nom_pdf}")  # confirmation

        total = count_documents(self.db_conn, cmf_id)  # total cumulé
        print(f"[INFO] {saved} nouveau(x) document(s) pour {company_key} ({total} au total en base)")  # résumé
        return saved  # documents ajoutés

    # ================================================================================== #
    # ÉTAPE 5 : PIPELINE COMPLET POUR UNE SOCIÉTÉ
    # ================================================================================== #

    # ------------------  Fonction 13 : orchestre tout le déroulé, relance ×3 en cas de timeout -------------------
    def run(self, company_key, retries=3):
        """Comme _verify_pdf_link : le portail CMF peut occasionnellement ne
        pas charger a temps (page lente, widget Chosen pas encore pret) ->
        on relance la sequence complete (page fraiche) plutot qu'une seule
        etape, car un TimeoutException en cours de route laisse le driver
        dans un etat intermediaire non reutilisable."""
        last_exc = None  # mémorise la dernière erreur
        for attempt in range(1, retries + 1):  # jusqu'à `retries` tentatives
            try:
                self.open_page()  # étape 1 : charger la page
                self.select_company(company_key)  # étape 2 : sélectionner la société
                self.click_search()  # étape 3 : lancer la recherche
                return self.extract_and_store(company_key)  # étape 4 : filtrer + dédupliquer + enregistrer
            except TimeoutException as exc:
                last_exc = exc  # mémorise l'erreur
                print(f"[WARN] Tentative {attempt}/{retries} echouee pour {company_key} (page CMF) : {exc}")  # avertissement
                if attempt < retries:
                    time.sleep(2)  # pause avant relance
        raise last_exc  # échec final, relève l'erreur

    # ------------------  Fonction 14 : ferme le navigateur Chrome et la connexion base -------------------
    def close(self):
        try:
            self.driver.quit()  # ferme Chrome
        except Exception:
            pass  # sans conséquence
        try:
            self.db_conn.close()  # ferme la connexion
        except Exception:
            pass  # sans conséquence
