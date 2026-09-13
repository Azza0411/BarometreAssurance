import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getLogoSrc } from "../utils/logos";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const DARK    = "#2E2E38";
const BG      = "#F2F5FB";
const BORDER  = "#DDE2EC";
const MUTED   = "#6B7280";
const ACCENT  = "#0F6E56";
const ACCENT_BG = "#E1F5EE";

const GROUP_PAGE_SIZE = 8;

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
// Chiffre + fine barre de progression plutôt qu'un bloc label/nombre/détail
// chargé — retour utilisateur : affichage jugé trop lourd pour une simple
// donnée en un coup d'œil. La barre porte visuellement la même information
// que le "detail" textuel (part du total), en plus discret.
function StatChip({ label, pct, detail }) {
  const color = pct == null ? MUTED : pct >= 90 ? "#16A34A" : pct >= 70 ? "#B45309" : "#C8102E";
  return (
    <div style={{ flex: 1, minWidth: 190 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 10.5, fontWeight: 600, color: MUTED }}>{label}</span>
        <span style={{ fontSize: 17, fontWeight: 800, color, fontVariantNumeric: "tabular-nums" }}>{pct == null ? "—" : `${pct}%`}</span>
      </div>
      <div style={{ height: 4, borderRadius: 4, background: "#EEF1F7", overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${pct ?? 0}%`, background: color, borderRadius: 4, transition: "width .3s" }} />
      </div>
      <div style={{ fontSize: 10.5, color: "#9CA3AF", marginTop: 4 }}>{detail}</div>
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
      <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
        <StatChip label="PDF collectés" pct={collecte.pct} detail={`${collecte.collectes} / ${collecte.total} attendus`} />
        <StatChip label={`Fiabilité extraction (${fe.tableau})`} pct={fe.pct} detail={`${fe.reussis} / ${fe.total} réussis`} />
      </div>
    </Card>
  );
}

/* ═══════════════════════════ Source : dans le bandeau d'en-tête ═══════════════════════════
   Retour utilisateur : ni une section à part sur la page, ni une carte
   isolée — la source doit vivre dans le bandeau EY sombre, à côté du titre,
   comme un vrai réglage global de la page plutôt qu'un bloc de contenu.
   Tuiles claires sur fond sombre : le contraste porte lui-même l'idée que
   c'est un contrôle de premier niveau, pas un widget parmi d'autres. */
function HeaderSourceSwitch({ counts, active, onChange }) {
  return (
    <div style={{ display: "flex", gap: 10 }}>
      {SOURCES.map(s => {
        const isActive = s.key === active;
        return (
          <button key={s.key} onClick={() => onChange(s.key)} title={s.label} style={{
            position: "relative", width: 54, height: 54, padding: 6, border: "none", borderRadius: 12,
            cursor: "pointer", background: "#fff", opacity: isActive ? 1 : .55,
            boxShadow: isActive ? "0 4px 14px rgba(0,0,0,.28)" : "0 1px 4px rgba(0,0,0,.15)",
            display: "flex", alignItems: "center", justifyContent: "center",
            transition: "opacity .15s, box-shadow .15s",
          }}
            onMouseEnter={e => { if (!isActive) e.currentTarget.style.opacity = .85; }}
            onMouseLeave={e => { if (!isActive) e.currentTarget.style.opacity = .55; }}
          >
            <img src={s.logo} alt={s.label} style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }} />
            <span style={{
              position: "absolute", top: -6, right: -6, minWidth: 18, height: 18, padding: "0 4px",
              borderRadius: 20, background: isActive ? ACCENT : "#fff", color: isActive ? "#fff" : DARK,
              fontSize: 9.5, fontWeight: 800, display: "flex", alignItems: "center", justifyContent: "center",
              border: `2px solid ${DARK}`, fontVariantNumeric: "tabular-nums",
            }}>{counts?.[s.key] ?? 0}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════ Année — toujours visible, jamais à défiler ═══════════════════════════
   Retour d'affichage : voir toutes les années d'un coup, sans faire défiler
   une rangée horizontale — passe donc en grille qui retombe à la ligne. */
function YearGrid({ options, selected, onToggle }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {options.map(a => {
        const isSel = selected.has(a);
        return (
          <button key={a} onClick={() => onToggle(a)} style={{
            padding: "6px 13px", borderRadius: 20, fontSize: 12, fontWeight: 700,
            cursor: "pointer", border: `1.5px solid ${isSel ? ACCENT : BORDER}`,
            background: isSel ? ACCENT_BG : "#fff", color: isSel ? ACCENT : DARK,
            fontVariantNumeric: "tabular-nums", transition: "background .12s, border-color .12s",
          }}>
            {a}
          </button>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════ Filtre Entreprise — combo multi-sélection ═══════════════════════════
   Recherche + sélection multiple (cumuler plusieurs sociétés dans un même
   export), les sociétés choisies apparaissent en puces avec leur logo à
   l'intérieur du champ — une seule ligne compacte plutôt qu'une liste
   verticale qui pousserait le reste de la page vers le bas. */
function EntrepriseCombo({ societes, selected, onToggle, onRemove, disabledSet }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const ref = useRef(null);

  useEffect(() => {
    function onDocClick(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const filteredOptions = useMemo(() => {
    const q = query.toLowerCase();
    if (!q) return societes;
    return societes.filter(s => (s.nom ?? "").toLowerCase().includes(q) || s.code.toLowerCase().includes(q));
  }, [societes, query]);

  return (
    <div ref={ref} style={{ position: "relative", flex: "1 1 340px", minWidth: 260 }}>
      <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 5 }}>
        Entreprise
      </label>
      <div
        onClick={() => setOpen(true)}
        style={{
          display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", padding: "5px 8px",
          border: `1px solid ${open ? ACCENT : BORDER}`, borderRadius: 8, background: "#fff", cursor: "text",
        }}
      >
        {[...selected].map(code => {
          const s = societes.find(x => x.code === code);
          const logo = getLogoSrc(code);
          return (
            <span key={code} style={{
              display: "flex", alignItems: "center", gap: 7, background: ACCENT_BG, color: ACCENT,
              fontSize: 12, fontWeight: 700, padding: "3px 6px 3px 3px", borderRadius: 20,
            }}>
              <span style={{
                width: 26, height: 26, borderRadius: 7, background: "#fff", flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
                boxShadow: "0 1px 3px rgba(0,0,0,0.12)",
              }}>
                {logo ? <img src={logo} alt="" style={{ maxWidth: 22, maxHeight: 22, objectFit: "contain" }} /> : null}
              </span>
              {s?.nom ?? code}
              <button onClick={e => { e.stopPropagation(); onRemove(code); }} style={{
                border: "none", background: "rgba(0,0,0,.08)", color: "inherit", width: 15, height: 15,
                borderRadius: "50%", fontSize: 9, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              }}>×</button>
            </span>
          );
        })}
        <input
          value={query}
          onChange={e => { setQuery(e.target.value); setOpen(true); }}
          onFocus={() => setOpen(true)}
          placeholder={selected.size ? "Ajouter…" : "Toutes les entreprises"}
          style={{ flex: 1, minWidth: 100, border: "none", outline: "none", fontSize: 12.5, padding: "3px 4px", font: "inherit" }}
        />
      </div>

      {open && (
        <div style={{
          position: "absolute", top: "100%", left: 0, right: 0, marginTop: 4, zIndex: 30,
          background: "#fff", border: `1px solid ${BORDER}`, borderRadius: 10,
          boxShadow: "0 8px 22px rgba(0,0,0,.1)", maxHeight: 240, overflowY: "auto", padding: 6,
        }}>
          {filteredOptions.length === 0 ? (
            <div style={{ padding: "8px 8px", fontSize: 12, color: MUTED }}>Aucune correspondance.</div>
          ) : filteredOptions.map(s => {
            const logo = getLogoSrc(s.code);
            const isSel = selected.has(s.code);
            const isDisabled = disabledSet?.has(s.code);
            return (
              <button
                key={s.code} disabled={isDisabled}
                title={isDisabled ? "Aucune donnée pour le(s) tableau(x) sélectionné(s)" : undefined}
                onClick={() => { if (isDisabled) return; onToggle(s.code); setQuery(""); }}
                style={{
                  display: "flex", alignItems: "center", width: "100%", gap: 12, padding: "8px",
                  border: "none", background: isSel ? ACCENT_BG : "transparent", borderRadius: 10,
                  cursor: isDisabled ? "not-allowed" : "pointer", textAlign: "left", opacity: isDisabled ? .45 : 1,
                }}
                onMouseEnter={e => { if (!isSel && !isDisabled) e.currentTarget.style.background = "#F8F9FC"; }}
                onMouseLeave={e => { if (!isSel && !isDisabled) e.currentTarget.style.background = "transparent"; }}>
                <span style={{
                  width: 34, height: 34, borderRadius: 9, background: "#fff", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
                  border: `1px solid ${BORDER}`, boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                }}>
                  {logo
                    ? <img src={logo} alt="" style={{ maxWidth: 28, maxHeight: 28, objectFit: "contain", filter: isDisabled ? "grayscale(1)" : "none" }} />
                    : <span style={{ fontSize: 9, fontWeight: 800, color: MUTED }}>{s.code.slice(0, 2)}</span>}
                </span>
                <span style={{ fontSize: 13, fontWeight: isSel ? 700 : 500, color: isDisabled ? MUTED : DARK, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
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

/* ═══════════════════════════ Filtre Tableau — puces multi-sélection ═══════════════════════════ */
function TableauChips({ options, selected, onToggle }) {
  return (
    <div style={{ flex: "0 0 auto" }}>
      <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 5 }}>
        Tableau
      </label>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {options.map(o => {
          const isSel = selected.has(o.value);
          return (
            <button key={o.value} onClick={() => onToggle(o.value)} style={{
              padding: "6px 13px", borderRadius: 20, fontSize: 12, fontWeight: 700, cursor: "pointer",
              border: `1.5px solid ${isSel ? ACCENT : BORDER}`,
              background: isSel ? ACCENT_BG : "#fff", color: isSel ? ACCENT : DARK,
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

/* ═══════════════════════════ Documents & extraction (une seule console) ═══════════════════════════
   `source` vient du filtre de page (SourceFilterBar, au-dessus de Collecte/
   Fiabilité) — cette console n'en garde plus l'état, elle le reçoit. */
function DocumentsConsole({ docs, opts, source }) {
  const navigate = useNavigate();
  const [entreprises, setEntreprises] = useState(new Set());
  const [annees, setAnnees] = useState(new Set());
  const [tableaux, setTableaux] = useState(new Set());
  const [page, setPage] = useState(1);
  const [exportLoading, setExportLoading] = useState(false);
  const [exportErreur, setExportErreur] = useState(null);

  const sourceDocs = useMemo(() => (docs ?? []).filter(d => d.source === source), [docs, source]);
  const anneesDisponibles = useMemo(
    () => [...new Set(sourceDocs.map(d => d.annee))].sort((a, b) => b - a),
    [sourceDocs],
  );
  const tableauOptions = useMemo(() => opts?.tableaux ?? [], [opts]);

  // Sociétés à désactiver dans le sélecteur Entreprise : celles qui n'ont
  // structurellement AUCUNE donnée pour AUCUN des tableaux actuellement
  // sélectionnés (ex. ATTIJARI/UIB pour Annexe 13 — sociétés Vie only). Sans
  // tableau sélectionné, personne n'est désactivé (pas de filtre). Plusieurs
  // tableaux sélectionnés = éligible si la société a AU MOINS UN d'entre eux
  // (union, pas intersection) — même règle que l'ancien export flexible.
  const entreprisesDisabled = useMemo(() => {
    if (!opts?.societes_par_tableau || tableaux.size === 0) return new Set();
    const eligible = new Set();
    tableaux.forEach(t => (opts.societes_par_tableau[t] || []).forEach(c => eligible.add(c)));
    if (eligible.size === 0) return new Set();
    return new Set((opts.societes ?? []).map(s => s.code).filter(c => !eligible.has(c)));
  }, [opts, tableaux]);

  // Une société déjà sélectionnée qui devient inéligible (l'utilisateur
  // change le tableau après coup) est retirée automatiquement de la
  // sélection plutôt que laissée cochée mais grisée.
  useEffect(() => {
    if (entreprisesDisabled.size === 0) return;
    setEntreprises(prev => {
      const next = new Set([...prev].filter(c => !entreprisesDisabled.has(c)));
      return next.size === prev.size ? prev : next;
    });
  }, [entreprisesDisabled]);

  // Tableau de départ raisonnable pour la correction manuelle d'une société
  // donnée — le premier groupe (dans l'ordre Annexe12/Annexe13/Bilan) pour
  // lequel elle a effectivement des cellules stockées ; l'utilisateur peut
  // ensuite changer de tableau directement sur la page de correction.
  const defaultTableauFor = (code) => {
    const match = tableauOptions.find(t => (opts?.societes_par_tableau?.[t.key] ?? []).includes(code));
    return match?.key ?? "annexe12";
  };

  // Les filtres Entreprise/Tableau — et l'export Excel, qui s'appuie sur les
  // mêmes groupes de tableaux CMF (voir api/services/data_management.py::
  // TABLEAU_GROUPS, tous filtrés `WHERE s.nom = 'CMF'`) — n'existent que pour
  // CMF : CGA/FTUSA sont des sources sectorielles, sans société associée par
  // document (voir database/repository.py::list_all_documents).
  const isCmf = source === "CMF";

  useEffect(() => { setEntreprises(new Set()); setTableaux(new Set()); setAnnees(new Set()); setPage(1); }, [source]);

  const toggleIn = (setter) => (value) => setter(prev => {
    const next = new Set(prev);
    next.has(value) ? next.delete(value) : next.add(value);
    return next;
  });
  const toggleAnnee = toggleIn(setAnnees);
  const toggleTableau = toggleIn(setTableaux);
  const toggleEntreprise = toggleIn(setEntreprises);
  const removeEntreprise = (code) => setEntreprises(prev => { const n = new Set(prev); n.delete(code); return n; });

  const filtered = useMemo(() => sourceDocs
    .filter(d => entreprises.size === 0 || (d.code && entreprises.has(d.code)))
    .filter(d => annees.size === 0 || annees.has(d.annee))
    .filter(d => tableaux.size === 0 || (d.code && [...tableaux].some(t => (opts?.societes_par_tableau?.[t] ?? []).includes(d.code))))
    .sort((a, b) => b.annee - a.annee),
  [sourceDocs, entreprises, annees, tableaux, opts]);

  // Regroupé par société — retour utilisateur : une ligne par document
  // noyait les 10 dernières années d'une même compagnie dans une longue
  // liste plate. Un bloc par société avec toutes ses années côte à côte se
  // parcourt d'un coup d'œil. Les documents sans société (CGA/FTUSA
  // sectorielles) restent chacun leur propre bloc.
  const grouped = useMemo(() => {
    const map = new Map();
    filtered.forEach(d => {
      const key = d.code ?? `__doc_${d.id}`;
      if (!map.has(key)) map.set(key, { code: d.code, nom: d.nom_entreprise, items: [] });
      map.get(key).items.push(d);
    });
    const groups = [...map.values()];
    groups.forEach(g => g.items.sort((a, b) => b.annee - a.annee));
    groups.sort((a, b) => (a.nom ?? a.code ?? "").localeCompare(b.nom ?? b.code ?? "", "fr"));
    return groups;
  }, [filtered]);

  const totalPages = Math.max(1, Math.ceil(grouped.length / GROUP_PAGE_SIZE));
  const pageSafe = Math.min(page, totalPages);
  const pageGroups = grouped.slice((pageSafe - 1) * GROUP_PAGE_SIZE, pageSafe * GROUP_PAGE_SIZE);

  const tags = useMemo(() => {
    const t = [];
    entreprises.forEach(code => t.push({ key: `e-${code}`, label: opts?.societes?.find(s => s.code === code)?.nom ?? code, clear: () => removeEntreprise(code) }));
    tableaux.forEach(k => t.push({ key: `t-${k}`, label: tableauOptions.find(o => o.key === k)?.label.split(" — ")[0] ?? k, clear: () => toggleTableau(k) }));
    annees.forEach(a => t.push({ key: `a-${a}`, label: String(a), clear: () => toggleAnnee(a) }));
    return t;
  }, [entreprises, tableaux, annees, opts, tableauOptions]);

  // Génère l'export via fetch (au lieu d'un <a href> nu) pour pouvoir
  // afficher un indicateur de chargement — une génération large peut
  // prendre jusqu'à ~1-2 minutes (plafond d'extraction live côté serveur).
  // Le téléchargement lui-même est déclenché en JS une fois le fichier reçu
  // (lien blob synthétique, jamais visible de l'utilisateur).
  const genererExport = () => {
    if (!isCmf) return;
    setExportErreur(null);
    setExportLoading(true);
    const p = new URLSearchParams();
    tableaux.forEach(t => p.append("tableau", t));
    entreprises.forEach(s => p.append("societe", s));
    annees.forEach(a => p.append("annee", a));
    fetch(`${API}/api/gestion-donnees/export.xlsx?${p.toString()}`)
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
    <Card style={{ padding: 0 }}>
      {/* Année : même section qu'Entreprise/Tableau, mais jamais masquée par
          source — CGA/FTUSA ont aussi des années, même sans société. */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "flex-start", padding: "18px 24px" }}>
        <div style={{ flex: "1 1 100%" }}>
          <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 7 }}>
            Année
          </label>
          <YearGrid options={anneesDisponibles} selected={annees} onToggle={a => { toggleAnnee(a); setPage(1); }} />
        </div>

        {isCmf ? (
          <>
            <EntrepriseCombo
              societes={opts?.societes ?? []}
              selected={entreprises}
              onToggle={code => { toggleEntreprise(code); setPage(1); }}
              onRemove={code => { removeEntreprise(code); setPage(1); }}
              disabledSet={entreprisesDisabled}
            />
            <TableauChips
              options={tableauOptions.map(t => ({ value: t.key, label: t.label.split(" — ")[0] }))}
              selected={tableaux} onToggle={t => { toggleTableau(t); setPage(1); }}
            />
          </>
        ) : (
          <p style={{ margin: 0, fontSize: 11.5, color: MUTED }}>
            Source sectorielle : sans société ni tableau associé — seule l'année filtre les documents.
          </p>
        )}
      </div>

      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 14, flexWrap: "wrap",
        background: "#F8F9FC", padding: "11px 24px", borderTop: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}`,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", minWidth: 0 }}>
          {tags.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {tags.map(t => (
                <span key={t.key} style={{
                  display: "flex", alignItems: "center", gap: 6, background: ACCENT_BG, color: ACCENT,
                  fontSize: 11.5, fontWeight: 700, padding: "4px 6px 4px 10px", borderRadius: 20, whiteSpace: "nowrap",
                }}>
                  {t.label}
                  <button onClick={t.clear} style={{
                    border: "none", background: "rgba(0,0,0,.08)", color: "inherit", width: 15, height: 15,
                    borderRadius: "50%", fontSize: 10, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                  }}>×</button>
                </span>
              ))}
            </div>
          )}
          <span style={{ fontSize: 12, color: MUTED, whiteSpace: "nowrap" }}>
            <b style={{ color: DARK, fontWeight: 800 }}>{filtered.length}</b> document(s) correspondent
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexShrink: 0 }}>
          {exportErreur && <span style={{ fontSize: 11.5, color: "#C8102E", fontWeight: 600 }}>{exportErreur}</span>}
          <span style={{ fontSize: 11, color: MUTED }}>
            {isCmf ? "Une feuille par société, un tableau par annexe sélectionnée" : "Consultation PDF uniquement pour cette source"}
          </span>
          <button onClick={genererExport} disabled={!isCmf || exportLoading} style={actionBtnStyle(!isCmf || exportLoading)}
            onMouseEnter={e => isCmf && !exportLoading && (e.currentTarget.style.background = ACCENT_BG)}
            onMouseLeave={e => (e.currentTarget.style.background = "#fff")}>
            {exportLoading && <Spinner />}
            {exportLoading ? "Génération…" : "Générer l'Excel"}
          </button>
        </div>
      </div>

      <div>
        {!docs ? (
          <div style={{ padding: 28, textAlign: "center", color: MUTED }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}><Spinner color={MUTED} /> Chargement…</span>
          </div>
        ) : pageGroups.length === 0 ? (
          <div style={{ padding: 28, textAlign: "center", color: MUTED }}>Aucun document pour cette sélection.</div>
        ) : pageGroups.map(g => {
          const logo = g.code ? getLogoSrc(g.code) : null;
          const titre = g.nom ?? g.code ?? (g.items[0]?.source ?? "Document");
          return (
            <div key={g.code ?? g.items[0].id} style={{
              display: "flex", alignItems: "flex-start", gap: 16, padding: "14px 24px",
              borderBottom: `1px solid #F0F1F5`,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 11, flex: "0 0 260px", minWidth: 0 }}>
                <span style={{
                  width: 40, height: 40, borderRadius: 10, background: "#fff", flexShrink: 0,
                  display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden",
                  border: `1px solid ${BORDER}`, boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
                }}>
                  {logo
                    ? <img src={logo} alt="" style={{ maxWidth: 33, maxHeight: 33, objectFit: "contain" }} />
                    : <span style={{ fontSize: 10, fontWeight: 800, color: MUTED }}>{(g.code ?? g.items[0].source).slice(0, 2)}</span>}
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: DARK, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{titre}</div>
                  <div style={{ fontSize: 10.5, color: MUTED }}>{g.items.length} document(s)</div>
                </div>
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, flex: 1, paddingTop: 2 }}>
                {g.items.map(d => {
                  const href = d.fichier_local ? `${API}/api/gestion-donnees/documents/${d.id}/pdf` : d.lien;
                  return (
                    <span key={d.id} style={{ display: "inline-flex", alignItems: "center", gap: 2 }}>
                      {href ? (
                        <a href={href} target="_blank" rel="noreferrer" title={d.nom_pdf} style={{
                          display: "flex", alignItems: "center", gap: 5, color: ACCENT, background: ACCENT_BG,
                          fontWeight: 700, fontSize: 11.5, padding: "5px 10px", borderRadius: d.code ? "7px 0 0 7px" : 7,
                          textDecoration: "none", whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums",
                        }}>
                          {d.annee} ↗
                        </a>
                      ) : (
                        <span style={{
                          fontSize: 11.5, fontWeight: 700, color: MUTED, background: "#F3F4F6",
                          padding: "5px 10px", borderRadius: d.code ? "7px 0 0 7px" : 7, fontVariantNumeric: "tabular-nums",
                        }}>
                          {d.annee}
                        </span>
                      )}
                      {d.code && (
                        <button
                          title="Corriger manuellement ce document"
                          onClick={() => navigate(`/correction-manuelle?code=${d.code}&annee=${d.annee}&tableau=${defaultTableauFor(d.code)}`)}
                          style={{
                            display: "flex", alignItems: "center", border: "none", cursor: "pointer",
                            color: MUTED, background: "#F3F4F6", padding: "5px 9px", borderRadius: "0 7px 7px 0",
                            borderLeft: `1px solid ${href ? ACCENT_BG : "#E5E7EB"}`,
                          }}
                        >
                          <svg viewBox="0 0 14 14" fill="none" width="12" height="12">
                            <path d="M9.5 1.5l3 3-7.5 7.5-3.5.5.5-3.5 7.5-7.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
                          </svg>
                        </button>
                      )}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 24px 18px", fontSize: 12, color: MUTED }}>
        <span>{grouped.length} société(s)/document(s) · page {pageSafe}/{totalPages}</span>
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
  const [docs, setDocs] = useState(null);
  const [opts, setOpts] = useState(null);
  const [source, setSource] = useState("CMF");

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/documents`).then(r => r.json()).then(setDocs).catch(() => setDocs([]));
    fetch(`${API}/api/gestion-donnees/filtres`).then(r => r.json()).then(setOpts).catch(() => {});
  }, []);

  const counts = useMemo(() => {
    const c = { CMF: 0, CGA: 0, FTUSA: 0 };
    (docs ?? []).forEach(d => { if (c[d.source] != null) c[d.source] += 1; });
    return c;
  }, [docs]);

  return (
    <div style={{ minHeight: "100vh", background: BG, fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ background: DARK, padding: "20px 32px" }}>
        <div style={{ maxWidth: 1220, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24, flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,230,0,.7)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 4 }}>
              Data Management · EY
            </div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "white" }}>Gestion de base de données</h1>
            <p style={{ margin: "4px 0 0", fontSize: 11.5, color: "rgba(255,255,255,.45)" }}>
              La source filtre toute la page ; les filtres plus étroits et l'export Excel juste au-dessus des documents qu'ils affectent.
            </p>
          </div>
          <HeaderSourceSwitch counts={counts} active={source} onChange={setSource} />
        </div>
      </div>

      <div style={{ maxWidth: 1220, margin: "0 auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: 16 }}>
        <CollecteBar />
        <FiabiliteBar />
        <DocumentsConsole docs={docs} opts={opts} source={source} />
      </div>
    </div>
  );
}
