import { useState, useEffect, useMemo, useRef } from "react";
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

// Charte visuelle du VRAI fichier Excel généré (voir api/services/
// data_management.py::_write_full_grid_block / _REF_HEADER / _thin_border)
// — l'aperçu doit reproduire exactement ce à quoi ressemblera le fichier
// téléchargé, pas une mise en page propre à cette page.
const EXCEL_HEADER = "#5B6472";
const EXCEL_ZEBRA  = "#F3F4F6";
const EXCEL_TEXT   = "#2E2E38";
const EXCEL_BORDER = "1px solid #DDDDE3";

const ZOOM_MIN = 0.3;
const ZOOM_MAX = 3.0;

// Même format que la cellule Excel réelle (number_format "#,##0" — entier,
// séparateur de milliers, jamais de décimales).
function fmt(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return Math.round(n).toLocaleString("fr-TN", { maximumFractionDigits: 0 });
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

/* ═══════════════════════════ Menu déroulant de noms canoniques ═══════════════════════════
   Remplace le <select> natif (rendu par le navigateur, pas stylable, liste
   brute sans recherche) par un panneau cohérent avec le reste de l'appli —
   recherche + liste défilante, comme le sélecteur d'entreprise de Gestion
   de données. */
function NameSelect({ value, onChange, options, placeholder = "Choisir un nom…" }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef(null);

  useEffect(() => {
    function onDocClick(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const filtered = useMemo(() => {
    const q = query.toLowerCase();
    return q ? options.filter(o => o.toLowerCase().includes(q)) : options;
  }, [options, query]);

  return (
    <div ref={ref} style={{ position: "relative", flex: 1, minWidth: 0 }}>
      <button type="button" onClick={() => setOpen(o => !o)} style={{
        width: "100%", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
        padding: "8px 10px", borderRadius: 8, border: `1.5px solid ${ACCENT}`, background: "#fff",
        fontSize: 12.5, color: value ? DARK : MUTED, cursor: "pointer", font: "inherit", textAlign: "left",
      }}>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value || placeholder}</span>
        <span style={{ fontSize: 9, color: MUTED, transform: open ? "rotate(180deg)" : "none", flexShrink: 0 }}>▾</span>
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 40,
          background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 10,
          boxShadow: "0 10px 26px rgba(0,0,0,.14)", display: "flex", flexDirection: "column",
        }}>
          <input
            autoFocus value={query} onChange={e => setQuery(e.target.value)} placeholder="Rechercher…"
            style={{ margin: 6, padding: "7px 9px", border: `1px solid ${BORDER}`, borderRadius: 7, fontSize: 12.5, font: "inherit" }}
          />
          <div style={{ maxHeight: 220, overflowY: "auto", padding: "0 6px 6px" }}>
            {filtered.length === 0 ? (
              <div style={{ padding: 8, fontSize: 12, color: MUTED }}>Aucune correspondance.</div>
            ) : filtered.map(o => (
              <button
                key={o} type="button" onClick={() => { onChange(o); setOpen(false); setQuery(""); }}
                style={{
                  display: "block", width: "100%", textAlign: "left", padding: "7px 9px", borderRadius: 7,
                  border: "none", background: o === value ? ACCENT_BG : "transparent", color: DARK, fontSize: 12.5,
                  cursor: "pointer", font: "inherit",
                }}
                onMouseEnter={e => { if (o !== value) e.currentTarget.style.background = "#F8F9FC"; }}
                onMouseLeave={e => { if (o !== value) e.currentTarget.style.background = "transparent"; }}
              >
                {o}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════ Page ═══════════════════════════
   Consultation (et bientôt correction) d'un document CMF déjà en base,
   accessible directement depuis Gestion de données — même grammaire
   visuelle que KpiDetail (repère, visualiseur sombre). `Enregistrer tout`
   reste un espace réservé pour l'instant : l'écriture réelle en base est la
   prochaine étape. */
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
  const [corrections, setCorrections] = useState(new Map()); // key -> { kind, ligne, colonne, actuelle, nouvelle }
  const [saveNote, setSaveNote] = useState(null);

  // Zoom : `fitZoom` est calculé pour que le tableau tienne ENTIER dans le
  // visualiseur (ni trop petit pour être lisible, ni trop grand pour tenir
  // sans défiler) — c'est le niveau que "Réinitialiser" restaure, pas 100 %
  // fixe qui n'a pas de raison de convenir à un tableau à 2 colonnes comme à
  // un tableau à 10 branches.
  const [zoom, setZoom] = useState(1.0);
  const [fitZoom, setFitZoom] = useState(1.0);
  const viewerScrollRef = useRef(null);
  const tableCardRef = useRef(null);

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

  // Recalcule le zoom "ajusté" à chaque nouveau tableau chargé, pendant que
  // `zoom` vaut encore 1 (mesure de la taille NATURELLE de la carte, avant
  // toute mise à l'échelle) — comparée à la place réellement disponible
  // dans le visualiseur.
  useEffect(() => {
    if (!grid || grid.lignes.length === 0) return;
    const raf = requestAnimationFrame(() => {
      const card = tableCardRef.current;
      const scroller = viewerScrollRef.current;
      if (!card || !scroller || !card.offsetWidth || !card.offsetHeight) return;
      const availW = scroller.clientWidth - 52;
      const availH = scroller.clientHeight - 52;
      const fit = Math.min(availW / card.offsetWidth, availH / card.offsetHeight, 1);
      const clamped = Math.max(ZOOM_MIN, Math.min(1, +fit.toFixed(2)));
      setFitZoom(clamped);
      setZoom(clamped);
    });
    return () => cancelAnimationFrame(raf);
  }, [grid]);

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
    setNouvelleValeur("");
  };
  const selectLigne = (ligne) => {
    setSelected({ kind: "ligne", ligne, colonne: null, actuelle: displayLigne(ligne) });
    setNouvelleValeur(corrections.get(`ligne::${ligne}`)?.nouvelle ?? "");
  };
  const selectColonne = (colonne) => {
    setSelected({ kind: "colonne", ligne: null, colonne, actuelle: displayColonne(colonne) });
    setNouvelleValeur(corrections.get(`colonne::${colonne}`)?.nouvelle ?? "");
  };

  const ajouterCorrection = () => {
    if (!selected || !nouvelleValeur.trim() || nouvelleValeur.trim() === String(selected.actuelle ?? "")) return;
    const key = correctionKey(selected);
    setCorrections(prev => {
      const next = new Map(prev);
      next.set(key, { ...selected, nouvelle: nouvelleValeur.trim() });
      return next;
    });
    setNouvelleValeur(""); setSelected(null);
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

        {/* Localisation — repositionnée ici (sans titre de carte à part) pour
            libérer toute la hauteur du panneau gauche pour la correction
            elle-même ; juste à côté des onglets d'année, comme demandé. */}
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <span style={{ fontSize: 11.5, color: MUTED, whiteSpace: "nowrap" }}>
            {selected ? (
              selected.kind === "valeur"
                ? <>« {selected.ligne} » · « {selected.colonne} »</>
                : <>« {selected.kind === "ligne" ? selected.ligne : selected.colonne} » <span style={{ color: "#B0B6C2" }}>({selected.kind === "ligne" ? "ligne" : "colonne"})</span></>
            ) : "Aucune sélection"}
          </span>
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
      </div>

      {/* ── Corps : formulaire à gauche, visualiseur à droite ────────────── */}
      {/* Même proportion 1fr / 1fr que le corps de KpiDetail (page Qualité
          des données) — le visualiseur Excel occupe la même place que le
          visualiseur PDF là-bas, pas une colonne étroite à côté d'un
          panneau large. */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "calc(100vh - 92px - 58px)", overflow: "hidden" }}>
        {/* Gauche */}
        <div style={{ overflowY: "auto", padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
          {/* Résumé du document — une seule ligne compacte. */}
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

          {/* Correction — valeur (ancienne → saisie libre) ou nom (ancien →
              menu déroulant des noms déjà normalisés dans le code). */}
          <div style={{ background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 12, padding: "16px 18px" }}>
            <h3 style={{ margin: "0 0 10px", fontSize: 13.5, fontWeight: 800, color: DARK }}>Corriger</h3>
            {!selected ? (
              <p style={{ fontSize: 12.5, color: MUTED, margin: 0 }}>Cliquez une valeur, un nom de ligne ou de colonne dans le tableau à droite.</p>
            ) : (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
                    <NameSelect value={nouvelleValeur} onChange={setNouvelleValeur} options={options} />
                  ) : (
                    <input
                      value={nouvelleValeur} onChange={e => setNouvelleValeur(e.target.value)}
                      placeholder="Nouveau nom…" autoFocus
                      style={{ flex: 1, minWidth: 0, fontSize: 12.5, padding: "8px 10px", border: `1.5px solid ${ACCENT}`, borderRadius: 8, font: "inherit" }}
                    />
                  )}
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
            <h3 style={{ margin: "0 0 10px", fontSize: 13.5, fontWeight: 800, color: DARK }}>Corrections en attente</h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, overflowY: "auto" }}>
              {corrections.size === 0 ? (
                <div style={{ fontSize: 12, color: MUTED, textAlign: "center", padding: "12px 0" }}>Aucune correction en attente.</div>
              ) : [...corrections.entries()].map(([key, c]) => (
                <div key={key} onClick={() => (c.kind === "valeur" ? selectValeur(c.ligne, c.colonne, c.actuelle) : c.kind === "ligne" ? selectLigne(c.ligne) : selectColonne(c.colonne))} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "9px 10px", border: `1px solid ${BORDER}`,
                  borderRadius: 9, cursor: "pointer",
                }}>
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#B45309", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10.5, color: MUTED }}>
                      {c.kind === "valeur" ? `${c.ligne} · ${c.colonne}` : c.kind === "ligne" ? "Nom de ligne" : "Nom de colonne"}
                    </div>
                    <div style={{ fontSize: 12.5, fontWeight: 700, color: DARK, fontVariantNumeric: c.kind === "valeur" ? "tabular-nums" : "normal", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
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
              {pdfHref && (
                <a href={pdfHref} target="_blank" rel="noreferrer" style={{ display: "flex", alignItems: "center", gap: 5, color: "#93C5FD", fontSize: 11.5, fontWeight: 700, textDecoration: "none" }}>
                  Voir le PDF source ↗
                </a>
              )}
            </div>
          </div>

          {/* Barre de contrôles zoom — identique à celle du visualiseur PDF
              de KpiDetail (Qualité des données) : mêmes boutons, mêmes
              couleurs. "Réinitialiser" restaure le zoom AJUSTÉ (tableau
              entier visible), pas 100 % fixe. */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "center",
            gap: 8, padding: "6px 10px",
            background: "#1E293B", borderBottom: "1px solid #334155",
          }}>
            <button onClick={() => setZoom(z => Math.max(ZOOM_MIN, +(z - 0.1).toFixed(2)))}
              style={{ background: "#334155", border: "none", borderRadius: 6, color: "#CBD5E1",
                width: 28, height: 28, cursor: "pointer", fontSize: 16, lineHeight: 1 }}>−</button>
            <span style={{ fontSize: 12, color: "#94A3B8", minWidth: 44, textAlign: "center" }}>
              {Math.round(zoom * 100)} %
            </span>
            <button onClick={() => setZoom(z => Math.min(ZOOM_MAX, +(z + 0.1).toFixed(2)))}
              style={{ background: "#334155", border: "none", borderRadius: 6, color: "#CBD5E1",
                width: 28, height: 28, cursor: "pointer", fontSize: 16, lineHeight: 1 }}>+</button>
            <span style={{ width: 1, alignSelf: "stretch", background: "#334155", margin: "0 2px" }} />
            <button onClick={() => setZoom(fitZoom)}
              title="Revenir au zoom ajusté (tableau entier visible)"
              style={{ background: "none", border: "1px solid #334155", borderRadius: 6,
                color: "#64748B", fontSize: 10, padding: "3px 8px", cursor: "pointer" }}>Réinitialiser</button>
          </div>

          <div ref={viewerScrollRef} style={{ flex: 1, overflow: "auto", padding: 26, display: "flex", justifyContent: "center", alignItems: "flex-start" }}>
            {gridLoading ? (
              <p style={{ color: "#94A3B8", textAlign: "center", marginTop: 40 }}>Chargement…</p>
            ) : gridErreur ? (
              <p style={{ color: "#FCA5A5", textAlign: "center", marginTop: 40 }}>{gridErreur}</p>
            ) : !grid || grid.lignes.length === 0 ? (
              <p style={{ color: "#94A3B8", textAlign: "center", marginTop: 40 }}>Aucune cellule stockée pour cette combinaison.</p>
            ) : (
              // Même charte que le vrai fichier généré par
              // build_flexible_export_xlsx::_write_full_grid_block (en-tête
              // gris #5B6472/texte blanc, libellés en MAJUSCULES, police
              // Arial, lignes zébrées blanc/#F3F4F6, valeurs centrées) —
              // sans le titre au-dessus, uniquement le tableau. `zoom` est
              // appliqué en CSS `zoom` (pas `transform`) pour que la mesure
              // de taille naturelle (voir l'effet ci-dessus) et le calcul du
              // zoom ajusté restent cohérents avec le flux normal du DOM.
              <div ref={tableCardRef} style={{ background: "#fff", borderRadius: 4, boxShadow: "0 8px 30px rgba(0,0,0,.35)", padding: "30px 34px", flexShrink: 0, zoom }}>
                <table style={{ borderCollapse: "collapse", fontSize: 12.5, fontFamily: "Arial, sans-serif" }}>
                  <thead>
                    <tr>
                      <th style={{ background: EXCEL_HEADER, color: "#fff", padding: "8px 14px", border: EXCEL_BORDER, fontWeight: 700 }}>LIBELLÉ</th>
                      {grid.colonnes.map(col => {
                        const isSel = selected?.kind === "colonne" && selected.colonne === col;
                        const isCorr = corrections.has(`colonne::${col}`);
                        return (
                          <th
                            key={col}
                            onClick={() => selectColonne(col)}
                            title="Corriger le nom de cette colonne"
                            style={{
                              background: isCorr ? ACCENT : EXCEL_HEADER, color: "#fff", padding: "8px 14px",
                              border: EXCEL_BORDER, fontWeight: 700, whiteSpace: "nowrap", cursor: "pointer", textAlign: "center",
                              outline: isSel ? `2px solid ${BAD}` : "none", outlineOffset: -2,
                            }}
                          >
                            {displayColonne(col).toUpperCase()}
                          </th>
                        );
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {grid.lignes.map((row, i) => {
                      const zebra = i % 2 === 1;
                      const isLigneSel = selected?.kind === "ligne" && selected.ligne === row.ligne;
                      const isLigneCorr = corrections.has(`ligne::${row.ligne}`);
                      return (
                        <tr key={row.ligne}>
                          <td
                            onClick={() => selectLigne(row.ligne)}
                            title="Corriger le nom de cette ligne"
                            style={{
                              padding: "7px 14px", border: EXCEL_BORDER, color: EXCEL_TEXT, whiteSpace: "nowrap", cursor: "pointer", textAlign: "left",
                              background: isLigneSel ? "#FDE8E8" : isLigneCorr ? ACCENT_BG : zebra ? EXCEL_ZEBRA : "#fff",
                              outline: isLigneSel ? `2px solid ${BAD}` : "none", outlineOffset: -2,
                            }}
                          >
                            {displayLigne(row.ligne).toUpperCase()}
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
                                  padding: "7px 14px", border: EXCEL_BORDER, textAlign: "center", whiteSpace: "nowrap",
                                  color: EXCEL_TEXT, cursor: "pointer",
                                  background: isSelected ? "#FDE8E8" : isCorrected ? ACCENT_BG : zebra ? EXCEL_ZEBRA : "#fff",
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
