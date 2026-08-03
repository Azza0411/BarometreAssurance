"""Tests unitaires des briques pures d'api/services/quality.py (comparaison
sectorielle, formatage). build_quality_report lui-même dépend fortement de
la base MySQL (conn) et n'est pas testé ici — ce sont les fonctions isolables
qui le sont."""

from api.services.quality import _fmt, _sector_peer_anomalies, PROBLEMATIC_CODES


# ─── _fmt ────────────────────────────────────────────────────────────────────

def test_fmt_none():
    assert _fmt(None) is None


def test_fmt_millions():
    assert _fmt(2_500_000) == "2.50 M TND"


def test_fmt_thousands():
    assert _fmt(1_500) == "1,500 TND"


def test_fmt_small():
    assert _fmt(12.345) == "12.35"


# ─── _sector_peer_anomalies ──────────────────────────────────────────────────

def _detail(rc):
    return {"rc_final": rc, "pdf_local": True, "pdf_lien": None, "pdf_nom": None}


def test_peer_comparison_flags_outlier():
    kpi_detail = {
        "STAR": _detail(85.0), "COMAR": _detail(90.0), "GAT": _detail(95.0),
        "ASTREE": _detail(88.0), "BH": _detail(92.0),
        "OUTLIER": _detail(12.0),  # très en dessous de la moyenne du groupe
    }
    anomalies = _sector_peer_anomalies(kpi_detail, 2024)
    codes = {a["code"] for a in anomalies}
    assert "OUTLIER" in codes
    assert "STAR" not in codes


def test_peer_comparison_requires_minimum_group_size():
    kpi_detail = {"STAR": _detail(85.0), "COMAR": _detail(5.0)}  # 2 societes seulement
    assert _sector_peer_anomalies(kpi_detail, 2024) == []


def test_peer_comparison_ignores_missing_values():
    kpi_detail = {
        "STAR": _detail(85.0), "COMAR": _detail(90.0), "GAT": _detail(95.0),
        "ASTREE": _detail(88.0), "BH": {"rc_final": None, "pdf_local": True, "pdf_lien": None, "pdf_nom": None},
    }
    # Seulement 4 valeurs presentes < seuil minimal -> aucun signalement
    assert _sector_peer_anomalies(kpi_detail, 2024) == []


# ─── PROBLEMATIC_CODES ────────────────────────────────────────────────────────

def test_problematic_codes_have_individual_reasons():
    # Chaque societe exclue doit avoir sa propre raison (pas un texte
    # generique partage par les 8, corrige en juillet 2026).
    assert len(PROBLEMATIC_CODES) == 8
    assert len({reason for reason in PROBLEMATIC_CODES.values()}) >= 3
    assert all(isinstance(reason, str) and reason for reason in PROBLEMATIC_CODES.values())
