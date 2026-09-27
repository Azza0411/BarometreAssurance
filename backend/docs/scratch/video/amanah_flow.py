import time,sys
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.common.by import By
KPI=sys.argv[1] if len(sys.argv)>1 else "RATIO COMBINÉ"; ITEM=sys.argv[2] if len(sys.argv)>2 else "Voir le document source"; TAG=sys.argv[3] if len(sys.argv)>3 else "a"
o=webdriver.ChromeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1700,1100"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=1")
d=webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/fiches"); time.sleep(8)
    d.find_element(By.XPATH,"//button[.//img[@alt='STAR']]").click(); time.sleep(1)
    d.find_element(By.XPATH,"//button[normalize-space()='El Amana Takaful']").click(); time.sleep(5)
    t=d.find_elements(By.XPATH,"//*[normalize-space(text())='%s']"%KPI)[0]; b=None
    for _ in range(4):
        bs=t.find_elements(By.CSS_SELECTOR,"button.kpi-opts-btn")
        if bs: b=bs[0]; break
        t=t.find_element(By.XPATH,"./..")
    b.click(); time.sleep(1)
    d.find_element(By.XPATH,"//button[contains(., '%s')]"%ITEM).click(); time.sleep(9)
    print(d.current_url); d.save_screenshot("docs/scratch/video/amflow_%s.png"%TAG)
    print(d.execute_script("return document.body.innerText").replace("\n"," | ")[:1400])
finally: d.quit()
