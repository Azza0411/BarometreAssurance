"""Route /api/rapport-qualite + /api/pdf-local + /api/pdf-sections."""

import os
from flask import Blueprint, jsonify, send_file, abort, request
from database.repository import get_connection, get_available_years
from api.utils.formatters import required_year_arg
from api.services.quality import build_quality_report
from api.services.pipeline_audit import build_pipeline_audit
from api.services.pdf_sections import get_pdf_sections, _cache as _pdf_cache
from api.services.pdf_cell_coords import get_cell_coords
from api.services.anomalies_service import build_anomalies_systeme, generate_rapport_ia
from extraction.kpi_definitions import get_formule, get_context, CONTEXT_LABELS

bp = Blueprint("qualite", __name__)

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "cmf"
)
_DATA_ROOT = os.path.dirname(_DATA_DIR)

# Sources sectorielles (pas de société associée) dont le PDF est persisté par
# extraction/kpi_extraction_pipeline.py::_run_ftusa/_run_cga, sous
# data/<source>/<SOURCE>_<annee>.pdf. INS n'a volontairement pas d'entrée
# ici : ce n'est pas une source PDF (API/HTML de séries statistiques), donc
# aucun fichier ne peut exister pour elle — /api/pdf-local renverra 404,
# ce qui est le comportement honnête plutôt qu'une erreur de code.
_SECTORAL_SOURCES = {"FTUSA", "CGA"}


@bp.route("/api/rapport-qualite")
def rapport_qualite():
    annee = required_year_arg()
    conn  = get_connection()
    try:
        rapport = build_quality_report(conn, annee)
        return jsonify(rapport)
    finally:
        conn.close()


@bp.route("/api/annees-disponibles")
def annees_disponibles():
    """Années présentes en base pour une source donnée (défaut CMF), bornées
    à la plage validée 2014-2024.

    GET /api/annees-disponibles?source=CMF → {"annees": [2024, 2023, ..., 2014]}
    Utilisé par les sélecteurs d'année (Qualité Data, Anomalies Système,
    KpiDetail, Analyse Comparative) pour rester cohérents entre eux — plage
    fixée à 2014-2024 (décidé avec l'utilisateur), pas la plage brute
    disponible en base qui peut contenir des années plus récentes non
    encore validées pour affichage.
    """
    source = request.args.get("source", "CMF").strip().upper()
    conn = get_connection()
    try:
        years = [y for y in get_available_years(conn, source) if 2014 <= y <= 2024]
        return jsonify({"annees": years})
    finally:
        conn.close()


@bp.route("/api/pdf-local")
def pdf_local():
    """Sert un PDF en affichage inline (pas en téléchargement).

    CMF (par société) : GET /api/pdf-local?code=STAR&annee=2024
    Sources sectorielles (FTUSA, CGA — pas de société) :
      GET /api/pdf-local?source=FTUSA&annee=2024
    INS n'a pas de PDF (source API/HTML) : renvoie 404, comportement
    attendu plutôt qu'une erreur — voir _SECTORAL_SOURCES.
    """
    source = request.args.get("source", "CMF").strip().upper()
    code   = request.args.get("code", "").strip().upper()
    annee  = request.args.get("annee", "").strip()

    if not annee:
        abort(400, "Paramètre 'annee' requis")
    if "/" in annee or "\\" in annee or ".." in annee:
        abort(400, "Année invalide")

    if source == "CMF":
        if not code:
            abort(400, "Paramètre 'code' requis pour la source CMF")
        if "/" in code or "\\" in code or ".." in code:
            abort(400, "Code invalide")
        path = os.path.join(_DATA_DIR, code, f"{code}_{annee}.pdf")
        download_name = f"{code}_{annee}.pdf"
    elif source in _SECTORAL_SOURCES:
        path = os.path.join(_DATA_ROOT, source.lower(), f"{source}_{annee}.pdf")
        download_name = f"{source}_{annee}.pdf"
    else:
        abort(400, f"Source inconnue ou sans PDF : {source}")

    if not os.path.isfile(path):
        abort(404, f"PDF introuvable : {download_name}")

    return send_file(
        path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=download_name,
    )


@bp.route("/api/kpi-definition")
def kpi_definition():
    """Retourne la définition de formule d'un KPI, contextualisée par compagnie.

    GET /api/kpi-definition?kpi=Ratio+combiné+(%)&code=ASTREE
    → {expr, note, chercher, composantes, contexte, contexte_label}
    """
    kpi  = request.args.get("kpi",  "").strip()
    code = request.args.get("code", "").strip().upper()

    if not kpi:
        abort(400, "Paramètre 'kpi' requis")

    formule = get_formule(kpi, code or None)
    if formule is None:
        abort(404, f"KPI inconnu : {kpi}")

    ctx = get_context(code) if code else "mixte"
    return jsonify({
        **formule,
        "contexte":        ctx,
        "contexte_label":  CONTEXT_LABELS.get(ctx, ctx),
    })


@bp.route("/api/pdf-sections")
def pdf_sections():
    """Retourne les numéros de page (1-indexed) des grandes sections d'un PDF CMF.

    GET /api/pdf-sections?code=STAR&annee=2024
    → {"annexe12": 14, "annexe13": 21, "bilan": 5, "etat_resultat": 8}
    """
    code  = request.args.get("code", "").strip().upper()
    annee = request.args.get("annee", "").strip()

    if not code or not annee:
        abort(400, "Paramètres 'code' et 'annee' requis")
    if "/" in code or "\\" in code or ".." in code:
        abort(400, "Code invalide")

    try:
        annee_int = int(annee)
    except ValueError:
        abort(400, "Paramètre 'annee' invalide")

    sections = get_pdf_sections(code, annee_int)
    return jsonify(sections)


@bp.route("/api/pdf-cell-coords")
def pdf_cell_coords():
    """
    Retourne les coordonnées PDF d'une cellule précise.

    GET /api/pdf-cell-coords?code=STAR&annee=2024&page=31&ligne=Primes%20émises&colonne=Total
    → { found: true, x0, y0, x1, y1, page_width, page_height }  (coordonnées PDF, origine bas-gauche)
    → { found: false, reason }  si introuvable — reason permet au frontend d'afficher un
      message précis (ligne_introuvable, colonne_introuvable, pdf_manquant...) au lieu
      de laisser l'absence de surlignage sans explication.
    """
    code    = request.args.get("code",    "").strip().upper()
    annee   = request.args.get("annee",   "").strip()
    page    = request.args.get("page",    "").strip()
    ligne   = request.args.get("ligne",   "").strip()
    colonne = request.args.get("colonne", "").strip()

    if not all([code, annee, page, ligne, colonne]):
        abort(400, "Paramètres requis : code, annee, page, ligne, colonne")
    if "/" in code or "\\" in code or ".." in code:
        abort(400, "Code invalide")

    try:
        annee_int = int(annee)
        page_int  = int(page)
    except ValueError:
        abort(400, "annee et page doivent être des entiers")

    coords, reason = get_cell_coords(code, annee_int, page_int, ligne, colonne)
    if coords is None:
        return jsonify({"found": False, "reason": reason}), 200
    return jsonify({"found": True, **coords})


@bp.route("/api/pdf-sections/clear-cache", methods=["POST"])
def pdf_sections_clear_cache():
    """Vide le cache en mémoire des sections PDF (utile après un correctif de patterns)."""
    _pdf_cache.clear()
    return jsonify({"ok": True, "message": "Cache vidé"})


@bp.route("/api/anomalies-systeme")
def anomalies_systeme():
    """Données enrichies pour la page Anomalies Système.

    GET /api/anomalies-systeme?annee=2024
    """
    annee = required_year_arg()
    conn  = get_connection()
    try:
        data = build_anomalies_systeme(conn, annee)
        return jsonify(data)
    finally:
        conn.close()


@bp.route("/api/rapport-ia")
def rapport_ia():
    """Génère un rapport IA structuré (markdown) pour une année donnée.

    GET /api/rapport-ia?annee=2024
    → { rapport: "# Rapport..." }
    """
    annee = required_year_arg()
    conn  = get_connection()
    try:
        md = generate_rapport_ia(conn, annee)
        return jsonify({"rapport": md})
    finally:
        conn.close()


@bp.route("/api/rapport-pipeline")
def rapport_pipeline():
    """Audit complet du pipeline extraction → KPI pour une année donnée.

    GET /api/rapport-pipeline?annee=2024
    → { annee, n_problemes, par_gravite, par_etape, par_kpi, par_compagnie, problemes[] }
    """
    annee = required_year_arg()
    conn  = get_connection()
    try:
        rapport = build_pipeline_audit(conn, annee)
        return jsonify(rapport)
    finally:
        conn.close()
