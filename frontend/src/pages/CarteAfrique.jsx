import React, { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate, NavLink, useLocation } from "react-router-dom";
import africaSVGRaw from "../../public/images/africa.svg?raw";

const Y        = "#FFE600";
const TEXT     = "#1E2A3B";
const TEXT_MED = "#6B7A8D";

const FRANCO_COLORS = {
  TN: "#E53E3E",
  DZ: "#22C55E",
  LY: "#059669",
  MR: "#C9A227",
  SN: "#10B981",
  CI: "#F97316",
  CM: "#A855F7",
  CD: "#3B82F6",
  MG: "#EC4899",
  ML: "#FACC15",
  BF: "#6366F1",
};

const FRANCO_META = {
  TN: { cx:418, cy:82,  label:"Tunisie"       },
  DZ: { cx:342, cy:162, label:"Algérie"        },
  LY: { cx:540, cy:140, label:"Libye"          },
  MR: { cx:165, cy:227, label:"Mauritanie"     },
  SN: { cx:120, cy:317, label:"Sénégal"        },
  ML: { cx:295, cy:284, label:"Mali"           },
  BF: { cx:280, cy:360, label:"Burkina Faso"   },
  CI: { cx:238, cy:424, label:"Côte d'Ivoire"  },
  CM: { cx:460, cy:418, label:"Cameroun"       },
  CD: { cx:578, cy:556, label:"RD Congo"       },
  MG: { cx:862, cy:794, label:"Madagascar"     },
};

const PAYS = [
  { id:"TN", nom:"Tunisie",        flagImg:"/logos/tn-flag.png",     actif:true,  kpi:"11 compagnies · RC moy. 87.4%", target:"/analyse-comparative" },
  { id:"DZ", nom:"Algérie",        flagImg:"/logos/Algerie.png",     actif:false },
  { id:"LY", nom:"Libye",          flagImg:"/logos/Libye.jpg",       actif:false },
  { id:"MR", nom:"Mauritanie",     flagImg:"/logos/Mauritanie.png",  actif:false },
  { id:"SN", nom:"Sénégal",        flagImg:"/logos/Senegal.png",     actif:false },
  { id:"CI", nom:"Côte d'Ivoire",  flagImg:"/logos/CodeIvoire.png",  actif:false },
  { id:"CM", nom:"Cameroun",       flagImg:"/logos/Cameroun.png",    actif:false },
  { id:"CD", nom:"RD Congo",       flagImg:"/logos/Congo.png",       actif:false },
  { id:"MG", nom:"Madagascar",     flagImg:"/logos/Madagascar.png",  actif:false },
  { id:"ML", nom:"Mali",           flagImg:"/logos/Mali.png",        actif:false },
  { id:"BF", nom:"Burkina Faso",   flagImg:"/logos/BurkinaFaso.png", actif:false },
];

function hexToRgb(h) {
  return `${parseInt(h.slice(1,3),16)},${parseInt(h.slice(3,5),16)},${parseInt(h.slice(5,7),16)}`;
}

/* ══ Logo ══ */
function FSLogo({ size=32 }) {
  return (
    <div style={{ width:size, height:size, borderRadius:Math.round(size*.22),
      background:Y, flexShrink:0, display:"flex", alignItems:"center", justifyContent:"center" }}>
      <svg width={size*.58} height={size*.58} viewBox="0 0 24 24" fill="none">
        <rect x="2" y="15" width="4" height="7" rx="1" fill="#2E2E38"/>
        <rect x="8" y="10" width="4" height="12" rx="1" fill="#2E2E38"/>
        <rect x="14" y="5" width="4" height="17" rx="1" fill="#2E2E38"/>
        <polyline points="4,15 10,10 16,5" stroke="#2E2E38" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="4" cy="15" r="1.3" fill="#2E2E38"/>
        <circle cx="10" cy="10" r="1.3" fill="#2E2E38"/>
        <circle cx="16" cy="5"  r="1.3" fill="#2E2E38"/>
      </svg>
    </div>
  );
}

/* ══ Topbar dark ══ */
function Topbar({ onBack, onContinent }) {
  return (
    <div style={{ flexShrink:0, height:54, background:"#FFFFFF",
      borderBottom:`1px solid #E8EDF4`,
      display:"flex", alignItems:"center", justifyContent:"space-between",
      padding:"0 20px", zIndex:30, boxShadow:"0 1px 8px rgba(0,0,0,.06)" }}>

      {/* Left */}
      <div style={{ display:"flex", alignItems:"center", gap:10 }}>
        <button onClick={onBack}
          style={{ display:"flex", alignItems:"center", gap:5, background:"#F4F6FA",
            border:"1px solid #E0E6EF", cursor:"pointer", color:"#6B7A8D",
            fontSize:11, fontWeight:600, padding:"5px 11px", borderRadius:7,
            transition:"all .15s", fontFamily:"inherit" }}
          onMouseEnter={e=>{e.currentTarget.style.background="#E8EDF4";e.currentTarget.style.color="#1E2A3B";}}
          onMouseLeave={e=>{e.currentTarget.style.background="#F4F6FA";e.currentTarget.style.color="#6B7A8D";}}>
          <svg viewBox="0 0 12 12" fill="none" width="9" height="9">
            <path d="M8 2L3 6l5 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Accueil
        </button>
        <div style={{ width:1, height:18, background:"rgba(0,0,0,.1)" }}/>
        <FSLogo size={28}/>
        <span style={{ fontSize:11.5, fontWeight:900, letterSpacing:"1.6px", color:"#1E2A3B" }}>FS MARKET</span>
        <span style={{ fontSize:11.5, fontWeight:900, letterSpacing:"1.6px", color:"#C89200" }}>INTELLIGENCE</span>
        <div style={{ width:1, height:18, background:"rgba(0,0,0,.1)" }}/>
        <span style={{ fontSize:10.5, color:"#9AA5B4", fontWeight:500 }}>Sélection de marché</span>
      </div>

      {/* Right */}
      <div style={{ display:"flex", alignItems:"center", gap:10 }}>
        <div style={{ display:"flex", alignItems:"center", gap:6, padding:"4px 12px",
          borderRadius:20, background:"rgba(229,62,62,.18)", border:"1px solid rgba(229,62,62,.35)",
          fontSize:10.5, fontWeight:600, color:"#FC8181" }}>
          <span style={{ width:5, height:5, borderRadius:"50%", background:"#E53E3E",
            display:"inline-block", animation:"caPulse 2s ease-in-out infinite" }}/>
          Tunisie · Actif
        </div>
        <button onClick={onContinent}
          style={{ display:"flex", alignItems:"center", gap:7, padding:"6px 14px",
            background:Y, border:"none", borderRadius:8, cursor:"pointer",
            fontSize:11, fontWeight:700, color:"#1E2A3B", transition:"all .18s", fontFamily:"inherit",
            boxShadow:"0 2px 10px rgba(255,230,0,.35)" }}
          onMouseEnter={e=>{e.currentTarget.style.boxShadow="0 4px 18px rgba(255,230,0,.5)";e.currentTarget.style.transform="translateY(-1px)";}}
          onMouseLeave={e=>{e.currentTarget.style.boxShadow="0 2px 10px rgba(255,230,0,.35)";e.currentTarget.style.transform="none";}}>
          <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
            <circle cx="8" cy="8" r="5.5" stroke="#1E2A3B" strokeWidth="1.4"/>
            <ellipse cx="8" cy="8" rx="5.5" ry="2.3" stroke="#1E2A3B" strokeWidth="1.4"/>
            <line x1="8" y1="2.5" x2="8" y2="13.5" stroke="#1E2A3B" strokeWidth="1.2"/>
          </svg>
          Vue continentale
        </button>
      </div>
    </div>
  );
}

/* ══ Carte SVG + 3D ══ */
function AfricaMapSVG({ pays, onNavigate }) {
  const outerRef = useRef(null);
  const svgRef   = useRef(null);
  const dragRef  = useRef(null);
  const [tooltip,  setTooltip]  = useState(null);
  const [zoom,     setZoom]     = useState({ s:1, x:0, y:0 });
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const container = svgRef.current;
    if (!container) return;

    const div = document.createElement("div");
    div.innerHTML = africaSVGRaw;
    const svgEl = div.querySelector("svg");
    if (!svgEl) return;
    svgEl.setAttribute("width","100%");
    svgEl.setAttribute("height","auto");
    svgEl.style.display = "block";
    svgEl.style.overflow = "visible";

    const ns = "http://www.w3.org/2000/svg";
    const francoSet = new Set(pays.map(p => p.id));

    /* ── 1. Couleurs de base (attributs) ── */
    svgEl.querySelectorAll("path").forEach(path => {
      const id = path.getAttribute("id") || "";
      if (francoSet.has(id)) {
        const p   = pays.find(x => x.id === id);
        const col = FRANCO_COLORS[id];
        /* style.fill prioritaire sur tout CSS existant du SVG */
        path.style.fill        = col;
        path.style.stroke      = "rgba(0,0,0,0.55)";
        path.style.strokeWidth = p?.actif ? "2.5" : "1.8";
      } else {
        path.style.fill        = "#C8D4E3";
        path.style.stroke      = "rgba(10,15,40,0.75)";
        path.style.strokeWidth = "1.4";
      }
    });

    /* ── 2. CSS hover ── */
    let css = `
      path { transition: filter .22s; }
      .fl-ov { transition: opacity .22s; }
    `;
    pays.forEach(p => {
      const c   = FRANCO_COLORS[p.id];
      const rgb = hexToRgb(c);
      /* Lueur de base sur chaque pays francophone */
      css += `path#${p.id}{cursor:pointer;filter:drop-shadow(0 0 8px rgba(${rgb},.45)) drop-shadow(0 2px 4px rgba(${rgb},.3));}`;
      if (p.actif) {
        css += `path#${p.id}:hover{filter:brightness(1.18) drop-shadow(0 0 18px rgba(${rgb},.75)) drop-shadow(0 4px 12px rgba(${rgb},.5));stroke-width:3.5!important;}`;
      } else {
        css += `path#${p.id}:hover{filter:brightness(1.25) drop-shadow(0 0 16px rgba(${rgb},.7)) drop-shadow(0 4px 12px rgba(${rgb},.45));stroke-width:3!important;}`;
      }
    });
    css += `
      .mpring{animation:mpulse 2s ease-out infinite;transform-box:fill-box;transform-origin:center;}
      @keyframes mpulse{0%{transform:scale(1);opacity:.5}100%{transform:scale(2.4);opacity:0}}
    `;
    const styleEl = document.createElementNS(ns,"style");
    styleEl.textContent = css;
    svgEl.prepend(styleEl);

    /* ── 3. Insérer le SVG maintenant (getBBox a besoin du DOM) ── */
    container.innerHTML = "";
    container.appendChild(svgEl);

    /* ── 4. Overlays drapeau (clipPath vers la forme du pays) ── */
    const defs     = document.createElementNS(ns,"defs");
    const flagGrp  = document.createElementNS(ns,"g");
    const flagImgs = {};

    pays.forEach(p => {
      const pathEl = svgEl.querySelector(`path[id="${p.id}"]`);
      if (!pathEl) return;
      try {
        const d    = pathEl.getAttribute("d");
        const bbox = pathEl.getBBox();
        if (!bbox || bbox.width < 5) return;

        /* ClipPath = forme du pays */
        const cp = document.createElementNS(ns,"clipPath");
        cp.setAttribute("id",`fcl-${p.id}`);
        const cs = document.createElementNS(ns,"path");
        cs.setAttribute("d",d);
        cp.appendChild(cs);
        defs.appendChild(cp);

        /* Image drapeau */
        const img = document.createElementNS(ns,"image");
        img.setAttribute("href", p.flagImg);
        img.setAttribute("x",    String(bbox.x));
        img.setAttribute("y",    String(bbox.y));
        img.setAttribute("width", String(bbox.width));
        img.setAttribute("height",String(bbox.height));
        img.setAttribute("preserveAspectRatio","xMidYMid slice");
        img.setAttribute("clip-path",`url(#fcl-${p.id})`);
        img.setAttribute("opacity","0.78");
        img.setAttribute("class","fl-ov");
        img.style.pointerEvents = "none";
        flagGrp.appendChild(img);
        flagImgs[p.id] = img;
      } catch(_) { /* getBBox peut échouer */ }
    });

    const afterStyle = styleEl.nextSibling;
    svgEl.insertBefore(defs, afterStyle);
    svgEl.appendChild(flagGrp);

    /* ── 5. Marqueurs + labels cachés ── */
    const mg = document.createElementNS(ns,"g");
    const labelGrp = {};

    pays.forEach(p => {
      const meta = FRANCO_META[p.id]; if (!meta) return;
      const c   = FRANCO_COLORS[p.id];
      const rgb = hexToRgb(c);
      const g   = document.createElementNS(ns,"g");
      g.setAttribute("transform",`translate(${meta.cx},${meta.cy})`);

      if (p.actif) {
        g.setAttribute("data-id",p.id);
        g.style.cursor = "pointer";

        const ring = document.createElementNS(ns,"circle");
        ring.setAttribute("r","20"); ring.setAttribute("fill",c);
        ring.setAttribute("fill-opacity","0.18"); ring.setAttribute("class","mpring");

        const bg = document.createElementNS(ns,"circle");
        bg.setAttribute("r","12"); bg.setAttribute("fill",`rgba(${rgb},.15)`);

        const dot = document.createElementNS(ns,"circle");
        dot.setAttribute("r","9"); dot.setAttribute("fill",c);
        dot.setAttribute("stroke","white"); dot.setAttribute("stroke-width","3");
        dot.setAttribute("filter",`drop-shadow(0 2px 6px rgba(${rgb},.5))`);

        g.append(ring, bg, dot);
        g.addEventListener("click",()=>onNavigate(p.target));
      } else {
        const outer = document.createElementNS(ns,"circle");
        outer.setAttribute("r","6"); outer.setAttribute("fill","white");
        outer.setAttribute("fill-opacity","0.92");
        outer.setAttribute("filter",`drop-shadow(0 1px 5px rgba(0,0,0,.35))`);
        const inner = document.createElementNS(ns,"circle");
        inner.setAttribute("r","4"); inner.setAttribute("fill",c);
        g.append(outer, inner);
      }

      /* Étiquette cachée par défaut — visible au hover */
      const lw = meta.label.length * 7.8 + 32;
      const lg = document.createElementNS(ns,"g");
      lg.style.opacity = "0";
      lg.style.transition = "opacity .18s";
      lg.style.pointerEvents = "none";

      const lbg = document.createElementNS(ns,"rect");
      lbg.setAttribute("x",String(-lw/2)); lbg.setAttribute("y","-52");
      lbg.setAttribute("width",String(lw)); lbg.setAttribute("height","26");
      lbg.setAttribute("rx","8"); lbg.setAttribute("fill","#1E2A3B");
      lbg.setAttribute("stroke",c); lbg.setAttribute("stroke-width","2");
      lbg.setAttribute("filter","drop-shadow(0 4px 16px rgba(0,0,0,.35))");

      const ltxt = document.createElementNS(ns,"text");
      ltxt.setAttribute("y","-33"); ltxt.setAttribute("text-anchor","middle");
      ltxt.setAttribute("fill","#FFFFFF"); ltxt.setAttribute("font-size","13.5");
      ltxt.setAttribute("font-weight","800");
      ltxt.setAttribute("font-family","Inter,system-ui,sans-serif");
      ltxt.setAttribute("letter-spacing","0.3");
      ltxt.textContent = meta.label;

      lg.append(lbg, ltxt);
      g.appendChild(lg);
      labelGrp[p.id] = lg;

      mg.appendChild(g);
    });
    svgEl.appendChild(mg);

    /* ── 6. Listeners hover/click ── */
    svgEl.querySelectorAll("path").forEach(path => {
      const id = path.getAttribute("id")||"";
      const p  = pays.find(x=>x.id===id);
      if (!p) return;
      path.addEventListener("mouseenter", e => {
        if (flagImgs[id]) flagImgs[id].setAttribute("opacity","1");
        if (labelGrp[id]) labelGrp[id].style.opacity = "1";
        setTooltip({pays:p, x:e.clientX, y:e.clientY});
      });
      path.addEventListener("mousemove", e =>
        setTooltip(t => t ? {...t, x:e.clientX, y:e.clientY} : null)
      );
      path.addEventListener("mouseleave",()=>{
        if (flagImgs[id]) flagImgs[id].setAttribute("opacity","0.78");
        if (labelGrp[id]) labelGrp[id].style.opacity = "0";
        setTooltip(null);
      });
      if (p.actif && p.target) path.addEventListener("click",()=>onNavigate(p.target));
    });
  }, [pays]);

  const clamp = useCallback((s,x,y)=>{
    const el=outerRef.current; if(!el||s<=1) return {s,x:0,y:0};
    const {width:w,height:h}=el.getBoundingClientRect();
    return {s,x:Math.min(0,Math.max(w*(1-s),x)),y:Math.min(0,Math.max(h*(1-s),y))};
  },[]);

  useEffect(()=>{
    const el=outerRef.current; if(!el) return;
    const fn=e=>{
      e.preventDefault();
      const f=e.deltaY<0?1.22:1/1.22;
      const rc=el.getBoundingClientRect();
      setZoom(z=>{
        const ns2=Math.max(1,Math.min(7,z.s*f));
        if(ns2===1) return {s:1,x:0,y:0};
        const mx=e.clientX-rc.left,my=e.clientY-rc.top;
        return clamp(ns2,mx-(mx-z.x)*(ns2/z.s),my-(my-z.y)*(ns2/z.s));
      });
    };
    el.addEventListener("wheel",fn,{passive:false});
    return()=>el.removeEventListener("wheel",fn);
  },[clamp]);

  const onMD=e=>{if(zoom.s<=1)return;dragRef.current={sx:e.clientX-zoom.x,sy:e.clientY-zoom.y};setDragging(true);};
  const onMM=e=>{if(!dragRef.current)return;setZoom(z=>clamp(z.s,e.clientX-dragRef.current.sx,e.clientY-dragRef.current.sy));};
  const onMU=()=>{dragRef.current=null;setDragging(false);};

  const zBtn=(action,lbl)=>(
    <button onClick={action}
      style={{width:30,height:30,borderRadius:7,border:"1px solid rgba(255,255,255,.14)",
        background:"rgba(255,255,255,.08)",display:"flex",alignItems:"center",justifyContent:"center",
        fontSize:lbl==="⊙"?13:18,fontWeight:300,color:"rgba(255,255,255,.65)",
        cursor:"pointer",fontFamily:"system-ui",lineHeight:1,
        boxShadow:"0 2px 8px rgba(0,0,0,.3)"}}
      onMouseEnter={e=>e.currentTarget.style.background="rgba(255,255,255,.16)"}
      onMouseLeave={e=>e.currentTarget.style.background="rgba(255,255,255,.08)"}>
      {lbl}
    </button>
  );

  return (
    <div ref={outerRef}
      style={{width:"100%",height:"100%",position:"relative",overflow:"hidden",
        background:"#F5F7FF",
        cursor:zoom.s>1?(dragging?"grabbing":"grab"):"default"}}
      onMouseDown={onMD} onMouseMove={onMM} onMouseUp={onMU} onMouseLeave={onMU}>

      {/* ── Atmosphère claire : orbes pastel floutées ── */}
      {/* Orbe bleu ciel — nord-ouest */}
      <div style={{position:"absolute",width:560,height:560,borderRadius:"50%",
        background:"radial-gradient(circle,rgba(147,197,253,.45) 0%,transparent 70%)",
        filter:"blur(80px)",top:"-10%",left:"5%",pointerEvents:"none"}}/>
      {/* Orbe lavande — centre haut */}
      <div style={{position:"absolute",width:620,height:620,borderRadius:"50%",
        background:"radial-gradient(circle,rgba(196,181,253,.35) 0%,transparent 70%)",
        filter:"blur(100px)",top:"5%",left:"30%",pointerEvents:"none"}}/>
      {/* Orbe rose poudré — sud-est */}
      <div style={{position:"absolute",width:460,height:460,borderRadius:"50%",
        background:"radial-gradient(circle,rgba(251,207,232,.4) 0%,transparent 70%)",
        filter:"blur(80px)",bottom:"0%",right:"8%",pointerEvents:"none"}}/>
      {/* Halo doré subtil — derrière la carte */}
      <div style={{position:"absolute",width:500,height:500,borderRadius:"50%",
        background:"radial-gradient(circle,rgba(253,230,138,.3) 0%,transparent 65%)",
        filter:"blur(70px)",top:"28%",left:"36%",pointerEvents:"none"}}/>
      {/* Vignette bords légère */}
      <div style={{position:"absolute",inset:0,pointerEvents:"none",
        background:"radial-gradient(ellipse at 50% 50%, transparent 45%, rgba(200,210,240,.45) 100%)"}}/>
      {/* Grille de points fine */}
      <div style={{position:"absolute",inset:0,pointerEvents:"none",
        backgroundImage:"radial-gradient(circle at 1px 1px,rgba(100,120,200,.07) 1px,transparent 0)",
        backgroundSize:"28px 28px"}}/>

      {/* Conteneur zoomable */}
      <div style={{
        position:"absolute",inset:0,
        transform:`translate(${zoom.x}px,${zoom.y}px) scale(${zoom.s})`,
        transformOrigin:"0 0",
        transition:dragging?"none":"transform .18s cubic-bezier(.22,1,.36,1)",
        willChange:"transform",
        display:"flex",alignItems:"center",justifyContent:"center"}}>

        <div style={{perspective:"1400px",perspectiveOrigin:"50% 38%"}}>
          <div style={{
            transform:"rotateX(26deg) rotateY(-3deg)",
            transformStyle:"preserve-3d",
            animation:"mapFloat 8s ease-in-out infinite",
            filter:"drop-shadow(0 40px 80px rgba(100,120,200,.22)) drop-shadow(0 8px 28px rgba(100,120,200,.18)) drop-shadow(0 2px 8px rgba(0,0,0,.1))",
            width:"min(88vh,660px)",
            position:"relative"}}>
            {/* Halo de reflet sous le continent */}
            <div style={{position:"absolute",bottom:"-6%",left:"5%",right:"5%",height:"40px",
              background:"radial-gradient(ellipse,rgba(147,180,255,.28) 0%,transparent 70%)",
              filter:"blur(24px)",pointerEvents:"none",transform:"translateY(16px)"}}/>
            <div ref={svgRef} style={{display:"block",width:"100%"}}/>
          </div>
        </div>
      </div>

      {/* Contrôles zoom */}
      <div style={{position:"absolute",top:14,right:14,display:"flex",flexDirection:"column",gap:4,zIndex:20}}>
        {zBtn(()=>setZoom(z=>{const rc=outerRef.current?.getBoundingClientRect()||{width:800,height:600};const ns2=Math.min(7,z.s*1.35);if(ns2===1)return{s:1,x:0,y:0};return clamp(ns2,rc.width/2-(rc.width/2-z.x)*(ns2/z.s),rc.height/2-(rc.height/2-z.y)*(ns2/z.s));}),"+")}
        {zBtn(()=>setZoom(z=>{const ns2=Math.max(1,z.s/1.35);return clamp(ns2,z.x*(ns2/z.s),z.y*(ns2/z.s));}),"−")}
        {zoom.s>1&&zBtn(()=>setZoom({s:1,x:0,y:0}),"⊙")}
      </div>

      {/* Tooltip */}
      {tooltip&&(
        <div style={{position:"fixed",left:tooltip.x+16,top:tooltip.y-80,zIndex:200,pointerEvents:"none",
          background:"rgba(14,18,28,.94)",border:`1.5px solid ${FRANCO_COLORS[tooltip.pays.id]}55`,
          borderRadius:12,padding:"12px 16px",
          boxShadow:`0 16px 48px rgba(0,0,0,.5),0 0 0 1px ${FRANCO_COLORS[tooltip.pays.id]}22`,
          backdropFilter:"blur(12px)",animation:"caTooltip .12s ease",minWidth:165}}>
          <div style={{display:"flex",alignItems:"center",gap:9,marginBottom:6}}>
            <img src={tooltip.pays.flagImg} alt="" style={{width:24,height:15,objectFit:"cover",borderRadius:3,flexShrink:0,border:"1px solid rgba(255,255,255,.12)"}}/>
            <span style={{fontSize:13,fontWeight:800,color:"rgba(255,255,255,.92)"}}>{tooltip.pays.nom}</span>
            <div style={{width:7,height:7,borderRadius:2,background:FRANCO_COLORS[tooltip.pays.id],flexShrink:0}}/>
          </div>
          {tooltip.pays.actif
            ? <><div style={{fontSize:10.5,color:"rgba(255,255,255,.45)",marginBottom:7}}>{tooltip.pays.kpi}</div>
                <div style={{display:"flex",alignItems:"center",gap:5,fontSize:10.5,fontWeight:700,color:FRANCO_COLORS[tooltip.pays.id]}}>
                  Accéder au tableau de bord
                  <svg viewBox="0 0 12 12" fill="none" width="9" height="9"><path d="M2 6h8M6 3l3 3-3 3" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </div></>
            : <div style={{fontSize:10,color:"rgba(255,255,255,.3)"}}>Données disponibles prochainement</div>
          }
        </div>
      )}

      {zoom.s===1&&(
        <div style={{position:"absolute",bottom:14,right:14,padding:"4px 12px",borderRadius:20,
          background:"rgba(0,0,0,.38)",border:"1px solid rgba(255,255,255,.1)",
          fontSize:9.5,color:"rgba(255,255,255,.4)",fontWeight:500,pointerEvents:"none",zIndex:10,
          backdropFilter:"blur(8px)"}}>
          Molette · Glisser · Survoler
        </div>
      )}
    </div>
  );
}

/* ══ Sidebar pays — structure identique à Sidebar.jsx ══ */
function CountrySidebar({ pays, onNavigate }) {
  const [hov, setHov] = useState(null);

  /* item helper — même style que les NavLink de Sidebar.jsx */
  const navItem = (key, onClick, accentColor, bgActive, borderActive, colorActive, content) => (
    <div key={key} onClick={onClick}
      onMouseEnter={() => setHov(key)} onMouseLeave={() => setHov(null)}
      style={{
        display:"flex", alignItems:"center",
        height:44, paddingLeft:0, paddingRight:12,
        borderRadius:12, overflow:"hidden", cursor:"pointer",
        background: hov===key ? bgActive : "rgba(255,255,255,.04)",
        border:`1.5px solid ${hov===key ? borderActive : "transparent"}`,
        color: hov===key ? colorActive : "rgba(255,255,255,.65)",
        transition:"all .18s",
      }}>
      <div style={{ width:3, alignSelf:"stretch", background:accentColor,
        flexShrink:0, borderRadius:"0 2px 2px 0" }}/>
      <div style={{ display:"flex", alignItems:"center", gap:10, flex:1, paddingLeft:10 }}>
        {content}
      </div>
    </div>
  );

  return (
    <div style={{
      width:256, flexShrink:0,
      background:"#3C3C4A",
      borderRight:"1px solid rgba(255,255,255,.06)",
      display:"flex", flexDirection:"column",
      fontFamily:"Inter,system-ui,sans-serif",
      boxShadow:"2px 0 16px rgba(0,0,0,.25)",
      minHeight:"100%",
    }}>

      {/* LOGO — identique à Sidebar.jsx */}
      <div style={{ display:"flex", alignItems:"center", gap:12, padding:"20px 16px",
        borderBottom:"1px solid rgba(255,255,255,.08)" }}>
        <FSLogo size={38}/>
        <div>
          <div style={{ fontSize:11, fontWeight:900, letterSpacing:"1.6px", color:"white" }}>FS MARKET</div>
          <div style={{ fontSize:11, fontWeight:900, letterSpacing:"1.6px", color:"#FFE600" }}>INTELLIGENCE</div>
        </div>
      </div>

      {/* LABEL Navigation */}
      <div style={{ fontSize:9, fontWeight:700, letterSpacing:"2.5px", textTransform:"uppercase",
        color:"rgba(255,255,255,.22)", padding:"16px 16px 8px" }}>
        Navigation
      </div>

      {/* MENUS PRINCIPAUX — identiques à Sidebar.jsx */}
      <div style={{ padding:"0 12px", display:"flex", flexDirection:"column", gap:6 }}>

        {/* Page d'accueil */}
        {navItem("accueil", () => onNavigate("/accueil"),
          "#FFE600", "rgba(255,230,0,.18)", "rgba(255,230,0,.4)", "#FFE600",
          <>
            <svg viewBox="0 0 20 20" fill="none" width="15" height="15">
              <path d="M3 9.5L10 3l7 6.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M5 8.5v7a1 1 0 001 1h3v-3.5h2V16.5h3a1 1 0 001-1v-7" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span style={{ fontWeight:600, fontSize:13, flex:1 }}>Page d'accueil</span>
          </>
        )}

        {/* Vue continentale */}
        {navItem("continent", () => onNavigate("/apercu-marche"),
          "#C89200", "rgba(200,146,0,.22)", "rgba(200,146,0,.5)", "#FFE600",
          <>
            <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
              <circle cx="10" cy="10" r="7.5" stroke="currentColor" strokeWidth="1.5"/>
              <ellipse cx="10" cy="10" rx="7.5" ry="3" stroke="currentColor" strokeWidth="1.3"/>
              <line x1="10" y1="2.5" x2="10" y2="17.5" stroke="currentColor" strokeWidth="1.2"/>
            </svg>
            <span style={{ fontWeight:500, fontSize:13, flex:1 }}>Vue continentale</span>
          </>
        )}

        {/* Vue par pays — actif (page courante) */}
        <div style={{
          display:"flex", alignItems:"center",
          height:44, paddingLeft:0, paddingRight:12,
          borderRadius:12, overflow:"hidden",
          background:"rgba(59,130,246,.22)",
          border:"1.5px solid rgba(59,130,246,.5)",
          color:"#60A5FA",
        }}>
          <div style={{ width:3, alignSelf:"stretch", background:"#3B82F6", flexShrink:0, borderRadius:"0 2px 2px 0" }}/>
          <div style={{ display:"flex", alignItems:"center", gap:10, flex:1, paddingLeft:10 }}>
            <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
              <path d="M10 2C7.24 2 5 4.24 5 7c0 4.2 5 11 5 11s5-6.8 5-11c0-2.76-2.24-5-5-5z" stroke="currentColor" strokeWidth="1.5"/>
              <circle cx="10" cy="7" r="2" stroke="currentColor" strokeWidth="1.4"/>
            </svg>
            <span style={{ fontWeight:700, fontSize:13, flex:1 }}>Vue par pays</span>
            <div style={{ fontSize:8.5, fontWeight:800, padding:"2px 7px", borderRadius:20,
              background:"rgba(59,130,246,.25)", color:"#93C5FD",
              border:"1px solid rgba(59,130,246,.35)" }}>1 actif</div>
          </div>
        </div>


      </div>

      {/* LABEL Marchés */}
      <div style={{ fontSize:9, fontWeight:700, letterSpacing:"2.5px", textTransform:"uppercase",
        color:"rgba(255,255,255,.22)", padding:"16px 16px 8px" }}>
        Marchés
      </div>

      {/* LISTE PAYS — design uniforme : barre accent + drapeau circulaire + nom */}
      <div style={{ flex:1, overflowY:"auto", padding:"0 12px 8px", display:"flex", flexDirection:"column", gap:4 }}>
        {pays.map(p => {
          const c   = FRANCO_COLORS[p.id];
          const rgb = hexToRgb(c);
          const isH = hov === p.id;
          return (
            <div key={p.id}
              onClick={() => p.actif && p.target && onNavigate(p.target)}
              onMouseEnter={() => setHov(p.id)}
              onMouseLeave={() => setHov(null)}
              style={{
                display:"flex", alignItems:"center",
                height:44, paddingLeft:0, paddingRight:12,
                borderRadius:12, overflow:"hidden",
                background: isH ? `rgba(${rgb},.14)` : "rgba(255,255,255,.04)",
                border:`1.5px solid ${isH ? `rgba(${rgb},.45)` : "rgba(255,255,255,.07)"}`,
                cursor: p.actif ? "pointer" : "default",
                transition:"all .18s",
              }}>
              <div style={{ width:3, alignSelf:"stretch", flexShrink:0,
                background:c, borderRadius:"0 2px 2px 0",
                opacity: isH ? 1 : 0.7, transition:"opacity .15s" }}/>
              <div style={{ display:"flex", alignItems:"center", gap:10, flex:1, paddingLeft:10 }}>
                <div style={{ width:30, height:30, borderRadius:"50%", overflow:"hidden", flexShrink:0,
                  border:`2px solid rgba(${rgb},.5)`, boxShadow:"0 2px 6px rgba(0,0,0,.25)" }}>
                  <img src={p.flagImg} alt={p.nom}
                    style={{ width:"100%", height:"100%", objectFit:"cover", display:"block" }}/>
                </div>
                <span style={{ fontWeight: p.actif ? 600 : 400, fontSize:13, flex:1,
                  color: isH ? "white" : (p.actif ? "rgba(255,255,255,.82)" : "rgba(255,255,255,.38)"),
                  transition:"color .15s" }}>{p.nom}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* FOOTER — identique à Sidebar.jsx */}
      <div style={{ padding:"14px 16px", borderTop:"1px solid rgba(255,255,255,.07)" }}>
        <div style={{ fontSize:10, color:"rgba(255,255,255,.45)" }}>Données · CMF · FTUSA · CGA</div>
        <div style={{ fontSize:12, fontWeight:700, color:"#FFE600", marginTop:2 }}>2019 – 2024</div>
      </div>
    </div>
  );
}

/* ══ Page ══ */
export default function CarteAfrique() {
  const navigate = useNavigate();
  return (
    <div style={{height:"100vh",width:"100vw",display:"flex",flexDirection:"column",
      overflow:"hidden",fontFamily:"Inter,system-ui,sans-serif",background:"#1E222D"}}>

      <Topbar
        onBack={()=>navigate("/accueil")}
        onContinent={()=>navigate("/apercu-marche")}/>

      {/* Corps : sidebar + carte */}
      <div style={{flex:1,display:"flex",overflow:"hidden"}}>
        <CountrySidebar pays={PAYS} onNavigate={navigate}/>
        <div style={{flex:1,position:"relative",overflow:"hidden"}}>
          <AfricaMapSVG pays={PAYS} onNavigate={navigate}/>
        </div>
      </div>

      <style>{`
        @keyframes caPulse   { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.3;transform:scale(1.8)} }
        @keyframes caTooltip { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
        @keyframes mapFloat  { 0%,100%{transform:rotateX(28deg) rotateY(-4deg) translateY(0)} 50%{transform:rotateX(28deg) rotateY(-4deg) translateY(-6px)} }
      `}</style>
    </div>
  );
}
