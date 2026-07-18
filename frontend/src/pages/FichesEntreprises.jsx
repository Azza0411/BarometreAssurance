import { useState, useEffect, useRef } from "react";
import ReactApexChart from "react-apexcharts";
import TunisiaMap from "../components/TunisiaMap";
import { getLogoSrc } from "../utils/logos";
import PageHeaderBar from "../components/PageHeaderBar";

const Y  = "#FFE600";
const D  = "#2E2E38";
const G  = "#747480";
const API = "http://localhost:8002";

/* ── Labels d'affichage ── */
const LABEL = {
  AL_AMANAH_TAKAFUL: "El Amana Takaful", AMI: "AMI", ASTREE: "Astrée",
  ATTIJARI: "Attijari Assurances", AT_TAKAFULIA: "At-Takafulia", BH: "BH Assurance",
  BIAT: "BIAT Assurances", BNA: "BNA Assurances", CARTE: "La Carte",
  CARTE_VIE: "La Carte Vie", COMAR: "COMAR", COTUNACE: "COTUNACE",
  CTAMA: "CTAMA", GAT: "GAT", GAT_VIE: "GAT Vie", HAYETT: "Hayett",
  LLOYD_TUNISIEN: "Lloyd Tunisien", LLOYD_VIE: "Lloyd Vie",
  MAGHREBIA: "Maghrebia", MAGHREBIA_VIE: "Maghrebia Vie", STAR: "STAR",
  TUNIS_RE: "Tunis Re", UIB: "UIB Assurances", ZITOUNA_TAKAFUL: "Zitouna Takaful",
};

/* ── Utilitaires ── */
function fmt(v, decimals = 1) {
  if (v === null || v === undefined) return "N/D";
  return typeof v === "number" ? v.toFixed(decimals) : v;
}
function fmtM(v) { return v != null ? `${fmt(v)} M` : "N/D"; }
function fmtPct(v) { return v != null ? `${fmt(v)} %` : "N/D"; }

/* ── Mini composants ── */
function ChevronDown({ color = D, size = 12 }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" width={size} height={size} style={{ flexShrink: 0 }}>
      <path d="M2.5 4.5L6 8l3.5-3.5" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function AvatarPlaceholder({ size = 52 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 56 56" fill="none">
      <circle cx="28" cy="28" r="28" fill="#F0F0F4" />
      <circle cx="28" cy="22" r="10" fill="#C8C8D0" />
      <path d="M6 50c0-12.15 9.85-22 22-22s22 9.85 22 22" fill="#C8C8D0" />
    </svg>
  );
}

function SectionHead({ label }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12 }}>
      <div style={{ width: 8, height: 8, borderRadius: "50%", background: Y, border: `1.5px solid #E6B800`, flexShrink: 0 }} />
      <span style={{ fontSize: 10, fontWeight: 800, textTransform: "uppercase", letterSpacing: "1.5px", color: D }}>{label}</span>
    </div>
  );
}

function KpiBox({ label, value, unit = "", delta = null, deltaUp = null }) {
  return (
    <div style={{ background: "#FAFAFA", borderRadius: 9, border: "1px solid #F0F0F0", padding: "9px 10px" }}>
      <div style={{ fontSize: 8, fontWeight: 800, color: G, textTransform: "uppercase", letterSpacing: "0.7px", marginBottom: 4, lineHeight: 1.3 }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 900, color: value === "N/D" ? "#C0C0C8" : D, lineHeight: 1 }}>{value}</div>
      {unit && <div style={{ fontSize: 8, color: G, marginTop: 1 }}>{unit}</div>}
      {delta != null && (
        <div style={{ fontSize: 9, color: deltaUp ? "#15803D" : "#DC2626", fontWeight: 700, marginTop: 3 }}>
          {deltaUp ? "↗" : "↘"} {delta}
        </div>
      )}
    </div>
  );
}

/* ── Dropdown compagnie ── */
function CompanyDropdown({ companies, selected, onSelect }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    function handler(e) { if (ref.current && !ref.current.contains(e.target)) setOpen(false); }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const logo = getLogoSrc(selected);
  return (
    <div ref={ref} style={{ position: "relative" }}>
      <button onClick={() => setOpen(!open)} style={{
        display: "flex", alignItems: "center", gap: 8,
        background: Y, border: "none", cursor: "pointer",
        padding: "8px 14px", borderRadius: 10, fontSize: 12, fontWeight: 800,
        boxShadow: "0 2px 8px rgba(255,230,0,0.4)", color: D, minWidth: 160,
      }}>
        {logo && <img src={logo} alt={selected} style={{ height: 22, maxWidth: 52, objectFit: "contain" }} />}
        <span style={{ flex: 1, textAlign: "left" }}>{LABEL[selected] || selected}</span>
        <ChevronDown color={D} size={13} />
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", left: 0, zIndex: 200,
          background: "white", borderRadius: 12, border: "1px solid #E5E7EB",
          boxShadow: "0 8px 24px rgba(0,0,0,0.12)", minWidth: 220, maxHeight: 320,
          overflowY: "auto",
        }}>
          {companies.map(c => {
            const lg = getLogoSrc(c);
            return (
              <button key={c} onClick={() => { onSelect(c); setOpen(false); }} style={{
                display: "flex", alignItems: "center", gap: 10, width: "100%",
                padding: "9px 14px", border: "none", background: c === selected ? "#FFFBE6" : "transparent",
                cursor: "pointer", textAlign: "left", fontSize: 12, fontWeight: c === selected ? 700 : 500, color: D,
              }}>
                {lg ? <img src={lg} alt={c} style={{ height: 20, width: 44, objectFit: "contain" }} /> : <div style={{ width: 44 }} />}
                {LABEL[c] || c}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════ */
/* TAB 1 — PROFIL DE L'ASSURANCE                                 */
/* ══════════════════════════════════════════════════════════════ */
function ProfilAssurance({ code, annee, profil }) {
  if (!profil) return <div style={{ color: G, padding: 40, textAlign: "center" }}>Chargement…</div>;

  const logo = getLogoSrc(code);
  const totalAg = profil.total_agences;
  const agReg = profil.agences_region || {};

  // Construire les données pour TunisiaMap
  const mapData = {};
  const regionKey = {
    "Grand Tunis":   "grand-tunis",
    "Nord Est":      "nord",
    "Centre Est":    "centre-est",
    "Centre Ouest":  "centre-ouest",
    "Sud Est":       "sfax",
    "Sud Ouest":     "sud",
  };
  const totalForPct = totalAg || Object.values(agReg).reduce((a, b) => a + b, 0) || 1;
  for (const [reg, count] of Object.entries(agReg)) {
    const key = regionKey[reg];
    if (!key) continue;
    const pct = ((count / totalForPct) * 100).toFixed(1);
    const level = pct > 30 ? "forte" : pct > 15 ? "haute" : pct > 8 ? "moyenne" : "faible";
    mapData[key] = { level, value: `${count} agences · ${pct}%` };
  }

  const isCoted = profil.cours_action != null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

      {/* Bandeau identité */}
      <div style={{
        background: "white", borderRadius: 14, border: "1px solid #EBEBEB",
        boxShadow: "0 2px 10px rgba(0,0,0,0.05)",
        display: "flex", alignItems: "stretch", overflow: "hidden", minHeight: 110,
      }}>
        {/* Logo */}
        <div style={{
          width: 130, flexShrink: 0,
          background: "linear-gradient(160deg,#FFF9CC 0%,#FFE600 100%)",
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center", gap: 4, padding: "12px",
        }}>
          {logo
            ? <img src={logo} alt={code} style={{ height: 52, width: "auto", maxWidth: 110, objectFit: "contain" }} />
            : <div style={{ fontSize: 16, fontWeight: 900, color: D }}>{code}</div>
          }
          <div style={{ fontSize: 7.5, fontWeight: 800, color: "rgba(46,46,56,0.45)", letterSpacing: "1.2px", textAlign: "center", textTransform: "uppercase" }}>
            ASSURANCES · تأمينات
          </div>
        </div>

        {/* Siège social */}
        <div style={{ padding: "0 20px", borderLeft: "1px solid #F0F0F0", display: "flex", alignItems: "center", gap: 24, flexShrink: 0 }}>
          <div>
            <div style={{ fontSize: 8.5, fontWeight: 800, color: G, textTransform: "uppercase", letterSpacing: "1px", marginBottom: 3 }}>Siège social</div>
            <div style={{ fontSize: 12, fontWeight: 800, color: D, lineHeight: 1.4, maxWidth: 220 }}>{profil.siege_social || "N/D"}</div>
          </div>
        </div>

        {/* Part de marché */}
        <div style={{ borderLeft: "1px solid #F0F0F0", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: "0 24px", gap: 12 }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 8.5, fontWeight: 800, color: G, textTransform: "uppercase", letterSpacing: "1px", marginBottom: 3 }}>Part de marché</div>
            <div style={{ fontSize: 26, fontWeight: 900, color: D, lineHeight: 1 }}>{fmtPct(profil.pdm)}</div>
            <div style={{ fontSize: 9, fontWeight: 600, color: G, marginTop: 2 }}>du marché {annee}</div>
          </div>
        </div>

        {/* Cotation / capitalisation OU capitaux propres + réseau */}
        <div style={{ borderLeft: "1px solid #F0F0F0", flexShrink: 0, display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "0 24px", gap: 8, flex: 1 }}>
          {isCoted ? (
            <>
              <div style={{ display: "inline-flex", alignItems: "center", gap: 5, background: "#F0FDF4", color: "#15803D", fontSize: 10, fontWeight: 800, padding: "3px 12px", borderRadius: 20, border: "1px solid #BBF7D0" }}>
                <span style={{ fontSize: 8 }}>●</span> Cotée en Bourse
              </div>
              <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
                {profil.cours_action != null && (
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 8.5, fontWeight: 800, color: G, textTransform: "uppercase", letterSpacing: "1px", marginBottom: 3 }}>Cours action</div>
                    <div style={{ fontSize: 18, fontWeight: 900, color: D, lineHeight: 1 }}>{fmt(profil.cours_action)}</div>
                    <div style={{ fontSize: 9, fontWeight: 600, color: G, marginTop: 1 }}>TND</div>
                  </div>
                )}
                {profil.capitalisation != null && profil.cours_action != null && (
                  <div style={{ width: 1, height: 44, background: "#F0F0F0", alignSelf: "center" }} />
                )}
                {profil.capitalisation != null && (
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 8.5, fontWeight: 800, color: G, textTransform: "uppercase", letterSpacing: "1px", marginBottom: 3 }}>Capitalisation</div>
                    <div style={{ fontSize: 18, fontWeight: 900, color: D, lineHeight: 1 }}>{fmt(profil.capitalisation, 0)}</div>
                    <div style={{ fontSize: 9, fontWeight: 600, color: G, marginTop: 1 }}>M TND</div>
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
              {profil.capitaux_propres != null && (
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 8.5, fontWeight: 800, color: G, textTransform: "uppercase", letterSpacing: "1px", marginBottom: 3 }}>Capitaux propres</div>
                  <div style={{ fontSize: 18, fontWeight: 900, color: D, lineHeight: 1 }}>{fmt(profil.capitaux_propres, 1)}</div>
                  <div style={{ fontSize: 9, fontWeight: 600, color: G, marginTop: 1 }}>M TND</div>
                </div>
              )}
              {profil.capitaux_propres != null && totalAg != null && (
                <div style={{ width: 1, height: 44, background: "#F0F0F0", alignSelf: "center" }} />
              )}
              {totalAg != null && (
                <div style={{ textAlign: "center" }}>
                  <div style={{ fontSize: 8.5, fontWeight: 800, color: G, textTransform: "uppercase", letterSpacing: "1px", marginBottom: 3 }}>Réseau d'agences</div>
                  <div style={{ fontSize: 18, fontWeight: 900, color: D, lineHeight: 1 }}>{totalAg}</div>
                  <div style={{ fontSize: 9, fontWeight: 600, color: G, marginTop: 1 }}>agences ({profil.annee_cga})</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Corps 2 colonnes */}
      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 16, alignItems: "start" }}>

        {/* Carte réseau */}
        <div style={{ background: "white", borderRadius: 14, border: "1px solid #EBEBEB", boxShadow: "0 2px 10px rgba(0,0,0,0.05)", padding: "14px" }}>
          <SectionHead label={`Réseau d'agences ${profil.annee_cga || annee}${totalAg ? ` — ${totalAg} au total` : ""}`} />
          {Object.keys(mapData).length > 0
            ? <TunisiaMap data={mapData} />
            : <div style={{ width: 200, height: 200, display: "flex", alignItems: "center", justifyContent: "center", color: G, fontSize: 12 }}>Données non disponibles</div>
          }
        </div>

        {/* Col droite */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

          {/* Indicateurs financiers */}
          <div style={{ background: "white", borderRadius: 14, border: "1px solid #EBEBEB", boxShadow: "0 2px 10px rgba(0,0,0,0.05)", padding: "14px" }}>
            <SectionHead label={`Indicateurs financiers ${annee}`} />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
              <KpiBox label="PRIMES ÉMISES"      value={fmtM(profil.primes_emises)}      unit="TND (M)" />
              <KpiBox label="RÉSULTAT NET"        value={fmtM(profil.resultat_net)}        unit="TND (M)" />
              <KpiBox label="TOTAL ACTIF"         value={fmtM(profil.total_actif)}         unit="TND (M)" />
              <KpiBox label="RATIO COMBINÉ"       value={fmtPct(profil.ratio_combine)}                   />
              <KpiBox label="RATIO SINISTRALITÉ"  value={fmtPct(profil.ratio_sp)}                        />
              <KpiBox label="RATIO DE FRAIS"      value={fmtPct(profil.ratio_frais)}                     />
            </div>
          </div>

          {/* ROA / ROE / Résultat technique */}
          <div style={{ background: "white", borderRadius: 14, border: "1px solid #EBEBEB", boxShadow: "0 2px 10px rgba(0,0,0,0.05)", padding: "14px" }}>
            <SectionHead label="Rentabilité" />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
              <KpiBox label="ROA"                  value={fmtPct(profil.roa)}                              />
              <KpiBox label="ROE"                  value={fmtPct(profil.roe)}                              />
              <KpiBox label="RÉSULTAT TECHNIQUE"   value={fmtM(profil.resultat_technique)}  unit="TND (M)" />
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════ */
/* TAB 2 — PERFORMANCE FINANCIÈRE (sparklines sur 10 ans)        */
/* ══════════════════════════════════════════════════════════════ */
function PerformanceFinanciere({ code, evolution }) {
  if (!evolution || Object.keys(evolution).length === 0) {
    return <div style={{ color: G, padding: 40, textAlign: "center" }}>Données d'évolution non disponibles pour {LABEL[code] || code}</div>;
  }

  const years = Object.keys(evolution).map(Number).sort();
  const get = (field) => years.map(y => evolution[y]?.[field] ?? null);

  const indicators = [
    { label: "Primes émises",      field: "primes_emises",   unit: "M TND", color: D,         accentBg: "#F3F3F6"  },
    { label: "Résultat net",       field: "resultat_net",    unit: "M TND", color: "#E6A800",  accentBg: "#FFFBE6"  },
    { label: "ROE",                field: "roe",             unit: "%",     color: "#1A7A4A",  accentBg: "#F0FAF4"  },
    { label: "ROA",                field: "roa",             unit: "%",     color: "#1A6BB5",  accentBg: "#EFF6FF"  },
    { label: "Part de marché",     field: "pdm",             unit: "%",     color: "#C8102E",  accentBg: "#FFF0F3"  },
    { label: "Ratio combiné",      field: "ratio_combine",   unit: "%",     color: "#7C3AED",  accentBg: "#F5F3FF"  },
  ];

  function SparkCard({ ind }) {
    const data = get(ind.field);
    const clean = data.filter(v => v != null);
    if (clean.length === 0) return (
      <div style={{ background: "white", borderRadius: 16, border: "1px solid #EBEBEB", padding: 14, boxShadow: "0 2px 12px rgba(0,0,0,0.05)" }}>
        <div style={{ fontSize: 9, fontWeight: 800, textTransform: "uppercase", letterSpacing: "1.4px", color: G, marginBottom: 4 }}>{ind.label}</div>
        <div style={{ fontSize: 18, color: "#C0C0C8", fontWeight: 700 }}>N/D</div>
      </div>
    );

    const curr = [...data].reverse().find(v => v != null) ?? null;
    const prev = [...data].reverse().find((v, i) => i > 0 && v != null) ?? null;
    const delta = (prev != null && curr != null) ? (((curr - prev) / Math.abs(prev)) * 100).toFixed(1) : null;
    const up = delta != null && parseFloat(delta) >= 0;

    // ApexCharts ne supporte pas null dans sparkline — convertir en undefined
    const safeData = data.map(v => (v === null || v === undefined ? undefined : v));

    const sparkOpts = {
      chart: { type: "area", sparkline: { enabled: true }, animations: { enabled: false } },
      colors: [ind.color],
      stroke: { curve: "smooth", width: 2.5 },
      fill: { type: "gradient", gradient: { shade: "light", type: "vertical", opacityFrom: 0.35, opacityTo: 0.02 } },
      yaxis: { min: undefined },
      tooltip: {
        fixed: { enabled: false },
        x: { show: true, formatter: (_, opts) => years[opts?.dataPointIndex] ?? "" },
        y: { formatter: v => v != null ? `${v} ${ind.unit}` : "N/D" },
        theme: "light",
      },
    };

    return (
      <div style={{ background: "white", borderRadius: 16, border: "1px solid #EBEBEB", boxShadow: "0 2px 12px rgba(0,0,0,0.05)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div style={{ background: ind.accentBg, padding: "14px 16px 10px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 9, fontWeight: 800, textTransform: "uppercase", letterSpacing: "1.4px", color: G, marginBottom: 4 }}>{ind.label}</div>
              <div style={{ fontSize: 24, fontWeight: 900, color: D, lineHeight: 1, letterSpacing: "-0.5px" }}>
                {curr != null ? `${curr} ${ind.unit}` : "N/D"}
              </div>
            </div>
            {delta != null && (
              <div style={{ display: "inline-flex", alignItems: "center", gap: 3, background: up ? "#DCFCE7" : "#FEE2E2", color: up ? "#15803D" : "#DC2626", fontSize: 10, fontWeight: 800, padding: "3px 8px", borderRadius: 20, marginTop: 2, flexShrink: 0 }}>
                {up ? "↗" : "↘"} {Math.abs(delta)}%
              </div>
            )}
          </div>
          {/* Valeurs par année */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
            {years.map((y, i) => (
              <div key={y} style={{ flex: 1, textAlign: "center", minWidth: 30 }}>
                <div style={{ fontSize: 11, fontWeight: i === years.length - 1 ? 900 : 500, color: i === years.length - 1 ? ind.color : G, lineHeight: 1 }}>
                  {data[i] != null ? data[i] : "–"}
                </div>
                <div style={{ fontSize: 8, color: "rgba(116,116,128,0.6)", marginTop: 2 }}>{y}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ marginTop: -2 }}>
          <ReactApexChart options={sparkOpts} series={[{ data: safeData }]} type="area" height={70} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
        {indicators.map(ind => <SparkCard key={ind.field} ind={ind} />)}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════ */
/* PAGE PRINCIPALE                                               */
/* ══════════════════════════════════════════════════════════════ */
export default function FichesEntreprises() {
  const [tab,        setTab]        = useState("profil");
  const [companies,  setCompanies]  = useState([]);
  const [code,       setCode]       = useState("STAR");
  const [annee,      setAnnee]      = useState(null);
  const [profil,     setProfil]     = useState(null);
  const [evolution,  setEvolution]  = useState(null);
  const [loading,    setLoading]    = useState(false);

  // Charger la liste des compagnies
  useEffect(() => {
    fetch(`${API}/api/vue-assurance/companies`)
      .then(r => r.json())
      .then(data => { setCompanies(data); if (!data.includes(code)) setCode(data[0] || "STAR"); });
  }, []);

  // Toujours prendre la dernière année disponible pour la compagnie
  useEffect(() => {
    if (!code) return;
    fetch(`${API}/api/vue-assurance/annees?code=${code}`)
      .then(r => r.json())
      .then(data => setAnnee(data[data.length - 1] || null));
  }, [code]);

  // Charger le profil quand compagnie ou année change
  useEffect(() => {
    if (!code || !annee) return;
    setLoading(true);
    setProfil(null);
    fetch(`${API}/api/vue-assurance/profil?code=${code}&annee=${annee}`)
      .then(r => r.json())
      .then(data => { setProfil(data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [code, annee]);

  // Charger l'évolution une fois par compagnie
  useEffect(() => {
    if (!code) return;
    setEvolution(null);
    fetch(`${API}/api/vue-assurance/evolution?code=${code}`)
      .then(r => r.json())
      .then(setEvolution);
  }, [code]);

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"#F9F9FB", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar
        title="Vue par Assurance"
        tabs={[
          { key:"profil", label:"Profil de l'assurance"  },
          { key:"perf",   label:"Performance financière" },
        ]}
        activeTab={tab}
        onTabChange={t => { setTab(t); }}
        right={<CompanyDropdown companies={companies} selected={code} onSelect={c => { setCode(c); setTab("profil"); }} />}
      />

      {/* ── Corps scrollable ── */}
      <div style={{ flex:1, overflowY:"auto", padding:"16px 28px", display:"flex", flexDirection:"column", gap:12 }}>

      {loading && <div style={{ color: G, textAlign: "center", padding: 40 }}>Chargement…</div>}

      {!loading && tab === "profil" && (
        <ProfilAssurance code={code} annee={annee} profil={profil} />
      )}
      {tab === "perf" && (
        <PerformanceFinanciere code={code} evolution={evolution} />
      )}

      <div style={{ textAlign:"right", fontSize:10, color:G }}>
        Source : CMF · CGA · Données extraites
      </div>
      </div>{/* fin corps scrollable */}
    </div>
  );
}
