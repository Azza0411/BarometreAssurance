"""Tests unitaires des briques pures d'api/services/anomalies_service.py :
_enrich, _quality_score, et l'historique réel (build_anomalies_systeme, avec
build_pipeline_audit et get_quality_score_history mockés)."""

import api.services.anomalies_service as anomalies_service
from api.services.anomalies_service import _enrich, _quality_score


# ─── _enrich (couvre notamment la nouvelle étape 7) ─────────────────────────

def test_enrich_etape7_balance():
    p = {
        "code": "GAT", "annee": 2018, "kpi": "Total actif", "etape": 7,
        "gravite": "erreur", "raison": "Total actif ≠ Capitaux propres + Passif (écart 66,442,769 TND)",
        "composantes_manquantes": [],
    }
    enriched = _enrich(p)
    assert enriched["type"] == "Cohérence des données"
    assert enriched["dq_gravite"] == "Élevée"
    assert "GAT" in enriched["recommandation"]


def test_enrich_unknown_etape_falls_back():
    p = {"code": "X", "annee": 2024, "kpi": "K", "etape": 99, "composantes_manquantes": []}
    enriched = _enrich(p)
    assert enriched["type"] == "Inconnu"
    assert enriched["dq_gravite"] == "Faible"


# ─── _quality_score ──────────────────────────────────────────────────────────

def test_quality_score_no_problems_is_100():
    assert _quality_score([]) == 100.0


def test_quality_score_decreases_with_problems():
    problemes = [{"etape": 1}, {"etape": 6}]  # Critique + Elevee
    score = _quality_score(problemes, n_kpis_total=200)
    assert 0 <= score < 100.0


# ─── historique réel vs repli ────────────────────────────────────────────────

def test_historique_uses_persisted_points(monkeypatch):
    monkeypatch.setattr(
        anomalies_service, "get_quality_score_history",
        lambda conn, annee=None: [
            {"date": "2026-07-24T02:00:00", "score": 82.5, "n_anomalies": 40},
            {"date": "2026-07-31T02:00:00", "score": 88.0, "n_anomalies": 25},
        ],
    )
    monkeypatch.setattr(anomalies_service, "build_pipeline_audit", lambda conn, annee: {"problemes": [], "compagnies_affectees": []})
    monkeypatch.setattr(anomalies_service.os.path, "isdir", lambda path: False)

    result = anomalies_service.build_anomalies_systeme(None, 2024)
    assert len(result["historique"]) == 2
    assert result["historique"][0]["score"] == 82.5
    assert result["historique"][1]["label"] == "31/07"


def test_historique_falls_back_to_today_when_nothing_persisted(monkeypatch):
    monkeypatch.setattr(anomalies_service, "get_quality_score_history", lambda conn, annee=None: [])
    monkeypatch.setattr(anomalies_service, "build_pipeline_audit", lambda conn, annee: {"problemes": [], "compagnies_affectees": []})
    monkeypatch.setattr(anomalies_service.os.path, "isdir", lambda path: False)

    result = anomalies_service.build_anomalies_systeme(None, 2024)
    assert len(result["historique"]) == 1
    assert result["historique"][0]["score"] == 100.0
