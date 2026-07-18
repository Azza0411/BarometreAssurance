import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";

const NATURE_IMG = {
  "Coopération":    "/images/CGA1.png",
  "Réglementation": "/images/CGA2.png",
  "Publication":    "/images/CGA3.png",
  "Événement":      "/images/CGA4.png",
};

const NATURE_COLOR = {
  "Coopération":    { color:"#1E40AF", bg:"#EEF4FF" },
  "Réglementation": { color:"#059669", bg:"#ECFDF5" },
  "Publication":    { color:"#D97706", bg:"#FFF7ED" },
  "Événement":      { color:"#7C3AED", bg:"#F5F3FF" },
};

const NEWS = [
  { date:"28 AVR. 2025", nature:"Coopération",
    titre:"Accord de coopération tuniso-algérien dans la supervision du secteur des assurances",
    resume:"Renforcement de la collaboration entre les autorités de contrôle des deux pays." },
  { date:"28 AVR. 2025", nature:"Réglementation",
    titre:"Renforcement de la lutte contre le blanchiment d'argent",
    resume:"Nouvelles lignes directrices publiées par le CGA à destination des assureurs." },
  { date:"22 AVR. 2025", nature:"Réglementation",
    titre:"Lignes directrices sur l'identification des relations d'affaires",
    resume:"Cadre réglementaire actualisé pour la connaissance client dans les contrats d'assurance." },
  { date:"13 FÉV. 2025", nature:"Publication",
    titre:"Règlement N°03/2025 sur l'externalisation des activités d'assurance",
    resume:"Encadrement des pratiques d'externalisation pour les entreprises du secteur." },
  { date:"10 JAN. 2025", nature:"Publication",
    titre:"Rapport annuel du secteur des assurances — exercice 2024",
    resume:"Analyse des indicateurs clés du marché tunisien sur l'exercice écoulé." },
  { date:"05 JAN. 2025", nature:"Événement",
    titre:"Séminaire international sur la digitalisation du marché assurantiel",
    resume:"Experts internationaux réunis à Tunis pour débattre des enjeux de la transformation numérique." },
];

const INTERVAL = 5000;

export default function NewsTicker() {
  const navigate = useNavigate();
  const [idx, setIdx] = useState(0);
  const [dir, setDir] = useState(1); // 1 = vers gauche, -1 = vers droite
  const [anim, setAnim] = useState(false);
  const timerRef = useRef(null);

  const go = (next, direction = 1) => {
    setDir(direction);
    setAnim(true);
    setTimeout(() => {
      setIdx(next);
      setAnim(false);
    }, 320);
  };

  const startTimer = () => {
    clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setIdx(cur => {
        const next = (cur + 1) % NEWS.length;
        go(next, 1);
        return cur; // go handles the update
      });
    }, INTERVAL);
  };

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setIdx(cur => {
        const next = (cur + 1) % NEWS.length;
go(next, 1);
        return cur;
      });
    }, INTERVAL);
    return () => clearInterval(timerRef.current);
  }, []);

  const prev = () => {
    clearInterval(timerRef.current);
    const next = (idx - 1 + NEWS.length) % NEWS.length;
    go(next, -1);
    setTimeout(startTimer, 400);
  };
  const next = () => {
    clearInterval(timerRef.current);
    const nextIdx = (idx + 1) % NEWS.length;
    go(nextIdx, 1);
    setTimeout(startTimer, 400);
  };
  const goTo = (i) => {
    if (i === idx) return;
    clearInterval(timerRef.current);
    go(i, i > idx ? 1 : -1);
    setTimeout(startTimer, 400);
  };

  const item = NEWS[idx];
  const { color, bg } = NATURE_COLOR[item.nature] ?? { color:"#C8102E", bg:"#FFF0F0" };
  const img = NATURE_IMG[item.nature];

  return (
    <div style={{ marginTop: 20 }}>
      <style>{`
        @keyframes slideInRight { from { opacity:0; transform:translateX(40px); } to { opacity:1; transform:translateX(0); } }
        @keyframes slideInLeft  { from { opacity:0; transform:translateX(-40px); } to { opacity:1; transform:translateX(0); } }
        @keyframes slideOutLeft  { from { opacity:1; transform:translateX(0); } to { opacity:0; transform:translateX(-40px); } }
        @keyframes slideOutRight { from { opacity:1; transform:translateX(0); } to { opacity:0; transform:translateX(40px); } }
        @keyframes livepulse { 0%,100%{opacity:1} 50%{opacity:.2} }
        @keyframes progress { from{width:0%} to{width:100%} }
      `}</style>

      <div style={{
        borderRadius: 14,
        overflow: "hidden",
        boxShadow: "0 4px 20px rgba(0,0,0,0.10)",
        border: "1px solid #E8E8EE",
        display: "flex",
        height: 100,
      }}>
        {/* Panneau gauche rouge */}
        <div style={{
          width: 160, flexShrink: 0,
          background: "linear-gradient(160deg,#C8102E 0%,#7A0000 100%)",
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 6, padding: "0 14px",
        }}>
          <div style={{ display:"flex", alignItems:"center", gap:5 }}>
            <span style={{ width:5, height:5, borderRadius:"50%", background:"#FFE600",
              animation:"livepulse 1.5s ease-in-out infinite", display:"inline-block" }}/>
            <span style={{ fontSize:8, fontWeight:900, letterSpacing:"2px",
              textTransform:"uppercase", color:"rgba(255,255,255,0.7)" }}>
              EN DIRECT
            </span>
          </div>
          <span style={{ fontSize:11, fontWeight:900, letterSpacing:"1px",
            textTransform:"uppercase", color:"white", textAlign:"center", lineHeight:1.3 }}>
            Actualités<br/>CGA
          </span>
          {/* Dots */}
          <div style={{ display:"flex", gap:5, marginTop:2 }}>
            {NEWS.map((_,i) => (
              <button key={i} onClick={() => goTo(i)}
                style={{
                  width: i===idx ? 16 : 6, height: 6, borderRadius: 3,
                  background: i===idx ? "#FFE600" : "rgba(255,255,255,0.35)",
                  border:"none", cursor:"pointer", padding:0,
                  transition:"all .3s cubic-bezier(.22,1,.36,1)",
                }}/>
            ))}
          </div>
        </div>

        {/* Image */}
        <div style={{ width:120, flexShrink:0, overflow:"hidden", position:"relative" }}>
          <img src={img} alt={item.nature} key={`img-${idx}`}
            style={{
              width:"100%", height:"100%", objectFit:"cover",
              animation: anim
                ? `${dir>0?"slideOutLeft":"slideOutRight"} .32s ease forwards`
                : `${dir>0?"slideInRight":"slideInLeft"} .32s ease forwards`,
            }}
            onError={e => { e.currentTarget.style.display="none"; e.currentTarget.parentElement.style.background=bg; }}
          />
          <div style={{ position:"absolute", inset:0,
            background:"linear-gradient(to right, rgba(0,0,0,0.25) 0%, transparent 60%)" }}/>
        </div>

        {/* Contenu texte */}
        <div style={{
          flex:1, minWidth:0, background:"white",
          display:"flex", flexDirection:"column", justifyContent:"center",
          padding:"0 20px", overflow:"hidden", position:"relative",
        }}>
          <div key={`content-${idx}`} style={{
            animation: anim
              ? `${dir>0?"slideOutLeft":"slideOutRight"} .32s ease forwards`
              : `${dir>0?"slideInRight":"slideInLeft"} .32s ease forwards`,
          }}>
            <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:5 }}>
              <span style={{
                fontSize:8.5, fontWeight:800, padding:"2px 9px", borderRadius:20,
                background:bg, color, border:`1px solid ${color}25`,
                textTransform:"uppercase", letterSpacing:".6px",
              }}>
                {item.nature}
              </span>
              <span style={{ fontSize:9, color:"#BABAC8", fontWeight:600 }}>{item.date}</span>
            </div>
            <div style={{ fontSize:13, fontWeight:800, color:"#1E1E28", lineHeight:1.4,
              marginBottom:4,
              display:"-webkit-box", WebkitLineClamp:1, WebkitBoxOrient:"vertical", overflow:"hidden" }}>
              {item.titre}
            </div>
            <div style={{ fontSize:10.5, color:"#6B6B80", lineHeight:1.5,
              display:"-webkit-box", WebkitLineClamp:1, WebkitBoxOrient:"vertical", overflow:"hidden" }}>
              {item.resume}
            </div>
          </div>

          {/* Barre de progression */}
          <div style={{ position:"absolute", bottom:0, left:0, right:0, height:2, background:"#F0F0F5" }}>
            <div key={`prog-${idx}`} style={{
              height:"100%", background:`linear-gradient(to right, ${color}, #C8102E)`,
              animation:`progress ${INTERVAL}ms linear forwards`,
            }}/>
          </div>
        </div>

        {/* Flèches nav */}
        <div style={{
          width:50, flexShrink:0, background:"#FAFAFA",
          borderLeft:"1px solid #F0F0F5",
          display:"flex", flexDirection:"column",
        }}>
          {[{fn:prev,d:"M9 12L5 8l4-4"},{fn:next,d:"M5 4l4 4-4 4"}].map(({fn,d},i)=>(
            <button key={i} onClick={fn}
              style={{
                flex:1, border:"none", background:"none", cursor:"pointer",
                display:"flex", alignItems:"center", justifyContent:"center",
                borderBottom: i===0 ? "1px solid #F0F0F5" : "none",
                transition:"background .15s",
              }}
              onMouseEnter={e=>e.currentTarget.style.background="#F0F0F5"}
              onMouseLeave={e=>e.currentTarget.style.background="none"}
            >
              <svg viewBox="0 0 14 16" fill="none" stroke="#888" strokeWidth="2" width="12" height="12"
                strokeLinecap="round" strokeLinejoin="round">
                <path d={d}/>
              </svg>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
