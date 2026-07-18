import { useState, useMemo } from "react";
import ReactApexChart from "react-apexcharts";
import PageHeaderBar from "../components/PageHeaderBar";

const Y = "#FFE600", D = "#2E2E38", G = "#747480", RED = "#C8102E";
const FONT = "Barlow,system-ui,sans-serif";

/* ── Données réelles (sources : cga.gov.tn + ftusanet.org) ───────────────── */
const DOCS = [
  /* CGA — Règlements et Décisions du Collège */
  { id:1,  src:"CGA",   type:"Règlement",   ref:"Règlement N°03/2025",            date:"13/06/2025", annee:2025, objet:"Encadrement des conventions d'externalisation des activités liées à l'exécution des contrats d'assurance", pdf:true },
  { id:2,  src:"CGA",   type:"Règlement",   ref:"Règlement N°02/2025",            date:"05/06/2025", annee:2025, objet:"Création d'une plateforme automatisée pour la collecte de données transmises par les sociétés d'assurance et de réassurance au CGA", pdf:true },
  { id:3,  src:"CGA",   type:"Avenant",     ref:"Avenant au Règlement CGA N°01/2021", date:"05/06/2025", annee:2025, objet:"Modification des obligations de reporting et des éléments constitutifs du rapport annuel des sociétés d'assurance et/ou de réassurance", pdf:true },
  { id:4,  src:"CGA",   type:"Règlement",   ref:"Règlement N°01/2025",            date:"14/03/2025", annee:2025, objet:"Pratiques commerciales dans le secteur des assurances", pdf:true },
  { id:5,  src:"CGA",   type:"Règlement",   ref:"Règlement N°01/2023",            date:"15/09/2023", annee:2023, objet:"Traitement et suivi des requêtes adressées au CGA concernant les services d'assurance", pdf:true },
  { id:6,  src:"CGA",   type:"Règlement",   ref:"Règlement N°03/2022",            date:"11/11/2022", annee:2022, objet:"Organisation des contrats d'assurance collectifs, des conventions cadres et des conventions bilatérales", pdf:true },
  { id:7,  src:"CGA",   type:"Règlement",   ref:"Règlement N°02/2022",            date:"24/06/2022", annee:2022, objet:"Règles régissant la relation entre les courtiers d'assurance et les sociétés d'assurance", pdf:true },
  { id:8,  src:"CGA",   type:"Règlement",   ref:"Règlement N°01/2022",            date:"24/06/2022", annee:2022, objet:"Gestion financière et comptable des sociétés d'assurance Takaful", pdf:true },
  { id:9,  src:"CGA",   type:"Décision",    ref:"Décision N°01/2021",             date:"01/12/2021", annee:2021, objet:"Base et méthode de calcul des provisions pour dépréciation des créances sur les assurés et les intermédiaires d'assurance", pdf:true },
  { id:10, src:"CGA",   type:"Règlement",   ref:"Règlement CGA N°01/2021",        date:"11/02/2021", annee:2021, objet:"Obligations de reporting périodique et éléments constitutifs du rapport annuel des sociétés d'assurance et de réassurance", pdf:true },
  { id:11, src:"CGA",   type:"Décision",    ref:"Décision N°01/2020",             date:"19/06/2020", annee:2020, objet:"Travaux préparatifs pour l'adoption des normes comptables internationales IFRS/IAS par les sociétés d'assurance", pdf:true },
  { id:12, src:"CGA",   type:"Communiqué",  ref:"Avis du Collège — Avr. 2020",    date:"06/04/2020", annee:2020, objet:"Mesures prudentielles exceptionnelles en réponse à la crise sanitaire Covid-19", pdf:true },
  { id:13, src:"CGA",   type:"Règlement",   ref:"Règlement CGA N°01/2019",        date:"29/04/2019", annee:2019, objet:"Procédures et conditions de retrait de l'agrément accordé pour exercer la profession d'intermédiaire d'assurance", pdf:true },
  { id:14, src:"CGA",   type:"Règlement",   ref:"Règlement CGA N°03/2019",        date:"29/04/2019", annee:2019, objet:"Procédures et conditions d'acceptation des lettres de garantie présentées par les réassureurs", pdf:true },
  { id:15, src:"CGA",   type:"Règlement",   ref:"Règlement CGA N°04/2018",        date:"17/10/2018", annee:2018, objet:"Spécifications obligatoires à insérer dans les notes techniques relatives aux contrats d'assurance Vie et de Capitalisation", pdf:true },
  { id:16, src:"CGA",   type:"Règlement",   ref:"Règlement CGA N°03/2018",        date:"11/07/2018", annee:2018, objet:"Organisation des travaux des actuaires et contenu de leur rapport adressé au CGA", pdf:true },
  { id:17, src:"CGA",   type:"Règlement",   ref:"Règlement CGA N°02/2018",        date:"02/04/2018", annee:2018, objet:"Obligation d'informer le CGA de toute nomination au sein des structures d'administration, de gestion et de contrôle", pdf:true },
  { id:18, src:"CGA",   type:"Décision",    ref:"Décision N°24/2017",             date:"29/03/2017", annee:2017, objet:"Méthode de calcul des provisions pour dépréciation des créances dans le secteur des assurances", pdf:true },
  { id:19, src:"CGA",   type:"Règlement",   ref:"Règlement CGA N°01/2016",        date:"13/07/2016", annee:2016, objet:"Assurance-vie et capitalisation — conditions de commercialisation et de gestion des contrats", pdf:true },
  { id:20, src:"CGA",   type:"Décision",    ref:"Décision CGA N°01/2016",         date:"13/07/2016", annee:2016, objet:"Règles de bonne gouvernance et de gestion applicables aux sociétés d'assurance et de réassurance", pdf:true },
  { id:21, src:"CGA",   type:"Règlement",   ref:"Règlement CGA N°01/2014",        date:"28/03/2014", annee:2014, objet:"Documents constitutifs du rapport annuel prévu par l'article 60 du code des assurances", pdf:true },
  /* CGA — Circulaires du ministre des finances */
  { id:22, src:"CGA",   type:"Circulaire",  ref:"Circulaire MF N°01/2018",        date:"31/01/2018", annee:2018, objet:"Tarif d'assurance frontière pour les véhicules étrangers entrant sur le territoire tunisien", pdf:true },
  { id:23, src:"CGA",   type:"Circulaire",  ref:"Circulaire MF N°01/2017",        date:"28/02/2017", annee:2017, objet:"Fixation du tarif de l'assurance de la responsabilité civile du fait de l'usage des véhicules terrestres à moteur", pdf:true },
  { id:24, src:"CGA",   type:"Circulaire",  ref:"Circulaire MF N°258/2010",       date:"02/10/2010", annee:2010, objet:"Conditions et modalités d'élaboration des rapports des commissaires aux comptes des sociétés d'assurance adressés au CGA", pdf:true },
  /* FTUSA — Textes législatifs et réglementaires */
  { id:25, src:"FTUSA", type:"Loi",         ref:"Loi n°92-24 du 9 mars 1992",     date:"09/03/1992", annee:1992, objet:"Code des Assurances tunisien — contrat d'assurance, organisation des professions, contrôle, RC automobile, assurance construction", pdf:true },
  { id:26, src:"FTUSA", type:"Loi",         ref:"Loi n°94-9 du 31 jan. 1994",     date:"31/01/1994", annee:1994, objet:"Responsabilité civile et contrôle technique dans la construction — cadre décennal pour architectes, ingénieurs et entrepreneurs", pdf:true },
  { id:27, src:"FTUSA", type:"Loi",         ref:"Loi n°80-88 du 31 déc. 1980",    date:"31/12/1980", annee:1980, objet:"Obligation d'assurance du transport des marchandises à l'importation et assurance incendie des établissements industriels", pdf:true },
  { id:28, src:"FTUSA", type:"Loi",         ref:"Loi n°86-106 du 31 déc. 1986",   date:"31/12/1986", annee:1986, objet:"Fonds de mutualité pour l'indemnisation des dommages agricoles causés par les calamités naturelles", pdf:true },
  { id:29, src:"FTUSA", type:"Loi",         ref:"Loi n°99-95 du 6 déc. 1999",     date:"06/12/1999", annee:1999, objet:"Fonds de garantie de financement des exportations — garantie des crédits de préfinancement à l'export", pdf:true },
  { id:30, src:"FTUSA", type:"Loi",         ref:"Loi n°2000-98 du 31 déc. 2000",  date:"31/12/2000", annee:2000, objet:"Fonds de garantie des assurés — indemnisation des victimes en cas d'insolvabilité d'une société d'assurance (articles 35-39)", pdf:true },
];

const TYPE_COLORS = {
  Règlement:  { bg:"#EBF5FF", color:"#1E40AF", border:"#BFDBFE" },
  Décision:   { bg:"#ECFDF5", color:"#065F46", border:"#A7F3D0" },
  Circulaire: { bg:"#FFF7ED", color:"#92400E", border:"#FDE68A" },
  Avenant:    { bg:"#F5F3FF", color:"#5B21B6", border:"#DDD6FE" },
  Communiqué: { bg:"#F0FDF4", color:"#15803D", border:"#BBF7D0" },
  Loi:        { bg:"#FFF1F2", color:"#9F1239", border:"#FECDD3" },
};
const TYPES  = ["Tous","Règlement","Décision","Circulaire","Avenant","Loi","Communiqué"];
const ANNEES = ["Tous",...Array.from(new Set(DOCS.map(d=>d.annee))).filter(a=>a<=2024).sort((a,b)=>a-b).map(String)];
const PAGE_SIZE = 12;

function TypeBadge({ type }) {
  const s = TYPE_COLORS[type] || { bg:"#F5F5F5", color:G, border:"#E5E7EB" };
  return (
    <span style={{
      fontSize:9.5, fontWeight:700, padding:"2px 9px", borderRadius:20,
      background:s.bg, color:s.color, border:`1px solid ${s.border}`, whiteSpace:"nowrap",
    }}>{type}</span>
  );
}

function PdfIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke={RED} strokeWidth="1.8" width="16" height="16">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
      <polyline points="14,2 14,8 20,8"/>
      <line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/>
    </svg>
  );
}

/* ── 3 variantes de KPI card ─────────────────────────────────────────────── */
function KpiRed({ icon, value, label, sub }) {
  return (
    <div style={{
      flex:1, borderRadius:14, padding:"16px 20px", position:"relative", overflow:"hidden",
      background:"linear-gradient(135deg,#B80C26 0%,#7A0000 100%)",
      boxShadow:"0 4px 18px rgba(184,12,38,0.28)",
      display:"flex", alignItems:"center", gap:16,
    }}>
      <div style={{ position:"absolute", right:-20, top:-20, width:80, height:80,
        borderRadius:"50%", background:"rgba(255,255,255,0.07)" }}/>
      <div style={{ width:48, height:48, borderRadius:12, flexShrink:0,
        background:"rgba(255,255,255,0.2)", border:"1px solid rgba(255,255,255,0.15)",
        display:"flex", alignItems:"center", justifyContent:"center" }}>{icon}</div>
      <div>
        <div style={{ fontSize:28, fontWeight:900, color:"white", lineHeight:1 }}>{value}</div>
        <div style={{ fontSize:11, fontWeight:700, color:"rgba(255,255,255,0.85)", marginTop:2 }}>{label}</div>
        {sub && <div style={{ fontSize:9, color:"rgba(255,255,255,0.55)", marginTop:2 }}>{sub}</div>}
      </div>
    </div>
  );
}

function KpiYellow({ icon, value, label, sub }) {
  return (
    <div style={{
      flex:1, borderRadius:14, padding:"16px 20px", position:"relative", overflow:"hidden",
      background:"linear-gradient(135deg,#FFE600 0%,#E6B800 100%)",
      boxShadow:"0 4px 18px rgba(255,230,0,0.35)",
      display:"flex", alignItems:"center", gap:16,
    }}>
      <div style={{ position:"absolute", right:-20, top:-20, width:80, height:80,
        borderRadius:"50%", background:"rgba(0,0,0,0.05)" }}/>
      <div style={{ width:48, height:48, borderRadius:12, flexShrink:0,
        background:"rgba(0,0,0,0.12)", border:"1px solid rgba(0,0,0,0.08)",
        display:"flex", alignItems:"center", justifyContent:"center" }}>{icon}</div>
      <div>
        <div style={{ fontSize:28, fontWeight:900, color:D, lineHeight:1 }}>{value}</div>
        <div style={{ fontSize:11, fontWeight:700, color:"rgba(46,46,56,0.8)", marginTop:2 }}>{label}</div>
        {sub && <div style={{ fontSize:9, color:"rgba(46,46,56,0.55)", marginTop:2 }}>{sub}</div>}
      </div>
    </div>
  );
}

function KpiDark({ icon, value, label, sub }) {
  return (
    <div style={{
      flex:1, borderRadius:14, padding:"16px 20px", position:"relative", overflow:"hidden",
      background:"linear-gradient(135deg,#2E2E38 0%,#1A1A22 100%)",
      boxShadow:"0 4px 18px rgba(46,46,56,0.25)",
      display:"flex", alignItems:"center", gap:16,
    }}>
      <div style={{ position:"absolute", right:-20, top:-20, width:80, height:80,
        borderRadius:"50%", background:"rgba(255,255,255,0.04)" }}/>
      <div style={{ width:48, height:48, borderRadius:12, flexShrink:0,
        background:"rgba(255,230,0,0.15)", border:"1px solid rgba(255,230,0,0.25)",
        display:"flex", alignItems:"center", justifyContent:"center" }}>{icon}</div>
      <div>
        <div style={{ fontSize:28, fontWeight:900, color:Y, lineHeight:1 }}>{value}</div>
        <div style={{ fontSize:11, fontWeight:700, color:"rgba(255,255,255,0.8)", marginTop:2 }}>{label}</div>
        {sub && <div style={{ fontSize:9, color:"rgba(255,255,255,0.45)", marginTop:2 }}>{sub}</div>}
      </div>
    </div>
  );
}

/* ── Filtre pills ─────────────────────────────────────────────────────────── */
function FilterSelect({ label, options, value, onChange }) {
  return (
    <div style={{ flex:1, minWidth:160 }}>
      <div style={{ fontSize:9.5, fontWeight:800, color:G, textTransform:"uppercase",
        letterSpacing:"1px", marginBottom:6 }}>{label}</div>
      <div style={{
        display:"flex", alignItems:"center", gap:3, flexWrap:"wrap",
        background:"white", borderRadius:10, padding:"6px 10px",
        border:"1px solid #E5E7EB", boxShadow:"0 1px 4px rgba(0,0,0,0.04)",
      }}>
        {options.map(opt => {
          const active = value===opt;
          return (
            <button key={opt} onClick={() => onChange(opt)} style={{
              padding:"3px 9px", borderRadius:20, fontSize:10.5,
              fontWeight:active?800:500, cursor:"pointer", border:"none",
              background:active?D:"transparent", color:active?Y:G, transition:"all .12s",
            }}>{opt}</button>
          );
        })}
      </div>
    </div>
  );
}

/* ══ PAGE ═══════════════════════════════════════════════════════════════════ */
export default function VeilleReglementaire() {
  const [typeFilter,  setTypeFilter]  = useState("Tous");
  const [anneeFilter, setAnneeFilter] = useState("Tous");
  const [search,      setSearch]      = useState("");
  const [page,        setPage]        = useState(1);

  const filtered = useMemo(() => DOCS.filter(d => {
    if (typeFilter!=="Tous" && d.type!==typeFilter) return false;
    if (anneeFilter!=="Tous" && String(d.annee)!==anneeFilter) return false;
    if (search) {
      const q = search.toLowerCase();
      if (!d.ref.toLowerCase().includes(q) && !d.objet.toLowerCase().includes(q)) return false;
    }
    return true;
  }), [typeFilter, anneeFilter, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length/PAGE_SIZE));
  const paginated  = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);
  function reset() { setTypeFilter("Tous"); setAnneeFilter("Tous"); setSearch(""); setPage(1); }

  /* Chart A — barres jaunes par année */
  const byAnnee = useMemo(() => {
    const map = {};
    DOCS.forEach(d => { map[d.annee] = (map[d.annee]||0)+1; });
    const keys = Object.keys(map).sort();
    return { cats:keys, vals:keys.map(k=>map[k]) };
  }, []);

  const chartAOpts = {
    chart:{ type:"bar", toolbar:{ show:false }, fontFamily:FONT, background:"transparent" },
    colors:[Y],
    plotOptions:{ bar:{ borderRadius:5, columnWidth:"54%" } },
    grid:{ borderColor:"#F0F0F0", strokeDashArray:4 },
    xaxis:{
      categories:byAnnee.cats,
      labels:{ style:{ colors:G, fontSize:"10px", fontWeight:600 }, rotate:-35 },
      axisBorder:{ show:false }, axisTicks:{ show:false },
    },
    yaxis:{
      labels:{ style:{ colors:G, fontSize:"10px" } },
      title:{ text:"Nombre de documents", style:{ color:G, fontSize:"9px", fontWeight:600 } },
    },
    dataLabels:{
      enabled:true, formatter:v=>v, offsetY:-6,
      style:{ fontSize:"11px", fontWeight:900, colors:[D] },
    },
    tooltip:{ y:{ formatter:v=>`${v} document${v>1?"s":""}` } },
  };

  /* Chart B — barres horizontales colorées, labels sombres sur fond clair */
  const byType = useMemo(() => {
    const map = {};
    DOCS.forEach(d => { map[d.type] = (map[d.type]||0)+1; });
    const sorted = Object.entries(map).sort((a,b)=>b[1]-a[1]);
    return { labels:sorted.map(e=>e[0]), vals:sorted.map(e=>e[1]) };
  }, []);
  const total = DOCS.length;
  const CHART_B_COLORS = [Y,"#4ADE80","#FB923C","#A78BFA","#F472B6"];

  const chartBOpts = {
    chart:{ type:"bar", toolbar:{ show:false }, fontFamily:FONT, background:"transparent" },
    colors:CHART_B_COLORS,
    plotOptions:{ bar:{ horizontal:true, borderRadius:5, barHeight:"55%", distributed:true } },
    legend:{ show:false },
    grid:{ borderColor:"#F0F0F0", strokeDashArray:4, xaxis:{ lines:{ show:true } }, yaxis:{ lines:{ show:false } } },
    xaxis:{
      labels:{ style:{ colors:G, fontSize:"10px" } },
      axisBorder:{ show:false }, axisTicks:{ show:false },
    },
    yaxis:{ labels:{ style:{ colors:D, fontSize:"11px", fontWeight:700 } } },
    dataLabels:{
      enabled:true,
      formatter:(v,{ dataPointIndex })=>`${v} (${((v/total)*100).toFixed(1)} %)`,
      style:{ fontSize:"10px", fontWeight:800, colors:[D] },
      offsetX:8,
    },
    tooltip:{ x:{ show:false }, y:{ formatter:v=>`${v} document${v>1?"s":""}` } },
  };

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"#F2F2F4", fontFamily:"Barlow,system-ui,sans-serif", display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar title="Veille Réglementaire" />

      {/* ── Corps scrollable ── */}
      <div style={{ flex:1, overflowY:"auto", padding:"16px 28px", display:"flex", flexDirection:"column", gap:12 }}>

      {/* ── KPI ROW — rouge / jaune / sombre ── */}
      <div style={{ display:"flex", gap:12, marginBottom:16 }}>
        <KpiRed
          value={DOCS.length}
          label="documents recensés"
          sub="CGA (règlements, décisions, circulaires) + FTUSA (lois)"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.6" width="24" height="24">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
            <polyline points="14,2 14,8 20,8"/>
            <line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/>
          </svg>}
        />
        <KpiYellow
          value="1980–2024"
          label="Période couverte"
          sub="Du Code des Assurances aux derniers règlements CGA"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke={D} strokeWidth="1.6" width="24" height="24">
            <rect x="3" y="4" width="18" height="18" rx="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
          </svg>}
        />
        <KpiDark
          value={Object.keys(DOCS.reduce((m,d)=>{ m[d.type]=1; return m; },{})).length}
          label="natures de documents"
          sub="règlement, décision, circulaire, avenant, loi, communiqué"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke={Y} strokeWidth="1.6" width="24" height="24">
            <path d="M21.21 15.89A10 10 0 118 2.83"/>
            <path d="M22 12A10 10 0 0012 2v10z"/>
          </svg>}
        />
      </div>

      {/* ── FILTRES ── */}
      <div style={{
        background:"white", borderRadius:12, border:"1px solid #EBEBEB",
        boxShadow:"0 2px 8px rgba(0,0,0,0.05)", padding:"14px 18px",
        display:"flex", alignItems:"flex-end", gap:12, marginBottom:16, flexWrap:"wrap",
      }}>
        <FilterSelect label="Type de document" options={TYPES} value={typeFilter}
          onChange={v=>{ setTypeFilter(v); setPage(1); }}/>
        <FilterSelect label="Année" options={ANNEES} value={anneeFilter}
          onChange={v=>{ setAnneeFilter(v); setPage(1); }}/>

        <div style={{ flex:1, minWidth:200 }}>
          <div style={{ fontSize:9.5, fontWeight:800, color:G, textTransform:"uppercase",
            letterSpacing:"1px", marginBottom:6 }}>Recherche</div>
          <div style={{
            display:"flex", alignItems:"center", gap:8, background:"white",
            borderRadius:10, padding:"7px 12px", border:"1px solid #E5E7EB",
          }}>
            <svg viewBox="0 0 20 20" fill="none" stroke={G} strokeWidth="1.6" width="15" height="15">
              <circle cx="9" cy="9" r="6"/><path d="M15 15l3 3"/>
            </svg>
            <input value={search} onChange={e=>{ setSearch(e.target.value); setPage(1); }}
              placeholder="Référence, objet ou mot-clé"
              style={{ flex:1, border:"none", outline:"none", fontSize:11.5, color:D, background:"transparent", fontFamily:FONT }}/>
          </div>
        </div>

        <button onClick={reset} style={{
          display:"flex", alignItems:"center", gap:6,
          background:"white", border:`1.5px solid ${RED}`, color:RED,
          borderRadius:10, padding:"7px 14px", fontSize:11.5, fontWeight:700, cursor:"pointer",
        }}>
          <svg viewBox="0 0 20 20" fill="none" stroke={RED} strokeWidth="1.8" width="14" height="14">
            <path d="M3 10a7 7 0 1013.93-1.37" strokeLinecap="round"/>
            <polyline points="17,4 17,9 12,9" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Réinitialiser
        </button>
      </div>

      {/* ── CHARTS ── */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:16 }}>
        <div style={{ background:"white", borderRadius:12, border:"1px solid #EBEBEB",
          boxShadow:"0 2px 8px rgba(0,0,0,0.05)", padding:"14px 16px" }}>
          <div style={{ fontSize:12, fontWeight:800, color:D, marginBottom:10 }}>
            <span style={{ fontSize:11, fontWeight:700, color:RED, marginRight:6 }}>A.</span>
            Documents par année de publication
          </div>
          <ReactApexChart options={chartAOpts}
            series={[{ name:"Documents", data:byAnnee.vals }]} type="bar" height={220}/>
        </div>

        <div style={{ background:"white", borderRadius:12, border:"1px solid #EBEBEB",
          boxShadow:"0 2px 8px rgba(0,0,0,0.05)", padding:"14px 16px" }}>
          <div style={{ fontSize:12, fontWeight:800, color:D, marginBottom:10 }}>
            <span style={{ fontSize:11, fontWeight:700, color:RED, marginRight:6 }}>B.</span>
            Répartition par nature de document
          </div>
          <ReactApexChart options={chartBOpts}
            series={[{ name:"Documents", data:byType.vals }]} type="bar" height={220}/>
          <div style={{ fontSize:9, color:G, marginTop:4, fontStyle:"italic" }}>
            Répartition calculée à partir des sources CGA et FTUSA.
          </div>
        </div>
      </div>

      {/* ── TABLE ── */}
      <div style={{ background:"white", borderRadius:12, border:"1px solid #EBEBEB",
        boxShadow:"0 2px 8px rgba(0,0,0,0.05)", overflow:"hidden" }}>
        <div style={{ padding:"14px 18px", borderBottom:"1px solid #F0F0F0" }}>
          <span style={{ fontSize:13, fontWeight:800, color:D }}>Tableau consolidé des documents</span>
          <span style={{ marginLeft:10, fontSize:11, color:G }}>
            {filtered.length} résultat{filtered.length>1?"s":""}{filtered.length<DOCS.length?` (sur ${DOCS.length})`:""}
          </span>
        </div>

        <div style={{ display:"grid", gridTemplateColumns:"36px 110px 1fr 100px 1fr 44px",
          background:D, padding:"9px 18px" }}>
          {["#","Type","Référence","Date","Objet / intitulé","PDF"].map(h=>(
            <div key={h} style={{ fontSize:9, fontWeight:800, color:Y,
              textTransform:"uppercase", letterSpacing:"1.2px" }}>{h}</div>
          ))}
        </div>

        {paginated.map((doc,i) => (
          <div key={doc.id} style={{
            display:"grid", gridTemplateColumns:"36px 110px 1fr 100px 1fr 44px",
            padding:"9px 18px", alignItems:"center",
            background:i%2===0?"#FAFAFA":"white", borderBottom:"1px solid #F5F5F5",
            transition:"background .1s", cursor:"default",
          }}
          onMouseEnter={e=>e.currentTarget.style.background="#FFF8E6"}
          onMouseLeave={e=>e.currentTarget.style.background=i%2===0?"#FAFAFA":"white"}>
            <div style={{ fontSize:11, fontWeight:700, color:G }}>{(page-1)*PAGE_SIZE+i+1}</div>
            <div><TypeBadge type={doc.type}/></div>
            <div style={{ fontSize:11, fontWeight:600, color:D, paddingRight:12 }}>{doc.ref}</div>
            <div style={{ fontSize:10.5, color:G }}>{doc.date}</div>
            <div style={{ fontSize:10.5, color:D, lineHeight:1.4, paddingRight:12 }}>{doc.objet}</div>
            <div style={{ display:"flex", justifyContent:"center" }}>
              {doc.pdf && <button style={{ border:"none", background:"none", cursor:"pointer", padding:4 }}><PdfIcon/></button>}
            </div>
          </div>
        ))}

        {paginated.length===0 && (
          <div style={{ padding:"40px 0", textAlign:"center", color:G, fontSize:12 }}>
            Aucun document ne correspond aux filtres sélectionnés
          </div>
        )}

        <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:12,
          padding:"12px 18px", borderTop:"1px solid #F0F0F0" }}>
          <button onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1} style={{
            width:30, height:30, borderRadius:8, border:"1.5px solid #E5E7EB",
            background:"white", cursor:page===1?"default":"pointer",
            display:"flex", alignItems:"center", justifyContent:"center", opacity:page===1?0.35:1,
          }}>
            <svg viewBox="0 0 16 16" fill="none" width="10" height="10">
              <path d="M10 4L6 8l4 4" stroke={D} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <span style={{ fontSize:11.5, fontWeight:700, color:D }}>
            {(page-1)*PAGE_SIZE+1}–{Math.min(page*PAGE_SIZE,filtered.length)} sur {filtered.length}
          </span>
          <button onClick={()=>setPage(p=>Math.min(totalPages,p+1))} disabled={page===totalPages} style={{
            width:30, height:30, borderRadius:8, border:"1.5px solid #E5E7EB",
            background:"white", cursor:page===totalPages?"default":"pointer",
            display:"flex", alignItems:"center", justifyContent:"center", opacity:page===totalPages?0.35:1,
          }}>
            <svg viewBox="0 0 16 16" fill="none" width="10" height="10">
              <path d="M6 4l4 4-4 4" stroke={D} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
      </div>

      <div style={{ textAlign:"right", fontSize:9.5, color:G, fontStyle:"italic" }}>
        Sources : cga.gov.tn · ftusanet.org · FS Market Intelligence
      </div>
      </div>{/* fin corps scrollable */}
    </div>
  );
}
