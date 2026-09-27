import sys, time, re
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/gestion-donnees"); time.sleep(9)
    for page in range(3):
        t = d.execute_script("return document.body.innerText")
        hits = [m.start() for m in re.finditer(r"- STAR|STAR\b", t)]
        print("page", page + 1, "hits", len(hits))
        els = d.find_elements(By.XPATH, "//*[contains(text(),'STAR') and not(self::button) and not(self::img) and not(self::option)]")
        if els:
            e = els[-1]
            print(e.tag_name, repr(e.text[:100]))
            d.execute_script("arguments[0].scrollIntoView({block:'center'})", e); time.sleep(1)
            row = e
            for _ in range(6):
                if row.size["width"] > 900: break
                row = row.find_element(By.XPATH, "./..")
            print("row", row.size, repr(row.text[:200]))
            row.screenshot("docs/scratch/star/gestion_star_row.png")
            break
        nxt = d.find_elements(By.XPATH, "//button[contains(., 'Suivant')]")
        if not nxt: break
        d.execute_script("arguments[0].scrollIntoView({block:'center'})", nxt[0]); time.sleep(0.5)
        d.execute_script("arguments[0].click()", nxt[0]); time.sleep(2)
finally:
    d.quit()
