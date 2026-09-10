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

# ── COMAR — gabarit propre : pas de ligne "Primes acquises"/"Charges de
# prestations" à part (ce sont des en-têtes de section), "Solde financier"
# détaillé en "Produits de placements" + "Autres produits techniques",
# 3 lignes "Part des réassureurs" (pas de "participation aux résultats"),
# et un bloc "informations complémentaires" par exercice N / N-1. La ligne
# de séparation "Résultat technique" du gabarit standard est ici
# "RESULTAT TECHNIQUE NON VIE". Valeurs SIGNÉES (Prestations payées, Frais
# d'acquisition... en négatif).
_R_COMAR = [
    "Primes émises", "Variation des primes non acquises",
    "Prestations et frais payés", "Charges des provisions pour prestations diverses",
    "Solde de souscription", "Frais d'acquisition", "Autres charges de gestion nettes",
    "Charges d'acquisition et de gestion nettes", "Produits nets de placements",
    "Autres produits techniques", "Solde financier",
    "Part des réassureurs dans les primes acquises",
    "Part des réassureurs dans les prestations payées",
    "Part des réassureurs dans les charges de provisions pour prestations",
    "Commissions reçues des réassureurs / rétrocessionnaires",
    "Solde de réassurance / rétrocession", "Résultat technique",
    "Provisions pour primes non acquises (clôture)",
    "Provisions pour primes non acquises (réouverture)",
    "Provisions pour sinistres à payer (clôture)",
    "Provisions pour sinistres à payer (réouverture)",
    "Prévisions de recours à encaisser (exercice N)",
    "Prévisions de recours à encaisser (exercice N-1)",
    "Provisions pour participations aux bénéfices (exercice N)",
    "Provisions pour participations aux bénéfices (exercice N-1)",
    "Provisions pour égalisation et équilibrage (exercice N)",
    "Provisions pour égalisation et équilibrage (exercice N-1)",
    "Provisions mathématiques de rente (exercice N)",
    "Provisions mathématiques de rente (exercice N-1)",
    "Provisions pour risques en cours (exercice N)",
    "Provisions pour risques en cours (exercice N-1)",
]
_CM_COLS_8 = ["Incendie", "Accidents du travail", "Risques divers", "Automobile",
              "Transport", "Groupe", "Aviation", "Acceptation", "Total"]
_CM_TOT = lambda v: [None] * 8 + [v]

_CM_2019 = _grid(_CM_COLS_8, 33, [
    [22591601, 0, 31015415, 108539448, 7915330, 27004771, 468991, 9809753, 207345309],
    [-395010, 0, 752372, -2769382, 150208, -172061, -243020, 2191730, -485163],
    [-10585705, -414482, -8166116, -67995641, -1508519, -19638448, -1936046, -8293918, -118538875],
    [2302140, -130072, -14326850, -6928235, 4060632, -1011908, 74453, 0, -15959840],
    [13913026, -544554, 9274821, 30846190, 10617651, 6182354, -1635622, 3707565, 72361431],
    [-3229543, 125197, -5686251, -17507587, -2587659, -3346712, -998431, -3212922, -36443908],
    [-2138258, 0, -4031101, -12686090, -1751117, -2464115, -717769, 0, -23788450],
    [-5367801, 125197, -9717352, -30193677, -4338776, -5810827, -1716200, -3212922, -60232358],
    [2271185, 0, 3118051, 10911720, 795746, 2714852, 47149, 0, 19858703],
    [-23271, 0, -7576, 0, -284392, -370611, 0, 0, -685850],
    [2247914, 0, 3110475, 10911720, 511354, 2344241, 47149, 0, 19172853],
    [-16750862, 0, -9995618, -952909, -4207453, -501547, -436998, 0, -32845387],
    [9828274, 0, 2961428, 24879, 1171213, 74804, 0, 0, 14060598],
    [-7930975, 0, 3395501, -113064, 61829, 0, 14161, 0, -4572548],
    [5499701, 0, 2489269, 0, 1142809, 0, 175541, 0, 9307320],
    [-9353862, 0, -1149420, -1041094, -1831602, -426743, -247296, 0, -14050017],
    [1439277, -419357, 1518524, 10523139, 4958627, 2289025, -3551969, 494643, 17251909],
    _CM_TOT(61911077), _CM_TOT(61425914), _CM_TOT(365828889), _CM_TOT(358002011),
    _CM_TOT(-31147913), _CM_TOT(-29211253), _CM_TOT(6001870), _CM_TOT(6301156),
    _CM_TOT(17910262), _CM_TOT(8309966), _CM_TOT(13335550), _CM_TOT(11392965),
    _CM_TOT(3156383), _CM_TOT(4330354),
], rows=_R_COMAR)

_CM_2017 = _grid(_CM_COLS_8, 13, [
    [19941112, -467, 34272248, 96328493, 7550124, 19711467, 243447, 10300395, 188346819],
    [-108665, None, -4235569, -2322050, -197018, -3464, -317967, 34993, -7149740],
    [-5161752, -438578, -7178350, -63331962, -1260187, -16128742, None, -8599986, -102099557],
    [-18101905, None, 7363013, -1066757, 94603, -482335, 2607, -376514, -12567288],
    [-3431210, -439045, 30221342, 29607724, 6187522, 3096926, -71913, 1358888, 66530234],
    [-2933158, None, -5031228, -14760561, -2105794, -2857357, None, -3583770, -31271868],
    [-1569060, None, -2815361, -9376663, -1275572, -1828618, None, None, -16865274],
    [-4502218, None, -7846589, -24137224, -3381366, -4685975, 0, -3583770, -48137142],
    [1640003, None, 3095985, 8515575, 690452, 1776020, 21521, 910570, 16650126],
    [None, None, -3959, None, -182493, -304495, None, None, -490947],
    [1640003, None, 3092026, 8515575, 507959, 1471525, 21521, 910570, 16159179],
    [-14437220, None, -9711127, -886271, -2526521, None, -239258, None, -27800397],
    [2829860, None, 1860610, 172446, 429958, None, 7920, None, 5300794],
    [14451619, None, -2794408, -363813, 258167, None, -49165, None, 11502400],
    [4813691, None, 3008649, None, 996935, None, 52120, None, 8871395],
    [7657950, 0, -7636276, -1077638, -841461, 0, -228383, 0, -2125808],
    [1364525, -439045, 17830503, 12908437, 2472654, -117524, -278775, -1314312, 32426463],
    _CM_TOT(56987013), _CM_TOT(49837274), _CM_TOT(317900969), _CM_TOT(300640907),
    _CM_TOT(24367384), _CM_TOT(20917843), _CM_TOT(5685461), _CM_TOT(6642898),
    _CM_TOT(7676449), _CM_TOT(7667419), _CM_TOT(11080116), _CM_TOT(11014304),
    _CM_TOT(940043), _CM_TOT(1300682),
], rows=_R_COMAR)

# ── COMAR 15 branches (2020-2025) ─────────────────────────────────────────
_CM_COLS_15 = ["Incendie", "Accidents du travail", "Responsabilité civile", "Automobile",
               "Transport", "Groupe", "Autres dommages aux biens", "Risques agricoles",
               "Construction", "Perte d'exploitation", "Crédit-Caution", "Assistance",
               "Accidents corporels", "Acceptation", "Total"]
_R_COMAR_15 = [
    "Primes émises", "Variation des primes non acquises",
    "Prestations et frais payés", "Charges des provisions pour prestations diverses",
    "Solde de souscription", "Frais d'acquisition", "Autres charges de gestion nettes",
    "Charges d'acquisition et de gestion nettes", "Produits nets de placements",
    "Autres produits techniques", "Solde financier",
    "Part des réassureurs dans les primes acquises",
    "Part des réassureurs dans la variation des primes non acquises",
    "Part des réassureurs dans les prestations payées",
    "Part des réassureurs dans les charges de provisions pour prestations",
    "Commissions reçues des réassureurs / rétrocessionnaires",
    "Part des réassureurs dans la participation aux résultats",
    "Part des réassureurs dans les charges des autres provisions techniques",
    "Solde de réassurance / rétrocession", "Résultat technique",
    "Provisions pour primes non acquises (clôture)",
    "Provisions pour primes non acquises (réouverture)",
    "Provisions pour sinistres à payer (clôture)",
    "Provisions pour sinistres à payer (réouverture)",
    "Prévisions de recours à encaisser (exercice N)",
    "Prévisions de recours à encaisser (exercice N-1)",
    "Provisions pour participations aux bénéfices (exercice N)",
    "Provisions pour participations aux bénéfices (exercice N-1)",
    "Provisions pour égalisation et équilibrage (exercice N)",
    "Provisions pour égalisation et équilibrage (exercice N-1)",
    "Provisions mathématiques de rente (exercice N)",
    "Provisions mathématiques de rente (exercice N-1)",
    "Provisions pour risques en cours (exercice N)",
    "Provisions pour risques en cours (exercice N-1)",
]

_CM_2023 = _grid(_CM_COLS_15, 35, [
    [28740588, 0, 8185462, 127319950, 10255508, 48529230, 6188228, 1110348, 1192115, 1790718, 107339, 10626558, 8217041, 4075097, 256338182],
    [-276761, 0, 0, -1918580, 14861, -154409, -23853, -1589615, 172986, 0, 0, 0, 0, 559961, -3215410],
    [-4231126, -468836, -1668060, -82925700, -2441039, -37164224, -1354652, -304149, -955063, -141632, -279459, -3817862, -896189, -5823379, -142471370],
    [-7943913, 222972, 2822981, -19757364, 2424275, -124976, 204067, -126584, -1044970, 1000, -5000, -10781, -85753, 608487, -22815559],
    [16288788, -245864, 9340383, 22718306, 10253605, 11085621, 5013790, -910000, -634932, 1650086, -177120, 6797915, 7235099, -579834, 87835843],
    [-5026820, -113992, -1479528, -21530229, -3631389, -4178605, -1245885, -56645, -1292931, -362515, -170940, -1462166, -2018959, 0, -42570604],
    [-2406105, 0, -797521, -14052742, -2420178, -4003282, -808975, -242867, -843830, -259978, -108745, -1679661, -1303544, 0, -28927428],
    [-7432925, -113992, -2277049, -35582971, -6051567, -8181887, -2054860, -299512, -2136761, -622493, -279685, -3141827, -3322503, 0, -71498032],
    [5216375, 585701, 3588901, 23779221, 454853, 1298172, 551826, 897957, 1972841, 38830, 3710, 83596, 50593, 0, 38522576],
    [0, 0, 0, 134165, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 134165],
    [5216375, 585701, 3588901, 23913386, 454853, 1298172, 551826, 897957, 1972841, 38830, 3710, 83596, 50593, 0, 38656741],
    [-25321109, 0, -3331960, -1543535, -6344371, -2886299, -5725606, -757074, -1047679, 0, -43508, -295930, -377848, 0, -47674919],
    [265610, 0, 32565, 0, 440827, 0, 91793, 8102, 1176, 0, -223, 0, 31675, 0, 871525],
    [2381408, 0, 0, 0, 1221290, 2288670, 820857, 115813, 497089, 0, 0, 0, 33366, 0, 7358493],
    [5630643, 0, 228574, 2201413, -1519879, 0, 165791, 110085, 1033843, 0, 4250, 0, 10080, 0, 7864800],
    [6806820, 0, 709534, 0, 1355472, 704051, 1547838, 246652, 260302, 0, 10770, 29049, 91062, 0, 11761550],
    [0, 0, 0, 0, 573700, 0, 0, 39725, 0, 0, 0, 0, 0, 0, 613425],
    [185646, 0, 59352, 0, -3090, 0, -54166, -691, -60913, 0, 0, 0, -7890, 0, 118248],
    [-10050982, 0, -2301935, 657878, -4276051, 106422, -3153493, -237388, 683818, 0, -28711, -266881, -219555, 0, -19086878],
    [4021256, 225845, 8350300, 11706599, 380840, 4308328, 357263, -548943, -115034, 1066423, -481806, 3472803, 3743634, -579834, 35907674],
    [7635082, None, None, 45786662, 1508242, 1027274, 468659, 11916906, 3548861, None, None, None, None, 1847537, 73739223],
    [8042406, 81618, 1426248, 43868081, 1738651, 872866, 444806, 10327291, 3721847, None, None, None, None, None, 70523813],
    [48042038, None, 39155202, 290986883, 8904465, 4706097, 7501882, 538354, 23602886, 533800, 51000, 1149197, 695508, 10247102, 436114414],
    [40014179, None, 41877112, 270859351, 10472408, 5256802, 7683449, 411771, 22557916, 534800, 46000, 1138416, 609755, 10855589, 412317549],
    [-793290, None, None, -30131645, -6436141, None, -384563, -111000, -31000, None, None, None, None, None, -37887639],
    [-563890, None, None, -27150691, -5547075, None, -362063, -111000, -31000, None, None, None, None, None, -33765719],
    [1000307, None, 409844, 9646564, 988151, 1874811, None, None, None, None, None, None, None, None, 13919676],
    [854852, None, 443952, 9062562, 955418, 1470107, None, None, None, None, None, None, None, None, 12786891],
    [8322701, None, 7407414, None, None, 10224352, None, None, None, None, None, None, None, None, 25954467],
    [8322701, None, 7474376, None, None, 9964659, None, None, None, None, None, None, None, None, 25761736],
    [None, 7112430, None, 7249987, None, None, None, None, None, None, None, None, None, None, 14362417],
    [None, 7335402, None, 7085804, None, None, None, None, None, None, None, None, None, None, 14421206],
    [None, None, None, 3355664, None, 13506, None, None, None, None, None, None, None, None, 3369170],
    [None, None, None, 1493061, None, 2222, None, None, None, None, None, None, None, None, 1495283],
], rows=_R_COMAR_15)

VERIFIED = {
    ("AMI", 2019): _AMI_2019, ("AMI", 2020): _AMI_2020, ("AMI", 2023): _AMI_2023,
    ("COTUNACE", 2017): _COT_2017, ("COTUNACE", 2019): _COT_2019,
    ("COTUNACE", 2023): _COT_2023,
    ("LLOYD_TUNISIEN", 2021): _LL_2021, ("LLOYD_TUNISIEN", 2022): _LL_2022,
    ("COMAR", 2017): _CM_2017, ("COMAR", 2019): _CM_2019, ("COMAR", 2023): _CM_2023,
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
