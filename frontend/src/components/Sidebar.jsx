import { NavLink, useLocation } from "react-router-dom";
import { useState } from "react";

const Y   = "#FFE600";
const RED = "#C8102E";
const BG  = "#3C3C4A";

const subPages = [
  {
    to: "/apercu-marche",
    label: "Aperçu marché",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
        <path d="M2 14l4-4 3 3 4-5 4 3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="2"  cy="14" r="1.2" fill="currentColor"/>
        <circle cx="6"  cy="10" r="1.2" fill="currentColor"/>
        <circle cx="9"  cy="13" r="1.2" fill="currentColor"/>
        <circle cx="13" cy="8"  r="1.2" fill="currentColor"/>
        <circle cx="17" cy="11" r="1.2" fill="currentColor"/>
      </svg>
    ),
  },
  {
    to: "/analyse-comparative",
    label: "Analyse comparative",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
        <rect x="2"  y="10" width="3" height="8"  rx="1" fill="currentColor"/>
        <rect x="7"  y="6"  width="3" height="12" rx="1" fill="currentColor"/>
        <rect x="12" y="3"  width="3" height="15" rx="1" fill="currentColor"/>
        <rect x="17" y="8"  width="3" height="10" rx="1" fill="currentColor"/>
      </svg>
    ),
  },
  {
    to: "/fiches",
    label: "Vue par assurance",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
        <rect x="3" y="4" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M7 8h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    to: "/enquete-marche",
    label: "Enquête de marché",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
        <path d="M10 2a8 8 0 100 16A8 8 0 0010 2z" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M7 9.5h6M10 6.5v7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    to: "/actualites-seminaires",
    label: "Veille d'actualité",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
        <path d="M3 5h14M3 10h10M3 15h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        <circle cx="16" cy="14" r="3" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M15 14l.7.7 1.3-1.3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    to: "/veille-reglementaire",
    label: "Veille réglementaire",
    icon: (
      <svg viewBox="0 0 20 20" fill="none" width="14" height="14">
        <path d="M4 4h12v12H4z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M7 8h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        <path d="M13 2v3M7 2v3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
];

function FSLogo() {
  return (
    <div style={{ width:38, height:38, borderRadius:8, background:Y, flexShrink:0,
      display:"flex", alignItems:"center", justifyContent:"center" }}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <rect x="2"  y="15" width="4" height="7"  rx="1" fill="#2E2E38"/>
        <rect x="8"  y="10" width="4" height="12" rx="1" fill="#2E2E38"/>
        <rect x="14" y="5"  width="4" height="17" rx="1" fill="#2E2E38"/>
        <polyline points="4,15 10,10 16,5" stroke="#2E2E38" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="4"  cy="15" r="1.4" fill="#2E2E38"/>
        <circle cx="10" cy="10" r="1.4" fill="#2E2E38"/>
        <circle cx="16" cy="5"  r="1.4" fill="#2E2E38"/>
      </svg>
    </div>
  );
}

export default function Sidebar() {
  const [hov, setHov] = useState(null);
  const location      = useLocation();

  return (
    <aside style={{ width:256, minHeight:"100vh", background:BG, flexShrink:0,
      borderRight:"1px solid rgba(255,255,255,.06)",
      boxShadow:"2px 0 16px rgba(0,0,0,.25)",
      display:"flex", flexDirection:"column",
      fontFamily:"Inter,system-ui,sans-serif" }}>

      {/* LOGO */}
      <div style={{ display:"flex", alignItems:"center", gap:12, padding:"20px 16px",
        borderBottom:"1px solid rgba(255,255,255,.08)" }}>
        <FSLogo/>
        <div>
          <div style={{ fontSize:11, fontWeight:900, letterSpacing:"1.6px", color:"white" }}>FS MARKET</div>
          <div style={{ fontSize:11, fontWeight:900, letterSpacing:"1.6px", color:Y }}>INTELLIGENCE</div>
        </div>
      </div>

      {/* LABEL Navigation */}
      <div style={{ fontSize:9, fontWeight:700, letterSpacing:"2.5px", textTransform:"uppercase",
        color:"rgba(255,255,255,.22)", padding:"16px 16px 8px" }}>
        Navigation
      </div>

      {/* Page d'accueil */}
      <div style={{ padding:"0 12px 6px" }}>
        <NavLink to="/accueil"
          onMouseEnter={() => setHov("accueil")} onMouseLeave={() => setHov(null)}
          style={({ isActive }) => ({
            display:"flex", alignItems:"center", gap:10,
            height:44, paddingLeft:12, paddingRight:12, borderRadius:12,
            background: isActive
              ? "linear-gradient(135deg,#FFE600 0%,#E6B800 100%)"
              : (hov==="accueil" ? "rgba(255,230,0,.12)" : "rgba(255,255,255,.05)"),
            border: isActive ? "1.5px solid #FFE600"
              : (hov==="accueil" ? "1.5px solid rgba(255,230,0,.35)" : "1.5px solid rgba(255,255,255,.07)"),
            boxShadow: isActive ? "0 4px 14px rgba(255,230,0,.25)" : "none",
            color: isActive ? "#2E2E38" : (hov==="accueil" ? "#FFE600" : "rgba(255,255,255,.65)"),
            textDecoration:"none", transition:"all .18s",
          })}>
          {({ isActive }) => (<>
            <svg viewBox="0 0 20 20" fill="none" width="15" height="15">
              <path d="M3 9.5L10 3l7 6.5"
                stroke={isActive ? "#2E2E38" : "currentColor"}
                strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M5 8.5v7a1 1 0 001 1h3v-3.5h2V16.5h3a1 1 0 001-1v-7"
                stroke={isActive ? "#2E2E38" : "currentColor"}
                strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            <span style={{ fontWeight:600, fontSize:13, flex:1 }}>Page d'accueil</span>
          </>)}
        </NavLink>
      </div>

      {/* LABEL Marchés */}
      <div style={{ fontSize:9, fontWeight:700, letterSpacing:"2.5px", textTransform:"uppercase",
        color:"rgba(255,255,255,.22)", padding:"10px 16px 8px" }}>
        Marchés
      </div>

      {/* Bouton Tunisie */}
      <div style={{ padding:"0 12px 4px" }}>
        <div style={{
          display:"flex", alignItems:"center",
          height:44, paddingLeft:0, paddingRight:12,
          borderRadius:12, overflow:"hidden",
          background:"rgba(200,16,46,.18)",
          border:"1.5px solid rgba(200,16,46,.4)",
        }}>
          <div style={{ width:3, alignSelf:"stretch", background:RED,
            flexShrink:0, borderRadius:"0 2px 2px 0" }}/>
          <div style={{ display:"flex", alignItems:"center", gap:10, flex:1, paddingLeft:10 }}>
            <div style={{ width:30, height:30, borderRadius:"50%", overflow:"hidden", flexShrink:0,
              border:"2px solid rgba(200,16,46,.5)", boxShadow:"0 2px 6px rgba(0,0,0,.25)" }}>
              <img src="/logos/tn-flag.png" alt="TN"
                style={{ width:"100%", height:"100%", objectFit:"cover" }}/>
            </div>
            <span style={{ fontWeight:600, fontSize:13, flex:1, color:"rgba(255,255,255,.85)" }}>Tunisie</span>
            <div style={{ fontSize:7.5, fontWeight:800, padding:"2px 7px", borderRadius:20,
              background:"rgba(200,16,46,.22)", color:"#FF8080",
              border:"1px solid rgba(200,16,46,.35)" }}>ACTIF</div>
          </div>
        </div>
      </div>

      {/* Sous-pages */}
      <div style={{ flex:1, overflowY:"auto", padding:"0 12px 8px",
        display:"flex", flexDirection:"column", gap:3 }}>
        {subPages.map(p => {
          const isAct = location.pathname === p.to || location.pathname.startsWith(p.to + "/");
          const isH   = hov === p.to;
          return (
            <NavLink key={p.to} to={p.to}
              onMouseEnter={() => setHov(p.to)} onMouseLeave={() => setHov(null)}
              style={{
                display:"flex", alignItems:"center",
                height:40, paddingLeft:0, paddingRight:12,
                borderRadius:10, overflow:"hidden",
                background: isAct ? "rgba(255,255,255,.93)" : (isH ? "rgba(255,255,255,.07)" : "rgba(255,255,255,.03)"),
                border:`1px solid ${isAct ? "rgba(200,16,46,.5)" : (isH ? "rgba(255,255,255,.12)" : "rgba(255,255,255,.05)")}`,
                textDecoration:"none", transition:"all .15s",
              }}>
              <div style={{ width:3, alignSelf:"stretch", background:RED,
                flexShrink:0, borderRadius:"0 2px 2px 0",
                opacity: isAct ? 1 : (isH ? 0.6 : 0.3), transition:"opacity .15s" }}/>
              <div style={{ display:"flex", alignItems:"center", gap:9, flex:1, paddingLeft:10 }}>
                <span style={{ flexShrink:0, display:"flex",
                  color: isAct ? RED : (isH ? "white" : "rgba(255,255,255,.38)"),
                  transition:"color .15s" }}>
                  {p.icon}
                </span>
                <span style={{ fontWeight: isAct ? 700 : 400, fontSize:12, flex:1,
                  color: isAct ? RED : (isH ? "rgba(255,255,255,.85)" : "rgba(255,255,255,.55)"),
                  transition:"color .15s" }}>{p.label}</span>
              </div>
            </NavLink>
          );
        })}
      </div>

      {/* FOOTER */}
      <div style={{ padding:"14px 16px", borderTop:"1px solid rgba(255,255,255,.07)" }}>
        <div style={{ fontSize:10, color:"rgba(255,255,255,.38)" }}>Données · CMF · FTUSA · CGA</div>
        <div style={{ fontSize:12, fontWeight:700, color:Y, marginTop:2 }}>2019 – 2024</div>
      </div>

    </aside>
  );
}
