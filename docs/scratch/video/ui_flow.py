import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
D = "docs/scratch/video/"
def tile_button():
    # the "i" button of the RÉSULTAT TECHNIQUE tile
    tiles = d.find_elements(By.XPATH, "//*[normalize-space(text())='RÉSULTAT TECHNIQUE' or normalize-space(text())='Résultat technique']")
    print("tiles:", len(tiles))
    t = tiles[0]
    for _ in range(4):
        btns = t.find_elements(By.CSS_SELECTOR, "button.kpi-opts-btn")
        if btns: return btns[0]
        t = t.find_element(By.XPATH, "./..")
    return None
try:
    d.get("http://localhost:5173/fiches"); time.sleep(8)
    print("header:", d.execute_script("return document.body.innerText")[400:560].replace("\n", " | "))
    b = tile_button(); print("button found:", b is not None)
    d.execute_script("arguments[0].scrollIntoView({block:'center'})", b); time.sleep(1)
    b.click(); time.sleep(1)
    d.save_screenshot(D + "menu_open.png")
    items = d.find_elements(By.XPATH, "//button[contains(., 'Expliquer ce chiffre')]")
    print("explain items:", len(items))
    items[0].click(); time.sleep(20)
    d.save_screenshot(D + "explain_chat.png")
    panel = d.find_element(By.CSS_SELECTOR, ".chat-scroll").find_element(By.XPATH, "./..")
    print("CHAT:", panel.text[-700:].replace("\n", " | "))
    # source document path
    d.get("http://localhost:5173/fiches"); time.sleep(8)
    b = tile_button(); d.execute_script("arguments[0].scrollIntoView({block:'center'})", b); time.sleep(1); b.click(); time.sleep(1)
    src = d.find_elements(By.XPATH, "//button[contains(., 'Voir le document source')]")
    print("source items:", len(src)); src[0].click(); time.sleep(8)
    print("URL after source click:", d.current_url)
finally:
    d.quit()
