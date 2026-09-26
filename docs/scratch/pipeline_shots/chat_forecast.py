import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1500,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/qualite-donnees"); time.sleep(6)
    d.find_element(By.CSS_SELECTOR, "button[title='Assistant IA']").click(); time.sleep(4)
    inp = d.find_element(By.CSS_SELECTOR, ".chat-input"); inp.click()
    inp.send_keys("Quelle sera la part de marché de STAR en 2026 ?"); inp.send_keys(Keys.ENTER)
    time.sleep(25)
    els = d.find_elements(By.XPATH, "//*[normalize-space(text())='Prévision' or starts-with(normalize-space(text()),'Prévision')]")
    print("found", len(els))
    if els:
        d.execute_script("arguments[0].scrollIntoView({block:'start'})", els[-1]); time.sleep(1)
    sc = d.find_element(By.CSS_SELECTOR, ".chat-scroll"); panel = sc.find_element(By.XPATH, "./..")
    print(panel.text[-1200:])
    panel.screenshot("docs/scratch/pipeline_shots/chat_forecast.png")
finally:
    d.quit()
