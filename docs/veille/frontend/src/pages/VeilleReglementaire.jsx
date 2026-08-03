import { useState, useMemo, useEffect, useCallback } from "react";
import PageHeaderBar from "../components/PageHeaderBar";

const Y = "#FFE600", D = "#2E2E38", G = "#747480";
const FONT = "Barlow,system-ui,sans-serif";
const API = "http://localhost:8003";

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

const SOURCES = ["Toutes les sources", "CGA", "FTUSA"];

function TypeBadge({ type }) {
  const s = TYPE_COLORS[type] || { bg:"#F5F5F5", color:G, border:"#E5E7EB" };
  return (
    <span style={{ fontSize:9.5, fontWeight:700, padding:"3px 10px", borderRadius:20, background:s.bg, color:s.color, border:`1px solid ${s.border}`, whiteSpace:"nowrap" }}>
      {type}
    </span>
  );
}

function SourceLabel({ src }) {
  return <span style={{ fontSize:11, fontWeight:700, color:D }}>{src}</span>;
}

function Select({ value, onChange, options, dark = false }) {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ position:"relative" }}>
      <button
        onClick={() => setOpen(o => !o)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        style={{
          display:"flex", alignItems:"center", gap:8,
          background: dark ? "rgba(255,255,255,.08)" : "white",
          border: dark ? "1px solid rgba(255,255,255,.18)" : "1px solid #E5E7EB",
          borderRadius:8, padding:"8px 12px",
          fontSize:12, fontWeight:500,
          color: dark ? "white" : D,
          cursor:"pointer", fontFamily:FONT, outline:"none",
          minWidth:140, justifyContent:"space-between",
          whiteSpace:"nowrap",
        }}
      >
        <span style={{ overflow:"hidden", textOverflow:"ellipsis", maxWidth:160 }}>{value}</span>
        <svg viewBox="0 0 12 12" fill="none" width="10" height="10" style={{ flexShrink:0, opacity:.6, transform: open ? "rotate(180deg)" : "none", transition:"transform .15s" }}>
          <path d="M2.5 4.5L6 8l3.5-3.5" stroke={dark ? "white" : G} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      {open && (
        <div style={{
          position:"absolute", top:"calc(100% + 4px)", left:0, zIndex:500,
          background:"white", border:"1px solid #E5E7EB", borderRadius:10,
          boxShadow:"0 8px 24px rgba(0,0,0,.14)", minWidth:"100%", overflow:"hidden",
        }}>
          {options.map(o => (
            <div
              key={o}
              onMouseDown={() => { onChange(o); setOpen(false); }}
              style={{
                padding:"9px 14px", fontSize:12, fontWeight: o === value ? 700 : 400,
                color: o === value ? Y : D,
                background: o === value ? D : "white",
                cursor:"pointer", whiteSpace:"nowrap",
              }}
              onMouseEnter={e => { if (o !== value) e.currentTarget.style.background = "#F9FAFB"; }}
              onMouseLeave={e => { if (o !== value) e.currentTarget.style.background = "white"; }}
            >
              {o}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ConsulterModal({ doc, onClose }) {
  if (!doc) return null;
  const s = TYPE_COLORS[doc.type] || { bg:"#F5F5F5", color:G, border:"#E5E7EB" };
  return (
    <div style={{ position:"fixed", inset:0, zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center" }}
         onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div style={{ position:"absolute", inset:0, background:"rgba(0,0,0,.55)", backdropFilter:"blur(4px)" }}/>
      <div style={{
        position:"relative", width:"min(680px,95vw)", maxHeight:"80vh",
        background:"white", borderRadius:16, overflow:"hidden",
        boxShadow:"0 24px 64px rgba(0,0,0,.32)",
        display:"flex", flexDirection:"column",
        fontFamily:FONT,
      }}>
        <div style={{
          background:"linear-gradient(120deg, #13131A 0%, #1E1E2A 35%, #252535 65%, #424242 100%)",
          padding:"24px 28px 20px",
        }}>
          <div style={{ display:"flex", alignItems:"flex-start", gap:10, justifyContent:"space-between" }}>
            <div style={{ flex:1 }}>
              <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:10 }}>
                <span style={{ fontSize:9.5, fontWeight:700, padding:"3px 10px", borderRadius:20,
                  background:s.bg, color:s.color, border:`1px solid ${s.border}` }}>{doc.type}</span>
                <span style={{ fontSize:10, fontWeight:700, color:"rgba(255,255,255,.5)", letterSpacing:"1px" }}>
                  {doc.src}
                </span>
              </div>
              <div style={{ fontSize:15, fontWeight:800, color:"white", lineHeight:1.4 }}>
                {doc.titre}
              </div>
            </div>
            <button onClick={onClose} style={{
              flexShrink:0, width:32, height:32, borderRadius:"50%",
              background:"rgba(255,255,255,.10)", border:"none", cursor:"pointer",
              display:"flex", alignItems:"center", justifyContent:"center", color:"white", fontSize:18,
            }}>×</button>
          </div>
        </div>

        <div style={{ flex:1, overflowY:"auto", padding:"24px 28px" }}>
          <div style={{ display:"flex", gap:32, marginBottom:24, flexWrap:"wrap" }}>
            {doc.date && (
              <div>
                <div style={{ fontSize:10, fontWeight:700, color:G, textTransform:"uppercase", letterSpacing:"1.5px", marginBottom:4 }}>Date de publication</div>
                <div style={{ fontSize:13, fontWeight:600, color:D }}>{doc.date}</div>
              </div>
            )}
            {doc.annee && (
              <div>
                <div style={{ fontSize:10, fontWeight:700, color:G, textTransform:"uppercase", letterSpacing:"1.5px", marginBottom:4 }}>Année</div>
                <div style={{ fontSize:13, fontWeight:600, color:D }}>{doc.annee}</div>
              </div>
            )}
            <div>
              <div style={{ fontSize:10, fontWeight:700, color:G, textTransform:"uppercase", letterSpacing:"1.5px", marginBottom:4 }}>Source</div>
              <div style={{ fontSize:13, fontWeight:600, color:D }}>{doc.src === "CGA" ? "Comité Général des Assurances" : "Fédération Tunisienne des Sociétés d'Assurance"}</div>
            </div>
          </div>

          <div style={{ padding:"16px 20px", background:"#F9FAFB", borderRadius:10, border:"1px solid #E5E7EB", marginBottom:20 }}>
            <div style={{ fontSize:11, fontWeight:700, color:G, textTransform:"uppercase", letterSpacing:"1.5px", marginBottom:8 }}>À propos de ce texte</div>
            <p style={{ fontSize:13, color:D, lineHeight:1.65, margin:0 }}>
              {doc.type === "Code"
                ? "Document fondateur du secteur des assurances tunisien. Rassemble l'ensemble des dispositions législatives régissant les activités d'assurance, les intermédiaires, les tarifs et le contrôle prudentiel."
                : doc.type === "Règlement"
                ? "Texte réglementaire émis par le Comité Général des Assurances définissant des règles contraignantes applicables aux entreprises d'assurance et aux intermédiaires opérant en Tunisie."
                : doc.type === "Décision"
                ? "Décision administrative prise par le CGA dans l'exercice de ses attributions de supervision et de régulation du marché des assurances."
                : doc.type === "Circulaire"
                ? "Circulaire à caractère interprétatif ou prescriptif adressée aux professionnels du secteur par l'autorité de contrôle."
                : "Texte officiel publié par une institution de régulation du marché des assurances tunisien."}
            </p>
          </div>
        </div>

        <div style={{ padding:"16px 28px", borderTop:"1px solid #E5E7EB", display:"flex", gap:10, flexShrink:0 }}>
          <a href={doc.url} target="_blank" rel="noreferrer" style={{
            flex:1, display:"flex", alignItems:"center", justifyContent:"center", gap:7,
            background:D, color:Y, border:"none", borderRadius:8,
            padding:"10px 16px", fontSize:12, fontWeight:800,
            cursor:"pointer", textDecoration:"none",
          }}>
            <svg viewBox="0 0 16 16" fill="none" stroke={Y} strokeWidth="1.8" width="13" height="13">
              <path d="M6 3H3a1 1 0 00-1 1v9a1 1 0 001 1h10a1 1 0 001-1v-3" strokeLinecap="round"/>
              <path d="M10 2h4v4M14 2L9 7" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Ouvrir la source
          </a>
          {doc.pdf_url && (
            <button
              onClick={() => window.open(`${API}/api/pdf-proxy?url=${encodeURIComponent(doc.pdf_url)}`, "_blank")}
              style={{
                flex:1, display:"flex", alignItems:"center", justifyContent:"center", gap:7,
                background:"white", color:D, border:"1px solid #E5E7EB", borderRadius:8,
                padding:"10px 16px", fontSize:12, fontWeight:800, cursor:"pointer",
              }}>
              <svg viewBox="0 0 16 16" fill="none" stroke={D} strokeWidth="1.8" width="13" height="13">
                <path d="M8 2v9M4 8l4 4 4-4M2 14h12" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Télécharger le PDF
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VeilleReglementaire() {
  const [docs,         setDocs]         = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [refreshing,   setRefreshing]   = useState(false);
  const [modalDoc,     setModalDoc]     = useState(null);
  const [srcFilter,    setSrcFilter]    = useState("Toutes les sources");
  const [typeFilter,   setTypeFilter]   = useState("Tous les types");
  const [anneeFilter,  setAnneeFilter]  = useState("Toutes les années");
  const [search,       setSearch]       = useState("");
  const [page,         setPage]         = useState(1);
  const [perPage,      setPerPage]      = useState(10);
  const [sortCol,      setSortCol]      = useState("date");
  const [sortAsc,      setSortAsc]      = useState(false);

  const loadDocs = useCallback(() => {
    setLoading(true);
    fetch(`${API}/api/veille-reglementaire`)
      .then(r => r.ok ? r.json() : [])
      .then(data => {
        setDocs(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => { loadDocs(); }, [loadDocs]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetch(`${API}/api/veille-reglementaire/refresh`, { method: "POST" })
      .then(r => r.json())
      .then(data => { setDocs(Array.isArray(data.docs) ? data.docs : docs); })
      .catch(() => {})
      .finally(() => { setRefreshing(false); loadDocs(); });
  };

  const TYPES_LIST = useMemo(() => {
    const types = Array.from(new Set(docs.map(d => d.type).filter(Boolean))).sort();
    return ["Tous les types", ...types];
  }, [docs]);

  const ANNEES_LIST = useMemo(() => {
    const annees = Array.from(new Set(docs.map(d => d.annee).filter(Boolean))).sort((a,b) => b-a).map(String);
    return ["Toutes les années", ...annees];
  }, [docs]);

  const parseDate = s => {
    if (!s) return "0000/00/00";
    const parts = s.split("/");
    if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
    return s + "/00/00";
  };

  const filtered = useMemo(() => {
    let list = docs.filter(d => {
      if (srcFilter !== "Toutes les sources" && d.src !== srcFilter) return false;
      if (typeFilter !== "Tous les types" && d.type !== typeFilter) return false;
      if (anneeFilter !== "Toutes les années" && String(d.annee) !== anneeFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!(d.titre || "").toLowerCase().includes(q)) return false;
      }
      return true;
    });

    list = [...list].sort((a, b) => {
      let cmp = 0;
      if (sortCol === "date")   cmp = parseDate(a.date).localeCompare(parseDate(b.date));
      if (sortCol === "type")   cmp = (a.type || "").localeCompare(b.type || "");
      if (sortCol === "titre")  cmp = (a.titre || "").localeCompare(b.titre || "");
      if (sortCol === "source") cmp = (a.src || "").localeCompare(b.src || "");
      if (sortCol === "annee")  cmp = (a.annee || 0) - (b.annee || 0);
      return sortAsc ? cmp : -cmp;
    });

    return list;
  }, [docs, srcFilter, typeFilter, anneeFilter, search, sortCol, sortAsc]);

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

  const thStyle = () => ({
    fontSize:11, fontWeight:700, color:"#374151", textAlign:"left",
    padding:"11px 14px", background:"#F9FAFB", borderBottom:"1px solid #E5E7EB",
    cursor:"pointer", userSelect:"none", whiteSpace:"nowrap",
  });

  return (
    <>
    <style>{`@keyframes spin-veille { to { transform: rotate(360deg); } }`}</style>
    {modalDoc && <ConsulterModal doc={modalDoc} onClose={() => setModalDoc(null)}/>}
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

      <div style={{
        background:"linear-gradient(120deg, #13131A 0%, #1E1E2A 25%, #252535 55%, #424242 80%, #696969 100%)",
        padding:"14px 32px", flexShrink:0,
        boxShadow:"0 2px 12px rgba(10,10,20,.3)",
      }}>
        <div style={{ display:"flex", alignItems:"center", gap:10, flexWrap:"wrap" }}>
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

          <div style={{ width:1, height:32, background:"rgba(255,255,255,.10)", flexShrink:0 }}/>

          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <div style={{ fontSize:7.5, fontWeight:700, color:"rgba(255,255,255,.38)", textTransform:"uppercase", letterSpacing:"2px" }}>Source</div>
            <Select value={srcFilter} onChange={v => { setSrcFilter(v); setPage(1); }} options={SOURCES} dark/>
          </div>

          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <div style={{ fontSize:7.5, fontWeight:700, color:"rgba(255,255,255,.38)", textTransform:"uppercase", letterSpacing:"2px" }}>Type de texte</div>
            <Select value={typeFilter} onChange={v => { setTypeFilter(v); setPage(1); }} options={TYPES_LIST} dark/>
          </div>

          <div style={{ display:"flex", flexDirection:"column", gap:3 }}>
            <div style={{ fontSize:7.5, fontWeight:700, color:"rgba(255,255,255,.38)", textTransform:"uppercase", letterSpacing:"2px" }}>Année</div>
            <Select value={anneeFilter} onChange={v => { setAnneeFilter(v); setPage(1); }} options={ANNEES_LIST} dark/>
          </div>

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

          <button onClick={handleRefresh} disabled={refreshing} style={{
            marginTop:14, display:"flex", alignItems:"center", gap:6,
            background:"rgba(255,255,255,.06)", border:"1px solid rgba(255,255,255,.15)",
            color:"rgba(255,255,255,.6)", borderRadius:8, padding:"8px 14px", fontSize:11.5, fontWeight:700,
            cursor:refreshing?"not-allowed":"pointer", fontFamily:FONT,
          }}>
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" width="13" height="13"
              style={{ animation: refreshing ? "spin-veille 1s linear infinite" : "none" }}>
              <path d="M3 10a7 7 0 1013.93-1.37" strokeLinecap="round"/>
              <polyline points="17,4 17,9 12,9" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            {refreshing ? "Actualisation…" : "Actualiser"}
          </button>

          <div style={{ marginLeft:"auto", fontSize:10, color:"rgba(255,255,255,.38)", fontWeight:600 }}>
            {filtered.length} texte{filtered.length !== 1 ? "s" : ""}
          </div>
        </div>
      </div>

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
                <th key={i} style={{ ...thStyle(), width:h.w, paddingLeft: i===0?"32px":14, paddingRight: i===5?"32px":14 }}
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
                  <SourceLabel src={doc.src}/>
                </td>
                <td style={{ padding:"12px 14px", borderBottom:"1px solid #F3F4F6", color:D, fontWeight:600 }}>
                  {doc.annee}
                </td>
                <td style={{ padding:"12px 32px 12px 14px", borderBottom:"1px solid #F3F4F6" }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8 }}>
                    <button
                      onClick={() => setModalDoc(doc)}
                      style={{ fontSize:11, fontWeight:700, color:D, background:"none", border:"1px solid #E5E7EB", borderRadius:6, padding:"4px 10px", cursor:"pointer", whiteSpace:"nowrap" }}>
                      Consulter
                    </button>
                    {doc.pdf_url && (
                      <button
                        onClick={() => window.open(`${API}/api/pdf-proxy?url=${encodeURIComponent(doc.pdf_url)}`, "_blank")}
                        title="Télécharger le PDF"
                        style={{ width:26, height:26, borderRadius:6, border:"1px solid #E5E7EB", background:"white", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center" }}>
                        <svg viewBox="0 0 16 16" fill="none" stroke={G} strokeWidth="1.5" width="12" height="12">
                          <path d="M8 2v9M4 8l4 4 4-4M2 14h12" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
            {loading && (
              <tr>
                <td colSpan={6} style={{ padding:"60px 0", textAlign:"center", color:G, fontSize:13 }}>
                  <div style={{ display:"inline-flex", flexDirection:"column", alignItems:"center", gap:12 }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke={G} strokeWidth="2" width="28" height="28"
                      style={{ animation:"spin-veille 1s linear infinite" }}>
                      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4" strokeLinecap="round"/>
                    </svg>
                    Chargement des textes réglementaires…
                  </div>
                </td>
              </tr>
            )}
            {!loading && paginated.length === 0 && (
              <tr>
                <td colSpan={6} style={{ padding:"48px 0", textAlign:"center", color:G, fontSize:13 }}>
                  Aucun texte ne correspond aux filtres sélectionnés
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div style={{ padding:"12px 32px", borderTop:"1px solid #E5E7EB", flexShrink:0, display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        <div style={{ fontSize:12, color:G }}>
          Affichage de {filtered.length > 0 ? (page-1)*perPage+1 : 0} à {Math.min(page*perPage, filtered.length)} sur {filtered.length} textes
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:6 }}>
          <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page===1}
            style={{ width:30, height:30, borderRadius:7, border:"1px solid #E5E7EB", background:"white", cursor:page===1?"default":"pointer", display:"flex", alignItems:"center", justifyContent:"center", opacity:page===1?0.4:1 }}>
            <svg viewBox="0 0 16 16" fill="none" width="10" height="10">
              <path d="M10 4L6 8l4 4" stroke={D} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
            const p = totalPages <= 5 ? i+1 : Math.min(Math.max(page - 2 + i, 1), totalPages - 4 + i);
            return (
              <button key={p} onClick={() => setPage(p)}
                style={{ width:30, height:30, borderRadius:7, border: p===page ? "none" : "1px solid #E5E7EB", background: p===page ? D : "white", color: p===page ? Y : D, cursor:"pointer", fontSize:12, fontWeight: p===page ? 800 : 500, display:"flex", alignItems:"center", justifyContent:"center" }}>
                {p}
              </button>
            );
          })}

          <button onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={page===totalPages}
            style={{ width:30, height:30, borderRadius:7, border:"1px solid #E5E7EB", background:"white", cursor:page===totalPages?"default":"pointer", display:"flex", alignItems:"center", justifyContent:"center", opacity:page===totalPages?0.4:1 }}>
            <svg viewBox="0 0 16 16" fill="none" width="10" height="10">
              <path d="M6 4l4 4-4 4" stroke={D} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:8, fontSize:12, color:G }}>
          <span>Afficher</span>
          <Select value={String(perPage)} onChange={v => { setPerPage(Number(v)); setPage(1); }} options={["8","10","15","20","30"]}/>
          <span>par page</span>
        </div>
      </div>
    </div>
    </>
  );
}
