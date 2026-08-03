/**
 * Catalogue KPI canonique — source unique de vérité pour le NOM AFFICHÉ et
 * l'unité de chaque KPI, réutilisé par toutes les pages qui en montrent la
 * liste (AnalyseComparative, QualiteDonnees, KpiDetail, RapportPipeline,
 * AnomaliesSysteme).
 *
 * Ne touche PAS aux clés de stockage (storageKey) : ce sont les chaînes
 * exactes utilisées dans database.kpi_values.kpi, KPI_META, quality.py
 * (_EXPECTED_KPIS), pipeline_audit.py — les renommer serait une migration de
 * données (colonne VARCHAR sans FK, aucune table de référence) qui casse
 * silencieusement tout consommateur oublié. Seul le libellé affiché change.
 */

export const KPI_CATALOG = [
  {
    storageKey: "Primes émises par assurance",
    label: "Primes émises",
    unit: "MDT",
    lowerBetter: false,
  },
  {
    storageKey: "Ratio combiné (%)",
    label: "Ratio combiné",
    unit: "%",
    lowerBetter: true,
  },
  {
    storageKey: "Ratio de sinistralité (%)",
    label: "Ratio de sinistralité",
    unit: "%",
    lowerBetter: true,
  },
  {
    storageKey: "Ratio de frais de gestion (%)",
    label: "Ratio de frais de gestion",
    unit: "%",
    lowerBetter: true,
  },
  {
    storageKey: "Part de marché (%)",
    label: "Part de marché",
    unit: "%",
    lowerBetter: false,
  },
  {
    storageKey: "ROE (%)",
    label: "ROE",
    unit: "%",
    lowerBetter: false,
  },
  {
    storageKey: "ROA (%)",
    label: "ROA",
    unit: "%",
    lowerBetter: false,
  },
  {
    storageKey: "Résultat Net",
    label: "Résultat net",
    unit: "TND",
    lowerBetter: false,
  },
  {
    storageKey: "Total actif",
    label: "Total actif",
    unit: "TND",
    lowerBetter: false,
  },
  {
    storageKey: "Résultat technique (TND)",
    label: "Résultat technique",
    unit: "TND",
    lowerBetter: false,
  },
  {
    storageKey: "Capitaux propres",
    label: "Capitaux propres",
    unit: "TND",
    lowerBetter: false,
  },
];

const _byStorageKey = new Map(KPI_CATALOG.map(k => [k.storageKey, k]));

/** {storageKey, label, unit, lowerBetter} ou repli minimal si KPI inconnu. */
export function getKpiInfo(storageKey) {
  return _byStorageKey.get(storageKey) ?? { storageKey, label: storageKey, unit: "", lowerBetter: false };
}

/** Nom canonique à afficher pour une clé de stockage donnée. */
export function kpiLabel(storageKey) {
  return getKpiInfo(storageKey).label;
}
