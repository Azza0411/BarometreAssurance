import { useState, useEffect, useMemo } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { getLogoSrc } from "../utils/logos";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const DARK      = "#2E2E38";
const BG        = "#F2F5FB";
const BORDER    = "#DDE2EC";
const MUTED     = "#6B7280";
const ACCENT    = "#0F6E56";
const ACCENT_BG = "#E1F5EE";
const VIEWER_BG   = "#1E293B";
const BAD       = "#C8102E";
const BAD_BG    = "rgba(200,16,46,.18)";

function fmt(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("fr-TN", { maximumFractionDigits: 2 });
}

function cellKey(ligne, colonne) {
  return `${ligne}|||${colonne}`;
}

/* ═══════════════════════════ Page ═══════════════════════════
   Consultation (et bientôt correction) d'un document CMF déjà en base,
   accessible directement depuis Gestion de données — pensée pour pouvoir
   VOIR le contenu avant de télécharger l'Excel, comme KpiDetail permet de
   voir le PDF source. `Enregistrer tout` reste un espace réservé : le
   traitement de sauvegarde arrive dans une étape suivante, une fois
   l'emplacement des boutons et le design validés (backend en pause). */
export default function CorrectionManuelle() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const code = params.get("code");
  const annee = Number(params.get("annee"));
  const tableau = params.get("tableau") || "annexe12";

  const [docs, setDocs] = useState(null);
  const [opts, setOpts] = useState(null);
  const [grid, setGrid] = useState(null);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridErreur, setGridErreur] = useState(null);

  const [selected, setSelected] = useState(null); // { ligne, colonne, actuelle }
  const [nouvelleValeur, setNouvelleValeur] = useState("");
  const [motif, setMotif] = useState("");
  const [corrections, setCorrections] = useState(new Map()); // key -> { ligne, colonne, actuelle, nouvelle, motif }
  const [saveNote, setSaveNote] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/documents`).then(r => r.json()).then(setDocs).catch(() => setDocs([]));
    fetch(`${API}/api/gestion-donnees/filtres`).then(r => r.json()).then(setOpts).catch(() => {});
  }, []);

  useEffect(() => {
    if (!code || !annee || !tableau) return;
    setGridLoading(true);
    setGridErreur(null);
    setSelected(null);
    setCorrections(new Map());
    const p = new URLSearchParams({ societe: code, annee: String(annee), tableau });
    fetch(`${API}/api/gestion-donnees/cellules?${p.toString()}`)
      .then(async r => {
        if (!r.ok) throw new Error("echec");
        return r.json();
      })
      .then(setGrid)
      .catch(() => { setGrid(null); setGridErreur("Aucune donnée trouvée pour cette société/année/tableau."); })
      .finally(() => setGridLoading(false));
  }, [code, annee, tableau]);

  const societe = useMemo(() => opts?.societes?.find(s => s.code === code), [opts, code]);
  const logo = code ? getLogoSrc(code) : null;

  const anneesDisponibles = useMemo(() => {
    if (!docs) return [];
    return [...new Set(docs.filter(d => d.source === "CMF" && d.code === code).map(d => d.annee))].sort((a, b) => b - a);
  }, [docs, code]);

  const tableauxDisponibles = useMemo(() => {
    if (!opts?.tableaux) return [];
    return opts.tableaux.filter(t => (opts.societes_par_tableau?.[t.key] ?? []).includes(code));
  }, [opts, code]);

  const currentDoc = useMemo(
    () => (docs ?? []).find(d => d.source === "CMF" && d.code === code && d.annee === annee),
    [docs, code, annee],
  );
  const pdfHref = currentDoc
    ? (currentDoc.fichier_local ? `${API}/api/gestion-donnees/documents/${currentDoc.id}/pdf` : currentDoc.lien)
    : null;

  const goTableau = (t) => setParams(prev => { const n = new URLSearchParams(prev); n.set("tableau", t); return n; });
  const goAnnee = (a) => setParams(prev => { const n = new URLSearchParams(prev); n.set("annee", String(a)); return n; });

  const selectCell = (ligne, colonne, actuelle) => {
    setSelected({ ligne, colonne, actuelle });
    setNouvelleValeur("");
    setMotif("");
  };

  const ajouterCorrection = () => {
    if (!selected || !nouvelleValeur.trim()) return;
    const key = cellKey(selected.ligne, selected.colonne);
    setCorrections(prev => {
      const next = new Map(prev);
      next.set(key, { ...selected, nouvelle: nouvelleValeur.trim(), motif: motif.trim() });
      return next;
    });
    setNouvelleValeur("");
    setMotif("");
  };
  const retirerCorrection = (key) => setCorrections(prev => { const n = new Map(prev); n.delete(key); return n; });

  const enregistrerTout = () => {
    if (corrections.size === 0) return;
    // Le point de sauvegarde réel (écriture en base / audit) est le
    // "traitement spécifique" volontairement laissé pour l'étape suivante —
    // ici on ne fait que confirmer l'emplacement du bouton et son état.
    setSaveNote("L'enregistrement effectif sera branché à l'étape suivante — cette liste reste locale pour l'instant.");
  };

  if (!code || !annee) {
    return (
      <div style={{ minHeight: "calc(100vh - 92px)", background: BG, display: "flex", alignItems: "center", justifyContent: "center", color: MUTED, fontSize: 13 }}>
        Société ou année manquante. Retournez à <button onClick={() => navigate("/gestion-donnees")} style={{ border: "none", background: "none", color: ACCENT, fontWeight: 700, cursor: "pointer", marginLeft: 4 }}>Gestion de données</button>.
      </div>
    );
  }

  return (
    <div style={{ minHeight: "calc(100vh - 92px)", background: BG, fontFamily: "'Inter', system-ui, sans-serif" }}>
      {/* ── Repère ──────────────────────────────────────────────────────── */}
      <div style={{
        background: "#fff", borderBottom: `1px solid ${BORDER}`, padding: "11px 22px",
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <button onClick={() => navigate("/gestion-donnees")} style={{
            display: "flex", alignItems: "center", gap: 5, border: "none", background: "none",
            color: MUTED, fontSize: 12.5, fontWeight: 700, cursor: "pointer", font: "inherit",
          }}>‹ Gestion de données</button>
          <span style={{ color: BORDER }}>/</span>
          <div style={{ display: "flex", alignItems: "center", gap: 7, background: "#F8F9FC", border: `1px solid ${BORDER}`, borderRadius: 9, padding: "4px 10px 4px 6px" }}>
            <span style={{
              width: 22, height: 22, borderRadius: 5, background: "#fff", border: `1px solid ${BORDER}`,
              display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", flexShrink: 0,
            }}>
              {logo ? <img src={logo} alt="" style={{ maxWidth: 18, maxHeight: 18, objectFit: "contain" }} /> : <span style={{ fontSize: 8, fontWeight: 800, color: MUTED }}>{code.slice(0, 2)}</span>}
            </span>
            <b style={{ fontSize: 12.5, fontWeight: 800, color: DARK }}>{code}</b>
          </div>
          {societe?.nom && <span style={{ fontSize: 12, color: MUTED }}>{societe.nom}</span>}
          <span style={{
            background: ACCENT_BG, color: ACCENT, fontSize: 10.5, fontWeight: 800,
            padding: "3px 9px", borderRadius: 20, textTransform: "uppercase", letterSpacing: ".3px",
          }}>Correction manuelle</span>

          <div style={{ display: "flex", gap: 6, marginLeft: 6, flexWrap: "wrap" }}>
            {tableauxDisponibles.map(t => (
              <button key={t.key} onClick={() => goTableau(t.key)} style={{
                padding: "5px 12px", borderRadius: 20, fontSize: 11.5, fontWeight: 700, cursor: "pointer",
                border: `1.5px solid ${tableau === t.key ? ACCENT : BORDER}`,
                background: tableau === t.key ? ACCENT_BG : "#fff", color: tableau === t.key ? ACCENT : DARK,
              }}>
                {t.label.split(" — ")[0]}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: 4, background: "#F3F4F8", borderRadius: 10, padding: 3 }}>
          {anneesDisponibles.map(a => (
            <button key={a} onClick={() => goAnnee(a)} style={{
              border: "none", background: a === annee ? DARK : "transparent", color: a === annee ? "#fff" : MUTED,
              padding: "6px 11px", borderRadius: 7, fontSize: 12, fontWeight: 700, cursor: "pointer",
              fontVariantNumeric: "tabular-nums", font: "inherit",
            }}>{a}</button>
          ))}
        </div>
      </div>

      {/* ── Corps : formulaire à gauche, visualiseur à droite ────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "380px 1fr", height: "calc(100vh - 92px - 58px)", overflow: "hidden" }}>
        {/* Gauche */}
        <div style={{ overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, padding: "16px 18px" }}>
            <h3 style={{ margin: "0 0 3px", fontSize: 13.5, fontWeight: 800, color: DARK }}>Cellule sélectionnée</h3>
            <p style={{ margin: "0 0 12px", fontSize: 11.5, color: MUTED }}>
              Cliquez une cellule dans le tableau à droite pour la corriger.
            </p>
            {!selected ? (
              <p style={{ fontSize: 12.5, color: MUTED, margin: 0 }}>Aucune cellule sélectionnée.</p>
            ) : (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px 14px", marginBottom: 4 }}>
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: ".3px" }}>Ligne</div>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: DARK }}>{selected.ligne}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: ".3px" }}>Colonne</div>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: DARK }}>{selected.colonne}</div>
                  </div>
                </div>
                <div style={{ marginTop: 12 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: ".3px", marginBottom: 5 }}>Valeur actuelle (extraite)</div>
                  <div style={{ padding: "9px 11px", borderRadius: 8, background: "#F8F9FC", fontSize: 13, fontWeight: 700, color: MUTED, fontVariantNumeric: "tabular-nums" }}>
                    {fmt(selected.actuelle)}
                  </div>
                </div>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 5 }}>
                  <label style={{ fontSize: 10, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: ".3px" }}>Nouvelle valeur</label>
                  <input value={nouvelleValeur} onChange={e => setNouvelleValeur(e.target.value)} placeholder="Saisir la valeur corrigée…"
                    style={{ fontSize: 13, padding: "9px 11px", border: `1px solid ${BORDER}`, borderRadius: 8, font: "inherit" }} />
                </div>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 5 }}>
                  <label style={{ fontSize: 10, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: ".3px" }}>Motif (optionnel)</label>
                  <textarea value={motif} onChange={e => setMotif(e.target.value)} placeholder="Ex. coquille de saisie, erreur d'OCR…"
                    style={{ fontSize: 13, padding: "9px 11px", border: `1px solid ${BORDER}`, borderRadius: 8, minHeight: 56, font: "inherit", resize: "vertical" }} />
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
                  <button onClick={() => setSelected(null)} style={{
                    flex: 1, padding: "9px 16px", borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: "pointer",
                    border: `1.5px solid ${BORDER}`, background: "#fff", color: MUTED, font: "inherit",
                  }}>Annuler</button>
                  <button onClick={ajouterCorrection} disabled={!nouvelleValeur.trim()} style={{
                    flex: 1, padding: "9px 16px", borderRadius: 8, fontSize: 12.5, fontWeight: 700,
                    cursor: nouvelleValeur.trim() ? "pointer" : "not-allowed",
                    border: `1.5px solid ${ACCENT}`, background: ACCENT, color: "#fff", opacity: nouvelleValeur.trim() ? 1 : .5, font: "inherit",
                  }}>Ajouter à la liste</button>
                </div>
              </>
            )}
          </div>

          <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, padding: "16px 18px", flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
            <h3 style={{ margin: "0 0 3px", fontSize: 13.5, fontWeight: 800, color: DARK }}>Corrections en attente</h3>
            <p style={{ margin: "0 0 12px", fontSize: 11.5, color: MUTED }}>Empilez plusieurs corrections avant de tout enregistrer.</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, overflowY: "auto" }}>
              {corrections.size === 0 ? (
                <div style={{ fontSize: 12, color: MUTED, textAlign: "center", padding: "14px 0" }}>Aucune correction en attente.</div>
              ) : [...corrections.entries()].map(([key, c]) => (
                <div key={key} onClick={() => selectCell(c.ligne, c.colonne, c.actuelle)} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "9px 10px", border: `1px solid ${BORDER}`,
                  borderRadius: 9, cursor: "pointer",
                }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#B45309", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10.5, color: MUTED }}>{c.ligne} · {c.colonne}</div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: DARK, fontVariantNumeric: "tabular-nums" }}>
                      <s style={{ color: MUTED, fontWeight: 500, marginRight: 4 }}>{fmt(c.actuelle)}</s>→ {c.nouvelle}
                    </div>
                  </div>
                  <button onClick={e => { e.stopPropagation(); retirerCorrection(key); }} style={{
                    border: "none", background: "rgba(200,16,46,.08)", color: BAD, width: 22, height: 22,
                    borderRadius: "50%", cursor: "pointer", fontSize: 12,
                  }}>×</button>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginTop: 12 }}>
              <span style={{ fontSize: 11.5, color: MUTED }}>{corrections.size} correction{corrections.size > 1 ? "s" : ""} en attente</span>
              <button onClick={enregistrerTout} disabled={corrections.size === 0} style={{
                padding: "9px 16px", borderRadius: 8, fontSize: 12.5, fontWeight: 700,
                cursor: corrections.size ? "pointer" : "not-allowed",
                border: `1.5px solid ${ACCENT}`, background: ACCENT, color: "#fff", opacity: corrections.size ? 1 : .5, font: "inherit",
              }}>Enregistrer tout</button>
            </div>
            {saveNote && <p style={{ margin: "10px 0 0", fontSize: 11, color: "#B45309", fontWeight: 600 }}>{saveNote}</p>}
          </div>
        </div>

        {/* Droite : visualiseur */}
        <div style={{ background: VIEWER_BG, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "11px 18px", borderBottom: "1px solid rgba(255,255,255,.08)", flexWrap: "wrap" }}>
            <span style={{ color: "#E5E7EB", fontSize: 12.5, fontWeight: 700 }}>📊 Excel — {code} · {annee}</span>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto", flexWrap: "wrap" }}>
              <span style={{ background: "rgba(255,255,255,.08)", color: "#E5E7EB", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 20 }}>
                Feuille : {tableauxDisponibles.find(t => t.key === tableau)?.label.split(" — ")[0] ?? tableau}
              </span>
              {selected && (
                <span style={{ display: "flex", alignItems: "center", gap: 6, background: BAD_BG, color: "#FCA5A5", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 20 }}>
                  📍 {selected.ligne} · {selected.colonne}
                </span>
              )}
              {pdfHref && (
                <a href={pdfHref} target="_blank" rel="noreferrer" style={{ display: "flex", alignItems: "center", gap: 5, color: "#93C5FD", fontSize: 11.5, fontWeight: 700, textDecoration: "none" }}>
                  Voir le PDF source ↗
                </a>
              )}
            </div>
          </div>

          <div style={{ flex: 1, overflow: "auto", padding: 26 }}>
            {gridLoading ? (
              <p style={{ color: "#94A3B8", textAlign: "center", marginTop: 40 }}>Chargement…</p>
            ) : gridErreur ? (
              <p style={{ color: "#FCA5A5", textAlign: "center", marginTop: 40 }}>{gridErreur}</p>
            ) : !grid || grid.lignes.length === 0 ? (
              <p style={{ color: "#94A3B8", textAlign: "center", marginTop: 40 }}>Aucune cellule stockée pour cette combinaison.</p>
            ) : (
              <div style={{ background: "#fff", borderRadius: 4, boxShadow: "0 8px 30px rgba(0,0,0,.35)", maxWidth: 720, margin: "0 auto", padding: "30px 34px" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
                  <thead>
                    <tr>
                      <th style={{ background: "#1D4E89", color: "#fff", padding: "8px 10px", border: "1px solid #16406F" }} />
                      {grid.colonnes.map(col => (
                        <th key={col} style={{ background: "#1D4E89", color: "#fff", padding: "8px 10px", border: "1px solid #16406F", fontWeight: 700 }}>{col}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {grid.lignes.map(row => (
                      <tr key={row.ligne}>
                        <td style={{ padding: "7px 10px", border: "1px solid #E2E5EA", fontWeight: 600 }}>{row.ligne}</td>
                        {grid.colonnes.map(col => {
                          const val = row.valeurs[col];
                          const key = cellKey(row.ligne, col);
                          const isSelected = selected?.ligne === row.ligne && selected?.colonne === col;
                          const isCorrected = corrections.has(key);
                          return (
                            <td
                              key={col}
                              onClick={() => selectCell(row.ligne, col, val)}
                              style={{
                                padding: "7px 10px", border: "1px solid #E2E5EA", textAlign: "right",
                                fontVariantNumeric: "tabular-nums", cursor: "pointer",
                                background: isSelected ? "#FDE8E8" : isCorrected ? ACCENT_BG : "transparent",
                                outline: isSelected ? `2px solid ${BAD}` : "none", outlineOffset: -2,
                              }}
                            >
                              {fmt(val)}{isCorrected && <span style={{ color: ACCENT, fontWeight: 800, marginLeft: 5, fontSize: 10.5 }}>✓</span>}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
