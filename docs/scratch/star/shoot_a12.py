import sys, time, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
D = "docs/scratch/star/"
try:
    kpi = urllib.parse.quote("Charges d'acquisition et de gestion nettes Vie")
    d.get(f"http://localhost:5173/kpi-detail?code=STAR&kpi={kpi}&annee=2024"); time.sleep(8)
    b = d.find_elements(By.XPATH, "//button[contains(., 'Localiser dans le PDF')]")
    print("locate btn", len(b))
    if b: b[0].click(); time.sleep(10)
    d.save_screenshot(D + "a12_kpi_star2024.png"); print("saved")
    print(d.execute_script("return document.body.innerText")[:700])
    # formula page for the expense ratio
    kpi2 = urllib.parse.quote("Ratio de frais de gestion (%)")
    d.get(f"http://localhost:5173/kpi-detail?code=STAR&kpi={kpi2}&annee=2024"); time.sleep(8)
    d.save_screenshot(D + "frais_star2024.png"); print("saved formula")
finally:
    d.quit()
