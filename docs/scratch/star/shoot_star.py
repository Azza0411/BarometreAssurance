import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
D = "docs/scratch/star/"
def shot(n): d.save_screenshot(D + n + ".png"); print("saved", n)
try:
    # 1 KPI detail + PDF highlight, STAR 2025 and 2024
    for yr in (2025, 2024):
        d.get(f"http://localhost:5173/kpi-detail?code=STAR&kpi=Total%20actif&annee={yr}"); time.sleep(6)
        b = d.find_elements(By.XPATH, "//button[contains(., 'Localiser dans le PDF')]")
        print(yr, "btn", len(b))
        if b: b[0].click(); time.sleep(9)
        shot(f"hl_star_{yr}")
    # 2 Qualite with STAR search
    d.get("http://localhost:5173/qualite-donnees"); time.sleep(7)
    inp = d.find_elements(By.CSS_SELECTOR, "input[placeholder^='Rechercher']")
    print("search", len(inp))
    if inp: inp[0].send_keys("STAR"); time.sleep(3)
    shot("qualite_star")
    # 3 Gestion des donnees: click STAR logo
    d.get("http://localhost:5173/gestion-donnees"); time.sleep(7)
    imgs = d.find_elements(By.XPATH, "//img[contains(@src,'STAR')]")
    print("star imgs", len(imgs))
    if imgs:
        d.execute_script("arguments[0].scrollIntoView({block:'center'})", imgs[0]); time.sleep(1)
        d.execute_script("arguments[0].click()", imgs[0]); time.sleep(4)
    shot("gestion_star")
    # 4 Anomalies 2025
    d.get("http://localhost:5173/anomalies-systeme"); time.sleep(8)
    s = d.find_elements(By.CSS_SELECTOR, "input[placeholder^='Rechercher']")
    if s: s[0].send_keys("STAR"); time.sleep(3)
    shot("anomalies_star")
    # 5 Fiches entreprises
    d.get("http://localhost:5173/fiches"); time.sleep(7); shot("fiches")
finally:
    d.quit()
