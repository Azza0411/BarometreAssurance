"""
Extraction du cours de clôture par société depuis le "Bulletin Officiel de
la Cote" quotidien de la BVMT (tunis-stockexchange.com/editions-statistique,
archive remontant au moins à fin 2015).

Contrairement aux autres sources CMF (un document par société et par année),
un seul bulletin couvre TOUTES les sociétés cotées un jour donné -> comme
pour CGA (extraction/cga_kpi_extractor.py), un seul document par année
(cmf_id NULL) porte des KPI éclatés par société : "Cours de l'action -
{code}".

Colonnes du tableau "COTE DE LA BOURSE : MARCHE PRINCIPAL DES TITRES DE
CAPITAL" : COURS DE RÉFÉRENCE, OUVERTURE, CLÔTURE, PLUS HAUT, PLUS BAS (ordre
confirmé par la position x des en-têtes ; le texte à plat de pdfplumber
mélange l'ordre de lecture des colonnes, qui varie même d'une année à
l'autre). La colonne CLÔTURE est repérée par la position x0 de son en-tête
plutôt qu'un index fixe dans la ligne : le nombre de clusters numériques par
ligne varie (valeur peu liquide -> cellules Plus Haut/Plus Bas vides).

Reconnaissance de société en 2 passes, PAS par find_code_by_name (voir
CAS_PARTICULIERS_BVMT.md) :
  1. MNEMO exact (mot exact de la ligne == mnemo connu) : fiable, mais la
     colonne MNEMO n'existe que dans le format de bulletin récent (~2022+).
  2. Repli sur la "Dénomination sociale" complète (phrase exacte, la plus
     longue d'abord pour éviter qu'"ASSURANCES MAGHREBIA" ne matche à
     l'intérieur d'"ASSURANCES MAGHREBIA VIE") : nécessaire pour les
     bulletins plus anciens, sans colonne MNEMO.
Les deux passes sont nécessaires car plusieurs sociétés d'assurance
partagent un nom/sigle court avec une société non-assurance cotée
séparément (ex: "BH" = ticker ET premier mot du nom de BH BANK, alors que BH
ASSURANCE cote sous le mnemo "BHASS" mais s'appelle, en toutes lettres,
"BH ASSURANCE" — une simple recherche du mot "BH" matcherait la banque).

Voir extraction/CAS_PARTICULIERS_BVMT.md.
"""

import re

from extraction.bilan_kpi_extractor import NUMERIC_TOKEN_RE, _cluster_lines, _extract_numeric_clusters, _normalizer

MAX_PAGES_SCANNED = 15
CLOTURE_HEADER_RE = re.compile(r"^cl.tures?$")
# Tolérance autour de l'x0 de l'en-tête "CLÔTURE" pour rattacher un cluster de
# la ligne de données à cette colonne (les chiffres ne démarrent pas
# exactement au même x0 que le mot d'en-tête).
X0_TOLERANCE = 45


def _find_cloture_x0(lines):
    for line in lines:
        for word in line:
            if CLOTURE_HEADER_RE.match(_normalizer.clean(word["text"])):
                return word["x0"]
    return None


def _row_label_words(line):
    return [w["text"] for w in line if not NUMERIC_TOKEN_RE.match(w["text"])]


def _matched_code(label_words, mnemo_to_code, name_to_code_by_length):
    for word in label_words:
        code = mnemo_to_code.get(word)
        if code:
            return code
    normalized_label = _normalizer.clean(" ".join(label_words))
    for name, code in name_to_code_by_length:
        if name in normalized_label:
            return code
    return None


def extract_bulletin_cloture(pdf, mnemo_to_code, name_to_code):
    """Renvoie {code_cmf: cours_cloture}. `mnemo_to_code` : {mnemo: code},
    `name_to_code` : {denomination_sociale_normalisee: code} — une entrée par
    société cotée reconnue dans chacun des deux dictionnaires (voir
    scraping.bvmt_scraper pour leur construction)."""
    # Plus longue denomination en premier, pour qu'"assurances maghrebia vie"
    # soit teste avant "assurances maghrebia" (qui en est un prefixe).
    name_to_code_by_length = sorted(name_to_code.items(), key=lambda item: -len(item[0]))

    result = {}
    cloture_x0 = None
    for page in pdf.pages[:MAX_PAGES_SCANNED]:
        words = page.extract_words()
        lines = _cluster_lines(words, y_tolerance=5)
        if not lines:
            continue
        if cloture_x0 is None:
            cloture_x0 = _find_cloture_x0(lines)
            if cloture_x0 is None:
                continue
        for line in lines:
            label_words = _row_label_words(line)
            code = _matched_code(label_words, mnemo_to_code, name_to_code_by_length)
            if not code or code in result:
                continue
            clusters = _extract_numeric_clusters(line)
            if not clusters:
                continue
            value, x0 = min(clusters, key=lambda c: abs(c[1] - cloture_x0))
            if abs(x0 - cloture_x0) > X0_TOLERANCE:
                continue
            result[code] = value
    return result
