"""
Registre des sociétés d'assurance tunisiennes suivies sur le portail CMF.

`cmf_name` doit correspondre EXACTEMENT au texte de l'option telle qu'elle
apparaît dans le widget de sélection (Chosen) de la page :
https://www.cmf.tn/consultation-des-tats-financier-des-soci-t-s-faisant-ape

La clé du dictionnaire (ex: "STAR") sert de code court : elle est utilisée
comme nom de sous-dossier (data/cmf/{CLE}/) et comme préfixe de fichier
({CLE}_{annee}.pdf).

`aliases` sert à reconnaître la société sur d'autres sources (ex: BVMT) qui
n'utilisent pas forcément le même intitulé que le portail CMF -> voir
find_code_by_name().
"""

import unicodedata


def _normalize_name(name):
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    return name.strip().upper()


COMPANY_REGISTRY = {

    "STAR": {
        "cmf_name": "Sté. TUNISIENNE D'ASSURANCES ET DE REASSURANCES - STAR -",
        "aliases": ["STAR", "S.T.A.R", "Société STAR"],
    },

    "COMAR": {
        "cmf_name": "COMPAGNIE MEDITERRANEENNE D'ASSURANCES ET DE REASSURANCES - COMAR -",
        "aliases": ["COMAR"],
    },

    "GAT_VIE": {
        "cmf_name": "GAT VIE",
        "aliases": ["GAT VIE"],
    },

    "AMI": {
        "cmf_name": "ASSURANCE MUTUELLE EL ITTIHAD - AMI -",
        "aliases": ["AMI", "AMI Assurances", "El Ittihad"],
    },

    "GAT": {
        "cmf_name": "GROUPE DES ASSURANCES DE TUNISIE - GAT -",
        "aliases": ["GAT", "Groupe GAT"],
    },

    "ASTREE": {
        "cmf_name": "COMPAGNIE D'ASSURANCES ET DE REASSURANCES - ASTREE -",
        "aliases": ["ASTREE"],
    },

    "CARTE": {
        "cmf_name": "COMPAGNIE D'ASSURANCES ET DE REASSURANCES TUNISO-EUROPEENNE - CARTE -",
        "aliases": ["CARTE"],
    },

    "CARTE_VIE": {
        "cmf_name": "COMPAGNIE D'ASSURANCES ET DE REASSURANCES TUNISO-EUROPEENNE VIE - CARTE VIE -",
        "aliases": ["CARTE VIE"],
    },

    "LLOYD_TUNISIEN": {
        "cmf_name": "Sté. TUNISIENNE D'ASSURANCES - LLOYD TUNISIEN -",
        "aliases": ["LLOYD TUNISIEN"],
    },

    "LLOYD_VIE": {
        "cmf_name": "Sté. LLOYD VIE",
        "aliases": ["LLOYD VIE"],
    },

    "MAGHREBIA": {
        "cmf_name": "ASSURANCES MAGHREBIA",
        "aliases": ["MAGHREBIA", "Maghrebia Assurances"],
    },

    "MAGHREBIA_VIE": {
        "cmf_name": "Sté. D'ASSURANCE MAGHREBIA VIE",
        "aliases": ["MAGHREBIA VIE"],
    },

    "BNA": {
        "cmf_name": "BNA Assurances ( ex : ASSURANCE MUTUELLE EL ITTIHAD - AMI - )",
        "aliases": ["BNA Assurances", "BNA"],
    },

    "BIAT": {
        "cmf_name": "ASSURANCES BIAT",
        "aliases": ["ASSURANCES BIAT", "BIAT Assurances"],
    },

    "BH": {
        "cmf_name": "BH ASSURANCE (EX ASSURNCES SALIM)",
        "aliases": ["BH ASSURANCE", "Assurances Salim"],
    },

    "UIB": {
        "cmf_name": "UIB ASSURANCES",
        "aliases": ["UIB ASSURANCES"],
    },

    "ATTIJARI": {
        "cmf_name": "ATTIJARI ASSURANCE",
        "aliases": ["ATTIJARI ASSURANCE"],
    },

    "HAYETT": {
        "cmf_name": "COMPAGNIE D'ASSURANCES VIE ET DE CAPITALISATION - HAYETT -",
        "aliases": ["HAYETT"],
    },

    "CTAMA": {
        "cmf_name": "CAISSE TUNISENNE D’ASSURANCES MUTUELLES AGRICOLES-CTAMA-",
        "aliases": ["CTAMA"],
    },

    "ZITOUNA_TAKAFUL": {
        "cmf_name": "ZITOUNA TAKAFUL",
        "aliases": ["ZITOUNA TAKAFUL"],
    },

    "AL_AMANAH_TAKAFUL": {
        "cmf_name": "AL AMANAH TAKAFUL",
        # "EL AMANA TAKAFUL" : orthographe utilisée par le CGA (translittération
        # différente de celle du CMF).
        "aliases": ["AL AMANAH TAKAFUL", "EL AMANA TAKAFUL"],
    },

    "AT_TAKAFULIA": {
        "cmf_name": "Sté. LA TUNISIENNE DES ASSURANCES TAKAFUL - AT-TAKAFULIA -",
        # "ATTAKAFULIA" (sans tiret) : orthographe utilisee par le CGA.
        "aliases": ["AT-TAKAFULIA", "ATTAKAFULIA"],
    },

    "TUNIS_RE": {
        "cmf_name": "Sté. TUNISIENNE DE REASSURANCE - TUNIS RE -",
        "aliases": ["TUNIS RE"],
    },

    "COTUNACE": {
        "cmf_name": "COMPAGNIE TUNISIENNE POUR L'ASSURANCE DU COMMERCE EXTERIEUR - COTUNACE -",
        "aliases": ["COTUNACE"],
    },
}


# Articles/connecteurs sans valeur distinctive (variantes de translittération
# arabe-français notamment) : sans les exclure, un mot comme "EL" peut faire
# gagner une correspondance non pertinente (ex: "EL Amana Takaful" matchait à
# tort "AMI", alias "El Ittihad", les deux partageant seulement "EL").
_STOPWORDS = {"EL", "AL", "DE", "DU", "DES", "LA", "LE", "LES", "ET", "EN", "D", "L"}


def _significant_words(text):
    return set(_normalize_name(text).split()) - _STOPWORDS


# Poids par mot (1/nombre de sociétés dont un alias contient ce mot) : un mot
# générique partagé par plusieurs sociétés (ex: "ASSURANCES") doit compter
# moins qu'un mot distinctif (ex: "VIE", "MAGHREBIA") lors du rapprochement
# par similarité -> sans cette pondération, une société de base (ex:
# MAGHREBIA, alias "Maghrebia Assurances") et sa filiale Vie (alias
# "MAGHREBIA VIE") obtiennent le même score de similarité face au nom
# complet "ASSURANCES MAGHREBIA VIE", le mot "VIE" (le seul qui les
# distingue) ne pesant pas plus que "ASSURANCES".
def _build_word_weights():
    companies_per_word = {}
    for info in COMPANY_REGISTRY.values():
        words_in_company = {w for alias in info.get("aliases", []) for w in _significant_words(alias)}
        for word in words_in_company:
            companies_per_word[word] = companies_per_word.get(word, 0) + 1
    return {word: 1 / count for word, count in companies_per_word.items()}


_WORD_WEIGHTS = _build_word_weights()


def find_code_by_name(name, min_score=0.2):
    """Retrouve le code court (ex: "MAGHREBIA_VIE") d'une société à partir
    d'un nom affiché sur une autre source (ex: BVMT) qui ne correspond pas
    forcément exactement à un alias. Comparaison par similarité de Jaccard
    pondérée (voir _WORD_WEIGHTS) sur les mots significatifs (hors
    _STOPWORDS), contre `aliases` uniquement (pas `cmf_name`, trop verbeux
    et peu comparable d'une source à l'autre). Renvoie None si aucun alias
    n'atteint `min_score`."""
    target_words = _significant_words(name)
    best_code, best_score = None, min_score
    for code, info in COMPANY_REGISTRY.items():
        for alias in info.get("aliases", []):
            alias_words = _significant_words(alias)
            union = target_words | alias_words
            if not union:
                continue
            score = sum(_WORD_WEIGHTS.get(w, 1) for w in target_words & alias_words) / sum(
                _WORD_WEIGHTS.get(w, 1) for w in union
            )
            if score > best_score:
                best_code, best_score = code, score
    return best_code
