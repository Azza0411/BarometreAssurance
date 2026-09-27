import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars")
o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
D = "docs/scratch/pipeline_shots/"
def shot(name): d.save_screenshot(D + name + ".png"); print("saved", name)
try:
    # 1 traceability with a company whose 4-column layout is standard
    d.get("http://localhost:5173/kpi-detail?code=ASTREE&kpi=Total%20actif&annee=2025"); time.sleep(6)
    b = d.find_elements(By.XPATH, "//button[contains(., 'Localiser dans le PDF')]")
    if b: b[0].click(); time.sleep(9)
    shot("hl_astree")
    # 2 gestion des donnees
    d.get("http://localhost:5173/gestion-donnees"); time.sleep(7); shot("gestion")
    # 3 qualite
    d.get("http://localhost:5173/qualite-donnees"); time.sleep(7); shot("qualite")
    # 4 anomalies
    d.get("http://localhost:5173/anomalies-systeme"); time.sleep(8); shot("anomalies")
    # 5 rapport pipeline (slow analysis)
    d.get("http://localhost:5173/rapport-pipeline"); 
    for _ in range(30):
        time.sleep(2)
        if "Analyse du pipeline" not in d.find_element(By.TAG_NAME, "body").text: break
    time.sleep(2); shot("rapport")
    # 6 real pipeline run report (HTML written by run_pipeline.py)
    d.get("file:///C:/Users/HP/Desktop/SCRAPING/reports/pipeline_run_20260915_161522.html"); time.sleep(2); shot("run_report")
finally:
    d.quit()
