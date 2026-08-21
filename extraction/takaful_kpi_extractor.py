"""Extraction des KPI pour les compagnies Takaful (assurance islamique) :
ZITOUNA_TAKAFUL et AT_TAKAFULIA (motifs français ci-dessous), et
AL_AMANAH_TAKAFUL (états financiers en arabe — voir
extract_al_amanah_takaful_kpis plus bas et extraction/arabic_ocr_extractor.py
pour la technique : lecture RTL + NFKC, repli OCR bilingue arabe/anglais).

Deux formats réglementaires coexistent sur l'historique CMF de ces deux
compagnies (voir investigation documentée dans le commit associé) :

  - Format ANCIEN (jusqu'à l'exercice 2019 environ) : structure très proche
    d'un assureur conventionnel — un seul jeu de comptes par exercice
    (colonnes Brut/Amortissement/Net/Net Retraité côté Actif, une seule
    colonne côté Capitaux propres/Passif), sans distinction Fonds des
    Adhérents / Entreprise. On n'utilise PAS bilan_kpi_extractor.py
    directement : ses filtres de page (_is_actif_page notamment) rejettent
    certains documents Takaful (page non reconnue comme "page Actif" alors
    que la donnée y est bien présente) — on réutilise seulement ses
    utilitaires bas niveau (parsing de nombres, regroupement de lignes) et on
    scanne toutes les pages sans filtre.

  - Format NOUVEAU (à partir de l'exercice ~2020, suite à une réforme
    réglementaire) : le Bilan devient un "Bilan Combiné" à 3 colonnes par
    exercice — Fonds des Adhérents (capitaux des assurés, mutualisés) /
    Entreprise Takaful et/ou Rétakaful (bilan propre de la compagnie,
    actionnaires) / Entreprise ... combiné (somme des deux). Pour rester
    comparable aux assureurs conventionnels (dont le bilan n'inclut PAS de
    fonds mutualisé séparé), on retient la colonne "Entreprise" seule — ni
    le Fonds des Adhérents (qui appartient aux assurés, pas à la compagnie),
    ni le total combiné (qui mélangerait les deux). C'est toujours la 2e
    colonne du groupe de 3 (index 1) formant l'exercice en cours.

Dans les deux formats, l'État de Résultat de l'entreprise reste à colonne
unique par exercice (le compte de résultat de la compagnie elle-même n'est
jamais scindé Fonds/Entreprise) : "Résultat net de l'exercice" s'extrait
avec la même logique quel que soit le format.

Capitaux propres : certains documents affichent une ligne intermédiaire
"Total capitaux propres avant résultat de l'exercice" AVANT la ligne finale
"Total capitaux propres avant affectation" (ex: AT_TAKAFULIA 2018) — on
recherche en priorité la ligne "avant affectation" (le vrai total final) sur
tout le document avant de se rabattre sur un "Total capitaux propres" plus
générique (ex: AT_TAKAFULIA 2024, qui n'a pas de ligne intermédiaire)."""

import re
import unicodedata

from rapidfuzz import fuzz

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters, _label_text, _is_plausible,
)
from utils.text_normalizer import TextNormalizer

_normalizer = TextNormalizer()

MAX_PAGES_SCANNED = 20

TOTAL_ACTIF_RE = re.compile(r"^total (de l.?|des )?actifs?\b")
CAPITAUX_PROPRES_AFFECTATION_RE = re.compile(r"^total capitaux propres avant affectation\b")
CAPITAUX_PROPRES_RE = re.compile(r"^total capitaux propres\b")
# "r\s?esultat" tolère un artefact de rendu PDF où le "R" (accentué en
# amont) se retrouve séparé du reste du mot par un espace parasite (ex:
# "r esultat net de l exercice" chez ZITOUNA_TAKAFUL 2025, ligne 5) — sans
# ce tolérance, la regex stricte ne matchait JAMAIS la vraie ligne de l'État
# de résultat, ce qui faisait retomber l'extraction sur RESULTAT_EXERCICE_FALLBACK_RE
# plus bas, qui matche AUSSI (même libellé) une ligne d'un tableau différent
# (variation des capitaux propres) dont la 1ère colonne n'est pas le bon
# résultat -> "Résultat Net" à tort extrait à 0.
RESULTAT_NET_RE = re.compile(r"r\s?esultat net de l.?exercice\b")
# Repli : certains documents (ex: ZITOUNA_TAKAFUL 2025) omettent le mot "net"
# sur la ligne CP6 du Bilan ("Résultat de l'exercice" au lieu de "Résultat
# net de l'exercice"). Ancré en tête pour ne PAS matcher "...avant résultat
# de l'exercice" (total intermédiaire, valeur différente — voir AT_TAKAFULIA
# 2018) : cette ligne-là est toujours précédée d'un mot ("avant"), jamais en
# début de libellé une fois le préfixe de code retiré par _label_text.
RESULTAT_EXERCICE_FALLBACK_RE = re.compile(r"^r\s?esultat de l.?exercice\b")
PRIMES_EMISES_RE = re.compile(r"primes emises et acceptees\b")
BILAN_COMBINE_MARKER_RE = re.compile(r"bilan combine")

# Annexes 14/15 "Ventilation du Surplus ou déficit par catégorie
# d'assurance" (Familial/Général) : ces tableaux ventilent CE QUI, dans les
# Annexes 3/4 (extract_fonds_participants_kpis), n'apparaît qu'en un seul
# total par fonds — Charges de prestations et Charges d'acquisition et de
# gestion nettes, déjà PRÉ-SOMMÉES par catégorie sur la colonne "Total"
# (dernière colonne, quel que soit le nombre de branches). Titre variable
# selon la société ("Modèle de Ventilation..." chez AT_TAKAFULIA, sans
# "Modèle" chez ZITOUNA_TAKAFUL, espacement autour des parenthèses
# différent) - motif large sur les mots-clés communs uniquement.
ANNEXE_VENTILATION_FAMILIAL_TITLE_RE = re.compile(
    r"ventilation.*surplus.*deficit.*categorie.*assurance.*familial"
)
ANNEXE_VENTILATION_GENERAL_TITLE_RE = re.compile(
    r"ventilation.*surplus.*deficit.*categorie.*assurance.*general"
)
# Ancré en tête (^) pour ne pas matcher les lignes homonymes plus bas dans
# le même tableau : "Charges des provisions pour prestations..." (sous-poste
# différent) et "Part des réassureurs...dans les charges de prestations"
# (portion cédée, valeur différente). "prestations?" : ZITOUNA_TAKAFUL
# orthographie cette ligne au singulier ("Charges de prestation") côté
# Annexe 15 (Général) mais au pluriel côté Annexe 14 (Familial) - typo de la
# source elle-même, vérifié sur le PDF.
CHARGES_PRESTATIONS_RE = re.compile(r"^charges de prestations?\b")
CHARGES_ACQUISITION_GESTION_RE = re.compile(r"^charges d.?acquisition et de gestion nettes")

# ── Fonds des Participants (NCT 43, format "nouveau" uniquement — voir
# extract_fonds_participants_kpis) : ces lignes/tableaux n'existent PAS avant
# la réforme réglementaire (~2020), vérifié sur AT_TAKAFULIA_2018.pdf où le
# Bilan et l'État de Résultat sont structurellement identiques à un assureur
# conventionnel, sans Fonds des Adhérents ni états de surplus séparés.
#
# Le libellé de la ligne de résultat ("Surplus ou déficit de l'assurance
# Takaful et/ou Rétakaful Familial/Général") s'étale sur 3 lignes physiques
# reconstruites par _cluster_lines, avec les VALEURS au milieu et le mot
# distinctif ("Familial"/"Général") sur la ligne de fin, APRÈS les valeurs —
# donc invisible à une recherche par label sur une seule ligne. On distingue
# donc Familial/Général par la PAGE (titre "Etat de Surplus ou Déficit du
# fonds Takaful Familial/Général", ANNEXE N°3/4) plutôt que par le libellé de
# la ligne elle-même, qui est identique dans les deux tableaux — même
# stratégie de page ciblée que annexe13_kpi_extractor._is_target_page.
ANNEXE_FAMILIAL_TITLE_RE = re.compile(r"surplus ou deficit du fonds takaful familial")
ANNEXE_GENERAL_TITLE_RE  = re.compile(r"surplus ou deficit du fonds takaful general")
# Volontairement SANS "takaful" : le point de césure entre "de l'assurance"
# et "Takaful Familial/Général" varie d'un exercice à l'autre pour la même
# société (ex: ZITOUNA_TAKAFUL 2022, où "Takaful Familial" atterrit sur la
# 3e ligne physique, après les valeurs, contrairement aux autres exercices où
# "Takaful" reste accroché à "de l'assurance" sur la 1ère ligne). Le mot
# "Takaful" n'est de toute façon pas nécessaire pour désambiguïser puisque
# _find_row_on_page restreint déjà la recherche à la bonne page (titre
# Familial/Général) — l'ajouter ici ne fait que fragiliser le motif.
SURPLUS_LIGNE_RE = re.compile(r"surplus ou deficit de l.?assurance")
TOTAL_ACTIFS_NETS_ADHERENTS_RE = re.compile(r"total des actifs nets des adherents")
# Pas d'ancrage ^ : certains exercices (ex: ZITOUNA_TAKAFUL 2019/2025)
# collent le code de ligne au libellé sans espace ("PA3Provisions techniques
# brutes"), un cas déjà documenté pour d'autres sociétés côté Bilan
# conventionnel (bilan_kpi_extractor.py, ASTREE/BH) où ROW_CODE_PREFIX_RE
# (qui exige un espace après le code) ne le détecte pas. "provisions
# techniques brutes" reste une expression assez spécifique pour ne pas
# matcher par erreur "provision pour primes non acquises" ou "part des
# réassureurs dans les provisions techniques" (aucune ne contient "brutes").
PROVISIONS_TECHNIQUES_BRUTES_RE = re.compile(r"provisions techniques brutes\b")
# Titre de l'État de résultat de l'Opérateur (Annexe 5.1) — formulation
# variable selon la société ("Etat de résultat de l'entreprise d'assurance
# Takaful..." chez AT_TAKAFULIA, "L'état de Résultat de l'entreprise
# Takaful..." chez ZITOUNA_TAKAFUL), d'où un motif large. Nécessaire pour
# restreindre la recherche des commissions Wakala/Moudharaba à CETTE page :
# "Commission(s) Moudharaba" apparaît AUSSI (singulier chez ZITOUNA en plus,
# pas seulement pluriel chez AT_TAKAFULIA) comme poste de charge du fonds des
# participants dans les Annexes 3/4, sous un code de ligne différent
# (CHF411/CHG411) mais une valeur bien distincte de PR2 côté Opérateur — une
# recherche non bornée à la page renverrait la mauvaise des deux.
ENTREPRISE_RESULTAT_TITLE_RE = re.compile(r"etat de resultat de l.?entreprise")
# Pas d'ancrage ^ : le préfixe de code de ligne "PR1"/"PR2" n'est pas retiré
# par _label_text, qui ne connaît que les préfixes ac/pa/cp du Bilan (voir
# bilan_kpi_extractor.ROW_CODE_PREFIX_RE).
COMMISSION_WAKALA_RE    = re.compile(r"commission wakala\b")
COMMISSION_MOUDHARABA_RE = re.compile(r"commission moudharaba\b")

# Bilan Combiné (format nouveau) : Fonds des Adhérents / Entreprise Takaful
# et/ou Rétakaful / Entreprise ... combiné, par exercice. La colonne
# "Entreprise" (celle qu'on retient) est toujours la 2e (index 1) du groupe
# de 3 le plus à gauche (exercice en cours) sur une ligne de total.
NOUVEAU_COLS_PER_EXERCICE = 3
NOUVEAU_ENTREPRISE_COL_INDEX = 1


def _page_lines(page):
    words = page.extract_words()
    if not words:
        return []
    return _cluster_lines(words)


def detect_format(pdf):
    """Renvoie "nouveau" si le Bilan Combiné (3 colonnes/exercice) est
    détecté sur les premières pages, "ancien" sinon."""
    for page in pdf.pages[:MAX_PAGES_SCANNED]:
        text = page.extract_text() or ""
        if BILAN_COMBINE_MARKER_RE.search(_normalizer.clean(text)):
            return "nouveau"
    return "ancien"


def _find_row_value(pdf, pattern_re, column_selector, max_pages=MAX_PAGES_SCANNED, forward_scan=2):
    """Cherche la première ligne (dans l'ordre du document) dont le libellé
    normalisé correspond à `pattern_re`, et renvoie `column_selector(clusters)`
    pour la première ligne (elle-même ou l'une des `forward_scan` suivantes)
    portant des valeurs numériques."""
    for page in pdf.pages[:max_pages]:
        lines = _page_lines(page)
        if not lines:
            continue
        for i, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not pattern_re.search(label):
                continue
            for j in range(i, min(i + 1 + forward_scan, len(lines))):
                clusters = _extract_numeric_clusters(lines[j])
                if not clusters:
                    continue
                value = column_selector(clusters)
                if value is not None:
                    return value
    return None


def _col_nouveau_entreprise(clusters):
    if len(clusters) < NOUVEAU_COLS_PER_EXERCICE:
        return None
    value = clusters[NOUVEAU_ENTREPRISE_COL_INDEX][0]
    return value if _is_plausible(value) else None


def _col_ancien_actif(clusters):
    """Côté Actif (Brut/Amortissement/Net/Net Retraité) : avant-dernière
    colonne = Net de l'exercice en cours — même convention que
    bilan_kpi_extractor.py pour un bilan conventionnel."""
    value = clusters[-2][0] if len(clusters) >= 2 else clusters[0][0]
    return value if _is_plausible(value) else None


def _col_nettes_courantes(clusters):
    """États de Surplus/Déficit des fonds Takaful (Annexes 3/4, format
    nouveau) : jusqu'à 4 sous-colonnes par ligne — Opérations brutes /
    Cessions et rétrocessions / Opérations nettes exercice courant /
    Opérations nettes exercice précédent. Certaines colonnes sont vides
    (aucun token numérique, ex: cessions=0 non affiché) et disparaissent du
    cluster plutôt que d'apparaître comme 0 — l'exercice précédent reste
    toujours la DERNIÈRE valeur et l'exercice courant l'AVANT-DERNIÈRE, quel
    que soit le nombre de colonnes effectivement présentes avant elles (même
    convention que _col_ancien_actif pour le Bilan)."""
    value = clusters[-2][0] if len(clusters) >= 2 else clusters[0][0]
    return value if _is_plausible(value) else None


def _col_first(clusters):
    """Côté Capitaux propres/Passif (une seule sous-colonne par exercice) et
    État de Résultat : première colonne = exercice en cours."""
    value = clusters[0][0]
    return value if _is_plausible(value) else None


def _col_first_plausible(clusters):
    """Comme _col_first, mais ignore un éventuel numéro de renvoi de note
    glissé SANS séparateur entre le libellé et la valeur (donc capturé comme
    1er token numérique de la ligne) — ex: ZITOUNA_TAKAFUL 2019/2025,
    "PA3Provisions techniques brutes 10 102 283 503..." où "10" est le
    numéro de note, pas une valeur. _col_first renverrait None sur cette
    ligne (10 < MIN_PLAUSIBLE_VALUE), ce qui faisait retomber le
    forward-scan de _find_row_value sur la ligne de détail SUIVANTE (une
    sous-ligne différente, valeur incorrecte) plutôt que de simplement
    ignorer ce token et lire la vraie valeur sur la même ligne."""
    for value, _x in clusters:
        if _is_plausible(value):
            return value
    return None


def _col_last_plausible(clusters):
    """Annexes 14/15 (Ventilation par branche/catégorie) : la colonne
    "Total" est toujours la DERNIÈRE de la ligne, quel que soit le nombre de
    branches présentes avant elle (4 chez ZITOUNA_TAKAFUL, 10 chez
    AT_TAKAFULIA) - même logique que _col_first_plausible mais depuis la
    fin, puisque ces tableaux placent leur colonne de synthèse à droite
    plutôt qu'à gauche (contrairement au Bilan/État de Résultat)."""
    for value, _x in reversed(clusters):
        if _is_plausible(value):
            return value
    return None


def _find_row_on_page(pdf, title_re, row_re, col_selector, max_pages=MAX_PAGES_SCANNED, strict_page=False):
    """Comme _find_row_value, mais restreint la recherche de `row_re` aux
    pages associées au titre `title_re` — nécessaire quand le même libellé de
    ligne existe dans plusieurs tableaux du document avec des valeurs
    différentes (Familial vs Général, ou Commission côté Opérateur vs charge
    homonyme côté fonds des participants).

    Une page est retenue si `title_re` apparaît n'importe où dans SON PROPRE
    texte OU dans celui de la page précédente : le titre de l'Annexe 5.1
    ("Etat de résultat de l'entreprise...") est parfois imprimé en bas de la
    page précédente (ex: AT_TAKAFULIA, à la suite de l'Annexe 4) plutôt qu'en
    tête de la page où commence réellement le tableau (ex: ZITOUNA_TAKAFUL,
    où titre et tableau sont sur la même page) — un test restreint aux
    premières lignes de CHAQUE page (comme annexe13_kpi_extractor) rate donc
    la moitié des cas selon la société.

    `strict_page=True` désactive ce repli "page précédente" : nécessaire
    quand la page N+1 porte un titre DIFFÉRENT mais CONCURRENT (ex: Annexe 3
    "...Familial" suivie immédiatement de l'Annexe 4 "...Général") — la page
    Général se retrouve alors, à tort, également candidate pour une
    recherche "Familial" via ce repli, et si la ligne cherchée est absente de
    la page Familial (mais présente côté Général), la valeur du fonds
    General est renvoyée sous l'étiquette Familial. Confirmé 2026-08-11 sur
    ZITOUNA_TAKAFUL_2025 : "Primes émises et acceptées" absente de l'Annexe 3
    cette année-là, valeur de l'Annexe 4 (95 492 869) renvoyée à tort pour
    les deux fonds. Le Surplus/Déficit (usage existant, jamais strict) n'a
    jamais déclenché ce cas car la ligne cherchée existe systématiquement
    sur les DEUX pages, donc la page correcte répond toujours en premier."""
    pages = pdf.pages[:max_pages]
    page_texts = [_normalizer.clean(p.extract_text() or "") for p in pages]

    for idx, page in enumerate(pages):
        titled = title_re.search(page_texts[idx]) or (
            not strict_page and idx > 0 and title_re.search(page_texts[idx - 1])
        )
        if not titled:
            continue
        lines = _page_lines(page)
        if not lines:
            continue
        for i, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not row_re.search(label):
                continue
            for j in range(i, min(i + 3, len(lines))):
                clusters = _extract_numeric_clusters(lines[j])
                if not clusters:
                    continue
                value = col_selector(clusters)
                if value is not None:
                    return value
    return None


def _find_row_all_values_on_page(pdf, title_re, row_re, max_pages=MAX_PAGES_SCANNED, strict_page=False):
    """Comme _find_row_on_page, mais renvoie la liste ENTIÈRE des valeurs
    plausibles de la ligne (pas une seule colonne sélectionnée) - nécessaire
    pour la ventilation par branche (Annexe 15, colonne « Total » EXCLUE
    puisqu'elle n'est pas une branche) : chaque colonne y est une branche
    différente qu'il faut identifier par POSITION plutôt que par un
    sélecteur unique."""
    pages = pdf.pages[:max_pages]
    page_texts = [_normalizer.clean(p.extract_text() or "") for p in pages]

    for idx, page in enumerate(pages):
        titled = title_re.search(page_texts[idx]) or (
            not strict_page and idx > 0 and title_re.search(page_texts[idx - 1])
        )
        if not titled:
            continue
        lines = _page_lines(page)
        if not lines:
            continue
        for i, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not row_re.search(label):
                continue
            for j in range(i, min(i + 3, len(lines))):
                clusters = _extract_numeric_clusters(lines[j])
                values = [v for v, _x in clusters if _is_plausible(v)]
                if values:
                    return values
    return None


# Ligne "Primes émises" de l'Annexe 15 (Ventilation par branche, Fonds
# Général) : libellé DIFFÉRENT de PRIMES_EMISES_RE ("Primes émises et
# acceptées", Annexes 3/4) - vérifié sur AT_TAKAFULIA et ZITOUNA_TAKAFUL,
# cette ligne-ci ne porte jamais "et acceptées". Ancré en tête pour ne pas
# capturer une ligne de variation ("Variation des primes non acquises...").
PRIMES_EMISES_BRANCHE_RE = re.compile(r"^primes emises\b")


def _extract_branches_positional(values):
    """Automobile/Transport/Incendie = 3 premières colonnes (ordre constant
    chez AT_TAKAFULIA ET ZITOUNA_TAKAFUL, seule la suite diffère) ; Divers =
    somme de tout ce qui reste ENTRE Incendie et Total (la dernière colonne,
    exclue) - vaut la valeur "Divers" telle quelle chez ZITOUNA_TAKAFUL (déjà
    une colonne unique) et la somme des 6 branches restantes chez
    AT_TAKAFULIA (Santé, Ind/Groupe, RC I.A, Assistance, RDS, Acceptation).
    `values` exclut déjà les tokens implausibles (numéros de renvoi de note)
    via _find_row_all_values_on_page. Minimum 4 colonnes requises (3 branches
    nommées + Total) - sinon la ligne trouvée n'est probablement pas la bonne
    (ex: ligne de variation à 1 seule valeur passée le filtre par erreur)."""
    if len(values) < 4:
        return None
    automobile, transport, incendie = values[0], values[1], values[2]
    milieu = values[3:-1]
    divers = sum(milieu) if milieu else 0.0
    return automobile, transport, incendie, divers


def extract_branches_ventilation_kpis(pdf):
    """Contributions Takaful par branche (Fonds Général uniquement - voir
    DVRB, la ventilation par branche n'existe pas côté Fonds Familial,
    structure Prévoyance/Épargne). Pour AT_TAKAFULIA et ZITOUNA_TAKAFUL
    (français, texte réel) - AL_AMANAH_TAKAFUL (arabe) traité séparément,
    voir extract_al_amanah_branches_kpis."""
    values = _find_row_all_values_on_page(
        pdf, ANNEXE_VENTILATION_GENERAL_TITLE_RE, PRIMES_EMISES_BRANCHE_RE, max_pages=45, strict_page=True)
    branches = _extract_branches_positional(values) if values else None
    if branches is None:
        return {
            "Contributions Automobile (TND)": None,
            "Contributions Transport (TND)": None,
            "Contributions Incendie (TND)": None,
            "Contributions Divers (TND)": None,
        }
    automobile, transport, incendie, divers = branches
    return {
        "Contributions Automobile (TND)": automobile,
        "Contributions Transport (TND)": transport,
        "Contributions Incendie (TND)": incendie,
        "Contributions Divers (TND)": divers,
    }


def extract_fonds_participants_kpis(pdf):
    """Renvoie les indicateurs propres au Fonds des Participants (PRF) —
    sans équivalent conventionnel, donc jamais calculés/affichés pour les
    compagnies conventionnelles : Surplus/déficit des fonds Takaful Familial
    et Général (Annexes 3/4), Total des actifs nets des adhérents et
    Provisions techniques brutes côté Fonds des Adhérents (Annexe 1, colonne
    Fonds des Adhérents = 1ère sous-colonne du groupe de 3), Commission
    Wakala et Commission Moudharaba de l'Opérateur (Annexe 5.1).

    N'appeler que si detect_format(pdf) == "nouveau" (NCT 43) : ces tableaux
    n'existent pas en format ancien, vérifié sur AT_TAKAFULIA_2018.pdf."""
    return {
        "Surplus du Fonds Takaful Familial (TND)":
            _find_row_on_page(pdf, ANNEXE_FAMILIAL_TITLE_RE, SURPLUS_LIGNE_RE, _col_nettes_courantes),
        "Surplus du Fonds Takaful Général (TND)":
            _find_row_on_page(pdf, ANNEXE_GENERAL_TITLE_RE, SURPLUS_LIGNE_RE, _col_nettes_courantes),
        "Total actifs nets des adhérents (TND)":
            _find_row_value(pdf, TOTAL_ACTIFS_NETS_ADHERENTS_RE, _col_first_plausible),
        "Provisions techniques du Fonds des Adhérents (TND)":
            _find_row_value(pdf, PROVISIONS_TECHNIQUES_BRUTES_RE, _col_first_plausible),
        "Commission Wakala (TND)":
            _find_row_on_page(pdf, ENTREPRISE_RESULTAT_TITLE_RE, COMMISSION_WAKALA_RE, _col_nettes_courantes),
        "Commission Moudharaba (TND)":
            _find_row_on_page(pdf, ENTREPRISE_RESULTAT_TITLE_RE, COMMISSION_MOUDHARABA_RE, _col_nettes_courantes),
        # "Primes émises et acceptées" (PRF11/PRG11) est sur la MÊME page que
        # le Surplus/Déficit ci-dessus (Annexes 3/4) - même désambiguïsation
        # Familial/Général par titre de page, réutilisée ici. Colonne
        # "Opérations brutes" (1ère) : même convention que extract_all_takaful_kpis
        # (le total Familial+Général est déjà calculé ailleurs, ceci n'ajoute
        # que la répartition, jamais utilisée sans le total existant).
        "Primes émises Familial (TND)":
            _find_row_on_page(pdf, ANNEXE_FAMILIAL_TITLE_RE, PRIMES_EMISES_RE, _col_first_plausible, strict_page=True),
        "Primes émises Général (TND)":
            _find_row_on_page(pdf, ANNEXE_GENERAL_TITLE_RE, PRIMES_EMISES_RE, _col_first_plausible, strict_page=True),
        **_extract_ventilation_charges_kpis(pdf),
        **extract_branches_ventilation_kpis(pdf),
    }


def _extract_ventilation_charges_kpis(pdf):
    """Charges de prestations et Charges d'acquisition et de gestion nettes
    (Annexes 14/15, colonne "Total") : mêmes NOMS canoniques que les
    assureurs conventionnels (voir calculated_kpi_extractor._CMF_COMPUTED_KPI_NAMES)
    pour que kpi_builder/quality/DVRB fonctionnent sans modification -
    mais ici extraites DIRECTEMENT (déjà sommées Familial+Général par la
    société elle-même sur la colonne Total) plutôt que recalculées comme
    somme Vie+Non-Vie (structure inexistante côté Takaful). "strict_page"
    évite la contamination Familial<->Général déjà documentée pour Primes
    émises (voir _find_row_on_page).

    Somme Familial+Général exigée en ENTIER (aucune valeur partielle) :
    une seule branche disponible sous-estimerait silencieusement le total
    plutôt que de signaler clairement une extraction incomplète - cohérent
    avec le principe du projet de préférer None à une valeur inventée/erronée.
    Valeurs prises en valeur absolue : les Annexes 14/15 notent ces charges
    en négatif (déductions), même convention que calculated_kpi_extractor
    pour les assureurs conventionnels."""
    # Contrairement aux Annexes 3/4/5.1 (page ~3-4, couvertes par
    # MAX_PAGES_SCANNED=20), les Annexes 14/15 apparaissent bien plus loin
    # dans le document - vérifié entre la page 26 (AT_TAKAFULIA 2022) et la
    # page 37 (ZITOUNA_TAKAFUL 2024) selon la société et l'exercice. Plafond
    # choisi avec marge au-delà du maximum observé.
    max_pages = 45
    charges_prest_familial = _find_row_on_page(
        pdf, ANNEXE_VENTILATION_FAMILIAL_TITLE_RE, CHARGES_PRESTATIONS_RE, _col_last_plausible,
        max_pages=max_pages, strict_page=True)
    charges_prest_general = _find_row_on_page(
        pdf, ANNEXE_VENTILATION_GENERAL_TITLE_RE, CHARGES_PRESTATIONS_RE, _col_last_plausible,
        max_pages=max_pages, strict_page=True)
    charges_acq_familial = _find_row_on_page(
        pdf, ANNEXE_VENTILATION_FAMILIAL_TITLE_RE, CHARGES_ACQUISITION_GESTION_RE, _col_last_plausible,
        max_pages=max_pages, strict_page=True)
    charges_acq_general = _find_row_on_page(
        pdf, ANNEXE_VENTILATION_GENERAL_TITLE_RE, CHARGES_ACQUISITION_GESTION_RE, _col_last_plausible,
        max_pages=max_pages, strict_page=True)

    charges_prestations = None
    if charges_prest_familial is not None and charges_prest_general is not None:
        charges_prestations = abs(charges_prest_familial) + abs(charges_prest_general)

    charges_acquisition = None
    if charges_acq_familial is not None and charges_acq_general is not None:
        charges_acquisition = abs(charges_acq_familial) + abs(charges_acq_general)

    return {
        "Charges de prestations": charges_prestations,
        "Charges d'acquisition et de gestion nettes": charges_acquisition,
    }


def extract_all_takaful_kpis(pdf):
    """Renvoie {nom_kpi: valeur|None}, avec les mêmes noms canoniques que les
    assureurs conventionnels (Total actif, Capitaux propres, Résultat Net,
    Primes émises par assurance) — pour que le reste de l'application
    (kpi_builder.py, quality.py, comparative.py, vue_assurance.py...)
    fonctionne sans aucune modification sur les compagnies Takaful."""
    fmt = detect_format(pdf)

    if fmt == "nouveau":
        total_actif = _find_row_value(pdf, TOTAL_ACTIF_RE, _col_nouveau_entreprise)
        capitaux = _find_row_value(pdf, CAPITAUX_PROPRES_AFFECTATION_RE, _col_nouveau_entreprise)
        if capitaux is None:
            capitaux = _find_row_value(pdf, CAPITAUX_PROPRES_RE, _col_nouveau_entreprise)
    else:
        total_actif = _find_row_value(pdf, TOTAL_ACTIF_RE, _col_ancien_actif)
        capitaux = _find_row_value(pdf, CAPITAUX_PROPRES_AFFECTATION_RE, _col_first)
        if capitaux is None:
            capitaux = _find_row_value(pdf, CAPITAUX_PROPRES_RE, _col_first)

    resultat_net = _find_row_value(pdf, RESULTAT_NET_RE, _col_first)
    if resultat_net is None:
        resultat_net = _find_row_value(pdf, RESULTAT_EXERCICE_FALLBACK_RE, _col_first)

    primes_total = None
    for page in pdf.pages[:MAX_PAGES_SCANNED]:
        lines = _page_lines(page)
        for i, line in enumerate(lines):
            label = _label_text(line)
            if label is None or not PRIMES_EMISES_RE.search(label):
                continue
            for j in range(i, min(i + 3, len(lines))):
                clusters = _extract_numeric_clusters(lines[j])
                if not clusters:
                    continue
                value = clusters[0][0]  # 1ère colonne = Opérations brutes
                if _is_plausible(value) and value:
                    primes_total = (primes_total or 0) + value
                break

    result = {
        "Total actif": total_actif,
        "Capitaux propres": capitaux,
        "Résultat Net": resultat_net,
        "Primes émises par assurance": primes_total,
        "_takaful_format": fmt,
    }
    if fmt == "nouveau":
        result.update(extract_fonds_participants_kpis(pdf))
    return result


# ─────────────────────────────────────────────────────────────────────────
# AL_AMANAH_TAKAFUL : états financiers en arabe, texte réel disponible
# certaines années (2019-2022 vérifié) mais RTL + parfois police mal
# encodée, ou pages scannées en image d'autres années (2018, 2023-2025
# vérifié) - voir extraction/arabic_ocr_extractor.py pour le détail des
# techniques (correction RTL/tatweel, NFKC pour les formes de présentation,
# repli OCR bilingue arabe/anglais) et extraction/CAS_PARTICULIERS_TAKAFUL.md
# pour le suivi par exercice. Fonctionne sur les DEUX formats de Bilan
# (ancien/nouveau, voir _select_actif_like/_select_equity_like) - format
# détecté implicitement par le nombre de valeurs trouvées sur la ligne, pas
# par une détection préalable comme detect_format() (inutile ici : cette
# société n'a pas de tableau "Bilan Combiné" nommé comme tel dans le texte
# à chercher, le format se déduit seulement des données de la ligne
# elle-même).
_AR_TOTAL_ACTIF = ["مجموع الأصول"]
_AR_CAPITAUX_AFFECTATION = ["مجموع الأموال الذاتية قبل التوزيع"]
_AR_CAPITAUX = ["مجموع الأموال الذاتية"]
_AR_RESULTAT_NET = ["مال ذاتي نتيجة السنة المحاسبية"]
_AR_PRIMES = ["أر ع أقساط تأمين صادرة و مقبولة", "أقساط تأمين صادرة و مقبولة"]
# Annexes 14/15 (Ventilation du Surplus ou déficit par catégorie
# d'assurance) - mêmes libellés vérifiés indépendamment sur l'Annexe 14
# (Fonds Familial, exercice 2020, page 38) ET l'Annexe 15 (Fonds Général,
# même exercice, page 39) par reconstruction RTL mot-par-mot
# (_rtl_label_from_words) : terminologie standardisée entre les deux
# annexes, pas seulement au sein de l'une d'elles.
_AR_CHARGES_PRESTATIONS = ["أعباء تقديم الخدمة"]
_AR_CHARGES_ACQUISITION_GESTION = ["أعباء تصرف و اقتناء أخرى صافية"]

# Ventilation par branche (Annexe 15, Fonds Général) : libellé de ligne
# "أقساط تأمين صادرة" (Primes émises) - PLUS COURT que _AR_PRIMES
# ("...صادرة و مقبولة", Primes émises ET ACCEPTÉES, Annexes 3/4) : un motif
# flou pourrait confondre les deux pages puisque l'un est préfixe de
# l'autre - _EXCLUDE_PRIMES_BRANCHE écarte toute ligne contenant "مقبولة"
# (acceptées), absent de la ligne Annexe 15.
_AR_PRIMES_BRANCHE = ["أقساط تأمين صادرة"]
_EXCLUDE_PRIMES_BRANCHE = ["مقبولة"]

# "خصوم" (passif/dettes) et "صافية" (net) qualifient une ligne PARENTE qui
# partage un long préfixe avec la cible mais désigne un TOTAL DIFFÉRENT
# (ex: "مجموع الأموال الذاتية والخصوم" = Capitaux propres ET Passif, un
# contrôle d'équilibre bilanciel — pas la ligne Capitaux propres seule ;
# "مجموع الأصول الصافية" = Total des actifs NETS du Fonds des Participants
# uniquement, pas le Total Actif du bilan). Exclues des recherches
# concernées pour éviter qu'un score de similarité légèrement supérieur sur
# la ligne parente ne l'emporte par erreur (constaté 2026-08-11 sur
# AL_AMANAH_TAKAFUL_2020 : 76% pour "...والخصوم" contre 75% pour la bonne
# ligne "مجموع الأموال الذاتية").
#
# "الأصول"/"الذاتية" (actif/propres) : les deux libellés "مجموع الأصول"
# (Total actif) et "مجموع الأموال الذاتية" (Capitaux propres) partagent un
# préfixe assez long ("مجموع ال...") pour qu'une lecture OCR DÉGRADÉE de
# l'UN score suffisamment haut pour satisfaire une recherche visant
# l'AUTRE - constaté 2026-08-11 sur AL_AMANAH_TAKAFUL_2022 : "مجوع الأصول"
# (Total actif, OCR légèrement corrompu) scorait 62,5% contre la cible
# Capitaux propres, au-dessus du seuil, alors que la vraie ligne Capitaux
# propres n'a tout simplement pas été détectée sur cette page avec un
# meilleur score. Exclure "الأصول" du côté Capitaux propres et "الذاتية" du
# côté Total actif empêche cette confusion croisée sans dépendre d'un score
# plus élevé (qui rejetterait aussi de vrais positifs sur d'autres années).
_EXCLUDE_CAPITAUX = ["والخصوم", "الأصول"]
_EXCLUDE_ACTIF = ["الصافية", "الذاتية"]

# "Total actifs nets des adhérents" (Fonds des Participants) - Bilan Passif,
# section "أصول صافية" (actifs nets), AVANT la section Capitaux propres.
# "مجموع الأصول" (Total actif, 13 caractères) est un simple PRÉFIXE de cette
# cible (20 caractères) qui score ~76% par fuzz.ratio - juste au-dessus des
# seuils habituels (60-75%) et trouvé sur une page antérieure (Actif, pas
# Passif) : sans garde-fou de longueur, retenu à tort avant d'atteindre la
# vraie ligne (constaté 2026-08-20, voir arabic_ocr_extractor.find_label_row
# min_label_len_ratio). "والخصوم"/"الذاتية" exclus par cohérence avec
# _EXCLUDE_CAPITAUX (même risque de confusion avec le Total Bilan combiné ou
# les Capitaux propres).
_AR_TOTAL_ACTIFS_NETS_ADHERENTS = ["مجموع الأصول الصافية"]
_EXCLUDE_TOTAL_ACTIFS_NETS = ["والخصوم", "الذاتية"]
# Plancher/plafond propres à cette ligne (échelle différente de Total actif/
# Capitaux propres - c'est un solde NET du seul Fonds des Adhérents, pas le
# bilan entier) : sur 2020/2021/2024 vérifiés manuellement (-1 812 245 /
# 674 979 / 2 125 077), toujours sous 3 MDT en valeur absolue. Plafond fixé
# à 15 MDT (marge large) pour rejeter un faux positif observé sur
# AL_AMANAH_TAKAFUL_2022 (police PDF corrompue, voir commentaire
# find_kpi_value smart plus haut - la recherche y retombe par erreur sur la
# ligne Capitaux propres, 21 205 237) plutôt que de le laisser passer.
# Plancher à 10 000 : rejette un 0 par défaut (aucune ligne trouvée, ex:
# AL_AMANAH_TAKAFUL_2023 sur cet exercice) sans jamais rejeter une vraie
# valeur observée.
_MIN_PLAUSIBLE_ACTIFS_NETS_ADHERENTS = 10_000
_MAX_PLAUSIBLE_ACTIFS_NETS_ADHERENTS = 15_000_000

# Surplus du Fonds Takaful Familial/Général — même annexe "État de Surplus"
# que les Primes émises Familial/Général (pages 4/5 des exercices 2020-2022
# vérifiés, "Fonds des Adhérents"/"Fonds Familial ou Général" — mêmes pages
# que _AR_PRIMES ci-dessus). Vérifié VISUELLEMENT sur AL_AMANAH_TAKAFUL_2022
# (page 4 = Familial, page 5 = Général, images rendues et lues directement) :
# chaque ligne de ce tableau porte 3 ou 4 valeurs par exercice - "Cédées",
# "Nettes" (= colonne recherchée, même convention que _col_nettes_courantes
# côté français), "Total brut", précédées le cas échéant d'une colonne
# "exercice précédent" - avec l'identité comptable Net = Brut + Cédées
# vérifiée EXACTE sur les 4 cas contrôlés manuellement (ex: 2022 Familial :
# 359 339 = -891 528 + 1 250 867). Contrairement à Total actif/Capitaux
# propres, la ligne "فائض أو عجز..." est la DERNIÈRE de la page (pas de
# collision de préfixe connue), donc pas besoin de min_label_len_ratio ici.
_AR_SURPLUS_FAMILIAL = "فائض أو عجز صندوق التأمين التكافلي إعادة التأمين التكافلي العائلي".replace(" ", "")
_AR_SURPLUS_GENERAL = "فائض أو عجز صندوق التأمين التكافلي إعادة التأمين التكافلي العام".replace(" ", "")
# Ces 2 KPI vivent structurellement sur les pages 4 (Familial) et 5 (Général)
# - mêmes pages que Primes émises Familial/Général (_AR_PRIMES) - vérifié sur
# 2020/2021/2022. Ciblées directement plutôt que scannées sur AL_AMANAH_MAX_PAGES :
# une recherche floue générique sur plusieurs pages accroche à tort une page
# antérieure sur ce libellé long (score ~65-75% déjà sur la bonne page,
# jamais assez discriminant pour écarter un faux positif par le score seul).
_AL_AMANAH_SURPLUS_PAGE_FAMILIAL = 3  # index 0-based -> page 4
_AL_AMANAH_SURPLUS_PAGE_GENERAL = 4   # index 0-based -> page 5
_MAX_PLAUSIBLE_SURPLUS = 3_000_000
_SURPLUS_IDENTITY_TOLERANCE = 1.0


def _find_surplus_validated(pdf, page_index, target, min_score=55):
    """Localise la ligne de Surplus par correspondance floue OCR (fiable même
    sur les exercices à police corrompue, l'OCR lisant les glyphes affichés
    plutôt que le texte-couche - voir cas #4 du fichier CAS_PARTICULIERS_TAKAFUL.md),
    puis relit les CHIFFRES de cette ligne en texte réel quand il existe
    (fiable même sur ces mêmes exercices : la corruption de police touche les
    LETTRES arabes, pas les chiffres, qui utilisent des points de code
    standard) - combinaison OCR-localise/texte-réel-relit non couverte par
    find_kpi_value_smart (qui n'essaie chaque voie qu'isolément).

    N'accepte la valeur "Nette" (3e en partant de la fin) QUE si l'identité
    comptable Net = Cédées + Brut est vérifiée sur le triplet retenu -
    seul moyen fiable de distinguer un triplet complet [Net, Cédées, Brut]
    d'un triplet tronqué [exercice précédent, Net, Cédées] (même nombre de
    valeurs, sens différent) sans repère supplémentaire. Renvoie None plutôt
    qu'une valeur non vérifiée si l'identité échoue ou si le texte réel de
    cette page est indisponible (page scannée)."""
    from extraction.arabic_ocr_extractor import render_page, _ocr_lines
    from extraction.bilan_kpi_extractor import _extract_numeric_clusters, _is_plausible

    if page_index >= len(pdf.pages):
        return None
    page = pdf.pages[page_index]
    img = render_page(page)
    best_score, best_box = 0, None
    for text, box in _ocr_lines(img):
        label = unicodedata.normalize("NFKC", text).replace(" ", "")
        if len(label) < len(target) * 0.5:
            continue
        score = fuzz.ratio(label, target)
        if score > best_score:
            best_score, best_box = score, box
    if best_box is None or best_score < min_score:
        return None
    scale = page.height / img.height
    top, bottom = best_box[1] * scale, best_box[3] * scale
    for pad in (4, 2, 6, 8):
        cropped = page.crop((0, max(0, top - pad), page.width, bottom + pad))
        words = cropped.extract_words()
        clusters = [
            c[0] for c in _extract_numeric_clusters(words)
            if _is_plausible(c[0]) and abs(c[0]) <= _MAX_PLAUSIBLE_SURPLUS and c[0] != 0
        ]
        if len(clusters) >= 3:
            net, cedees, brut = clusters[-3], clusters[-2], clusters[-1]
            if abs(net - (cedees + brut)) <= _SURPLUS_IDENTITY_TOLERANCE:
                return net
    return None


AL_AMANAH_MAX_PAGES = 10

# Plancher de plausibilité PROPRE à cette société (pas le MIN_PLAUSIBLE_VALUE
# générique de bilan_kpi_extractor.py, trop bas ici) : sur l'historique
# 2017-2024 vérifié, jamais en-dessous de 6,8 MDT (2017, la plus petite
# valeur connue) - une lecture OCR garbée peut néanmoins produire un nombre
# NON NUL mais bien plus petit (ex: "25540" au lieu de "25540570", un
# groupe de chiffres tronqué) qui passerait le filtre générique sans
# problème. Fixé nettement en dessous du minimum historique (marge large
# pour une éventuelle année de démarrage non encore vue) plutôt que
# recalibré sur le minimum exact, pour ne jamais rejeter une vraie valeur
# basse par excès de prudence.
_MIN_PLAUSIBLE_TOTAL = 1_000_000

# Plafond de plausibilité pour les Charges de prestations/acquisition (pas
# pour Total actif/Capitaux propres, dont l'échelle est différente) : sur
# les 3 sociétés Takaful et 9 exercices vérifiés (2017-2025, voir dry-run),
# jamais au-delà de ~71 MDT (ZITOUNA_TAKAFUL 2025, la plus grosse valeur
# connue toutes sociétés confondues). Détecté nécessaire sur
# AL_AMANAH_TAKAFUL_2018 (exercice scanné, repli OCR) : "Charges
# d'acquisition et de gestion nettes" lu à 32,5 MILLIARDS de TND - un
# groupe de chiffres mal segmenté par l'OCR plutôt qu'une vraie valeur.
# Marge large (5x le maximum observé) pour ne pas rejeter une vraie
# croissance future, tout en écartant un ordre de grandeur manifestement
# aberrant.
_MAX_PLAUSIBLE_CHARGES = 350_000_000


def extract_al_amanah_takaful_kpis(pdf):
    from extraction.arabic_ocr_extractor import (
        find_kpi_value_smart, find_kpi_value_smart_sum, find_kpi_value_smart_list,
        find_kpi_row_all_values, find_row_by_value_scan,
        _select_actif_like, _select_equity_like, _select_last,
    )

    total_actif = find_kpi_value_smart(pdf, _AR_TOTAL_ACTIF, _select_actif_like, AL_AMANAH_MAX_PAGES,
                                        exclude_substrings=_EXCLUDE_ACTIF)
    if total_actif is not None and total_actif < _MIN_PLAUSIBLE_TOTAL:
        total_actif = None

    # Bilan Passif (mêmes pages que Total actif/Capitaux propres) : recherche
    # élargie (15 pages, garde-fou de longueur de libellé) - voir constantes
    # ci-dessus pour le détail du piège de confusion et sa correction.
    total_actifs_nets_adherents = find_kpi_value_smart(
        pdf, _AR_TOTAL_ACTIFS_NETS_ADHERENTS, _select_last, 15,
        min_score=60, min_row_score=60, min_label_len_ratio=0.75,
        exclude_substrings=_EXCLUDE_TOTAL_ACTIFS_NETS)
    if total_actifs_nets_adherents is not None and not (
        _MIN_PLAUSIBLE_ACTIFS_NETS_ADHERENTS <= abs(total_actifs_nets_adherents) <= _MAX_PLAUSIBLE_ACTIFS_NETS_ADHERENTS
    ):
        total_actifs_nets_adherents = None

    surplus_familial = _find_surplus_validated(pdf, _AL_AMANAH_SURPLUS_PAGE_FAMILIAL, _AR_SURPLUS_FAMILIAL)
    surplus_general = _find_surplus_validated(pdf, _AL_AMANAH_SURPLUS_PAGE_GENERAL, _AR_SURPLUS_GENERAL)

    capitaux = find_kpi_value_smart(pdf, _AR_CAPITAUX_AFFECTATION, _select_equity_like, AL_AMANAH_MAX_PAGES,
                                     exclude_substrings=_EXCLUDE_CAPITAUX)
    if capitaux is None:
        capitaux = find_kpi_value_smart(pdf, _AR_CAPITAUX, _select_equity_like, AL_AMANAH_MAX_PAGES,
                                         exclude_substrings=_EXCLUDE_CAPITAUX)
    if capitaux is not None and capitaux < _MIN_PLAUSIBLE_TOTAL:
        capitaux = None

    # Garde-fou anti-collision : Total actif et Capitaux propres ne peuvent
    # être RIGOUREUSEMENT égaux pour une société ayant le moindre passif -
    # une égalité exacte trahit presque toujours les deux recherches ayant
    # convergé sur la MÊME ligne par erreur (constaté 2026-08-11 en OCR pur,
    # les libellés "مجموع الأصول" et "مجموع الأموال الذاتية" étant parfois
    # confondus par une lecture dégradée). Mieux vaut aucune valeur qu'une
    # valeur dupliquée à tort - cohérent avec le principe du projet de
    # préférer None à un chiffre inventé/faux.
    if total_actif is not None and capitaux is not None and total_actif == capitaux:
        total_actif = None

    # Identité bilancielle Total actif = Capitaux propres + Total passif :
    # comme le passif ne peut être négatif, Total actif est TOUJOURS >=
    # Capitaux propres pour une société réelle. Une valeur qui viole cette
    # identité trahit une lecture OCR corrompue (chiffre tronqué ou groupe
    # de chiffres mal segmenté) plutôt qu'une donnée valide.
    if total_actif is not None and capitaux is not None and total_actif < capitaux:
        total_actif = None

    resultat_net = find_kpi_value_smart(pdf, _AR_RESULTAT_NET, _select_equity_like, AL_AMANAH_MAX_PAGES)

    # Le Fonds Familial est systematiquement la 1ere occurrence rencontree
    # dans le document (page anterieure au Fonds General) sur les 9 exercices
    # verifies (2017-2025) - meme convention d'ordre que cote francais
    # (extract_fonds_participants_kpis : Annexe 3 = Familial avant Annexe 4 =
    # General). Pas de somme separee ici : primes_familial + primes_general
    # redonne exactement primes_total quand les deux sont trouves.
    primes_list = find_kpi_value_smart_list(pdf, _AR_PRIMES, _select_last, AL_AMANAH_MAX_PAGES)
    primes_familial = primes_list[0] if len(primes_list) >= 1 else None
    primes_general = primes_list[1] if len(primes_list) >= 2 else None
    primes_total = sum(primes_list) if primes_list else None

    # Charges de prestations / Charges d'acquisition et de gestion nettes
    # (Annexes 14/15, colonne Total) : find_kpi_value_smart_sum somme déjà
    # les 2 pages (Familial + Général) trouvées pour ce libellé - même
    # fonction que celle utilisée pour Primes émises par assurance ci-dessus
    # côté "smart" (recherche sur texte réel ou repli OCR). Valeur absolue :
    # ces charges sont notées en négatif dans le document (même convention
    # que côté français, voir _extract_ventilation_charges_kpis).
    #
    # AL_AMANAH_MAX_PAGES=10 (calibré sur le Bilan/Annexes 3/4, en tête de
    # document) est insuffisant ici : les Annexes 14/15 sont vérifiées aux
    # pages 38-39 (exercice 2020) - plafond dédié avec marge.
    ventilation_max_pages = 45
    charges_prestations = find_kpi_value_smart_sum(pdf, _AR_CHARGES_PRESTATIONS, _select_last, ventilation_max_pages)
    if charges_prestations is not None:
        charges_prestations = abs(charges_prestations)
        if charges_prestations > _MAX_PLAUSIBLE_CHARGES:
            charges_prestations = None
    charges_acquisition = find_kpi_value_smart_sum(pdf, _AR_CHARGES_ACQUISITION_GESTION, _select_last, ventilation_max_pages)
    if charges_acquisition is not None:
        charges_acquisition = abs(charges_acquisition)
        if charges_acquisition > _MAX_PLAUSIBLE_CHARGES:
            charges_acquisition = None

    # Ventilation par branche (Annexe 15, Fonds Général uniquement) :
    # ORDRE DES COLONNES INVERSÉ par rapport au français - vérifié par
    # reconstruction mot-par-mot (x0 croissant) sur AL_AMANAH_TAKAFUL_2020,
    # page 39 : Total est la 1ère colonne (pas la dernière, contrairement à
    # AT_TAKAFULIA/ZITOUNA_TAKAFUL), Automobile la DERNIÈRE - cohérent avec
    # la mise en page RTL du document. Confirmé par somme de contrôle : les
    # 8 catégories intermédiaires + les 3 dernières valeurs redonnent
    # exactement la 1ère (Total = 27 074 059, vérifié au dinar près).
    #
    # min_row_score abaissé à 60 (repli OCR) : nécessaire pour que ce
    # libellé précis soit détecté sur toutes les pages testées, mais un
    # seuil aussi permissif peut accrocher à tort une AUTRE ligne du
    # document (constaté 2026-08-15 sur AL_AMANAH_TAKAFUL_2019 : la page 1,
    # sans rapport, matche AVANT la vraie page 38). `_branch_row_valid` sert
    # de VALIDATEUR à find_kpi_row_all_values : une page dont les valeurs ne
    # passent pas ce contrôle est écartée et la recherche CONTINUE sur les
    # pages suivantes plutôt que de s'arrêter là - indispensable, sinon le
    # premier faux positif empêche à tort d'atteindre la vraie page. Le
    # contrôle lui-même exploite la structure connue de la ligne (1ère
    # valeur = colonne Total, voir note ci-dessus) : si la somme des 8
    # branches ne lui correspond pas à 2% près, ce n'est presque
    # certainement pas la bonne ligne.
    def _branch_row_valid(values):
        if len(values) < 4:
            return False
        total_candidate = values[0]
        computed_sum = values[-1] + values[-2] + values[-3] + sum(values[1:-3])
        return bool(total_candidate) and abs(computed_sum - total_candidate) / total_candidate <= 0.02

    # Pas de start_page : l'Annexe 15 tombe à des pages très différentes
    # selon l'exercice (page 15 en 2021, page 38 en 2019) - aucun plancher
    # commun fiable. Le validateur ci-dessus suffit seul à écarter un faux
    # positif rencontré tôt (ex: page 1) SANS bloquer la recherche : il la
    # fait simplement continuer jusqu'à la vraie page, où qu'elle soit.
    branches_values = find_kpi_row_all_values(pdf, _AR_PRIMES_BRANCHE, ventilation_max_pages,
                                               min_row_score=60, exclude_substrings=_EXCLUDE_PRIMES_BRANCHE,
                                               ocr_x_frac=(0.02, 0.85),
                                               validator=_branch_row_valid)
    # Repli par BALAYAGE POSITIONNEL (pas de libellé) quand la recherche par
    # libellé échoue entièrement : arrive quand l'OCR lit correctement les
    # CHIFFRES d'une page mais rend le libellé arabe en charabia total
    # (constaté 2026-08-16 sur AL_AMANAH_TAKAFUL_2024, page 32 - voir
    # find_row_by_value_scan). On recoupe avec "Primes émises Général (TND)"
    # (primes_general, déjà extrait ci-dessus via l'Annexe 3/4 - table
    # DIFFÉRENTE, donc non affectée par la même dégradation OCR) : la ligne
    # Annexe 15 correspondante doit avoir exactement le même total.
    if branches_values is None and primes_general:
        branches_values = find_row_by_value_scan(pdf, primes_general, ventilation_max_pages,
                                                   ocr_x_frac=(0.02, 0.85))
        if branches_values and not _branch_row_valid(branches_values):
            branches_values = None
    if branches_values:
        automobile = branches_values[-1]
        transport = branches_values[-2]
        incendie = branches_values[-3]
        milieu = branches_values[1:-3]
        divers = sum(milieu) if milieu else 0.0
    else:
        automobile = transport = incendie = divers = None

    return {
        "Total actif": total_actif,
        "Capitaux propres": capitaux,
        "Total actifs nets des adhérents (TND)": total_actifs_nets_adherents,
        "Surplus du Fonds Takaful Familial (TND)": surplus_familial,
        "Surplus du Fonds Takaful Général (TND)": surplus_general,
        "Résultat Net": resultat_net,
        "Primes émises par assurance": primes_total,
        "Primes émises Familial (TND)": primes_familial,
        "Primes émises Général (TND)": primes_general,
        "Charges de prestations": charges_prestations,
        "Charges d'acquisition et de gestion nettes": charges_acquisition,
        "Contributions Automobile (TND)": automobile,
        "Contributions Transport (TND)": transport,
        "Contributions Incendie (TND)": incendie,
        "Contributions Divers (TND)": divers,
    }
