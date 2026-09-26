import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/kpi-detail?code=STAR&kpi=Ratio%20combin%C3%A9%20(%25)&annee=2025"); time.sleep(8)
    d.save_screenshot("docs/scratch/star/formula_star.png"); print("saved")
finally:
    d.quit()
