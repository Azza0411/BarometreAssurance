import { useState, useEffect } from "react";
import ReactApexChart from "react-apexcharts";
import { gouvernorats } from "../data/mockData";
import { C, barH } from "../utils/chartTheme";
import PageHeaderBar from "../components/PageHeaderBar";
import { DS, DsCard, DsTitle, DsBanner, DsSource } from "../components/Ds";

const D = DS.dark;
const Y = DS.accent;
const G = DS.secondary;
const BDR = DS.border;
const GREEN = "#2DB87C";
const FONT = DS.font;

function useWindowSize() {
  const [s, setS] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const fn = () => setS({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);
  return s;
}

const sorted = [...gouvernorats].sort((a, b) => b.primes - a.primes);
const regColors = [C.dark, C.yellow, C.slate, C.grey];

export default function Geographie() {
  const { h: winH } = useWindowSize();
  const chartH = Math.max(140, winH - 480);

  /* ─── Top 5 gouvernorats ─────────────────────────── */
  const top5 = sorted.slice(0, 5);
  const top5Options = {
    ...barH(top5.map(g => g.gouv).reverse()),
    colors: [C.yellow],
    yaxis: { labels: { style: { colors: D, fontWeight: 700, fontSize: "12px" }, maxWidth: 100 }, axisBorder: { show: false }, axisTicks: { show: false } },
    dataLabels: { enabled: true, textAnchor: "start", offsetX: 8, style: { fontSize: "11px", fontWeight: 700, fontFamily: FONT, colors: [D] }, formatter: v => `${(v / 1e9).toFixed(2)} Md` },
    tooltip: { style: { fontFamily: FONT, fontSize: "12px" }, y: { formatter: v => `${(v / 1e6).toFixed(0)} M TND` } },
  };
  const top5Series = [{ name: "Primes", data: top5.map(g => g.primes).reverse() }];

  /* ─── Répartition régions ────────────────────────── */
  const regions = {};
  gouvernorats.forEach(g => { regions[g.region] = (regions[g.region] || 0) + g.primes; });
  const totalReg = Object.values(regions).reduce((a, b) => a + b, 0);
  const regOrder = ["Grand Tunis", "Littoral", "Intérieur", "Sud"];

  const regOptions = {
    chart: { type: "bar", stacked: true, toolbar: { show: false }, fontFamily: FONT, background: "transparent", animations: { enabled: false } },
    plotOptions: { bar: { horizontal: true, barHeight: "56%", borderRadius: 3, borderRadiusApplication: "end" } },
    colors: regColors,
    xaxis: { categories: ["Régions"], labels: { show: false }, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis: { labels: { show: false } },
    grid: { show: false },
    dataLabels: { enabled: true, formatter: v => `${(v / totalReg * 100).toFixed(1)}%`, style: { fontSize: "11px", fontWeight: 700, fontFamily: FONT, colors: ["#fff", D, "#fff", "#fff"] } },
    legend: { position: "bottom", fontSize: "12px", fontWeight: 600, fontFamily: FONT, labels: { colors: D }, markers: { radius: 3, width: 14, height: 8 }, itemMargin: { horizontal: 10, vertical: 6 } },
    tooltip: { style: { fontFamily: FONT, fontSize: "12px" }, y: { formatter: v => `${(v/totalReg*100).toFixed(1)}%` } },
  };
  const regSeries = regOrder.map(r => ({ name: r, data: [regions[r] || 0] }));

  /* ─── Scatter positionnement gouvernorats ─────────── */
  const scatterOptions = {
    chart: { type: "scatter", toolbar: { show: false }, fontFamily: FONT, background: "transparent", animations: { enabled: false } },
    colors: [C.yellow],
    xaxis: {
      title: { text: "Densité agences / 100k hab.", style: { color: G, fontSize: "11px", fontFamily: FONT } },
      labels: { style: { colors: G, fontSize: "11px", fontFamily: FONT } },
      axisBorder: { show: false }, axisTicks: { show: false },
    },
    yaxis: {
      title: { text: "Primes / habitant (DT)", style: { color: G, fontSize: "11px", fontFamily: FONT } },
      labels: { style: { colors: G, fontSize: "11px", fontFamily: FONT } },
    },
    grid: { borderColor: "#EBEBEF", strokeDashArray: 4 },
    dataLabels: { enabled: true, formatter: (v, opts) => gouvernorats[opts.dataPointIndex]?.gouv || "", style: { fontSize: "10px", fontWeight: 600, fontFamily: FONT, colors: [D] }, offsetY: -10 },
    markers: { size: 9, strokeColors: D, strokeWidth: 1.5, hover: { size: 11 } },
    tooltip: { style: { fontFamily: FONT, fontSize: "12px" }, x: { formatter: v => `Densité: ${v}` }, y: { formatter: v => `${v} DT/hab` } },
  };
  const scatterData = gouvernorats.map(g => ({ x: parseFloat(((g.agences / g.pop) * 100000).toFixed(1)), y: parseFloat((g.primes / g.pop).toFixed(1)) }));
  const scatterSeries = [{ name: "Gouvernorats", data: scatterData }];

  const potentiel = (g) => {
    const ppA = g.primes / g.agences;
    if (ppA > 3000000 || g.gouv === "Zaghouan" || g.gouv === "Mahdia") return { label: "Élevé", color: GREEN };
    return { label: "Moyen", color: "#F5A623" };
  };

  return (
    <div style={{ height:"calc(100vh - 92px)", background: DS.bg, fontFamily: DS.font, display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar title="Performance Géographique" />

      {/* ── Corps ── */}
      <div style={{ flex:1, overflow:"hidden", padding:"14px 24px 12px", display:"flex", flexDirection:"column", gap:10 }}>

        {/* Bannière KPI */}
        <DsBanner kpis={[
          { label:"Total Agences",              value:"1 856",    sub:"à travers la Tunisie" },
          { label:"Primes par Agence",           value:"2.61 MDT", sub:"en moyenne", accent:true },
          { label:"Taux de Couverture National", value:"+11.8%",   sub:"vs 2024", delta:"+11.8%", pos:true, accent:true },
          { label:"Concentration Grand Tunis",   value:"48.7%",    sub:"des primes nationales" },
        ]}/>

        {/* Map + charts + table */}
        <div style={{ flex:1, minHeight:0, display:"grid", gridTemplateColumns:"200px 1fr 1fr", gap:10 }}>

          {/* Map */}
          <DsCard style={{ overflow:"hidden" }}>
            <DsTitle>Primes par Gouvernorat</DsTitle>
            <div style={{ position:"relative", width:"100%" }}>
              <svg viewBox="0 0 220 340" style={{ width:"100%", height:"auto" }}>
                <defs>
                  <linearGradient id="mapBg" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#F5F5E8" />
                    <stop offset="100%" stopColor="#EEF0D8" />
                  </linearGradient>
                </defs>
                <rect width="220" height="340" fill="url(#mapBg)" rx="8" />
                <path d="M85,15 L110,12 L130,18 L145,30 L155,50 L158,75 L155,100 L165,125 L168,145 L162,165 L155,180 L160,200 L155,220 L148,240 L140,260 L130,275 L118,285 L105,295 L95,310 L85,315 L75,305 L70,285 L78,265 L80,245 L75,225 L68,205 L65,185 L60,165 L55,145 L52,125 L58,105 L55,85 L60,65 L70,45 L78,30 Z"
                  fill="#E8E8D8" stroke="#C8C8B8" strokeWidth="1.5" />
                {[
                  { x:105, y:50,  r:18, c:Y, label:"Tunis" },
                  { x:118, y:42,  r:14, c:"#FFD000", label:"Ariana" },
                  { x:118, y:60,  r:10, c:"#FFD000", label:"Ben Arous" },
                  { x:95,  y:48,  r:9,  c:"#FFE880", label:"Manouba" },
                  { x:90,  y:30,  r:10, c:"#FFE880", label:"Bizerte" },
                  { x:145, y:80,  r:12, c:"#FFD000", label:"Nabeul" },
                  { x:130, y:130, r:14, c:"#FFD000", label:"Sousse" },
                  { x:120, y:210, r:15, c:"#FFD000", label:"Sfax" },
                ].map((pt, i) => (
                  <g key={i}>
                    <circle cx={pt.x} cy={pt.y} r={pt.r} fill={pt.c} stroke={D} strokeWidth="0.8" opacity="0.9" />
                  </g>
                ))}
              </svg>
            </div>
          </DsCard>

          {/* Charts col */}
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            <DsCard style={{ flex:1, display:"flex", flexDirection:"column" }}>
              <DsTitle>Top 5 Gouvernorats par Primes (TND)</DsTitle>
              <div style={{ flex:1, minHeight:0 }}>
                <ReactApexChart options={top5Options} series={top5Series} type="bar" height="100%"/>
              </div>
            </DsCard>
            <DsCard style={{ flex:1, display:"flex", flexDirection:"column" }}>
              <DsTitle>Positionnement des Gouvernorats</DsTitle>
              <div style={{ flex:1, minHeight:0 }}>
                <ReactApexChart options={scatterOptions} series={scatterSeries} type="scatter" height="100%"/>
              </div>
            </DsCard>
          </div>

          {/* Régions + table */}
          <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
            <DsCard>
              <DsTitle>Répartition par Grande région</DsTitle>
              <ReactApexChart options={regOptions} series={regSeries} type="bar" height={100} />
              <div style={{ marginTop:8, display:"flex", flexDirection:"column", gap:4 }}>
                {regOrder.map((r, i) => (
                  <div key={r} style={{ display:"flex", alignItems:"center", gap:8, fontSize:11 }}>
                    <div style={{ width:10, height:10, borderRadius:2, background:regColors[i], flexShrink:0 }}/>
                    <span style={{ fontWeight:700, color:D }}>{r}</span>
                    <span style={{ marginLeft:"auto", color:G, fontWeight:700 }}>{((regions[r]||0)/totalReg*100).toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </DsCard>
            {/* Table gouvernorats scrollable */}
            <DsCard style={{ flex:1, overflow:"hidden", display:"flex", flexDirection:"column", padding:"16px 0" }}>
              <div style={{ padding:"0 18px 10px" }}><DsTitle>Classement des gouvernorats</DsTitle></div>
              <div style={{ overflowY:"auto", flex:1 }}>
                <table style={{ width:"100%", fontSize:10, borderCollapse:"collapse" }}>
                  <thead style={{ position:"sticky", top:0 }}>
                    <tr style={{ background:D, color:"#fff" }}>
                      <th style={{ padding:"8px 10px", textAlign:"left", fontWeight:700, fontSize:9, letterSpacing:"0.8px" }}>Gouvernorat</th>
                      <th style={{ padding:"8px 10px", textAlign:"right", fontWeight:700, fontSize:9 }}>% Marché</th>
                      <th style={{ padding:"8px 10px", textAlign:"right", fontWeight:700, fontSize:9 }}>Agences</th>
                      <th style={{ padding:"8px 10px", textAlign:"left", fontWeight:700, fontSize:9 }}>Potentiel</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((g, i) => {
                      const pot = potentiel(g);
                      return (
                        <tr key={g.gouv} style={{ borderBottom:"1px solid #F5F5F8", background: i%2===0 ? "#fff" : "#FAFAFA" }}>
                          <td style={{ padding:"6px 10px", fontWeight:700, color:D }}>{g.gouv}</td>
                          <td style={{ padding:"6px 10px", textAlign:"right", color:G }}>{g.pdm}%</td>
                          <td style={{ padding:"6px 10px", textAlign:"right", color:G }}>{g.agences}</td>
                          <td style={{ padding:"6px 10px" }}>
                            <span style={{ fontSize:9, fontWeight:800, color:pot.color }}>{pot.label}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </DsCard>
          </div>
        </div>

        <DsSource>Dernière mise à jour : 20/05/2025</DsSource>
      </div>
    </div>
  );
}
