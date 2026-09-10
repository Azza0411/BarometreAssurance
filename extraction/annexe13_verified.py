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


# Ordre des lignes du gabarit LLOYD_TUNISIEN : comme `_R` mais avec la ligne
# "Primes cédées aux réassureurs" intercalée après "Solde financier", et
# 2 postes "Autres provisions techniques" en fin de tableau.
_R_LLOYD = _R[:13] + ["Primes cédées aux réassureurs"] + _R[13:] + [
    "Autres provisions techniques (clôture)",
    "Autres provisions techniques (réouverture)",
]


def _grid(cols, page, matrix, rows=_R):
    """matrix : liste de lignes (alignée sur `rows`), chacune = liste de
    valeurs alignée sur `cols` (None = néant/vide). -> grille {"colonnes",
    "lignes"} (cellules None omises), prête pour `normalize_table`."""
    lignes = {}
    for label, vals in zip(rows, matrix):
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

# ── LLOYD_TUNISIEN — 9 branches ; pages Annexe 13 (IV.7) 2021/2022 SCANNÉES ─
# (2020/2023/2024 ont une couche texte, extraction camelot correcte).
_LL_COLS = ["Acceptation", "ARD", "Automobile", "Accidents du travail",
            "Incendie", "Transport", "Grêle", "Groupe", "Total"]

_LL_2021 = _grid(_LL_COLS, 33, [
    [645119, 18821481, 73461647, 0, 12096828, 7958606, 5151823, 14417879, 132553384],
    [621601, 18673660, 77853568, 0, 12682816, 9199499, 5296016, 14417879, 138745039],
    [23519, 147821, -4391921, 0, -585988, -1240893, -144193, None, -6191655],
    [17830, 10295172, 41243972, 67627, 8276509, 927302, -32609, 12848081, 73643883],
    [56890, 7999618, 37705656, 105147, 6320835, 2257785, 51810, 12817092, 67314834],
    [-39060, 2295553, 3538316, -37520, 1955674, -1330483, -84419, 30989, 6329050],
    [627289, 8526309, 32217675, -67627, 3820320, 7031304, 5184433, 1569798, 58909501],
    [289319, 1904280, 15203190, 0, 1510704, 645699, 69615, 1613754, 21236560],
    [44115, 1670237, 6235127, 0, 972690, 632326, 349886, 1149326, 11053707],
    [333434, 3574517, 21438318, 0, 2483394, 1278025, 419501, 2763079, 32290267],
    [20345, 881215, 2491555, 26632, 432742, 232184, 21206, 90755, 4196636],
    [0, -559513, 32537, 0, -811739, -135348, -43886, -296589, -1814538],
    [20345, 321703, 2524092, 26632, -378997, 96836, -22679, -205834, 2382098],
    [-308908, -13982014, -36007758, 0, -11149670, -8719993, -5150169, -869960, -76188472],
    [0, -154863, -844789, 0, 514188, 1187246, 173363, 0, 875144],
    [47178, 5272607, 16278943, 0, 5619426, 1788699, 45134, 35334, 29087321],
    [-61589, 3523123, 2788834, 0, 1248229, -1017772, -66621, 20000, 6434204],
    [0, 534024, 2574077, 0, 438152, 18133, 0, 0, 3564387],
    [89986, 1716385, 8792155, 0, 2393538, 1185312, 286997, 1038261, 15502634],
    [-233332, -3090738, -6418538, 0, -936138, -5558375, -4711297, 223635, -20724782],
    [80869, 2182757, 6884912, -40995, 21791, 291741, 30956, -1175481, 8276550],
    [-413584, -5483883, -29955691, 0, -2823787, -2228715, -793385, None, -41699045],
    [437103, 5631703, 25563770, 0, 2237799, 987823, 649192, None, 35507390],
    [375474, 28692848, 66675873, 33013, 13959517, 6776240, 0, 3519824, 120032790],
    [-414533, -26397295, -63137557, -33013, -11584245, -8106723, -113485, -3488835, -113275687],
    [None, 0, 0, 999874, 0, 0, 29066, 0, 1028940],
    [None, 0, 0, -1037394, -419599, 0, 0, 0, -1456993],
], rows=_R_LLOYD)

_LL_2022 = _grid(_LL_COLS, 34, [
    [495025, 21918799, 85470061, 0, 15526595, 10475196, 3202475, 18854031, 155942182],
    [469352, 22152932, 88335986, 0, 15759247, 9101056, 2835576, 18854031, 157508181],
    [25673, -234133, -2865925, 0, -232651, 1374140, 366899, None, -1565998],
    [34148, 8891946, 56672836, 67627, 11417591, 1188663, 183894, 17543704, 96000409],
    [32470, 9288599, 48698020, 104668, 9149679, 817313, 17035, 17523157, 85630942],
    [1678, -396653, 7974817, -37041, 2267912, 371351, 166858, 20546, 10369467],
    [460877, 13026853, 28797225, -67627, 4109005, 9286533, 3018581, 1310327, 59941773],
    [178636, 2681262, 17045471, 0, 2081976, 1444112, 85404, 1745608, 25262469],
    [44007, 1948529, 7609567, 0, 1436791, 854461, 284692, 1325657, 13503704],
    [222642, 4629791, 24655038, 0, 3518766, 2298573, 370097, 3071266, 38766173],
    [38302, 1702888, 5380495, 49856, 965428, 400621, 31160, 177245, 8745995],
    [0, -856931, -840311, 0, -143118, -122529, -211148, -259915, -2433952],
    [38302, 845957, 4540184, 49856, 822310, 278092, -179988, -82670, 6312043],
    [-308908, -15502372, -41792699, 0, -13248173, -8200072, -2650706, -1309676, -83012605],
    [0, -13850, -35911, 0, 359256, -1689075, -645200, 0, -2024780],
    [18094, 6264396, 21230649, 0, 7719224, 351376, 12147, 164177, 35760063],
    [4026, -434904, 2248941, 0, 2647084, 294265, 166786, 2935, 4929132],
    [0, 741295, 4160802, 0, 48988, 0, 196230, 0, 5147315],
    [89929, 1561274, 10127533, 0, 2820785, 1490600, 225051, 971518, 17286691],
    [-196859, -7384161, -4060684, 0, 347164, -7752906, -2695693, -171046, -21914185],
    [79677, 1858859, 4621688, -17771, 1759712, -486855, -227196, -2014655, 5573459],
    [-387911, -5718016, -32821616, 0, -3056438, -854575, -426486, None, -43265044],
    [413584, 5483883, 29955691, 0, 2823787, 2228715, 793385, None, 41699045],
    [377151, 28296196, 74650690, 33013, 16227429, 7147590, 195924, 3540371, 130468364],
    [-375474, -28692848, -66675873, -33013, -13959517, -6776240, 0, -3519824, -120032790],
    [None, 0, 0, 962833, 0, 0, 0, 0, 962833],
    [None, 0, 0, -999874, 0, 0, -29066, 0, -1028940],
], rows=_R_LLOYD)

VERIFIED = {
    ("AMI", 2019): _AMI_2019, ("AMI", 2020): _AMI_2020, ("AMI", 2023): _AMI_2023,
    ("COTUNACE", 2017): _COT_2017, ("COTUNACE", 2019): _COT_2019,
    ("COTUNACE", 2023): _COT_2023,
    ("LLOYD_TUNISIEN", 2021): _LL_2021, ("LLOYD_TUNISIEN", 2022): _LL_2022,
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
