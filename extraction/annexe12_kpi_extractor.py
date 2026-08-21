"""
Extraction ciblée du tableau "Résultat technique par catégorie d'assurance
Vie" (Annexe N°12) : pendant "Vie" de l'Annexe N°13 (Non-Vie), même logique
d'extraction (voir annexe13_kpi_extractor et bilan_kpi_extractor pour les
briques bas-niveau réutilisées).

La colonne cible (dernière colonne de la ligne) n'est pas toujours nommée
"Total" littéralement (ex: "Montant" chez GAT) : on prend systématiquement
la dernière valeur numérique de la ligne, quel que soit l'intitulé exact de
l'en-tête de colonne.

Voir extraction/CAS_PARTICULIERS_ANNEXE12.md pour l'historique des cas
particuliers rencontrés (notamment : COMAR n'a pas d'activité Vie propre,
gérée par sa filiale HAYETT — plusieurs KPI y sont donc légitimement absents).
"""

import io
import re

import requests

from extraction.bilan_kpi_extractor import USER_AGENT
from extraction.annexe13_kpi_extractor import (
    _extract_numeric_clusters,
    _is_plausible,
    _label_text,
    _page_lines,
    _normalizer,
)

# Cette annexe peut se trouver très loin dans le document (voir Annexe 13).
MAX_PAGES_SCANNED = 120

# Titre de page : "Résultat technique par catégorie d'assurance Vie" ou
# "Tableau de raccordement du résultat technique par catégorie
# d'assurance..." — dans les deux cas, on exige la présence du mot "vie" et
# l'ABSENCE de "non vie"/"non-vie" pour ne pas confondre avec l'Annexe 13.
# "(?:non.?vie |vie )?" : chez BIAT (et probablement d'autres), l'ordre des
# mots est "RESULTAT TECHNIQUE VIE PAR CATEGORIE..." (le mot "Vie" intercalé
# entre "technique" et "par"), alors que le motif d'origine supposait l'ordre
# "...PAR CATEGORIE D'ASSURANCE VIE" (le mot "Vie" en fin de titre) — sans ce
# groupe optionnel, la page "par catégorie" de BIAT n'était jamais reconnue
# comme cible, seule la page "raccordement" (titre différent) l'était.
# GAT_VIE (et probablement d'autres) : titre "État de résultat technique Vie
# DE GAT VIE" (nom de la société, pas "par/de la catégorie") - variante de
# gabarit PDF découverte 2026-08-16 en auditant les trous "Primes émises"
# sur Vue par Assurance. Sans le 2e groupe alternatif, cette page n'était
# jamais reconnue comme cible malgré un contenu identique aux autres
# sociétés (mêmes lignes Primes/Charges), laissant tout Annexe 12 vide.
# CTAMA (et probablement d'autres) : titre "ETAT DE RESULTAT TECHNIQUE DE
# L'ASSURANCE ET/OU DE LA REASSURANCE VIE" — ni "catégorie" ni "raccordement"
# ni "vie" immédiatement après "technique" (structure "technique DE
# L'ASSURANCE ET/OU DE LA REASSURANCE vie", pas "technique vie DE..."),
# aucune des 3 alternatives existantes ne matchait alors que la table est la
# même (codes PRV1/CHV1 identiques). Découvert le 2026-08-17 en auditant les
# trous Primes émises/ratios sur Vue par Assurance pour CTAMA (0/2 années).
# Motif volontairement large ("de l'assurance", sans exiger "et/ou de la
# réassurance" qui ne s'applique qu'aux réassureurs) ; la désambiguïsation
# Vie/Non-Vie reste faite par VIE_RE/NON_VIE_RE dans _is_target_page, et
# NOTES_SECTION_RE continue d'exclure les pages de notes narratives (cas
# ATTIJARI déjà documenté).
PAGE_TITLE_RE = re.compile(
    r"resultat technique (?:non.?vie |vie )?(?:par|de la?) categorie"
    r"|resultat technique (?:non.?vie|vie) de\b"
    r"|raccordement du resultat technique"
    r"|etat de resultat technique de l.?assurance"
)
VIE_RE = re.compile(r"\bvie\b")
NON_VIE_RE = re.compile(r"non.?vie")

# ATTIJARI 2024 (et probablement d'autres années) : la seule page dont le
# TEXTE mentionne "un état de résultat technique par catégories de contrats a
# été établi..." est une page de "NOTES" narrative (glose en prose autour de
# mini-tableaux "Désignation / 2024 / 2023 / Variation %"), pas la table
# Annexe 12 elle-même — mais cette phrase descriptive suffit à faire matcher
# PAGE_TITLE_RE. Sur cette page, la colonne "Variation" du mini-tableau se
# fait alors passer pour la valeur "nette année en cours" (ex: "Primes
# émises" y ressort à 3 457 860, qui est en réalité l'écart 2024 vs 2023, pas
# une prime réelle — la vraie valeur, 141 663 231, n'apparaît que dans la
# phrase en prose juste au-dessus). Plutôt que d'apprendre à ce module la
# structure de ce tableau de note (rencontrée une seule fois à ce jour), on
# exclut ces pages : Primes émises Vie redevient alors None/anomalie détectée
# pour ATTIJARI plutôt qu'une valeur fausse — voir CAS_PARTICULIERS_ANNEXE12.md.
NOTES_SECTION_RE = re.compile(r"\bnotes sur\b")

PRIOR_YEAR_EXCLUSION_RE = re.compile(r"n-1|ouverture|precedent|anterieur")

KPI_PATTERNS = {
    "Charges des provisions d'assurance vie et des autres provisions techniques": re.compile(
        r"charges des provisions d assurance vie et des autres provisions"
    ),
    # BIAT : sur le tableau "par catégorie" ET sur la page "raccordement",
    # cette ligne est intitulée juste "Primes" (sans "émises"), parfois avec
    # une annotation de renvoi collée après ("primes prv1 1ère colonne" sur
    # la page raccordement) — d'où l'absence d'ancrage de fin ($) ; on exclut
    # explicitement "cédées"/"acquises" pour ne pas capturer "Primes cédées
    # et/ou rétrocédées" ou "Primes acquises" (lignes différentes, plus bas
    # sur les mêmes pages, qui commencent aussi par "primes").
    "Primes émises Vie par assurance": re.compile(r"^primes emises\b|^primes\b(?!.*(cedees|acquises))"),
    "Primes acquises Vie": re.compile(r"^primes acquises\b"),
    "Charges de prestations Vie": re.compile(r"^charges de prestations?\b"),
    # "s" optionnel sur "charge(s)" (BIAT : "Charge d'acquisition et de
    # gestion nettes", singulier, contrairement à la plupart des sociétés).
    "Charges d'acquisition et de gestion nettes Vie": re.compile(
        r"charges? d acquisition et de gestion"
    ),
    "Résultat technique Vie": re.compile(r"^resultat technique\b(?!.*(categorie|assurance))"),
}


def _is_target_page(page, lines_checked=4):
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    if NOTES_SECTION_RE.search(normalized):
        return False
    if not PAGE_TITLE_RE.search(normalized):
        return False
    if NON_VIE_RE.search(normalized):
        return False
    return bool(VIE_RE.search(normalized))


_RACCORDEMENT_RE = re.compile(r"raccordement")

# Sections qui marquent la FIN d'un groupe "Charges de prestations" dans le
# forward scan : dès qu'une sous-ligne commence par l'un de ces termes, on
# arrête l'accumulation (ces lignes n'appartiennent pas au groupe CP).
_SECTION_STOP_RE = re.compile(
    r"^(solde|frais d acquisition|charges d acquisition et de gestion|"
    r"produits|resultat technique|part des reassureurs|retrocessionn|"
    r"provisions pour primes non acquises|participations aux benefices|commissions)"
)
_FORWARD_SCAN_WINDOW = 6


def _find_total_value(pdf, pattern, max_pages=MAX_PAGES_SCANNED):
    """Cherche, sur les pages "Résultat technique par catégorie... Vie", la
    première ligne dont le libellé correspond à `pattern`, et renvoie la
    DERNIÈRE valeur numérique de cette ligne.

    Les pages "raccordement" (colonne unique) sont scannées EN PREMIER pour
    éviter de lire une colonne de branche dans les tableaux multi-colonnes.

    Si la ligne correspondante n'a pas de valeur inline (en-tête de section
    sans total, ex: COMAR/CARTE où "Charges de prestations" est suivi de
    sous-lignes "Prestations et frais payés" + "Charges des provisions"),
    on accumule les valeurs des sous-lignes suivantes jusqu'au prochain
    marqueur de section."""
    target_pages = []
    for page in pdf.pages[:max_pages]:
        if not _is_target_page(page):
            continue
        norm = _normalizer.clean((page.extract_text() or "")[:300])
        target_pages.append((not _RACCORDEMENT_RE.search(norm), page))

    target_pages.sort(key=lambda x: x[0])

    for _, page in target_pages:
        lines = _page_lines(page)
        if not lines:
            continue
        for idx, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not pattern.search(label):
                continue
            if PRIOR_YEAR_EXCLUSION_RE.search(label):
                continue
            clusters = _extract_numeric_clusters(line)
            # Rejette un renvoi de note ou un numéro de page/ligne capturé par
            # erreur (voir bilan_kpi_extractor._is_plausible / CAS_PARTICULIERS) :
            # on retombe alors sur l'accumulation des sous-lignes.
            value = _pick_current_year_value(clusters)
            if value is not None and _is_plausible(value):
                return value
            # En-tête sans valeur (ou valeur inline implausible) : accumuler
            # les sous-lignes suivantes. `last_seen` évite un double-comptage
            # quand le PDF source affiche deux fois la même rangée de
            # chiffres sans libellé sur la 2e occurrence (constaté chez
            # CARTE_VIE et COMAR, ~10pt plus bas que la ligne labellée —
            # artefact de rendu du PDF source, pas un vrai second poste) :
            # découvert le 2026-08-17, ce doublon gonflait Primes émises
            # Vie/Non-Vie ×2 pour ces sociétés. Un vrai sous-total légitime
            # (ex: "Prestations et frais payés" + "Charges des provisions"
            # chez COMAR/CARTE) a toujours des valeurs DIFFÉRENTES d'une
            # sous-ligne à l'autre, donc n'est jamais filtré par cette garde.
            total = None
            last_seen = None
            for j in range(idx + 1, min(idx + 1 + _FORWARD_SCAN_WINDOW, len(lines))):
                nxt_label = _label_text(lines[j])
                if nxt_label and _SECTION_STOP_RE.search(nxt_label):
                    break
                nxt_clusters = _extract_numeric_clusters(lines[j])
                nxt_value = _pick_current_year_value(nxt_clusters)
                if nxt_value is not None and _is_plausible(nxt_value):
                    if last_seen is not None and abs(nxt_value - last_seen) < 0.01:
                        continue
                    total = (total or 0) + nxt_value
                    last_seen = nxt_value
            if total is not None:
                return total
    return None


def _pick_current_year_value(clusters):
    """4 colonnes = Brut(année N) / Cessions(année N) / Net(année N) /
    Net(année N-1, comparaison) — format standard des pages "par catégorie"
    (non-raccordement) de cette annexe, vérifié ligne par ligne (Primes,
    Charges, Revenus des placements...) sur STAR/CTAMA : `clusters[-1]`
    (dernière colonne) est alors l'année PRÉCÉDENTE, pas l'année en cours —
    Net(N) = clusters[-2], et vaut systématiquement Brut − Cessions.
    Découvert le 2026-08-17 : ce bug affectait potentiellement tous les
    documents utilisant ce format à 4 colonnes (jusqu'ici indétecté car la
    valeur retournée n'était jamais `None` — juste celle de la mauvaise
    année). Pour 1-3 ou ≥5 clusters (pages "raccordement" à colonne unique,
    ou toute autre disposition), on garde `clusters[-1]` (comportement
    historique, non concerné par cette ambiguïté)."""
    if not clusters:
        return None
    if len(clusters) == 4:
        return clusters[-2][0]
    return clusters[-1][0]


def _apply_primes_emises_fallback(kpis):
    """Repli GAT_VIE (probablement d'autres) : sur la page "raccordement",
    certaines sociétés étiquettent leur SEULE ligne de primes "Primes
    Acquises" au lieu de "Primes émises" - la ligne "Primes émises et
    acceptées" du tableau détaillé multi-colonnes existe bien mais n'a pas
    de colonne "Total" propre (Brut/Cessions/Net-courant/Net-antérieur),
    rendant `_find_total_value` ambigu sur CETTE page (elle attend UNE
    valeur par ligne). Vérifié 2026-08-16 sur GAT_VIE_2024.pdf : la page
    raccordement affiche "Primes Acquises PRV11 72 354 649", valeur
    identique à la colonne "Opérations Brutes" (courante) du tableau
    détaillé, et cohérente avec la note "Les primes émises nettes
    d'annulation de l'exercice 2024 s'élèvent à 72 354 649 dinars". Ne
    s'applique QUE si "Primes émises..." est absent - jamais en écrasement
    d'une valeur déjà trouvée."""
    if kpis.get("Primes émises Vie par assurance") is None and kpis.get("Primes acquises Vie") is not None:
        kpis["Primes émises Vie par assurance"] = kpis["Primes acquises Vie"]
    return kpis


def extract_annexe12_kpis(pdf):
    """Renvoie {nom_kpi: valeur|None} pour les 6 KPI de l'Annexe N°12."""
    kpis = {name: _find_total_value(pdf, pattern) for name, pattern in KPI_PATTERNS.items()}
    return _apply_primes_emises_fallback(kpis)


def extract_annexe12_kpis_from_url(pdf_url, timeout=30):
    """Télécharge le PDF en mémoire (aucune écriture sur disque) et en
    extrait les KPI de l'Annexe N°12."""
    import pdfplumber  # import local pour éviter la dépendance si non utilisé

    response = requests.get(pdf_url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        return extract_annexe12_kpis(pdf)
