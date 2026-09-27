import time,sys
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.common.by import By
o=webdriver.ChromeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1700,2200"); o.add_argument("--hide-scrollbars")
d=webdriver.Chrome(options=o)
try:
    d.get("http://localhost:5173/fiches"); time.sleep(8)
    d.find_element(By.XPATH,"//button[.//img[@alt='STAR']]").click(); time.sleep(1)
    d.find_element(By.XPATH,"//button[normalize-space()='El Amana Takaful' or .//span[normalize-space()='El Amana Takaful']]").click(); time.sleep(5)
    d.save_screenshot("docs/scratch/video/am_profil.png")
    print(d.execute_script("return document.body.innerText").replace("\n"," | ")[:1500])
    d.find_element(By.XPATH,"//*[normalize-space()='Performance financière']").click(); time.sleep(5)
    d.save_screenshot("docs/scratch/video/am_perf.png")
    print("PERF:",d.execute_script("return document.body.innerText").replace("\n"," | ")[:2500])
finally: d.quit()
