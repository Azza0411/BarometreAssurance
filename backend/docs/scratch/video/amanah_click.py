import time,sys
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.common.by import By
ANNEE=sys.argv[1]; KPI=sys.argv[2]
o=webdriver.ChromeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1100"); o.add_argument("--hide-scrollbars")
d=webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/kpi-detail?code=AL_AMANAH_TAKAFUL&kpi=%s&annee=%s"%(KPI,ANNEE)); time.sleep(8)
    chips=d.find_elements(By.XPATH,"//button[.//text()[contains(.,'TND')]]")
    print("chips:",[c.text.replace("\n"," ") for c in chips][:8])
    for i,c in enumerate(chips[:3]):
        c.click(); time.sleep(9)
        d.save_screenshot("docs/scratch/video/amclick_%s_%d.png"%(ANNEE,i))
        print(i, d.execute_script("return document.body.innerText").replace("\n"," | ")[-700:])
finally: d.quit()
