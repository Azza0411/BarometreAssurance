import { useState, useEffect, useRef } from "react";
import ReactApexChart from "react-apexcharts";
import TunisiaMap from "../components/TunisiaMap";
import { getLogoSrc } from "../utils/logos";
import PageHeaderBar from "../components/PageHeaderBar";

const Y = "#FFE600", D = "#2E2E38", G = "#747480";
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
const FONT = "Barlow,system-ui,sans-serif";
const TC = ["#2E2E38","#FFE600","#ffbf00","#6f8206","#468d21","#5C4A00","#BFBFBF"];

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

function buildMapData(geo) {
  const level = p => p >= 40 ? "haute" : p >= 20 ? "forte" : p >= 10 ? "moyenne" : "faible";
  if (!geo) return {
    "grand-tunis":  { level:"haute",  value:"—" },
    "nord-est":     { level:"haute",  value:"—" },
    "nord-ouest":   { level:"faible", value:"—" },
    "centre-est":   { level:"forte",  value:"—" },
    "centre-ouest": { level:"faible", value:"—" },
    "sud-est":      { level:"moyenne",value:"—" },
    "sud-ouest":    { level:"moyenne",value:"—" },
  };
  const ne = geo["nord-est"] || 0, ce = geo["centre-est"] || 0,
        nco = geo["nord-centre-ouest"] || 0, seo = geo["sud-est-ouest"] || 0;
  return {
    "grand-tunis":  { level:level(ne),  value:`${ne}% des répondants`  },
    "nord-est":     { level:level(ne),  value:`${ne}% des répondants`  },
    "nord-ouest":   { level:level(nco), value:`${nco}% des répondants` },
    "centre-ouest": { level:level(nco), value:`${nco}% des répondants` },
    "centre-est":   { level:level(ce),  value:`${ce}% des répondants`  },
    "sud-est":      { level:level(seo), value:`${seo}% des répondants` },
    "sud-ouest":    { level:level(seo), value:`${seo}% des répondants` },
  };
}

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
          <span style={{ fontSize:9.5, fontWeight:900, textTransform:"uppercase", letterSpacing:"1.2px", color:"#E70013" }}>
            {title}
          </span>
        </div>
      )}
      {children}
    </div>
  );
}

/* ── Barres horizontales compactes ───────────────────────────────────────────*/
function HBar({ labs=[], vals=[], labelWidth=130, fill=false }) {
  if (!labs.length) return <div style={{ color:G, fontSize:11, textAlign:"center", padding:"12px 0" }}>N/D</div>;
  const max = Math.max(...vals, 1);
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:fill?4:7, ...(fill && { flex:1 }) }}>
      {labs.map((lab,i) => (
        <div key={i} style={{ display:"flex", alignItems:"center", gap:6, ...(fill && { flex:1 }) }}>
          <div style={{
            width:labelWidth, fontSize:9.5, fontWeight:600, color:D, textAlign:"right", flexShrink:0,
            lineHeight:1.3, wordBreak:"break-word",
          }}>{lab}</div>
          <div style={{ flex:1, background:"#F0F0F4", borderRadius:3, overflow:"hidden",
            ...(fill ? { alignSelf:"stretch", minHeight:10 } : { height:13 }) }}>
            <div style={{ height:"100%", width:`${(vals[i]/max)*100}%`, background:i===0?"#C8C8D0":Y, borderRadius:3 }}/>
          </div>
          <div style={{ width:36, fontSize:11.5, fontWeight:800, color:D, flexShrink:0, textAlign:"right" }}>
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
  const geo = data?.geo || null;

  const [gridH, setGridH] = useState(() => Math.max(260, window.innerHeight - 340));
  useEffect(() => {
    const update = () => setGridH(Math.max(260, window.innerHeight - 340));
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  if (!d) return <div style={{ color:G, padding:32, textAlign:"center" }}>Données non disponibles</div>;

  const geoZones = geo ? [
    { label:"Nord-Est",            pct: geo["nord-est"]          || 0, color:"#FFE600" },
    { label:"Centre-Est",          pct: geo["centre-est"]        || 0, color:"#2E2E38" },
    { label:"Sud-Est & Ouest",     pct: geo["sud-est-ouest"]     || 0, color:"#8B7000" },
    { label:"Nord & Centre-Ouest", pct: geo["nord-centre-ouest"] || 0, color:"#BFBFBF" },
  ] : null;

  const GAP = 6;
  const r1  = Math.floor((gridH - GAP) * 2 / 3);
  const r2  = gridH - r1 - GAP;
  const CO  = 38;
  const ch1 = Math.max(60, r1 - CO);
  const ch2 = Math.max(60, r2 - CO);
  const LABEL_W = 128;

  const genreOpts = {
    chart:{ type:"donut", fontFamily:FONT },
    colors:[D, Y],
    labels:["Homme","Femme"],
    plotOptions:{ pie:{ donut:{ size:"66%" } } },
    legend:{ show:false },
    dataLabels:{ enabled:true, formatter:v=>`${Math.round(v)}%`,
      style:{ fontSize:"10px", fontWeight:700, colors:["white","#2E2E38"] } },
    stroke:{ show:false },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  const ageOpts = {
    chart:{ type:"bar", toolbar:{ show:false }, fontFamily:FONT },
    colors:[Y],
    plotOptions:{ bar:{ borderRadius:3, columnWidth:"65%" } },
    grid:{ borderColor:"#F0F0F0", strokeDashArray:3, padding:{ left:0, right:0, top:0, bottom:0 } },
    xaxis:{
      categories:["18–24","25–34","35–44","45–54","55–64","65+"],
      labels:{ style:{ colors:G, fontSize:"9px" } },
      axisBorder:{ show:false }, axisTicks:{ show:false },
    },
    yaxis:{ show:false },
    dataLabels:{ enabled:true, formatter:v=>`${v}%`, offsetY:-4,
      style:{ fontSize:"9px", fontWeight:700, colors:[D] } },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  const treeOpts = {
    chart:{ type:"treemap", toolbar:{ show:false }, fontFamily:FONT },
    colors:TC,
    plotOptions:{ treemap:{ distributed:true, enableShades:false } },
    dataLabels:{
      enabled:true,
      formatter:(text, op) => [`${text}`, `${op.value}%`],
      style:{ fontSize:"10px", fontWeight:"bold", colors:["white"] },
    },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  return (
    <div style={{
      display:"grid",
      gridTemplateColumns:"1.3fr 0.8fr 0.8fr 0.8fr 0.8fr 0.8fr",
      gridTemplateRows:`${r1}px ${r2}px`,
      gap:GAP,
      height:gridH,
    }}>

      {/* Col 1, rows 1-2 : Répartition géographique */}
      <Card title="Répartition géographique"
        style={{ gridColumn:1, gridRow:"1 / span 2", padding:"10px 10px" }}>
        <TunisiaMap data={buildMapData(geo)} zones={geoZones}/>
      </Card>

      {/* Col 2, row 1 : Genre */}
      <Card title="Genre" style={{ gridColumn:2, gridRow:1 }}>
        <ReactApexChart options={genreOpts} series={d.genre||[0,0]} type="donut" height={ch1 - 30}/>
        <div style={{ display:"flex", flexDirection:"column", gap:3, marginTop:2 }}>
          {[["Homme",D,d.genre?.[0]??0],["Femme",Y,d.genre?.[1]??0]].map(([lbl,c,v])=>(
            <div key={lbl} style={{ display:"flex", alignItems:"center", gap:5 }}>
              <div style={{ width:8, height:8, borderRadius:2, background:c, flexShrink:0 }}/>
              <span style={{ fontSize:9.5, color:D, fontWeight:600, flex:1 }}>{lbl}</span>
              <span style={{ fontSize:10.5, fontWeight:900, color:D }}>{v}%</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Col 3-4, row 1 : Type de profession */}
      <Card title="Type de profession" style={{ gridColumn:"3 / span 2", gridRow:1 }}>
        {(d.typePro||[]).length > 0
          ? <ReactApexChart options={treeOpts} series={[{ data:d.typePro }]} type="treemap" height={ch1}/>
          : <div style={{ height:ch1, display:"flex", alignItems:"center", justifyContent:"center", color:G }}>N/D</div>
        }
      </Card>

      {/* Col 5, row 1 : Tranche d'âge */}
      <Card title="Tranche d'âge" style={{ gridColumn:"5 / span 2", gridRow:1 }}>
        <ReactApexChart options={ageOpts}
          series={[{ name:"Répondants", data:d.age||[] }]} type="bar" height={ch1}/>
      </Card>

      {/* Col 2, row 2 : Véhicule + Propriétaire */}
      <div style={{ gridColumn:2, gridRow:2, display:"flex", flexDirection:"column", gap:GAP, minHeight:0 }}>
        {[
          { iconFn:ICONS.vehicule, val:d.vehicule, lbl:"Ont un véhicule" },
          { iconFn:ICONS.maison,   val:d.proprio,  lbl:"Propriétaires"   },
        ].map(({ iconFn, val, lbl }) => (
          <div key={lbl} style={{
            flex:1, background:"white", borderRadius:10, border:"1px solid #EBEBEB",
            boxShadow:"0 2px 6px rgba(0,0,0,.05)", padding:"10px 12px",
            display:"flex", alignItems:"center", gap:10,
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
              <div style={{ fontSize:8.5, color:G, fontWeight:600, marginTop:2 }}>{lbl}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Col 3-4, row 2 : RevFam + RevInd côte à côte */}
      <div style={{ gridColumn:"3 / span 3", gridRow:2, display:"flex", flexDirection:"row", gap:GAP, minHeight:0 }}>
        <Card title="Revenu familial mensuel" style={{ flex:5, minWidth:0, minHeight:0, overflow:"hidden", display:"flex", flexDirection:"column" }}>
          <div style={{ flex:1, minHeight:0, overflowY:"auto" }}>
            <HBar labs={d.revFam?.labs||[]} vals={d.revFam?.vals||[]} labelWidth={LABEL_W}/>
          </div>
        </Card>
        <Card title="Revenu individuel mensuel" style={{ flex:5, minWidth:0, minHeight:0, overflow:"hidden", display:"flex", flexDirection:"column" }}>
          <div style={{ flex:1, minHeight:0, overflowY:"auto" }}>
            <HBar labs={d.revInd?.labs||[]} vals={d.revInd?.vals||[]} labelWidth={LABEL_W}/>
          </div>
        </Card>
      </div>

      {/* Col 5, row 2 : Profession */}
      <Card title="Profession" style={{ gridColumn:6, gridRow:2, display:"flex", flexDirection:"column" }}>
        <div style={{ flex:1, minHeight:0, overflowY:"auto", display:"flex", flexDirection:"column", gap:3 }}>
          {(d.professions||[]).slice(0,8).map(([name,pct],i) => (
            <div key={i} style={{
              display:"flex", alignItems:"center", gap:5,
              padding:"3px 5px", background:i%2===0?"#FAFAFA":"white", borderRadius:3,
            }}>
              <span style={{ flex:1, fontSize:9, color:D, fontWeight:600,
                overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{name}</span>
              <div style={{ height:4, width:36, background:"#EBEBEB", borderRadius:2, overflow:"hidden", flexShrink:0 }}>
                <div style={{ height:"100%", width:`${pct}%`, background:Y, borderRadius:2 }}/>
              </div>
              <span style={{ fontSize:9, fontWeight:800, color:D, width:24, textAlign:"right", flexShrink:0 }}>{pct}%</span>
            </div>
          ))}
        </div>
      </Card>

    </div>
  );
}

/* ── Panneau géo Entreprises : carte + badges zones + tableau villes ─────────*/
const ENT_ZONES = [
  { key:"nord-est",          label:"Nord-Est",            color:Y,         fg:D,      cities:["Bizerte","Tunis","Nabeul","Ben Arous","Manouba","Ariana","Zaghouan"] },
  { key:"nord-centre-ouest", label:"Nord & Centre-Ouest", color:"#BFBFBF", fg:D,      cities:["Jendouba","Kasserine","Béja","Sidi Bouzid","Siliana","Le Kef","Kairouan"] },
  { key:"sud-est-ouest",     label:"Sud-Est & Ouest",     color:"#8B7000", fg:"white", cities:["Gabès","Médenine","Tozeur","Gafsa","Tataouine"] },
  { key:"centre-est",        label:"Centre-Est",          color:D,         fg:"white", cities:["Monastir","Sousse","Mahdia","Sfax"] },
];

function GeoEntreprisesPanel({ geo }) {
  const mapData   = buildMapData(geo);
  const MAP_SCALE = 0.8;
  const scaledW   = Math.round(155 * MAP_SCALE);
  const scaledH   = Math.round(328 * MAP_SCALE);
  const zones     = ENT_ZONES.map(z => ({ ...z, pct: geo?.[z.key] || 0 }));
  const maxRows   = Math.max(...ENT_ZONES.map(z => z.cities.length));

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:6, height:"100%", minHeight:0 }}>
      {/* Carte + badges % — centré verticalement dans l'espace dispo */}
      <div style={{ flex:1, minHeight:0, display:"flex", alignItems:"center", justifyContent:"center" }}>
        <div style={{ display:"flex", gap:10, alignItems:"center" }}>
          <div style={{ width:scaledW, height:scaledH, flexShrink:0, overflow:"hidden" }}>
            <div style={{ transform:`scale(${MAP_SCALE})`, transformOrigin:"top left", width:155, height:328 }}>
              <TunisiaMap data={mapData} noPanel/>
            </div>
          </div>
          <div style={{ display:"flex", flexDirection:"column", gap:8, minWidth:0 }}>
            {zones.map(z => (
              <div key={z.key} style={{ display:"flex", alignItems:"center", gap:7 }}>
                <div style={{
                  fontSize:15, fontWeight:900, color:z.color===Y?D:"white",
                  background:z.color, padding:"2px 9px", borderRadius:6, flexShrink:0,
                  border:z.color===Y?"1px solid #c8a000":"none",
                }}>{z.pct}%</div>
                <span style={{ fontSize:9, fontWeight:600, color:G, lineHeight:1.3 }}>{z.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Tableau villes — hauteur fixe */}
      <div style={{ flexShrink:0, overflow:"hidden", borderRadius:6, border:"1px solid #E5E7EB" }}>
        <div style={{ display:"grid", gridTemplateColumns:`repeat(${ENT_ZONES.length},1fr)` }}>
          {ENT_ZONES.map(z => (
            <div key={z.key} style={{ background:z.color, color:z.fg,
              fontSize:7, fontWeight:800, padding:"4px 5px", textAlign:"center", lineHeight:1.3 }}>
              {z.label}
            </div>
          ))}
        </div>
        {Array.from({ length: maxRows }).map((_,row) => (
          <div key={row} style={{ display:"grid", gridTemplateColumns:`repeat(${ENT_ZONES.length},1fr)` }}>
            {ENT_ZONES.map(z => (
              <div key={z.key} style={{ fontSize:7.5, color:D, padding:"2px 5px",
                background:row%2===0?"#FAFAFA":"white", borderTop:"1px solid #F0F0F0" }}>
                {z.cities[row]||""}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ══ VUE ENTREPRISES ══════════════════════════════════════════════════════════*/
function EntreprisesView({ data }) {
  const e   = data?.entreprises;
  const geo = data?.geo || null;

  if (!e) return <div style={{ color:G, padding:32, textAlign:"center" }}>Données non disponibles</div>;

  const GAP = 6;
  const CO  = 38;

  const treeOpts = {
    chart:{ type:"treemap", toolbar:{ show:false }, fontFamily:FONT },
    colors: TC,
    plotOptions:{ treemap:{ distributed:true, enableShades:false } },
    dataLabels:{
      enabled:true,
      formatter:(text, op) => [`${text}`, `${op.value}%`],
      style:{ fontSize:"11px", fontWeight:"bold", colors:["white"] },
    },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  const donutOpts = {
    chart:{ type:"donut", fontFamily:FONT, toolbar:{ show:false } },
    colors:[Y, D, "#8B7000"],
    labels: e.employes?.labs || [],
    plotOptions:{ pie:{ donut:{ size:"62%" } } },
    legend:{ position:"bottom", fontSize:"9px", fontFamily:FONT,
      markers:{ width:8, height:8, radius:2 }, itemMargin:{ horizontal:6 } },
    dataLabels:{ enabled:true, formatter:v=>`${Math.round(v)}%`,
      style:{ fontSize:"10px", fontFamily:FONT, fontWeight:700 },
      dropShadow:{ enabled:false } },
    stroke:{ show:false },
    tooltip:{ y:{ formatter:v=>`${v}%` } },
  };

  return (
    <div style={{
      display:"grid",
      gridTemplateColumns:"1.8fr 1fr 1.4fr",
      gridTemplateRows:"55fr 45fr",
      gap:GAP,
      height:"100%",
    }}>

      {/* Col 1, rows 1-2 : Secteur d'activité */}
      <Card title="Secteur d'activité"
        style={{ gridColumn:1, gridRow:"1 / span 2", display:"flex", flexDirection:"column" }}>
        {(e.secteurs||[]).length > 0
          ? <div style={{ flex:1, minHeight:0 }}>
              <ReactApexChart options={treeOpts} series={[{ data:e.secteurs }]} type="treemap" height="90%"/>
            </div>
          : <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", color:G }}>N/D</div>
        }
      </Card>

      {/* Col 2, row 1 : Nombre d'employés */}
      <Card title="Nombre d'employés"
        style={{ gridColumn:2, gridRow:1, display:"flex", flexDirection:"column" }}>
        <div style={{ flex:1, minHeight:0 }}>
          <ReactApexChart options={donutOpts} series={e.employes?.vals||[]} type="donut" height="100%"/>
        </div>
      </Card>

      {/* Col 2, row 2 : Chiffres d'affaires annuel */}
      <Card title="Chiffres d'affaires annuel"
        style={{ gridColumn:2, gridRow:2, display:"flex", flexDirection:"column" }}>
        <div style={{ flex:1, minHeight:0, overflowY:"auto", display:"flex", alignItems:"center" }}>
          <div style={{ width:"100%" }}>
            <HBar labs={e.ca?.labs||[]} vals={e.ca?.vals||[]} labelWidth={105}/>
          </div>
        </div>
      </Card>

      {/* Col 3, rows 1-2 : Répartition géographique */}
      <Card title="Répartition géographique"
        style={{ gridColumn:3, gridRow:"1 / span 2", padding:"10px 10px", display:"flex", flexDirection:"column" }}>
        <GeoEntreprisesPanel geo={geo}/>
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

/* ── Stacked horizontal bar (perception / confiance) ─────────────────────────*/
function StackedBar({ labs=[], vals=[], colors=[] }) {
  const total = vals.reduce((s,v)=>s+v, 0) || 1;
  if (!vals.length) return <div style={{ color:G, fontSize:10 }}>N/D</div>;
  return (
    <div>
      <div style={{ display:"flex", height:18, borderRadius:4, overflow:"hidden", marginBottom:5 }}>
        {vals.map((v,i) => (
          <div key={i} style={{ flex:v, background:colors[i]||G, transition:"flex .3s" }}/>
        ))}
      </div>
      <div style={{ display:"flex", flexWrap:"wrap", gap:"4px 10px" }}>
        {labs.map((lab,i) => (
          <div key={i} style={{ display:"flex", alignItems:"center", gap:4 }}>
            <div style={{ width:7, height:7, borderRadius:2, background:colors[i]||G, flexShrink:0 }}/>
            <span style={{ fontSize:8, color:G, fontWeight:600 }}>{lab}</span>
            <span style={{ fontSize:8.5, fontWeight:900, color:D }}>{vals[i]}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Ranking card ─────────────────────────────────────────────────────────────
   accent       : couleur du winner (#1) — Y pour positif, rouge pour pire
   accentFg     : couleur texte sur le winner
   icon         : SVG path JSX affiché dans le winner banner
──────────────────────────────────────────────────────────────────────────────*/
/* podium column helpers */
const PODIUM_H  = { 0:30, 1:46, 2:20 };
const PODIUM_OP = { 0:.82, 1:1, 2:.6  };
const PODIUM_ORD= [1, 0, 2];

function PodiumCol({ item, pos, accent, accentFg }) {
  const rank  = pos === 0 ? 2 : pos === 1 ? 1 : 3;
  const isTop = rank === 1;
  const logo  = getLogoSrc(item.code);
  const label = LABEL[item.code] || item.label || item.code || "";
  const short = label.split(" ")[0];

  /* normalise accent alias early (needed for step colors) */
  const accN = accent === D ? "DB" : accent;
  const isCustom = accN !== Y && accN !== "DB" && accN !== "#B80C26";

  /* rich step colors — distinct shades, no opacity trick */
  let stepBg, stepFg, stepRankColor;
  if (accent === Y) {
    stepBg       = isTop ? "linear-gradient(180deg,#FFE030 0%,#D4A900 100%)"
                 : pos===0 ? "#C8A000" : "#9E8000";
    stepFg       = D;
    stepRankColor= isTop ? "rgba(0,0,0,.22)" : "rgba(0,0,0,.18)";
  } else if (accN === "DB") {
    stepBg       = isTop ? "linear-gradient(180deg,#454558 0%,#2A2A38 100%)"
                 : pos===0 ? "#5C5C70" : "#7C7C8E";
    stepFg       = isTop ? Y : "rgba(255,255,255,.6)";
    stepRankColor= isTop ? "rgba(255,230,0,.25)" : "rgba(255,255,255,.2)";
  } else if (isCustom) {
    stepBg       = isTop ? `linear-gradient(180deg,${accent} 0%,${accent}CC 100%)`
                 : pos===0 ? `${accent}CC` : `${accent}88`;
    stepFg       = "white";
    stepRankColor= "rgba(255,255,255,.22)";
  } else {
    stepBg       = isTop ? "linear-gradient(180deg,#D41028 0%,#8B0A1D 100%)"
                 : pos===0 ? "#943040" : "#6A2535";
    stepFg       = "white";
    stepRankColor= "rgba(255,255,255,.2)";
  }

  /* glow tint behind #1 info area */
  const glowBg = isTop
    ? (accent===Y    ? "radial-gradient(ellipse at 50% 90%,rgba(255,224,0,.18) 0%,transparent 75%)"
     : accN==="DB"   ? "radial-gradient(ellipse at 50% 90%,rgba(255,230,0,.10) 0%,transparent 75%)"
     : isCustom      ? `radial-gradient(ellipse at 50% 90%,${accent}28 0%,transparent 75%)`
     : "radial-gradient(ellipse at 50% 90%,rgba(200,10,30,.14) 0%,transparent 75%)")
    : "none";

  const pctColor = isTop
    ? (accent===Y ? "#6B5000" : accN==="DB" ? Y : isCustom ? accent : "#FFD0D8")
    : "#555560";

  const crownColor = accent===Y ? "#8B6A00" : accN==="DB" ? Y : "#FFD700";

  /* logo box dimensions — logo is the visual hero */
  const LW = isTop ? 52 : pos===0 ? 38 : 30;
  const LH = isTop ? 34 : pos===0 ? 24 : 18;
  const LI = isTop ? 20 : pos===0 ? 14 : 10;

  const accentBorder = accent===Y ? Y : accN==="DB" ? Y : isCustom ? accent : "#B80C26";

  return (
    <div style={{ flex:1, display:"flex", flexDirection:"column", alignItems:"center" }}>
      {/* ── info above step ── */}
      <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:3,
        paddingBottom:4, width:"100%", borderRadius:"6px 6px 0 0",
        background:glowBg }}>

        {/* crown — only #1, spacer for others */}
        {isTop
          ? <svg viewBox="0 0 22 15" width="16" height="10" fill="none"
              stroke={crownColor} strokeWidth="1.9"
              strokeLinejoin="round" strokeLinecap="round"
              style={{ filter:`drop-shadow(0 1px 3px ${crownColor}88)` }}>
              <polyline points="1,14 4,5 9,10 11,1 13,10 18,5 21,14 1,14"/>
            </svg>
          : <div style={{ height:10 }}/>
        }

        {/* ── LOGO — hero element ── */}
        <div style={{
          width:LW, height:LH,
          background:"white",
          borderRadius: isTop ? 9 : 5,
          display:"flex", alignItems:"center", justifyContent:"center",
          boxShadow: isTop
            ? `0 0 0 3px ${accentBorder}, 0 6px 20px rgba(0,0,0,.28)`
            : pos===0
            ? "0 0 0 1.5px #E0E0E8, 0 3px 10px rgba(0,0,0,.14)"
            : "0 1px 6px rgba(0,0,0,.10)",
          position:"relative",
        }}>
          {logo
            ? <img src={logo} alt={item.code}
                style={{ height:LI, maxWidth:LW-10, objectFit:"contain" }}/>
            : <span style={{ fontSize: isTop?10:8, fontWeight:900, color:D,
                textAlign:"center", padding:"2px 3px",
                overflow:"hidden", display:"-webkit-box",
                WebkitLineClamp:2, WebkitBoxOrient:"vertical" }}>
                {short}
              </span>
          }
          {/* rank badge — top-right corner of logo */}
          <div style={{
            position:"absolute", top:-5, right:-5,
            width: isTop?13:11, height: isTop?13:11,
            borderRadius:"50%",
            background: isTop
              ? (accent===Y ? "#D4A900" : accent==="DB" ? Y : "#B80C26")
              : "#E8E8F0",
            display:"flex", alignItems:"center", justifyContent:"center",
            fontSize: isTop?9:8, fontWeight:900,
            color: isTop ? (accent===Y?D:"black") : G,
            boxShadow:"0 1px 4px rgba(0,0,0,.18)",
            border:"1.5px solid white",
          }}>{rank}</div>
        </div>

        {/* pct — bold accent for #1 */}
        <div style={{
          fontSize: isTop?14:9.5,
          fontWeight:900,
          color: pctColor,
          letterSpacing: isTop?"-0.5px":"-0.1px",
          lineHeight:1,
        }}>{item.pct}%</div>

        {/* name */}
        <div style={{
          fontSize: isTop?8.5:7.5, fontWeight: isTop?700:500,
          color: isTop?"#333340":"#888898",
          textAlign:"center", lineHeight:1.2,
          overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap",
          width:"100%", padding:"0 3px",
        }}>{short}</div>
      </div>

      {/* ── step ── */}
      <div style={{
        width:"100%", height:PODIUM_H[pos],
        background:stepBg,
        borderRadius:"4px 4px 0 0",
        display:"flex", alignItems:"center", justifyContent:"center",
        boxShadow: isTop ? "inset 0 2px 0 rgba(255,255,255,.18)" : "none",
      }}/>
    </div>
  );
}

function RankingCard({ title, items=[], accent=Y, accentFg=D }) {
  if (!items.length) {
    return (
      <Card title={title} style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column" }}>
        <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", color:G, fontSize:10 }}>N/D</div>
      </Card>
    );
  }

  const list  = items.slice(0, 5);
  const tail  = list.slice(3);               // #4 and #5
  const max1  = list[0]?.pct || 1;
  const barColor = accent === "#B80C26" ? "#B80C26" : accent === Y ? "#C8A000" : accent === D ? D : accent;

  /* normalise accent alias */
  const acc = accent === D ? "DB" : accent;

  return (
    <Card title={title} style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column" }}>
      <div style={{ flex:1, display:"flex", flexDirection:"column", minHeight:0 }}>

        {/* ── Podium ── */}
        <div style={{ flexShrink:0 }}>
          {/* columns */}
          <div style={{ display:"flex", alignItems:"flex-end", gap:2 }}>
            {PODIUM_ORD.map((idx, pos) => {
              const item = list[idx];
              if (!item) return <div key={pos} style={{ flex:1 }}/>;
              return <PodiumCol key={pos} item={item} pos={pos} accent={acc} accentFg={accentFg}/>;
            })}
          </div>
          {/* base bar */}
          <div style={{ height:3, background:acc==="DB"?D:acc===Y?Y:accent,
            borderRadius:"0 0 4px 4px", marginBottom:6 }}/>
        </div>

        {/* ── Tail #4-5 ── */}
        {tail.length > 0 && (
          <div style={{ display:"flex", flexDirection:"column", gap:4 }}>
            {tail.map((item, i) => {
              const logo = getLogoSrc(item.code);
              const bw   = Math.round((item.pct / max1) * 100);
              return (
                <div key={i} style={{ display:"flex", alignItems:"center", gap:5 }}>
                  <div style={{ width:15, height:15, borderRadius:3, flexShrink:0,
                    background:"#F0F0F4", display:"flex", alignItems:"center", justifyContent:"center",
                    fontSize:8.5, fontWeight:900, color:G }}>{i+4}</div>
                  {logo
                    ? <img src={logo} alt={item.code} style={{ height:12, maxWidth:28, objectFit:"contain", flexShrink:0 }}/>
                    : <div style={{ width:28, fontSize:8, fontWeight:700, color:D, flexShrink:0,
                        overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                        {(LABEL[item.code]||item.label||"").split(" ")[0]}
                      </div>
                  }
                  <div style={{ flex:1, fontSize:8.5, fontWeight:600, color:D,
                    overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
                    {LABEL[item.code]||item.label||item.code}
                  </div>
                  <div style={{ display:"flex", alignItems:"center", gap:3, flexShrink:0, width:60 }}>
                    <div style={{ flex:1, height:4, background:"#EBEBEB", borderRadius:3, overflow:"hidden" }}>
                      <div style={{ height:"100%", width:`${bw}%`, background:barColor, borderRadius:3 }}/>
                    </div>
                    <span style={{ fontSize:9, fontWeight:800, color:D, width:20, textAlign:"right" }}>{item.pct}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
}

/* ══ FICHE CLIENT ENTREPRISE ══════════════════════════════════════════════════*/
function FicheClientEntreprise({ data, code }) {
  const f      = data?.fiche      || {};
  // Clients RÉELS de la compagnie sélectionnée (colonnes "Assurance -
  // Compagnie 1..5" du fichier source) - PAS `data.counts`, qui est
  // l'échantillon global toutes compagnies confondues (utilisé par l'onglet
  // "Analyse de l'échantillon", pas par cette fiche). Avant ce fix, ce
  // widget affichait déjà "Clients de [la compagnie]" mais avec le total
  // global (toujours 50, quelle que soit la compagnie) - corrigé 2026-08-21.
  const counts = f.clientCounts   || {};
  const total  = f.nbRepondants ?? Object.values(counts).reduce((s,v)=>s+(v||0), 0);
  const ca     = data?.entreprises?.ca  || { labs:[], vals:[] };
  const revMen = data?.segments?.all?.revFam || { labs:[], vals:[] };
  const GAP    = 6;

  /* Modèle */
  const modLabs   = f.modeleIdeal?.labs || ["Digital","Mixte","Physique"];
  const modVals   = f.modeleIdeal?.vals || [];
  const modColors = [D, "#9B9BA8", "#BFBFBF"];

  /* Perception / Confiance */
  const percLabs   = f.perception?.labs || [];
  const percVals   = f.perception?.vals || [];
  const percColors = ["#B80C26","#FF8C42","#FFE600","#2E2E38"];

  const confLabs   = f.confiance?.labs || [];
  const confVals   = f.confiance?.vals || [];
  const confColors = [D,"#5a5a6a","#747480","#9B9BA8",Y];

  /* Canal */
  const canal = f.canal || null;
  const canalRowColors = { "Digital":Y, "Mixte":"#9B9BA8", "Physique":D };

  /* Satisfaction */
  const satif = f.satisfaction || null;
  const satColors = ["#B80C26","#FF8C42","#FFE600","#2E2E38"];

  const segDefs = [
    { key:"particuliers",   label:"Particuliers",   iconFn:ICONS.particuliers   },
    { key:"professionnels", label:"Professionnels", iconFn:ICONS.professionnels },
    { key:"entreprises",    label:"Entreprises",    iconFn:ICONS.tre            },
  ];

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:GAP, height:"100%", overflow:"hidden" }}>

      {/* ── Ligne 1 : Clients | CA annuel | Rev. mensuel | Modèle ── */}
      <div style={{ display:"flex", gap:GAP, flex:"0 0 28%", minHeight:0 }}>

        {/* Clients de la compagnie — layout horizontal : donut gauche, segments droite */}
        {(() => {
          const segColors = { particuliers:"#2E2E38", professionnels:Y, entreprises:"#A0A0B4" };
          const cumul = segDefs.reduce((acc, { key }, i) => {
            const pct = total ? Math.round(((counts[key]||0)/total)*100) : 0;
            acc.push({ key, pct, start: i===0 ? 0 : acc[i-1].start + acc[i-1].pct });
            return acc;
          }, []);
          const conicStops = cumul.map(({ key, pct, start }) =>
            `${segColors[key]} ${start}% ${start+pct}%`
          ).join(", ");
          return (
            <div style={{
              flex:"0 0 27%", borderRadius:12,
              background:"white", border:"1px solid #E8E8EE",
              boxShadow:"0 2px 12px rgba(0,0,0,.06)",
              display:"flex", flexDirection:"column", padding:"10px 12px",
              overflow:"hidden",
            }}>
              {/* Header */}
              <div style={{ flexShrink:0 }}>
                <div style={{ display:"flex", alignItems:"center", gap:5, marginBottom:1 }}>
                  <div style={{ width:3, height:12, background:Y, borderRadius:2, flexShrink:0 }}/>
                  <div style={{ fontSize:8, fontWeight:700, textTransform:"uppercase", letterSpacing:"1.3px", color:G }}>Clients de la</div>
                </div>
                <div style={{ display:"flex", alignItems:"baseline", gap:6, paddingLeft:8 }}>
                  <div style={{ fontSize:14, fontWeight:900, color:D, letterSpacing:"-0.3px", lineHeight:1.2 }}>
                    {LABEL[code]||code}
                  </div>
                  {/* Échantillon restreint : la fiche est filtrée sur les clients
                      RÉELS de la compagnie (colonnes "Assurance - Compagnie
                      1..5") - un échantillon global de 50 répondants donne très
                      peu de clients identifiés par compagnie prise isolément
                      (souvent < 10). Signalé plutôt que masqué, cohérent avec le
                      principe du projet de ne jamais présenter une donnée comme
                      plus solide qu'elle ne l'est. */}
                  {total > 0 && total < 15 && (
                    <span style={{ fontSize:7.5, fontWeight:700, color:"#B8860B", background:"#FFF6DC",
                      border:"1px solid #F0DFA0", borderRadius:4, padding:"1px 5px", whiteSpace:"nowrap" }}>
                      échantillon restreint
                    </span>
                  )}
                </div>
              </div>

              {/* Corps : donut à gauche, segments à droite */}
              <div style={{ flex:1, display:"flex", gap:10, alignItems:"center", minHeight:0, marginTop:8 }}>
                {/* Donut */}
                <div style={{ flexShrink:0 }}>
                  <div style={{
                    width:76, height:76, borderRadius:"50%",
                    background: total ? `conic-gradient(${conicStops})` : "#F0F0F4",
                    display:"flex", alignItems:"center", justifyContent:"center",
                    boxShadow:"0 2px 12px rgba(0,0,0,.10)",
                  }}>
                    <div style={{
                      width:50, height:50, borderRadius:"50%", background:"white",
                      display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center",
                      boxShadow:"0 1px 4px rgba(0,0,0,.08)",
                    }}>
                      <span style={{ fontSize:16, fontWeight:900, color:D, lineHeight:1 }}>{total||"—"}</span>
                      <span style={{ fontSize:7, color:G, fontWeight:600, textTransform:"uppercase", letterSpacing:"0.6px" }}>répond.</span>
                    </div>
                  </div>
                </div>

                {/* Segments */}
                <div style={{ flex:1, display:"flex", flexDirection:"column", gap:5, justifyContent:"space-evenly" }}>
                  {cumul.map(({ key, pct }) => {
                    const def = segDefs.find(s => s.key===key);
                    if (!def) return null;
                    const cnt = counts[key] || 0;
                    const barW = total ? Math.round((cnt/total)*100) : 0;
                    const c = segColors[key];
                    return (
                      <div key={key}>
                        <div style={{ display:"flex", alignItems:"center", gap:4, marginBottom:2 }}>
                          <div style={{ width:7, height:7, borderRadius:2, flexShrink:0, background:c }}/>
                          <div style={{ fontSize:9, color:G, fontWeight:600, flex:1 }}>{def.label}</div>
                          <div style={{ display:"flex", alignItems:"baseline", gap:2 }}>
                            <span style={{ fontSize:12, fontWeight:900, color:D, lineHeight:1 }}>{cnt||"—"}</span>
                            <span style={{ fontSize:9, fontWeight:800, color: c===Y?"#8B7000":c }}> {pct}%</span>
                          </div>
                        </div>
                        <div style={{ height:4, background:"#F0F0F4", borderRadius:3, overflow:"hidden" }}>
                          <div style={{ height:"100%", width:`${barW}%`, background:c, borderRadius:3, transition:"width .5s ease" }}/>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          );
        })()}

        {/* CA annuel */}
        <Card title="Chiffre d'affaires annuel" style={{ flex:"0 0 24%", minHeight:0, display:"flex", flexDirection:"column" }}>
          <div style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column" }}>
            <HBar labs={ca.labs} vals={ca.vals} labelWidth={105} fill={true}/>
          </div>
        </Card>

        {/* Revenu mensuel */}
        <Card title="Revenu mensuel" style={{ flex:"0 0 24%", minHeight:0, display:"flex", flexDirection:"column" }}>
          <div style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column" }}>
            <HBar labs={revMen.labs} vals={revMen.vals} labelWidth={105} fill={true}/>
          </div>
        </Card>

        {/* Modèle assurantiel idéal — compact */}
        <Card title="Modèle assurantiel idéal" style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column" }}>
          {modVals.length > 0 ? (
            <div style={{ flex:1, display:"flex", gap:10, alignItems:"center", minHeight:0 }}>
              <div style={{ width:32, alignSelf:"stretch", display:"flex", flexDirection:"column", borderRadius:8, overflow:"hidden", flexShrink:0 }}>
                {modLabs.map((lab, i) => (
                  <div key={lab} style={{
                    flex:modVals[i]||1, background:modColors[i],
                    display:"flex", alignItems:"center", justifyContent:"center",
                  }}>
                    <span style={{ fontSize:9, fontWeight:900, color:modColors[i]===Y?D:"white",
                      writingMode:"vertical-rl", textOrientation:"mixed" }}>
                      {modVals[i]}%
                    </span>
                  </div>
                ))}
              </div>
              <div style={{ flex:1, display:"flex", flexDirection:"column", gap:10, justifyContent:"space-evenly" }}>
                {modLabs.map((lab, i) => (
                  <div key={lab} style={{ display:"flex", alignItems:"center", gap:6 }}>
                    <div style={{ width:9, height:9, borderRadius:2, background:modColors[i], flexShrink:0 }}/>
                    <span style={{ fontSize:10, fontWeight:700, color:D, flex:1 }}>{lab}</span>
                    <span style={{ fontSize:14, fontWeight:900, color:D }}>{modVals[i]??0}%</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", color:G }}>N/D</div>
          )}
        </Card>
      </div>

      {/* ── Ligne 2 : Perception+Confiance | Pire | Top of Mind | Meilleure ── */}
      <div style={{ display:"flex", gap:GAP, flex:"0 0 40%", minHeight:0 }}>

        {/* Perception générale + Degré de confiance */}
        <div style={{
          flex:"0 0 27%", background:"white", borderRadius:12, border:"1px solid #EBEBEB",
          boxShadow:"0 2px 8px rgba(0,0,0,0.05)", padding:"10px 12px",
          display:"flex", flexDirection:"column", gap:8, overflow:"hidden",
        }}>
          <div style={{ flex:1, display:"flex", flexDirection:"column", justifyContent:"space-between" }}>
            <div style={{ display:"flex", alignItems:"center", gap:5 }}>
              <span style={{ width:5, height:5, borderRadius:"50%", background:"#E70013", display:"block" }}/>
              <span style={{ fontSize:9.5, fontWeight:900, textTransform:"uppercase", letterSpacing:"1.2px", color:"#E70013" }}>
                Perception générale
              </span>
            </div>
            <StackedBar labs={percLabs} vals={percVals} colors={percColors}/>
          </div>
          <div style={{ height:1, background:"#F0F0F4", flexShrink:0 }}/>
          <div style={{ flex:1, display:"flex", flexDirection:"column", justifyContent:"space-between" }}>
            <div style={{ display:"flex", alignItems:"center", gap:5 }}>
              <span style={{ width:5, height:5, borderRadius:"50%", background:"#E70013", display:"block" }}/>
              <span style={{ fontSize:9.5, fontWeight:900, textTransform:"uppercase", letterSpacing:"1.2px", color:"#E70013" }}>
                Degré de confiance
              </span>
            </div>
            <StackedBar labs={confLabs} vals={confVals} colors={confColors}/>
          </div>
        </div>

        {/* Pire compagnie */}
        <div style={{ flex:"0 0 24%", minHeight:0, display:"flex", flexDirection:"column" }}>
          <RankingCard
            title="Pire compagnie"
            items={f.pireCompagnie||[]}
            accent="#B80C26"
            accentFg="white"
          />
        </div>

        {/* Top of Mind */}
        <div style={{ flex:"0 0 24%", minHeight:0, display:"flex", flexDirection:"column" }}>
          <RankingCard
            title="Top of Mind"
            items={f.topOfMind||[]}
            accent={Y}
            accentFg={D}
          />
        </div>

        {/* Meilleure compagnie */}
        <div style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column" }}>
          <RankingCard
            title="Meilleure compagnie"
            items={f.meilleureCompagnie||[]}
            accent="#1A7A4A"
            accentFg="white"
          />
        </div>
      </div>

      {/* ── Ligne 3 : Canal | Satisfaction ──────────────────────────────── */}
      <div style={{ display:"flex", gap:GAP, flex:1, minHeight:0 }}>

        {/* Canal préférentiel */}
        <Card title="Canal préférentiel pour les parcours clés"
          style={{ flex:"0 0 52%", minHeight:0, display:"flex", flexDirection:"column", padding:"8px 10px" }}>
          {canal ? (
            <div style={{ flex:1, display:"flex", flexDirection:"column", minHeight:0 }}>
              {/* Headers */}
              <div style={{ display:"grid", gridTemplateColumns:`120px repeat(${(canal.ops||[]).length}, 1fr)`,
                gap:2, marginBottom:2, flexShrink:0 }}>
                <div/>
                {(canal.ops||[]).map((op, i) => (
                  <div key={i} style={{ fontSize:8.5, fontWeight:700, color:G, textAlign:"center", lineHeight:1.25 }}>{op}</div>
                ))}
              </div>
              {/* Rows */}
              {(canal.rows||[]).map((row, ri) => {
                const bg = row.label==="Digital" ? Y : row.label==="Mixte" ? "#F5F5F5" : D;
                const fg = row.label==="Digital" ? D : row.label==="Mixte" ? G : "white";
                return (
                  <div key={ri} style={{ display:"grid", gap:2,
                    gridTemplateColumns:`120px repeat(${(canal.ops||[]).length}, 1fr)`,
                    marginBottom:2, flex:1 }}>
                    <div style={{
                      background:bg, color:fg, borderRadius:4,
                      fontSize:10, fontWeight:800, display:"flex", alignItems:"center", padding:"0 8px",
                    }}>{row.label}</div>
                    {(row.vals||[]).map((v,ci) => (
                      <div key={ci} style={{
                        background:row.label==="Digital"?"#FFFBE6":row.label==="Mixte"?"#F8F8F8":"#F0F0F4",
                        borderRadius:4, display:"flex", alignItems:"center", justifyContent:"center",
                        fontSize:11, fontWeight:700, color:D,
                      }}>{v}%</div>
                    ))}
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", color:G }}>N/D</div>
          )}
        </Card>

        {/* Niveau de satisfaction */}
        <Card title="Niveau de satisfaction par type d'opération"
          style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column", padding:"8px 10px" }}>
          {satif ? (
            <div style={{ flex:1, display:"flex", flexDirection:"column", minHeight:0 }}>
              {/* Headers */}
              <div style={{ display:"grid",
                gridTemplateColumns:`140px repeat(${(satif.ops||[]).length}, 1fr)`,
                gap:2, marginBottom:2, flexShrink:0 }}>
                <div/>
                {(satif.ops||[]).map((op, i) => (
                  <div key={i} style={{ fontSize:8, fontWeight:700, color:G, textAlign:"center", lineHeight:1.25 }}>{op}</div>
                ))}
              </div>
              {/* Rows */}
              {(satif.rows||[]).map((row, ri) => (
                <div key={ri} style={{ display:"grid", gap:2,
                  gridTemplateColumns:`140px repeat(${(satif.ops||[]).length}, 1fr)`,
                  marginBottom:2, flex:1 }}>
                  <div style={{
                    background:satColors[ri]||G, color:"white", borderRadius:4,
                    fontSize:9, fontWeight:700, display:"flex", alignItems:"center", padding:"0 6px", lineHeight:1.2,
                  }}>{row.label}</div>
                  {(row.vals||[]).map((v, ci) => (
                    <div key={ci} style={{
                      background:`${satColors[ri]}22`,
                      borderRadius:4, display:"flex", alignItems:"center", justifyContent:"center",
                      fontSize:10.5, fontWeight:700, color:D,
                      border:`1px solid ${satColors[ri]}33`,
                    }}>{v}%</div>
                  ))}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center", color:G }}>N/D</div>
          )}
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
