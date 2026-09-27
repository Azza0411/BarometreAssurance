import sys, time, re
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1000")
d = webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/gestion-donnees"); time.sleep(10)
    t = d.execute_script("return document.body.innerText")
    print(len(t))
    for m in re.finditer(r"STAR|TUNISIENNE D.ASSURANCES ET DE R", t):
        print(m.start(), repr(t[max(0, m.start()-60): m.start()+90]))
    print(t[-1500:])
finally:
    d.quit()
