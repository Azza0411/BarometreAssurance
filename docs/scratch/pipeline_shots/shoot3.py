import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars")
d = webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/kpi-detail?code=ATTIJARI&kpi=Total%20actif&annee=2024"); time.sleep(6)
    btn = d.find_elements(By.XPATH, "//button[contains(., 'Localiser dans le PDF')]")
    print("btn", len(btn))
    if btn:
        btn[0].click(); time.sleep(9)
    d.save_screenshot("docs/scratch/pipeline_shots/kpi_pdf_highlight.png")
finally:
    d.quit()
