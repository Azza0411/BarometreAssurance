import { useState, useEffect, useRef } from "react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";
const Y = "#FFE600", D = "#2E2E38";

export const BANNER_HEIGHT = 34;

// Intervalle de sondage volontairement court (15s) : la collecte
// automatique au premier lancement dure typiquement plusieurs dizaines
// de minutes (voir docs/packaging_portable.md) — un utilisateur qui
// n'est pas prévenu peut légitimement croire l'application cassée
// devant des pages vides (retour utilisateur direct, 2026-09-15, capture
// d'écran d'"Aperçu marché" entièrement à "—" sans aucune explication).
const POLL_INTERVAL_MS = 15_000;

const SOURCE_LABEL = {
  premier_lancement: "Premier lancement — récupération initiale des données",
  manuelle: "Collecte lancée manuellement",
};

function formatDuree(demarreeLe) {
  if (!demarreeLe) return null;
  const debut = new Date(demarreeLe.replace(" ", "T"));
  if (Number.isNaN(debut.getTime())) return null;
  const minutes = Math.max(0, Math.round((Date.now() - debut.getTime()) / 60000));
  if (minutes < 1) return "à l'instant";
  if (minutes === 1) return "depuis 1 minute";
  return `depuis ${minutes} minutes`;
}

/* Sondage partagé — un seul appel dans AppShell (pas un par page/bandeau),
   pour que la mise en page (décalage de la navbar fixe) et le contenu du
   bandeau restent toujours synchronisés sur le même statut. */
export function useCollecteStatus() {
  const [statut, setStatut] = useState(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const check = () => {
      fetch(`${API}/api/gestion-donnees/statut-collecte`)
        .then(r => r.json())
        .then(setStatut)
        .catch(() => {});
    };
    check();
    intervalRef.current = setInterval(check, POLL_INTERVAL_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  return statut;
}

/* Vrai tant que le bandeau doit rester affiché : simplement `en_cours`.
   Retour utilisateur direct 2026-09-16 : le bandeau avait été masqué dès
   que les sources prioritaires étaient prêtes (voir git history) - "je
   remarque que le bandeau a été retiré, ce que je n'ai pas demandé. Je
   veux voir la progression". Le bandeau reste donc visible du DÉBUT à la
   TOUTE FIN de la collecte (y compris le complément des grilles
   complètes en arrière-plan), affichant l'étape en cours via
   statut.phase_label — jamais masqué avant la fin réelle. App.jsx utilise
   la même fonction pour décaler la navbar, afin que bandeau et mise en
   page restent toujours synchronisés. */
export function isBandeauVisible(statut) {
  return !!statut?.en_cours;
}

/* Bandeau global fixe (toutes pages, y compris Accueil) — position:fixed
   plutôt qu'un élément de flux normal : AppNavbar est déjà fixed/top:0,
   un bandeau "normal" serait donc masqué derrière elle plutôt que de
   s'afficher au-dessus. AppShell décale AppNavbar/le contenu principal de
   BANNER_HEIGHT quand ce bandeau est visible (voir son usage de
   useCollecteStatus) pour que rien ne se chevauche. Sans indication,
   des pages entières de "—" (voir capture d'écran utilisateur) sont
   indissociables d'une application cassée ; ce bandeau disparaît
   uniquement quand la collecte est intégralement terminée. */
export default function CollecteBanner({ statut }) {
  if (!isBandeauVisible(statut)) return null;

  const duree = formatDuree(statut.demarree_le);
  const label = SOURCE_LABEL[statut.source] || "Collecte des données en cours";
  // Message d'étape (scraping, calcul des KPI...) affiché en plus du
  // libellé de source — retour utilisateur direct 2026-09-16 : "on voit
  // que le scraping a commencé, ensuite on voit que le calcul des KPI a
  // également commencé" — un "collecte en cours" générique ne dit rien de
  // la progression réelle pendant l'initialisation (voir
  // pipelines/progress.py, statut.phase_label vient de là).
  const etape = statut.phase_label;

  return (
    <div style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 101,
      height: BANNER_HEIGHT,
      display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
      background: D, color: "#fff", fontSize: 12.5, fontWeight: 600,
      padding: "0 16px",
    }}>
      <span style={{
        width: 8, height: 8, borderRadius: "50%", background: Y, flexShrink: 0,
        animation: "collecte-pulse 1.4s ease-in-out infinite",
      }} />
      <span>
        {label}
        {duree && <span style={{ color: "rgba(255,255,255,.6)" }}> · {duree}</span>}
        {etape && (
          <span style={{ color: Y, fontWeight: 700 }}> — {etape}</span>
        )}
        {" — "}
        <span style={{ color: "rgba(255,255,255,.75)" }}>
          certaines pages peuvent afficher des données incomplètes pendant ce temps.
        </span>
      </span>
      <style>{`
        @keyframes collecte-pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: .4; transform: scale(.75); }
        }
      `}</style>
    </div>
  );
}
