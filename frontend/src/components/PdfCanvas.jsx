import { useState, useEffect, useRef } from "react";
import * as pdfjsLib from "pdfjs-dist";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).href;

/* ── Rendu PDF sur canvas avec overlay de surlignage ───────────────────── */
// Extrait de KpiDetail.jsx (page Qualité des données) pour être réutilisé
// tel quel dans Correction manuelle (page originale à côté de l'aperçu
// Excel) — aucun changement de comportement, seulement partagé entre pages.
export default function PdfCanvas({ pdfUrl, pageNum, highlight }) {
  const canvasRef     = useRef(null);
  const overlayRef    = useRef(null);
  const containerRef  = useRef(null);
  const renderTaskRef = useRef(null);
  // Cache du document PDF déjà parsé, par pdfUrl — un rapport CMF peut faire
  // plusieurs Mo et des dizaines de pages ; avant ce cache, changer de PAGE
  // (ex. Annexe 12 -> bilan_passif) ou de ZOOM redéclenchait un
  // pdfjsLib.getDocument() complet (re-téléchargement + re-parsing de TOUT
  // le PDF), d'où plusieurs secondes d'attente à chaque clic alors que seule
  // la page/le zoom changeait. getDocument() n'est refait que si pdfUrl
  // change réellement (nouvelle société/année) ; getPage() sur un document
  // déjà chargé est quasi instantané.
  const pdfDocCacheRef = useRef({ url: null, pdf: null });
  const [loading, setLoading] = useState(false);
  const [zoom, setZoom] = useState(1.0);
  // Rotation manuelle ajoutée par l'utilisateur (0/90/180/270), en plus de
  // la rotation propre du PDF (page.rotate) — utile pour les rapports
  // sectoriels FTUSA/CGA dont le tableau chiffré est dessiné à 90° dans le
  // flux de contenu (pas via /Rotate, voir sector_pdf_cell_coords.py), donc
  // toujours rendu "sur le côté" sans ce contrôle. Réinitialisée à chaque
  // changement de document (pdfUrl) pour ne pas laisser un PDF société
  // tourné par erreur après avoir consulté un PDF sectoriel.
  const [rotation, setRotation] = useState(0);
  useEffect(() => { setRotation(0); }, [pdfUrl]);
  // pdfDims as state (not ref) so overlay effect re-runs when render completes
  const [pdfDims, setPdfDims] = useState(null);
  // Dernier viewport pdf.js utilisé pour le rendu — nécessaire pour convertir
  // les coordonnées du surlignage (espace PDF natif, non tourné) vers
  // l'espace pixel du canvas, quelle que soit la rotation appliquée.
  const viewportRef = useRef(null);

  /* Rendu de la page PDF */
  useEffect(() => {
    if (!pdfUrl || !pageNum) return;

    setPdfDims(null);
    setLoading(true);

    if (renderTaskRef.current) {
      renderTaskRef.current.cancel();
      renderTaskRef.current = null;
    }

    let cancelled = false;

    const run = async () => {
      let pdf;
      if (pdfDocCacheRef.current.url === pdfUrl && pdfDocCacheRef.current.pdf) {
        pdf = pdfDocCacheRef.current.pdf;
      } else {
        try { pdf = await pdfjsLib.getDocument({ url: pdfUrl }).promise; }
        catch (e) {
          console.error("[PdfCanvas] getDocument failed:", e?.message ?? e);
          if (!cancelled) setLoading(false);
          return;
        }
        if (cancelled) return;
        pdfDocCacheRef.current = { url: pdfUrl, pdf };
      }

      let page;
      try { page = await pdf.getPage(pageNum); }
      catch (e) {
        console.error("[PdfCanvas] getPage failed:", e?.message ?? e);
        if (!cancelled) setLoading(false);
        return;
      }
      if (cancelled) return;

      const effRotation = ((page.rotate || 0) + rotation) % 360;
      const containerW = containerRef.current?.offsetWidth || 640;
      // getViewport({scale:1, rotation}) déjà avec la rotation appliquée :
      // pour 90°/270°, largeur et hauteur sont inversées, donc l'ajustement
      // à la largeur du conteneur reste correct après rotation (sinon un
      // tableau tourné à 90° s'affichait bien plus large/étroit que prévu).
      const pdfVP0 = page.getViewport({ scale: 1, rotation: effRotation });
      const scale  = (containerW / pdfVP0.width) * zoom;
      const vp     = page.getViewport({ scale, rotation: effRotation });
      viewportRef.current = vp;

      const canvas = canvasRef.current;
      if (!canvas || cancelled) return;

      canvas.width  = Math.round(vp.width);
      canvas.height = Math.round(vp.height);
      // Le canvas de surbrillance (overlay) DOIT être redimensionné ICI, au
      // même moment que le canvas PDF lui-même : l'effet séparé qui dessine
      // le surlignage (dépendances [highlight, pdfDims]) copie aussi
      // `canvas.width/height` vers l'overlay, mais ne se redéclenche QUE
      // quand `highlight`/`pdfDims` changent - pas quand ce canvas est
      // redimensionné pour une AUTRE raison (nouvelle page/zoom sans
      // changement de highlight). Sans cette synchronisation ici, l'overlay
      // pouvait rester bloqué à sa taille par défaut (300×150, avant tout
      // dessin) alors que le canvas PDF réel faisait déjà 638×451 - le
      // rectangle de surlignage se dessinait alors dans un buffer trop
      // petit et mal calé, donc invisible malgré un badge "Cellule
      // surlignée" correct (coordonnées bien trouvées côté API) - retour
      // utilisateur du 2026-08-22, capture à l'appui.
      const overlayEl = overlayRef.current;
      if (overlayEl) {
        overlayEl.width  = canvas.width;
        overlayEl.height = canvas.height;
      }

      const ctx = canvas.getContext("2d");
      const renderTask = page.render({ canvasContext: ctx, viewport: vp });
      renderTaskRef.current = renderTask;

      try { await renderTask.promise; }
      catch (e) {
        if (e?.name !== "RenderingCancelledException") {
          console.error("[PdfCanvas] renderTask failed:", e?.message ?? e);
        }
        return;
      }

      renderTaskRef.current = null;
      if (cancelled) return;

      setLoading(false);
      setPdfDims({ width: pdfVP0.width, height: pdfVP0.height });
    };

    run().catch(e => {
      console.error("[PdfCanvas] uncaught:", e);
      if (!cancelled) setLoading(false);
    });

    return () => {
      cancelled = true;
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel();
        renderTaskRef.current = null;
      }
    };
  }, [pdfUrl, pageNum, zoom, rotation]);

  /* Dessin de l'overlay de surlignage — se redessine quand highlight OU pdfDims change */
  useEffect(() => {
    const overlay = overlayRef.current;
    const canvas  = canvasRef.current;
    if (!overlay || !canvas) return;

    // Toujours synchroniser les dimensions de l'overlay avec le canvas PDF
    overlay.width  = canvas.width;
    overlay.height = canvas.height;
    const ctx = overlay.getContext("2d");
    ctx.clearRect(0, 0, overlay.width, overlay.height);

    if (!highlight || !pdfDims || !viewportRef.current) return;

    const { x0, y0, x1, y1 } = highlight;
    // convertToViewportPoint applique la même transformation (échelle +
    // rotation) que celle utilisée pour le rendu du canvas — fonctionne donc
    // quelle que soit la rotation choisie (voir `rotation` plus haut), pas
    // seulement à 0°. (pdfjs-dist n'expose pas de convertToViewportRectangle
    // dans cette version — seulement le point-à-point ; on convertit donc
    // les 2 coins séparément.) Les coins renvoyés ne sont pas forcément
    // "haut-gauche puis bas-droite" une fois tournés, d'où le Math.min/abs.
    const [vx0, vy0] = viewportRef.current.convertToViewportPoint(x0, y0);
    const [vx1, vy1] = viewportRef.current.convertToViewportPoint(x1, y1);
    const rx = Math.min(vx0, vx1);
    const ry = Math.min(vy0, vy1);
    const rw = Math.abs(vx1 - vx0);
    const rh = Math.abs(vy1 - vy0);

    ctx.fillStyle = "rgba(239, 68, 68, 0.30)";
    ctx.fillRect(rx, ry, rw, rh);

    ctx.strokeStyle = "rgba(220, 38, 38, 0.95)";
    ctx.lineWidth   = 2.5;
    ctx.strokeRect(rx, ry, rw, rh);

    ctx.strokeStyle = "rgba(220, 38, 38, 0.20)";
    ctx.lineWidth   = 8;
    ctx.strokeRect(rx - 2, ry - 2, rw + 4, rh + 4);

    // Scroll pour rendre la cellule surlignée visible (avec marge de 80px)
    const container = containerRef.current;
    if (container) {
      const viewH   = container.clientHeight;
      const cellTop = ry * (canvas.offsetHeight / canvas.height);
      const cellBot = (ry + rh) * (canvas.offsetHeight / canvas.height);
      const scrollTop = container.scrollTop;
      if (cellTop - 80 < scrollTop || cellBot + 80 > scrollTop + viewH) {
        container.scrollTo({ top: Math.max(0, cellTop - viewH / 2), behavior: "smooth" });
      }
    }
  }, [highlight, pdfDims]);

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Barre de contrôles zoom */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "center",
        gap: 8, padding: "6px 12px",
        background: "#1E293B", borderBottom: "1px solid #334155",
      }}>
        <button onClick={() => setZoom(z => Math.max(0.5, +(z - 0.25).toFixed(2)))}
          style={{ background: "#334155", border: "none", borderRadius: 6, color: "#CBD5E1",
            width: 28, height: 28, cursor: "pointer", fontSize: 16, lineHeight: 1 }}>−</button>
        <span style={{ fontSize: 12, color: "#94A3B8", minWidth: 44, textAlign: "center" }}>
          {Math.round(zoom * 100)} %
        </span>
        <button onClick={() => setZoom(z => Math.min(3.0, +(z + 0.25).toFixed(2)))}
          style={{ background: "#334155", border: "none", borderRadius: 6, color: "#CBD5E1",
            width: 28, height: 28, cursor: "pointer", fontSize: 16, lineHeight: 1 }}>+</button>
        <span style={{ width: 1, alignSelf: "stretch", background: "#334155", margin: "0 2px" }} />
        <button onClick={() => setRotation(r => (r + 90) % 360)}
          title="Tourner la page de 90°"
          aria-label="Tourner la page de 90°"
          style={{ background: "#334155", border: "none", borderRadius: 6, color: "#CBD5E1",
            width: 28, height: 28, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 4v5h5" />
            <path d="M4.5 9A8 8 0 1 1 4 13" />
          </svg>
        </button>
        <button onClick={() => { setZoom(1.0); setRotation(0); }}
          style={{ background: "none", border: "1px solid #334155", borderRadius: 6,
            color: "#64748B", fontSize: 10, padding: "3px 8px", cursor: "pointer" }}>Réinitialiser</button>
      </div>
    <div ref={containerRef} style={{ flex: 1, overflow: "auto", background: "#374151" }}>
      {/* Le div interne a position:relative + display:inline-block, sa taille
          suit donc EXACTEMENT la taille du canvas PDF (pilotée par `zoom`) —
          pas la largeur du conteneur flex. Sans inline-block, un div bloc
          s'étire à 100% du conteneur quel que soit son contenu, ce qui
          forçait visuellement le canvas à toujours faire la largeur du
          conteneur et rendait le zoom inopérant (le buffer interne devenait
          plus grand/net, mais l'affichage restait clampé à 100%). */}
      <div style={{ position: "relative", display: "inline-block" }}>
        {loading && (
          <div style={{
            position: "absolute", inset: 0, display: "flex",
            alignItems: "center", justifyContent: "center",
            background: "rgba(30,41,59,0.7)", zIndex: 10,
          }}>
            <div style={{ textAlign: "center", color: "#94A3B8" }}>
              <div style={{
                width: 32, height: 32, border: "3px solid #334155",
                borderTopColor: "#60A5FA", borderRadius: "50%",
                animation: "spin 0.8s linear infinite",
                margin: "0 auto 10px",
              }} />
              <div style={{ fontSize: 12 }}>Chargement PDF…</div>
            </div>
          </div>
        )}
        <canvas ref={canvasRef} style={{ display: "block" }} />
        <canvas
          ref={overlayRef}
          style={{
            position: "absolute", top: 0, left: 0,
            width: "100%", height: "100%",
            pointerEvents: "none",
          }}
        />
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
    </div>
  );
}
