import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { KPI_CATALOG } from "../utils/kpiCatalog";
import { classifyCell, resolveCellVisual, CELL_VISUAL } from "../utils/kpiStatus";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

// Assurances islamiques (Takaful) — structure comptable fondamentalement
// différente (comptes "Fonds des Adhérents" / "Entreprise" séparés au lieu
// d'un bilan unique) : le pipeline d'extraction actuel n'est pas conçu pour
// ce modèle, donc quasi tout y apparaît comme non extrait/non calculé. Ce
// n'est pas une anomalie de CES sociétés, c'est un pipeline qui reste à
// construire — les afficher ici mélangerait les deux et serait trompeur.
// Retiré de cette page ; à traiter dans un pipeline Takaful dédié (voir
// docs/travaux_futurs.md).
const TAKAFUL_CODES = new Set(["AL_AMANAH_TAKAFUL", "AT_TAKAFULIA", "ZITOUNA_TAKAFUL"]);

function fmtVal(v, storageKey) {
  if (v === null || v === undefined) return null;
  const isRatio = storageKey?.includes("%");
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
  const [search, setSearch]    = useState("");

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
        .filter(([code]) => !TAKAFUL_CODES.has(code))
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
              Source de chaque KPI, pour chaque société, pour {annee ?? "…"}. Cliquez une cellule pour l'ouvrir dans le PDF.
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
            <input
              placeholder="Rechercher une compagnie…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                padding: "8px 16px", borderRadius: 10, border: "1px solid #DDE2EC",
                fontSize: 12, background: "#fff", outline: "none", width: 240,
              }}
            />
          </div>

          <div style={{ fontSize: 10.5, color: "#8896A8", marginBottom: 10 }}>
            Assurances islamiques (Takaful) non affichées ici — structure comptable différente (Fonds des Adhérents / Entreprise séparés), pipeline d'extraction dédié pas encore construit. Voir <code>docs/travaux_futurs.md</code>.
          </div>

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
                        }}>
                          {code}
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
                          return (
                            <td
                              key={k.storageKey}
                              onClick={() => goToSource(code, k.storageKey)}
                              title={title}
                              style={{ padding: "5px 4px", textAlign: "center", borderBottom: "1px solid #EEF1F6", cursor: "pointer" }}
                            >
                              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 1 }}>
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
        </div>
      )}
    </div>
  );
}
