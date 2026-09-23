import { useState, useEffect, useRef, useMemo } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
const Y = "#FFE600", D = "#2E2E38", GRIS = "#6B7280", PISTE = "#E6E8EE";

// Deux hauteurs : bandeau "étendu" (anneau de progression, étapes, temps
// restant) pour une vraie collecte (premier lancement / manuelle), bandeau
// "compact" (une ligne) pour le rattrapage au démarrage, ou si l'utilisateur
// l'a réduit.
export const BANNER_COMPACT = 34;
export const BANNER_EXPANDED = 104;
export const BANNER_HEIGHT = BANNER_COMPACT; // compat : ancien nom

// Sondage plus rapproché tant qu'une collecte tourne (avancement x/y et temps
// restant changent en continu), retour à 15s quand rien ne tourne — la
// collecte automatique au premier lancement dure typiquement plusieurs
// dizaines de minutes (voir docs/packaging_portable.md) : un utilisateur qui
// n'est pas prévenu peut légitimement croire l'application cassée devant des
// pages vides (retour utilisateur direct, 2026-09-15).
const POLL_INTERVAL_MS = 15_000;
const POLL_ACTIVE_MS = 3_000;

const TITRE = {
  premier_lancement: "Premier lancement — récupération initiale des données",
  manuelle: "Collecte des données en cours",
  rattrapage: "Mise à jour au démarrage",
};

const AVERTISSEMENT = "Certaines pages peuvent afficher des données incomplètes pendant la collecte.";

/* Sondage partagé — un seul appel dans AppShell (pas un par page/bandeau),
   pour que la mise en page (décalage de la navbar fixe) et le contenu du
   bandeau restent toujours synchronisés sur le même statut. Ajoute `_ui`
   (mode compact choisi par l'utilisateur + instant de la dernière réponse,
   qui sert à faire défiler le compte à rebours entre deux sondages). */
export function useCollecteStatus() {
  const [statut, setStatut] = useState(null);
  const [fetchedAt, setFetchedAt] = useState(Date.now());
  const [compact, setCompact] = useState(() => {
    try { return localStorage.getItem("collecte-compact") === "1"; } catch { return false; }
  });
  const intervalRef = useRef(null);

  const enCours = !!statut?.en_cours;
  useEffect(() => {
    const check = () => {
      fetch(`${API}/api/gestion-donnees/statut-collecte`)
        .then(r => r.json())
        .then(s => { setStatut(s); setFetchedAt(Date.now()); })
        .catch(() => {});
    };
    check();
    intervalRef.current = setInterval(check, enCours ? POLL_ACTIVE_MS : POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, [enCours]);

  const toggle = () => setCompact(c => {
    const next = !c;
    try { localStorage.setItem("collecte-compact", next ? "1" : "0"); } catch { /* stockage indisponible */ }
    return next;
  });

  return useMemo(
    () => (statut ? { ...statut, _ui: { compact, toggle, fetchedAt } } : null),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [statut, compact, fetchedAt],
  );
}

/* Vrai tant que le bandeau doit rester affiché : simplement `en_cours`.
   Retour utilisateur direct 2026-09-16 : le bandeau avait été masqué dès
   que les sources prioritaires étaient prêtes - "je remarque que le bandeau
   a été retiré, ce que je n'ai pas demandé. Je veux voir la progression".
   Il reste donc visible du DÉBUT à la TOUTE FIN de la collecte. */
export function isBandeauVisible(statut) {
  return !!statut?.en_cours;
}

function isCompact(statut) {
  return statut?.source === "rattrapage" || !!statut?._ui?.compact;
}

/* Hauteur réelle du bandeau (0 si masqué) — App.jsx s'en sert pour décaler la
   navbar et le contenu, afin que rien ne se chevauche. */
export function bandeauHeight(statut) {
  if (!isBandeauVisible(statut)) return 0;
  return isCompact(statut) ? BANNER_COMPACT : BANNER_EXPANDED;
}

export function formatReste(s) {
  if (s == null) return null;
  if (s < 60) return "< 1 min";
  const m = Math.ceil(s / 60);
  if (m < 90) return `≈ ${m} min`;
  return `≈ ${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
}

function formatEcoule(s) {
  s = Math.max(0, Math.round(s));
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  const mm = String(m).padStart(2, "0"), ss = String(sec).padStart(2, "0");
  return h > 0 ? `${h} h ${mm}:${ss}` : `${mm}:${ss}`;
}

// Horloge à 1 Hz, uniquement quand le bandeau est affiché.
function useNow(active) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active]);
  return now;
}

/* Anneau de progression globale : le pourcentage est LE chiffre à voir en
   premier. Sans pourcentage (phase de durée inconnue), l'arc tourne. */
function Anneau({ pct, taille = 58 }) {
  const trait = 6, r = (taille - trait) / 2, c = 2 * Math.PI * r, milieu = taille / 2;
  const arc = pct === null ? 0.25 : pct / 100;
  return (
    <svg width={taille} height={taille} viewBox={`0 0 ${taille} ${taille}`}
      style={{ flexShrink: 0, animation: pct === null ? "collecte-tourne 1.2s linear infinite" : "none" }}>
      <circle cx={milieu} cy={milieu} r={r} fill="none" stroke={PISTE} strokeWidth={trait} />
      <circle cx={milieu} cy={milieu} r={r} fill="none" stroke={D} strokeWidth={trait} strokeLinecap="round"
        strokeDasharray={`${arc * c} ${c}`} transform={`rotate(-90 ${milieu} ${milieu})`}
        style={{ transition: "stroke-dasharray .6s ease" }} />
      {pct !== null && (
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" fontSize="15" fontWeight="800" fill={D}>{pct}%</text>
      )}
    </svg>
  );
}

/* Une barre segmentée = une étape par segment : sombre (terminée), jaune
   cerclé de sombre (en cours, remplie selon son propre avancement), grise
   (à venir). Le libellé de chaque étape est dessous. */
function Segments({ etapes, prog }) {
  return (
    <div style={{ display: "flex", gap: 6 }}>
      {etapes.map(e => {
        const enCours = e.statut === "en_cours";
        const terminee = e.statut === "terminee";
        const connu = prog?.total > 0;
        const frac = enCours && connu ? Math.min(prog.done / prog.total, 1) : 0;
        return (
          <div key={e.code} title={e.label} style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              position: "relative", height: 8, borderRadius: 4, overflow: "hidden",
              background: terminee ? D : PISTE,
              boxShadow: enCours ? `0 0 0 1.5px ${D}` : "none",
            }}>
              {enCours && (connu
                ? <div style={{ height: "100%", width: `${frac * 100}%`, background: Y, transition: "width .6s ease" }} />
                : <div style={{ height: "100%", width: "40%", background: Y, animation: "collecte-indetermine 1.6s ease-in-out infinite" }} />)}
            </div>
            <div style={{
              marginTop: 4, fontSize: 10.5, lineHeight: "13px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              fontWeight: enCours ? 800 : 500, color: enCours ? D : terminee ? GRIS : "#A3A9B5",
            }}>{terminee ? "✓ " : ""}{e.label}</div>
          </div>
        );
      })}
    </div>
  );
}

const STYLES = `
  @keyframes collecte-pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .45; transform: scale(.75); } }
  @keyframes collecte-tourne { to { transform: rotate(360deg); } }
  @keyframes collecte-indetermine { 0% { transform: translateX(-100%); } 100% { transform: translateX(300%); } }
`;

/* Bandeau global fixe (toutes pages, y compris Accueil) — position:fixed
   plutôt qu'un élément de flux normal : AppNavbar est déjà fixed/top:0,
   un bandeau "normal" serait donc masqué derrière elle plutôt que de
   s'afficher au-dessus. AppShell décale AppNavbar/le contenu principal de
   `bandeauHeight(statut)` quand ce bandeau est visible pour que rien ne se
   chevauche. Sans indication, des pages entières de "—" sont
   indissociables d'une application cassée ; ce bandeau disparaît
   uniquement quand la collecte est intégralement terminée.

   Design (2026-09-23, à la demande de l'utilisatrice : "plus lisible, plus
   clair, minimaliste, mis en valeur") : bandeau CLAIR, trois informations
   seulement — le pourcentage (anneau), la phase en cours en une phrase, et
   le temps restant (pastille jaune) — plus la barre segmentée des étapes. */
export default function CollecteBanner({ statut }) {
  const visible = isBandeauVisible(statut);
  const now = useNow(visible);
  if (!visible) return null;

  const prog = statut.progression;
  const pct = typeof statut.pourcentage === "number" ? statut.pourcentage : null;
  const compact = isCompact(statut);
  const titre = TITRE[statut.source] || "Collecte des données en cours";
  const etapes = prog?.etapes ?? [];
  const decalage = (now - (statut._ui?.fetchedAt ?? now)) / 1000;
  const ecoule = prog?.ecoule_s != null ? prog.ecoule_s + decalage : null;
  const resteS = prog?.reste_s != null ? Math.max(prog.reste_s - decalage, 0) : null;
  const reste = formatReste(resteS);
  const compteur = prog && prog.total > 0 ? `${Math.min(prog.done, prog.total)} / ${prog.total}${prog.unite ? " " + prog.unite : ""}` : null;
  const etapeCourante = etapes.find(e => e.statut === "en_cours");
  const toggle = statut.source !== "rattrapage" ? statut._ui?.toggle : null;

  const boutonToggle = (libelle, aide) => toggle && (
    <button onClick={toggle} title={aide}
      style={{ flexShrink: 0, background: "transparent", border: "none", color: GRIS, fontSize: 11.5, fontWeight: 600, cursor: "pointer", padding: "2px 4px" }}>
      {libelle}
    </button>
  );

  if (compact) {
    return (
      <div title={AVERTISSEMENT} style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 101, height: BANNER_COMPACT, boxSizing: "border-box",
        display: "flex", alignItems: "center", gap: 10, background: "#fff", color: D, fontSize: 12.5, fontWeight: 600,
        padding: "0 18px", overflow: "hidden", borderBottom: "1px solid #E5E7EB", boxShadow: "0 1px 6px rgba(20,20,40,.08)",
      }}>
        <span style={{ width: 9, height: 9, borderRadius: "50%", background: Y, boxShadow: `0 0 0 2px ${D}`, flexShrink: 0, animation: "collecte-pulse 1.4s ease-in-out infinite" }} />
        <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          <b>{titre}</b>
          {prog?.etape_index && <span style={{ color: GRIS }}> · étape {prog.etape_index}/{prog.etapes_total}</span>}
          {etapeCourante && <span> · {etapeCourante.label}</span>}
          {compteur && <span style={{ color: GRIS }}> {compteur}</span>}
        </span>
        {reste && <span style={{ background: Y, borderRadius: 10, padding: "2px 10px", fontWeight: 800, flexShrink: 0 }}>{reste}</span>}
        {pct !== null && <span style={{ fontWeight: 800, flexShrink: 0 }}>{pct} %</span>}
        {boutonToggle("Agrandir ▾", "Afficher le détail de la collecte")}
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 3, background: PISTE }}>
          <div style={pct !== null
            ? { height: "100%", width: `${pct}%`, background: Y, transition: "width .6s ease" }
            : { height: "100%", width: "35%", background: Y, animation: "collecte-indetermine 1.6s ease-in-out infinite" }} />
        </div>
        <style>{STYLES}</style>
      </div>
    );
  }

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 101, height: BANNER_EXPANDED, boxSizing: "border-box",
      display: "flex", flexDirection: "column", justifyContent: "space-between",
      background: "#fff", color: D, padding: "9px 28px 8px", overflow: "hidden",
      borderBottom: "1px solid #E5E7EB", boxShadow: "0 3px 16px rgba(20,20,40,.10)",
    }}>
      {/* Ligne 1 : pourcentage · ce qui se passe · temps restant */}
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <Anneau pct={pct} />
        <div style={{ flex: 1, minWidth: 0 }} title={AVERTISSEMENT}>
          <div style={{ fontSize: 16.5, fontWeight: 800, letterSpacing: "-.1px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{titre}</div>
          <div style={{ marginTop: 3, fontSize: 13, color: GRIS, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {prog?.etape_index && etapeCourante
              ? <><b style={{ color: D }}>Étape {prog.etape_index} sur {prog.etapes_total} · {etapeCourante.label}</b>
                  {compteur && <span> — {compteur}</span>}
                  {prog.detail && <span> · en ce moment : {prog.detail}</span>}</>
              : (statut.phase_label || "Initialisation…")}
          </div>
        </div>
        <div style={{ textAlign: "right", flexShrink: 0 }}>
          {reste
            ? <div style={{ display: "inline-flex", alignItems: "baseline", gap: 6, background: Y, borderRadius: 14, padding: "4px 14px" }}>
                <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: "-.3px" }}>{reste}</span>
                <span style={{ fontSize: 11.5, fontWeight: 600 }}>restantes</span>
              </div>
            : <div style={{ fontSize: 12.5, fontWeight: 600, color: GRIS }}>Estimation du temps restant…</div>}
          {ecoule !== null && <div style={{ marginTop: 3, fontSize: 11.5, color: GRIS }}>écoulé {formatEcoule(ecoule)}</div>}
        </div>
        {boutonToggle("Réduire ▴", "Réduire le bandeau")}
      </div>

      {/* Ligne 2 : une barre segmentée = les étapes de la collecte */}
      {etapes.length > 0 ? <Segments etapes={etapes} prog={prog} /> : <div style={{ height: 25 }} />}
      <style>{STYLES}</style>
    </div>
  );
}
