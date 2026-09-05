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
RESULTAT_NET_RE = re.compile(r"r\s?esultat net de l.?exercice\b")
RESULTAT_EXERCICE_FALLBACK_RE = re.compile(r"^r\s?esultat de l.?exercice\b")
PRIMES_EMISES_RE = re.compile(r"primes emises et acceptees\b")
BILAN_COMBINE_MARKER_RE = re.compile(r"bilan combine")

ANNEXE_VENTILATION_FAMILIAL_TITLE_RE = re.compile(
    r"ventilation.*surplus.*deficit.*categorie.*assurance.*familial"
)
ANNEXE_VENTILATION_GENERAL_TITLE_RE = re.compile(
    r"ventilation.*surplus.*deficit.*categorie.*assurance.*general"
)
CHARGES_PRESTATIONS_RE = re.compile(r"^charges de prestations?\b")
CHARGES_ACQUISITION_GESTION_RE = re.compile(r"^charges d.?acquisition et de gestion nettes")

ANNEXE_FAMILIAL_TITLE_RE = re.compile(r"surplus ou deficit du fonds takaful familial")
ANNEXE_GENERAL_TITLE_RE  = re.compile(r"surplus ou deficit du fonds takaful general")
SURPLUS_LIGNE_RE = re.compile(r"surplus ou deficit de l.?assurance")
TOTAL_ACTIFS_NETS_ADHERENTS_RE = re.compile(r"total des actifs nets des adherents")
PROVISIONS_TECHNIQUES_BRUTES_RE = re.compile(r"provisions techniques brutes\b")
ENTREPRISE_RESULTAT_TITLE_RE = re.compile(r"etat de resultat de l.?entreprise")
COMMISSION_WAKALA_RE    = re.compile(r"commission wakala\b")
COMMISSION_MOUDHARABA_RE = re.compile(r"commission moudharaba\b")

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
                value = clusters[0][0]
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


_AR_TOTAL_ACTIF = ["مجموع الأصول"]
_AR_CAPITAUX_AFFECTATION = ["مجموع الأموال الذاتية قبل التوزيع"]
_AR_CAPITAUX = ["مجموع الأموال الذاتية"]
_AR_RESULTAT_NET = ["مال ذاتي نتيجة السنة المحاسبية"]
_AR_PRIMES = ["أر ع أقساط تأمين صادرة و مقبولة", "أقساط تأمين صادرة و مقبولة"]
_AR_CHARGES_PRESTATIONS = ["أعباء تقديم الخدمة"]
_AR_CHARGES_ACQUISITION_GESTION = ["أعباء تصرف و اقتناء أخرى صافية"]

_AR_PRIMES_BRANCHE = ["أقساط تأمين صادرة"]
_EXCLUDE_PRIMES_BRANCHE = ["مقبولة"]

_EXCLUDE_CAPITAUX = ["والخصوم", "الأصول"]
_EXCLUDE_ACTIF = ["الصافية", "الذاتية"]

_AR_TOTAL_ACTIFS_NETS_ADHERENTS = ["مجموع الأصول الصافية"]
_EXCLUDE_TOTAL_ACTIFS_NETS = ["والخصوم", "الذاتية"]
_MIN_PLAUSIBLE_ACTIFS_NETS_ADHERENTS = 10_000
_MAX_PLAUSIBLE_ACTIFS_NETS_ADHERENTS = 15_000_000

_AR_SURPLUS_FAMILIAL = "فائض أو عجز صندوق التأمين التكافلي إعادة التأمين التكافلي العائلي".replace(" ", "")
_AR_SURPLUS_GENERAL = "فائض أو عجز صندوق التأمين التكافلي إعادة التأمين التكافلي العام".replace(" ", "")
_AL_AMANAH_SURPLUS_PAGE_FAMILIAL = 3
_AL_AMANAH_SURPLUS_PAGE_GENERAL = 4
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

_MIN_PLAUSIBLE_TOTAL = 1_000_000

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

    if total_actif is not None and capitaux is not None and total_actif == capitaux:
        total_actif = None

    if total_actif is not None and capitaux is not None and total_actif < capitaux:
        total_actif = None

    resultat_net = find_kpi_value_smart(pdf, _AR_RESULTAT_NET, _select_equity_like, AL_AMANAH_MAX_PAGES)

    primes_list = find_kpi_value_smart_list(pdf, _AR_PRIMES, _select_last, AL_AMANAH_MAX_PAGES)
    primes_familial = primes_list[0] if len(primes_list) >= 1 else None
    primes_general = primes_list[1] if len(primes_list) >= 2 else None
    primes_total = sum(primes_list) if primes_list else None

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

    def _branch_row_valid(values):
        if len(values) < 4:
            return False
        total_candidate = values[0]
        computed_sum = values[-1] + values[-2] + values[-3] + sum(values[1:-3])
        return bool(total_candidate) and abs(computed_sum - total_candidate) / total_candidate <= 0.02

    branches_values = find_kpi_row_all_values(pdf, _AR_PRIMES_BRANCHE, ventilation_max_pages,
                                               min_row_score=60, exclude_substrings=_EXCLUDE_PRIMES_BRANCHE,
                                               ocr_x_frac=(0.02, 0.85),
                                               validator=_branch_row_valid)
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
