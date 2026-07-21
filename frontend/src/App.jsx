import React, { useState, useEffect, useRef } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import Chatbot from "./components/Chatbot";
import Sidebar            from "./components/Sidebar";
import ApercuMarche       from "./pages/ApercuMarche";
import Positionnement     from "./pages/Positionnement";
import Geographie         from "./pages/Geographie";
import FichesEntreprises  from "./pages/FichesEntreprises";
import AnalyseComparative from "./pages/AnalyseComparative";
import EnqueteMarche      from "./pages/EnqueteMarche";
import VeilleReglementaire    from "./pages/VeilleReglementaire";
import ActualitesSeminaires   from "./pages/ActualitesSeminaires";

/* ─── palette tokens ─── */
const C = {
  bg:     "#EEF0F6",
  card:   "#FFFFFF",
  navy:   "#0C1B2E",
  mid:    "#4A5568",
  muted:  "#8896A8",
  border: "#DDE2EC",
  yellow: "#FFE600",
  red:    "#C8102E",
  sidebar:"#3C3C4A",
};

/* ─── stats affichées en haut de page ─── */
const STATS = [
  { v:"11",       u:"compagnies",     sub:"actives en 2024" },
  { v:"87.4 %",   u:"ratio combiné",  sub:"moyenne secteur" },
  { v:"2,3 Md TND", u:"primes émises", sub:"exercice 2024"  },
  { v:"6 ans",    u:"historique",     sub:"2019 – 2024"     },
];

/* ─── modules ─── */
const MODULES = [
  { to:"/accueil",              label:"Accueil",
    tag:"", desc:"", color:"#FFE600",
    icon:<svg viewBox="0 0 20 20" fill="none" width="16" height="16">
      <path d="M3 9.5L10 3l7 6.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M5 8.5v7a1 1 0 001 1h3v-3h2v3h3a1 1 0 001-1v-7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
    </svg> },
  { to:"/apercu-marche",        label:"Aperçu marché",       tag:"Macro · Tendances",
    desc:"Vue macroéconomique, taux de pénétration, densité et évolution sectorielle.",
    color:"#2563EB",
    icon:<svg viewBox="0 0 20 20" fill="none" width="16" height="16">
      <path d="M2 14l4-4 3 3 4-5 4 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="2" cy="14" r="1.2" fill="currentColor"/><circle cx="6" cy="10" r="1.2" fill="currentColor"/>
      <circle cx="9" cy="13" r="1.2" fill="currentColor"/><circle cx="13" cy="8" r="1.2" fill="currentColor"/>
      <circle cx="17" cy="11" r="1.2" fill="currentColor"/>
    </svg> },
  { to:"/analyse-comparative",  label:"Analyse comparative",  tag:"Ratios · Benchmarking",
    desc:"Ratio combiné, sinistralité, frais de gestion et parts de marché comparées.",
    color:"#0891B2",
    icon:<svg viewBox="0 0 20 20" fill="none" width="16" height="16">
      <rect x="2" y="10" width="3" height="8" rx="1" fill="currentColor"/>
      <rect x="7" y="6"  width="3" height="12" rx="1" fill="currentColor"/>
      <rect x="12" y="3" width="3" height="15" rx="1" fill="currentColor"/>
      <rect x="17" y="8" width="3" height="10" rx="1" fill="currentColor"/>
    </svg> },
  { to:"/fiches",               label:"Vue par assurance",    tag:"Fiches · KPIs",
    desc:"Fiches détaillées par compagnie — KPIs financiers, bilan et résultats techniques.",
    color:"#7C3AED",
    icon:<svg viewBox="0 0 20 20" fill="none" width="16" height="16">
      <rect x="3" y="4" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M7 8h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg> },
  { to:"/enquete-marche",       label:"Enquête de marché",    tag:"Géographie · Distribution",
    desc:"Cartographie des agences, distribution territoriale et densité de couverture.",
    color:"#059669",
    icon:<svg viewBox="0 0 20 20" fill="none" width="16" height="16">
      <path d="M10 2a8 8 0 100 16A8 8 0 0010 2z" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M7 9.5h6M10 6.5v7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg> },
  { to:"/actualites-seminaires",label:"Veille d'actualité",   tag:"Presse · Événements",
    desc:"Articles de presse, séminaires et événements sectoriels — ilboursa, atlas-mag.",
    color:"#D97706",
    icon:<svg viewBox="0 0 20 20" fill="none" width="16" height="16">
      <path d="M3 5h14M3 10h10M3 15h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <circle cx="16" cy="14" r="3" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M15 14l.7.7 1.3-1.3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg> },
  { to:"/veille-reglementaire", label:"Veille réglementaire", tag:"CGA · Textes de loi",
    desc:"Circulaires CGA, textes de loi et décisions de l'autorité de contrôle.",
    color:"#BE123C",
    icon:<svg viewBox="0 0 20 20" fill="none" width="16" height="16">
      <path d="M4 4h12v12H4z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M7 8h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M13 2v3M7 2v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg> },
];

/* ─── Tunisia market viz (right panel) ─── */
function MarketViz() {
  const bars = [
    { y:2019, v:68 }, { y:2020, v:72 }, { y:2021, v:78 },
    { y:2022, v:81 }, { y:2023, v:85 }, { y:2024, v:87.4 },
  ];
  const maxV = 100;
  const W = 340, H = 180, padL = 32, padB = 28, padT = 12;
  const barW = 34, gap = 18;

  return (
    <div style={{ position:"relative", width:"100%", height:"100%",
      display:"flex", flexDirection:"column", gap:20 }}>

      {/* KPI tiles — haut droite */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
        {[
          { label:"Taux de pénétration", value:"1.9 %",  delta:"+0.2pp", up:true  },
          { label:"Primes nettes / hab.", value:"218 TND", delta:"+6.4 %", up:true  },
          { label:"Sinistres / Primes",  value:"58.1 %", delta:"−1.8pp", up:true  },
          { label:"Fonds propres total", value:"1.1 Md",  delta:"+4.2 %", up:true  },
        ].map(k => (
          <div key={k.label} style={{
            background:C.card, borderRadius:12,
            padding:"14px 16px",
            border:`1px solid ${C.border}`,
            boxShadow:"0 1px 4px rgba(12,27,46,.06)",
          }}>
            <div style={{ fontSize:9.5, fontWeight:600, color:C.muted,
              textTransform:"uppercase", letterSpacing:"1px", marginBottom:6 }}>{k.label}</div>
            <div style={{ fontSize:20, fontWeight:800, color:C.navy,
              letterSpacing:"-0.5px", lineHeight:1 }}>{k.value}</div>
            <div style={{ fontSize:10.5, fontWeight:600, marginTop:5,
              color: k.up ? "#059669" : "#DC2626" }}>{k.delta} vs N−1</div>
          </div>
        ))}
      </div>

      {/* Graphique ratio combiné */}
      <div style={{ background:C.card, borderRadius:12, border:`1px solid ${C.border}`,
        padding:"18px 20px", boxShadow:"0 1px 4px rgba(12,27,46,.06)" }}>
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline", marginBottom:16 }}>
          <div>
            <div style={{ fontSize:11, fontWeight:700, color:C.navy }}>Ratio combiné moyen</div>
            <div style={{ fontSize:9.5, color:C.muted, marginTop:2 }}>Ensemble du secteur · 2019–2024</div>
          </div>
          <div style={{ fontSize:9, fontWeight:700, padding:"3px 9px", borderRadius:20,
            background:"rgba(5,150,105,.1)", color:"#059669",
            border:"1px solid rgba(5,150,105,.2)" }}>↓ en amélioration</div>
        </div>

        <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ overflow:"visible" }}>
          {/* Grille horizontale */}
          {[70, 80, 90, 100].map(g => {
            const y = padT + (H - padB - padT) * (1 - g / maxV);
            return (
              <g key={g}>
                <line x1={padL} y1={y} x2={W} y2={y}
                  stroke={C.border} strokeWidth="1" strokeDasharray="4 4"/>
                <text x={padL - 6} y={y + 4} fontSize="8" fill={C.muted}
                  textAnchor="end" fontFamily="Barlow,system-ui,sans-serif">{g}</text>
              </g>
            );
          })}

          {/* Barres */}
          {bars.map((b, i) => {
            const x    = padL + i * (barW + gap);
            const bH   = (b.v / maxV) * (H - padB - padT);
            const y    = padT + (H - padB - padT) - bH;
            const last = i === bars.length - 1;
            return (
              <g key={b.y}>
                <rect x={x} y={y} width={barW} height={bH} rx="4"
                  fill={last ? C.yellow : "#E2E8F2"}/>
                <text x={x + barW / 2} y={H - 10} fontSize="8.5" fill={last ? C.navy : C.muted}
                  textAnchor="middle" fontWeight={last ? "700" : "400"}
                  fontFamily="Barlow,system-ui,sans-serif">{b.y}</text>
                {last && (
                  <text x={x + barW / 2} y={y - 6} fontSize="9" fill={C.navy}
                    textAnchor="middle" fontWeight="800"
                    fontFamily="Barlow,system-ui,sans-serif">{b.v}%</text>
                )}
              </g>
            );
          })}

          {/* Ligne de tendance */}
          <polyline
            points={bars.map((b, i) => {
              const x = padL + i * (barW + gap) + barW / 2;
              const y = padT + (H - padB - padT) * (1 - b.v / maxV);
              return `${x},${y}`;
            }).join(" ")}
            fill="none" stroke={C.red} strokeWidth="1.5"
            strokeDasharray="4 3" strokeLinecap="round"/>

          {bars.map((b, i) => {
            const x = padL + i * (barW + gap) + barW / 2;
            const y = padT + (H - padB - padT) * (1 - b.v / maxV);
            return <circle key={b.y} cx={x} cy={y} r="3" fill={C.red}/>;
          })}
        </svg>
      </div>

      {/* Source */}
      <div style={{ fontSize:9.5, color:C.muted, letterSpacing:"0.3px" }}>
        Sources · CMF · FTUSA · CGA &nbsp;—&nbsp; Données 2019–2024
      </div>
    </div>
  );
}

/* ─── Module card ─── */
function ModuleCard({ mod }) {
  const [hov, setHov] = useState(false);
  const nav = useNavigate();
  const rgb = mod.color.slice(1).match(/../g).map(h=>parseInt(h,16)).join(",");
  return (
    <div onClick={() => nav(mod.to)}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        display:"flex", alignItems:"center", gap:12,
        padding:"12px 14px", borderRadius:10, cursor:"pointer",
        background: hov ? `rgba(${rgb},.05)` : C.card,
        border:`1.5px solid ${hov ? `rgba(${rgb},.35)` : C.border}`,
        transition:"all .18s cubic-bezier(.22,1,.36,1)",
        transform: hov ? "translateY(-1px)" : "none",
        boxShadow: hov ? `0 6px 20px rgba(${rgb},.12)` : "0 1px 3px rgba(12,27,46,.05)",
      }}>
      <div style={{ width:34, height:34, borderRadius:8, flexShrink:0,
        background: hov ? `rgba(${rgb},.12)` : `rgba(${rgb},.07)`,
        display:"flex", alignItems:"center", justifyContent:"center",
        color: mod.color, transition:"background .18s" }}>
        {mod.icon}
      </div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:12.5, fontWeight:700, color:C.navy,
          letterSpacing:"-0.2px", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
          {mod.label}
        </div>
        <div style={{ fontSize:10, color: hov ? mod.color : C.muted,
          marginTop:1, transition:"color .18s" }}>{mod.tag}</div>
      </div>
      <svg viewBox="0 0 10 10" fill="none" width="10" height="10"
        style={{ flexShrink:0, color: hov ? mod.color : C.border,
          transform: hov ? "translateX(2px)" : "none", transition:"all .18s" }}>
        <path d="M2 5h6M5 2l3 3-3 3" stroke="currentColor" strokeWidth="1.6"
          strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    </div>
  );
}

/* ─── Slides hero ─── */
const SLIDES = [
  {
    imgSrc: "/imagesFond/CGA.png",
    tag: "CGA · Réglementation",
    headline: "Le cadre réglementaire\ntunisien de l'assurance",
    body: "Le Conseil Général des Assurances supervise l'ensemble des acteurs. Circulaires, décisions de tutelle et textes législatifs structurant le marché assurantiel tunisien.",
    cta: "Voir la veille réglementaire",
    to: "/veille-reglementaire",
  },
  {
    /* CMF — Sidi Bou Said / Tunis méditerranéen */
    imgSrc: "/imagesFond/CMF.png",
    tag: "CMF · Marchés financiers",
    headline: "Performance & ratios\nau cœur de l'analyse",
    body: "La Commission du Marché Financier publie les données de performance des sociétés cotées. Ratios combinés, sinistralité et tendances de profitabilité sur 6 exercices.",
    cta: "Ouvrir l'analyse comparative",
    to: "/analyse-comparative",
  },
  {
    /* FTUSA — architecture Tunis moderne / médina */
    imgSrc: "/imagesFond/FTUSA.png",
    tag: "FTUSA · Secteur assurance",
    headline: "11 compagnies,\nune vision d'ensemble",
    body: "La Fédération Tunisienne des Sociétés d'Assurances regroupe tous les acteurs Vie & Non-Vie. Parts de marché, primes émises et résultats techniques sous un même tableau de bord.",
    cta: "Explorer l'aperçu marché",
    to: "/apercu-marche",
  },
  {
    /* BVMT — Tunis bâtiment avec drapeau / centre financier */
    imgSrc: "/imagesFond/BVMT.png",
    tag: "BVMT · Bourse & cotations",
    headline: "La valeur boursière\ndes assureurs tunisiens",
    body: "La Bourse des Valeurs Mobilières de Tunis révèle capitalisations et cours des compagnies cotées. Suivez STAR, Salim, Tunis Re et Carte en temps réel.",
    cta: "Consulter les fiches compagnies",
    to: "/fiches",
  },
  {
    /* STAR / COMAR — Tunis Les Berges du Lac / quartier affaires */
    imgSrc: "/imagesFond/STAR.png",
    tag: "STAR · Analyse compagnie",
    headline: "Décryptez chaque acteur\ndu marché en détail",
    body: "Fiches individuelles par compagnie : bilan, compte de résultat, ratio de solvabilité, sinistralité branche par branche. Benchmark précis pour vos décisions stratégiques.",
    cta: "Voir les fiches entreprises",
    to: "/fiches",
  },
  {
    imgSrc: "/imagesFond/LLOYD.png",
    tag: "Lloyd's · Réassurance",
    headline: "Réassurance & marchés\ninternationaux",
    body: "La place de Lloyd's et les grands réassureurs internationaux structurent la capacité et les conditions de souscription du marché tunisien. Un prisme indispensable à l'analyse sectorielle.",
    cta: "Explorer l'analyse comparative",
    to: "/analyse-comparative",
  },
];

/* ─── Cadre EY diagonal ─── */
function EYFrame({ width=720, height=240, strokeW=7, fill="#030810",
                   animated=true, erasing=false, glowSvg=false, showDots=true, children }) {
  const pts  = `0,${height} 0,${height*0.2} ${width},0 ${width},${height}`;
  const diag = Math.sqrt(width*width + (height*0.2)**2);
  const perim = Math.ceil(height + diag + height + width);
  const eraseid = `ef${perim}`;
  const strokeStyle =
    animated ? { animation:"drawFrame 2.2s cubic-bezier(.4,0,.2,1) .3s forwards" } :
    erasing  ? { animation:`${eraseid} 1.4s cubic-bezier(.4,0,1,1) forwards` } :
    {};
  return (
    <div style={{ position:"relative", width, height, flexShrink:0 }}>
      <svg width={width} height={height} style={{
        position:"absolute", inset:0, overflow:"visible",
        filter: glowSvg ? "drop-shadow(0 0 12px rgba(255,230,0,.5))" : "none",
      }}>
        {erasing && <style>{`@keyframes ${eraseid}{from{stroke-dashoffset:0}to{stroke-dashoffset:${perim}}}`}</style>}
        <polygon points={pts} fill={fill}/>
        <polygon points={pts} fill="none" stroke={C.yellow} strokeWidth={strokeW}
          strokeDasharray={perim} strokeDashoffset={animated ? perim : 0}
          style={strokeStyle}/>
      </svg>
      <div style={{ position:"absolute", inset:0 }}>{children}</div>
      {showDots && (
        <div style={{ position:"absolute", bottom:-48, left:0, display:"flex", gap:14 }}>
          {[1,.5,.2].map((o,j) => (
            <div key={j} style={{
              width:11, height:11, background:C.yellow, opacity:o,
              animation:`fadeSlide .4s ${2.0 + j*0.14}s ease both`,
              boxShadow: o===1 ? "0 0 8px rgba(255,230,0,.6)" : "none",
            }}/>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Brand EY navbar ─── */
function NavBrand({ onClick }) {
  return (
    <div onClick={onClick} style={{
      height:"100%", display:"flex", alignItems:"center",
      gap:0, flexShrink:0,
      cursor: onClick ? "pointer" : "default",
      borderRight:"1px solid rgba(255,255,255,.08)",
    }}>
      {/* Zone logo */}
      <div style={{
        height:"100%", display:"flex", alignItems:"center",
        padding:"0 18px 0 20px",
        borderRight:"1.5px solid rgba(255,230,0,.3)",
      }}>
        <img src="/imagesFond/LogoEY.png" alt="EY" style={{
          height:64, width:"auto", objectFit:"contain",
          filter:"none",
        }}/>
      </div>

      {/* Zone texte */}
      <div style={{ padding:"0 28px", lineHeight:1.38 }}>
        <div style={{
          fontSize:17, fontWeight:800, letterSpacing:"-0.5px",
          color:"white", whiteSpace:"nowrap",
        }}>
          Baromètre&nbsp;<span style={{ color:C.yellow }}>Assurance TN</span>
        </div>
        <div style={{
          fontSize:10, color:"rgba(255,255,255,.36)",
          letterSpacing:"2.5px", textTransform:"uppercase",
          whiteSpace:"nowrap", marginTop:3,
        }}>
          Intelligence marché · Tunisie
        </div>
      </div>
    </div>
  );
}

/* ─── Page Accueil ─── */
function Accueil() {
  const nav = useNavigate();
  const [phase, setPhase]               = useState("intro");
  const [introFading, setIntroFading]   = useState(false);
  const [slide, setSlide]               = useState(0);
  const [slideVisible, setSlideVisible] = useState(true);
  const [hovMod, setHovMod]             = useState(null);

  /* intro → disparition fluide → hero */
  useEffect(() => {
    const t1 = setTimeout(() => setIntroFading(true), 3000);
    const t2 = setTimeout(() => setPhase("hero"),     3480);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  /* Défilement slides toutes les 7s */
  useEffect(() => {
    if (phase !== "hero") return;
    const iv = setInterval(() => {
      setSlideVisible(false);
      setTimeout(() => { setSlide(s => (s+1) % SLIDES.length); setSlideVisible(true); }, 750);
    }, 7000);
    return () => clearInterval(iv);
  }, [phase]);

  const S = SLIDES[slide];

  /* ══ HERO — image plein écran immersive, texte sur gradient ══ */
  return (
    <div style={{
      width:"100vw", height:"100vh", position:"relative",
      fontFamily:"Barlow,system-ui,sans-serif", overflow:"hidden",
      background:"#030810",
    }}>

      {/* ── IMAGE — réduite, visible en totalité, côté droit ── */}
      <div key={`bg-${slide}`} style={{
        position:"absolute", inset:0,
        backgroundImage:`url('${S.imgSrc}')`,
        backgroundSize:"100% 100%",
        animation:"kenBurns 16s ease-in-out forwards",
        opacity: slideVisible ? 1 : 0,
        transition:"opacity 1.2s ease",
      }}/>

      {/* Gradient gauche → droit : sombre pour lire le texte, transparent pour voir l'image */}
      <div style={{
        position:"absolute", inset:0, zIndex:1,
        background:`linear-gradient(
          to right,
          rgba(3,8,16,.97) 0%,
          rgba(3,8,16,.90) 22%,
          rgba(3,8,16,.68) 38%,
          rgba(3,8,16,.28) 52%,
          rgba(3,8,16,.06) 65%,
          transparent 78%
        )`,
      }}/>

      {/* Gradient haut → bas : légère vignette pour la navbar */}
      <div style={{
        position:"absolute", inset:0, zIndex:1,
        background:"linear-gradient(to bottom, rgba(3,8,16,.45) 0%, transparent 18%, transparent 80%, rgba(3,8,16,.5) 100%)",
        pointerEvents:"none",
      }}/>

      {/* Accent vertical jaune — signature EY discrète */}
      <div style={{
        position:"absolute", top:"20%", bottom:"20%", left:"41%",
        width:1.5, background:`linear-gradient(to bottom, transparent, ${C.yellow}, transparent)`,
        opacity:.35, zIndex:3, pointerEvents:"none",
      }}/>

      {/* ══ NAVBAR ══ */}
      <nav style={{
        position:"absolute", top:0, left:0, right:0, zIndex:20,
        display:"flex", alignItems:"center",
        height:72, background:"#2E2E38",
        animation:"navDown .65s cubic-bezier(.22,1,.36,1) both",
      }}>
        <NavBrand/>

        <div style={{ display:"flex", alignItems:"center", flex:1, height:"100%" }}>
          {MODULES.map((m, i) => {
            const isH = hovMod === i;
            return (
              <button key={m.to} onClick={() => nav(m.to)}
                onMouseEnter={() => setHovMod(i)} onMouseLeave={() => setHovMod(null)}
                style={{
                  background:"none", border:"none", cursor:"pointer",
                  padding:"0 14px", height:"100%",
                  display:"flex", alignItems:"center",
                  fontSize:12.5, fontWeight: isH ? 500 : 400,
                  color: isH ? "white" : "rgba(255,255,255,.68)",
                  borderBottom:`3px solid ${isH ? C.yellow : "transparent"}`,
                  borderTop:"3px solid transparent",
                  transition:"color .18s, border-color .18s",
                  whiteSpace:"nowrap",
                }}>
                {m.label}
              </button>
            );
          })}
        </div>

        <div style={{ display:"flex", alignItems:"center", height:"100%",
          flexShrink:0, borderLeft:"1px solid rgba(255,255,255,.1)" }}>
          <div style={{ display:"flex", alignItems:"center", gap:6, padding:"0 18px",
            height:"100%", cursor:"pointer" }}>
            <svg viewBox="0 0 18 18" fill="none" width="13" height="13">
              <circle cx="9" cy="9" r="7.5" stroke="rgba(255,255,255,.6)" strokeWidth="1.3"/>
              <ellipse cx="9" cy="9" rx="3.2" ry="7.5" stroke="rgba(255,255,255,.6)" strokeWidth="1.3"/>
              <path d="M1.5 9h15" stroke="rgba(255,255,255,.6)" strokeWidth="1.3"/>
            </svg>
            <span style={{ fontSize:12, color:"rgba(255,255,255,.6)" }}>Tunisie</span>
          </div>
        </div>
      </nav>

      {/* ══ CADRE EY HERO — contenu slide dans le parallélogramme ══ */}
      <div style={{
        position:"absolute", left:52, zIndex:4,
        top:"50%", transform:"translateY(calc(-50% - 40px))",
      }}>
        <EYFrame width={560} height={366} strokeW={4} fill="none" glowSvg={false} animated={false} showDots={false}>
          <div key={slide} style={{
            position:"absolute", inset:0,
            opacity: slideVisible ? 1 : 0,
            transition:"opacity .5s ease",
            padding:"88px 34px 36px 68px",
            display:"flex", flexDirection:"column", justifyContent:"flex-start", gap:0,
            overflow:"hidden",
          }}>

            {/* Tag */}
            <div style={{ display:"inline-flex", alignItems:"center", gap:9, marginBottom:13,
              animation:"slideUp .5s ease both" }}>
              <div style={{ width:16, height:2, background:C.yellow, flexShrink:0 }}/>
              <span style={{ fontSize:8, fontWeight:700, letterSpacing:"2.8px",
                color:C.yellow, textTransform:"uppercase" }}>
                {S.tag}
              </span>
            </div>

            {/* Titre */}
            <h1 style={{
              margin:"0 0 14px", fontWeight:200,
              fontSize:"clamp(20px,2.2vw,34px)",
              color:"white", lineHeight:1.12, letterSpacing:"-0.5px",
              whiteSpace:"pre-line",
              animation:"slideUp .6s .08s ease both",
            }}>
              {S.headline}
            </h1>

            {/* Trait */}
            <div style={{ width:36, height:1, background:"rgba(255,255,255,.15)",
              marginBottom:12, animation:"slideUp .4s .14s ease both" }}/>

            {/* Corps */}
            <p style={{
              margin:"0 0 22px", fontSize:11.5,
              color:"rgba(255,255,255,.48)", lineHeight:1.65,
              animation:"slideUp .6s .2s ease both",
            }}>
              {S.body}
            </p>

            {/* CTA */}
            <button onClick={() => nav(S.to)}
              onMouseEnter={e => e.currentTarget.style.background="#fff"}
              onMouseLeave={e => e.currentTarget.style.background=C.yellow}
              style={{
                display:"inline-flex", alignItems:"center", gap:9,
                background:C.yellow, border:"none", cursor:"pointer",
                padding:"10px 22px", alignSelf:"flex-start",
                fontSize:9, fontWeight:700, color:"#2E2E38",
                letterSpacing:"1.1px", textTransform:"uppercase",
                transition:"background .2s",
                animation:"slideUp .5s .28s ease both",
              }}>
              {S.cta}
              <svg viewBox="0 0 14 10" fill="none" width="10" height="10">
                <path d="M1 5h12M8 1l5 4-5 4" stroke="currentColor"
                  strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </EYFrame>
      </div>

      {/* Indicateurs slides */}
      <div style={{
        position:"absolute", bottom:32, left:72, zIndex:5,
        display:"flex", alignItems:"center", gap:8,
      }}>
        {SLIDES.map((_,i) => (
          <div key={i} onClick={() => { setSlide(i); setSlideVisible(true); }}
            style={{
              height:2, width: i===slide ? 28 : 7,
              background: i===slide ? C.yellow : "rgba(255,255,255,.18)",
              cursor:"pointer",
              transition:"width .4s cubic-bezier(.22,1,.36,1), background .4s",
            }}/>
        ))}
        <span style={{ marginLeft:10, fontSize:9.5, letterSpacing:"1.5px",
          color:"rgba(255,255,255,.2)", fontVariantNumeric:"tabular-nums" }}>
          {String(slide+1).padStart(2,"0")}&thinsp;/&thinsp;{String(SLIDES.length).padStart(2,"0")}
        </span>
      </div>

      {/* Barre de progression */}
      <div key={`prog-${slide}`} style={{
        position:"absolute", bottom:0, left:0, right:0, height:2,
        background:C.yellow, zIndex:6, transformOrigin:"left",
        animation:"progressGrow 7s linear forwards",
      }}/>

      <style>{`
        @keyframes kenBurns {
          from { transform:scale(1) translate(0,0); }
          to   { transform:scale(1.08) translate(-1.5%,-1%); }
        }
        @keyframes slideUp {
          from { opacity:0; transform:translateY(18px); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes navDown {
          from { opacity:0; transform:translateY(-100%); }
          to   { opacity:1; transform:translateY(0); }
        }
        @keyframes progressGrow {
          from { transform:scaleX(0); }
          to   { transform:scaleX(1); }
        }
      `}</style>

      {/* ══ INTRO OVERLAY — par-dessus le hero, disparaît en fondu ══ */}
      {phase === "intro" && (
        <div style={{
          position:"fixed", inset:0, zIndex:200,
          fontFamily:"Barlow,system-ui,sans-serif",
          background:"#1e2028",
          display:"flex", flexDirection:"column",
          alignItems:"center", justifyContent:"center", gap:0,
          pointerEvents:"none",
          opacity: introFading ? 0 : 1,
          filter: introFading ? "blur(6px)" : "none",
          transition: introFading ? "opacity .42s ease-in, filter .42s ease-in" : "none",
        }}>

          {/* Grille de fond subtile */}
          <div style={{
            position:"absolute", inset:0, pointerEvents:"none",
            backgroundImage:`linear-gradient(rgba(255,230,0,.03) 1px, transparent 1px),
                             linear-gradient(90deg, rgba(255,230,0,.03) 1px, transparent 1px)`,
            backgroundSize:"48px 48px",
          }}/>

          {/* Halo jaune derrière la carte */}
          <div style={{
            position:"absolute", width:320, height:220, borderRadius:"50%",
            background:"rgba(255,230,0,.05)", filter:"blur(48px)", pointerEvents:"none",
          }}/>

          {/* Barre jaune en haut */}
          <div style={{
            position:"absolute", top:0, left:0, right:0, height:3,
            background:C.yellow,
            animation:"lineIn .5s ease both",
          }}/>

          {/* Barre jaune en bas */}
          <div style={{
            position:"absolute", bottom:0, left:0, right:0, height:1,
            background:`linear-gradient(90deg,transparent,rgba(255,230,0,.25),transparent)`,
          }}/>

          {/* Wrapper centré */}
          <div style={{ position:"relative", zIndex:1, display:"flex", flexDirection:"column", alignItems:"center", gap:26 }}>

            {/* Card logo EY */}
            <div style={{
              position:"relative",
              width:210, height:128, flexShrink:0,
              animation:"cardIn .55s cubic-bezier(.22,1,.36,1) .15s both",
            }}>
              <svg width={210} height={128} style={{ position:"absolute", inset:0, overflow:"visible" }}>
                <defs>
                  <linearGradient id="ig" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#26283a"/>
                    <stop offset="100%" stopColor="#0f1118"/>
                  </linearGradient>
                  <filter id="yglow">
                    <feGaussianBlur stdDeviation="3" result="blur"/>
                    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                  </filter>
                </defs>
                <polygon points={`0,128 0,${128*0.18} 210,0 210,128`} fill="url(#ig)"/>
                <polygon points={`0,128 0,${128*0.18} 210,0 210,128`}
                  fill="none" stroke={C.yellow} strokeWidth={2} filter="url(#yglow)"
                  strokeDasharray="6 3" strokeDashoffset="0"/>
              </svg>
              <div style={{
                position:"absolute", inset:0,
                display:"flex", alignItems:"center", justifyContent:"center",
                paddingLeft:22,
              }}>
                <img src="/imagesFond/LogoEY.png" alt="EY" style={{
                  height:76, width:"auto", objectFit:"contain",
                }}/>
              </div>
            </div>

            {/* Séparateur */}
            <div style={{
              display:"flex", alignItems:"center", gap:12,
              animation:"titleIn .4s ease .5s both",
            }}>
              <div style={{ width:28, height:1, background:`rgba(255,230,0,.35)` }}/>
              <div style={{ width:5, height:5, background:C.yellow, transform:"rotate(45deg)" }}/>
              <div style={{ width:28, height:1, background:`rgba(255,230,0,.35)` }}/>
            </div>

            {/* Titre + sous-titre */}
            <div style={{
              textAlign:"center",
              animation:"titleIn .5s cubic-bezier(.22,1,.36,1) .38s both",
            }}>
              <div style={{
                fontSize:"clamp(20px,2vw,26px)", fontWeight:300,
                color:"rgba(255,255,255,.88)", letterSpacing:"0.3px", lineHeight:1.3,
              }}>
                Baromètre&nbsp;<span style={{ fontWeight:700, color:C.yellow }}>Assurance TN</span>
              </div>
              <div style={{
                marginTop:10, fontSize:9, fontWeight:500,
                color:"rgba(255,255,255,.25)", letterSpacing:"5px",
                textTransform:"uppercase",
                animation:"titleIn .4s ease .58s both",
              }}>
                Intelligence marché · Tunisie
              </div>
            </div>
          </div>

          <style>{`
            @keyframes cardIn  { from{opacity:0;transform:translateY(10px) scale(.96)} to{opacity:1;transform:translateY(0) scale(1)} }
            @keyframes titleIn { from{opacity:0;transform:translateY(7px)} to{opacity:1;transform:translateY(0)} }
            @keyframes lineIn  { from{transform:scaleX(0)} to{transform:scaleX(1)} }
          `}</style>
        </div>
      )}
    </div>
  );
}

/* ─── Navbar partagée (toutes les pages hors Accueil) ─── */
function AppNavbar() {
  const nav  = useNavigate();
  const loc  = useLocation();
  const [hov, setHov] = useState(null);
  return (
    <nav style={{
      position:"fixed", top:0, left:0, right:0, zIndex:100,
      display:"flex", alignItems:"center",
      height:92, background:"#2E2E38",
      boxShadow:"0 1px 0 rgba(255,255,255,.07)",
      fontFamily:"Barlow,system-ui,sans-serif",
    }}>
      <NavBrand onClick={() => nav("/accueil")}/>

      {/* Modules */}
      <div style={{ display:"flex", alignItems:"center", flex:1, height:"100%" }}>
        {MODULES.map((m, i) => {
          const isActive = loc.pathname === m.to;
          const isH = hov === i;
          return (
            <button key={m.to} onClick={() => nav(m.to)}
              onMouseEnter={() => setHov(i)} onMouseLeave={() => setHov(null)}
              style={{
                background:"none", border:"none", cursor:"pointer",
                padding:"0 14px", height:"100%",
                display:"flex", alignItems:"center",
                fontSize:14,
                fontWeight: isActive || isH ? 600 : 400,
                color: isActive ? C.yellow : isH ? "white" : "rgba(255,255,255,.65)",
                borderBottom:`3px solid ${isActive ? C.yellow : isH ? "rgba(255,255,255,.3)" : "transparent"}`,
                borderTop:"3px solid transparent",
                transition:"all .15s",
                whiteSpace:"nowrap",
              }}>
              {m.label}
            </button>
          );
        })}
      </div>

      {/* Droite */}
      <div style={{ display:"flex", alignItems:"center", height:"100%",
        flexShrink:0, borderLeft:"1px solid rgba(255,255,255,.1)" }}>
        <div style={{ display:"flex", alignItems:"center", gap:6, padding:"0 18px",
          height:"100%", cursor:"pointer" }}>
          <svg viewBox="0 0 18 18" fill="none" width="13" height="13">
            <circle cx="9" cy="9" r="7.5" stroke="rgba(255,255,255,.6)" strokeWidth="1.3"/>
            <ellipse cx="9" cy="9" rx="3.2" ry="7.5" stroke="rgba(255,255,255,.6)" strokeWidth="1.3"/>
            <path d="M1.5 9h15" stroke="rgba(255,255,255,.6)" strokeWidth="1.3"/>
          </svg>
          <span style={{ fontSize:12, color:"rgba(255,255,255,.6)" }}>Tunisie</span>
        </div>
      </div>
    </nav>
  );
}

/* ─── Transition de page ─── */
function PageTransition({ children }) {
  const loc = useLocation();
  return (
    <div key={loc.pathname} style={{
      animation:"pageEnter .38s cubic-bezier(.22,1,.36,1) both",
      flex:1, display:"flex", flexDirection:"column",
      minHeight:"calc(100vh - 92px)",
    }}>
      {children}
    </div>
  );
}

/* ─── Shell ─── */
function AppShell() {
  const location = useLocation();

  if (location.pathname === "/accueil" || location.pathname === "/") {
    return (
      <Routes>
        <Route path="/"        element={<Navigate to="/accueil" replace/>}/>
        <Route path="/accueil" element={<Accueil/>}/>
      </Routes>
    );
  }

  return (
    <div style={{ height:"100vh", width:"100%", fontFamily:"Barlow,system-ui,sans-serif",
      display:"flex", flexDirection:"column" }}>
      <AppNavbar/>
      <main style={{
        marginTop:92, flex:1, overflowY:"auto",
        background:"#F2F5FB",
        display:"flex", flexDirection:"column",
      }}>
        <style>{`
          @keyframes pageEnter {
            from { opacity:0; transform:translateY(10px); }
            to   { opacity:1; transform:translateY(0); }
          }
          * { scroll-behavior:smooth; }
        `}</style>
        <PageTransition>
          <Routes>
            <Route path="/apercu-marche"         element={<ApercuMarche/>}/>
            <Route path="/positionnement"        element={<Positionnement/>}/>
            <Route path="/geographie"            element={<Geographie/>}/>
            <Route path="/fiches"                element={<FichesEntreprises/>}/>
            <Route path="/analyse-comparative"   element={<AnalyseComparative/>}/>
            <Route path="/enquete-marche"        element={<EnqueteMarche/>}/>
            <Route path="/veille-reglementaire"  element={<VeilleReglementaire/>}/>
            <Route path="/actualites-seminaires" element={<ActualitesSeminaires/>}/>
          </Routes>
        </PageTransition>
      </main>
      <Chatbot/>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell/>
    </BrowserRouter>
  );
}
