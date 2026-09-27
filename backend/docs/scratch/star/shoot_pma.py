import sys, time, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
try:
    sql = ("SELECT tableau, regle_code, colonne, attendu, trouve, ecart, statut FROM regles_validations "
           "WHERE document_id=67 AND tableau='annexe12' AND regle_code='charges_acquisition_gestion'")
    url = "http://localhost/phpmyadmin/index.php?route=/sql&db=MarketInsurance&sql_query=" + urllib.parse.quote(sql)
    d.get(url); time.sleep(6)
    print(d.title)
    print(d.execute_script("return document.body.innerText")[:600])
    d.save_screenshot("docs/scratch/star/pma.png")
finally:
    d.quit()
