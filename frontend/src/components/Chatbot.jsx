import { useState, useRef, useEffect } from "react";

const D = "#2E2E38", Y = "#FFE600", G = "#747480";
const API = "http://localhost:8002";

/* ── Charge les données du marché (dernière année disponible) ── */
async function fetchContext() {
  try {
    // 1. Récupérer la liste des années disponibles
    const anneesResp = await fetch(`${API}/api/apercu-marche/annees`);
    const annees = anneesResp.ok ? await anneesResp.json() : [];
    const annee = annees.length ? Math.max(...annees) : 2024;

    // 2. Trouver la dernière année avec des données réelles (classement non vide)
    let activeAnnee = annee;
    for (const a of annees.sort((x,y) => y-x)) {
      const cl = await fetch(`${API}/api/classement-compagnies?annee=${a}`).then(r => r.ok ? r.json() : []).catch(() => []);
      if (cl && cl.length > 0) { activeAnnee = a; break; }
    }

    // 3. Charger profil + classement pour l'année active
    const [profil, classement] = await Promise.allSettled([
      fetch(`${API}/api/apercu-marche/profil-pays?annee=${activeAnnee}`).then(r => r.ok ? r.json() : null),
      fetch(`${API}/api/classement-compagnies?annee=${activeAnnee}`).then(r => r.ok ? r.json() : null),
    ]);
    return {
      profil:     profil.status     === "fulfilled" ? profil.value     : null,
      classement: classement.status === "fulfilled" ? classement.value : null,
      annee: activeAnnee,
    };
  } catch { return { annee: 2024 }; }
}

/* ── Prompt système enrichi ── */
function buildSystemPrompt(ctx) {
  const pp  = ctx.profil    || {};
  const cl  = (ctx.classement || []);
  const an  = ctx.annee     || 2024;
  const leaders = cl.slice(0,5).map((c,i)=>`#${i+1} ${c.entreprise}: ${c.pdm_pct}%PDM`).join(", ");

  return `Tu es un expert analytique du marché des assurances en Tunisie, intégré dans la plateforme FS Market Intelligence (EY).

DONNÉES MARCHÉ ${an} :
- Total primes: ${pp.total_primes_emises_mdt ? pp.total_primes_emises_mdt.toFixed(0)+" MDT" : "n/d"}
- Taux pénétration: ${pp.taux_penetration_pct ? pp.taux_penetration_pct.toFixed(2)+"%" : "n/d"}
- Densité: ${pp.densite_tnd ? pp.densite_tnd.toFixed(0)+" TND/hab" : "n/d"}
- Nb assureurs: ${pp.nb_assureurs || "n/d"}
- Classement PDM: ${leaders || "n/d"}

RÈGLES:
- Réponds TOUJOURS en français, de façon experte et concise (2-3 phrases max sauf si détail demandé)
- Cite les données chiffrées disponibles
- Si données absentes, dis-le et oriente vers la page correspondante de la plateforme
- Tu peux faire des analyses, comparaisons et projections qualitatives`;
}

/* ── Réponses locales rapides (pas besoin d'API IA) ── */
function localAnswer(q, ctx) {
  const lq  = q.toLowerCase();
  const cl  = ctx.classement || [];
  const pp  = ctx.profil    || {};
  const an  = ctx.annee     || 2024;

  const has = (...kw) => kw.some(k => lq.includes(k));

  if (has("leader","premier","#1","numéro 1","n°1","meilleur")) {
    const t = cl[0];
    return t ? `**${t.entreprise}** est le leader du marché tunisien avec **${t.pdm_pct}%** de part de marché en ${an}.` : null;
  }
  if (has("top 3","top3","trois premier","podium")) {
    const t3 = cl.slice(0,3);
    return t3.length ? `🏆 Podium ${an} :\n1. **${t3[0]?.entreprise}** — ${t3[0]?.pdm_pct}%\n2. **${t3[1]?.entreprise}** — ${t3[1]?.pdm_pct}%\n3. **${t3[2]?.entreprise}** — ${t3[2]?.pdm_pct}%` : null;
  }
  if (has("pénétration","penetration")) {
    return pp.taux_penetration_pct
      ? `Le taux de pénétration est **${pp.taux_penetration_pct.toFixed(2)}%** du PIB en ${an}. La moyenne mondiale est ~7%, ce qui illustre le fort potentiel de croissance du secteur tunisien.`
      : null;
  }
  if (has("densité","densite")) {
    return pp.densite_tnd ? `La densité d'assurance s'élève à **${pp.densite_tnd.toFixed(0)} TND/habitant** en ${an}.` : null;
  }
  if (has("taille","total","primes","marché") && !has("ratio","combine","sinistralité")) {
    return pp.total_primes_emises_mdt
      ? `Le marché des assurances tunisien totalise **${pp.total_primes_emises_mdt.toFixed(0)} MDT** de primes émises en ${an}.`
      : null;
  }
  if (has("combien","nombre","assureur","compagnie")) {
    return pp.nb_assureurs ? `Il y a **${pp.nb_assureurs} compagnies d'assurance** actives sur le marché tunisien en ${an}.` : null;
  }
  // Compagnie spécifique
  for (const c of cl) {
    if (lq.includes(c.entreprise.toLowerCase())) {
      const rank = cl.indexOf(c) + 1;
      return `**${c.entreprise}** est classée **#${rank}** avec **${c.pdm_pct}%** de PDM en ${an}.`;
    }
  }
  return null;
}

const SUGGESTIONS = [
  "Qui est le leader du marché ?",
  "Top 3 des assureurs tunisiens ?",
  "Quel est le taux de pénétration ?",
  "Taille du marché en MDT ?",
];

/* ── Rendu d'un message ── */
function Msg({ role, text }) {
  const isUser = role === "user";
  // Rend **bold** → <b>
  const rendered = text.replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
  return (
    <div style={{ display:"flex", justifyContent: isUser?"flex-end":"flex-start", marginBottom:10, gap:8, alignItems:"flex-end" }}>
      {!isUser && (
        <div style={{ width:26, height:26, borderRadius:"50%", flexShrink:0,
          background:`linear-gradient(135deg,${Y} 0%,#C8A000 100%)`,
          display:"flex", alignItems:"center", justifyContent:"center",
          boxShadow:"0 2px 8px rgba(255,200,0,.4)" }}>
          <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
            <circle cx="8" cy="8" r="2.5" fill={D}/>
            <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke={D} strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
        </div>
      )}
      <div
        dangerouslySetInnerHTML={{ __html: rendered }}
        style={{
          maxWidth:"80%", padding:"9px 13px",
          borderRadius: isUser ? "16px 16px 4px 16px" : "4px 16px 16px 16px",
          background: isUser
            ? "linear-gradient(135deg,#2E2E38 0%,#1A1A26 100%)"
            : "rgba(255,255,255,0.93)",
          color: isUser ? "#fff" : D,
          fontSize:12, lineHeight:1.58,
          border: isUser ? "none" : "1px solid rgba(46,46,56,.08)",
          boxShadow: isUser ? "0 2px 12px rgba(0,0,0,.22)" : "0 2px 8px rgba(0,0,0,.06)",
          whiteSpace:"pre-wrap",
        }}
      />
    </div>
  );
}

/* ══ CHATBOT ══════════════════════════════════════════════════════════════════ */
export default function Chatbot() {
  const [open,    setOpen]    = useState(false);
  const [msgs,    setMsgs]    = useState([{
    role:"assistant",
    text:"Bonjour ! Je suis votre assistant IA spécialisé dans le marché des assurances tunisien.\n\nPosez-moi n'importe quelle question sur les données de la plateforme.",
  }]);
  const [input,   setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const [ctx,     setCtx]     = useState({});
  const [ctxReady,setCtxReady]= useState(false);
  const bottomRef = useRef(null);
  const inputRef  = useRef(null);

  useEffect(() => {
    fetchContext().then(data => { setCtx(data); setCtxReady(true); });
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior:"smooth" }), 50);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [msgs, open]);

  async function send(text) {
    const q = (text || input).trim();
    if (!q || loading) return;
    setInput("");
    const newMsgs = [...msgs, { role:"user", text:q }];
    setMsgs(newMsgs);
    setLoading(true);

    await new Promise(r => setTimeout(r, 250));

    // Tentative réponse locale
    const local = localAnswer(q, ctx);
    if (local) {
      setMsgs(m => [...m, { role:"assistant", text:local }]);
      setLoading(false);
      return;
    }

    // Appel Claude Haiku
    const key = import.meta.env.VITE_ANTHROPIC_KEY || "";
    if (!key) {
      setMsgs(m => [...m, { role:"assistant", text:"Clé API non configurée (VITE_ANTHROPIC_KEY). Consultez les graphiques de la plateforme pour accéder aux données." }]);
      setLoading(false);
      return;
    }

    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method:"POST",
        headers:{
          "Content-Type":"application/json",
          "x-api-key": key,
          "anthropic-version":"2023-06-01",
          "anthropic-dangerous-direct-browser-access":"true",
        },
        body: JSON.stringify({
          model:"claude-haiku-4-5-20251001",
          max_tokens:400,
          system: buildSystemPrompt(ctx),
          messages: newMsgs.slice(-10).map(m => ({ role:m.role, content:m.text })),
        }),
      });
      if (!res.ok) throw new Error(res.status);
      const data = await res.json();
      setMsgs(m => [...m, { role:"assistant", text: data.content?.[0]?.text || "Réponse indisponible." }]);
    } catch(e) {
      setMsgs(m => [...m, { role:"assistant", text:"Impossible de contacter l'assistant IA. Vérifiez votre connexion ou la clé API." }]);
    }
    setLoading(false);
  }

  /* ─── FAB ─── */
  const FAB = (
    <button
      onClick={() => setOpen(o => !o)}
      title="Assistant IA"
      style={{
        position:"fixed", bottom:28, right:28, zIndex:9999,
        width:56, height:56, borderRadius:"50%", border:"none", cursor:"pointer",
        background: open
          ? "linear-gradient(135deg,#3A3A4A 0%,#2E2E38 100%)"
          : `linear-gradient(135deg,${Y} 0%,#C8A000 50%,#8B6E00 100%)`,
        boxShadow: open
          ? "0 4px 20px rgba(46,46,56,.5)"
          : "0 4px 20px rgba(200,160,0,.5), 0 0 0 6px rgba(255,230,0,.12)",
        display:"flex", alignItems:"center", justifyContent:"center",
        transition:"all .25s cubic-bezier(.34,1.56,.64,1)",
        transform: open ? "rotate(45deg)" : "scale(1)",
      }}
    >
      {open ? (
        <svg viewBox="0 0 20 20" fill="none" width="20" height="20">
          <path d="M5 5l10 10M15 5L5 15" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ) : (
        <svg viewBox="0 0 20 20" fill="none" width="20" height="20">
          <path d="M4 6h12M4 10h8M4 14h10" stroke={D} strokeWidth="1.8" strokeLinecap="round"/>
          <circle cx="16" cy="14" r="3" fill={D}/>
          <circle cx="16" cy="14" r="1" fill={Y}/>
        </svg>
      )}
    </button>
  );

  if (!open) return FAB;

  return (
    <>
      {FAB}
      <div style={{
        position:"fixed", bottom:96, right:28, zIndex:9998,
        width:360, height:500,
        borderRadius:18,
        background:"linear-gradient(160deg,#1C1C26 0%,#252535 60%,#2A2A3C 100%)",
        border:"1px solid rgba(255,230,0,.14)",
        boxShadow:"0 20px 60px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.04) inset",
        display:"flex", flexDirection:"column", overflow:"hidden",
        animation:"chatUp .22s cubic-bezier(.34,1.3,.64,1) both",
      }}>
        <style>{`
          @keyframes chatUp {
            from { opacity:0; transform:translateY(16px) scale(.96); }
            to   { opacity:1; transform:translateY(0) scale(1); }
          }
          .chat-input::placeholder { color:rgba(255,255,255,.25); }
          .chat-scroll::-webkit-scrollbar { width:4px; }
          .chat-scroll::-webkit-scrollbar-track { background:transparent; }
          .chat-scroll::-webkit-scrollbar-thumb { background:rgba(255,255,255,.1); border-radius:4px; }
        `}</style>

        {/* Header */}
        <div style={{
          padding:"13px 16px 11px",
          borderBottom:"1px solid rgba(255,255,255,.06)",
          display:"flex", alignItems:"center", gap:10, flexShrink:0,
        }}>
          <div style={{
            width:34, height:34, borderRadius:10, flexShrink:0,
            background:`linear-gradient(135deg,${Y} 0%,#C8A000 100%)`,
            display:"flex", alignItems:"center", justifyContent:"center",
            boxShadow:"0 2px 10px rgba(200,160,0,.4)",
          }}>
            <svg viewBox="0 0 20 20" fill="none" width="16" height="16">
              <circle cx="10" cy="10" r="3" fill={D}/>
              <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.41 1.41M14.37 14.37l1.41 1.41M4.22 15.78l1.41-1.41M14.37 5.63l1.41-1.41" stroke={D} strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize:13, fontWeight:800, color:"#fff", letterSpacing:"-.2px", lineHeight:1.2 }}>
              Assistant IA
            </div>
            <div style={{ fontSize:9.5, color:"rgba(255,230,0,.65)", fontWeight:600, marginTop:1 }}>
              FS Market Intelligence · EY
            </div>
          </div>
          <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:5 }}>
            {!ctxReady && (
              <div style={{ fontSize:9, color:"rgba(255,255,255,.35)" }}>Chargement données…</div>
            )}
            {ctxReady && (
              <div style={{ fontSize:9, color:"rgba(255,255,255,.35)" }}>Données {ctx.annee}</div>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="chat-scroll" style={{ flex:1, overflowY:"auto", padding:"14px 14px 6px" }}>
          {msgs.map((m,i) => <Msg key={i} role={m.role} text={m.text}/>)}
          {loading && (
            <div style={{ display:"flex", gap:5, padding:"6px 4px", alignItems:"center" }}>
              {[0,1,2].map(i => (
                <div key={i} style={{
                  width:7, height:7, borderRadius:"50%",
                  background:Y, opacity:.6,
                  animation:`dot .9s ${i*.18}s infinite ease-in-out`,
                }}/>
              ))}
              <style>{`@keyframes dot{0%,80%,100%{transform:translateY(0);opacity:.6}40%{transform:translateY(-7px);opacity:1}}`}</style>
            </div>
          )}
          <div ref={bottomRef}/>
        </div>

        {/* Suggestions (seulement au départ) */}
        {msgs.length <= 1 && (
          <div style={{ padding:"4px 14px 8px", display:"flex", flexWrap:"wrap", gap:5 }}>
            {SUGGESTIONS.map(s => (
              <button key={s} onClick={() => send(s)} style={{
                fontSize:10, padding:"4px 10px", borderRadius:14,
                border:"1px solid rgba(255,230,0,.2)",
                background:"rgba(255,230,0,.06)", color:"rgba(255,255,255,.65)",
                cursor:"pointer", fontFamily:"Barlow,system-ui,sans-serif",
                transition:"all .12s",
              }}
              onMouseEnter={e=>{ e.target.style.background="rgba(255,230,0,.15)"; e.target.style.color=Y; }}
              onMouseLeave={e=>{ e.target.style.background="rgba(255,230,0,.06)"; e.target.style.color="rgba(255,255,255,.65)"; }}>
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Zone de saisie */}
        <div style={{ padding:"8px 12px 13px", borderTop:"1px solid rgba(255,255,255,.06)", flexShrink:0 }}>
          <div style={{
            display:"flex", gap:8, alignItems:"center",
            background:"rgba(255,255,255,.05)", borderRadius:12,
            padding:"7px 7px 7px 12px",
            border:"1px solid rgba(255,255,255,.09)",
          }}>
            <input
              ref={inputRef}
              className="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
              placeholder="Votre question…"
              style={{
                flex:1, background:"none", border:"none", outline:"none",
                color:"#fff", fontSize:12, fontFamily:"Barlow,system-ui,sans-serif",
              }}
            />
            <button
              onClick={() => send()}
              disabled={!input.trim() || loading}
              style={{
                width:30, height:30, borderRadius:8, border:"none",
                cursor: input.trim() ? "pointer" : "default",
                background: input.trim()
                  ? `linear-gradient(135deg,${Y},#C8A000)`
                  : "rgba(255,255,255,.07)",
                display:"flex", alignItems:"center", justifyContent:"center",
                transition:"all .15s", flexShrink:0,
              }}
            >
              <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
                <path d="M14 8L3 3l2.5 5L3 13l11-5z" fill={input.trim() ? D : "rgba(255,255,255,.25)"}/>
              </svg>
            </button>
          </div>
          <div style={{ fontSize:9, color:"rgba(255,255,255,.18)", textAlign:"center", marginTop:6, fontFamily:"Barlow,system-ui,sans-serif" }}>
            Données CGA · CMF · FTUSA · EY Tunisia
          </div>
        </div>
      </div>
    </>
  );
}
