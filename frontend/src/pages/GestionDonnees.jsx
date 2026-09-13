import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getLogoSrc } from "../utils/logos";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const DARK    = "#2E2E38";
const BG      = "#F2F5FB";
const BORDER  = "#DDE2EC";
const MUTED   = "#6B7280";
// Jaune (famille navbar) mais volontairement plus foncé et plus discret que
// le jaune vif d'origine — retour utilisateur : appliqué en pleine
// saturation sur toutes les bordures/tuiles actives à la fois (24 sociétés
// sélectionnées par défaut), le jaune vif devenait criard. Un ton plus
// sourd (moutarde) reste identifiable comme "jaune" sans agresser l'œil
// quand il est répété partout. Texte toujours en DARK, jamais en jaune.
const ACCENT  = "#C9A227";
const ACCENT_BG = "#F6EFD8";

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
// assez minimaliste. Contour clair (même jaune que la navbar) au lieu d'un
// pavé sombre — texte DARK, pas jaune, pour rester lisible sur fond blanc.
function actionBtnStyle(disabled) {
  return {
    padding: "9px 16px", borderRadius: 8, fontSize: 12.5, fontWeight: 700,
    cursor: disabled ? "not-allowed" : "pointer",
    border: `1.5px solid ${disabled ? BORDER : ACCENT}`,
    background: "#fff", color: disabled ? "#9CA3AF" : DARK,
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
              borderRadius: 20, background: isActive ? ACCENT : "#fff", color: DARK,
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
            background: isSel ? ACCENT_BG : "#fff", color: DARK,
            fontVariantNumeric: "tabular-nums", transition: "background .12s, border-color .12s",
          }}>
            {a}
          </button>
        );
      })}
    </div>
  );
}

/* ═══════════════════════════ Filtre Entreprise — grille de logos ═══════════════════════════
   Même logique que le sélecteur d'assureurs d'Analyse comparative : les
   logos EUX-MÊMES sont les boutons (clic = sélection/désélection), pas une
   liste déroulante à ouvrir — reconnaître un logo est plus rapide que lire
   un nom dans une liste. Grille à colonnes égales (comme là-bas) plutôt que
   flex-wrap : les logos ont des largeurs très variables et un flex-wrap
   produirait des lignes en escalier au retour à la ligne. */
function EntrepriseLogoGrid({ societes, selected, onToggle, onOnly, disabledSet, onReset, hasExclusions }) {
  const [hovered, setHovered] = useState(null);
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 7 }}>
        <label style={{ fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px" }}>
          Entreprise
        </label>
        {hasExclusions && (
          <button onClick={onReset} style={{ border: "none", background: "none", color: DARK, fontWeight: 700, fontSize: 11, cursor: "pointer", padding: 0, textDecoration: "underline", textDecorationColor: ACCENT, textUnderlineOffset: 2 }}>
            Tout resélectionner
          </button>
        )}
      </div>
      {/* Retour utilisateur : choisir seulement 2-3 sociétés obligeait à
          désélectionner toutes les autres une par une. Un bouton "Seulement"
          au survol isole cette société en un clic (comme "Solo" sur un calque
          Figma) — clic normal sur le logo pour ajouter/retirer, ce petit
          bouton pour "juste celle-ci". */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(84px, 1fr))", gap: 6 }}>
        {societes.map(s => {
          const active = selected.has(s.code);
          const disabled = disabledSet?.has(s.code);
          const logo = getLogoSrc(s.code);
          const showOnly = hovered === s.code && !disabled;
          return (
            <button
              key={s.code}
              onClick={() => { if (!disabled) onToggle(s.code); }}
              onMouseEnter={() => setHovered(s.code)}
              onMouseLeave={() => setHovered(null)}
              disabled={disabled}
              title={disabled ? "Aucune donnée pour le(s) tableau(x) sélectionné(s)" : (active ? `Retirer ${s.nom ?? s.code}` : `Ajouter ${s.nom ?? s.code}`)}
              style={{
                // Bordure fine, pas d'ombre portée : avec la sélection
                // "tout par défaut", une trentaine de tuiles actives en même
                // temps ne doivent pas toutes s'allumer/briller à la fois —
                // seul le fond blanc + un liseré discret marquent l'état
                // sélectionné, le vrai contraste vient du gris des exclues.
                position: "relative", display: "flex", alignItems: "center", justifyContent: "center", padding: "8px 6px", height: 48,
                background: active ? "#fff" : "transparent",
                border: `1px solid ${active ? "#E9DCAE" : "transparent"}`,
                borderRadius: 9, cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.28 : active ? 1 : 0.4,
                filter: (active || disabled) ? "none" : "grayscale(65%)",
                boxShadow: active ? "0 1px 3px rgba(20,22,28,.06)" : "none",
                transition: "all .15s",
              }}
            >
              {logo
                ? <img src={logo} alt={s.nom ?? s.code} style={{ maxWidth: 44, maxHeight: 32, objectFit: "contain", filter: disabled ? "grayscale(1)" : "none" }} />
                : <span style={{ fontSize: 9, fontWeight: 800, color: MUTED }}>{s.code.slice(0, 2)}</span>}
              {showOnly && (
                <span
                  onClick={e => { e.stopPropagation(); onOnly(s.code); }}
                  title={`Sélectionner seulement ${s.nom ?? s.code}`}
                  style={{
                    position: "absolute", bottom: -3, left: "50%", transform: "translateX(-50%)",
                    background: DARK, color: ACCENT, fontSize: 9, fontWeight: 800, padding: "2px 8px",
                    borderRadius: 20, whiteSpace: "nowrap", boxShadow: "0 2px 6px rgba(0,0,0,.25)",
                  }}
                >
                  Seulement
                </span>
              )}
            </button>
          );
        })}
      </div>
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
              background: isSel ? ACCENT_BG : "#fff", color: DARK,
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
  // Toutes les entreprises sont sélectionnées PAR DÉFAUT (retour utilisateur
  // explicite) — on suit donc les EXCLUSIONS plutôt que les inclusions : un
  // Set vide veut dire "personne d'exclu" = tout le monde sélectionné, sans
  // avoir à peupler explicitement la liste complète (et sans dépendre du
  // chargement asynchrone de `opts` pour connaître cette liste).
  const [entreprisesExclues, setEntreprisesExclues] = useState(new Set());
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

  // Une société sélectionnée qui devient inéligible (l'utilisateur change
  // le tableau après coup) est exclue automatiquement plutôt que laissée
  // visuellement active mais grisée.
  useEffect(() => {
    if (entreprisesDisabled.size === 0) return;
    setEntreprisesExclues(prev => {
      const next = new Set(prev);
      let changed = false;
      entreprisesDisabled.forEach(c => { if (!next.has(c)) { next.add(c); changed = true; } });
      return changed ? next : prev;
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

  // Sociétés effectivement sélectionnées (= tout le monde moins les
  // exclusions) — dérivé, jamais stocké séparément, pour ne pas avoir deux
  // sources de vérité à synchroniser.
  const societesSelectionnees = useMemo(
    () => (opts?.societes ?? []).map(s => s.code).filter(c => !entreprisesExclues.has(c)),
    [opts, entreprisesExclues],
  );

  // Cible de "Corriger les données Excel" dans la barre résumé — n'a de sens
  // que pour UNE société précise (Correction manuelle prend un document, pas
  // une sélection multiple) : actif seulement quand le filtre Entreprise en
  // isole exactement une. Année/tableau retenus = ceux du filtre s'il n'y en
  // a qu'un sélectionné, sinon un choix par défaut raisonnable (le plus
  // récent disponible / le premier tableau où la société a des données).
  const correctionCible = useMemo(() => {
    if (!isCmf || societesSelectionnees.length !== 1) return null;
    const code = societesSelectionnees[0];
    const anneesCode = sourceDocs.filter(d => d.code === code).map(d => d.annee).sort((a, b) => b - a);
    const annee = annees.size === 1 ? [...annees][0] : anneesCode[0];
    if (!annee) return null;
    const tableauCible = tableaux.size === 1 ? [...tableaux][0] : defaultTableauFor(code);
    return { code, annee, tableau: tableauCible };
  }, [isCmf, societesSelectionnees, annees, tableaux, sourceDocs, tableauOptions, opts]);

  useEffect(() => { setEntreprisesExclues(new Set()); setTableaux(new Set()); setAnnees(new Set()); setPage(1); }, [source]);

  const toggleIn = (setter) => (value) => setter(prev => {
    const next = new Set(prev);
    next.has(value) ? next.delete(value) : next.add(value);
    return next;
  });
  const toggleAnnee = toggleIn(setAnnees);
  const toggleTableau = toggleIn(setTableaux);
  const toggleEntreprise = toggleIn(setEntreprisesExclues);

  const filtered = useMemo(() => sourceDocs
    .filter(d => !d.code || !entreprisesExclues.has(d.code))
    .filter(d => annees.size === 0 || annees.has(d.annee))
    .filter(d => tableaux.size === 0 || (d.code && [...tableaux].some(t => (opts?.societes_par_tableau?.[t] ?? []).includes(d.code))))
    .sort((a, b) => b.annee - a.annee),
  [sourceDocs, entreprisesExclues, annees, tableaux, opts]);

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
    // Une puce par société EXCLUE (pas sélectionnée) — cohérent avec "tout
    // le monde est sélectionné par défaut, on retire au clic" : la retirer
    // ici revient à réintégrer cette société dans la sélection.
    entreprisesExclues.forEach(code => t.push({ key: `e-${code}`, label: `Sans ${opts?.societes?.find(s => s.code === code)?.nom ?? code}`, clear: () => toggleEntreprise(code) }));
    tableaux.forEach(k => t.push({ key: `t-${k}`, label: tableauOptions.find(o => o.key === k)?.label.split(" — ")[0] ?? k, clear: () => toggleTableau(k) }));
    annees.forEach(a => t.push({ key: `a-${a}`, label: String(a), clear: () => toggleAnnee(a) }));
    return t;
  }, [entreprisesExclues, tableaux, annees, opts, tableauOptions]);

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
    // Rien n'est ajouté quand personne n'est exclu : le backend traite
    // l'absence de paramètre "societe" comme "toutes", exactement le
    // comportement par défaut voulu.
    if (entreprisesExclues.size > 0) societesSelectionnees.forEach(s => p.append("societe", s));
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
      <div style={{ display: "flex", flexDirection: "column", gap: 16, padding: "18px 24px" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 14, alignItems: "flex-start" }}>
          <div style={{ flex: "1 1 auto" }}>
            <label style={{ display: "block", fontSize: 10, fontWeight: 700, color: "#9CA3AF", textTransform: "uppercase", letterSpacing: ".4px", marginBottom: 7 }}>
              Année
            </label>
            <YearGrid options={anneesDisponibles} selected={annees} onToggle={a => { toggleAnnee(a); setPage(1); }} />
          </div>
          {isCmf && (
            <TableauChips
              options={tableauOptions.map(t => ({ value: t.key, label: t.label.split(" — ")[0] }))}
              selected={tableaux} onToggle={t => { toggleTableau(t); setPage(1); }}
            />
          )}
        </div>

        {isCmf ? (
          <EntrepriseLogoGrid
            societes={opts?.societes ?? []}
            selected={new Set(societesSelectionnees)}
            onToggle={code => { toggleEntreprise(code); setPage(1); }}
            onOnly={code => {
              setEntreprisesExclues(new Set((opts?.societes ?? []).map(s => s.code).filter(c => c !== code)));
              setPage(1);
            }}
            onReset={() => { setEntreprisesExclues(new Set()); setPage(1); }}
            hasExclusions={entreprisesExclues.size > 0}
            disabledSet={entreprisesDisabled}
          />
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
                  display: "flex", alignItems: "center", gap: 6, background: ACCENT_BG, color: DARK,
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
          <button
            onClick={() => correctionCible && navigate(`/correction-manuelle?code=${correctionCible.code}&annee=${correctionCible.annee}&tableau=${correctionCible.tableau}`)}
            disabled={!correctionCible}
            title={correctionCible ? undefined : "Sélectionnez une seule entreprise pour corriger ses données"}
            style={actionBtnStyle(!correctionCible)}
            onMouseEnter={e => correctionCible && (e.currentTarget.style.background = ACCENT_BG)}
            onMouseLeave={e => (e.currentTarget.style.background = "#fff")}>
            <svg viewBox="0 0 14 14" fill="none" width="12" height="12">
              <path d="M9.5 1.5l3 3-7.5 7.5-3.5.5.5-3.5 7.5-7.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
            </svg>
            Corriger les données Excel
          </button>
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
                  return href ? (
                    <a key={d.id} href={href} target="_blank" rel="noreferrer" title={d.nom_pdf} style={{
                      display: "flex", alignItems: "center", gap: 5, color: DARK, background: ACCENT_BG,
                      fontWeight: 700, fontSize: 11.5, padding: "5px 10px", borderRadius: 7,
                      textDecoration: "none", whiteSpace: "nowrap", fontVariantNumeric: "tabular-nums",
                    }}>
                      {d.annee} ↗
                    </a>
                  ) : (
                    <span key={d.id} style={{
                      fontSize: 11.5, fontWeight: 700, color: MUTED, background: "#F3F4F6",
                      padding: "5px 10px", borderRadius: 7, fontVariantNumeric: "tabular-nums",
                    }}>
                      {d.annee}
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
