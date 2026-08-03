import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { kpiLabel } from "../utils/kpiCatalog";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

/* ── Palette gravité ─────────────────────────────────────────────────────── */
const GRAVITE = {
  critique:      { text: "#991B1B", bg: "#FEF2F2", border: "#FCA5A5", dot: "#DC2626", label: "Critique" },
  erreur:        { text: "#9A3412", bg: "#FFF7ED", border: "#FED7AA", dot: "#EA580C", label: "Erreur" },
  avertissement: { text: "#854D0E", bg: "#FEFCE8", border: "#FDE68A", dot: "#CA8A04", label: "Avertissement" },
  info:          { text: "#1E40AF", bg: "#EFF6FF", border: "#BFDBFE", dot: "#2563EB", label: "Info" },
};

const GRAVITE_ORDER = ["critique", "erreur", "avertissement", "info"];

/* ── Étapes pipeline ─────────────────────────────────────────────────────── */
const ETAPES = [
  { num: 1, label: "PDF manquant",                          dot: "#DC2626" },
  { num: 2, label: "Section PDF probablement non extraite", dot: "#EA580C" },
  { num: 3, label: "Composante manquante",                  dot: "#F59E0B" },
  { num: 4, label: "Recalculé (composantes partielles)",    dot: "#2563EB" },
  { num: 5, label: "Extraction échouée",                    dot: "#7C3AED" },
  { num: 6, label: "Valeur aberrante",                      dot: "#CA8A04" },
];

const ETAPE_DOT = Object.fromEntries(ETAPES.map(e => [e.num, e.dot]));

const METHODO = [
  { num: 1, label: "PDF manquant",         dot: "#DC2626", desc: "Le fichier PDF du rapport CMF n'a pas été téléchargé localement.", methode: "os.path.isfile(data/cmf/{CODE}/{CODE}_{ANNEE}.pdf)" },
  { num: 2, label: "Section non extraite", dot: "#EA580C", desc: "Aucune valeur de la section cible (Annexe 12/13, Bilan…) n'est en base.", methode: "Aucun KPI de la section présent en DB → section inaccessible dans le PDF." },
  { num: 3, label: "Composante manquante", dot: "#F59E0B", desc: "La section a été trouvée, mais la ligne ou colonne précise n'a pas été reconnue.", methode: "Comparaison du libellé normalisé (NFKD, minuscules) avec les patterns de l'extracteur." },
  { num: 4, label: "Recalculé partiel",    dot: "#2563EB", desc: "Le KPI a été estimé malgré des composantes manquantes.", methode: "kpi_builder.py applique la formule avec les composantes disponibles. Valeur approximative." },
  { num: 5, label: "Extraction échouée",   dot: "#7C3AED", desc: "La valeur brute est absente de la DB sans cause amont identifiée.", methode: "Valeur nulle en DB après passage complet du pipeline." },
  { num: 6, label: "Valeur aberrante",     dot: "#CA8A04", desc: "La valeur est présente mais hors des bornes métier définies.", methode: "Comparaison avec plages : RC [30–500 %], ROE [−200–200 %], ROA [−50–50 %], etc." },
];

const PLAGES = {
  "Ratio combiné (%)":             [30, 500],
  "Ratio de sinistralité (%)":     [10, 400],
  "Ratio de frais de gestion (%)": [2,  200],
  "Part de marché (%)":            [0.01, 50],
  "ROE (%)":                       [-200, 200],
  "ROA (%)":                       [-50,  50],
};

/* ── Composants utilitaires ─────────────────────────────────────────────── */
function GravDot({ gravite, size = 8 }) {
  const g = GRAVITE[gravite] || GRAVITE.info;
  return <span style={{ display:"inline-block", width:size, height:size, borderRadius:"50%", background:g.dot, flexShrink:0 }} />;
}

function GravBadge({ gravite }) {
  const g = GRAVITE[gravite] || GRAVITE.info;
  return (
    <span style={{
      display:"inline-flex", alignItems:"center", gap:5,
      background:g.bg, color:g.text, border:`1px solid ${g.border}`,
      fontSize:10, fontWeight:700, padding:"2px 8px", borderRadius:4,
      textTransform:"uppercase", letterSpacing:"0.06em", whiteSpace:"nowrap",
    }}>
      <GravDot gravite={gravite} size={6} />
      {g.label}
    </span>
  );
}

function StatCard({ label, value, dot, sub }) {
  return (
    <div style={{ background:"#fff", border:"1px solid #E5E7EB", borderRadius:10, padding:"16px 20px", flex:"1 1 130px", minWidth:130 }}>
      <div style={{ fontSize:30, fontWeight:800, color:dot, fontVariantNumeric:"tabular-nums", lineHeight:1 }}>{value}</div>
      <div style={{ fontSize:12, color:"#374151", fontWeight:600, marginTop:6 }}>{label}</div>
      {sub && <div style={{ fontSize:11, color:"#9CA3AF", marginTop:2 }}>{sub}</div>}
    </div>
  );
}

/* ── Ligne d'anomalie ────────────────────────────────────────────────────── */
function AnomalieRow({ p, navigate }) {
  const [open, setOpen] = useState(false);
  const plage = PLAGES[p.kpi];

  return (
    <div style={{ borderBottom:"1px solid #F3F4F6", background: open ? "#FAFAFA" : "#fff" }}>
      <div onClick={() => setOpen(o => !o)}
        style={{ display:"flex", alignItems:"center", gap:10, padding:"10px 16px", cursor:"pointer" }}>
        <span style={{
          width:20, height:20, borderRadius:"50%", background: ETAPE_DOT[p.etape] || "#94A3B8",
          display:"flex", alignItems:"center", justifyContent:"center",
          fontSize:10, fontWeight:800, color:"#fff", flexShrink:0,
        }}>{p.etape}</span>
        <GravBadge gravite={p.gravite} />
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:12, fontWeight:700, color:"#111827", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{kpiLabel(p.kpi)}</div>
          <div style={{ fontSize:11, color:"#6B7280", marginTop:1, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{p.raison}</div>
        </div>
        <span style={{ color:"#9CA3AF", fontSize:11 }}>{open ? "▲" : "▼"}</span>
      </div>

      {open && (
        <div style={{ padding:"0 16px 14px 46px", display:"flex", flexDirection:"column", gap:10 }}>
          <div style={{ fontSize:11, color:"#374151", lineHeight:1.6, background:"#F8FAFC", borderRadius:6, padding:"8px 12px", borderLeft:"3px solid #E5E7EB" }}>
            <strong>Analyse :</strong> {p.details || p.raison}
          </div>

          {/* Valeur aberrante */}
          {p.etape === 6 && p.valeur != null && (
            <div style={{ background:"#FFFBEB", border:"1px solid #FDE68A", borderRadius:8, padding:"12px 14px" }}>
              <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", color:"#854D0E", letterSpacing:"0.06em", marginBottom:8 }}>Justification — valeur aberrante</div>
              <div style={{ display:"flex", alignItems:"center", gap:16, flexWrap:"wrap" }}>
                <div>
                  <div style={{ fontSize:22, fontWeight:800, color:"#EA580C", fontVariantNumeric:"tabular-nums" }}>
                    {p.valeur.toLocaleString("fr-TN", { maximumFractionDigits:2 })}{p.kpi.includes("%") ? " %" : ""}
                  </div>
                  <div style={{ fontSize:10, color:"#9CA3AF", marginTop:2 }}>Valeur extraite</div>
                </div>
                {plage && (
                  <div>
                    <div style={{ fontSize:13, fontWeight:700, color:"#374151" }}>
                      [{plage[0].toLocaleString("fr-TN")} ; {plage[1].toLocaleString("fr-TN")}{p.kpi.includes("%") ? " %" : ""}]
                    </div>
                    <div style={{ fontSize:10, color:"#9CA3AF", marginTop:2 }}>Plage métier attendue</div>
                  </div>
                )}
              </div>
              <div style={{ fontSize:11, color:"#78350F", marginTop:8, lineHeight:1.5 }}>
                <strong>Causes probables :</strong> décalage de colonne, cellule fusionnée mal interprétée, ou unité différente (milliers vs unités).
              </div>
            </div>
          )}

          {/* Valeur recalculée */}
          {p.etape === 4 && p.valeur != null && (
            <div style={{ display:"flex", alignItems:"center", gap:10, fontSize:12 }}>
              <span style={{ color:"#6B7280" }}>Valeur estimée :</span>
              <span style={{ fontWeight:800, color:"#2563EB", fontVariantNumeric:"tabular-nums" }}>
                {p.valeur.toLocaleString("fr-TN", { maximumFractionDigits:2 })}{p.kpi.includes("%") ? " %" : ""}
              </span>
              <span style={{ color:"#9CA3AF", fontSize:11 }}>(approximation — composante(s) manquante(s))</span>
            </div>
          )}

          {/* Composantes manquantes */}
          {p.composantes_manquantes?.length > 0 && (
            <div>
              <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", color:"#6B7280", letterSpacing:"0.06em", marginBottom:5 }}>Composantes manquantes</div>
              <div style={{ display:"flex", flexWrap:"wrap", gap:5 }}>
                {p.composantes_manquantes.map(c => (
                  <span key={c} style={{ background:"#FEF2F2", border:"1px solid #FCA5A5", color:"#991B1B", fontSize:11, padding:"2px 8px", borderRadius:4, fontFamily:"ui-monospace,monospace" }}>{c}</span>
                ))}
              </div>
            </div>
          )}

          {/* Sections accessibles */}
          {Object.keys(p.sections_accessibles || {}).length > 0 && (
            <div style={{ display:"flex", gap:5, flexWrap:"wrap" }}>
              {Object.keys(p.sections_accessibles).map(s => (
                <span key={s} style={{ background:"#F0FDF4", border:"1px solid #BBF7D0", color:"#15803D", fontSize:10, padding:"2px 8px", borderRadius:4 }}>✓ {s}</span>
              ))}
            </div>
          )}

          <div style={{ display:"flex", gap:8, paddingTop:4 }}>
            {p.pdf_local && (
              <button onClick={e => { e.stopPropagation(); navigate(`/kpi-detail?code=${encodeURIComponent(p.code)}&kpi=${encodeURIComponent(p.kpi)}&annee=${p.annee}`); }}
                style={{ background:"#111827", color:"#fff", border:"none", borderRadius:6, padding:"5px 12px", fontSize:11, cursor:"pointer", fontWeight:600 }}>
                Voir dans le PDF
              </button>
            )}
            {p.pdf_lien && (
              <a href={p.pdf_lien} target="_blank" rel="noreferrer"
                style={{ background:"#fff", color:"#374151", border:"1px solid #D1D5DB", borderRadius:6, padding:"5px 12px", fontSize:11, textDecoration:"none", fontWeight:600 }}>
                Source CMF
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Carte compagnie ─────────────────────────────────────────────────────── */
function CompanyCard({ code, problemes, annee, navigate }) {
  const [open, setOpen] = useState(false);

  const sorted = [...problemes].sort((a, b) => {
    const gi = g => GRAVITE_ORDER.indexOf(g);
    if (gi(a.gravite) !== gi(b.gravite)) return gi(a.gravite) - gi(b.gravite);
    return a.etape - b.etape;
  });

  const gravCounts = GRAVITE_ORDER.reduce((acc, g) => {
    const n = problemes.filter(p => p.gravite === g).length;
    if (n) acc.push({ g, n });
    return acc;
  }, []);

  const pdfLocal = problemes[0]?.pdf_local;
  const pdfLien  = problemes[0]?.pdf_lien;
  const worstGrav = sorted[0]?.gravite || "info";
  const wg = GRAVITE[worstGrav] || GRAVITE.info;

  return (
    <div style={{ border:`1px solid ${open ? wg.border : "#E5E7EB"}`, borderRadius:10, overflow:"hidden", background:"#fff" }}>
      <div onClick={() => setOpen(o => !o)} style={{
        display:"flex", alignItems:"center", gap:12, padding:"12px 16px", cursor:"pointer",
        background: open ? wg.bg : "#fff",
        borderBottom: open ? `1px solid ${wg.border}` : "none",
      }}>
        <span style={{ fontFamily:"ui-monospace,monospace", fontWeight:800, fontSize:13, color:"#111827", background:"#F3F4F6", padding:"3px 10px", borderRadius:5, whiteSpace:"nowrap" }}>
          {code}
        </span>

        <div style={{ display:"flex", gap:6, flexWrap:"wrap" }}>
          {gravCounts.map(({ g, n }) => (
            <span key={g} style={{
              display:"flex", alignItems:"center", gap:4,
              background: GRAVITE[g].bg, border:`1px solid ${GRAVITE[g].border}`,
              color: GRAVITE[g].text, fontSize:11, fontWeight:700, padding:"2px 7px", borderRadius:4,
            }}>
              <GravDot gravite={g} size={6} />
              {n} {GRAVITE[g].label}
            </span>
          ))}
        </div>

        <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:8 }}>
          <span style={{
            fontSize:10, fontWeight:700, textTransform:"uppercase",
            color: pdfLocal ? "#15803D" : "#DC2626",
            background: pdfLocal ? "#F0FDF4" : "#FEF2F2",
            border: `1px solid ${pdfLocal ? "#BBF7D0" : "#FCA5A5"}`,
            padding:"2px 7px", borderRadius:4,
          }}>
            PDF {pdfLocal ? "LOCAL ✓" : "ABSENT ✗"}
          </span>
          {pdfLien && (
            <a href={pdfLien} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
              style={{ fontSize:11, color:"#6B7280", textDecoration:"none", fontWeight:600 }}>
              CMF ↗
            </a>
          )}
          <span style={{ color:"#9CA3AF", fontSize:12 }}>{open ? "▲" : "▼"}</span>
        </div>
      </div>

      {open && (
        <div>
          {sorted.map((p, i) => (
            <AnomalieRow key={`${p.kpi}-${p.etape}-${i}`} p={p} navigate={navigate} />
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Pipeline bar ────────────────────────────────────────────────────────── */
function PipelineBar({ par_etape }) {
  const total = Object.values(par_etape).reduce((a, b) => a + b, 0);
  if (!total) return null;
  return (
    <div>
      <div style={{ display:"flex", height:8, borderRadius:4, overflow:"hidden", gap:1, marginBottom:10 }}>
        {ETAPES.map(e => {
          const count = par_etape[e.label] || 0;
          if (!count) return null;
          return <div key={e.num} title={`${e.label} : ${count}`} style={{ flex:count, background:e.dot, minWidth:4 }} />;
        })}
      </div>
      <div style={{ display:"flex", flexWrap:"wrap", gap:"8px 20px" }}>
        {ETAPES.map(e => {
          const count = par_etape[e.label] || 0;
          if (!count) return null;
          return (
            <div key={e.num} style={{ display:"flex", alignItems:"center", gap:6, fontSize:12 }}>
              <span style={{ width:10, height:10, borderRadius:2, background:e.dot, flexShrink:0 }} />
              <span style={{ color:"#374151" }}>
                <strong>{e.label}</strong>
                <span style={{ color:"#9CA3AF", marginLeft:4 }}>{count} ({((count/total)*100).toFixed(0)} %)</span>
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Méthodologie (collapsible) ──────────────────────────────────────────── */
function Methodo({ open, onToggle }) {
  return (
    <div style={{ border:"1px solid #E5E7EB", borderRadius:10, overflow:"hidden", marginBottom:20 }}>
      <button onClick={onToggle} style={{
        width:"100%", display:"flex", alignItems:"center", justifyContent:"space-between",
        padding:"12px 18px", background:"#F9FAFB", border:"none", cursor:"pointer",
      }}>
        <div>
          <div style={{ fontSize:13, fontWeight:700, color:"#111827" }}>Méthodologie de détection des anomalies</div>
          <div style={{ fontSize:11, color:"#6B7280", marginTop:1 }}>Pipeline en 6 étapes — du PDF source au KPI final</div>
        </div>
        <span style={{ color:"#9CA3AF", fontSize:16 }}>{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div style={{ padding:"0 18px 18px", background:"#fff", borderTop:"1px solid #E5E7EB" }}>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(280px, 1fr))", gap:10, marginTop:14 }}>
            {METHODO.map(e => (
              <div key={e.num} style={{ padding:"10px 12px", borderRadius:8, border:"1px solid #E5E7EB", background:"#FAFAFA" }}>
                <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:5 }}>
                  <span style={{ width:20, height:20, borderRadius:"50%", background:e.dot, display:"flex", alignItems:"center", justifyContent:"center", fontSize:10, fontWeight:800, color:"#fff", flexShrink:0 }}>{e.num}</span>
                  <span style={{ fontSize:12, fontWeight:700, color:"#111827" }}>{e.label}</span>
                </div>
                <p style={{ margin:"0 0 6px", fontSize:11, color:"#374151", lineHeight:1.5 }}>{e.desc}</p>
                <div style={{ fontSize:10, color:"#6B7280", background:"#F3F4F6", borderRadius:4, padding:"4px 8px", fontFamily:"ui-monospace,monospace" }}>{e.methode}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Page principale ──────────────────────────────────────────────────────── */
export default function RapportPipeline() {
  const navigate = useNavigate();
  const [annee, setAnnee]     = useState(2024);
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);
  const [methodoOpen, setMethodoOpen] = useState(false);
  const [filtreGrav,  setFiltreGrav]  = useState("Toutes");
  const [filtreEtape, setFiltreEtape] = useState("Toutes");
  const [searchQ, setSearchQ] = useState("");

  const annees = [2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015, 2014];

  useEffect(() => {
    setData(null); setError(null); setLoading(true);
    fetch(`${API}/api/rapport-pipeline?annee=${annee}`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [annee]);

  const companyGroups = useMemo(() => {
    if (!data?.problemes) return [];
    const q = searchQ.toLowerCase();
    const filtered = data.problemes.filter(p => {
      if (filtreGrav  !== "Toutes" && p.gravite     !== filtreGrav)    return false;
      if (filtreEtape !== "Toutes" && p.etape_label !== filtreEtape)   return false;
      if (q && !`${p.code} ${p.kpi} ${p.raison} ${p.details || ""}`.toLowerCase().includes(q)) return false;
      return true;
    });
    const map = {};
    for (const p of filtered) {
      if (!map[p.code]) map[p.code] = [];
      map[p.code].push(p);
    }
    return Object.entries(map).sort(([, a], [, b]) => {
      const worst = ps => Math.min(...ps.map(p => GRAVITE_ORDER.indexOf(p.gravite)));
      if (worst(a) !== worst(b)) return worst(a) - worst(b);
      return b.length - a.length;
    });
  }, [data, filtreGrav, filtreEtape, searchQ]);

  const totalFiltered = companyGroups.reduce((s, [, ps]) => s + ps.length, 0);
  const grav = data?.par_gravite || {};
  const sel = { border:"1px solid #D1D5DB", borderRadius:6, padding:"6px 10px", fontSize:12, background:"#fff", color:"#111827", cursor:"pointer" };

  return (
    <div style={{ minHeight:"100vh", background:"#F3F4F6", fontFamily:"Barlow, system-ui, sans-serif" }}>
      <div style={{ background:"#fff", borderBottom:"1px solid #E5E7EB", padding:"20px 0" }}>
        <div style={{ maxWidth:1200, margin:"0 auto", padding:"0 32px" }}>
          <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:8 }}>
            <button onClick={() => navigate(-1)} style={{ background:"none", border:"1px solid #E5E7EB", borderRadius:6, padding:"5px 12px", cursor:"pointer", color:"#6B7280", fontSize:12, fontWeight:600 }}>← Retour</button>
            <span style={{ fontSize:11, color:"#6B7280", fontWeight:700, background:"#F3F4F6", padding:"2px 10px", borderRadius:20 }}>Audit pipeline · {annee}</span>
          </div>
          <h1 style={{ margin:"0 0 6px", fontSize:24, fontWeight:800, color:"#111827", letterSpacing:"-0.02em" }}>
            Rapport d'anomalies — Pipeline d'extraction
          </h1>
          <p style={{ margin:0, fontSize:13, color:"#6B7280", maxWidth:640, lineHeight:1.6 }}>
            Traçabilité complète de chaque indicateur depuis le scraping PDF jusqu'au KPI final.
            Anomalies regroupées par compagnie, triées par sévérité décroissante.
          </p>
        </div>
      </div>

      <div style={{ maxWidth:1200, margin:"0 auto", padding:"24px 32px" }}>
        {/* Sélecteur année */}
        <div style={{ display:"flex", alignItems:"center", gap:6, marginBottom:20, background:"#fff", border:"1px solid #E5E7EB", borderRadius:8, padding:"10px 14px", flexWrap:"wrap" }}>
          <span style={{ fontSize:11, fontWeight:700, color:"#6B7280", marginRight:4 }}>Année</span>
          {annees.map(a => (
            <button key={a} onClick={() => setAnnee(a)} style={{
              padding:"4px 11px", borderRadius:6, fontSize:13, cursor:"pointer",
              border: a===annee ? "1.5px solid #111827" : "1px solid #E5E7EB",
              background: a===annee ? "#111827" : "#fff",
              color: a===annee ? "#fff" : "#374151",
              fontWeight: a===annee ? 700 : 400,
            }}>{a}</button>
          ))}
        </div>

        {loading && (
          <div style={{ textAlign:"center", padding:80, color:"#9CA3AF" }}>
            <div style={{ width:36, height:36, border:"3px solid #E5E7EB", borderTopColor:"#111827", borderRadius:"50%", animation:"spin 0.7s linear infinite", margin:"0 auto 14px" }} />
            <div style={{ fontSize:13, fontWeight:600 }}>Analyse du pipeline…</div>
          </div>
        )}

        {error && (
          <div style={{ background:"#FEF2F2", border:"1px solid #FCA5A5", borderRadius:8, padding:"16px 20px", color:"#991B1B", fontSize:13 }}>
            <strong>Erreur de chargement :</strong> {error}
            <div style={{ marginTop:6, fontSize:12, color:"#9A3412" }}>Vérifiez que le backend Flask tourne sur le port 8002 : <code>python api/app.py</code></div>
          </div>
        )}

        {data && !loading && (
          <>
            {/* Stats */}
            <div style={{ display:"flex", gap:12, flexWrap:"wrap", marginBottom:16 }}>
              <StatCard label="Anomalies détectées" value={data.n_problemes} dot="#111827" />
              <StatCard label="Compagnies affectées" value={data.n_compagnies_affectees} dot="#374151" sub={`sur ${data.compagnies_affectees?.length || "—"}`} />
              <StatCard label="Critiques" value={grav.critique || 0} dot="#DC2626" sub="PDF manquant" />
              <StatCard label="Erreurs" value={grav.erreur || 0} dot="#EA580C" sub="Extraction / section" />
              <StatCard label="Avertissements" value={grav.avertissement || 0} dot="#CA8A04" sub="Valeurs aberrantes" />
              <StatCard label="Infos" value={grav.info || 0} dot="#2563EB" sub="Recalculs partiels" />
            </div>

            {/* Pipeline bar */}
            <div style={{ background:"#fff", border:"1px solid #E5E7EB", borderRadius:10, padding:"16px 18px", marginBottom:16 }}>
              <div style={{ fontSize:12, fontWeight:700, color:"#111827", marginBottom:10 }}>Répartition par étape du pipeline</div>
              <PipelineBar par_etape={data.par_etape || {}} />
            </div>

            {/* Méthodologie */}
            <Methodo open={methodoOpen} onToggle={() => setMethodoOpen(o => !o)} />

            {/* Filtres */}
            <div style={{ background:"#fff", border:"1px solid #E5E7EB", borderRadius:10, padding:"10px 14px", marginBottom:12, display:"flex", gap:8, flexWrap:"wrap", alignItems:"center" }}>
              <input placeholder="Rechercher (compagnie, KPI, cause…)" value={searchQ} onChange={e => setSearchQ(e.target.value)}
                style={{ ...sel, minWidth:220, outline:"none" }} />
              <select value={filtreGrav} onChange={e => setFiltreGrav(e.target.value)} style={sel}>
                {["Toutes", "critique", "erreur", "avertissement", "info"].map(g => (
                  <option key={g} value={g}>{g === "Toutes" ? "Toutes gravités" : GRAVITE[g]?.label}</option>
                ))}
              </select>
              <select value={filtreEtape} onChange={e => setFiltreEtape(e.target.value)} style={sel}>
                <option value="Toutes">Toutes étapes</option>
                {ETAPES.map(e => <option key={e.num} value={e.label}>{e.num}. {e.label}</option>)}
              </select>
              <button onClick={() => { setFiltreGrav("Toutes"); setFiltreEtape("Toutes"); setSearchQ(""); }}
                style={{ ...sel, color:"#6B7280" }}>Réinitialiser</button>
              <span style={{ fontSize:12, color:"#9CA3AF", marginLeft:"auto", fontWeight:600 }}>
                {totalFiltered} anomalie{totalFiltered>1?"s":""} · {companyGroups.length} compagnie{companyGroups.length>1?"s":""}
              </span>
            </div>

            {/* Liste groupée par compagnie */}
            {companyGroups.length === 0 ? (
              <div style={{ textAlign:"center", color:"#9CA3AF", padding:60, background:"#fff", border:"1px solid #E5E7EB", borderRadius:10, fontSize:13 }}>
                Aucune anomalie ne correspond aux filtres.
              </div>
            ) : (
              <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
                {companyGroups.map(([code, ps]) => (
                  <CompanyCard key={code} code={code} problemes={ps} annee={annee} navigate={navigate} />
                ))}
              </div>
            )}
          </>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
