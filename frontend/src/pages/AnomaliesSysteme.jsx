import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { getLayer } from "../utils/anomalyLayers";
import { GravBadge, LayerBadge } from "../components/AnomalyDetail";
import { kpiLabel } from "../utils/kpiCatalog";
import { getLogoSrc } from "../utils/logos";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const C = {
  bg: "#F2F5FB", card: "#FFFFFF", navy: "#0C1B2E",
  mid: "#4A5568", muted: "#8896A8", border: "#DDE2EC",
};

const GRAVITE_ORDER = { "Critique": 0, "Élevée": 1, "Moyenne": 2, "Faible": 3 };

/**
 * Page volontairement minimale : un tableau filtrable des anomalies
 * détectées, rien d'autre. Le diagnostic détaillé (couche, cause,
 * recommandation, propagation amont) vit désormais dans KpiDetail.jsx —
 * chaque ligne y mène directement, c'est le seul endroit où "pourquoi c'est
 * faux" est expliqué (voir frontend/src/components/AnomalyDetail.jsx).
 */
export default function AnomaliesSysteme() {
  const navigate = useNavigate();
  const [urlParams] = useSearchParams();

  const [years, setYears] = useState([]);
  const [annee, setAnnee] = useState(() => Number(urlParams.get("annee")) || null);
  const [data, setData]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [searchQ, setSearchQ]     = useState(urlParams.get("code") ?? "");
  const [filterGrav, setFilterGrav] = useState("Tous");
  const [filterType, setFilterType] = useState("Tous");
  const [filterLayer, setFilterLayer] = useState("Tous");
  // Filtre précis "code + kpi exact" venant d'un lien depuis Qualité Data ou
  // KpiDetail — distinct de la recherche libre pour ne pas remonter toutes
  // les anomalies de la société quand on cherchait UN KPI précis.
  const [kpiLinkFilter, setKpiLinkFilter] = useState(() => {
    const code = urlParams.get("code");
    const kpi  = urlParams.get("kpi");
    return code && kpi ? { code, kpi } : null;
  });

  // Rapport IA générative (Groq, voir api/services/anomalies_service.py::
  // generate_rapport_ia) — backend construit depuis le début de la session
  // mais jamais branché au frontend jusqu'ici (étape 4 du plan explicite de
  // l'utilisateur, 2026-08-19). Généré à la demande (bouton), pas au
  // chargement de la page : l'appel LLM a un coût et une latence, pas
  // question de le déclencher à chaque visite/changement d'année.
  const [rapportIa, setRapportIa] = useState(null);
  const [rapportLoading, setRapportLoading] = useState(false);
  const [rapportError, setRapportError] = useState(null);
  const [rapportOpen, setRapportOpen] = useState(false);

  const genererRapportIa = () => {
    if (!annee) return;
    setRapportOpen(true);
    setRapportLoading(true);
    setRapportError(null);
    fetch(`${API}/api/rapport-ia?annee=${annee}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setRapportIa(d.rapport); setRapportLoading(false); })
      .catch(e => { setRapportError(e.message); setRapportLoading(false); });
  };

  // Un rapport déjà généré ne concerne qu'une année précise — on l'efface
  // au changement d'année plutôt que d'afficher un rapport périmé sous un
  // nouveau contexte sans que l'utilisateur s'en aperçoive.
  useEffect(() => { setRapportIa(null); setRapportError(null); setRapportOpen(false); }, [annee]);

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

  useEffect(() => {
    if (!annee) return;
    setLoading(true);
    setError(null);
    fetch(`${API}/api/anomalies-systeme?annee=${annee}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [annee]);

  const anomalies = data?.anomalies ?? [];
  const types  = ["Tous", ...new Set(anomalies.map(a => a.type))];
  const gravs  = ["Tous", "Critique", "Élevée", "Moyenne", "Faible"];
  const layers = ["Tous", "Extraction", "Cleaning data", "Modélisation"];

  const filtered = anomalies
    .filter(a => {
      if (kpiLinkFilter && (a.code !== kpiLinkFilter.code || a.kpi !== kpiLinkFilter.kpi)) return false;
      if (filterGrav !== "Tous" && a.dq_gravite !== filterGrav) return false;
      if (filterType !== "Tous" && a.type !== filterType) return false;
      if (filterLayer !== "Tous" && getLayer(a.etape, a.kpi) !== filterLayer) return false;
      if (searchQ) {
        const q = searchQ.toLowerCase();
        if (!kpiLabel(a.kpi)?.toLowerCase().includes(q) && !a.code?.toLowerCase().includes(q)
          && !a.raison?.toLowerCase().includes(q)) return false;
      }
      return true;
    })
    .sort((a, b) => (GRAVITE_ORDER[a.dq_gravite] ?? 9) - (GRAVITE_ORDER[b.dq_gravite] ?? 9));

  const goToKpiDetail = (a) => navigate(`/kpi-detail?code=${encodeURIComponent(a.code)}&kpi=${encodeURIComponent(a.kpi)}&annee=${a.annee}`);

  return (
    <div style={{ minHeight: "calc(100vh - 92px)", background: C.bg, fontFamily: "Barlow,system-ui,sans-serif" }}>

      {/* ── En-tête ───────────────────────────────────────────────────── */}
      <div style={{ background: "#2E2E38", padding: "20px 32px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,230,0,.7)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 4 }}>
            Pipeline Data Quality · EY
          </div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "white" }}>Anomalies Système</h1>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
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
          <button onClick={genererRapportIa} disabled={rapportLoading} style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "8px 16px", borderRadius: 8, fontSize: 12, fontWeight: 700,
            cursor: rapportLoading ? "default" : "pointer", border: "none",
            background: "#FFE600", color: "#2E2E38", opacity: rapportLoading ? 0.7 : 1,
          }}>
            ✦ {rapportLoading ? "Génération…" : "Rapport IA"}
          </button>
        </div>
      </div>

      <div style={{ padding: "24px 32px" }}>
        {rapportOpen && (
          <div style={{ maxWidth: 1100, margin: "0 auto 18px" }}>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, overflow: "hidden" }}>
              <div style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "10px 16px", background: "#2E2E38",
              }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#FFE600" }}>✦ Rapport IA générative — {annee}</span>
                <button onClick={() => setRapportOpen(false)} title="Fermer" style={{
                  background: "none", border: "none", color: "rgba(255,255,255,.6)",
                  fontSize: 16, cursor: "pointer", lineHeight: 1, padding: 4,
                }}>×</button>
              </div>
              <div style={{ padding: "18px 22px", maxHeight: 520, overflowY: "auto" }}>
                {rapportLoading && (
                  <div style={{ textAlign: "center", padding: 30, color: C.muted }}>
                    <div style={{ width: 26, height: 26, border: "3px solid #E5E7EB", borderTopColor: C.navy,
                      borderRadius: "50%", animation: "spin .8s linear infinite", margin: "0 auto 12px" }} />
                    Génération du rapport en cours…
                  </div>
                )}
                {rapportError && (
                  <div style={{ color: "#DC2626", fontSize: 13 }}>Erreur : {rapportError}</div>
                )}
                {!rapportLoading && !rapportError && rapportIa && (
                  <div className="rapport-ia-markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{rapportIa}</ReactMarkdown>
                  </div>
                )}
              </div>
            </div>
            <style>{`
              .rapport-ia-markdown { font-size: 13px; line-height: 1.65; color: ${C.mid}; }
              .rapport-ia-markdown h1 { font-size: 18px; font-weight: 800; color: ${C.navy}; margin: 0 0 10px; }
              .rapport-ia-markdown h2 { font-size: 15px; font-weight: 800; color: ${C.navy}; margin: 20px 0 8px; }
              .rapport-ia-markdown h3 { font-size: 13px; font-weight: 700; color: ${C.navy}; margin: 14px 0 6px; }
              .rapport-ia-markdown p { margin: 0 0 10px; }
              .rapport-ia-markdown strong { color: ${C.navy}; }
              .rapport-ia-markdown ul, .rapport-ia-markdown ol { margin: 0 0 10px; padding-left: 20px; }
              .rapport-ia-markdown li { margin-bottom: 4px; }
              .rapport-ia-markdown hr { border: none; border-top: 1px solid ${C.border}; margin: 16px 0; }
              .rapport-ia-markdown table { width: 100%; border-collapse: collapse; margin: 0 0 14px; font-size: 12px; }
              .rapport-ia-markdown th, .rapport-ia-markdown td { border: 1px solid ${C.border}; padding: 6px 10px; text-align: left; }
              .rapport-ia-markdown th { background: #F8FAFC; font-weight: 700; color: ${C.navy}; }
            `}</style>
          </div>
        )}
        {loading && (
          <div style={{ textAlign: "center", padding: 60, color: C.muted }}>
            <div style={{ width: 32, height: 32, border: "3px solid #E5E7EB", borderTopColor: C.navy,
              borderRadius: "50%", animation: "spin .8s linear infinite", margin: "0 auto 14px" }} />
            <div>Chargement…</div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        )}
        {error && (
          <div style={{ background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 10, padding: 20, color: "#DC2626", fontSize: 13 }}>
            Erreur de chargement : {error}
          </div>
        )}

        {!loading && !error && (
          <div style={{ maxWidth: 1100, margin: "0 auto" }}>

            {/* ── Filtres ───────────────────────────────────────────────── */}
            <div style={{
              display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
              background: C.card, border: `1px solid ${C.border}`, borderRadius: 10,
              padding: "12px 14px", marginBottom: 14,
            }}>
              <input
                placeholder="Rechercher KPI, compagnie, description…"
                value={searchQ} onChange={e => setSearchQ(e.target.value)}
                style={{ flex: 1, minWidth: 200, border: `1px solid ${C.border}`, borderRadius: 8, padding: "7px 12px", fontSize: 12, outline: "none", fontFamily: "inherit" }}
              />
              <select value={filterGrav} onChange={e => setFilterGrav(e.target.value)}
                style={{ border: `1px solid ${C.border}`, borderRadius: 8, padding: "7px 10px", fontSize: 12, fontFamily: "inherit", background: C.card }}>
                {gravs.map(g => <option key={g}>{g}</option>)}
              </select>
              <select value={filterType} onChange={e => setFilterType(e.target.value)}
                style={{ border: `1px solid ${C.border}`, borderRadius: 8, padding: "7px 10px", fontSize: 12, fontFamily: "inherit", background: C.card }}>
                {types.map(t => <option key={t}>{t}</option>)}
              </select>
              <select value={filterLayer} onChange={e => setFilterLayer(e.target.value)}
                style={{ border: `1px solid ${C.border}`, borderRadius: 8, padding: "7px 10px", fontSize: 12, fontFamily: "inherit", background: C.card }}>
                {layers.map(l => <option key={l}>{l}</option>)}
              </select>
              {kpiLinkFilter && (
                <span
                  onClick={() => setKpiLinkFilter(null)}
                  title="Retirer ce filtre"
                  style={{
                    display: "flex", alignItems: "center", gap: 6, cursor: "pointer",
                    background: "#EEF2FF", color: "#4338CA", border: "1px solid #C7D2FE",
                    borderRadius: 20, padding: "5px 10px", fontSize: 11, fontWeight: 600,
                  }}>
                  {kpiLinkFilter.code} · {kpiLabel(kpiLinkFilter.kpi)} <strong>×</strong>
                </span>
              )}
              <span style={{ fontSize: 11, color: C.muted, whiteSpace: "nowrap" }}>
                {filtered.length} anomalie{filtered.length > 1 ? "s" : ""}
              </span>
            </div>

            {/* ── Tableau ───────────────────────────────────────────────── */}
            <div style={{ background: C.card, borderRadius: 10, border: `1px solid ${C.border}`, overflow: "hidden" }}>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr style={{ background: "#F8FAFC" }}>
                    {["Compagnie", "KPI", "Couche", "Gravité", "Description"].map(h => (
                      <th key={h} style={{
                        padding: "9px 14px", fontSize: 10, fontWeight: 700, color: C.muted,
                        textAlign: "left", textTransform: "uppercase", letterSpacing: "0.5px",
                        borderBottom: `1px solid ${C.border}`,
                      }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 && (
                    <tr><td colSpan={5} style={{ padding: 40, textAlign: "center", color: C.muted, fontSize: 12 }}>
                      Aucune anomalie correspondant aux filtres
                    </td></tr>
                  )}
                  {filtered.map((a, i) => (
                    <tr
                      key={i}
                      onClick={() => goToKpiDetail(a)}
                      style={{ cursor: "pointer", borderTop: i > 0 ? `1px solid ${C.border}` : "none" }}
                      onMouseEnter={e => { e.currentTarget.style.background = "#F8FAFC"; }}
                      onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
                    >
                      <td style={{ padding: "9px 14px", fontSize: 12, fontWeight: 700, color: C.navy }} title={a.code}>
                        {getLogoSrc(a.code)
                          ? <img src={getLogoSrc(a.code)} alt={a.code} style={{ height: 24, maxWidth: 64, objectFit: "contain", display: "block" }} />
                          : a.code
                        }
                      </td>
                      <td style={{ padding: "9px 14px", fontSize: 12, color: C.mid }}>{kpiLabel(a.kpi)}</td>
                      <td style={{ padding: "9px 14px" }}><LayerBadge layer={getLayer(a.etape, a.kpi)} /></td>
                      <td style={{ padding: "9px 14px" }}><GravBadge g={a.dq_gravite} /></td>
                      <td style={{
                        padding: "9px 14px", fontSize: 11.5, color: C.mid,
                        maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }} title={a.raison}>{a.raison}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
