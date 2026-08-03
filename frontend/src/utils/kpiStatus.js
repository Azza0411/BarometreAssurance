/**
 * Classification d'une cellule (société × KPI × année) selon la taxonomie
 * validée avec l'utilisateur :
 *
 *   Nature (mutuellement exclusive) :
 *     - "extrait" : lu directement dans une ligne du PDF
 *     - "calcule"  : résultat d'une formule (KPI extraits et/ou calculés, récursif)
 *
 *   Si la valeur est absente :
 *     - "non_extrait" (nature extrait)  : la ligne attendue est introuvable
 *     - "non_calcule" (nature calcule)  : une composante manque quelque part
 *       dans la chaîne — on remonte pour identifier laquelle (rootCause)
 *
 *   Si la valeur est présente, une alerte peut s'ajouter EN PLUS (pas à la
 *   place) de la nature : "aberrant" — détecté côté backend par écart
 *   année sur année, écart au secteur, ou zéro structurellement impossible
 *   (voir extraction/data_cleaning.py::YOY_CHECKED_KPIS et
 *   api/services/quality.py::_ZERO_SUSPECT_KPIS).
 */
import { KPI_META } from "./kpiMeta";

/** Cherche, dans l'arbre de composantes, le premier nœud dont la valeur
 * brute est absente — sert à expliquer un "non_calcule" plutôt que de dire
 * juste "ça manque". Ignore les nœuds "externe" (hors CMF, ex. FTUSA),
 * impossibles à vérifier depuis les données de qualité CMF seules. */
function findMissingComponent(node, kpisRaw) {
  const children = node.composantes ?? node.sousComposantes ?? [];
  for (const c of children) {
    if (c.type === "externe") continue;
    const val = c.rawKey ? kpisRaw?.[c.rawKey] : undefined;
    const missing = val === undefined || val === null;
    if (missing) {
      if (c.type === "calcule" && c.sousComposantes?.length) {
        const nested = findMissingComponent(c, kpisRaw);
        if (nested) return nested;
      }
      return c.label ?? c.rawKey;
    }
  }
  return null;
}

/**
 * Classifie une cellule. Retourne :
 *   { nature: "extrait"|"calcule",
 *     available: bool,
 *     value: number|null,         // valeur à afficher — résolue ici une
 *                                 // fois pour toutes (extraite, calculée,
 *                                 // OU recalculée de secours), pour que
 *                                 // chaque page ne réinvente pas sa propre
 *                                 // logique de repli et diverge des autres
 *                                 // (voir bug : cellule "Non calculé" ici
 *                                 // alors que d'autres pages affichaient
 *                                 // déjà la valeur recalculée)
 *     rootCause: string|null,     // uniquement si !available && nature==="calcule"
 *     aberrant: bool,
 *     aberrantReasons: string[] } // raisons textuelles, depuis data.anomalies
 */
export function classifyCell(code, storageKey, data) {
  const meta   = KPI_META[storageKey];
  const nature = meta?.type === "calcule" ? "calcule" : "extrait";
  const detail = data?.kpi_detail?.[code];
  const anomalies = data?.anomalies ?? [];

  const aberrantReasons = anomalies
    .filter(a => a.code === code && a.kpi === storageKey && a.type === "aberrant")
    .map(a => a.raison)
    .filter(Boolean);

  if (!detail) {
    return { nature, available: false, value: null, rootCause: null, aberrant: false, aberrantReasons: [] };
  }

  const available = detail.present?.includes(storageKey) ?? false;
  if (available) {
    return {
      nature, available: true, value: detail.kpis_raw?.[storageKey] ?? null, rootCause: null,
      aberrant: detail.aberrant?.includes(storageKey) ?? false,
      aberrantReasons,
    };
  }

  // Recalcul de secours (kpi_builder) : la ligne directe manquait, mais une
  // formule de repli a quand même produit une valeur — c'est celle que
  // d'autres pages (Analyse Comparative, Aperçu Marché...) affichent déjà
  // via ce même calcul. Compter cette cellule comme "non calculé" alors
  // qu'une vraie valeur existe et circule ailleurs serait trompeur.
  const recalc = anomalies.find(a => a.type === "recalcule" && a.code === code && a.kpi === storageKey);
  if (recalc) {
    return { nature, available: true, value: recalc.valeur ?? null, rootCause: null, aberrant: false, aberrantReasons: [] };
  }

  const rootCause = nature === "calcule" && meta
    ? findMissingComponent(meta, detail.kpis_raw)
    : null;

  return { nature, available: false, value: null, rootCause, aberrant: false, aberrantReasons: [] };
}

/** Libellé + icône pour l'affichage — un seul endroit pour tout l'app. */
export const CELL_VISUAL = {
  extrait:     { icon: "⊡", color: "#15803D", bg: "#F0FDF4", border: "#86EFAC", label: "Extrait" },
  calcule:     { icon: "ƒ", color: "#4338CA", bg: "#EEF2FF", border: "#C7D2FE", label: "Calculé" },
  non_extrait: { icon: "✗", color: "#6B7280", bg: "#F3F4F6", border: "#D1D5DB", label: "Non extrait" },
  non_calcule: { icon: "⊘", color: "#6B7280", bg: "#F3F4F6", border: "#D1D5DB", label: "Non calculé" },
};

/** Résout la classification en {icon, color, bg, border, label, detail}
 * prêt à afficher — `detail` est la phrase complète pour le survol/sous-titre. */
export function resolveCellVisual(status) {
  const key = status.available ? status.nature : (status.nature === "extrait" ? "non_extrait" : "non_calcule");
  const v = CELL_VISUAL[key];
  let detail = v.label;
  if (!status.available && status.rootCause) {
    detail = `Non calculé — cause : ${status.rootCause}`;
  } else if (!status.available && key === "non_extrait") {
    detail = "Non extrait — ligne introuvable dans le PDF";
  }
  return { ...v, detail, aberrant: status.aberrant, aberrantReasons: status.aberrantReasons };
}
