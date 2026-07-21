import { useState, useEffect, useRef } from "react";
import ReactApexChart from "react-apexcharts";
import TunisiaMap from "../components/TunisiaMap";
import { getLogoSrc } from "../utils/logos";
import PageHeaderBar from "../components/PageHeaderBar";

const Y = "#FFE600", D = "#2E2E38", G = "#747480";
const API = "http://localhost:8002";
const FONT = "Barlow,system-ui,sans-serif";
const TC = ["#2E2E38","#FFE600","#B8941A","#8B7000","#E6B800","#5C4A00","#BFBFBF"];

const LABEL = {
  AL_AMANAH_TAKAFUL:"El Amana Takaful", AMI:"AMI", ASTREE:"Astrée",
  ATTIJARI:"Attijari Assurances", AT_TAKAFULIA:"At-Takafulia", BH:"BH Assurance",
  BIAT:"BIAT Assurances", BNA:"BNA Assurances", CARTE:"La Carte",
  CARTE_VIE:"La Carte Vie", COMAR:"COMAR", COTUNACE:"COTUNACE",
  CTAMA:"CTAMA", GAT:"GAT", GAT_VIE:"GAT Vie", HAYETT:"Hayett",
  LLOYD_TUNISIEN:"Lloyd Tunisien", LLOYD_VIE:"Lloyd Vie",
  MAGHREBIA:"Maghrebia", MAGHREBIA_VIE:"Maghrebia Vie", STAR:"STAR",
  TUNIS_RE:"Tunis Re", UIB:"UIB Assurances", ZITOUNA_TAKAFUL:"Zitouna Takaful",
};

const ICONS = {
  particuliers: (c="white") => (
    <svg viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" width="20" height="20">
      <circle cx="12" cy="8" r="4"/><path d="M4 20v-1a8 8 0 0116 0v1"/>
    </svg>
  ),
  professionnels: (c="white") => (
    <svg viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" width="20" height="20">
      <rect x="2" y="7" width="20" height="14" rx="2"/>
      <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/>
      <line x1="12" y1="12" x2="12" y2="16"/><line x1="10" y1="14" x2="14" y2="14"/>
    </svg>
  ),
  tre: (c="white") => (
    <svg viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" width="20" height="20">
      <circle cx="12" cy="12" r="9"/>
      <path d="M12 3v18M3 12h18M4.22 7.22C6.5 9.5 9 11 12 11s5.5-1.5 7.78-3.78M4.22 16.78C6.5 14.5 9 13 12 13s5.5 1.5 7.78 3.78"/>
    </svg>
  ),
  etudiants: (c="white") => (
    <svg viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" width="20" height="20">
      <path d="M22 10v6M2 10l10-5 10 5-10 5-10-5z"/>
      <path d="M6 12v5c3.33 2 8.67 2 12 0v-5"/>
    </svg>
  ),
  retraites: (c="white") => (
    <svg viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" width="20" height="20">
      <circle cx="12" cy="7" r="4"/>
      <path d="M5.5 20H4a1 1 0 01-1-1v-1a7 7 0 0114 0v1a1 1 0 01-1 1h-1.5M9 20l1 2h4l1-2"/>
    </svg>
  ),
  vehicule: (c=D) => (
    <svg viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" width="20" height="20">
      <path d="M5 17H3a1 1 0 01-1-1v-5l2.5-6h13L20 11v5a1 1 0 01-1 1h-2"/>
      <circle cx="7.5" cy="17.5" r="2.5"/><circle cx="16.5" cy="17.5" r="2.5"/>
      <path d="M5 11h14"/>
    </svg>
  ),
  maison: (c=D) => (
    <svg viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.6" width="20" height="20">
      <path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/>
      <path d="M9 21V12h6v9"/>
    </svg>
  ),
};

/* Structure géo visuelle (pas des KPIs numériques) */
const GEO_MAP = {
  "grand-tunis":  { level:"forte",  value:"Grand Tunis"  },
  "nord-est":     { level:"forte",  value:"Nord-Est"     },
  "nord-ouest":   { level:"faible", value:"Nord-Ouest"   },
  "centre-est":   { level:"haute",  value:"Centre-Est"   },
  "centre-ouest": { level:"faible", value:"Centre-Ouest" },
  "sud-est":      { level:"faible", value:"Sud-Est"      },
  "sud-ouest":    { level:"faible", value:"Sud-Ouest"    },
};

function ChevronDown({ color=D, size=12 }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" width={size} height={size} style={{ flexShrink:0 }}>
      <path d="M2.5 4.5L6 8l3.5-3.5" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/* ── Dropdown — identique FichesEntreprises ──────────────────────────────────*/
function CompanyDropdown({ companies, selected, onSelect }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    function h(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  const logo = getLogoSrc(selected);
  return (
    <div ref={ref} style={{ position:"relative" }}>
      <button onClick={() => setOpen(!open)} style={{
        display:"flex", alignItems:"center", gap:8,
        background:Y, border:"none", cursor:"pointer",
        padding:"8px 14px", borderRadius:10, fontSize:12, fontWeight:800,
        boxShadow:"0 2px 8px rgba(255,230,0,0.4)", color:D, minWidth:160,
      }}>
        {logo && <img src={logo} alt={selected} style={{ height:22, maxWidth:52, objectFit:"contain" }}/>}
        <span style={{ flex:1, textAlign:"left" }}>{LABEL[selected]||selected}</span>
        <ChevronDown color={D} size={13}/>
      </button>
      {open && (
        <div style={{
          position:"absolute", top:"calc(100% + 6px)", left:0, zIndex:200,
          background:"white", borderRadius:12, border:"1px solid #E5E7EB",
          boxShadow:"0 8px 24px rgba(0,0,0,0.12)", minWidth:220, maxHeight:320, overflowY:"auto",
        }}>
          {companies.map(c => {
            const lg = getLogoSrc(c);
            return (
              <button key={c} onClick={() => { onSelect(c); setOpen(false); }} style={{
                display:"flex", alignItems:"center", gap:10, width:"100%",
                padding:"9px 14px", border:"none",
                background:c===selected?"#FFFBE6":"transparent",
                cursor:"pointer", textAlign:"left", fontSize:12,
                fontWeight:c===selected?700:500, color:D,
              }}>
                {lg ? <img src={lg} alt={c} style={{ height:20, width:44, objectFit:"contain" }}/> : <div style={{ width:44 }}/>}
                {LABEL[c]||c}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── KpiCard — dark gradient style (inspiré DarkKpiBanner / ProfilPays) ─────*/
function KpiCard({ label, value, iconFn, selected, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        flex: 1,
        borderRadius: 8,
        padding: "14px 16px 12px",
        display: "flex", flexDirection: "column",
        background: selected
          ? "linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)"
          : "linear-gradient(120deg, #1A1A22 0%, #22222E 50%, #2E2E3E 100%)",
        boxShadow: selected
          ? `0 4px 20px rgba(255,230,0,.18), 0 1px 0 rgba(255,255,255,.06) inset`
          : "0 2px 10px rgba(10,10,20,.25), 0 1px 0 rgba(255,255,255,.04) inset",
        outline: selected ? `2px solid ${Y}` : "2px solid transparent",
        transition: "all .18s ease",
        cursor: "pointer",
        position: "relative",
        overflow: "hidden",
      }}
      onMouseEnter={e => { e.currentTarget.style.transform = "translateY(-2px)"; }}
      onMouseLeave={e => { e.currentTarget.style.transform = "none"; }}
    >
      {selected && (
        <div style={{
          position: "absolute", top: 6, right: 8,
          background: Y, borderRadius: 20,
          padding: "1px 6px", fontSize: 7.5, fontWeight: 900, color: D,
        }}>✓</div>
      )}
      <div style={{
        width: 28, height: 28, borderRadius: 7, flexShrink: 0,
        background: selected ? Y : "rgba(255,255,255,.08)",
        display: "flex", alignItems: "center", justifyContent: "center",
        marginBottom: 8,
      }}>
        {iconFn(selected ? D : "rgba(255,255,255,.55)")}
      </div>
      <div style={{ fontSize: 7.5, fontWeight: 700, color: "rgba(255,255,255,.38)", textTransform: "uppercase", letterSpacing: "2px", marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 300, color: "#FFFFFF", lineHeight: 1, letterSpacing: "-0.5px" }}>
        {value ?? "—"}
      </div>
    </div>
  );
}

/* ── Card ────────────────────────────────────────────────────────────────────*/
function Card({ title, children, style={} }) {
  return (
    <div style={{
      background:"white", borderRadius:12, border:"1px solid #EBEBEB",
      boxShadow:"0 2px 8px rgba(0,0,0,0.05)", padding:"10px 12px",
      display:"flex", flexDirection:"column", overflow:"hidden", ...style,
    }}>
      {title && (
        <div style={{ display:"flex", alignItems:"center", gap:5, marginBottom:7 }}>
          <span style={{ width:5, height:5, borderRadius:"50%", background:"#E70013", display:"block" }}/>
          <span style={{ fontSize:8.5, fontWeight:900, textTransform:"uppercase", letterSpacing:"1.4px", color:"#E70013" }}>
            {title}
          </span>
        </div>
      )}
      {children}
    </div>
  );
}

/* ── Barres horizontales compactes ───────────────────────────────────────────*/
function HBar({ labs=[], vals=[] }) {
  if (!labs.length) return <div style={{ color:G, fontSize:11, textAlign:"center", padding:"12px 0" }}>N/D</div>;
  const max = Math.max(...vals, 1);
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:5 }}>
      {labs.map((lab,i) => (
        <div key={i} style={{ display:"flex", alignItems:"center", gap:6 }}>
          <div style={{
            width:80, fontSize:8, fontWeight:600, color:D, textAlign:"right", flexShrink:0,
            lineHeight:1.2, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis",
          }} title={lab}>{lab}</div>
          <div style={{ flex:1, height:11, background:"#F3F3F6", borderRadius:3, overflow:"hidden" }}>
            <div style={{ height:"100%", width:`${(vals[i]/max)*100}%`, background:i===0?"#C8C8D0":Y, borderRadius:3 }}/>
          </div>
          <div style={{ width:28, fontSize:9.5, fontWeight:800, color:D, flexShrink:0, textAlign:"right" }}>
            {vals[i]}%
          </div>
        </div>
      ))}
    </div>
  );
}

/* ══ VUE GRAND PUBLICS ════════════════════════════════════════════════════════*/
function GrandPublicsView({ seg, data }) {
  const d = data?.segments?.[seg] || data?.segments?.all;
  if (!d) return <div style={{ color:G, padding:32, textAlign:"center" }}>Données non disponibles</div>;

  /* Available height ≈ viewport − topbar(58) − padding(20) − switcher(32) − kpiTiles(56) − gaps(40) − source(20)
     Distribute: row1 gets 44%, row2 gets 56% of that. Chart fits inside card minus title(22px)+pad(20px). */
  const avail = Math.max(300, window.innerHeight - 92 - 20 - 32 - 56 - 40 - 20);
  const H1 = Math.floor(avail * 0.44) - 42;   // row 1 card chart height
  const H2 = Math.floor(avail * 0.56) - 42;   // row 2 card chart height
  const H = H1;

  const genreOpts = {
    chart:{ type:"donut", fontFamily:FONT },
    colors:[D, Y],
    labels:["Homme","Femme"],
    plotOptions:{ pie:{ donut:{ size:"70%" } } },
    legend:{ show:false },
    dataLabels:{ enabled:true, formatter:v=>`${Math.round(v)}%`,
      style:{ fontSize:"10px", fontWeight:700, colors:["white","#2E2E38"] } },
    stroke:{ show:false },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  const ageOpts = {
    chart:{ type:"bar", toolbar:{ show:false }, fontFamily:FONT },
    colors:[Y],
    plotOptions:{ bar:{ borderRadius:3, columnWidth:"68%" } },
    grid:{ borderColor:"#F5F5F5", strokeDashArray:3, padding:{ left:0, right:0, top:0, bottom:0 } },
    xaxis:{
      categories:["18–24","25–34","35–44","45–54","55–64","65+"],
      labels:{ style:{ colors:G, fontSize:"8px" } },
      axisBorder:{ show:false }, axisTicks:{ show:false },
    },
    yaxis:{ show:false },
    dataLabels:{ enabled:true, formatter:v=>`${v}%`, offsetY:-5,
      style:{ fontSize:"8px", fontWeight:700, colors:[D] } },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  const treeOpts = {
    chart:{ type:"treemap", toolbar:{ show:false }, fontFamily:FONT },
    colors:TC,
    plotOptions:{ treemap:{ distributed:true, enableShades:false } },
    dataLabels:{ enabled:true, style:{ fontSize:"10px", fontWeight:"bold", colors:["white"] } },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  /*
   Layout repensé : 3 colonnes × 2 lignes + carte géo span 2 lignes
   Col 1 (étroite) : Genre (donut, petit) + stats Véhicule/Proprio
   Col 2 (large)   : Tranche d'âge (bar, besoin de largeur) + Profession (liste)
   Col 3 (large)   : TypePro treemap (besoin d'espace) + Rev Fam+Ind côte à côte
   Col 4 (fixe)    : Carte géo sur toute la hauteur
  */
  const CH = Math.max(90, Math.floor((window.innerHeight - 92 - 20 - 32 - 56 - 40 - 20) * 0.42) - 40);

  return (
    <div style={{
      display:"grid",
      gridTemplateColumns:"180px 1fr 1.5fr 152px",
      gridTemplateRows:"40% 60%",
      gap:6,
      height:"100%",
    }}>

      {/* [row0, col0] Genre — donut compact avec légende intégrée */}
      <Card title="Genre">
        <ReactApexChart options={genreOpts} series={d.genre||[0,0]} type="donut" height={CH}/>
        <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
          {[["Homme",D,d.genre?.[0]??0],["Femme",Y,d.genre?.[1]??0]].map(([lbl,c,v])=>(
            <div key={lbl} style={{ display:"flex", alignItems:"center", gap:5 }}>
              <div style={{ width:8, height:8, borderRadius:2, background:c, flexShrink:0 }}/>
              <span style={{ fontSize:9, color:D, fontWeight:600, flex:1 }}>{lbl}</span>
              <span style={{ fontSize:10, fontWeight:900, color:D }}>{v}%</span>
            </div>
          ))}
        </div>
      </Card>

      {/* [row0, col1] Tranche d'âge — bar chart (a besoin de largeur) */}
      <Card title="Tranche d'âge">
        <ReactApexChart options={ageOpts}
          series={[{ name:"Répondants", data:d.age||[] }]} type="bar" height={CH}/>
      </Card>

      {/* [row0, col2] Type profession — treemap (a besoin d'espace) */}
      <Card title="Type de profession">
        {(d.typePro||[]).length > 0
          ? <ReactApexChart options={treeOpts} series={[{ data:d.typePro }]} type="treemap" height={CH}/>
          : <div style={{ height:CH, display:"flex", alignItems:"center", justifyContent:"center", color:G }}>N/D</div>
        }
      </Card>

      {/* [row0-1, col3] Carte géo — toute la hauteur */}
      <Card title="Géo." style={{ gridRow:"1 / span 2", padding:"10px 8px" }}>
        <TunisiaMap data={GEO_MAP} compact/>
      </Card>

      {/* [row1, col0] Véhicule + Proprio — 2 tuiles stat empilées */}
      <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
        {[
          { iconFn:ICONS.vehicule, val:d.vehicule, lbl:"Ont un véhicule" },
          { iconFn:ICONS.maison,   val:d.proprio,  lbl:"Propriétaires"   },
        ].map(({ iconFn, val, lbl })=>(
          <div key={lbl} style={{
            background:"white", borderRadius:10, border:"1px solid #EBEBEB",
            boxShadow:"0 2px 6px rgba(0,0,0,0.05)", padding:"10px 12px",
            display:"flex", alignItems:"center", gap:10, flex:1,
          }}>
            <div style={{
              width:32, height:32, borderRadius:8, background:"#FFF8E6",
              border:"1px solid #FFE600",
              display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0,
            }}>
              {iconFn(D)}
            </div>
            <div>
              <div style={{ fontSize:20, fontWeight:900, color:D, lineHeight:1 }}>{val??0}%</div>
              <div style={{ fontSize:8.5, color:G, fontWeight:600, lineHeight:1.3, marginTop:2 }}>{lbl}</div>
            </div>
          </div>
        ))}
      </div>

      {/* [row1, col1] Profession — liste, ce cadre est assez large */}
      <Card title="Profession">
        <div style={{ display:"flex", flexDirection:"column", gap:3, overflow:"hidden" }}>
          {(d.professions||[]).slice(0,9).map(([name,pct],i)=>(
            <div key={i} style={{
              display:"flex", alignItems:"center", gap:6,
              padding:"3px 5px", background:i%2===0?"#FAFAFA":"white", borderRadius:3,
            }}>
              <span style={{ flex:1, fontSize:9, color:D, fontWeight:600, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{name}</span>
              <div style={{ height:3, width:36, background:"#F0F0F0", borderRadius:2, overflow:"hidden", flexShrink:0 }}>
                <div style={{ height:"100%", width:`${pct}%`, background:Y, borderRadius:2 }}/>
              </div>
              <span style={{ fontSize:9, fontWeight:800, color:D, width:24, textAlign:"right", flexShrink:0 }}>{pct}%</span>
            </div>
          ))}
        </div>
      </Card>

      {/* [row1, col2] Revenus familiaux + individuels côte à côte — grand cadre */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:6 }}>
        <Card title="Revenu familial mensuel">
          <HBar labs={d.revFam?.labs||[]} vals={d.revFam?.vals||[]}/>
        </Card>
        <Card title="Revenu individuel mensuel">
          <HBar labs={d.revInd?.labs||[]} vals={d.revInd?.vals||[]}/>
        </Card>
      </div>
    </div>
  );
}

/* ══ VUE ENTREPRISES ══════════════════════════════════════════════════════════*/
function EntreprisesView({ data }) {
  const e = data?.entreprises;
  if (!e) return <div style={{ color:G, padding:32, textAlign:"center" }}>Données non disponibles</div>;

  const treeOpts = {
    chart:{ type:"treemap", toolbar:{ show:false }, fontFamily:FONT },
    colors:TC,
    plotOptions:{ treemap:{ distributed:true, enableShades:false } },
    dataLabels:{ enabled:true, style:{ fontSize:"10px", fontWeight:"bold", colors:["white"] } },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };
  const donutOpts = {
    chart:{ type:"donut", fontFamily:FONT },
    colors:[Y, D, "#8B7000"],
    labels:e.employes?.labs||[],
    plotOptions:{ pie:{ donut:{ size:"60%" } } },
    legend:{ position:"bottom", fontSize:"10px", fontFamily:FONT },
    dataLabels:{ enabled:true, formatter:v=>`${Math.round(v)}%`, style:{ fontSize:"10px" } },
    stroke:{ show:false },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  /* Layout : 3 colonnes × 2 lignes, carte géo sur 2 lignes */
  return (
    <div style={{ display:"grid", gridTemplateColumns:"2fr 1.4fr 180px", gridTemplateRows:"55% 45%", gap:8, height:"100%" }}>

      {/* [row0, col0] Secteur d'activité */}
      <Card title="Secteur d'activité">
        <ReactApexChart options={treeOpts} series={[{ data:e.secteurs||[] }]} type="treemap" height={Math.max(140, Math.floor(window.innerHeight * 0.24))}/>
      </Card>

      {/* [row0, col1] Effectif employés */}
      <Card title="Effectif employés">
        <ReactApexChart options={donutOpts} series={e.employes?.vals||[]} type="donut" height={Math.max(140, Math.floor(window.innerHeight * 0.24))}/>
      </Card>

      {/* [row0-1, col2] Répartition géographique — occupe toute la hauteur */}
      <Card title="Répartition géographique" style={{ gridRow:"1 / span 2", padding:"10px 8px" }}>
        <TunisiaMap data={GEO_MAP} compact/>
      </Card>

      {/* [row1, col0-1] Chiffres d'affaires — occupe les 2 premières colonnes */}
      <Card title="Chiffres d'affaires annuel" style={{ gridColumn:"1 / span 2" }}>
        <HBar labs={e.ca?.labs||[]} vals={e.ca?.vals||[]}/>
      </Card>

    </div>
  );
}

/* ══ ANALYSE ÉCHANTILLON ══════════════════════════════════════════════════════*/
const SUB_FILTERS = [
  { key:"particuliers",   label:"Particulier",   iconFn:ICONS.particuliers   },
  { key:"professionnels", label:"Professionnel", iconFn:ICONS.professionnels },
  { key:"etudiants",      label:"Étudiant",      iconFn:ICONS.etudiants      },
  { key:"tre",            label:"TRE",           iconFn:ICONS.tre            },
  { key:"retraites",      label:"Retraité",      iconFn:ICONS.retraites      },
];

function AnalyseEchantillon({ data }) {
  const [mainSeg, setMainSeg] = useState("gp");
  const [subSeg,  setSubSeg]  = useState(null);
  const counts = data?.counts || {};

  return (
    <div style={{ display:"flex", flexDirection:"column", flex:1, minHeight:0, overflow:"hidden" }}>
      {/* Switcher */}
      <div style={{ display:"flex", gap:6, alignItems:"center", marginBottom:5, flexWrap:"wrap", flexShrink:0 }}>
        {[{ key:"ent", label:"Entreprises" },{ key:"gp", label:"Grand public" }].map(({ key, label })=>(
          <button key={key} onClick={() => { setMainSeg(key); setSubSeg(null); }} style={{
            padding:"6px 16px", borderRadius:8, fontSize:12, fontWeight:700, cursor:"pointer",
            background:mainSeg===key?Y:"white", color:D,
            border:mainSeg===key?`1.5px solid ${Y}`:"1.5px solid #E5E7EB",
            boxShadow:mainSeg===key?"0 2px 8px rgba(255,230,0,0.35)":"none",
          }}>{label}</button>
        ))}

        {mainSeg==="gp" && (
          <div style={{ display:"flex", gap:5, marginLeft:4, flexWrap:"wrap" }}>
            {SUB_FILTERS.map(({ key, label, iconFn })=>{
              const on = subSeg===key;
              return (
                <button key={key} onClick={() => setSubSeg(on ? null : key)} style={{
                  padding:"4px 10px", borderRadius:20, fontSize:11, fontWeight:700,
                  cursor:"pointer", display:"flex", alignItems:"center", gap:4,
                  transition:"all .15s",
                  background:on ? D : "#F5F5F8",
                  color:on ? Y : G,
                  border:on ? `1.5px solid ${D}` : "1.5px solid #E5E7EB",
                }}>
                  <span style={{ opacity:on?1:0.6 }}>{iconFn(on ? Y : G)}</span>
                  {label}
                  {on && <span style={{ fontSize:10, marginLeft:2 }}>×</span>}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* KPI tiles — dark gradient, uniquement pour Grand Public */}
      {mainSeg==="gp" && (
        <div style={{ display:"flex", gap:6, marginBottom:5, flexShrink:0 }}>
          {SUB_FILTERS.map(({ key, label, iconFn })=>(
            <KpiCard
              key={key}
              label={label}
              value={counts[key]}
              iconFn={iconFn}
              selected={subSeg===key}
              onClick={() => setSubSeg(subSeg===key ? null : key)}
            />
          ))}
        </div>
      )}

      <div style={{ flex:1, minHeight:0, overflow:"hidden" }}>
        {mainSeg==="gp"
          ? <GrandPublicsView seg={subSeg || "all"} data={data}/>
          : <EntreprisesView data={data}/>
        }
      </div>
    </div>
  );
}

/* ══ FICHE CLIENT ENTREPRISE ══════════════════════════════════════════════════*/
function FicheClientEntreprise({ data, code }) {
  const e = data?.entreprises;
  const counts = data?.counts || {};

  const secteurDominant = (e?.secteurs||[]).reduce((best,cur) => cur.y>(best?.y??0)?cur:best, null);
  const emploiDominant = (() => {
    const vals = e?.employes?.vals||[], labs = e?.employes?.labs||[];
    if (!vals.length) return null;
    const i = vals.indexOf(Math.max(...vals));
    return labs[i] ? { lab:labs[i], pct:vals[i] } : null;
  })();
  const caDominant = (() => {
    const vals = e?.ca?.vals||[], labs = e?.ca?.labs||[];
    if (!vals.length) return null;
    const i = vals.indexOf(Math.max(...vals));
    return labs[i] ? { lab:labs[i], pct:vals[i] } : null;
  })();
  const totalRepondants = Object.values(counts).reduce((s,v)=>s+(v||0),0);

  const ficheKpis = [
    {
      label:"Secteur dominant",
      value:secteurDominant ? secteurDominant.x : "—",
      sub:secteurDominant ? `${secteurDominant.y}% des entreprises` : "",
      icon:<><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></>,
    },
    {
      label:"Taille typique",
      value:emploiDominant ? emploiDominant.lab : "—",
      sub:emploiDominant ? `employés (${emploiDominant.pct}%)` : "",
      icon:<><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/></>,
    },
    {
      label:"CA majoritaire",
      value:caDominant ? caDominant.lab : "—",
      sub:caDominant ? `par an (${caDominant.pct}%)` : "",
      icon:<><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></>,
    },
    {
      label:"Zone principale",
      value:"Grand Tunis / Nord",
      sub:"concentration des répondants",
      icon:<><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></>,
    },
  ];

  const treeOpts = {
    chart:{ type:"treemap", toolbar:{ show:false }, fontFamily:FONT },
    colors:TC, plotOptions:{ treemap:{ distributed:true, enableShades:false } },
    dataLabels:{ enabled:true, style:{ fontSize:"10px", fontWeight:"bold", colors:["white"] } },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
      {/* Header */}
      <div style={{
        background:"white", borderRadius:12, border:"1px solid #EBEBEB",
        boxShadow:"0 2px 10px rgba(0,0,0,0.05)", padding:"14px 18px",
        display:"flex", alignItems:"center", gap:14,
      }}>
        <div style={{
          width:44, height:44, borderRadius:10,
          background:"linear-gradient(135deg,#B80C26 0%,#7A0000 100%)",
          display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0,
        }}>
          <svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.6" width="22" height="22">
            <rect x="2" y="7" width="20" height="14" rx="2"/>
            <path d="M16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2"/>
          </svg>
        </div>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:15, fontWeight:900, color:D }}>Profil type — Client Entreprise</div>
          <div style={{ fontSize:10.5, color:G, marginTop:2 }}>
            Synthèse du segment Entreprises · Enquête de marché {LABEL[code]||code}
          </div>
        </div>
        <div style={{ textAlign:"right", flexShrink:0 }}>
          <div style={{ fontSize:7.5, fontWeight:800, color:G, textTransform:"uppercase", letterSpacing:"1px" }}>Échantillon total</div>
          <div style={{ fontSize:22, fontWeight:900, color:D }}>{totalRepondants||"—"}</div>
          <div style={{ fontSize:9.5, color:G }}>répondants</div>
        </div>
      </div>

      {/* KPI — dark gradient style DarkKpiBanner / ProfilPays */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr 1fr", gap:8 }}>
        {ficheKpis.map(({ label, value, sub, icon })=>(
          <div key={label} style={{
            borderRadius:8, padding:"13px 15px 11px",
            background:"linear-gradient(120deg, #0D0D14 0%, #13131A 20%, #1A1A24 45%, #252535 70%, #2E2E38 100%)",
            boxShadow:"0 4px 20px rgba(10,10,20,.30), 0 1px 0 rgba(255,255,255,.04) inset",
            display:"flex", flexDirection:"column", gap:5,
          }}>
            <div style={{
              width:26, height:26, borderRadius:6,
              background:"rgba(255,255,255,0.08)",
              display:"flex", alignItems:"center", justifyContent:"center",
            }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,.55)" strokeWidth="1.6" width="15" height="15">
                {icon}
              </svg>
            </div>
            <div style={{ fontSize:7.5, fontWeight:700, letterSpacing:"2px",
              textTransform:"uppercase", color:"rgba(255,255,255,.38)" }}>{label}</div>
            <div style={{ fontSize:14, fontWeight:300, color:"white", lineHeight:1.2, letterSpacing:"-0.2px" }}>{value}</div>
            {sub && <div style={{ fontSize:8, color:"rgba(255,255,255,0.28)" }}>{sub}</div>}
          </div>
        ))}
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8 }}>
        <Card title="Répartition par secteur d'activité">
          {e?.secteurs?.length
            ? <ReactApexChart options={treeOpts} series={[{ data:e.secteurs }]} type="treemap" height={190}/>
            : <div style={{ height:190, display:"flex", alignItems:"center", justifyContent:"center", color:G }}>N/D</div>
          }
        </Card>
        <Card title="Chiffres d'affaires annuel">
          <HBar labs={e?.ca?.labs||[]} vals={e?.ca?.vals||[]}/>
        </Card>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"200px 1fr", gap:8 }}>
        <Card title="Effectif employés">
          <ReactApexChart
            options={{
              chart:{ type:"donut", fontFamily:FONT },
              colors:[Y, D, "#8B7000"],
              labels:e?.employes?.labs||[],
              plotOptions:{ pie:{ donut:{ size:"60%" } } },
              legend:{ position:"bottom", fontSize:"10px" },
              dataLabels:{ enabled:true, formatter:v=>`${Math.round(v)}%`, style:{ fontSize:"10px" } },
              stroke:{ show:false },
              tooltip:{ y:{ formatter:v=>`${v}%` } },
            }}
            series={e?.employes?.vals||[]} type="donut" height={190}
          />
        </Card>
        <Card title="Répartition géographique">
          <TunisiaMap data={GEO_MAP} compact/>
        </Card>
      </div>
    </div>
  );
}

/* ══ PAGE PRINCIPALE ══════════════════════════════════════════════════════════*/
export default function EnqueteMarche() {
  const [tab,        setTab]        = useState("echantillon");
  const [companies,  setCompanies]  = useState([]);
  const [code,       setCode]       = useState("STAR");
  const [surveyData, setSurveyData] = useState(null);
  const [loading,    setLoading]    = useState(false);

  /* Liste de TOUTES les compagnies (même source que FichesEntreprises) */
  useEffect(() => {
    fetch(`${API}/api/vue-assurance/companies`)
      .then(r => r.json())
      .then(list => { setCompanies(list); })
      .catch(() => {});
  }, []);

  /* Données enquête pour la compagnie sélectionnée */
  useEffect(() => {
    if (!code) return;
    setLoading(true);
    setSurveyData(null);
    fetch(`${API}/api/enquete-marche/data?code=${code}`)
      .then(r => r.json())
      .then(d => { setSurveyData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, [code]);

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"#EEEEF4", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar
        title="Enquête de Marché"
        tabs={[
          { key:"echantillon", label:"Analyse de l'échantillon" },
          { key:"fiche",       label:"Fiche client entreprise"  },
        ]}
        activeTab={tab}
        onTabChange={setTab}
        right={companies.length > 0 ? <CompanyDropdown companies={companies} selected={code} onSelect={setCode}/> : null}
      />

      {/* ── Corps ── */}
      <div style={{ flex:1, overflow:"hidden", padding:"12px 28px 8px", display:"flex", flexDirection:"column", gap:10 }}>

      {/* Contenu */}
      {loading && (
        <div style={{ color:G, textAlign:"center", padding:60, fontSize:13 }}>Chargement…</div>
      )}
      {!loading && !surveyData && (
        <div style={{ color:G, textAlign:"center", padding:60, fontSize:13 }}>
          Aucune donnée d'enquête disponible pour <strong>{LABEL[code]||code}</strong>
        </div>
      )}
      {!loading && surveyData && tab==="echantillon" && <AnalyseEchantillon data={surveyData}/>}
      {!loading && surveyData && tab==="fiche" && <FicheClientEntreprise data={surveyData} code={code}/>}

      <div style={{ textAlign:"right", fontSize:9.5, color:G }}>
        Source : Enquête de marché {LABEL[code]||code} · Base de données FS Market Intelligence
      </div>
      </div>{/* fin corps scrollable */}
    </div>
  );
}
