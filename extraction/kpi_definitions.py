"""
Source de vérité pour les formules KPI du marché assurance tunisien CMF —
mais uniquement à des fins d'AFFICHAGE (utilisé par api/services/quality.py,
api/routes/qualite.py, api/services/pipeline_audit.py pour expliquer un KPI
côté frontend). Ce module n'est importé par AUCUN extracteur : les champs
"chercher" ci-dessous sont une description en texte libre de ce que
l'extraction est censée chercher, écrite indépendamment des vraies regex
d'extraction (voir bilan_kpi_extractor.py, annexe12/13_kpi_extractor.py...).
Rien ne garantit leur synchronisation — si une regex d'extraction change de
libellé cible, ce fichier peut dériver silencieusement sans que ça casse
quoi que ce soit (juste un texte d'aide légèrement faux affiché à l'utilisateur).

La même dénomination KPI peut correspondre à des formules différentes selon
le type de compagnie (Vie, Non-Vie, Mixte, Réassurance, Takaful) — mais
"différentes" au sens du LIBELLÉ MÉTIER affiché, pas du calcul réellement
exécuté. Vérifié empiriquement (juillet 2026, PDF réels COTUNACE/TUNIS_RE/
AT_TAKAFULIA) : extraction/calculated_kpi_extractor.py applique UNE seule
formule ("mixte" : somme des composantes Vie + Non-Vie quand elles existent,
via _safe_sum) pour toutes les sociétés, sans branchement par contexte. Pour
une compagnie de réassurance ou Takaful, les composantes "Vie" sont
simplement absentes des KPI extraits (nos extracteurs ne trouvent pas
d'Annexe 12 pour ces sociétés) : la somme se réduit alors naturellement au
bon segment, sans code dédié. Les variantes "reassurance"/"takaful"
ci-dessous documentent donc l'INTERPRÉTATION MÉTIER de ce même calcul dans
ces contextes ("Primes émises" se lit "primes acceptées" pour un réassureur,
"Cotisations" pour une compagnie Takaful), pas une formule alternative à
implémenter séparément.

Structure FORMULES_PAR_CONTEXTE :
  {kpi_name: {contexte: {expr, note, chercher, composantes}}}
  "_all" = même formule quel que soit le contexte.
"""

# ── Contexte par compagnie ────────────────────────────────────────────────────
COMPANY_CONTEXT: dict[str, str] = {
    # Vie uniquement
    "CARTE_VIE":     "vie",
    "GAT_VIE":       "vie",
    "LLOYD_VIE":     "vie",
    "MAGHREBIA_VIE": "vie",
    "ATTIJARI":      "vie",
    "BIAT":          "vie",
    "BNA":           "vie",
    "UIB":           "vie",
    # Réassurance / caution
    "COTUNACE":  "reassurance",
    "TUNIS_RE":  "reassurance",
    # Takaful participatif
    "AL_AMANAH_TAKAFUL": "takaful",
    "AT_TAKAFULIA":      "takaful",
    "HAYETT":            "takaful",
    "ZITOUNA_TAKAFUL":   "takaful",
    # Mixte (défaut) : ASTREE, BH, CARTE, COMAR, GAT, LLOYD_TUNISIEN, MAGHREBIA, STAR
}

CONTEXT_LABELS = {
    "vie":          "Assurance Vie",
    "non-vie":      "Assurance Non-Vie",
    "mixte":        "Vie + Non-Vie",
    "reassurance":  "Réassurance",
    "takaful":      "Assurance participative (Takaful)",
}


def get_context(code: str) -> str:
    """Retourne le contexte métier d'une compagnie (défaut : 'mixte')."""
    return COMPANY_CONTEXT.get(code.upper(), "mixte")


# ── Traçabilité extraction : KPI brut → section PDF ──────────────────────────
# Sources exactes d'après le DVRB (Data Value Realisation Book - FS Market Intel)
SOURCE_PAR_KPI: dict[str, dict] = {
    # ── Charges de prestations ──────────────────────────────────────────────
    "Charges de prestations": {
        "doc": "Annexe 12 + 13",
        "section": "annexe12",
        "tableau": "Résultat technique (Vie + Non-Vie)",
        "reference": "Ligne « Charges de prestations » / Colonne « Total »",
    },
    "Charges de prestations Vie": {
        "doc": "Annexe 12",
        "section": "annexe12",
        "tableau": "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
        "reference": "Ligne « Charges de prestations » / Colonne « Total »",
    },
    "Charges de prestations Non-Vie": {
        "doc": "Annexe 13",
        "section": "annexe13",
        "tableau": "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        "reference": "Ligne « Charges de prestations » / Colonne « Total »",
    },
    # ── Charges d'acquisition et de gestion nettes ──────────────────────────
    "Charges d'acquisition et de gestion nettes": {
        "doc": "Annexe 12 + 13",
        "section": "annexe12",
        "tableau": "Résultat technique (Vie + Non-Vie)",
        "reference": "Ligne « Charges d'acquisition et de gestion nettes » / Colonne « Total »",
    },
    "Charges d'acquisition et de gestion nettes Vie": {
        "doc": "Annexe 12",
        "section": "annexe12",
        "tableau": "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
        "reference": "Ligne « Charges d'acquisition et de gestion nettes » / Colonne « Total »",
    },
    "Charges d'acquisition et de gestion nettes Non-Vie": {
        "doc": "Annexe 13",
        "section": "annexe13",
        "tableau": "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        "reference": "Ligne « Charges d'acquisition et de gestion nettes » / Colonne « Total »",
    },
    # ── Primes émises ────────────────────────────────────────────────────────
    "Primes émises par assurance": {
        "doc": "Annexe 12 + 13",
        "section": "annexe12",
        "tableau": "Calcul interne",
        "reference": "Primes émises Vie + Primes émises Non-Vie",
    },
    "Primes émises Vie par assurance": {
        "doc": "Annexe 12",
        "section": "annexe12",
        "tableau": "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
        "reference": "Ligne « Primes émises » / Colonne « Total »",
    },
    "Primes émises Non-Vie par assurance": {
        "doc": "Annexe 13",
        "section": "annexe13",
        "tableau": "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        "reference": "Ligne « Primes émises » / Colonne « Total »",
    },
    # ── Charges de sinistres ─────────────────────────────────────────────────
    "Charge de sinistres": {
        "doc": "Annexe 12 + 13",
        "section": "annexe12",
        "tableau": "Résultat technique (Vie + Non-Vie)",
        "reference": "Ligne « CHV1 – Charges de sinistres » / Colonne « Opérations nettes »",
    },
    "Charge de sinistres Vie": {
        "doc": "Annexe 12",
        "section": "annexe12",
        "tableau": "État de résultat technique de l'assurance Vie",
        "reference": "Ligne « CHV1 – Charges de sinistres » / Colonne « Opérations nettes »",
    },
    "Charge de sinistres Non-Vie": {
        "doc": "Annexe 13",
        "section": "annexe13",
        "tableau": "État de résultat technique de l'assurance Non-Vie",
        "reference": "Ligne « CHV1 – Charges de sinistres » / Colonne « Opérations nettes »",
    },
    # ── Primes acquises ──────────────────────────────────────────────────────
    "Primes acquises": {
        "doc": "Annexe 13",
        "section": "annexe13",
        "tableau": "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        "reference": "Ligne « PRIMES ACQUISES » / Colonne « Total »",
    },
    # ── Résultat technique ───────────────────────────────────────────────────
    "Résultat technique Vie": {
        "doc": "Annexe 12",
        "section": "annexe12",
        "tableau": "Annexe N°12 : Résultat technique de la catégorie d'Assurance Vie",
        "reference": "Ligne « Résultat technique » / Colonne « Total »",
    },
    "Résultat technique Non-Vie": {
        "doc": "Annexe 13",
        "section": "annexe13",
        "tableau": "Annexe N°13 : Résultat technique de la catégorie d'Assurance Non-Vie",
        "reference": "Ligne « Résultat technique » / Colonne « Total »",
    },
    # ── Bilan ────────────────────────────────────────────────────────────────
    "Résultat Net": {
        "doc": "État de résultat",
        "section": "etat_resultat",
        "tableau": "État de résultat arrêté au 30/06",
        "reference": "Ligne « Résultat net de l'exercice » / Colonne « 30/06/{annee} »",
    },
    "Capitaux propres": {
        "doc": "Bilan",
        "section": "bilan",
        "tableau": "Bilan au 30/06",
        "reference": "Ligne « Total capitaux propres avant résultat de l'exercice » / Colonne « 30/06/{annee} »",
    },
    "Total actif": {
        "doc": "Bilan",
        "section": "bilan",
        "tableau": "Bilan au 30/06",
        "reference": "Ligne « Total de l'actif » / Colonne « 30/06/{annee} » / Sous-colonne « Net »",
    },
}

# ── Formules par KPI et par contexte ─────────────────────────────────────────
FORMULES_PAR_CONTEXTE: dict[str, dict] = {

    "Primes émises par assurance": {
        "mixte": {
            "expr": "Primes émises Vie (Annexe 12) + Primes émises Non-Vie (Annexe 13)",
            "note": "Montant brut avant cessions en réassurance, lu dans les tableaux CMF des Annexes 12 et 13. Somme des deux branches.",
            "chercher": "Primes émises",
            "composantes": [
                "Primes émises Vie par assurance",
                "Primes émises Non-Vie par assurance",
                "Primes émises par assurance",
            ],
        },
        "vie": {
            "expr": "Primes émises brutes Vie (Annexe 12)",
            "note": "Montant brut avant cessions, colonne totale de l'Annexe 12 — compagnie Vie uniquement.",
            "chercher": "Primes émises",
            "composantes": [
                "Primes émises Vie par assurance",
                "Primes émises par assurance",
            ],
        },
        "non-vie": {
            "expr": "Primes émises brutes Non-Vie (Annexe 13)",
            "note": "Montant brut avant cessions, colonne totale de l'Annexe 13 — compagnie Non-Vie uniquement.",
            "chercher": "Primes émises",
            "composantes": [
                "Primes émises Non-Vie par assurance",
                "Primes émises par assurance",
            ],
        },
        "reassurance": {
            "expr": "Primes acceptées en réassurance (traités + facultatif)",
            "note": "Pour les réassureurs (COTUNACE, TUNIS_RE) : primes des traités de réassurance acceptés, non des primes directes.",
            "chercher": "Primes émises",
            "composantes": ["Primes émises par assurance"],
        },
        "takaful": {
            "expr": "Cotisations Takaful brutes émises (Annexe 12 et/ou 13)",
            "note": "Pour les compagnies Takaful : les cotisations jouent le rôle des primes dans l'assurance conventionnelle.",
            "chercher": "Primes émises",
            "composantes": ["Primes émises par assurance"],
        },
    },

    "Ratio combiné (%)": {
        "mixte": {
            "expr": "(Charges de prestations Vie + Non-Vie + Charges d'acq. et gestion nettes) / Primes émises × 100",
            "note": "Vie + Non-Vie agrégés. Si les charges Vie et Non-Vie sont disponibles séparément, elles sont additionnées. < 100 % = compagnie bénéficiaire.",
            "chercher": "Charges de prestations",
            "composantes": [
                "Charges de prestations Vie",
                "Charges de prestations Non-Vie",
                "Charges de prestations",
                "Charges d'acquisition et de gestion nettes",
                "Primes émises Vie par assurance",
                "Primes émises Non-Vie par assurance",
                "Primes émises par assurance",
            ],
        },
        "vie": {
            "expr": "(Charges de prestations Vie + Charges d'acq. et gestion Vie) / Primes émises Vie × 100",
            "note": "Vie uniquement — Annexe 12. < 100 % = compagnie bénéficiaire.",
            "chercher": "Charges de prestations",
            "composantes": [
                "Charges de prestations Vie",
                "Charges d'acquisition et de gestion nettes Vie",
                "Charges d'acquisition et de gestion nettes",
                "Primes émises Vie par assurance",
                "Primes émises par assurance",
            ],
        },
        "non-vie": {
            "expr": "(Charges de prestations Non-Vie + Charges d'acq. et gestion Non-Vie) / Primes émises Non-Vie × 100",
            "note": "Non-Vie uniquement — Annexe 13.",
            "chercher": "Charges de prestations",
            "composantes": [
                "Charges de prestations Non-Vie",
                "Charges d'acquisition et de gestion nettes",
                "Primes émises Non-Vie par assurance",
                "Primes émises par assurance",
            ],
        },
        "reassurance": {
            "expr": "(Sinistres à la charge + Commissions cédées + Frais de gestion) / Primes acceptées × 100",
            "note": "Pour les réassureurs : le ratio combiné utilise les primes des traités acceptés comme dénominateur.",
            "chercher": "Sinistres",
            "composantes": [
                "Charges de prestations",
                "Charges d'acquisition et de gestion nettes",
                "Primes émises par assurance",
            ],
        },
        "takaful": {
            "expr": "(Charges de prestations + Charges d'acq. et gestion nettes) / Cotisations émises × 100",
            "note": "Structure similaire au ratio combiné conventionnel, appliqué aux cotisations Takaful.",
            "chercher": "Charges de prestations",
            "composantes": [
                "Charges de prestations",
                "Charges d'acquisition et de gestion nettes",
                "Primes émises par assurance",
            ],
        },
    },

    "Ratio de sinistralité (%)": {
        "mixte": {
            "expr": "Charge de sinistres (Vie + Non-Vie) / Primes acquises × 100",
            "note": "Aussi appelé S/P. Primes acquises = Primes émises ± variation PSAP. Si indisponibles, Primes émises est utilisé comme approximation.",
            "chercher": "Charge de sinistres",
            "composantes": [
                "Charge de sinistres Vie",
                "Charge de sinistres Non-Vie",
                "Charge de sinistres",
                "Primes acquises",
                "Primes émises par assurance",
            ],
        },
        "vie": {
            "expr": "Charge de sinistres Vie / Primes acquises Vie × 100",
            "note": "S/P Vie — Annexe 12.",
            "chercher": "Charge de sinistres",
            "composantes": [
                "Charge de sinistres Vie",
                "Charge de sinistres",
                "Primes acquises",
                "Primes émises Vie par assurance",
                "Primes émises par assurance",
            ],
        },
        "non-vie": {
            "expr": "Charge de sinistres Non-Vie / Primes acquises Non-Vie × 100",
            "note": "S/P Non-Vie — Annexe 13.",
            "chercher": "Charge de sinistres",
            "composantes": [
                "Charge de sinistres Non-Vie",
                "Charge de sinistres",
                "Primes acquises",
                "Primes émises Non-Vie par assurance",
                "Primes émises par assurance",
            ],
        },
        "reassurance": {
            "expr": "Sinistres à la charge des acceptations / Primes acceptées × 100",
            "note": "Pour les réassureurs : sinistres des traités de réassurance acceptés.",
            "chercher": "Charge de sinistres",
            "composantes": [
                "Charge de sinistres",
                "Primes acquises",
                "Primes émises par assurance",
            ],
        },
        "takaful": {
            "expr": "Charge de sinistres (prestations Takaful) / Cotisations acquises × 100",
            "note": "Appliqué aux cotisations et prestations Takaful.",
            "chercher": "Charge de sinistres",
            "composantes": [
                "Charge de sinistres",
                "Primes acquises",
                "Primes émises par assurance",
            ],
        },
    },

    "Ratio de frais de gestion (%)": {
        "_all": {
            "expr": "Charges d'acq. et gestion nettes / Primes émises × 100",
            "note": "Charges d'acquisition nettes des commissions reçues en réassurance. Mesure la part des primes absorbée par les frais commerciaux et administratifs.",
            "chercher": "Charges d'acquisition",
            "composantes": [
                "Charges d'acquisition et de gestion nettes",
                "Primes émises par assurance",
            ],
        },
    },

    "ROE (%)": {
        "_all": {
            "expr": "Résultat net / Capitaux propres × 100",
            "note": "Rentabilité des fonds propres. Capitaux propres en fin d'exercice. Comparaison avec le coût du capital de la compagnie.",
            "chercher": "Résultat net de l'exercice",
            "composantes": ["Résultat Net", "Capitaux propres"],
        },
    },

    "ROA (%)": {
        "_all": {
            "expr": "Résultat net / Total actif × 100",
            "note": "Rendement de l'ensemble des actifs déployés par la compagnie en fin d'exercice.",
            "chercher": "Total de l'actif",
            "composantes": ["Résultat Net", "Total actif"],
        },
    },

    "Résultat Net": {
        "_all": {
            "expr": "Extrait directement de l'État de résultat (aucun recalcul)",
            "note": "Dernière ligne du compte de résultat, après tous les produits et charges — valeur telle que publiée par la compagnie.",
            "chercher": "Résultat net de l'exercice",
            "composantes": [],
        },
    },

    "Résultat technique (TND)": {
        "_all": {
            "expr": "Résultat technique Vie + Résultat technique Non-Vie",
            "note": "Résultat propre à l'activité d'assurance (Vie + Non-Vie), avant éléments financiers non techniques et exceptionnels.",
            "chercher": "Résultat technique",
            "composantes": ["Résultat technique Vie", "Résultat technique Non-Vie"],
        },
    },

    "Total actif": {
        "_all": {
            "expr": "Extrait directement du Bilan (aucun recalcul)",
            "note": "Total de l'actif à la clôture de l'exercice, colonne « Net » — valeur telle que publiée par la compagnie.",
            "chercher": "Total de l'actif",
            "composantes": [],
        },
    },

    "Capitaux propres": {
        "_all": {
            "expr": "Extrait directement du Bilan (aucun recalcul)",
            "note": "Total des capitaux propres avant résultat de l'exercice, tel que publié au passif du bilan.",
            "chercher": "Total capitaux propres",
            "composantes": [],
        },
    },

    "Part de marché (%)": {
        "_all": {
            "expr": "Primes compagnie / Total Primes marché (FTUSA) × 100",
            "note": "Calculée par rapport au total des primes émises déclarées à la FTUSA (Fédération Tunisienne des Sociétés d'Assurance).",
            "chercher": None,
            "composantes": [],
        },
    },
}


def get_formule(kpi: str, code: str | None = None) -> dict | None:
    """Retourne la définition de formule pour un KPI et un code compagnie.

    Résout automatiquement le contexte (vie/non-vie/mixte/…) si `code` est fourni.
    Retourne None si le KPI est inconnu.
    """
    ctx_defs = FORMULES_PAR_CONTEXTE.get(kpi)
    if ctx_defs is None:
        return None

    if "_all" in ctx_defs:
        return dict(ctx_defs["_all"])

    ctx = get_context(code) if code else "mixte"
    result = ctx_defs.get(ctx) or ctx_defs.get("mixte")
    return dict(result) if result else None


# Plages de plausibilité métier par KPI (détection de valeur aberrante) :
# source de vérité unique pour api/services/quality.py ET pipeline_audit.py.
# Avant juillet 2026, chacun définissait sa propre plage pour les mêmes KPI
# — quality.py : [2 %, 1 000 %] quasi permissif, appliqué à RC/RSP/RF
# seulement ; pipeline_audit.py : plages plus étroites et spécifiques par
# KPI (_PLAGES). Les deux fichiers pouvaient donc juger différemment
# "aberrant" pour la même valeur. Reprend les plages de pipeline_audit.py
# (plus discriminantes, bien que sans base empirique citée — contrairement
# au plancher/plafond de bilan_kpi_extractor.MIN/MAX_PLAUSIBLE_VALUE,
# validé sur 186 PDF réels).
KPI_PLAGES_PLAUSIBLES: dict[str, tuple[float, float]] = {
    "Ratio combiné (%)":             (30, 500),
    "Ratio de sinistralité (%)":     (10, 400),
    "Ratio de frais de gestion (%)": (2, 200),
    "Part de marché (%)":            (0.01, 50),
    "ROE (%)":                       (-200, 200),
    "ROA (%)":                       (-50, 50),
}

# KPI en valeur absolue qui ne peuvent structurellement jamais être 0 pour
# une compagnie en activité — pas de plage fixe possible pour un montant
# (l'échelle varie trop d'une société à l'autre), donc contrôlé séparément.
# Source unique : avant août 2026, api/services/quality.py et
# api/services/pipeline_audit.py avaient chacun leur propre copie de cette
# liste (à ce moment-là identiques, mais exposées au même risque de
# divergence silencieuse que KPI_PLAGES_PLAUSIBLES avant son unification).
ZERO_SUSPECT_KPIS = {
    "Total actif",
    "Capitaux propres",
    "Primes émises par assurance",
}


def filter_reliable(kpi_name: str, value):
    """Renvoie `value` si elle est jugée fiable pour affichage (mêmes règles
    que api/services/quality.py pour la page Qualité Data), sinon None.

    Sert à ce que toute page montrant un KPI par société (Analyse
    Comparative, Aperçu Marché, Vue par assurance...) reste cohérente avec
    Qualité Data au lieu de réafficher une valeur qu'elle a elle-même
    flaguée non fiable (hors plage métier, ou zéro structurellement
    impossible) — sans ce filtre partagé, chaque page pouvait décider
    indépendamment si une même valeur était affichable ou non."""
    if value is None:
        return None
    plage = KPI_PLAGES_PLAUSIBLES.get(kpi_name)
    if plage and not (plage[0] <= value <= plage[1]):
        return None
    if kpi_name in ZERO_SUSPECT_KPIS and value == 0:
        return None
    return value


# Backward-compat : alias pour quality.py
FORMULES = {
    kpi: (ctx_defs.get("_all") or ctx_defs.get("mixte") or next(iter(ctx_defs.values())))
    for kpi, ctx_defs in FORMULES_PAR_CONTEXTE.items()
    if kpi in (
        "Ratio combiné (%)", "Ratio de sinistralité (%)", "Ratio de frais de gestion (%)",
        "ROE (%)", "ROA (%)",
    )
}
