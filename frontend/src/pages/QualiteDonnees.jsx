import { useState, useEffect, useCallback, Fragment } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { KPI_CATALOG } from "../utils/kpiCatalog";
import { KPI_META } from "../utils/kpiMeta";
import { classifyCell, resolveCellVisual, CELL_VISUAL } from "../utils/kpiStatus";
import { getLogoSrc } from "../utils/logos";
import KpiOptionsMenu from "../components/KpiOptionsMenu";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

// KPI sectoriels (code="MARCHE", pas une société CMF) — voir kpiMeta.js
// "KPI sectoriels". Regroupés pour la vue "Données sectorielles" ci-dessous,
// symétrique de la matrice société × KPI_CATALOG existante.
// Ajouté le 2026-08-19 sur demande explicite de l'utilisateur : cette page
// ne permettait d'accéder qu'aux KPI par société, aucun moyen de voir/
// auditer les KPI sectoriels (Population, PIB, ratios marché...) ici.
//
// Titres de groupe = vrai nom de la PAGE DE L'APPLICATION où le KPI est
// affiché à l'utilisateur (les 2 onglets d'Aperçu Marché, voir
// ApercuMarche.jsx::TABS "Profil Pays"/"Distribution des agences"), pas le
// nom du document/tableau source (essayé d'abord, corrigé sur demande
// explicite de l'utilisateur 2026-08-19 : "je voulais dire le nom de la
// page comme 'Aperçu marché - Profil pays'"). Tous les KPI sectoriels sauf
// "Total agences (marché)" sont affichés dans Profil Pays (banniere macro +
// taille du marché + ratios techniques) ; seul "Total agences" vit dans
// l'onglet Distribution des agences.
const SECTOR_KPI_GROUPS = [
  {
    title: "Aperçu marché — Profil Pays",
    keys: [
      "Population", "PIB", "Taux de pénétration (marché)", "Densité d'assurance (marché)",
      "Total primes marché", "Primes marché Vie", "Primes marché Non-Vie",
      "Ratio S/P marché", "Ratio de frais marché", "Ratio combiné marché",
      "Ratio S/P marché Vie", "Ratio de frais marché Vie", "Ratio combiné marché Vie",
      "Ratio S/P marché Non-Vie", "Ratio de frais marché Non-Vie", "Ratio combiné marché Non-Vie",
    ],
  },
  {
    title: "Aperçu marché — Distribution des agences",
    keys: ["Total agences (marché)"],
  },
];

// Les 3 sociétés Takaful (AT_TAKAFULIA, ZITOUNA_TAKAFUL, AL_AMANAH_TAKAFUL)
// ont chacune un pipeline d'extraction dédié (extraction/takaful_kpi_extractor.py
// pour les 2 premières, en français ; extraction/arabic_ocr_extractor.py +
// arabic_pdf_cell_coords.py pour AL_AMANAH_TAKAFUL, en arabe RTL) et
// apparaissent donc normalement ici, comme n'importe quelle société
// conventionnelle. AL_AMANAH_TAKAFUL exclue jusqu'au 2026-08-19 (pipeline
// OCR/RTL pas encore construit à l'époque) — retirée de la liste
// maintenant que son extraction est opérationnelle et vérifiée.

function fmtVal(v, storageKey) {
  if (v === null || v === undefined) return null;
  // Les KPI sectoriels "Ratio .../Taux de pénétration" sont des pourcentages
  // mais leur storageKey ne contient pas de "%" littéral (contrairement à
  // "Ratio combiné (%)" côté société) — détecté aussi par motif de libellé.
  const isRatio = storageKey?.includes("%") || /^Ratio |^Taux de pénétration/.test(storageKey ?? "");
  const num = Number(v);
  if (isNaN(num)) return String(v);
  if (isRatio) return `${num.toLocaleString("fr-TN", { maximumFractionDigits: 1 })}%`;
  if (Math.abs(num) >= 1_000_000) return `${(num / 1_000_000).toLocaleString("fr-TN", { maximumFractionDigits: 1 })}M`;
  if (Math.abs(num) >= 1_000)    return `${Math.round(num / 1_000).toLocaleString("fr-TN")}k`;
  return num.toLocaleString("fr-TN", { maximumFractionDigits: 1 });
}

/* ── Page principale : dashboard de pilotage des sources ─────────────────
   Un seul écran — année, puis une matrice société × KPI. Chaque cellule
   mène en UN clic à sa source exacte (KpiDetail) : pas de liste de KPI
   puis liste de sociétés à traverser. ─────────────────────────────────── */
export default function QualiteDonnees() {
  const navigate = useNavigate();
  const [urlParams] = useSearchParams();

  const [years, setYears]      = useState([]);
  const [annee, setAnnee]      = useState(() => Number(urlParams.get("annee")) || null);
  const [data, setData]        = useState(null);
  const [loading, setLoading]  = useState(true);
  // Pré-filtre venant d'un lien direct (KpiOptionsMenu "Voir la qualité de
  // la donnée") : on ne connaît que le code de la société ici (recherche
  // texte déjà existante), `kpi` sert seulement à mettre la ligne en
  // évidence une fois la société ouverte.
  const [search, setSearch]    = useState(() => urlParams.get("code") ?? "");
  const kpiLinkFilter = urlParams.get("kpi");
  // Sélecteur affiché EN PREMIER sur cette page : "entreprise" (matrice
  // société × KPI, comportement historique) ou "sectorielle" (KPI marché,
  // code="MARCHE" — Population, PIB, ratios techniques marché...), sur
  // demande explicite de l'utilisateur (2026-08-19) : cette page ne donnait
  // accès qu'aux KPI par société, aucun moyen d'auditer les KPI sectoriels.
  const [mode, setMode] = useState(() => (urlParams.get("code") === "MARCHE" ? "sectorielle" : "entreprise"));
  const [sectorRaw, setSectorRaw] = useState({});
  // Filtre par page d'application (groupe de SECTOR_KPI_GROUPS) — demande
  // explicite de l'utilisateur (2026-08-19) : pouvoir isoler les KPI d'une
  // seule page plutôt que de tout parcourir d'un coup. "all" = pas de filtre.
  const [pageFilter, setPageFilter] = useState("all");

  useEffect(() => {
    if (!annee) return;
    fetch(`${API}/api/sector-kpi-value?annee=${annee}`)
      .then(r => r.ok ? r.json() : {}).then(setSectorRaw).catch(() => setSectorRaw({}));
  }, [annee]);

  useEffect(() => {
    fetch(`${API}/api/annees-disponibles?source=CMF`)
      .then(r => r.json())
      .then(d => {
        const ys = (d.annees ?? []).slice(0, 10);
        setYears(ys);
        setAnnee(prev => prev ?? ys[0] ?? new Date().getFullYear());
      })
      .catch(() => setYears([]));
  }, []);

  const load = useCallback(async (yr) => {
    if (!yr) return;
    setLoading(true);
    try {
      const r = await fetch(`${API}/api/rapport-qualite?annee=${yr}`);
      setData(await r.json());
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (annee) load(annee); }, [annee, load]);

  const companies = data
    ? Object.entries(data.kpi_detail)
        .filter(([code]) => code.toLowerCase().includes(search.toLowerCase()))
        .sort((a, b) => b[1].taux_remplissage - a[1].taux_remplissage)
    : [];

  const goToSource = (code, storageKey) =>
    navigate(`/kpi-detail?code=${encodeURIComponent(code)}&kpi=${encodeURIComponent(storageKey)}&annee=${annee}`);

  return (
    <div style={{ minHeight: "100vh", background: "#F2F5FB", fontFamily: "'Inter', system-ui, sans-serif" }}>

      {/* ── Header ────────────────────────────────────────────────────── */}
      <div style={{ background: "#2E2E38", padding: "20px 32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", maxWidth: 1400, margin: "0 auto", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,230,0,.7)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 4 }}>
              Pipeline Data Quality · EY
            </div>
            <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "white" }}>
              Qualité Data
            </h1>
            <p style={{ margin: "4px 0 0", fontSize: 11.5, color: "rgba(255,255,255,.45)" }}>
              {mode === "entreprise"
                ? `Source de chaque KPI, pour chaque société, pour ${annee ?? "…"}. Cliquez une cellule pour l'ouvrir dans le PDF.`
                : `Source de chaque KPI sectoriel (marché entier), pour ${annee ?? "…"}. Cliquez une ligne pour l'ouvrir dans sa source.`}
            </p>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", maxWidth: 480 }}>
            {years.map(y => (
              <button key={y} onClick={() => setAnnee(y)} style={{
                padding: "6px 14px", borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: "pointer",
                border: y === annee ? "2px solid #FFE600" : "1px solid rgba(255,255,255,.2)",
                background: y === annee ? "#FFE600" : "rgba(255,255,255,.08)",
                color: y === annee ? "#2E2E38" : "rgba(255,255,255,.6)",
              }}>{y}</button>
            ))}
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 300, color: "#6B7280" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>⏳</div>
            Chargement…
          </div>
        </div>
      ) : !data ? (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 300, color: "#EF4444" }}>
          Erreur de chargement
        </div>
      ) : (
        <div style={{ maxWidth: 1400, margin: "0 auto", padding: "20px 32px" }}>

          {/* ── Sélecteur de périmètre : premier choix sur la page, avant
              tout le reste — demande explicite de l'utilisateur. ── */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            {[
              { key: "entreprise",  label: "🏢 Données entreprise" },
              { key: "sectorielle", label: "🌐 Données sectorielles" },
            ].map(opt => (
              <button key={opt.key} onClick={() => setMode(opt.key)} style={{
                padding: "9px 18px", borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: "pointer",
                border: mode === opt.key ? "2px solid #2E2E38" : "1px solid #DDE2EC",
                background: mode === opt.key ? "#2E2E38" : "#fff",
                color: mode === opt.key ? "#fff" : "#374151",
              }}>{opt.label}</button>
            ))}
          </div>

          {/* ── Légende : chaque icône est toujours accompagnée d'un mot ── */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, flexWrap: "wrap", gap: 12 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {Object.entries(CELL_VISUAL).map(([key, v]) => (
                <div key={key} style={{
                  display: "flex", alignItems: "center", gap: 6,
                  background: v.bg, border: `1px solid ${v.border}`,
                  borderRadius: 20, padding: "4px 10px",
                }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: v.color }}>{v.icon}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: v.color }}>{v.label}</span>
                </div>
              ))}
              <div style={{
                display: "flex", alignItems: "center", gap: 6,
                background: "#FFF7ED", border: "2px solid #F59E0B",
                borderRadius: 20, padding: "3px 10px",
              }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#9A3412" }}>⚠ Aberrant</span>
                <span style={{ fontSize: 10, color: "#9A3412" }}>(entoure Extrait/Calculé — valeur présente mais suspecte)</span>
              </div>
            </div>
            {mode === "entreprise" && (
              <input
                placeholder="Rechercher une compagnie…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{
                  padding: "8px 16px", borderRadius: 10, border: "1px solid #DDE2EC",
                  fontSize: 12, background: "#fff", outline: "none", width: 240,
                }}
              />
            )}
            {mode === "sectorielle" && (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {[{ title: "all", label: "Toutes les pages" }, ...SECTOR_KPI_GROUPS].map(opt => (
                  <button key={opt.title} onClick={() => setPageFilter(opt.title)} style={{
                    padding: "6px 12px", borderRadius: 20, fontSize: 11.5, fontWeight: 700, cursor: "pointer",
                    border: pageFilter === opt.title ? "1.5px solid #2E2E38" : "1px solid #DDE2EC",
                    background: pageFilter === opt.title ? "#2E2E38" : "#fff",
                    color: pageFilter === opt.title ? "#fff" : "#374151",
                  }}>{opt.label ?? opt.title}</button>
                ))}
              </div>
            )}
          </div>

          {mode === "sectorielle" ? (
            // Vrai <table>, pas des cartes — même langage visuel que la
            // matrice société ci-dessous (en-tête sombre, lignes zébrées,
            // survol), sur demande explicite de l'utilisateur (2026-08-19) :
            // "structurer de la même façon que pour données entreprise dans
            // un tableau : par nom de page et nom de kpi". Une ligne
            // d'en-tête de groupe (nom de la page/source réelle) précède
            // chaque bloc de KPI qui en proviennent.
            <div style={{ background: "#fff", borderRadius: 14, border: "1px solid #DDE2EC", overflow: "hidden", boxShadow: "0 2px 12px rgba(12,27,46,.06)" }}>
              <div style={{ overflowX: "auto" }}>
                <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 640 }}>
                  <thead>
                    <tr style={{ background: "#2E2E38" }}>
                      <th style={{ padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,.7)", letterSpacing: "1px", textTransform: "uppercase" }}>KPI</th>
                      <th style={{ padding: "12px 16px", textAlign: "right", fontSize: 11, fontWeight: 700, color: "rgba(255,255,255,.7)", letterSpacing: "1px", textTransform: "uppercase" }}>Valeur</th>
                      <th style={{ width: 40 }} />
                    </tr>
                  </thead>
                  <tbody>
                    {SECTOR_KPI_GROUPS.filter(g => pageFilter === "all" || pageFilter === g.title).map(group => (
                      <Fragment key={group.title}>
                        <tr>
                          <td colSpan={3} style={{
                            padding: "9px 16px", fontSize: 10.5, fontWeight: 700, color: "#8896A8",
                            textTransform: "uppercase", letterSpacing: ".5px", background: "#F8FAFC",
                            borderBottom: "1px solid #EEF1F6", borderTop: "1px solid #EEF1F6",
                          }}>
                            {group.title}
                          </td>
                        </tr>
                        {group.keys.map((key, idx) => {
                          const meta = KPI_META[key];
                          const status = classifyCell("MARCHE", key, data, sectorRaw);
                          const v = resolveCellVisual(status);
                          const value = fmtVal(status.value, key);
                          // Ligne exacte du tableau source (ex. « Population Totale »)
                          // pour les KPI "externe" — plus de colonne dédiée
                          // (retiré sur demande explicite de l'utilisateur,
                          // 2026-08-19), gardée dans l'infobulle au survol.
                          const ligneRef = meta?.type === "externe" ? meta.ligne : null;
                          const title = [`${meta?.label ?? key}${value ? " : " + value : ""}`, ligneRef ? `Ligne : « ${ligneRef} »` : null, v.detail, ...v.aberrantReasons].filter(Boolean).join("\n");
                          const rowBg = idx % 2 === 0 ? "#fff" : "#F8FAFC";
                          return (
                            <tr key={key}
                              className="kpi-hover-card"
                              onClick={() => goToSource("MARCHE", key)}
                              title={title}
                              style={{ background: rowBg, cursor: "pointer" }}
                              onMouseEnter={e => { e.currentTarget.style.background = "#EEF2FF"; }}
                              onMouseLeave={e => { e.currentTarget.style.background = rowBg; }}
                            >
                              <td style={{ padding: "8px 16px", borderBottom: "1px solid #EEF1F6" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                  <span style={{
                                    width: 20, height: 20, borderRadius: 5, flexShrink: 0,
                                    background: v.bg, border: v.aberrant ? "2px solid #F59E0B" : `1.5px solid ${v.border}`,
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    fontSize: 10, fontWeight: 800, color: v.color,
                                  }}>{v.icon}</span>
                                  <span style={{ fontSize: 12.5, fontWeight: 700, color: "#0C1B2E" }}>{meta?.label ?? key}</span>
                                </div>
                              </td>
                              <td style={{ padding: "8px 16px", borderBottom: "1px solid #EEF1F6", textAlign: "right", fontSize: 13, fontWeight: 800, color: "#374151" }}>
                                {value ?? "—"}
                              </td>
                              <td style={{ padding: "8px 8px", borderBottom: "1px solid #EEF1F6" }} onClick={e => e.stopPropagation()}>
                                <KpiOptionsMenu code="MARCHE" kpi={key} annee={annee} label={meta?.label ?? key} value={value ?? undefined} size={20} />
                              </td>
                            </tr>
                          );
                        })}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
          <div style={{ background: "#fff", borderRadius: 14, border: "1px solid #DDE2EC", overflow: "hidden", boxShadow: "0 2px 12px rgba(12,27,46,.06)" }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 1050 }}>
                <thead>
                  <tr style={{ background: "#2E2E38" }}>
                    <th style={{
                      padding: "12px 16px", textAlign: "left", fontSize: 11, fontWeight: 700,
                      color: "rgba(255,255,255,.7)", whiteSpace: "nowrap", letterSpacing: "1px", textTransform: "uppercase",
                      position: "sticky", left: 0, background: "#2E2E38", zIndex: 2,
                      borderRight: "1px solid rgba(255,255,255,.08)",
                    }}>Compagnie</th>
                    {KPI_CATALOG.map(k => (
                      <th key={k.storageKey} title={k.label} style={{
                        padding: "10px 8px", textAlign: "center", fontSize: 10, fontWeight: 700,
                        color: "rgba(255,255,255,.6)", whiteSpace: "nowrap", letterSpacing: ".3px",
                        maxWidth: 90, overflow: "hidden", textOverflow: "ellipsis",
                      }}>
                        {k.label}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {companies.map(([code, detail], idx) => {
                    const fill  = detail.taux_remplissage ?? 0;
                    const rowBg = idx % 2 === 0 ? "#fff" : "#F8FAFC";
                    const accentColor = fill >= 80 ? "#10B981" : fill >= 50 ? "#F59E0B" : "#EF4444";
                    return (
                      <tr key={code} style={{ background: rowBg, borderLeft: `3px solid ${accentColor}` }}
                        onMouseEnter={e => { e.currentTarget.style.background = "#EEF2FF"; }}
                        onMouseLeave={e => { e.currentTarget.style.background = rowBg; }}
                      >
                        <td style={{
                          padding: "8px 16px", fontSize: 12.5, fontWeight: 700, color: "#0C1B2E",
                          borderBottom: "1px solid #EEF1F6", whiteSpace: "nowrap",
                          position: "sticky", left: 0, background: "inherit", zIndex: 1,
                          borderRight: "1px solid #EEF1F6",
                        }} title={code}>
                          {getLogoSrc(code)
                            ? <img src={getLogoSrc(code)} alt={code} style={{ height: 26, maxWidth: 68, objectFit: "contain", display: "block" }} />
                            : code
                          }
                        </td>
                        {KPI_CATALOG.map(k => {
                          const status = classifyCell(code, k.storageKey, data);
                          const v = resolveCellVisual(status);
                          const value = fmtVal(status.value, k.storageKey);
                          const title = [
                            `${code} · ${k.label}${value ? " : " + value : ""}`,
                            v.detail,
                            ...v.aberrantReasons,
                          ].filter(Boolean).join("\n");
                          const isLinked = kpiLinkFilter === k.storageKey && code === urlParams.get("code");
                          return (
                            <td
                              key={k.storageKey}
                              className="kpi-hover-card"
                              ref={isLinked ? (el) => el?.scrollIntoView({ behavior: "smooth", block: "center" }) : undefined}
                              onClick={() => goToSource(code, k.storageKey)}
                              title={title}
                              style={{
                                padding: "5px 4px", textAlign: "center", borderBottom: "1px solid #EEF1F6", cursor: "pointer",
                                outline: isLinked ? "2px solid #FFE600" : "none", outlineOffset: -2,
                                background: isLinked ? "#FFFBEA" : undefined,
                              }}
                            >
                              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1, position: "relative" }}>
                                <div style={{
                                  width: 22, height: 22, borderRadius: 6, position: "relative",
                                  background: v.bg,
                                  border: v.aberrant ? "2px solid #F59E0B" : `1.5px solid ${v.border}`,
                                  display: "flex", alignItems: "center", justifyContent: "center",
                                  fontSize: 10, fontWeight: 800, color: v.color,
                                }}>
                                  {v.icon}
                                  {v.aberrant && (
                                    <span style={{
                                      position: "absolute", top: -5, right: -5,
                                      fontSize: 9, background: "#FFF7ED", borderRadius: "50%",
                                    }}>⚠</span>
                                  )}
                                </div>
                                <span style={{ fontSize: 9, fontWeight: 600, color: "#6B7280", whiteSpace: "nowrap" }}>
                                  {value ?? "—"}
                                </span>
                                <div style={{ position: "absolute", top: -6, left: -6 }}>
                                  <KpiOptionsMenu code={code} kpi={k.storageKey} annee={annee} label={k.label} value={value ?? undefined} size={18} />
                                </div>
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
          )}
        </div>
      )}
    </div>
  );
}
