"""Extraction PLEINE GRILLE de l'Annexe 5.1 Takaful "État de résultat de
l'entreprise d'assurance Takaful et/ou Rétakaful" — le compte de résultat
de l'OPÉRATEUR (Commissions Wakala/Moudharaba, charges générales,
résultat net), par opposition aux Annexes 3/4 qui portent sur les FONDS.
Source du KPI narrow existant "Commission Wakala"/"Commission Moudharaba"
(voir extraction/takaful_kpi_extractor.py::extract_fonds_participants_kpis).
Stockée dans `tableau_cellules` sous 'takaful_resultat_entreprise'.

Structure BEAUCOUP plus simple que les Annexes 3/4 : SEULEMENT 2 colonnes
(exercice courant / exercice précédent, pas de distinction Brut/Cessions),
donc aucune ambiguïté de correspondance colonne à gérer.

Chaque ligne porte un code réglementaire PR<n>/CH<n> (avec le même piège
"Sous total N" qu'Annexes 3/4 — le numéro qui suit immédiatement "total"
n'est PAS une valeur ; voir `takaful_surplus_full_extractor.py` pour le
détail du bug que ceci évite. Ici certains sous-totaux portent un suffixe
lettré, "Sous total 1a", qui n'est PAS un token numérique isolé — le piège
ne se produit donc QUE sur les sous-totaux à numéro bare comme "Sous total
1"/"Sous total 2", mais on applique le même garde-fou uniformément par
simplicité et cohérence).

Contrairement aux Annexes 3/4, les lignes de RÉSULTAT INTERMÉDIAIRE les
plus importantes ("Produit net sur activités de gestion des fonds
Takaful", "Résultat d'exploitation avant/après impôt", "Résultat
extraordinaire", "Résultat net de l'exercice" [+ variante "...après
modifications comptables"]) n'ont AUCUN code réglementaire ni préfixe
"Sous total" — ce sont de simples lignes de libellé. Plutôt que de lister
ces phrases une à une (fragile, et incomplet dès qu'un document reformule
légèrement), toute ligne SANS code reconnu mais PORTANT des valeurs
numériques plausibles est capturée telle quelle, avec son texte normalisé
comme clé — capture générique, pas de liste figée de libellés."""

import re

from extraction.bilan_kpi_extractor import (
    _cluster_lines, _extract_numeric_clusters, _normalizer,
    _words_with_bracket_negatives_resolved, NUMERIC_TOKEN_RE,
    _OcrFallbackPage,
)

_ROW_CODE_RE = re.compile(r"^(PR|CH)\s?(\d+)(?:,\d+)*", re.IGNORECASE)
_SOUS_TOTAL_RE = re.compile(r"^sous\s*total\b")
_SECTION_NUM_RE = re.compile(r"^\d{1,2}$")
_DASH_PLACEHOLDER_RE = re.compile(r"^[-‐‑–—]+$")
_TITLE_RE = re.compile(r"etat de resultat de l.?entreprise")
_HEADER_LINE_RE = re.compile(r"^rubrique\b")

_COLUMN_NAMES = ["Exercice courant", "Exercice précédent"]
_MIN_ROWS = 5


def _is_target_page(page, lines_checked=6):
    text = (page.extract_text() or "").strip()
    if not text:
        return False
    normalized = _normalizer.clean(" ".join(text.split("\n")[:lines_checked]))
    return bool(_TITLE_RE.search(normalized))


def _resolved_words(line):
    resolved = _words_with_bracket_negatives_resolved(line)
    return [{**w, "text": "0"} if _DASH_PLACEHOLDER_RE.match(w["text"]) else w for w in resolved]


def _strip_leading_section_number(resolved, text_norm):
    """Même correctif que `takaful_surplus_full_extractor.py` pour "Sous
    total N ..." : le numéro de section bare (1-2 chiffres) juste après
    "total" n'est pas une valeur — le retirer avant tout calcul de
    cluster. Un suffixe lettré ("1a") n'est pas concerné (déjà exclu des
    tokens numériques par NUMERIC_TOKEN_RE, donc déjà traité comme
    libellé)."""
    tokens = text_norm.split()
    if len(tokens) < 3 or tokens[0] != "sous" or tokens[1] != "total" or not _SECTION_NUM_RE.match(tokens[2]):
        return resolved, None
    num = tokens[2]
    seen = False
    out = []
    for w in resolved:
        if not seen and _normalizer.clean(w["text"]) == num and NUMERIC_TOKEN_RE.match(w["text"]):
            seen = True
            continue
        out.append(w)
    return out, num


def _assign_columns(clusters):
    """2 colonnes seulement : la dernière valeur présente = exercice
    précédent, l'avant-dernière (ou l'unique, si une seule) = exercice
    courant — même convention que `_col_nettes_courantes`."""
    result = {}
    n = len(clusters)
    if n == 0:
        return result
    if n == 1:
        result[0] = clusters[0][0]
        return result
    result[0] = clusters[-2][0]
    result[1] = clusters[-1][0]
    return result


def extract_takaful_resultat_grid(page, min_rows=_MIN_ROWS):
    """Reconstruit la grille complète de l'Annexe 5.1 visible sur `page`.
    Renvoie {"colonnes": [...], "lignes": {...}}, ou None si trop peu de
    lignes reconnues."""
    words = page.extract_words()
    if not words:
        return None
    lines = _cluster_lines(words)

    prepared = []
    for line in lines:
        resolved = _resolved_words(line)
        label_words0 = [w for w in resolved if not NUMERIC_TOKEN_RE.match(w["text"])]
        text_norm = _normalizer.clean(" ".join(w["text"] for w in label_words0))
        resolved, sous_total_num = _strip_leading_section_number(resolved, text_norm)
        clusters = _extract_numeric_clusters(resolved)
        prepared.append({"text_norm": text_norm, "clusters": clusters, "sous_total_num": sous_total_num})

    lignes, label_by_key = {}, {}
    sous_total_seq = 0
    seen_keys = set()
    for p in prepared:
        text_norm = p["text_norm"]
        if not text_norm or not p["clusters"] or _HEADER_LINE_RE.match(text_norm):
            # Ligne d'en-tête "RUBRIQUE Notes 2023 2022" : les millésimes
            # ressemblent à des valeurs plausibles (4 chiffres) et se
            # feraient sinon capturer comme une fausse ligne de données.
            continue

        m = _ROW_CODE_RE.match(text_norm)
        sous_total_m = _SOUS_TOTAL_RE.match(text_norm)

        if text_norm.startswith("ch9") or text_norm.startswith("pr7"):
            # "CH9/PR7 Effet des modifications comptables" — combiné,
            # jamais confondu avec une autre ligne (préfixe propre).
            key = "CH9_PR7"
            label_by_key[key] = text_norm
            lignes[key] = _assign_columns(p["clusters"])
        elif m:
            code = f"{m.group(1).upper()}{m.group(2)}"
            rest = text_norm[m.end():].strip()
            if rest and code not in label_by_key:
                label_by_key[code] = rest
            lignes[code] = _assign_columns(p["clusters"])
        elif sous_total_m:
            sous_total_seq += 1
            num = p["sous_total_num"] or str(sous_total_seq)
            key = f"SOUS_TOTAL_{num}"
            label_by_key[key] = text_norm
            lignes[key] = _assign_columns(p["clusters"])
        else:
            # Ligne de résultat intermédiaire sans code (ex: "Résultat net
            # de l'exercice") : capture générique par son texte normalisé,
            # dédupliquée si répétée mot pour mot.
            key = text_norm
            n = 2
            while key in seen_keys:
                key = f"{text_norm} ({n})"
                n += 1
            seen_keys.add(key)
            label_by_key[key] = text_norm
            lignes[key] = _assign_columns(p["clusters"])

    if len(lignes) < min_rows:
        return None
    colonnes = _COLUMN_NAMES
    lignes_out = {
        key: {"libelle": label_by_key.get(key, key), **{
            colonnes[i]: v for i, v in vals.items() if i < len(colonnes)
        }}
        for key, vals in lignes.items()
    }
    return {"colonnes": colonnes, "lignes": lignes_out}


def locate_and_extract_takaful_resultat(pdf_path, max_pages=20):
    """Parcourt les premières pages de `pdf_path` à la recherche de
    l'Annexe 5.1 et en extrait la grille complète. Enveloppe chaque page
    avec `_OcrFallbackPage` (repli OCR si le texte natif est vide). Renvoie
    (numero_page_1_indexe, grille) ou (None, None)."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            ocr_page = _OcrFallbackPage(page)
            if not _is_target_page(ocr_page):
                continue
            grid = extract_takaful_resultat_grid(ocr_page)
            if grid is not None:
                return i + 1, grid
    return None, None


def process_takaful_resultat(pdf_path):
    """Pipeline complète pour un document : localise + extrait, renvoie
    {"page", "colonnes", "lignes", "validations"} au même contrat que les
    autres pipelines `process_*`, ou None si introuvable. Validation :
    Produit net = Sous total 1 + Sous total 2 (charges des placements),
    puis chaîne Résultat d'exploitation avant impôt -> après impôt ->
    Résultat net (via CH7/CH9-PR7) — vérifiée quand les 2 lignes existent,
    silencieusement ignorée sinon (ex: gabarits qui omettent une étape
    intermédiaire)."""
    page, grid = locate_and_extract_takaful_resultat(pdf_path)
    if grid is None:
        return None
    lignes = grid["lignes"]
    validations = []

    def _add(rule_code, rule_desc, colonne, attendu, trouve):
        if attendu is None or trouve is None:
            return
        ecart = round(trouve - attendu, 2)
        validations.append({"regle_code": rule_code, "regle": rule_desc, "colonne": colonne,
                             "attendu": round(attendu, 2), "trouve": round(trouve, 2),
                             "ecart": ecart, "statut": "ok" if abs(ecart) <= 2 else "ecart"})

    def _find_by_prefix(prefix):
        for key, vals in lignes.items():
            if _normalizer.clean(vals.get("libelle", key)).startswith(prefix):
                return vals
        return None

    resultat_avant_impot = _find_by_prefix("resultat d exploitation avant impot")
    resultat_apres_impot = _find_by_prefix("resultat d exploitation apres impot")
    ch7 = lignes.get("CH7")
    resultat_net = _find_by_prefix("resultat net de l exercice") if not _find_by_prefix(
        "resultat net de l exercice apres") else _find_by_prefix("resultat net de l exercice")
    resultat_extraordinaire = _find_by_prefix("resultat extraordinaire")
    resultat_net_apres_modif = _find_by_prefix("resultat net de l exercice apres modifications")

    if resultat_avant_impot and resultat_apres_impot and ch7:
        for col in grid["colonnes"]:
            attendu = resultat_avant_impot.get(col, 0) + ch7.get(col, 0)
            _add("takaful_resultat_impot", "Résultat d'exploitation avant impôt + CH7 = après impôt",
                 col, attendu, resultat_apres_impot.get(col))

    if resultat_apres_impot and resultat_net and resultat_extraordinaire:
        for col in grid["colonnes"]:
            attendu = resultat_apres_impot.get(col, 0) + resultat_extraordinaire.get(col, 0)
            _add("takaful_resultat_net", "Résultat après impôt + Résultat extraordinaire = Résultat net",
                 col, attendu, resultat_net.get(col))

    if resultat_net and resultat_net_apres_modif:
        ch9 = lignes.get("CH9_PR7", {})
        for col in grid["colonnes"]:
            attendu = resultat_net.get(col, 0) + ch9.get(col, 0)
            _add("takaful_resultat_modif_comptable", "Résultat net + Effet modifications comptables = Résultat net après modification",
                 col, attendu, resultat_net_apres_modif.get(col))

    lignes_final = {}
    for code, vals in lignes.items():
        libelle = vals.get("libelle") or code
        key = f"{code} — {libelle.capitalize()}" if libelle != code else code
        lignes_final[key] = {c: v for c, v in vals.items() if c != "libelle"}
    return {"page": page, "colonnes": grid["colonnes"], "lignes": lignes_final, "validations": validations}
