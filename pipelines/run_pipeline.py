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
    if isinstance(result, dict) and "ok" in result and "total" in result:
        # Grille complète (tableau_pipeline_service_*.process_all) : {"total",
        # "ok", "partiel", "page_introuvable", "pdf_absent", "erreur"} - le
        # nombre de documents "traités avec au moins un résultat" (ok +
        # partiel) est plus parlant ici que le total brut de la table
        # documents (qui inclut les PDF jamais téléchargés localement).
        return result["ok"] + result.get("partiel", 0)
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


def _run_bilan_full():
    """Grille complète Bilan Actif/Passif (tableau_cellules) — nécessite les
    PDF CMF déjà présents localement (voir _save_cmf_pdf_local, appelé par
    _run_cmf juste avant dans SOURCES) : toujours placé APRÈS "CMF" pour
    qu'un document tout juste synchronisé soit déjà sur disque."""
    from api.services.tableau_pipeline_service_bilan import process_all
    return process_all()


def _run_annexe12_full():
    from api.services.tableau_pipeline_service_annexe12 import process_all
    return process_all()


def _run_annexe13_full():
    from api.services.tableau_pipeline_service import process_all
    return process_all()


def _run_takaful_surplus_full():
    from api.services.tableau_pipeline_service_takaful_surplus import process_all
    return process_all()


def _run_takaful_resultat_full():
    from api.services.tableau_pipeline_service_takaful_resultat import process_all
    return process_all()


def _run_takaful_ventilation_full():
    from api.services.tableau_pipeline_service_takaful_ventilation import process_all
    return process_all()


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
    # Grilles complètes (tableau_cellules, Correction manuelle) — ajoutées
    # 2026-09-15 : avant cela, RIEN ne les relançait automatiquement sur un
    # document tout juste synchronisé par "CMF" ci-dessus (seule
    # l'extraction KPI narrow, kpi_values, était rafraîchie par le pipeline
    # planifié ; la grille complète restait figée tant que quelqu'un ne
    # relançait pas process_all() à la main). Chacune est une entrée SOURCE
    # séparée (pas un seul appel groupé) pour la même raison que
    # FTUSA/CGA/INS/BVMT ci-dessous : une régression dans l'une ne doit
    # jamais empêcher les autres de tourner.
    ("Bilan (grille complète)", _run_bilan_full),
    ("Annexe 12 (grille complète)", _run_annexe12_full),
    ("Annexe 13 (grille complète)", _run_annexe13_full),
    ("Takaful Surplus (grille complète)", _run_takaful_surplus_full),
    ("Takaful Résultat entreprise (grille complète)", _run_takaful_resultat_full),
    ("Takaful Ventilation (grille complète)", _run_takaful_ventilation_full),
    ("FTUSA", _run_ftusa),
    ("CGA", _run_cga),
    ("INS", _run_ins),
    ("BVMT", _run_bvmt),
]

# Noms (doivent correspondre exactement à SOURCES ci-dessus) des sources
# RÉELLEMENT utilisées par les 3 pages prioritaires — Aperçu marché (Profil
# pays + Distribution des agences, Conventionnelle ET Takaful), Analyse
# comparative, Vue par assurance — voir l'audit du 2026-09-16 (CMF, déjà
# séquentiel en premier, inclut l'extraction Takaful narrow des 3 sociétés
# Takaful-extractibles, donc les DEUX familles sont déjà couvertes sans
# entrée séparée ici). Les 6 grilles complètes restantes n'alimentent QUE
# "Correction manuelle" (tableau_cellules) — jamais ces 3 pages — donc
# reportées après, pour rendre la plateforme utilisable plus tôt (retour
# utilisateur direct, insistant : "on va restreindre notre terrain de
# travail... et prioriser les données qui vont nous servir à calculer les
# KPI qui vont être affichés" sur ces 3 pages).
PRIORITY_SOURCE_NAMES = {"FTUSA", "CGA", "INS", "BVMT"}


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


def _run_veille():
    """Scrape actualités + veille réglementaire et détecte les nouveautés
    depuis le dernier passage (voir api.routes.veille.sync_new_items /
    database.repository.diff_and_mark_*). Wrapper séparé du reste du
    pipeline (pas dans SOURCES) : ce n'est pas une source de données KPI,
    juste un déclencheur de notification - une erreur ici ne doit jamais
    faire échouer le pipeline principal."""
    try:
        from api.routes.veille import sync_new_items
        return sync_new_items()
    except Exception as exc:
        _log_json("veille_sync_failed", error=str(exc))
        return {"actualites": [], "reglementation": []}


def _save_notifications(results, failed_sources, quality, veille=None):
    """Persiste des notifications in-app (cloche de la barre de navigation)
    pour les événements jugés dignes d'attention utilisateur : nouveau
    document (toutes sources), anomalie qualité critique (extraction KPI
    totalement vide sur une source), échec d'une source après tous les
    essais, nouvelle(s) actualité(s)/texte(s) réglementaire(s).
    N'interrompt jamais le pipeline : une erreur ici est journalisée et
    ignorée, comme _check_quality()."""
    try:
        from database.repository import get_connection, save_notification
        conn = get_connection()
        try:
            for name, ok, _duration, doc_count, kpi_count in results:
                if ok and doc_count:
                    save_notification(
                        conn, "nouveau_document",
                        f"{doc_count} nouveau(x) document(s) {name}",
                        f"Le pipeline a détecté {doc_count} nouveau(x) document(s) {name} non encore en base.",
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
            if veille:
                nouvelles_actus = veille.get("actualites") or []
                if nouvelles_actus:
                    titres = "; ".join(a["titre"] for a in nouvelles_actus[:3])
                    suffixe = f" (dont : {titres}…)" if len(nouvelles_actus) > 3 else f" : {titres}"
                    save_notification(
                        conn, "nouvelle_actualite",
                        f"{len(nouvelles_actus)} nouvelle(s) actualité(s)",
                        f"{len(nouvelles_actus)} nouvel(les) article(s) détecté(s) depuis le dernier passage"
                        f"{suffixe}",
                        gravite="info", lien="/actualites-seminaires",
                    )
                nouveaux_regls = veille.get("reglementation") or []
                if nouveaux_regls:
                    titres = "; ".join(r["titre"] for r in nouveaux_regls[:3])
                    suffixe = f" (dont : {titres}…)" if len(nouveaux_regls) > 3 else f" : {titres}"
                    save_notification(
                        conn, "nouvelle_reglementation",
                        f"{len(nouveaux_regls)} nouveau(x) texte(s) réglementaire(s)",
                        f"{len(nouveaux_regls)} nouveau(x) document(s) détecté(s) depuis le dernier passage"
                        f"{suffixe}",
                        gravite="info", lien="/veille-reglementaire",
                    )
        finally:
            conn.close()
    except Exception as exc:
        _log_json("notifications_save_failed", error=str(exc))


def check_and_notify_veille():
    """Point d'entrée léger réutilisable par l'API elle-même (voir
    api/app.py::_start_veille_watcher), indépendant de la tâche planifiée
    Windows du pipeline complet. Constaté 2026-08-22 (retour utilisateur) :
    la tâche planifiée (mode "Interactive uniquement", voir limite déjà
    documentée dans docs/pfe_phase_documentation.md) n'avait tout simplement
    JAMAIS tourné une seule fois depuis son enregistrement
    (`Get-ScheduledTaskInfo` -> LastRunTime = date par défaut Windows,
    signifiant "jamais exécutée") - de vraies actualités publiées le jour
    même ne généraient donc aucune notification, quelle que soit la
    fiabilité du code de détection lui-même (déjà vérifié à 5 niveaux lors
    de la construction de la fonctionnalité).

    Ne fait QUE la veille (actualités/réglementation), pas la collecte CMF
    complète (téléchargement de PDF, plus lourde, réservée au pipeline
    planifié via schtasks) - couvre spécifiquement le symptôme signalé.
    Le cache 1h de sync_new_items()/_scrape_ilboursa (_CACHE_TTL) borne déjà
    la fréquence réelle des vraies requêtes réseau, donc un appel plus
    fréquent que 1h ici ne re-scrape pas inutilement."""
    veille = _run_veille()
    _save_notifications([], [], None, veille)
    return veille


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


def _classify_result(name, ok, result, failed_sources, empty_sources):
    doc_count = _extract_doc_count(result) if ok else None
    kpi_count = _extract_kpi_count(result) if ok else None
    if not ok:
        failed_sources.append(name)
        return doc_count, kpi_count
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
    return doc_count, kpi_count


def _run_parallel_batch(sources, results, failed_sources, empty_sources):
    """Exécute un lot de sources en parallèle et fusionne leurs résultats
    dans `results`, ré-ordonnés selon `sources` (pas l'ordre d'achèvement,
    non déterministe) pour que le rapport HTML reste lisible/stable d'une
    exécution à l'autre. Factorisée pour être appelée deux fois par
    main() — une fois pour les sources prioritaires, une fois pour les
    grilles complètes reportées (voir PRIORITY_SOURCE_NAMES)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    parallel_results = {}
    with ThreadPoolExecutor(max_workers=min(len(sources), 6)) as pool:
        futures = {pool.submit(run_with_retry, name, func): name for name, func in sources}
        for future in as_completed(futures):
            name = futures[future]
            parallel_results[name] = future.result()
    for name, _func in sources:
        ok, result, duration = parallel_results[name]
        doc_count, kpi_count = _classify_result(name, ok, result, failed_sources, empty_sources)
        results.append((name, ok, duration, doc_count, kpi_count))


def main():
    from pipelines.control import clear_cancel, is_cancel_requested
    from pipelines.progress import set_phase, clear_phase, mark_quick_ready, clear_quick_ready

    started_at = datetime.now()
    _log_json("pipeline_start")
    clear_cancel()  # une éventuelle annulation d'un run précédent ne doit jamais affecter celui-ci
    clear_quick_ready()  # un run précédent ne doit jamais faire croire la plateforme "prête" avant celui-ci

    results = []
    failed_sources = []
    empty_sources = []
    cancelled = False

    # "CMF" reste SEQUENTIEL et en premier : c'est la seule dépendance
    # réelle entre sources — les 6 pipelines grille complète (Bilan,
    # Annexe 12/13, Takaful) lisent les PDF que CMF vient de sauvegarder
    # localement (voir extraction/kpi_extraction_pipeline.py
    # ::_save_cmf_pdf_local).
    #
    # Les sources restantes sont scindées en 2 lots, EXÉCUTÉS L'UN APRÈS
    # L'AUTRE (pas un seul gros lot parallèle comme avant le 2026-09-16) :
    #   1. PRIORITAIRE (FTUSA/CGA/INS/BVMT) : seules sources, avec CMF,
    #      réellement lues par Aperçu marché/Analyse comparative/Vue par
    #      assurance (voir PRIORITY_SOURCE_NAMES) — une fois ce lot fini,
    #      la plateforme a tout ce qu'il faut pour ces 3 pages.
    #   2. REPORTÉ (les 6 grilles complètes) : n'alimentent QUE
    #      "Correction manuelle" (tableau_cellules), jamais ces 3 pages —
    #      continuent en arrière-plan après le signal "prêt", sans jamais
    #      retarder l'utilisabilité de la plateforme (retour utilisateur
    #      direct, insistant : la plateforme doit être utilisable même si
    #      "le scraping du reste des données n'est pas encore terminé").
    cmf_name, cmf_func = SOURCES[0]
    priority_sources = [s for s in SOURCES[1:] if s[0] in PRIORITY_SOURCE_NAMES]
    deferred_sources = [s for s in SOURCES[1:] if s[0] not in PRIORITY_SOURCE_NAMES]

    if is_cancel_requested():
        cancelled = True
    else:
        ok, result, duration = run_with_retry(cmf_name, cmf_func)
        doc_count, kpi_count = _classify_result(cmf_name, ok, result, failed_sources, empty_sources)
        results.append((cmf_name, ok, duration, doc_count, kpi_count))

    if not cancelled and is_cancel_requested():
        _log_json("pipeline_cancelled", remaining_source=priority_sources[0][0])
        cancelled = True

    if not cancelled:
        set_phase("sources_prioritaires")
        _run_parallel_batch(priority_sources, results, failed_sources, empty_sources)
        # Signal "prêt" : CMF (5 ans, 24 sociétés, Takaful narrow inclus) +
        # FTUSA/CGA/INS/BVMT sont là — tout ce dont Aperçu marché/Analyse
        # comparative/Vue par assurance ont besoin. Émis même si une de
        # ces sources a échoué (voir failed_sources) : ne jamais bloquer
        # indéfiniment le signal "prêt" sur une panne isolée.
        mark_quick_ready()

    if not cancelled and is_cancel_requested():
        _log_json("pipeline_cancelled", remaining_source=deferred_sources[0][0])
        cancelled = True

    if not cancelled:
        set_phase("grilles")
        _run_parallel_batch(deferred_sources, results, failed_sources, empty_sources)

    # Annulée : on saute les étapes annexes (qualité/veille), pas la peine de
    # les faire porter sur un jeu de sources incomplet.
    if not cancelled:
        set_phase("qualite")
    quality = _check_quality() if not cancelled else None
    if not cancelled:
        set_phase("veille")
    veille = _run_veille() if not cancelled else None
    if not cancelled:
        _save_notifications(results, failed_sources, quality, veille)
    ended_at = datetime.now()
    report_path = _write_html_report(results, quality, started_at, ended_at)
    clear_phase()

    _log_json(
        "pipeline_end",
        failed_sources=failed_sources,
        empty_sources=empty_sources,
        report=report_path,
        duration_s=round((ended_at - started_at).total_seconds(), 1),
        cancelled=cancelled,
    )
    print(f"\nRapport : {report_path}")

    if cancelled:
        return 2
    if failed_sources:
        _notify_failure(failed_sources)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
