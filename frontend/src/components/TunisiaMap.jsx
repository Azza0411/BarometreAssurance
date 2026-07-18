import { useEffect, useRef, useState } from "react";

/**
 * TunisiaMap — carte choroplèthe basée sur le vrai SVG des gouvernorats
 *
 * Prop `data` (backend-ready) — 7 régions CGA (découpage INS standard) :
 * {
 *   "grand-tunis":  { level:"haute"|"forte"|"moyenne"|"faible", value:"475 agences · 25.6%" },
 *   "nord-est":     { level:"forte",   value:"..." },
 *   "nord-ouest":   { level:"faible",  value:"..." },
 *   "centre-est":   { level:"forte",   value:"..." },
 *   "centre-ouest": { level:"moyenne", value:"..." },
 *   "sud-est":      { level:"faible",  value:"..." },
 *   "sud-ouest":    { level:"faible",  value:"..." },
 * }
 */

// Gouvernorat ISO → région CGA (7 régions, découpage INS)
const GOV_TO_REGION = {
  TN11: "grand-tunis",  // Tunis
  TN12: "grand-tunis",  // Ariana
  TN13: "grand-tunis",  // Ben Arous
  TN14: "grand-tunis",  // Manouba
  TN21: "nord-est",     // Nabeul
  TN22: "nord-est",     // Zaghouan
  TN23: "nord-est",     // Bizerte
  TN31: "nord-ouest",   // Béja
  TN32: "nord-ouest",   // Jendouba
  TN33: "nord-ouest",   // Le Kef
  TN34: "nord-ouest",   // Siliana
  TN41: "centre-ouest", // Kairouan
  TN42: "centre-ouest", // Kasserine
  TN43: "centre-ouest", // Sidi Bouzid
  TN51: "centre-est",   // Sousse
  TN52: "centre-est",   // Monastir
  TN53: "centre-est",   // Mahdia
  TN61: "centre-est",   // Sfax
  TN71: "sud-ouest",    // Gafsa
  TN72: "sud-ouest",    // Tozeur
  TN73: "sud-ouest",    // Kébili
  TN81: "sud-est",      // Gabès
  TN82: "sud-est",      // Médenine
  TN83: "sud-est",      // Tataouine
};

const REGIONS_META = {
  "grand-tunis":  { label: "Grand Tunis",  sub: "Tunis · Ariana · Ben Arous · Manouba" },
  "nord-est":     { label: "Nord-Est",     sub: "Nabeul · Zaghouan · Bizerte" },
  "nord-ouest":   { label: "Nord-Ouest",   sub: "Béja · Jendouba · Le Kef · Siliana" },
  "centre-est":   { label: "Centre-Est",   sub: "Sousse · Monastir · Mahdia · Sfax" },
  "centre-ouest": { label: "Centre-Ouest", sub: "Kairouan · Kasserine · Sidi Bouzid" },
  "sud-est":      { label: "Sud-Est",      sub: "Gabès · Médenine · Tataouine" },
  "sud-ouest":    { label: "Sud-Ouest",    sub: "Gafsa · Tozeur · Kébili" },
};

const REGION_ORDER = ["grand-tunis", "nord-est", "nord-ouest", "centre-est", "centre-ouest", "sud-est", "sud-ouest"];

const LEVEL_COLORS = {
  haute:   "#FFE600",
  forte:   "#2E2E38",
  moyenne: "#8B7000",
  faible:  "#BFBFBF",
  vide:    "#E0E0E0",
};

const LEVEL_LABELS = {
  haute:   "Haute",
  forte:   "Forte",
  moyenne: "Moyenne",
  faible:  "Faible",
};

const DEFAULT_LEVELS = {
  "grand-tunis": "haute", "nord-est": "forte", "nord-ouest": "faible",
  "centre-est": "forte", "centre-ouest": "moyenne", "sud-est": "faible", "sud-ouest": "faible",
};

// viewBox réel : 438 × 926 → ratio hauteur/largeur = 2.115
const MAP_W = 155;
const MAP_H = Math.round(MAP_W * 926 / 438); // ~328px

export default function TunisiaMap({ data = {}, compact = false }) {
  const containerRef = useRef(null);
  const [hovered, setHovered]     = useState(null); // region id
  const [tooltip, setTooltip]     = useState({ x: 0, y: 0, visible: false });

  const getLevel = (id) => data[id]?.level ?? DEFAULT_LEVELS[id] ?? "vide";
  const getColor = (id) => LEVEL_COLORS[getLevel(id)] ?? LEVEL_COLORS.vide;
  const getValue = (id) => data[id]?.value ?? "";

  // ── Chargement & colorisation du SVG ──────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    fetch("/tunisia-map.svg")
      .then(r => r.text())
      .then(svgText => {
        if (cancelled) return;
        const parser = new DOMParser();
        const doc    = parser.parseFromString(svgText, "image/svg+xml");
        const svgEl  = doc.querySelector("svg");
        if (!svgEl) return;

        // Ajuster le SVG pour qu'il tienne dans le conteneur
        svgEl.removeAttribute("width");
        svgEl.removeAttribute("height");
        svgEl.setAttribute("width",  "100%");
        svgEl.setAttribute("height", "100%");
        // viewBox déjà corrigé dans le fichier SVG source — juste normaliser la casse
        const vb = svgEl.getAttribute("viewBox") || svgEl.getAttribute("viewbox") || "302 85 375 640";
        svgEl.removeAttribute("viewbox");
        svgEl.setAttribute("viewBox", vb);
        svgEl.setAttribute("preserveAspectRatio", "xMinYMid meet");
        svgEl.style.display = "block";

        // Cacher le groupe de labels (points de texte)
        const labelGroup = doc.getElementById("label_points");
        if (labelGroup) labelGroup.style.display = "none";
        const pointsGroup = doc.getElementById("points");
        if (pointsGroup) pointsGroup.style.display = "none";

        // Coloriser chaque gouvernorat
        Object.entries(GOV_TO_REGION).forEach(([govId, regionId]) => {
          const el = doc.getElementById(govId);
          if (!el) return;
          el.setAttribute("fill",         getColor(regionId));
          el.setAttribute("stroke",       "#ffffff");
          el.setAttribute("stroke-width", "1.5");
          el.style.cursor      = "pointer";
          el.style.transition  = "filter 0.15s";
          el.dataset.region    = regionId;
        });

        // Injecter dans le DOM React
        if (containerRef.current) {
          const mapDiv = containerRef.current.querySelector(".svg-host");
          if (mapDiv) {
            mapDiv.innerHTML = "";
            mapDiv.appendChild(doc.documentElement);

            // Événements hover sur les paths
            const paths = mapDiv.querySelectorAll("path[data-region]");
            paths.forEach(path => {
              path.addEventListener("mouseenter", (e) => {
                const rid = e.target.dataset.region;
                setHovered(rid);
                // Surbrillance tous les paths de la même région
                paths.forEach(p => {
                  if (p.dataset.region === rid) {
                    p.style.filter = "brightness(1.22)";
                    p.setAttribute("stroke-width", "2.5");
                  }
                });
              });
              path.addEventListener("mousemove", (e) => {
                const rect = mapDiv.getBoundingClientRect();
                setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, visible: true });
              });
              path.addEventListener("mouseleave", () => {
                setHovered(null);
                setTooltip(t => ({ ...t, visible: false }));
                paths.forEach(p => {
                  p.style.filter = "";
                  p.setAttribute("stroke-width", "1.5");
                });
              });
            });
          }
        }
      });

    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(data)]);

  return (
    <div ref={containerRef} style={{ display: "flex", gap: 16, alignItems: "stretch" }}>

      {/* ── Carte — dimensions fixes calculées depuis le vrai viewBox 438×926 ── */}
      <div style={{ position: "relative", flexShrink: 0, width: MAP_W, height: MAP_H }}>
        <div className="svg-host" style={{ width: "100%", height: "100%" }} />

        {/* Tooltip */}
        {tooltip.visible && hovered && REGIONS_META[hovered] && (
          <div style={{
            position:  "absolute",
            left:      tooltip.x + 14,
            top:       Math.max(0, tooltip.y - 40),
            background:"#2E2E38",
            color:     "white",
            borderRadius: 10,
            padding:   "10px 14px",
            fontSize:  11,
            whiteSpace:"nowrap",
            boxShadow: "0 4px 16px rgba(0,0,0,0.28)",
            zIndex:    20,
            pointerEvents: "none",
            minWidth:  160,
          }}>
            <div style={{ fontWeight: 800, fontSize: 13, marginBottom: 3 }}>
              {REGIONS_META[hovered].label}
            </div>
            <div style={{ color: "rgba(255,255,255,0.50)", fontSize: 10, marginBottom: 6, lineHeight: 1.5 }}>
              {REGIONS_META[hovered].sub}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <div style={{
                width: 9, height: 9, borderRadius: 2, flexShrink: 0,
                background: LEVEL_COLORS[getLevel(hovered)],
                border: "1px solid rgba(255,255,255,0.3)",
              }} />
              <span style={{ fontWeight: 700 }}>{getValue(hovered)}</span>
              <span style={{ color: "rgba(255,255,255,0.45)", fontSize: 10 }}>
                {LEVEL_LABELS[getLevel(hovered)]}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── Panneau droit ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", gap: 16 }}>

        {/* Niveaux */}
        <div>
          <div style={{ fontSize: 8, fontWeight: 800, textTransform: "uppercase",
            letterSpacing: "2px", color: "#B0B0B8", marginBottom: 8 }}>Densité</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {Object.entries(LEVEL_LABELS).map(([k, label]) => (
              <div key={k} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{
                  width: 28, height: 7, borderRadius: 4, flexShrink: 0,
                  background: LEVEL_COLORS[k],
                  boxShadow: "0 1px 4px rgba(0,0,0,0.10)",
                }} />
                <span style={{ fontSize: 10.5, color: "#2E2E38", fontWeight: 500 }}>{label}</span>
              </div>
            ))}
          </div>
        </div>

        {!compact && <div style={{ height: 1, background: "#F0F0F0" }} />}

        {/* Régions */}
        {!compact && <div>
          <div style={{ fontSize: 8, fontWeight: 800, textTransform: "uppercase",
            letterSpacing: "2px", color: "#B0B0B8", marginBottom: 8 }}>Régions</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {REGION_ORDER.map((id, i) => {
              const color  = getColor(id);
              const txtCol = color === "#FFE600" ? "#2E2E38" : "white";
              const meta   = REGIONS_META[id];
              const isHov  = hovered === id;
              return (
                <div key={id}
                  style={{ display: "flex", alignItems: "center", gap: 8, cursor: "default",
                    transition: "opacity .15s", opacity: hovered && !isHov ? 0.45 : 1 }}
                  onMouseEnter={() => setHovered(id)}
                  onMouseLeave={() => setHovered(null)}>
                  {/* Badge numéro coloré */}
                  <div style={{
                    width: 18, height: 18, borderRadius: 5, flexShrink: 0,
                    background: color,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 8.5, fontWeight: 900, color: txtCol,
                    boxShadow: isHov ? "0 2px 8px rgba(0,0,0,0.18)" : "0 1px 3px rgba(0,0,0,0.10)",
                    transition: "box-shadow .15s",
                  }}>{i + 1}</div>
                  {/* Texte */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 10.5, fontWeight: 700, color: "#2E2E38",
                      lineHeight: 1.2, whiteSpace: "nowrap" }}>
                      {meta.label}
                    </div>
                    {getValue(id) && (
                      <div style={{ fontSize: 9, color: "#9B9BA8", marginTop: 1 }}>
                        {getValue(id)}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>}

      </div>
    </div>
  );
}
