import { useState, useEffect, useRef, useMemo } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
const Y = "#FFE600", D = "#2E2E38", OK = "#7EE787";

// Deux hauteurs : bandeau "étendu" (frise d'étapes, temps restant...) pour une
// vraie collecte (premier lancement / manuelle), bandeau "compact" (une ligne)
// pour le rattrapage au démarrage, ou si l'utilisateur l'a réduit.
export const BANNER_COMPACT = 34;
export const BANNER_EXPANDED = 128;
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
  rattrapage: "Mise à jour au démarrage — vérification des données déjà collectées",
};

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

function Barre({ pct, hauteur }) {
  return (
    <div style={{ position: "relative", flex: 1, height: hauteur, borderRadius: hauteur / 2, background: "rgba(255,255,255,.16)", overflow: "hidden" }}>
      <div style={pct !== null
        ? { height: "100%", width: `${pct}%`, background: Y, borderRadius: hauteur / 2, transition: "width .6s ease" }
        : { height: "100%", width: "35%", background: Y, borderRadius: hauteur / 2, animation: "collecte-indetermine 1.6s ease-in-out infinite" }} />
    </div>
  );
}

function Frise({ etapes, prog }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, overflow: "hidden", whiteSpace: "nowrap" }}>
      {etapes.map((e, i) => {
        const enCours = e.statut === "en_cours";
        const terminee = e.statut === "terminee";
        const compteur = enCours && prog?.total > 0 ? ` ${Math.min(prog.done, prog.total)}/${prog.total}` : "";
        return (
          <span key={e.code} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            {i > 0 && <span style={{ color: "rgba(255,255,255,.35)", fontSize: 12 }}>›</span>}
            <span style={{
              padding: "3px 10px", borderRadius: 13, fontSize: 11.5,
              fontWeight: enCours ? 800 : 600,
              background: enCours ? Y : terminee ? "rgba(126,231,135,.14)" : "transparent",
              color: enCours ? D : terminee ? OK : "rgba(255,255,255,.55)",
              border: terminee || enCours ? "1px solid transparent" : "1px dashed rgba(255,255,255,.3)",
              animation: enCours ? "collecte-pulse-chip 1.6s ease-in-out infinite" : "none",
            }}>
              {terminee ? "✓ " : enCours ? "● " : ""}{e.label}{compteur}
            </span>
          </span>
        );
      })}
    </div>
  );
}

/* Bandeau global fixe (toutes pages, y compris Accueil) — position:fixed
   plutôt qu'un élément de flux normal : AppNavbar est déjà fixed/top:0,
   un bandeau "normal" serait donc masqué derrière elle plutôt que de
   s'afficher au-dessus. AppShell décale AppNavbar/le contenu principal de
   `bandeauHeight(statut)` quand ce bandeau est visible pour que rien ne se
   chevauche. Sans indication, des pages entières de "—" sont
   indissociables d'une application cassée ; ce bandeau disparaît
   uniquement quand la collecte est intégralement terminée.

   Retour du responsable pro (2026-09-21/23) : "on ne sait pas où en est la
   collecte". Le bandeau affiche donc : la nature de la collecte, le temps
   écoulé ET le temps restant estimé, une barre globale, la frise des étapes
   (terminée / en cours / à venir) et, pour l'étape en cours, combien
   d'éléments restent et lequel est traité en ce moment. */
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

  const styles = `
    @keyframes collecte-pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: .4; transform: scale(.75); } }
    @keyframes collecte-pulse-chip { 0%, 100% { box-shadow: 0 0 0 0 rgba(255,230,0,.55); } 50% { box-shadow: 0 0 0 4px rgba(255,230,0,0); } }
    @keyframes collecte-indetermine { 0% { transform: translateX(-100%); } 100% { transform: translateX(300%); } }
  `;

  const pastille = (
    <span style={{ width: 9, height: 9, borderRadius: "50%", background: Y, flexShrink: 0, animation: "collecte-pulse 1.4s ease-in-out infinite" }} />
  );

  if (compact) {
    return (
      <div style={{
        position: "fixed", top: 0, left: 0, right: 0, zIndex: 101, height: BANNER_COMPACT, boxSizing: "border-box",
        display: "flex", alignItems: "center", gap: 10, background: D, color: "#fff", fontSize: 12.5, fontWeight: 600,
        padding: "0 16px", overflow: "hidden",
      }}>
        {pastille}
        <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {titre}
          {prog?.etape_index && <span style={{ color: "rgba(255,255,255,.7)" }}> · étape {prog.etape_index}/{prog.etapes_total}</span>}
          {etapeCourante && <span style={{ color: Y, fontWeight: 700 }}> — {etapeCourante.label}</span>}
          {compteur && <span> {compteur}</span>}
          {prog?.detail && <span style={{ color: "rgba(255,255,255,.75)", fontWeight: 500 }}> ({prog.detail})</span>}
        </span>
        {reste && <span style={{ color: Y, fontWeight: 700, flexShrink: 0 }}>reste {reste}</span>}
        {pct !== null && <span style={{ color: Y, fontWeight: 800, flexShrink: 0 }}>{pct} %</span>}
        {toggle && (
          <button onClick={toggle} title="Afficher le détail de la collecte"
            style={{ flexShrink: 0, background: "transparent", border: "1px solid rgba(255,255,255,.4)", color: "#fff", borderRadius: 5, fontSize: 11, padding: "1px 8px", cursor: "pointer" }}>
            Agrandir ▾
          </button>
        )}
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 3, background: "rgba(255,255,255,.18)" }}>
          <div style={pct !== null
            ? { height: "100%", width: `${pct}%`, background: Y, transition: "width .6s ease" }
            : { height: "100%", width: "35%", background: Y, animation: "collecte-indetermine 1.6s ease-in-out infinite" }} />
        </div>
        <style>{styles}</style>
      </div>
    );
  }

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 101, height: BANNER_EXPANDED, boxSizing: "border-box",
      display: "flex", flexDirection: "column", justifyContent: "space-between",
      background: D, color: "#fff", padding: "10px 24px 9px", overflow: "hidden",
      borderBottom: `3px solid ${Y}`,
    }}>
      {/* Ligne 1 : nature de la collecte + temps écoulé / restant */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {pastille}
        <span style={{ fontSize: 15.5, fontWeight: 800, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{titre}</span>
        {ecoule !== null && (
          <span style={{ fontSize: 12.5, color: "rgba(255,255,255,.7)", flexShrink: 0 }}>Écoulé <b style={{ color: "#fff" }}>{formatEcoule(ecoule)}</b></span>
        )}
        <span style={{ fontSize: 15, fontWeight: 800, color: Y, flexShrink: 0 }}>
          {reste ? <>Temps restant estimé {reste}</> : <span style={{ fontWeight: 600, fontSize: 12.5 }}>Estimation du temps restant en cours…</span>}
        </span>
        {toggle && (
          <button onClick={toggle} title="Réduire le bandeau"
            style={{ flexShrink: 0, background: "transparent", border: "1px solid rgba(255,255,255,.4)", color: "#fff", borderRadius: 5, fontSize: 11, padding: "2px 9px", cursor: "pointer" }}>
            Réduire ▴
          </button>
        )}
      </div>

      {/* Ligne 2 : barre globale */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <Barre pct={pct} hauteur={11} />
        <span style={{ width: 46, textAlign: "right", fontSize: 15, fontWeight: 800, color: Y }}>{pct !== null ? `${pct} %` : "…"}</span>
      </div>

      {/* Ligne 3 : frise des étapes */}
      {etapes.length > 0 ? <Frise etapes={etapes} prog={prog} /> : <div style={{ height: 22 }} />}

      {/* Ligne 4 : détail de l'étape en cours */}
      <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 12.5, minHeight: 16 }}>
        <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {prog?.etape_index && <b>Étape {prog.etape_index} sur {prog.etapes_total}</b>}
          {statut.phase_label && <span style={{ color: "rgba(255,255,255,.85)" }}> — {statut.phase_label}</span>}
          {compteur && <span> · <b>{compteur}</b>{prog.restantes != null && <span style={{ color: "rgba(255,255,255,.75)" }}> (reste {prog.restantes})</span>}</span>}
          {prog?.detail && <span style={{ color: "rgba(255,255,255,.75)" }}> · en ce moment : <b style={{ color: "#fff" }}>{prog.detail}</b></span>}
        </span>
        <span style={{ fontSize: 11, color: "rgba(255,255,255,.6)", flexShrink: 0 }}>Certaines pages peuvent afficher des données incomplètes pendant ce temps.</span>
      </div>
      <style>{styles}</style>
    </div>
  );
}
