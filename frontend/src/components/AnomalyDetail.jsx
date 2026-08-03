import { getLayer, LAYER_COLOR, findUpstreamCause } from "../utils/anomalyLayers";
import { kpiLabel } from "../utils/kpiCatalog";

/**
 * Diagnostic complet d'une anomalie (gravité, couche, cause, recommandation,
 * propagation amont) — extrait de AnomaliesSysteme.jsx pour être réutilisé
 * tel quel dans KpiDetail.jsx (affichage en place, sans navigation vers une
 * page séparée) et dans AnomaliesSysteme.jsx (panneau détail).
 */
const GRAVITE_COLOR = {
  "Critique": { bg:"#FEF2F2", text:"#DC2626", border:"#FECACA" },
  "Élevée":   { bg:"#FFF7ED", text:"#EA580C", border:"#FED7AA" },
  "Moyenne":  { bg:"#FEFCE8", text:"#CA8A04", border:"#FEF08A" },
  "Faible":   { bg:"#F0FDF4", text:"#16A34A", border:"#BBF7D0" },
};

export function GravBadge({ g }) {
  const col = GRAVITE_COLOR[g] || { bg:"#F3F4F6", text:"#6B7280", border:"#E5E7EB" };
  return (
    <span style={{
      background: col.bg, color: col.text,
      border: `1px solid ${col.border}`,
      borderRadius: 20, padding: "2px 9px",
      fontSize: 10.5, fontWeight: 700,
    }}>{g}</span>
  );
}

export function LayerBadge({ layer }) {
  if (!layer) return null;
  const col = LAYER_COLOR[layer] || { bg:"#F3F4F6", text:"#6B7280", border:"#E5E7EB" };
  return (
    <span style={{
      background: col.bg, color: col.text,
      border: `1px solid ${col.border}`,
      borderRadius: 20, padding: "2px 9px",
      fontSize: 10.5, fontWeight: 700, whiteSpace: "nowrap",
    }}>{layer}</span>
  );
}

const CAUSE_PAR_ETAPE = {
  1: "PDF source absent ou non collecté lors du scraping.",
  2: "Section non détectée dans le PDF — pattern de titre non reconnu.",
  3: "Libellé de composante introuvable dans le tableau PDF extrait.",
  4: "KPI recalculé avec composantes partiellement disponibles.",
  5: "Valeur brute absente dans la cellule ciblée du tableau PDF.",
  6: "Valeur hors plage métier — probable décalage de colonne ou mauvaise unité.",
  7: "Incohérence détectée à l'étape de nettoyage (Cleaning data) : déséquilibre du Bilan (Total actif ≠ Capitaux propres + Passif) ou variation année sur année implausible.",
  8: "Ratio combiné et Ratio de frais quasi identiques — probable lecture de la même cellule PDF pour deux KPI distincts.",
  9: "Valeur individuellement plausible mais très éloignée de la moyenne du secteur pour la même année.",
};

export default function AnomalyDetail({ anomalie, allAnomalies, onSelectAnomalie }) {
  if (!anomalie) return null;

  const a = anomalie;
  const layer = getLayer(a.etape, a.kpi);
  const upstream = allAnomalies ? findUpstreamCause(a, allAnomalies) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* Titre */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <GravBadge g={a.dq_gravite} />
        <LayerBadge layer={layer} />
        <span style={{ fontSize: 10, color: "#8896A8" }}>Étape {a.etape}</span>
      </div>

      {/* Propagation amont */}
      {upstream && (
        <div
          onClick={() => onSelectAnomalie?.(upstream)}
          style={{
            background: "#FEF2F2", border: "1px solid #FECACA", borderRadius: 8,
            padding: "12px 14px", cursor: onSelectAnomalie ? "pointer" : "default",
          }}
        >
          <div style={{ fontSize: 10, fontWeight: 700, color: "#DC2626", textTransform: "uppercase",
            letterSpacing: "1px", marginBottom: 6 }}>Cause probable — propagée</div>
          <div style={{ fontSize: 11.5, color: "#991B1B", lineHeight: 1.6 }}>
            Cette valeur dépend de <strong>{kpiLabel(upstream.kpi)}</strong>, qui présente elle-même
            une anomalie ({upstream.type}, étape {upstream.etape}) pour {a.code} · {a.annee}.
            {onSelectAnomalie && <> Cliquez pour voir l'anomalie amont.</>}
          </div>
        </div>
      )}

      {/* Cause probable */}
      <div>
        <div style={{ fontSize: 10, fontWeight: 700, color: "#8896A8", textTransform: "uppercase",
          letterSpacing: "1px", marginBottom: 6 }}>Cause probable</div>
        <div style={{ fontSize: 11.5, color: "#4A5568", lineHeight: 1.6 }}>
          {CAUSE_PAR_ETAPE[a.etape] ?? "Cause non déterminée."}
        </div>
      </div>

      {/* Recommandation */}
      {a.recommandation && (
        <div style={{ background: "#EFF6FF", border: "1px solid #BFDBFE", borderRadius: 8, padding: "12px 14px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#1D4ED8", textTransform: "uppercase",
            letterSpacing: "1px", marginBottom: 6 }}>Recommandation</div>
          <div style={{ fontSize: 11.5, color: "#1E40AF", lineHeight: 1.65 }}>
            {a.recommandation}
          </div>
        </div>
      )}

      {a.composantes_manquantes?.length > 0 && (
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: "#8896A8", textTransform: "uppercase",
            letterSpacing: "1px", marginBottom: 6 }}>Composantes manquantes</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {a.composantes_manquantes.map((c, i) => (
              <span key={i} style={{
                background: "#FEF2F2", color: "#DC2626",
                border: "1px solid #FECACA", borderRadius: 4,
                padding: "2px 7px", fontSize: 10,
              }}>{c}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
