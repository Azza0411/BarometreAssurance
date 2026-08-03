/**
 * Définitions des KPIs : type, formule, composantes avec localisation exacte dans le PDF.
 * Source de référence : DVRB (Data Value Realisation Book).
 *
 * Types de nœuds :
 *   "extrait"  → cellule PDF directe    { rawKey, section, tableau, ligne, colonne }
 *   "calcule"  → dérivé d'autres KPIs  { rawKey?, formule, sousComposantes[], denominator? }
 *   "externe"  → source hors PDF CMF   { label, source, tableau, ligne, colonne }
 *
 * denominator: true  → composante au dénominateur d'un ratio (pour l'affichage fraction)
 */
export const KPI_META = {
  /* ── Primes émises ─────────────────────────────────────────────────────── */
  "Primes émises par assurance": {
    type: "calcule",
    formule: "Primes émises Vie + Primes émises Non-Vie",
    note: "Montant brut avant cessions en réassurance.",
    composantes: [
      {
        type: "extrait", rawKey: "Primes émises Vie par assurance",
        label: "Primes émises Vie",
        section: "annexe12",
        tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
        ligne: "Primes émises", colonne: "Total",
      },
      {
        type: "extrait", rawKey: "Primes émises Non-Vie par assurance",
        label: "Primes émises Non-Vie",
        section: "annexe13",
        tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        ligne: "Primes émises", colonne: "Total",
      },
    ],
  },

  /* ── Ratio combiné ─────────────────────────────────────────────────────── */
  "Ratio combiné (%)": {
    type: "calcule",
    formule: "(Charges de prestations + Charges d'acq. et gestion nettes) / Primes émises × 100",
    note: "< 100 % = compagnie bénéficiaire sur le plan technique.",
    composantes: [
      {
        type: "calcule", rawKey: "Charges de prestations",
        label: "Charges de prestations",
        formule: "Charges de prestations Vie + Charges de prestations Non-Vie",
        sousComposantes: [
          {
            type: "extrait", rawKey: "Charges de prestations Vie",
            label: "Charges de prestations Vie",
            section: "annexe12",
            tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
            ligne: "Charges de prestations", colonne: "Total",
          },
          {
            type: "extrait", rawKey: "Charges de prestations Non-Vie",
            label: "Charges de prestations Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Charges de prestations", colonne: "Total",
          },
        ],
      },
      {
        type: "calcule", rawKey: "Charges d'acquisition et de gestion nettes",
        label: "Charges d'acq. et gestion nettes",
        formule: "Charges d'acq. nettes Vie + Charges d'acq. nettes Non-Vie",
        sousComposantes: [
          {
            type: "extrait", rawKey: "Charges d'acquisition et de gestion nettes Vie",
            label: "Charges d'acq. nettes Vie",
            section: "annexe12",
            tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
            ligne: "Charges d'acquisition et de gestion nettes", colonne: "Total",
          },
          {
            type: "extrait", rawKey: "Charges d'acquisition et de gestion nettes Non-Vie",
            label: "Charges d'acq. nettes Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Charges d'acquisition et de gestion nettes", colonne: "Total",
          },
        ],
      },
      {
        type: "calcule", rawKey: "Primes émises par assurance",
        label: "Primes émises", denominator: true,
        formule: "Primes émises Vie + Primes émises Non-Vie",
        sousComposantes: [
          {
            type: "extrait", rawKey: "Primes émises Vie par assurance",
            label: "Primes émises Vie",
            section: "annexe12",
            tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
            ligne: "Primes émises", colonne: "Total",
          },
          {
            type: "extrait", rawKey: "Primes émises Non-Vie par assurance",
            label: "Primes émises Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Primes émises", colonne: "Total",
          },
        ],
      },
    ],
  },

  /* ── Ratio de sinistralité ─────────────────────────────────────────────── */
  "Ratio de sinistralité (%)": {
    type: "calcule",
    formule: "Charges de sinistres (Vie + Non-Vie) / Primes acquises × 100",
    note: "Aussi appelé S/P. Primes acquises = Primes émises ± variation PSAP.",
    composantes: [
      {
        type: "calcule", rawKey: "Charge de sinistres",
        label: "Charges de sinistres",
        formule: "Charges de sinistres Vie + Charges de sinistres Non-Vie",
        sousComposantes: [
          {
            type: "extrait", rawKey: "Charge de sinistres Vie",
            label: "Charges de sinistres Vie",
            section: "annexe12",
            tableau: "État de résultat technique de l'assurance Vie",
            ligne: "CHV1 – Charges de sinistres", colonne: "Opérations nettes",
          },
          {
            type: "extrait", rawKey: "Charge de sinistres Non-Vie",
            label: "Charges de sinistres Non-Vie",
            section: "annexe13",
            tableau: "État de résultat technique de l'assurance Non-Vie",
            ligne: "CHV1 – Charges de sinistres", colonne: "Opérations nettes",
          },
        ],
      },
      {
        type: "extrait", rawKey: "Primes acquises",
        label: "Primes acquises", denominator: true,
        section: "annexe13",
        tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        ligne: "PRIMES ACQUISES", colonne: "Total",
      },
    ],
  },

  /* ── Ratio de frais ────────────────────────────────────────────────────── */
  "Ratio de frais de gestion (%)": {
    type: "calcule",
    formule: "Charges d'acq. et gestion nettes / Primes émises × 100",
    note: "Part des primes absorbée par les frais commerciaux et administratifs.",
    composantes: [
      {
        type: "calcule", rawKey: "Charges d'acquisition et de gestion nettes",
        label: "Charges d'acq. et gestion nettes",
        formule: "Charges d'acq. nettes Vie + Charges d'acq. nettes Non-Vie",
        sousComposantes: [
          {
            type: "extrait", rawKey: "Charges d'acquisition et de gestion nettes Vie",
            label: "Charges d'acq. nettes Vie",
            section: "annexe12",
            tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
            ligne: "Charges d'acquisition et de gestion nettes", colonne: "Total",
          },
          {
            type: "extrait", rawKey: "Charges d'acquisition et de gestion nettes Non-Vie",
            label: "Charges d'acq. nettes Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Charges d'acquisition et de gestion nettes", colonne: "Total",
          },
        ],
      },
      {
        type: "calcule", rawKey: "Primes émises par assurance",
        label: "Primes émises", denominator: true,
        formule: "Primes émises Vie + Primes émises Non-Vie",
        sousComposantes: [
          {
            type: "extrait", rawKey: "Primes émises Vie par assurance",
            label: "Primes émises Vie",
            section: "annexe12",
            tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
            ligne: "Primes émises", colonne: "Total",
          },
          {
            type: "extrait", rawKey: "Primes émises Non-Vie par assurance",
            label: "Primes émises Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Primes émises", colonne: "Total",
          },
        ],
      },
    ],
  },

  /* ── Part de marché ────────────────────────────────────────────────────── */
  "Part de marché (%)": {
    type: "calcule",
    formule: "Primes émises compagnie / Total Primes marché (FTUSA) × 100",
    note: "Calculée par rapport au total des primes déclarées à la FTUSA.",
    composantes: [
      {
        type: "calcule", rawKey: "Primes émises par assurance",
        label: "Primes émises compagnie",
        formule: "Primes émises Vie + Primes émises Non-Vie",
        sousComposantes: [
          {
            type: "extrait", rawKey: "Primes émises Vie par assurance",
            label: "Primes émises Vie",
            section: "annexe12",
            tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
            ligne: "Primes émises", colonne: "Total",
          },
          {
            type: "extrait", rawKey: "Primes émises Non-Vie par assurance",
            label: "Primes émises Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Primes émises", colonne: "Total",
          },
        ],
      },
      {
        type: "externe", denominator: true,
        label: "Total Primes marché (FTUSA)",
        source: "FTUSA — Rapport annuel",
        tableau: "Tableau récapitulatif des primes émises",
        ligne: "Total marché", colonne: "TOTAL (AFF. DIR + ACC)",
      },
    ],
  },

  /* ── ROE ───────────────────────────────────────────────────────────────── */
  "ROE (%)": {
    type: "calcule",
    formule: "Résultat net / Capitaux propres × 100",
    note: "Rentabilité des fonds propres en fin d'exercice.",
    composantes: [
      {
        type: "extrait", rawKey: "Résultat Net",
        label: "Résultat net",
        section: "etat_resultat",
        tableau: "État de résultat arrêté au 30/06",
        ligne: "Résultat net de l'exercice", colonne: "{annee}",
      },
      {
        type: "extrait", rawKey: "Capitaux propres",
        label: "Capitaux propres", denominator: true,
        section: "bilan_passif",
        tableau: "Bilan au 30/06",
        ligne: "Total capitaux propres avant résultat", colonne: "{annee}",
      },
    ],
  },

  /* ── ROA ───────────────────────────────────────────────────────────────── */
  "ROA (%)": {
    type: "calcule",
    formule: "Résultat net / Total actif × 100",
    note: "Rendement de l'ensemble des actifs déployés par la compagnie.",
    composantes: [
      {
        type: "extrait", rawKey: "Résultat Net",
        label: "Résultat net",
        section: "etat_resultat",
        tableau: "État de résultat arrêté au 30/06",
        ligne: "Résultat net de l'exercice", colonne: "{annee}",
      },
      {
        type: "extrait", rawKey: "Total actif",
        label: "Total actif", denominator: true,
        section: "bilan",
        tableau: "Bilan au 30/06",
        ligne: "Total de l'actif", colonne: "Net",
      },
    ],
  },

  /* ── KPIs extraits directement ─────────────────────────────────────────── */
  "Résultat Net": {
    type: "extrait",
    section: "etat_resultat",
    tableau: "État de résultat arrêté au 30/06",
    ligne: "Résultat net de l'exercice", colonne: "{annee}",
  },
  "Total actif": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Total de l'actif", colonne: "Net",
  },
  "Capitaux propres": {
    type: "extrait",
    section: "bilan_passif",
    tableau: "Bilan au 30/06",
    ligne: "Total capitaux propres avant résultat", colonne: "{annee}",
  },

  /* ── Résultat technique ────────────────────────────────────────────────── */
  "Résultat technique (TND)": {
    type: "calcule",
    formule: "Résultat technique Vie + Résultat technique Non-Vie",
    note: "Résultat propre à l'activité d'assurance, avant éléments financiers non techniques.",
    composantes: [
      {
        type: "extrait", rawKey: "Résultat technique Vie",
        label: "Résultat technique Vie",
        section: "annexe12",
        tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
        ligne: "Résultat technique", colonne: "Total",
      },
      {
        type: "extrait", rawKey: "Résultat technique Non-Vie",
        label: "Résultat technique Non-Vie",
        section: "annexe13",
        tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        ligne: "Résultat technique", colonne: "Total",
      },
    ],
  },

  /* ── Bilan — Actif (dashboard Performance financière) ─────────────────── */
  "Total Passif": {
    type: "extrait",
    section: "bilan_passif",
    tableau: "Bilan au 30/06",
    ligne: "Total du Passif", colonne: "{annee}",
  },
  "Actifs incorporels": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Actifs incorporels", colonne: "Net",
  },
  "Actifs corporels": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Actifs corporels d'exploitation", colonne: "Net",
  },
  "Placements": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Placements", colonne: "Net",
  },
  "Créances": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Créances", colonne: "Net",
  },
  "Autres éléments d'actifs": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Autres éléments d'actif", colonne: "Net",
  },
  "Autres passifs": {
    type: "extrait",
    section: "bilan_passif",
    tableau: "Bilan au 30/06",
    ligne: "Autres passifs", colonne: "{annee}",
  },
  "Part des réassureurs dans les provisions techniques": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Part des réassureurs dans les provisions techniques", colonne: "Net",
  },
  "Provisions techniques brutes": {
    type: "extrait",
    section: "bilan_passif",
    tableau: "Bilan au 30/06",
    ligne: "Provisions techniques brutes", colonne: "{annee}",
  },
  "Obligations": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Obligations et autres titres à revenu fixe", colonne: "Net",
  },
  "Actions et titres de participation": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Actions, autres titres à revenu variable", colonne: "Net",
  },
  "OPCVM": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Autres placements financiers", colonne: "Net",
  },
  "Dépôts et liquidité": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Avoirs en banque, CCP, chèques et caisse", colonne: "Net",
  },
  "Placements représentant des provisions techniques": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 30/06",
    ligne: "Placements représentant des provisions techniques", colonne: "Net",
    note: "Le DVRB référence par erreur la même ligne que « Part des réassureurs dans les provisions techniques » — corrigé ici pour pointer vers la vraie section AC4 du Bilan (voir bilan_kpi_extractor.py).",
  },

  /* ── Annexes 12/13 — Provisions techniques ─────────────────────────────── */
  "Provisions pour Primes non acquises": {
    type: "extrait",
    section: "annexe13",
    tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
    ligne: "Provisions pour Primes non Acquises clôture", colonne: "Total",
  },
  "Charges des provisions d'assurance vie et des autres provisions techniques": {
    type: "extrait",
    section: "annexe12",
    tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
    ligne: "Charges des provisions d'assurance vie et des autres provisions techniques", colonne: "Total",
  },
  "Charges des provisions pour prestations diverses": {
    type: "extrait",
    section: "annexe13",
    tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
    ligne: "Charges des provisions pour prestations diverses", colonne: "Total",
  },
  "Provisions d'assurance": {
    type: "calcule",
    formule: "Charges des provisions d'assurance vie et des autres provisions techniques + Charges des provisions pour prestations diverses",
    note: "Montant total mis en réserve pour couvrir les engagements futurs envers les assurés (Vie + Non-Vie).",
    composantes: [
      {
        type: "extrait", rawKey: "Charges des provisions d'assurance vie et des autres provisions techniques",
        label: "Provisions Vie",
        section: "annexe12",
        tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
        ligne: "Charges des provisions d'assurance vie et des autres provisions techniques", colonne: "Total",
      },
      {
        type: "extrait", rawKey: "Charges des provisions pour prestations diverses",
        label: "Provisions Non-Vie",
        section: "annexe13",
        tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        ligne: "Charges des provisions pour prestations diverses", colonne: "Total",
      },
    ],
  },
};
