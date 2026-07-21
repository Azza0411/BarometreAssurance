import { useState, useMemo, useEffect, useRef } from "react";
import { getLogoSrc } from "../utils/logos";
import PageHeaderBar from "../components/PageHeaderBar";

const Y = "#FFE600", D = "#2E2E38", G = "#747480";
const FONT = "Barlow,system-ui,sans-serif";

/* ── Données (sources : ilboursa.com · atlas-mag.net · cga.gov.tn) ── */
const ACTU = [
  { id:1,  src:"ILBOURSA",      date:"08/07/2026", annee:2026, compagnie:"BNA Assurances",   categorie:"Innovation",             url:"https://www.ilboursa.com/marches/mobilite-electrique-bna-assurances-installe-deux-nouvelles-bornes-de-recharge-a-sfax_62826",    une:true,
    titre:"BNA Assurances inaugure deux bornes de recharge VE à Sfax",
    resume:"BNA Assurances a inauguré deux bornes de recharge VE/hybrides devant son siège régional de Sfax, en présence du Gouverneur Mohamed Hajri. Deuxième déploiement après le siège de Tunis." },
  { id:2,  src:"ILBOURSA",      date:"2026",       annee:2026, compagnie:"—",                categorie:"Résultats financiers",    url:"https://www.ilboursa.com/marches/exclusif--assurance-sante-groupe-en-tunisie-treize-ans-de-derive-technique-decryptes_62269",    une:false,
    titre:"Assurance santé groupe en Tunisie : 14 ans de dérive technique décryptés",
    resume:"11 compagnies sur 15 affichent des résultats techniques négatifs en 2024. Déficit cumulé : -54 MDT vs -23 MDT en 2023. Ratio combiné passé de 96,4% (2011) à 109,3% (2024)." },
  { id:3,  src:"ATLAS MAGAZINE", date:"18/05/2023", annee:2023, compagnie:"—",               categorie:"Publication",             url:"https://www.atlas-mag.net/fr/focus",  une:false,
    titre:"Histoire du marché tunisien de l'assurance",
    resume:"Analyse de l'évolution du marché depuis 1874 jusqu'à aujourd'hui : réformes structurelles, montée en puissance des acteurs locaux et enjeux de modernisation." },
  { id:4,  src:"ATLAS MAGAZINE", date:"23/11/2022", annee:2022, compagnie:"—",               categorie:"Publication",             url:"https://www.atlas-mag.net/fr/fiches-pays",  une:false,
    titre:"Le marché tunisien de l'assurance en 2021 — Fiche pays",
    resume:"Données 2021 : dépense par habitant 82,4 USD, taux de pénétration 1,7%. Analyse comparative des compagnies et tendances post-Covid." },
  { id:5,  src:"ATLAS MAGAZINE", date:"30/04/2019", annee:2019, compagnie:"—",               categorie:"Publication",             url:"https://www.atlas-mag.net/fr/dossiers-speciaux",  une:false,
    titre:"L'assurance des risques agricoles en Tunisie",
    resume:"Tour d'horizon de la couverture des risques agricoles en Tunisie : rôle de la CTAMA, régimes obligatoires et facultatifs, fonds de mutualité pour calamités naturelles." },
  { id:6,  src:"ATLAS MAGAZINE", date:"08/01/2018", annee:2018, compagnie:"—",               categorie:"Résultats financiers",    url:"https://www.atlas-mag.net/fr/statistiques-compagnies",  une:false,
    titre:"Marché de l'assurance au Maghreb : classement 2016 des compagnies",
    resume:"STAR Assurances (11e) et COMAR Assurances (19e) au classement Maghreb 2016. Analyse des primes émises et positionnement des acteurs tunisiens." },
  { id:7,  src:"CGA",           date:"13/06/2025", annee:2025, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:true,
    titre:"Règlement N°03/2025 : encadrement de l'externalisation des activités d'assurance",
    resume:"Fixe les conditions et modalités des conventions dans le cadre de l'externalisation des activités liées à l'exécution des contrats d'assurance." },
  { id:8,  src:"CGA",           date:"05/06/2025", annee:2025, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement N°02/2025 : plateforme automatisée de collecte de données au CGA",
    resume:"Création d'une plateforme dédiée à la collecte automatique des données transmises par les sociétés d'assurance et de réassurance." },
  { id:9,  src:"CGA",           date:"14/03/2025", annee:2025, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement N°01/2025 : pratiques commerciales dans le secteur des assurances",
    resume:"Encadrement des pratiques commerciales des sociétés d'assurance vis-à-vis des assurés et prospects." },
  { id:10, src:"CGA",           date:"15/09/2023", annee:2023, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement N°01/2023 : traitement des requêtes adressées au CGA",
    resume:"Définit les procédures de traitement et de suivi des requêtes adressées au CGA par les assurés et bénéficiaires." },
  { id:11, src:"CGA",           date:"11/11/2022", annee:2022, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement N°03/2022 : organisation des contrats d'assurance collectifs",
    resume:"Fixe les règles d'organisation des contrats collectifs, conventions cadres et conventions bilatérales dans le secteur." },
  { id:12, src:"CGA",           date:"24/06/2022", annee:2022, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement N°02/2022 : relation courtiers – sociétés d'assurance",
    resume:"Encadrement des rapports entre les courtiers d'assurance et les sociétés : obligations réciproques, rémunération, sinistres délégués." },
  { id:13, src:"CGA",           date:"01/12/2021", annee:2021, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Décision N°01/2021 : méthode de calcul des provisions pour dépréciation des créances",
    resume:"Fixe la base et la méthode de calcul des provisions pour dépréciation des créances sur les assurés et les intermédiaires." },
  { id:14, src:"CGA",           date:"11/02/2021", annee:2021, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement CGA N°01/2021 : obligations de reporting et rapport annuel",
    resume:"Fixe les obligations de reporting périodique et les éléments constitutifs du rapport annuel transmis au CGA." },
  { id:15, src:"CGA",           date:"06/04/2020", annee:2020, compagnie:"—",               categorie:"Coopération institutionnelle", url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:true,
    titre:"Avis du Collège CGA : mesures prudentielles Covid-19",
    resume:"Communiqué du Collège du CGA fixant les mesures prudentielles exceptionnelles adoptées en réponse à la crise sanitaire." },
  { id:16, src:"CGA",           date:"19/06/2020", annee:2020, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Décision N°01/2020 : travaux préparatifs pour l'adoption des normes IFRS/IAS",
    resume:"Fixe les travaux préparatoires à engager par les sociétés d'assurance pour l'adoption des normes comptables internationales." },
  { id:17, src:"CGA",           date:"29/04/2019", annee:2019, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement CGA N°01/2019 : procédures de retrait d'agrément des intermédiaires",
    resume:"Précise les procédures et conditions de retrait de l'agrément pour exercer la profession d'intermédiaire d'assurance." },
  { id:18, src:"CGA",           date:"17/10/2018", annee:2018, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement CGA N°04/2018 : notes techniques des contrats Vie et Capitalisation",
    resume:"Définit les spécifications obligatoires à insérer dans les notes techniques des contrats d'assurance Vie et de Capitalisation." },
  { id:19, src:"CGA",           date:"02/04/2018", annee:2018, compagnie:"—",               categorie:"Gouvernance",             url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement CGA N°02/2018 : obligation d'information sur les nominations",
    resume:"Oblige les sociétés à informer le CGA de toute nomination dans leurs structures d'administration, gestion et contrôle." },
  { id:20, src:"CGA",           date:"29/03/2017", annee:2017, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Décision N°24/2017 : méthode de calcul des provisions pour dépréciation",
    resume:"Fixe la méthode de calcul des provisions pour dépréciation des créances dans le secteur des assurances." },
  { id:21, src:"CGA",           date:"13/07/2016", annee:2016, compagnie:"—",               categorie:"Gouvernance",             url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Décision CGA N°01/2016 : règles de bonne gouvernance des sociétés d'assurance",
    resume:"Définit les règles de bonne gouvernance et de gestion applicables aux sociétés d'assurance et de réassurance." },
  { id:22, src:"CGA",           date:"28/03/2014", annee:2014, compagnie:"—",               categorie:"Réglementation",          url:"https://www.cga.gov.tn/index.php?id=33&L=0",  une:false,
    titre:"Règlement CGA N°01/2014 : documents constitutifs du rapport annuel (art. 60)",
    resume:"Précise les documents constitutifs du rapport annuel prévu par l'article 60 du code des assurances." },
];

/* ── Listes de filtres ── */
const SOURCES    = ["Toutes les sources", "ILBOURSA", "ATLAS MAGAZINE", "CGA"];
const CATEGORIES = ["Toutes les catégories", "Réglementation", "Résultats financiers", "Gouvernance", "Coopération institutionnelle", "Publication", "Innovation"];
const PERIODES   = ["Toutes les périodes", "30 derniers jours", "Cette année", "Année dernière"];
const PER_PAGE_OPTS = [5, 10, 20];

/* Compagnies avec actualités */
const COMPAGNIES_ACTU = ["Toutes les compagnies", ...Array.from(new Set(ACTU.map(a => a.compagnie).filter(c => c !== "—")))];

/* Logos carousel À la une */
const UNE_ITEMS = ACTU.filter(a => a.une);

/* Styles badges source */
const SRC_STYLE = {
  "ILBOURSA":      { bg:"#DCFCE7", color:"#15803D", border:"#BBF7D0" },
  "ATLAS MAGAZINE":{ bg:"#FFF7ED", color:"#92400E", border:"#FDE68A" },
  "CGA":           { bg:"#EFF6FF", color:"#1D4ED8", border:"#BFDBFE" },
};

const CAT_STYLE = {
  "Réglementation":             { bg:"#FEF2F2", color:"#991B1B", border:"#FECACA" },
  "Résultats financiers":       { bg:"#F0FDF4", color:"#15803D", border:"#BBF7D0" },
  "Gouvernance":                { bg:"#FFFBEB", color:"#92400E", border:"#FDE68A" },
  "Coopération institutionnelle":{ bg:"#EFF6FF", color:"#1D4ED8", border:"#BFDBFE" },
  "Publication":                { bg:"#F5F3FF", color:"#5B21B6", border:"#DDD6FE" },
  "Innovation":                 { bg:"#F0FDFA", color:"#0F766E", border:"#99F6E4" },
  "Digital":                    { bg:"#EFF6FF", color:"#1D4ED8", border:"#BFDBFE" },
  "Partenariat":                { bg:"#FFF7ED", color:"#C2410C", border:"#FDBA74" },
};

function SrcBadge({ src }) {
  const s = SRC_STYLE[src] || { bg:"#F5F5F5", color:G, border:"#E5E7EB" };
  return (
    <span style={{ fontSize:9, fontWeight:800, padding:"2px 8px", borderRadius:20,
      background:s.bg, color:s.color, border:`1px solid ${s.border}`, whiteSpace:"nowrap",
      letterSpacing:"0.3px", textTransform:"uppercase" }}>
      {src}
    </span>
  );
}

function CatBadge({ cat }) {
  const s = CAT_STYLE[cat] || { bg:"#F5F5F5", color:G, border:"#E5E7EB" };
  return (
    <span style={{ fontSize:9, fontWeight:700, padding:"2px 8px", borderRadius:20,
      background:s.bg, color:s.color, border:`1px solid ${s.border}`, whiteSpace:"nowrap" }}>
      {cat}
    </span>
  );
}

function parseDate(str) {
  const p = str.split("/");
  if (p.length === 3) return `${p[0]}/${p[1]}/${p[2]}`;
  return str;
}

/* ── Select dropdown — variante light ou dark ── */
function Sel({ value, onChange, options, dark = false }) {
  if (dark) {
    return (
      <select value={value} onChange={e => onChange(e.target.value)} style={{
        appearance:"none", WebkitAppearance:"none",
        background:"rgba(255,255,255,.08)",
        border:"1px solid rgba(255,255,255,.18)", borderRadius:8,
        padding:"7px 30px 7px 12px",
        fontSize:11, fontWeight:500, color:"rgba(255,255,255,.9)", cursor:"pointer",
        fontFamily:FONT, outline:"none", colorScheme:"dark",
        backgroundImage:`url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M2.5 4.5L6 8l3.5-3.5' stroke='rgba(255,255,255,.6)' stroke-width='1.8' fill='none' stroke-linecap='round'/%3E%3C/svg%3E")`,
        backgroundRepeat:"no-repeat", backgroundPosition:"right 9px center", backgroundSize:11,
      }}>
        {options.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  return (
    <select value={value} onChange={e => onChange(e.target.value)} style={{
      appearance:"none", WebkitAppearance:"none", background:"white",
      border:"1px solid #E5E7EB", borderRadius:8, padding:"8px 30px 8px 12px",
      fontSize:11.5, fontWeight:500, color:D, cursor:"pointer", fontFamily:FONT,
      outline:"none", boxShadow:"0 1px 4px rgba(0,0,0,.05)",
      backgroundImage:`url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12'%3E%3Cpath d='M2.5 4.5L6 8l3.5-3.5' stroke='%23747480' stroke-width='1.8' fill='none' stroke-linecap='round'/%3E%3C/svg%3E")`,
      backgroundRepeat:"no-repeat", backgroundPosition:"right 9px center", backgroundSize:11,
    }}>
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

/* ── Visuel par catégorie — image réelle + overlay sombre ── */
const CAT_IMG = {
  "Réglementation":              "/images/News1.png",
  "Résultats financiers":        "/images/News2.png",
  "Gouvernance":                 "/images/News3.png",
  "Coopération institutionnelle":"/images/News4.png",
  "Publication":                 "/images/News1.png",
  "Innovation":                  "/images/News2.png",
};

function CatVisual({ item }) {
  const img = CAT_IMG[item.categorie] || "/images/News1.png";
  return (
    <div style={{ position:"relative", overflow:"hidden", minHeight:280 }}>
      {/* Image de fond */}
      <img src={img} alt={item.categorie}
        style={{ position:"absolute", inset:0, width:"100%", height:"100%", objectFit:"cover" }}/>
      {/* Overlay dégradé pour lisibilité */}
      <div style={{
        position:"absolute", inset:0,
        background:"linear-gradient(135deg, rgba(0,0,0,.65) 0%, rgba(0,0,0,.25) 100%)",
      }}/>
      {/* Pill catégorie */}
      <div style={{
        position:"absolute", top:16, left:16,
        fontSize:9.5, fontWeight:800, color:"white",
        background:"rgba(255,255,255,.18)",
        border:"1px solid rgba(255,255,255,.3)",
        borderRadius:20, padding:"4px 12px",
        letterSpacing:"1px", textTransform:"uppercase",
        backdropFilter:"blur(4px)",
      }}>
        {item.categorie}
      </div>
      {/* Source caption */}
      <div style={{ position:"absolute", bottom:12, right:12, fontSize:9.5, color:"rgba(255,255,255,.6)",
        background:"rgba(0,0,0,.4)", padding:"3px 8px", borderRadius:4, fontStyle:"italic" }}>
        Source : {item.src}
      </div>
    </div>
  );
}

/* ── Carousel À la une — image plein cadre avec overlay texte ── */
function AlaUne({ onRead }) {
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % UNE_ITEMS.length), 7000);
    return () => clearInterval(t);
  }, []);

  if (!UNE_ITEMS.length) return null;
  const item = UNE_ITEMS[idx];
  const img = CAT_IMG[item.categorie] || "/images/News1.png";

  return (
    <div style={{ borderRadius:12, overflow:"hidden", position:"relative", height:220,
      boxShadow:"0 4px 24px rgba(0,0,0,.28)", flexShrink:0 }}>

      {/* Image de fond plein cadre */}
      <img src={img} alt={item.categorie}
        style={{ position:"absolute", inset:0, width:"100%", height:"100%", objectFit:"cover" }}/>

      {/* Overlay dégradé — assez opaque pour lisibilité */}
      <div style={{
        position:"absolute", inset:0,
        background:"linear-gradient(135deg, rgba(0,0,0,.82) 0%, rgba(0,0,0,.55) 55%, rgba(0,0,0,.2) 100%)",
      }}/>

      {/* Contenu texte sur l'overlay */}
      <div style={{ position:"absolute", inset:0, padding:"22px 28px",
        display:"flex", flexDirection:"column", justifyContent:"space-between" }}>

        {/* Haut : label + badges */}
        <div style={{ display:"flex", alignItems:"center", gap:10, flexWrap:"wrap" }}>
          <span style={{ fontSize:9, fontWeight:900, color:Y, textTransform:"uppercase",
            letterSpacing:"2.5px", display:"flex", alignItems:"center", gap:5 }}>
            <svg viewBox="0 0 16 16" fill={Y} width="9" height="9">
              <polygon points="8,1 10,6 15,6.5 11,10 12.5,15 8,12 3.5,15 5,10 1,6.5 6,6"/>
            </svg>
            À LA UNE
          </span>
          <CatBadge cat={item.categorie}/>
          <SrcBadge src={item.src}/>
          <span style={{ fontSize:10, color:"rgba(255,255,255,.55)", fontWeight:500 }}>{item.date}</span>
        </div>

        {/* Titre */}
        <div style={{ fontSize:20, fontWeight:900, color:"white", lineHeight:1.3,
          letterSpacing:"-0.3px", maxWidth:"70%" }}>
          {item.titre}
        </div>

        {/* Bas : bouton + navigation */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
          <a href={item.url} target="_blank" rel="noreferrer" style={{
            display:"inline-flex", alignItems:"center", gap:8,
            background:Y, color:D, textDecoration:"none",
            padding:"9px 18px", borderRadius:8, fontSize:12, fontWeight:800,
          }}>
            Lire l'article
            <svg viewBox="0 0 16 16" fill="none" stroke={D} strokeWidth="2.2" width="11" height="11">
              <path d="M3 8h10M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </a>

          {/* Flèches + dots */}
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <button onClick={() => setIdx(i => (i - 1 + UNE_ITEMS.length) % UNE_ITEMS.length)}
              style={{ background:"rgba(255,255,255,.15)", border:"none", borderRadius:6, width:30, height:30,
                display:"flex", alignItems:"center", justifyContent:"center", cursor:"pointer" }}>
              <svg viewBox="0 0 16 16" fill="none" stroke="white" strokeWidth="2" width="12" height="12">
                <path d="M10 4l-4 4 4 4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <div style={{ display:"flex", gap:5 }}>
              {UNE_ITEMS.map((_, i) => (
                <button key={i} onClick={() => setIdx(i)} style={{
                  width: i === idx ? 20 : 6, height:6, borderRadius:3, border:"none", cursor:"pointer",
                  background: i === idx ? Y : "rgba(255,255,255,.35)", transition:"all .25s", padding:0,
                }}/>
              ))}
            </div>
            <button onClick={() => setIdx(i => (i + 1) % UNE_ITEMS.length)}
              style={{ background:"rgba(255,255,255,.15)", border:"none", borderRadius:6, width:30, height:30,
                display:"flex", alignItems:"center", justifyContent:"center", cursor:"pointer" }}>
              <svg viewBox="0 0 16 16" fill="none" stroke="white" strokeWidth="2" width="12" height="12">
                <path d="M6 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Barre logos compagnies ── */
const LOGO_COMPANIES = ["STAR","COMAR","GAT","ASTREE","CARTE","LLOYD_TUNISIEN","MAGHREBIA","BH","BIAT","BNA","AMI"];

function LogoBar({ selected, onSelect }) {
  const ref = useRef(null);
  return (
    <div style={{ background:"white", border:"1px solid #E5E7EB", borderRadius:10,
      padding:"10px 16px", display:"flex", alignItems:"center", gap:10, flexShrink:0 }}>
      <span style={{ fontSize:9, fontWeight:800, color:G, textTransform:"uppercase",
        letterSpacing:"1.2px", whiteSpace:"nowrap", flexShrink:0 }}>
        Filtrer par compagnie
      </span>
      <div style={{ width:1, height:28, background:"#E5E7EB", flexShrink:0 }}/>
      <div ref={ref} style={{ display:"flex", alignItems:"center", gap:10, overflowX:"auto",
        flex:1, scrollbarWidth:"none" }}>
        {LOGO_COMPANIES.map(code => {
          const logo = getLogoSrc(code);
          const isActive = selected === code;
          return (
            <button key={code} onClick={() => onSelect(isActive ? null : code)}
              style={{ flexShrink:0, padding:"4px 10px", borderRadius:7, cursor:"pointer",
                border: isActive ? `2px solid ${Y}` : "1.5px solid #E5E7EB",
                background: isActive ? "#FFFBE6" : "white",
                display:"flex", alignItems:"center", justifyContent:"center",
                transition:"all .15s", minWidth:60 }}>
              {logo
                ? <img src={logo} alt={code} style={{ height:22, maxWidth:60, objectFit:"contain" }}/>
                : <span style={{ fontSize:9, fontWeight:700, color:D }}>{code}</span>
              }
            </button>
          );
        })}
      </div>
      <button onClick={() => ref.current?.scrollBy({ left:120, behavior:"smooth" })}
        style={{ background:"#F9FAFB", border:"1px solid #E5E7EB", borderRadius:6, width:28, height:28,
          display:"flex", alignItems:"center", justifyContent:"center", cursor:"pointer", flexShrink:0 }}>
        <svg viewBox="0 0 12 12" fill="none" stroke={G} strokeWidth="1.8" width="10" height="10">
          <path d="M4 3l4 3-4 3" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
    </div>
  );
}

/* ══ PAGE ═══════════════════════════════════════════════════════════════════ */
export default function ActualitesSeminaires() {
  const [search,       setSearch]       = useState("");
  const [srcFilter,    setSrcFilter]    = useState("Toutes les sources");
  const [compFilter,   setCompFilter]   = useState("Toutes les compagnies");
  const [catFilter,    setCatFilter]    = useState("Toutes les catégories");
  const [periodeFilter,setPeriodeFilter]= useState("Toutes les périodes");
  const [logoFilter,   setLogoFilter]   = useState(null);
  const [page,         setPage]         = useState(1);
  const [perPage,      setPerPage]      = useState(10);
  const [sortCol,      setSortCol]      = useState("date");
  const [sortAsc,      setSortAsc]      = useState(false);

  const parseNum = (s) => {
    const p = s.split("/");
    return p.length === 3 ? `${p[2]}${p[1]}${p[0]}` : `${s}0101`;
  };

  const filtered = useMemo(() => {
    let list = ACTU.filter(a => {
      if (srcFilter  !== "Toutes les sources"    && a.src       !== srcFilter)      return false;
      if (compFilter !== "Toutes les compagnies" && a.compagnie !== compFilter)     return false;
      if (catFilter  !== "Toutes les catégories" && a.categorie !== catFilter)      return false;
      if (logoFilter && a.compagnie.toUpperCase().replace(/\s/g,"_") !== logoFilter &&
          !a.compagnie.toLowerCase().includes(logoFilter.toLowerCase().replace(/_/g," "))) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!a.titre.toLowerCase().includes(q) && !a.compagnie.toLowerCase().includes(q) &&
            !a.categorie.toLowerCase().includes(q)) return false;
      }
      return true;
    });

    list = [...list].sort((a, b) => {
      let cmp = 0;
      if (sortCol === "date")      cmp = parseNum(a.date).localeCompare(parseNum(b.date));
      if (sortCol === "titre")     cmp = a.titre.localeCompare(b.titre);
      if (sortCol === "compagnie") cmp = a.compagnie.localeCompare(b.compagnie);
      if (sortCol === "src")       cmp = a.src.localeCompare(b.src);
      if (sortCol === "categorie") cmp = a.categorie.localeCompare(b.categorie);
      return sortAsc ? cmp : -cmp;
    });
    return list;
  }, [search, srcFilter, compFilter, catFilter, logoFilter, sortCol, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const paginated  = filtered.slice((page - 1) * perPage, page * perPage);
  const from = filtered.length === 0 ? 0 : (page - 1) * perPage + 1;
  const to   = Math.min(page * perPage, filtered.length);

  function reset() {
    setSearch(""); setSrcFilter("Toutes les sources"); setCompFilter("Toutes les compagnies");
    setCatFilter("Toutes les catégories"); setPeriodeFilter("Toutes les périodes");
    setLogoFilter(null); setPage(1);
  }

  function toggleSort(col) {
    if (sortCol === col) setSortAsc(v => !v);
    else { setSortCol(col); setSortAsc(false); }
  }

  const SortIcon = ({ col }) => (
    <span style={{ marginLeft:3, opacity: sortCol === col ? 1 : 0.3, fontSize:9 }}>
      {sortCol === col ? (sortAsc ? "↑" : "↓") : "↕"}
    </span>
  );

  const thStyle = { fontSize:11, fontWeight:700, color:"#374151", padding:"11px 14px",
    background:"#F9FAFB", borderBottom:"2px solid #E5E7EB", cursor:"pointer",
    userSelect:"none", whiteSpace:"nowrap", textAlign:"left" };

  /* Page numbers display */
  const pageNums = useMemo(() => {
    const nums = [];
    for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) nums.push(i);
    return nums;
  }, [page, totalPages]);

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"white", fontFamily:FONT,
      display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar
        title="Veille d'actualités"
        right={
          <div style={{ display:"flex", alignItems:"center", gap:10 }}>
            <div style={{ display:"flex", alignItems:"center", gap:7, background:"#F9FAFB",
              border:"1px solid #E5E7EB", borderRadius:20, padding:"5px 14px" }}>
              <div style={{ width:7, height:7, borderRadius:"50%", background:"#22C55E" }}/>
              <span style={{ fontSize:11, fontWeight:600, color:D }}>IlBoursa · Atlas Magazine · CGA</span>
            </div>
            <div style={{ display:"flex", alignItems:"center", gap:8, background:"white",
              border:"1px solid #E5E7EB", borderRadius:8, padding:"7px 12px", width:240,
              boxShadow:"0 1px 4px rgba(0,0,0,.05)" }}>
              <svg viewBox="0 0 20 20" fill="none" stroke={G} strokeWidth="1.6" width="13" height="13">
                <circle cx="9" cy="9" r="6"/><path d="M15 15l3 3" strokeLinecap="round"/>
              </svg>
              <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
                placeholder="Rechercher..."
                style={{ flex:1, border:"none", outline:"none", fontSize:11.5, color:D,
                  background:"transparent", fontFamily:FONT }}/>
              {search && (
                <button onClick={() => { setSearch(""); setPage(1); }}
                  style={{ border:"none", background:"none", cursor:"pointer", color:G, fontSize:14, lineHeight:1 }}>×</button>
              )}
            </div>
          </div>
        }
      />

      {/* ── Corps scrollable ── */}
      <div style={{ flex:1, overflowY:"auto", padding:"16px 32px 20px",
        display:"flex", flexDirection:"column", gap:14 }}>

        {/* Carousel */}
        <AlaUne/>

        {/* Filtres — dark gradient comme Aperçu Marché */}
        <div style={{
          background:"linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)",
          borderRadius:10, padding:"12px 18px",
          display:"flex", alignItems:"center", gap:10, flexShrink:0, flexWrap:"wrap",
          boxShadow:"0 4px 16px rgba(0,0,0,.25)",
        }}>
          <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
            <span style={{ fontSize:8.5, fontWeight:700, color:"rgba(255,255,255,.38)", letterSpacing:"1.5px", textTransform:"uppercase" }}>Source</span>
            <Sel dark value={srcFilter}     onChange={v => { setSrcFilter(v);     setPage(1); }} options={SOURCES}/>
          </div>
          <div style={{ width:1, height:40, background:"rgba(255,255,255,.1)", flexShrink:0 }}/>
          <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
            <span style={{ fontSize:8.5, fontWeight:700, color:"rgba(255,255,255,.38)", letterSpacing:"1.5px", textTransform:"uppercase" }}>Compagnie</span>
            <Sel dark value={compFilter}    onChange={v => { setCompFilter(v);    setPage(1); }} options={COMPAGNIES_ACTU}/>
          </div>
          <div style={{ width:1, height:40, background:"rgba(255,255,255,.1)", flexShrink:0 }}/>
          <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
            <span style={{ fontSize:8.5, fontWeight:700, color:"rgba(255,255,255,.38)", letterSpacing:"1.5px", textTransform:"uppercase" }}>Catégorie</span>
            <Sel dark value={catFilter}     onChange={v => { setCatFilter(v);     setPage(1); }} options={CATEGORIES}/>
          </div>
          <div style={{ width:1, height:40, background:"rgba(255,255,255,.1)", flexShrink:0 }}/>
          <div style={{ display:"flex", flexDirection:"column", gap:2 }}>
            <span style={{ fontSize:8.5, fontWeight:700, color:"rgba(255,255,255,.38)", letterSpacing:"1.5px", textTransform:"uppercase" }}>Période</span>
            <Sel dark value={periodeFilter} onChange={v => { setPeriodeFilter(v); setPage(1); }} options={PERIODES}/>
          </div>
          <button onClick={reset} style={{ display:"flex", alignItems:"center", gap:6, marginLeft:"auto",
            background:"transparent", border:"1.5px solid rgba(255,230,0,.55)", color:Y,
            borderRadius:8, padding:"7px 14px", fontSize:11, fontWeight:700, cursor:"pointer",
            fontFamily:FONT }}>
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" width="12" height="12">
              <path d="M3 10a7 7 0 1013.93-1.37" strokeLinecap="round"/>
              <polyline points="17,4 17,9 12,9" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Réinitialiser
          </button>
          <span style={{ fontSize:10, fontWeight:700, color:"rgba(255,255,255,.45)", whiteSpace:"nowrap" }}>
            {filtered.length} actualité{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Barre logos */}
        <LogoBar selected={logoFilter} onSelect={c => { setLogoFilter(c); setPage(1); }}/>

        {/* Table */}
        <div style={{ background:"white", border:"1px solid #E5E7EB", borderRadius:10, overflow:"hidden" }}>
          <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
            <thead>
              <tr>
                <th style={thStyle} onClick={() => toggleSort("date")}>
                  Date <SortIcon col="date"/>
                </th>
                <th style={{ ...thStyle, width:"40%" }} onClick={() => toggleSort("titre")}>
                  Actualité <SortIcon col="titre"/>
                </th>
                <th style={thStyle} onClick={() => toggleSort("compagnie")}>
                  Compagnie <SortIcon col="compagnie"/>
                </th>
                <th style={thStyle} onClick={() => toggleSort("src")}>
                  Source <SortIcon col="src"/>
                </th>
                <th style={thStyle} onClick={() => toggleSort("categorie")}>
                  Catégorie <SortIcon col="categorie"/>
                </th>
                <th style={{ ...thStyle, cursor:"default" }}>Lien</th>
              </tr>
            </thead>
            <tbody>
              {paginated.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding:"40px", textAlign:"center", color:G, fontSize:13 }}>
                    Aucune actualité ne correspond aux filtres sélectionnés.
                  </td>
                </tr>
              ) : paginated.map((a, i) => (
                <tr key={a.id} style={{ background: i % 2 === 0 ? "white" : "#FAFAFA",
                  borderBottom:"1px solid #F0F0F0" }}
                  onMouseEnter={e => e.currentTarget.style.background="#FFFBE6"}
                  onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? "white" : "#FAFAFA"}>
                  <td style={{ padding:"12px 14px", whiteSpace:"nowrap", color:G, fontSize:11, fontWeight:500 }}>
                    {parseDate(a.date)}
                  </td>
                  <td style={{ padding:"12px 14px", color:D, fontWeight:600, lineHeight:1.45 }}>
                    {a.titre}
                  </td>
                  <td style={{ padding:"12px 14px", color:D, whiteSpace:"nowrap" }}>
                    {a.compagnie}
                  </td>
                  <td style={{ padding:"12px 14px", whiteSpace:"nowrap" }}>
                    <SrcBadge src={a.src}/>
                  </td>
                  <td style={{ padding:"12px 14px", whiteSpace:"nowrap" }}>
                    <CatBadge cat={a.categorie}/>
                  </td>
                  <td style={{ padding:"12px 14px", whiteSpace:"nowrap" }}>
                    <a href={a.url} target="_blank" rel="noreferrer"
                      style={{ display:"inline-flex", alignItems:"center", gap:5,
                        fontSize:11, fontWeight:700, color:"#1D4ED8", textDecoration:"none" }}>
                      Lire l'article
                      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" width="10" height="10">
                        <path d="M4 12L12 4M6 4h6v6" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between",
          padding:"8px 0", flexShrink:0, flexWrap:"wrap", gap:10 }}>
          <span style={{ fontSize:12, color:G }}>
            Affichage de <b style={{ color:D }}>{from}</b> à <b style={{ color:D }}>{to}</b> sur{" "}
            <b style={{ color:D }}>{filtered.length}</b> actualité{filtered.length !== 1 ? "s" : ""}
          </span>

          <div style={{ display:"flex", alignItems:"center", gap:6 }}>
            {/* Précédent */}
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              style={{ padding:"6px 10px", border:"1px solid #E5E7EB", borderRadius:7, background:"white",
                cursor: page === 1 ? "default" : "pointer", color: page === 1 ? "#C0C0C8" : D,
                fontFamily:FONT, fontSize:11, fontWeight:600, display:"flex", alignItems:"center", gap:4 }}>
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" width="9" height="9">
                <path d="M8 3L4 6l4 3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>

            {pageNums.map(n => (
              <button key={n} onClick={() => setPage(n)}
                style={{ width:32, height:32, border: n === page ? "none" : "1px solid #E5E7EB",
                  borderRadius:7, background: n === page ? D : "white",
                  color: n === page ? "white" : D, fontSize:12, fontWeight: n === page ? 800 : 500,
                  cursor:"pointer", fontFamily:FONT }}>
                {n}
              </button>
            ))}

            {/* Suivant */}
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              style={{ padding:"6px 10px", border:"1px solid #E5E7EB", borderRadius:7, background:"white",
                cursor: page === totalPages ? "default" : "pointer",
                color: page === totalPages ? "#C0C0C8" : D,
                fontFamily:FONT, fontSize:11, fontWeight:600, display:"flex", alignItems:"center", gap:4 }}>
              <svg viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8" width="9" height="9">
                <path d="M4 3l4 3-4 3" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>

            {/* Par page */}
            <div style={{ display:"flex", alignItems:"center", gap:6, marginLeft:8 }}>
              <span style={{ fontSize:11, color:G }}>Afficher</span>
              <Sel value={String(perPage)} onChange={v => { setPerPage(+v); setPage(1); }}
                options={PER_PAGE_OPTS.map(String)}/>
              <span style={{ fontSize:11, color:G }}>par page</span>
            </div>
          </div>
        </div>

        <div style={{ textAlign:"right", fontSize:10, color:G, flexShrink:0 }}>
          Source : IlBoursa · Atlas Magazine · CGA · Données actualisées Avril 2026
        </div>
      </div>
    </div>
  );
}
