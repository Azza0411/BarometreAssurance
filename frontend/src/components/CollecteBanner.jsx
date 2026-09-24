import { useState, useEffect, useRef, useMemo } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
const Y = "#FFE600", D = "#2E2E38", GRIS = "#6B7280", PISTE = "#E6E8EE";

// Compat : App.jsx importe encore bandeauHeight / BANNER_HEIGHT pour décaler
// la navbar. Avec le panneau droit flottant, il n'y a plus de décalage vertical.
export const BANNER_COMPACT = 0;
export const BANNER_EXPANDED = 0;
export const BANNER_HEIGHT = 0;
export function bandeauHeight() { return 0; }

const POLL_INTERVAL_MS = 15_000;
const POLL_ACTIVE_MS   = 3_000;

const TITRE = {
  premier_lancement: "Récupération initiale des données",
  manuelle:          "Collecte des données",
  rattrapage:        "Mise à jour au démarrage",
};

export function useCollecteStatus() {
  const [statut, setStatut]     = useState(null);
  const [fetchedAt, setFetchedAt] = useState(Date.now());
  const [collapsed, setCollapsed] = useState(false);
  const intervalRef = useRef(null);

  const enCours = !!statut?.en_cours;
  useEffect(() => {
    const check = () =>
      fetch(`${API}/api/gestion-donnees/statut-collecte`)
        .then(r => r.json())
        .then(s => { setStatut(s); setFetchedAt(Date.now()); })
        .catch(() => {});
    check();
    intervalRef.current = setInterval(check, enCours ? POLL_ACTIVE_MS : POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, [enCours]);

  const toggle = () => setCollapsed(c => !c);

  return useMemo(
    () => (statut ? { ...statut, _ui: { collapsed, toggle, fetchedAt } } : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [statut, collapsed, fetchedAt],
  );
}

export function isBandeauVisible(statut) {
  return !!statut?.en_cours;
}

export function formatReste(s) {
  if (s == null) return null;
  if (s < 60) return "< 1 min";
  const m = Math.ceil(s / 60);
  if (m < 90) return `≈ ${m} min`;
  return `≈ ${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
}

function useNow(active) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

/* Anneau SVG — pourcentage global */
function Anneau({ pct, taille = 52 }) {
  const trait = 5, r = (taille - trait) / 2, c = 2 * Math.PI * r, mid = taille / 2;
  const arc = pct === null ? 0.25 : pct / 100;
  return (
    <svg width={taille} height={taille} viewBox={`0 0 ${taille} ${taille}`}
      style={{ flexShrink: 0, animation: pct === null ? "cp-spin 1.2s linear infinite" : "none" }}>
      <circle cx={mid} cy={mid} r={r} fill="none" stroke={PISTE} strokeWidth={trait} />
      <circle cx={mid} cy={mid} r={r} fill="none" stroke={D} strokeWidth={trait}
        strokeLinecap="round"
        strokeDasharray={`${arc * c} ${c}`}
        transform={`rotate(-90 ${mid} ${mid})`}
        style={{ transition: "stroke-dasharray .5s ease" }} />
      {pct !== null && (
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
          fontSize="13" fontWeight="800" fill={D}>{pct}%</text>
      )}
    </svg>
  );
}

/* Icône d'état par étape */
function Icone({ statut }) {
  if (statut === "terminee") return (
    <svg width={16} height={16} viewBox="0 0 16 16" style={{ flexShrink: 0 }}>
      <circle cx={8} cy={8} r={8} fill={D} />
      <polyline points="4,8 7,11 12,5" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
  if (statut === "en_cours") return (
    <div style={{
      width: 16, height: 16, borderRadius: "50%", flexShrink: 0,
      background: Y, border: `2px solid ${D}`,
      animation: "cp-pulse 1.4s ease-in-out infinite",
    }} />
  );
  return (
    <div style={{ width: 16, height: 16, borderRadius: "50%", flexShrink: 0, border: `2px solid ${PISTE}`, background: "#fff" }} />
  );
}

const CSS = `
  @keyframes cp-spin  { to { transform: rotate(360deg); } }
  @keyframes cp-pulse { 0%,100% { opacity:1; transform:scale(1); } 50% { opacity:.5; transform:scale(.8); } }
  @keyframes cp-slide { 0% { transform:translateX(-100%); } 100% { transform:translateX(300%); } }
`;

/* Panneau flottant droit */
export default function CollecteBanner({ statut }) {
  const visible = isBandeauVisible(statut);
  const now = useNow(visible);
  if (!visible) return null;

  const prog = statut.progression;
  const pct  = typeof statut.pourcentage === "number" ? statut.pourcentage : null;
  const collapsed = !!statut._ui?.collapsed;
  const titre = TITRE[statut.source] || "Collecte des données";
  const etapes = prog?.etapes ?? [];
  const decalage = (now - (statut._ui?.fetchedAt ?? now)) / 1000;
  const resteS   = prog?.reste_s != null ? Math.max(prog.reste_s - decalage, 0) : null;
  const reste    = formatReste(resteS);
  const etapeCourante = etapes.find(e => e.statut === "en_cours");
  const compteur = prog?.total > 0
    ? `${Math.min(prog.done, prog.total)} / ${prog.total}${prog.unite ? " " + prog.unite : ""}`
    : null;

  // Ligne connecteur entre étapes
  const CONN_H = 14;

  return (
    <>
      <style>{CSS}</style>
      <div style={{
        position: "fixed",
        right: 0,
        top: 70,            // sous la navbar (~64px)
        width: collapsed ? 44 : 300,
        zIndex: 200,
        background: "#fff",
        borderRadius: "12px 0 0 12px",
        boxShadow: "-4px 4px 24px rgba(20,20,40,.13)",
        border: `1px solid #E5E7EB`,
        borderRight: "none",
        overflow: "hidden",
        transition: "width .3s ease",
      }}>

        {/* Mode réduit : juste le bouton + % */}
        {collapsed ? (
          <button onClick={statut._ui?.toggle}
            title="Voir la progression de la collecte"
            style={{
              width: 44, height: 80, background: "transparent", border: "none",
              cursor: "pointer", display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center", gap: 6,
            }}>
            <div style={{
              width: 10, height: 10, borderRadius: "50%", background: Y,
              border: `2px solid ${D}`, animation: "cp-pulse 1.4s ease-in-out infinite",
            }} />
            {pct !== null && <span style={{ fontSize: 11, fontWeight: 800, color: D }}>{pct}%</span>}
          </button>
        ) : (
          <div style={{ padding: "14px 16px 16px" }}>

            {/* En-tête : anneau + titre + bouton réduire */}
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
              <Anneau pct={pct} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 800, color: D, lineHeight: "1.3" }}>{titre}</div>
                {reste
                  ? <div style={{ marginTop: 4, display: "inline-flex", alignItems: "baseline", gap: 5,
                      background: Y, borderRadius: 10, padding: "2px 10px" }}>
                      <span style={{ fontSize: 13, fontWeight: 800 }}>{reste}</span>
                      <span style={{ fontSize: 10.5, fontWeight: 600 }}>restantes</span>
                    </div>
                  : <div style={{ marginTop: 4, fontSize: 11.5, color: GRIS }}>Estimation en cours…</div>}
              </div>
              <button onClick={statut._ui?.toggle} title="Réduire"
                style={{ background: "transparent", border: "none", cursor: "pointer",
                  color: GRIS, fontSize: 16, lineHeight: 1, padding: "2px 4px", flexShrink: 0 }}>›</button>
            </div>

            {/* Séparateur */}
            <div style={{ borderTop: `1px solid ${PISTE}`, marginBottom: 12 }} />

            {/* Liste des étapes */}
            <div style={{ display: "flex", flexDirection: "column" }}>
              {etapes.map((e, i) => {
                const enCours  = e.statut === "en_cours";
                const terminee = e.statut === "terminee";
                const connu = prog?.total > 0;
                const frac  = enCours && connu ? Math.min(prog.done / prog.total, 1) : 0;
                const isLast = i === etapes.length - 1;

                return (
                  <div key={e.code}>
                    {/* Étape */}
                    <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                      {/* Colonne icône + trait */}
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
                        <Icone statut={e.statut} />
                        {!isLast && (
                          <div style={{ width: 2, height: CONN_H + (enCours ? 24 : 0),
                            background: terminee ? D : PISTE, marginTop: 2 }} />
                        )}
                      </div>

                      {/* Texte */}
                      <div style={{ flex: 1, minWidth: 0, paddingBottom: isLast ? 0 : CONN_H / 2 }}>
                        <div style={{
                          fontSize: 12.5,
                          fontWeight: enCours ? 800 : terminee ? 600 : 500,
                          color: enCours ? D : terminee ? GRIS : "#B0B7C3",
                          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                        }}>{e.label}</div>

                        {/* Barre + compteur pour l'étape en cours */}
                        {enCours && (
                          <div style={{ marginTop: 5 }}>
                            <div style={{ height: 5, borderRadius: 3, background: PISTE, overflow: "hidden" }}>
                              {(!connu || frac === 0)
                                ? <div style={{ height: "100%", width: "40%", background: Y, animation: "cp-slide 1.6s ease-in-out infinite" }} />
                                : <div style={{ height: "100%", width: `${frac * 100}%`, background: Y, transition: "width .6s ease" }} />
                              }
                            </div>
                            {compteur && (
                              <div style={{ marginTop: 3, fontSize: 11, color: GRIS }}>
                                {compteur}
                                {prog.detail && <span> · {prog.detail}</span>}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

          </div>
        )}
      </div>
    </>
  );
}
