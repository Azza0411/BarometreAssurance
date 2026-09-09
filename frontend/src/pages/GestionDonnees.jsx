import { useState, useEffect, useCallback, useRef, useMemo } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const DARK    = "#2E2E38";
const YELLOW  = "#FFE600";
const BG      = "#F2F5FB";
const BORDER  = "#DDE2EC";
const MUTED   = "#6B7280";
const ACCENT  = "#0F6E56";
const ACCENT_BG = "#E1F5EE";

const PAGE_SIZE = 15;

function Card({ children, style }) {
  return (
    <div style={{
      background: "#fff", borderRadius: 14, border: `1px solid ${BORDER}`,
      boxShadow: "0 2px 10px rgba(0,0,0,0.05)", padding: "20px 24px", ...style,
    }}>{children}</div>
  );
}

// Style de bouton commun aux 3 actions principales (Collecte, Exporter,
// Générer l'export) — retour utilisateur : le bloc plein DARK/YELLOW était
// jugé trop sombre / pas assez minimaliste. Contour clair + accent teal au
// lieu d'un pavé sombre.
function actionBtnStyle(disabled) {
  return {
    padding: "9px 16px", borderRadius: 8, fontSize: 12.5, fontWeight: 700,
    cursor: disabled ? "not-allowed" : "pointer",
    border: `1.5px solid ${disabled ? BORDER : ACCENT}`,
    background: "#fff", color: disabled ? "#9CA3AF" : ACCENT,
    display: "flex", alignItems: "center", justifyContent: "center", gap: 7, whiteSpace: "nowrap",
    transition: "background .12s",
  };
}

/* ═══════════════════════════ Collecte (bande compacte) ═══════════════════════════ */
function CollecteBar() {
  const [statut, setStatut] = useState(null);
  const [lancement, setLancement] = useState(false);
  const [erreur, setErreur] = useState(null);
  const pollRef = useRef(null);

  const fetchStatut = useCallback(() => {
    fetch(`${API}/api/gestion-donnees/statut-collecte`)
      .then(r => r.json())
      .then(setStatut)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchStatut();
    return () => clearInterval(pollRef.current);
  }, [fetchStatut]);

  useEffect(() => {
    if (statut?.en_cours) {
      pollRef.current = setInterval(fetchStatut, 4000);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [statut?.en_cours, fetchStatut]);

  const lancer = () => {
    setErreur(null);
    setLancement(true);
    fetch(`${API}/api/gestion-donnees/lancer-collecte`, { method: "POST" })
      .then(async r => {
        if (r.status === 409) { setErreur("Une collecte est déjà en cours."); return; }
        if (!r.ok) { setErreur("Échec du lancement."); return; }
        fetchStatut();
      })
      .catch(() => setErreur("Échec du lancement (API injoignable)."))
      .finally(() => setLancement(false));
  };

  const derniere = statut?.derniere_execution;
  const enCours = statut?.en_cours;

  return (
    <Card style={{ padding: "14px 20px" }}>
      {erreur && <div style={{ marginBottom: 8, fontSize: 12, color: "#C8102E", fontWeight: 600 }}>{erreur}</div>}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 3 }}>
            Collecte des données
          </div>
          <div style={{ fontSize: 12.5, color: DARK }}>
            {enCours ? (
              <span>Collecte en cours — reprise automatique en cas d'échec (~quelques minutes)…</span>
            ) : derniere ? (
              <span>
                Dernière exécution : <b>{derniere.ts?.replace("T", " ").slice(0, 16)}</b>
                {" · "}durée {derniere.duration_s ?? "?"}s
                {derniere.failed_sources?.length
                  ? <span style={{ color: "#C8102E", fontWeight: 700 }}> · {derniere.failed_sources.length} source(s) en échec</span>
                  : <span style={{ color: "#16A34A", fontWeight: 700 }}> · toutes sources OK</span>}
              </span>
            ) : (
              <span>Aucune exécution enregistrée pour l'instant.</span>
            )}
          </div>
        </div>
        <button onClick={lancer} disabled={enCours || lancement} style={actionBtnStyle(enCours || lancement)}
          onMouseEnter={e => !(enCours || lancement) && (e.currentTarget.style.background = ACCENT_BG)}
          onMouseLeave={e => (e.currentTarget.style.background = "#fff")}>
          {enCours ? "⏳ Collecte en cours…" : "▶ Lancer une nouvelle collecte"}
        </button>
      </div>
    </Card>
  );
}

/* ═══════════════════════════ Documents ═══════════════════════════ */
function DocumentsPanel({ onExporter }) {
  const [docs, setDocs] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/documents`).then(r => r.json()).then(setDocs).catch(() => setDocs([]));
  }, []);

  // Uniquement CMF pour l'instant — seule source couverte par la pipeline
  // d'extraction/validation ; les autres sources (CGA, FTUSA, BVMT, INS,
  // Enquête) reviendront quand elles seront traitées de la même façon.
  const cmfDocs = useMemo(() => (docs ?? []).filter(d => d.source === "CMF"), [docs]);
  const filtered = useMemo(() => cmfDocs
    .filter(d => !search || `${d.code ?? ""} ${d.nom_entreprise ?? ""} ${d.nom_pdf}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => b.annee - a.annee), // le plus recent d'abord
  [cmfDocs, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const pageRows = filtered.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);

  return (
    <Card style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: DARK }}>Documents</h2>
          <span style={{ fontSize: 11, background: BORDER, color: MUTED, padding: "1px 9px", borderRadius: 20, fontWeight: 700 }}>
            {cmfDocs.length}
          </span>
          <span style={{ fontSize: 10.5, fontWeight: 700, color: MUTED, background: "#F3F4F6", padding: "3px 9px", borderRadius: 6 }}>
            Source : CMF
          </span>
        </div>
        <button onClick={() => onExporter(null, null)} style={actionBtnStyle(false)}
          onMouseEnter={e => (e.currentTarget.style.background = ACCENT_BG)}
          onMouseLeave={e => (e.currentTarget.style.background = "#fff")}>
          ⬇ Exporter des données
        </button>
      </div>
      <p style={{ margin: "4px 0 14px", fontSize: 11.5, color: MUTED }}>
        Cliquez une ligne pour exporter directement cette société/année, ou le bouton ci-dessus pour un export libre.
      </p>

      <input
        placeholder="Rechercher (société, fichier…)"
        value={search}
        onChange={e => { setSearch(e.target.value); setPage(1); }}
        style={{ padding: "8px 14px", borderRadius: 8, border: `1px solid ${BORDER}`, fontSize: 12, width: "100%", marginBottom: 12 }}
      />

      <div style={{ border: `1px solid ${BORDER}`, borderRadius: 10, overflow: "hidden" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead>
            <tr style={{ background: "#F8F9FC" }}>
              {["Société", "Fichier", "Année", "Local", ""].map((h, i) => (
                <th key={i} style={{ textAlign: "left", padding: "9px 12px", fontWeight: 700, color: MUTED, fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".3px", borderBottom: `1px solid ${BORDER}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!docs ? (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: "center", color: MUTED }}>Chargement…</td></tr>
            ) : pageRows.length === 0 ? (
              <tr><td colSpan={5} style={{ padding: 24, textAlign: "center", color: MUTED }}>Aucun document.</td></tr>
            ) : pageRows.map(d => (
              <tr
                key={d.id}
                onClick={() => onExporter(d.code, d.annee)}
                style={{ borderBottom: "1px solid #F0F1F5", cursor: d.code ? "pointer" : "default" }}
                onMouseEnter={e => (e.currentTarget.style.background = ACCENT_BG)}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
              >
                <td style={{ padding: "8px 12px" }}>{d.nom_entreprise ?? d.code ?? "—"}</td>
                <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 11.5, color: "#4B5563" }}>{d.nom_pdf}</td>
                <td style={{ padding: "8px 12px" }}>{d.annee}</td>
                <td style={{ padding: "8px 12px" }}>
                  {d.fichier_local
                    ? <span style={{ color: "#16A34A", fontWeight: 700 }}>✓ oui</span>
                    : <span style={{ color: "#9CA3AF" }}>— non</span>}
                </td>
                <td style={{ padding: "8px 12px", textAlign: "right" }}>
                  {(d.fichier_local || d.lien) && (
                    <a
                      href={d.fichier_local ? `${API}/api/gestion-donnees/documents/${d.id}/pdf` : d.lien}
                      target="_blank" rel="noreferrer"
                      onClick={e => e.stopPropagation()}
                      style={{
                        color: ACCENT, background: ACCENT_BG, fontWeight: 700, fontSize: 11.5,
                        padding: "5px 10px", borderRadius: 6, textDecoration: "none", whiteSpace: "nowrap",
                      }}>
                      Voir le PDF ↗
                    </a>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 12, fontSize: 12, color: MUTED }}>
        <span>{filtered.length} document(s) · page {pageSafe}/{totalPages}</span>
        <span style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={pageSafe <= 1}
            style={{ border: `1px solid ${BORDER}`, background: "#fff", borderRadius: 6, padding: "5px 12px", fontSize: 12, cursor: pageSafe <= 1 ? "not-allowed" : "pointer", opacity: pageSafe <= 1 ? .5 : 1 }}>
            ‹ Précédent
          </button>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={pageSafe >= totalPages}
            style={{ border: `1px solid ${BORDER}`, background: "#fff", borderRadius: 6, padding: "5px 12px", fontSize: 12, cursor: pageSafe >= totalPages ? "not-allowed" : "pointer", opacity: pageSafe >= totalPages ? .5 : 1 }}>
            Suivant ›
          </button>
        </span>
      </div>
    </Card>
  );
}

/* ═══════════════════════════ Export Excel (tiroir) ═══════════════════════════ */
function ExportDrawer({ open, prefill, onClose }) {
  const [opts, setOpts] = useState(null);
  const [tableau, setTableau] = useState("");
  const [societe, setSociete] = useState("");
  const [annee, setAnnee] = useState("");

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/filtres`).then(r => r.json()).then(setOpts).catch(() => {});
  }, []);

  useEffect(() => {
    if (!open) return;
    setSociete(prefill?.societe ?? "");
    setAnnee(prefill?.annee ? String(prefill.annee) : "");
    if (!prefill) setTableau("");
  }, [open, prefill]);

  const buildUrl = () => {
    const p = new URLSearchParams();
    if (tableau) p.append("tableau", tableau);
    if (societe) p.append("societe", societe);
    if (annee) p.append("annee", annee);
    return `${API}/api/gestion-donnees/export.xlsx?${p.toString()}`;
  };

  // Sélection compacte (retour utilisateur : la phrase à menus déroulants
  // dorés était jugée "pas moderne du tout" et "trop d'espace") — 3 champs
  // courts, un par filtre, avec micro-étiquette au-dessus, plutôt qu'une
  // grande ligne de texte.
  const fieldWrap = { flex: 1, minWidth: 0 };
  const fieldLabel = { display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 5 };
  const compactSelect = {
    width: "100%", appearance: "none", background: "#fff", color: DARK,
    border: `1px solid ${BORDER}`, borderRadius: 8, font: "inherit", fontSize: 12.5,
    padding: "8px 26px 8px 10px", cursor: "pointer",
    backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%236B7280'/%3E%3C/svg%3E\")",
    backgroundRepeat: "no-repeat", backgroundPosition: "right 9px center",
  };
  const resume = () => {
    const t = tableau ? (opts?.tableaux.find(x => x.key === tableau)?.label ?? tableau) : "tous les tableaux";
    const s = societe || "toutes les sociétés";
    const a = annee || "toutes les années";
    return `${t} · ${s} · ${a}`;
  };

  return (
    <div style={{
      width: open ? 380 : 0, opacity: open ? 1 : 0, padding: open ? "20px 22px" : 0,
      border: open ? `1px solid ${BORDER}` : "none", overflow: "hidden", flexShrink: 0,
      background: "#fff", borderRadius: 14, boxShadow: open ? "0 2px 10px rgba(0,0,0,0.05)" : "none",
      transition: "width .38s cubic-bezier(.2,.8,.2,1), opacity .25s ease, padding .38s, border-width .38s",
    }}>
      <div style={{ minWidth: 336 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: DARK }}>Export Excel</h2>
          <button onClick={onClose} aria-label="Fermer" style={{
            background: "none", border: `1px solid ${BORDER}`, borderRadius: 8, width: 30, height: 30,
            cursor: "pointer", fontSize: 14, color: DARK,
          }}>✕</button>
        </div>
        {prefill?.societe && (
          <p style={{ margin: "10px 0 0", fontSize: 11.5, color: ACCENT, fontWeight: 700 }}>
            Pré-rempli depuis {prefill.societe}{prefill.annee ? ` · ${prefill.annee}` : ""}
          </p>
        )}

        {!opts ? (
          <div style={{ color: MUTED, fontSize: 12.5, marginTop: 16 }}>Chargement des filtres…</div>
        ) : (
          <>
            <div style={{ display: "flex", gap: 10, margin: "18px 0 10px" }}>
              <div style={fieldWrap}>
                <label style={fieldLabel}>Tableau</label>
                <select value={tableau} onChange={e => setTableau(e.target.value)} style={compactSelect}>
                  <option value="">Tous</option>
                  {opts.tableaux.map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
                </select>
              </div>
              <div style={fieldWrap}>
                <label style={fieldLabel}>Société</label>
                <select value={societe} onChange={e => setSociete(e.target.value)} style={compactSelect}>
                  <option value="">Toutes</option>
                  {opts.societes.map(s => <option key={s.code} value={s.code}>{s.code}</option>)}
                </select>
              </div>
              <div style={fieldWrap}>
                <label style={fieldLabel}>Année</label>
                <select value={annee} onChange={e => setAnnee(e.target.value)} style={compactSelect}>
                  <option value="">Toutes</option>
                  {opts.annees.map(a => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>
            </div>

            <p style={{ fontSize: 11.5, color: MUTED, margin: "0 0 18px" }}>
              Sélection : {resume()}
            </p>

            <a href={buildUrl()} style={{ ...actionBtnStyle(false), textDecoration: "none", padding: "11px 20px" }}
              onMouseEnter={e => (e.currentTarget.style.background = ACCENT_BG)}
              onMouseLeave={e => (e.currentTarget.style.background = "#fff")}>
              ⬇ Générer l'export Excel
            </a>
            <p style={{ fontSize: 10.5, color: "#9CA3AF", margin: "8px 0 0" }}>
              Une feuille par société, un tableau réel par annexe demandée.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════ Page ═══════════════════════════ */
export default function GestionDonnees() {
  const [exportOpen, setExportOpen] = useState(false);
  const [prefill, setPrefill] = useState(null);

  const ouvrirExport = (societe, annee) => {
    setPrefill(societe || annee ? { societe, annee } : null);
    setExportOpen(true);
  };

  return (
    <div style={{ minHeight: "100vh", background: BG, fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ background: DARK, padding: "20px 32px" }}>
        <div style={{ maxWidth: 1220, margin: "0 auto" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,230,0,.7)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 4 }}>
            Data Management · EY
          </div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "white" }}>Gestion de base de données</h1>
          <p style={{ margin: "4px 0 0", fontSize: 11.5, color: "rgba(255,255,255,.45)" }}>
            Accès à toute la donnée collectée — parcourir les documents, exporter n'importe quel extrait en Excel.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 1220, margin: "0 auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: 16 }}>
        <CollecteBar />
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
          <DocumentsPanel onExporter={ouvrirExport} />
          <ExportDrawer open={exportOpen} prefill={prefill} onClose={() => setExportOpen(false)} />
        </div>
      </div>
    </div>
  );
}
