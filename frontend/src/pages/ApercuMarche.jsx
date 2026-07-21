import { useState, useEffect } from "react";
import ReactApexChart from "react-apexcharts";
import { useNavigate } from "react-router-dom";
import TunisiaMap from "../components/TunisiaMap";
import NewsTicker from "../components/NewsTicker";
import { C, CAT6, combo, line, donut } from "../utils/chartTheme";
import { DS, DsBanner, DsSource } from "../components/Ds";
import { getLogoSrc } from "../utils/logos";

/* ── Labels compagnies ── */
const COMPANY_LABELS = {
  STAR:"STAR",COMAR:"COMAR",CARTE:"CARTE",GAT:"GAT",
  LLOYD_TUNISIEN:"LLOYD ASSURANCES",ASTREE:"ASTREE",BH:"BH ASSURANCES",
  ATTIJARI:"ATTIJARI ASSURANCE",MAGHREBIA:"MAGHREBIA",AMI:"AMI",
  CTAMA:"CTAMA",AL_AMANAH_TAKAFUL:"EL AMANA TAKAFUL",
  AT_TAKAFULIA:"AT-TAKAFULIA",ZITOUNA_TAKAFUL:"ZITOUNA TAKAFUL",
  MAE:"MAE",BIAT:"BIAT",BNA:"BNA",COTUNACE:"COTUNACE",
  HAYETT:"HAYETT",TUNIS_RE:"TUNIS RE",UIB:"UIB",
  CARTE_VIE:"CARTE VIE",GAT_VIE:"GAT VIE",
  LLOYD_VIE:"LLOYD VIE",MAGHREBIA_VIE:"MAGHREBIA VIE",
};

/* ── Charte EY light ── */
const D   = "#2E2E38";
const Y   = "#FFE600";
const G   = "#747480";
const BG  = "#F2F2F4";
const WH  = "#FFFFFF";
const BDR = "#E5E7EB";
const GR  = "#059669";
const RD  = "#DC2626";

/* ── Hook taille fenêtre ── */
function useWindowSize() {
  const [s, setS] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const fn = () => setS({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);
  return s;
}

const API = "http://localhost:8002";

function fmt(v, d=1) { return v==null ? "—" : Number(v).toLocaleString("fr-TN",{minimumFractionDigits:d,maximumFractionDigits:d}); }
function fmtG(v) { return v==null ? null : `${v>=0?"+":""}${Number(v).toFixed(1)}%`; }

/* ════════════════════════════════════════════════════════════
   COMPOSANTS PARTAGÉS
════════════════════════════════════════════════════════════ */

/* ─── Card ─── */
function Card({ children, style={} }) {
  return (
    <div style={{
      background: WH,
      border: "1px solid #E8E8EF",
      borderRadius: 6,
      padding: "24px 26px",
      ...style,
    }}>{children}</div>
  );
}

/* ─── SectionTitle : underline jaune pleine largeur ─── */
function SectionTitle({ children, action }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", paddingBottom: 12 }}>
        <span style={{ fontSize:10, fontWeight:800, letterSpacing:"2px", textTransform:"uppercase", color:D }}>{children}</span>
        {action}
      </div>
      <div style={{ height:2, background:Y, width:"100%", borderRadius:1 }}/>
    </div>
  );
}

/* ══════════════════════════════════════════════════
   KPI secondaire — tile gris, pas de border
══════════════════════════════════════════════════ */
function Kpi({ label, value, sub, delta, pos=true, accent=false }) {
  return (
    <div
      onMouseEnter={e=>{e.currentTarget.style.transform="translateY(-2px)";e.currentTarget.style.boxShadow="0 10px 28px rgba(46,46,56,.10)";}}
      onMouseLeave={e=>{e.currentTarget.style.transform="none";e.currentTarget.style.boxShadow="0 2px 8px rgba(46,46,56,.05)";}}
      style={{
        background: WH,
        borderRadius: 7,
        padding: "11px 13px 9px",
        display: "flex", flexDirection: "column",
        minWidth: 0,
        boxShadow: "0 2px 8px rgba(46,46,56,.05)",
        transition: "transform .16s ease, box-shadow .16s ease",
        borderLeft: `3px solid ${accent ? Y : "transparent"}`,
        borderTop: "1px solid #EBEBF2",
        borderRight: "1px solid #EBEBF2",
        borderBottom: "1px solid #EBEBF2",
      }}>
      <div style={{ fontSize:8, fontWeight:700, letterSpacing:"2px", textTransform:"uppercase", color:"#9898B0", marginBottom:5 }}>{label}</div>
      <div style={{ fontSize:22, fontWeight:900, color:D, lineHeight:1, fontVariantNumeric:"tabular-nums", letterSpacing:"-0.6px", marginBottom:5 }}>{value}</div>
      <div style={{ display:"flex", alignItems:"center", gap:4, marginTop:"auto" }}>
        {sub && <span style={{ fontSize:9, color:"#ABABC2", lineHeight:1.3 }}>{sub}</span>}
        {delta && (
          <span style={{ fontSize:9, fontWeight:800, marginLeft:"auto", flexShrink:0, color: pos ? "#15803d" : "#dc2626" }}>
            {pos ? "↑" : "↓"} {delta}
          </span>
        )}
      </div>
    </div>
  );
}

/* Aliases rétrocompat */
const KpiTop   = (p) => <Kpi {...p}/>;
const KpiBadge = (p) => <Kpi {...p}/>;

/* baseChart supprimé — remplacé par chartTheme */

/* ════════════════════════════════════════════════════════════
   PROFIL PAYS
════════════════════════════════════════════════════════════ */
function ProfilPays({ data, annee, chartH, winW }) {
  const navigate    = useNavigate();
  const [ratioTab, setRatioTab] = useState("Vie");
  const [showDD,   setShowDD]   = useState(false);

  /* Evolution marché */
  const [evData, setEvData] = useState([]);
  useEffect(()=>{
    fetch(`${API}/api/apercu-marche/evolution?nb_annees=10`)
      .then(r=>r.ok?r.json():[]).then(setEvData).catch(()=>{});
  },[]);
  const years = evData.length ? evData.map(d=>String(d.annee)) : ["2020","2021","2022","2023","2024"];
  const evSeries = [
    {name:"Vie",     data:evData.map(d=>d.vie!=null?Math.round(d.vie):null)},
    {name:"Non-Vie", data:evData.map(d=>d.non_vie!=null?Math.round(d.non_vie):null)},
    {name:"Total",   data:evData.map(d=>d.total!=null?Math.round(d.total):null)},
  ];
  const evOpts = {
    chart: { type:"area", toolbar:{show:false}, fontFamily:"Barlow,system-ui,sans-serif", background:"transparent", animations:{enabled:false} },
    colors: [C.yellow, C.blue, C.dark],
    stroke: { width:[2,2,2.5], curve:"smooth" },
    fill: {
      type:"gradient",
      gradient:{ shade:"light", type:"vertical", shadeIntensity:.05, opacityFrom:.25, opacityTo:0, stops:[0,100] },
    },
    markers: { size:0, hover:{size:5} },
    dataLabels: { enabled:false },
    xaxis: {
      categories: years,
      labels: { style:{ colors:G, fontSize:"11px", fontFamily:"Barlow,system-ui,sans-serif" }, rotate:0 },
      axisBorder:{ show:false }, axisTicks:{ show:false },
    },
    yaxis: {
      labels: {
        style:{ colors:G, fontSize:"11px", fontFamily:"Barlow,system-ui,sans-serif" },
        formatter: v => v!=null ? `${Math.round(v/1000).toFixed(1)}k` : "",
      },
    },
    grid: { borderColor:"#EBEBEF", strokeDashArray:4, xaxis:{lines:{show:false}}, yaxis:{lines:{show:true}} },
    legend: {
      position:"top", horizontalAlign:"left", fontSize:"11px", fontWeight:600,
      fontFamily:"Barlow,system-ui,sans-serif", labels:{colors:D},
      markers:{radius:3,width:12,height:6,offsetY:1}, itemMargin:{horizontal:14},
    },
    tooltip: { shared:true, y:{ formatter: v => v!=null ? `${Math.round(v).toLocaleString("fr-TN")} MDT` : "—" } },
   annotations: {
  xaxis: [{
    x: "2018",
    label: {
      text: "Données non disponibles",
      position: "top",
      offsetY: -12,
      style: {
        background: "#2e2b2a",
        color: "#ffffff",
        fontSize: "9px",
        fontWeight: 900,
        fontFamily: "Barlow, sans-serif",
        padding: { left: 10, right: 10, top: 4, bottom: 4 },
        borderRadius: 6,
      }
    }
  }]
},
  };

  /* Ratios */
  const [ratiosApi, setRatiosApi] = useState(null);
  useEffect(()=>{
    fetch(`${API}/api/apercu-marche/ratios?annee=${annee}`)
      .then(r=>r.ok?r.json():null).then(setRatiosApi).catch(()=>{});
  },[annee]);
  const rd = ratiosApi ? {"Vie":ratiosApi.vie,"Non-Vie":ratiosApi.non_vie,"Total":ratiosApi.total}[ratioTab] : null;

  const [ratiosEv, setRatiosEv] = useState([]);
  useEffect(()=>{
    fetch(`${API}/api/apercu-marche/ratios-evolution?nb_annees=10`)
      .then(r=>r.ok?r.json():[]).then(setRatiosEv).catch(()=>{});
  },[]);
  const ratioYears = ratiosEv.length ? ratiosEv.map(d=>String(d.annee)) : years;
  const RF = {"Vie":{sp:"vie_sp",f:"vie_frais",c:"vie_combine"},"Non-Vie":{sp:"non_vie_sp",f:"non_vie_frais",c:"non_vie_combine"},"Total":{sp:"total_sp",f:"total_frais",c:"total_combine"}}[ratioTab];
  const ratioOpts = {
    chart: { type:"line", toolbar:{show:false}, fontFamily:"Barlow,system-ui,sans-serif", background:"transparent", animations:{enabled:false} },
    colors: [C.dark, C.yellow, C.blue],
    stroke: { width:[2.5,2.5,3], curve:"smooth", dashArray:[4,4,0] },
    markers: { size:[3,3,4], strokeColors:"#fff", strokeWidth:2, hover:{size:6} },
    dataLabels: { enabled:false },
    xaxis: {
      categories: ratioYears,
      labels: { style:{ colors:G, fontSize:"11px", fontFamily:"Barlow,system-ui,sans-serif" } },
      axisBorder:{ show:false }, axisTicks:{ show:false },
    },
    yaxis: {
      min:0, max:130, tickAmount:5,
      labels: {
        style:{ colors:G, fontSize:"11px", fontFamily:"Barlow,system-ui,sans-serif" },
        formatter: v => `${v}%`,
      },
    },
    grid: { borderColor:"#EBEBEF", strokeDashArray:4, xaxis:{lines:{show:false}}, yaxis:{lines:{show:true}} },
    legend: {
      position:"top", horizontalAlign:"left", fontSize:"11px", fontWeight:600,
      fontFamily:"Barlow,system-ui,sans-serif", labels:{colors:D},
      markers:{radius:3,width:14,height:4,offsetY:2}, itemMargin:{horizontal:14},
    },
    annotations: { yaxis:[{ y:100, borderColor:"#EF4444", borderWidth:1.5, strokeDashArray:3, label:{ text:"100%", style:{ color:"#EF4444", fontSize:"10px", fontWeight:700, background:"transparent", border:"none" } } }] },
    tooltip: { shared:true, y:{ formatter: v => v!=null ? `${v}%` : "—" } },
  };
  const ratioSeries = [
    {name:"S/P",    data:ratiosEv.map(d=>RF?d[RF.sp]:null)},
    {name:"Frais",  data:ratiosEv.map(d=>RF?d[RF.f]:null)},
    {name:"Combiné",data:ratiosEv.map(d=>RF?d[RF.c]:null)},
  ];

  /* Structure portefeuille */
  const b = data?.branches_non_vie ?? {};
  const totalB = Object.values(b).reduce((s,v)=>s+(v??0),0) || 1;
  const PROD_COLORS = [D, Y, G, "#A8A8B8", "#C8C8D8"];
  const produits = [
    {label:"Automobile",    val:b.automobile,    color:PROD_COLORS[0]},
    {label:"Groupe Maladie",val:b.groupe,         color:PROD_COLORS[1]},
    {label:"Incendie",      val:b.incendie,       color:PROD_COLORS[2]},
    {label:"Risques Divers",val:b.risques_divers, color:PROD_COLORS[3]},
    {label:"Transport",     val:b.transport,      color:PROD_COLORS[4]},
  ].map(p=>({...p, pct:p.val!=null?Math.round(p.val/totalB*100):0, mdt:p.val!=null?`${fmt(p.val,0)} MDT`:"—"}));

  /* Classement */
  const [classement, setClassement] = useState([]);
  useEffect(()=>{
    fetch(`${API}/api/classement-compagnies?annee=${annee}`)
      .then(r=>r.ok?r.json():[]).then(d=>{if(d?.length)setClassement(d);}).catch(()=>{});
  },[annee]);
  const top3    = classement.slice(0,3);
  const leaders = classement.slice(0,10);

  /* Valeurs synthèse */
  const totalVal  = data ? `${fmt(data.total_primes_emises_mdt,0)} MDT` : "—";
  const vieVal    = data ? `${fmt(data.primes_vie_mdt,0)} MDT` : "—";
  const nvVal     = data ? `${fmt(data.primes_non_vie_mdt,0)} MDT` : "—";
  const viePct    = data ? `${fmt(data.part_vie_pct,0)}%` : "—";
  const nvPct     = data ? `${fmt(data.part_non_vie_pct,0)}%` : "—";
  const growth    = data?.croissance_primes_pct != null ? fmtG(data.croissance_primes_pct) : null;
  const growthPos = data ? (data.croissance_primes_pct ?? 0) >= 0 : true;

  /* Dropdown ratios */
  const RatioDropdown = (
    <div style={{ position:"relative" }}>
      <button onClick={()=>setShowDD(!showDD)} style={{
        display:"flex", alignItems:"center", gap:5,
        background:Y, border:"none", cursor:"pointer",
        padding:"3px 9px", borderRadius:5, fontSize:10, fontWeight:800, color:D,
      }}>
        {ratioTab}
        <svg viewBox="0 0 10 10" fill="none" width="7" height="7">
          <path d="M2 3.5l3 3 3-3" stroke={D} strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
      </button>
      {showDD && (
        <div style={{ position:"absolute", right:0, top:"calc(100% + 4px)", background:WH, border:`1px solid ${BDR}`, borderRadius:7, boxShadow:"0 8px 24px rgba(0,0,0,.12)", zIndex:50, minWidth:100, overflow:"hidden" }}>
          {["Vie","Non-Vie","Total"].map(o=>(
            <button key={o} onClick={()=>{setRatioTab(o);setShowDD(false);}} style={{
              display:"block",width:"100%",textAlign:"left",padding:"8px 12px",
              fontSize:11,fontWeight:ratioTab===o?800:500,border:"none",cursor:"pointer",
              color:ratioTab===o?D:G, background:ratioTab===o?`${Y}44`:WH,
            }}>{o}</button>
          ))}
        </div>
      )}
    </div>
  );

  return (
    <div style={{ display:"grid", gridTemplateColumns:"34% 24% 42%", gap:12, flex:1, minHeight:0 }}>

      {/* ── COL 1 : Taille du marché + évolution ── */}
      <Card style={{ display:"flex", flexDirection:"column", overflow:"hidden", padding:"14px 16px" }}>
        <SectionTitle>Taille du marché</SectionTitle>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:6, flexShrink:0, marginBottom:8 }}>
          <Kpi label="Total"   value={totalVal} sub={`Données ${annee}`} delta={growth||null} pos={growthPos} accent/>
          <Kpi label="Vie"     value={vieVal}   sub={viePct}/>
          <Kpi label="Non-Vie" value={nvVal}    sub={nvPct}/>
        </div>
        <div style={{ fontSize:9, fontWeight:700, color:G, letterSpacing:"1.2px", textTransform:"uppercase", marginBottom:4, flexShrink:0 }}>Évolution des primes émises (MDT) — Vie · Non-Vie</div>
        <div style={{ flex:1, minHeight:0 }}>
          <ReactApexChart options={evOpts} series={evSeries} type="area" height="100%"/>
        </div>
      </Card>

      {/* ── COL 2 : Ratios (haut) + Structure portefeuille (bas) ── */}
      <div style={{ display:"flex", flexDirection:"column", gap:10, overflow:"hidden" }}>

        {/* Ratios techniques — en haut */}
        <Card style={{ flexShrink:0, padding:"12px 14px", display:"flex", flexDirection:"column" }}>
          <SectionTitle action={RatioDropdown}>Ratios techniques</SectionTitle>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:6 }}>
            {[
              { k:"S/P",     v:rd?.ratio_sp_pct,     sub:"Sinistres/Primes", range:[0,140], zones:[70,100] },
              { k:"Frais",   v:rd?.ratio_frais_pct,  sub:"Frais/Primes",     range:[0,50],  zones:[15,25] },
              { k:"Combiné", v:rd?.ratio_combine_pct,sub:"Ratio global",      range:[0,140], zones:[90,100] },
            ].map((r,i)=>{
              const vNum = r.v != null ? Number(r.v) : null;
              const vStr = vNum!=null ? `${vNum.toFixed(1)}%` : ratiosApi===null ? "…" : "—";
              const [lo, hi] = r.zones;
              const [rMin, rMax] = r.range;
              return (
                <div key={i}
                  onMouseEnter={e=>{e.currentTarget.style.transform="translateY(-2px)";e.currentTarget.style.boxShadow="0 10px 28px rgba(46,46,56,.10)";}}
                  onMouseLeave={e=>{e.currentTarget.style.transform="none";e.currentTarget.style.boxShadow="0 2px 8px rgba(46,46,56,.05)";}}
                  style={{ background:WH, borderRadius:7, padding:"12px 14px 10px", display:"flex", flexDirection:"column", minWidth:0,
                    boxShadow:"0 2px 8px rgba(46,46,56,.05)", transition:"transform .16s ease, box-shadow .16s ease",
                    borderLeft:`3px solid ${i===0?Y:i===1?"#5B5BFF":"transparent"}`,
                    border:"1px solid #EBEBF2", borderLeft:`3px solid ${i===0?Y:i===1?"#5B5BFF":D}`,
                  }}>
                  <div style={{ fontSize:7.5, fontWeight:700, letterSpacing:"2px", textTransform:"uppercase", color:"#9898B0", marginBottom:6 }}>{r.k}</div>
                  <div style={{ fontSize:22, fontWeight:900, color:D, lineHeight:1, fontVariantNumeric:"tabular-nums", letterSpacing:"-0.5px" }}>{vStr}</div>
                  <div style={{ fontSize:8, color:"#ABABC2", marginTop:5 }}>{r.sub}</div>
                </div>
              );
            })}
          </div>
        </Card>

        {/* Structure portefeuille — donut EY */}
        <Card style={{ flex:1, padding:"12px 14px 10px", display:"flex", flexDirection:"column", overflow:"hidden" }}>
          <SectionTitle>Structure du portefeuille</SectionTitle>
          <div style={{ flex:1, minHeight:0, paddingTop:10 }}>
            <ReactApexChart
              key={`portfolio-donut-${annee}`}
              options={{
                chart:{ type:"donut", fontFamily:"Barlow,system-ui,sans-serif", background:"transparent", animations:{enabled:false}, toolbar:{show:false} },
                colors: PROD_COLORS,
                labels: produits.map(p=>p.label),
                plotOptions:{ pie:{ donut:{
                  size:"62%",
                  labels:{
                    show:true,
                    total:{ show:true, showAlways:true, label:"Non-Vie", fontSize:"9px", fontWeight:700, color:G, fontFamily:"Barlow,system-ui,sans-serif", formatter:()=>totalVal },
                    value:{ fontSize:"15px", fontWeight:800, color:D, fontFamily:"Barlow,system-ui,sans-serif", formatter:v=>`${Math.round(v)}%` },
                    name:{ fontSize:"10px", fontWeight:700, color:G, fontFamily:"Barlow,system-ui,sans-serif" },
                  }
                }}},
                dataLabels:{
                  enabled:true,
                  formatter: val => `${Math.round(val)}%`,
                  style:{ fontSize:"10px", fontWeight:700, fontFamily:"Barlow,system-ui,sans-serif", colors:["#fff"] },
                  dropShadow:{ enabled:false },
                },
                legend:{
                  position:"right", fontSize:"10px", fontWeight:700,
                  fontFamily:"Barlow,system-ui,sans-serif", labels:{colors:D},
                  markers:{ radius:2, width:8, height:8, offsetY:1 },
                  itemMargin:{ vertical:4 },
                  formatter:(name, opts)=>{
                    const p = produits[opts.seriesIndex];
                    return `${name}  ${p?.pct ?? 0}%`;
                  },
                },
                stroke:{ width:2, colors:["#FFFFFF"] },
                tooltip:{ y:{ formatter:(v,{seriesIndex})=>produits[seriesIndex]?.mdt||"" }, style:{fontFamily:"Barlow,system-ui,sans-serif",fontSize:"12px"} },
                grid:{ padding:{ top:-10, bottom:-10 } },
              }}
              series={produits.map(p=>p.pct)}
              type="donut"
              height="100%"
            />
          </div>
        </Card>
      </div>

      {/* ── COL 3 : Structure concurrentielle — Skyline de puissance ── */}
      {(() => {
        const maxPdm  = leaders[0]?.pdm_pct || 20;
        const eqShare = (100 / (leaders.length || 10));
        /* Leader=jaune EY · Challengers=anthracite EY · Followers=gris EY */
        const BAR_COLS = [Y, "#2E2E38", "#44445A", "#5A5A74", "#70708C", "#909098", "#A8A8B4", "#C0C0CC", "#D4D4DE", "#E8E8EE"];

        const shortCode = code => {
          const full = COMPANY_LABELS[code] ?? code;
          return full.replace(/\b(assurances?|tunisienne?|nationale?|générale?|compagnie)\b/gi,'')
                     .trim().split(/\s+/).filter(Boolean).slice(0,1).join('').toUpperCase().slice(0,5);
        };

        return (
          <Card style={{ padding:0, display:"flex", flexDirection:"column", overflow:"hidden" }}>
            <div style={{ padding:"12px 14px 6px", flexShrink:0 }}>
              <SectionTitle action={
                <button onClick={()=>navigate("/analyse-comparative")} style={{
                  display:"flex", alignItems:"center", gap:6,
                  background:D, color:Y, border:"none", cursor:"pointer",
                  padding:"4px 11px", borderRadius:6, fontSize:9, fontWeight:800, letterSpacing:"1px",
                }}>
                  COMPARATIF
                  <svg viewBox="0 0 12 10" fill="none" width="9" height="9"><path d="M1 5h10M7 1l4 4-4 4" stroke={Y} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </button>
              }>Structure concurrentielle</SectionTitle>
            </div>

            {/* Indicateur métrique */}
            <div style={{ padding:"0 14px 6px", flexShrink:0, display:"flex", alignItems:"center", gap:8 }}>
              <span style={{ fontSize:7.5, fontWeight:700, letterSpacing:"1.5px", textTransform:"uppercase", color:G }}>Part de marché PDM% · classement {annee}</span>
              <div style={{ flex:1, height:"1px", background:BDR }}/>
              <span style={{ fontSize:7.5, color:G, whiteSpace:"nowrap" }}>
                — — part égale {eqShare.toFixed(1)}%
              </span>
            </div>

            {/* Skyline */}
            <div style={{ flex:1, minHeight:0, padding:"0 14px 10px", display:"flex", flexDirection:"column" }}>
              {/* Zone barres : flex:1, alignement bas */}
              <div style={{
                flex:1, minHeight:0,
                display:"flex", alignItems:"flex-end",
                justifyContent:"space-between",
                gap:5, position:"relative",
              }}>
                {/* Ligne part égale */}
                <div style={{
                  position:"absolute", left:0, right:0,
                  bottom:`${(eqShare/maxPdm)*100}%`,
                  borderTop:"1.5px dashed rgba(116,116,128,.35)",
                  pointerEvents:"none", zIndex:1,
                }}/>

                {leaders.map((c, i) => {
                  const pdm    = c.pdm_pct || 0;
                  const hPct   = `${(pdm / maxPdm) * 88}%`;
                  const isL    = i === 0;
                  const bg     = BAR_COLS[i] ?? G;
                  const code   = shortCode(c.entreprise);
                  return (
                    <div key={c.entreprise}
                      style={{ flex:1, display:"flex", flexDirection:"column", alignItems:"center", height:"100%", justifyContent:"flex-end", zIndex:2 }}
                    >
                      {/* Couronne leader */}
                      {isL && <div style={{ fontSize:11, lineHeight:1, marginBottom:2, filter:"drop-shadow(0 0 4px rgba(255,230,0,.6))" }}>👑</div>}

                      {/* Valeur PDM */}
                      <div style={{ fontSize:isL?10:8, fontWeight:900, color:isL?Y:D, lineHeight:1, marginBottom:3, fontVariantNumeric:"tabular-nums" }}>
                        {pdm.toFixed(1)}%
                      </div>

                      {/* Barre */}
                      <div
                        title={`#${i+1} · ${COMPANY_LABELS[c.entreprise]??c.entreprise} · ${pdm.toFixed(1)}% PDM`}
                        onMouseEnter={e=>{ e.currentTarget.style.filter="brightness(1.15)"; e.currentTarget.style.transform="scaleX(1.08)"; }}
                        onMouseLeave={e=>{ e.currentTarget.style.filter="none"; e.currentTarget.style.transform="none"; }}
                        style={{
                          width:"100%", height:hPct,
                          background: isL
                            ? `linear-gradient(180deg,${Y} 0%,#D4B800 100%)`
                            : `linear-gradient(180deg,${bg} 0%,${bg}AA 100%)`,
                          borderRadius:"4px 4px 2px 2px",
                          boxShadow: isL
                            ? "0 0 14px rgba(255,230,0,.35), 0 3px 10px rgba(0,0,0,.18)"
                            : "0 2px 8px rgba(0,0,0,.12)",
                          cursor:"default",
                          transition:"filter .14s, transform .14s",
                          transformOrigin:"bottom",
                          minHeight:8,
                        }}
                      />

                      {/* Rang */}
                      <div style={{ fontSize:7.5, fontWeight:800, color:isL?Y:G, marginTop:4, lineHeight:1 }}>#{i+1}</div>
                      {/* Abréviation */}
                      <div style={{ fontSize:7, color:G, lineHeight:1, marginTop:2, letterSpacing:".3px" }}>{code}</div>
                    </div>
                  );
                })}
              </div>

              {/* Légende bas */}
              <div style={{ marginTop:10, display:"flex", alignItems:"center", gap:10, flexShrink:0 }}>
                <div style={{ width:22, height:10, background:Y, borderRadius:2 }}/>
                <span style={{ fontSize:7.5, color:G }}>Leader</span>
                <div style={{ width:22, height:10, background:"linear-gradient(90deg,#2E2E38,#70708C)", borderRadius:2, marginLeft:8 }}/>
                <span style={{ fontSize:7.5, color:G }}>Challengers #2–5</span>
                <div style={{ width:22, height:10, background:"linear-gradient(90deg,#909098,#E8E8EE)", borderRadius:2, marginLeft:8 }}/>
                <span style={{ fontSize:7.5, color:G }}>Suiveurs #6+</span>
              </div>
            </div>
          </Card>
        );
      })()}
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   CLASSEMENT TAB
════════════════════════════════════════════════════════════ */
function ClassementTab({ annee }) {
  const navigate = useNavigate();
  const [classement, setClassement] = useState([]);
  useEffect(()=>{
    fetch(`${API}/api/classement-compagnies?annee=${annee}`)
      .then(r=>r.ok?r.json():[]).then(d=>{if(d?.length)setClassement(d);}).catch(()=>{});
  },[annee]);
  const top3    = classement.slice(0,3);
  const leaders = classement.slice(0,10);

  return (
    <Card style={{ padding:0, flex:1, display:"flex", flexDirection:"column", overflow:"hidden" }}>
      <div style={{ padding:"14px 20px 10px", display:"flex", alignItems:"center", justifyContent:"space-between", flexShrink:0 }}>
        <SectionTitle action={
          <button onClick={()=>navigate("/analyse-comparative")} style={{
            display:"flex", alignItems:"center", gap:8,
            background:D, color:Y, border:"none", cursor:"pointer",
            padding:"6px 14px", borderRadius:8, fontSize:10, fontWeight:800, letterSpacing:"1px",
          }}>
            ANALYSE CONCURRENTIELLE
            <svg viewBox="0 0 12 10" fill="none" width="10" height="10"><path d="M1 5h10M7 1l4 4-4 4" stroke={Y} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </button>
        }>Structure concurrentielle — {annee}</SectionTitle>
      </div>
      <div style={{ display:"flex", flex:1, minHeight:0, borderTop:`1px solid ${BDR}`, overflow:"hidden" }}>
        {/* Podium top 3 */}
        <div style={{ width:270, flexShrink:0, borderRight:`1px solid ${BDR}`, overflowY:"auto" }}>
          {top3.map((c,i)=>{
            const bgMap=[`${Y}22`,"#F7F8FA","#F9F9FA"];
            const accentMap=[Y,"#D1D5DB","#DEB887"];
            return (
              <div key={c.entreprise} style={{ display:"flex", alignItems:"center", gap:12, padding:"16px 16px", borderBottom:i<2?`1px solid ${BDR}`:"none", background:bgMap[i] }}>
                <div style={{ width:32, height:32, borderRadius:7, flexShrink:0, background:accentMap[i], display:"flex", alignItems:"center", justifyContent:"center", fontSize:13, fontWeight:900, color:i===0?D:"#888" }}>#{i+1}</div>
                <div style={{ width:76, height:42, background:WH, flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center", padding:"3px 8px", border:`1px solid ${i===0?Y+"88":BDR}`, borderRadius:5 }}>
                  {getLogoSrc(c.entreprise)
                    ? <img src={getLogoSrc(c.entreprise)} alt={c.entreprise} style={{ maxHeight:32, maxWidth:66, objectFit:"contain" }}/>
                    : <span style={{ fontSize:9, fontWeight:800, color:D }}>{COMPANY_LABELS[c.entreprise]??c.entreprise}</span>
                  }
                </div>
                <div>
                  <div style={{ fontSize:9, fontWeight:600, color:G, marginBottom:2 }}>{COMPANY_LABELS[c.entreprise]??c.entreprise}</div>
                  <div style={{ fontSize:21, fontWeight:900, color:D, lineHeight:1, fontVariantNumeric:"tabular-nums" }}>{c.pdm_pct}%</div>
                  <div style={{ fontSize:9, color:G, marginTop:1 }}>part de marché</div>
                </div>
              </div>
            );
          })}
        </div>
        {/* Table */}
        <div style={{ flex:1, overflowY:"auto" }}>
          <table style={{ width:"100%", borderCollapse:"collapse" }}>
            <thead style={{ position:"sticky", top:0, zIndex:2 }}>
              <tr style={{ background:"#F5F5F7", borderBottom:"1px solid #E0E0E6" }}>
                {["Rang","Compagnie","Total Actif","Part de marché",""].map((h,i)=>(
                  <th key={i} style={{ padding:"10px 16px", textAlign:"left", fontSize:9, fontWeight:700, letterSpacing:"1.5px", textTransform:"uppercase", color:G }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {leaders.map((c,i)=>(
                <tr key={c.entreprise} style={{ borderBottom:`1px solid ${BDR}` }}
                  onMouseEnter={e=>e.currentTarget.style.background=`${Y}18`}
                  onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
                  <td style={{ padding:"9px 16px" }}>
                    <span style={{ display:"inline-block", fontSize:11, fontWeight:900, fontVariantNumeric:"tabular-nums", padding:"3px 9px", borderRadius:5, background:i===0?Y:i===1?"#E8E8EE":i===2?"#F4ECE0":"transparent", color:D }}>#{i+1}</span>
                  </td>
                  <td style={{ padding:"7px 16px" }}>
                    <div style={{ width:88, height:44, background:WH, border:`1px solid ${i===0?Y+"66":BDR}`, borderRadius:5, display:"inline-flex", alignItems:"center", justifyContent:"center", padding:"3px 8px" }}>
                      {getLogoSrc(c.entreprise)
                        ? <img src={getLogoSrc(c.entreprise)} alt={c.entreprise} style={{ maxHeight:34, maxWidth:74, objectFit:"contain" }}/>
                        : <span style={{ fontSize:9, fontWeight:800, color:D }}>{COMPANY_LABELS[c.entreprise]??c.entreprise}</span>
                      }
                    </div>
                  </td>
                  <td style={{ padding:"9px 16px", fontSize:12, fontWeight:700, color:D, fontVariantNumeric:"tabular-nums" }}>
                    {c.total_actif!=null ? `${Math.round(c.total_actif/1_000_000).toLocaleString("fr-TN")} MDT` : "—"}
                  </td>
                  <td style={{ padding:"9px 16px" }}>
                    <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                      <div style={{ width:80, height:5, background:"#F0F0F4", borderRadius:3 }}>
                        <div style={{ height:5, borderRadius:3, background:i===0?Y:D, width:`${Math.min((c.pdm_pct||0)/30*100,100)}%` }}/>
                      </div>
                      <span style={{ fontSize:13, fontWeight:900, color:D, minWidth:38, fontVariantNumeric:"tabular-nums" }}>{c.pdm_pct ?? 0}%</span>
                    </div>
                  </td>
                  <td style={{ padding:"9px 16px" }}/>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  );
}

/* ════════════════════════════════════════════════════════════
   DISTRIBUTION AGENCES
════════════════════════════════════════════════════════════ */
const REGION_ORDER_IDS = ["grand-tunis","nord-est","nord-ouest","centre-est","centre-ouest","sud-est","sud-ouest"];
const REGION_LABELS    = {"grand-tunis":"Grand Tunis","nord-est":"Nord-Est","nord-ouest":"Nord-Ouest","centre-est":"Centre-Est","centre-ouest":"Centre-Ouest","sud-est":"Sud-Est","sud-ouest":"Sud-Ouest"};

function DistributionAgences({ annee, chartH, winW }) {
  const [data, setData] = useState(null);
  useEffect(()=>{
    if(!annee) return;
    fetch(`${API}/api/apercu-marche/distribution-agences?annee=${annee}`)
      .then(r=>r.ok?r.json():null).then(setData).catch(()=>{});
  },[annee]);

  const gouvsData     = data?.gouvernorats ?? [];
  const maxN          = gouvsData.length ? Math.max(...gouvsData.map(g=>g.n)) : 1;
  const regionSeries  = REGION_ORDER_IDS.map(id=>data?.regions?.[id]?.pct??0);
  const regionLabels  = REGION_ORDER_IDS.map(id=>REGION_LABELS[id]);
  const totalStr      = data?.total_agences != null ? data.total_agences.toLocaleString("fr-FR") : "—";
  const mapData       = {};
  if(data?.regions){for(const[id,r]of Object.entries(data.regions)){mapData[id]={level:r.level,value:r.n!=null&&r.pct!=null?`${r.n} agences · ${r.pct}%`:""};}}
  const classement    = data?.classement ?? [];
  const maxCN         = classement.length ? classement[0].n : 1;
  const noteAnnee     = data && data.annee_cga !== annee ? `Données CGA de ${data.annee_cga} (dernière année disponible)` : null;

  const govColors = [C.dark, C.yellow, C.blue, C.orange, C.slate, C.grey];

  const donutOpts = {
    ...donut(regionLabels, () => totalStr),
    colors: CAT6,
    dataLabels: {
      enabled: true,
      formatter: (val) => `${val.toFixed(1)}%`,
      style: { fontSize:"11px", fontWeight:700, fontFamily:"Barlow,system-ui,sans-serif", colors:["#fff"] },
      dropShadow: { enabled:false },
    },
    plotOptions: { pie: { donut: { size:"62%", labels: { show:true, total: { show:true, showAlways:true, label:"Total", fontSize:"11px", fontWeight:700, fontFamily:"Barlow,system-ui,sans-serif", color:D, formatter: () => totalStr } } } } },
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:12, flex:1, minHeight:0 }}>
      {noteAnnee && (
        <div style={{ fontSize:10, color:G, fontStyle:"italic", padding:"7px 12px", background:WH, border:`1px solid ${BDR}`, borderRadius:6, flexShrink:0 }}>{noteAnnee}</div>
      )}

      {/* KPI Banner — même style fond sombre que Profil Pays */}
      <div style={{
        background:"linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)",
        borderRadius:8, display:"flex", overflow:"hidden", flexShrink:0,
        boxShadow:"0 4px 24px rgba(10,10,20,.38), 0 1px 0 rgba(255,255,255,.04) inset",
      }}>
        {[
          { label:"Total agences",        value: data?.total_agences!=null?data.total_agences.toLocaleString("fr-FR"):"—", sub:"agences en Tunisie" },
          { label:"Moyenne par assureur", value: data?.moyenne_agences!=null?String(data.moyenne_agences):"—",             sub:"agences par compagnie" },
          { label:"Leader réseau",        value: data?.leader_reseau??"—",                                                  sub:"plus grand réseau national" },
          { label:"Région concentrée",    value: data?.region_concentree??"—",                                              sub: data?.region_concentree_pct!=null?`${data.region_concentree_pct}% des agences`:"" },
        ].map((k, i) => (
          <div key={i} style={{ flex:1, minWidth:0, padding:"14px 20px 12px", borderLeft: i>0?"1px solid rgba(255,255,255,.07)":"none", display:"flex", flexDirection:"column" }}>
            <div style={{ fontSize:7.5, fontWeight:700, letterSpacing:"2px", textTransform:"uppercase", color:"rgba(255,255,255,.38)", marginBottom:8 }}>{k.label}</div>
            <div style={{ fontSize:26, fontWeight:300, lineHeight:1, fontVariantNumeric:"tabular-nums", letterSpacing:"-0.8px", marginBottom:6, color:WH, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{k.value}</div>
            <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:"auto" }}>
              {k.sub && <span style={{ fontSize:9.5, color:"rgba(255,255,255,.30)" }}>{k.sub}</span>}
            </div>
          </div>
        ))}
      </div>

      {/* 3 colonnes flex:1 */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12, flex:1, minHeight:0 }}>

        <Card style={{ display:"flex", flexDirection:"column", overflow:"hidden" }}>
          <SectionTitle>Par gouvernorat</SectionTitle>
          <div style={{ flex:1, overflowY:"auto", display:"flex", flexDirection:"column", gap:2 }}>
            {gouvsData.map((g,i)=>{
              const pct = (g.n / maxN) * 100;
              const col = govColors[i] ?? G;
              return (
                <div key={g.nom} style={{ display:"flex", alignItems:"center", gap:8, padding:"2px 0" }}>
                  <div style={{ width:68, fontSize:10, fontWeight:600, color:D, textAlign:"right", flexShrink:0 }}>{g.nom}</div>
                  <div style={{ flex:1, height:16, background:"#F3F4F6", borderRadius:3, overflow:"hidden" }}>
                    <div style={{ height:"100%", width:`${pct}%`, background:col, borderRadius:3 }}/>
                  </div>
                  <div style={{ display:"flex", gap:4, alignItems:"center", minWidth:56, flexShrink:0 }}>
                    <span style={{ fontSize:11, fontWeight:900, color:D, fontVariantNumeric:"tabular-nums" }}>{g.n}</span>
                    <span style={{ fontSize:9, color:G }}>({g.pct}%)</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <Card style={{ display:"flex", flexDirection:"column", overflow:"hidden" }}>
          <SectionTitle>Par région</SectionTitle>
          <div style={{ flex:1, minHeight:0 }}>
            <ReactApexChart key={`donut-region-${data?.annee_cga}`} options={donutOpts} series={regionSeries} type="donut" height="100%"/>
          </div>
        </Card>

        <Card style={{ display:"flex", flexDirection:"column", overflow:"hidden" }}>
          <SectionTitle>Carte réseau national</SectionTitle>
          <div style={{ flex:1, overflow:"hidden" }}>
            <TunisiaMap data={mapData}/>
          </div>
        </Card>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════════════════
   PAGE PRINCIPALE
════════════════════════════════════════════════════════════ */
export default function ApercuMarche() {
  const [tab,          setTab]          = useState("profil");
  const [année,        setAnnée]        = useState(2024);
  const [showYearDD,   setShowYearDD]   = useState(false);
  const [années,       setAnnées]       = useState([2024,2023,2022,2021,2020]);
  const [profilData,   setProfilData]   = useState(null);
  const [profilLoad,   setProfilLoad]   = useState(true);

  useEffect(()=>{
    fetch(`${API}/api/apercu-marche/annees`)
      .then(r=>r.ok?r.json():null).then(d=>{
        if(d?.length){const fil=d.filter(a=>a>=2014&&a<=2024);setAnnées(fil);setAnnée(fil[0]);}
      }).catch(()=>{});
  },[]);

  useEffect(()=>{
    setProfilLoad(true);
    fetch(`${API}/api/apercu-marche/profil-pays?annee=${année}`)
      .then(r=>r.ok?r.json():null)
      .then(d=>{setProfilData(d);setProfilLoad(false);})
      .catch(()=>{setProfilData(null);setProfilLoad(false);});
  },[année]);

  const lv = v => v != null ? v : profilLoad ? "…" : "—";

  /* Dimensions dynamiques basées sur la taille de l'écran réel */
  const { w: winW, h: winH } = useWindowSize();
  const chartH = 190;

  const TABS = [
    {key:"profil",  label:"Profil Pays"},
    {key:"agences", label:"Distribution des agences"},
  ];

  /* KPI values */
  const kpiPop  = profilData?(profilData.population!=null?`${(profilData.population/1e6).toFixed(1)}M`:lv(null)):lv(null);
  const kpiPib  = profilData?(profilData.pib_mdt!=null?`${Math.round(profilData.pib_mdt/1000)} Md`:lv(null)):lv(null);
  const kpiPen  = profilData?`${fmt(profilData.taux_penetration_pct,2)}%`:lv(null);
  const kpiPenD = profilData?fmtG(profilData.var_penetration):null;
  const kpiPenP = profilData?(profilData.var_penetration??0)>=0:true;
  const kpiDen  = profilData?(profilData.densite_assurance_dt!=null?`${Math.round(profilData.densite_assurance_dt)}`:lv(null)):lv(null);
  const kpiDenD = profilData?fmtG(profilData.var_densite):null;
  const kpiDenP = profilData?(profilData.var_densite??0)>=0:true;
  const kpiAss  = profilData?(profilData.nb_assureurs!=null?String(profilData.nb_assureurs):lv(null)):lv(null);

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"#EEEEF4", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>

      {/* ══ BARRE TITRE sticky (titre + tabs + filtre uniquement) ══ */}
      <div style={{ background:WH, borderBottom:`1px solid ${BDR}`, flexShrink:0 }}>
        <div style={{ padding:"0 28px" }}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", height: winW<640?48:58, flexWrap:"wrap", gap: winW<640?4:0 }}>
            <div style={{ display:"flex", alignItems:"stretch", gap:0 }}>
              <div style={{ display:"flex", alignItems:"center", gap:10, paddingRight:24, marginRight:8, borderRight:`1px solid ${BDR}` }}>
                <img src="/logos/tn-flag.png" alt="TN" style={{ height:20, borderRadius:3, opacity:.85, flexShrink:0 }}/>
                <h1 style={{ fontSize:17, fontWeight:900, color:D, margin:0, letterSpacing:"-0.2px" }}>Aperçu marché</h1>
              </div>
              {TABS.map(t=>(
                <button key={t.key} onClick={()=>setTab(t.key)} style={{
                  padding:"0 20px", border:"none", background:"none", cursor:"pointer",
                  fontSize:13, fontWeight:tab===t.key?800:500,
                  color:tab===t.key?D:G,
                  borderBottom:`3px solid ${tab===t.key?Y:"transparent"}`,
                  transition:"all .15s", whiteSpace:"nowrap",
                }}>{t.label}</button>
              ))}
            </div>

            <div style={{ position:"relative", display:"flex", alignItems:"center", gap:10 }}>
              <span style={{ fontSize:10, fontWeight:700, color:G, letterSpacing:"1px", textTransform:"uppercase" }}>Année</span>
              <button onClick={()=>setShowYearDD(!showYearDD)} style={{
                display:"flex", alignItems:"center", gap:10,
                background:Y, border:"none", cursor:"pointer",
                padding:"8px 18px", borderRadius:9, fontSize:15, fontWeight:900, color:D,
                boxShadow:"0 2px 10px rgba(255,230,0,.35)", fontVariantNumeric:"tabular-nums",
              }}>
                {année}
                <svg viewBox="0 0 10 10" fill="none" width="10" height="10" style={{ transform:showYearDD?"rotate(180deg)":"none", transition:"transform .15s" }}>
                  <path d="M1.5 3.5l3 3 3-3" stroke={D} strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
              {showYearDD && (
                <div style={{ position:"absolute", right:0, top:"calc(100% + 8px)", background:WH, border:`1px solid ${BDR}`, borderRadius:12, boxShadow:"0 12px 32px rgba(0,0,0,.14)", zIndex:60, minWidth:120, overflow:"hidden" }}>
                  {années.map(a=>{
                    const nd = a===2018;
                    return (
                      <button key={a} onClick={nd?undefined:()=>{setAnnée(a);setShowYearDD(false);}} disabled={nd}
                        style={{
                          display:"flex", alignItems:"center", justifyContent:"space-between",
                          width:"100%", padding:"10px 16px", fontSize:13,
                          fontWeight:a===année?900:500,
                          color: nd?BDR:a===année?D:G,
                          background:a===année?`${Y}44`:WH,
                          border:"none", borderBottom:`1px solid ${BDR}`, cursor:nd?"default":"pointer",
                        }}>
                        <span>{a}{nd&&<span style={{fontSize:9,marginLeft:6,color:BDR}}>n/d</span>}</span>
                        {a===année&&!nd&&<span style={{color:D,fontWeight:900,fontSize:14}}>✓</span>}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ══ CONTENU no-scroll ══ */}
      <div style={{ flex:1, minHeight:0, overflow:"hidden", padding:"12px 24px 10px", display:"flex", flexDirection:"column", gap:12 }}>

        {/* ── BANNIÈRE KPI MACRO — fond sombre uniforme ── */}
        {tab==="profil" && (
          <div style={{
            background:"linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)",
            borderRadius:8, display:"flex", overflow:"hidden", flexShrink:0,
            boxShadow:"0 4px 24px rgba(10,10,20,.38), 0 1px 0 rgba(255,255,255,.04) inset",
          }}>
            {[
              { label:"Population",          value:kpiPop, sub:"habitants"                               },
              { label:"PIB",                 value:kpiPib, sub:"milliards TND"                           },
              { label:"Taux de pénétration", value:kpiPen, sub:`vs ${année-1}`, delta:kpiPenD, pos:kpiPenP },
              { label:"Densité d'assurance", value:kpiDen, sub:"TND / habitant",delta:kpiDenD, pos:kpiDenP },
              { label:"Assureurs actifs",    value:kpiAss, sub:"compagnies"                              },
            ].map((k, i) => (
              <div key={i} style={{
                flex:1, minWidth:0,
                padding:"14px 20px 12px",
                borderLeft: i>0 ? "1px solid rgba(255,255,255,.07)" : "none",
                display:"flex", flexDirection:"column",
              }}>
                <div style={{ fontSize:7.5, fontWeight:700, letterSpacing:"2px", textTransform:"uppercase", color:"rgba(255,255,255,.38)", marginBottom:8 }}>{k.label}</div>
                <div style={{ fontSize:28, fontWeight:300, lineHeight:1, fontVariantNumeric:"tabular-nums", letterSpacing:"-1px", marginBottom:6, color:WH, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{k.value}</div>
                <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:"auto" }}>
                  {k.sub && <span style={{ fontSize:10, color:"rgba(255,255,255,.30)" }}>{k.sub}</span>}
                  {k.delta && (
                    <span style={{ fontSize:10, fontWeight:800, marginLeft:"auto", flexShrink:0,
                      color: k.pos ? "#4ade80" : "#f87171",
                    }}>{k.pos?"↑":"↓"} {k.delta}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {tab==="profil"  && <ProfilPays         data={profilData} annee={année} winW={winW}/>}
        {tab==="agences" && <DistributionAgences annee={année}   winW={winW}/>}

        {/* ── Bande de news live ── */}
        <NewsTicker/>
      </div>
    </div>
  );
}
