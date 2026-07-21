import { useState } from "react";

const D = "#2E2E38", Y = "#FFE600", G = "#747480", BDR = "#E5E7EB", WH = "#FFFFFF";

/* ── Chevron SVG ── */
function Chev({ open }) {
  return (
    <svg viewBox="0 0 10 10" fill="none" width="10" height="10"
      style={{ transform: open ? "rotate(180deg)" : "none", transition: "transform .15s", flexShrink:0 }}>
      <path d="M1.5 3.5l3 3 3-3" stroke={D} strokeWidth="2" strokeLinecap="round"/>
    </svg>
  );
}

/* ── Sélecteur d'année (même design qu'ApercuMarche) ── */
export function YearSelector({ year, years, onChange, noDataYears = [] }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ position:"relative", display:"flex", alignItems:"center", gap:10 }}>
      <span style={{ fontSize:10, fontWeight:700, color:G, letterSpacing:"1px", textTransform:"uppercase" }}>Année</span>
      <button onClick={() => setOpen(o => !o)} style={{
        display:"flex", alignItems:"center", gap:10,
        background:Y, border:"none", cursor:"pointer",
        padding:"8px 18px", borderRadius:9, fontSize:15, fontWeight:900, color:D,
        boxShadow:"0 2px 10px rgba(255,230,0,.35)", fontVariantNumeric:"tabular-nums",
        fontFamily:"Barlow, system-ui, sans-serif",
      }}>
        {year}
        <Chev open={open}/>
      </button>
      {open && (
        <div style={{
          position:"absolute", right:0, top:"calc(100% + 8px)",
          background:WH, border:`1px solid ${BDR}`, borderRadius:12,
          boxShadow:"0 12px 32px rgba(0,0,0,.14)", zIndex:60, minWidth:120, overflow:"hidden",
        }}>
          {years.map(a => {
            const nd = noDataYears.includes(a);
            return (
              <button key={a} onClick={nd ? undefined : () => { onChange(a); setOpen(false); }}
                disabled={nd}
                style={{
                  display:"flex", alignItems:"center", justifyContent:"space-between",
                  width:"100%", padding:"10px 16px", fontSize:13,
                  fontWeight: a === year ? 900 : 500,
                  color: nd ? BDR : a === year ? D : G,
                  background: a === year ? `${Y}44` : WH,
                  border:"none", borderBottom:`1px solid ${BDR}`,
                  cursor: nd ? "default" : "pointer",
                  fontFamily:"Barlow, system-ui, sans-serif",
                }}>
                <span>{a}{nd && <span style={{ fontSize:9, marginLeft:6, color:BDR }}>n/d</span>}</span>
                {a === year && !nd && <span style={{ color:D, fontWeight:900, fontSize:14 }}>✓</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ══ DarkKpiBanner — bandeau KPI sombre unifié (style ApercuMarche) ══
   items: [{ label, value, sub?, delta?, pos? }]
*/
export function DarkKpiBanner({ items = [] }) {
  return (
    <div style={{
      background:"linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)",
      borderRadius:8, display:"flex", overflow:"hidden", flexShrink:0,
      boxShadow:"0 4px 24px rgba(10,10,20,.38), 0 1px 0 rgba(255,255,255,.04) inset",
    }}>
      {items.map((k, i) => (
        <div key={i} style={{
          flex:1, minWidth:0,
          padding:"14px 20px 12px",
          borderLeft: i > 0 ? "1px solid rgba(255,255,255,.07)" : "none",
          display:"flex", flexDirection:"column",
        }}>
          <div style={{ fontSize:7.5, fontWeight:700, letterSpacing:"2px", textTransform:"uppercase", color:"rgba(255,255,255,.38)", marginBottom:8 }}>{k.label}</div>
          <div style={{ fontSize:26, fontWeight:300, lineHeight:1, fontVariantNumeric:"tabular-nums", letterSpacing:"-0.8px", marginBottom:6, color:"#FFFFFF", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{String(k.value ?? "—")}</div>
          <div style={{ display:"flex", alignItems:"center", gap:6, marginTop:"auto" }}>
            {k.sub && <span style={{ fontSize:9.5, color:"rgba(255,255,255,.30)", overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{k.sub}</span>}
            {k.delta && (
              <span style={{ fontSize:9.5, fontWeight:800, marginLeft:"auto", flexShrink:0, color: k.pos !== false ? "#4ade80" : "#f87171" }}>
                {k.pos !== false ? "↑" : "↓"} {k.delta}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ══ PageHeaderBar — composant principal ══
   Props :
   - title       : string
   - tabs        : [{ key, label }] (optionnel)
   - activeTab   : string (si tabs)
   - onTabChange : fn(key) (si tabs)
   - right       : ReactNode (ex: YearSelector ou filtres)
*/
export default function PageHeaderBar({ title, tabs, activeTab, onTabChange, right }) {
  const hasTabs = tabs && tabs.length > 0;
  return (
    <div style={{ background:WH, borderBottom:`1px solid ${BDR}`, flexShrink:0 }}>
      <div style={{ padding:"0 28px" }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", height:58 }}>

          {/* ── Gauche : drapeau + titre + tabs ── */}
          <div style={{ display:"flex", alignItems:"stretch", gap:0 }}>
            <div style={{
              display:"flex", alignItems:"center", gap:10,
              paddingRight: hasTabs ? 24 : 0,
              marginRight:  hasTabs ? 8  : 0,
              borderRight:  hasTabs ? `1px solid ${BDR}` : "none",
            }}>
              <img src="/logos/tn-flag.png" alt="TN"
                style={{ height:20, borderRadius:3, opacity:.85, flexShrink:0 }}/>
              <h1 style={{ fontSize:17, fontWeight:900, color:D, margin:0, letterSpacing:"-0.2px", whiteSpace:"nowrap" }}>
                {title}
              </h1>
            </div>
            {hasTabs && tabs.map(t => (
              <button key={t.key} onClick={() => onTabChange?.(t.key)} style={{
                padding:"0 20px", border:"none", background:"none", cursor:"pointer",
                fontSize:13, fontWeight: activeTab === t.key ? 800 : 500,
                color: activeTab === t.key ? D : G,
                borderBottom:`3px solid ${activeTab === t.key ? Y : "transparent"}`,
                transition:"all .15s", whiteSpace:"nowrap",
                fontFamily:"Barlow, system-ui, sans-serif",
              }}>{t.label}</button>
            ))}
          </div>

          {/* ── Droite : slot libre (filtre année, sélecteur, etc.) ── */}
          {right && <div style={{ display:"flex", alignItems:"center", gap:12 }}>{right}</div>}
        </div>
      </div>
    </div>
  );
}
