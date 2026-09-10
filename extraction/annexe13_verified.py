# -*- coding: utf-8 -*-
"""Tableaux Annexe 13 saisis À LA MAIN et vérifiés, pour les documents dont
la page est un SCAN que l'OCR ne lit pas de façon fiable (AMI 2019/2020/2023,
COTUNACE 2017/2019/2023 — voir CAS_PARTICULIERS_FULL_TABLE.md).

Chaque grille a été transcrite depuis le PDF source puis recoupée par les
identités comptables du document (chaque identité tombe juste, écart ≤ 1
millime — sauf l'anomalie AMI 2020 signalée plus bas, qui est DANS le PDF).

`process_one_document` (api/services/tableau_pipeline_service.py) consulte ce
module AVANT de tenter camelot/OCR : si le couple (code, année) y figure, la
grille vérifiée est stockée telle quelle (normalisée exactement comme les
autres — mêmes libellés canoniques de ligne/colonne, même ordre, mêmes
règles de validation), et l'OCR n'est pas tenté. Une revalidation ultérieure
ne peut donc jamais écraser ces valeurs avec du bruit OCR.

Pour ajouter une année vérifiée : compléter `VERIFIED` avec la même
structure (valeurs telles qu'imprimées dans le PDF, `None` = tiret « néant »
ou cellule vide)."""

from extraction.annexe13_pipeline import normalize_table, validate_table

# Colonnes dans leur ordre physique gauche→droite (déjà sous leur forme
# canonique — voir CANONICAL_COLUMNS / _COLUMN_ALIASES).
_AMI_COLS = ["Incendie", "Transport", "Risques divers", "Risques spéciaux",
            "Automobile", "Groupe", "Total"]
_COT_COLS = ["Crédit-Caution"]

_R = [
    "Primes acquises", "Primes émises", "Variation des primes non acquises",
    "Charges de prestations", "Prestations et frais payés",
    "Charges des provisions pour prestations diverses", "Solde de souscription",
    "Frais d'acquisition", "Autres charges de gestion nettes",
    "Charges d'acquisition et de gestion nettes", "Produits nets de placements",
    "Participation aux résultats", "Solde financier",
    "Part des réassureurs dans les primes acquises",
    "Part des réassureurs dans les prestations payées",
    "Part des réassureurs dans les charges de provisions pour prestations",
    "Part des réassureurs dans la participation aux résultats",
    "Commissions reçues des réassureurs / rétrocessionnaires",
    "Solde de réassurance / rétrocession", "Résultat technique",
    "Provisions pour primes non acquises (clôture)",
    "Provisions pour primes non acquises (réouverture)",
    "Provisions pour sinistres à payer (clôture)",
    "Provisions pour sinistres à payer (réouverture)",
]


def _grid(cols, page, matrix):
    """matrix : liste de 24 lignes, chacune = liste de valeurs alignée sur
    `cols` (None = néant/vide). -> grille {"colonnes", "lignes"} (cellules
    None omises), prête pour `normalize_table`."""
    lignes = {}
    for label, vals in zip(_R, matrix):
        cells = {c: v for c, v in zip(cols, vals) if v is not None}
        if cells:
            lignes[label] = cells
    return {"page": page, "colonnes": list(cols), "lignes": lignes}


# ── AMI — 7 branches ──────────────────────────────────────────────────────
_AMI_2019 = _grid(_AMI_COLS, 59, [
    [1941638, 1765146, 1897133, 826546, 148587462, 5007444, 160025370],
    [1931705, 1815347, 1868364, 688823, 147432233, 5007444, 158743916],
    [9934, -50201, 28769, 137723, 1155229, None, 1281454],
    [-86113, 992984, 1373247, -123681, 128586326, 6302214, 137044978],
    [645945, 941582, 469076, 130297, 122791284, 8292596, 133270781],
    [-732058, 51402, 904170, -253979, 5795042, -1990382, 3774196],
    [2027751, 772162, 523887, 950227, 20001136, -1294770, 22980392],
    [475906, 291470, 420756, 110207, 19976872, 365868, 21641078],
    [255312, 303898, 230865, 80431, 24645607, 1385028, 26901142],
    [731218, 595368, 651621, 190638, 44622479, 1750896, 48542220],
    [91433, 46113, 79293, 28550, 9391359, 53271, 9690018],
    [-161781, None, None, -59014, None, -53608, -274403],
    [-70348, 46113, 79293, -30464, 9391359, -337, 9415615],
    [-1956278, -1543427, -855100, -222332, -949530, None, -5526666],
    [457851, 750178, 215681, 63280, 1371702, None, 2858692],
    [-536112, -94836, -167826, -326442, -935821, None, -2061037],
    [None, None, None, None, None, None, None],
    [499832, 257395, 124291, 56299, None, None, 937818],
    [-1534707, -630689, -682955, -429195, -513649, None, -3791194],
    [-308522, -407782, -731396, 299931, -15743633, -3046004, -19937406],
    [1726449, 418334, 435380, 708593, 54558171, None, 57846928],
    [1736383, 368134, 464149, 846316, 55713400, None, 59128381],
    [1786067, 1591074, 3370201, 308193, 341501764, 1267437, 349824736],
    [2518125, 1539672, 2466030, 562171, 332803381, 3257819, 343147198],
])

# AMI 2020 — anomalie DANS LE PDF : Résultat technique / colonne Total
# affiche 5 880 087 alors que la somme des 6 branches vaut 10 264 890.
# Valeur laissée telle qu'imprimée (le contrôle `resultat_technique` sur la
# colonne Total sera donc signalé en écart — c'est le PDF qui ne se recoupe
# pas sur cette seule cellule).
_AMI_2020 = _grid(_AMI_COLS, 47, [
    [2351677, 1273240, 1489196, 432140, 134090352, 4963392, 144599997],
    [2355701, 1330116, 1417435, 512385, 130553939, 4963392, 141132967],
    [-4023, -56876, 71761, -80245, 3536413, None, 3467030],
    [1699703, 1976975, -9900, 24347, 88543324, 4878377, 97112826],
    [172376, 272122, 491190, 14493, 99028022, 4713860, 104692064],
    [1527327, 1704853, -501090, 9853, -10484698, 164517, -7579238],
    [651974, -703734, 1499096, 407794, 45547028, 85015, 47487172],
    [745554, 367610, 457387, 115513, 21020603, 348108, 23054775],
    [261122, 197307, 239338, 79098, 27995005, 1216822, 29988691],
    [1006676, 564917, 696725, 194611, 49015608, 1564930, 53043466],
    [142335, 96159, 117082, 35327, 13114936, 44904, 13550744],
    [None, None, None, None, None, 78038, 78038],
    [142335, 96159, 117082, 35327, 13114936, 122943, 13628782],
    [1799931, 1392094, 521635, 199791, 954180, None, 4867630],
    [-82645, -112039, -83403, -9200, 1277712, None, 990426],
    [-1303735, -1089486, -431959, -32271, 218266, None, -2639185],
    [None, None, None, None, None, None, None],
    [-583145, -272033, -118305, -52987, None, None, -1026470],
    [-169593, -81464, -112032, 105333, 2450158, None, 2192402],
    [-381960, -1253956, 807421, 353843, 12096514, -1356972, 5880087],
    [1730472, 475210, 363619, 788838, 51021758, None, 54379898],
    [1726449, 418334, 435380, 708593, 54558171, None, 57846928],
    [3313394, 3295927, 2869111, 318046, 336165598, 1431954, 347394031],
    [-1786067, -1591074, -3370201, -308193, -341501764, -1267437, -349824736],
])

_AMI_2023 = _grid(_AMI_COLS, 55, [
    [1777389, 2545007, 907292, 578723, 131181410, 6781912, 143771733],
    [1759921, 2479999, 879822, 1196716, 132724897, 6781912, 145823267],
    [17468, 65008, 27470, -617993, -1543487, None, -2051534],
    [-556767, 1951237, 535367, 16258, -99337197, -5025439, -102416541],
    [-252367, -416384, -380107, -207637, -89794549, -6028550, -97079594],
    [-304400, 2367621, 915474, 223895, -9542648, 1003111, -5336947],
    [1220622, 4496244, 1442659, 594981, 31844213, 1756473, 41355192],
    [-589623, -1083419, -308596, -1339477, -36699714, -1707944, -41728773],
    [-278678, -483579, -243330, 962647, -2132523, -1425342, -3600805],
    [-868301, -1566998, -551926, -376830, -38832237, -3133286, -45329578],
    [266687, 156971, 168716, 88556, 16965843, 48499, 17695272],
    [0, -3168, 0, 0, 0, -491297, -494465],
    [266687, 153803, 168716, 88556, 16965843, -442798, 17200807],
    [-1621353, -2105700, -326738, -948016, -3735024, None, -8736831],
    [205470, 646075, 183606, 221798, 2267178, None, 3524127],
    [267469, -1890660, -1507681, 305216, 2803804, None, -21852],
    [None, None, None, 23999, None, None, 23999],
    [523010, 364485, 8001, 231695, 1754, None, 1128945],
    [-625404, -2985800, -1642812, -165308, 1337712, None, -4081612],
    [-6396, 97249, -583363, 141399, 11315531, -1819611, 9144809],
    [1958715, 536365, 311264, 1450934, 52046155, None, 56303433],
    [1976184, 601373, 338734, 832941, 50502668, None, 54251900],
    [3896161, 2143633, 2830505, 642634, 315166629, 537102, 325216664],
    [3591761, 3442052, 3745979, 866529, 307297145, 1540211, 320483677],
])

# ── COTUNACE — mono-branche Crédit-Caution (millimes) ─────────────────────
_COT_2019 = _grid(_COT_COLS, 63, [[v] for v in [
    15617266.358, 15782293.398, 165027.040, 8810252.618, 3232365.493,
    5577887.125, 6807013.740, 1594329.713, 2475476.994, 4069806.707,
    3089652.752, 420281.182, 2669371.570, 9375979.293, 2249198.725,
    3106522.441, 256748.204, 2673352.124, -1090157.799, 4316420.804,
    2774151.788, 2609124.748, 16074216.918, 14080905.116,
]])

_COT_2023 = _grid(_COT_COLS, 67, [[v] for v in [
    12786040.966, 12823217.066, -37176.100, 5922048.696, 5642099.272,
    279949.424, 6863992.270, 2014565.803, 3184018.488, 5198584.291,
    2514731.627, -234355.700, 2749087.327, 7729341.540, 3093508.148,
    687214.892, -144871.520, 2202646.838, -1890843.182, 2523652.124,
    2437334.920, 2400158.820, 22717959.415, 21773736.456,
]])

# COTUNACE 2017 : dépôt CMF EN ARABE — « État de résultat technique »
# (Brut/Cessions/Net), PAS une Annexe 13 « par catégorie ». Seules les
# lignes qui correspondent sont reportées (colonne NET 2017, page 4) ; les
# sous-totaux propres à l'Annexe 13 (Solde de souscription, Solde financier,
# Solde de réassurance) et le détail « Part des réassureurs » ne figurent
# pas sous cette forme dans ce dépôt.
_COT_2017 = _grid(_COT_COLS, 4, [[v] for v in [
    4681088, 4947743, -266655, -2079012, -1195653, -883359, None,
    -1257958, -1078054, -2336012, None, None, None, None, None, None, None,
    2269639, None, 2259234, None, None, None, None,
]])

VERIFIED = {
    ("AMI", 2019): _AMI_2019, ("AMI", 2020): _AMI_2020, ("AMI", 2023): _AMI_2023,
    ("COTUNACE", 2017): _COT_2017, ("COTUNACE", 2019): _COT_2019,
    ("COTUNACE", 2023): _COT_2023,
}


def has(code, annee):
    return (code, int(annee)) in VERIFIED


def build_result(code, annee):
    """Renvoie le dict résultat au MÊME contrat que
    `annexe13_pipeline.process_annexe13` (page, colonnes, lignes,
    non_reconnues, colonnes_non_reconnues, validations) — normalisé et validé
    exactement comme la voie d'extraction normale, pour un stockage
    homogène."""
    grid = VERIFIED[(code, int(annee))]
    normalized = normalize_table({"colonnes": grid["colonnes"], "lignes": grid["lignes"]})
    validations = validate_table(normalized["lignes"], normalized["colonnes"])
    return {
        "page": grid["page"],
        "colonnes": normalized["colonnes"],
        "lignes": normalized["lignes"],
        "non_reconnues": normalized["non_reconnues"],
        "colonnes_non_reconnues": normalized["colonnes_non_reconnues"],
        "validations": validations,
    }
