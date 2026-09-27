import sys,time
sys.stdout.reconfigure(encoding="utf-8")
from selenium import webdriver
from selenium.webdriver.common.by import By
O="docs/scratch/star/crops/"

def bar_card(title, rows, forecast_label, forecast_value, w=1000):
    bars=""
    for name,mape,rmse,score,win in rows:
        pct=max(min(mape,100),11)
        bg="#484B54" if win else "#D8D8DE"
        fg="#fff" if win else "#3A3A3A"
        tag=" &nbsp;<span style='color:#0f7b43'>&#10003; selected</span>" if win else ""
        bars+=f"""<div class='lab'>{name}{tag}</div><div class='bar' style='width:{pct}%;background:{bg};color:{fg}'>MAPE {mape:.2f} %</div><div class='sm'>RMSE {rmse:.3f} &middot; score {score:.4f}</div>"""
    return f"""<html><head><meta charset='utf-8'><style>body{{margin:0;background:#fff;font-family:'Segoe UI',Arial,sans-serif}}
.c{{width:{w}px;box-sizing:border-box;border:1px solid #e3e6ee;border-radius:14px;padding:22px 26px;background:#fff}}
.k{{font-size:11px;letter-spacing:1.6px;color:#8b8b90;font-weight:700;text-transform:uppercase;margin-bottom:14px}}
.lab{{font-size:14px;font-weight:700;color:#26282f;margin:10px 0 5px}}.bar{{height:26px;min-width:110px;border-radius:6px;display:flex;align-items:center;padding-left:10px;font-weight:700;font-size:13px;white-space:nowrap}}
.sm{{font-size:12.5px;color:#5a5d66}}.fc{{margin-top:16px;font-size:14px;color:#26282f}}.fc b{{background:#FFE600;padding:2px 10px;border-radius:6px}}
</style></head><body><div id='c' class='c'><div class='k'>{title}</div>{bars}<div class='fc'>Forecast 2026 (winner) : <b>{forecast_label} {forecast_value}</b></div></div></body></html>"""

xgb_card = bar_card("Model competition &middot; R&eacute;sultat Net &middot; STAR &middot; time-series cross-validation",
    [("XGBoost",18.12,5.307,13.0007,True),("Prophet",96.45,23.685,67.8167,False)], "", "31,59 MDT")
pro_card = bar_card("Model competition &middot; Total actif &middot; COMAR &middot; time-series cross-validation",
    [("Prophet",1.61,15.807,1.4418,True),("XGBoost",8.14,81.296,6.0019,False)], "", "1 211,63 MDT")

D="docs/scratch/video/"
open(D+"pred_xgb.html","w",encoding="utf-8").write(xgb_card)
open(D+"pred_pro.html","w",encoding="utf-8").write(pro_card)

o=webdriver.ChromeOptions(); o.add_argument("--headless=new"); o.add_argument("--window-size=1200,700"); o.add_argument("--hide-scrollbars"); o.add_argument("--force-device-scale-factor=2")
d=webdriver.Chrome(options=o)
try:
    for n in ("pred_xgb","pred_pro"):
        d.get("file:///C:/Users/HP/Desktop/SCRAPING/docs/scratch/video/%s.html"%n); time.sleep(.8)
        d.find_element(By.ID,"c").screenshot(O+n+".png")
finally: d.quit()
from PIL import Image
for n in ("pred_xgb","pred_pro"): print(n, Image.open(O+n+".png").size)
