import { useState, useEffect } from "react";
import ReactApexChart from "react-apexcharts";
import { compagnies, bubble } from "../data/mockData";
import { C, bar } from "../utils/chartTheme";
import PageHeaderBar from "../components/PageHeaderBar";
import { DS, DsCard, DsTitle, DsKpi, DsBanner, DsSource } from "../components/Ds";

export default function Positionnement() {
  const [winH, setWinH] = useState(window.innerHeight);
  useEffect(() => {
    const fn = () => setWinH(window.innerHeight);
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);

  const chartH = Math.max(180, winH - 92 - 58 - 72 - 48 - 12 * 3 - 20);

  /* ─── Bubble chart ─── */
  const bubbleOptions = {
    chart:{ type:"bubble", toolbar:{show:false}, fontFamily: DS.font, background:"transparent", animations:{enabled:false} },
    colors: bubble.map(b => b.nom === "STAR" ? C.yellow : "#C0C0CC"),
    xaxis:{
      title:{ text:"Part de Marché (%)", style:{color: DS.secondary, fontSize:"11px", fontFamily: DS.font} },
      min:0, max:22,
      labels:{ style:{colors: DS.secondary, fontSize:"11px", fontFamily: DS.font}, formatter: v => `${v}%` },
      axisBorder:{show:false}, axisTicks:{show:false},
    },
    yaxis:{
      title:{ text:"Croissance (%)", style:{color: DS.secondary, fontSize:"11px", fontFamily: DS.font} },
      min:-5, max:20,
      labels:{ formatter: v => `${v}%`, style:{colors: DS.secondary, fontSize:"11px"} },
    },
    grid:{ borderColor:"#E0E0EA", strokeDashArray:4, xaxis:{lines:{show:true}}, yaxis:{lines:{show:true}} },
    dataLabels:{ enabled:true, formatter:(v,opts) => bubble[opts.seriesIndex]?.nom||"", style:{fontSize:"10px",fontWeight:700,fontFamily: DS.font, colors:[DS.primary]} },
    annotations:{
      xaxis:[{ x:9, borderColor:"#C0C0CC", borderWidth:1, strokeDashArray:5 }],
      yaxis:[{ y:10, borderColor:"#C0C0CC", borderWidth:1, strokeDashArray:5 }],
      texts:[
        { x:1,  y:19, text:"Défi à fort potentiel", style:{color: DS.muted, fontSize:"10px", fontFamily: DS.font, background:"transparent"} },
        { x:14, y:19, text:"Leaders",               style:{color: DS.muted, fontSize:"10px", fontFamily: DS.font, background:"transparent"} },
        { x:1,  y:-3, text:"Niche / En retrait",    style:{color: DS.muted, fontSize:"10px", fontFamily: DS.font, background:"transparent"} },
        { x:14, y:-3, text:"Solides Performers",    style:{color: DS.muted, fontSize:"10px", fontFamily: DS.font, background:"transparent"} },
      ],
    },
    legend:{show:false},
    tooltip:{ style:{fontFamily: DS.font, fontSize:"12px"}, y:{ formatter:(v,{seriesIndex}) => `${bubble[seriesIndex]?.primes} M TND` } },
  };
  const bubbleSeries = bubble.map(b => ({ name:b.nom, data:[[b.pdm, b.croissance, b.primes/40]] }));

  /* ─── Comparaison barres ─── */
  const cmpOptions = {
    ...bar(["Part de Marché","Ratio Combiné","ROE"]),
    colors:[C.yellow, C.dark, C.slate],
    yaxis:{ labels:{ formatter: v => `${v}%`, style:{colors: DS.muted, fontSize:"11px"} } },
    tooltip:{ y:{ formatter: v => `${v}%` } },
  };
  const cmpSeries = [
    { name:"STAR",  data:[19.6, 30.0, 89.2] },
    { name:"BH",    data:[17.2, 63.2, 69.4] },
    { name:"COMAR", data:[14.1, 40.0, 47.2] },
  ];

  return (
    <div style={{ height:"calc(100vh - 92px)", background: DS.bg, fontFamily: DS.font, display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar title="Positionnement Concurrentiel" />

      <div style={{ flex:1, overflow:"hidden", padding:"14px 24px 12px", display:"flex", flexDirection:"column", gap:10 }}>

        {/* ── Bannière KPI ── */}
        <DsBanner kpis={[
          { label:"Primes Totales",           value:"4.85 MDT", sub:"exercice 2024",   delta:"+11.8%", pos:true, accent:true },
          { label:"Nombre d'Assureurs",        value:"29",       sub:"compagnies actives" },
          { label:"Croissance Moy. Marché",   value:"+11.8 %",  sub:"vs 2023",         delta:"+11.8%", pos:true, accent:true },
        ]}/>

        {/* ── 3 colonnes — remplit l'espace restant ── */}
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:10, flex:1, minHeight:0, overflow:"hidden" }}>

          {/* Top 10 tableau */}
          <DsCard style={{ display:"flex", flexDirection:"column", overflow:"hidden" }}>
            <DsTitle>Top 10 Assureurs par Parts de Marché</DsTitle>
            <div style={{ flex:1, overflowY:"auto" }}>
              <table style={{ width:"100%", fontSize:11, borderCollapse:"collapse" }}>
                <thead>
                  <tr>
                    <th style={{ color: DS.muted, fontWeight:700, paddingBottom:8, textAlign:"left", fontSize:9, letterSpacing:"1.2px", textTransform:"uppercase" }}>Assureur</th>
                    <th style={{ color: DS.muted, fontWeight:700, paddingBottom:8, textAlign:"left", fontSize:9, letterSpacing:"1.2px", textTransform:"uppercase" }}>PDM</th>
                    <th style={{ color: DS.muted, fontWeight:700, paddingBottom:8, textAlign:"left", fontSize:9, letterSpacing:"1.2px", textTransform:"uppercase" }}>VS 2024</th>
                  </tr>
                </thead>
                <tbody>
                  {compagnies.map((c,i) => (
                    <tr key={c.nom} style={{ background: i===0 ? `${DS.accent}22` : "transparent", borderBottom:`1px solid ${DS.border}` }}>
                      <td style={{ paddingBlock:7, paddingRight:8 }}>
                        <img src={c.logo} alt={c.nom} style={{ height:22, maxWidth:80, objectFit:"contain" }}/>
                      </td>
                      <td style={{ paddingBlock:7, paddingRight:8 }}>
                        <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                          <div style={{ flex:1, height:4, background: DS.tile, borderRadius:99, overflow:"hidden" }}>
                            <div style={{ height:4, background: DS.accent, borderRadius:99, width:`${(c.pdm/16)*100}%` }}/>
                          </div>
                          <span style={{ color: DS.secondary, fontWeight:700, fontSize:10 }}>{c.pdm}%</span>
                        </div>
                      </td>
                      <td style={{ paddingBlock:7, color: DS.pos, fontWeight:700, whiteSpace:"nowrap" }}>↑ +{(1.5-i*0.12).toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </DsCard>

          {/* Bubble */}
          <DsCard style={{ display:"flex", flexDirection:"column" }}>
            <DsTitle>Matrice de Positionnement (Taille = Volume Primes)</DsTitle>
            <div style={{ flex:1, minHeight:0 }}>
              <ReactApexChart options={bubbleOptions} series={bubbleSeries} type="bubble" height="100%"/>
            </div>
          </DsCard>

          {/* Comparaison */}
          <DsCard style={{ display:"flex", flexDirection:"column" }}>
            <DsTitle>Comparaison des Assureurs Sélectionnés</DsTitle>
            <div style={{ flex:1, minHeight:0 }}>
              <ReactApexChart options={cmpOptions} series={cmpSeries} type="bar" height="100%"/>
            </div>
          </DsCard>
        </div>

        <DsSource>Dernière mise à jour : 20/05/2025</DsSource>
      </div>
    </div>
  );
}
