import { useState, useEffect, useMemo } from "react";
import ReactApexChart from "react-apexcharts";
import { getLogoSrc } from "../utils/logos";
import { YearSelector, DarkKpiBanner } from "../components/PageHeaderBar";

const API = "http://localhost:8002";
const Y   = "#FFE600";
const D   = "#2E2E38";
const G   = "#747480";

/* ── Tier palette (EY brand) ── */
const COLOR_LEADER     = "#FFE600";   // #1  — jaune EY
const COLOR_CHALLENGER = "#2E2E38";   // #2–5 — anthracite EY
const COLOR_FOLLOWER   = "#747480";   // #6+  — gris EY
const COLOR_ND         = "#E5E7EB";   // pas de données

/* ── Seuils de catégorisation ──
   Leader     : rang 1 (meilleur score absolu)
   Challengers: rangs 2 à 5
   Followers  : rangs 6 et au-delà                */
function getTier(rank) {
  if (rank === 1) return "leader";
  if (rank <= 5)  return "challenger";
  return "follower";
}
function tierColor(rank) {
  const t = getTier(rank);
  if (t === "leader")     return COLOR_LEADER;
  if (t === "challenger") return COLOR_CHALLENGER;
  return COLOR_FOLLOWER;
}
function tierLabel(rank) {
  if (rank === 1) return "Leader";
  if (rank <= 5)  return "Challenger";
  return "Follower";
}

const ASSUREURS = [
  "STAR","COMAR","GAT","ASTREE","CARTE","LLOYD_TUNISIEN",
  "MAGHREBIA","BH","BIAT","TUNIS_RE","COTUNACE",
];
const ASSUREUR_LABELS = {
  STAR:"STAR", COMAR:"COMAR", GAT:"GAT", ASTREE:"ASTREE", CARTE:"CARTE",
  LLOYD_TUNISIEN:"LLOYD", MAGHREBIA:"MAGHREBIA", BH:"BH",
  BIAT:"BIAT", TUNIS_RE:"TUNIS RE", COTUNACE:"COTUNACE",
};
const INDICATEURS = {
  "Ratio combiné":      { field:"ratio_combine", unit:"%",    lowerBetter:true  },
  "Ratio sinistralité": { field:"ratio_sp",      unit:"%",    lowerBetter:true  },
  "Ratio de frais":     { field:"ratio_frais",   unit:"%",    lowerBetter:true  },
  "Part de marché":     { field:"pdm",           unit:"%",    lowerBetter:false },
  "Primes émises":      { field:"primes",        unit:" MDT", lowerBetter:false },
};
const SANS_DONNEES = [
  "AMI","BNA","UIB","HAYETT","CTAMA",
  "GAT VIE","CARTE VIE","LLOYD VIE","MAGHREBIA VIE",
  "ZITOUNA TAKAFUL","AL AMANAH TAKAFUL","AT-TAKAFULIA",
];

function useWindowSize() {
  const [s, setS] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const fn = () => setS({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);
  return s;
}

function ChevronDown({ color = D, size = 12 }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" width={size} height={size} style={{ flexShrink:0 }}>
      <path d="M2.5 4.5L6 8l3.5-3.5" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/* ── Badge de tier ── */
function TierBadge({ rank }) {
  const t = getTier(rank);
  const colors = {
    leader:     { bg:"#FFF8CC", color:"#6B5000", border:"#FFE600" },
    challenger: { bg:"#EEEEF4", color:"#2E2E38", border:"#2E2E38" },
    follower:   { bg:"#F3F3F7", color:"#5E5E74", border:"#747480" },
  };
  const c = colors[t];
  return (
    <span style={{
      fontSize:8, fontWeight:800, padding:"2px 7px", borderRadius:20,
      background:c.bg, color:c.color, border:`1px solid ${c.border}`,
      whiteSpace:"nowrap", textTransform:"uppercase", letterSpacing:"0.5px",
    }}>{tierLabel(rank)}</span>
  );
}

export default function AnalyseComparative() {
  const { h: winH } = useWindowSize();
  const chartH = Math.max(180, winH - 400);

  const [selected,      setSelected]      = useState(new Set(ASSUREURS));
  const [indicateur,    setIndicateur]    = useState("Ratio combiné");
  const [showIndDD,     setShowIndDD]     = useState(false);
  const [showAssDD,     setShowAssDD]     = useState(false);
  const [annee,         setAnnee]         = useState(2024);
  const [apiData,       setApiData]       = useState({});
  const années = [2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014];

  useEffect(() => {
    setApiData({});
    fetch(`${API}/api/analyse-comparative?annee=${annee}`)
      .then(r => r.ok ? r.json() : {})
      .then(setApiData)
      .catch(() => {});
  }, [annee]);

  const toggleAssureur = (a) => {
    const s = new Set(selected);
    if (s.has(a)) { if (s.size > 1) s.delete(a); } else s.add(a);
    setSelected(s);
  };

  const ind      = INDICATEURS[indicateur];
  const filtered = ASSUREURS.filter(a => selected.has(a));
  const vals     = filtered.map(a => apiData[a]?.[ind.field] ?? null);

  /* Classement des compagnies avec données pour déterminer les tiers */
  const rankMap = useMemo(() => {
    const withData = filtered
      .map((a, i) => ({ a, v: vals[i] }))
      .filter(x => x.v != null)
      .sort((x, y) => ind.lowerBetter ? x.v - y.v : y.v - x.v);
    const m = {};
    withData.forEach((x, i) => { m[x.a] = i + 1; });
    return m;
  }, [filtered, vals, ind]);

  const barColors = vals.map((v, i) => {
    if (v == null) return COLOR_ND;
    const rank = rankMap[filtered[i]];
    return rank ? tierColor(rank) : COLOR_FOLLOWER;
  });

  const labelColors = vals.map((v, i) => {
    if (v == null) return "#9CA3AF";
    const rank = rankMap[filtered[i]];
    return rank === 1 ? D : "#FFFFFF";
  });

  const Y_AXIS_W = 54;

  const chartOpts = {
    chart: {
      type:"bar", toolbar:{ show:false },
      fontFamily:"Barlow, system-ui, sans-serif",
      animations:{ enabled:false }, background:"transparent",
    },
    plotOptions: { bar:{ columnWidth:"58%", borderRadius:4, borderRadiusApplication:"end", distributed:true } },
    colors: barColors,
    legend: { show:false },
    xaxis: {
      categories: filtered.map(a => ASSUREUR_LABELS[a] ?? a),
      labels:{ show:false },
      axisBorder:{ show:false }, axisTicks:{ show:false },
    },
    yaxis: {
      labels:{
        formatter: v => `${v}${ind.unit}`,
        style:{ colors:"#747480", fontSize:"11px", fontFamily:"Barlow, system-ui, sans-serif" },
        minWidth: Y_AXIS_W, maxWidth: Y_AXIS_W,
      },
      min:0,
    },
    grid: {
      borderColor:"#EBEBEF", strokeDashArray:4,
      xaxis:{ lines:{ show:false } }, yaxis:{ lines:{ show:true } },
      padding:{ left:0, right:4, bottom:-10 },
    },
    dataLabels: {
      enabled:true,
      formatter: (v, { dataPointIndex }) => {
        const orig = vals[dataPointIndex];
        return orig != null ? `${orig}${ind.unit}` : "N/D";
      },
      style:{ fontSize:"11px", fontWeight:700, fontFamily:"Barlow, system-ui, sans-serif", colors: labelColors },
      background:{ enabled:false },
      offsetY: -7,
    },
    tooltip: {
      style:{ fontFamily:"Barlow, system-ui, sans-serif", fontSize:"12px" },
      y:{ formatter: (v, { dataPointIndex }) => {
        const orig = vals[dataPointIndex];
        const a    = filtered[dataPointIndex];
        const rank = rankMap[a];
        const tier = rank ? ` — ${tierLabel(rank)}` : "";
        return orig != null ? `${orig}${ind.unit}${tier}` : "Donnée non disponible";
      }},
    },
  };

  /* Classement complet pour le panel droit */
  const rankingList = useMemo(() => {
    return filtered
      .map((a, i) => ({ a, v: vals[i], rank: rankMap[a] ?? null }))
      .filter(x => x.v != null)
      .sort((x, y) => ind.lowerBetter ? x.v - y.v : y.v - x.v);
  }, [filtered, vals, rankMap, ind]);

  /* KPI banner — leader parmi les compagnies affichées */
  const leader = rankingList[0];
  const validVals = vals.filter(v => v != null);

  return (
    <div
      style={{ height:"calc(100vh - 92px)", background:"#EEEEF4", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}
      onClick={() => { if (showIndDD) setShowIndDD(false); if (showAssDD) setShowAssDD(false); }}
    >

      {/* ── Header ── */}
      <div style={{ background:"#FFFFFF", borderBottom:"1px solid #E5E7EB", flexShrink:0 }}>
        <div style={{ padding:"0 28px" }}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", height:58 }}>
            <div style={{ display:"flex", alignItems:"center", gap:10 }}>
              <img src="/logos/tn-flag.png" alt="TN" style={{ height:20, borderRadius:3, opacity:.85, flexShrink:0 }}/>
              <h1 style={{ fontSize:17, fontWeight:900, color:D, margin:0, letterSpacing:"-0.2px" }}>Analyse Comparative</h1>
            </div>
            <div style={{ display:"flex", gap:10, alignItems:"center" }}>

              {/* Indicateur */}
              <div style={{ position:"relative" }} onClick={e => e.stopPropagation()}>
                <button onClick={() => { setShowIndDD(!showIndDD); setShowAssDD(false); }}
                  style={{ display:"flex", alignItems:"center", gap:8, background:Y, color:D, border:"none", cursor:"pointer", padding:"7px 14px", borderRadius:9, fontSize:12, fontWeight:800, boxShadow:"0 2px 8px rgba(255,230,0,0.35)" }}>
                  <span style={{ color:"rgba(46,46,56,.45)", fontSize:8.5, fontWeight:700, letterSpacing:"1px", textTransform:"uppercase" }}>Indicateur</span>
                  <span style={{ width:1, height:12, background:"rgba(0,0,0,0.15)" }}/>
                  <span style={{ fontWeight:900 }}>{indicateur}</span>
                  <ChevronDown color={D} size={12}/>
                </button>
                {showIndDD && (
                  <div style={{ position:"absolute", top:"calc(100% + 6px)", left:0, background:"#fff", border:"1px solid #E5E7EB", borderRadius:12, boxShadow:"0 8px 28px rgba(0,0,0,0.13)", zIndex:60, minWidth:210, overflow:"hidden" }}>
                    {Object.keys(INDICATEURS).map(k => (
                      <button key={k} onClick={() => { setIndicateur(k); setShowIndDD(false); }}
                        style={{ display:"block", width:"100%", textAlign:"left", padding:"10px 16px", fontSize:12, border:"none", cursor:"pointer", fontWeight: indicateur===k ? 800 : 500, color: indicateur===k ? D : G, background: indicateur===k ? "rgba(255,230,0,.13)" : "#fff", borderBottom:"1px solid #F5F5F5" }}>
                        {k}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Sélection assureurs */}
              <div style={{ position:"relative" }} onClick={e => e.stopPropagation()}>
                <button onClick={() => { setShowAssDD(!showAssDD); setShowIndDD(false); }}
                  style={{ display:"flex", alignItems:"center", gap:8, background:"#fff", color:D, border:"1.5px solid #E5E7EB", padding:"7px 14px", borderRadius:9, fontSize:12, fontWeight:700, cursor:"pointer" }}>
                  <span style={{ color:G, fontSize:8.5, fontWeight:700, letterSpacing:"1px", textTransform:"uppercase" }}>Assurance</span>
                  <span style={{ width:1, height:12, background:"#E5E7EB" }}/>
                  <span>{selected.size === ASSUREURS.length ? "Toutes" : `${selected.size} sél.`}</span>
                  <ChevronDown color={G} size={12}/>
                </button>
                {showAssDD && (
                  <div style={{ position:"absolute", top:"calc(100% + 6px)", right:0, background:"#fff", border:"1px solid #E5E7EB", borderRadius:12, boxShadow:"0 8px 28px rgba(0,0,0,0.13)", zIndex:60, width:220, overflow:"hidden" }}>
                    {ASSUREURS.map(a => (
                      <button key={a} onClick={() => toggleAssureur(a)}
                        style={{ display:"flex", alignItems:"center", gap:10, width:"100%", padding:"8px 14px", fontSize:12, border:"none", cursor:"pointer", background: selected.has(a) ? "#FAFAFA" : "#fff", borderBottom:"1px solid #F3F4F6" }}>
                        <div style={{ width:16, height:16, borderRadius:4, flexShrink:0, border:`2px solid ${selected.has(a) ? D : "#D1D5DB"}`, background: selected.has(a) ? D : "#fff", display:"flex", alignItems:"center", justifyContent:"center" }}>
                          {selected.has(a) && <span style={{ color:"#fff", fontSize:10, lineHeight:1 }}>✓</span>}
                        </div>
                        {getLogoSrc(a)
                          ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]} style={{ width:70, height:22, objectFit:"contain" }}/>
                          : <span style={{ fontSize:11, fontWeight:700, color:D }}>{ASSUREUR_LABELS[a]}</span>
                        }
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <YearSelector year={annee} years={années} onChange={setAnnee}/>
            </div>
          </div>
        </div>

        {/* Chips logos */}
        <div style={{ display:"flex", flexWrap:"wrap", gap:5, alignItems:"center", padding:"5px 28px 8px" }}>
          <span style={{ fontSize:9, fontWeight:800, color:G, letterSpacing:"1.5px", textTransform:"uppercase", marginRight:2 }}>Comparaison active :</span>
          {ASSUREURS.map(a => {
            const active = selected.has(a);
            return (
              <button key={a} onClick={() => toggleAssureur(a)}
                title={active ? `Retirer ${ASSUREUR_LABELS[a]}` : `Ajouter ${ASSUREUR_LABELS[a]}`}
                style={{ display:"flex", alignItems:"center", padding:"3px 8px", background: active ? "white" : "transparent", border: active ? "1.5px solid #D1D5DB" : "1.5px solid transparent", borderRadius:8, cursor:"pointer", opacity: active ? 1 : 0.35, filter: active ? "none" : "grayscale(60%)", transition:"all .15s", boxShadow: active ? "0 1px 4px rgba(0,0,0,0.08)" : "none" }}>
                {getLogoSrc(a)
                  ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]} style={{ width:64, height:24, objectFit:"contain" }}/>
                  : <span style={{ fontSize:9, fontWeight:800, color: active ? D : G }}>{ASSUREUR_LABELS[a]}</span>
                }
              </button>
            );
          })}
        </div>
      </div>

      {/* ── Corps ── */}
      <div style={{ flex:1, padding:"12px 28px 14px", display:"flex", flexDirection:"column", gap:10, overflow:"hidden" }}>

        {/* KPI Banner */}
        <DarkKpiBanner items={[
          { label:"Indicateur analysé",  value: indicateur,                                        sub:`${ind.unit} · données CMF` },
          { label:"Année d'analyse",     value: String(annee),                                     sub:"données certifiées CMF" },
          { label:"Assureurs comparés",  value: String(selected.size),                             sub:`sur ${ASSUREURS.length} disponibles` },
          { label:"Leader",              value: leader ? (ASSUREUR_LABELS[leader.a] ?? leader.a) : "—", sub: leader ? `${leader.v}${ind.unit}` : "" },
        ]}/>

        {/* Graphique + Panel classement */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 280px", gap:14, flex:1, overflow:"hidden" }}>

          {/* ── Bar chart ── */}
          <div style={{ background:"white", borderRadius:14, border:"1px solid #EBEBEB", padding:"16px 16px 10px", boxShadow:"0 2px 10px rgba(0,0,0,0.05)", display:"flex", flexDirection:"column", minHeight:0, overflow:"hidden" }}>

            {/* Titre + légende tiers */}
            <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:10, flexShrink:0 }}>
              <div style={{ fontSize:10, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D }}>
                {indicateur} par assurance — {annee}
              </div>
              <div style={{ display:"flex", alignItems:"center", gap:14 }}>
                {[
                  { color:COLOR_LEADER,     label:"Leader #1" },
                  { color:COLOR_CHALLENGER, label:"Challengers #2–5" },
                  { color:COLOR_FOLLOWER,   label:"Followers #6+" },
                ].map(l => (
                  <div key={l.label} style={{ display:"flex", alignItems:"center", gap:5 }}>
                    <div style={{ width:10, height:10, borderRadius:2, background:l.color, flexShrink:0 }}/>
                    <span style={{ fontSize:9, color:G, fontWeight:600 }}>{l.label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ flex:1, position:"relative" }}>
              <ReactApexChart
                key={`bar-${annee}-${indicateur}-${selected.size}`}
                options={chartOpts}
                series={[{ name:indicateur, data: vals.map(v => v ?? 0) }]}
                type="bar"
                height={chartH}
              />

              {/* Logos sous le graphique */}
              <div style={{ display:"flex", alignItems:"center", paddingLeft:Y_AXIS_W, paddingRight:6, height:36, marginTop:-14 }}>
                {filtered.map(a => (
                  <div key={a} style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center" }}>
                    {getLogoSrc(a)
                      ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]} style={{ width:52, height:22, objectFit:"contain" }}/>
                      : <span style={{ fontSize:8, fontWeight:700, color:D, textAlign:"center" }}>{ASSUREUR_LABELS[a]}</span>
                    }
                  </div>
                ))}
              </div>
            </div>

            {/* Note compagnies sans données */}
            <div style={{ marginTop:8, padding:"7px 10px", background:"#FAFAFA", borderRadius:8, border:"1px solid #F0F0F0", flexShrink:0 }}>
              <span style={{ fontSize:9, fontWeight:700, color:G, letterSpacing:"0.8px", textTransform:"uppercase" }}>Données non disponibles : </span>
              <span style={{ fontSize:9, color:G }}>{SANS_DONNEES.join(" · ")}</span>
            </div>
          </div>

          {/* ── Panel classement ── */}
          <div style={{ background:"white", borderRadius:14, border:"1px solid #EBEBEB", boxShadow:"0 2px 10px rgba(0,0,0,0.05)", display:"flex", flexDirection:"column", overflow:"hidden" }}>
            <div style={{ padding:"13px 16px", borderBottom:"1px solid #F0F0F0", flexShrink:0 }}>
              <div style={{ fontSize:10, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D }}>Classement {annee}</div>
              <div style={{ fontSize:9, color:G, marginTop:2 }}>
                {ind.lowerBetter ? "Plus bas = meilleure performance" : "Plus haut = meilleure performance"}
              </div>
            </div>

            <div style={{ flex:1, overflowY:"auto" }}>
              {rankingList.map((row, i) => {
                const isLeader = row.rank === 1;
                return (
                  <div key={row.a} style={{ display:"flex", alignItems:"center", gap:10, padding:"11px 14px", borderBottom:"1px solid #F8F8F8", background: isLeader ? "#FEFCE8" : "white" }}>
                    {/* Rang */}
                    <div style={{
                      width:26, height:26, borderRadius:7, flexShrink:0,
                      display:"flex", alignItems:"center", justifyContent:"center",
                      background: tierColor(row.rank),
                      color: isLeader ? D : "#FFFFFF",
                      fontSize:12, fontWeight:900,
                    }}>{row.rank}</div>

                    {/* Logo */}
                    <div style={{ width:72, height:32, flexShrink:0, background:"#FAFAFA", borderRadius:7, border:"1px solid #E5E7EB", display:"flex", alignItems:"center", justifyContent:"center", padding:"3px 6px" }}>
                      {getLogoSrc(row.a)
                        ? <img src={getLogoSrc(row.a)} alt={ASSUREUR_LABELS[row.a]} style={{ width:60, height:26, objectFit:"contain" }}/>
                        : <span style={{ fontSize:10, fontWeight:800, color:D }}>{ASSUREUR_LABELS[row.a]}</span>
                      }
                    </div>

                    {/* Valeur + tier */}
                    <div style={{ flex:1, textAlign:"right" }}>
                      <div style={{ fontSize:16, fontWeight:700, color:D, lineHeight:1 }}>{row.v}{ind.unit}</div>
                      <div style={{ marginTop:4 }}><TierBadge rank={row.rank}/></div>
                    </div>
                  </div>
                );
              })}
              {rankingList.length === 0 && (
                <div style={{ padding:24, textAlign:"center", color:G, fontSize:12 }}>
                  Aucune donnée disponible pour cette année
                </div>
              )}
            </div>

            <div style={{ padding:"9px 14px", borderTop:"1px solid #F0F0F0", flexShrink:0 }}>
              <div style={{ fontSize:9, color:G }}>Source CMF · {annee}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
