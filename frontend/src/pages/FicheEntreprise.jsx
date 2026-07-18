import { useState, useEffect } from "react";
import ReactApexChart from "react-apexcharts";
import { starData, YEARS } from "../data/mockData";
import { C, CAT6, bar, barH, line, donut } from "../utils/chartTheme";
import PageHeaderBar from "../components/PageHeaderBar";

const D = "#2E2E38";
const Y = "#FFE600";
const G = "#747480";
const BDR = "#E5E7EB";
const GREEN = "#2DB87C";
const YELLOW = C.yellow;
const DARK = C.dark;
const GREY = C.muted;

function useWindowSize() {
  const [s, setS] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const fn = () => setS({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);
  return s;
}

export default function FicheEntreprise() {
  const [tab, setTab] = useState("overview");
  const { h: winH } = useWindowSize();
  const chartH = Math.max(160, winH - 420);

  /* ─── Options graphiques ── */
  const donutProduits = { ...donut(starData.produits.map(p => p.label)), colors: CAT6 };
  const donutSeries = starData.produits.map(p => p.value);

  const barPrimesOpts = {
    ...bar(YEARS), colors: [C.yellow],
    yaxis: { labels: { formatter: v => `${v}`, style: { colors: C.muted, fontSize: "11px" } }, min: 0, max: 320 },
    tooltip: { y: { formatter: v => `${v} MDT` } },
  };
  const barPrimesSeries = [{ name: "Primes Émises (MDT)", data: starData.primesEvolution }];

  const dualLineOpts = {
    ...line([...YEARS, 2026]),
    colors: [C.yellow, C.dark],
    stroke: { width: [2.5, 2], dashArray: [0, 5], curve: "smooth" },
    markers: { size: [4, 3], strokeColors: "#fff", strokeWidth: 2, hover: { size: 6 } },
    yaxis: [
      { labels: { formatter: v => `${v}`, style: { colors: C.muted, fontSize: "11px" } } },
      { opposite: true, labels: { formatter: v => `${v}`, style: { colors: C.muted, fontSize: "11px" } } },
    ],
    legend: { position: "top", horizontalAlign: "left", fontSize: "11px", fontWeight: 600, fontFamily: "Barlow, system-ui, sans-serif", labels: { colors: C.dark }, markers: { radius: 3, width: 12, height: 7 }, itemMargin: { horizontal: 12 } },
  };
  const dualLineSeries = [
    { name: "Primes émises",      data: [...starData.primesEvolution, 290.0] },
    { name: "Résultat technique", data: [...starData.resTechEvolution, null], yAxisIndex: 1 },
  ];

  const roeRoaOpts = {
    ...line(YEARS), colors: [C.dark, C.yellow],
    stroke: { width: 2.5, curve: "smooth" },
    markers: { size: 4, strokeColors: "#fff", strokeWidth: 2, hover: { size: 6 } },
    yaxis: [
      { labels: { formatter: v => `${v}%`, style: { colors: C.muted, fontSize: "11px" } }, min: 0, max: 5 },
      { opposite: true, labels: { formatter: v => `${v}%`, style: { colors: C.muted, fontSize: "11px" } }, min: 0, max: 22 },
    ],
    tooltip: { y: { formatter: v => `${v}%` } },
  };
  const roeRoaSeries = [
    { name: "ROA", data: starData.roa },
    { name: "ROE", data: starData.roe, yAxisIndex: 1 },
  ];

  const brancheBase = () => ({
    ...barH(["Vie", "Non-Vie"]), colors: [C.yellow],
    yaxis: { labels: { style: { colors: C.dark, fontWeight: 700, fontSize: "12px" }, maxWidth: 70 }, axisBorder: { show: false }, axisTicks: { show: false } },
    dataLabels: { enabled: true, textAnchor: "start", offsetX: 8, style: { fontSize: "11px", fontWeight: 700, fontFamily: "Barlow, system-ui, sans-serif", colors: [C.dark] } },
    tooltip: { y: { formatter: v => `${v} MDT` } },
  });

  const KPIS_OVERVIEW = [
    { label:"Primes Émises",      value:"2.52 MDT" },
    { label:"Sinistres Réglés",   value:"1.3 MDT"  },
    { label:"Ratio Sinistralité", value:"64.11%"   },
    { label:"Ratio Frais",        value:"28.40%"   },
    { label:"Ratio Combiné",      value:"92.52%"   },
  ];

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"#F9F9FB", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar
        title="Fiche Entreprise"
        tabs={[
          { key:"overview", label:"Vue d'ensemble" },
          { key:"perf",     label:"Performance & Rentabilité" },
        ]}
        activeTab={tab}
        onTabChange={setTab}
        right={
          <span style={{ background:Y, color:D, fontSize:11, fontWeight:800, padding:"4px 12px", borderRadius:8 }}>STAR</span>
        }
      />

      {/* ── Corps ── */}
      <div style={{ flex:1, overflow:"hidden", padding:"14px 28px", display:"flex", flexDirection:"column", gap:12 }}>

        {/* ── VUE D'ENSEMBLE ── */}
        {tab === "overview" && (
          <>
            {/* Identité + KPIs côte à côte */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr 1fr", gap:12, flexShrink:0 }}>
              {/* Logo */}
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px 18px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center" }}>
                <div style={{ fontSize:20, fontWeight:900, color:D, letterSpacing:2 }}>★ STAR</div>
                <div style={{ fontSize:9, fontWeight:800, letterSpacing:3, color:G, textTransform:"uppercase", marginTop:2 }}>Assurances</div>
                <div style={{ fontSize:10, color:G, textAlign:"center", marginTop:6 }}>Société Tunisienne d'Assurances et de Réassurances</div>
              </div>
              {/* Rang */}
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px 18px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center" }}>
                <div style={{ fontSize:9, color:G, marginBottom:4 }}>Rang · <span style={{ background:Y, color:D, fontSize:9, fontWeight:800, padding:"2px 6px", borderRadius:4 }}>Primes Totales</span></div>
                <div style={{ fontSize:32, fontWeight:900, color:D }}>2<span style={{ fontSize:16 }}>/24</span></div>
                <div style={{ fontSize:11, fontWeight:800, color:Y, background:D, padding:"2px 8px", borderRadius:4, marginTop:4 }}>PDM : 12.4%</div>
              </div>
              {/* Infos légales */}
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px 18px", boxShadow:"0 1px 6px rgba(0,0,0,.04)" }}>
                {[["Forme juridique","S.A"],["Activité","Multi-Branches"],["Date de création","15/06/1995"],["Effectif","842 agents"]].map(([k,v]) => (
                  <div key={k} style={{ display:"flex", justifyContent:"space-between", paddingBlock:5, borderBottom:"1px solid #F5F5F8", fontSize:11 }}>
                    <span style={{ color:G }}>{k}</span>
                    <span style={{ fontWeight:700, color:D }}>{v}</span>
                  </div>
                ))}
              </div>
              {/* Financiers */}
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px 18px", boxShadow:"0 1px 6px rgba(0,0,0,.04)" }}>
                {[["Résultat Net","62.7 MDT",GREEN],["Total Actif","1.245 MDT",GREEN],["Capitaux propres","290.4 MDT",GREEN],["ROE","11.4%",D],["ROA","5.8%",D]].map(([k,v,c]) => (
                  <div key={k} style={{ display:"flex", justifyContent:"space-between", paddingBlock:5, borderBottom:"1px solid #F5F5F8", fontSize:11 }}>
                    <span style={{ color:G }}>{k}</span>
                    <span style={{ fontWeight:800, color:c }}>{v}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* KPIs */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:12, flexShrink:0 }}>
              {KPIS_OVERVIEW.map(k => (
                <div key={k.label} style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"12px 16px", boxShadow:"0 1px 6px rgba(0,0,0,.04)" }}>
                  <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:G, marginBottom:6 }}>{k.label}</div>
                  <div style={{ fontSize:18, fontWeight:900, color:D }}>{k.value}</div>
                </div>
              ))}
            </div>

            {/* Charts */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, flex:1, minHeight:0 }}>
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column" }}>
                <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D, marginBottom:6 }}>Evolution des Primes Emises (MDT)</div>
                <div style={{ flex:1 }}>
                  <ReactApexChart options={barPrimesOpts} series={barPrimesSeries} type="bar" height={chartH} />
                </div>
              </div>
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column" }}>
                <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D, marginBottom:6 }}>Répartition des Primes par Produit</div>
                <div style={{ flex:1 }}>
                  <ReactApexChart options={donutProduits} series={donutSeries} type="donut" height={chartH} />
                </div>
              </div>
            </div>
          </>
        )}

        {/* ── PERFORMANCE & RENTABILITÉ ── */}
        {tab === "perf" && (
          <>
            {/* KPIs */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(6,1fr)", gap:10, flexShrink:0 }}>
              {[
                { label:"Primes Émises",      value:"2.52 MDT" },
                { label:"Sinistres Réglés",   value:"1.3 MDT"  },
                { label:"Ratio Sinistralité", value:"64.11%"   },
                { label:"Ratio Frais",        value:"28.40%"   },
                { label:"Ratio Combiné",      value:"92.52%"   },
                { label:"Résultat Net",       value:"62.7 MDT" },
              ].map(k => (
                <div key={k.label} style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"12px 14px", boxShadow:"0 1px 6px rgba(0,0,0,.04)" }}>
                  <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:G, marginBottom:6 }}>{k.label}</div>
                  <div style={{ fontSize:16, fontWeight:900, color:D }}>{k.value}</div>
                </div>
              ))}
            </div>

            {/* Charts rows */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12, flex:1, minHeight:0 }}>
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column" }}>
                <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D, marginBottom:6 }}>Répartition Primes par Produit</div>
                <div style={{ flex:1 }}>
                  <ReactApexChart options={donutProduits} series={donutSeries} type="donut" height={chartH} />
                </div>
              </div>
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column" }}>
                <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D, marginBottom:6 }}>Evolution Primes & Résultat technique (MDT)</div>
                <div style={{ flex:1 }}>
                  <ReactApexChart options={dualLineOpts} series={dualLineSeries} type="line" height={chartH} />
                </div>
              </div>
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column" }}>
                <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D, marginBottom:6 }}>Primes émises vs Cédées par Branche (MDT)</div>
                <div style={{ flex:1 }}>
                  <ReactApexChart
                    options={{
                      ...barBrancheOpts(),
                      plotOptions: { bar: { horizontal: false, columnWidth: "65%", borderRadius: 4 } },
                      xaxis: { categories: ["Non-vie", "Vie"], labels: { style: { colors: GREY } }, axisBorder: { show: false } },
                      yaxis: { labels: { formatter: v => `${v}`, style: { colors: GREY } } },
                      colors: [YELLOW, DARK],
                      legend: { show: true, position: "top", fontFamily: "Barlow, system-ui, sans-serif", fontSize: "11px" },
                      dataLabels: { enabled: true, style: { fontSize: "10px" } },
                    }}
                    series={[
                      { name: "Primes émises", data: [201.5, 51.3] },
                      { name: "Primes cédées", data: [51.2,  12.3] },
                    ]}
                    type="bar" height={chartH}
                  />
                </div>
              </div>
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, flex:1, minHeight:0 }}>
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column" }}>
                <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D, marginBottom:6 }}>Structure Actif vs Passif (MDT)</div>
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, flex:1 }}>
                  <ReactApexChart options={{ ...donutProduits, labels: ["Placements","Créances","Trésorerie","Immobilisations","Autres"] }} series={[72.4,15.4,6.8,3.2,2.0]} type="donut" height={Math.max(120, chartH/2)} />
                  <ReactApexChart options={{ ...donutProduits, labels: ["Prov. techniques","Dettes","Cap. propres","Autres"] }} series={[72.4,15.4,6.8,5.4]} type="donut" height={Math.max(120, chartH/2)} />
                </div>
              </div>
              <div style={{ background:"#fff", border:`1px solid ${BDR}`, borderRadius:12, padding:"14px", boxShadow:"0 1px 6px rgba(0,0,0,.04)", display:"flex", flexDirection:"column" }}>
                <div style={{ fontSize:9, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D, marginBottom:6 }}>ROA & ROE (évolution)</div>
                <div style={{ flex:1 }}>
                  <ReactApexChart options={roeRoaOpts} series={roeRoaSeries} type="line" height={chartH} />
                </div>
              </div>
            </div>
          </>
        )}

        <div style={{ textAlign:"right", fontSize:10, color:G, flexShrink:0 }}>Dernière mise à jour : 20/05/2025</div>
      </div>
    </div>
  );
}
