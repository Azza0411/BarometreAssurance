import { useState, useRef, useEffect } from "react";

const D = "#2E2E38", Y = "#FFE600", TXT = "#0C1B2E", MUTED = "#5C5C6E";
const CHATBOT_API = (import.meta.env.VITE_CHATBOT_URL ?? "http://localhost:5001") + "/api/chatbot";

// Session ID unique par onglet navigateur
const SESSION_ID = crypto.randomUUID();

/* ── Rendu rich selon le type retourné par le backend ────────────────────── */
function RichContent({ render, data, text }) {
  const bold = t => (t || "").replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");

  if (render === "table" && data?.results?.length) {
    const cols = Object.keys(data.results[0]);
    return (
      <div style={{ overflowX: "auto", maxWidth: "100%" }}>
        <table style={{ borderCollapse: "collapse", fontSize: 10.5, width: "100%" }}>
          <thead>
            <tr>
              {cols.map(c => (
                <th key={c} style={{
                  padding: "5px 8px", textAlign: "left",
                  borderBottom: `2px solid ${Y}`,
                  color: TXT, fontWeight: 700, whiteSpace: "nowrap",
                  background: "#F2F5FB",
                }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.results.map((row, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #DDE2EC", background: i % 2 === 0 ? "#fff" : "#F8F9FB" }}>
                {cols.map(c => (
                  <td key={c} style={{ padding: "4px 8px", color: TXT }}>
                    {row[c] ?? "—"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (render === "ranking" && data?.results?.length) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {data.results.slice(0, 10).map((r, i) => {
          const label = r.entreprise || r.compagnie || r.code || Object.values(r)[0];
          const value = r.pdm_pct || r.primes || r.valeur || Object.values(r)[1];
          return (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "4px 0",
              borderBottom: "1px solid #DDE2EC",
            }}>
              <span style={{
                fontSize: 10, fontWeight: 700,
                color: i < 3 ? D : MUTED,
                background: i < 3 ? Y : "transparent",
                width: 18, height: 18, borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0, fontSize: 9,
              }}>{i + 1}</span>
              <span style={{ flex: 1, fontSize: 11, color: TXT, fontWeight: 600 }}>{label}</span>
              {value != null && (
                <span style={{
                  fontSize: 11, fontWeight: 700, flexShrink: 0,
                  background: D, color: Y,
                  padding: "2px 7px", borderRadius: 6,
                }}>
                  {typeof value === "number" ? value.toFixed(1) : value}
                  {r.pdm_pct != null ? "%" : ""}
                </span>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  if (render === "evolution" && data?.results?.length) {
    const vals = data.results.map(r => r.valeur || r.primes || Object.values(r)[1] || 0).filter(Number.isFinite);
    const maxV = Math.max(...vals, 1);
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {data.results.map((r, i) => {
          const yr = r.annee || Object.values(r)[0];
          const val = r.valeur || r.primes || Object.values(r)[1];
          const pct = Math.round((val / maxV) * 100);
          return (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ fontSize: 10, color: MUTED, width: 34, flexShrink: 0, fontWeight: 600 }}>{yr}</span>
              <div style={{ flex: 1, height: 6, background: "#DDE2EC", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ width: `${pct}%`, height: "100%", background: D, borderRadius: 3 }}/>
              </div>
              <span style={{ fontSize: 10, color: TXT, width: 54, flexShrink: 0, textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>
                {typeof val === "number" ? val.toLocaleString("fr-FR", { maximumFractionDigits: 1 }) : val}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  if (render === "kpi_cards" && data?.results?.length) {
    const row = data.results[0];
    const entries = Object.entries(row).filter(([k]) => k !== "entreprise" && k !== "annee");
    return (
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {entries.slice(0, 8).map(([k, v]) => (
          <div key={k} style={{
            background: "#F2F5FB", borderRadius: 8,
            padding: "7px 10px", border: "1px solid #DDE2EC",
          }}>
            <div style={{ fontSize: 9, color: MUTED, textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 600 }}>{k}</div>
            <div style={{ fontSize: 13, fontWeight: 800, color: D, marginTop: 2 }}>
              {v != null ? (typeof v === "number" ? v.toLocaleString("fr-FR", { maximumFractionDigits: 2 }) : v) : "—"}
            </div>
          </div>
        ))}
      </div>
    );
  }

  // Fallback : texte markdown
  return (
    <div
      dangerouslySetInnerHTML={{ __html: bold(text) }}
      style={{ fontSize: 12, lineHeight: 1.58, whiteSpace: "pre-wrap", color: TXT }}
    />
  );
}

/* ── Bulle de message ────────────────────────────────────────────────────── */
function Msg({ role, text, render, data, suggestions, onSuggest }) {
  const isUser = role === "user";
  const bold = t => (t || "").replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
  return (
    <div style={{ display: "flex", justifyContent: isUser ? "flex-end" : "flex-start", marginBottom: 10, gap: 8, alignItems: "flex-end" }}>
      {!isUser && (
        <div style={{
          width: 26, height: 26, borderRadius: "50%", flexShrink: 0,
          background: `linear-gradient(135deg,${Y} 0%,#C8A000 100%)`,
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 2px 8px rgba(255,200,0,.4)",
        }}>
          <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
            <circle cx="8" cy="8" r="2.5" fill={D}/>
            <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41"
              stroke={D} strokeWidth="1.4" strokeLinecap="round"/>
          </svg>
        </div>
      )}
      <div style={{ maxWidth: "85%", display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{
          padding: "9px 13px",
          borderRadius: isUser ? "16px 16px 4px 16px" : "4px 16px 16px 16px",
          background: isUser
            ? `linear-gradient(135deg,${D} 0%,#1A1A26 100%)`
            : "#FFFFFF",
          color: isUser ? "#fff" : TXT,
          border: isUser ? "none" : "1px solid #DDE2EC",
          boxShadow: isUser ? "0 2px 12px rgba(0,0,0,.18)" : "0 1px 4px rgba(0,0,0,.06)",
        }}>
          {isUser
            ? <div dangerouslySetInnerHTML={{ __html: bold(text) }} style={{ fontSize: 12, lineHeight: 1.58 }}/>
            : <RichContent render={render} data={data} text={text}/>
          }
        </div>
        {/* Suggestions cliquables */}
        {!isUser && suggestions?.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4, paddingLeft: 4 }}>
            {suggestions.map((s, i) => (
              <button key={i} onClick={() => onSuggest(s)} style={{
                fontSize: 10, padding: "3px 9px", borderRadius: 12,
                border: `1px solid ${D}22`,
                background: "#F2F5FB", color: MUTED,
                cursor: "pointer", fontFamily: "Barlow,system-ui,sans-serif",
              }}
                onMouseEnter={e => { e.target.style.background = D; e.target.style.color = Y; }}
                onMouseLeave={e => { e.target.style.background = "#F2F5FB"; e.target.style.color = MUTED; }}>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ══ CHATBOT ══════════════════════════════════════════════════════════════════ */
export default function Chatbot() {
  const [open,    setOpen]    = useState(false);
  const [msgs,    setMsgs]    = useState([]);
  const [input,   setInput]   = useState("");
  const [loading, setLoading] = useState(false);
  const [status,  setStatus]  = useState(null);
  const bottomRef = useRef(null);
  const inputRef  = useRef(null);

  useEffect(() => {
    fetch(`${CHATBOT_API}/status`)
      .then(r => r.json())
      .then(d => setStatus(d.llm_available ? "ok" : "warn"))
      .catch(() => setStatus("error"));

    fetch(`${CHATBOT_API}/greet`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: SESSION_ID }),
    })
      .then(r => r.json())
      .then(d => setMsgs([{
        role: "assistant",
        text: d.text,
        suggestions: d.suggestions,
        render: d.render || "text",
      }]))
      .catch(() => setMsgs([{
        role: "assistant",
        text: "Bonjour ! Je suis votre assistant spécialisé dans le marché des assurances tunisien.\n\nPosez-moi n'importe quelle question sur les compagnies, KPIs, classements ou prévisions.",
        suggestions: ["Part de marché de STAR en 2023 ?", "Top 5 compagnies 2023 ?", "Prévision primes COMAR 2026 ?"],
        render: "text",
      }]));
  }, []);

  useEffect(() => {
    if (open) {
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [msgs, open]);

  async function send(text) {
    const q = (text || input).trim();
    if (!q || loading) return;
    setInput("");
    setMsgs(m => [...m, { role: "user", text: q }]);
    setLoading(true);

    try {
      const res = await fetch(CHATBOT_API, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: q, session_id: SESSION_ID }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const d = await res.json();
      setMsgs(m => [...m, {
        role: "assistant",
        text: d.text || "Réponse reçue.",
        render: d.render || "text",
        data: d.data,
        suggestions: d.suggestions,
      }]);
    } catch {
      setMsgs(m => [...m, {
        role: "assistant",
        text: "Le backend du chatbot est inaccessible. Vérifiez que `python app.py` tourne sur le port 5001.",
        render: "text",
      }]);
    }
    setLoading(false);
  }

  /* ─── FAB ─── */
  const FAB = (
    <button
      onClick={() => setOpen(o => !o)}
      title="Assistant IA"
      style={{
        position: "fixed", bottom: 28, right: 28, zIndex: 9999,
        width: 100, height: 100, borderRadius: "50%",
        border: "none", cursor: "pointer", padding: 0,
        background: "transparent", overflow: "visible",
        boxShadow: "none",
        display: "flex", alignItems: "center", justifyContent: "center",
        transition: "transform .2s cubic-bezier(.34,1.56,.64,1)",
      }}
      onMouseEnter={e => e.currentTarget.style.transform = "scale(1.06)"}
      onMouseLeave={e => e.currentTarget.style.transform = "scale(1)"}
    >
      <div style={{
        position: "absolute", width: 52, height: 52, borderRadius: "50%",
        background: "#00695C",
        border: "3px solid #00897B",
        boxShadow: "0 4px 18px rgba(0,105,92,.55), 0 0 0 2px rgba(0,137,123,.28)",
        zIndex: 0,
      }}/>
      <img
        src={open ? "/images/gif 8.webp" : "/images/gif 9.gif"}
        alt="Assistant IA"
        style={{ width: 100, height: 100, objectFit: "cover", borderRadius: "50%", display: "block", position: "relative", zIndex: 1 }}
      />
      {status && (
        <div style={{
          position: "absolute", top: 6, right: 6, zIndex: 2,
          width: 10, height: 10, borderRadius: "50%",
          background: status === "ok" ? "#22C55E" : status === "warn" ? Y : "#EF4444",
          border: "2px solid #00695C",
          boxShadow: `0 0 6px ${status === "ok" ? "#22C55E" : status === "warn" ? Y : "#EF4444"}`,
        }}/>
      )}
    </button>
  );

  if (!open) return FAB;

  return (
    <>
      {FAB}
      <div style={{
        position: "fixed", bottom: 96, right: 28, zIndex: 9998,
        width: 380, height: 540,
        borderRadius: 18,
        background: "#F2F5FB",
        border: "1px solid #DDE2EC",
        boxShadow: "0 20px 60px rgba(0,0,0,.18), 0 4px 16px rgba(0,0,0,.08)",
        display: "flex", flexDirection: "column", overflow: "hidden",
        animation: "chatUp .22s cubic-bezier(.34,1.3,.64,1) both",
      }}>
        <style>{`
          @keyframes chatUp {
            from { opacity:0; transform:translateY(16px) scale(.96); }
            to   { opacity:1; transform:translateY(0) scale(1); }
          }
          .chat-input::placeholder { color: #9AA0B0; }
          .chat-scroll::-webkit-scrollbar { width:4px; }
          .chat-scroll::-webkit-scrollbar-track { background:transparent; }
          .chat-scroll::-webkit-scrollbar-thumb { background:#DDE2EC; border-radius:4px; }
        `}</style>

        {/* Header EY */}
        <div style={{
          padding: "13px 16px 11px",
          background: D,
          borderBottom: `3px solid ${Y}`,
          display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
        }}>
          <div style={{
            width: 34, height: 34, borderRadius: 10, flexShrink: 0,
            background: `linear-gradient(135deg,${Y} 0%,#C8A000 100%)`,
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 2px 10px rgba(200,160,0,.4)",
          }}>
            <svg viewBox="0 0 20 20" fill="none" width="16" height="16">
              <circle cx="10" cy="10" r="3" fill={D}/>
              <path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.22 4.22l1.41 1.41M14.37 14.37l1.41 1.41M4.22 15.78l1.41-1.41M14.37 5.63l1.41-1.41"
                stroke={D} strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 800, color: "#fff", letterSpacing: "-.2px", lineHeight: 1.2 }}>
              Assistant IA
            </div>
            <div style={{ fontSize: 9.5, color: `${Y}AA`, fontWeight: 600, marginTop: 1 }}>
              FS Market Intelligence · EY
            </div>
          </div>
          <div style={{ marginLeft: "auto" }}>
            <button
              title="Nouvelle conversation"
              onClick={() => {
                fetch(`${CHATBOT_API}/reset`, {
                  method: "POST",
                  headers: { "Content-Type": "application/json" },
                  body: JSON.stringify({ session_id: SESSION_ID }),
                });
                setMsgs([{
                  role: "assistant",
                  text: "Conversation réinitialisée. Comment puis-je vous aider ?",
                  render: "text",
                }]);
              }}
              style={{
                background: "rgba(255,255,255,.1)", border: "none",
                borderRadius: 6, cursor: "pointer", padding: "4px 8px",
                color: "rgba(255,255,255,.6)", fontSize: 14,
              }}>
              ↺
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="chat-scroll" style={{ flex: 1, overflowY: "auto", padding: "14px 14px 6px", background: "#F2F5FB" }}>
          {msgs.map((m, i) => (
            <Msg key={i} role={m.role} text={m.text}
              render={m.render} data={m.data}
              suggestions={m.suggestions} onSuggest={send}/>
          ))}
          {loading && (
            <div style={{ display: "flex", gap: 5, padding: "6px 4px", alignItems: "center" }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 7, height: 7, borderRadius: "50%",
                  background: D, opacity: .5,
                  animation: `dot .9s ${i * .18}s infinite ease-in-out`,
                }}/>
              ))}
              <style>{`@keyframes dot{0%,80%,100%{transform:translateY(0);opacity:.5}40%{transform:translateY(-7px);opacity:1}}`}</style>
            </div>
          )}
          <div ref={bottomRef}/>
        </div>

        {/* Zone de saisie */}
        <div style={{ padding: "8px 12px 13px", borderTop: "1px solid #DDE2EC", flexShrink: 0, background: "#fff" }}>
          <div style={{
            display: "flex", gap: 8, alignItems: "center",
            background: "#F2F5FB", borderRadius: 12,
            padding: "7px 7px 7px 12px",
            border: "1px solid #DDE2EC",
          }}>
            <input
              ref={inputRef}
              className="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && !e.shiftKey && send()}
              placeholder="Posez votre question…"
              style={{
                flex: 1, background: "none", border: "none", outline: "none",
                color: TXT, fontSize: 12, fontFamily: "Barlow,system-ui,sans-serif",
              }}
            />
            <button
              onClick={() => send()}
              disabled={!input.trim() || loading}
              style={{
                width: 30, height: 30, borderRadius: 8, border: "none",
                cursor: input.trim() ? "pointer" : "default",
                background: input.trim()
                  ? `linear-gradient(135deg,${Y},#C8A000)`
                  : "#DDE2EC",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all .15s", flexShrink: 0,
              }}>
              <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
                <path d="M14 8L3 3l2.5 5L3 13l11-5z" fill={input.trim() ? D : "#9AA0B0"}/>
              </svg>
            </button>
          </div>
          <div style={{ fontSize: 9, color: "#9AA0B0", textAlign: "center", marginTop: 6, fontFamily: "Barlow,system-ui,sans-serif" }}>
            MarketInsurance.db · Groq LLM · 2015–2024
          </div>
        </div>
      </div>
    </>
  );
}
