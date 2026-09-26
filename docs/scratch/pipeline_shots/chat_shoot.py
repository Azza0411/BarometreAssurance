import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1500,1000"); o.add_argument("--hide-scrollbars")
o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
D = "docs/scratch/pipeline_shots/"
def panel():
    sc = d.find_element(By.CSS_SELECTOR, ".chat-scroll")
    return sc.find_element(By.XPATH, "./..")
try:
    d.get("http://localhost:5173/qualite-donnees"); time.sleep(6)
    d.find_element(By.CSS_SELECTOR, "button[title='Assistant IA']").click(); time.sleep(4)
    print("PANEL START:\n", panel().text[:600], "\n-----")
    panel().screenshot(D + "chat_start.png")
    inp = d.find_element(By.CSS_SELECTOR, ".chat-input")
    qs = sys.argv[1:]
    for i, q in enumerate(qs, 1):
        inp = d.find_element(By.CSS_SELECTOR, ".chat-input")
        inp.click(); inp.send_keys(q); inp.send_keys(Keys.ENTER)
        last = ""
        for _ in range(40):
            time.sleep(2)
            t = panel().text
            if t == last and len(t) > 0 and time.time():
                stable = True
            else:
                stable = False
            last = t
            if stable and "…" not in t[-40:] and "..." not in t[-40:]:
                break
        time.sleep(2)
        print(f"PANEL AFTER Q{i}:\n", panel().text[-900:], "\n-----")
        panel().screenshot(D + f"chat_q{i}.png")
finally:
    d.quit()
