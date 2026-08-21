"""Tests unitaires des briques bas-niveau de bilan_kpi_extractor : regroupement
de mots en lignes, parsing des nombres (formats FR/US, négatifs entre
parenthèses/chevrons, nombres "collés"), et sélection de la colonne "année en
cours". Ce sont les fonctions les plus denses en cas particuliers réels (voir
le module et extraction/CAS_PARTICULIERS.md) — testées ici sur des mots
synthétiques, sans dépendre d'un vrai PDF."""

from extraction.bilan_kpi_extractor import (
    _cluster_lines,
    _extract_numeric_clusters,
    _find_capitaux_propres,
    _find_section_total,
    _is_actif_page,
    _label_text,
    _section_code,
    _select_column_value,
    _split_glued_negative,
    _words_with_bracket_negatives_resolved,
)
from extraction.tests.conftest import FakePDF, FakePage, W


# ─── _cluster_lines ────────────────────────────────────────────────────────

def test_cluster_lines_groups_by_vertical_tolerance():
    words = [
        W("Total", 0, top=100),
        W("actif", 30, top=102),   # même ligne visuelle (écart <= 5)
        W("Total", 0, top=115),    # nouvelle ligne (écart > 5)
        W("passif", 30, top=114),
    ]
    lines = _cluster_lines(words)
    assert len(lines) == 2
    assert [w["text"] for w in lines[0]] == ["Total", "actif"]
    assert [w["text"] for w in lines[1]] == ["Total", "passif"]


def test_cluster_lines_sorts_words_left_to_right():
    words = [W("B", 50, top=100), W("A", 0, top=100)]
    lines = _cluster_lines(words)
    assert [w["text"] for w in lines[0]] == ["A", "B"]


# ─── _extract_numeric_clusters ─────────────────────────────────────────────

def test_thousands_separated_by_space_join_into_one_number():
    # "350 104" : deux tokens PDF proches (séparateur de milliers) -> un seul nombre
    line = [W("350", 0, top=100, width=20), W("104", 22, top=100, width=20)]
    values = _extract_numeric_clusters(line)
    assert values == [(350104.0, 0)]


def test_distant_numbers_form_separate_clusters():
    line = [W("100", 0, top=100, width=20), W("200", 80, top=100, width=20)]
    values = _extract_numeric_clusters(line)
    assert [v for v, _ in values] == [100.0, 200.0]


def test_french_decimal_comma():
    line = [W("113,026", 0, top=100)]
    values = _extract_numeric_clusters(line)
    assert values[0][0] == 113.026


def test_us_thousands_and_decimal_point():
    line = [W("13,966,819.225", 0, top=100)]
    values = _extract_numeric_clusters(line)
    assert values[0][0] == 13966819.225


def test_implausibly_large_value_is_rejected():
    line = [W("999999999999999", 0, top=100)]
    assert _extract_numeric_clusters(line) == []


def test_bracket_negative_astree_style():
    # "< 2 094 225>" (ASTREE) — tokens PDF proches (séparateur de milliers)
    line = [W("<2", 0, top=100, width=14), W("094", 16, top=100, width=14), W("225>", 32, top=100)]
    resolved = _words_with_bracket_negatives_resolved(line)
    values = _extract_numeric_clusters(resolved)
    assert values[0][0] == -2094225.0


def test_parenthesis_negative_gat_style():
    # "(84 334 072)" (GAT)
    line = [W("(84", 0, top=100, width=14), W("334", 16, top=100, width=14), W("072)", 32, top=100)]
    resolved = _words_with_bracket_negatives_resolved(line)
    values = _extract_numeric_clusters(resolved)
    assert values[0][0] == -84334072.0


def test_glued_negative_number_is_split():
    # "104-1" = fin d'un nombre "...350 104" suivie du début de "-1 144..."
    word = W("104-1", 0, top=100)
    split = _split_glued_negative(word)
    assert [w["text"] for w in split] == ["104", "-1"]
    # l'écart forcé entre les deux moitiés dépasse le seuil -> 2 clusters distincts
    values = _extract_numeric_clusters(split)
    assert [v for v, _ in values] == [104.0, -1.0]


# ─── _label_text / _section_code ───────────────────────────────────────────

def test_label_text_strips_row_code_prefix():
    line = [W("AC332", 0, top=100), W("Obligations", 40, top=100), W("100", 200, top=100)]
    assert _label_text(line) == "obligations"


def test_label_text_none_when_only_numbers():
    line = [W("100", 0, top=100), W("200", 40, top=100)]
    assert _label_text(line) is None


def test_section_code_detects_valid_section_title():
    line = [W("AC3", 0, top=100), W("Placements", 30, top=100)]
    assert _section_code(line) == ("ac", "3")


def test_section_code_rejects_bare_code_without_label():
    # ex: COMAR répète "AC1" seul sur la ligne de total de la section -> pas
    # un nouveau titre de section (voir docstring de _section_code)
    line = [W("AC1", 0, top=100), W("100", 40, top=100)]
    assert _section_code(line) is None


# ─── _select_column_value ──────────────────────────────────────────────────

def test_passif_side_picks_leftmost_column():
    clusters = [(4000.0, 10), (3800.0, 60)]
    assert _select_column_value(clusters, lines=[], target_top=100, header_token=None) == 4000.0


def test_passif_side_skips_footnote_number_column():
    # première colonne = numéro de note de bas de page (ex: COTUNACE)
    clusters = [(3.0, 10), (5000.0, 60)]
    assert _select_column_value(clusters, lines=[], target_top=100, header_token=None) == 5000.0


def test_actif_side_picks_second_to_last_column_up_to_4_cols():
    # [brut, amortissements, net_annee_courante, net_annee_precedente]
    clusters = [(5000.0, 10), (1000.0, 60), (4000.0, 110), (3800.0, 160)]
    assert _select_column_value(clusters, lines=[], target_top=100, header_token="net") == 4000.0


def test_actif_side_beyond_4_cols_uses_header_position():
    header_line = [W("Net", 200, top=50)]
    data_top = 100
    # 6 colonnes (brut/amort/net pour année courante ET précédente) : la
    # position ordinale devient ambiguë, on résout via l'en-tête "Net"
    clusters = [(1000.0, 10), (2000.0, 60), (3000.0, 110), (4000.0, 210), (5000.0, 260), (6000.0, 310)]
    lines = [header_line]
    result = _select_column_value(clusters, lines, target_top=data_top, header_token="net")
    # la colonne dont le x0 (210) est le plus proche du x0 de l'en-tête "Net" (200)
    assert result == 4000.0


# ─── _find_section_total ───────────────────────────────────────────────────

def _actif_page(lines_words_by_top):
    words = [w for words in lines_words_by_top for w in words]
    return FakePage(text="ACTIF\n", words=words)


def test_find_section_total_reads_total_from_section_title_line():
    # Convention GAT : le total de la section est directement sur sa ligne de titre
    header = [W("AC3", 0, top=100), W("Placements", 30, top=100),
              W("5000", 200, top=100), W("1000", 250, top=100),
              W("4000", 300, top=100), W("3800", 350, top=100)]
    next_section = [W("AC4", 0, top=200), W("Placements", 30, top=200),
                     W("representant", 100, top=200)]
    page = _actif_page([header, next_section])
    pdf = FakePDF(pages=[page])

    value = _find_section_total(pdf, "ac", "3", "net")
    assert value == 4000.0


def test_find_section_total_takes_last_numeric_line_before_next_section():
    # Convention STAR/COMAR : titre de section sans chiffres, total sur la
    # DERNIÈRE ligne de sous-élément avant la section suivante
    header = [W("AC3", 0, top=100), W("Placements", 30, top=100)]
    sub1 = [W("AC31", 0, top=110), W("Obligations", 30, top=110),
            W("100000", 200, top=110), W("20000", 250, top=110),
            W("80000", 300, top=110), W("75000", 350, top=110)]
    sub2 = [W("AC32", 0, top=120), W("Actions", 30, top=120),
            W("50000", 200, top=120), W("10000", 250, top=120),
            W("40000", 300, top=120), W("38000", 350, top=120)]
    total = [W("150000", 200, top=130), W("30000", 250, top=130),
             W("120000", 300, top=130), W("113000", 350, top=130)]
    next_section = [W("AC4", 0, top=140), W("Placements", 30, top=140),
                     W("representant", 100, top=140)]
    page = _actif_page([header, sub1, sub2, total, next_section])
    pdf = FakePDF(pages=[page])

    value = _find_section_total(pdf, "ac", "3", "net")
    assert value == 120000.0  # ligne de total (derniere ligne a chiffres avant AC4), avant-derniere colonne


def test_find_section_total_ignores_trailing_subitem_with_no_total_line():
    # Decouvert le 2026-08-18 sur MAGHREBIA_VIE 2025 : certains documents ne
    # portent AUCUNE ligne de total pour la section, juste une liste plate
    # de sous-elements. Prendre "la derniere ligne a chiffres" retournait
    # alors un sous-element quelconque (souvent petit) au lieu du plus
    # proche de la vraie grandeur. On retient desormais le MAXIMUM des
    # candidats de la plage : un vrai total (s'il existe) est toujours le
    # plus grand par construction, et a defaut, le plus grand sous-element
    # reste une valeur bien moins trompeuse que le dernier de la liste.
    header = [W("AC3", 0, top=100), W("Placements", 30, top=100)]
    sub1 = [W("AC31", 0, top=110), W("Obligations", 30, top=110),
            W("100000", 200, top=110), W("20000", 250, top=110),
            W("80000", 300, top=110), W("75000", 350, top=110)]
    sub2 = [W("AC32", 0, top=120), W("Actions", 30, top=120),
            W("50000", 200, top=120), W("10000", 250, top=120),
            W("40000", 300, top=120), W("38000", 350, top=120)]
    next_section = [W("AC4", 0, top=130), W("Placements", 30, top=130),
                     W("representant", 100, top=130)]
    page = _actif_page([header, sub1, sub2, next_section])
    pdf = FakePDF(pages=[page])

    value = _find_section_total(pdf, "ac", "3", "net")
    assert value == 80000.0  # plus grand sous-element (AC31), pas le dernier liste (AC32=40000)


# ─── _is_actif_page ─────────────────────────────────────────────────────────

def test_is_actif_page_detects_marker_beyond_default_5_line_window():
    # Cas BIAT 2025 : bandeau d'en-tête de 5 lignes avant "ACTIFS Brut Amort.
    # Net Net" (ligne 6) -> une fenêtre lines_checked=5 la manque entièrement
    # et la page entière (donc "Total actif") devient introuvable.
    text = (
        "Assurances BIAT\n"
        "Bilan\n"
        "Arrete au 31/12/2025\n"
        "Unite : en dinars\n"
        "Exercice clos le 31/12/2025\n"
        "ACTIFS Brut Amort. Net Net\n"
    )
    page = FakePage(text=text, words=[])
    assert _is_actif_page(page) is True


def test_is_actif_page_still_bounded_past_widened_window():
    # La fenetre elargie (20, cf. bilan_kpi_extractor.py) reste une fenetre :
    # un marqueur trop tardif (ligne 21) ne doit toujours pas etre detecte
    # comme page Actif. Seuil mis a jour le 2026-08-17 (10->20, motif STAR/
    # BIAT/ASTREE/MAGHREBIA_VIE/GAT_VIE 2015) ; ce test verifiait encore
    # l'ancien seuil 10 et echouait donc a tort (ligne 11 est desormais dans
    # la fenetre valide).
    text = "\n".join([f"ligne bruit {i}" for i in range(20)] + ["ACTIFS Brut Amort. Net Net"])
    page = FakePage(text=text, words=[])
    assert _is_actif_page(page) is False


# ─── _find_capitaux_propres ─────────────────────────────────────────────────

def test_find_capitaux_propres_prefers_avant_affectation_over_avant_resultat():
    # Cas BIAT 2025 : le document a les deux lignes. "avant resultat" est
    # une valeur INTERMEDIAIRE (avant d'ajouter le resultat de l'exercice en
    # cours) ; "avant affectation" est le vrai total final. Utiliser la
    # premiere ligne trouvee textuellement (l'intermediaire) sous-estimait
    # les capitaux propres de exactement le montant du resultat de
    # l'exercice (103 137 732 au lieu de 128 786 575), gonflant le ROE affiche.
    avant_resultat = [
        W("Total", 0, top=100), W("capitaux", 50, top=100), W("propres", 110, top=100),
        W("avant", 170, top=100), W("resultat", 220, top=100), W("de", 280, top=100),
        W("l'exercice", 300, top=100), W("103137732", 400, top=100),
    ]
    resultat_exercice = [
        W("CP6", 0, top=110), W("Resultat", 50, top=110), W("de", 110, top=110),
        W("l'exercice", 140, top=110), W("25648843", 400, top=110),
    ]
    avant_affectation = [
        W("Total", 0, top=120), W("capitaux", 50, top=120), W("propres", 110, top=120),
        W("avant", 170, top=120), W("affectation", 220, top=120), W("128786575", 400, top=120),
    ]
    words = avant_resultat + resultat_exercice + avant_affectation
    page = FakePage(text="Passif\n", words=words)
    pdf = FakePDF(pages=[page])

    assert _find_capitaux_propres(pdf) == 128786575.0


def test_find_capitaux_propres_falls_back_to_avant_resultat_when_no_affectation_line():
    # Documents sans ligne "avant affectation" distincte (le "avant resultat"
    # est alors deja le total final) : ne doit pas renvoyer None.
    avant_resultat = [
        W("Total", 0, top=100), W("capitaux", 50, top=100), W("propres", 110, top=100),
        W("avant", 170, top=100), W("resultat", 220, top=100), W("de", 280, top=100),
        W("l'exercice", 300, top=100), W("50000000", 400, top=100),
    ]
    page = FakePage(text="Passif\n", words=avant_resultat)
    pdf = FakePDF(pages=[page])

    assert _find_capitaux_propres(pdf) == 50000000.0
