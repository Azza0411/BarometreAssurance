import { useState, useMemo, useEffect, useRef } from "react";
import PageHeaderBar from "../components/PageHeaderBar";

const Y = "#FFE600", D = "#2E2E38", G = "#747480";
const FONT = "Barlow,system-ui,sans-serif";
const API = "http://localhost:8002";

/* ── Données statiques de secours ────────────────────────────────────────── */
const ACTU_STATIC = [
  { id:1, src:"ILBOURSA",       date:"08/07/2026", compagnie:"BNA Assurances", categorie:"Innovation",
    url:"https://www.ilboursa.com/marches/mobilite-electrique-bna-assurances-installe-deux-nouvelles-bornes-de-recharge-a-sfax_62826",
    image:null, titre:"BNA Assurances inaugure deux bornes de recharge VE à Sfax" },
  { id:2, src:"ATLAS MAGAZINE", date:"17/07/2026", compagnie:"STAR Assurances", categorie:"Résultats financiers",
    url:"https://www.atlas-mag.net/fr/articles/star-assurances-distribution-de-dividendes-0",
    image:null, titre:"STAR Assurances : distribution de dividendes" },
];

/* ── Logos compagnies — même liste que Analyse Comparative ─────────────── */
const LOGO_COMPANIES = [
  { key:"STAR Assurances",    logo:"/logos/STAR.png"       },
  { key:"COMAR Assurances",   logo:"/logos/COMAR.png"      },
  { key:"GAT Assurances",     logo:"/logos/GAT.png"        },
  { key:"Astree Assurances",  logo:"/logos/astree.png"     },
  { key:"Carte Assurances",   logo:"/logos/Carte.png"      },
  { key:"Lloyd Tunisien",     logo:"/logos/LLOYD.png"      },
  { key:"Maghrebia",          logo:"/logos/Maghrebia.png"  },
  { key:"BH Assurance",       logo:"/logos/BH.png"         },
  { key:"BNA Assurances",     logo:"/logos/BNA.png"        },
  { key:"AMI Assurances",     logo:"/logos/AMI.png"        },
  { key:"Attijari Assurance", logo:"/logos/Attijari.png"   },
  { key:"Tunis Re",           logo:"/logos/TunisRe.png"    },
];

const SOURCES  = ["Toutes les sources", "ILBOURSA", "ATLAS MAGAZINE"];
const PERIODES = [
  "Toutes les périodes","Cette semaine","Ce mois",
  "Les 3 derniers mois","Les 6 derniers mois","Cette année",
];
const PER_PAGE_OPTS = [5, 10, 20, 50];

/* Styles badges */
const SRC_STYLE = {
  "ILBOURSA":      { bg:"#DCFCE7", color:"#15803D", border:"#BBF7D0" },
  "ATLAS MAGAZINE":{ bg:"#FFF7ED", color:"#92400E", border:"#FDE68A" },
};
const CAT_STYLE = {
  "Réglementation":              { bg:"#FEF2F2", color:"#991B1B", border:"#FECACA" },
  "Résultats financiers":        { bg:"#F0FDF4", color:"#15803D", border:"#BBF7D0" },
  "Gouvernance":                 { bg:"#FFFBEB", color:"#92400E", border:"#FDE68A" },
  "Coopération institutionnelle":{ bg:"#EFF6FF", color:"#1D4ED8", border:"#BFDBFE" },
  "Publication":                 { bg:"#F5F3FF", color:"#5B21B6", border:"#DDD6FE" },
  "Innovation":                  { bg:"#F0FDFA", color:"#0F766E", border:"#99F6E4" },
  "Digital":                     { bg:"#EFF6FF", color:"#1D4ED8", border:"#BFDBFE" },
  "Partenariat":                 { bg:"#FFF7ED", color:"#C2410C", border:"#FDBA74" },
  "Actualité":                   { bg:"#F9FAFB", color:"#374151", border:"#E5E7EB" },
};

function SrcBadge({ src }) {
  const s = SRC_STYLE[src] || { bg:"#F5F5F5", color:G, border:"#E5E7EB" };
  return (
    <span style={{ fontSize:9, fontWeight:800, padding:"2px 9px", borderRadius:20,
      background:s.bg, color:s.color, border:`1px solid ${s.border}`,
      letterSpacing:"0.3px", textTransform:"uppercase", whiteSpace:"nowrap" }}>
      {src}
    </span>
  );
}
function CatBadge({ cat }) {
  const s = CAT_STYLE[cat] || { bg:"#F9FAFB", color:"#374151", border:"#E5E7EB" };
  return (
    <span style={{ fontSize:9, fontWeight:700, padding:"2px 9px", borderRadius:20,
      background:s.bg, color:s.color, border:`1px solid ${s.border}`, whiteSpace:"nowrap" }}>
      {cat || "—"}
    </span>
  );
}

function parseDate(str) {
  const p = str.split("/");
  return p.length === 3 ? `${p[0]}/${p[1]}/${p[2]}` : str;
}

/* ── Select dropdown dark ou light ── */
function Sel({ value, onChange, options, dark = false, style = {} }) {
  const arrow = dark
    ? `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M2.5 4.5L6 8l3.5-3.5' stroke='rgba(255,255,255,.6)' stroke-width='1.8' fill='none' stroke-linecap='round'/%3E%3C/svg%3E")`
    : `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M2.5 4.5L6 8l3.5-3.5' stroke='%23747480' stroke-width='1.8' fill='none' stroke-linecap='round'/%3E%3C/svg%3E")`;
  return (
    <select value={value} onChange={e => onChange(e.target.value)} style={{
      appearance:"none", WebkitAppearance:"none", fontFamily:FONT, outline:"none",
      cursor:"pointer", backgroundImage:arrow,
      backgroundRepeat:"no-repeat", backgroundPosition:"right 9px center", backgroundSize:11,
      ...(dark ? {
        background:"rgba(255,255,255,.08)", border:"1px solid rgba(255,255,255,.18)",
        borderRadius:8, padding:"7px 30px 7px 12px", fontSize:11, fontWeight:500,
        color:"rgba(255,255,255,.9)", colorScheme:"dark",
      } : {
        background:"white", border:"1px solid #E5E7EB", borderRadius:8,
        padding:"8px 30px 8px 12px", fontSize:11.5, fontWeight:500, color:D,
        boxShadow:"0 1px 4px rgba(0,0,0,.05)",
      }),
      ...style,
    }}>
      {options.map(o => <option key={o} value={o} style={{ color:D, background:"white" }}>{o}</option>)}
    </select>
  );
}

/* ══ CAROUSEL ════════════════════════════════════════════════════════════════ */
const NEWS_FONT = `"Barlow",system-ui,sans-serif`;

/* Category badge colors (matching PDF style) */
const CAT_CAROUSEL = {
  "Réglementation":               { bg:"#FFE600", color:D },
  "Résultats financiers":         { bg:"#FFE600", color:D },
  "Gouvernance":                  { bg:"#FFE600", color:D },
  "Coopération institutionnelle": { bg:"#FFE600", color:D },
  "Partenariat":                  { bg:"#FFE600", color:D },
  "Digital":                      { bg:"#FFE600", color:D },
  "Publication":                  { bg:"#FFE600", color:D },
};

function AlaUne({ items }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    if (!items.length) return;
    const t = setInterval(() => setIdx(i => (i + 1) % items.length), 7000);
    return () => clearInterval(t);
  }, [items.length]);
  if (!items.length) return null;
  const item = items[Math.min(idx, items.length - 1)];
  const hasImg = !!item.image;
  const catStyle = CAT_CAROUSEL[item.categorie] || { bg:"#FFE600", color:D };

  const navBtnBase = {
    position:"absolute", top:"50%", transform:"translateY(-50%)",
    zIndex:10, background:"rgba(255,255,255,.18)", border:"none", borderRadius:"50%",
    width:34, height:34, cursor:"pointer", display:"flex", alignItems:"center",
    justifyContent:"center", backdropFilter:"blur(6px)",
    boxShadow:"0 2px 8px rgba(0,0,0,.25)",
  };

  return (
    <div style={{
      height: 300, borderRadius:12, overflow:"hidden",
      boxShadow:"0 4px 24px rgba(0,0,0,.18)",
      position:"relative", display:"flex",
      background: "#13131A",
    }}>

      {/* ── Panneau gauche — texte ── */}
      <div style={{
        width:"52%", flexShrink:0,
        background:"linear-gradient(120deg, #777575 0%, #424242 25%, #252535 55%, #303030 80%, #000000 100%)",
        padding:"22px 26px 18px",
        display:"flex", flexDirection:"column", gap:0,
        borderRight:"1px solid rgba(255,255,255,.06)",
        position:"relative",
      }}>
        {/* "À LA UNE" avec barre jaune */}
        <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:14 }}>
          <div style={{ width:4, height:20, background:Y, borderRadius:2, flexShrink:0 }}/>
          <span style={{
            fontSize:9, fontWeight:900, letterSpacing:"3px", textTransform:"uppercase",
            color:Y, fontFamily:FONT,
          }}>À LA UNE</span>
        </div>

        {/* Badges : catégorie + source + date */}
        <div style={{ display:"flex", alignItems:"center", gap:7, flexWrap:"wrap", marginBottom:14 }}>
          {item.categorie && (
            <span style={{
              fontSize:9.5, fontWeight:800, textTransform:"uppercase", letterSpacing:"0.8px",
              background:catStyle.bg, color:catStyle.color,
              padding:"3px 10px", borderRadius:4, fontFamily:FONT,
            }}>{item.categorie}</span>
          )}
          <span style={{
            fontSize:9.5, fontWeight:700, color:"rgba(255,255,255,.75)",
            background:"rgba(255,255,255,.12)", padding:"3px 10px", borderRadius:4,
            fontFamily:FONT,
          }}>{item.src === "ILBOURSA" ? "IlBoursa" : "Atlas Magazine"}</span>
          <span style={{
            fontSize:9.5, fontWeight:600, color:"rgba(255,255,255,.55)",
            background:"rgba(255,255,255,.07)", padding:"3px 10px", borderRadius:4,
            fontFamily:FONT,
          }}>{item.date}</span>
        </div>

        {/* Grand titre */}
        <div style={{
          fontFamily: NEWS_FONT,
          fontSize: 24, fontWeight: 900,
          color:"white", lineHeight:1.22, letterSpacing:"-0.3px",
          display:"-webkit-box", WebkitLineClamp:3,
          WebkitBoxOrient:"vertical", overflow:"hidden",
          marginBottom:10,
        }}>
          {item.titre}
        </div>

        {/* Résumé */}
        {item.resume && (
          <div style={{
            fontSize:12, color:"rgba(255,255,255,.65)",
            lineHeight:1.55, fontFamily:FONT,
            display:"-webkit-box", WebkitLineClamp:2,
            WebkitBoxOrient:"vertical", overflow:"hidden",
            marginBottom:14,
          }}>
            {item.resume}
          </div>
        )}

        {/* Spacer */}
        <div style={{ flex:1 }}/>

        {/* CTA */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
          <a href={item.url} target="_blank" rel="noreferrer" style={{
            display:"inline-flex", alignItems:"center", gap:6,
            background:Y, color:D, textDecoration:"none",
            padding:"8px 18px", borderRadius:6, fontSize:11, fontWeight:800,
            fontFamily:FONT, boxShadow:"0 2px 12px rgba(239, 233, 233, 0.67)",
            letterSpacing:"0.2px",
          }}>
            Lire l'article →
          </a>

          {/* Dots navigation */}
          <div style={{ display:"flex", gap:5, alignItems:"center" }}>
            {items.map((_, i) => (
              <button key={i} onClick={() => setIdx(i)} style={{
                width: i === idx ? 20 : 6, height:6, borderRadius:3,
                border:"none", cursor:"pointer", padding:0,
                background: i === idx ? Y : "rgba(255,255,255,.35)",
                transition:"all .25s",
              }}/>
            ))}
          </div>
        </div>
      </div>

      {/* ── Panneau droit — image ── */}
      <div style={{ flex:1, position:"relative", overflow:"hidden", background:"#1a1a2e" }}>
        {hasImg ? (
          <img
            key={item.image}
            src={item.image}
            alt={item.titre}
            style={{
              width:"100%", height:"100%",
              objectFit:"cover", objectPosition:"center top",
              transition:"opacity .5s ease",
            }}
            onError={e => { e.target.style.display="none"; }}
          />
        ) : (
          <div style={{ width:"100%", height:"100%", background:`linear-gradient(135deg,#1a1a2e 0%,${D} 100%)` }}/>
        )}
        {/* Gradient flou côté gauche (séparation texte/image) */}
        <div style={{
          position:"absolute", inset:0, left:0, top:0, width:80, height:"100%",
          background:"linear-gradient(to right, #0D0D14 0%, rgba(13,13,20,.6) 40%, transparent 100%)",
          pointerEvents:"none",
        }}/>
        {/* Photo credit */}
        {item.src && (
          <span style={{
            position:"absolute", bottom:8, right:10,
            fontSize:9, color:"rgba(255,255,255,.55)", fontFamily:FONT,
            background:"rgba(0,0,0,.4)", padding:"2px 7px", borderRadius:3,
          }}>
            Photo : {item.src === "ILBOURSA" ? "IlBoursa" : "Atlas Magazine"}
          </span>
        )}
      </div>

      {/* Flèche gauche */}
      <button onClick={() => setIdx(i => (i - 1 + items.length) % items.length)}
        style={{ ...navBtnBase, left:12 }}>
        <svg viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2.2" width="10" height="10">
          <path d="M8 2L4 6l4 4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      {/* Flèche droite */}
      <button onClick={() => setIdx(i => (i + 1) % items.length)}
        style={{ ...navBtnBase, right:12 }}>
        <svg viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2.2" width="10" height="10">
          <path d="M4 2l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
    </div>
  );
}

/* ══ LOGO BAR — bande défilante sans cadres ═════════════════════════════════ */
const MARQUEE_STYLE = `
@keyframes marquee-logos {
  from { transform: translateX(0); }
  to   { transform: translateX(-50%); }
}
.logo-track {
  animation: marquee-logos 36s linear infinite;
  display: flex;
  align-items: center;
  gap: 8px;
  width: max-content;
  padding: 8px 4px;
}
.logo-track-wrap:hover .logo-track {
  animation-play-state: paused;
}
.logo-item {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 14px 6px 10px;
  border-radius: 8px;
  border: 1.5px solid #E5E7EB;
  background: white;
  flex-shrink: 0;
  cursor: pointer;
  transition: border-color .15s, background .15s, box-shadow .15s;
  box-shadow: 0 1px 3px rgba(0,0,0,.05);
}
.logo-item:hover {
  border-color: #D1D5DB;
  background: #F9FAFB;
  box-shadow: 0 2px 8px rgba(0,0,0,.08);
}
.logo-item.active {
  border-color: #FFE600;
  background: #FFFBE6;
  box-shadow: 0 2px 8px rgba(255,230,0,.2);
}
`;

function LogoFilterBar({ selected, onSelect, counts }) {

  /* Logos dupliqués pour boucle seamless */
  const doubled = [...LOGO_COMPANIES, ...LOGO_COMPANIES];

  return (
    <>
      <style>{MARQUEE_STYLE}</style>
      <div style={{
        background:"white", border:"1px solid #E5E7EB", borderRadius:10,
        padding:"10px 16px", boxShadow:"0 1px 6px rgba(0,0,0,.05)",
      }}>
        {/* ── En-tête ── */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:8 }}>
          <div style={{ display:"flex", alignItems:"center", gap:7 }}>
            <span style={{ width:3, height:13, background:Y, borderRadius:2, flexShrink:0 }}/>
            <span style={{ fontSize:9.5, fontWeight:800, color:D, letterSpacing:"1.5px", textTransform:"uppercase", fontFamily:FONT }}>
              Filtrer par compagnie
            </span>
            {selected && (
              <span style={{ fontSize:9, color:G, fontFamily:FONT }}>
                — <b style={{ color:D }}>{selected}</b>
                <button onClick={() => onSelect(null)} style={{
                  marginLeft:4, border:"none", background:"none",
                  cursor:"pointer", color:G, fontSize:13, lineHeight:1, padding:0,
                }}>×</button>
              </span>
            )}
          </div>
          <button onClick={() => onSelect(null)} style={{
            padding:"3px 12px", borderRadius:20, cursor:"pointer",
            fontFamily:FONT, fontSize:9.5, fontWeight:700,
            background: !selected ? D : "transparent",
            color: !selected ? "white" : G,
            border: !selected ? `1px solid ${D}` : "1px solid #D1D5DB",
            transition:"all .15s",
          }}>Toutes</button>
        </div>

        {/* ── Bande défilante claire ── */}
        <div className="logo-track-wrap" style={{ overflow:"hidden", position:"relative" }}>
          {/* Fondu gauche */}
          <div style={{ position:"absolute", left:0, top:0, bottom:0, width:32,
            background:"linear-gradient(90deg,white,transparent)", zIndex:2, pointerEvents:"none" }}/>
          {/* Fondu droit */}
          <div style={{ position:"absolute", right:0, top:0, bottom:0, width:32,
            background:"linear-gradient(270deg,white,transparent)", zIndex:2, pointerEvents:"none" }}/>

          <div className="logo-track">
            {doubled.map(({ key, logo }, i) => {
              const active = selected === key;
              return (
                <div
                  key={i}
                  className={`logo-item${active ? " active" : ""}`}
                  onClick={() => onSelect(active ? null : key)}
                  title={key}
                >
                  <img
                    src={logo}
                    alt={key}
                    style={{
                      height:22, maxWidth:60, objectFit:"contain",
                      filter: active ? "none" : "grayscale(15%) opacity(0.85)",
                      transition:"filter .15s",
                    }}
                    onError={e => { e.target.style.display="none"; }}
                  />
                  <span style={{
                    fontSize:9, fontWeight:600, color: active ? D : G,
                    whiteSpace:"nowrap", fontFamily:FONT,
                    transition:"color .15s",
                  }}>{key.replace(" Assurances","").replace(" Assurance","")}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}

/* ══ PAGE ════════════════════════════════════════════════════════════════════ */
export default function ActualitesSeminaires() {
  const [actu,         setActu]         = useState(ACTU_STATIC);
  const [search,       setSearch]       = useState("");
  const [srcFilter,    setSrcFilter]    = useState("Toutes les sources");
  const [compFilter,   setCompFilter]   = useState(null);   // null = toutes
  const [periodeFilter,setPeriodeFilter]= useState("Toutes les périodes");
  const [page,         setPage]         = useState(1);
  const [perPage,      setPerPage]      = useState(10);
  const [sortCol,      setSortCol]      = useState("date");
  const [sortAsc,      setSortAsc]      = useState(false);

  /* Fetch live data */
  useEffect(() => {
    fetch(`${API}/api/actualites`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && Array.isArray(data) && data.length > 0)
          setActu(data.map((item, i) => ({ id: 1000 + i, ...item })));
      })
      .catch(() => {});
  }, []);

  /* Carousel : 5 articles les plus récents toutes sources confondues, priorité image */
  const uneItems = useMemo(() => {
    const sortDate = a => {
      const p = a.date.split("/");
      return p.length === 3 ? `${p[2]}${p[1]}${p[0]}` : a.date + "0101";
    };
    return [...actu]
      .sort((a, b) => {
        const imgA = a.image ? 1 : 0, imgB = b.image ? 1 : 0;
        if (imgB !== imgA) return imgB - imgA;
        return sortDate(b).localeCompare(sortDate(a));
      })
      .slice(0, 5);
  }, [actu]);

  /* Comptage par compagnie (pour badges sur logos) */
  const companyCounts = useMemo(() => {
    const counts = {};
    actu.forEach(a => {
      if (a.compagnie && a.compagnie !== "—")
        counts[a.compagnie] = (counts[a.compagnie] || 0) + 1;
    });
    return counts;
  }, [actu]);

  const parseNum = s => {
    const p = s.split("/");
    return p.length === 3 ? `${p[2]}${p[1]}${p[0]}` : `${s}0101`;
  };

  const filtered = useMemo(() => {
    const now = new Date();
    let list = actu.filter(a => {
      if (srcFilter !== "Toutes les sources" && a.src !== srcFilter) return false;
      if (compFilter && a.compagnie !== compFilter) return false;

      if (periodeFilter !== "Toutes les périodes") {
        const parts = a.date.split("/");
        const aDate = parts.length === 3
          ? new Date(`${parts[2]}-${parts[1]}-${parts[0]}`)
          : new Date(`${a.date}-01-01`);
        const diff = now - aDate;
        const DAY  = 86400000;
        if (periodeFilter === "Cette semaine"       && diff > 7   * DAY) return false;
        if (periodeFilter === "Ce mois"             && diff > 31  * DAY) return false;
        if (periodeFilter === "Les 3 derniers mois" && diff > 91  * DAY) return false;
        if (periodeFilter === "Les 6 derniers mois" && diff > 182 * DAY) return false;
        if (periodeFilter === "Cette année"         && aDate.getFullYear() !== now.getFullYear()) return false;
      }

      if (search) {
        const q = search.toLowerCase();
        if (
          !a.titre.toLowerCase().includes(q) &&
          !(a.compagnie||"").toLowerCase().includes(q) &&
          !a.src.toLowerCase().includes(q) &&
          !a.date.toLowerCase().includes(q)
        ) return false;
      }
      return true;
    });

    list = [...list].sort((a, b) => {
      let cmp = 0;
      if (sortCol === "date")      cmp = parseNum(a.date).localeCompare(parseNum(b.date));
      if (sortCol === "titre")     cmp = a.titre.localeCompare(b.titre);
      if (sortCol === "compagnie") cmp = (a.compagnie||"").localeCompare(b.compagnie||"");
      if (sortCol === "src")       cmp = a.src.localeCompare(b.src);
      if (sortCol === "categorie") cmp = (a.categorie||"").localeCompare(b.categorie||"");
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [actu, search, srcFilter, compFilter, periodeFilter, sortCol, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const paginated  = filtered.slice((page - 1) * perPage, page * perPage);
  const from = filtered.length === 0 ? 0 : (page - 1) * perPage + 1;
  const to   = Math.min(page * perPage, filtered.length);

  function reset() {
    setSearch(""); setSrcFilter("Toutes les sources");
    setCompFilter(null); setPeriodeFilter("Toutes les périodes"); setPage(1);
  }

  function toggleSort(col) {
    if (sortCol === col) setSortAsc(v => !v);
    else { setSortCol(col); setSortAsc(false); }
  }

  const SortIcon = ({ col }) => (
    <span style={{ marginLeft:3, opacity: sortCol === col ? 1 : 0.3, fontSize:9 }}>
      {sortCol === col ? (sortAsc ? "↑" : "↓") : "↕"}
    </span>
  );

  const thStyle = {
    fontSize:11, fontWeight:700, color:"#374151", padding:"11px 14px",
    background:"#F9FAFB", borderBottom:"2px solid #E5E7EB", cursor:"pointer",
    userSelect:"none", whiteSpace:"nowrap", textAlign:"left",
  };

  const pageNums = useMemo(() => {
    const nums = [];
    for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) nums.push(i);
    return nums;
  }, [page, totalPages]);

  const hasActiveFilter = search || srcFilter !== "Toutes les sources"
    || compFilter || periodeFilter !== "Toutes les périodes";

  return (
    <div style={{ background:"#F8F9FA", fontFamily:FONT, minHeight:"calc(100vh - 92px)" }}>

      <PageHeaderBar
        title="Veille d'actualités"
        right={
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <div style={{ display:"flex", alignItems:"center", gap:7, background:"#F9FAFB",
              border:"1px solid #E5E7EB", borderRadius:20, padding:"5px 14px" }}>
              <div style={{ width:7, height:7, borderRadius:"50%", background:"#22C55E" }}/>
              <span style={{ fontSize:11, fontWeight:600, color:D }}>Sources · IlBoursa · Atlas Magazine</span>
            </div>
          </div>
        }
      />

      {/* ── Carousel ── */}
      <div style={{ padding:"16px 32px 0" }}>
        <AlaUne items={uneItems}/>
      </div>

      {/* ── Barre filtres + logos — sticky ── */}
      <div style={{ position:"sticky", top:0, zIndex:20, background:"#F8F9FA", padding:"12px 32px 0", display:"flex", flexDirection:"column", gap:10 }}>

        {/* ── Barre filtres ── */}
        <div style={{
          background:"linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)",
          padding:"14px 20px", borderRadius:10,
          boxShadow:"0 2px 12px rgba(10,10,20,.3)",
          display:"flex", alignItems:"center", gap:10, flexWrap:"wrap",
        }}>
          {/* Recherche */}
          <div style={{ display:"flex", alignItems:"center", gap:8,
            background:"rgba(255,255,255,.08)", border:"1px solid rgba(255,255,255,.14)",
            borderRadius:8, padding:"7px 12px", flex:"0 0 240px" }}>
            <svg viewBox="0 0 20 20" fill="none" stroke="rgba(255,255,255,.5)" strokeWidth="1.6" width="14" height="14">
              <circle cx="9" cy="9" r="6"/><path d="M15 15l3 3" strokeLinecap="round"/>
            </svg>
            <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
              placeholder="Titre, compagnie, source, date (ex: 07/2026)…"
              style={{ flex:1, border:"none", outline:"none", fontSize:11, color:"white",
                background:"transparent", fontFamily:FONT }}/>
            {search && (
              <button onClick={() => { setSearch(""); setPage(1); }}
                style={{ border:"none", background:"none", cursor:"pointer", color:"rgba(255,255,255,.5)", fontSize:14, lineHeight:1 }}>×</button>
            )}
          </div>

          <div style={{ width:1, height:32, background:"rgba(255,255,255,.10)", flexShrink:0 }}/>

          {/* Source */}
          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <span style={{ fontSize:7.5, fontWeight:700, color:"rgba(255,255,255,.38)", letterSpacing:"2px", textTransform:"uppercase" }}>Source</span>
            <Sel value={srcFilter} onChange={v => { setSrcFilter(v); setPage(1); }} options={SOURCES} dark/>
          </div>

          <div style={{ width:1, height:32, background:"rgba(255,255,255,.10)", flexShrink:0 }}/>

          {/* Période */}
          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <span style={{ fontSize:7.5, fontWeight:700, color:"rgba(255,255,255,.38)", letterSpacing:"2px", textTransform:"uppercase" }}>Période</span>
            <Sel value={periodeFilter} onChange={v => { setPeriodeFilter(v); setPage(1); }} options={PERIODES} dark/>
          </div>

          {/* Réinitialiser */}
          <button onClick={reset} style={{
            marginTop:14, display:"flex", alignItems:"center", gap:6,
            background:"rgba(255,230,0,.12)", border:"1px solid rgba(255,230,0,.35)",
            color:Y, borderRadius:8, padding:"8px 14px", fontSize:11.5, fontWeight:700,
            cursor:"pointer", fontFamily:FONT,
          }}>
            <svg viewBox="0 0 20 20" fill="none" stroke={Y} strokeWidth="1.8" width="13" height="13">
              <path d="M3 10a7 7 0 1013.93-1.37" strokeLinecap="round"/>
              <polyline points="17,4 17,9 12,9" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Réinitialiser
          </button>

          <div style={{ marginLeft:"auto", fontSize:10, color:"rgba(255,255,255,.38)", fontWeight:600 }}>
            {filtered.length} actualité{filtered.length !== 1 ? "s" : ""}
          </div>
        </div>

        {/* ── Logo bar ── */}
        <LogoFilterBar
          selected={compFilter}
          onSelect={key => { setCompFilter(key); setPage(1); }}
          counts={companyCounts}
        />

      </div>{/* end sticky bar */}

      {/* ── Table + pagination ── */}
      <div style={{ padding:"14px 32px 40px", display:"flex", flexDirection:"column", gap:14 }}>

        {/* ── Table ── */}
        <div style={{ background:"white", border:"1px solid #E5E7EB", borderRadius:10, overflow:"hidden" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
            <thead>
              <tr>
                <th style={thStyle} onClick={() => toggleSort("date")}>
                  Date <SortIcon col="date"/>
                </th>
                <th style={{ ...thStyle, width:"28%" }} onClick={() => toggleSort("titre")}>
                  Actualité <SortIcon col="titre"/>
                </th>
                <th style={{ ...thStyle, width:"22%", cursor:"default" }}>Résumé</th>
                <th style={thStyle} onClick={() => toggleSort("compagnie")}>
                  Compagnie <SortIcon col="compagnie"/>
                </th>
                <th style={thStyle} onClick={() => toggleSort("src")}>
                  Source <SortIcon col="src"/>
                </th>
                <th style={{ ...thStyle, cursor:"default" }}>Lien</th>
              </tr>
            </thead>
            <tbody>
              {paginated.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding:"48px", textAlign:"center", color:G, fontSize:13 }}>
                    Aucune actualité ne correspond aux filtres sélectionnés.
                  </td>
                </tr>
              ) : paginated.map((a, i) => (
                <tr key={a.id || i}
                  style={{ background: i % 2 === 0 ? "white" : "#FAFAFA", borderBottom:"1px solid #F0F0F0" }}
                  onMouseEnter={e => e.currentTarget.style.background="#FFFBE6"}
                  onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? "white" : "#FAFAFA"}>
                  <td style={{ padding:"12px 14px", whiteSpace:"nowrap", color:G, fontSize:11, fontWeight:500 }}>
                    {parseDate(a.date)}
                  </td>
                  <td style={{ padding:"12px 14px", color:D, fontWeight:600, lineHeight:1.45 }}>
                    {a.titre}
                  </td>
                  <td style={{ padding:"10px 14px", color:G, fontSize:11, lineHeight:1.5, maxWidth:220 }}>
                    {a.resume ? (
                      <span style={{
                        display:"-webkit-box", WebkitLineClamp:2,
                        WebkitBoxOrient:"vertical", overflow:"hidden",
                      }}>{a.resume}</span>
                    ) : <span style={{ color:"#C0C0C8", fontStyle:"italic" }}>—</span>}
                  </td>
                  <td style={{ padding:"12px 14px", color:D, whiteSpace:"nowrap", fontSize:11 }}>
                    {a.compagnie || "—"}
                  </td>
                  <td style={{ padding:"12px 14px", whiteSpace:"nowrap" }}>
                    <SrcBadge src={a.src}/>
                  </td>
                  <td style={{ padding:"12px 14px", whiteSpace:"nowrap" }}>
                    <a href={a.url} target="_blank" rel="noreferrer"
                      style={{ display:"inline-flex", alignItems:"center", gap:5,
                        fontSize:11, fontWeight:700, color:"#1D4ED8", textDecoration:"none" }}>
                      Lire l'article
                      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" width="10" height="10">
                        <path d="M4 12L12 4M6 4h6v6" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* ── Pagination ── */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"4px 0", flexWrap:"wrap", gap:10 }}>
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <span style={{ fontSize:12, color:G }}>
              Affichage de <b style={{ color:D }}>{from}</b> à <b style={{ color:D }}>{to}</b> sur{" "}
              <b style={{ color:D }}>{filtered.length}</b> actualité{filtered.length !== 1 ? "s" : ""}
            </span>
            <Sel value={String(perPage)} onChange={v => { setPerPage(Number(v)); setPage(1); }}
              options={PER_PAGE_OPTS.map(String)} style={{ padding:"6px 28px 6px 10px", fontSize:11 }}/>
            <span style={{ fontSize:12, color:G }}>par page</span>
          </div>

          <div style={{ display:"flex", alignItems:"center", gap:5 }}>
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              style={{ padding:"6px 10px", border:"1px solid #E5E7EB", borderRadius:7, background:"white",
                cursor: page === 1 ? "default" : "pointer", color: page === 1 ? "#C0C0C8" : D,
                fontFamily:FONT, fontSize:11, fontWeight:600, display:"flex", alignItems:"center" }}>
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" width="9" height="9">
                <path d="M8 3L4 6l4 3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            {pageNums.map(n => (
              <button key={n} onClick={() => setPage(n)}
                style={{ width:32, height:32, border: n === page ? "none" : "1px solid #E5E7EB",
                  borderRadius:7, background: n === page ? D : "white",
                  color: n === page ? "white" : D, fontSize:12, fontWeight: n === page ? 800 : 500,
                  cursor:"pointer", fontFamily:FONT }}>
                {n}
              </button>
            ))}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              style={{ padding:"6px 10px", border:"1px solid #E5E7EB", borderRadius:7, background:"white",
                cursor: page === totalPages ? "default" : "pointer",
                color: page === totalPages ? "#C0C0C8" : D,
                fontFamily:FONT, fontSize:11, fontWeight:600, display:"flex", alignItems:"center" }}>
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" width="9" height="9">
                <path d="M4 3l4 3-4 3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </div>

      </div>{/* end table area */}
    </div>
  );
}
