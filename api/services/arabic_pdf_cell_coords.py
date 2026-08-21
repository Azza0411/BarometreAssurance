"""
Localisation de page + cellule dans les PDF Takaful en ARABE
(AL_AMANAH_TAKAFUL uniquement — les 2 autres Takaful, AT_TAKAFULIA et
ZITOUNA_TAKAFUL, publient en français et passent déjà par
pdf_sections.py/pdf_cell_coords.py comme n'importe quelle société CMF)
pour "Localiser dans le PDF" côté KpiDetail.jsx — même esprit que
pdf_cell_coords.py (CMF, français) et sector_pdf_cell_coords.py
(FTUSA/CGA), mais réutilise la recherche floue RTL déjà validée par
extraction/arabic_ocr_extractor.py / extraction/takaful_kpi_extractor.py
plutôt que de la refaire depuis zéro. Ajouté le 2026-08-19, étape 3 du
plan explicite de l'utilisateur ("documents Takaful arabe").

Portée volontairement limitée aux 4 KPI "primaires" affichés directement
dans KpiDetail (Total actif, Capitaux propres, Résultat Net, Primes
émises par assurance) — PAS la ventilation par branche (Annexe 14/15),
dont la logique d'extraction (validateur de cohérence + repli par
balayage positionnel) est bien plus complexe et n'est jamais consultée
comme une cellule isolée dans l'UI actuelle.

Surlignage de cellule (bbox) : seulement sur les pages à TEXTE RÉEL (2017,
2019-2022 vérifié) — coordonnées natives pdfplumber directement fiables,
même repère que le reste de l'app. Sur les pages SCANNÉES (2018,
2023-2025), seule la PAGE est déterminée (déjà une vraie amélioration :
badge "Page X" + ouverture directe) — un surlignage pixel-exact
nécessiterait une conversion résolution-image → points PDF non
vérifiable visuellement dans cet environnement de développement, donc
non tenté plutôt que de risquer un encadré mal positionné.

Garde-fou supplémentaire pour le surlignage (texte réel) : la valeur
numérique lue dans la cellule candidate est comparée à la valeur DÉJÀ
extraite et persistée en base pour ce (KPI, année) — élaborée
indépendamment par extraction/takaful_kpi_extractor.py, avec toute sa
logique de nettoyage/validation propre. Une cellule dont la valeur ne
correspond pas n'est PAS surlignée (mieux vaut aucun encadré qu'un
encadré au mauvais endroit) : cette reconstruction simplifiée du
regroupement de tokens numériques (voir _numeric_clusters_with_bbox)
n'a besoin que de repérer une position à l'écran, pas de reproduire
fidèlement tous les cas particuliers (négatifs entre chevrons, nombres
tunisiens collés...) déjà gérés par le vrai pipeline d'extraction.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pdfplumber
import pytesseract

from extraction.bilan_kpi_extractor import NUMBER_GAP_THRESHOLD, NUMERIC_TOKEN_RE, _is_plausible, _parse_number
from extraction.arabic_ocr_extractor import (
    page_lines_if_real_text, find_label_row_words, find_label_row,
    render_page, ocr_row_numbers, _OCR_LABEL_REGION_FRAC, _OCR_ROW_X_FRAC,
    _select_actif_like, _select_equity_like, _select_last,
    _ROW_DIGITS_CONFIG, _DIGIT_GROUP_MERGE_GAP,
)
from extraction.takaful_kpi_extractor import (
    _AR_TOTAL_ACTIF, _AR_CAPITAUX_AFFECTATION, _AR_CAPITAUX, _AR_RESULTAT_NET, _AR_PRIMES,
    _AR_CHARGES_PRESTATIONS, _AR_CHARGES_ACQUISITION_GESTION,
    _EXCLUDE_ACTIF, _EXCLUDE_CAPITAUX, AL_AMANAH_MAX_PAGES,
)
from database.repository import get_document_id, get_kpi_values_for_document

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cmf",
)

COMPANY_CODE = "AL_AMANAH_TAKAFUL"


def _actif_index(n):
    if n >= 5:
        return -2
    if n == 4:
        return -3
    return None


def _equity_index(n):
    if n >= 3:
        return -2
    if n == 2:
        return -1
    return None


def _last_index(n):
    return -1 if n >= 1 else None


# storageKey -> groupes de libellés à essayer DANS L'ORDRE (comme le fait
# extract_al_amanah_takaful_kpis lui-même — ex: Capitaux propres essaie
# d'abord la variante "avant répartition" avant la variante simple),
# exclusions, sélecteur de colonne "depuis la droite" selon le nombre de
# valeurs trouvées sur la ligne (même conventions que arabic_ocr_extractor
# ._select_actif_like / ._select_equity_like — reprises ici pour ne pas
# dépendre de leur signature interne, qui opère sur les VALEURS, alors
# qu'ici on n'a besoin que du COMPTE pour choisir le bon index).
_KPI_CONFIG = {
    "Total actif": {
        "label_groups": [_AR_TOTAL_ACTIF],
        "exclude": _EXCLUDE_ACTIF,
        "select_index": _actif_index,
        "select_value": _select_actif_like,
    },
    "Capitaux propres": {
        "label_groups": [_AR_CAPITAUX_AFFECTATION, _AR_CAPITAUX],
        "exclude": _EXCLUDE_CAPITAUX,
        "select_index": _equity_index,
        "select_value": _select_equity_like,
    },
    "Résultat Net": {
        "label_groups": [_AR_RESULTAT_NET],
        "exclude": None,
        "select_index": _equity_index,
        "select_value": _select_equity_like,
    },
    "Primes émises par assurance": {
        "label_groups": [_AR_PRIMES],
        "exclude": None,
        "select_index": _last_index,
        "select_value": _select_last,
    },
    # Composantes réelles de "Ratio combiné (%)"/"Ratio de frais de gestion
    # (%)" côté Takaful (voir calculated_kpi_extractor.py — repli Takaful :
    # ces 2 clés BRUTES, pas de ventilation Vie/Non-Vie) — ajoutées le
    # 2026-08-19 pour que "Localiser dans le PDF" fonctionne aussi en
    # décomposant ces ratios, pas seulement les 4 KPI "primaires". Comme
    # "Primes émises par assurance", ce sont des sommes Familial+Général
    # (Annexes 14/15, voir extract_al_amanah_takaful_kpis) : jamais
    # surlignables cellule par cellule, page repérée avec le même repli
    # OCR/vérification que le reste du module.
    "Charges de prestations": {
        "label_groups": [_AR_CHARGES_PRESTATIONS],
        "exclude": None,
        "select_index": _last_index,
        "select_value": _select_last,
    },
    "Charges d'acquisition et de gestion nettes": {
        "label_groups": [_AR_CHARGES_ACQUISITION_GESTION],
        "exclude": None,
        "select_index": _last_index,
        "select_value": _select_last,
    },
}

# Pages où chercher chaque KPI — les 4 primaires (Bilan/État de résultat)
# apparaissent tôt (AL_AMANAH_MAX_PAGES), mais "Primes émises par
# assurance" (Annexes 3/4) et les 2 KPI de charges ci-dessus (Annexes
# 14/15, bien plus loin dans le document — vérifié jusqu'à la page 38-39
# selon l'exercice, voir extract_al_amanah_takaful_kpis) ont besoin d'un
# plafond de pages beaucoup plus large.
_EXTENDED_SCAN_KPIS = {
    "Primes émises par assurance": 20,
    "Charges de prestations": 45,
    "Charges d'acquisition et de gestion nettes": 45,
}

# Cache PERSISTÉ SUR DISQUE (pas seulement en mémoire process) : contrairement
# à pdf_cell_coords.py/sector_pdf_cell_coords.py (recherche en texte réel,
# quasi instantanée), le repli OCR ici peut prendre plusieurs dizaines de
# secondes par (KPI, année) sur les exercices scannés (rendu 300dpi + lecture
# Tesseract, page par page) — inacceptable à recalculer à chaque clic
# "Localiser dans le PDF" d'un utilisateur, ni même à chaque redémarrage du
# serveur Flask (cache mémoire vidé). Une fois calculé, le résultat ne varie
# jamais (mêmes PDF sources, immuables) : persisté en JSON à côté des PDF de
# la société, écrit une seule fois par (année, KPI) puis relu instantanément
# ensuite. Ajouté le 2026-08-19 après un premier passage synchrone qui
# dépassait largement un temps de réponse HTTP acceptable.
_CACHE_FILE = os.path.join(DATA_DIR, COMPANY_CODE, ".arabic_cell_cache.json")


def _load_disk_cache() -> dict:
    if not os.path.isfile(_CACHE_FILE):
        return {}
    try:
        with open(_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_disk_cache() -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


_cache: dict = _load_disk_cache()


def _numeric_clusters_with_bbox(line):
    """Reconstruction SIMPLIFIÉE de extraction.bilan_kpi_extractor.
    _extract_numeric_clusters, qui renvoie la bbox de chaque groupe (pas
    seulement x0) — nécessaire pour le surlignage. Volontairement plus
    sommaire (pas de résolution des négatifs entre chevrons/parenthèses ni
    des nombres tunisiens collés) : le garde-fou de cross-vérification
    contre la base (voir get_arabic_cell_coords) rattrape les cas où cette
    reconstruction diverge du vrai pipeline d'extraction, en refusant
    simplement le surlignage plutôt que d'en proposer un incorrect."""
    numeric_words = sorted((w for w in line if NUMERIC_TOKEN_RE.match(w["text"])), key=lambda w: w["x0"])
    clusters, current, prev_x1 = [], [], None
    for w in numeric_words:
        if prev_x1 is not None and (w["x0"] - prev_x1) >= NUMBER_GAP_THRESHOLD:
            clusters.append(current)
            current = []
        current.append(w)
        prev_x1 = w["x1"]
    if current:
        clusters.append(current)

    out = []
    for tokens in clusters:
        text = "".join(t["text"] for t in tokens)
        negative = text.startswith("-")
        value = _parse_number(text.lstrip("-"), negative=negative)
        if value is None or not _is_plausible(value):
            continue
        out.append({
            "value": value,
            "x0": min(t["x0"] for t in tokens), "x1": max(t["x1"] for t in tokens),
            "top": min(t["top"] for t in tokens), "bottom": max(t["bottom"] for t in tokens),
        })
    return out


def _match_real_text(lines, config, min_score=75):
    for label_group in config["label_groups"]:
        line = find_label_row_words(lines, label_group, min_score=min_score, exclude_substrings=config["exclude"])
        if line is not None:
            break
    else:
        return None
    clusters = _numeric_clusters_with_bbox(line)
    idx = config["select_index"](len(clusters))
    if idx is None or abs(idx) > len(clusters):
        return None
    return clusters[idx]


def _values_close(a, b, tol=0.005):
    if a is None or b is None:
        return False
    if a == b == 0:
        return True
    return abs(a - b) / max(abs(a), abs(b), 1) <= tol


def _ocr_row_numbers_with_bbox(image, y_range, x_range, pad_y=4):
    """Variante de arabic_ocr_extractor.ocr_row_numbers qui conserve, pour
    chaque nombre détecté, sa bbox en coordonnées PLEINE IMAGE (pixels, même
    résolution que render_page) plutôt que seulement sa valeur — nécessaire
    pour construire un encadré de surlignage sur les pages scannées.
    Même algorithme de regroupement (écart horizontal >= _DIGIT_GROUP_MERGE_GAP
    px = nouveau nombre, pas juste un séparateur de milliers) que l'original,
    pour rester cohérent avec les valeurs qu'il produit."""
    top, bottom = y_range
    left, right = x_range
    crop_top = max(0, top - pad_y)
    crop = image.crop((left, crop_top, right, bottom + pad_y))
    data = pytesseract.image_to_data(crop, config=_ROW_DIGITS_CONFIG, output_type=pytesseract.Output.DICT)
    tokens = []
    for i in range(len(data["text"])):
        t = data["text"][i].strip()
        if t and any(c.isdigit() for c in t):
            tokens.append((data["left"][i], data["left"][i] + data["width"][i],
                            data["top"][i], data["top"][i] + data["height"][i], t))
    tokens.sort(key=lambda tok: tok[0])

    groups, current, prev_right = [], [], None
    for tok in tokens:
        tok_left, tok_right = tok[0], tok[1]
        if prev_right is not None and (tok_left - prev_right) >= _DIGIT_GROUP_MERGE_GAP:
            groups.append(current)
            current = []
        current.append(tok)
        prev_right = tok_right
    if current:
        groups.append(current)

    out = []
    for g in groups:
        text = "".join(t[4] for t in g)
        try:
            value = float(text)
        except ValueError:
            value = None
        bbox = (
            min(t[0] for t in g) + left, min(t[2] for t in g) + crop_top,
            max(t[1] for t in g) + left, max(t[3] for t in g) + crop_top,
        )
        out.append((value, bbox))
    return out


def get_arabic_cell_coords(conn, annee: int, kpi_storage_key: str):
    """Renvoie (résultat, raison) — même contrat que pdf_cell_coords.
    get_cell_coords et sector_pdf_cell_coords.get_sector_cell_coords :
    résultat = {x0,y0,x1,y1,page_width,page_height,page} si surlignage
    possible ; sinon résultat=None + raison (avec `page` inclus dès qu'elle
    a pu être déterminée, même sans surlignage précis, pour que le
    frontend affiche au moins la bonne page)."""
    config = _KPI_CONFIG.get(kpi_storage_key)
    if config is None:
        return None, {"reason": "kpi_non_pris_en_charge", "page": None}

    path = os.path.join(DATA_DIR, COMPANY_CODE, f"{COMPANY_CODE}_{annee}.pdf")
    if not os.path.isfile(path):
        return None, {"reason": "pdf_manquant", "page": None}

    cache_key = f"{int(annee)}|{kpi_storage_key}"
    if cache_key in _cache:
        return tuple(_cache[cache_key])

    # Valeur de référence déjà extraite et persistée (voir garde-fou dans
    # la docstring du module) — absence de valeur en base n'empêche pas la
    # recherche de page (utile même sans confirmation de cellule), mais
    # empêche tout surlignage.
    reference_value = None
    doc_id = get_document_id(conn, COMPANY_CODE, annee)
    if doc_id:
        kpis = get_kpi_values_for_document(conn, doc_id)
        reference_value = kpis.get(kpi_storage_key)

    result, reason = None, {"reason": "ligne_introuvable", "page": None}
    try:
        with pdfplumber.open(path) as pdf:
            max_pages = _EXTENDED_SCAN_KPIS.get(kpi_storage_key, AL_AMANAH_MAX_PAGES)
            # Seuils de score alignés sur find_kpi_value_smart_sum (déjà
            # éprouvée par le vrai pipeline pour ces 3 KPI "smart sum") : le
            # repli "somme sur toutes les pages" additionne la valeur de
            # CHAQUE page qui matche, donc bien plus sensible à un faux
            # positif de libellé qu'une simple lecture page par page — un
            # seuil par défaut (75 texte réel / 60 OCR, pensé pour un match
            # unique) laissait passer un faux positif sur "Primes émises",
            # trop générique, qui faussait la somme (découvert le
            # 2026-08-20 : Primes émises régressait alors que Charges
            # d'acquisition, corrigée juste avant, fonctionnait).
            is_smart_sum = kpi_storage_key in _EXTENDED_SCAN_KPIS
            real_text_min_score = 90 if is_smart_sum else 75
            ocr_min_score = 75 if is_smart_sum else 60

            # Candidats (texte réel) pour un éventuel repli "somme sur 2
            # pages" ci-dessous — même besoin que côté OCR (voir plus bas) :
            # ces KPI "smart sum" (Familial+Général) n'ont jamais de page
            # unique égale à la référence, texte réel ou pas.
            real_text_candidates = []
            for i, page in enumerate(pdf.pages[:max_pages]):
                lines = page_lines_if_real_text(page)
                if lines is None:
                    continue
                match = _match_real_text(lines, config, min_score=real_text_min_score)
                if match is None:
                    continue
                page_w, page_h = float(page.width), float(page.height)
                real_text_candidates.append((i + 1, match["value"], match, page_w, page_h))
                if not isinstance(reference_value, (int, float)) or not _values_close(match["value"], reference_value):
                    # Ligne trouvée mais valeur non confirmée par la base —
                    # on continue de chercher une page mieux surlignable
                    # plutôt que de risquer un encadré au mauvais endroit,
                    # mais on retient au moins la page pour le repli.
                    reason = {"reason": "valeur_non_confirmee", "page": i + 1}
                    continue
                result = {
                    "x0": match["x0"], "x1": match["x1"],
                    "y0": page_h - match["bottom"], "y1": page_h - match["top"],
                    "page_width": page_w, "page_height": page_h,
                    "page": i + 1,
                }
                break

            if result is None and isinstance(reference_value, (int, float)) and len(real_text_candidates) >= 2:
                # Repli "somme de toutes les pages correspondantes" en texte
                # réel — voir la version OCR plus bas pour le contexte
                # complet (même principe, tenté ici EN PREMIER puisque le
                # texte réel donne des coordonnées pdfplumber natives, plus
                # fiables qu'une bbox reconstruite par OCR).
                #
                # Reproduit EXACTEMENT extraction/arabic_ocr_extractor.py::
                # find_kpi_value_smart_sum, déjà utilisée avec succès par le
                # vrai pipeline (extract_al_amanah_takaful_kpis) pour ces 3
                # KPI : somme TOUTES les valeurs SIGNÉES trouvées (pas juste
                # 2 — un 3e "faux positif" de libellé peut exister, ex.
                # AL_AMANAH_TAKAFUL 2024 page 34 pour "Charges d'acquisition"
                # : +2 110 768, un nombre de référence sans rapport, qui
                # s'annule presque exactement avec la vraie valeur Familial
                # dans la somme signée), PUIS abs() de la somme totale — PAS
                # abs() de chaque valeur individuellement avant de sommer
                # (les deux ne coïncident que si toutes les valeurs ont le
                # même signe, ce qui n'est pas garanti — découvert et corrigé
                # le 2026-08-20 après un premier essai abs-puis-somme qui
                # marchait sur "Charges de prestations" par coïncidence de
                # signe mais pas sur "Charges d'acquisition et de gestion
                # nettes", où le faux positif positif compense en signé).
                raw_sum = sum(v for _p, v, _m, _pw, _ph in real_text_candidates)
                if _values_close(abs(raw_sum), reference_value):
                    first_candidate = min(real_text_candidates, key=lambda c: c[0])
                    first_page, _v, first_match, first_pw, first_ph = first_candidate
                    other_pages = sorted({p for p, *_ in real_text_candidates if p != first_page})
                    result = {
                        "x0": first_match["x0"], "x1": first_match["x1"],
                        "y0": first_ph - first_match["bottom"], "y1": first_ph - first_match["top"],
                        "page_width": first_pw, "page_height": first_ph,
                        "page": first_page,
                        "note": (
                            f"Somme confirmée sur {len(real_text_candidates)} page(s) "
                            f"(Fonds Familial + Fonds Général) : cellule surlignée ici "
                            f"(page {first_page}) ; le reste de la somme se trouve "
                            f"page(s) {', '.join(str(p) for p in other_pages)}."
                        ),
                    }

            if result is None:
                # Repli OCR — page seule, pas de surlignage (voir note de
                # portée en tête de module). Tenté sur TOUTES les pages, pas
                # seulement celles détectées "scannées" (is_scanned_page) :
                # au moins un exercice (2022) a du texte réellement
                # extractible mais dont la police embarquée mappe certains
                # caractères vers le mauvais point de code Unicode (voir
                # arabic_ocr_extractor.py, tête de fichier) — is_scanned_page
                # ne détecte PAS ce cas (le nombre de caractères est normal,
                # seul leur contenu est faux), donc la vraie recherche
                # (extract_al_amanah_takaful_kpis) tente l'OCR sur TOUTES
                # les pages sans ce filtre — reproduit ici à l'identique
                # (bug réel constaté le 2026-08-19 : 2019/2022 ne
                # trouvaient rien tant que ce filtre restait).
                # Un match de LIBELLÉ seul ne suffit pas à retenir une page :
                # l'OCR peut accrocher un libellé visuellement proche sur une
                # ligne qui n'a rien à voir (ex. AL_AMANAH_TAKAFUL 2024 —
                # "نتيجة الفترة" dans le détail des fonds du Bilan matchait
                # à tort le libellé de "Résultat Net", donnant une page dont
                # aucune valeur ne correspondait aux 3,75 M TND réellement
                # extraits). On applique donc la MÊME vérification que le
                # vrai pipeline (_search_ocr dans arabic_ocr_extractor.py) :
                # lire les nombres de la ligne (ocr_row_numbers), appliquer
                # le sélecteur réel du KPI, et ne retenir la page que si une
                # valeur plausible en ressort — recroisée avec la valeur déjà
                # persistée en base quand elle est disponible (bug réel
                # constaté et corrigé le 2026-08-19).
                # Deux niveaux de repli si aucune page n'est pleinement
                # confirmée (valeur lue ET recroisée avec la base) : d'abord
                # une page où une valeur a bien été lue mais ne correspond
                # pas à la référence (fallback_reason), puis, à défaut, la
                # toute première page où seul le LIBELLÉ a matché sans
                # qu'aucun nombre n'ait pu être lu sur la ligne
                # (label_only_reason) — mieux vaut une page ouverte avec un
                # message franchement moins confiant que rien du tout ;
                # seule la confiance affichée change, jamais le surlignage
                # (qui reste refusé dans les 3 cas).
                labels_flat = [lbl for grp in config["label_groups"] for lbl in grp]
                fallback_reason = None
                label_only_reason = None
                # Candidats retenus pour un éventuel repli "somme sur 2
                # pages" (voir plus bas) : ces 3 KPI (voir
                # _EXTENDED_SCAN_KPIS) sont en réalité des sommes Fonds
                # Familial + Fonds Général, extraites sur 2 pages DISTINCTES
                # par le vrai pipeline (find_kpi_value_smart_sum) — aucune
                # page seule n'égale donc jamais la valeur totale en base,
                # d'où "valeur_non_confirmee" systématique tant qu'on ne
                # teste qu'une page à la fois.
                sum_candidates = []
                for i, page in enumerate(pdf.pages[:max_pages]):
                    image = render_page(page)
                    w, h = image.size
                    label_region = (int(w * _OCR_LABEL_REGION_FRAC), 0, w, h)
                    y_range = find_label_row(image, labels_flat, region=label_region, min_score=ocr_min_score,
                                              exclude_substrings=config["exclude"])
                    if y_range is None:
                        continue
                    if label_only_reason is None:
                        label_only_reason = {"reason": "position_approximative", "page": i + 1}
                    row_x_range = (int(w * _OCR_ROW_X_FRAC[0]), int(w * _OCR_ROW_X_FRAC[1]))
                    # select_index (pas select_value) : opère sur (valeur,
                    # bbox) par POSITION, donnant accès à la bbox du nombre
                    # choisi — nécessaire pour surligner. Même sélecteur
                    # positionnel que celui déjà utilisé côté select_value
                    # (voir _actif_index/_equity_index/_last_index en tête de
                    # module, qui encodent la même règle que
                    # _select_actif_like/_select_equity_like/_select_last).
                    pairs = [(v, bbox) for v, bbox in _ocr_row_numbers_with_bbox(image, y_range, row_x_range)
                             if v is not None and _is_plausible(v)]
                    if not pairs:
                        continue
                    idx = config["select_index"](len(pairs))
                    if idx is None or abs(idx) > len(pairs):
                        continue
                    value, bbox = pairs[idx]
                    sum_candidates.append((i + 1, value, bbox, float(page.width), float(page.height)))
                    if isinstance(reference_value, (int, float)) and not _values_close(value, reference_value):
                        if fallback_reason is None:
                            fallback_reason = {"reason": "valeur_non_confirmee", "page": i + 1}
                        continue
                    # Valeur confirmée : surlignage réel désormais possible
                    # (conversion image 300dpi -> points PDF, 72/300 = 0.24 -
                    # même repère top-down que pdfplumber donc même flip Y que
                    # le chemin texte réel ci-dessus). Vérifié visuellement en
                    # navigateur avant activation (2026-08-19) plutôt que
                    # laissé "non surlignable" comme précédemment (limite
                    # documentée en tête de module, levée ici).
                    scale = 72.0 / 300.0
                    bl, bt, br, bb = bbox
                    page_w, page_h = float(page.width), float(page.height)
                    result = {
                        "x0": bl * scale, "x1": br * scale,
                        "y0": page_h - (bb * scale), "y1": page_h - (bt * scale),
                        "page_width": page_w, "page_height": page_h,
                        "page": i + 1,
                    }
                    break
                else:
                    reason = fallback_reason or label_only_reason or reason
                    # Repli "somme de toutes les pages correspondantes" —
                    # même principe que le repli texte réel ci-dessus
                    # (reproduit find_kpi_value_smart_sum : somme TOUTES les
                    # valeurs trouvées, pas juste 2, puis abs() de la somme
                    # totale — jamais abs() de chaque valeur individuellement,
                    # les deux ne coïncidant que par coïncidence de signe).
                    # L'OCR ne capture pas le signe "-" (whitelist chiffres
                    # seuls, voir _ROW_DIGITS_CONFIG) : les valeurs lues ici
                    # sont déjà positives, donc surtout utile pour écarter un
                    # éventuel faux positif de libellé dont la valeur ne
                    # cadre pas dans la somme totale.
                    if isinstance(reference_value, (int, float)) and len(sum_candidates) >= 2:
                        raw_sum = sum(v for _p, v, _bbox, _pw, _ph in sum_candidates)
                        if _values_close(abs(raw_sum), reference_value):
                            first_page, _v, first_bbox, first_pw, first_ph = min(sum_candidates, key=lambda c: c[0])
                            other_pages = sorted({p for p, *_ in sum_candidates if p != first_page})
                            scale = 72.0 / 300.0
                            bl, bt, br, bb = first_bbox
                            result = {
                                "x0": bl * scale, "x1": br * scale,
                                "y0": first_ph - (bb * scale), "y1": first_ph - (bt * scale),
                                "page_width": first_pw, "page_height": first_ph,
                                "page": first_page,
                                "note": (
                                    f"Somme confirmée sur {len(sum_candidates)} page(s) "
                                    f"(Fonds Familial + Fonds Général) : cellule surlignée ici "
                                    f"(page {first_page}) ; le reste de la somme se trouve "
                                    f"page(s) {', '.join(str(p) for p in other_pages)}."
                                ),
                            }
    except Exception as exc:
        reason = {"reason": "erreur", "page": None, "detail": str(exc)}

    out = (result, None) if result is not None else (None, reason)
    _cache[cache_key] = list(out)
    _save_disk_cache()
    return out
