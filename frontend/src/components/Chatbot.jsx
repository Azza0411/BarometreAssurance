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

  if (render === "market_overview" && data?.results?.length) {
    const ov = data.results[0];
    const annee = ov.annee ?? data.annee ?? "—";
    const fmt = (v, dec = 2) => v != null ? Number(v).toLocaleString("fr-FR", { maximumFractionDigits: dec }) : "—";
    const metrics = [
      { label: "Total primes émises", value: ov.total_primes_mdt != null ? `${fmt(ov.total_primes_mdt)} MDT` : "—", accent: true },
      { label: "Taux de pénétration", value: ov.taux_penetration != null ? `${fmt(ov.taux_penetration, 2)} %` : "—", accent: false },
      { label: "Primes Vie", value: ov.primes_vie_mdt != null ? `${fmt(ov.primes_vie_mdt)} MDT` : "—", accent: false },
      { label: "Primes Non-Vie", value: ov.primes_non_vie_mdt != null ? `${fmt(ov.primes_non_vie_mdt)} MDT` : "—", accent: false },
      { label: "Nombre d'assureurs", value: ov.nb_assureurs != null ? fmt(ov.nb_assureurs, 0) : "—", accent: false },
      { label: "Densité assurance", value: ov.densite != null ? `${fmt(ov.densite, 1)} TND/hab.` : "—", accent: false },
    ];
    const bold = t => (t || "").replace(/\*\*(.*?)\*\*/g, "<b>$1</b>");
    return (
      <div>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <div style={{ width: 3, height: 28, background: "#1B6EC2", borderRadius: 2 }} />
          <div>
            <div style={{ fontSize: 11, fontWeight: 800, color: D, letterSpacing: ".3px" }}>
              Marché des assurances tunisien — {annee}
            </div>
            <div style={{ fontSize: 9, color: MUTED, marginTop: 1 }}>Vue d'ensemble macro-économique</div>
          </div>
        </div>
        {/* KPI grid */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6, marginBottom: 10 }}>
          {metrics.map(({ label, value, accent }) => (
            <div key={label} style={{
              borderRadius: 8,
              padding: "8px 10px",
              background: accent ? "#EBF3FB" : "#F8FAFC",
              border: `1px solid ${accent ? "#BEDAF5" : BORDER_LIGHT}`,
            }}>
              <div style={{ fontSize: 8.5, color: MUTED, textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 600, marginBottom: 3 }}>{label}</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: accent ? "#1B6EC2" : D }}>{value}</div>
            </div>
          ))}
        </div>
        {/* LLM narrative */}
        {text && (
          <div style={{
            fontSize: 11.5, color: TXT, lineHeight: 1.65,
            borderTop: `1px solid ${BORDER_LIGHT}`, paddingTop: 8, marginTop: 4,
          }} dangerouslySetInnerHTML={{ __html: bold(text) }} />
        )}
      </div>
    );
  }

  if (render === "explain" && data) {
    const current = data.current;
    const yoy = data.yoy_pct;
    const sAvg = data.sector_avg_display ?? (data.sector_avg != null ? String(data.sector_avg) : null);
    const sUnit = data.sector_avg_unit ?? "";
    const sRank = data.sector_rank;
    const sN = data.sector_n;
    const yoyPositive = yoy != null && yoy > 0;
    // Vert = hausse, rouge = baisse (logique métier assurance)
    const yoyColor = yoy != null ? (yoyPositive ? "#16A34A" : "#DC2626") : MUTED;
    const yoyBg   = yoy != null ? (yoyPositive ? "#F0FDF4" : "#FEF2F2") : "#F8FAFC";
    const yoyBorder = yoy != null ? (yoyPositive ? "#BBF7D0" : "#FECACA") : BORDER_LIGHT;
    const yoyIcon = yoy != null ? (yoyPositive ? "▲" : "▼") : "";
    // Classement : top 3 = OR/vert, reste = neutre
    const rankColor = sRank != null && sRank <= 3 ? "#16A34A" : D;
    const rankBg    = sRank != null && sRank <= 3 ? "#F0FDF4" : "#F8FAFC";
    const rankBorder = sRank != null && sRank <= 3 ? "#BBF7D0" : BORDER_LIGHT;

    // Détecte le fallback structuré : commence par **kpi** (markdown gras),
    // à la différence de la prose LLM qui commence par "La " / "Le " etc.
    const isFallback = text && text.trimStart().startsWith("**");

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {/* Carte valeur principale */}
        <div style={{
          background: "linear-gradient(135deg, #0C1B2E 0%, #1a3050 100%)",
          borderRadius: 10, padding: "12px 16px",
          display: "flex", alignItems: "flex-end", justifyContent: "space-between",
        }}>
          <div>
            <div style={{ fontSize: 9, color: "rgba(255,255,255,.55)", textTransform: "uppercase", letterSpacing: ".7px", fontWeight: 700, marginBottom: 5 }}>
              {(current?.kpi || data.kpi || "").replace(/\s*\(%\)\s*/i, "")} · {data.annee}
            </div>
            <div style={{ fontSize: 26, fontWeight: 800, color: "#fff", letterSpacing: "-.5px", lineHeight: 1 }}>
              {current?.display || "—"}
              {current?.unit && <span style={{ fontSize: 13, fontWeight: 500, color: "rgba(255,255,255,.6)", marginLeft: 5 }}>{current.unit}</span>}
            </div>
          </div>
          {sRank === 1 && <div style={{ fontSize: 22 }}>🏆</div>}
        </div>

        {/* Grille 3 métriques : YoY · Moy. secteur · Classement */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 6 }}>
          {yoy != null && (
            <div style={{ background: yoyBg, borderRadius: 8, padding: "8px 10px", border: `1px solid ${yoyBorder}` }}>
              <div style={{ fontSize: 8.5, color: MUTED, textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 700, marginBottom: 4 }}>
                vs {data.annee - 1}
              </div>
              <div style={{ fontSize: 14, fontWeight: 800, color: yoyColor }}>
                {yoyIcon} {yoy > 0 ? "+" : ""}{yoy.toFixed(1)} %
              </div>
            </div>
          )}
          {sAvg != null && (
            <div style={{ background: "#F8FAFC", borderRadius: 8, padding: "8px 10px", border: `1px solid ${BORDER_LIGHT}` }}>
              <div style={{ fontSize: 8.5, color: MUTED, textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 700, marginBottom: 4 }}>
                Moy. secteur
              </div>
              <div style={{ fontSize: 14, fontWeight: 800, color: D }}>
                {sAvg}{sUnit && <span style={{ fontSize: 10, fontWeight: 500, marginLeft: 2 }}>{sUnit}</span>}
              </div>
              {sN != null && <div style={{ fontSize: 8.5, color: MUTED, marginTop: 2 }}>{sN} compagnies</div>}
            </div>
          )}
          {sRank != null && (
            <div style={{ background: rankBg, borderRadius: 8, padding: "8px 10px", border: `1px solid ${rankBorder}` }}>
              <div style={{ fontSize: 8.5, color: MUTED, textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 700, marginBottom: 4 }}>
                Classement
              </div>
              <div style={{ fontSize: 14, fontWeight: 800, color: rankColor }}>
                #{sRank}
                <span style={{ fontSize: 10, fontWeight: 500, color: MUTED, marginLeft: 3 }}>/ {sN}</span>
              </div>
            </div>
          )}
        </div>

        {/* Explication — prose LLM ou fallback stylisé */}
        {text && (
          isFallback ? (
            // Fallback : lignes structurées → liste propre
            <div style={{ background: "#F8FAFC", border: `1px solid ${BORDER_LIGHT}`, borderRadius: 8, padding: "9px 12px" }}>
              <div style={{ fontSize: 8.5, color: MUTED, textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 700, marginBottom: 6 }}>
                Contexte
              </div>
              {text.trim().split("\n").filter(Boolean).map((line, i) => (
                <div key={i} style={{ fontSize: 11.5, color: TXT, lineHeight: 1.7, display: "flex", gap: 6, alignItems: "baseline" }}>
                  <span style={{ color: MUTED, flexShrink: 0 }}>·</span>
                  <span dangerouslySetInnerHTML={{ __html: bold(line) }} />
                </div>
              ))}
            </div>
          ) : (
            // Prose LLM → carte bleue sobre
            <div style={{
              background: "#EBF3FB", border: "1px solid #BEDAF5",
              borderRadius: 8, padding: "9px 12px",
            }}>
              <div style={{ fontSize: 8.5, color: "#1B6EC2", textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 700, marginBottom: 6, display: "flex", alignItems: "center", gap: 5 }}>
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#1B6EC2" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                Analyse EY
              </div>
              <div style={{ fontSize: 12, lineHeight: 1.7, color: TXT }}
                dangerouslySetInnerHTML={{ __html: bold(text) }} />
            </div>
          )
        )}
      </div>
    );
  }

  if (render === "forecast" && data?.rows?.length) {
    const rows = data.rows;
    const histRows = rows.filter(r => r.historical);
    const foreRows = rows.filter(r => !r.historical);
    const allVals = rows.map(r => r.value);
    const maxV = Math.max(...allVals, 1);
    const unit = rows[0]?.unit || "%";
    const kpiLabel = data.kpi || "KPI";
    const companyLabel = data.company || "le marché";
    const modelLabel = data.model_used || "Régression linéaire";
    const fmtVal = v => v != null ? Number(v).toLocaleString("fr-FR", { maximumFractionDigits: 2 }) + " " + unit : "—";
    const fmtPct = v => v != null ? Number(v).toLocaleString("fr-FR", { maximumFractionDigits: 2 }) + " " + unit : "—";
    // pick the last historical as baseline for trend arrow
    const lastHist = histRows.length ? histRows[histRows.length - 1].value : null;
    const lastFore = foreRows.length ? foreRows[foreRows.length - 1].value : null;
    const trendUp = lastHist != null && lastFore != null && lastFore >= lastHist;

    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {/* Header */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 3, height: 30, background: "#7C3AED", borderRadius: 2 }} />
          <div>
            <div style={{ fontSize: 11, fontWeight: 800, color: D, letterSpacing: ".2px" }}>
              Prévision — {kpiLabel}
            </div>
            <div style={{ fontSize: 9, color: MUTED, marginTop: 1 }}>
              {companyLabel} · {modelLabel}
            </div>
          </div>
          <div style={{ marginLeft: "auto", fontSize: 20 }}>{trendUp ? "📈" : "📉"}</div>
        </div>

        {/* Forecast cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
          {/* Historical context (smaller) */}
          {histRows.length > 0 && (
            <div style={{ fontSize: 9, color: MUTED, textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 600, marginBottom: 2 }}>
              Historique récent
            </div>
          )}
          {histRows.map(r => {
            const barPct = Math.round((r.value / maxV) * 100);
            return (
              <div key={r.year} style={{ display: "flex", alignItems: "center", gap: 7, opacity: 0.65 }}>
                <span style={{ fontSize: 9.5, color: MUTED, width: 34, flexShrink: 0, fontWeight: 600 }}>{r.year}</span>
                <div style={{ flex: 1, height: 5, background: BORDER_LIGHT, borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ width: `${barPct}%`, height: "100%", background: D, borderRadius: 3 }} />
                </div>
                <span style={{ fontSize: 9.5, color: MUTED, width: 60, flexShrink: 0, textAlign: "right", fontVariantNumeric: "tabular-nums", fontWeight: 600 }}>
                  {fmtVal(r.value)}
                </span>
              </div>
            );
          })}

          {/* Forecast rows (prominent) */}
          {foreRows.length > 0 && (
            <div style={{ fontSize: 9, color: "#7C3AED", textTransform: "uppercase", letterSpacing: ".5px", fontWeight: 700, marginTop: 6, marginBottom: 2 }}>
              Prévisions
            </div>
          )}
          {foreRows.map((r, i) => {
            const barPct = Math.round((r.value / maxV) * 100);
            const isTarget = i === foreRows.length - 1;
            return (
              <div key={r.year} style={{
                background: isTarget ? "#F5F0FF" : "#FAFBFF",
                border: `1px solid ${isTarget ? "#C4B5FD" : "#E8EAF0"}`,
                borderRadius: 8,
                padding: "8px 10px",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700,
                    color: isTarget ? "#7C3AED" : D,
                    width: 34, flexShrink: 0,
                  }}>{r.year}</span>
                  <div style={{ flex: 1, height: 6, background: BORDER_LIGHT, borderRadius: 3, overflow: "hidden" }}>
                    <div style={{ width: `${barPct}%`, height: "100%", background: isTarget ? "#7C3AED" : "#9B72F8", borderRadius: 3 }} />
                  </div>
                  <span style={{
                    fontSize: isTarget ? 13 : 11, fontWeight: isTarget ? 800 : 700,
                    color: isTarget ? "#7C3AED" : D,
                    width: 70, flexShrink: 0, textAlign: "right",
                    fontVariantNumeric: "tabular-nums",
                  }}>{fmtPct(r.value)}</span>
                </div>
                {/* IC band */}
                {r.ci_low != null && (
                  <div style={{ marginTop: 4, marginLeft: 41, fontSize: 9, color: MUTED, fontVariantNumeric: "tabular-nums" }}>
                    IC 80 % : {fmtPct(r.ci_low)} – {fmtPct(r.ci_high)}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* LLM narrative — parsée en sections Prévision / Explication */}
        {text && (() => {
          // Extraire les sections **Titre** \n contenu
          const sectionRe = /\*\*([^*]+)\*\*[\s\S]*?\n([\s\S]*?)(?=\n\s*\*\*|$)/g;
          const sections = [];
          let m;
          const src = text.trim();
          while ((m = sectionRe.exec(src)) !== null) {
            const title = m[1].trim();
            const body = m[2].trim();
            const bullets = body.split("\n").filter(l => l.trim().startsWith("- ")).map(l => l.replace(/^-\s*/, "").trim());
            const prose = body.split("\n").filter(l => !l.trim().startsWith("- ")).join(" ").trim();
            sections.push({ title, bullets, prose });
          }
          // Afficher uniquement la section Explication (Prévision = déjà dans les cartes)
          const expl = sections.find(s => s.title.toLowerCase().includes("explication") || s.title.toLowerCase().includes("analyse"));
          const toShow = expl ? [expl] : sections;
          if (!toShow.length) {
            return (
              <div style={{ fontSize: 11.5, color: TXT, lineHeight: 1.65, borderTop: `1px solid ${BORDER_LIGHT}`, paddingTop: 8 }}
                dangerouslySetInnerHTML={{ __html: bold(text) }} />
            );
          }
          return (
            <div style={{ borderTop: `1px solid ${BORDER_LIGHT}`, paddingTop: 9, marginTop: 4, display: "flex", flexDirection: "column", gap: 6 }}>
              {toShow.map(({ title, bullets, prose }) => (
                <div key={title} style={{
                  background: "#F5F0FF", border: "1px solid #DDD6FE",
                  borderRadius: 8, padding: "9px 12px",
                }}>
                  <div style={{
                    fontSize: 9, fontWeight: 800, color: "#7C3AED",
                    textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 6,
                    display: "flex", alignItems: "center", gap: 5,
                  }}>
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                    Analyse du modèle
                  </div>
                  {bullets.length > 0 && (
                    <ul style={{ margin: "0 0 5px 0", paddingLeft: 14 }}>
                      {bullets.map((b, i) => (
                        <li key={i} style={{ fontSize: 11, color: TXT, lineHeight: 1.6, marginBottom: 2 }}
                          dangerouslySetInnerHTML={{ __html: bold(b) }} />
                      ))}
                    </ul>
                  )}
                  {prose && (
                    <div style={{ fontSize: 11.5, color: TXT, lineHeight: 1.7 }}
                      dangerouslySetInnerHTML={{ __html: bold(prose) }} />
                  )}
                </div>
              ))}
            </div>
          );
        })()}
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

  if (isUser) {
    return (
      <div style={{ marginBottom: 18, display: "flex", justifyContent: "flex-end", alignItems: "flex-end", gap: 8 }}>
        {/* Bulle consultant — droite, bleu marine distinctif */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", maxWidth: "78%" }}>
          <div style={{ fontSize: 9.5, fontWeight: 700, color: "#3B6FA8", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 5 }}>
            Consultant
          </div>
          <div style={{
            background: "linear-gradient(135deg,#1C4F8C,#2563EB)",
            borderRadius: "12px 12px 3px 12px",
            padding: "10px 14px", boxSizing: "border-box",
            boxShadow: "0 2px 8px rgba(37,99,235,.25)",
          }}>
            <div dangerouslySetInnerHTML={{ __html: bold(text) }} style={{ fontSize: 12.5, lineHeight: 1.6, color: "#fff" }}/>
          </div>
        </div>
        {/* Avatar consultant */}
        <div style={{
          width: 32, height: 32, borderRadius: 16, flexShrink: 0,
          background: "linear-gradient(135deg,#1C4F8C,#2563EB)",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 2px 6px rgba(37,99,235,.3)",
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
          </svg>
        </div>
      </div>
    );
  }

  return (
    <div style={{ marginBottom: 18, display: "flex", flexDirection: "column", alignItems: "stretch" }}>
      <div style={{
        fontSize: 9.5, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 6,
        width: "100%",
      }}>
        Assistant
      </div>
      <div style={{
        background: "#F7F8FA",
        border: `1px solid ${BORDER_LIGHT}`,
        borderRadius: 10,
        padding: "9px 13px",
        maxWidth: "100%", textAlign: "left",
        boxSizing: "border-box",
      }}>
        <RichContent render={render} data={data} text={text}/>
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
