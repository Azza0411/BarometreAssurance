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

// Indicateur de chargement — retour utilisateur : une action longue
// (collecte, export) laissait la page silencieuse/figée pendant l'attente,
// sans distinguer "ça travaille" de "rien ne se passe". `color` hérite de
// currentColor par défaut pour s'accorder au texte du bouton qui l'utilise.
function Spinner({ size = 13, color = "currentColor" }) {
  return (
    <span
      aria-label="Chargement en cours" role="status"
      style={{
        display: "inline-block", width: size, height: size, borderRadius: "50%",
        border: `2px solid ${color}`, borderTopColor: "transparent",
        animation: "gd-spin .7s linear infinite", flexShrink: 0,
      }}
    />
  );
}
// Keyframes injectées une seule fois (pas de fichier CSS séparé pour ce module).
if (typeof document !== "undefined" && !document.getElementById("gd-spin-kf")) {
  const style = document.createElement("style");
  style.id = "gd-spin-kf";
  style.textContent = "@keyframes gd-spin{to{transform:rotate(360deg)}}";
  document.head.appendChild(style);
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

  const [annulation, setAnnulation] = useState(false);

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

  const annuler = () => {
    setErreur(null);
    setAnnulation(true);
    fetch(`${API}/api/gestion-donnees/annuler-collecte`, { method: "POST" })
      .then(async r => {
        if (!r.ok) { setErreur("Échec de l'annulation."); return; }
        fetchStatut();
      })
      .catch(() => setErreur("Échec de l'annulation (API injoignable)."))
      .finally(() => setAnnulation(false));
  };

  const derniere = statut?.derniere_execution;
  const enCours = statut?.en_cours;
  const annulationDemandee = statut?.annulation_demandee;

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
              annulationDemandee
                ? <span>Annulation en cours — arrêt au prochain document/société traité…</span>
                : <span>Collecte en cours — seuls les documents nouveaux ou jamais traités sont extraits…</span>
            ) : derniere ? (
              <span>
                Dernière exécution : <b>{derniere.ts?.replace("T", " ").slice(0, 16)}</b>
                {" · "}durée {derniere.duration_s ?? "?"}s
                {derniere.cancelled
                  ? <span style={{ color: "#B45309", fontWeight: 700 }}> · annulée</span>
                  : derniere.failed_sources?.length
                    ? <span style={{ color: "#C8102E", fontWeight: 700 }}> · {derniere.failed_sources.length} source(s) en échec</span>
                    : <span style={{ color: "#16A34A", fontWeight: 700 }}> · toutes sources OK</span>}
              </span>
            ) : (
              <span>Aucune exécution enregistrée pour l'instant.</span>
            )}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {enCours && (
            <button onClick={annuler} disabled={annulation || annulationDemandee}
              style={{ ...actionBtnStyle(annulation || annulationDemandee), borderColor: "#C8102E", color: "#C8102E" }}
              onMouseEnter={e => !(annulation || annulationDemandee) && (e.currentTarget.style.background = "#FDECEC")}
              onMouseLeave={e => (e.currentTarget.style.background = "#fff")}>
              {annulationDemandee && <Spinner />}
              {annulationDemandee ? "Annulation…" : "Annuler"}
            </button>
          )}
          <button onClick={lancer} disabled={enCours || lancement} style={actionBtnStyle(enCours || lancement)}
            onMouseEnter={e => !(enCours || lancement) && (e.currentTarget.style.background = ACCENT_BG)}
            onMouseLeave={e => (e.currentTarget.style.background = "#fff")}>
            {(enCours || lancement) && <Spinner />}
            {enCours ? "Collecte en cours…" : "Lancer une nouvelle collecte"}
          </button>
        </div>
      </div>
    </Card>
  );
}

/* ═══════════════════════════ Fiabilité (indicateurs réels) ═══════════════════════════ */
function StatChip({ label, pct, detail }) {
  const color = pct == null ? MUTED : pct >= 90 ? "#16A34A" : pct >= 70 ? "#B45309" : "#C8102E";
  return (
    <div style={{ flex: 1, minWidth: 200 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 3 }}>
        {label}
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
        <span style={{ fontSize: 20, fontWeight: 800, color }}>{pct == null ? "—" : `${pct}%`}</span>
        <span style={{ fontSize: 11.5, color: MUTED }}>{detail}</span>
      </div>
    </div>
  );
}

function FiabiliteBar() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/fiabilite`).then(r => r.json()).then(setStats).catch(() => {});
  }, []);

  if (!stats) return null;
  const { collecte, fiabilite_extraction: fe } = stats;

  return (
    <Card style={{ padding: "14px 20px" }}>
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <StatChip
          label="PDF collectés"
          pct={collecte.pct}
          detail={`${collecte.collectes} / ${collecte.total} attendus`}
        />
        <StatChip
          label={`Fiabilité de l'extraction (${fe.tableau})`}
          pct={fe.pct}
          detail={`${fe.reussis} / ${fe.total} documents extraits avec succès`}
        />
      </div>
      <p style={{ fontSize: 10.5, color: "#9CA3AF", margin: "10px 0 0" }}>
        Collecte : PDF présents sur les exercices attendus pour chaque société. Fiabilité : documents dont l'extraction
        complète a abouti, parmi les sociétés éligibles à l'Annexe 13 Non-Vie (hors sociétés Vie/Takaful).
      </p>
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
          Exporter des données
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
              {["Société", "Fichier", "Année", ""].map((h, i) => (
                <th key={i} style={{ textAlign: "left", padding: "9px 12px", fontWeight: 700, color: MUTED, fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".3px", borderBottom: `1px solid ${BORDER}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!docs ? (
              <tr><td colSpan={4} style={{ padding: 24, textAlign: "center", color: MUTED }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><Spinner color={MUTED} /> Chargement…</span>
              </td></tr>
            ) : pageRows.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: 24, textAlign: "center", color: MUTED }}>Aucun document.</td></tr>
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

// Micro-étiquette + zone de champ compacte partagées par les 3 filtres.
const fieldWrap = { flex: 1, minWidth: 0, position: "relative" };
const fieldLabel = { display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 5 };

// Sélection multiple compacte — retour utilisateur : pouvoir choisir
// plusieurs sociétés/années/tableaux à la fois (le backend le supportait
// déjà via des paramètres répétés, seule l'interface ne le permettait pas).
// Un bouton façon menu déroulant qui ouvre un panneau à cases à cocher,
// plutôt qu'un mur de puces (déjà écarté comme trop volumineux) ou un
// <select multiple> natif (peu intuitif, nécessite ctrl/cmd+clic).
function MultiSelect({ label, options, selected, onToggle, allLabel = "Toutes", disabledSet, disabledHint }) {
  const [openMenu, setOpenMenu] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onDocClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpenMenu(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const summary = selected.size === 0
    ? allLabel
    : selected.size === 1
      ? (options.find(o => o.value === [...selected][0])?.label ?? [...selected][0])
      : `${selected.size} sélectionnées`;

  return (
    <div ref={ref} style={fieldWrap}>
      <label style={fieldLabel}>{label}</label>
      <button
        type="button" onClick={() => setOpenMenu(o => !o)}
        style={{
          width: "100%", textAlign: "left", background: "#fff", color: selected.size ? DARK : "#9CA3AF",
          border: `1px solid ${openMenu ? ACCENT : BORDER}`, borderRadius: 8, font: "inherit", fontSize: 12.5,
          padding: "8px 26px 8px 10px", cursor: "pointer", position: "relative",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
        {summary}
        <span style={{ position: "absolute", right: 9, top: "50%", transform: `translateY(-50%) ${openMenu ? "rotate(180deg)" : ""}`, fontSize: 9, color: MUTED }}>▾</span>
      </button>
      {openMenu && (
        <div style={{
          position: "absolute", top: "100%", left: 0, right: 0, marginTop: 4, zIndex: 30,
          background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 8,
          boxShadow: "0 6px 18px rgba(0,0,0,.1)", maxHeight: 230, overflowY: "auto", padding: 4,
        }}>
          {options.map(o => {
            const isDisabled = disabledSet?.has(o.value);
            return (
              <label key={o.value}
                title={isDisabled ? disabledHint : undefined}
                style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", fontSize: 12.5,
                  cursor: isDisabled ? "not-allowed" : "pointer", borderRadius: 6,
                  color: isDisabled ? "#C2C6D2" : DARK,
                }}
                onMouseEnter={e => { if (!isDisabled) e.currentTarget.style.background = "#F8F9FC"; }}
                onMouseLeave={e => (e.currentTarget.style.background = "transparent")}>
                <input type="checkbox" checked={selected.has(o.value)} disabled={isDisabled}
                  onChange={() => onToggle(o.value)} />
                {o.label}
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════ Export Excel (tiroir) ═══════════════════════════ */
function ExportDrawer({ open, prefill, onClose }) {
  const [opts, setOpts] = useState(null);
  const [tableaux, setTableaux] = useState(new Set());
  const [societes, setSocietes] = useState(new Set());
  const [annees, setAnnees] = useState(new Set());
  const [exportLoading, setExportLoading] = useState(false);
  const [exportErreur, setExportErreur] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/filtres`).then(r => r.json()).then(setOpts).catch(() => {});
  }, []);

  useEffect(() => {
    if (!open) return;
    setSocietes(prefill?.societe ? new Set([prefill.societe]) : new Set());
    setAnnees(prefill?.annee ? new Set([String(prefill.annee)]) : new Set());
    if (!prefill) setTableaux(new Set());
  }, [open, prefill]);

  const toggleIn = (setter) => (value) => setter(prev => {
    const next = new Set(prev);
    next.has(value) ? next.delete(value) : next.add(value);
    return next;
  });

  // Sociétés éligibles pour la sélection de tableau en cours — retour
  // utilisateur : une société sans AUCUNE donnée pour un tableau choisi (ex.
  // ATTIJARI/UIB pour l'Annexe 13, sociétés Vie exclusivement) doit être
  // désactivée dans le sélecteur plutôt que de rester choisissable pour
  // produire un export vide. Aucun tableau sélectionné = tous éligibles
  // (pas de filtre). Plusieurs tableaux sélectionnés = éligible si la
  // société a AU MOINS UN des tableaux choisis (union, pas intersection —
  // sinon une société qui n'a que l'Annexe 12 serait exclue dès qu'on
  // ajoute l'Annexe 13 à la sélection).
  const societesDisabled = useMemo(() => {
    if (!opts?.societes_par_tableau || tableaux.size === 0) return new Set();
    const eligible = new Set();
    tableaux.forEach(t => (opts.societes_par_tableau[t] || []).forEach(c => eligible.add(c)));
    // Filet de sécurité : si `eligible` finit vide alors qu'un tableau EST
    // sélectionné, c'est que la donnée n'est structurellement pas dispo côté
    // client (jamais le cas réel — chaque groupe a au moins une société) —
    // ne désactive personne plutôt que de bloquer tout le sélecteur (repli
    // "fail open", pas "fail closed").
    if (eligible.size === 0) return new Set();
    return new Set(opts.societes.map(s => s.code).filter(c => !eligible.has(c)));
  }, [opts, tableaux]);

  // Une société déjà cochée qui devient désactivée (l'utilisateur change la
  // sélection de tableau après coup) est retirée automatiquement — jamais
  // laissée sélectionnée mais grisée/invisible dans son propre résumé.
  useEffect(() => {
    if (societesDisabled.size === 0) return;
    setSocietes(prev => {
      const next = new Set([...prev].filter(c => !societesDisabled.has(c)));
      return next.size === prev.size ? prev : next;
    });
  }, [societesDisabled]);

  const buildUrl = () => {
    const p = new URLSearchParams();
    tableaux.forEach(t => p.append("tableau", t));
    societes.forEach(s => p.append("societe", s));
    annees.forEach(a => p.append("annee", a));
    return `${API}/api/gestion-donnees/export.xlsx?${p.toString()}`;
  };

  const resume = () => {
    const t = tableaux.size ? `${tableaux.size} tableau(x)` : "tous les tableaux";
    const s = societes.size ? [...societes].join(", ") : "toutes les sociétés";
    const a = annees.size ? [...annees].sort().join(", ") : "toutes les années";
    return `${t} · ${s} · ${a}`;
  };

  // Génère l'export via fetch (au lieu d'un <a href> nu) pour pouvoir
  // afficher un indicateur de chargement — retour utilisateur : une
  // génération large peut prendre jusqu'à ~1-2 minutes (voir le plafond
  // d'extraction live côté serveur), la page restait silencieuse pendant
  // l'attente. Le téléchargement lui-même est déclenché en JS une fois le
  // fichier reçu (lien blob synthétique, jamais visible de l'utilisateur).
  const genererExport = () => {
    setExportErreur(null);
    setExportLoading(true);
    fetch(buildUrl())
      .then(async r => {
        if (!r.ok) throw new Error("echec");
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "Export_donnees.xlsx";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      })
      .catch(() => setExportErreur("Échec de la génération de l'export."))
      .finally(() => setExportLoading(false));
  };

  return (
    <div style={{
      width: open ? 460 : 0, opacity: open ? 1 : 0, padding: open ? "20px 22px" : 0,
      border: open ? `1px solid ${BORDER}` : "none", overflow: open ? "visible" : "hidden", flexShrink: 0,
      background: "#fff", borderRadius: 14, boxShadow: open ? "0 2px 10px rgba(0,0,0,0.05)" : "none",
      transition: "width .38s cubic-bezier(.2,.8,.2,1), opacity .25s ease, padding .38s, border-width .38s",
    }}>
      <div style={{ minWidth: 416 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
          <h2 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: DARK }}>Export Excel</h2>
          <button onClick={onClose} aria-label="Fermer" style={{
            background: "none", border: `1px solid ${BORDER}`, borderRadius: 8, width: 30, height: 30,
            cursor: "pointer", fontSize: 14, color: DARK,
          }}>×</button>
        </div>
        {prefill?.societe && (
          <p style={{ margin: "10px 0 0", fontSize: 11.5, color: ACCENT, fontWeight: 700 }}>
            Pré-rempli depuis {prefill.societe}{prefill.annee ? ` · ${prefill.annee}` : ""}
          </p>
        )}

        {!opts ? (
          <div style={{ color: MUTED, fontSize: 12.5, marginTop: 16, display: "flex", alignItems: "center", gap: 8 }}>
            <Spinner color={MUTED} /> Chargement des filtres…
          </div>
        ) : (
          <>
            <div style={{ margin: "18px 0 10px", display: "flex", flexDirection: "column", gap: 10 }}>
              <MultiSelect
                label="Tableau"
                options={opts.tableaux.map(t => ({ value: t.key, label: t.label }))}
                selected={tableaux} onToggle={toggleIn(setTableaux)}
              />
              <div style={{ display: "flex", gap: 10 }}>
                <MultiSelect
                  label="Société"
                  options={opts.societes.map(s => ({ value: s.code, label: s.code }))}
                  selected={societes} onToggle={toggleIn(setSocietes)}
                  disabledSet={societesDisabled}
                  disabledHint="Aucune donnée pour le(s) tableau(x) sélectionné(s)"
                />
                <MultiSelect
                  label="Année"
                  options={opts.annees.map(a => ({ value: String(a), label: String(a) }))}
                  selected={annees} onToggle={toggleIn(setAnnees)}
                />
              </div>
            </div>
            <p style={{ fontSize: 10.5, color: "#9CA3AF", margin: "-4px 0 4px" }}>
              Sélectionnez plusieurs valeurs par filtre si besoin.
            </p>

            <p style={{ fontSize: 11.5, color: MUTED, margin: "0 0 18px" }}>
              Sélection : {resume()}
            </p>

            {exportErreur && <p style={{ fontSize: 12, color: "#C8102E", fontWeight: 600, margin: "0 0 8px" }}>{exportErreur}</p>}
            <button onClick={genererExport} disabled={exportLoading}
              style={{ ...actionBtnStyle(exportLoading), padding: "11px 20px", width: "100%" }}
              onMouseEnter={e => !exportLoading && (e.currentTarget.style.background = ACCENT_BG)}
              onMouseLeave={e => (e.currentTarget.style.background = "#fff")}>
              {exportLoading && <Spinner />}
              {exportLoading ? "Génération en cours…" : "Générer l'export Excel"}
            </button>
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
        <FiabiliteBar />
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
          <DocumentsPanel onExporter={ouvrirExport} />
          <ExportDrawer open={exportOpen} prefill={prefill} onClose={() => setExportOpen(false)} />
        </div>
      </div>
    </div>
  );
}
