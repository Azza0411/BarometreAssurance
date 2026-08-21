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
import { isTakaful } from "./famille";

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

// S4/S5/I1/I2 (Dettes/CP, Dettes/Actif, Actions/Actif, Placements/CP) sont
// VOLONTAIREMENT absents de KPI_CATALOG ci-dessus : ce catalogue est partagé
// avec QualiteDonnees/KpiDetail/RapportPipeline/AnomaliesSysteme, qui
// l'utilisent pour lister les KPI EXTRAITS/CALCULÉS et PERSISTÉS en base
// (kpi_values). Ces 4 ratios sont calculés à la volée à la lecture
// (api/services/kpi_builder.py::compute_solvabilite_investissement), jamais
// écrits en base — les y ajouter faisait afficher "✗ Non extrait" sur ces
// 4 colonnes pour TOUTES les compagnies dans Qualité Données (faux
// positif : rien n'est réellement manquant, juste jamais persisté).
// N'existent donc que dans LABELS_HORS_CATALOGUE, consommé uniquement par
// AnalyseComparative.jsx (le seul endroit qui en a besoin).
export const LABELS_HORS_CATALOGUE = {
  "Dettes/Capitaux propres (%)":    { label: "Dettes / Capitaux propres",    unit: "%", lowerBetter: true  },
  "Dettes/Actif (%)":               { label: "Dettes / Actif",               unit: "%", lowerBetter: true  },
  "Actions/Actif (%)":              { label: "Actions / Actif",              unit: "%", lowerBetter: false },
  "Placements/Capitaux propres (%)":{ label: "Placements / Capitaux propres", unit: "%", lowerBetter: false },
};

const _byStorageKey = new Map(KPI_CATALOG.map(k => [k.storageKey, k]));

/** {storageKey, label, unit, lowerBetter} ou repli minimal si KPI inconnu. */
export function getKpiInfo(storageKey) {
  return _byStorageKey.get(storageKey) ?? { storageKey, label: storageKey, unit: "", lowerBetter: false };
}

// Terminologie propre au Takaful : "Contribution" (cotisation mutualiste)
// est le terme technique exact, "Primes émises" étant un terme d'assurance
// conventionnelle qui ne s'applique pas au principe Takaful — signalé par
// l'utilisateur le 2026-08-19 ("au lieu d'écrire prime émise on doit écrire
// contribution").
const _TAKAFUL_LABEL_OVERRIDES = {
  "Primes émises par assurance": "Contribution",
};

/** Nom canonique à afficher pour une clé de stockage donnée. `code` (optionnel) :
 * société courante — permet d'adapter le libellé pour le Takaful (ex.
 * "Contribution" au lieu de "Primes émises"). Sans `code`, comportement
 * inchangé (utilisé par les colonnes/menus statiques non liés à une société). */
export function kpiLabel(storageKey, code) {
  if (code && _TAKAFUL_LABEL_OVERRIDES[storageKey] && isTakaful(code)) {
    return _TAKAFUL_LABEL_OVERRIDES[storageKey];
  }
  return getKpiInfo(storageKey).label;
}
