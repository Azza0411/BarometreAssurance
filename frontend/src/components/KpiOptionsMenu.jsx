import { useState, useRef, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";

/* ── Icône + menu à 3 options, partagée par tous les KPI de l'application ──
   Remplace les icônes disparates ajoutées au fil des pages (redirection
   anomalie sur FichesEntreprises, "Voir la source" sur QualiteDonnees,
   bouton dédié sur RapportPipeline...) par UN seul point d'entrée cohérent,
   sur demande explicite de l'utilisateur (2026-08-18) : chaque KPI affiché
   doit donner accès à 3 actions identiques, plutôt que des combinaisons
   différentes selon la page.

   Props :
   - code   : code société (ex: "STAR")
   - kpi    : nom canonique du KPI (storageKey, ex: "Résultat Net") — celui
              utilisé par le backend, PAS le libellé d'affichage
   - annee  : année de l'exercice
   - label  : libellé affiché du KPI (pour la question posée au chatbot)
   - value  : valeur affichée déjà formatée (ex: "39,89 M TND"), pour la
              question posée au chatbot — optionnel
   - size   : diamètre de la zone cliquable en px (défaut 20)

   Design : icône "i" cercle (info), fine et discrète, TOUJOURS visible en
   coin de carte plutôt que masquée jusqu'au survol — un survol de carte
   entière n'est pas un signal fiable sur les vues où plusieurs cartes sont
   denses (mobile, tableaux). Choisi par l'utilisateur le 2026-08-19 après
   présentation de 3 pistes visuelles (le précédent bouton rond bordé "⋯"
   ne convenait pas : "je n'aime pas du tout le choix du design de l'icône
   que ce soit pour les kpis sectoriels ou les kpis entreprise"). Porte
   quand même la classe CSS `kpi-opts-btn` (voir index.css) pour un léger
   surlignage au survol du bouton lui-même.

   Infobulle explicite ("Qualité, source et explication de ce chiffre" au
   lieu du générique "Plus d'options") — retour utilisateur du 2026-08-19 :
   l'icône seule ne rendait pas assez visible que l'accès à la page Qualité
   Data passait par ce menu. Choisi parmi 3 pistes (infobulle explicite /
   item de menu mis en avant / icône dédiée qualité) comme changement
   minimal suffisant.

   Badge bleu clair rempli (pas juste un contour gris sur fond transparent)
   + taille par défaut relevée 20→24px — 2e retour utilisateur le même jour
   ("encore c'est pas assez visible") après le premier passage à l'infobulle
   seule : un simple trait fin se noie visuellement sur des fonds variés
   (bannière sombre, cartes colorées) quel que soit sa taille, un badge
   rempli avec contraste de couleur reste repérable partout.

   N'affiche rien si `code`/`kpi`/`annee` manquent (impossible de construire
   les 3 actions sans ces 3 identifiants). */
export default function KpiOptionsMenu({ code, kpi, annee, label, value, size = 24 }) {
  const [open, setOpen] = useState(false);
  const [menuPos, setMenuPos] = useState(null);
  const ref = useRef(null);
  const btnRef = useRef(null);
  const menuRef = useRef(null);
  const navigate = useNavigate();

  // Le menu est monté hors du DOM de la carte (portail sur document.body,
  // position "fixed" calculée depuis le bouton) plutôt qu'en `position:
  // absolute` classique dans le flux local : les cartes KPI utilisent
  // presque toutes `overflow: hidden` (coins arrondis), ce qui tronquait le
  // menu à mi-texte ("lité de la donnée", "ument source"...) dès qu'il
  // dépassait le bord de la carte — signalé par l'utilisateur le
  // 2026-08-19 via capture d'écran, reproductible sur toute carte KPI.
  const computePos = useCallback(() => {
    const r = btnRef.current?.getBoundingClientRect();
    if (!r) return;
    const menuW = 220;
    let left = r.right - menuW;
    left = Math.max(8, Math.min(left, window.innerWidth - menuW - 8));
    let top = r.bottom + 4;
    if (top + 130 > window.innerHeight) top = r.top - 130 - 4; // pas assez de place en dessous : ouvre vers le haut
    setMenuPos({ top, left, width: menuW });
  }, []);

  useEffect(() => {
    if (!open) return;
    computePos();
    function onClickOutside(e) {
      if (ref.current?.contains(e.target)) return;
      if (menuRef.current?.contains(e.target)) return;
      setOpen(false);
    }
    function onScrollOrResize() { computePos(); }
    document.addEventListener("mousedown", onClickOutside);
    window.addEventListener("resize", onScrollOrResize);
    document.addEventListener("scroll", onScrollOrResize, true);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      window.removeEventListener("resize", onScrollOrResize);
      document.removeEventListener("scroll", onScrollOrResize, true);
    };
  }, [open, computePos]);

  if (!code || !kpi || !annee) return null;

  const goQualite = () => {
    setOpen(false);
    navigate(`/qualite-donnees?code=${encodeURIComponent(code)}&kpi=${encodeURIComponent(kpi)}&annee=${annee}`);
  };
  const goSource = () => {
    setOpen(false);
    navigate(`/kpi-detail?code=${encodeURIComponent(code)}&kpi=${encodeURIComponent(kpi)}&annee=${annee}`);
  };
  const askChatbot = () => {
    setOpen(false);
    const q = value
      ? `Pourquoi ${label ?? kpi} de ${code} est à ${value} en ${annee} ?`
      : `Explique-moi ${label ?? kpi} de ${code} en ${annee}.`;
    window.dispatchEvent(new CustomEvent("kpi:ask-chatbot", { detail: { question: q } }));
  };

  return (
    <div ref={ref} style={{ position: "relative", display: "inline-flex" }}>
      <button
        ref={btnRef}
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}
        title="Qualité, source et explication de ce chiffre"
        aria-label="Qualité, source et explication de ce chiffre"
        className="kpi-opts-btn"
        style={{
          width: size, height: size, borderRadius: "50%",
          border: `1.5px solid ${open ? "#93C5FD" : "#BFDBFE"}`,
          background: open ? "#DBEAFE" : "#EFF6FF",
          cursor: "pointer", padding: 0,
          display: "flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none" stroke={open ? "#1D4ED8" : "#3B82F6"} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="9" />
          <line x1="12" y1="11" x2="12" y2="16.5" />
          <circle cx="12" cy="7.5" r="0.75" fill={open ? "#1D4ED8" : "#3B82F6"} stroke="none" />
        </svg>
      </button>

      {open && menuPos && createPortal(
        <div ref={menuRef} style={{
          position: "fixed", top: menuPos.top, left: menuPos.left, width: menuPos.width, zIndex: 9999,
          background: "white", borderRadius: 8, border: "1px solid #E6E6EC",
          boxShadow: "0 6px 20px rgba(0,0,0,0.12)",
          overflow: "hidden",
        }}>
          <MenuItem icon="⊘" text="Voir la qualité de la donnée" onClick={goQualite} />
          <MenuItem icon="⎘" text="Voir le document source" onClick={goSource} />
          <MenuItem icon="✦" text="Expliquer ce chiffre" onClick={askChatbot} last />
        </div>,
        document.body
      )}
    </div>
  );
}

function MenuItem({ icon, text, onClick, last = false }) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{
        display: "flex", alignItems: "center", gap: 8, width: "100%",
        padding: "8px 12px", background: "none", border: "none",
        borderBottom: last ? "none" : "1px solid #F2F2F6",
        cursor: "pointer", textAlign: "left",
        fontSize: 11, fontWeight: 600, color: "#2E2E38",
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = "#FAFAFA"; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
    >
      <span style={{ fontSize: 12, color: "#747480", width: 14, textAlign: "center", flexShrink: 0 }}>{icon}</span>
      {text}
    </button>
  );
}
