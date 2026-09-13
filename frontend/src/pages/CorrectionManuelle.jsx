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
const VIEWER_BG = "#1E293B";
const BAD       = "#C8102E";
const BAD_BG    = "rgba(200,16,46,.18)";

function fmt(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return n.toLocaleString("fr-TN", { maximumFractionDigits: 2 });
}

// Clé de correction — une par ligne (nom), une par colonne (nom), une par
// cellule de valeur (ligne+colonne) ; toujours basée sur le nom ORIGINAL
// (avant renommage), jamais sur le nom affiché, pour rester stable même
// après un renommage en attente.
function correctionKey(sel) {
  if (sel.kind === "ligne") return `ligne::${sel.ligne}`;
  if (sel.kind === "colonne") return `colonne::${sel.colonne}`;
  return `valeur::${sel.ligne}|||${sel.colonne}`;
}

const gridLabel = { display: "block", fontSize: 10, fontWeight: 700, color: MUTED, textTransform: "uppercase", letterSpacing: ".3px" };

/* ═══════════════════════════ Page ═══════════════════════════
   Consultation (et bientôt correction) d'un document CMF déjà en base,
   accessible directement depuis Gestion de données — même grammaire
   visuelle que KpiDetail (repère, grille Tableau/Ligne/Colonne, visualiseur
   sombre). `Enregistrer tout` reste un espace réservé pour l'instant :
   l'écriture réelle en base est la prochaine étape, une fois ce contenu de
   gauche validé. */
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
  const [referentiel, setReferentiel] = useState({ lignes: [], colonnes: [] });

  // { kind: 'valeur'|'ligne'|'colonne', ligne, colonne, actuelle }
  const [selected, setSelected] = useState(null);
  const [nouvelleValeur, setNouvelleValeur] = useState("");
  const [motif, setMotif] = useState("");
  const [corrections, setCorrections] = useState(new Map()); // key -> { kind, ligne, colonne, actuelle, nouvelle, motif }
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
      .then(async r => { if (!r.ok) throw new Error("echec"); return r.json(); })
      .then(setGrid)
      .catch(() => { setGrid(null); setGridErreur("Aucune donnée trouvée pour cette société/année/tableau."); })
      .finally(() => setGridLoading(false));
    fetch(`${API}/api/gestion-donnees/referentiel?tableau=${tableau}`)
      .then(r => r.json()).then(setReferentiel).catch(() => setReferentiel({ lignes: [], colonnes: [] }));
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
  const tableauLabel = tableauxDisponibles.find(t => t.key === tableau)?.label.split(" — ")[0] ?? tableau;

  const currentDoc = useMemo(
    () => (docs ?? []).find(d => d.source === "CMF" && d.code === code && d.annee === annee),
    [docs, code, annee],
  );
  const pdfHref = currentDoc
    ? (currentDoc.fichier_local ? `${API}/api/gestion-donnees/documents/${currentDoc.id}/pdf` : currentDoc.lien)
    : null;

  const goTableau = (t) => setParams(prev => { const n = new URLSearchParams(prev); n.set("tableau", t); return n; });
  const goAnnee = (a) => setParams(prev => { const n = new URLSearchParams(prev); n.set("annee", String(a)); return n; });

  // Nom affiché pour une ligne/colonne — reflète immédiatement un
  // renommage en attente (pas encore enregistré), pour "voir le changement
  // directement sur l'Excel" sans attendre une sauvegarde réelle.
  const displayLigne = (ligne) => corrections.get(`ligne::${ligne}`)?.nouvelle ?? ligne;
  const displayColonne = (colonne) => corrections.get(`colonne::${colonne}`)?.nouvelle ?? colonne;

  const selectValeur = (ligne, colonne, actuelle) => {
    setSelected({ kind: "valeur", ligne, colonne, actuelle });
    setNouvelleValeur(""); setMotif("");
  };
  const selectLigne = (ligne) => {
    setSelected({ kind: "ligne", ligne, colonne: null, actuelle: displayLigne(ligne) });
    setNouvelleValeur(corrections.get(`ligne::${ligne}`)?.nouvelle ?? ""); setMotif("");
  };
  const selectColonne = (colonne) => {
    setSelected({ kind: "colonne", ligne: null, colonne, actuelle: displayColonne(colonne) });
    setNouvelleValeur(corrections.get(`colonne::${colonne}`)?.nouvelle ?? ""); setMotif("");
  };

  const ajouterCorrection = () => {
    if (!selected || !nouvelleValeur.trim() || nouvelleValeur.trim() === String(selected.actuelle ?? "")) return;
    const key = correctionKey(selected);
    setCorrections(prev => {
      const next = new Map(prev);
      next.set(key, { ...selected, nouvelle: nouvelleValeur.trim(), motif: motif.trim() });
      return next;
    });
    setNouvelleValeur(""); setMotif(""); setSelected(null);
  };
  const retirerCorrection = (key) => setCorrections(prev => { const n = new Map(prev); n.delete(key); return n; });

  const enregistrerTout = () => {
    if (corrections.size === 0) return;
    // Le point de sauvegarde réel (écriture en base / audit) reste la
    // prochaine étape, une fois ce contenu de gauche validé.
    setSaveNote("L'enregistrement effectif sera branché à l'étape suivante — cette liste reste locale pour l'instant.");
  };

  if (!code || !annee) {
    return (
      <div style={{ minHeight: "calc(100vh - 92px)", background: BG, display: "flex", alignItems: "center", justifyContent: "center", color: MUTED, fontSize: 13 }}>
        Société ou année manquante. Retournez à <button onClick={() => navigate("/gestion-donnees")} style={{ border: "none", background: "none", color: ACCENT, fontWeight: 700, cursor: "pointer", marginLeft: 4 }}>Gestion de données</button>.
      </div>
    );
  }

  // Référentiel applicable au type sélectionné — vide (donc repli sur un
  // champ libre) pour 'bilan', non encore normalisé.
  const options = selected?.kind === "ligne" ? referentiel.lignes : selected?.kind === "colonne" ? referentiel.colonnes : [];

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
      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", height: "calc(100vh - 92px - 58px)", overflow: "hidden" }}>
        {/* Gauche */}
        <div style={{ overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Résumé du document — une seule ligne compacte, l'essentiel déjà
              visible dans le repère du haut n'a pas besoin d'être répété
              dans une carte entière. */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
            padding: "8px 12px", background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 9, fontSize: 11,
          }}>
            <span style={{ color: MUTED }}>
              {grid ? <><b style={{ color: DARK }}>{grid.lignes.length}</b> lignes × <b style={{ color: DARK }}>{grid.colonnes.length}</b> colonnes</> : "—"}
            </span>
            <span style={{ display: "flex", gap: 12 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: "#FDE8E8", border: `1.5px solid ${BAD}` }} />
                <span style={{ color: MUTED }}>Sélection</span>
              </span>
              <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: ACCENT_BG, border: `1.5px solid ${ACCENT}` }} />
                <span style={{ color: MUTED }}>Corrigé</span>
              </span>
            </span>
          </div>

          {/* Localisation — même grille (label 72px / valeur) que la carte
              "Source dans le PDF" de KpiDetail. */}
          <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, padding: "14px 16px" }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 800, color: DARK }}>Localisation</h3>
            {!selected ? (
              <p style={{ fontSize: 12, color: MUTED, margin: 0 }}>Cliquez une valeur, un nom de ligne ou de colonne dans le tableau à droite.</p>
            ) : (
              <div style={{ display: "grid", gridTemplateColumns: "72px 1fr", gap: "5px 10px", fontSize: 11.5 }}>
                <span style={{ color: MUTED, fontWeight: 600 }}>Tableau</span>
                <span style={{ color: DARK }}>{tableauLabel}</span>
                <span style={{ color: MUTED, fontWeight: 600 }}>Ligne</span>
                <span style={{ color: DARK, fontFamily: "ui-monospace, monospace" }}>
                  {selected.kind === "colonne" ? <span style={{ color: "#B0B6C2" }}>— (colonne)</span> : `« ${selected.ligne} »`}
                </span>
                <span style={{ color: MUTED, fontWeight: 600 }}>Colonne</span>
                <span style={{ color: DARK, fontFamily: "ui-monospace, monospace" }}>
                  {selected.kind === "ligne" ? <span style={{ color: "#B0B6C2" }}>— (ligne)</span> : `« ${selected.colonne} »`}
                </span>
                <span style={{ color: MUTED, fontWeight: 600 }}>Type</span>
                <span style={{ color: DARK }}>{selected.kind === "valeur" ? "Valeur de cellule" : selected.kind === "ligne" ? "Nom de ligne" : "Nom de colonne"}</span>
              </div>
            )}
          </div>

          {/* Correction — valeur (ancienne → saisie libre) ou nom (ancien →
              menu déroulant des noms déjà normalisés dans le code). */}
          <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, padding: "14px 16px" }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 800, color: DARK }}>Corriger</h3>
            {!selected ? (
              <p style={{ fontSize: 12, color: MUTED, margin: 0 }}>Aucune sélection.</p>
            ) : (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <div style={{
                    flex: 1, minWidth: 0, padding: "8px 10px", borderRadius: 8, background: "#F8F9FC",
                    fontSize: 12.5, fontWeight: 700, color: MUTED, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    fontVariantNumeric: selected.kind === "valeur" ? "tabular-nums" : "normal",
                  }}>
                    {selected.kind === "valeur" ? fmt(selected.actuelle) : selected.actuelle}
                  </div>
                  <span style={{ color: MUTED, fontSize: 14, flexShrink: 0 }}>→</span>
                  {selected.kind === "valeur" ? (
                    <input
                      value={nouvelleValeur} onChange={e => setNouvelleValeur(e.target.value)}
                      placeholder="Nouvelle valeur…" autoFocus
                      style={{ flex: 1, minWidth: 0, fontSize: 12.5, padding: "8px 10px", border: `1.5px solid ${ACCENT}`, borderRadius: 8, font: "inherit", fontVariantNumeric: "tabular-nums" }}
                    />
                  ) : options.length > 0 ? (
                    <select
                      value={nouvelleValeur} onChange={e => setNouvelleValeur(e.target.value)}
                      style={{ flex: 1, minWidth: 0, fontSize: 12.5, padding: "8px 10px", border: `1.5px solid ${ACCENT}`, borderRadius: 8, font: "inherit", background: "#fff" }}
                    >
                      <option value="">Choisir un nom…</option>
                      {options.map(o => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : (
                    <input
                      value={nouvelleValeur} onChange={e => setNouvelleValeur(e.target.value)}
                      placeholder="Nouveau nom…" autoFocus
                      style={{ flex: 1, minWidth: 0, fontSize: 12.5, padding: "8px 10px", border: `1.5px solid ${ACCENT}`, borderRadius: 8, font: "inherit" }}
                    />
                  )}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 5, marginBottom: 12 }}>
                  <label style={gridLabel}>Motif (optionnel)</label>
                  <textarea value={motif} onChange={e => setMotif(e.target.value)} placeholder="Ex. coquille de saisie, erreur d'OCR…"
                    style={{ fontSize: 12.5, padding: "8px 10px", border: `1px solid ${BORDER}`, borderRadius: 8, minHeight: 48, font: "inherit", resize: "vertical" }} />
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <button onClick={() => setSelected(null)} style={{
                    flex: 1, padding: "8px 14px", borderRadius: 8, fontSize: 12.5, fontWeight: 700, cursor: "pointer",
                    border: `1.5px solid ${BORDER}`, background: "#fff", color: MUTED, font: "inherit",
                  }}>Annuler</button>
                  <button onClick={ajouterCorrection} disabled={!nouvelleValeur.trim()} style={{
                    flex: 1, padding: "8px 14px", borderRadius: 8, fontSize: 12.5, fontWeight: 700,
                    cursor: nouvelleValeur.trim() ? "pointer" : "not-allowed",
                    border: `1.5px solid ${ACCENT}`, background: ACCENT, color: "#fff", opacity: nouvelleValeur.trim() ? 1 : .5, font: "inherit",
                  }}>Ajouter à la liste</button>
                </div>
              </>
            )}
          </div>

          <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, padding: "14px 16px", flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 13, fontWeight: 800, color: DARK }}>Corrections en attente</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, overflowY: "auto" }}>
              {corrections.size === 0 ? (
                <div style={{ fontSize: 12, color: MUTED, textAlign: "center", padding: "12px 0" }}>Aucune correction en attente.</div>
              ) : [...corrections.entries()].map(([key, c]) => (
                <div key={key} onClick={() => (c.kind === "valeur" ? selectValeur(c.ligne, c.colonne, c.actuelle) : c.kind === "ligne" ? selectLigne(c.ligne) : selectColonne(c.colonne))} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", border: `1px solid ${BORDER}`,
                  borderRadius: 9, cursor: "pointer",
                }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#B45309", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10.5, color: MUTED }}>
                      {c.kind === "valeur" ? `${c.ligne} · ${c.colonne}` : c.kind === "ligne" ? "Nom de ligne" : "Nom de colonne"}
                    </div>
                    <div style={{ fontSize: 12, fontWeight: 700, color: DARK, fontVariantNumeric: c.kind === "valeur" ? "tabular-nums" : "normal", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      <s style={{ color: MUTED, fontWeight: 500, marginRight: 4 }}>{c.kind === "valeur" ? fmt(c.actuelle) : c.actuelle}</s>→ {c.nouvelle}
                    </div>
                  </div>
                  <button onClick={e => { e.stopPropagation(); retirerCorrection(key); }} style={{
                    border: "none", background: "rgba(200,16,46,.08)", color: BAD, width: 22, height: 22,
                    borderRadius: "50%", cursor: "pointer", fontSize: 12, flexShrink: 0,
                  }}>×</button>
                </div>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginTop: 12 }}>
              <span style={{ fontSize: 11.5, color: MUTED }}>{corrections.size} en attente</span>
              <button onClick={enregistrerTout} disabled={corrections.size === 0} style={{
                padding: "8px 14px", borderRadius: 8, fontSize: 12.5, fontWeight: 700,
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
            <span style={{ display: "flex", alignItems: "center", gap: 7, color: "#E5E7EB", fontSize: 12.5, fontWeight: 700 }}>
              <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
                <rect x="2" y="1" width="12" height="14" rx="2" stroke="#94A3B8" strokeWidth="1.3"/>
                <path d="M5 5h6M5 8h4M5 11h5" stroke="#94A3B8" strokeWidth="1.1" strokeLinecap="round"/>
              </svg>
              Excel — {code} · {annee}
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto", flexWrap: "wrap" }}>
              <span style={{ background: "rgba(255,255,255,.08)", color: "#E5E7EB", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 20 }}>
                Feuille : {tableauLabel}
              </span>
              {selected && (
                <span style={{ display: "flex", alignItems: "center", gap: 6, background: BAD_BG, color: "#FCA5A5", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 20 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#FCA5A5", flexShrink: 0 }} />
                  {selected.kind === "ligne" ? selected.ligne : selected.kind === "colonne" ? selected.colonne : `${selected.ligne} · ${selected.colonne}`}
                </span>
              )}
              {pdfHref && (
                <a href={pdfHref} target="_blank" rel="noreferrer" style={{ display: "flex", alignItems: "center", gap: 5, color: "#93C5FD", fontSize: 11.5, fontWeight: 700, textDecoration: "none" }}>
                  Voir le PDF source ↗
                </a>
              )}
            </div>
          </div>

          <div style={{ flex: 1, overflow: "auto", padding: 26, display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
            {gridLoading ? (
              <p style={{ color: "#94A3B8", textAlign: "center", marginTop: 40 }}>Chargement…</p>
            ) : gridErreur ? (
              <p style={{ color: "#FCA5A5", textAlign: "center", marginTop: 40 }}>{gridErreur}</p>
            ) : !grid || grid.lignes.length === 0 ? (
              <p style={{ color: "#94A3B8", textAlign: "center", marginTop: 40 }}>Aucune cellule stockée pour cette combinaison.</p>
            ) : (
              // Pas de largeur figée : un tableau à beaucoup de colonnes doit
              // pousser cette carte plus large que l'écran et laisser le
              // conteneur parent défiler horizontalement plutôt que de
              // comprimer/couper les dernières colonnes.
              <div style={{ background: "#fff", borderRadius: 4, boxShadow: "0 8px 30px rgba(0,0,0,.35)", padding: "30px 34px", flexShrink: 0 }}>
                <table style={{ borderCollapse: "collapse", fontSize: 12.5 }}>
                  <thead>
                    <tr>
                      <th style={{ background: "#1D4E89", border: "1px solid #16406F" }} />
                      {grid.colonnes.map(col => {
                        const isSel = selected?.kind === "colonne" && selected.colonne === col;
                        const isCorr = corrections.has(`colonne::${col}`);
                        return (
                          <th
                            key={col}
                            onClick={() => selectColonne(col)}
                            title="Corriger le nom de cette colonne"
                            style={{
                              background: isCorr ? ACCENT : "#1D4E89", color: "#fff", padding: "8px 14px",
                              border: "1px solid #16406F", fontWeight: 700, whiteSpace: "nowrap", cursor: "pointer",
                              outline: isSel ? `2px solid ${BAD}` : "none", outlineOffset: -2,
                            }}
                          >
                            {displayColonne(col)}
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {grid.lignes.map(row => {
                      const isLigneSel = selected?.kind === "ligne" && selected.ligne === row.ligne;
                      const isLigneCorr = corrections.has(`ligne::${row.ligne}`);
                      return (
                        <tr key={row.ligne}>
                          <td
                            onClick={() => selectLigne(row.ligne)}
                            title="Corriger le nom de cette ligne"
                            style={{
                              padding: "7px 14px", border: "1px solid #E2E5EA", fontWeight: 600, whiteSpace: "nowrap", cursor: "pointer",
                              background: isLigneSel ? "#FDE8E8" : isLigneCorr ? ACCENT_BG : "#fff",
                              outline: isLigneSel ? `2px solid ${BAD}` : "none", outlineOffset: -2,
                            }}
                          >
                            {displayLigne(row.ligne)}
                          </td>
                          {grid.colonnes.map(col => {
                            const val = row.valeurs[col];
                            const key = `valeur::${row.ligne}|||${col}`;
                            const isSelected = selected?.kind === "valeur" && selected.ligne === row.ligne && selected.colonne === col;
                            const isCorrected = corrections.has(key);
                            return (
                              <td
                                key={col}
                                onClick={() => selectValeur(row.ligne, col, val)}
                                style={{
                                  padding: "7px 14px", border: "1px solid #E2E5EA", textAlign: "right", whiteSpace: "nowrap",
                                  fontVariantNumeric: "tabular-nums", cursor: "pointer",
                                  background: isSelected ? "#FDE8E8" : isCorrected ? ACCENT_BG : "#fff",
                                  outline: isSelected ? `2px solid ${BAD}` : "none", outlineOffset: -2,
                                }}
                              >
                                {isCorrected ? corrections.get(key).nouvelle : fmt(val)}
                              </td>
                            );
                          })}
                        </tr>
                      );
                    })}
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
