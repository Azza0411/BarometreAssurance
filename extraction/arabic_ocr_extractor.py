"""Extraction générique pour les pages de états financiers scannées en
arabe (image, pas de texte PDF direct) — cas rencontré sur les documents
El Amana Takaful (voir CAS_PARTICULIERS_TAKAFUL.md).

Principe (vérifié manuellement le 2026-08-11 sur AL_AMANAH_TAKAFUL_2024.pdf,
chiffres recoupés avec les 2 autres compagnies Takaful) :
  - L'OCR du modèle arabe de Tesseract n'est PAS fiable pour lire des
    montants (confond les chiffres, ex. "38 089 744" lu "35 089 4") — donc
    jamais utilisé comme source de valeur.
  - Il reste assez fiable pour repérer approximativement une LIGNE par
    correspondance floue sur le libellé arabe attendu (ex. "مجموع الأصول"),
    même si le texte reconnu contient des erreurs de caractères.
  - Une fois la ligne (et la colonne, repérée de la même façon via l'en-tête
    de colonne) localisée, on découpe précisément cette cellule et on la
    relit avec le modèle ANGLAIS de Tesseract (mode chiffres uniquement) :
    les rapports financiers tunisiens utilisent des chiffres occidentaux
    même en arabe, et le modèle anglais les lit correctement là où le
    modèle arabe se trompe.

Ceci généralise à N'IMPORTE QUEL rapport scanné en arabe suivant la même
logique (libellés + tableaux de chiffres occidentaux) ; seule la LISTE des
libellés à chercher est spécifique à chaque KPI, pas la mécanique.
"""
import os
import re
import unicodedata
import pytesseract
from rapidfuzz import fuzz

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters, NUMERIC_TOKEN_RE, _is_plausible,
)

_TESSDATA_DIR = os.path.join(os.path.dirname(__file__), "tessdata_ara")
_ARA_CONFIG = f'--tessdata-dir "{_TESSDATA_DIR}" -l ara --psm 6'
_DIGIT_CONFIG = '-l eng --psm 7 -c tessedit_char_whitelist=0123456789-'

MIN_CHARS_FOR_REAL_TEXT = 300


def is_scanned_page(pdf_page):
    """Vrai si le corps de la page n'a pas de texte réellement extractible
    (donc rendu comme une image) — condition de repli vers l'OCR."""
    return len(pdf_page.chars) < MIN_CHARS_FOR_REAL_TEXT


def render_page(pdf_page, resolution=300):
    return pdf_page.to_image(resolution=resolution).original


def _ocr_lines(image, region=None):
    """Renvoie [(texte, (left,top,right,bottom)), ...] pour chaque ligne de
    texte détectée par le modèle arabe dans `region` (ou toute l'image)."""
    crop = image.crop(region) if region else image
    data = pytesseract.image_to_data(
        crop, config=_ARA_CONFIG, output_type=pytesseract.Output.DICT
    )
    lines = {}
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        e = lines.setdefault(key, {"words": [], "l": [], "t": [], "r": [], "b": []})
        e["words"].append(text)
        e["l"].append(data["left"][i])
        e["t"].append(data["top"][i])
        e["r"].append(data["left"][i] + data["width"][i])
        e["b"].append(data["top"][i] + data["height"][i])
    x_off, y_off = (region[0], region[1]) if region else (0, 0)
    out = []
    for e in lines.values():
        text = " ".join(e["words"])
        box = (min(e["l"]) + x_off, min(e["t"]) + y_off, max(e["r"]) + x_off, max(e["b"]) + y_off)
        out.append((text, box))
    return out


def find_label_row(image, label_variants, region=None, min_score=65, exclude_substrings=None,
                    min_label_len_ratio=None):
    """Correspondance floue entre les lignes OCRisées de `region` et une
    liste de libellés arabes candidats (plusieurs variantes possibles selon
    l'année du rapport). Renvoie la plage y (top, bottom) de la meilleure
    correspondance, ou None si rien ne dépasse `min_score`.

    Utilise fuzz.ratio (similarité globale), pas partial_ratio : ces
    rapports ont plusieurs libellés qui PARTAGENT un même suffixe générique
    (ex. « ...السنة المحاسبية » = « ... de l'exercice comptable » apparaît
    aussi bien sur « نتيجة السنة المحاسبية » — le résultat net recherché —
    que sur une ligne totalement différente, « فائض أو عجز صندوق
    المشتركين للسنة المحاسبية » — confirmé confondu en test le 2026-08-11).
    partial_ratio score les deux haut sur ce seul suffixe commun ; ratio
    pénalise correctement la différence de longueur/contenu global.
    `label_variants` doit donc rester le libellé le plus complet possible
    (avec son préfixe numéroté, ex. « مال ذاتي 6 نتيجة السنة المحاسبية »),
    pas un fragment générique, pour rester discriminant.

    `min_label_len_ratio` écarte un candidat dont le libellé OCRisé (espaces
    retirés) est nettement plus COURT que la cible : un libellé qui est un
    simple PRÉFIXE d'un libellé plus long peut suffire à passer `min_score`
    (ratio pénalise la différence de longueur mais pas toujours assez) -
    constaté 2026-08-20 sur AL_AMANAH_TAKAFUL : « مجموع الأصول » (Total
    actif, 13 caractères) score 76% contre la cible « مجموع الأصول الصافية »
    (Total actifs nets, 20 caractères) et est trouvé sur une page antérieure,
    donc retenu à tort avant que le vrai libellé (plus long, mais moins bien
    reconnu par l'OCR, ~65-70%) ne soit atteint. Sans effet si None (défaut),
    pour ne rien changer aux appels existants."""
    best, best_score = None, min_score
    for text, box in _ocr_lines(image, region):
        # Espaces retirés pour la vérification d'exclusion uniquement : l'OCR
        # insère des espaces parasites de façon imprévisible (ex: "و الخصوم"
        # au lieu de "والخصوم"), ce qui ferait passer une sous-chaîne à
        # exclure au travers d'un test `in` naïf - constaté 2026-08-11 sur
        # AL_AMANAH_TAKAFUL_2022 (voir takaful_kpi_extractor._EXCLUDE_CAPITAUX).
        text_nospace = text.replace(" ", "")
        if exclude_substrings:
            if any(sub.replace(" ", "") in text_nospace for sub in exclude_substrings):
                continue
        for label in label_variants:
            if min_label_len_ratio is not None and len(text_nospace) < len(label.replace(" ", "")) * min_label_len_ratio:
                continue
            score = fuzz.ratio(text, label)
            if score > best_score:
                best_score, best = score, box
    return (best[1], best[3]) if best else None


_ROW_DIGITS_CONFIG = "-l eng --psm 11 -c tessedit_char_whitelist=0123456789"


# Écart (px, image rendue ~300 dpi) séparant deux groupes de chiffres du
# MÊME nombre (un séparateur de milliers fin/étroit) d'un écart entre deux
# nombres DIFFÉRENTS. Calibré 2026-08-11 sur AL_AMANAH_TAKAFUL_2022.pdf :
# tesseract (mode texte épars) segmente parfois un seul nombre à séparateurs
# de milliers en plusieurs "mots" OCR - ex. "21587910" détecté comme deux
# mots adjacents "21587"+"10" (écart 6px) - alors que l'écart entre deux
# VRAIES colonnes voisines est nettement plus large (20-29px sur le même
# document). Sans ce regroupement, `float()` sur chaque mot séparément
# tronque silencieusement le nombre (ex. "21587" au lieu de "21587910").
_DIGIT_GROUP_MERGE_GAP = 14


def ocr_row_numbers(image, y_range, x_range, pad_y=4):
    """Lit TOUS les nombres présents sur la ligne `y_range` (dans la plage
    horizontale `x_range`), triés de gauche à droite. Bien plus fiable que
    de viser une colonne précise via son en-tête arabe (fragile — en-têtes
    fusionnées sur plusieurs lignes, libellés quasi identiques d'une colonne
    à l'autre) : ici on laisse Tesseract (mode « texte épars », chiffres
    uniquement) détecter chaque groupe de chiffres indépendamment, puis on
    choisit par POSITION (index gauche→droite), déterminée une fois pour
    toutes par le nombre de colonnes connu du gabarit du rapport."""
    top, bottom = y_range
    left, right = x_range
    crop = image.crop((left, max(0, top - pad_y), right, bottom + pad_y))
    data = pytesseract.image_to_data(crop, config=_ROW_DIGITS_CONFIG, output_type=pytesseract.Output.DICT)
    tokens = []
    for i in range(len(data["text"])):
        t = data["text"][i].strip()
        if t and any(c.isdigit() for c in t):
            tokens.append((data["left"][i], data["left"][i] + data["width"][i], t))
    tokens.sort(key=lambda tok: tok[0])

    groups, current_text, current_left, prev_right = [], "", None, None
    for tok_left, tok_right, text in tokens:
        if prev_right is not None and (tok_left - prev_right) >= _DIGIT_GROUP_MERGE_GAP:
            groups.append((current_left, current_text))
            current_text = ""
        if not current_text:
            current_left = tok_left
        current_text += text
        prev_right = tok_right
    if current_text:
        groups.append((current_left, current_text))

    values = []
    for _, t in groups:
        try:
            values.append(float(t))
        except ValueError:
            values.append(None)
    return values


def extract_cell(image, label_variants, column_index_from_right, n_columns_expected=None,
                  label_region=None, row_x_range=None, min_row_score=65):
    """Trouve la ligne par libellé arabe (flou), lit tous les nombres de
    cette ligne triés de gauche à droite, puis renvoie celui situé à
    `column_index_from_right` colonnes de la FIN de la ligne (0 = dernière
    colonne, 1 = avant-dernière, etc.) — pas depuis le début.

    Pourquoi depuis la droite : en test (2026-08-11), un « 0 » isolé en fin
    de ligne est parfois manqué par l'OCR sur ces tableaux (plausible :
    faible confiance sur un unique chiffre de petite taille), ce qui décale
    tous les index comptés depuis la gauche. La colonne visée (Entreprise,
    année en cours) est structurellement l'avant-dernière de la ligne (la
    toute dernière étant Fonds des Participants de l'année en cours) —
    compter depuis la droite reste donc correct même si un zéro de tête
    (années/colonnes plus anciennes) a été perdu, tant que les valeurs de
    FIN de ligne sont bien détectées (constaté fiable sur les tests).

    `n_columns_expected` tolère qu'il manque une valeur (le zéro isolé
    ci-dessus) mais pas plus : au-delà, mieux vaut N/D qu'un chiffre pris au
    mauvais endroit."""
    y_range = find_label_row(image, label_variants, region=label_region, min_score=min_row_score)
    if y_range is None:
        return None
    x_range = row_x_range or (0, image.width)
    values = ocr_row_numbers(image, y_range, x_range)
    if n_columns_expected is not None and len(values) not in (n_columns_expected, n_columns_expected - 1):
        return None
    idx = -(column_index_from_right + 1)
    if abs(idx) > len(values):
        return None
    return values[idx]


# ─────────────────────────────────────────────────────────────────────────
# Texte réel (pages NON scannées) — plusieurs exercices d'El Amana Takaful
# (2017, 2019-2022 vérifié) ont en fait du texte PDF réellement extractible,
# juste en arabe : plus fiable qu'une relecture OCR quand disponible, donc
# toujours tenté EN PREMIER (voir extract_document_kpis), l'OCR ne servant
# que de repli pour les pages/exercices réellement scannés (2018, 2023,
# 2024, 2025 vérifié).
#
# Deux défauts SPÉCIFIQUES à l'extraction de texte réel en arabe (absents en
# français, donc absents de bilan_kpi_extractor._label_text) :
#   1. Chaque MOT a ses caractères stockés en ordre MIROIR (visuel), pas en
#      ordre logique Unicode - ex. "الأصول" (assets) est extrait
#      "لوـــصلأا" (tatweel ـ inclus). Corrigé en retirant le tatweel puis
#      en inversant la chaîne du mot.
#   2. Les MOTS eux-mêmes sont physiquement disposés de droite à gauche sur
#      la page (RTL) : le mot lu EN PREMIER (le plus à droite) a le plus
#      grand x0, contrairement au français où le premier mot lu est le plus
#      à gauche. Corrigé en triant par x0 DÉCROISSANT.
# Les deux corrections vérifiées le 2026-08-11 en reconstruisant "مجموع
# الأصول" (Total actif) à l'identique depuis les tokens bruts d'un document
# réel (AL_AMANAH_TAKAFUL_2020.pdf).
#
# Les NOMBRES ne sont PAS affectés (jamais mis en miroir, toujours disposés
# g→d sur la page comme dans un document français) : on réutilise donc
# _extract_numeric_clusters tel quel.
# Certaines lignes portent une annotation glissée AU MILIEU du libellé
# (ex: AL_AMANAH_TAKAFUL_2021, "...الذاتي)7211:dic(ة..." - une note de type
# date/référence de renvoi, mécanisme non identifié avec certitude mais dont
# l'effet est net : elle coupe le libellé en deux morceaux, faisant
# s'effondrer le score de similarité même si le contenu réel correspond
# parfaitement une fois l'annotation retirée). Comme pour le tatweel, ce
# n'est pas du contenu porteur de sens pour l'appariement - on le retire
# avant comparaison.
_PARENTHETICAL_RE = re.compile(r"\([^()]*\)|\)[^()]*\(")


def _rtl_label_from_words(words):
    non_numeric = [w for w in words if not NUMERIC_TOKEN_RE.match(w["text"])]
    non_numeric.sort(key=lambda w: -w["x0"])
    raw = " ".join(w["text"].replace("ـ", "")[::-1] for w in non_numeric)
    cleaned = _PARENTHETICAL_RE.sub("", raw)
    # Certains exercices (constaté : AL_AMANAH_TAKAFUL_2017) encodent le
    # texte en formes de présentation arabes (Unicode "Arabic Presentation
    # Forms-B", des points de code DIFFÉRENTS des lettres arabes standard
    # bien que visuellement identiques une fois affichés) plutôt qu'en
    # lettres normales - la comparaison échoue totalement (score ~4%) tant
    # que le texte n'est pas replié vers sa forme standard. NFKC fait
    # exactement ça (et ne change rien sur du texte déjà en lettres
    # standard, donc sans risque pour les autres exercices) - vérifié
    # 2026-08-11, score 100% après normalisation contre 4% avant.
    return unicodedata.normalize("NFKC", cleaned)


def find_label_row_words(lines, label_variants, min_score=75, exclude_substrings=None, min_label_len_ratio=None):
    """Équivalent de find_label_row pour des lignes déjà regroupées par
    bilan_kpi_extractor._cluster_lines (texte réel, pas OCR).

    Compare les libellés ESPACES RETIRÉS (comparaison caractère à caractère
    via fuzz.ratio) plutôt que mot à mot : pdfplumber découpe régulièrement
    un seul mot arabe en plusieurs tokens à cause d'espacements de police
    internes (kerning), ce qui insère des espaces arbitraires au milieu d'un
    mot une fois reconstruit - un vrai mot ne se distingue plus d'une
    coupure d'espacement. Vérifié le 2026-08-11 : "نتيجة السنة المحاسبية"
    reconstruit en "نتي جة ا ل سنة ا لم حا سبية" (espaces internes en trop)
    ne matche qu'à 50% avec token_sort_ratio (sensible à ces "mots"
    fantômes) mais à 100% une fois les espaces retirés des deux côtés.

    `exclude_substrings` écarte toute ligne dont le libellé (espaces
    retirés) contient l'une de ces sous-chaînes, AVANT le calcul du score -
    nécessaire quand une ligne "parente" partage un long préfixe avec la
    cible mais ajoute un qualificatif qui change complètement le sens (ex:
    AL_AMANAH_TAKAFUL_2020, page Passif : "مجموع الأموال الذاتية" seul =
    Capitaux propres, mais "مجموع الأموال الذاتية والخصوم" = Total Capitaux
    propres ET Passif, un contrôle d'équilibre bilanciel différent - vérifié
    2026-08-11, ce dernier scorait 76% contre la cible "...قبل التوزيع"
    quand le vrai Capitaux Propres ne scorait que 75%, inversant le
    classement d'un seul point)."""
    best, best_score = None, min_score - 1
    for line in lines:
        label = _rtl_label_from_words(line).replace(" ", "")
        if not label:
            continue
        if exclude_substrings and any(sub in label for sub in exclude_substrings):
            continue
        for variant in label_variants:
            variant_nospace = variant.replace(" ", "")
            if min_label_len_ratio is not None and len(label) < len(variant_nospace) * min_label_len_ratio:
                continue
            score = fuzz.ratio(label, variant_nospace)
            if score >= min_score and score > best_score:
                best_score, best = score, line
    return best


def extract_cell_from_words(lines, label_variants, column_index_from_right, min_score=75, exclude_substrings=None):
    """Équivalent de extract_cell pour du texte réel : trouve la ligne par
    libellé arabe (flou, RTL-corrigé), lit tous les nombres de cette ligne
    (déjà dans le bon ordre gauche→droite, cf. remarque ci-dessus) et
    renvoie celui situé à `column_index_from_right` de la fin - même
    convention que la voie OCR (voir extract_cell), pour que les DEUX voies
    utilisent les mêmes appels côté logique métier (takaful_kpi_extractor).

    Filtre les valeurs via _is_plausible avant l'indexation : certaines
    lignes collent un code de ligne numérique (ex: "أر ع 11") directement
    contre le libellé, SANS séparateur - capturé comme un token numérique
    de plus, à la position la plus à droite (donc la dernière de la liste,
    vu que les codes de ligne arabes sont positionnés à la même extrémité
    que le début de lecture RTL) - ex: AL_AMANAH_TAKAFUL_2020, page Fonds
    Familial : [3706721, 3500164, -1266194, 4766358, 11] où "11" est le code
    de ligne, pas une 5e colonne. Même problème et même solution que
    bilan_kpi_extractor._col_first_plausible côté français."""
    line = find_label_row_words(lines, label_variants, min_score, exclude_substrings)
    if line is None:
        return None
    clusters = [c for c in _extract_numeric_clusters(line) if _is_plausible(c[0])]
    if not clusters:
        return None
    idx = -(column_index_from_right + 1)
    if abs(idx) > len(clusters):
        return None
    return clusters[idx][0]


def page_lines_if_real_text(page):
    """Renvoie les lignes regroupées (utilisables par extract_cell_from_words)
    si la page a du texte réellement extractible, sinon None (page
    scannée - voir is_scanned_page)."""
    if is_scanned_page(page):
        return None
    words = page.extract_words()
    if not words:
        return None
    return _cluster_lines(words)


# ─────────────────────────────────────────────────────────────────────────
# Recherche document entier, texte réel PUIS OCR en repli — le second passage
# n'est PAS réservé aux pages détectées "scannées" (is_scanned_page) : au
# moins un exercice (AL_AMANAH_TAKAFUL_2022) a du texte réellement
# extractible mais dont la police embarquée mappe certains caractères vers
# le MAUVAIS point de code Unicode (constaté : "مجموع" ressort "يدًىع" -
# lettres non correspondantes, pas un simple décalage inversible). Les
# GLYPHES affichés restent corrects (sinon le document serait illisible à
# l'œil) : rendre la page en image et OCRiser contourne donc ce défaut
# d'encodage, quelle que soit sa cause exacte. Le second passage n'est tenté
# que si le premier échoue partout (l'OCR est nettement plus lent).
def find_kpi_value(pdf, label_variants, column_index_from_right, max_pages=20,
                    min_score=75, min_row_score=60):
    for page in pdf.pages[:max_pages]:
        lines = page_lines_if_real_text(page)
        if lines is None:
            continue
        value = extract_cell_from_words(lines, label_variants, column_index_from_right, min_score)
        if value is not None:
            return value
    for page in pdf.pages[:max_pages]:
        image = render_page(page)
        value = extract_cell(image, label_variants, column_index_from_right, min_row_score=min_row_score)
        if value is not None:
            return value
    return None


def find_kpi_value_sum(pdf, label_variants, column_index_from_right, max_pages=20,
                        min_score=90, min_row_score=75):
    """Comme find_kpi_value, mais SOMME toutes les occurrences trouvées
    (Primes émises = famille + général, chacune sur sa propre page/table) au
    lieu de s'arrêter à la première. `min_score`/`min_row_score` sont ici
    volontairement plus stricts que find_kpi_value par défaut : une somme
    est bien plus sensible à un faux positif (double comptage ou ajout d'une
    ligne non pertinente) qu'une recherche à occurrence unique - vérifié le
    2026-08-11, un libellé tronqué ("أقساط تأمين صادرة" sans "و مقبولة",
    présent sur une page de détail sans rapport) matchait à 75-81% mais
    jamais au-delà de 90% une fois le préfixe de code de ligne inclus dans
    `label_variants`."""
    total = None
    for page in pdf.pages[:max_pages]:
        lines = page_lines_if_real_text(page)
        if lines is None:
            continue
        value = extract_cell_from_words(lines, label_variants, column_index_from_right, min_score)
        if value is not None:
            total = (total or 0) + value
    if total is not None:
        return total
    for page in pdf.pages[:max_pages]:
        image = render_page(page)
        value = extract_cell(image, label_variants, column_index_from_right, min_row_score=min_row_score)
        if value is not None:
            total = (total or 0) + value
    return total


# ─────────────────────────────────────────────────────────────────────────
# Sélecteurs de colonne SENSIBLES AU FORMAT ("nouveau" NCT 43 vs "ancien",
# voir takaful_kpi_extractor.py) — nécessaires car un `column_index_from_right`
# FIXE ne suffit plus une fois l'historique complet couvert : AL_AMANAH_TAKAFUL
# a changé de mise en page du Bilan au moins une fois (vérifié 2026-08-11,
# comparaison directe AL_AMANAH_TAKAFUL_2017.pdf vs 2020.pdf) :
#   - "nouveau" (2019+ vérifié) : Bilan Combiné, 3 sous-colonnes par exercice
#     (Combiné/Entreprise/Fonds des Participants) x 2 exercices comparés,
#     Entreprise-exercice-courant = avant-dernière valeur de la ligne.
#   - "ancien" (2017 vérifié) : une seule colonne pour l'exercice PRÉCÉDENT
#     (pas de scission Fonds/Entreprise cette année-là) + la scission
#     complète à 3 colonnes pour l'exercice EN COURS seulement -> 4 valeurs
#     au total, Entreprise-exercice-courant = 3e à partir de la fin (et non
#     avant-dernière : la dernière valeur de la ligne dans ce format est déjà
#     le Fonds des Participants de l'exercice en cours, pas un second
#     exercice complet).
# Capitaux propres / Résultat net, eux, n'ont JAMAIS de colonne Fonds des
# Participants (notion qui ne s'applique pas à ces lignes) : "nouveau"
# duplique simplement Combiné=Entreprise (2 valeurs par exercice, 4 au
# total), "ancien" n'a qu'une seule valeur par exercice (2 au total) - dans
# les deux cas l'exercice en cours est le DERNIER groupe, mais sa position
# absolue diffère (avant-dernière vs dernière valeur).
def _select_actif_like(values):
    if len(values) >= 5:
        idx = -2
    elif len(values) == 4:
        idx = -3
    else:
        return None
    return values[idx] if abs(idx) <= len(values) else None


def _select_equity_like(values):
    if len(values) >= 3:
        idx = -2
    elif len(values) == 2:
        idx = -1
    else:
        return None
    return values[idx] if abs(idx) <= len(values) else None


def _select_last(values):
    """Primes émises (Annexes Fonds Familial/Général) : le Total Brut est
    toujours la DERNIÈRE colonne de la ligne, quel que soit le format
    ancien/nouveau (vérifié 2026-08-11 sur AL_AMANAH_TAKAFUL_2017 ET
    2020-2022/2024) - ce tableau n'a jamais eu de scission Fonds/Entreprise,
    contrairement au Bilan."""
    return values[-1] if values else None


def _search_realtext(pdf, label_variants, selector, max_pages, min_score=75, exclude_substrings=None,
                      min_label_len_ratio=None):
    for page in pdf.pages[:max_pages]:
        lines = page_lines_if_real_text(page)
        if lines is None:
            continue
        line = find_label_row_words(lines, label_variants, min_score, exclude_substrings, min_label_len_ratio)
        if line is None:
            continue
        values = [c[0] for c in _extract_numeric_clusters(line) if _is_plausible(c[0])]
        if not values:
            continue
        value = selector(values)
        if value is not None:
            return value
    return None


# Régions relatives (fraction de largeur de page) plutôt que des pixels
# fixes : les libellés arabes de ce gabarit de rapport se trouvent toujours
# dans le dernier ~40% (droite) de la page, les valeurs numériques dans les
# ~58% suivants en partant de la gauche (une marge est laissée de chaque
# côté) - vérifié cohérent sur les rendus 2018/2023/2024/2025 malgré de
# petites variations de largeur de page entre exercices.
_OCR_LABEL_REGION_FRAC = 0.6
_OCR_ROW_X_FRAC = (0.04, 0.62)


def _search_ocr(pdf, label_variants, selector, max_pages, min_row_score=60, exclude_substrings=None,
                 min_label_len_ratio=None):
    for page in pdf.pages[:max_pages]:
        image = render_page(page)
        w, h = image.size
        label_region = (int(w * _OCR_LABEL_REGION_FRAC), 0, w, h)
        row_x_range = (int(w * _OCR_ROW_X_FRAC[0]), int(w * _OCR_ROW_X_FRAC[1]))
        y_range = find_label_row(image, label_variants, region=label_region, min_score=min_row_score,
                                  exclude_substrings=exclude_substrings, min_label_len_ratio=min_label_len_ratio)
        if y_range is None:
            continue
        values = [v for v in ocr_row_numbers(image, y_range, row_x_range) if v is not None and _is_plausible(v)]
        if not values:
            continue
        value = selector(values)
        if value is not None:
            return value
    return None


def find_kpi_value_smart(pdf, label_variants, selector, max_pages=10, min_score=75, min_row_score=60,
                          exclude_substrings=None, min_label_len_ratio=None):
    """Comme find_kpi_value, mais avec un sélecteur de colonne sensible au
    format (voir _select_actif_like / _select_equity_like) au lieu d'un
    index fixe."""
    value = _search_realtext(pdf, label_variants, selector, max_pages, min_score, exclude_substrings,
                              min_label_len_ratio=min_label_len_ratio)
    if value is not None:
        return value
    return _search_ocr(pdf, label_variants, selector, max_pages, min_row_score, exclude_substrings,
                        min_label_len_ratio=min_label_len_ratio)


def find_kpi_value_smart_sum(pdf, label_variants, selector, max_pages=10, min_score=90, min_row_score=75):
    total = None
    for page in pdf.pages[:max_pages]:
        lines = page_lines_if_real_text(page)
        if lines is None:
            continue
        line = find_label_row_words(lines, label_variants, min_score)
        if line is None:
            continue
        values = [c[0] for c in _extract_numeric_clusters(line) if _is_plausible(c[0])]
        if not values:
            continue
        value = selector(values)
        if value is not None:
            total = (total or 0) + value
    if total is not None:
        return total
    for page in pdf.pages[:max_pages]:
        image = render_page(page)
        w, h = image.size
        label_region = (int(w * _OCR_LABEL_REGION_FRAC), 0, w, h)
        row_x_range = (int(w * _OCR_ROW_X_FRAC[0]), int(w * _OCR_ROW_X_FRAC[1]))
        y_range = find_label_row(image, label_variants, region=label_region, min_score=min_row_score)
        if y_range is None:
            continue
        values = [v for v in ocr_row_numbers(image, y_range, row_x_range) if v is not None and _is_plausible(v)]
        if not values:
            continue
        value = selector(values)
        if value is not None:
            total = (total or 0) + value
    return total


def find_kpi_value_smart_list(pdf, label_variants, selector, max_pages=10, min_score=90, min_row_score=75,
                               min_label_len_ratio=None):
    """Comme find_kpi_value_smart_sum, mais renvoie la liste ORDONNÉE des
    valeurs trouvées (une par page correspondante, dans l'ordre du document)
    au lieu de leur somme - utilisé pour distinguer Famille (1ère occurrence,
    toujours avant le Fonds Général dans ces rapports) et Général (2e) plutôt
    que de n'en garder que le total, déjà disponible via find_kpi_value_smart_sum."""
    results = []
    for page in pdf.pages[:max_pages]:
        lines = page_lines_if_real_text(page)
        if lines is None:
            continue
        line = find_label_row_words(lines, label_variants, min_score, min_label_len_ratio=min_label_len_ratio)
        if line is None:
            continue
        values = [c[0] for c in _extract_numeric_clusters(line) if _is_plausible(c[0])]
        if not values:
            continue
        value = selector(values)
        if value is not None:
            results.append(value)
    if results:
        return results
    for page in pdf.pages[:max_pages]:
        image = render_page(page)
        w, h = image.size
        label_region = (int(w * _OCR_LABEL_REGION_FRAC), 0, w, h)
        row_x_range = (int(w * _OCR_ROW_X_FRAC[0]), int(w * _OCR_ROW_X_FRAC[1]))
        y_range = find_label_row(image, label_variants, region=label_region, min_score=min_row_score,
                                  min_label_len_ratio=min_label_len_ratio)
        if y_range is None:
            continue
        values = [v for v in ocr_row_numbers(image, y_range, row_x_range) if v is not None and _is_plausible(v)]
        if not values:
            continue
        value = selector(values)
        if value is not None:
            results.append(value)
    return results


def find_kpi_row_all_values(pdf, label_variants, max_pages=10, min_score=90, min_row_score=75,
                             exclude_substrings=None, ocr_x_frac=None, start_page=0, validator=None):
    """Comme find_kpi_value_smart, mais renvoie la liste COMPLÈTE des valeurs
    plausibles de la première page correspondante (pas une seule colonne
    sélectionnée) - nécessaire pour la ventilation par branche (Annexe 15),
    où chaque colonne est une branche différente identifiée par POSITION.
    Contrairement à find_kpi_value_smart_sum/_list, un seul match suffit (la
    ventilation par branche n'existe que sur UNE page, le Fonds Général —
    voir DVRB, pas de pendant côté Fonds Familial).

    `exclude_substrings` : le libellé de cette ligne (« أقساط تأمين صادرة »,
    Annexe 15) est un PRÉFIXE du libellé « أقساط تأمين صادرة و مقبولة »
    (Annexes 3/4, Primes émises ET ACCEPTÉES) - un score de similarité assez
    élevé pourrait matcher à tort la page Annexes 3/4 (rencontrée en premier
    dans le document) si elle est balayée avant l'Annexe 15.

    `ocr_x_frac` : remplace _OCR_ROW_X_FRAC (calibré sur les tableaux à 4-5
    colonnes du Bilan/Annexes 3/4) - nécessaire pour l'Annexe 15 (9 colonnes
    serrées) où la borne haute par défaut (0.62) tronque la dernière colonne
    (Automobile, la plus à droite) avant que l'OCR ne puisse la lire.
    Confirmé 2026-08-15 sur AL_AMANAH_TAKAFUL_2019 : la colonne Automobile
    (18 431 657, ~70% du total) manque entièrement à 0.62 mais apparaît dès
    0.70, et la somme des 9 valeurs retombe alors exactement sur le Total.

    `start_page` : ignore les pages avant cet index - utile pour écarter des
    pages antérieures (Bilan, Résultat...) où un score de similarité assez
    bas (nécessaire pour ce libellé précis) peut accrocher un faux positif
    SANS rapport avec le tableau visé.

    `validator(values) -> bool` : si fourni, une page dont les valeurs ne
    passent pas ce contrôle est ignorée et la recherche CONTINUE sur les
    pages suivantes plutôt que de s'arrêter là - indispensable ici : sans
    lui, un faux positif rencontré tôt (ex: page 1, score flou juste
    au-dessus du seuil) fait `return` immédiatement et empêche à tort
    d'atteindre la vraie page plus loin dans le document (constaté
    2026-08-15 sur AL_AMANAH_TAKAFUL_2019 : page 1 matchée avant la page 38,
    la vraie ligne jamais atteinte sans ce garde-fou)."""
    for page in pdf.pages[start_page:max_pages]:
        lines = page_lines_if_real_text(page)
        if lines is None:
            continue
        line = find_label_row_words(lines, label_variants, min_score, exclude_substrings)
        if line is None:
            continue
        values = [c[0] for c in _extract_numeric_clusters(line) if _is_plausible(c[0])]
        if values and (validator is None or validator(values)):
            return values
    x_frac = ocr_x_frac or _OCR_ROW_X_FRAC
    for page in pdf.pages[start_page:max_pages]:
        image = render_page(page)
        w, h = image.size
        label_region = (int(w * _OCR_LABEL_REGION_FRAC), 0, w, h)
        row_x_range = (int(w * x_frac[0]), int(w * x_frac[1]))
        y_range = find_label_row(image, label_variants, region=label_region, min_score=min_row_score,
                                  exclude_substrings=exclude_substrings)
        if y_range is None:
            continue
        values = [v for v in ocr_row_numbers(image, y_range, row_x_range) if v is not None and _is_plausible(v)]
        if values and (validator is None or validator(values)):
            return values
    return None


def find_row_by_value_scan(pdf, target_total, max_pages=45, start_page=0, tolerance=0.005,
                            ocr_x_frac=None, y_step=10, row_height=30):
    """Repli quand AUCUN score de similarité de libellé ne suffit à localiser
    la ligne (constaté 2026-08-16 sur AL_AMANAH_TAKAFUL_2024, page 32/Annexe
    15 : l'OCR lit les CHIFFRES de cette page correctement mais rend le
    LIBELLÉ arabe en charabia total - `أقساط تأمين صادرة` OCRisé donne
    `B pala Cypalt bls`, score de similarité 0 quel que soit le seuil).

    Balaie la page verticalement par pas de `y_step` px (fenêtre `row_height`)
    et renvoie la PREMIÈRE liste de valeurs dont la valeur totale (1ère
    colonne, convention Annexe 14/15 - voir extraction/takaful_kpi_extractor.py)
    est proche de `target_total` à `tolerance` près. `target_total` doit
    provenir d'une extraction DÉJÀ VALIDÉE indépendamment (ici : "Primes
    émises Général (TND)", trouvée via l'Annexe 3/4 - table différente, donc
    non sujette à la même dégradation OCR) - garde-fou nécessaire car
    PLUSIEURS lignes de cette table (Primes émises, Primes acquises, Charges)
    valident toutes leur propre cohérence interne (Total = somme des
    branches, par construction du tableau), donc un simple contrôle de
    somme ne suffit PAS à distinguer laquelle est la bonne."""
    if not target_total:
        return None
    x_frac = ocr_x_frac or _OCR_ROW_X_FRAC
    for page in pdf.pages[start_page:max_pages]:
        image = render_page(page)
        w, h = image.size
        row_x_range = (int(w * x_frac[0]), int(w * x_frac[1]))
        for y_top in range(0, h - row_height, y_step):
            values = ocr_row_numbers(image, (y_top, y_top + row_height), row_x_range)
            values = [v for v in values if v is not None and _is_plausible(v)]
            if len(values) < 4:
                continue
            if abs(values[0] - target_total) / target_total <= tolerance:
                return values
    return None
