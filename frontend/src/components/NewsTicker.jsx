import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

const Y = "#FFE600", D = "#2E2E38";
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const CAT_COLOR = {
  "Réglementation":               "#ef4444",
  "Résultats financiers":         "#22c55e",
  "Gouvernance":                  "#f59e0b",
  "Coopération institutionnelle": "#3b82f6",
  "Partenariat":                  "#f97316",
  "Digital":                      "#6366f1",
  "Publication":                  "#8b5cf6",
  "Innovation":                   "#14b8a6",
  "Actualité":                    "#94a3b8",
};

const STATIC = [
  { titre:"BNA Assurances inaugure deux bornes de recharge VE à Sfax",      categorie:"Innovation",          compagnie:"BNA Assurances",    src:"ILBOURSA",       url:"#" },
  { titre:"STAR Assurances : distribution de dividendes",                    categorie:"Résultats financiers", compagnie:"STAR Assurances",   src:"ATLAS MAGAZINE", url:"#" },
  { titre:"BH Assurance renforce son partenariat avec Qatar Insurance Group",categorie:"Partenariat",          compagnie:"BH Assurance",      src:"ATLAS MAGAZINE", url:"#" },
  { titre:"Le secteur des assurances face aux nouveaux défis réglementaires",categorie:"Réglementation",       compagnie:"—",                 src:"ATLAS MAGAZINE", url:"#" },
];

export default function NewsTicker() {
  const navigate = useNavigate();
  const [items, setItems] = useState(STATIC);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/actualites`)
      .then(r => r.json())
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
          setItems(data.slice(0, 30));
          setLoaded(true);
        }
      })
      .catch(() => {});
  }, []);

  /* Duplicate for seamless loop */
  const doubled = [...items, ...items];
  /* Speed: ~80px/s, estimate ~140px per item on average */
  const duration = Math.max(items.length * 7, 40);

  return (
    <div style={{
      flexShrink: 0,
      background: "linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)",
      borderRadius: 8,
      overflow: "hidden",
      boxShadow: "0 4px 24px rgba(10,10,20,.38), 0 1px 0 rgba(255,255,255,.04) inset",
      display: "flex",
      alignItems: "stretch",
      height: 42,
    }}>
      <style>{`
        @keyframes nt-scroll {
          from { transform: translateX(0); }
          to   { transform: translateX(-50%); }
        }
        .nt-track { animation: nt-scroll ${duration}s linear infinite; }
        .nt-wrap:hover .nt-track { animation-play-state: paused; }
        @keyframes nt-pulse { 0%,100%{opacity:1} 50%{opacity:.15} }
      `}</style>

      {/* ── Label gauche ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "0 16px 0 18px", flexShrink: 0,
        borderRight: "1px solid rgba(255,255,255,.10)",
      }}>
        <span style={{
          width: 7, height: 7, borderRadius: "50%",
          background: "#ef4444",
          animation: "nt-pulse 1.4s ease-in-out infinite",
          display: "inline-block", flexShrink: 0,
        }}/>
        <span style={{
          fontSize: 8, fontWeight: 900, letterSpacing: "2px",
          textTransform: "uppercase", color: Y, whiteSpace: "nowrap",
        }}>Actualités marché</span>
      </div>

      {/* ── Ticker défilant ── */}
      <div className="nt-wrap" style={{
        flex: 1, overflow: "hidden", position: "relative",
        display: "flex", alignItems: "center",
      }}>
        {/* Fondu gauche */}
        <div style={{
          position: "absolute", left: 0, top: 0, bottom: 0, width: 40, zIndex: 2,
          background: "linear-gradient(to right, #1E1E2A, transparent)",
          pointerEvents: "none",
        }}/>
        {/* Fondu droit */}
        <div style={{
          position: "absolute", right: 0, top: 0, bottom: 0, width: 40, zIndex: 2,
          background: "linear-gradient(to left, #252535, transparent)",
          pointerEvents: "none",
        }}/>

        <div className="nt-track" style={{
          display: "flex", alignItems: "center",
          width: "max-content", gap: 0,
        }}>
          {doubled.map((item, i) => {
            const catColor = CAT_COLOR[item.categorie] || "#94a3b8";
            const label = item.compagnie && item.compagnie !== "—"
              ? item.compagnie
              : (item.src === "ILBOURSA" ? "IlBoursa" : "Atlas Magazine");
            return (
              <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                <a
                  href={item.url !== "#" ? item.url : undefined}
                  onClick={item.url === "#" ? undefined : undefined}
                  target={item.url !== "#" ? "_blank" : undefined}
                  rel="noreferrer"
                  style={{
                    display: "inline-flex", alignItems: "center", gap: 7,
                    textDecoration: "none", padding: "0 20px",
                    cursor: item.url !== "#" ? "pointer" : "default",
                  }}
                >
                  {/* Dot coloré selon catégorie */}
                  <span style={{
                    width: 5, height: 5, borderRadius: "50%",
                    background: catColor, flexShrink: 0,
                  }}/>
                  {/* Catégorie */}
                  <span style={{
                    fontSize: 8, fontWeight: 800, textTransform: "uppercase",
                    letterSpacing: "0.8px", color: catColor,
                    flexShrink: 0,
                  }}>{item.categorie || "Actualité"}</span>
                  {/* Titre */}
                  <span style={{
                    fontSize: 12, fontWeight: 600, color: "white",
                    whiteSpace: "nowrap",
                  }}>{item.titre}</span>
                  {/* Source */}
                  <span style={{
                    fontSize: 9.5, color: "rgba(255,255,255,.38)",
                    whiteSpace: "nowrap",
                  }}>— {label}</span>
                </a>
                {/* Séparateur */}
                <span style={{
                  fontSize: 10, color: "rgba(255,255,255,.15)",
                  userSelect: "none", flexShrink: 0,
                }}>◆</span>
              </span>
            );
          })}
        </div>
      </div>

      {/* ── Lien Veille ── */}
      <button
        onClick={() => navigate("/actualites-seminaires")}
        style={{
          flexShrink: 0,
          display: "flex", alignItems: "center", gap: 6,
          padding: "0 16px",
          background: "rgba(255,230,0,.10)", border: "none",
          borderLeft: "1px solid rgba(255,255,255,.10)",
          cursor: "pointer", transition: "background .15s",
          fontSize: 10, fontWeight: 800, color: Y,
          letterSpacing: "0.5px", whiteSpace: "nowrap",
        }}
        onMouseEnter={e => e.currentTarget.style.background = "rgba(255,230,0,.18)"}
        onMouseLeave={e => e.currentTarget.style.background = "rgba(255,230,0,.10)"}
      >
        Voir tout
        <svg viewBox="0 0 12 12" fill="none" stroke={Y} strokeWidth="2" width="9" height="9">
          <path d="M4 2l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
    </div>
  );
}
