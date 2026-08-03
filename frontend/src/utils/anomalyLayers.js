/**
 * Classification des anomalies par COUCHE du pipeline (Extraction / Cleaning
 * data / Modélisation) et détection de PROPAGATION AMONT (une anomalie sur
 * un KPI composite peut être causée par une anomalie sur un KPI utilisé
 * dans sa formule, pour la même société/année).
 *
 * Réutilise KPI_META (déjà la source de vérité pour l'arbre de dépendance
 * des KPI côté KpiDetail.jsx) plutôt que extraction/kpi_definitions.py
 * (backend, texte libre, sujet à dérive — voir CAS_PARTICULIERS_QUALITE.md).
 */
import { KPI_META } from "./kpiMeta";

export const LAYERS = {
  EXTRACTION:    "Extraction",
  CLEANING:      "Cleaning data",
  MODELISATION:  "Modélisation",
};

export const LAYER_COLOR = {
  [LAYERS.EXTRACTION]:   { bg: "#FFF7ED", text: "#EA580C", border: "#FED7AA" },
  [LAYERS.CLEANING]:     { bg: "#EFF6FF", text: "#1D4ED8", border: "#BFDBFE" },
  [LAYERS.MODELISATION]: { bg: "#F5F3FF", text: "#6D28D9", border: "#DDD6FE" },
};

/**
 * Étape (1-7, voir api/services/pipeline_audit.py) -> couche.
 *   1 PDF manquant, 2 section non détectée, 3 composante manquante,
 *   5 valeur brute absente  → Extraction
 *   7 déséquilibre Bilan / variation YoY implausible → Cleaning data
 *   4 recalculé              → Modélisation
 *   6 valeur aberrante       → Modélisation si le KPI est "calcule" dans
 *                              KPI_META (l'aberration vient du calcul),
 *                              sinon Extraction (l'aberration vient de la
 *                              lecture PDF elle-même).
 *   8 doublure RC≈RF         → Extraction (même cellule PDF lue deux fois
 *                              pour deux KPI distincts — voir quality.py).
 *   9 écart sectoriel        → même logique que l'étape 6 (dépend du type
 *                              du KPI dans KPI_META).
 */
export function getLayer(etape, kpiName) {
  if (etape === 7) return LAYERS.CLEANING;
  if (etape === 4) return LAYERS.MODELISATION;
  if (etape === 8) return LAYERS.EXTRACTION;
  if (etape === 6 || etape === 9) {
    const meta = KPI_META[kpiName];
    return meta?.type === "calcule" ? LAYERS.MODELISATION : LAYERS.EXTRACTION;
  }
  if ([1, 2, 3, 5].includes(etape)) return LAYERS.EXTRACTION;
  return null;
}

// Cache : nom de KPI -> Set des rawKey apparaissant dans son arbre de
// composantes/sousComposantes (mémoïsé, KPI_META est statique).
const _upstreamCache = new Map();

function _collectRawKeys(node, acc) {
  if (!node) return;
  if (node.rawKey) acc.add(node.rawKey);
  for (const c of node.composantes ?? []) {
    if (c.rawKey) acc.add(c.rawKey);
    _collectRawKeys(c, acc);
  }
  for (const c of node.sousComposantes ?? []) {
    if (c.rawKey) acc.add(c.rawKey);
    _collectRawKeys(c, acc);
  }
}

/** Ensemble des noms de KPI/composantes dont dépend `kpiName` (récursif). */
export function getUpstreamKeys(kpiName) {
  if (_upstreamCache.has(kpiName)) return _upstreamCache.get(kpiName);
  const meta = KPI_META[kpiName];
  const acc = new Set();
  if (meta?.type === "calcule") _collectRawKeys(meta, acc);
  _upstreamCache.set(kpiName, acc);
  return acc;
}

/**
 * Pour une anomalie donnée et la liste complète des anomalies de la même
 * année, retourne l'anomalie AMONT la plus probable (même société, KPI
 * présent dans l'arbre de dépendance de l'anomalie courante), ou null.
 * Ignore les propagations `manquant` déjà expliquées par une composante
 * elle-même manquante que le message existant couvre déjà — on garde tout
 * de même le lien car il précise QUELLE composante est en cause.
 */
export function findUpstreamCause(anomalie, allAnomalies) {
  if (!anomalie?.kpi || !anomalie?.code) return null;
  const upstream = getUpstreamKeys(anomalie.kpi);
  if (upstream.size === 0) return null;
  return allAnomalies.find(b =>
    b !== anomalie &&
    b.code === anomalie.code &&
    b.annee === anomalie.annee &&
    b.kpi && b.kpi !== anomalie.kpi &&
    upstream.has(b.kpi)
  ) ?? null;
}
