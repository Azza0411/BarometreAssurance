import { useState, useMemo } from "react";
import PageHeaderBar from "../components/PageHeaderBar";

const Y = "#FFE600", D = "#2E2E38", G = "#747480";
const FONT = "Barlow,system-ui,sans-serif";

/* ── Données réelles (sources : cga.gov.tn + ftusanet.org) ───────────────── */
const DOCS = [
  { id:1,  src:"CGA",   type:"Règlement",   date:"13/06/2025", annee:2025, titre:"Règlement n°03/2025 relatif à l'externalisation des activités d'assurance",                                       pdf:true },
  { id:2,  src:"CGA",   type:"Règlement",   date:"05/06/2025", annee:2025, titre:"Règlement n°02/2025 relatif à la plateforme de collecte automatique des données",                                 pdf:true },
  { id:3,  src:"CGA",   type:"Avenant",     date:"05/06/2025", annee:2025, titre:"Avenant au règlement n°01/2021 relatif au reporting annuel des entreprises d'assurance",                          pdf:true },
  { id:4,  src:"CGA",   type:"Règlement",   date:"14/03/2025", annee:2025, titre:"Règlement relatif aux pratiques commerciales dans le secteur des assurances",                                     pdf:true },
  { id:5,  src:"CGA",   type:"Règlement",   date:"15/09/2023", annee:2023, titre:"Règlement n°01/2023 relatif au traitement et suivi des requêtes adressées au CGA",                               pdf:true },
  { id:6,  src:"CGA",   type:"Règlement",   date:"11/11/2022", annee:2022, titre:"Règlement n°03/2022 relatif à l'organisation des contrats d'assurance collectifs",                               pdf:true },
  { id:7,  src:"CGA",   type:"Règlement",   date:"24/06/2022", annee:2022, titre:"Règlement n°02/2022 relatif aux règles régissant la relation entre courtiers et sociétés d'assurance",           pdf:true },
  { id:8,  src:"CGA",   type:"Règlement",   date:"24/06/2022", annee:2022, titre:"Règlement n°01/2022 relatif à la gestion financière et comptable des sociétés d'assurance Takaful",             pdf:true },
  { id:9,  src:"CGA",   type:"Décision",    date:"01/12/2021", annee:2021, titre:"Décision n°01/2021 relative à la base de calcul des provisions pour dépréciation des créances",                 pdf:true },
  { id:10, src:"CGA",   type:"Règlement",   date:"11/02/2021", annee:2021, titre:"Règlement CGA n°01/2021 relatif aux obligations de reporting périodique des sociétés d'assurance",              pdf:true },
  { id:11, src:"CGA",   type:"Décision",    date:"19/06/2020", annee:2020, titre:"Décision n°01/2020 relative aux travaux préparatifs pour l'adoption des normes IFRS/IAS",                        pdf:true },
  { id:12, src:"CGA",   type:"Communiqué",  date:"06/04/2020", annee:2020, titre:"Mesures prudentielles exceptionnelles en réponse à la crise sanitaire Covid-19",                                 pdf:true },
  { id:13, src:"CGA",   type:"Règlement",   date:"29/04/2019", annee:2019, titre:"Règlement CGA n°01/2019 relatif aux procédures de retrait de l'agrément des intermédiaires",                    pdf:true },
  { id:14, src:"CGA",   type:"Règlement",   date:"29/04/2019", annee:2019, titre:"Règlement CGA n°03/2019 relatif aux conditions d'acceptation des lettres de garantie des réassureurs",          pdf:true },
  { id:15, src:"CGA",   type:"Règlement",   date:"17/10/2018", annee:2018, titre:"Règlement CGA n°04/2018 relatif aux spécifications des notes techniques contrats Vie et Capitalisation",        pdf:true },
  { id:16, src:"CGA",   type:"Règlement",   date:"11/07/2018", annee:2018, titre:"Règlement CGA n°03/2018 relatif à l'organisation des travaux des actuaires",                                    pdf:true },
  { id:17, src:"CGA",   type:"Règlement",   date:"02/04/2018", annee:2018, titre:"Règlement CGA n°02/2018 relatif à l'obligation d'informer le CGA des nominations dans les organes de gestion", pdf:true },
  { id:18, src:"CGA",   type:"Décision",    date:"29/03/2017", annee:2017, titre:"Décision n°24/2017 relative à la méthode de calcul des provisions pour dépréciation des créances",             pdf:true },
  { id:19, src:"CGA",   type:"Règlement",   date:"13/07/2016", annee:2016, titre:"Règlement CGA n°01/2016 relatif à l'assurance-vie et capitalisation",                                           pdf:true },
  { id:20, src:"CGA",   type:"Décision",    date:"13/07/2016", annee:2016, titre:"Décision CGA n°01/2016 relative aux règles de bonne gouvernance des sociétés d'assurance",                      pdf:true },
  { id:21, src:"CGA",   type:"Règlement",   date:"28/03/2014", annee:2014, titre:"Règlement CGA n°01/2014 relatif au rapport annuel prévu à l'article 60 du code des assurances",                 pdf:true },
  { id:22, src:"CGA",   type:"Circulaire",  date:"31/01/2018", annee:2018, titre:"Circulaire MF n°01/2018 relative au tarif d'assurance frontière pour les véhicules étrangers",                  pdf:true },
  { id:23, src:"CGA",   type:"Circulaire",  date:"28/02/2017", annee:2017, titre:"Circulaire MF n°01/2017 fixant le tarif de la RC du fait de l'usage des véhicules terrestres à moteur",        pdf:true },
  { id:24, src:"CGA",   type:"Circulaire",  date:"02/10/2010", annee:2010, titre:"Circulaire MF n°258/2010 relative aux rapports des commissaires aux comptes adressés au CGA",                   pdf:true },
  { id:25, src:"FTUSA", type:"Code",        date:"09/03/1992", annee:1992, titre:"Code des assurances",                                                                                            pdf:true },
  { id:26, src:"FTUSA", type:"Loi",         date:"31/01/1994", annee:1994, titre:"Loi n°94-9 du 31 jan. 1994 relative à la responsabilité civile et contrôle dans la construction",               pdf:true },
  { id:27, src:"FTUSA", type:"Loi",         date:"31/12/1980", annee:1980, titre:"Loi n°80-88 du 31 déc. 1980 relative à l'obligation d'assurance du transport des marchandises à l'importation", pdf:true },
  { id:28, src:"FTUSA", type:"Loi",         date:"31/12/1986", annee:1986, titre:"Loi n°86-106 du 31 déc. 1986 relative au fonds de mutualité pour les dommages agricoles",                       pdf:true },
  { id:29, src:"FTUSA", type:"Loi",         date:"06/12/1999", annee:1999, titre:"Loi n°99-95 du 6 déc. 1999 relative au fonds de garantie de financement des exportations",                      pdf:true },
  { id:30, src:"FTUSA", type:"Décret",      date:"14/02/2002", annee:2002, titre:"Décret n°2002-571 du 14 février 2002 fixant les conditions de fonctionnement des entreprises d'assurance",      pdf:true },
  { id:31, src:"FTUSA", type:"Décret",      date:"24/11/1981", annee:1981, titre:"Décret n°81-1257 du 24 novembre 1981 relatif à l'assurance obligatoire des véhicules automobiles",              pdf:true },
  { id:32, src:"FTUSA", type:"Loi",         date:"31/12/2000", annee:2000, titre:"Loi n°2000-98 du 31 déc. 2000 relative au fonds de garantie des assurés",                                       pdf:true },
  { id:33, src:"FTUSA", type:"Loi",         date:"30/12/2016", annee:2016, titre:"Loi n°2016-48 du 30 décembre 2016 portant loi de finances pour l'année 2017",                                   pdf:true },
];

const TYPE_COLORS = {
  Règlement:  { bg:"#EBF5FF", color:"#1E40AF", border:"#BFDBFE" },
  Décision:   { bg:"#ECFDF5", color:"#065F46", border:"#A7F3D0" },
  Circulaire: { bg:"#FFF7ED", color:"#92400E", border:"#FDE68A" },
  Avenant:    { bg:"#F5F3FF", color:"#5B21B6", border:"#DDD6FE" },
  Communiqué: { bg:"#F0FDF4", color:"#15803D", border:"#BBF7D0" },
  Loi:        { bg:"#FFF8E6", color:"#854D0E", border:"#FEF08A" },
  Code:       { bg:"#F5F5F5", color:"#374151", border:"#D1D5DB" },
  Décret:     { bg:"#FFF0E6", color:"#9A3412", border:"#FDBA74" },
};

const SOURCES  = ["Toutes les sources", "CGA", "FTUSA"];
const TYPES    = ["Tous les types", "Règlement", "Décision", "Circulaire", "Avenant", "Loi", "Code", "Décret", "Communiqué"];
const ANNEES_LIST = ["Toutes les années", ...Array.from(new Set(DOCS.map(d => d.annee))).sort((a,b) => b-a).map(String)];
const PAGE_SIZE = 10;

/* ── Composants ── */
function TypeBadge({ type }) {
  const s = TYPE_COLORS[type] || { bg:"#F5F5F5", color:G, border:"#E5E7EB" };
  return (
    <span style={{ fontSize:9.5, fontWeight:700, padding:"3px 10px", borderRadius:20, background:s.bg, color:s.color, border:`1px solid ${s.border}`, whiteSpace:"nowrap" }}>
      {type}
    </span>
  );
}

function SourceLogo({ src }) {
  if (src === "CGA") {
    return (
      <div style={{ display:"flex", alignItems:"center", gap:5 }}>
        <img src="/imagesFond/CGA.png" alt="CGA" style={{ height:22, objectFit:"contain" }}
          onError={e => { e.target.style.display="none"; }}/>
        <span style={{ fontSize:10, fontWeight:700, color:D }}>CGA</span>
      </div>
    );
  }
  return (
    <div style={{ display:"flex", alignItems:"center", gap:5 }}>
      <img src="/imagesFond/FTUSA.png" alt="FTUSA" style={{ height:22, objectFit:"contain" }}
        onError={e => { e.target.style.display="none"; }}/>
      <span style={{ fontSize:10, fontWeight:700, color:D }}>FTUSA</span>
    </div>
  );
}

function Select({ value, onChange, options, dark = false }) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      style={{
        appearance:"none", WebkitAppearance:"none",
        background: dark ? "rgba(255,255,255,.08)" : "white",
        border: dark ? "1px solid rgba(255,255,255,.18)" : "1px solid #E5E7EB",
        borderRadius:8, padding:"8px 30px 8px 12px",
        fontSize:12, fontWeight:500,
        color: dark ? "white" : D,
        cursor:"pointer", fontFamily:FONT, outline:"none",
        backgroundImage: dark
          ? `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12' fill='none'%3E%3Cpath d='M2.5 4.5L6 8l3.5-3.5' stroke='rgba(255,255,255,.5)' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`
          : `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12' fill='none'%3E%3Cpath d='M2.5 4.5L6 8l3.5-3.5' stroke='%23747480' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
        backgroundRepeat:"no-repeat", backgroundPosition:"right 10px center",
        backgroundSize:12,
        colorScheme: dark ? "dark" : "light",
      }}
    >
      {options.map(o => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

/* ══ PAGE ═══════════════════════════════════════════════════════════════════ */
export default function VeilleReglementaire() {
  const [srcFilter,    setSrcFilter]    = useState("Toutes les sources");
  const [typeFilter,   setTypeFilter]   = useState("Tous les types");
  const [anneeFilter,  setAnneeFilter]  = useState("Toutes les années");
  const [search,       setSearch]       = useState("");
  const [page,         setPage]         = useState(1);
  const [perPage,      setPerPage]      = useState(10);
  const [sortCol,      setSortCol]      = useState("date");
  const [sortAsc,      setSortAsc]      = useState(false);

  /* Parse date dd/mm/yyyy → comparable string yyyy/mm/dd */
  const parseDate = (s) => {
    const [d, m, y] = s.split("/");
    return `${y}/${m}/${d}`;
  };

  const filtered = useMemo(() => {
    let list = DOCS.filter(d => {
      if (srcFilter !== "Toutes les sources" && d.src !== srcFilter) return false;
      if (typeFilter !== "Tous les types" && d.type !== typeFilter) return false;
      if (anneeFilter !== "Toutes les années" && String(d.annee) !== anneeFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!d.titre.toLowerCase().includes(q)) return false;
      }
      return true;
    });

    list = [...list].sort((a, b) => {
      let cmp = 0;
      if (sortCol === "date")   cmp = parseDate(a.date).localeCompare(parseDate(b.date));
      if (sortCol === "type")   cmp = a.type.localeCompare(b.type);
      if (sortCol === "titre")  cmp = a.titre.localeCompare(b.titre);
      if (sortCol === "source") cmp = a.src.localeCompare(b.src);
      if (sortCol === "annee")  cmp = a.annee - b.annee;
      return sortAsc ? cmp : -cmp;
    });

    return list;
  }, [srcFilter, typeFilter, anneeFilter, search, sortCol, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / perPage));
  const paginated  = filtered.slice((page - 1) * perPage, page * perPage);

  function reset() {
    setSrcFilter("Toutes les sources");
    setTypeFilter("Tous les types");
    setAnneeFilter("Toutes les années");
    setSearch(""); setPage(1);
  }

  function toggleSort(col) {
    if (sortCol === col) setSortAsc(v => !v);
    else { setSortCol(col); setSortAsc(false); }
  }

  function SortIcon({ col }) {
    const active = sortCol === col;
    return (
      <span style={{ marginLeft:4, opacity: active ? 1 : 0.35, fontSize:9 }}>
        {active ? (sortAsc ? "↑" : "↓") : "↕"}
      </span>
    );
  }

  const thStyle = (col) => ({
    fontSize:11, fontWeight:700, color:"#374151", textAlign:"left",
    padding:"11px 14px", background:"#F9FAFB", borderBottom:"1px solid #E5E7EB",
    cursor:"pointer", userSelect:"none", whiteSpace:"nowrap",
  });

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"white", fontFamily:FONT, display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar
        title="Veille réglementaire"
        right={
          <div style={{ display:"flex", alignItems:"center", gap:7, background:"#F9FAFB",
            border:"1px solid #E5E7EB", borderRadius:20, padding:"5px 14px" }}>
            <div style={{ width:7, height:7, borderRadius:"50%", background:"#22C55E" }}/>
            <span style={{ fontSize:11, fontWeight:600, color:D }}>Sources officielles · CGA · FTUSA</span>
          </div>
        }
      />

      {/* ── Filtres — dark gradient (même style que barre KPI Aperçu Marché) ── */}
      <div style={{
        background:"linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)",
        padding:"14px 32px", flexShrink:0,
        boxShadow:"0 2px 12px rgba(10,10,20,.3)",
      }}>
        <div style={{ display:"flex", alignItems:"center", gap:10, flexWrap:"wrap" }}>
          {/* Recherche */}
          <div style={{ display:"flex", alignItems:"center", gap:8, background:"rgba(255,255,255,.08)", border:"1px solid rgba(255,255,255,.14)", borderRadius:8, padding:"7px 12px", flex:"0 0 240px" }}>
            <svg viewBox="0 0 20 20" fill="none" stroke="rgba(255,255,255,.5)" strokeWidth="1.6" width="14" height="14">
              <circle cx="9" cy="9" r="6"/><path d="M15 15l3 3"/>
            </svg>
            <input value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
              placeholder="Rechercher un texte, mot-clé..."
              style={{ flex:1, border:"none", outline:"none", fontSize:12, color:"white", background:"transparent", fontFamily:FONT }}/>
            {search && (
              <button onClick={() => { setSearch(""); setPage(1); }} style={{ border:"none", background:"none", cursor:"pointer", color:"rgba(255,255,255,.5)", fontSize:14, lineHeight:1 }}>×</button>
            )}
          </div>

          {/* Séparateur */}
          <div style={{ width:1, height:32, background:"rgba(255,255,255,.10)", flexShrink:0 }}/>

          {/* Source */}
          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <div style={{ fontSize:7.5, fontWeight:700, color:"rgba(255,255,255,.38)", textTransform:"uppercase", letterSpacing:"2px" }}>Source</div>
            <Select value={srcFilter} onChange={v => { setSrcFilter(v); setPage(1); }} options={SOURCES} dark/>
          </div>

          {/* Type */}
          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <div style={{ fontSize:7.5, fontWeight:700, color:"rgba(255,255,255,.38)", textTransform:"uppercase", letterSpacing:"2px" }}>Type de texte</div>
            <Select value={typeFilter} onChange={v => { setTypeFilter(v); setPage(1); }} options={TYPES} dark/>
          </div>

          {/* Année */}
          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <div style={{ fontSize:7.5, fontWeight:700, color:"rgba(255,255,255,.38)", textTransform:"uppercase", letterSpacing:"2px" }}>Année</div>
            <Select value={anneeFilter} onChange={v => { setAnneeFilter(v); setPage(1); }} options={ANNEES_LIST} dark/>
          </div>

          {/* Réinitialiser */}
          <button onClick={reset} style={{
            marginTop:14, display:"flex", alignItems:"center", gap:6,
            background:"rgba(255,230,0,.12)", border:"1px solid rgba(255,230,0,.35)",
            color:"#FFE600", borderRadius:8, padding:"8px 14px", fontSize:11.5, fontWeight:700,
            cursor:"pointer", fontFamily:FONT,
          }}>
            <svg viewBox="0 0 20 20" fill="none" stroke="#FFE600" strokeWidth="1.8" width="13" height="13">
              <path d="M3 10a7 7 0 1013.93-1.37" strokeLinecap="round"/>
              <polyline points="17,4 17,9 12,9" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Réinitialiser
          </button>

          {/* Compteur résultats */}
          <div style={{ marginLeft:"auto", fontSize:10, color:"rgba(255,255,255,.38)", fontWeight:600 }}>
            {filtered.length} texte{filtered.length !== 1 ? "s" : ""}
          </div>
        </div>
      </div>

      {/* ── Table ── */}
      <div style={{ flex:1, overflow:"auto" }}>
        <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
          <thead style={{ position:"sticky", top:0, zIndex:10 }}>
            <tr>
              {[
                { col:"date",   label:"Date de publication", w:"130px" },
                { col:"type",   label:"Type de texte",       w:"120px" },
                { col:"titre",  label:"Titre du texte",      w:"auto"  },
                { col:"source", label:"Source",              w:"90px"  },
                { col:"annee",  label:"Année",               w:"70px"  },
                { col:null,     label:"Actions",             w:"130px" },
              ].map((h, i) => (
                <th key={i} style={{ ...thStyle(h.col), width:h.w, paddingLeft: i===0?"32px":14, paddingRight: i===5?"32px":14 }}
                  onClick={() => h.col && toggleSort(h.col)}>
                  {h.label}{h.col && <SortIcon col={h.col}/>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paginated.map((doc, i) => (
              <tr key={doc.id}
                style={{ background: i%2===0 ? "white" : "#FAFAFA", transition:"background .1s", cursor:"default" }}
                onMouseEnter={e => e.currentTarget.style.background = "#FFF9E6"}
                onMouseLeave={e => e.currentTarget.style.background = i%2===0 ? "white" : "#FAFAFA"}
              >
                <td style={{ padding:"12px 14px 12px 32px", color:G, whiteSpace:"nowrap", borderBottom:"1px solid #F3F4F6" }}>
                  <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke={G} strokeWidth="1.5" width="13" height="13">
                      <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
                    </svg>
                    {doc.date}
                  </div>
                </td>
                <td style={{ padding:"12px 14px", borderBottom:"1px solid #F3F4F6" }}>
                  <TypeBadge type={doc.type}/>
                </td>
                <td style={{ padding:"12px 14px", borderBottom:"1px solid #F3F4F6", color:D, lineHeight:1.45, maxWidth:520 }}>
                  {doc.titre}
                </td>
                <td style={{ padding:"12px 14px", borderBottom:"1px solid #F3F4F6" }}>
                  <SourceLogo src={doc.src}/>
                </td>
                <td style={{ padding:"12px 14px", borderBottom:"1px solid #F3F4F6", color:D, fontWeight:600 }}>
                  {doc.annee}
                </td>
                <td style={{ padding:"12px 32px 12px 14px", borderBottom:"1px solid #F3F4F6" }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <button style={{ fontSize:11, fontWeight:700, color:D, background:"none", border:"1px solid #E5E7EB", borderRadius:6, padding:"4px 10px", cursor:"pointer", whiteSpace:"nowrap" }}>
                      Consulter
                    </button>
                    <button style={{ width:26, height:26, borderRadius:6, border:"1px solid #E5E7EB", background:"white", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center" }}>
                      <svg viewBox="0 0 16 16" fill="none" stroke={G} strokeWidth="1.5" width="12" height="12">
                        <path d="M10 2h4v4M14 2L9 7M3 7v7h10v-4" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                    <button style={{ width:26, height:26, borderRadius:6, border:"1px solid #E5E7EB", background:"white", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center" }}>
                      <svg viewBox="0 0 16 16" fill="none" stroke={G} strokeWidth="1.5" width="12" height="12">
                        <path d="M8 2v9M4 8l4 4 4-4M2 14h12" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {paginated.length === 0 && (
              <tr>
                <td colSpan={6} style={{ padding:"48px 0", textAlign:"center", color:G, fontSize:13 }}>
                  Aucun texte ne correspond aux filtres sélectionnés
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* ── Pagination ── */}
      <div style={{ padding:"12px 32px", borderTop:"1px solid #E5E7EB", flexShrink:0, display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        <div style={{ fontSize:12, color:G }}>
          Affichage de {filtered.length > 0 ? (page-1)*perPage+1 : 0} à {Math.min(page*perPage, filtered.length)} sur {filtered.length} textes
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:6 }}>
          {/* Prev */}
          <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page===1}
            style={{ width:30, height:30, borderRadius:7, border:"1px solid #E5E7EB", background:"white", cursor:page===1?"default":"pointer", display:"flex", alignItems:"center", justifyContent:"center", opacity:page===1?0.4:1 }}>
            <svg viewBox="0 0 16 16" fill="none" width="10" height="10">
              <path d="M10 4L6 8l4 4" stroke={D} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          {/* Page numbers */}
          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
            const p = totalPages <= 5 ? i+1 : Math.min(Math.max(page - 2 + i, 1), totalPages - 4 + i);
            return (
              <button key={p} onClick={() => setPage(p)}
                style={{ width:30, height:30, borderRadius:7, border: p===page ? "none" : "1px solid #E5E7EB", background: p===page ? D : "white", color: p===page ? Y : D, cursor:"pointer", fontSize:12, fontWeight: p===page ? 800 : 500, display:"flex", alignItems:"center", justifyContent:"center" }}>
                {p}
              </button>
            );
          })}

          {/* Next */}
          <button onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={page===totalPages}
            style={{ width:30, height:30, borderRadius:7, border:"1px solid #E5E7EB", background:"white", cursor:page===totalPages?"default":"pointer", display:"flex", alignItems:"center", justifyContent:"center", opacity:page===totalPages?0.4:1 }}>
            <svg viewBox="0 0 16 16" fill="none" width="10" height="10">
              <path d="M6 4l4 4-4 4" stroke={D} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        {/* Per page */}
        <div style={{ display:"flex", alignItems:"center", gap:8, fontSize:12, color:G }}>
          <span>Afficher</span>
          <Select value={String(perPage)} onChange={v => { setPerPage(Number(v)); setPage(1); }} options={["8","10","15","20","30"]}/>
          <span>par page</span>
        </div>
      </div>
    </div>
  );
}
