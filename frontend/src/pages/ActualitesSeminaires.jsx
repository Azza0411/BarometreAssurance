import { useState, useMemo, useEffect, useRef } from "react";
import ReactApexChart from "react-apexcharts";
import PageHeaderBar from "../components/PageHeaderBar";

const RED = "#C8102E", Y = "#FFE600", D = "#2E2E38", G = "#747480";
const FONT = "Barlow,system-ui,sans-serif";

/* ── Données réelles (sources : ilboursa.com · atlas-mag.net · cga.gov.tn) ── */
const ACTU = [
  /* ── ilboursa.com ── */
  { id:1,  src:"ilboursa",  date:"08/07/2026", annee:2026, lieu:"Sfax",   nature:"Marché / Compagnies",       url:"https://www.ilboursa.com/marches/mobilite-electrique-bna-assurances-installe-deux-nouvelles-bornes-de-recharge-a-sfax_62826",
    titre:"BNA Assurances inaugure deux bornes de recharge pour véhicules électriques à Sfax",
    resume:"BNA Assurances a inauguré deux bornes de recharge VE/hybrides devant son siège régional de Sfax, en présence du Gouverneur Mohamed Hajri. Deuxième déploiement après le siège de Tunis (Berges du Lac II). L'initiative s'inscrit dans la stratégie RSE de la compagnie.", une:true },
  { id:2,  src:"ilboursa",  date:"2026",       annee:2026, lieu:"-",      nature:"Marché / Compagnies",       url:"https://www.ilboursa.com/marches/exclusif--assurance-sante-groupe-en-tunisie-treize-ans-de-derive-technique-decryptes_62269",
    titre:"Assurance santé groupe en Tunisie : 14 ans de dérive technique décryptés (rapport Healio)",
    resume:"11 compagnies sur 15 (73%) affichent des résultats techniques négatifs en 2024. Déficit cumulé du secteur : -54 MDT (vs -23 MDT en 2023). Pour 100 DT de primes, le secteur supporte 109 DT de charges. Ratio combiné passé de 96,4% (2011) à 109,3% (2024).", une:false },
  /* ── atlas-mag.net ── */
  { id:3,  src:"atlas-mag", date:"18/05/2023", annee:2023, lieu:"-",      nature:"Publications officielles",  url:"https://www.atlas-mag.net/fr/focus",
    titre:"Histoire du marché tunisien de l'assurance",
    resume:"Analyse de l'évolution du marché depuis 1874 (Phénix Vie) jusqu'à aujourd'hui : réformes structurelles, montée en puissance des acteurs locaux et enjeux de modernisation.", une:false },
  { id:4,  src:"atlas-mag", date:"23/11/2022", annee:2022, lieu:"-",      nature:"Publications officielles",  url:"https://www.atlas-mag.net/fr/fiches-pays",
    titre:"Le marché tunisien de l'assurance en 2021 — Fiche pays",
    resume:"Données 2021 : dépense par habitant 82,4 USD, taux de pénétration 1,7%. Analyse comparative des compagnies (STAR, COMAR, AMI, GAT, ASTREE) et tendances du marché post-Covid.", une:false },
  { id:5,  src:"atlas-mag", date:"30/04/2019", annee:2019, lieu:"-",      nature:"Publications officielles",  url:"https://www.atlas-mag.net/fr/dossiers-speciaux",
    titre:"L'assurance des risques agricoles en Tunisie",
    resume:"Tour d'horizon de la couverture des risques agricoles en Tunisie : rôle de la CTAMA, régimes obligatoires et facultatifs, fonds de mutualité pour calamités naturelles.", une:false },
  { id:6,  src:"atlas-mag", date:"08/01/2018", annee:2018, lieu:"-",      nature:"Publications officielles",  url:"https://www.atlas-mag.net/fr/statistiques-compagnies",
    titre:"Marché de l'assurance au Maghreb : classement 2016 des compagnies",
    resume:"STAR Assurances (11e) et COMAR Assurances (19e) au classement Maghreb 2016. Analyse des primes émises, parts de marché et positionnement des acteurs tunisiens dans la région.", une:false },
  /* ── cga.gov.tn — actes réels vérifiés ── */
  { id:7,  src:"CGA", date:"13/06/2025", annee:2025, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement N°03/2025 : encadrement de l'externalisation des activités d'assurance",
    resume:"Fixe les conditions et modalités des conventions conclues dans le cadre de l'externalisation des activités liées à l'exécution des contrats d'assurance.", une:false },
  { id:8,  src:"CGA", date:"05/06/2025", annee:2025, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement N°02/2025 : plateforme automatisée de collecte de données au CGA",
    resume:"Création d'une plateforme dédiée à la collecte automatique des données transmises par les sociétés d'assurance et de réassurance.", une:false },
  { id:9,  src:"CGA", date:"14/03/2025", annee:2025, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement N°01/2025 : pratiques commerciales dans le secteur des assurances",
    resume:"Encadrement des pratiques commerciales des sociétés d'assurance vis-à-vis des assurés et prospects.", une:false },
  { id:10, src:"CGA", date:"15/09/2023", annee:2023, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement N°01/2023 : traitement des requêtes adressées au CGA",
    resume:"Définit les procédures de traitement et de suivi des requêtes adressées au CGA par les assurés et bénéficiaires.", une:false },
  { id:11, src:"CGA", date:"11/11/2022", annee:2022, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement N°03/2022 : organisation des contrats d'assurance collectifs",
    resume:"Fixe les règles d'organisation des contrats collectifs, conventions cadres et conventions bilatérales dans le secteur.", une:false },
  { id:12, src:"CGA", date:"24/06/2022", annee:2022, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement N°02/2022 : relation courtiers – sociétés d'assurance",
    resume:"Encadrement des rapports entre les courtiers d'assurance et les sociétés : obligations réciproques, rémunération, sinistres délégués.", une:false },
  { id:13, src:"CGA", date:"01/12/2021", annee:2021, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Décision N°01/2021 : méthode de calcul des provisions pour dépréciation des créances",
    resume:"Fixe la base et la méthode de calcul des provisions pour dépréciation des créances sur les assurés et les intermédiaires.", une:false },
  { id:14, src:"CGA", date:"11/02/2021", annee:2021, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement CGA N°01/2021 : obligations de reporting et rapport annuel",
    resume:"Fixe les obligations de reporting périodique et les éléments constitutifs du rapport annuel transmis au CGA.", une:false },
  { id:15, src:"CGA", date:"06/04/2020", annee:2020, lieu:"-", nature:"Coopération institutionnelle", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Avis du Collège CGA : mesures prudentielles Covid-19",
    resume:"Communiqué du Collège du CGA fixant les mesures prudentielles exceptionnelles adoptées en réponse à la crise sanitaire.", une:false },
  { id:16, src:"CGA", date:"19/06/2020", annee:2020, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Décision N°01/2020 : travaux préparatifs pour l'adoption des normes IFRS/IAS",
    resume:"Fixe les travaux préparatoires à engager par les sociétés d'assurance pour l'adoption des normes comptables internationales.", une:false },
  { id:17, src:"CGA", date:"29/04/2019", annee:2019, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement CGA N°01/2019 : procédures de retrait d'agrément des intermédiaires",
    resume:"Précise les procédures et conditions de retrait de l'agrément pour exercer la profession d'intermédiaire d'assurance.", une:false },
  { id:18, src:"CGA", date:"17/10/2018", annee:2018, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement CGA N°04/2018 : notes techniques des contrats d'assurance Vie et Capitalisation",
    resume:"Définit les spécifications obligatoires à insérer dans les notes techniques des contrats d'assurance Vie et de Capitalisation.", une:false },
  { id:19, src:"CGA", date:"02/04/2018", annee:2018, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement CGA N°02/2018 : obligation d'information sur les nominations",
    resume:"Oblige les sociétés à informer le CGA de toute nomination dans leurs structures d'administration, gestion et contrôle.", une:false },
  { id:20, src:"CGA", date:"29/03/2017", annee:2017, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Décision N°24/2017 : méthode de calcul des provisions pour dépréciation",
    resume:"Fixe la méthode de calcul des provisions pour dépréciation des créances dans le secteur des assurances.", une:false },
  { id:21, src:"CGA", date:"13/07/2016", annee:2016, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Décision CGA N°01/2016 : règles de bonne gouvernance des sociétés d'assurance",
    resume:"Définit les règles de bonne gouvernance et de gestion applicables aux sociétés d'assurance et de réassurance.", une:false },
  { id:22, src:"CGA", date:"28/03/2014", annee:2014, lieu:"-", nature:"Réglementation / supervision", url:"https://www.cga.gov.tn/index.php?id=33&L=0",
    titre:"Règlement CGA N°01/2014 : documents constitutifs du rapport annuel (art. 60)",
    resume:"Précise les documents constitutifs du rapport annuel prévu par l'article 60 du code des assurances.", une:false },
];

const NATURES = ["Toutes","Coopération institutionnelle","Réglementation / supervision","Publications officielles","Événements sectoriels","Avis administratifs"];
const ANNEES  = ["Tous", ...Array.from(new Set(ACTU.map(a=>a.annee))).sort((x,y)=>y-x).map(String)];
const PAGE_SIZE = 9;

const NATURE_META = {
  "Coopération institutionnelle":  { bg:"#EBF5FF", color:"#1E40AF", border:"#BFDBFE", accent:"#1E40AF", icon:"🤝" },
  "Réglementation / supervision":  { bg:"#ECFDF5", color:"#065F46", border:"#A7F3D0", accent:"#059669", icon:"⚖️" },
  "Publications officielles":      { bg:"#FFF7ED", color:"#92400E", border:"#FDE68A", accent:"#D97706", icon:"📄" },
  "Événements sectoriels":         { bg:"#F5F3FF", color:"#5B21B6", border:"#DDD6FE", accent:"#7C3AED", icon:"📅" },
  "Avis administratifs":           { bg:"#FFF1F2", color:"#9F1239", border:"#FECDD3", accent:"#E11D48", icon:"📢" },
};

function parseDate(str) {
  const p = str.split("/");
  const months = ["","JAN","FÉV","MAR","AVR","MAI","JUN","JUL","AOU","SEP","OCT","NOV","DÉC"];
  if(p.length === 3) return { day:p[0], month:months[+p[1]]||"", year:p[2], full:str };
  return { day:"—", month:"", year:str, full:str };
}

function NatureBadge({ nature, small }) {
  const s = NATURE_META[nature] || { bg:"#F5F5F5", color:G, border:"#E5E7EB" };
  return (
    <span style={{ fontSize: small ? 8.5 : 9.5, fontWeight:700, padding: small ? "2px 7px" : "3px 10px",
      borderRadius:20, background:s.bg, color:s.color, border:`1px solid ${s.border}`, whiteSpace:"nowrap" }}>
      {nature}
    </span>
  );
}

/* ── KPI card ─────────────────────────────────────────────────── */
function KpiCard({ icon, label, value, sub, accent }) {
  return (
    <div style={{ flex:1, borderRadius:12, padding:"14px 18px", display:"flex", alignItems:"center", gap:14,
      background:"linear-gradient(135deg,#B80C26 0%,#7A0000 100%)",
      boxShadow:"0 4px 16px rgba(184,12,38,.25)", position:"relative", overflow:"hidden" }}>
      <div style={{ position:"absolute", right:-14, top:-14, width:72, height:72, borderRadius:"50%",
        background:"rgba(255,255,255,.06)", pointerEvents:"none" }}/>
      <div style={{ width:44, height:44, borderRadius:10, flexShrink:0, display:"flex",
        alignItems:"center", justifyContent:"center",
        background:"rgba(255,255,255,.15)", border:"1px solid rgba(255,255,255,.22)" }}>
        {icon}
      </div>
      <div style={{ minWidth:0 }}>
        <div style={{ fontSize:9.5, fontWeight:700, color:"rgba(255,255,255,.6)",
          textTransform:"uppercase", letterSpacing:"1.2px", marginBottom:2 }}>{label}</div>
        <div style={{ fontSize: accent ? 20 : 26, fontWeight:900, color: accent || "white", lineHeight:1.1 }}>{value}</div>
        {sub && <div style={{ fontSize:9, color:"rgba(255,255,255,.45)", marginTop:2, lineHeight:1.4,
          maxWidth:200, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>{sub}</div>}
      </div>
    </div>
  );
}

/* ── Carousel À la une ─────────────────────────────────────────── */
const UNE_ITEMS = ACTU.slice(0, 5);

function AlaUne() {
  const [idx, setIdx] = useState(0);
  const [imgOk, setImgOk] = useState(true);
  const item = UNE_ITEMS[idx];
  const recent = ACTU.slice(1, 5);

  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i+1) % UNE_ITEMS.length), 7000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => { setImgOk(true); }, [idx]);

  const d = parseDate(item.date);
  const nm = NATURE_META[item.nature] || {};

  return (
    <div style={{ borderRadius:14, overflow:"hidden", boxShadow:"0 8px 32px rgba(0,0,0,.2)",
      display:"grid", gridTemplateColumns:"1fr 270px", background:D }}>

      {/* Panneau gauche — image + overlay */}
      <div style={{ position:"relative", minHeight:300, overflow:"hidden" }}>
        {/* Image */}
        {item.img && imgOk
          ? <img src={item.img} alt="" onError={()=>setImgOk(false)}
              style={{ width:"100%", height:"100%", objectFit:"cover", position:"absolute", inset:0 }}/>
          : <div style={{ position:"absolute", inset:0,
              background:"linear-gradient(135deg,#0D1B3E 0%,#1A3A6E 40%,#0D1B3E 100%)" }}>
              {/* Motif décoratif */}
              <svg viewBox="0 0 400 300" width="100%" height="100%" style={{ opacity:.12 }}>
                <circle cx="80"  cy="80"  r="120" fill="none" stroke="white" strokeWidth="1"/>
                <circle cx="320" cy="220" r="160" fill="none" stroke="white" strokeWidth="1"/>
                <circle cx="200" cy="150" r="80"  fill="none" stroke="white" strokeWidth=".5"/>
                <line x1="0" y1="150" x2="400" y2="150" stroke="white" strokeWidth=".5"/>
                <line x1="200" y1="0" x2="200" y2="300" stroke="white" strokeWidth=".5"/>
              </svg>
            </div>
        }
        {/* Gradient overlay */}
        <div style={{ position:"absolute", inset:0,
          background:"linear-gradient(to top, rgba(0,0,0,.82) 0%, rgba(0,0,0,.4) 50%, rgba(0,0,0,.15) 100%)" }}/>

        {/* Contenu sur l'image */}
        <div style={{ position:"absolute", inset:0, padding:"22px 26px",
          display:"flex", flexDirection:"column", justifyContent:"flex-end", gap:12 }}>

          {/* Badge "À la une" */}
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:2 }}>
            <span style={{ display:"flex", alignItems:"center", gap:5, fontSize:9, fontWeight:900,
              color:Y, textTransform:"uppercase", letterSpacing:"2px" }}>
              <svg viewBox="0 0 16 16" fill={Y} width="11" height="11">
                <polygon points="8,1 10,6 15,6.5 11,10 12.5,15 8,12 3.5,15 5,10 1,6.5 6,6"/>
              </svg>
              À la une
            </span>
            <NatureBadge nature={item.nature} small/>
          </div>

          {/* Titre */}
          <div style={{ fontSize:19, fontWeight:900, color:"white", lineHeight:1.35,
            textShadow:"0 2px 8px rgba(0,0,0,.5)" }}>{item.titre}</div>

          {/* Résumé */}
          {item.resume && (
            <div style={{ fontSize:11, color:"rgba(255,255,255,.72)", lineHeight:1.6,
              display:"-webkit-box", WebkitLineClamp:2, WebkitBoxOrient:"vertical", overflow:"hidden" }}>
              {item.resume}
            </div>
          )}

          {/* Bas de carte */}
          <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginTop:4 }}>
            <div style={{ display:"flex", alignItems:"center", gap:10 }}>
              <div style={{ textAlign:"center", background:"rgba(255,255,255,.12)",
                borderRadius:8, padding:"5px 10px", backdropFilter:"blur(4px)",
                border:"1px solid rgba(255,255,255,.15)" }}>
                <div style={{ fontSize:20, fontWeight:900, color:"white", lineHeight:1 }}>{d.day}</div>
                <div style={{ fontSize:8, fontWeight:800, color:Y, textTransform:"uppercase", letterSpacing:1 }}>{d.month} {d.year}</div>
              </div>
              {item.lieu && item.lieu !== "-" && (
                <div style={{ display:"flex", alignItems:"center", gap:5, fontSize:10.5, color:"rgba(255,255,255,.6)" }}>
                  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="11" height="11">
                    <path d="M8 1.5a4 4 0 0 1 4 4c0 3-4 9-4 9S4 8.5 4 5.5a4 4 0 0 1 4-4z"/><circle cx="8" cy="5.5" r="1.5"/>
                  </svg>
                  {item.lieu}
                </div>
              )}
            </div>
            <button style={{ display:"flex", alignItems:"center", gap:7, background:Y, border:"none",
              borderRadius:8, padding:"8px 16px", fontWeight:800, fontSize:11.5, color:D,
              cursor:"pointer", fontFamily:FONT }}>
              Lire la suite
              <svg viewBox="0 0 16 16" fill="none" stroke={D} strokeWidth="2.2" width="11" height="11">
                <path d="M3 8h10M9 4l4 4-4 4"/>
              </svg>
            </button>
          </div>

          {/* Dots */}
          <div style={{ display:"flex", gap:5 }}>
            {UNE_ITEMS.map((_,i) => (
              <button key={i} onClick={() => setIdx(i)} style={{
                width: i===idx ? 22 : 7, height:6, borderRadius:3, border:"none", cursor:"pointer",
                background: i===idx ? Y : "rgba(255,255,255,.35)", transition:"all .25s", padding:0 }}/>
            ))}
          </div>
        </div>
      </div>

      {/* Panneau droit — actualités récentes */}
      <div style={{ borderLeft:"1px solid rgba(255,255,255,.08)", display:"flex", flexDirection:"column" }}>
        <div style={{ padding:"14px 16px", borderBottom:"1px solid rgba(255,255,255,.08)" }}>
          <span style={{ fontSize:9, fontWeight:800, textTransform:"uppercase", letterSpacing:"2px",
            color:"rgba(255,255,255,.35)" }}>Actualités récentes</span>
        </div>
        {recent.map((a, i) => {
          const dp = parseDate(a.date);
          const nm2 = NATURE_META[a.nature] || {};
          return (
            <div key={a.id} style={{ padding:"12px 16px",
              borderBottom: i<recent.length-1 ? "1px solid rgba(255,255,255,.07)" : "none",
              display:"flex", gap:11, alignItems:"flex-start", cursor:"pointer", transition:"background .15s" }}
              onMouseEnter={e=>e.currentTarget.style.background="rgba(255,255,255,.05)"}
              onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
              {/* Date bloc */}
              <div style={{ flexShrink:0, textAlign:"center", minWidth:34,
                background:"rgba(255,255,255,.06)", borderRadius:7, padding:"5px 6px",
                border:"1px solid rgba(255,255,255,.08)" }}>
                <div style={{ fontSize:16, fontWeight:900, color:"white", lineHeight:1 }}>{dp.day}</div>
                <div style={{ fontSize:7, fontWeight:800, color:Y, textTransform:"uppercase" }}>{dp.month}</div>
                <div style={{ fontSize:7.5, color:"rgba(255,255,255,.35)" }}>{dp.year}</div>
              </div>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:8, fontWeight:800, textTransform:"uppercase", letterSpacing:"1px",
                  color: nm2.accent ? nm2.accent+"CC" : "rgba(255,255,255,.4)", marginBottom:3 }}>
                  {a.nature}
                </div>
                <div style={{ fontSize:10.5, color:"rgba(255,255,255,.82)", lineHeight:1.4,
                  display:"-webkit-box", WebkitLineClamp:2, WebkitBoxOrient:"vertical", overflow:"hidden" }}>
                  {a.titre}
                </div>
              </div>
              <svg viewBox="0 0 16 16" fill="none" stroke="rgba(255,255,255,.25)" strokeWidth="1.5"
                width="11" height="11" style={{ flexShrink:0, marginTop:3 }}>
                <path d="M6 4l4 4-4 4"/>
              </svg>
            </div>
          );
        })}
        <div style={{ padding:"10px 16px", marginTop:"auto", borderTop:"1px solid rgba(255,255,255,.07)" }}>
          <button style={{ background:"none", border:"none", color:Y, fontWeight:700, fontSize:10.5,
            cursor:"pointer", fontFamily:FONT, display:"flex", alignItems:"center", gap:5 }}>
            Voir toutes les actualités
            <svg viewBox="0 0 16 16" fill="none" stroke={Y} strokeWidth="2" width="11" height="11">
              <path d="M3 8h10M9 4l4 4-4 4"/>
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── News Card ─────────────────────────────────────────────────── */
function NewsCard({ actu }) {
  const d = parseDate(actu.date);
  const nm = NATURE_META[actu.nature] || { accent:"#666", bg:"#F5F5F5", color:"#555", border:"#ddd" };
  const [hov, setHov] = useState(false);

  return (
    <div onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
      style={{ background:"white", borderRadius:12, overflow:"hidden", cursor:"pointer",
        border:"1px solid #EBEBEF", display:"flex", flexDirection:"column",
        boxShadow: hov ? "0 8px 28px rgba(0,0,0,.11)" : "0 2px 8px rgba(0,0,0,.05)",
        transition:"box-shadow .2s, transform .2s",
        transform: hov ? "translateY(-2px)" : "translateY(0)" }}>

      {/* Accent top strip */}
      <div style={{ height:4, background: nm.accent, flexShrink:0 }}/>

      {/* Body */}
      <div style={{ padding:"14px 16px", flex:1, display:"flex", flexDirection:"column", gap:9 }}>
        {/* Nature + date */}
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", gap:6 }}>
          <NatureBadge nature={actu.nature} small/>
          <span style={{ fontSize:9.5, color:G, fontWeight:500, whiteSpace:"nowrap" }}>
            {d.day} {d.month}. {d.year}
          </span>
        </div>

        {/* Titre */}
        <div style={{ fontSize:12, fontWeight:800, color:D, lineHeight:1.45,
          display:"-webkit-box", WebkitLineClamp:3, WebkitBoxOrient:"vertical", overflow:"hidden",
          flex:1 }}>
          {actu.titre}
        </div>

        {/* Résumé */}
        {actu.resume && (
          <div style={{ fontSize:10.5, color:G, lineHeight:1.55,
            display:"-webkit-box", WebkitLineClamp:2, WebkitBoxOrient:"vertical", overflow:"hidden" }}>
            {actu.resume}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{ padding:"9px 16px", borderTop:"1px solid #F0F0F4",
        display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        {actu.lieu && actu.lieu !== "-"
          ? <span style={{ fontSize:9.5, color:G, display:"flex", alignItems:"center", gap:4 }}>
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" width="9" height="9">
                <path d="M8 1.5a3 3 0 0 1 3 3c0 2.5-3 7-3 7s-3-4.5-3-7a3 3 0 0 1 3-3z"/>
              </svg>
              {actu.lieu}
            </span>
          : <span/>
        }
        <span style={{ fontSize:10.5, fontWeight:700, color: hov ? RED : nm.color,
          display:"flex", alignItems:"center", gap:4, transition:"color .15s" }}>
          Lire la suite
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" width="10" height="10">
            <path d="M3 8h10M9 4l4 4-4 4"/>
          </svg>
        </span>
      </div>
    </div>
  );
}

/* ── Page principale ───────────────────────────────────────────── */
export default function ActualitesSeminaires() {
  const [filterNature, setFilterNature] = useState("Toutes");
  const [filterAnnee,  setFilterAnnee]  = useState("Tous");
  const [search,       setSearch]       = useState("");
  const [page,         setPage]         = useState(1);

  const filtered = useMemo(() => ACTU.filter(a => {
    if(filterNature !== "Toutes" && a.nature !== filterNature) return false;
    if(filterAnnee  !== "Tous"   && a.annee  !== +filterAnnee)  return false;
    if(search) {
      const q = search.toLowerCase();
      if(!a.titre.toLowerCase().includes(q) && !a.nature.toLowerCase().includes(q)) return false;
    }
    return true;
  }), [filterNature, filterAnnee, search]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const slice = filtered.slice((page-1)*PAGE_SIZE, page*PAGE_SIZE);
  function reset() { setFilterNature("Toutes"); setFilterAnnee("Tous"); setSearch(""); setPage(1); }

  /* Charts */
  const yearMap = useMemo(() => {
    const m = {};
    ACTU.forEach(a => { m[a.annee] = (m[a.annee]||0)+1; });
    return m;
  }, []);
  const chartYears  = Object.keys(yearMap).sort();
  const chartValues = chartYears.map(y => yearMap[y]);

  const chartAOptions = {
    chart: { type:"bar", toolbar:{show:false}, background:"transparent", fontFamily:FONT },
    plotOptions: { bar:{ borderRadius:4, columnWidth:"55%" } },
    colors: [D],
    dataLabels: { enabled:true, style:{ fontSize:"10px", fontWeight:800, colors:["white"] }, offsetY:-1 },
    xaxis: { categories:chartYears, labels:{ style:{ fontSize:"9px", colors:G } }, axisBorder:{show:false}, axisTicks:{show:false} },
    yaxis: { labels:{ style:{ fontSize:"9px", colors:G } }, title:{ text:"Actualités", style:{ fontSize:"9px", color:G } } },
    grid: { borderColor:"#F0F0F4", strokeDashArray:4 },
    tooltip: { theme:"light" },
  };

  const natureMap = useMemo(() => {
    const m = {};
    ACTU.forEach(a => { m[a.nature] = (m[a.nature]||0)+1; });
    return m;
  }, []);
  const donutLabels = Object.keys(natureMap);
  const donutVals   = donutLabels.map(k => natureMap[k]);
  const DONUT_COLORS = ["#1E40AF","#059669","#D97706","#7C3AED","#E11D48"];

  const chartBOptions = {
    chart: { type:"donut", background:"transparent", fontFamily:FONT },
    labels: donutLabels, colors: DONUT_COLORS,
    legend: { show:false },
    dataLabels: { enabled:true, style:{ fontSize:"10px", fontWeight:800 }, formatter:v=>`${Math.round(v)}%` },
    plotOptions: { pie:{ donut:{ size:"55%", labels:{ show:true,
      total:{ show:true, label:"Total", fontSize:"11px", color:G, formatter:()=>ACTU.length.toString() } } } } },
    tooltip: { theme:"light" }, stroke: { width:2 },
  };

  const inp = { border:"1px solid #E5E7EB", borderRadius:8, padding:"7px 12px",
    fontSize:12, color:D, background:"white", fontFamily:FONT, outline:"none" };

  return (
    <div style={{ height:"calc(100vh - 92px)", background:"#F2F2F4", fontFamily:FONT, color:D, display:"flex", flexDirection:"column", overflow:"hidden" }}>

      <PageHeaderBar title="Actualités & Séminaires" />

      {/* ── Corps scrollable ── */}
      <div style={{ flex:1, overflowY:"auto", padding:"16px 28px", display:"flex", flexDirection:"column", gap:12 }}>

      {/* ── KPI row ── */}
      <div style={{ display:"flex", gap:12, marginBottom:18 }}>
        <KpiCard label="Actualités recensées" value={ACTU.length} sub="publications"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.6" width="20" height="20"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="16" y2="17"/></svg>}/>
        <KpiCard label="Période visible" value="2018 – 2024" sub="7 années"
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.6" width="20" height="20"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>}/>
        <KpiCard label="Dernière actualité publiée" value={ACTU[0].date} accent={Y}
          sub={ACTU[0].titre}
          icon={<svg viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.6" width="20" height="20"><circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/></svg>}/>
      </div>

      {/* ── Filtres ── */}
      <div style={{ background:"white", border:"1px solid #E5E7EB", borderRadius:12,
        padding:"11px 16px", display:"flex", alignItems:"center", gap:10, marginBottom:16,
        boxShadow:"0 1px 4px rgba(0,0,0,.04)", flexWrap:"wrap" }}>
        <span style={{ display:"flex", alignItems:"center", gap:5, color:G, fontSize:11, fontWeight:700, flexShrink:0 }}>
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" width="13" height="13"><path d="M3 5h14M6 10h8M9 15h2"/></svg>
          Filtres
        </span>
        <div style={{ width:1, height:20, background:"#E5E7EB", flexShrink:0 }}/>
        <div style={{ position:"relative" }}>
          <select value={filterAnnee} onChange={e=>{setFilterAnnee(e.target.value);setPage(1);}}
            style={{ ...inp, appearance:"none", cursor:"pointer", paddingRight:26 }}>
            {ANNEES.map(a=><option key={a} value={a}>{a==="Tous"?"Année — Tous":a}</option>)}
          </select>
          <svg viewBox="0 0 16 16" fill="none" stroke={G} strokeWidth="1.8" width="9" height="9"
            style={{ position:"absolute", right:8, top:"50%", transform:"translateY(-50%)", pointerEvents:"none" }}>
            <path d="M4 6l4 4 4-4"/>
          </svg>
        </div>
        <div style={{ position:"relative" }}>
          <select value={filterNature} onChange={e=>{setFilterNature(e.target.value);setPage(1);}}
            style={{ ...inp, appearance:"none", cursor:"pointer", paddingRight:26, minWidth:210 }}>
            {NATURES.map(n=><option key={n} value={n}>{n==="Toutes"?"Nature — Toutes":n}</option>)}
          </select>
          <svg viewBox="0 0 16 16" fill="none" stroke={G} strokeWidth="1.8" width="9" height="9"
            style={{ position:"absolute", right:8, top:"50%", transform:"translateY(-50%)", pointerEvents:"none" }}>
            <path d="M4 6l4 4 4-4"/>
          </svg>
        </div>
        <div style={{ flex:1, minWidth:200, display:"flex", alignItems:"center", gap:7,
          border:"1px solid #E5E7EB", borderRadius:8, padding:"7px 11px", background:"#FAFAFA" }}>
          <svg viewBox="0 0 20 20" fill="none" stroke={G} strokeWidth="1.7" width="13" height="13">
            <circle cx="9" cy="9" r="6"/><path d="M15 15l3 3"/>
          </svg>
          <input value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}}
            placeholder="Rechercher un mot-clé…"
            style={{ border:"none", outline:"none", fontSize:11.5, color:D, background:"transparent", fontFamily:FONT, flex:1 }}/>
        </div>
        <button onClick={reset} style={{ display:"flex", alignItems:"center", gap:5, background:"white",
          border:"1px solid #E5E7EB", color:G, borderRadius:8, padding:"7px 12px", fontSize:11, fontWeight:700,
          cursor:"pointer", fontFamily:FONT, flexShrink:0 }}>
          <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" width="12" height="12">
            <path d="M4 8a6 6 0 1 1 1.5 4M4 4v4h4"/>
          </svg>
          Réinitialiser
        </button>
      </div>

      {/* ── À la une ── */}
      <div style={{ marginBottom:16 }}>
        <AlaUne />
      </div>

      {/* ── Charts ── */}
      <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12, marginBottom:16 }}>
        <div style={{ background:"white", border:"1px solid #E5E7EB", borderRadius:12,
          padding:"16px 18px", boxShadow:"0 1px 4px rgba(0,0,0,.04)" }}>
          <div style={{ fontSize:12.5, fontWeight:800, color:D, marginBottom:4 }}>Actualités par année de publication</div>
          <ReactApexChart type="bar" series={[{name:"Actualités",data:chartValues}]} options={chartAOptions} height={170}/>
        </div>
        <div style={{ background:"white", border:"1px solid #E5E7EB", borderRadius:12,
          padding:"16px 18px", boxShadow:"0 1px 4px rgba(0,0,0,.04)" }}>
          <div style={{ fontSize:12.5, fontWeight:800, color:D, marginBottom:8 }}>Lecture par nature d'actualité</div>
          <div style={{ display:"flex", gap:16, alignItems:"center" }}>
            <ReactApexChart type="donut" series={donutVals} options={chartBOptions} height={170} width={170}/>
            <div style={{ flex:1, display:"flex", flexDirection:"column", gap:7 }}>
              {donutLabels.map((lbl,i)=>(
                <div key={lbl} style={{ display:"flex", alignItems:"center", gap:7 }}>
                  <div style={{ width:9, height:9, borderRadius:3, flexShrink:0, background:DONUT_COLORS[i]}}/>
                  <span style={{ fontSize:10, color:D, flex:1 }}>{lbl}</span>
                  <span style={{ fontSize:11, fontWeight:800, color:DONUT_COLORS[i] }}>{donutVals[i]}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Grille d'actualités ── */}
      <div style={{ marginBottom:6 }}>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", marginBottom:12 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8 }}>
            <span style={{ fontSize:14, fontWeight:900, color:D }}>Toutes les actualités</span>
            <span style={{ fontSize:11, color:G, background:"#F5F5F7", border:"1px solid #E5E7EB",
              borderRadius:20, padding:"2px 10px" }}>{filtered.length}</span>
          </div>
          <span style={{ fontSize:10.5, color:G }}>
            Page {page} sur {pages}
          </span>
        </div>

        {filtered.length === 0
          ? <div style={{ textAlign:"center", padding:"60px 0", color:G, fontSize:13 }}>
              Aucune actualité ne correspond à vos critères.
            </div>
          : <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:12 }}>
              {slice.map(a => <NewsCard key={a.id} actu={a}/>)}
            </div>
        }

        {/* Pagination */}
        {pages > 1 && (
          <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:6, marginTop:16 }}>
            <button onClick={()=>setPage(p=>Math.max(1,p-1))} disabled={page===1}
              style={{ width:32, height:32, borderRadius:8, border:"1px solid #E5E7EB", background:"white",
                cursor:page===1?"default":"pointer", display:"flex", alignItems:"center", justifyContent:"center",
                color:G, opacity:page===1?.35:1 }}>
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" width="10" height="10"><path d="M10 4l-4 4 4 4"/></svg>
            </button>
            {Array.from({length:pages},(_,i)=>i+1).map(p=>(
              <button key={p} onClick={()=>setPage(p)}
                style={{ width:32, height:32, borderRadius:8,
                  border:"1px solid "+(p===page?RED:"#E5E7EB"),
                  background:p===page?RED:"white", color:p===page?"white":G,
                  fontWeight:p===page?700:400, fontSize:12, cursor:"pointer", fontFamily:FONT }}>
                {p}
              </button>
            ))}
            <button onClick={()=>setPage(p=>Math.min(pages,p+1))} disabled={page===pages}
              style={{ width:32, height:32, borderRadius:8, border:"1px solid #E5E7EB", background:"white",
                cursor:page===pages?"default":"pointer", display:"flex", alignItems:"center", justifyContent:"center",
                color:G, opacity:page===pages?.35:1 }}>
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" width="10" height="10"><path d="M6 4l4 4-4 4"/></svg>
            </button>
          </div>
        )}
      </div>
      </div>{/* fin corps scrollable */}
    </div>
  );
}
