import { useState, useRef, useEffect } from "react";

/* Palette sobre "panneau documentaire" — refonte du 2026-08-19 sur demande
   explicite de l'utilisateur ("changez carrément le design du chatbot, il
   doit être amélioré et surtout plus pro") : plus d'accent jaune vif façon
   widget marketing — structure épurée type document/rapport (labels
   "Assistant"/"Vous", accent navy sobre), choisie parmi 3 pistes présentées
   visuellement à l'utilisateur.

   Bulles réintroduites le 2026-08-19 (même jour, retour utilisateur
   ultérieur) : la version "filet + alignement" seule ne suffisait pas à
   distinguer les 2 rôles d'un coup d'œil ("faites une bulle pour Vous et
   une autre pour l'Assistant"). Restent SOBRES (fond teinté léger, pas de
   couleur vive ni d'ombre marquée) pour ne pas retomber dans l'esthétique
   "widget marketing" explicitement rejetée plus haut — juste assez de
   contraste de fond pour séparer visuellement les 2 rôles, en plus de
   l'alignement gauche/droite déjà en place. */
const D = "#0C1B2E", TXT = "#0C1B2E", MUTED = "#8896A8", BORDER = "#DDE2EC", BORDER_LIGHT = "#EEF1F6";
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
                  borderBottom: `2px solid ${D}`,
                  color: TXT, fontWeight: 700, whiteSpace: "nowrap",
                  background: "#F8FAFC",
                }}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.results.map((row, i) => (
              <tr key={i} style={{ borderBottom: `1px solid ${BORDER_LIGHT}`, background: i % 2 === 0 ? "#fff" : "#F8FAFC" }}>
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
              borderBottom: `1px solid ${BORDER_LIGHT}`,
            }}>
              <span style={{
                fontSize: 9, fontWeight: 700,
                color: i < 3 ? "#fff" : MUTED,
                background: i < 3 ? D : "transparent",
                border: i < 3 ? "none" : `1px solid ${BORDER}`,
                width: 18, height: 18, borderRadius: "50%",
                display: "flex", alignItems: "center", justifyContent: "center",
                flexShrink: 0,
              }}>{i + 1}</span>
              <span style={{ flex: 1, fontSize: 11, color: TXT, fontWeight: 600 }}>{label}</span>
              {value != null && (
                <span style={{
                  fontSize: 11, fontWeight: 700, flexShrink: 0,
                  color: D,
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
              <div style={{ flex: 1, height: 6, background: BORDER_LIGHT, borderRadius: 3, overflow: "hidden" }}>
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
            background: "#F8FAFC", borderRadius: 8,
            padding: "7px 10px", border: `1px solid ${BORDER_LIGHT}`,
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
      style={{ fontSize: 12.5, lineHeight: 1.6, whiteSpace: "pre-wrap", color: TXT }}
    />
  );
}

/* ── Bloc de message — style "document" : label Assistant/Vous au-dessus,
   bulle sobre (fond teinté léger, pas de couleur vive) pour distinguer les
   2 rôles au premier coup d'œil, en plus de l'alignement gauche/droite. */
function Msg({ role, text, render, data, suggestions, onSuggest }) {
  const isUser = role === "user";
  const bold = t => (t || "").replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
  return (
    <div style={{ marginBottom: 18, display: "flex", flexDirection: "column", alignItems: isUser ? "flex-end" : "stretch" }}>
      <div style={{
        fontSize: 9.5, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 6,
        width: isUser ? "auto" : "100%",
      }}>
        {isUser ? "Vous" : "Assistant"}
      </div>
      <div style={{
        background: isUser ? "#EEF2F8" : "#F7F8FA",
        border: `1px solid ${isUser ? "#DCE4F0" : BORDER_LIGHT}`,
        borderRadius: 10,
        padding: "9px 13px",
        maxWidth: isUser ? "85%" : "100%", textAlign: isUser ? "right" : "left",
        boxSizing: "border-box",
      }}>
        {isUser
          ? <div dangerouslySetInnerHTML={{ __html: bold(text) }} style={{ fontSize: 12.5, lineHeight: 1.6, color: TXT }}/>
          : <RichContent render={render} data={data} text={text}/>
        }
      </div>
      {!isUser && suggestions?.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
          {suggestions.map((s, i) => (
            <button key={i} onClick={() => onSuggest(s)} style={{
              fontSize: 10.5, padding: "4px 10px", borderRadius: 6,
              border: `1px solid ${BORDER}`,
              background: "#fff", color: MUTED,
              cursor: "pointer", fontFamily: "Barlow,system-ui,sans-serif",
              transition: "background .12s, color .12s, border-color .12s",
            }}
              onMouseEnter={e => { e.currentTarget.style.background = D; e.currentTarget.style.color = "#fff"; e.currentTarget.style.borderColor = D; }}
              onMouseLeave={e => { e.currentTarget.style.background = "#fff"; e.currentTarget.style.color = MUTED; e.currentTarget.style.borderColor = BORDER; }}>
              {s}
            </button>
          ))}
        </div>
      )}
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

  // Déclenchement externe (voir components/KpiOptionsMenu.jsx, action
  // "Expliquer ce chiffre") : un événement window plutôt qu'un contexte
  // React, pour ne rien changer à la façon dont ce composant est monté
  // (aucun Provider ailleurs dans l'arbre) — juste ouvrir le panneau et
  // envoyer la question comme si l'utilisateur l'avait tapée.
  useEffect(() => {
    function onExternalAsk(e) {
      const question = e.detail?.question;
      if (!question) return;
      setOpen(true);
      setTimeout(() => send(question), 150);
    }
    window.addEventListener("kpi:ask-chatbot", onExternalAsk);
    return () => window.removeEventListener("kpi:ask-chatbot", onExternalAsk);
  }, []);

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

  /* ─── FAB — cercle sombre sobre, sans jaune ni image/gif ─── */
  const FAB = (
    <button
      onClick={() => setOpen(o => !o)}
      title="Assistant IA"
      style={{
        position: "fixed", bottom: 28, right: 28, zIndex: 9999,
        width: 54, height: 54, borderRadius: "50%",
        border: "none", cursor: "pointer", padding: 0,
        background: D,
        boxShadow: "0 6px 20px rgba(12,27,46,.30)",
        display: "flex", alignItems: "center", justifyContent: "center",
        transition: "transform .16s cubic-bezier(.34,1.56,.64,1), box-shadow .16s ease",
      }}
      onMouseEnter={e => { e.currentTarget.style.transform = "scale(1.06)"; e.currentTarget.style.boxShadow = "0 8px 26px rgba(12,27,46,.40)"; }}
      onMouseLeave={e => { e.currentTarget.style.transform = "scale(1)"; e.currentTarget.style.boxShadow = "0 6px 20px rgba(12,27,46,.30)"; }}
    >
      {open ? (
        <svg viewBox="0 0 20 20" fill="none" width="18" height="18">
          <path d="M5 5l10 10M15 5L5 15" stroke="#E4E7EC" strokeWidth="2" strokeLinecap="round"/>
        </svg>
      ) : (
        <svg viewBox="0 0 22 22" fill="none" width="20" height="20">
          <path d="M4 6.5a2.5 2.5 0 0 1 2.5-2.5h9A2.5 2.5 0 0 1 18 6.5v6a2.5 2.5 0 0 1-2.5 2.5H9l-4 3.5v-3.5H6.5A2.5 2.5 0 0 1 4 12.5v-6Z"
            stroke="#E4E7EC" strokeWidth="1.6" strokeLinejoin="round"/>
          <circle cx="8" cy="9.3" r="0.9" fill="#E4E7EC"/>
          <circle cx="11" cy="9.3" r="0.9" fill="#E4E7EC"/>
          <circle cx="14" cy="9.3" r="0.9" fill="#E4E7EC"/>
        </svg>
      )}
      {status && (
        <div style={{
          position: "absolute", top: 2, right: 2,
          width: 9, height: 9, borderRadius: "50%",
          background: status === "ok" ? "#22C55E" : status === "warn" ? "#F59E0B" : "#EF4444",
          border: `2px solid ${D}`,
        }}/>
      )}
    </button>
  );

  if (!open) return FAB;

  return (
    <>
      {FAB}
      <div style={{
        position: "fixed", bottom: 90, right: 28, zIndex: 9998,
        width: 380, height: 540,
        borderRadius: 10,
        background: "#fff",
        border: `1px solid ${BORDER}`,
        boxShadow: "0 12px 36px rgba(12,27,46,.16)",
        display: "flex", flexDirection: "column", overflow: "hidden",
        animation: "chatUp .18s ease both",
      }}>
        <style>{`
          @keyframes chatUp {
            from { opacity:0; transform:translateY(16px) scale(.96); }
            to   { opacity:1; transform:translateY(0) scale(1); }
          }
          .chat-input::placeholder { color: #9AA0B0; }
          .chat-scroll::-webkit-scrollbar { width:4px; }
          .chat-scroll::-webkit-scrollbar-track { background:transparent; }
          .chat-scroll::-webkit-scrollbar-thumb { background:${BORDER}; border-radius:4px; }
        `}</style>

        {/* En-tête sobre : point de statut + titre + badge, pas d'icône jaune */}
        <div style={{
          padding: "14px 18px",
          background: "#fff",
          borderBottom: `1px solid ${BORDER_LIGHT}`,
          display: "flex", alignItems: "center", gap: 10, flexShrink: 0,
        }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%", flexShrink: 0,
            background: status === "ok" ? "#22C55E" : status === "warn" ? "#F59E0B" : "#EF4444",
          }}/>
          <div style={{ fontSize: 13, fontWeight: 600, color: TXT }}>
            Assistant marché
          </div>
          <span style={{
            marginLeft: "auto", fontSize: 9, fontWeight: 700, color: MUTED,
            textTransform: "uppercase", letterSpacing: ".4px",
            border: `1px solid ${BORDER}`, borderRadius: 5, padding: "2px 6px",
            whiteSpace: "nowrap",
          }}>
            FS Market Intelligence
          </span>
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
              background: "none", border: "none",
              cursor: "pointer", padding: "2px 4px",
              color: MUTED, fontSize: 14, flexShrink: 0,
            }}>
            ↺
          </button>
        </div>

        {/* Messages */}
        <div className="chat-scroll" style={{ flex: 1, overflowY: "auto", padding: "16px 18px 6px", background: "#fff" }}>
          {msgs.map((m, i) => (
            <Msg key={i} role={m.role} text={m.text}
              render={m.render} data={m.data}
              suggestions={m.suggestions} onSuggest={send}/>
          ))}
          {loading && (
            <div style={{ display: "flex", gap: 5, padding: "6px 0", alignItems: "center" }}>
              {[0, 1, 2].map(i => (
                <div key={i} style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: D, opacity: .45,
                  animation: `dot .9s ${i * .18}s infinite ease-in-out`,
                }}/>
              ))}
              <style>{`@keyframes dot{0%,80%,100%{transform:translateY(0);opacity:.45}40%{transform:translateY(-6px);opacity:.9}}`}</style>
            </div>
          )}
          <div ref={bottomRef}/>
        </div>

        {/* Zone de saisie */}
        <div style={{ padding: "12px 14px 16px", borderTop: `1px solid ${BORDER_LIGHT}`, flexShrink: 0, background: "#fff" }}>
          <div style={{
            display: "flex", gap: 8, alignItems: "center",
            border: `1px solid ${BORDER}`, borderRadius: 8,
            padding: "9px 9px 9px 14px",
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
                width: 26, height: 26, borderRadius: 6, border: "none",
                cursor: input.trim() ? "pointer" : "default",
                background: input.trim() ? D : BORDER,
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "background .15s", flexShrink: 0,
              }}>
              <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
                <path d="M14 8L3 3l2.5 5L3 13l11-5z" fill={input.trim() ? "#fff" : "#9AA0B0"}/>
              </svg>
            </button>
          </div>
          <div style={{ fontSize: 9, color: "#9AA0B0", textAlign: "center", marginTop: 8, fontFamily: "Barlow,system-ui,sans-serif" }}>
            MarketInsurance.db · Groq LLM · 2015–2024
          </div>
        </div>
      </div>
    </>
  );
}
