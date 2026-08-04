"""
Orchestrateur du pipeline de collecte/extraction, destine a etre lance par
Task Scheduler (Windows) ou cron (Linux) via run_pipeline.bat / run_pipeline.sh.

Pour chaque source (CMF, FTUSA, CGA, INS, BVMT) :
  - jusqu'a 3 tentatives avec backoff exponentiel (2s, 4s, 8s) en cas d'echec,
  - une source en echec n'interrompt pas les suivantes,
  - le resultat (ok/echec, duree, nb documents) est journalise en JSON Lines
    (logs/pipeline.log, rotation quotidienne sur 14 jours) et affiche console.

A la fin : verification qualite (api.services.quality.build_quality_report)
sur la derniere annee CMF disponible, puis generation d'un rapport HTML
d'execution dans reports/pipeline_run_<horodatage>.html.

Si PIPELINE_ALERT_WEBHOOK est defini (URL Slack incoming-webhook ou
compatible), un message y est poste en cas d'echec d'au moins une source.
"""

import os
import sys
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pipeline_logging import get_logger, log_json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

logger = get_logger("pipeline")


def _log_json(event: str, **fields):
    log_json(logger, event, **fields)


def _extract_doc_count(result):
    """Normalise le resultat heterogene des sources en nombre de documents.

    La plupart des sources renvoient directement un int (nb documents
    enregistres). CMF renvoie {"sync": {societe: nb, ...}, "kpi": ...} :
    on somme les compteurs par societe. Renvoie None si la forme est
    inconnue (le compte ne peut alors pas etre affiche, mais ce n'est pas
    traite comme une erreur)."""
    if isinstance(result, int):
        return result
    if isinstance(result, dict) and isinstance(result.get("sync"), dict):
        return sum(v for v in result["sync"].values() if isinstance(v, int))
    return None


def _extract_kpi_count(result):
    """Pour la source CMF uniquement : result["kpi"] est le dict renvoye par
    extraction.kpi_extraction_pipeline.run(), qui execute en realite
    l'extraction KPI de CMF + FTUSA + BVMT + BVMT bulletin + CGA, puis la
    modelisation (KPI calcules) en une seule passe (voir ce module). Renvoie
    le total de valeurs de KPI enregistrees toutes ces sous-pipelines
    confondues, ou None pour les autres sources (rien a extraire, juste des
    metadonnees de document synchronisees)."""
    if not isinstance(result, dict) or not isinstance(result.get("kpi"), dict):
        return None
    kpi = result["kpi"]
    total = kpi.get("kpi_values_saved") or 0
    for sub_source in ("ftusa", "bvmt", "bvmt_bulletin", "cga"):
        total += (kpi.get(sub_source) or {}).get("kpi_values_saved") or 0
    total += kpi.get("calculated_kpi_values_saved") or 0
    return total


def run_with_retry(name, func, max_attempts=3, base_delay=2):
    """Execute `func()` avec jusqu'a `max_attempts` tentatives (backoff x2).

    Renvoie (ok, resultat_ou_exception, duree_s). Un succes avec 0 document
    est journalise a part ("source_empty") : ok=True (ce n'est pas forcement
    une panne, une source peut legitimement n'avoir rien de nouveau), mais
    visible distinctement d'un succes normal pour ne pas masquer une
    regression silencieuse (site change de structure sans lever d'erreur)."""
    for attempt in range(1, max_attempts + 1):
        start = time.monotonic()
        try:
            result = func()
            duration = time.monotonic() - start
            doc_count = _extract_doc_count(result)
            if doc_count == 0:
                _log_json("source_empty", source=name, attempt=attempt, duration_s=round(duration, 1))
            else:
                _log_json(
                    "source_ok", source=name, attempt=attempt,
                    duration_s=round(duration, 1), nb_documents=doc_count,
                )
            return True, result, duration
        except Exception as exc:
            duration = time.monotonic() - start
            _log_json(
                "source_failed", source=name, attempt=attempt, max_attempts=max_attempts,
                duration_s=round(duration, 1), error=str(exc),
            )
            if attempt < max_attempts:
                delay = base_delay * (2 ** (attempt - 1))
                time.sleep(delay)
    return False, None, 0.0


def _run_cmf():
    from pipelines.cmf_pipeline import main as cmf_main
    return cmf_main()


def _run_ftusa():
    from scraping.ftusa_scraper import sync_documents
    return sync_documents()


def _run_cga():
    from scraping.cga_scraper import sync_documents
    return sync_documents()


def _run_ins():
    from scraping.ins_scraper import sync_all
    return sync_all()


def _run_bvmt():
    from scraping.bvmt_scraper import sync_all
    return sync_all()


SOURCES = [
    ("CMF", _run_cmf),
    ("FTUSA", _run_ftusa),
    ("CGA", _run_cga),
    ("INS", _run_ins),
    ("BVMT", _run_bvmt),
]


def _check_quality():
    """Verifie la completude des KPI sur la derniere annee CMF disponible, et
    persiste un instantane du score qualite (table anomalies_detectees,
    source="quality_score_snapshot") pour alimenter un historique reel de
    tendance dans le temps (voir api/services/anomalies_service.py -
    build_anomalies_systeme - et database/repository.py::get_quality_score_history).
    Avant juillet 2026, ce point etait recalcule a chaque affichage de page
    sans jamais etre conserve : aucune tendance n'etait possible.
    N'interrompt jamais le pipeline : une erreur ici est journalisee et ignoree."""
    try:
        from database.repository import get_connection, list_documents_by_source, save_anomaly
        from api.services.anomalies_service import build_anomalies_systeme

        conn = get_connection()
        years = [
            annee for _doc_id, _cmf_id, _code, annee in list_documents_by_source(conn, "CMF")
            if annee
        ]
        if not years:
            return None
        annee = max(years)
        rapport = build_anomalies_systeme(conn, annee)
        kpis = rapport.get("kpis", {})
        save_anomaly(
            conn, source="quality_score_snapshot", gravite="info", annee=annee,
            details={
                "score": kpis.get("score_qualite"),
                "n_anomalies": kpis.get("n_anomalies"),
                "documents_analyses": kpis.get("documents_analyses"),
            },
        )
        conn.close()
        return {
            "annee": annee,
            "total_companies": kpis.get("documents_analyses"),
            "nb_anomalies": kpis.get("n_anomalies"),
            "score_qualite": kpis.get("score_qualite"),
        }
    except Exception as exc:
        _log_json("quality_check_failed", error=str(exc))
        return None


def _save_notifications(results, failed_sources, quality):
    """Persiste des notifications in-app (cloche de la barre de navigation)
    pour les trois événements jugés dignes d'attention utilisateur : nouveau
    document CMF, anomalie qualité critique (extraction KPI totalement
    vide sur une source), échec d'une source après tous les essais.
    N'interrompt jamais le pipeline : une erreur ici est journalisée et
    ignorée, comme _check_quality()."""
    try:
        from database.repository import get_connection, save_notification
        conn = get_connection()
        try:
            for name, ok, _duration, doc_count, kpi_count in results:
                if name == "CMF" and ok and doc_count:
                    save_notification(
                        conn, "nouveau_document",
                        f"{doc_count} nouveau(x) document(s) CMF",
                        f"Le pipeline a détecté {doc_count} nouveau(x) rapport(s) CMF non encore en base.",
                        gravite="info", lien="/rapport-pipeline",
                    )
                if name == "CMF" and ok and kpi_count == 0:
                    save_notification(
                        conn, "anomalie_critique",
                        "Extraction KPI CMF totalement vide",
                        "Aucune valeur de KPI extraite sur l'ensemble de l'historique CMF — "
                        "signe presque certain d'une régression (extracteur cassé, structure PDF changée).",
                        gravite="critique", lien="/rapport-pipeline",
                    )
            for name in failed_sources:
                save_notification(
                    conn, "echec_pipeline", f"Échec de la source {name}",
                    f"La source {name} a échoué après plusieurs tentatives. Voir le rapport d'exécution.",
                    gravite="critique", lien="/rapport-pipeline",
                )
            if quality and quality.get("score_qualite") is not None and quality["score_qualite"] < 50:
                save_notification(
                    conn, "anomalie_critique",
                    f"Score qualité faible : {quality['score_qualite']}/100",
                    f"{quality.get('nb_anomalies')} anomalie(s) détectée(s) pour l'exercice {quality.get('annee')}.",
                    gravite="avertissement", lien="/qualite-donnees",
                )
        finally:
            conn.close()
    except Exception as exc:
        _log_json("notifications_save_failed", error=str(exc))


def _notify_failure(failed_sources):
    webhook = os.environ.get("PIPELINE_ALERT_WEBHOOK")
    if not webhook:
        return
    try:
        import requests
        message = f"[FS Market Intelligence] Echec pipeline pour : {', '.join(failed_sources)}"
        requests.post(webhook, json={"text": message}, timeout=10)
    except Exception as exc:
        _log_json("notify_failed", error=str(exc))


def _write_html_report(results, quality, started_at, ended_at):
    ts = started_at.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORT_DIR, f"pipeline_run_{ts}.html")

    def _row(name, ok, duration, doc_count, kpi_count):
        if not ok:
            color, status = "#c00", "ECHEC"
        elif doc_count == 0 or kpi_count == 0:
            color, status = "#c80", "OK (0 document)" if doc_count == 0 else "OK (0 KPI extrait)"
        else:
            color, status = "#0a0", "OK"
        doc_display = "?" if doc_count is None else str(doc_count)
        kpi_display = "—" if kpi_count is None else str(kpi_count)
        return (
            f"<tr><td>{name}</td><td style='color:{color}'>{status}</td>"
            f"<td>{doc_display}</td><td>{kpi_display}</td><td>{duration:.1f}s</td></tr>"
        )

    rows = "\n".join(
        _row(name, ok, duration, doc_count, kpi_count)
        for name, ok, duration, doc_count, kpi_count in results
    )
    quality_html = (
        f"<p>Annee {quality['annee']} : {quality['total_companies']} document(s) analyse(s), "
        f"{quality['nb_anomalies']} anomalie(s) detectee(s), "
        f"score qualite {quality['score_qualite']}/100.</p>"
        if quality else "<p>Verification qualite non disponible (base inaccessible ou vide).</p>"
    )

    html = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>Rapport pipeline {ts}</title>
<style>
body {{ font-family: Segoe UI, Arial, sans-serif; margin: 2rem; color: #222; }}
h1 {{ color: #2E2E38; }}
table {{ border-collapse: collapse; width: 100%; max-width: 600px; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #2E2E38; color: #FFE600; }}
</style></head>
<body>
<h1>Rapport d'execution du pipeline</h1>
<p>Debut : {started_at.isoformat(timespec='seconds')} — Fin : {ended_at.isoformat(timespec='seconds')}
 — Duree totale : {(ended_at - started_at).total_seconds():.1f}s</p>
<table>
<tr><th>Source</th><th>Statut</th><th>Documents</th><th>Valeurs KPI</th><th>Duree</th></tr>
{rows}
</table>
<h2>Qualite des donnees</h2>
{quality_html}
</body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def main():
    started_at = datetime.now()
    _log_json("pipeline_start")

    results = []
    failed_sources = []
    empty_sources = []
    for name, func in SOURCES:
        ok, result, duration = run_with_retry(name, func)
        doc_count = _extract_doc_count(result) if ok else None
        kpi_count = _extract_kpi_count(result) if ok else None
        results.append((name, ok, duration, doc_count, kpi_count))
        if not ok:
            failed_sources.append(name)
            continue
        if doc_count == 0:
            empty_sources.append(name)
        if kpi_count == 0:
            # kpi_extraction_pipeline.run() traite TOUS les documents CMF deja
            # en base (pas seulement les nouveaux) : contrairement a
            # doc_count=0 (rien de nouveau a scraper, peut etre normal), 0
            # valeur de KPI extraite sur l'ensemble de l'historique trahit
            # presque toujours une vraie regression (ex: bibliotheque
            # d'extraction cassee), jamais une "semaine calme".
            empty_sources.append(f"{name} (extraction KPI)")
            _log_json("kpi_extraction_totally_empty", source=name)

    quality = _check_quality()
    _save_notifications(results, failed_sources, quality)
    ended_at = datetime.now()
    report_path = _write_html_report(results, quality, started_at, ended_at)

    _log_json(
        "pipeline_end",
        failed_sources=failed_sources,
        empty_sources=empty_sources,
        report=report_path,
        duration_s=round((ended_at - started_at).total_seconds(), 1),
    )
    print(f"\nRapport : {report_path}")

    if failed_sources:
        _notify_failure(failed_sources)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
