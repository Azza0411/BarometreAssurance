import sys, time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
O = "docs/scratch/star/crops/"
QS = {"ai_sql": "Combien de compagnies ont un ratio combiné inférieur à 100 % en 2024 ?",
      "ai_fc": "Quel sera le résultat net de STAR en 2026 ?",
      "ai_ols": "Quelle sera la part de marché de STAR en 2026 ?",
      "ai_rag": "Quel est le capital minimum requis pour une compagnie d'assurance ?",
      "ai_refuse": "Quelle est la prime moyenne des compagnies Takaful en 2022 ?"}
o = Options(); o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1500"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o)
try:
    for name, q in QS.items():
        d.get("http://localhost:5173/"); time.sleep(6)
        d.execute_script("localStorage.clear();sessionStorage.clear()")
        d.find_element(By.CSS_SELECTOR, "button[title='Assistant IA']").click(); time.sleep(1.5)
        inp = d.find_element(By.CSS_SELECTOR, "input.chat-input, textarea.chat-input"); inp.click(); inp.send_keys(q); time.sleep(.5)
        from selenium.webdriver.common.keys import Keys
        inp.send_keys(Keys.ENTER); time.sleep(28 if name != "ai_rag" else 30)
        d.execute_script("""const sc=document.querySelector('.chat-scroll');let p=sc.parentElement;p.style.height='1000px';p.style.maxHeight='1000px';"""); time.sleep(.5)
        d.execute_script("""const s=document.querySelector('.chat-scroll');const els=[...s.querySelectorAll('*')].filter(e=>e.children.length==0&&e.textContent.trim()==='VOUS');if(els.length){els[els.length-1].scrollIntoView({block:'start'});s.scrollTop-=14;}""")
        time.sleep(1)
        panel = d.find_element(By.CSS_SELECTOR, ".chat-scroll").find_element(By.XPATH, "./..")
        panel.screenshot(O + name + ".png"); print(name, panel.size, panel.text[-160:].replace("\n"," | "))
finally: d.quit()
