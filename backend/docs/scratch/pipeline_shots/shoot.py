import sys, time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

routes = sys.argv[1:]
o = Options()
o.add_argument("--headless=new"); o.add_argument("--window-size=1600,1000"); o.add_argument("--hide-scrollbars")
d = webdriver.Chrome(options=o)
try:
    for r in routes:
        name = r.strip("/").replace("/", "_") or "root"
        d.get("http://localhost:5173/" + r.strip("/"))
        time.sleep(6)
        out = f"docs/scratch/pipeline_shots/{name}.png"
        d.save_screenshot(out)
        print("saved", out, d.title)
finally:
    d.quit()
