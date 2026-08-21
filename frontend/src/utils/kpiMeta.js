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

// Portail de données INS (Population, PIB) — INS n'a pas de PDF (voir
// scraping/ins_scraper.py::PORTAL_PAGE_URL, même URL utilisée pour toutes
// les années scrapées). Utilisé comme lien "Ouvrir la source" pour les
// noeuds "externe" dont la source est INS, faute de document local à
// afficher/surligner comme pour FTUSA/CGA.
const INS_PORTAL_URL = "http://dataportal.ins.tn/fr/DataAnalysis?lWAcF5hGHkStY9XWRfYgzQ";

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
        ligne: "Primes émises", colonne: "Total || Opérations Nettes",
      },
      {
        type: "extrait", rawKey: "Primes émises Non-Vie par assurance",
        label: "Primes émises Non-Vie",
        section: "annexe13",
        tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        ligne: "Primes émises", colonne: "Total || Opérations Nettes",
      },
    ],
  },

  /* ── Primes émises — variante Arabe (AL_AMANAH_TAKAFUL uniquement) ───────
     Contrairement à AT_TAKAFULIA/ZITOUNA_TAKAFUL (français, vraie Annexe
     12/13 Vie/Non-Vie déjà localisable normalement, voir l'entrée
     conventionnelle ci-dessus qui leur reste applicable), AL_AMANAH_TAKAFUL
     n'a aucune segmentation Vie/Non-Vie : la valeur est déjà Familial+
     Général sommée à l'extraction (extract_al_amanah_takaful_kpis). Utiliser
     l'entrée conventionnelle pour cette société affichait donc 2
     sous-composantes ("Primes émises Vie/Non-Vie") en permanence "Non
     extrait" — signalé par l'utilisateur le 2026-08-19. */
  "Primes émises par assurance Arabe": {
    type: "extrait",
    rawKey: "Primes émises par assurance",
    tableau: "Annexes 3/4 — Primes émises et acceptées (Fonds Familial + Général)",
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
            ligne: "Charges de prestations || Charges de prestation", colonne: "Total || Opérations Nettes",
          },
          {
            type: "extrait", rawKey: "Charges de prestations Non-Vie",
            label: "Charges de prestations Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Charges de prestations || Charges de prestation", colonne: "Total || Opérations Nettes",
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
            ligne: "Charges d'acquisition et de gestion nettes || Charge d'acquisition et de gestion nettes", colonne: "Total || Opérations Nettes",
          },
          {
            type: "extrait", rawKey: "Charges d'acquisition et de gestion nettes Non-Vie",
            label: "Charges d'acq. nettes Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Charges d'acquisition et de gestion nettes || Charge d'acquisition et de gestion nettes", colonne: "Total || Opérations Nettes",
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
            ligne: "Primes émises", colonne: "Total || Opérations Nettes",
          },
          {
            type: "extrait", rawKey: "Primes émises Non-Vie par assurance",
            label: "Primes émises Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Primes émises", colonne: "Total || Opérations Nettes",
          },
        ],
      },
    ],
  },

  /* ── Ratios techniques — variantes Takaful ───────────────────────────────
     Les 3 sociétés Takaful (AT_TAKAFULIA, ZITOUNA_TAKAFUL, AL_AMANAH_TAKAFUL)
     n'ont PAS de segmentation Vie/Non-Vie (Annexe 12/13 — structure propre
     aux conventionnels) : le calcul réel de ces 3 ratios (voir
     extraction/calculated_kpi_extractor.py, commentaires "Repli Takaful")
     utilise directement les clés BRUTES "Charges de prestations"/"Charges
     d'acquisition et de gestion nettes"/"Primes émises par assurance" (déjà
     sommées Familial+Général à l'extraction, voir
     extraction/takaful_kpi_extractor.py::_extract_ventilation_charges_kpis),
     pas une décomposition Vie+Non-Vie. Utiliser les entrées CONVENTIONNELLES
     ci-dessous pour une société Takaful affichait donc un détail
     structurellement faux (Annexe 12/13, qui n'existe pas pour ces
     sociétés) et bloquait "Localiser dans le PDF" ("Localisation non prise
     en charge pour ce KPI" — signalé par l'utilisateur le 2026-08-19).
     Sélectionnées dynamiquement par KpiDetail.jsx selon la famille de la
     société (voir `isTakaful(code)`), suffixe " Takaful" sur le nom de clé. */
  "Ratio combiné (%) Takaful": {
    type: "calcule",
    formule: "(Charges de prestations + Charges d'acq. et gestion nettes) / Contribution × 100",
    note: "< 100 % = compagnie bénéficiaire sur le plan technique. Charges/contribution déjà sommées Fonds Familial + Fonds Général à l'extraction (pas de segmentation Vie/Non-Vie côté Takaful).",
    composantes: [
      {
        type: "extrait", rawKey: "Charges de prestations",
        label: "Charges de prestations",
        tableau: "Annexes 14/15 — Ventilation des charges (Fonds Familial + Général)",
      },
      {
        type: "extrait", rawKey: "Charges d'acquisition et de gestion nettes",
        label: "Charges d'acq. et gestion nettes",
        tableau: "Annexes 14/15 — Ventilation des charges (Fonds Familial + Général)",
      },
      {
        type: "extrait", rawKey: "Primes émises par assurance",
        label: "Contribution", denominator: true,
        tableau: "Annexes 3/4 — Primes émises et acceptées (Fonds Familial + Général)",
      },
    ],
  },
  "Ratio de sinistralité (%) Takaful": {
    type: "calcule",
    formule: "Charges de prestations / Contribution × 100",
    note: "Aussi appelé S/P. Pas de \"Primes acquises\" distinctes côté Takaful (structure Annexe 12/13 inexistante) : la Contribution sert de dénominateur, même repli que le calcul réel.",
    composantes: [
      {
        type: "extrait", rawKey: "Charges de prestations",
        label: "Charges de prestations",
        tableau: "Annexes 14/15 — Ventilation des charges (Fonds Familial + Général)",
      },
      {
        type: "extrait", rawKey: "Primes émises par assurance",
        label: "Contribution", denominator: true,
        tableau: "Annexes 3/4 — Primes émises et acceptées (Fonds Familial + Général)",
      },
    ],
  },
  "Ratio de frais de gestion (%) Takaful": {
    type: "calcule",
    formule: "Charges d'acq. et gestion nettes / Contribution × 100",
    note: "Part de la contribution absorbée par les frais commerciaux et administratifs.",
    composantes: [
      {
        type: "extrait", rawKey: "Charges d'acquisition et de gestion nettes",
        label: "Charges d'acq. et gestion nettes",
        tableau: "Annexes 14/15 — Ventilation des charges (Fonds Familial + Général)",
      },
      {
        type: "extrait", rawKey: "Primes émises par assurance",
        label: "Contribution", denominator: true,
        tableau: "Annexes 3/4 — Primes émises et acceptées (Fonds Familial + Général)",
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
            section: "resultat_sinistres_vie",
            tableau: "État de résultat technique de l'assurance Vie",
            ligne: "CHV1 Charg", colonne: "Opérations nettes",
          },
          {
            type: "extrait", rawKey: "Charge de sinistres Non-Vie",
            label: "Charges de sinistres Non-Vie",
            section: "resultat_sinistres_non_vie",
            tableau: "État de résultat technique de l'assurance Non-Vie",
            ligne: "CHNV1 Charg", colonne: "Opérations nettes",
          },
        ],
      },
      {
        type: "extrait", rawKey: "Primes acquises",
        label: "Primes acquises", denominator: true,
        section: "annexe13",
        tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        ligne: "PRIMES ACQUISES", colonne: "Total || Opérations Nettes",
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
            ligne: "Charges d'acquisition et de gestion nettes || Charge d'acquisition et de gestion nettes", colonne: "Total || Opérations Nettes",
          },
          {
            type: "extrait", rawKey: "Charges d'acquisition et de gestion nettes Non-Vie",
            label: "Charges d'acq. nettes Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Charges d'acquisition et de gestion nettes || Charge d'acquisition et de gestion nettes", colonne: "Total || Opérations Nettes",
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
            ligne: "Primes émises", colonne: "Total || Opérations Nettes",
          },
          {
            type: "extrait", rawKey: "Primes émises Non-Vie par assurance",
            label: "Primes émises Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Primes émises", colonne: "Total || Opérations Nettes",
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
            ligne: "Primes émises", colonne: "Total || Opérations Nettes",
          },
          {
            type: "extrait", rawKey: "Primes émises Non-Vie par assurance",
            label: "Primes émises Non-Vie",
            section: "annexe13",
            tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
            ligne: "Primes émises", colonne: "Total || Opérations Nettes",
          },
        ],
      },
      {
        type: "externe", denominator: true, rawKey: "Total Primes émises",
        label: "Total Primes marché (FTUSA)",
        source: "FTUSA — Rapport annuel",
        tableau: "Compte d'exploitation par branche, affaires directes",
        ligne: "Primes émises", colonne: "TOTAL (AFF. DIR + ACC)",
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
        tableau: "État de résultat arrêté au 31/12",
        ligne: "Résultat net de l'exercice", colonne: "{annee}",
      },
      {
        type: "extrait", rawKey: "Capitaux propres",
        label: "Capitaux propres", denominator: true,
        section: "bilan_passif",
        tableau: "Bilan au 31/12",
        ligne: "Total capitaux propres avant affectation || Total capitaux propres avant résultat || Total capitaux propres", colonne: "{annee}",
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
        tableau: "État de résultat arrêté au 31/12",
        ligne: "Résultat net de l'exercice", colonne: "{annee}",
      },
      {
        type: "extrait", rawKey: "Total actif",
        label: "Total actif", denominator: true,
        section: "bilan",
        tableau: "Bilan au 31/12",
        ligne: "Total de l'actif || Total des actifs || Total actifs", colonne: "Net",
      },
    ],
  },

  /* ── KPIs extraits directement ─────────────────────────────────────────── */
  "Résultat Net": {
    type: "extrait",
    section: "etat_resultat",
    tableau: "État de résultat arrêté au 31/12",
    ligne: "Résultat net de l'exercice", colonne: "{annee}",
  },
  "Total actif": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Total de l'actif || Total des actifs || Total actifs", colonne: "Net",
  },
  "Capitaux propres": {
    type: "extrait",
    section: "bilan_passif",
    tableau: "Bilan au 31/12",
    ligne: "Total capitaux propres avant affectation || Total capitaux propres avant résultat || Total capitaux propres", colonne: "{annee}",
  },

  /* ── KPIs spécifiques Takaful (commissions de gestion des fonds) ────────
     Sur l'État de résultat des sociétés Takaful (PR1/PR2), format simple
     2 colonnes (année en cours / précédente) — pas le Bilan "Combiné" des
     3 sociétés Takaful (voir _find_combine_col_x côté pdf_cell_coords.py). */
  "Commission Wakala (TND)": {
    type: "extrait",
    section: "etat_resultat",
    tableau: "État de résultat arrêté au 31/12",
    ligne: "Commission Wakala", colonne: "{annee}",
  },
  "Commission Moudharaba (TND)": {
    type: "extrait",
    section: "etat_resultat",
    tableau: "État de résultat arrêté au 31/12",
    ligne: "Commission Moudharaba", colonne: "{annee}",
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
        ligne: "Résultat technique", colonne: "Total || Opérations Nettes",
      },
      {
        type: "extrait", rawKey: "Résultat technique Non-Vie",
        label: "Résultat technique Non-Vie",
        section: "annexe13",
        tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        ligne: "Résultat technique", colonne: "Total || Opérations Nettes",
      },
    ],
  },

  /* ── Bilan — Actif (dashboard Performance financière) ─────────────────── */
  "Total Passif": {
    type: "extrait",
    section: "bilan_passif",
    tableau: "Bilan au 31/12",
    ligne: "Total du Passif", colonne: "{annee}",
  },
  "Actifs incorporels": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Actifs incorporels", colonne: "Net",
  },
  "Actifs corporels": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Actifs corporels d'exploitation", colonne: "Net",
  },
  "Placements": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Placements", colonne: "Net",
  },
  "Créances": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Créances", colonne: "Net",
  },
  "Autres éléments d'actifs": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Autres éléments d'actif", colonne: "Net",
  },
  "Autres passifs": {
    type: "extrait",
    section: "bilan_passif",
    tableau: "Bilan au 31/12",
    ligne: "Autres passifs", colonne: "{annee}",
  },
  "Part des réassureurs dans les provisions techniques": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Part des réassureurs dans les provisions techniques", colonne: "Net",
  },
  "Provisions techniques brutes": {
    type: "extrait",
    section: "bilan_passif",
    tableau: "Bilan au 31/12",
    ligne: "Provisions techniques brutes", colonne: "{annee}",
  },
  "Obligations": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Obligations et autres titres à revenu fixe", colonne: "Net",
  },
  "Actions et titres de participation": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Actions, autres titres à revenu variable", colonne: "Net",
  },
  "OPCVM": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Autres placements financiers", colonne: "Net",
  },
  "Dépôts et liquidité": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Avoirs en banque, CCP, chèques et caisse", colonne: "Net",
  },
  "Placements représentant des provisions techniques": {
    type: "extrait",
    section: "bilan",
    tableau: "Bilan au 31/12",
    ligne: "Placements représentant des provisions techniques", colonne: "Net",
    note: "Le DVRB référence par erreur la même ligne que « Part des réassureurs dans les provisions techniques » — corrigé ici pour pointer vers la vraie section AC4 du Bilan (voir bilan_kpi_extractor.py).",
  },

  /* ── Annexes 12/13 — Provisions techniques ─────────────────────────────── */
  "Provisions pour Primes non acquises": {
    type: "extrait",
    section: "annexe13",
    tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
    ligne: "Provisions pour Primes non Acquises clôture", colonne: "Total || Opérations Nettes",
  },
  "Charges des provisions d'assurance vie et des autres provisions techniques": {
    type: "extrait",
    section: "annexe12",
    tableau: "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
    ligne: "Charges des provisions d'assurance vie et des autres provisions techniques", colonne: "Total || Opérations Nettes",
  },
  "Charges des provisions pour prestations diverses": {
    type: "extrait",
    section: "annexe13",
    tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
    ligne: "Charges des provisions pour prestations diverses", colonne: "Total || Opérations Nettes",
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
        ligne: "Charges des provisions d'assurance vie et des autres provisions techniques", colonne: "Total || Opérations Nettes",
      },
      {
        type: "extrait", rawKey: "Charges des provisions pour prestations diverses",
        label: "Provisions Non-Vie",
        section: "annexe13",
        tableau: "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        ligne: "Charges des provisions pour prestations diverses", colonne: "Total || Opérations Nettes",
      },
    ],
  },

  /* ── KPI sectoriels (Aperçu marché) ──────────────────────────────────────
     Contrairement aux KPI ci-dessus, pas de `code` société : la source est
     FTUSA (rapport annuel, PDF), CGA (rapport annuel, PDF) ou INS (portail
     de données en ligne, pas de PDF — voir ExterneDetail côté KpiDetail.jsx,
     qui affiche alors "pas de PDF disponible" plutôt qu'un lien mort).
     Ajouté le 2026-08-19 : ces KPI étaient affichés sur Aperçu Marché sans
     aucun accès à leur source (retour utilisateur explicite — "on doit
     pouvoir accéder à la source des KPI sectoriels aussi"). Consommé avec
     `code: "MARCHE"` (pseudo-code, pas une société réelle) dans
     KpiOptionsMenu/KpiDetail. */
  "Population": {
    type: "externe", rawKey: "Population Totale",
    label: "Population",
    source: "INS — Institut National de la Statistique",
    tableau: "Population totale (portail de données INS)",
    ligne: "Population Totale", colonne: "{annee}",
    lien: INS_PORTAL_URL,
  },
  "PIB": {
    type: "externe", rawKey: "Produit Interieur Brut (PIB)",
    label: "Produit Intérieur Brut",
    source: "INS — Institut National de la Statistique",
    tableau: "Comptes nationaux (portail de données INS)",
    ligne: "Produit Intérieur Brut (PIB)", colonne: "{annee}",
    lien: INS_PORTAL_URL,
  },
  "Taux de pénétration (marché)": {
    type: "calcule", rawKey: "Taux de pénétration",
    label: "Taux de pénétration",
    formule: "Total Primes émises (FTUSA) / PIB (INS) × 100",
    note: "Poids du secteur assurance dans l'économie nationale.",
    composantes: [
      {
        type: "externe", rawKey: "Total Primes émises",
        label: "Total Primes marché",
        source: "FTUSA — Rapport annuel",
        tableau: "Compte d'exploitation par branche, affaires directes",
        ligne: "Primes émises", colonne: "TOTAL (AFF. DIR + ACC)",
      },
      {
        type: "externe", denominator: true, rawKey: "Produit Interieur Brut (PIB)",
        label: "PIB",
        source: "INS — Institut National de la Statistique",
        tableau: "Comptes nationaux (portail de données INS)",
        ligne: "Produit Intérieur Brut (PIB)", colonne: "{annee}",
        lien: INS_PORTAL_URL,
      },
    ],
  },
  "Densité d'assurance (marché)": {
    type: "calcule", rawKey: "Densité de l'assurance",
    label: "Densité d'assurance",
    formule: "Total Primes émises (FTUSA) / Population (INS)",
    note: "Prime moyenne payée par habitant.",
    composantes: [
      {
        type: "externe", rawKey: "Total Primes émises",
        label: "Total Primes marché",
        source: "FTUSA — Rapport annuel",
        tableau: "Compte d'exploitation par branche, affaires directes",
        ligne: "Primes émises", colonne: "TOTAL (AFF. DIR + ACC)",
      },
      {
        type: "externe", denominator: true, rawKey: "Population Totale",
        label: "Population",
        source: "INS — Institut National de la Statistique",
        tableau: "Population totale (portail de données INS)",
        ligne: "Population Totale", colonne: "{annee}",
        lien: INS_PORTAL_URL,
      },
    ],
  },

  /* ── Taux de pénétration / Densité — vue Takaful ─────────────────────────
     DVRB (DASH-FS-INS-03-C) demande "Total des contributions Takaful" issu
     du rapport FTUSA — mais la FTUSA ne publie aucune ventilation Takaful
     séparée (vérifié sur data/ftusa/FTUSA_*.pdf, voir commentaire en tête de
     api/routes/apercu_marche.py) : repli documenté sur l'agrégation des
     contributions déjà extraites par société (Annexe 3/4 de chaque
     opérateur Takaful), PIB/Population INS inchangés (même source que la
     vue conventionnelle, comme le spécifie le DVRB). Ajoutées le
     2026-08-19 : auparavant la bannière Takaful pointait ces 2 cartes vers
     "Taux de pénétration (marché)"/"Densité d'assurance (marché)"
     (FTUSA/conventionnel) alors que le chiffre affiché venait de cet
     agrégat Takaful — source affichée ne correspondant pas au calcul réel. */
  "Taux de pénétration (marché Takaful)": {
    type: "calcule", rawKey: "Taux de pénétration Takaful",
    label: "Taux de pénétration Takaful",
    formule: "Total des contributions Takaful / PIB (INS) × 100",
    note: "Poids du marché Takaful dans l'économie nationale.",
    composantes: [
      {
        type: "externe", rawKey: "Total des contributions Takaful",
        label: "Total contributions Takaful",
        source: "Agrégation CMF (3 opérateurs Takaful agréés)",
        tableau: "Annexe 3/4 — Primes émises et acceptées, par opérateur",
        ligne: "Primes émises et acceptées", colonne: "Opérations Brutes",
      },
      {
        type: "externe", denominator: true, rawKey: "Produit Interieur Brut (PIB)",
        label: "PIB",
        source: "INS — Institut National de la Statistique",
        tableau: "Comptes nationaux (portail de données INS)",
        ligne: "Produit Intérieur Brut (PIB)", colonne: "{annee}",
        lien: INS_PORTAL_URL,
      },
    ],
  },
  "Densité d'assurance (marché Takaful)": {
    type: "calcule", rawKey: "Densité de l'assurance Takaful",
    label: "Densité d'assurance Takaful",
    formule: "Total des contributions Takaful / Population (INS)",
    note: "Contribution Takaful moyenne payée par habitant.",
    composantes: [
      {
        type: "externe", rawKey: "Total des contributions Takaful",
        label: "Total contributions Takaful",
        source: "Agrégation CMF (3 opérateurs Takaful agréés)",
        tableau: "Annexe 3/4 — Primes émises et acceptées, par opérateur",
        ligne: "Primes émises et acceptées", colonne: "Opérations Brutes",
      },
      {
        type: "externe", denominator: true, rawKey: "Population Totale",
        label: "Population",
        source: "INS — Institut National de la Statistique",
        tableau: "Population totale (portail de données INS)",
        ligne: "Population Totale", colonne: "{annee}",
        lien: INS_PORTAL_URL,
      },
    ],
  },

  "Total primes marché": {
    type: "externe", rawKey: "Total Primes émises",
    label: "Total Primes marché",
    source: "FTUSA — Rapport annuel",
    tableau: "Compte d'exploitation par branche, affaires directes",
    ligne: "Primes émises", colonne: "TOTAL (AFF. DIR + ACC)",
  },
  "Primes marché Vie": {
    type: "externe", rawKey: "Primes émises Vie",
    label: "Primes marché Vie",
    source: "FTUSA — Rapport annuel",
    tableau: "Compte d'exploitation par branche, affaires directes",
    ligne: "Primes émises Vie", colonne: "TOTAL (AFF. DIR + ACC)",
  },
  "Primes marché Non-Vie": {
    type: "externe", rawKey: "Primes émises Non-Vie",
    label: "Primes marché Non-Vie",
    source: "FTUSA — Rapport annuel",
    tableau: "Compte d'exploitation par branche, affaires directes",
    ligne: "Primes émises Non-Vie", colonne: "TOTAL (AFF. DIR + ACC)",
  },
  "Total agences (marché)": {
    type: "externe", rawKey: "Total agences",
    label: "Total agences",
    source: "CGA — Rapport annuel",
    tableau: "Distribution géographique des agents d'assurance",
    ligne: "Total", colonne: "{annee}",
  },
};

// Génère les 3 ratios techniques marché (S/P, Frais, Combiné) pour un
// segment donné — même construction que
// extraction/calculated_kpi_extractor.py::_compute_sector_kpis, pour rester
// l'exact reflet de ce qui est réellement calculé côté backend plutôt que
// répéter 9 fois un bloc quasi identique à la main. Clés de `rawKey`
// vérifiées le 2026-08-19 directement sur la réponse de
// /api/sector-kpi-value (pas de suffixe implicite déduit par concaténation
// de chaîne — un piège sur le segment "total", qui n'a PAS le même préfixe
// "Total " que les KPI Vie/Non-Vie).
const _MARCHE_SEGMENTS = [
  { suffix: "",         label: "totales", primesLigne: "Primes émises",         primesRawKey: "Total Primes émises",         prestationsRawKey: "Total Charges de prestations",         acquisitionRawKey: "Total Charges d'acquisition et de gestion nettes",        ratioSuffix: "" },
  { suffix: " Vie",     label: "Vie",     primesLigne: "Primes émises Vie",     primesRawKey: "Primes émises Vie",           prestationsRawKey: "Charges de prestations Vie",           acquisitionRawKey: "Charges d'acquisition et de gestion nettes Vie",           ratioSuffix: " Vie" },
  { suffix: " Non-Vie", label: "Non-Vie", primesLigne: "Primes émises Non-Vie", primesRawKey: "Primes émises Non-Vie",       prestationsRawKey: "Charges de prestations Non-Vie",       acquisitionRawKey: "Charges d'acquisition et de gestion nettes Non-Vie",       ratioSuffix: " Non-Vie" },
];

for (const seg of _MARCHE_SEGMENTS) {
  const primesNode = {
    type: "externe", denominator: true, rawKey: seg.primesRawKey,
    label: `Primes ${seg.label} marché`,
    source: "FTUSA — Rapport annuel",
    tableau: "Compte d'exploitation par branche, affaires directes",
    ligne: seg.primesLigne, colonne: "TOTAL (AFF. DIR + ACC)",
  };
  const prestationsNode = {
    type: "externe", rawKey: seg.prestationsRawKey,
    label: `Charges de prestations${seg.suffix}`,
    source: "FTUSA — Rapport annuel",
    tableau: "Compte d'exploitation par branche, affaires directes",
    ligne: "Charges de prestations", colonne: "TOTAL (AFF. DIR + ACC)",
  };
  const acquisitionNode = {
    type: "externe", rawKey: seg.acquisitionRawKey,
    label: `Charges d'acquisition${seg.suffix}`,
    source: "FTUSA — Rapport annuel",
    tableau: "Compte d'exploitation par branche, affaires directes",
    ligne: "Charges d'acquisition et de gestion nettes", colonne: "TOTAL (AFF. DIR + ACC)",
  };
  KPI_META[`Ratio S/P marché${seg.suffix}`] = {
    type: "calcule", rawKey: `Ratio S/P${seg.ratioSuffix}`,
    label: `Ratio S/P marché${seg.suffix}`,
    formule: `Charges de prestations${seg.suffix} / Primes ${seg.label} marché × 100`,
    note: "Sinistres/primes au niveau du marché entier (FTUSA).",
    composantes: [prestationsNode, primesNode],
  };
  KPI_META[`Ratio de frais marché${seg.suffix}`] = {
    type: "calcule", rawKey: `Ratio de frais${seg.ratioSuffix}`,
    label: `Ratio de frais marché${seg.suffix}`,
    formule: `Charges d'acquisition${seg.suffix} / Primes ${seg.label} marché × 100`,
    note: "Frais de gestion/primes au niveau du marché entier (FTUSA).",
    composantes: [acquisitionNode, primesNode],
  };
  KPI_META[`Ratio combiné marché${seg.suffix}`] = {
    type: "calcule", rawKey: `Ratio combiné${seg.ratioSuffix}`,
    label: `Ratio combiné marché${seg.suffix}`,
    formule: `(Charges de prestations${seg.suffix} + Charges d'acquisition${seg.suffix}) / Primes ${seg.label} marché × 100`,
    note: "< 100 % = secteur bénéficiaire sur le plan technique.",
    composantes: [prestationsNode, acquisitionNode, primesNode],
  };
}
