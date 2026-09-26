import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/gestion-donnees"); time.sleep(8)
    els = d.find_elements(By.XPATH, "//*[contains(text(),'STAR') and not(self::button) and not(self::img)]")
    print("candidates", len(els))
    for i, e in enumerate(els):
        print(i, e.tag_name, repr(e.text[:80]), e.location)
    # pick the one that is in the document list (largest y)
    target = None
    for e in els:
        if "REASSURANCES - STAR" in e.text.upper().replace("É", "E") or e.text.strip().upper().endswith("STAR") or "STAR" in e.text.upper():
            target = e
    if target is not None:
        d.execute_script("arguments[0].scrollIntoView({block:'center'})", target); time.sleep(1)
        row = target
        for _ in range(3):
            row = row.find_element(By.XPATH, "./..")
        print("row size", row.size)
        row.screenshot("docs/scratch/star/gestion_star_row.png")
        print("saved")
finally:
    d.quit()
