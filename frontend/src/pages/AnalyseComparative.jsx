import { useState, useEffect, useMemo } from "react";
import ReactApexChart from "react-apexcharts";
import { getLogoSrc } from "../utils/logos";
import KpiOptionsMenu from "../components/KpiOptionsMenu";
import { YearSelector, DarkKpiBanner, FamilleFilter } from "../components/PageHeaderBar";
import ExportPdfButton from "../components/ExportPdfButton";
import ExportExcelButton from "../components/ExportExcelButton";
import { kpiLabel, LABELS_HORS_CATALOGUE } from "../utils/kpiCatalog";
import { isTakaful } from "../utils/famille";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
const Y   = "#FFE600";
const D   = "#2E2E38";
const G   = "#747480";

/* ── Tier palette (EY brand) ── */
const COLOR_LEADER     = "#FFE600";   // #1  — jaune EY
const COLOR_CHALLENGER = "#2E2E38";   // #2–5 — anthracite EY
const COLOR_FOLLOWER   = "#747480";   // #6+  — gris EY

/* ── Seuils de catégorisation ──
   Leader     : rang 1 (meilleur score absolu)
   Challengers: rangs 2 à 3
   Followers  : rangs 4 et au-delà                */
function getTier(rank) {
  if (rank === 1) return "leader";
  if (rank <= 3)  return "challenger";
  return "follower";
}
function tierColor(rank) {
  const t = getTier(rank);
  if (t === "leader")     return COLOR_LEADER;
  if (t === "challenger") return COLOR_CHALLENGER;
  return COLOR_FOLLOWER;
}
function tierLabel(rank) {
  if (rank === 1) return "Leader";
  if (rank <= 3)  return "Challenger";
  return "Follower";
}

// COTUNACE, UIB et CARTE_VIE retirées (api/services/quality.py::
// PROBLEMATIC_CODES — corruption OCR chronique à la source, exclues de
// /api/analyse-comparative même quand une valeur numérique existe, car elle
// n'est pas fiable ; les sélectionner ici serait une case à cocher sans
// donnée fiable derrière). ATTIJARI, AT_TAKAFULIA et ZITOUNA_TAKAFUL
// ajoutées : la première avait toujours eu des données, simplement jamais
// incluse dans ce comparatif ; les deux Takaful ont un extracteur dédié
// depuis août 2026 (extraction/takaful_kpi_extractor.py). LLOYD_VIE et
// MAGHREBIA_VIE ajoutées le 2026-08-09 : contrairement à GAT_VIE/CARTE_VIE
// (aucune des 4 données clés extraite / OCR défaillant à l'époque), leur
// document CMF 2024 est intégralement exploitable — elles étaient de vraies
// données prêtes à l'emploi, mais absentes de cette liste et donc invisibles
// nulle part dans l'app.
// GAT_VIE ajoutée le 2026-08-16 : la cause du "aucune des 4 données clés
// extraite" ci-dessus est corrigée (bug de reconnaissance de page +
// libellé "Primes Acquises" au lieu de "Primes émises" sur la page
// raccordement, voir extraction/CAS_PARTICULIERS_ANNEXE12.md) — couverture
// désormais complète sur les 11 exercices disponibles (2015-2025).
// BNA ajoutée le 2026-08-16 : aucune donnée exploitable en 2024 (document
// CMF présent mais rien d'extractible), mais 2025 est intégralement
// exploitable (ratio combiné, ROE/ROA, primes...) — même raisonnement que
// LLOYD_VIE/MAGHREBIA_VIE ci-dessus (couverture partielle sur les années,
// pas absente de la liste pour autant).
const ASSUREURS = [
  "STAR","COMAR","GAT","GAT_VIE","ASTREE","CARTE","LLOYD_TUNISIEN","LLOYD_VIE",
  "MAGHREBIA","MAGHREBIA_VIE","BH","BIAT","BNA","TUNIS_RE","ATTIJARI",
  "AT_TAKAFULIA","ZITOUNA_TAKAFUL","AL_AMANAH_TAKAFUL",
];
const ASSUREUR_LABELS = {
  STAR:"STAR", COMAR:"COMAR", GAT:"GAT", GAT_VIE:"GAT VIE", ASTREE:"ASTREE", CARTE:"CARTE",
  LLOYD_TUNISIEN:"LLOYD", LLOYD_VIE:"LLOYD VIE", MAGHREBIA:"MAGHREBIA",
  MAGHREBIA_VIE:"MAGHREBIA VIE", BH:"BH",
  BIAT:"BIAT", BNA:"BNA", TUNIS_RE:"TUNIS RE", ATTIJARI:"ATTIJARI",
  AT_TAKAFULIA:"AT-TAKAFULIA", ZITOUNA_TAKAFUL:"ZITOUNA TAKAFUL",
  AL_AMANAH_TAKAFUL:"EL AMANA TAKAFUL",
};
// Libellés repris de frontend/src/utils/kpiCatalog.js (source unique du nom
// affiché) — seuls le champ backend, l'unité de formatage et le sens
// "plus bas = mieux" restent propres à cette page.
//
// Ratio combiné / de sinistralité / de frais de gestion et Part de marché :
// EXCLUS du référentiel Takaful jusqu'au 2026-08-16 (vérifié le 2026-08-09
// sur AT_TAKAFULIA/ZITOUNA_TAKAFUL : les 3 ratios techniques ressortaient
// null pour les deux, charges non extraites à l'époque). RÉINTÉGRÉS le
// 2026-08-16 : l'extraction dédiée des Annexes 14/15 (Charges de prestations/
// d'acquisition Takaful, voir extraction/takaful_kpi_extractor.py) couvre
// désormais les 3 opérateurs Takaful avec des valeurs dans la plage plausible
// — vérifié en direct sur /api/analyse-comparative (ex: AT_TAKAFULIA 2024 :
// RC 93,1 %, RSP 74,5 %, RF 18,6 %, PDM 1,8 %, tous non-null). Rappel
// d'interprétation : pour un opérateur Takaful, le Ratio combiné/de
// sinistralité reflète l'équilibre du FONDS DES PARTICIPANTS (mutualisé),
// pas la rentabilité propre de l'Opérateur — même nuance déjà affichée sur
// Vue par Assurance (TAKAFUL_NOTES dans FichesEntreprises.jsx), reprise ici
// via TAKAFUL_INDICATOR_NOTE ci-dessous. Ne jamais mélanger les deux listes :
// chaque référentiel n'affiche que les indicateurs qui lui sont réellement
// applicables (retour utilisateur).
const INDICATEURS_CONVENTIONNELLE = {
  [kpiLabel("Ratio combiné (%)")]:             { field:"ratio_combine",     unit:"%",    lowerBetter:true  },
  [kpiLabel("Ratio de sinistralité (%)")]:     { field:"ratio_sp",           unit:"%",    lowerBetter:true  },
  [kpiLabel("Ratio de frais de gestion (%)")]: { field:"ratio_frais",        unit:"%",    lowerBetter:true  },
  [kpiLabel("Part de marché (%)")]:            { field:"pdm",                unit:"%",    lowerBetter:false },
  [kpiLabel("Primes émises par assurance")]:   { field:"primes",             unit:" MDT", lowerBetter:false },
  [kpiLabel("ROE (%)")]:                       { field:"roe",                unit:"%",    lowerBetter:false },
  [kpiLabel("ROA (%)")]:                       { field:"roa",                unit:"%",    lowerBetter:false },
  [LABELS_HORS_CATALOGUE["Dettes/Capitaux propres (%)"].label]:    { field:"dette_cp",      unit:"%", lowerBetter:true  },
  [LABELS_HORS_CATALOGUE["Dettes/Actif (%)"].label]:               { field:"dette_actif",   unit:"%", lowerBetter:true  },
  [LABELS_HORS_CATALOGUE["Actions/Actif (%)"].label]:              { field:"actions_actif", unit:"%", lowerBetter:false },
  [LABELS_HORS_CATALOGUE["Placements/Capitaux propres (%)"].label]:{ field:"placements_cp", unit:"%", lowerBetter:false },
};
const INDICATEURS_TAKAFUL = {
  [kpiLabel("Ratio combiné (%)")]:             { field:"ratio_combine",     unit:"%",    lowerBetter:true  },
  [kpiLabel("Ratio de sinistralité (%)")]:     { field:"ratio_sp",           unit:"%",    lowerBetter:true  },
  [kpiLabel("Ratio de frais de gestion (%)")]: { field:"ratio_frais",        unit:"%",    lowerBetter:true  },
  [kpiLabel("Part de marché (%)")]:            { field:"pdm",                unit:"%",    lowerBetter:false },
  // "Contributions" et non "Primes émises" : en Takaful, le participant verse
  // une cotisation de don mutuel (Tabarru') dans le fonds collectif, pas une
  // prime commerciale (retour utilisateur du 2026-08-16) — même champ backend
  // "primes" (le montant en base ne change pas), seul le libellé affiché
  // diffère. Clé de menu volontairement distincte de kpiLabel("Primes émises
  // par assurance") pour ne pas dupliquer l'entrée conventionnelle.
  "Contributions":                             { field:"primes",             unit:" MDT", lowerBetter:false },
  // Surplus du Fonds des Participants (Familial + Général) : indicateur
  // Takaful sans équivalent conventionnel, déjà extrait et affiché sur Vue
  // par Assurance (section "Fonds des Participants") mais absent d'Analyse
  // Comparative jusqu'ici — ajouté le 2026-08-16 (retour utilisateur).
  "Surplus du Fonds des Participants":         { field:"surplus_fonds",      unit:" MDT", lowerBetter:false },
  [kpiLabel("ROE (%)")]:                       { field:"roe",                unit:"%",    lowerBetter:false },
  [kpiLabel("ROA (%)")]:                       { field:"roa",                unit:"%",    lowerBetter:false },
  [LABELS_HORS_CATALOGUE["Dettes/Capitaux propres (%)"].label]:    { field:"dette_cp",      unit:"%", lowerBetter:true  },
  [LABELS_HORS_CATALOGUE["Dettes/Actif (%)"].label]:               { field:"dette_actif",   unit:"%", lowerBetter:true  },
  [LABELS_HORS_CATALOGUE["Actions/Actif (%)"].label]:              { field:"actions_actif", unit:"%", lowerBetter:false },
  [LABELS_HORS_CATALOGUE["Placements/Capitaux propres (%)"].label]:{ field:"placements_cp", unit:"%", lowerBetter:false },
};
// Note d'interprétation affichée sous le titre du graphique quand la famille
// active est Takaful ET que l'indicateur choisi porte sur le Fonds des
// Participants plutôt que sur l'Opérateur lui-même — condensé de
// docs/ratios_takaful_ifsb_aaoifi.md, même texte que FichesEntreprises.jsx::
// TAKAFUL_NOTES pour rester cohérent entre les deux pages.
const TAKAFUL_INDICATOR_NOTE = {
  "Ratio combiné":            "Reflète l'équilibre du Fonds des Participants (PRF), pas la rentabilité de l'Opérateur.",
  "Ratio de sinistralité":    "Cotisation = don mutuel (Tabarru'), pas une prime commerciale — mesure l'équilibre du fonds.",
};
// AMI : aucun document CMF 2024 (dernier disponible : 2023). HAYETT :
// document CMF 2024 présent mais aucune des 4 données clés (primes, ratio
// combiné, ratio de frais, PDM) n'a pu en être extraite. CTAMA : absente du
// portail CMF pour 2021-2025 (limite source, pas un bug pipeline — voir
// commit du 2026-08-08). UIB/COTUNACE/CARTE VIE : données extraites mais
// écartées par api/services/quality.py::PROBLEMATIC_CODES (qualité OCR
// source non fiable), pas absentes à proprement parler. Cette liste
// s'affiche telle quelle quelle que soit l'année sélectionnée : elle liste
// les sociétés STRUCTURELLEMENT indisponibles (absentes de ASSUREURS
// ci-dessus), pas les trous ponctuels d'une société déjà affichée sur une
// année donnée (ceux-là remontent "N/D" cellule par cellule, pas ici).
const SANS_DONNEES_CONVENTIONNELLE = [
  "AMI","UIB","HAYETT","CTAMA","COTUNACE","CARTE VIE",
];
// AL AMANAH TAKAFUL : etats financiers en arabe, extraction dediee ajoutee
// le 2026-08-11 (voir extraction/CAS_PARTICULIERS_TAKAFUL.md) - couverture
// partielle sur 2024 (Total actif introuvable, donc ROA/ratios bases sur
// l'actif absents, mais Capitaux propres/Resultat Net/Primes disponibles).
const SANS_DONNEES_TAKAFUL = [];

// Indicateur par défaut par référentiel : "Ratio combiné" pour les deux
// depuis le 2026-08-16 (voir note sur INDICATEURS_TAKAFUL ci-dessus — fiable
// désormais pour les 3 opérateurs Takaful).
const INDICATEUR_DEFAUT = { conventionnelle:"Ratio combiné", takaful:"Ratio combiné" };

// Clé de stockage canonique (kpiMeta.js/KPI_CATALOG) par libellé d'indicateur
// — nécessaire pour KpiOptionsMenu (icône ⋯ : Qualité data / Document source
// / Chatbot), qui a besoin du storageKey, pas du libellé affiché. Seuls les
// indicateurs réellement suivis dans kpiMeta.js sont listés : les ratios
// "hors catalogue" (Dettes/Actif, Actions/Actif...) et les indicateurs
// Takaful spécifiques (Contributions, Surplus du Fonds des Participants)
// n'ont pas de fiche /kpi-detail — l'icône ne s'affiche alors pas
// (KpiOptionsMenu se masque déjà tout seul si `kpi` est absent).
const INDICATEUR_STORAGE_KEY = {
  "Ratio combiné":            "Ratio combiné (%)",
  "Ratio de sinistralité":    "Ratio de sinistralité (%)",
  "Ratio de frais de gestion":"Ratio de frais de gestion (%)",
  "Part de marché":           "Part de marché (%)",
  "Primes émises":            "Primes émises par assurance",
  "ROE":                      "ROE (%)",
  "ROA":                      "ROA (%)",
};

function useWindowSize() {
  const [s, setS] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const fn = () => setS({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", fn);
    return () => window.removeEventListener("resize", fn);
  }, []);
  return s;
}

function ChevronDown({ color = D, size = 12 }) {
  return (
    <svg viewBox="0 0 12 12" fill="none" width={size} height={size} style={{ flexShrink:0 }}>
      <path d="M2.5 4.5L6 8l3.5-3.5" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/* ── Badge de tier ── */
function TierBadge({ rank }) {
  const t = getTier(rank);
  const colors = {
    leader:     { bg:"#FFF8CC", color:"#6B5000", border:"#FFE600" },
    challenger: { bg:"#EEEEF4", color:"#2E2E38", border:"#2E2E38" },
    follower:   { bg:"#F3F3F7", color:"#5E5E74", border:"#747480" },
  };
  const c = colors[t];
  return (
    <span style={{
      fontSize:8, fontWeight:800, padding:"2px 7px", borderRadius:20,
      background:c.bg, color:c.color, border:`1px solid ${c.border}`,
      whiteSpace:"nowrap", textTransform:"uppercase", letterSpacing:"0.5px",
    }}>{tierLabel(rank)}</span>
  );
}

export default function AnalyseComparative() {
  const { h: winH } = useWindowSize();
  const chartH = Math.max(180, winH - 400);

  // Jamais "toutes" au chargement : les deux familles ne doivent jamais
  // être affichées simultanément (règle métier n°1, PROMPT MAÎTRE 2026-08-06).
  const [selected,      setSelected]      = useState(new Set(ASSUREURS.filter(a => !isTakaful(a))));
  const [famille,       setFamille]       = useState("conventionnelle");
  const [indicateur,    setIndicateur]    = useState("Ratio combiné");
  const [showIndDD,     setShowIndDD]     = useState(false);
  const [annee,         setAnnee]         = useState(2024);
  const [apiData,       setApiData]       = useState({});
  // Années réellement présentes en base (même source que Qualité Data,
  // Anomalies Système et KpiDetail) au lieu d'une liste codée en dur qui
  // finissait à 2024 et masquait silencieusement les années plus récentes.
  const [années,        setAnnées]        = useState([2024,2023,2022,2021,2020,2019,2018,2017,2016,2015,2014]);

  useEffect(() => {
    fetch(`${API}/api/annees-disponibles?source=CMF`)
      .then(r => r.json())
      .then(d => { if (d.annees?.length) setAnnées(d.annees); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setApiData({});
    fetch(`${API}/api/analyse-comparative?annee=${annee}`)
      .then(r => r.ok ? r.json() : {})
      .then(setApiData)
      .catch(() => {});
  }, [annee]);

  const toggleAssureur = (a) => {
    const s = new Set(selected);
    if (s.has(a)) { if (s.size > 1) s.delete(a); } else s.add(a);
    setSelected(s);
  };

  const applyFamilleFilter = (key) => {
    setFamille(key);
    const subset = ASSUREURS.filter(a => key === "takaful" ? isTakaful(a) : !isTakaful(a));
    setSelected(new Set(subset));
    setIndicateur(INDICATEUR_DEFAUT[key]);
  };

  // Les deux référentiels ne doivent jamais apparaître ensemble (règle
  // métier n°1) : toute liste de compagnies affichée à l'écran (chips,
  // dropdown, compteurs) doit être bornée à la famille active, pas aux 13
  // compagnies au total.
  const assureursFamille = useMemo(
    () => ASSUREURS.filter(a => famille === "takaful" ? isTakaful(a) : !isTakaful(a)),
    [famille]
  );
  const sansDonnees = famille === "takaful" ? SANS_DONNEES_TAKAFUL : SANS_DONNEES_CONVENTIONNELLE;
  const INDICATEURS = famille === "takaful" ? INDICATEURS_TAKAFUL : INDICATEURS_CONVENTIONNELLE;

  const ind      = INDICATEURS[indicateur];
  const filtered = assureursFamille.filter(a => selected.has(a));
  const vals     = filtered.map(a => apiData[a]?.[ind.field] ?? null);

  // Un indicateur qu'une seule compagnie (ou aucune) de la sélection active
  // peut renseigner n'a rien de "comparatif" — on le retire du menu plutôt
  // que de laisser l'utilisateur choisir un graphique à une seule barre
  // (retour utilisateur du 2026-08-16). Recalculé à chaque changement de
  // sélection/année : un indicateur peut réapparaître si l'utilisateur
  // réélargit sa sélection de compagnies.
  const availableIndicateurs = useMemo(() => {
    return Object.entries(INDICATEURS)
      .filter(([, def]) => filtered.filter(a => apiData[a]?.[def.field] != null).length >= 2)
      .map(([k]) => k);
  }, [INDICATEURS, filtered, apiData]);

  useEffect(() => {
    if (availableIndicateurs.length === 0) return;
    if (!availableIndicateurs.includes(indicateur)) {
      const fallback = availableIndicateurs.includes(INDICATEUR_DEFAUT[famille])
        ? INDICATEUR_DEFAUT[famille]
        : availableIndicateurs[0];
      setIndicateur(fallback);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableIndicateurs]);

  // Le graphique ne trace QUE les compagnies avec une valeur pour l'indicateur/
  // année courants — une barre "N/D" à 0 ne se distingue pas visuellement d'une
  // vraie valeur nulle et encombre le classement pour rien (retour utilisateur
  // du 2026-08-16). Les compagnies sans donnée pour CETTE sélection précise
  // sont listées à part, par logo, sous le graphique (cf. missingForSelection
  // plus bas) — distinct de `sansDonnees` (compagnies absentes de la liste
  // elle-même, quelle que soit l'année/l'indicateur).
  const plottedCodes = filtered.filter((a, i) => vals[i] != null);
  const plottedVals  = filtered.map((a, i) => vals[i]).filter(v => v != null);
  const missingForSelection = filtered.filter((a, i) => vals[i] == null);

  /* Classement des compagnies avec données pour déterminer les tiers */
  const rankMap = useMemo(() => {
    const withData = filtered
      .map((a, i) => ({ a, v: vals[i] }))
      .filter(x => x.v != null)
      .sort((x, y) => ind.lowerBetter ? x.v - y.v : y.v - x.v);
    const m = {};
    withData.forEach((x, i) => { m[x.a] = i + 1; });
    return m;
  }, [filtered, vals, ind]);

  const barColors = plottedVals.map((v, i) => {
    const rank = rankMap[plottedCodes[i]];
    return rank ? tierColor(rank) : COLOR_FOLLOWER;
  });

  const Y_AXIS_W = 54;

  const chartOpts = {
    chart: {
      type:"bar", toolbar:{ show:false },
      fontFamily:"Barlow, system-ui, sans-serif",
      animations:{ enabled:false }, background:"transparent",
    },
    plotOptions: { bar:{ columnWidth:"58%", borderRadius:4, borderRadiusApplication:"end", distributed:true } },
    colors: barColors,
    legend: { show:false },
    xaxis: {
      categories: plottedCodes.map(a => ASSUREUR_LABELS[a] ?? a),
      labels:{ show:false },
      axisBorder:{ show:false }, axisTicks:{ show:false },
    },
    yaxis: {
      labels:{
        formatter: v => `${v}${ind.unit}`,
        style:{ colors:"#747480", fontSize:"11px", fontFamily:"Barlow, system-ui, sans-serif" },
        minWidth: Y_AXIS_W, maxWidth: Y_AXIS_W,
      },
      min:0,
    },
    grid: {
      borderColor:"#EBEBEF", strokeDashArray:4,
      xaxis:{ lines:{ show:false } }, yaxis:{ lines:{ show:true } },
      padding:{ left:0, right:4, bottom:-10 },
    },
    dataLabels: {
      enabled:true,
      formatter: (v, { dataPointIndex }) => `${plottedVals[dataPointIndex]}${ind.unit}`,
      // dataLabels.style.colors est ignoré dès que background.enabled=true :
      // ApexCharts réécrit alors le fill du texte avec background.foreColor
      // (par défaut "#fff", voir apexcharts.esm.js::dataLabelsBackground —
      // `el.setAttribute("fill", w.config.dataLabels.background.foreColor)`
      // s'exécute APRÈS le dessin, écrasant toute couleur définie via
      // style.colors). C'est ce qui rendait le texte blanc même avec un fond
      // blanc — le vrai réglage de couleur de texte est foreColor, pas
      // style.colors, dès qu'un fond est actif (bug de config découvert le
      // 2026-08-17). Chip clair (fond blanc, bordure fine, ombre légère)
      // plutôt qu'un badge plein : cohérent avec le reste de l'app (KpiBox,
      // TierBadge — cartes claires à bordure fine) et moins "lourd"
      // visuellement (retour utilisateur : le badge marine plein ne plaisait
      // pas).
      style:{ fontSize:"11px", fontWeight:800, fontFamily:"Barlow, system-ui, sans-serif" },
      background:{
        foreColor:D,
        enabled:true, backgroundColor:"#FFFFFF", borderWidth:1, borderColor:"#E5E7EB",
        borderRadius:6, padding:5, opacity:1,
        dropShadow:{ enabled:true, top:1, left:0, blur:3, color:"#000000", opacity:0.10 },
      },
      offsetY: -7,
    },
    tooltip: {
      style:{ fontFamily:"Barlow, system-ui, sans-serif", fontSize:"12px" },
      y:{ formatter: (v, { dataPointIndex }) => {
        const orig = plottedVals[dataPointIndex];
        const a    = plottedCodes[dataPointIndex];
        const rank = rankMap[a];
        const tier = rank ? ` — ${tierLabel(rank)}` : "";
        return orig != null ? `${orig}${ind.unit}${tier}` : "Donnée non disponible";
      }},
    },
  };

  /* Classement complet pour le panel droit */
  const rankingList = useMemo(() => {
    return filtered
      .map((a, i) => ({ a, v: vals[i], rank: rankMap[a] ?? null }))
      .filter(x => x.v != null)
      .sort((x, y) => ind.lowerBetter ? x.v - y.v : y.v - x.v);
  }, [filtered, vals, rankMap, ind]);

  /* KPI banner — leader parmi les compagnies affichées */
  const leader = rankingList[0];
  const validVals = vals.filter(v => v != null);

  return (
    <div
      style={{ height:"calc(100vh - 92px)", background:"#EEEEF4", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}
      onClick={() => { if (showIndDD) setShowIndDD(false); }}
    >

      {/* ── Header ── */}
      <div style={{ background:"#FFFFFF", borderBottom:"1px solid #E5E7EB", flexShrink:0 }}>
        <div style={{ padding:"0 28px" }}>
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", height:58 }}>
            <div style={{ display:"flex", alignItems:"center", gap:10 }}>
              <img src="/logos/tn-flag.png" alt="TN" style={{ height:20, borderRadius:3, opacity:.85, flexShrink:0 }}/>
              <h1 style={{ fontSize:17, fontWeight:900, color:D, margin:0, letterSpacing:"-0.2px" }}>Analyse Comparative</h1>
            </div>
            <div style={{ display:"flex", gap:10, alignItems:"center" }}>

              <FamilleFilter value={famille} onChange={applyFamilleFilter}/>
              <span style={{ width:1, height:24, background:"#E5E7EB" }}/>

              {/* Indicateur */}
              <div style={{ position:"relative" }} onClick={e => e.stopPropagation()}>
                <button onClick={() => setShowIndDD(!showIndDD)}
                  style={{ display:"flex", alignItems:"center", gap:8, background:Y, color:D, border:"none", cursor:"pointer", padding:"7px 14px", borderRadius:9, fontSize:12, fontWeight:800, boxShadow:"0 2px 8px rgba(255,230,0,0.35)" }}>
                  <span style={{ color:"rgba(46,46,56,.45)", fontSize:8.5, fontWeight:700, letterSpacing:"1px", textTransform:"uppercase" }}>Indicateur</span>
                  <span style={{ width:1, height:12, background:"rgba(0,0,0,0.15)" }}/>
                  <span style={{ fontWeight:900 }}>{indicateur}</span>
                  <ChevronDown color={D} size={12}/>
                </button>
                {showIndDD && (
                  <div style={{ position:"absolute", top:"calc(100% + 6px)", left:0, background:"#fff", border:"1px solid #E5E7EB", borderRadius:12, boxShadow:"0 8px 28px rgba(0,0,0,0.13)", zIndex:60, minWidth:210, overflow:"hidden" }}>
                    {availableIndicateurs.map(k => (
                      <button key={k} onClick={() => { setIndicateur(k); setShowIndDD(false); }}
                        style={{ display:"block", width:"100%", textAlign:"left", padding:"10px 16px", fontSize:12, border:"none", cursor:"pointer", fontWeight: indicateur===k ? 800 : 500, color: indicateur===k ? D : G, background: indicateur===k ? "rgba(255,230,0,.13)" : "#fff", borderBottom:"1px solid #F5F5F5" }}>
                        {k}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <YearSelector year={annee} years={années} onChange={setAnnee}/>
              <ExportPdfButton href={`${API}/api/export/analyse-comparative?annee=${annee}`} />
              <ExportExcelButton href={`${API}/api/export/analyse-comparative.xlsx?annee=${annee}`} />
            </div>
          </div>
        </div>

        {/* Chips logos — grille (colonnes de largeur égale) plutôt qu'un flex-
            wrap : les pastilles ont des largeurs très variables selon la
            longueur du nom (ex: "GAT" vs "Assurances BIAT"), donc un simple
            flex-wrap produit des lignes en escalier dès que ça retombe à la
            ligne (repéré par l'utilisateur le 2026-08-19, capture à l'appui :
            "Tunis Re"/"Attijari Assurance" en 2e ligne, pas alignés sous les
            colonnes du dessus). La grille à colonnes égales aligne chaque
            pastille wrapée exactement sous celle du dessus. */}
        <div style={{ padding:"5px 28px 8px" }}>
          <div style={{ fontSize:9, fontWeight:800, color:G, letterSpacing:"1.5px", textTransform:"uppercase", marginBottom:5 }}>Comparaison active :</div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(112px, 1fr))", gap:5 }}>
            {assureursFamille.map(a => {
              const active = selected.has(a);
              return (
                <button key={a} onClick={() => toggleAssureur(a)}
                  title={active ? `Retirer ${ASSUREUR_LABELS[a]}` : `Ajouter ${ASSUREUR_LABELS[a]}`}
                  style={{ display:"flex", alignItems:"center", justifyContent:"center", padding:"3px 8px", background: active ? "white" : "transparent", border: active ? "1.5px solid #D1D5DB" : "1.5px solid transparent", borderRadius:8, cursor:"pointer", opacity: active ? 1 : 0.35, filter: active ? "none" : "grayscale(60%)", transition:"all .15s", boxShadow: active ? "0 1px 4px rgba(0,0,0,0.08)" : "none" }}>
                  {getLogoSrc(a)
                    ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]} style={{ height:36, width:"auto", maxWidth:110, objectFit:"contain" }}/>
                    : <span style={{ fontSize:9, fontWeight:800, color: active ? D : G }}>{ASSUREUR_LABELS[a]}</span>
                  }
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Corps ── */}
      <div style={{ flex:1, padding:"12px 28px 14px", display:"flex", flexDirection:"column", gap:10, overflow:"hidden" }}>

        {/* KPI Banner */}
        <DarkKpiBanner items={[
          { label:"Indicateur analysé",  value: indicateur,                                        sub:`${ind.unit} · données CMF` },
          { label:"Année d'analyse",     value: String(annee),                                     sub:"données certifiées CMF" },
          { label:"Assureurs comparés",  value: String(selected.size),                             sub:`sur ${assureursFamille.length} disponibles` },
          { label:"Leader",              value: leader ? (ASSUREUR_LABELS[leader.a] ?? leader.a) : "—", sub: leader ? `${leader.v}${ind.unit}` : "" },
        ]}/>

        {/* Graphique + Panel classement */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 280px", gap:14, flex:1, overflow:"hidden" }}>

          {/* ── Bar chart ── */}
          <div style={{ background:"white", borderRadius:14, border:"1px solid #EBEBEB", padding:"16px 16px 10px", boxShadow:"0 2px 10px rgba(0,0,0,0.05)", display:"flex", flexDirection:"column", minHeight:0, overflow:"hidden" }}>

            {/* Titre + légende tiers */}
            <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:10, flexShrink:0 }}>
              <div>
                <div style={{ fontSize:10, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D }}>
                  {indicateur} par assurance — {annee}
                </div>
                {famille === "takaful" && TAKAFUL_INDICATOR_NOTE[indicateur] && (
                  <div style={{ fontSize:9, color:G, marginTop:2, fontWeight:600 }}>
                    ☾ {TAKAFUL_INDICATOR_NOTE[indicateur]}
                  </div>
                )}
              </div>
              <div style={{ display:"flex", alignItems:"center", gap:14 }}>
                {[
                  { color:COLOR_LEADER,     label:"Leader #1" },
                  { color:COLOR_CHALLENGER, label:"Challengers #2–3" },
                  { color:COLOR_FOLLOWER,   label:"Followers #4+" },
                ].map(l => (
                  <div key={l.label} style={{ display:"flex", alignItems:"center", gap:5 }}>
                    <div style={{ width:10, height:10, borderRadius:2, background:l.color, flexShrink:0 }}/>
                    <span style={{ fontSize:9, color:G, fontWeight:600 }}>{l.label}</span>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column" }}>
              {validVals.length === 0 ? (
                <div style={{ flex:1, minHeight:0, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:8, color:G }}>
                  <div style={{ fontSize:12, fontWeight:700 }}>
                    {indicateur === "Part de marché"
                      ? `Total sectoriel FTUSA ${annee} pas encore publié`
                      : `Aucune donnée fiable pour « ${indicateur} »${famille==="takaful" ? " côté Takaful" : ""}`}
                  </div>
                  <div style={{ fontSize:10.5, textAlign:"center", maxWidth:360 }}>
                    {indicateur === "Part de marché"
                      ? "La Part de marché se calcule contre le total sectoriel publié par la FTUSA, qui paraît avec un décalage par rapport aux rapports individuels des compagnies — pas un problème d'extraction, juste une donnée pas encore disponible pour cette année."
                      : "Essayez un autre indicateur ou une autre année."}
                  </div>
                </div>
              ) : (<>
              {/* Le graphique prend tout l'espace flexible restant (flex:1 +
                  minHeight:0 — le piège classique flexbox/ApexCharts) ; la
                  ligne de logos garde sa PROPRE place fixe juste en dessous
                  au lieu d'un chevauchement par marge négative, qui pouvait
                  dépasser la hauteur de la carte (overflow:hidden) et
                  couper à la fois le bas du graphique et les logos
                  (retour utilisateur du 2026-08-09). */}
              <div style={{ flex:1, minHeight:0 }}>
                <ReactApexChart
                  key={`bar-${annee}-${indicateur}-${selected.size}`}
                  options={chartOpts}
                  series={[{ name:indicateur, data: plottedVals }]}
                  type="bar"
                  height="100%"
                />
              </div>

              {/* Logos sous le graphique */}
              <div style={{ display:"flex", alignItems:"center", paddingLeft:Y_AXIS_W, paddingRight:6, height:42, flexShrink:0 }}>
                {plottedCodes.map(a => (
                  <div key={a} style={{ flex:1, display:"flex", alignItems:"center", justifyContent:"center" }}>
                    {getLogoSrc(a)
                      ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]} style={{ height:32, width:"auto", maxWidth:82, objectFit:"contain" }}/>
                      : <span style={{ fontSize:8, fontWeight:700, color:D, textAlign:"center" }}>{ASSUREUR_LABELS[a]}</span>
                    }
                  </div>
                ))}
              </div>
              </>)}
            </div>

            {/* Compagnies sélectionnées mais sans donnée pour CET indicateur/
                CETTE année (dynamique) — distinct de sansDonnees ci-dessous
                (compagnies structurellement absentes de tout le comparatif,
                quel que soit l'indicateur/l'année). Logos plutôt qu'un simple
                texte : cohérent avec le reste de la page, et identifie la
                compagnie plus vite qu'un code (retour utilisateur du
                2026-08-16). */}
            {missingForSelection.length > 0 && (
              <div style={{ marginTop:10, padding:"10px 14px", background:"#FFFBEB", borderRadius:10, border:"1.5px solid #FDE68A", flexShrink:0, display:"flex", alignItems:"center", gap:12, flexWrap:"wrap" }}>
                <span style={{ fontSize:11, fontWeight:800, color:"#92400E", letterSpacing:"0.4px", whiteSpace:"nowrap", display:"flex", alignItems:"center", gap:5 }}>
                  <span style={{ fontSize:13 }}>⚠</span>
                  Sans donnée « {indicateur} » {annee} ({missingForSelection.length}) :
                </span>
                {missingForSelection.map(a => (
                  <div key={a} title={`${ASSUREUR_LABELS[a]} — pas de donnée pour « ${indicateur} » en ${annee}`}
                    style={{ display:"flex", alignItems:"center", padding:"3px 8px", background:"#FFFFFF", borderRadius:7, border:"1px solid #FDE68A" }}>
                    {getLogoSrc(a)
                      ? <img src={getLogoSrc(a)} alt={ASSUREUR_LABELS[a]} style={{ height:30, width:"auto", maxWidth:78, objectFit:"contain" }}/>
                      : <span style={{ fontSize:10.5, fontWeight:700, color:"#92400E" }}>{ASSUREUR_LABELS[a]}</span>
                    }
                  </div>
                ))}
              </div>
            )}

            {/* Compagnies absentes du comparatif quels que soient l'année/
                l'indicateur (voir SANS_DONNEES_CONVENTIONNELLE/TAKAFUL) */}
            {sansDonnees.length > 0 && (
              <div style={{ marginTop:6, padding:"7px 10px", background:"#FAFAFA", borderRadius:8, border:"1px solid #F0F0F0", flexShrink:0 }}>
                <span style={{ fontSize:9, fontWeight:700, color:G, letterSpacing:"0.8px", textTransform:"uppercase" }}>Non incluses dans ce comparatif : </span>
                <span style={{ fontSize:9, color:G }}>{sansDonnees.join(" · ")}</span>
              </div>
            )}
          </div>

          {/* ── Panel classement ── */}
          <div style={{ background:"white", borderRadius:14, border:"1px solid #EBEBEB", boxShadow:"0 2px 10px rgba(0,0,0,0.05)", display:"flex", flexDirection:"column", overflow:"hidden" }}>
            <div style={{ padding:"13px 16px", borderBottom:"1px solid #F0F0F0", flexShrink:0 }}>
              <div style={{ fontSize:10, fontWeight:800, letterSpacing:"1.5px", textTransform:"uppercase", color:D }}>Classement {annee}</div>
              <div style={{ fontSize:9, color:G, marginTop:2 }}>
                {ind.lowerBetter ? "Plus bas = meilleure performance" : "Plus haut = meilleure performance"}
              </div>
            </div>

            <div style={{ flex:1, overflowY:"auto" }}>
              {rankingList.map((row, i) => {
                const isLeader = row.rank === 1;
                return (
                  <div key={row.a} className="kpi-hover-card" style={{ display:"flex", alignItems:"center", gap:10, padding:"11px 14px", borderBottom:"1px solid #F8F8F8", background: isLeader ? "#FEFCE8" : "white" }}>
                    {/* Rang */}
                    <div style={{
                      width:26, height:26, borderRadius:7, flexShrink:0,
                      display:"flex", alignItems:"center", justifyContent:"center",
                      background: tierColor(row.rank),
                      color: isLeader ? D : "#FFFFFF",
                      fontSize:12, fontWeight:900,
                    }}>{row.rank}</div>

                    {/* Logo */}
                    <div style={{ width:100, height:44, flexShrink:0, background:"#FAFAFA", borderRadius:7, border:"1px solid #E5E7EB", display:"flex", alignItems:"center", justifyContent:"center", padding:"3px 6px" }}>
                      {getLogoSrc(row.a)
                        ? <img src={getLogoSrc(row.a)} alt={ASSUREUR_LABELS[row.a]} style={{ height:38, width:"auto", maxWidth:90, objectFit:"contain" }}/>
                        : <span style={{ fontSize:10, fontWeight:800, color:D }}>{ASSUREUR_LABELS[row.a]}</span>
                      }
                    </div>

                    {/* Valeur + tier */}
                    <div style={{ flex:1, textAlign:"right" }}>
                      <div style={{ display:"flex", alignItems:"center", justifyContent:"flex-end", gap:4 }}>
                        <div style={{ fontSize:16, fontWeight:700, color:D, lineHeight:1 }}>{row.v}{ind.unit}</div>
                        <KpiOptionsMenu
                          code={row.a}
                          kpi={INDICATEUR_STORAGE_KEY[indicateur]}
                          annee={annee}
                          label={indicateur}
                          value={`${row.v}${ind.unit}`}
                        />
                      </div>
                      <div style={{ marginTop:4 }}><TierBadge rank={row.rank}/></div>
                    </div>
                  </div>
                );
              })}
              {rankingList.length === 0 && (
                <div style={{ padding:24, textAlign:"center", color:G, fontSize:12 }}>
                  Aucune donnée disponible pour cette année
                </div>
              )}
            </div>

            <div style={{ padding:"9px 14px", borderTop:"1px solid #F0F0F0", flexShrink:0 }}>
              <div style={{ fontSize:9, color:G }}>Source CMF · {annee}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
