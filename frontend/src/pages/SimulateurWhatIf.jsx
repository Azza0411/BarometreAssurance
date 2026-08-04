import { useState, useEffect } from "react";
import PageHeaderBar from "../components/PageHeaderBar";
import { getLogoSrc } from "../utils/logos";

const D = "#2E2E38", Y = "#FFE600", G = "#747480", BDR = "#E5E7EB";
const BLUE = "#3A6EA8", ORANGE = "#D4620A";
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

function fmt(v, decimals = 1) {
  if (v === null || v === undefined || isNaN(v)) return "N/D";
  return v.toLocaleString("fr-TN", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

/* ── Slider réutilisable ── */
function SliderRow({ label, value, onChange, min, max, step, unit, resetValue }) {
  const changed = value !== resetValue;
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <span style={{ fontSize: 11.5, fontWeight: 700, color: D }}>{label}</span>
        <span style={{ fontSize: 13, fontWeight: 900, color: changed ? BLUE : G, fontVariantNumeric: "tabular-nums" }}>
          {value > 0 && unit.includes("pt") ? "+" : ""}{fmt(value, step < 1 ? 1 : 0)}{unit}
        </span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        style={{ width: "100%", accentColor: changed ? BLUE : D, cursor: "pointer" }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 9, color: G, marginTop: 2 }}>
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

function ResultCard({ label, baseline, simulated, unit = "", decimals = 1 }) {
  const delta = (baseline != null && simulated != null) ? simulated - baseline : null;
  const up = delta != null && delta >= 0;
  return (
    <div style={{ background: "#fff", border: `1px solid ${BDR}`, borderRadius: 12, padding: "14px 16px" }}>
      <div style={{ fontSize: 9, fontWeight: 800, color: G, textTransform: "uppercase", letterSpacing: "1px", marginBottom: 8 }}>{label}</div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span style={{ fontSize: 22, fontWeight: 900, color: D }}>{fmt(simulated, decimals)}{unit}</span>
        {delta != null && Math.abs(delta) > 0.001 && (
          <span style={{ fontSize: 11, fontWeight: 800, color: up ? "#15803D" : "#DC2626" }}>
            {up ? "↑" : "↓"} {fmt(Math.abs(delta), decimals)}{unit}
          </span>
        )}
      </div>
      <div style={{ fontSize: 10, color: G, marginTop: 4 }}>Référence : {fmt(baseline, decimals)}{unit}</div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════ */
/* MODE COMPAGNIE                                                 */
/* ══════════════════════════════════════════════════════════════ */
function ModeCompagnie() {
  const [companies, setCompanies] = useState([]);
  const [code, setCode] = useState("STAR");
  const [annees, setAnnees] = useState([]);
  const [annee, setAnnee] = useState(null);
  const [profil, setProfil] = useState(null);
  const [totalMarche, setTotalMarche] = useState(null);

  const [dPrimes, setDPrimes] = useState(0);
  const [dRatioSp, setDRatioSp] = useState(0);
  const [dRatioFrais, setDRatioFrais] = useState(0);
  const [dCapitaux, setDCapitaux] = useState(0);
  const [dActif, setDActif] = useState(0);

  useEffect(() => {
    fetch(`${API}/api/vue-assurance/companies`).then(r => r.json()).then(data => {
      setCompanies(data);
      if (!data.includes(code)) setCode(data[0] || "STAR");
    });
  }, []);

  useEffect(() => {
    if (!code) return;
    fetch(`${API}/api/vue-assurance/annees?code=${code}`).then(r => r.json()).then(data => {
      setAnnees(data);
      setAnnee(data[data.length - 1] || null);
    });
  }, [code]);

  useEffect(() => {
    if (!code || !annee) return;
    setProfil(null);
    fetch(`${API}/api/vue-assurance/profil?code=${code}&annee=${annee}`).then(r => r.json()).then(setProfil);
    fetch(`${API}/api/apercu-marche/profil-pays?annee=${annee}`).then(r => r.json())
      .then(d => setTotalMarche(d.total_primes_emises_mdt));
  }, [code, annee]);

  useEffect(() => { setDPrimes(0); setDRatioSp(0); setDRatioFrais(0); setDCapitaux(0); setDActif(0); }, [code, annee]);

  if (!profil) return <div style={{ color: G, textAlign: "center", padding: 60 }}>Chargement…</div>;

  // Référence et simulation utilisent EXACTEMENT la même formule (seule la
  // valeur d'entrée change) : à réglage nul (tous les curseurs à 0), la
  // simulation doit reproduire la référence à l'identique. Utiliser la
  // vraie valeur historique (ex: profil.resultat_net) comme "référence"
  // ici serait trompeur, puisque le résultat simulé provient d'un modèle
  // simplifié qui ne reconstitue jamais exactement le résultat réel — un
  // écart apparaîtrait même sans toucher aux curseurs.
  const primesBase = profil.primes_emises;
  const ratioSpBase = profil.ratio_sp;
  const ratioFraisBase = profil.ratio_frais;
  const capitauxBase = profil.capitaux_propres;
  const actifBase = profil.total_actif;
  const ratioCombineBase = ratioSpBase != null && ratioFraisBase != null ? ratioSpBase + ratioFraisBase : profil.ratio_combine;
  const resultatBase = (primesBase != null && ratioCombineBase != null)
    ? primesBase * (100 - ratioCombineBase) / 100 : null;
  const roeBase = (resultatBase != null && capitauxBase) ? resultatBase / capitauxBase * 100 : null;
  const roaBase = (resultatBase != null && actifBase) ? resultatBase / actifBase * 100 : null;
  const pdmBase = (primesBase != null && totalMarche) ? primesBase / totalMarche * 100 : null;

  const primesSim = primesBase != null ? primesBase * (1 + dPrimes / 100) : null;
  const ratioSpSim = ratioSpBase != null ? ratioSpBase + dRatioSp : null;
  const ratioFraisSim = ratioFraisBase != null ? ratioFraisBase + dRatioFrais : null;
  const ratioCombineSim = ratioSpSim != null && ratioFraisSim != null ? ratioSpSim + ratioFraisSim : null;
  const capitauxSim = capitauxBase != null ? capitauxBase * (1 + dCapitaux / 100) : null;
  const actifSim = actifBase != null ? actifBase * (1 + dActif / 100) : null;
  const resultatSim = (primesSim != null && ratioCombineSim != null)
    ? primesSim * (100 - ratioCombineSim) / 100 : null;
  const roeSim = (resultatSim != null && capitauxSim) ? resultatSim / capitauxSim * 100 : null;
  const roaSim = (resultatSim != null && actifSim) ? resultatSim / actifSim * 100 : null;
  const pdmSim = (primesSim != null && totalMarche) ? primesSim / totalMarche * 100 : null;

  const logo = getLogoSrc(code);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16, flex: 1, minHeight: 0 }}>
      {/* Colonne gauche : sélection + sliders */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, overflowY: "auto" }}>
        <div style={{ background: "#fff", border: `1px solid ${BDR}`, borderRadius: 12, padding: 14 }}>
          <label style={{ fontSize: 9, fontWeight: 800, color: G, textTransform: "uppercase" }}>Compagnie</label>
          <select value={code} onChange={e => setCode(e.target.value)} style={{
            width: "100%", marginTop: 6, padding: "8px 10px", borderRadius: 8, border: `1px solid ${BDR}`,
            fontSize: 13, fontWeight: 700, color: D, fontFamily: "Barlow, system-ui, sans-serif",
          }}>
            {companies.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          <label style={{ fontSize: 9, fontWeight: 800, color: G, textTransform: "uppercase", marginTop: 10, display: "block" }}>Année de référence</label>
          <select value={annee || ""} onChange={e => setAnnee(Number(e.target.value))} style={{
            width: "100%", marginTop: 6, padding: "8px 10px", borderRadius: 8, border: `1px solid ${BDR}`,
            fontSize: 13, fontWeight: 700, color: D, fontFamily: "Barlow, system-ui, sans-serif",
          }}>
            {annees.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
          {logo && <img src={logo} alt={code} style={{ height: 30, marginTop: 10, objectFit: "contain" }} />}
        </div>

        <div style={{ background: "#fff", border: `1px solid ${BDR}`, borderRadius: 12, padding: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: D, marginBottom: 12 }}>Variables ajustables</div>
          <SliderRow label="Primes émises" value={dPrimes} onChange={setDPrimes} min={-30} max={30} step={1} unit="%" resetValue={0} />
          <SliderRow label="Ratio de sinistralité" value={dRatioSp} onChange={setDRatioSp} min={-20} max={20} step={0.5} unit=" pt" resetValue={0} />
          <SliderRow label="Ratio de frais de gestion" value={dRatioFrais} onChange={setDRatioFrais} min={-10} max={10} step={0.5} unit=" pt" resetValue={0} />
          <SliderRow label="Capitaux propres" value={dCapitaux} onChange={setDCapitaux} min={-30} max={30} step={1} unit="%" resetValue={0} />
          <SliderRow label="Total actif" value={dActif} onChange={setDActif} min={-30} max={30} step={1} unit="%" resetValue={0} />
          <button onClick={() => { setDPrimes(0); setDRatioSp(0); setDRatioFrais(0); setDCapitaux(0); setDActif(0); }}
            style={{ width: "100%", marginTop: 4, padding: "8px", borderRadius: 8, border: `1px solid ${BDR}`,
              background: "#fff", color: G, fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
            Réinitialiser
          </button>
        </div>
      </div>

      {/* Colonne droite : résultats */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, overflowY: "auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
          <ResultCard label="Résultat net (MDT)" baseline={resultatBase} simulated={resultatSim} />
          <ResultCard label="ROE" baseline={roeBase} simulated={roeSim} unit="%" />
          <ResultCard label="ROA" baseline={roaBase} simulated={roaSim} unit="%" />
          <ResultCard label="Ratio combiné" baseline={ratioCombineBase} simulated={ratioCombineSim} unit="%" />
          <ResultCard label="Part de marché" baseline={pdmBase} simulated={pdmSim} unit="%" decimals={2} />
          <ResultCard label="Primes émises (MDT)" baseline={primesBase} simulated={primesSim} />
        </div>
        <div style={{ background: "#FFFBEA", border: "1px solid #FDE68A", borderRadius: 10, padding: "10px 14px", fontSize: 10.5, color: "#92700B" }}>
          ⚠ Simulateur exploratoire — formules simplifiées (Ratio combiné = Ratio S/P + Ratio de frais ;
          Résultat net ≈ Primes × (1 − Ratio combiné/100)). Ne remplace pas une analyse actuarielle ou financière détaillée.
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════ */
/* MODE MARCHÉ                                                    */
/* ══════════════════════════════════════════════════════════════ */
function ModeMarche() {
  const [annees, setAnnees] = useState([]);
  const [annee, setAnnee] = useState(null);
  const [profil, setProfil] = useState(null);

  const [dPib, setDPib] = useState(0);
  const [dPenetration, setDPenetration] = useState(0);
  const [dPopulation, setDPopulation] = useState(0);

  useEffect(() => {
    fetch(`${API}/api/apercu-marche/annees`).then(r => r.json()).then(data => {
      setAnnees(data);
      setAnnee(data[0] || null);
    });
  }, []);

  useEffect(() => {
    if (!annee) return;
    setProfil(null);
    fetch(`${API}/api/apercu-marche/profil-pays?annee=${annee}`).then(r => r.json()).then(setProfil);
  }, [annee]);

  useEffect(() => { setDPib(0); setDPenetration(0); setDPopulation(0); }, [annee]);

  if (!profil) return <div style={{ color: G, textAlign: "center", padding: 60 }}>Chargement…</div>;

  const pibBase = profil.pib_mdt;
  const penetrationBase = profil.taux_penetration_pct;
  const populationBase = profil.population;
  const primesBase = profil.total_primes_emises_mdt;
  const densiteBase = profil.densite_assurance_dt;

  const pibSim = pibBase != null ? pibBase * (1 + dPib / 100) : null;
  const penetrationSim = penetrationBase != null ? penetrationBase + dPenetration : null;
  const populationSim = populationBase != null ? populationBase * (1 + dPopulation / 100) : null;
  const primesSim = (pibSim != null && penetrationSim != null) ? pibSim * penetrationSim / 100 : null;
  const densiteSim = (primesSim != null && populationSim) ? (primesSim * 1_000_000) / populationSim : null;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16, flex: 1, minHeight: 0 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12, overflowY: "auto" }}>
        <div style={{ background: "#fff", border: `1px solid ${BDR}`, borderRadius: 12, padding: 14 }}>
          <label style={{ fontSize: 9, fontWeight: 800, color: G, textTransform: "uppercase" }}>Année de référence</label>
          <select value={annee || ""} onChange={e => setAnnee(Number(e.target.value))} style={{
            width: "100%", marginTop: 6, padding: "8px 10px", borderRadius: 8, border: `1px solid ${BDR}`,
            fontSize: 13, fontWeight: 700, color: D, fontFamily: "Barlow, system-ui, sans-serif",
          }}>
            {annees.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>

        <div style={{ background: "#fff", border: `1px solid ${BDR}`, borderRadius: 12, padding: 14 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: D, marginBottom: 12 }}>Variables macro ajustables</div>
          <SliderRow label="PIB" value={dPib} onChange={setDPib} min={-20} max={20} step={1} unit="%" resetValue={0} />
          <SliderRow label="Taux de pénétration" value={dPenetration} onChange={setDPenetration} min={-1} max={1} step={0.05} unit=" pt" resetValue={0} />
          <SliderRow label="Population" value={dPopulation} onChange={setDPopulation} min={-5} max={5} step={0.25} unit="%" resetValue={0} />
          <button onClick={() => { setDPib(0); setDPenetration(0); setDPopulation(0); }}
            style={{ width: "100%", marginTop: 4, padding: "8px", borderRadius: 8, border: `1px solid ${BDR}`,
              background: "#fff", color: G, fontSize: 11, fontWeight: 700, cursor: "pointer" }}>
            Réinitialiser
          </button>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10 }}>
          <ResultCard label="Primes totales (MDT)" baseline={primesBase} simulated={primesSim} />
          <ResultCard label="Densité (TND/hab.)" baseline={densiteBase} simulated={densiteSim} />
          <ResultCard label="Taux de pénétration" baseline={penetrationBase} simulated={penetrationSim} unit="%" decimals={2} />
          <ResultCard label="PIB (MDT)" baseline={pibBase} simulated={pibSim} decimals={0} />
          <ResultCard label="Population (hab.)" baseline={populationBase} simulated={populationSim} decimals={0} />
        </div>
        <div style={{ background: "#FFFBEA", border: "1px solid #FDE68A", borderRadius: 10, padding: "10px 14px", fontSize: 10.5, color: "#92700B" }}>
          ⚠ Simulateur exploratoire — Primes totales = PIB × Taux de pénétration (relation par définition), Densité = Primes / Population.
          Ignore les effets de second ordre (composition du marché, inflation sur la sinistralité...).
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════ */
/* PAGE PRINCIPALE                                                 */
/* ══════════════════════════════════════════════════════════════ */
export default function SimulateurWhatIf() {
  const [mode, setMode] = useState("compagnie");

  return (
    <div style={{ height: "calc(100vh - 92px)", background: "#F9F9FB", fontFamily: "Barlow,system-ui,sans-serif", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <PageHeaderBar
        title="Simulateur What-If"
        tabs={[
          { key: "compagnie", label: "Compagnie" },
          { key: "marche", label: "Marché" },
        ]}
        activeTab={mode}
        onTabChange={setMode}
      />
      <div style={{ flex: 1, overflow: "hidden", padding: "16px 28px", display: "flex", flexDirection: "column" }}>
        {mode === "compagnie" ? <ModeCompagnie /> : <ModeMarche />}
      </div>
    </div>
  );
}
