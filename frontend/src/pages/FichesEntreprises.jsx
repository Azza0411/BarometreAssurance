import { useState, useEffect, useRef } from "react";
import ReactApexChart from "react-apexcharts";
import TunisiaMap from "../components/TunisiaMap";
import { getLogoSrc } from "../utils/logos";
import PageHeaderBar, { DarkKpiBanner } from "../components/PageHeaderBar";

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
/* TAB 2 — PERFORMANCE FINANCIÈRE                                */
/* ══════════════════════════════════════════════════════════════ */
const BILAN_COLORS = [D, "#44445A", "#747480", "#9898B0", "#B8B8CC", "#D4D4DE", "#E8E8EE"];

function DonutSection({ title, items, total, totalLabel, colors }) {
  const vals = items.map(it => Math.max(0, it.value ?? 0));
  const sum  = vals.reduce((a, b) => a + b, 0) || 1;
  /* Formatte le total en abrégeant les grands nombres pour éviter le débordement */
  const fmtTotal = (v) => {
    if (v == null) return "N/D";
    if (v >= 1000) return `${(v / 1000).toFixed(1)}B`;
    return `${v.toFixed(0)} M`;
  };
  const opts = {
    chart:   { type: "donut", animations: { enabled: false }, background: "transparent" },
    labels:  items.map(it => it.label),
    colors:  colors || BILAN_COLORS.slice(0, items.length),
    legend:  { show: false },
    dataLabels: { enabled: false },
    plotOptions: { pie: { donut: { size: "62%", labels: {
      show: true,
      value: { fontSize: "11px", fontWeight: 800, color: D, offsetY: -2,
               formatter: () => fmtTotal(total) },
      total: { show: true, label: totalLabel || "Total", fontSize: "8px", fontWeight: 700, color: G,
               formatter: () => fmtTotal(total) },
    }}}},
    tooltip: { y: { formatter: v => `${v.toFixed(1)} M TND` } },
    stroke:  { width: 1.5, colors: ["#FFFFFF"] },
  };
  return (
    <div style={{ background: "white", borderRadius: 12, border: "1px solid #EBEBEB", padding: "14px 16px", display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 9, fontWeight: 800, textTransform: "uppercase", letterSpacing: "1.5px", color: D }}>{title}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div style={{ flexShrink: 0 }}>
          <ReactApexChart options={opts} series={vals} type="donut" width={130} height={130} />
        </div>
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
          {items.map((it, i) => {
            const pct = sum > 0 ? ((it.value ?? 0) / sum * 100).toFixed(1) : "0";
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{ width: 7, height: 7, borderRadius: 2, flexShrink: 0, background: (colors || BILAN_COLORS)[i] }} />
                <span style={{ fontSize: 8.5, color: D, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.label}</span>
                <span style={{ fontSize: 8.5, fontWeight: 700, color: D, flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>{it.value != null ? it.value.toFixed(1) : "—"}</span>
                <span style={{ fontSize: 7.5, color: G, flexShrink: 0, width: 32, textAlign: "right" }}>{pct}%</span>
              </div>
            );
          })}
          <div style={{ borderTop: "1px solid #F0F0F0", paddingTop: 4, display: "flex", justifyContent: "space-between", marginTop: 2 }}>
            <span style={{ fontSize: 8.5, fontWeight: 800, color: D }}>{totalLabel || "Total"}</span>
            <span style={{ fontSize: 8.5, fontWeight: 800, color: D }}>{total != null ? `${total.toFixed(1)} M` : "N/D"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function PerformanceFinanciere({ code, profil, evolution, bilan }) {

  if (!evolution || Object.keys(evolution).length === 0) {
    return <div style={{ color: G, padding: 40, textAlign: "center" }}>Données non disponibles pour {LABEL[code] || code}</div>;
  }

  const years = Object.keys(evolution).map(Number).sort();
  const get   = (field) => years.map(y => evolution[y]?.[field] ?? null);

  /* KPIs du dessus — depuis profil (dernière année) */
  const lastYear = [...years].reverse().find(y => evolution[y]?.resultat_net != null) ?? years[years.length - 1];
  const prevYear = [...years].filter(y => y < lastYear).reverse().find(y => evolution[y]?.resultat_net != null);
  function delta(field) {
    const cur = evolution[lastYear]?.[field];
    const prv = prevYear ? evolution[prevYear]?.[field] : null;
    if (cur == null || prv == null || prv === 0) return null;
    return { val: (((cur - prv) / Math.abs(prv)) * 100).toFixed(1), up: cur >= prv };
  }

  /* Chart 1 — Primes & Résultat (barres M TND) */
  const chartPrimesOpts = {
    chart: { type: "bar", toolbar: { show: false }, animations: { enabled: false }, background: "transparent" },
    plotOptions: { bar: { columnWidth: "55%", borderRadius: 3, grouped: true } },
    colors: [D, Y],
    legend: { position: "top", fontSize: "9px", fontFamily: "Barlow,system-ui,sans-serif",
              markers: { width: 10, height: 6, radius: 2 } },
    xaxis:  { categories: years, labels: { style: { fontSize: "9px", colors: G } }, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis:  { title: { text: "M TND", style: { fontSize: "8px", color: G } },
              labels: { style: { fontSize: "9px", colors: G }, formatter: v => v?.toFixed(0) } },
    tooltip: { shared: true, intersect: false, y: { formatter: v => `${v?.toFixed(1)} M TND` } },
    grid:   { borderColor: "#F0F0F0", strokeDashArray: 3 },
    dataLabels: { enabled: false },
  };
  const chartPrimesSeries = [
    { name: "Primes émises",          data: get("primes_emises") },
    { name: "Résultat de l'exercice", data: get("resultat_net")  },
  ];

  /* Chart 2 — Ratios de performance (lignes %) */
  const chartRatiosOpts = {
    chart: { type: "line", toolbar: { show: false }, animations: { enabled: false }, background: "transparent" },
    stroke: { width: [2.5, 2.5, 2], curve: "smooth", dashArray: [0, 0, 4] },
    colors: [D, Y, G],
    markers: { size: 3 },
    legend: { position: "top", fontSize: "9px", fontFamily: "Barlow,system-ui,sans-serif",
              markers: { width: 10, height: 6, radius: 2 } },
    xaxis:  { categories: years, labels: { style: { fontSize: "9px", colors: G } }, axisBorder: { show: false }, axisTicks: { show: false } },
    yaxis:  { title: { text: "%", style: { fontSize: "8px", color: G } },
              labels: { style: { fontSize: "9px", colors: G }, formatter: v => `${v?.toFixed(1)}%` } },
    tooltip: { shared: true, intersect: false, y: { formatter: v => `${v?.toFixed(2)}%` } },
    grid:   { borderColor: "#F0F0F0", strokeDashArray: 3 },
    dataLabels: { enabled: false },
  };
  const chartRatiosSeries = [
    { name: "ROE (%)",          data: get("roe")           },
    { name: "ROA (%)",          data: get("roa")           },
    { name: "Ratio combiné (%)", data: get("ratio_combine") },
  ];

  function KpiTop({ label, value, unit, d }) {
    return (
      <div style={{ background: "white", borderRadius: 10, border: "1px solid #EBEBEB",
        padding: "12px 16px", display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{ fontSize: 8, fontWeight: 700, color: G, textTransform: "uppercase", letterSpacing: "2px" }}>{label}</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span style={{ fontSize: 24, fontWeight: 900, color: value != null ? D : "#C0C0C8", lineHeight: 1 }}>
            {value != null ? value : "N/D"}
          </span>
          {unit && value != null && <span style={{ fontSize: 10, color: G }}>{unit}</span>}
        </div>
        {d && (
          <div style={{ fontSize: 9, fontWeight: 800, color: d.up ? "#15803D" : "#DC2626" }}>
            {d.up ? "↑" : "↓"} {Math.abs(d.val)}%
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>

      {/* KPIs haut — dark banner */}
      {(()=>{
        /* Valeurs calculées en fallback si absentes */
        const roaVal = evolution[lastYear]?.roa != null
          ? evolution[lastYear].roa
          : (evolution[lastYear]?.resultat_net != null && evolution[lastYear]?.total_actif > 0)
            ? parseFloat(((evolution[lastYear].resultat_net / evolution[lastYear].total_actif) * 100).toFixed(2))
            : null;

        /* ROE = résultat_net / capitaux_propres (depuis bilan.passif si dispo) */
        const cpItem = bilan?.passif?.find(p => p.label?.toLowerCase().includes("capitaux propres"));
        const roeVal = evolution[lastYear]?.roe != null
          ? evolution[lastYear].roe
          : (evolution[lastYear]?.resultat_net != null && cpItem?.value > 0)
            ? parseFloat(((evolution[lastYear].resultat_net / cpItem.value) * 100).toFixed(2))
            : null;

        const mkItem = (label, rawVal, sub) => {
          const val = rawVal;
          const prevVal = prevYear
            ? (label === "ROA"
                ? (evolution[prevYear]?.roa ?? (evolution[prevYear]?.resultat_net != null && evolution[prevYear]?.total_actif > 0
                    ? (evolution[prevYear].resultat_net / evolution[prevYear].total_actif) * 100 : null))
                : label === "ROE"
                  ? (evolution[prevYear]?.roe ?? null)
                  : evolution[prevYear]?.[label === "Résultat de l'exercice" ? "resultat_net" : ""])
            : null;
          const dVal = (val != null && prevVal != null && prevVal !== 0)
            ? { val: (((val - prevVal) / Math.abs(prevVal)) * 100).toFixed(1), up: val >= prevVal }
            : null;
          return {
            label,
            value: val != null ? fmt(val, label === "Résultat de l'exercice" ? 1 : 2) : "N/D",
            sub,
            delta: dVal ? (dVal.up ? `+${dVal.val}` : `-${Math.abs(dVal.val)}`) : undefined,
            pos: dVal ? dVal.up : undefined,
          };
        };
        const rnVal = evolution[lastYear]?.resultat_net ?? null;
        return <DarkKpiBanner items={[
          mkItem("Résultat de l'exercice", rnVal, "M TND"),
          mkItem("ROA", roaVal, "%"),
          mkItem("ROE", roeVal, "%"),
        ]}/>;
      })()}

      {/* Structure bilan + évolution */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>

        {/* Colonne gauche : donuts bilan */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {bilan?.actif?.length > 0 && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <DonutSection title={`Structure Actif ${bilan.annee || ""}`}
                items={bilan.actif} total={bilan.total_actif} totalLabel="Total Actif" />
              <DonutSection title={`Structure Passif ${bilan.annee || ""}`}
                items={bilan.passif} total={bilan.total_passif} totalLabel="Total Passif"
                colors={["#2E2E38","#5A5A74","#747480","#9898B0","#B8B8CC","#D4D4DE"]} />
            </div>
          )}
          {bilan?.placements?.length > 0 && (
            <DonutSection title={`Composition des placements ${bilan.annee || ""}`}
              items={bilan.placements} total={bilan.total_placements} totalLabel="Total Placements"
              colors={[Y, "#E6B800", "#D4D4DE", "#9898B0"]} />
          )}
          {!bilan && (
            <div style={{ background: "white", borderRadius: 12, border: "1px solid #EBEBEB", padding: 24, textAlign: "center", color: G, fontSize: 12 }}>
              Chargement structure du bilan…
            </div>
          )}
          {bilan && bilan.actif?.length === 0 && (
            <div style={{ background: "white", borderRadius: 12, border: "1px solid #EBEBEB", padding: 24, textAlign: "center", color: G, fontSize: 12 }}>
              Structure du bilan non disponible pour {LABEL[code] || code}
            </div>
          )}
        </div>

        {/* Colonne droite : 2 graphiques clairs */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ background: "white", borderRadius: 12, border: "1px solid #EBEBEB", padding: "12px 14px 6px" }}>
            <div style={{ fontSize: 9, fontWeight: 800, textTransform: "uppercase", letterSpacing: "1.5px", color: D, marginBottom: 2 }}>
              Évolution primes &amp; résultat (M TND)
            </div>
            <ReactApexChart options={chartPrimesOpts} series={chartPrimesSeries} type="bar" height={130} />
          </div>
          <div style={{ background: "white", borderRadius: 12, border: "1px solid #EBEBEB", padding: "12px 14px 6px" }}>
            <div style={{ fontSize: 9, fontWeight: 800, textTransform: "uppercase", letterSpacing: "1.5px", color: D, marginBottom: 2 }}>
              Évolution des ratios de performance (%)
            </div>
            <ReactApexChart options={chartRatiosOpts} series={chartRatiosSeries} type="line" height={130} />
          </div>
        </div>
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
  const [bilan,      setBilan]      = useState(null);
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

  // Charger le bilan (partagé entre ProfilAssurance et PerformanceFinanciere)
  useEffect(() => {
    if (!code) return;
    setBilan(null);
    fetch(`${API}/api/vue-assurance/bilan?code=${code}`)
      .then(r => r.json()).then(setBilan).catch(() => {});
  }, [code]);

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"#EEEEF4", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>

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
        <PerformanceFinanciere code={code} profil={profil} evolution={evolution} bilan={bilan} />
      )}

      <div style={{ textAlign:"right", fontSize:10, color:G }}>
        Source : CMF · CGA · Données extraites
      </div>
      </div>{/* fin corps scrollable */}
    </div>
  );
}
