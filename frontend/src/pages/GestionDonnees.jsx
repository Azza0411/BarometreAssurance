import { useState, useEffect, useCallback, useRef } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

const DARK   = "#2E2E38";
const YELLOW = "#FFE600";
const BG     = "#F2F5FB";
const BORDER = "#DDE2EC";
const MUTED  = "#6B7280";

const SOURCE_LABELS = {
  CMF: "CMF — États financiers", FTUSA: "FTUSA — Rapports annuels",
  CGA: "CGA — Rapports annuels", BVMT: "BVMT — Bourse", INS: "INS — Portail socioéconomique",
  ENQUETE: "Enquête de marché",
};

function Card({ children, style }) {
  return (
    <div style={{
      background: "#fff", borderRadius: 14, border: `1px solid ${BORDER}`,
      boxShadow: "0 2px 10px rgba(0,0,0,0.05)", padding: 22, ...style,
    }}>{children}</div>
  );
}

function SectionTitle({ eyebrow, title, desc }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: "#9CA3AF", letterSpacing: "1.5px", textTransform: "uppercase", marginBottom: 4 }}>
        {eyebrow}
      </div>
      <h2 style={{ margin: 0, fontSize: 17, fontWeight: 800, color: DARK }}>{title}</h2>
      {desc && <p style={{ margin: "4px 0 0", fontSize: 12.5, color: MUTED, maxWidth: 720 }}>{desc}</p>}
    </div>
  );
}

function Pill({ active, onClick, children }) {
  return (
    <button onClick={onClick} style={{
      padding: "6px 13px", borderRadius: 20, fontSize: 12, fontWeight: 600, cursor: "pointer",
      border: active ? `1.5px solid ${DARK}` : `1px solid ${BORDER}`,
      background: active ? DARK : "#fff",
      color: active ? YELLOW : "#374151",
      transition: "all .12s",
    }}>{children}</button>
  );
}

/* ═══════════════════════════ Collecte ═══════════════════════════ */
function CollecteSection() {
  const [statut, setStatut] = useState(null);
  const [lancement, setLancement] = useState(false);
  const [erreur, setErreur] = useState(null);
  const pollRef = useRef(null);

  const fetchStatut = useCallback(() => {
    fetch(`${API}/api/gestion-donnees/statut-collecte`)
      .then(r => r.json())
      .then(setStatut)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchStatut();
    return () => clearInterval(pollRef.current);
  }, [fetchStatut]);

  useEffect(() => {
    if (statut?.en_cours) {
      pollRef.current = setInterval(fetchStatut, 4000);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [statut?.en_cours, fetchStatut]);

  const lancer = () => {
    setErreur(null);
    setLancement(true);
    fetch(`${API}/api/gestion-donnees/lancer-collecte`, { method: "POST" })
      .then(async r => {
        if (r.status === 409) { setErreur("Une collecte est déjà en cours."); return; }
        if (!r.ok) { setErreur("Échec du lancement."); return; }
        fetchStatut();
      })
      .catch(() => setErreur("Échec du lancement (API injoignable)."))
      .finally(() => setLancement(false));
  };

  const derniere = statut?.derniere_execution;
  const enCours = statut?.en_cours;

  return (
    <Card>
      <SectionTitle
        eyebrow="Étape 1"
        title="Collecte des données"
        desc="Relance le scraping des 5 sources (CMF, FTUSA, CGA, INS, BVMT) et l'extraction des indicateurs qui en découle. Traitement en tâche de fond — cette page reste utilisable pendant l'exécution."
      />
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <button
          onClick={lancer}
          disabled={enCours || lancement}
          style={{
            padding: "12px 22px", borderRadius: 10, fontSize: 13.5, fontWeight: 700,
            cursor: enCours ? "not-allowed" : "pointer", border: "none",
            background: enCours ? "#D1D5DB" : DARK, color: enCours ? "#6B7280" : YELLOW,
            display: "flex", alignItems: "center", gap: 8,
          }}>
          {enCours ? "⏳ Collecte en cours…" : "▶ Lancer une nouvelle collecte"}
        </button>

        <div style={{ fontSize: 12, color: MUTED }}>
          {enCours ? (
            <span>Démarrée à {statut?.demarree_le?.split("T")[1] ?? "…"} — les 5 sources sont interrogées avec reprise automatique en cas d'échec (~quelques minutes).</span>
          ) : derniere ? (
            <span>
              Dernière exécution : <b style={{ color: DARK }}>{derniere.ts?.replace("T", " ").slice(0, 16)}</b>
              {" · "}durée {derniere.duration_s ?? "?"}s
              {derniere.failed_sources?.length
                ? <span style={{ color: "#C8102E", fontWeight: 700 }}> · {derniere.failed_sources.length} source(s) en échec</span>
                : <span style={{ color: "#16A34A", fontWeight: 700 }}> · toutes sources OK</span>}
            </span>
          ) : (
            <span>Aucune exécution enregistrée pour l'instant.</span>
          )}
        </div>
      </div>
      {erreur && <div style={{ marginTop: 10, fontSize: 12, color: "#C8102E", fontWeight: 600 }}>{erreur}</div>}
    </Card>
  );
}

/* ═══════════════════════════ Documents ═══════════════════════════ */
function DocumentsSection() {
  const [docs, setDocs] = useState(null);
  const [source, setSource] = useState("TOUS");
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/documents`).then(r => r.json()).then(setDocs).catch(() => setDocs([]));
  }, []);

  const sources = docs ? ["TOUS", ...Array.from(new Set(docs.map(d => d.source)))] : ["TOUS"];
  const filtered = (docs ?? []).filter(d =>
    (source === "TOUS" || d.source === source) &&
    (!search || `${d.code ?? ""} ${d.nom_entreprise ?? ""} ${d.nom_pdf}`.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <Card>
      <SectionTitle
        eyebrow="Étape 2"
        title="Documents scrapés"
        desc={`${docs?.length ?? "…"} documents en base. "Ouvrir" affiche le PDF réellement stocké en local (le lien externe peut avoir changé ou disparu depuis le scraping) ; sinon, le lien source d'origine est proposé.`}
      />
      <div style={{ display: "flex", gap: 8, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        {sources.map(s => (
          <Pill key={s} active={source === s} onClick={() => setSource(s)}>
            {s === "TOUS" ? "Toutes sources" : (SOURCE_LABELS[s] ?? s)}
          </Pill>
        ))}
        <input
          placeholder="Rechercher (société, fichier…)"
          value={search} onChange={e => setSearch(e.target.value)}
          style={{ marginLeft: "auto", padding: "7px 14px", borderRadius: 8, border: `1px solid ${BORDER}`, fontSize: 12, width: 220 }}
        />
      </div>

      <div style={{ maxHeight: 360, overflowY: "auto", border: `1px solid ${BORDER}`, borderRadius: 10 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
          <thead style={{ position: "sticky", top: 0, background: "#F8F9FC", zIndex: 1 }}>
            <tr>
              {["Source", "Société", "Fichier", "Année", "Fichier local", ""].map((h, i) => (
                <th key={i} style={{ textAlign: "left", padding: "9px 12px", fontWeight: 700, color: "#6B7280", borderBottom: `1px solid ${BORDER}` }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!docs ? (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: "center", color: MUTED }}>Chargement…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={6} style={{ padding: 24, textAlign: "center", color: MUTED }}>Aucun document.</td></tr>
            ) : filtered.map(d => (
              <tr key={d.id} style={{ borderBottom: `1px solid #F0F1F5` }}>
                <td style={{ padding: "8px 12px" }}>{d.source}</td>
                <td style={{ padding: "8px 12px" }}>{d.nom_entreprise ?? "—"}</td>
                <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: 11.5, color: "#4B5563" }}>{d.nom_pdf}</td>
                <td style={{ padding: "8px 12px" }}>{d.annee}</td>
                <td style={{ padding: "8px 12px" }}>
                  {d.fichier_local
                    ? <span style={{ color: "#16A34A", fontWeight: 700 }}>✓ oui</span>
                    : <span style={{ color: "#9CA3AF" }}>— non</span>}
                </td>
                <td style={{ padding: "8px 12px" }}>
                  {d.fichier_local ? (
                    <a href={`${API}/api/gestion-donnees/documents/${d.id}/pdf`} target="_blank" rel="noreferrer"
                       style={{ color: "#2563EB", fontWeight: 600, textDecoration: "none" }}>Ouvrir (local)</a>
                  ) : d.lien ? (
                    <a href={d.lien} target="_blank" rel="noreferrer"
                       style={{ color: "#9CA3AF", fontWeight: 600, textDecoration: "none" }}>Lien source ↗</a>
                  ) : <span style={{ color: "#D1D5DB" }}>—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ═══════════════════════════ Validation Annexe 13 ═══════════════════════════ */
function ValidationSection() {
  const [statut, setStatut] = useState(null);
  const [lancement, setLancement] = useState(false);
  const [erreur, setErreur] = useState(null);
  const pollRef = useRef(null);

  const fetchStatut = useCallback(() => {
    fetch(`${API}/api/gestion-donnees/statut-validation-annexe13`)
      .then(r => r.json())
      .then(setStatut)
      .catch(() => {});
  }, []);

  useEffect(() => {
    fetchStatut();
    return () => clearInterval(pollRef.current);
  }, [fetchStatut]);

  useEffect(() => {
    if (statut?.en_cours) {
      pollRef.current = setInterval(fetchStatut, 3000);
    } else {
      clearInterval(pollRef.current);
    }
    return () => clearInterval(pollRef.current);
  }, [statut?.en_cours, fetchStatut]);

  const lancer = () => {
    setErreur(null);
    setLancement(true);
    fetch(`${API}/api/gestion-donnees/valider-annexe13`, { method: "POST" })
      .then(async r => {
        if (r.status === 409) { setErreur("Une validation est déjà en cours."); return; }
        if (!r.ok) { setErreur("Échec du lancement."); return; }
        fetchStatut();
      })
      .catch(() => setErreur("Échec du lancement (API injoignable)."))
      .finally(() => setLancement(false));
  };

  const enCours = statut?.en_cours;
  const progression = statut?.progression;
  const derniere = statut?.derniere;

  return (
    <Card>
      <SectionTitle
        eyebrow="Étape 3"
        title="Validation Annexe 13"
        desc="Extrait le tableau complet (toutes branches) de chaque document, normalise les libellés de ligne contre le référentiel comptable, vérifie les identités métier (Primes acquises = Primes émises + Variation…) et stocke le résultat validé en base — l'export Excel ci-dessous s'en sert directement (instantané) au lieu de re-lire chaque PDF."
      />
      <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <button
          onClick={lancer}
          disabled={enCours || lancement}
          style={{
            padding: "12px 22px", borderRadius: 10, fontSize: 13.5, fontWeight: 700,
            cursor: enCours ? "not-allowed" : "pointer", border: "none",
            background: enCours ? "#D1D5DB" : DARK, color: enCours ? "#6B7280" : YELLOW,
            display: "flex", alignItems: "center", gap: 8,
          }}>
          {enCours ? "⏳ Validation en cours…" : "▶ Lancer la validation Annexe 13"}
        </button>

        <div style={{ fontSize: 12, color: MUTED }}>
          {enCours ? (
            <span>{progression ? `${progression.fait} / ${progression.total} documents traités…` : "Démarrage…"}</span>
          ) : derniere ? (
            <span>
              Dernière exécution : <b style={{ color: DARK }}>{derniere.terminee_le?.replace("T", " ").slice(0, 16)}</b>
              {" · "}<span style={{ color: "#16A34A", fontWeight: 700 }}>{derniere.ok} validé(s)</span>
              {derniere.page_introuvable ? <span> · {derniere.page_introuvable} sans page Annexe 13 identifiable</span> : null}
              {derniere.erreur ? <span style={{ color: "#C8102E", fontWeight: 700 }}> · {derniere.erreur} erreur(s)</span> : null}
            </span>
          ) : (
            <span>Aucune exécution enregistrée pour l'instant — l'export utilisera l'extraction directe du PDF en attendant.</span>
          )}
        </div>
      </div>
      {erreur && <div style={{ marginTop: 10, fontSize: 12, color: "#C8102E", fontWeight: 600 }}>{erreur}</div>}
    </Card>
  );
}

/* ═══════════════════════════ Export Excel ═══════════════════════════ */
function toggleInSet(set, value) {
  const next = new Set(set);
  next.has(value) ? next.delete(value) : next.add(value);
  return next;
}

function ExportSection() {
  const [opts, setOpts] = useState(null);
  const [tableaux, setTableaux] = useState(new Set());
  const [societes, setSocietes] = useState(new Set());
  const [annees, setAnnees] = useState(new Set());

  useEffect(() => {
    fetch(`${API}/api/gestion-donnees/filtres`).then(r => r.json()).then(setOpts).catch(() => {});
  }, []);

  const buildUrl = () => {
    const p = new URLSearchParams();
    tableaux.forEach(t => p.append("tableau", t));
    societes.forEach(s => p.append("societe", s));
    annees.forEach(a => p.append("annee", a));
    return `${API}/api/gestion-donnees/export.xlsx?${p.toString()}`;
  };

  const resume = () => {
    const t = tableaux.size ? `${tableaux.size} tableau(x)` : "tous les tableaux";
    const s = societes.size ? `${societes.size} société(s)` : "toutes les sociétés";
    const a = annees.size ? Array.from(annees).sort().join(", ") : "toutes les années";
    return `${t} · ${s} · ${a}`;
  };

  return (
    <Card>
      <SectionTitle
        eyebrow="Étape 4"
        title="Export Excel flexible"
        desc={'Ne cochez rien dans un groupe pour dire "tous" — ex. laisser Société et Année vides mais cocher "Annexe 12" exporte l\'Annexe 12 de toutes les compagnies, toutes années confondues.'}
      />

      {!opts ? (
        <div style={{ color: MUTED, fontSize: 12.5 }}>Chargement des filtres…</div>
      ) : (
        <>
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#9CA3AF", marginBottom: 6, textTransform: "uppercase", letterSpacing: ".5px" }}>Tableau</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {opts.tableaux.map(t => (
                <Pill key={t.key} active={tableaux.has(t.key)} onClick={() => setTableaux(s => toggleInSet(s, t.key))}>{t.label}</Pill>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#9CA3AF", marginBottom: 6, textTransform: "uppercase", letterSpacing: ".5px" }}>Société</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", maxHeight: 96, overflowY: "auto" }}>
              {opts.societes.map(s => (
                <Pill key={s.code} active={societes.has(s.code)} onClick={() => setSocietes(x => toggleInSet(x, s.code))}>{s.code}</Pill>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "#9CA3AF", marginBottom: 6, textTransform: "uppercase", letterSpacing: ".5px" }}>Année</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {opts.annees.map(a => (
                <Pill key={a} active={annees.has(a)} onClick={() => setAnnees(s => toggleInSet(s, a))}>{a}</Pill>
              ))}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
            <a href={buildUrl()} style={{
              padding: "12px 22px", borderRadius: 10, fontSize: 13.5, fontWeight: 700,
              background: DARK, color: YELLOW, textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 8,
            }}>⬇ Générer l'export Excel</a>
            <span style={{ fontSize: 12, color: MUTED }}>Sélection actuelle : {resume()}</span>
          </div>
        </>
      )}
    </Card>
  );
}

/* ═══════════════════════════ Page ═══════════════════════════ */
export default function GestionDonnees() {
  return (
    <div style={{ minHeight: "100vh", background: BG, fontFamily: "'Inter', system-ui, sans-serif" }}>
      <div style={{ background: DARK, padding: "20px 32px" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "rgba(255,230,0,.7)", letterSpacing: "2px", textTransform: "uppercase", marginBottom: 4 }}>
            Data Management · EY
          </div>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: "white" }}>Gestion de base de données</h1>
          <p style={{ margin: "4px 0 0", fontSize: 11.5, color: "rgba(255,255,255,.45)" }}>
            Accès à toute la donnée collectée, sans connaissance technique requise — lancer la collecte, consulter les documents, exporter n'importe quel extrait en Excel.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: 20 }}>
        <CollecteSection />
        <DocumentsSection />
        <ValidationSection />
        <ExportSection />
      </div>
    </div>
  );
}
