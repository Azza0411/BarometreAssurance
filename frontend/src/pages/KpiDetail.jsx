import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { KPI_META } from "../utils/kpiMeta";
import { isTakaful } from "../utils/famille";
import { kpiLabel } from "../utils/kpiCatalog";
import { classifyCell, resolveCellVisual } from "../utils/kpiStatus";
import AnomalyDetail from "../components/AnomalyDetail";
import * as pdfjsLib from "pdfjs-dist";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url
).href;

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8002";

/* ── Formatage valeur ───────────────────────────────────────────────────── */
function fmtVal(v, kpi = "") {
  if (v === null || v === undefined) return null;
  const num = Number(v);
  if (isNaN(num)) return String(v);
  if (kpi.includes("%")) return `${num.toLocaleString("fr-TN", { maximumFractionDigits: 2 })} %`;
  if (Math.abs(num) >= 1_000_000) return `${(num / 1_000_000).toLocaleString("fr-TN", { maximumFractionDigits: 2 })} M TND`;
  if (Math.abs(num) >= 1_000) return `${num.toLocaleString("fr-TN", { maximumFractionDigits: 0 })} TND`;
  return num.toLocaleString("fr-TN", { maximumFractionDigits: 2 });
}

/* ── Palette tokens ────────────────────────────────────────────────────── */
const T = {
  calcBg:     "#EEF2FF",
  calcBorder: "#C7D2FE",
  calcText:   "#3730A3",
  calcDark:   "#1E1B4B",
  extrBg:     "#F0FDF4",
  extrBorder: "#86EFAC",
  extrText:   "#15803D",
  extrDark:   "#14532D",
  extBg:      "#F8FAFC",
  extBorder:  "#CBD5E1",
  extText:    "#475569",
  divLine:    "#1E293B",
  opText:     "#94A3B8",
  multText:   "#1E293B",
};

/* ── Rendu PDF sur canvas avec overlay de surlignage ───────────────────── */
function PdfCanvas({ pdfUrl, pageNum, highlight }) {
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

      console.log("[PdfCanvas] render done ✓", pdfVP0.width, "×", pdfVP0.height);
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

/* ── Badge page PDF ─────────────────────────────────────────────────────── */
function PageBadge({ page, onClick }) {
  if (!page) return null;
  return (
    <span
      onClick={onClick}
      title={onClick ? `Afficher la page ${page} dans le PDF` : ""}
      style={{
        display: "inline-flex", alignItems: "center", gap: 4,
        padding: "2px 8px", borderRadius: 12,
        background: "#DBEAFE", color: "#1D4ED8", border: "1px solid #BFDBFE",
        fontSize: 11, fontWeight: 700, fontVariantNumeric: "tabular-nums",
        cursor: onClick ? "pointer" : "default",
        userSelect: "none",
        transition: "background 0.15s",
      }}
      onMouseEnter={e => { if (onClick) e.currentTarget.style.background = "#BFDBFE"; }}
      onMouseLeave={e => { if (onClick) e.currentTarget.style.background = "#DBEAFE"; }}
    >
      <svg viewBox="0 0 12 12" fill="none" width="9" height="9">
        <rect x="1.5" y="1" width="9" height="10" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
        <path d="M4 4.5h4M4 6.5h3" stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"/>
      </svg>
      p.{page}
    </span>
  );
}

/* ── Chip pour un nœud (formule mathématique) ───────────────────────────── */
function NodeChip({ node, raw, active, onClick }) {
  const val    = node.rawKey ? raw[node.rawKey] : null;
  const valStr = fmtVal(val, node.rawKey ?? "");
  const isCalc = node.type === "calcule";
  const isExt  = node.type === "externe";

  const color  = isCalc ? "#4338CA" : isExt ? "#6B7280" : "#15803D";
  const bg     = active ? (isCalc ? "#EEF2FF" : isExt ? "#F1F5F9" : "#F0FDF4") : "#fff";
  const border = active ? color : "#D1D5DB";

  return (
    <button
      onClick={onClick}
      style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: "5px 10px", borderRadius: 6,
        border: `1.5px solid ${border}`,
        background: bg, color,
        cursor: "pointer", fontFamily: "inherit",
        fontSize: 12, fontWeight: 600,
        transition: "all 0.12s",
      }}
    >
      <span style={{ fontSize: 9, opacity: 0.6 }}>{isCalc ? "𝑓" : isExt ? "⊕" : "⊡"}</span>
      <span style={{ whiteSpace: "nowrap" }}>{node.label}</span>
      {valStr && (
        <span style={{
          fontSize: 10, fontWeight: 700, padding: "1px 5px", borderRadius: 4,
          background: "rgba(0,0,0,0.05)", fontVariantNumeric: "tabular-nums",
        }}>
          {valStr}
        </span>
      )}
    </button>
  );
}

/* ── Formule mathématique avec fraction ─────────────────────────────────── */
function MathFormula({ meta, raw, activeIdx, onChipClick }) {
  if (!meta?.composantes) return null;

  const nums      = meta.composantes.filter(c => !c.denominator);
  const dens      = meta.composantes.filter(c =>  c.denominator);
  const numIdxMap = meta.composantes.map((c, i) => ({ c, i })).filter(x => !x.c.denominator);
  const denIdxMap = meta.composantes.map((c, i) => ({ c, i })).filter(x =>  x.c.denominator);
  const hasFrac   = dens.length > 0;
  const multiplier = meta.formule?.match(/×\s*(\d+)/)?.[1];

  const renderGroup = (group, idxMap) => group.map((c, gi) => (
    <span key={gi} style={{ display: "inline-flex", alignItems: "center" }}>
      {gi > 0 && (
        <span style={{
          fontFamily: "Georgia, 'Times New Roman', serif",
          fontSize: 24, color: T.opText, margin: "0 10px", fontWeight: 300,
        }}>+</span>
      )}
      <NodeChip
        node={c}
        raw={raw}
        active={activeIdx === idxMap[gi].i}
        onClick={() => onChipClick(idxMap[gi].i)}
      />
    </span>
  ));

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap", padding: "8px 0" }}>
      {hasFrac ? (
        <>
          <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 0 }}>
            <div style={{ display: "flex", alignItems: "center", paddingBottom: 12, flexWrap: "wrap", gap: 4 }}>
              {renderGroup(nums, numIdxMap)}
            </div>
            <div style={{
              width: "calc(100% + 32px)", height: 2,
              background: T.divLine, borderRadius: 1,
              margin: "0 -16px",
            }} />
            <div style={{ display: "flex", alignItems: "center", paddingTop: 12, flexWrap: "wrap", gap: 4 }}>
              {renderGroup(dens, denIdxMap)}
            </div>
          </div>
          {multiplier && (
            <span style={{
              fontFamily: "Georgia, 'Times New Roman', serif",
              fontSize: 24, color: T.multText, fontWeight: 400,
            }}>
              × {multiplier}
            </span>
          )}
        </>
      ) : (
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 4 }}>
          {renderGroup(nums, numIdxMap)}
        </div>
      )}
    </div>
  );
}

/* ── Détail d'un nœud extrait ────────────────────────────────────────────── */
// AL_AMANAH_TAKAFUL publie en arabe — le ligne/colonne français de
// kpiMeta.js ne s'y applique pas et pdfSections (détection française) y
// est toujours vide, donc le badge/bouton habituel (gated sur `page`)
// n'apparaît jamais pour cette société. Repli dédié : bouton "Localiser"
// TOUJOURS visible, page ET cellule déterminées côté serveur au clic (voir
// goArabicPage / /api/arabic-pdf-cell) plutôt que pré-calculées. Ajouté le
// 2026-08-19, étape 3 du plan explicite de l'utilisateur.
const _ARABIC_TAKAFUL_CODE = "AL_AMANAH_TAKAFUL";

// Libellés arabes réellement recherchés dans le PDF pour chaque KPI (copie
// d'affichage des constantes _AR_* de extraction/takaful_kpi_extractor.py —
// dupliquées ici plutôt qu'exposées par API, ce sont des libellés fixes qui
// ne changent qu'avec le format du rapport CMF). Affiché à côté de la
// source PDF pour AL_AMANAH_TAKAFUL sur demande explicite de l'utilisateur
// ("afficher sa traduction à côté avec la formule", 2026-08-19) : permet de
// vérifier visuellement, même sans lire l'arabe, que le bon libellé est
// recherché sur la page ouverte.
const _AR_LABELS = {
  "Total actif": "مجموع الأصول",
  "Capitaux propres": "مجموع الأموال الذاتية",
  "Résultat Net": "مال ذاتي نتيجة السنة المحاسبية",
  "Primes émises par assurance": "أقساط تأمين صادرة و مقبولة",
  "Charges de prestations": "أعباء تقديم الخدمة",
  "Charges d'acquisition et de gestion nettes": "أعباء تصرف و اقتناء أخرى صافية",
};

function ExtraitDetail({ node, annee, pdfSections, onGoPage, code, onGoArabicPage }) {
  const isArabic = code === _ARABIC_TAKAFUL_CODE;
  const page = !isArabic && node.section ? pdfSections?.[node.section] : null;
  const canLocateArabic = isArabic && Boolean(node.rawKey) && Boolean(onGoArabicPage);
  return (
    <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", overflow: "hidden", background: "#fff" }}>
      <div style={{
        padding: "9px 14px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em",
            color: "#15803D", background: "#DCFCE7", border: "1px solid #BBF7D0",
            padding: "2px 6px", borderRadius: 3,
          }}>PDF</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#111827" }}>{node.label}</span>
        </div>
        {!isArabic && <PageBadge page={page} onClick={page ? () => onGoPage(page, node) : null} />}
      </div>
      <div style={{ padding: "10px 14px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "72px 1fr", gap: "4px 10px", fontSize: 11 }}>
          <span style={{ color: "#9CA3AF", fontWeight: 600, paddingTop: 1 }}>Tableau</span>
          <span style={{ color: "#374151", lineHeight: 1.5 }}>{node.tableau}</span>
          {!isArabic && <>
            <span style={{ color: "#9CA3AF", fontWeight: 600 }}>Ligne</span>
            <span style={{ color: "#374151", fontFamily: "ui-monospace, monospace" }}>« {node.ligne} »</span>
            <span style={{ color: "#9CA3AF", fontWeight: 600 }}>Colonne</span>
            <span style={{ color: "#374151", fontFamily: "ui-monospace, monospace" }}>« {node.colonne?.replace("{annee}", annee)} »</span>
          </>}
          {page && <>
            <span style={{ color: "#9CA3AF", fontWeight: 600 }}>Page</span>
            <span style={{ color: "#111827", fontWeight: 700 }}>{page}</span>
          </>}
        </div>
        {isArabic && (
          <div style={{ marginTop: 8, fontSize: 10.5, color: "#9CA3AF", fontStyle: "italic" }}>
            Document en arabe — libellé/colonne français non applicables. Localisation par reconnaissance de texte arabe.
          </div>
        )}
        {isArabic && _AR_LABELS[node.rawKey] && (
          <div style={{
            marginTop: 8, padding: "8px 10px", borderRadius: 6,
            background: "#F9FAFB", border: "1px solid #E5E7EB",
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10,
          }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: "#9CA3AF", whiteSpace: "nowrap" }}>Libellé recherché</span>
            <span dir="rtl" lang="ar" style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>
              {_AR_LABELS[node.rawKey]}
            </span>
          </div>
        )}
        {page && !isArabic && (
          <button
            onClick={() => onGoPage(page, node)}
            style={{
              marginTop: 10, width: "100%", padding: "7px 12px",
              borderRadius: 6, border: "1px solid #D1D5DB",
              background: "#fff", color: "#374151",
              fontSize: 11, fontWeight: 600, cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              transition: "background 0.12s",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "#F3F4F6"}
            onMouseLeave={e => e.currentTarget.style.background = "#fff"}
          >
            <svg viewBox="0 0 14 14" fill="none" width="11" height="11">
              <rect x="1" y="1" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M4 5h6M4 7.5h4M4 10h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            Localiser dans le PDF — page {page}
          </button>
        )}
        {canLocateArabic && (
          <button
            onClick={() => onGoArabicPage(node)}
            style={{
              marginTop: 10, width: "100%", padding: "7px 12px",
              borderRadius: 6, border: "1px solid #D1D5DB",
              background: "#fff", color: "#374151",
              fontSize: 11, fontWeight: 600, cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              transition: "background 0.12s",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "#F3F4F6"}
            onMouseLeave={e => e.currentTarget.style.background = "#fff"}
          >
            <svg viewBox="0 0 14 14" fill="none" width="11" height="11">
              <rect x="1" y="1" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M4 5h6M4 7.5h4M4 10h5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
            </svg>
            Localiser dans le PDF
          </button>
        )}
      </div>
    </div>
  );
}

/* ── Détail d'un nœud calculé (avec ses sous-composantes) ───────────────── */
function CalcDetail({ node, raw, annee, pdfSections, onGoPage, code, onGoArabicPage }) {
  const val    = node.rawKey ? raw[node.rawKey] : null;
  const valStr = fmtVal(val, node.rawKey ?? "");

  return (
    <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", overflow: "hidden", background: "#fff" }}>
      <div style={{
        padding: "9px 14px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em",
            color: "#4338CA", background: "#EEF2FF", border: "1px solid #C7D2FE",
            padding: "2px 6px", borderRadius: 3,
          }}>Calculé</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#111827" }}>{node.label}</span>
        </div>
        {valStr && (
          <span style={{ fontSize: 13, fontWeight: 800, color: "#111827", fontVariantNumeric: "tabular-nums" }}>
            {valStr}
          </span>
        )}
      </div>
      <div style={{ padding: "10px 14px" }}>
        <div style={{
          fontFamily: "ui-monospace, Consolas, monospace",
          fontSize: 11, color: "#4338CA",
          background: "#F5F3FF", borderRadius: 5,
          padding: "6px 10px", marginBottom: node.sousComposantes?.length ? 10 : 0,
        }}>
          {node.formule}
        </div>
        {node.sousComposantes?.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {node.sousComposantes.map((sc, i) =>
              sc.type === "extrait"
                ? <ExtraitDetail key={i} node={sc} annee={annee} pdfSections={pdfSections} onGoPage={onGoPage} code={code} onGoArabicPage={onGoArabicPage} />
                : null
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Détail source externe ───────────────────────────────────────────────── */
// Sources sectorielles dont le PDF est désormais persisté par
// extraction/kpi_extraction_pipeline.py (voir _save_sectoral_pdf) et
// servi par /api/pdf-local?source=... — INS n'y figure pas volontairement :
// ce n'est pas une source PDF (API/série statistique), il n'y a rien à ouvrir.
const _SECTORAL_PDF_SOURCES = ["FTUSA", "CGA"];

function ExterneDetail({ node, annee, raw = {}, onLocate }) {
  const sourceCode = _SECTORAL_PDF_SOURCES.find(s => node.source?.toUpperCase().startsWith(s));
  const pdfUrl = sourceCode ? `${API}/api/pdf-local?source=${sourceCode}&annee=${annee}` : null;
  const val    = node.rawKey ? raw[node.rawKey] : null;
  const valStr = fmtVal(val, node.rawKey ?? "");
  const canLocate = Boolean(sourceCode && node.ligne && node.colonne && onLocate);

  return (
    <div style={{ borderRadius: 8, border: "1px solid #E5E7EB", overflow: "hidden", background: "#fff" }}>
      <div style={{
        padding: "9px 14px", background: "#F9FAFB", borderBottom: "1px solid #E5E7EB",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em",
            color: "#6B7280", background: "#F3F4F6", border: "1px solid #D1D5DB",
            padding: "2px 6px", borderRadius: 3,
          }}>🌐 Secteur</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#111827" }}>{node.label}</span>
          {valStr && (
            <span style={{ fontSize: 12, fontWeight: 800, color: "#111827", fontVariantNumeric: "tabular-nums" }}>
              {valStr}
            </span>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {canLocate && (
            <button
              onClick={() => onLocate(sourceCode, node)}
              style={{
                fontSize: 11, fontWeight: 600, color: "#1D4ED8", background: "none",
                border: "none", padding: 0, cursor: "pointer",
                display: "flex", alignItems: "center", gap: 4,
              }}
            >
              📍 Localiser dans le PDF
            </button>
          )}
          {pdfUrl && (
            <a href={pdfUrl} target="_blank" rel="noreferrer" style={{
              fontSize: 11, fontWeight: 600, color: "#1D4ED8", textDecoration: "none",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              Ouvrir le PDF source ↗
            </a>
          )}
          {!pdfUrl && node.lien && (
            <a href={node.lien} target="_blank" rel="noreferrer" style={{
              fontSize: 11, fontWeight: 600, color: "#1D4ED8", textDecoration: "none",
              display: "flex", alignItems: "center", gap: 4,
            }}>
              Ouvrir le portail source ↗
            </a>
          )}
        </div>
      </div>
      <div style={{ padding: "10px 14px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "72px 1fr", gap: "4px 10px", fontSize: 11 }}>
          <span style={{ color: "#9CA3AF", fontWeight: 600 }}>Source</span>
          <span style={{ color: "#374151" }}>{node.source}</span>
          <span style={{ color: "#9CA3AF", fontWeight: 600 }}>Tableau</span>
          <span style={{ color: "#374151" }}>{node.tableau}</span>
          <span style={{ color: "#9CA3AF", fontWeight: 600 }}>Ligne</span>
          <span style={{ color: "#374151", fontFamily: "ui-monospace, monospace" }}>« {node.ligne} »</span>
          <span style={{ color: "#9CA3AF", fontWeight: 600 }}>Colonne</span>
          <span style={{ color: "#374151", fontFamily: "ui-monospace, monospace" }}>« {node.colonne} »</span>
        </div>
        {!pdfUrl && !node.lien && (
          <div style={{ marginTop: 10, fontSize: 10.5, color: "#9CA3AF", fontStyle: "italic" }}>
            Pas de PDF ni de lien disponible pour cette source.
          </div>
        )}
        {!pdfUrl && node.lien && (
          <div style={{ marginTop: 10, fontSize: 10.5, color: "#9CA3AF", fontStyle: "italic" }}>
            Série statistique (pas de rapport PDF) — valeur consultable sur le portail INS ci-dessus.
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Page principale ────────────────────────────────────────────────────── */
export default function KpiDetail() {
  const [params]  = useSearchParams();
  const navigate  = useNavigate();
  const code      = params.get("code") ?? "";
  const kpiName   = params.get("kpi")  ?? "";
  const annee     = Number(params.get("annee") || 2024);

  const [qualData,    setQualData]    = useState(null);
  const [anomaliesData, setAnomaliesData] = useState(null);
  const [years,       setYears]       = useState([]);
  const [pdfSections, setPdfSections] = useState(null);
  const [activeIdx,   setActiveIdx]   = useState(null);
  const [pdfPage,     setPdfPage]     = useState(null);
  const [highlight,   setHighlight]   = useState(null); // coords cellule {x0,y0,x1,y1,page_width,page_height}
  const [noHighlightReason, setNoHighlightReason] = useState(null); // raison si non trouvée
  const [selectedAnomalyIdx, setSelectedAnomalyIdx] = useState(0); // pour le lien "cause amont" du diagnostic intégré
  // Source active du panneau PDF de droite quand elle est sectorielle
  // (FTUSA/CGA) plutôt qu'une société CMF — voir goSectorPage. Ajouté le
  // 2026-08-19 : les KPI sectoriels n'avaient jusqu'ici qu'un lien "Ouvrir
  // le PDF" en nouvel onglet, pas de surlignage dans le panneau comme les
  // KPI société (retour utilisateur explicite).
  const [sectorPdfSource, setSectorPdfSource] = useState(null);

  useEffect(() => { setSectorPdfSource(null); setPdfPage(null); setHighlight(null); setNoHighlightReason(null); }, [code, kpiName, annee]);

  /* Années réellement présentes en base (au lieu d'une liste codée en dur) —
     même source que QualiteDonnees.jsx/AnomaliesSysteme.jsx pour rester
     cohérent sur les 3 pages. */
  useEffect(() => {
    fetch(`${API}/api/annees-disponibles?source=CMF`)
      .then(r => r.json())
      .then(d => setYears(d.annees ?? []))
      .catch(() => setYears([]));
  }, []);

  /* Fetch données qualité */
  useEffect(() => {
    fetch(`${API}/api/rapport-qualite?annee=${annee}`)
      .then(r => r.json()).then(setQualData).catch(() => {});
  }, [annee]);

  /* Fetch données anomalies (diagnostic couche/cause/recommandation/
     propagation, déjà enrichies côté backend) — pour le diagnostic intégré
     affiché directement sur cette page (voir Partie 3 du plan). */
  useEffect(() => {
    fetch(`${API}/api/anomalies-systeme?annee=${annee}`)
      .then(r => r.ok ? r.json() : null).then(setAnomaliesData).catch(() => {});
  }, [annee]);

  useEffect(() => { setSelectedAnomalyIdx(0); }, [code, kpiName, annee]);

  /* Fetch numéros de page PDF */
  useEffect(() => {
    if (!code) return;
    fetch(`${API}/api/pdf-sections?code=${encodeURIComponent(code)}&annee=${annee}`)
      .then(r => r.ok ? r.json() : null).then(setPdfSections).catch(() => {});
  }, [code, annee]);

  /* Valeurs brutes des KPI sectoriels (FTUSA/CGA/INS — Population, PIB,
     Total Primes marché, ratios techniques marché, Total agences...) —
     fusionnées avec les KPI société ci-dessous. Nécessaire pour deux cas :
     (1) un KPI "calculé" société dont une composante est sectorielle (ex:
     "Part de marché (%)" = Primes émises compagnie / Total Primes marché
     FTUSA — le dénominateur ne s'affichait jusqu'ici JAMAIS, `raw` ne
     contenant que les KPI de `code`) ; (2) un KPI purement sectoriel
     (code="MARCHE", ex: Population, Total agences) affiché directement.
     Ajouté le 2026-08-19 sur demande explicite de l'utilisateur ("on ne
     peut pas voir la source des KPI sectoriels"). */
  const [sectorRaw, setSectorRaw] = useState({});
  useEffect(() => {
    fetch(`${API}/api/sector-kpi-value?annee=${annee}`)
      .then(r => r.ok ? r.json() : {}).then(setSectorRaw).catch(() => setSectorRaw({}));
  }, [annee]);

  const detail = qualData?.kpi_detail?.[code];
  // Priorité : variante arabe (AL_AMANAH_TAKAFUL uniquement — pas de
  // segmentation Vie/Non-Vie du tout, contrairement à AT_TAKAFULIA/
  // ZITOUNA_TAKAFUL qui publient en français et ont une vraie Annexe 12/13
  // Vie/Non-Vie déjà localisable normalement) > variante Takaful générique
  // (ratios techniques, mêmes clés brutes pour les 3 sociétés) > défaut.
  const meta   = (code === _ARABIC_TAKAFUL_CODE && KPI_META[`${kpiName} Arabe`])
    || (isTakaful(code) && KPI_META[`${kpiName} Takaful`])
    || KPI_META[kpiName];
  const raw    = { ...sectorRaw, ...(detail?.kpis_raw ?? {}) };

  const pdfUrl = sectorPdfSource
    ? `${API}/api/pdf-local?source=${sectorPdfSource}&annee=${annee}`
    : detail?.pdf_local
      ? `${API}/api/pdf-local?code=${encodeURIComponent(code)}&annee=${annee}`
      : null;

  /* Aller à une page + surligner une cellule extrait (KPI société, CMF) */
  const goPage = useCallback(async (page, nodeOrSection) => {
    setSectorPdfSource(null);
    setPdfPage(page);
    setHighlight(null);
    setNoHighlightReason(null);

    // nodeOrSection peut être un nœud extrait (avec ligne/colonne) ou juste une string section
    const node = (nodeOrSection && typeof nodeOrSection === "object") ? nodeOrSection : null;
    if (!node?.ligne || !node?.colonne || !code) return;

    const colonne = node.colonne?.replace("{annee}", annee);
    try {
      const r = await fetch(
        `${API}/api/pdf-cell-coords?code=${encodeURIComponent(code)}&annee=${annee}` +
        `&page=${page}&ligne=${encodeURIComponent(node.ligne)}&colonne=${encodeURIComponent(colonne)}`
      );
      const data = await r.json();
      if (data.found) setHighlight(data);
      else setNoHighlightReason(data.reason ?? "inconnue");
    } catch {
      setNoHighlightReason("erreur_reseau");
    }
  }, [code, annee]);

  /* Équivalent sectoriel de goPage : la page n'est pas connue à l'avance
     (déterminée côté serveur, voir /api/sector-pdf-cell), donc reçue depuis
     la réponse plutôt que passée en argument. */
  const goSectorPage = useCallback(async (sourceCode, node) => {
    setSectorPdfSource(sourceCode);
    setPdfPage(null);
    setHighlight(null);
    setNoHighlightReason(null);
    if (!node?.ligne || !node?.colonne || !sourceCode) return;

    const colonne = node.colonne?.replace("{annee}", annee);
    try {
      const r = await fetch(
        `${API}/api/sector-pdf-cell?source=${encodeURIComponent(sourceCode)}&annee=${annee}` +
        `&ligne=${encodeURIComponent(node.ligne)}&colonne=${encodeURIComponent(colonne)}`
      );
      const data = await r.json();
      setPdfPage(data.page ?? null);
      if (data.found) setHighlight(data);
      else setNoHighlightReason(data.reason ?? "inconnue");
    } catch {
      setNoHighlightReason("erreur_reseau");
    }
  }, [annee]);

  /* Équivalent AL_AMANAH_TAKAFUL (PDF en arabe) de goPage : le ligne/
     colonne français de kpiMeta.js ne s'applique pas à ce document — page
     ET cellule déterminées côté serveur par recherche floue RTL (voir
     /api/arabic-pdf-cell, arabic_pdf_cell_coords.py), le KPI étant
     identifié par sa clé de stockage plutôt que par ligne/colonne. Ajouté
     le 2026-08-19, étape 3 du plan explicite de l'utilisateur ("documents
     Takaful arabe"). */
  const goArabicPage = useCallback(async (node) => {
    setPdfPage(null);
    setHighlight(null);
    setNoHighlightReason(null);
    if (!code || !node?.rawKey) return;
    try {
      const r = await fetch(
        `${API}/api/arabic-pdf-cell?code=${encodeURIComponent(code)}&annee=${annee}` +
        `&kpi=${encodeURIComponent(node.rawKey)}`
      );
      const data = await r.json();
      setPdfPage(data.page ?? null);
      if (data.found) setHighlight(data);
      else setNoHighlightReason(data.reason ?? "inconnue");
    } catch {
      setNoHighlightReason("erreur_reseau");
    }
  }, [code, annee]);

  const NO_HIGHLIGHT_LABELS = {
    pdf_manquant:         "PDF non disponible localement.",
    page_invalide:        "Numéro de page invalide pour ce PDF.",
    page_introuvable:     "Tableau source introuvable dans ce PDF.",
    source_non_prise_en_charge: "Localisation non prise en charge pour cette source.",
    kpi_non_pris_en_charge: "Localisation non prise en charge pour ce KPI.",
    valeur_non_confirmee: "Ligne repérée, mais la valeur ne correspond pas à celle extraite — surlignage non affiché par prudence.",
    page_scannee_pas_de_surlignage: "Page scannée (OCR) — position exacte non surlignable, page ouverte tout de même.",
    position_approximative: "Page probable repérée par libellé (OCR), mais sans confirmation par la valeur — à vérifier manuellement.",
    page_vide:            "Aucun texte extractible sur cette page (page probablement scannée).",
    ligne_introuvable:    "Ligne introuvable sur cette page — le libellé attendu ne correspond à aucune ligne du PDF.",
    colonne_introuvable:  "Colonne introuvable sur cette page — l'en-tête attendu n'a pas été trouvé.",
    cellule_introuvable:  "Ligne et colonne repérées, mais aucune cellule PDF correspondante.",
    erreur:               "Erreur interne lors de la lecture du PDF.",
    erreur_reseau:        "Impossible de contacter le serveur pour localiser la cellule.",
    inconnue:             "Cellule introuvable dans le PDF.",
  };

  /* Clic sur un chip de la formule */
  const handleChipClick = (idx) => {
    const newActive = activeIdx === idx ? null : idx;
    setActiveIdx(newActive);
    if (newActive === null) { setHighlight(null); return; }

    const comp = meta?.composantes?.[idx];
    if (!comp) return;
    // Composante simple (un seul extrait) : on peut naviguer directement.
    // Composante composite (calcule, ex. Vie + Non-Vie) : pas de navigation
    // automatique vers un seul sous-composant — CalcDetail affiche déjà
    // chaque sous-composante avec son propre bouton "Localiser dans le PDF",
    // laissant l'utilisateur choisir explicitement laquelle consulter.
    if (comp.type === "extrait" && comp.section) {
      const page = pdfSections?.[comp.section];
      if (page) goPage(page, comp);
    }
  };

  /* ── Status — taxonomie partagée (voir frontend/src/utils/kpiStatus.js) :
     Extrait / Calculé, ou Non extrait / Non calculé si absent, avec une
     alerte Aberrant en plus si la valeur est présente mais suspecte. Le cas
     "recalculé" (formule de secours quand la ligne directe manquait) est
     fondu dans "Calculé" sans marqueur à part, comme validé — classifyCell
     résout déjà la valeur (extraite, calculée ou recalculée de secours),
     pas besoin de dupliquer cette logique ici. ── */
  const anomalies = qualData?.anomalies ?? [];
  const cellStatus = classifyCell(code, kpiName, qualData, raw);
  const s      = resolveCellVisual(cellStatus);
  const valStr = fmtVal(cellStatus.value, kpiName);

  const activeComp = activeIdx !== null ? meta?.composantes?.[activeIdx] : null;
  // Lien web (portail INS...) du KPI "externe" actuellement affiché, quand
  // il n'a pas de PDF — permet au panneau de droite d'afficher un état
  // "donnée web" au lieu de réutiliser le message "PDF non disponible
  // localement" (trompeur ici : il n'y a jamais eu de PDF à trouver).
  const noPdfLien = activeComp?.type === "externe" ? activeComp.lien
    : meta?.type === "externe" ? meta.lien
    : null;

  /* Diagnostic d'anomalie intégré — remplace la navigation vers une page
     séparée (voir Partie 3 du plan) : toute anomalie déjà classifiée par
     étape/couche pour ce code+kpi+année est affichée directement ici. */
  const allSysAnomalies = anomaliesData?.anomalies ?? [];
  const kpiAnomalies = allSysAnomalies.filter(a => a.code === code && a.kpi === kpiName);
  const shownAnomaly = kpiAnomalies[selectedAnomalyIdx] ?? kpiAnomalies[0] ?? null;
  const goToUpstreamAnomaly = (upstreamAnomalie) => {
    if (upstreamAnomalie.code === code && upstreamAnomalie.kpi === kpiName) {
      const idx = kpiAnomalies.indexOf(upstreamAnomalie);
      if (idx >= 0) setSelectedAnomalyIdx(idx);
      return;
    }
    navigate(`/kpi-detail?code=${encodeURIComponent(upstreamAnomalie.code)}&kpi=${encodeURIComponent(upstreamAnomalie.kpi)}&annee=${annee}`);
  };

  return (
    <div style={{ minHeight: "calc(100vh - 92px)", background: "#F2F5FB", fontFamily: "Barlow, system-ui, sans-serif" }}>

      {/* ── Barre de navigation contextuelle ── */}
      <div style={{
        background: "#fff", borderBottom: "1px solid #E5E7EB",
        padding: "12px 32px",
        display: "flex", alignItems: "center", gap: 16,
      }}>
        <button
          onClick={() => navigate("/qualite-donnees")}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            background: "none", border: "1px solid #E5E7EB", borderRadius: 7,
            padding: "6px 12px", cursor: "pointer",
            fontSize: 12, fontWeight: 600, color: "#6B7280",
          }}
          onMouseEnter={e => { e.currentTarget.style.background = "#F9FAFB"; e.currentTarget.style.color = "#111827"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "none"; e.currentTarget.style.color = "#6B7280"; }}
        >
          <svg viewBox="0 0 12 12" fill="none" width="11" height="11">
            <path d="M8 2L4 6l4 4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Qualité des données
        </button>

        <span style={{ color: "#D1D5DB" }}>/</span>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#6B7280", padding: "3px 10px", background: "#F3F4F6", borderRadius: 6 }}>
            {code}
          </span>
          <span style={{ fontSize: 14, fontWeight: 700, color: "#111827" }}>{kpiLabel(kpiName, code)}</span>
          <span
            title={s.detail}
            style={{
              fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 12,
              background: s.bg, color: s.color,
              border: s.aberrant ? "2px solid #F59E0B" : "none",
            }}
          >
            {s.icon} {s.label}{s.aberrant ? " · ⚠ Aberrant" : ""}
          </span>
          {valStr && (
            <span style={{
              fontSize: 13, fontWeight: 800, color: "#111827",
              fontVariantNumeric: "tabular-nums",
              padding: "3px 12px", background: "#F9FAFB", borderRadius: 8,
              border: "1px solid #E5E7EB",
            }}>
              {valStr}
            </span>
          )}
        </div>

        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {(years.includes(annee) ? years : [...years, annee].sort((a, b) => b - a)).map(y => (
            <button
              key={y}
              onClick={() => navigate(`/kpi-detail?code=${encodeURIComponent(code)}&kpi=${encodeURIComponent(kpiName)}&annee=${y}`)}
              style={{
                padding: "5px 12px", borderRadius: 6, fontSize: 12, fontWeight: 600,
                border: "1px solid #E5E7EB", cursor: "pointer",
                background: y === annee ? "#111827" : "#fff",
                color: y === annee ? "#fff" : "#6B7280",
              }}
            >
              {y}
            </button>
          ))}
        </div>
      </div>

      {/* ── Corps en deux colonnes ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 0,
        height: "calc(100vh - 92px - 57px)",
        overflow: "hidden",
      }}>

        {/* ══ Colonne gauche : formule + composantes ══ */}
        <div style={{
          padding: "28px 32px",
          overflowY: "auto",
          borderRight: "1px solid #E5E7EB",
          display: "flex", flexDirection: "column", gap: 28,
        }}>
          {/* Diagnostic d'anomalie intégré — toujours visible ici s'il y a un
              problème, pas besoin de naviguer vers une autre page. */}
          {shownAnomaly && (
            <section>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#DC2626", marginBottom: 12 }}>
                Anomalie détectée
              </div>
              <div style={{ background: "#fff", border: "1px solid #FECACA", borderRadius: 10, padding: "18px 20px" }}>
                <AnomalyDetail
                  anomalie={shownAnomaly}
                  allAnomalies={allSysAnomalies}
                  onSelectAnomalie={goToUpstreamAnomaly}
                />
              </div>
            </section>
          )}

          {/* Section formule */}
          {meta?.type === "calcule" && (
            <section>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#9CA3AF", marginBottom: 12 }}>
                Formule de calcul
              </div>
              <div style={{ background: "#fff", border: "1px solid #E5E7EB", borderRadius: 10, padding: "20px 22px" }}>
                <MathFormula meta={meta} raw={raw} activeIdx={activeIdx} onChipClick={handleChipClick} />
                {meta.note && (
                  <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid #F3F4F6", fontSize: 11, color: "#6B7280", fontStyle: "italic", lineHeight: 1.5 }}>
                    {meta.note}
                  </div>
                )}
              </div>
              <div style={{ marginTop: 8, display: "flex", gap: 14, fontSize: 10, color: "#9CA3AF", flexWrap: "wrap" }}>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ padding: "1px 5px", borderRadius: 3, background: "#EEF2FF", border: "1px solid #C7D2FE", color: "#4338CA", fontWeight: 700, fontSize: 9 }}>𝑓</span>
                  Calculé — cliquer pour décomposer
                </span>
                <span style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ padding: "1px 5px", borderRadius: 3, background: "#F0FDF4", border: "1px solid #BBF7D0", color: "#15803D", fontWeight: 700, fontSize: 9 }}>⊡</span>
                  Extrait PDF — cliquer pour localiser
                </span>
              </div>
            </section>
          )}

          {/* KPI directement extrait */}
          {meta?.type === "extrait" && (
            <section>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#9CA3AF", marginBottom: 12 }}>
                Source dans le PDF
              </div>
              <ExtraitDetail
                node={{ ...meta, label: kpiLabel(kpiName, code), rawKey: meta.rawKey ?? kpiName }}
                annee={annee}
                pdfSections={pdfSections}
                onGoPage={goPage}
                code={code}
                onGoArabicPage={goArabicPage}
              />
            </section>
          )}

          {/* KPI sectoriel direct (Population, Total agences...) — pas de
              formule ni de PDF société, voir kpiMeta.js "KPI sectoriels" et
              ExterneDetail. Ajouté le 2026-08-19 : ces KPI n'avaient
              jusqu'ici AUCUN rendu au premier niveau (seul `type: "extrait"`
              et `type: "calcule"` étaient gérés ici), donc rien ne
              s'affichait pour eux malgré une entrée kpiMeta correcte. */}
          {meta?.type === "externe" && (
            <section>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#9CA3AF", marginBottom: 12 }}>
                Source du KPI sectoriel
              </div>
              <ExterneDetail node={{ ...meta, label: kpiName ? kpiLabel(kpiName, code) : meta.label }} annee={annee} raw={raw} onLocate={goSectorPage} />
            </section>
          )}

          {/* Détail de la composante sélectionnée */}
          {activeComp && (
            <section>
              <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#9CA3AF", marginBottom: 12, display: "flex", alignItems: "center", gap: 10 }}>
                Détail — {activeComp.label}
                <button
                  onClick={() => { setActiveIdx(null); setHighlight(null); }}
                  style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", fontSize: 16, lineHeight: 1, padding: "0 2px" }}
                >×</button>
              </div>
              {activeComp.type === "calcule" && (
                <CalcDetail node={activeComp} raw={raw} annee={annee} pdfSections={pdfSections} onGoPage={goPage} code={code} onGoArabicPage={goArabicPage} />
              )}
              {activeComp.type === "extrait" && (
                <ExtraitDetail node={activeComp} annee={annee} pdfSections={pdfSections} onGoPage={goPage} code={code} onGoArabicPage={goArabicPage} />
              )}
              {activeComp.type === "externe" && <ExterneDetail node={activeComp} annee={annee} raw={raw} onLocate={goSectorPage} />}
            </section>
          )}

          {/* Guide si rien de sélectionné */}
          {!activeComp && meta?.type === "calcule" && (
            <div style={{
              padding: "16px 20px", borderRadius: 10,
              border: "1px dashed #D1D5DB", background: "#F9FAFB",
              fontSize: 12, color: "#9CA3AF", textAlign: "center", lineHeight: 1.6,
            }}>
              Cliquez sur un élément de la formule pour voir<br/>
              sa source exacte dans le PDF et sa décomposition.
            </div>
          )}
        </div>

        {/* ══ Colonne droite : PDF avec overlay ══ */}
        <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>

          {/* Barre PDF */}
          <div style={{
            padding: "10px 20px", background: "#1E293B",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            flexShrink: 0,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <rect x="2" y="1" width="12" height="14" rx="2" stroke="#94A3B8" strokeWidth="1.3"/>
                <path d="M5 5h6M5 8h4M5 11h5" stroke="#94A3B8" strokeWidth="1.1" strokeLinecap="round"/>
              </svg>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#94A3B8" }}>PDF — {code} · {annee}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {highlight && highlight.note && (
                <span
                  title={highlight.note}
                  style={{
                    fontSize: 10, fontWeight: 700, padding: "3px 10px",
                    borderRadius: 8, background: "#0c2d48", color: "#7dd3fc",
                    display: "flex", alignItems: "center", gap: 5, cursor: "help",
                  }}
                >
                  <span style={{ fontSize: 12 }}>📍</span> Cellule surlignée — somme sur 2 pages
                </span>
              )}
              {highlight && !highlight.note && (
                <span style={{
                  fontSize: 10, fontWeight: 700, padding: "3px 10px",
                  borderRadius: 8, background: "#450a0a", color: "#fca5a5",
                  display: "flex", alignItems: "center", gap: 5,
                }}>
                  <span style={{ fontSize: 12 }}>📍</span> Cellule surlignée
                </span>
              )}
              {!highlight && noHighlightReason && (
                <span
                  title={NO_HIGHLIGHT_LABELS[noHighlightReason] ?? NO_HIGHLIGHT_LABELS.inconnue}
                  style={{
                    fontSize: 10, fontWeight: 700, padding: "3px 10px",
                    borderRadius: 8, background: "#422006", color: "#fcd34d",
                    display: "flex", alignItems: "center", gap: 5, cursor: "help",
                  }}
                >
                  <span style={{ fontSize: 12 }}>⚠</span> Non surligné : {NO_HIGHLIGHT_LABELS[noHighlightReason] ?? NO_HIGHLIGHT_LABELS.inconnue}
                </span>
              )}
              {pdfPage && (
                <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 10px", borderRadius: 8, background: "#334155", color: "#CBD5E1" }}>
                  Page {pdfPage}
                </span>
              )}
              {detail?.pdf_lien && (
                <a href={detail.pdf_lien} target="_blank" rel="noreferrer"
                  style={{ fontSize: 11, fontWeight: 600, color: "#60A5FA", textDecoration: "none", display: "flex", alignItems: "center", gap: 4 }}>
                  <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
                    <path d="M5 2H2a1 1 0 00-1 1v7a1 1 0 001 1h7a1 1 0 001-1V8M8 1h3m0 0v3m0-3L5 7" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  CMF
                </a>
              )}
            </div>
          </div>

          {/* PDF Canvas ou placeholder */}
          {pdfUrl && pdfPage ? (
            <PdfCanvas pdfUrl={pdfUrl} pageNum={pdfPage} highlight={highlight} />
          ) : pdfUrl ? (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#1E293B", gap: 14 }}>
              <svg viewBox="0 0 48 48" fill="none" width="40" height="40">
                <path d="M24 10v14M24 28v2" stroke="#60A5FA" strokeWidth="2.5" strokeLinecap="round"/>
                <circle cx="24" cy="24" r="20" stroke="#334155" strokeWidth="2"/>
              </svg>
              <div style={{ textAlign: "center", fontSize: 13, color: "#64748B", lineHeight: 1.6 }}>
                Cliquez sur un élément de la formule<br/>pour ouvrir la page PDF correspondante.
              </div>
            </div>
          ) : noPdfLien ? (
            // KPI "externe" sans PDF (série statistique en ligne, ex. INS) :
            // pas de document à paginer/surligner, donc pas de panneau PDF
            // vide — juste un accès direct à la source web, sur demande
            // explicite de l'utilisateur ("trouvez autre chose que
            // d'afficher un espace pdf" pour ce cas, 2026-08-19).
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#1E293B", gap: 16, padding: "0 32px" }}>
              <svg viewBox="0 0 48 48" fill="none" width="44" height="44">
                <circle cx="24" cy="24" r="19" stroke="#475569" strokeWidth="2"/>
                <ellipse cx="24" cy="24" rx="8" ry="19" stroke="#475569" strokeWidth="2"/>
                <path d="M5 24h38M24 5v38" stroke="#475569" strokeWidth="1.4"/>
                <path d="M7.5 15h33M7.5 33h33" stroke="#475569" strokeWidth="1.4"/>
              </svg>
              <div style={{ textAlign: "center", fontSize: 13, color: "#94A3B8", lineHeight: 1.6, maxWidth: 300 }}>
                Donnée issue d'une série statistique en ligne — pas de document PDF associé.
              </div>
              <a href={noPdfLien} target="_blank" rel="noreferrer" style={{
                fontSize: 12, fontWeight: 700, color: "#0F172A", background: "#60A5FA",
                padding: "9px 18px", borderRadius: 8, textDecoration: "none",
              }}>
                Ouvrir le portail source ↗
              </a>
            </div>
          ) : (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#1E293B", gap: 14 }}>
              <svg viewBox="0 0 48 48" fill="none" width="48" height="48">
                <rect x="8" y="4" width="32" height="40" rx="4" stroke="#475569" strokeWidth="2"/>
                <path d="M16 16h16M16 22h12M16 28h14" stroke="#475569" strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
              <div style={{ textAlign: "center", fontSize: 13, color: "#64748B", lineHeight: 1.6 }}>
                PDF non disponible localement.<br/>
                {detail?.pdf_lien && (
                  <a href={detail.pdf_lien} target="_blank" rel="noreferrer" style={{ color: "#60A5FA", fontWeight: 600 }}>
                    Télécharger depuis le CMF →
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Navigation rapide entre sections */}
          {pdfSections && (
            <div style={{
              padding: "10px 16px", background: "#F8FAFC",
              borderTop: "1px solid #E5E7EB",
              display: "flex", gap: 8, flexWrap: "wrap", flexShrink: 0,
            }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: "#9CA3AF", alignSelf: "center", marginRight: 4 }}>ALLER À :</span>
              {Object.entries(pdfSections).map(([section, page]) => {
                const labels = { annexe12: "Annexe 12", annexe13: "Annexe 13", bilan: "Bilan", etat_resultat: "État résultat" };
                return (
                  <button
                    key={section}
                    onClick={() => goPage(page, section)}
                    style={{
                      padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 600,
                      border: `1px solid ${pdfPage === page ? "#BFDBFE" : "#E5E7EB"}`,
                      background: pdfPage === page ? "#EFF6FF" : "#fff",
                      color: pdfPage === page ? "#1D4ED8" : "#6B7280",
                      cursor: "pointer",
                      display: "flex", alignItems: "center", gap: 5,
                    }}
                  >
                    {labels[section] ?? section}
                    <span style={{ fontSize: 9, fontWeight: 700, padding: "0 4px", background: "#DBEAFE", color: "#1D4ED8", borderRadius: 4 }}>
                      p.{page}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
