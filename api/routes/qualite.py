"""Route /api/rapport-qualite + /api/pdf-local + /api/pdf-sections."""

import os
from flask import Blueprint, jsonify, send_file, abort, request
from database.repository import get_connection, get_available_years
from api.utils.formatters import required_year_arg, kpis_by_year
from api.services.quality import build_quality_report
from api.services.pipeline_audit import build_pipeline_audit
from api.services.pdf_sections import get_pdf_sections, _cache as _pdf_cache
from api.services.pdf_cell_coords import get_cell_coords
from api.services.sector_pdf_cell_coords import get_sector_cell_coords
from api.services.arabic_pdf_cell_coords import get_arabic_cell_coords, COMPANY_CODE as _ARABIC_COMPANY_CODE
from api.services.anomalies_service import build_anomalies_systeme, generate_rapport_ia
from api.routes.apercu_marche import _takaful_sector_snapshot
from api.utils.formatters import PRIMES_UNIT_DIVISOR
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


@bp.route("/api/sector-kpi-value")
def sector_kpi_value():
    """Valeurs brutes des KPI sectoriels (FTUSA/CGA/INS, pas de société
    associée) pour une année — pendant sectoriel de `kpi_detail[code].kpis_raw`
    (voir /api/rapport-qualite) qui, lui, ne couvre que les sociétés CMF.
    Ajouté le 2026-08-19 pour que KpiDetail.jsx puisse résoudre la valeur des
    KPI "secteur" (Population, PIB, Total Primes marché, ratios techniques
    marché...) avec exactement la même mécanique extrait/calculé que les KPI
    société, sur demande explicite de l'utilisateur ("on ne peut pas voir la
    source des KPI sectoriels").

    GET /api/sector-kpi-value?annee=2024
    → {"Total Primes émises": 4181..., "Population Totale": 11..., ...}
    Fusion FTUSA+CGA+INS : les trois référentiels de noms de KPI ne se
    recoupent pas (vérifié dans extraction/*_kpi_extractor.py), donc aucune
    collision possible en les fusionnant dans un seul dict.
    """
    annee = required_year_arg()
    conn = get_connection()
    try:
        merged = {}
        for source in ("FTUSA", "CGA", "INS"):
            merged.update(kpis_by_year(conn, source).get(annee, {}))

        # KPI sectoriels TAKAFUL (Total des contributions, Taux de
        # pénétration, Densité d'assurance) : absents des sources FTUSA/CGA/
        # INS ci-dessus (agrégat CMF, voir _takaful_sector_snapshot), donc
        # jusqu'ici invisibles pour KpiDetail — le bouton "Voir le document
        # source" affichait à tort, sur la bannière Aperçu Marché en vue
        # Takaful, la formule/source CONVENTIONNELLE (FTUSA) alors que le
        # chiffre affiché venait réellement de cet agrégat CMF. Calculées ici
        # avec exactement la même formule que apercu_marche_profil_pays
        # (dont c'est le seul autre point de calcul) pour ne jamais diverger.
        snap = _takaful_sector_snapshot(conn, annee)
        pib = merged.get("Produit Interieur Brut (PIB)")
        population = merged.get("Population Totale")
        total = snap["total"]
        total_mdt = total / PRIMES_UNIT_DIVISOR if total is not None else None
        merged["Total des contributions Takaful"] = total
        if total_mdt is not None and pib:
            merged["Taux de pénétration Takaful"] = total_mdt / pib * 100
        if total is not None and population:
            merged["Densité de l'assurance Takaful"] = total / population

        return jsonify(merged)
    finally:
        conn.close()


@bp.route("/api/annees-disponibles")
def annees_disponibles():
    """Années présentes en base pour une source donnée (défaut CMF), bornées
    à la plage validée 2014-2025.

    GET /api/annees-disponibles?source=CMF → {"annees": [2025, 2024, ..., 2014]}
    Utilisé par les sélecteurs d'année (Qualité Data, Anomalies Système,
    KpiDetail, Analyse Comparative) pour rester cohérents entre eux — plage
    bornée manuellement plutôt que la plage brute disponible en base, pour ne
    jamais exposer une année dont les données n'ont pas encore été jugées
    fiables pour l'affichage.

    Plafond relevé de 2024 à 2025 le 2026-08-16 : les 223 documents CMF 2025
    sont désormais extraits et leurs KPI dérivés recalculés correctement
    (voir extraction/CAS_PARTICULIERS_CALCULS.md, bug de lecture
    auto-référentielle corrigé) — seule "Part de marché (%)" reste
    systématiquement absente pour 2025 (total sectoriel FTUSA pas encore
    publié, pas un problème d'extraction CMF), déjà signalé explicitement
    côté frontend (AnalyseComparative.jsx) plutôt que de bloquer toute
    l'année.
    """
    source = request.args.get("source", "CMF").strip().upper()
    conn = get_connection()
    try:
        years = [y for y in get_available_years(conn, source) if 2014 <= y <= 2025]
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


@bp.route("/api/sector-pdf-cell")
def sector_pdf_cell():
    """
    Équivalent sectoriel de /api/pdf-cell-coords : pour un KPI FTUSA/CGA
    (Population, PIB n'ont pas de PDF — voir kpiMeta.js, INS exclu). Pas de
    paramètre `page` en entrée (contrairement à la version CMF) : la page
    n'est pas connue à l'avance côté frontend pour ces documents, elle est
    déterminée ici (voir sector_pdf_cell_coords.py).

    GET /api/sector-pdf-cell?source=FTUSA&annee=2024&ligne=Primes%20émises&colonne=TOTAL%20(AFF.%20DIR%20+%20ACC)
    → { found: true, page, x0, y0, x1, y1, page_width, page_height }
    → { found: false, reason, page }  (page peut être non-null même en échec,
      si la page a été déterminée mais pas la cellule précise)
    """
    source  = request.args.get("source",  "").strip()
    annee   = request.args.get("annee",   "").strip()
    ligne   = request.args.get("ligne",   "").strip()
    colonne = request.args.get("colonne", "").strip()

    if not all([source, annee, ligne, colonne]):
        abort(400, "Paramètres requis : source, annee, ligne, colonne")

    try:
        annee_int = int(annee)
    except ValueError:
        abort(400, "annee doit être un entier")

    coords, reason = get_sector_cell_coords(source, annee_int, ligne, colonne)
    if coords is None:
        return jsonify({"found": False, **reason}), 200
    return jsonify({"found": True, **coords})


@bp.route("/api/arabic-pdf-cell")
def arabic_pdf_cell():
    """
    Équivalent AL_AMANAH_TAKAFUL (PDF en arabe) de /api/pdf-cell-coords : le
    `ligne`/`colonne` de kpiMeta.js (français) ne s'applique pas à ce
    document, donc pas de paramètre `page`/`ligne`/`colonne` en entrée —
    juste le KPI par sa clé de stockage (ex: "Total actif"), la recherche
    RTL et la page étant déterminées ici (voir arabic_pdf_cell_coords.py).
    Portée limitée aux 4 KPI "primaires" (Total actif, Capitaux propres,
    Résultat Net, Primes émises par assurance) ; PDF non disponible en
    surlignage sur les pages scannées (page seule, voir raison).

    GET /api/arabic-pdf-cell?code=AL_AMANAH_TAKAFUL&annee=2024&kpi=Total%20actif
    → { found: true, page, x0, y0, x1, y1, page_width, page_height }
    → { found: false, reason, page }  (page peut être non-null même en échec)
    """
    code  = request.args.get("code",  "").strip().upper()
    annee = request.args.get("annee", "").strip()
    kpi   = request.args.get("kpi",   "").strip()

    if code != _ARABIC_COMPANY_CODE:
        abort(400, f"Source non prise en charge : {code}")
    if not all([annee, kpi]):
        abort(400, "Paramètres requis : annee, kpi")

    try:
        annee_int = int(annee)
    except ValueError:
        abort(400, "annee doit être un entier")

    conn = get_connection()
    try:
        coords, reason = get_arabic_cell_coords(conn, annee_int, kpi)
    finally:
        conn.close()
    if coords is None:
        return jsonify({"found": False, **reason}), 200
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
