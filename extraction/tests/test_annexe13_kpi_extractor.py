"""Tests de extraction/annexe13_kpi_extractor.py : détection de la page cible
(Non-Vie / table combinée, en excluant les pages Vie pures) et extraction de
la valeur "Total" d'une ligne, y compris quand elle est répartie sur les
sous-lignes suivantes (forward scan)."""

from extraction.annexe13_kpi_extractor import (
    KPI_PATTERNS,
    _find_total_value,
    _is_target_page,
    extract_annexe13_kpis,
)
from extraction.tests.conftest import FakePDF, FakePage, W


# ─── _is_target_page ───────────────────────────────────────────────────────

def test_accepts_non_vie_page():
    page = FakePage("Resultat technique par categorie d'assurance Non Vie\n", words=[])
    assert _is_target_page(page) is True


def test_accepts_raccordement_page():
    page = FakePage("Tableau de raccordement du resultat technique par categorie\n", words=[])
    assert _is_target_page(page) is True


def test_accepts_combined_table_without_vie_qualifier():
    # ex: MAGHREBIA, table combinée Vie/Non-Vie sans distinction
    page = FakePage("Resultat technique par categorie d'assurance\n", words=[])
    assert _is_target_page(page) is True


def test_rejects_pure_vie_page():
    # domaine de l'Annexe 12, pas de l'Annexe 13
    page = FakePage("Resultat technique par categorie d'assurance Vie\n", words=[])
    assert _is_target_page(page) is False


def test_rejects_unrelated_page():
    page = FakePage("Bilan Actif\n", words=[])
    assert _is_target_page(page) is False


# ─── _find_total_value / extract_annexe13_kpis ─────────────────────────────

def _make_pdf():
    title = "Tableau de raccordement du resultat technique par categorie d'assurance Non Vie\n"
    row_primes = [W("Primes", 0, top=100), W("emises", 30, top=100), W("125000", 200, top=100)]
    row_resultat = [W("Resultat", 0, top=110), W("technique", 40, top=110), W("45000", 200, top=110)]
    words = row_primes + row_resultat
    page = FakePage(title, words)
    return FakePDF(pages=[page])


def test_find_total_value_reads_inline_value():
    pdf = _make_pdf()
    value = _find_total_value(pdf, KPI_PATTERNS["Primes émises Non-Vie par assurance"])
    assert value == 125000.0


def test_find_total_value_returns_none_when_absent():
    pdf = _make_pdf()
    value = _find_total_value(pdf, KPI_PATTERNS["Primes acquises"])
    assert value is None


def test_extract_annexe13_kpis_returns_all_keys():
    pdf = _make_pdf()
    result = extract_annexe13_kpis(pdf)
    assert set(result.keys()) == set(KPI_PATTERNS.keys())
    assert result["Primes émises Non-Vie par assurance"] == 125000.0
    assert result["Résultat technique Non-Vie"] == 45000.0
    assert result["Primes acquises"] is None


def test_forward_scan_accumulates_sub_lines_until_section_stop():
    # En-tête de section sans total inline (ex: COMAR/CARTE) : le total est
    # la somme des sous-lignes jusqu'au prochain marqueur de section.
    title = "Resultat technique par categorie d'assurance Non Vie\n"
    header = [W("Charges", 0, top=100), W("de", 30, top=100), W("prestations", 45, top=100)]
    sub1 = [W("Sinistres", 0, top=110), W("payes", 40, top=110), W("10000", 200, top=110)]
    sub2 = [W("Sinistres", 0, top=120), W("a", 40, top=120), W("payer", 50, top=120), W("5000", 200, top=120)]
    stop = [W("Solde", 0, top=130), W("de", 30, top=130), W("souscription", 45, top=130)]
    words = header + sub1 + sub2 + stop
    pdf = FakePDF(pages=[FakePage(title, words)])

    value = _find_total_value(pdf, KPI_PATTERNS["Charges de prestations Non-Vie"])
    assert value == 15000.0
