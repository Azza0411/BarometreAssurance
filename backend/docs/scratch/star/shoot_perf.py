import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/fiches"); time.sleep(7)
    els = d.find_elements(By.XPATH, "//*[normalize-space(text())='Performance financière']")
    print("tab", len(els))
    if els: els[0].click(); time.sleep(6)
    d.save_screenshot("docs/scratch/star/perf_star.png"); print("saved")
    print(d.execute_script("return document.body.innerText")[:900])
finally:
    d.quit()
