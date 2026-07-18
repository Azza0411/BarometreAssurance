import { useState, useEffect } from "react";
import ReactApexChart from "react-apexcharts";
import { primesMarche, ratioSinistralite, compagnies } from "../data/mockData";
import { C, line, barH, bar, donut } from "../utils/chartTheme";
import PageHeaderBar from "../components/PageHeaderBar";
import { DS, DsCard, DsTitle, DsKpi, DsBanner, DsSource } from "../components/Ds";

export default function EtatGeneral() {
  const [winH, setWinH] = useState(window.innerHeight);
  useEffect(() => {
    const fn = () => setWinH(window.innerHeight);
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);

  /* hauteur graphiques row 1 — fixe */
  const r1H = Math.max(130, Math.round((winH - 92 - 58 - 72 - 48 - 40 - 12 * 4) / 2) - 10);

  /* ─── Évolution primes ─── */
  const cats = primesMarche.categories.map(y => y === 2026 ? "2026 (Prév.)" : String(y));
  const lineOptions = {
    ...line(cats),
    colors: [C.dark, C.blue],
    stroke: { width:[2.5,2], dashArray:[0,5], curve:"smooth" },
    markers: { size:[4,3], strokeColors:"#fff", strokeWidth:2, hover:{size:6} },
    yaxis: { min:0, labels:{ style:{colors:C.muted,fontSize:"11px"}, formatter: v => v.toFixed(1) } },
    tooltip: { y:{ formatter: v => v != null ? `${v} MDT` : "" } },
  };
  const lineSeries = [
    { name:"Primes Collectées", data: primesMarche.historique },
    { name:"Prévision",         data: primesMarche.prevision  },
  ];

  /* ─── Primes par branche ─── */
  const brancheOptions = {
    ...barH(["Vie","Non-Vie"]),
    colors:[C.yellow],
    yaxis:{ labels:{ style:{colors:C.dark,fontWeight:700,fontSize:"12px"},maxWidth:80 }, axisBorder:{show:false}, axisTicks:{show:false} },
    dataLabels:{ enabled:true, textAnchor:"start", offsetX:8, style:{fontSize:"12px",fontWeight:700,fontFamily:"Barlow,system-ui,sans-serif",colors:[C.dark]}, formatter: v => `${v} MDT` },
    tooltip:{ y:{ formatter: v => `${v} MDT` } },
  };
  const brancheSeries = [{ name:"Primes", data:[129,1306] }];

  /* ─── Donut Vie/Non-Vie ─── */
  const donutOptions = {
    ...donut(["Non-vie","Vie"], () => "1 435 MDT"),
    colors:[C.dark,C.yellow],
    tooltip:{ y:{ formatter: v => `${v} MDT` } },
  };
  const donutSeries = [1306,129];

  /* ─── Top 5 entreprises ─── */
  const top5 = compagnies.slice(0,5);
  const top5Options = {
    ...barH(top5.map(c=>c.nom).reverse()),
    colors:[C.yellow],
    yaxis:{ labels:{ style:{colors:C.dark,fontWeight:600,fontSize:"11px"},maxWidth:110 }, axisBorder:{show:false}, axisTicks:{show:false} },
    dataLabels:{ enabled:true, textAnchor:"start", offsetX:8, style:{fontSize:"11px",fontWeight:700,fontFamily:"Barlow,system-ui,sans-serif",colors:[C.dark]}, formatter: v => `${v} M TND` },
    tooltip:{ y:{ formatter: v => `${v} M TND` } },
  };
  const top5Series = [{ name:"Primes", data: top5.map(c=>c.primes).reverse() }];

  /* ─── Ratio sinistralité ─── */
  const ratioOptions = {
    ...bar(ratioSinistralite.categories),
    colors:[C.dark],
    yaxis:{ min:0, max:100, labels:{ style:{colors:C.muted,fontSize:"11px"}, formatter: v => `${v}%` } },
    tooltip:{ y:{ formatter: v => `${v}%` } },
  };
  const ratioSeries = [{ name:"Ratio sinistralité", data: ratioSinistralite.values }];

  return (
    <div style={{ height:"calc(100vh - 92px)", background: DS.bg, fontFamily: DS.font, display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar title="État Général du Marché" />

      <div style={{ flex:1, overflow:"hidden", padding:"14px 24px 12px", display:"flex", flexDirection:"column", gap:10 }}>

        {/* ── Bannière KPI ── */}
        <DsBanner kpis={[
          { label:"Total Primes Émises",         value:"1.435 MDT", sub:"exercice 2024" },
          { label:"Taux de Pénétration",         value:"3.8 %",     sub:"du PIB",        delta:"+0.2%", pos:true,  accent:true },
          { label:"Croissance des Primes",       value:"+7.6 %",    sub:"vs 2023",       delta:"+4.2%", pos:true,  accent:true },
          { label:"Ratio de Sinistralité Moyen", value:"69.1 %",    sub:"moyenne marché" },
          { label:"Nombre d'Entreprises",        value:"24",        sub:"assureurs actifs" },
        ]}/>

        {/* ── Row 1 : 3 graphiques ── */}
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:10, flexShrink:0 }}>
          <DsCard>
            <DsTitle>Évolution des primes collectées (MDT)</DsTitle>
            <ReactApexChart options={lineOptions} series={lineSeries} type="line" height={r1H}/>
          </DsCard>
          <DsCard>
            <DsTitle>Primes collectées par branche (MDT)</DsTitle>
            <ReactApexChart options={brancheOptions} series={brancheSeries} type="bar" height={r1H}/>
          </DsCard>
          <DsCard>
            <DsTitle>Répartition Vie vs Non-Vie (MDT)</DsTitle>
            <ReactApexChart options={donutOptions} series={donutSeries} type="donut" height={r1H}/>
          </DsCard>
        </div>

        {/* ── Row 2 : 2 graphiques — remplit l'espace restant ── */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10, flex:1, minHeight:0 }}>
          <DsCard style={{ display:"flex", flexDirection:"column", overflow:"hidden" }}>
            <DsTitle>Top 5 Entreprises par Primes Collectées (TND)</DsTitle>
            <div style={{ flex:1, minHeight:0 }}>
              <ReactApexChart options={top5Options} series={top5Series} type="bar" height="100%"/>
            </div>
          </DsCard>
          <DsCard style={{ display:"flex", flexDirection:"column", overflow:"hidden" }}>
            <DsTitle>Évolution du ratio de sinistralité (%)</DsTitle>
            <div style={{ flex:1, minHeight:0 }}>
              <ReactApexChart options={ratioOptions} series={ratioSeries} type="bar" height="100%"/>
            </div>
          </DsCard>
        </div>

        <DsSource>Dernière mise à jour : 20/05/2025</DsSource>
      </div>
    </div>
  );
}
