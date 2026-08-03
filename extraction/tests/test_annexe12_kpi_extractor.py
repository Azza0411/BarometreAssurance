"""Tests de extraction/annexe12_kpi_extractor.py : détection de la page cible
(Vie uniquement — l'inverse d'annexe13, qui couvre Non-Vie et les tables
combinées)."""

from extraction.annexe12_kpi_extractor import _is_target_page
from extraction.tests.conftest import FakePage


def test_accepts_vie_page():
    page = FakePage("Resultat technique par categorie d'assurance Vie\n", words=[])
    assert _is_target_page(page) is True


def test_rejects_non_vie_page():
    page = FakePage("Resultat technique par categorie d'assurance Non Vie\n", words=[])
    assert _is_target_page(page) is False


def test_rejects_combined_table_without_vie_qualifier():
    # à la différence d'annexe13 (qui accepte cette page), l'Annexe 12 exige
    # explicitement la présence du mot "vie" (ex: COMAR, sans activité Vie
    # propre, n'a pas de page Vie du tout à détecter ici)
    page = FakePage("Resultat technique par categorie d'assurance\n", words=[])
    assert _is_target_page(page) is False


def test_rejects_unrelated_page():
    page = FakePage("Bilan Actif\n", words=[])
    assert _is_target_page(page) is False


def test_accepts_raccordement_vie_page():
    page = FakePage("Tableau de raccordement du resultat technique par categorie d'assurance Vie\n", words=[])
    assert _is_target_page(page) is True
