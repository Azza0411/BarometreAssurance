"""Pipeline complète Annexe 13 (Phase 1, 2026-09-08) : extraction de la
grille complète (full_table_extractor.py) → normalisation des libellés de
ligne contre une liste canonique → validation par règles métier (identités
comptables du tableau) → structure prête pour stockage en base et export
Excel.

Contrairement aux extracteurs narrow existants (annexe13_kpi_extractor.py,
utilisés par les dashboards), cette pipeline ne se limite pas à 7 KPI et
ajoute une boucle de validation — inspirée d'un script de référence fourni
par l'utilisatrice (C:\\Users\\HP\\Music\\AzzaStage25-26\\FS_Market_Intelligence
\\B.py, fonctions normalize_excel/validate_excel) qui applique le même
principe (normalisation par correspondance floue + contrôles croisés C1-C9)
sur un cas particulier (STAR uniquement, valeurs de colonnes fixes). Ici,
généralisée à TOUTES les sociétés (les libellés de ligne sont un vocabulaire
réglementaire commun à toutes ; les colonnes/branches, elles, varient
réellement d'une société à l'autre selon ses lignes de produits — pas de
liste de colonnes fixe).

Décision explicite (voir échange utilisateur du 2026-09-08) : cette pipeline
reste SÉPARÉE des extracteurs narrow existants pour l'instant (Phase 1).
Les dashboards ne sont pas branchés dessus — seule la page "Gestion de
données" l'utilise. Une Phase 2, plus tard, migrera éventuellement les
dashboards vers les valeurs validées en base, une fois cette pipeline
éprouvée sur l'ensemble des sociétés.
"""

import difflib
import re

from extraction.bilan_kpi_extractor import _normalizer
from config.company_registry import TAKAFUL_CODES

# ── Sociétés hors périmètre de l'Annexe 13 (Résultat technique Non-Vie) ────
# Par nature du modèle métier — pas des échecs d'extraction. Référentiel
# UNIQUE (2026-09-09) : importé à la fois par le script d'audit de
# couverture (scripts/audit_full_table_extraction.py) et par le calcul des
# indicateurs de fiabilité (api/services/data_management.py::get_reliability_
# stats) pour ne jamais diverger sur "qui est censé avoir une Annexe 13
# Non-Vie". ATTIJARI et UIB vérifiés le 2026-09-09 : leur propre objet
# social ("opérations d'assurances sur la vie... et de capitalisation")
# confirme des sociétés Vie exclusivement — aucune page Annexe 13 Non-Vie
# dans leurs documents CMF, à aucune année (les rares résultats obtenus
# avant ce correctif étaient des faux positifs sur la page de raccordement
# Vie, codes PRV1/CHV1/CHV2). Takaful (Annexes 14/15 spécifiques) réutilise
# TAKAFUL_CODES du registre société plutôt que de le redéfinir ici.
VIE_ONLY_CODES = {
    "GAT_VIE", "LLOYD_VIE", "MAGHREBIA_VIE", "CARTE_VIE", "HAYETT",
    "ATTIJARI", "UIB",
}
ANNEXE13_NON_VIE_EXCLUSIONS = VIE_ONLY_CODES | TAKAFUL_CODES

# ── Normalisation des libellés de ligne ─────────────────────────────────────
# Vocabulaire réglementaire commun à toutes les sociétés (poste comptable du
# tableau "Résultat technique par catégorie d'assurance Non-Vie") — construit
# par union des libellés réellement observés sur plusieurs sociétés (STAR,
# GAT, BIAT) plutôt que copié d'une seule société, et recoupé avec la liste
# EXPECTED_ROWS du script de référence fourni par l'utilisatrice (résultat
# quasi identique, qui confirme qu'il s'agit bien du même vocabulaire
# standard, pas d'une liste propre à STAR).
CANONICAL_ROWS = [
    "Primes acquises",
    "Primes émises",
    "Variation des primes non acquises",
    "Charges de prestations",
    "Prestations et frais payés",
    "Charges des provisions pour prestations diverses",
    # Flux de résultat (composante du Solde de souscription sur les gabarits
    # qui l'isolent — BH « C4 » / « C7 »), à ne PAS confondre avec le stock
    # bilanciel « Autres provisions techniques (clôture/réouverture) » plus
    # bas : sans cette entrée canonique, la normalisation floue rabattait
    # « Variation des autres provisions techniques » sur « Autres provisions
    # techniques (clôture) » (libellés trop proches pour difflib).
    "Variation des autres provisions techniques",
    "Solde de souscription",
    "Frais d'acquisition",
    "Autres charges de gestion nettes",
    "Charges d'acquisition et de gestion nettes",
    "Produits nets de placements",
    "Participation aux résultats",
    "Solde financier",
    "Part des réassureurs dans les primes acquises",
    "Part des réassureurs dans les prestations payées",
    "Part des réassureurs dans les charges de provisions pour prestations",
    "Part des réassureurs dans la participation aux résultats",
    "Commissions reçues des réassureurs / rétrocessionnaires",
    "Solde de réassurance / rétrocession",
    "Résultat technique",
    "Provisions pour primes non acquises (clôture)",
    "Provisions pour primes non acquises (réouverture)",
    "Provisions pour sinistres à payer (clôture)",
    "Provisions pour sinistres à payer (réouverture)",
    # Ajoutés le 2026-09-09 suite à un relevé exhaustif des libellés NON
    # reconnus sur les 101 documents disponibles, toutes sociétés confondues
    # (pas seulement STAR/GAT/BIAT) — voir CAS_PARTICULIERS_FULL_TABLE.md.
    # Récurrents sur plusieurs exercices d'une même société (donc de vrais
    # postes du tableau source, pas un artefact ponctuel) mais absents des
    # 3 sociétés ayant servi à construire la liste initiale.
    "Intérêts servis",
    "Primes cédées aux réassureurs",
    # COMAR distingue ces 2 postes par exercice (N / N-1) sur 2 lignes
    # séparées, chacune avec ses PROPRES valeurs par branche — les fusionner
    # sous un même libellé canonique perdrait silencieusement la moitié des
    # valeurs (`normalize_table` ne fait qu'un `setdefault` par colonne en
    # cas de collision). Distingués explicitement plutôt que fusionnés — le
    # marqueur d'exercice est détecté et rattaché au bon libellé par
    # `normalize_row_label` (voir `_PRIOR_YEAR_MARKER_RE`).
    "Provisions mathématiques de rente (exercice N)",
    "Provisions mathématiques de rente (exercice N-1)",
    "Prévisions de recours à encaisser (exercice N)",
    "Prévisions de recours à encaisser (exercice N-1)",
    "Provisions pour égalisation et équilibrage (exercice N)",
    "Provisions pour égalisation et équilibrage (exercice N-1)",
    # Ajouté le 2026-09-10 (vérification TUNIS_RE, réassureur avec clientèle
    # Takaful) : poste de commissions "Wakala" propre à ce type de contrat,
    # absent des sociétés d'assurance directe ayant servi à construire la
    # liste initiale. Mot court (6 lettres) : sous le seuil de score flou
    # `_MATCH_THRESHOLD`, il finissait donc en "non reconnu" plutôt que
    # rattaché à un poste canonique inexistant à tort — ajouté tel quel.
    "Wakala",
    # Ajoutés le 2026-09-10 (vérification LLOYD_TUNISIEN) : ces 2 postes des
    # "informations complémentaires" matchaient à tort (difflib) "Provisions
    # pour sinistres à payer (clôture)/(réouverture)" — proches en surface,
    # sémantiquement distincts — et leurs valeurs étaient perdues par
    # collision. Explicités pour matcher exactement.
    "Autres provisions techniques (clôture)",
    "Autres provisions techniques (réouverture)",
    # Ajoutés le 2026-09-10 (vérification COMAR) : COMAR détaille son "Solde
    # financier" en "Produits de placements" + "Autres produits techniques"
    # (2 lignes) plutôt qu'en "Produits nets de placements" + "Participation
    # aux résultats", et ses "informations complémentaires" incluent 2 postes
    # de plus, chacun par exercice N / N-1.
    "Autres produits techniques", "Autres charges techniques",
    "Provisions pour participations aux bénéfices (exercice N)",
    "Provisions pour participations aux bénéfices (exercice N-1)",
    "Provisions pour risques en cours (exercice N)",
    "Provisions pour risques en cours (exercice N-1)",
    # COMAR 15 branches (2020-2025) : lignes "Part des réassureurs" de plus,
    # à ne PAS confondre (difflib) avec "... dans les primes acquises".
    "Part des réassureurs dans la variation des primes non acquises",
    "Part des réassureurs dans les charges des autres provisions techniques",
    "Part des réassureurs dans les frais reportés",
    "Part des réassureurs dans les frais d'acquisition",
    "Part des réassureurs dans les autres charges techniques",
    # Ajoutés le 2026-09-10 (vérification MAGHREBIA) : MAGHREBIA porte dans son
    # bloc réassurance une ligne "... dans les provisions pour égalisation et
    # équilibrage" (à NE PAS rabattre par difflib sur "... dans les charges de
    # provisions pour prestations"), et ses "informations complémentaires"
    # détaillent une "Provision mathématique" (vie logée en non-vie) à la
    # clôture / à l'ouverture.
    "Part des réassureurs dans les provisions pour égalisation et équilibrage",
    "Provisions mathématiques (clôture)",
    "Provisions mathématiques (réouverture)",
]

# Score minimal (difflib.SequenceMatcher.ratio, 0-1) pour accepter une
# correspondance — en-dessous, le libellé brut est gardé tel quel plutôt que
# rattaché à tort à un poste canonique qui n'est pas le sien (mieux vaut un
# libellé non normalisé visible que silencieusement faux).
_MATCH_THRESHOLD = 0.55

_CANONICAL_NORMALIZED = [(label, _normalizer.clean(label)) for label in CANONICAL_ROWS]

# Une ligne de repli fragmentée sur 2 libellés bruts consécutifs (ex. le
# tableau écrit la "part des réassureurs" en 4 sous-lignes commençant par
# "les..."/"la..." — voir full_table_extractor.py, cas STAR) : ces préfixes,
# une fois isolés, ne matcheraient RIEN d'assez proche seuls ("les prestations
# payes" est trop court/générique) — on les rattache explicitement à leur
# poste "Part des réassureurs..." correspondant avant le score flou.
_KNOWN_PREFIXED_VARIANTS = {
    "les prestations payes": "Part des réassureurs dans les prestations payées",
    "les charges de provi. pour prestations": "Part des réassureurs dans les charges de provisions pour prestations",
    "les charges de provisions pour prestations": "Part des réassureurs dans les charges de provisions pour prestations",
    "la participation aux resultats": "Part des réassureurs dans la participation aux résultats",
}

# COMAR distingue certains postes (provisions/prévisions) par exercice sur
# 2 lignes physiques ("... Année N" / "... Année N-1"), avec des valeurs par
# branche DIFFÉRENTES sur chaque ligne — le marqueur d'exercice est retiré
# du texte AVANT la correspondance floue (sinon "Annee N" et "Annee N-1" ne
# matcheraient pas exactement le même poste canonique) puis réinjecté APRÈS,
# pour router vers la variante "(exercice N)"/"(exercice N-1)" de
# CANONICAL_ROWS plutôt que de fusionner deux lignes réellement distinctes
# (voir le commentaire sur ces entrées dans CANONICAL_ROWS).
_YEAR_MARKER_RE = re.compile(r"[\s-]*annee\s*n([\s-]*1)?\s*$")


def normalize_row_label(raw_label):
    """Rattache un libellé de ligne brut extrait du PDF au poste comptable
    canonique correspondant (`CANONICAL_ROWS`), par correspondance floue —
    tolère les variantes de formulation déjà rencontrées entre sociétés
    ("Charges de prestation" vs "Charges de prestations", "Primes émises et
    acceptées" vs "Primes émises"...). Renvoie (libelle_normalise, matched)
    où `matched` est False si aucun poste canonique n'est assez proche (le
    libellé brut original est alors renvoyé tel quel, jamais perdu)."""
    norm = _normalizer.clean(raw_label)
    if norm in _KNOWN_PREFIXED_VARIANTS:
        return _KNOWN_PREFIXED_VARIANTS[norm], True

    match_target = norm
    year_marker = _YEAR_MARKER_RE.search(norm)
    if year_marker:
        base = _YEAR_MARKER_RE.sub("", norm).strip()
        suffix = "(exercice n-1)" if year_marker.group(1) else "(exercice n)"
        match_target = f"{base} {suffix}"

    best_label, best_score = None, 0.0
    for canonical, canonical_norm in _CANONICAL_NORMALIZED:
        # Un préfixe exact (ex. "primes acquises" contenu dans "primes
        # acquises brutes 31/12/2024") est un signal plus fort qu'un simple
        # ratio de similarité de chaînes — priorité absolue s'il existe.
        if match_target.startswith(canonical_norm) or canonical_norm.startswith(match_target):
            score = 0.9 + 0.1 * (len(canonical_norm) / max(len(match_target), len(canonical_norm)))
        else:
            score = difflib.SequenceMatcher(None, match_target, canonical_norm).ratio()
        if score > best_score:
            best_label, best_score = canonical, score

    if best_score >= _MATCH_THRESHOLD:
        return best_label, True
    return raw_label.strip().capitalize(), False


# ── Normalisation des libellés de COLONNE (branches) ────────────────────────
# Contrairement aux lignes (un vocabulaire comptable réglementaire commun à
# TOUTES les sociétés), les colonnes de l'Annexe 13 sont les BRANCHES
# d'assurance réellement vendues par chaque société — un ensemble qui varie
# légitimement d'une société à l'autre (ex. TUNIS_RE, réassureur, a des
# colonnes "Marines"/"Wakala" sans rapport avec le portefeuille d'un
# assureur direct). La normalisation ici ne fusionne donc JAMAIS deux
# branches réellement différentes — elle unifie seulement les variantes
# d'ORTHOGRAPHE/ABRÉVIATION d'une même branche observées d'une société à
# l'autre (ex. "AUTO" (ASTREE, BH, BIAT...) vs "AUTOMOBILE" (AMI, BNA,
# CARTE...), "R DIVERS"/"RISQ. DIVERS" vs "RISQUES DIVERS"...). Construite le
# 2026-09-09 par relevé exhaustif des colonnes RÉELLEMENT extraites sur les
# 101 documents disponibles (toutes sociétés, tous exercices confondus —
# voir scripts/audit_full_table_extraction.py pour rejouer un tel relevé),
# pas seulement celles de STAR.
CANONICAL_COLUMNS = [
    "Automobile", "Transport", "Incendie", "Risques divers", "Aviation",
    "Groupe", "Acceptation", "Total", "Maladie", "Construction",
    "Assistance", "Responsabilité civile", "Accidents du travail",
    "Accidents corporels", "Risques spéciaux", "Risques agricoles",
    "Pertes pécuniaires", "Protection juridique", "Crédit-Caution",
    "Responsabilité décennale", "Vol", "Grêle",
    "Autres dommages aux biens", "Individuelle accident", "Invalidité",
    "Autres", "Risques techniques", "Marines", "Non marines", "ARD",
    "Total marines", "Total non marines", "Total non vie", "Wakala",
    "Perte d'exploitation",  # branche COMAR (2020-2025)
    "Loi",  # branche ASTREE (« Individuelle » / « Loi » = 2 colonnes distinctes)
    # Gabarit "raccordement" (Brut/Cessions/Net) — pas des branches mais un
    # 2e type de tableau Annexe 13 rencontré sur certaines sociétés/années
    # (BH, AMI, CTAMA, COMAR — voir CAS_PARTICULIERS_FULL_TABLE.md, cas STAR
    # 2023 déjà documenté) : colonnes "Opérations brutes N" / "Cessions et/ou
    # rétrocessions N" / "Opérations nettes N" / "Opérations nettes N-1",
    # l'année étant un simple suffixe variable retiré avant comparaison
    # (voir `_COLUMN_YEAR_SUFFIX_RE`).
    "Opérations brutes", "Cessions et/ou rétrocessions", "Opérations nettes",
]

# Alias observés -> nom canonique (clé = texte déjà passé par
# `_normalizer.clean`, donc minuscules/sans accents). Une abréviation courte
# ("acctrav", "r.c") n'a pas assez de lettres en commun avec sa forme longue
# pour qu'une correspondance floue (difflib) la retrouve de façon fiable —
# contrairement aux lignes, un dictionnaire d'alias EXPLICITE est donc la
# méthode principale ici, la correspondance floue ne servant qu'en dernier
# recours (voir `normalize_column_label`).
_COLUMN_ALIASES = {
    "auto": "Automobile", "automobile": "Automobile",
    "transport": "Transport",
    "incendie": "Incendie",
    "risques divers": "Risques divers", "risq. divers": "Risques divers",
    "risq.divers": "Risques divers", "r divers": "Risques divers",
    "aviation": "Aviation",
    "groupe": "Groupe",
    "acceptation": "Acceptation", "acceptations": "Acceptation",
    "total": "Total", "montant": "Total", "total general": "Total",
    "t o t a l": "Total",
    # Distinct de "Total" (le total général Vie+Non-Vie) : certaines sociétés
    # (ex. TUNIS_RE, réassureur Vie+Non-Vie) ont les DEUX colonnes dans le
    # même tableau - les fusionner sous le même nom canonique "Total"
    # provoquait une collision réglée (à tort) par le suffixe de
    # désambiguïsation " (2)" de `normalize_table` (ex. "Total (2)"), qui
    # masquait la vraie structure du PDF plutôt que de la refléter.
    "total non vie": "Total non vie",
    "maladie": "Maladie",
    "construction": "Construction",
    "assistance": "Assistance", "assistances": "Assistance",
    "assistance a.e.a": "Assistance", "a.e.a": "Assistance",
    "rc gle": "Responsabilité civile", "r.c": "Responsabilité civile",
    "rc": "Responsabilité civile", "responsabilite civile": "Responsabilité civile",
    "civile": "Responsabilité civile", "e civile": "Responsabilité civile",
    "r.c generale": "Responsabilité civile",
    # MAGHREBIA porte "R.S" ET "R.C" comme deux colonnes distinctes : "R.S" y
    # est "Risques spéciaux" (branche incendie élargie), pas la RC.
    "r.s": "Risques spéciaux",
    "acctrav": "Accidents du travail", "a.travail": "Accidents du travail",
    "a. travail": "Accidents du travail", "a t": "Accidents du travail",
    "a.t. accident": "Accidents du travail", "a.t accident": "Accidents du travail",
    "a t accident": "Accidents du travail", "a.t.": "Accidents du travail",
    "accident travail": "Accidents du travail",
    "accidents de travail": "Accidents du travail",
    "accident de travail": "Accidents du travail", "travail": "Accidents du travail",
    "acc corp": "Accidents corporels", "accidents corporels": "Accidents corporels",
    "accident corporel": "Accidents corporels", "corporels": "Accidents corporels",
    "individuel accident": "Individuelle accident", "individuelle": "Individuelle accident",
    "individuel": "Individuelle accident",
    # MAGHREBIA écrit "MARITIME" pour sa branche Transport (assurance maritime).
    "maritime": "Transport",
    "risq.spx": "Risques spéciaux", "risq. spx": "Risques spéciaux",
    "risques agricoles": "Risques agricoles", "risque agricole": "Risques agricoles",
    "agricole": "Risques agricoles",
    "pertes pecuniaires": "Pertes pécuniaires", "pecuniaires": "Pertes pécuniaires",
    "protection juridique": "Protection juridique", "juridique": "Protection juridique",
    "credit-caution": "Crédit-Caution", "credit - caution": "Crédit-Caution",
    "caution": "Crédit-Caution", "credit export": "Crédit-Caution",
    "credit": "Crédit-Caution", "assurance credit": "Crédit-Caution",
    "responsabilite decennale": "Responsabilité décennale", "decennale": "Responsabilité décennale",
    "vol": "Vol",
    "grele": "Grêle",
    "perte d exploitation": "Perte d'exploitation", "perte d eploitation": "Perte d'exploitation",
    "pertes d exploitation": "Perte d'exploitation", "perte d'exploitation": "Perte d'exploitation",
    "autres dommages aux biens": "Autres dommages aux biens",
    "dommages aux biens": "Autres dommages aux biens", "aux biens": "Autres dommages aux biens",
    "invalidite": "Invalidité",
    "autres": "Autres", "autre s": "Autres",
    "risque tech.": "Risques techniques", "risque tech": "Risques techniques",
    # "ARD" / "Acc R.D" = "Accidents et Risques Divers" — abréviation d'usage
    # sur ces gabarits (TUNIS_RE écrit "ARD", LLOYD_TUNISIEN "Acc R.D"),
    # distincte de "Risques divers" (branche assureur direct) donc jamais
    # fusionnée avec elle (voir remarque en tête de dictionnaire).
    "ard": "ARD", "acc r.d": "ARD", "acc rd": "ARD", "acc r d": "ARD",
    "acc. r.d": "ARD", "accidents et risques divers": "ARD",
    "marines": "Marines", "non marines": "Non marines", "non m arines": "Non marines",
    "total marines": "Total marines", "total m arines": "Total marines",
    "total non marines": "Total non marines", "total non m arines": "Total non marines",
    "wakala": "Wakala",
    "vie": "Vie", "non vie": "Non-Vie", "globale": "Globale",
    # Gabarit "raccordement" (voir CANONICAL_COLUMNS ci-dessus) — libellés
    # une fois le suffixe année retiré par `_COLUMN_YEAR_SUFFIX_RE`.
    "operations brutes": "Opérations brutes", "brutes": "Opérations brutes",
    "operations nettes": "Opérations nettes", "nettes": "Opérations nettes",
    "cessions et/ou retrocessions": "Cessions et/ou rétrocessions",
    "cessions et retrocessions": "Cessions et/ou rétrocessions",
    "et/ou retrocessions": "Cessions et/ou rétrocessions",
    "retrocessions": "Cessions et/ou rétrocessions",
    "cessions": "Cessions et/ou rétrocessions",
}

_CANONICAL_COLUMNS_NORMALIZED = [(label, _normalizer.clean(label)) for label in CANONICAL_COLUMNS]
_COLUMN_MATCH_THRESHOLD = 0.8  # plus strict que pour les lignes : les libellés de
# colonne sont courts, un seuil bas confondrait des branches réellement
# différentes (ex. "Vol" / "Vie").

# Gabarit "raccordement" : le libellé de colonne porte souvent l'année en
# suffixe ("Opérations nettes 31/12/2021", "operations brutes 2015",
# "brutes au 31/12/2020" — CARTE) — une valeur variable par nature, retirée
# avant comparaison (généralisable à toute société utilisant ce gabarit,
# pas propre à une société). Le "au" optionnel avant la date ("brutes AU
# 31/12/2020" = "brutes AS OF 31/12/2020") est retiré avec elle.
_COLUMN_YEAR_SUFFIX_RE = re.compile(r"\s*(?:au\s+)?(?:\d{2}/\d{2}/)?\d{4}\s*$")

# Certaines sociétés numérotent leurs branches dans l'en-tête (ex. CARTE :
# "1-Auto", "2-Transport"...) — préfixe sans valeur distinctive pour la
# correspondance, retiré avant recherche (généralisable à toute société
# utilisant cette convention, pas propre à CARTE).
_COLUMN_NUM_PREFIX_RE = re.compile(r"^\d{1,2}[.\-)]\s*")

# Un libellé de colonne brut peut déjà porter un suffixe de désambiguïsation
# " (2)"/" (3)" posé en amont par full_table_extractor.py (deux colonnes du
# PDF littéralement identiques avant même la normalisation, ex. "Nettes" /
# "Nettes" sur le gabarit raccordement sans année en en-tête) — retiré avant
# recherche d'alias puis réappliqué au résultat, sinon "nettes (2)" ne
# matche jamais l'alias "nettes".
_COLUMN_DEDUP_SUFFIX_RE = re.compile(r"\s*\((\d+)\)\s*$")


def normalize_column_label(raw_label):
    """Équivalent de `normalize_row_label` pour les colonnes (branches).
    Renvoie (libelle_normalise, matched). `matched=False` laisse le libellé
    brut inchangé (jamais deviné à tort) — couvre notamment les placeholders
    "(colonne N)" (aucun mot d'en-tête détecté sur cette colonne, voir
    full_table_extractor.py) et les en-têtes visiblement mal reconstruits
    (plusieurs colonnes fusionnées en une seule chaîne)."""
    norm = _normalizer.clean(raw_label)
    if norm in _COLUMN_ALIASES:
        return _COLUMN_ALIASES[norm], True
    if norm.startswith("(colonne"):
        return raw_label, False

    dedup_suffix_match = _COLUMN_DEDUP_SUFFIX_RE.search(norm)
    dedup_suffix = f" ({dedup_suffix_match.group(1)})" if dedup_suffix_match else ""
    base = _COLUMN_DEDUP_SUFFIX_RE.sub("", norm) if dedup_suffix_match else norm

    no_year = _COLUMN_YEAR_SUFFIX_RE.sub("", base).strip()
    if no_year in _COLUMN_ALIASES:
        return _COLUMN_ALIASES[no_year] + dedup_suffix, True

    stripped = _COLUMN_NUM_PREFIX_RE.sub("", base)
    if stripped in _COLUMN_ALIASES:
        return _COLUMN_ALIASES[stripped] + dedup_suffix, True

    best_label, best_score = None, 0.0
    for canonical, canonical_norm in _CANONICAL_COLUMNS_NORMALIZED:
        score = difflib.SequenceMatcher(None, stripped, canonical_norm).ratio()
        if score > best_score:
            best_label, best_score = canonical, score
    if best_score >= _COLUMN_MATCH_THRESHOLD:
        return best_label + dedup_suffix, True
    return raw_label.strip(), False


_SECTION_SEPARATOR_LABELS = {
    "informations complementaires", "informations complementaires :",
    "a deduire", "a deduire :",
}


def normalize_table(grid):
    """Applique `normalize_row_label`/`normalize_column_label` à toutes les
    lignes ET colonnes d'une grille issue de `full_table_extractor.
    extract_full_table_camelot` / `locate_and_extract_full_table`. Renvoie
    {"colonnes": [...], "lignes": {libelle_normalise: {colonne_normalisee:
    valeur}}, "non_reconnues": [...], "colonnes_non_reconnues": [...]}.
    L'ORDRE physique des colonnes (gauche->droite tel qu'extrait du PDF,
    voir `colonne_ordre` en base) est préservé — seul le LIBELLÉ change, pas
    la position. Deux libellés bruts (ligne ou colonne) distincts qui se
    normalisent vers le même poste/branche canonique (rare — ne devrait pas
    arriver sur une page bien reconstruite) sont fusionnés en gardant la
    valeur non-nulle si l'une des deux est vide, pour ne perdre aucune
    donnée plutôt que d'écraser silencieusement."""
    # Colonnes : renommage préservant l'ordre, avec désambiguïsation si deux
    # colonnes se retrouvent avec le même libellé normalisé (même principe
    # que la déduplication déjà faite en amont sur les libellés bruts —
    # voir full_table_extractor.py).
    col_rename = {}
    colonnes_normalisees = []
    colonnes_non_reconnues = []
    seen_cols = {}
    for raw_col in grid["colonnes"]:
        normalized, matched = normalize_column_label(raw_col)
        if not matched:
            colonnes_non_reconnues.append(raw_col)
        n = seen_cols.get(normalized, 0) + 1
        seen_cols[normalized] = n
        final = normalized if n == 1 else f"{normalized} ({n})"
        col_rename[raw_col] = final
        colonnes_normalisees.append(final)

    lignes_normalisees = {}
    non_reconnues = []
    for raw_label, values in grid["lignes"].items():
        # Lignes de SÉPARATION de section, jamais des postes (ex. LLOYD_TUNISIEN :
        # "Informations complémentaires", "A déduire :") — parfois captées avec
        # une valeur résiduelle (Total = 0) par la reconstruction de grille.
        if _normalizer.clean(raw_label) in _SECTION_SEPARATOR_LABELS:
            continue
        normalized, matched = normalize_row_label(raw_label)
        if not matched:
            non_reconnues.append(raw_label)
        renamed_values = {col_rename.get(col, col): val for col, val in values.items()}
        if normalized in lignes_normalisees:
            existing = lignes_normalisees[normalized]
            for col, val in renamed_values.items():
                existing.setdefault(col, val)
        else:
            lignes_normalisees[normalized] = renamed_values
    return {
        "colonnes": colonnes_normalisees,
        "lignes": lignes_normalisees,
        "non_reconnues": non_reconnues,
        "colonnes_non_reconnues": colonnes_non_reconnues,
    }


# ── Validation par règles métier ────────────────────────────────────────────
# Identités comptables réelles du tableau "Résultat technique" (pas propres à
# une société — ce sont des définitions du plan comptable des assurances,
# valables branche par branche ET sur la colonne Total). Toutes les valeurs
# sont déjà SIGNÉES (les charges/sorties sont négatives dans les données
# extraites), donc chaque identité s'exprime comme une simple SOMME — à la
# différence du script de référence fourni par l'utilisatrice, dont certaines
# formules (C4, C6) soustrayaient un poste censé s'additionner ; ces identités
# sont ré-établies ici depuis la logique comptable elle-même plutôt que
# recopiées telles quelles.
_TOLERANCE = 5  # ecart (en unite monetaire du tableau, generalement le dinar) tolere avant signalement — arrondis/dinarisation

VALIDATION_RULES = [
    ("primes_acquises",
     "Primes acquises = Primes émises + Variation des primes non acquises",
     "Primes acquises", ["Primes émises", "Variation des primes non acquises"]),
    ("charges_prestations",
     "Charges de prestations = Prestations et frais payés + Charges des provisions pour prestations diverses",
     "Charges de prestations", ["Prestations et frais payés", "Charges des provisions pour prestations diverses"]),
    ("solde_souscription",
     "Solde de souscription = Primes acquises + Charges de prestations",
     "Solde de souscription", ["Primes acquises", "Charges de prestations"]),
    ("charges_acquisition_gestion",
     "Charges d'acquisition et de gestion nettes = Frais d'acquisition + Autres charges de gestion nettes",
     "Charges d'acquisition et de gestion nettes", ["Frais d'acquisition", "Autres charges de gestion nettes"]),
    ("solde_financier",
     "Solde financier = Produits nets de placements + Participation aux résultats",
     "Solde financier", ["Produits nets de placements", "Participation aux résultats"]),
    ("solde_reassurance",
     "Solde de réassurance / rétrocession = Part des réassureurs dans les primes acquises "
     "+ Part des réassureurs dans les prestations payées + Part des réassureurs dans les charges "
     "de provisions pour prestations + Part des réassureurs dans la participation aux résultats "
     "+ Commissions reçues des réassureurs / rétrocessionnaires",
     "Solde de réassurance / rétrocession",
     ["Part des réassureurs dans les primes acquises", "Part des réassureurs dans les prestations payées",
      "Part des réassureurs dans les charges de provisions pour prestations",
      "Part des réassureurs dans la participation aux résultats",
      "Commissions reçues des réassureurs / rétrocessionnaires",
      # Postes de réassurance qui n'apparaissent que sur certains gabarits
      # (MAGHREBIA : « … dans les provisions pour égalisation et équilibrage » ;
      # ASTREE / COMAR détaillé : « … dans la variation des primes non
      # acquises »). Préfixe "?" = FACULTATIF : absent -> compté 0, ne rend
      # pas la règle « données manquantes » (sinon on régresserait les
      # gabarits qui n'ont pas ces lignes).
      "?Part des réassureurs dans les provisions pour égalisation et équilibrage",
      "?Part des réassureurs dans la variation des primes non acquises",
      # BIAT loge « Intérêts servis » (aux réassureurs) dans son bloc
      # réassurance, en déduction du Solde de réassurance.
      "?Intérêts servis"]),
    ("resultat_technique",
     "Résultat technique = Solde de souscription + Charges d'acquisition et de gestion nettes "
     "+ Solde financier + Solde de réassurance / rétrocession",
     "Résultat technique",
     ["Solde de souscription", "Charges d'acquisition et de gestion nettes",
      "Solde financier", "Solde de réassurance / rétrocession"]),
]


_GROUP_TERMINAL_RE = re.compile(r"^total\s+(.+)$", re.IGNORECASE)
# « Total non vie » (et « Total non-vie ») est un SOUS-TOTAL courant, pas un
# en-tête de groupe fusionné : le PDF source affiche un en-tête PLAT au-dessus
# des branches (constaté sur ASTREE — capture utilisateur du 2026-09-10). Ne
# jamais en dériver un regroupement (sinon l'export Excel fabrique une fusion
# « Non vie » qui n'existe pas dans le PDF).
_GROUP_TERMINAL_EXCLUDE = {"non vie", "non-vie", "nonvie"}


def derive_column_groups(colonnes):
    """À partir de la liste ORDONNÉE des noms de colonnes déjà normalisés,
    retrouve les groupes que le PDF source affiche avec un en-tête de groupe
    fusionné au-dessus de plusieurs sous-colonnes (ex. TUNIS_RE : "NON
    MARINES" au-dessus d'Incendie/ARD/Risques techniques — retour
    utilisateur du 2026-09-10, capture d'écran du PDF original). L'en-tête de
    groupe lui-même n'existe plus comme colonne à part entière (voir
    `full_table_extractor.py::reconstruct_grid_from_rows`, qui l'exclut de la
    concaténation de la sous-colonne où camelot l'avait posé par erreur) mais
    sa PRÉSENCE reste déductible : ce type de gabarit fait toujours suivre la
    série de sous-colonnes d'un groupe par une colonne "Total <Groupe>" — le
    nom de cette colonne, une fois le préfixe "Total " retiré, EST le nom du
    groupe (ex. "Total non marines" -> groupe "Non marines"). Généralisable à
    toute société utilisant ce gabarit (pas une règle propre à TUNIS_RE) :
    fonctionne sur la seule liste de noms, donc aussi bien sur une grille
    fraîchement extraite que sur une grille relue depuis la base.

    Renvoie une liste de {"libelle": nom_du_groupe, "debut": idx_première_
    colonne_membre, "fin": idx_dernière_colonne_membre} (indices dans
    `colonnes`, bornes incluses, EXCLUANT la colonne "Total <Groupe>"
    elle-même — elle reste une colonne à part entière à sa propre droite,
    comme dans le PDF). Aucun groupe n'est produit si la portée calculée est
    vide (colonne "Total X" immédiatement adjacente à la frontière du groupe
    précédent — ex. "Total non vie" juste après "Total marines" — ou en tout
    début de tableau) : jamais de regroupement fabriqué artificiellement."""
    groups = []
    boundary = 0  # 1re colonne pas encore rattachée à un groupe précédent
    for idx, name in enumerate(colonnes):
        m = _GROUP_TERMINAL_RE.match((name or "").strip())
        if not m:
            continue
        gname = m.group(1).strip()
        # « Total non vie », ou un suffixe de désambiguïsation « Total (2) »
        # (collision de noms résolue par normalize_table sur une extraction
        # camelot bancale) : ce n'est pas un vrai en-tête de groupe fusionné.
        if gname.lower() in _GROUP_TERMINAL_EXCLUDE or re.fullmatch(r"\(\d+\)", gname):
            boundary = idx + 1  # colonne total consommée, aucun groupe produit
            continue
        start, end = boundary, idx - 1
        if end >= start:
            groups.append({"libelle": m.group(1).strip().capitalize(), "debut": start, "fin": end})
        boundary = idx + 1
    return groups


def validate_table(normalized_lignes, columns):
    """Applique `VALIDATION_RULES` colonne par colonne (chaque branche, plus
    Total). Renvoie une liste de résultats {regle, colonne, attendu, trouve,
    ecart, statut} — statut 'ok' (écart ≤ tolérance), 'ecart' (dépassement,
    signale un souci d'extraction ou une vraie incohérence du document
    source) ou 'donnees_manquantes' (un des postes de la règle est absent de
    cette grille — rien à valider)."""
    results = []
    for rule_code, rule_desc, target, sources in VALIDATION_RULES:
        target_row = normalized_lignes.get(target)
        # Un poste source préfixé "?" est FACULTATIF : s'il est absent de la
        # grille (ou sa cellule vide) il compte 0 et ne déclenche pas
        # « données manquantes » — pour les lignes de réassurance qui
        # n'existent que sur certains gabarits.
        parsed = [(s[1:], True) if s.startswith("?") else (s, False) for s in sources]
        req_rows = [normalized_lignes.get(name) for name, opt in parsed if not opt]
        for col in columns:
            base = {"regle_code": rule_code, "regle": rule_desc, "colonne": col}
            if target_row is None or any(r is None for r in req_rows):
                results.append({**base, "attendu": None, "trouve": None,
                                 "ecart": None, "statut": "donnees_manquantes"})
                continue
            found = target_row.get(col)
            source_vals = []
            missing_required = False
            for name, opt in parsed:
                row = normalized_lignes.get(name)
                v = row.get(col) if row is not None else None
                if v is None:
                    if opt:
                        continue
                    missing_required = True
                    break
                source_vals.append(v)
            if found is None or missing_required:
                results.append({**base, "attendu": None, "trouve": found,
                                 "ecart": None, "statut": "donnees_manquantes"})
                continue
            expected = sum(source_vals)
            ecart = round(found - expected, 2)
            statut = "ok" if abs(ecart) <= _TOLERANCE else "ecart"
            results.append({**base, "attendu": round(expected, 2),
                             "trouve": round(found, 2), "ecart": ecart, "statut": statut})
    return results


def process_annexe13(pdf_path, is_target_page, kpi_patterns, raccordement_re, relaxed_page_predicate):
    """Pipeline complète pour un document : localise + extrait la grille
    (full_table_extractor), normalise les libellés de ligne ET de colonne,
    valide par règles métier. Renvoie None si aucune page valide n'a été
    trouvée, sinon {"page", "colonnes", "lignes", "non_reconnues",
    "colonnes_non_reconnues", "validations"}."""
    from extraction.full_table_extractor import locate_and_extract_full_table

    page_num, grid = locate_and_extract_full_table(
        pdf_path, is_target_page, kpi_patterns, raccordement_re,
        extra_page_predicate=relaxed_page_predicate,
    )
    if grid is None:
        return None

    normalized = normalize_table(grid)
    validations = validate_table(normalized["lignes"], normalized["colonnes"])
    return {
        "page": page_num,
        "colonnes": normalized["colonnes"],
        "lignes": normalized["lignes"],
        "non_reconnues": normalized["non_reconnues"],
        "colonnes_non_reconnues": normalized["colonnes_non_reconnues"],
        "validations": validations,
    }
