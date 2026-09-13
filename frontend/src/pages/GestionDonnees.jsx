import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { getLogoSrc } from "../utils/logos";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const DARK    = "#2E2E38";
const BG      = "#F2F5FB";
const BORDER  = "#DDE2EC";
const MUTED   = "#6B7280";
const ACCENT  = "#0F6E56";
const ACCENT_BG = "#E1F5EE";

const PAGE_SIZE = 10;

// Sources dont les documents correspondent réellement à des PDF individuels
// scrapés (voir api/services/data_management.py::local_pdf_path) — les
// seules dont la page de gestion a du sens à afficher document par
// document. CGA/FTUSA n'ont pas de société associée (sources sectorielles),
// seul CMF a une entreprise par document — les filtres Entreprise/Tableau
// ne s'affichent donc que sur cet onglet (gestion d'espace : pas de filtre
// grisé/inopérant affiché pour rien).
const SOURCES = [
  { key: "CMF",   label: "CMF",   logo: "/logos/LogoCMF.png" },
  { key: "CGA",   label: "CGA",   logo: "/logos/LogoCGA.png" },
  { key: "FTUSA", label: "FTUSA", logo: "/logos/LogoFTUSA.png" },
];

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

// Style de bouton commun aux actions principales (Collecte…) — retour
// utilisateur : le bloc plein DARK/YELLOW était jugé trop sombre / pas
// assez minimaliste. Contour clair + accent teal au lieu d'un pavé sombre.
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

/* ═══════════════════════════ Onglets de source (logos CMF / CGA / FTUSA) ═══════════════════════════ */
function SourceTabs({ counts, active, onChange }) {
  return (
    <div style={{ display: "flex", gap: 10 }}>
      {SOURCES.map(s => {
        const isActive = s.key === active;
        return (
          <button
            key={s.key}
            onClick={() => onChange(s.key)}
            style={{
              display: "flex", alignItems: "center", gap: 10, padding: "10px 18px",
              borderRadius: 12, cursor: "pointer", flex: 1, minWidth: 0,
              border: `1.5px solid ${isActive ? ACCENT : BORDER}`,
              background: isActive ? ACCENT_BG : "#fff",
              boxShadow: isActive ? "0 2px 8px rgba(15,110,86,0.12)" : "none",
              transition: "background .12s, border-color .12s",
            }}
          >
            <span style={{
              width: 34, height: 34, borderRadius: 8, background: "#fff",
              border: `1px solid ${BORDER}`, display: "flex", alignItems: "center",
              justifyContent: "center", flexShrink: 0, overflow: "hidden",
            }}>
              <img src={s.logo} alt={s.label} style={{ maxWidth: 26, maxHeight: 26, objectFit: "contain" }} />
            </span>
            <span style={{ textAlign: "left", minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 800, color: isActive ? ACCENT : DARK }}>{s.label}</div>
              <div style={{ fontSize: 10.5, color: MUTED }}>{counts?.[s.key] ?? 0} document(s)</div>
            </span>
          </button>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════ Filtre Entreprise (logos priorisés) ═══════════════════════════ */
function EntrepriseSelect({ societes, selected, onSelect }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function onDocClick(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const selectedLogo = selected ? getLogoSrc(selected.code) : null;

  return (
    <div ref={ref} style={{ position: "relative", flex: "1 1 220px", minWidth: 200 }}>
      <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 5 }}>
        Entreprise
      </label>
      <button type="button" onClick={() => setOpen(o => !o)} style={{
        width: "100%", display: "flex", alignItems: "center", gap: 8, textAlign: "left",
        background: "#fff", border: `1px solid ${open ? ACCENT : BORDER}`, borderRadius: 8,
        padding: "6px 10px", cursor: "pointer", font: "inherit",
      }}>
        <span style={{
          width: 24, height: 24, borderRadius: 6, background: "#F8F9FC", flexShrink: 0,
          display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
          border: `1px solid ${BORDER}`,
        }}>
          {selectedLogo
            ? <img src={selectedLogo} alt="" style={{ maxWidth: 20, maxHeight: 20, objectFit: "contain" }} />
            : <span style={{ fontSize: 9, fontWeight: 800, color: MUTED }}>TN</span>}
        </span>
        <span style={{ fontSize: 12.5, color: selected ? DARK : "#9CA3AF", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
          {selected ? (selected.nom || selected.code) : "Toutes les entreprises"}
        </span>
        <span style={{ fontSize: 9, color: MUTED, transform: open ? "rotate(180deg)" : "none" }}>▾</span>
      </button>

      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, right: 0, marginTop: 4, zIndex: 30,
          background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 10,
          boxShadow: "0 8px 22px rgba(0,0,0,.1)", maxHeight: 280, overflowY: "auto", padding: 6,
        }}>
          <button onClick={() => { onSelect(null); setOpen(false); }} style={{
            display: "flex", alignItems: "center", width: "100%", gap: 8, padding: "7px 8px",
            border: "none", background: !selected ? "#F8F9FC" : "transparent", borderRadius: 8,
            cursor: "pointer", fontSize: 12.5, fontWeight: 700, color: DARK, textAlign: "left",
          }}>
            Toutes les entreprises
          </button>
          {societes.map(s => {
            const logo = getLogoSrc(s.code);
            const isSel = selected?.code === s.code;
            return (
              <button key={s.code} onClick={() => { onSelect(s); setOpen(false); }} style={{
                display: "flex", alignItems: "center", width: "100%", gap: 10, padding: "7px 8px",
                border: "none", background: isSel ? ACCENT_BG : "transparent", borderRadius: 8,
                cursor: "pointer", textAlign: "left",
              }}
                onMouseEnter={e => { if (!isSel) e.currentTarget.style.background = "#F8F9FC"; }}
                onMouseLeave={e => { if (!isSel) e.currentTarget.style.background = "transparent"; }}>
                <span style={{
                  width: 26, height: 26, borderRadius: 6, background: "#fff", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
                  border: `1px solid ${BORDER}`,
                }}>
                  {logo
                    ? <img src={logo} alt="" style={{ maxWidth: 21, maxHeight: 21, objectFit: "contain" }} />
                    : <span style={{ fontSize: 9, fontWeight: 800, color: MUTED }}>{s.code.slice(0, 2)}</span>}
                </span>
                <span style={{ fontSize: 12.5, fontWeight: isSel ? 700 : 500, color: DARK, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {s.nom || s.code}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ═══════════════════════════ Filtres à puces (Année / Tableau) ═══════════════════════════ */
function ChipToggleGroup({ label, options, selected, onToggle }) {
  return (
    <div style={{ flex: "1 1 260px", minWidth: 220 }}>
      <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 5 }}>
        {label}
      </label>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {options.map(o => {
          const isSel = selected.has(o.value);
          return (
            <button key={o.value} onClick={() => onToggle(o.value)} style={{
              padding: "5px 12px", borderRadius: 20, fontSize: 12, fontWeight: 700, cursor: "pointer",
              border: `1.5px solid ${isSel ? ACCENT : BORDER}`,
              background: isSel ? ACCENT : "#fff", color: isSel ? "#fff" : DARK,
              transition: "background .12s",
            }}>
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════════════════════ Documents (traitement visuel, une seule page) ═══════════════════════════ */
function DocumentsPanel() {
  const [docs, setDocs] = useState(null);
  const [opts, setOpts] = useState(null);
  const [source, setSource] = useState("CMF");
  const [entreprise, setEntreprise] = useState(null);
  const [annees, setAnnees] = useState(new Set());
  const [tableaux, setTableaux] = useState(new Set());
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/documents`).then(r => r.json()).then(setDocs).catch(() => setDocs([]));
    fetch(`${API}/api/gestion-donnees/filtres`).then(r => r.json()).then(setOpts).catch(() => {});
  }, []);

  const counts = useMemo(() => {
    const c = { CMF: 0, CGA: 0, FTUSA: 0 };
    (docs ?? []).forEach(d => { if (c[d.source] != null) c[d.source] += 1; });
    return c;
  }, [docs]);

  const sourceDocs = useMemo(() => (docs ?? []).filter(d => d.source === source), [docs, source]);
  const anneesDisponibles = useMemo(
    () => [...new Set(sourceDocs.map(d => d.annee))].sort((a, b) => b - a),
    [sourceDocs],
  );
  const tableauOptions = opts?.tableaux ?? [];

  // Les filtres Entreprise/Tableau n'existent que pour CMF : CGA/FTUSA sont
  // des sources sectorielles, sans société associée par document (voir
  // database/repository.py::list_all_documents) — les cacher plutôt que de
  // les afficher désactivés économise de l'espace pour rien d'utilisable.
  const showEntrepriseFiltre = source === "CMF";
  const showTableauFiltre = source === "CMF";

  useEffect(() => { setEntreprise(null); setTableaux(new Set()); setAnnees(new Set()); setSearch(""); setPage(1); }, [source]);

  const toggleAnnee = (a) => setAnnees(prev => {
    const next = new Set(prev);
    next.has(a) ? next.delete(a) : next.add(a);
    return next;
  });
  const toggleTableau = (t) => setTableaux(prev => {
    const next = new Set(prev);
    next.has(t) ? next.delete(t) : next.add(t);
    return next;
  });

  const filtered = useMemo(() => sourceDocs
    .filter(d => !entreprise || d.code === entreprise.code)
    .filter(d => annees.size === 0 || annees.has(d.annee))
    .filter(d => tableaux.size === 0 || (d.code && [...tableaux].some(t => (opts?.societes_par_tableau?.[t] ?? []).includes(d.code))))
    .filter(d => !search || `${d.code ?? ""} ${d.nom_entreprise ?? ""} ${d.nom_pdf}`.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => b.annee - a.annee),
  [sourceDocs, entreprise, annees, tableaux, opts, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const pageRows = filtered.slice((pageSafe - 1) * PAGE_SIZE, pageSafe * PAGE_SIZE);

  const filtresActifs = (entreprise ? 1 : 0) + annees.size + tableaux.size;
  const reinitialiser = () => { setEntreprise(null); setAnnees(new Set()); setTableaux(new Set()); setSearch(""); setPage(1); };

  return (
    <Card>
      <div style={{ marginBottom: 18 }}>
        <h2 style={{ margin: "0 0 3px", fontSize: 15, fontWeight: 800, color: DARK }}>Documents collectés</h2>
        <p style={{ margin: 0, fontSize: 11.5, color: MUTED }}>
          Sélectionnez une source puis affinez par entreprise, année ou tableau.
        </p>
      </div>

      <SourceTabs counts={counts} active={source} onChange={setSource} />

      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "flex-end", margin: "18px 0 6px" }}>
        {showEntrepriseFiltre && (
          <EntrepriseSelect
            societes={opts?.societes ?? []}
            selected={entreprise}
            onSelect={s => { setEntreprise(s); setPage(1); }}
          />
        )}
        <div onClick={() => setPage(1)}>
          <ChipToggleGroup
            label="Année"
            options={anneesDisponibles.map(a => ({ value: a, label: String(a) }))}
            selected={annees} onToggle={a => { toggleAnnee(a); setPage(1); }}
          />
        </div>
        {showTableauFiltre && (
          <div onClick={() => setPage(1)}>
            <ChipToggleGroup
              label="Tableau"
              options={tableauOptions.map(t => ({ value: t.key, label: t.label.split(" — ")[0] }))}
              selected={tableaux} onToggle={t => { toggleTableau(t); setPage(1); }}
            />
          </div>
        )}
        <div style={{ flex: "1 1 200px", minWidth: 180 }}>
          <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 5 }}>
            Recherche
          </label>
          <input
            placeholder="Fichier, code…"
            value={search}
            onChange={e => { setSearch(e.target.value); setPage(1); }}
            style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${BORDER}`, fontSize: 12, width: "100%" }}
          />
        </div>
        {filtresActifs > 0 && (
          <button onClick={reinitialiser} style={{
            border: "none", background: "none", color: ACCENT, fontWeight: 700, fontSize: 12,
            cursor: "pointer", padding: "8px 4px",
          }}>
            Réinitialiser ({filtresActifs})
          </button>
        )}
      </div>

      <div style={{ border: `1px solid ${BORDER}`, borderRadius: 10, overflow: "hidden", marginTop: 12 }}>
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
              <tr><td colSpan={4} style={{ padding: 28, textAlign: "center", color: MUTED }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><Spinner color={MUTED} /> Chargement…</span>
              </td></tr>
            ) : pageRows.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: 28, textAlign: "center", color: MUTED }}>Aucun document pour cette sélection.</td></tr>
            ) : pageRows.map(d => {
              const logo = d.code ? getLogoSrc(d.code) : null;
              const href = d.fichier_local ? `${API}/api/gestion-donnees/documents/${d.id}/pdf` : d.lien;
              return (
                <tr key={d.id} style={{ borderBottom: "1px solid #F0F1F5" }}>
                  <td style={{ padding: "8px 12px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                      <span style={{
                        width: 26, height: 26, borderRadius: 6, background: "#F8F9FC", flexShrink: 0,
                        display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
                        border: `1px solid ${BORDER}`,
                      }}>
                        {logo
                          ? <img src={logo} alt="" style={{ maxWidth: 21, maxHeight: 21, objectFit: "contain" }} />
                          : <span style={{ fontSize: 9, fontWeight: 800, color: MUTED }}>{(d.code ?? d.source).slice(0, 2)}</span>}
                      </span>
                      <span>{d.nom_entreprise ?? d.code ?? "—"}</span>
                    </div>
                  </td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 11.5, color: "#4B5563" }}>{d.nom_pdf}</td>
                  <td style={{ padding: "8px 12px" }}>{d.annee}</td>
                  <td style={{ padding: "8px 12px", textAlign: "right" }}>
                    {href && (
                      <a
                        href={href} target="_blank" rel="noreferrer"
                        style={{
                          color: ACCENT, background: ACCENT_BG, fontWeight: 700, fontSize: 11.5,
                          padding: "5px 10px", borderRadius: 6, textDecoration: "none", whiteSpace: "nowrap",
                        }}>
                        Voir le PDF ↗
                      </a>
                    )}
                  </td>
                </tr>
              );
            })}
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

/* ═══════════════════════════ Page ═══════════════════════════ */
export default function GestionDonnees() {
  return (
    <div style={{ minHeight: "100vh", background: BG, fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ background: DARK, padding: "20px 32px" }}>
        <div style={{ maxWidth: 1220, margin: "0 auto" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,230,0,.7)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 4 }}>
            Data Management · EY
          </div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "white" }}>Gestion de base de données</h1>
          <p style={{ margin: "4px 0 0", fontSize: 11.5, color: "rgba(255,255,255,.45)" }}>
            Accès à toute la donnée collectée par source — CMF, CGA, FTUSA — filtrée par entreprise, année ou tableau.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 1220, margin: "0 auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: 16 }}>
        <CollecteBar />
        <FiabiliteBar />
        <DocumentsPanel />
      </div>
    </div>
  );
}
