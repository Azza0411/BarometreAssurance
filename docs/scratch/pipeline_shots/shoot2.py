import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1600,1000"); o.add_argument("--hide-scrollbars")
d = webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/qualite-donnees"); time.sleep(6)
    els = d.find_elements(By.XPATH, "//*[normalize-space(text())='881,1M']")
    print("found", len(els))
    if els:
        d.execute_script("arguments[0].scrollIntoView({block:'center'})", els[0]); time.sleep(1)
        els[0].click(); time.sleep(7)
    d.save_screenshot("docs/scratch/pipeline_shots/qualite_click.png")
    print(d.current_url, len(d.window_handles))
finally:
    d.quit()
