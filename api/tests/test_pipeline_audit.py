"""Tests unitaires des briques pures d'api/services/pipeline_audit.py :
_sections_inferees (pure) et _persisted_anomalies_as_problemes (DB mockée via
monkeypatch — pas de vraie connexion nécessaire)."""

import api.services.pipeline_audit as pipeline_audit
from api.services.pipeline_audit import _sections_inferees


# ─── _sections_inferees ──────────────────────────────────────────────────────

def test_sections_inferees_detects_present_section():
    kpis = {"Total actif": 1000.0, "Capitaux propres": 500.0}
    sections = _sections_inferees(kpis)
    assert sections["bilan"] is True
    assert sections["annexe12"] is False


def test_sections_inferees_all_absent():
    sections = _sections_inferees({})
    assert all(ok is False for ok in sections.values())


# ─── _persisted_anomalies_as_problemes ──────────────────────────────────────

def test_persisted_anomalies_converted_to_etape7(monkeypatch):
    mock_anomaly = {
        "id": 1, "detected_at": "2026-07-31T10:00:00", "source": "extraction_balance",
        "code": "GAT", "annee": 2018, "kpi": "Total actif", "gravite": "erreur",
        "details": {"total_actif": 492955073.689, "ecart": 66442769.278},
    }
    monkeypatch.setattr(pipeline_audit, "get_anomalies", lambda conn, annee=None: [mock_anomaly])
    monkeypatch.setattr(pipeline_audit, "get_document_meta", lambda conn, code, annee: ("GAT_2018.pdf", "http://x"))
    monkeypatch.setattr(pipeline_audit, "_pdf_ok", lambda code, annee: True)

    problemes = pipeline_audit._persisted_anomalies_as_problemes(None, 2018)
    assert len(problemes) == 1
    p = problemes[0]
    assert p["etape"] == 7
    assert p["code"] == "GAT"
    assert p["gravite"] == "erreur"
    assert "66,442,769" in p["raison"]


def test_persisted_anomalies_filters_unknown_sources(monkeypatch):
    # Une source non reconnue (ex: "quality_score_snapshot", pas une
    # anomalie individuelle) ne doit jamais devenir un probleme etape 7.
    mock_anomaly = {
        "id": 2, "detected_at": "2026-07-31T02:00:00", "source": "quality_score_snapshot",
        "code": None, "annee": 2024, "kpi": None, "gravite": "info",
        "details": {"score": 88.0},
    }
    monkeypatch.setattr(pipeline_audit, "get_anomalies", lambda conn, annee=None: [mock_anomaly])
    assert pipeline_audit._persisted_anomalies_as_problemes(None, 2024) == []


def test_persisted_anomalies_empty_when_no_anomalies(monkeypatch):
    monkeypatch.setattr(pipeline_audit, "get_anomalies", lambda conn, annee=None: [])
    assert pipeline_audit._persisted_anomalies_as_problemes(None, 2024) == []
