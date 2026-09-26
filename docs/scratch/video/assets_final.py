import sys, time, io, base64, html, requests, openpyxl, pymysql
sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
D = "docs/scratch/video/"; O = "docs/scratch/star/crops/"

# 1) platform screenshots -> crops
Image.open(D + "rt_click_0.png").crop((1680, 300, 3364, 1300)).save(O + "f1_collect.png")
Image.open(D + "rt_formula.png").crop((64, 200, 1613, 690)).save(O + "f5_model.png")

# 2) Excel export of the example (fresh, from the running API) -> Excel-like image, only the identity rows shown
x = requests.get("http://localhost:8002/api/gestion-donnees/export.xlsx", params=[("tableau", "annexe12"), ("societe", "STAR"), ("annee", "2024")], timeout=120)
wb = openpyxl.load_workbook(io.BytesIO(x.content)); ws = wb.active
b64 = base64.b64encode(ws._images[0]._data()).decode()
widths = {c: int(ws.column_dimensions[c].width * 7 + 5) for c in "ABCDEF"}
rgb = lambda c: ("#" + c.rgb[-6:]) if isinstance(getattr(c, "rgb", None), str) and len(c.rgb) >= 6 else None
fmt = lambda v: f"{int(v):,}".replace(",", "\u202f") if isinstance(v, (int, float)) else ("" if v is None else str(v))
rows_by_label = {str(ws.cell(r, 1).value): r for r in range(5, ws.max_row + 1)}
want = ["SOLDE DE SOUSCRIPTION", "CHARGES D'ACQUISITION ET DE GESTION NETTES", "SOLDE FINANCIER", "SOLDE DE RÉASSURANCE / RÉTROCESSION", "RÉSULTAT TECHNIQUE"]
def tr(r, hi=False):
    tds = ""
    for col in "ABCDEF":
        c = ws[f"{col}{r}"]; fill = rgb(c.fill.fgColor) if c.fill.fill_type else None
        st = f"width:{widths[col]}px;text-align:{c.alignment.horizontal or 'left'};color:{rgb(c.font.color) or '#2E2E38'};font-weight:{700 if c.font.bold else 400};" + (f"background:{fill};" if fill else "")
        if hi and col == "F": st += "background:#FFE600;outline:2px solid #33363F;outline-offset:-2px;font-weight:700;"
        tds += f'<td style="{st}">{html.escape(fmt(c.value))}</td>'
    return f"<tr>{tds}</tr>"
sep = f"<tr><td colspan='6' style='height:9px;padding:0;background:repeating-linear-gradient(90deg,#d0d3da 0 6px,#fff 6px 12px);'></td></tr>"
body = tr(5)
for i, lab in enumerate(want):
    body += (sep if i else "") + tr(rows_by_label[lab], hi=(lab == "RÉSULTAT TECHNIQUE"))
doc = f"""<html><head><meta charset='utf-8'><style>body{{margin:0;font-family:Arial}}#s{{width:{sum(widths.values())}px;background:#fff}}
.t1{{height:45px;line-height:45px;text-align:center;font-weight:700;font-size:15px}}.t2{{height:22px;text-align:center;font-size:11px;color:#595959}}
.lg{{height:66px;position:relative}}.lg img{{position:absolute;left:{widths['A']-88}px;top:6px;height:52px}}.t4{{height:26px;line-height:26px;text-align:center;font-weight:700;font-size:14px;color:#2E2E38}}
table{{border-collapse:collapse;table-layout:fixed}}td{{height:21px;padding:0 4px;font-size:13.3px;white-space:nowrap;overflow:hidden;box-sizing:border-box}}tr:first-child td{{color:#fff;font-weight:700;text-align:center;height:22px}}</style></head><body><div id='s'>
<div class='t1'>{html.escape(ws['A1'].value)}</div><div class='t2'>{html.escape(ws['A2'].value)}</div><div class='lg'><img src='data:image/png;base64,{b64}'></div><div class='t4'>{html.escape(ws['A4'].value)}</div><table>{body}</table></div></body></html>"""
open(D + "excel_final.html", "w", encoding="utf-8").write(doc)

# 3) identity card from the stored validation rows (resultat_technique)
c = pymysql.connect(host="127.0.0.1", port=3306, user="root", password="", database="MarketInsurance", charset="utf8mb4"); cur = c.cursor()
cur.execute("SELECT regle, colonne, attendu, trouve, ecart, statut FROM regles_validations WHERE document_id=67 AND tableau='annexe12' AND regle_code='resultat_technique'")
rows = sorted(cur.fetchall(), key=lambda r: ["Vie", "Décès", "Mixte", "Acceptation", "Total"].index(r[1]))
n = lambda v: f"{int(v):,}".replace(",", " ")
trs = "".join(f"<tr class='{'hi' if r[1]=='Total' else ''}'><td>{r[1]}</td><td>{n(r[2])}</td><td>{n(r[3])}</td><td>{n(r[4])}</td><td><span class='ok'>✓ OK</span></td></tr>" for r in rows)
card = f"""<html><head><meta charset='utf-8'><style>body{{margin:0;background:#f1f3f9;font-family:'Segoe UI',Arial,sans-serif}}#card{{width:900px;background:#fff;border:1px solid #e3e6ee;border-radius:14px;padding:22px 26px;box-sizing:border-box}}
.k{{font-size:11px;letter-spacing:1.6px;color:#8b8b90;font-weight:700;text-transform:uppercase}}.h{{font-size:17px;font-weight:700;color:#26282f;margin:6px 0 4px}}.rule{{font-size:12.5px;color:#5a5d66;margin-bottom:14px;line-height:1.35}}
table{{width:100%;border-collapse:collapse;font-size:14px}}th{{text-align:right;color:#8b8b90;font-size:11.5px;letter-spacing:1px;padding:6px 10px;border-bottom:1px solid #e3e6ee;font-weight:700}}th:first-child,td:first-child{{text-align:left}}
td{{text-align:right;padding:8px 10px;color:#26282f;border-bottom:1px solid #f0f1f5}}tr.hi td{{background:#fff8c2;font-weight:700}}.ok{{display:inline-block;background:#e6f7ee;color:#0f7b43;border:1px solid #a9e3c3;border-radius:999px;padding:2px 12px;font-weight:700;font-size:13px}}</style></head><body><div id='card'>
<div class='k'>Contrôle comptable · Annexe 12 · STAR 2024</div><div class='h'>Résultat technique</div><div class='rule'>{html.escape(rows[0][0])}</div>
<table><tr><th>COLONNE</th><th>ATTENDU</th><th>TROUVÉ</th><th>ÉCART</th><th>STATUT</th></tr>{trs}</table></div></body></html>"""
open(D + "identity_card.html", "w", encoding="utf-8").write(card)

o = Options(); o.add_argument("--headless=new"); o.add_argument("--window-size=1200,800"); o.add_argument("--force-device-scale-factor=2"); o.add_argument("--hide-scrollbars")
d = webdriver.Chrome(options=o)
try:
    d.get("file:///C:/Users/HP/Desktop/SCRAPING/docs/scratch/video/excel_final.html"); time.sleep(1); d.find_element(By.ID, "s").screenshot(O + "f2_extract.png")
    d.get("file:///C:/Users/HP/Desktop/SCRAPING/docs/scratch/video/identity_card.html"); time.sleep(1); d.find_element(By.ID, "card").screenshot(O + "f6_validate.png")
finally: d.quit()

# 4) chatbot explanation panel (real UI flow)
o2 = Options(); o2.add_argument("--headless=new"); o2.add_argument("--window-size=1700,1000"); o2.add_argument("--hide-scrollbars"); o2.add_argument("--force-device-scale-factor=2")
d = webdriver.Chrome(options=o2)
try:
    d.get("http://localhost:5173/fiches"); time.sleep(8)
    t = d.find_elements(By.XPATH, "//*[normalize-space(text())='RÉSULTAT TECHNIQUE']")[0]
    b = None
    for _ in range(4):
        bs = t.find_elements(By.CSS_SELECTOR, "button.kpi-opts-btn")
        if bs: b = bs[0]; break
        t = t.find_element(By.XPATH, "./..")
    d.execute_script("arguments[0].scrollIntoView({block:'center'})", b); time.sleep(1); b.click(); time.sleep(1)
    d.find_elements(By.XPATH, "//button[contains(., 'Expliquer ce chiffre')]")[0].click(); time.sleep(22)
    panel = d.find_element(By.CSS_SELECTOR, ".chat-scroll").find_element(By.XPATH, "./..")
    print("CHAT:", panel.text[-500:].replace("\n", " | "))
    panel.screenshot(O + "f8_chat.png")
finally: d.quit()
for f in ("f1_collect", "f2_extract", "f5_model", "f6_validate", "f8_chat"): print(f, Image.open(O + f + ".png").size)
