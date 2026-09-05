"""
Nettoyage post-extraction des valeurs de KPI déjà en base : détection de
variations d'une année sur l'autre implausibles pour une même société (ex :
un "Total actif" qui chute de 95 % ou qui est multiplié par 20 d'une année à
l'autre trahit presque toujours une erreur d'extraction plutôt qu'une vraie
évolution business).

Contrairement aux garde-fous d'extraction (bilan_kpi_extractor._is_plausible,
kpi_extraction_pipeline._check_balance), qui jugent une valeur dans l'absolu
ou par cohérence interne à un même document, ce contrôle compare une valeur
fraîchement extraite à l'historique déjà stocké de la même société — il ne
peut donc s'exécuter qu'après extraction, sur des valeurs déjà en base : une
étape de nettoyage à part entière, pas un garde-fou d'extraction de plus.

Inspiré de la règle R-YOY du projet C:\\fsmi (staging.validator), adapté à
notre modèle de données : au lieu de comparer deux colonnes côte-à-côte dans
le même PDF (leur architecture stocke Brut/Net courant/Net précédent par
cellule), on compare contre la valeur déjà enregistrée pour le document de
l'année précédente de la même société — donnée déjà disponible dans notre
base, aucune extraction supplémentaire nécessaire.

Comme _check_balance, ce contrôle est informatif, jamais bloquant : une
valeur signalée n'est ni rejetée ni corrigée automatiquement, seulement
journalisée pour investigation. Une évolution business réellement extrême
(fusion, sinistre majeur, recapitalisation, société nouvellement cotée)
reste possible et ne doit pas être écrasée silencieusement.
"""

from database.repository import get_document_id, get_kpi_values_for_document

YOY_MAX_DROP_PCT = 95.0
YOY_MAX_GROWTH_X = 20.0
YOY_MIN_ABS = 1000.0

YOY_CHECKED_KPIS = {
    "Total actif",
    "Capitaux propres",
    "Total Passif",
    "Actifs incorporels",
    "Actifs corporels",
    "Placements",
    "Créances",
    "Autres éléments d'actifs",
    "Autres passifs",
    "Part des réassureurs dans les provisions techniques",
    "Provisions techniques brutes",
    "Primes émises par assurance",
}


def _flag_variation(name, cur, prev):
    """Logique pure (sans dépendance DB) : décide si la variation de `cur`
    par rapport à `prev` pour le KPI `name` est implausible. Renvoie un dict
    de signalement (sans "annee_precedente", ajouté par l'appelant) ou None.
    Isolée de check_yoy_consistency() pour rester testable sans connexion
    MySQL — même convention que api/services/quality.py (voir
    api/tests/test_quality.py : les fonctions couplées à `conn` n'y sont pas
    testées directement, seule leur logique pure l'est)."""
    if not isinstance(cur, (int, float)) or not isinstance(prev, (int, float)):
        return None
    if max(abs(cur), abs(prev)) < YOY_MIN_ABS or prev == 0:
        return None

    sign_flip = (cur * prev) < 0
    pct = (cur - prev) / abs(prev) * 100
    big_drop = pct <= -YOY_MAX_DROP_PCT
    big_jump = abs(cur / prev) >= YOY_MAX_GROWTH_X
    if not (sign_flip or big_drop or big_jump):
        return None

    return {
        "kpi": name,
        "valeur_precedente": prev,
        "valeur_actuelle": cur,
        "variation_pct": round(pct, 1),
        "signe_inverse": sign_flip,
    }


def check_yoy_consistency(conn, code, annee, kpis):
    """Compare chaque KPI de `kpis` ({nom: valeur}, fraîchement extrait pour
    le document (code, annee)) à la valeur déjà enregistrée en base pour la
    même société l'année précédente. Renvoie une liste de signalements
    (dicts) pour toute variation jugée implausible ; liste vide si rien à
    signaler ou si le document de l'année précédente n'est pas encore en
    base (première année couverte pour cette société)."""
    prev_document_id = get_document_id(conn, code, annee - 1)
    if prev_document_id is None:
        return []
    prev_kpis = get_kpi_values_for_document(conn, prev_document_id)

    flags = []
    for name in YOY_CHECKED_KPIS:
        flag = _flag_variation(name, kpis.get(name), prev_kpis.get(name))
        if flag is not None:
            flag["annee_precedente"] = annee - 1
            flags.append(flag)
    return flags
