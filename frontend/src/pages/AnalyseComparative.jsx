import { useState, useEffect } from "react";
import ReactApexChart from "react-apexcharts";
import { getLogoSrc } from "../utils/logos";
import PageHeaderBar, { YearSelector } from "../components/PageHeaderBar";

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
const Y   = "#FFE600";
const D   = "#2E2E38";
const G   = "#747480";
const RED = "#C8102E";

// 11 compagnies avec données CMF (ATTIJARI retiré : aucun ratio disponible)
const ASSUREURS = [
  "STAR","COMAR","GAT","ASTREE","CARTE","LLOYD_TUNISIEN",
  "MAGHREBIA","BH","BIAT","TUNIS_RE","COTUNACE",
];

const ASSUREUR_LABELS = {
  "STAR":           "STAR",
  "COMAR":          "COMAR",
  "GAT":            "GAT",
  "ASTREE":         "ASTREE",
  "CARTE":          "CARTE",
  "LLOYD_TUNISIEN": "LLOYD",
  "MAGHREBIA":      "MAGHREBIA",
  "BH":             "BH",
  "BIAT":           "BIAT",
  "TUNIS_RE":       "TUNIS RE",
  "COTUNACE":       "COTUNACE",
};

const BAR_COLOR  = "#2E2E38";   // gris foncé charte
const TOP_COLOR  = "#FFE600";   // jaune marque → leader
const ND_COLOR   = "#E5E7EB";   // gris clair → pas de données
const RANK_COLORS = ["#1A9E5C","#2DB87C","#5BC89A","#F5A623","#F59E5C"];

const INDICATEURS = {
  "Ratio combiné":      { field:"ratio_combine", unit:"%" },
  "Ratio sinistralité": { field:"ratio_sp",      unit:"%" },
  "Ratio de frais":     { field:"ratio_frais",   unit:"%" },
  "Part de marché":     { field:"pdm",           unit:"%" },
  "Primes émises":      { field:"primes",        unit:" MDT" },
};

// Compagnies sans données (PDFs scannés / non extractibles)
const SANS_DONNEES = [
  "AMI","BNA","UIB","HAYETT","CTAMA",
  "GAT VIE","CARTE VIE","LLOYD VIE","MAGHREBIA VIE",
  "ZITOUNA TAKAFUL","AL AMANAH TAKAFUL","AT-TAKAFULIA",
];

function ChevronDown({ color = D, size = 12 }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" width={size} height={size} style={{flexShrink:0}}>
      <path d="M2.5 4.5L6 8l3.5-3.5" stroke={color} strokeWidth="1.8"
            strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export default function AnalyseComparative() {
  const { h: winH } = useWindowSize();
  const chartH = Math.max(260, winH - 330);
  const [selected, setSelected]       = useState(new Set(ASSUREURS));
  const [indicateur, setIndicateur]   = useState("Ratio combiné");
  const [showIndDD, setShowIndDD]     = useState(false);
  const [showAssDD, setShowAssDD]     = useState(false);
  const [showAnneeDD, setShowAnneeDD] = useState(false);
  const [annee, setAnnee]             = useState(2024);
  const [apiData, setApiData]         = useState({});
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

  const ind          = INDICATEURS[indicateur];
  const filtered     = ASSUREURS.filter(a => selected.has(a));
  const filteredVals = filtered.map(a => apiData[a]?.[ind.field] ?? null);
  const chartVals    = filteredVals.map(v => v ?? 0);

  // Pour PDM et Primes : le leader est le maximum (plus grand = meilleur)
  // Pour les ratios RC/RSP/RF : le leader est le minimum (plus bas = plus efficient)
  const validVals = filteredVals.filter(v => v != null);
  const isRatioIndicateur = ["ratio_combine","ratio_sp","ratio_frais"].includes(ind.field);
  const leaderVal = isRatioIndicateur
    ? Math.min(...validVals)
    : Math.max(...validVals);
  const barColors = filteredVals.map(v => {
    if (v == null)        return ND_COLOR;
    if (v === leaderVal)  return TOP_COLOR;
    return BAR_COLOR;
  });
  const labelColors = filteredVals.map(v => {
    if (v == null)        return "#9CA3AF";
    if (v === leaderVal)  return D;       // texte sombre sur jaune
    return "#FFFFFF";                     // texte blanc sur marine
  });

  // Largeur fixe de l'axe Y pour aligner les logos
  const Y_AXIS_W = 54;

  const chartOpts = {
    chart: { type:"bar", toolbar:{show:false}, fontFamily:"Barlow, system-ui, sans-serif", animations:{enabled:false}, background:"transparent" },
    plotOptions: { bar:{ columnWidth:"58%", borderRadius:4, borderRadiusApplication:"end", distributed:true } },
    colors: barColors,
    legend: { show: false },
    xaxis: {
      categories: filtered.map(a => ASSUREUR_LABELS[a] ?? a),
      labels: { show: false },
      axisBorder: { show:false }, axisTicks:{ show:false },
    },
    yaxis: {
      labels: {
        formatter: v => `${v}${ind.unit}`,
        style: { colors:"#747480", fontSize:"11px", fontFamily:"Barlow, system-ui, sans-serif" },
        minWidth: Y_AXIS_W, maxWidth: Y_AXIS_W,
      },
      min: 0,
    },
    grid: { borderColor:"#EBEBEF", strokeDashArray:4, xaxis:{ lines:{show:false} }, yaxis:{ lines:{show:true} }, padding:{ left:0, right:4, bottom:-10 } },
    dataLabels: {
      enabled: true,
      formatter: (v, { dataPointIndex }) => {
        const orig = filteredVals[dataPointIndex];
        return orig != null ? `${orig}${ind.unit}` : "N/D";
      },
      style: { fontSize:"11px", fontWeight:700, fontFamily:"Barlow, system-ui, sans-serif", colors: labelColors },
      background: { enabled: false },
      offsetY: -7,
    },
    tooltip: {
      style: { fontFamily:"Barlow, system-ui, sans-serif", fontSize:"12px" },
      y:{ formatter: (v, { dataPointIndex }) => {
        const orig = filteredVals[dataPointIndex];
        return orig != null ? `${orig}${ind.unit}` : "Donnée non disponible";
      }},
    },
  };

  const top5 = filtered
    .map(a => ({ nom:a, val: apiData[a]?.[ind.field] ?? null }))
    .filter(a => a.val != null)
    .sort((a,b) => b.val - a.val)
    .slice(0, 5);

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"#F2F2F4", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>

      {/* ── Header unifié ── */}
      <div style={{ background:"#FFFFFF", borderBottom:"1px solid #E5E7EB", flexShrink:0 }}>

        {/* Titre + filtres */}
        <div style={{ padding:"0 28px" }}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", height:58 }}>

            {/* Gauche : drapeau + titre */}
            <div style={{ display:"flex", alignItems:"center", gap:10 }}>
              <img src="/logos/tn-flag.png" alt="TN" style={{ height:20, borderRadius:3, opacity:.85, flexShrink:0 }}/>
              <h1 style={{ fontSize:17, fontWeight:900, color:D, margin:0, letterSpacing:"-0.2px" }}>Analyse Comparative</h1>
            </div>

            {/* Droite : filtres */}
            <div style={{ display:"flex", gap:10, alignItems:"center" }}>

              {/* Indicateur */}
              <div style={{ position:"relative" }}>
                <button onClick={() => setShowIndDD(!showIndDD)}
                  style={{ display:"flex", alignItems:"center", gap:8, background:"#FFE600", color:D, border:"none", cursor:"pointer", padding:"7px 14px", borderRadius:9, fontSize:12, fontWeight:800, boxShadow:"0 2px 8px rgba(255,230,0,0.35)" }}>
                  <span style={{color:"rgba(46,46,56,.5)", fontSize:9, fontWeight:700, letterSpacing:"1px", textTransform:"uppercase"}}>Indicateur</span>
                  <span style={{width:1, height:12, background:"rgba(0,0,0,0.15)"}}/>
                  <span style={{fontWeight:900}}>{indicateur}</span>
                  <ChevronDown color={D} size={12}/>
                </button>
                {showIndDD && (
                  <div style={{ position:"absolute", top:"calc(100% + 6px)", left:0, background:"#fff", border:"1px solid #E5E7EB", borderRadius:12, boxShadow:"0 8px 28px rgba(0,0,0,0.12)", zIndex:60, minWidth:200, overflow:"hidden" }}>
                    {Object.keys(INDICATEURS).map(k => (
                      <button key={k} onClick={() => { setIndicateur(k); setShowIndDD(false); }}
                        style={{ display:"block", width:"100%", textAlign:"left", padding:"10px 16px", fontSize:12, border:"none", cursor:"pointer", fontWeight: indicateur===k ? 800 : 500, color: indicateur===k ? D : G, background: indicateur===k ? "rgba(255,230,0,.15)" : "#fff", borderBottom:"1px solid #F5F5F5" }}>
                        {k}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Assurance */}
              <div style={{ position:"relative" }}>
                <button onClick={() => { setShowAssDD(!showAssDD); setShowIndDD(false); }}
                  style={{ display:"flex", alignItems:"center", gap:8, background:"#fff", color:D, border:"1.5px solid #E5E7EB", padding:"7px 14px", borderRadius:9, fontSize:12, fontWeight:700, cursor:"pointer" }}>
                  <span style={{color:G, fontSize:9, fontWeight:700, letterSpacing:"1px", textTransform:"uppercase"}}>Assurance</span>
                  <span style={{width:1, height:12, background:"#E5E7EB"}}/>
                  <span>{selected.size === ASSUREURS.length ? "Toutes" : `${selected.size} sél.`}</span>
                  <ChevronDown color={G} size={12}/>
                </button>
                {showAssDD && (
                  <div style={{ position:"absolute", top:"calc(100% + 6px)", right:0, background:"#fff", border:"1px solid #E5E7EB", borderRadius:12, boxShadow:"0 8px 28px rgba(0,0,0,0.12)", zIndex:60, width:220, overflow:"hidden" }}>
                    {ASSUREURS.map(a => (
                      <button key={a} onClick={() => toggleAssureur(a)}
                        style={{ display:"flex", alignItems:"center", gap:10, width:"100%", padding:"8px 14px", fontSize:12, border:"none", cursor:"pointer", background: selected.has(a) ? "#FAFAFA" : "#fff", borderBottom:"1px solid #F3F4F6" }}>
                        <div style={{ width:16, height:16, borderRadius:4, flexShrink:0, border:`2px solid ${selected.has(a) ? D : "#D1D5DB"}`, background: selected.has(a) ? D : "#fff", display:"flex", alignItems:"center", justifyContent:"center" }}>
                          {selected.has(a) && <span style={{color:"#fff",fontSize:10,lineHeight:1}}>✓</span>}
                        </div>
                        {getLogoSrc(a) ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]} style={{width:70,height:22,objectFit:"contain"}}/> : <span style={{fontSize:11,fontWeight:700,color:D}}>{ASSUREUR_LABELS[a]}</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <YearSelector
                year={annee}
                years={années}
                onChange={setAnnee}
              />

            </div>
          </div>
        </div>

        {/* Chips logos assureurs */}
        <div style={{display:"flex", flexWrap:"wrap", gap:5, alignItems:"center", padding:"6px 28px 8px"}}>
          <span style={{fontSize:9,fontWeight:800,color:G,letterSpacing:"1.5px",textTransform:"uppercase",marginRight:2}}>
            Comparaison active :
          </span>
          {ASSUREURS.map(a => {
            const active = selected.has(a);
            return (
              <button key={a} onClick={() => toggleAssureur(a)}
                title={active ? `Retirer ${ASSUREUR_LABELS[a]}` : `Ajouter ${ASSUREUR_LABELS[a]}`}
                style={{
                  display:"flex", alignItems:"center",
                  padding:"3px 8px",
                  background: active ? "white" : "transparent",
                  border: active ? "1.5px solid #D1D5DB" : "1.5px solid transparent",
                  borderRadius:8, cursor:"pointer",
                  opacity: active ? 1 : 0.35,
                  filter: active ? "none" : "grayscale(60%)",
                  transition:"all .15s",
                  boxShadow: active ? "0 1px 4px rgba(0,0,0,0.08)" : "none",
                }}>
                {getLogoSrc(a)
                  ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]}
                      style={{width:64, height:24, objectFit:"contain"}}/>
                  : <span style={{fontSize:9,fontWeight:800,color: active ? D : G}}>{ASSUREUR_LABELS[a]}</span>
                }
              </button>
            );
          })}
        </div>

      </div>

      {/* ── Corps : chart + classement ── */}
      <div style={{display:"grid", gridTemplateColumns:"1fr 280px", gap:16, flex:1, padding:"16px 28px", overflow:"hidden"}}>

        {/* Graphique */}
        <div style={{
          background:"white", borderRadius:14, border:"1px solid #EBEBEB",
          padding:"18px 18px 10px", boxShadow:"0 2px 10px rgba(0,0,0,0.05)",
          display:"flex", flexDirection:"column",
        }}>
          <div style={{fontSize:10, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D, marginBottom:12}}>
            {indicateur} par assurance
          </div>
          <div style={{flex:1, position:"relative"}}>
            <ReactApexChart
              options={chartOpts}
              series={[{ name:indicateur, data:chartVals }]}
              type="bar"
              height={chartH}
            />
            {/* Logo row */}
            <div style={{
              display:"flex", alignItems:"center",
              paddingLeft:Y_AXIS_W, paddingRight:6,
              height:36, marginTop:-14,
            }}>
              {filtered.map(a => (
                <div key={a} style={{flex:1, display:"flex", alignItems:"center", justifyContent:"center"}}>
                  {getLogoSrc(a)
                    ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]}
                        style={{width:52, height:22, objectFit:"contain"}}/>
                    : <span style={{fontSize:8,fontWeight:700,color:D,textAlign:"center"}}>{ASSUREUR_LABELS[a]}</span>
                  }
                </div>
              ))}
            </div>
          </div>

          {/* Note compagnies sans données */}
          <div style={{
            marginTop:10, padding:"8px 12px",
            background:"#FAFAFA", borderRadius:8, border:"1px solid #F0F0F0",
          }}>
            <span style={{fontSize:9, fontWeight:700, color:G, letterSpacing:"1px", textTransform:"uppercase"}}>
              Données non disponibles (PDFs scannés / format non extractible) :
            </span>
            <span style={{fontSize:9, color:G, marginLeft:6}}>
              {SANS_DONNEES.join(" · ")}
            </span>
          </div>
        </div>

        {/* Classement */}
        <div style={{
          background:"white", borderRadius:14, border:"1px solid #EBEBEB",
          boxShadow:"0 2px 10px rgba(0,0,0,0.05)",
          display:"flex", flexDirection:"column", overflow:"hidden",
        }}>
          <div style={{padding:"14px 16px", borderBottom:"1px solid #F0F0F0", flexShrink:0}}>
            <div style={{fontSize:10, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D}}>
              Classement des assurances
            </div>
          </div>

          <div style={{flex:1, overflowY:"auto"}}>
            {top5.map((a,i) => (
              <div key={a.nom} style={{
                display:"flex", alignItems:"center", gap:12,
                padding:"14px 16px", borderBottom:"1px solid #F8F8F8",
              }}>
                <div style={{
                  width:28, height:28, borderRadius:8, flexShrink:0,
                  display:"flex", alignItems:"center", justifyContent:"center",
                  background: RANK_COLORS[i], color:"white",
                  fontSize:13, fontWeight:900,
                }}>
                  {i+1}
                </div>
                <div style={{
                  width:90, height:50, flexShrink:0,
                  background:"#FAFAFA", borderRadius:9,
                  border:"1px solid #E5E7EB",
                  display:"flex", alignItems:"center", justifyContent:"center",
                  padding:"6px 8px",
                }}>
                  {getLogoSrc(a.nom)
                    ? <img src={getLogoSrc(a.nom)} alt={a.nom}
                        style={{width:76, height:38, objectFit:"contain"}}/>
                    : <span style={{fontSize:11,fontWeight:800,color:D}}>{ASSUREUR_LABELS[a.nom]}</span>
                  }
                </div>
                <div style={{flex:1, textAlign:"right"}}>
                  <div style={{fontSize:18, fontWeight:600, color: D, lineHeight:1}}>
                    {a.val}{ind.unit}
                  </div>
                </div>
              </div>
            ))}

            {top5.length === 0 && (
              <div style={{padding:24, textAlign:"center", color:G, fontSize:12}}>
                Aucune donnée disponible pour cette année
              </div>
            )}
          </div>

          <div style={{padding:"10px 16px", borderTop:"1px solid #F0F0F0", flexShrink:0}}>
            <div style={{fontSize:9, color:G}}>Données {annee} · Source CMF</div>
          </div>
        </div>
      </div>
    </div>
  );
}
