import sys, time, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
D = "docs/scratch/video/"
try:
    kpi = urllib.parse.quote("Résultat technique (TND)")
    d.get(f"http://localhost:5173/kpi-detail?code=STAR&kpi={kpi}&annee=2024"); time.sleep(8)
    for i, label in enumerate(["Résultat technique Vie", "Résultat technique Non-Vie"]):
        chips = d.find_elements(By.XPATH, f"//button[contains(., '{label}')]")
        print(label, "chips:", len(chips))
        chips[0].click(); time.sleep(9)
        d.save_screenshot(D + f"rt_click_{i}.png")
        print(d.execute_script("return document.body.innerText")[:900].replace("\n", " | "))
finally:
    d.quit()
