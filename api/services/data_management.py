"""Logique de la page "Gestion de base de données" : liste des documents
scrapés (avec résolution du fichier PDF réellement stocké en local), listes
d'options pour les filtres d'export, et génération de l'export Excel
flexible (n'importe quelle combinaison Tableau × Société × Année).

Séparé de excel_export.py (dédié à l'export figé "Analyse Comparative") —
ici l'export est un extrait BRUT de kpi_values (format long : une ligne par
valeur de KPI), pas une mise en page métier avec formules recalculables.
"""

import math
import os
import re

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.views import Selection
from openpyxl.drawing.image import Image as XLImage
from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
from openpyxl.drawing.xdr import XDRPositiveSize2D
import io

from database.repository import (
    get_connection, list_all_documents, get_tableau_cellules, get_document_id,
    get_cached_tableau_page, save_cached_tableau_page, TABLEAU_PAGE_MISS,
)
from extraction.annexe13_kpi_extractor import (
    _is_target_page as _is_annexe13_page,
    RACCORDEMENT_RE as _ANNEXE13_RACCORDEMENT_RE,
    KPI_PATTERNS as _ANNEXE13_KPI_PATTERNS,
)
from extraction.full_table_extractor import (
    locate_and_extract_full_table, relaxed_is_annexe13_page, relaxed_is_annexe12_page,
)
from extraction.annexe13_pipeline import normalize_table, CANONICAL_ROWS, CANONICAL_COLUMNS, derive_column_groups
from extraction.annexe12_kpi_extractor import (
    _is_target_page as _is_annexe12_page,
    _RACCORDEMENT_RE as _ANNEXE12_RACCORDEMENT_RE,
    KPI_PATTERNS as _ANNEXE12_KPI_PATTERNS,
)
from extraction.annexe12_pipeline import normalize_table_vie, CANONICAL_ROWS_VIE

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")

# Logos déjà présents dans le projet (frontend/public/logos, utilisés par la
# plateforme elle-même) — réutilisés tels quels pour l'export Excel plutôt
# que de dupliquer des assets. Mapping par code société car les noms de
# fichiers ne suivent pas exactement la convention des codes CMF.
_LOGO_DIR = os.path.join(_PROJECT_ROOT, "frontend", "public", "logos")
_LOGO_FILES = {
    "STAR": "STAR.png", "GAT": "GAT.png", "GAT_VIE": "GAT-vie.png",
    "COMAR": "COMAR.png", "ATTIJARI": "Attijari.png", "BH": "BH.png",
    "BIAT": "BIAT.png", "BNA": "BNA.png", "CARTE": "Carte.png",
    "CARTE_VIE": "Carte-Vie.png", "COTUNACE": "COTUNACE.png", "CTAMA": "CTAMA.png",
    "LLOYD_TUNISIEN": "LLOYD.png", "LLOYD_VIE": "LLOYD-Vie.png",
    "MAGHREBIA": "Maghrebia.png", "MAGHREBIA_VIE": "Maghrebia-Vie.png",
    "TUNIS_RE": "TunisRe.png", "UIB": "UIB.png", "AMI": "AMI.png",
    "ASTREE": "astree.png", "HAYETT": "hayett.png",
    "AT_TAKAFULIA": "At-Takafulia.png", "AL_AMANAH_TAKAFUL": "AlAmanaTakaful.png",
    "ZITOUNA_TAKAFUL": "Zitouna-Takaful.png",
}


def _logo_path(code):
    filename = _LOGO_FILES.get(code)
    if not filename:
        return None
    path = os.path.join(_LOGO_DIR, filename)
    return path if os.path.isfile(path) else None


def _excel_col_width_to_px(width, mdw=7):
    """Conversion largeur de colonne Excel (unités de caractère) → pixels —
    formule officielle documentée par Microsoft (pas une simple
    approximation linéaire) : Truncate(((256*width + Truncate(128/MDW))
    /256) * MDW), MDW = largeur du chiffre le plus large de la police par
    défaut (7px pour Calibri 11). Sert à centrer précisément le logo sur la
    largeur réelle du tableau (retour utilisateur : le titre du bloc doit
    être exactement en-dessous du logo, ce qui suppose que les deux soient
    calculés sur la MÊME largeur réelle, pas une valeur approchée)."""
    if not width:
        return 64
    return int(((256 * width + int(128 / mdw)) // 256) * mdw)


def _table_width_px(ws, start_col, end_col):
    """Largeur cumulée (pixels) des colonnes [start_col, end_col] — budget
    disponible pour le logo, ancré sur plusieurs colonnes plutôt qu'une
    seule pour lui laisser plus de place tout en restant dans la largeur
    réelle du tableau (jamais au-delà de sa dernière colonne)."""
    return sum(
        _excel_col_width_to_px(ws.column_dimensions[get_column_letter(c)].width)
        for c in range(max(start_col, 1), end_col + 1)
    )


def _centered_anchor(ws, row_idx, n_cols, image_width_px, image_height_px):
    """Ancre précise (colonne + décalage en pixels) pour centrer
    horizontalement une image sur la largeur du tableau (colonnes 1..n_cols),
    à la ligne `row_idx` (1-indexée) — un simple ancrage sur une colonne ne
    suffit pas pour un centrage exact, il faut aussi le décalage EN PIXELS
    à l'intérieur de cette colonne."""
    total_width = _table_width_px(ws, 1, n_cols)
    target_left = max((total_width - image_width_px) / 2, 0)
    cum = 0
    col, col_off_px = n_cols, 0
    for c in range(1, n_cols + 1):
        col_w = _excel_col_width_to_px(ws.column_dimensions[get_column_letter(c)].width)
        if cum + col_w > target_left:
            col, col_off_px = c, int(target_left - cum)
            break
        cum += col_w
    EMU_PER_PX = 9525
    marker = AnchorMarker(col=col - 1, colOff=col_off_px * EMU_PER_PX, row=row_idx - 1, rowOff=0)
    ext = XDRPositiveSize2D(cx=int(image_width_px * EMU_PER_PX), cy=int(image_height_px * EMU_PER_PX))
    return OneCellAnchor(_from=marker, ext=ext)


def _logo_dimensions(logo_path, target_height=48, max_width=110):
    """Taille (largeur, hauteur) en pixels pour l'export Excel — hauteur
    cible, largeur déduite du ratio RÉEL de l'image (les logos ne sont pas
    tous carrés) et plafonnée pour ne jamais empiéter sur le texte du
    bandeau. Allers-retours successifs (22→40→60→90px, tantôt trop petit,
    tantôt trop grand) : 48px, un point milieu plus sobre."""
    try:
        from PIL import Image as PILImage
        with PILImage.open(logo_path) as im:
            w, h = im.size
        width = w * (target_height / h)
        if width > max_width:
            return max_width, h * (max_width / w)
        return width, target_height
    except Exception:
        return target_height, target_height

# Sources dont chaque document correspond à un vrai fichier PDF stocké en
# local (téléchargé par le scraper), avec son schéma de chemin propre.
# BVMT/INS sont des scrapes de pages HTML (pas de PDF individuel) et ENQUETE
# vient d'un fichier Excel unique fourni par l'utilisateur — pour ces
# 3 sources, aucun fichier local par document : le lien externe reste la
# seule référence consultable.
def local_pdf_path(source_nom, code, nom_pdf):
    if source_nom == "CMF" and code:
        return os.path.join(_DATA_DIR, "cmf", code, nom_pdf)
    if source_nom == "FTUSA":
        return os.path.join(_DATA_DIR, "ftusa", nom_pdf)
    if source_nom == "CGA":
        return os.path.join(_DATA_DIR, "cga", nom_pdf)
    return None


def list_documents_for_ui(conn):
    """Liste tous les documents en base pour la page Gestion de données,
    avec un flag `fichier_local` (True si le PDF réellement scrapé est
    encore présent sur le disque, pas seulement référencé par son URL
    d'origine — c'est la distinction qui compte pour une page de gestion
    "locale" : l'URL externe peut avoir changé ou disparu depuis)."""
    rows = []
    for doc_id, source_nom, code, nom_entreprise, nom_pdf, annee, lien in list_all_documents(conn):
        local_path = local_pdf_path(source_nom, code, nom_pdf)
        rows.append({
            "id": doc_id,
            "source": source_nom,
            "code": code,
            "nom_entreprise": nom_entreprise,
            "nom_pdf": nom_pdf,
            "annee": annee,
            "lien": lien,
            "fichier_local": bool(local_path and os.path.isfile(local_path)),
        })
    return rows


def get_local_pdf_path_for_document(conn, document_id):
    """Résout le chemin local d'un document par son id, ou None si aucun
    fichier local n'existe pour ce document (source sans PDF individuel, ou
    fichier absent du disque). Utilisé par la route de téléchargement."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.nom, c.code, d.nom_pdf
            FROM documents d
            JOIN sources s ON s.id = d.source_id
            LEFT JOIN societes c ON c.id = d.cmf_id
            WHERE d.id = %s
            """,
            (document_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    source_nom, code, nom_pdf = row
    path = local_pdf_path(source_nom, code, nom_pdf)
    if path and os.path.isfile(path):
        return path
    return None


# ── Filtres d'export ────────────────────────────────────────────────────────
# Regroupement volontairement limité aux tableaux financiers CMF par
# compagnie (le cas d'usage explicite de cette fonctionnalité : "tous les
# Annexe 12 de toutes les compagnies", "tous les tableaux financiers d'une
# compagnie"...). Les autres sources (BVMT, CGA, FTUSA, INS, Enquête) ne
# sont pas rattachées à une compagnie CMF individuelle de la même façon et
# restent hors du périmètre de cet export flexible pour l'instant.
#
# Le regroupement doit composer avec une réalité déjà documentée (voir
# CAS_PARTICULIERS*.txt) : plusieurs extracteurs écrivent des libellés de
# "tableau" légèrement différents pour ce qui est conceptuellement la même
# annexe ("Annexe12" vs "Annexe 12 - Resultat technique Vie"...), et
# "Annexe 12/13" est parfois utilisé comme libellé combiné par un extracteur
# plus ancien — il est donc inclus dans les deux groupes Annexe 12 et
# Annexe 13 ci-dessous (limite connue : sélectionner "Annexe 12" seul peut
# ramener quelques lignes Non-Vie si le document source utilise ce libellé
# combiné, plutôt qu'une erreur silencieuse de filtrage).
TABLEAU_GROUPS = [
    ("annexe12", "Annexe 12 — Résultat technique Vie",
     ["Annexe12", "Annexe 12 - Resultat technique Vie", "Annexe 12/13"]),
    ("annexe13", "Annexe 13 — Résultat technique Non-Vie",
     ["Annexe13", "Annexe 13 - Resultat technique Non-Vie", "Annexe 12/13"]),
    # Actif et Passif sont deux tableaux DISTINCTS du PDF source (pages
    # différentes, totaux propres) — deux clés séparées plutôt qu'une
    # grille fusionnée, pour préserver cette structure côté Correction
    # manuelle. `raws=["Bilan"]` dupliqué sur les deux : le KPI narrow
    # historique (bilan_kpi_extractor.py, kpi_values) ne distingue pas
    # Actif/Passif, donc les deux groupes s'appuient sur la même présence
    # ; seule l'enrichissement `tableau_cellules` ci-dessous (tc.tableau=
    # 'bilan_actif'/'bilan_passif') les différencie réellement.
    # Pas de " — " dans ces deux libellés (contrairement aux groupes
    # ci-dessus) : le frontend (CorrectionManuelle.jsx) affiche
    # `label.split(" — ")[0]` comme texte d'onglet court — avec un tiret,
    # "Bilan — Actif" et "Bilan — Passif" ressortiraient IDENTIQUES
    # ("Bilan") une fois tronqués, rendant les deux onglets indistinguables.
    ("bilan_actif", "Bilan Actif", ["Bilan"]),
    ("bilan_passif", "Bilan Passif", ["Bilan"]),
    # "État de résultat" / "Ratios calculés (interne)" / "Présentation de la
    # société" retirés du sélecteur (2026-09-09, retour utilisateur direct)
    # — restent des libellés `tableau` réels dans kpi_values (un export
    # "tous les tableaux" sans filtre les inclut donc toujours), seulement
    # plus proposés comme filtre explicite.
    # Takaful (2026-09-15) : 5 clés `tableau_cellules` pour les 5 annexes
    # utilisées par le pipeline KPI narrow Takaful (voir
    # extraction/CAS_PARTICULIERS_TAKAFUL_SURPLUS.md). `raws` reprend les 2
    # libellés `kpi_values.tableau` réels de
    # extraction/kpi_extraction_pipeline.py::KPI_TABLE_LABEL — "Annexes
    # 3/4/5.1 - Fonds des Participants (Takaful)" est PARTAGÉ par 3 clés
    # tableau_cellules distinctes (Familial/Général/Entreprise, mêmes
    # raisons que bilan_actif/bilan_passif ci-dessus : le KPI narrow
    # historique ne distingue pas l'annexe d'origine, seule
    # `tableau_cellules` le fait réellement). PAS de " — " dans ces
    # libellés, même raison que Bilan Actif/Passif ci-dessus : le frontend
    # tronque sur ce séparateur pour le texte d'onglet, et les 5 libellés
    # commencent tous par "Takaful" — un " — " les rendrait tous
    # indistinguables une fois tronqués.
    ("takaful_surplus_familial", "Takaful Surplus Familial (Annexe 3)",
     ["Annexes 3/4/5.1 - Fonds des Participants (Takaful)"]),
    ("takaful_surplus_general", "Takaful Surplus Général (Annexe 4)",
     ["Annexes 3/4/5.1 - Fonds des Participants (Takaful)"]),
    ("takaful_resultat_entreprise", "Takaful État de résultat entreprise (Annexe 5.1)",
     ["Annexes 3/4/5.1 - Fonds des Participants (Takaful)"]),
    ("takaful_ventilation_familial", "Takaful Ventilation Familial (Annexe 14)",
     ["Annexes 14/15 - Ventilation par categorie d'assurance (Takaful)"]),
    ("takaful_ventilation_general", "Takaful Ventilation Général (Annexe 15)",
     ["Annexes 14/15 - Ventilation par categorie d'assurance (Takaful)"]),
]
_TABLEAU_GROUP_TO_RAW = {key: raws for key, _label, raws in TABLEAU_GROUPS}


def kpi_raw_labels_for(tableau):
    """Libellés bruts `kpi_values.tableau` correspondant à une clé
    `tableau_cellules` (ex. 'annexe12' -> ["Annexe12", "Annexe 12 - ...",
    "Annexe 12/13"]) — sert à retrouver, après une correction manuelle, le
    KPI narrow (kpi_values) qui pourrait représenter la même donnée que la
    cellule corrigée (voir database/repository.py::apply_manual_corrections,
    propagation par VALEUR plutôt que par nom — voir sa docstring)."""
    return _TABLEAU_GROUP_TO_RAW.get(tableau, [])


def get_filter_options(conn):
    """Options disponibles pour les 3 filtres de l'export flexible :
    sociétés CMF (code + nom), années CMF disponibles, groupes de tableaux,
    et `societes_par_tableau` — pour CHAQUE groupe de tableau, la liste des
    codes société qui ont RÉELLEMENT au moins un résultat pour ce tableau
    (tous documents/exercices confondus). Sert au frontend à désactiver dans
    le sélecteur une société qui n'a structurellement AUCUNE donnée pour le
    tableau choisi (ex. ATTIJARI/UIB pour Annexe 13 — sociétés Vie
    exclusivement, jamais de résultat Non-Vie à aucune année, voir
    extraction/annexe13_pipeline.ANNEXE13_NON_VIE_EXCLUSIONS) plutôt que de
    la laisser sélectionnable pour produire un export vide. Généralisé à
    TOUS les groupes de TABLEAU_GROUPS, pas seulement Annexe 13."""
    with conn.cursor() as cur:
        cur.execute("SELECT code, nom_entreprise FROM societes ORDER BY code")
        societes = [{"code": c, "nom": n} for c, n in cur.fetchall()]
        cur.execute(
            """
            SELECT DISTINCT d.annee FROM documents d
            JOIN sources s ON s.id = d.source_id
            WHERE s.nom = 'CMF'
            ORDER BY d.annee DESC
            """
        )
        annees = [row[0] for row in cur.fetchall()]

        societes_par_tableau = {key: set() for key, _label, _raws in TABLEAU_GROUPS}
        cur.execute(
            """
            SELECT DISTINCT c.code, k.tableau
            FROM kpi_values k
            JOIN documents d ON d.id = k.document_id
            JOIN sources s ON s.id = d.source_id
            JOIN societes c ON c.id = d.cmf_id
            WHERE s.nom = 'CMF'
            """
        )
        for code, raw in cur.fetchall():
            for key, raws in _TABLEAU_GROUP_TO_RAW.items():
                if raw in raws:
                    societes_par_tableau[key].add(code)
        # Annexe 13 grille complète (extraction/annexe13_pipeline.py) : une
        # source de vérité SÉPARÉE de kpi_values (tableau_cellules) — une
        # société peut y avoir un résultat que le sous-ensemble narrow 7-KPI
        # n'a pas (ou l'inverse), les deux comptent comme "a ce tableau".
        cur.execute(
            """
            SELECT DISTINCT c.code
            FROM tableau_cellules tc
            JOIN documents d ON d.id = tc.document_id
            JOIN sources s ON s.id = d.source_id
            JOIN societes c ON c.id = d.cmf_id
            WHERE s.nom = 'CMF' AND tc.tableau = 'annexe13'
            """
        )
        for (code,) in cur.fetchall():
            societes_par_tableau.setdefault("annexe13", set()).add(code)
        # Annexe 12 grille complète (extraction/annexe12_pipeline.py) — même
        # principe que l'Annexe 13 ci-dessus, source de vérité séparée de
        # kpi_values.
        cur.execute(
            """
            SELECT DISTINCT c.code
            FROM tableau_cellules tc
            JOIN documents d ON d.id = tc.document_id
            JOIN sources s ON s.id = d.source_id
            JOIN societes c ON c.id = d.cmf_id
            WHERE s.nom = 'CMF' AND tc.tableau = 'annexe12'
            """
        )
        for (code,) in cur.fetchall():
            societes_par_tableau.setdefault("annexe12", set()).add(code)
        # Bilan Actif / Passif grille complète (extraction/bilan_full_extractor.py)
        # — même principe, deux clés séparées (voir TABLEAU_GROUPS ci-dessus) :
        # sans ce bloc, la présence des onglets Bilan dans Correction manuelle ne
        # reposerait que sur le KPI narrow historique (kpi_values, tableau='Bilan'),
        # qui peut être vide alors que la grille complète existe (ou l'inverse).
        for cle in ("bilan_actif", "bilan_passif"):
            cur.execute(
                """
                SELECT DISTINCT c.code
                FROM tableau_cellules tc
                JOIN documents d ON d.id = tc.document_id
                JOIN sources s ON s.id = d.source_id
                JOIN societes c ON c.id = d.cmf_id
                WHERE s.nom = 'CMF' AND tc.tableau = %s
                """,
                (cle,),
            )
            for (code,) in cur.fetchall():
                societes_par_tableau.setdefault(cle, set()).add(code)
        # Takaful (2026-09-15) — même principe que Bilan ci-dessus : les 5
        # clés tableau_cellules Takaful (voir TABLEAU_GROUPS) peuvent avoir
        # des sociétés que le KPI narrow (kpi_values, raws partagés entre
        # plusieurs clés) ne reflète pas fidèlement une par une.
        for cle in (
            "takaful_surplus_familial", "takaful_surplus_general", "takaful_resultat_entreprise",
            "takaful_ventilation_familial", "takaful_ventilation_general",
        ):
            cur.execute(
                """
                SELECT DISTINCT c.code
                FROM tableau_cellules tc
                JOIN documents d ON d.id = tc.document_id
                JOIN sources s ON s.id = d.source_id
                JOIN societes c ON c.id = d.cmf_id
                WHERE s.nom = 'CMF' AND tc.tableau = %s
                """,
                (cle,),
            )
            for (code,) in cur.fetchall():
                societes_par_tableau.setdefault(cle, set()).add(code)

    # Garde-fou pour Annexe 13 : kpi_values (ancien extracteur 7-KPI) peut
    # taguer à tort une société structurellement Vie-only comme ayant un
    # résultat "Non-Vie" — constaté sur ATTIJARI (page de raccordement Vie
    # non qualifiée "Vie" dans son titre, passe le contrôle de vraisemblance
    # par accident, voir CAS_PARTICULIERS_FULL_TABLE.md). Le référentiel
    # `ANNEXE13_NON_VIE_EXCLUSIONS` (construit à partir du texte réel des
    # PDF, pas d'une heuristique de titre) reste la source de vérité — il
    # exclut TOUJOURS ces sociétés ici, quoi que dise kpi_values/
    # tableau_cellules.
    from extraction.annexe13_pipeline import ANNEXE13_NON_VIE_EXCLUSIONS
    societes_par_tableau["annexe13"] -= ANNEXE13_NON_VIE_EXCLUSIONS

    tableaux = [{"key": key, "label": label} for key, label, _raws in TABLEAU_GROUPS]
    return {
        "societes": societes, "annees": annees, "tableaux": tableaux,
        "societes_par_tableau": {k: sorted(v) for k, v in societes_par_tableau.items()},
    }


def get_reliability_stats(conn):
    """Deux indicateurs calculés à partir de données RÉELLES déjà en base —
    jamais une estimation — tous deux corrigés le 2026-09-09 sur retour
    utilisateur explicite (les deux premières versions mesuraient la
    mauvaise chose, voir historique git) :

    1. Collecte : part des PDF réellement présents en local PARMI TOUS CEUX
       QUI DEVRAIENT L'ÊTRE — pas juste parmi les documents déjà référencés
       en base (ce qui donnait artificiellement ~100% : un document non
       découvert n'y apparaît jamais). L'univers attendu est calculé PAR
       SOCIÉTÉ : tous les exercices compris entre sa PREMIÈRE et sa
       DERNIÈRE année connue en base (jamais une plage fixe identique pour
       les 24 sociétés) — ainsi une société récemment créée/renommée (ex.
       "BNA Assurances", dont les dépôts CMF ne commencent qu'en 2024,
       ex-"AMI"/Assurance Mutuelle El Ittihad qui a cessé de publier sous
       cet ancien nom à partir de 2024) n'est jamais pénalisée pour des
       années où elle n'existait pas encore sous ce nom, ni "AMI" pour ne
       plus rien publier après son dernier exercice connu. Univers dérivé
       uniquement des documents déjà découverts par le scrapeur (pas
       d'appel réseau live dans cette route HTTP).
    2. Fiabilité de l'extraction (Annexe 13) : part des DOCUMENTS (pas des
       lignes/règles comptables individuelles — un document reste "fiable"
       même avec un écart mineur sur une règle) dont l'extraction complète
       a réellement abouti en base (`tableau_cellules`) PARMI TOUS CEUX OÙ
       ELLE ÉTAIT ATTENDUE : documents CMF collectés d'une société
       structurellement éligible à l'Annexe 13 Non-Vie (exclut les sociétés
       Vie exclusivement/Takaful, voir `annexe13_pipeline.
       ANNEXE13_NON_VIE_EXCLUSIONS` — leur absence de résultat n'est pas un
       échec d'extraction, c'est attendu par nature du modèle métier)."""
    from config.company_registry import COMPANY_REGISTRY
    from extraction.annexe13_pipeline import ANNEXE13_NON_VIE_EXCLUSIONS

    docs = [d for d in list_all_documents(conn) if d[1] == "CMF" and d[2]]  # (id, source, code, nom, pdf, annee, lien)
    by_code = {}
    for doc_id, _src, code, _nom, nom_pdf, annee, _lien in docs:
        by_code.setdefault(code, []).append((annee, nom_pdf, doc_id))

    # --- 1. Collecte : univers attendu = plage [1re, dernière] année connue,
    # par société, comparée aux PDF réellement présents sur disque.
    def _has_local_pdf(code, nom_pdf):
        path = local_pdf_path("CMF", code, nom_pdf)
        return bool(path and os.path.isfile(path))

    attendus = collectes = 0
    for code, entries in by_code.items():
        annees = [a for a, _p, _i in entries]
        attendus += max(annees) - min(annees) + 1
        collectes += sum(1 for _a, nom_pdf, _i in entries if _has_local_pdf(code, nom_pdf))
    collecte_pct = round(100 * collectes / attendus, 1) if attendus else None

    # --- 2. Fiabilité de l'extraction Annexe 13 : documents éligibles
    # (société Non-Vie-eligible, PDF présent) vs documents réellement
    # stockés en base après extraction (tableau_cellules).
    eligibles_ids = {
        doc_id for code, entries in by_code.items() if code in COMPANY_REGISTRY
        and code not in ANNEXE13_NON_VIE_EXCLUSIONS
        for _a, nom_pdf, doc_id in entries
        if _has_local_pdf(code, nom_pdf)
    }
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT document_id FROM tableau_cellules WHERE tableau = 'annexe13'")
        reussis_ids = {row[0] for row in cur.fetchall()}
    reussis = len(eligibles_ids & reussis_ids)
    total_eligibles = len(eligibles_ids)
    fiabilite_pct = round(100 * reussis / total_eligibles, 1) if total_eligibles else None

    return {
        "collecte": {"pct": collecte_pct, "collectes": collectes, "total": attendus},
        "fiabilite_extraction": {
            "pct": fiabilite_pct, "reussis": reussis, "total": total_eligibles,
            "tableau": "Annexe 13",
        },
    }


def get_document_grid(conn, code, annee, tableau):
    """Grille de cellules déjà stockée (`tableau_cellules`) pour UN document
    CMF (société + année), pour la page de correction manuelle — un pur
    aperçu en lecture de ce qui est déjà en base, aucune ré-extraction. Les
    lignes sont ordonnées selon l'ordre canonique métier (même référentiel
    que l'export Excel) quand il existe pour ce tableau, sinon dans l'ordre
    où `tableau_cellules` les restitue. Renvoie None si aucun document
    CMF (code, annee) n'existe encore en base."""
    doc_id = get_document_id(conn, code, annee)
    if not doc_id:
        return None
    rows = get_tableau_cellules(conn, [doc_id], tableau)
    colonnes = []
    lignes_map = {}
    for _doc_id, ligne, colonne, valeur in rows:
        if colonne not in colonnes:
            colonnes.append(colonne)
        lignes_map.setdefault(ligne, {})[colonne] = valeur
    if tableau == "annexe13":
        ordered = _sorted_grid_rows(lignes_map, _ROW_DISPLAY_ORDER, len(CANONICAL_ROWS))
    elif tableau == "annexe12":
        ordered = _sorted_grid_rows(lignes_map, _ROW_DISPLAY_ORDER_VIE, len(CANONICAL_ROWS_VIE))
    else:
        ordered = list(lignes_map.items())
    return {
        "document_id": doc_id,
        "colonnes": colonnes,
        "lignes": [{"ligne": ligne, "valeurs": valeurs} for ligne, valeurs in ordered],
    }


def get_referentiel(tableau):
    """Noms canoniques de ligne/colonne déjà définis pour la normalisation
    (voir extraction/annexe13_pipeline.py, annexe12_pipeline.py) — sert à
    peupler le menu déroulant de la page de correction manuelle quand
    l'utilisateur corrige un NOM de ligne/colonne plutôt qu'une valeur : on
    ne laisse choisir que des libellés déjà reconnus par le pipeline, jamais
    une saisie libre qui échapperait à la normalisation. `colonnes` est
    volontairement le même référentiel partagé pour les deux annexes (Non-Vie
    et Vie, voir le commentaire sur CANONICAL_COLUMNS) — seules les lignes
    diffèrent par tableau. Aucun référentiel pour 'bilan' : structure encore
    hors normalisation (retourne des listes vides)."""
    if tableau == "annexe13":
        return {"lignes": CANONICAL_ROWS, "colonnes": CANONICAL_COLUMNS}
    if tableau == "annexe12":
        return {"lignes": CANONICAL_ROWS_VIE, "colonnes": CANONICAL_COLUMNS}
    return {"lignes": [], "colonnes": []}


def _grid_reference_values(grid):
    """Valeurs numériques distinctes (entiers, valeur absolue, hors 0 —
    représente conventionnellement une cellule vide "-", jamais un vrai
    chiffre) de la grille STOCKÉE. Sert de signature de contenu pour
    retrouver la page PDF réelle — voir `_find_page_matching_grid_values`.
    TRONCATURE (pas round()) : le texte du PDF concatène partie entière et
    décimale sans séparateur une fois nettoyé ("532,784" -> "532784") —
    round() change le dernier chiffre dès que la décimale est ≥ 0.5,
    cassant la recherche par sous-chaîne à tort pour ~moitié des valeurs
    (même bug identifié et corrigé dans l'audit externe Annexe 12,
    2026-09-14 : CARTE_VIE 2022 passait de 24/44 à 44/44 confirmées une
    fois la troncature appliquée)."""
    values = set()
    for row in grid["lignes"]:
        for v in row["valeurs"].values():
            if v is None:
                continue
            try:
                iv = int(math.floor(abs(float(v))))
            except (TypeError, ValueError):
                continue
            if iv != 0:
                values.add(iv)
    return values


def _find_page_matching_grid_values(pdf_path, grid, max_pages=120):
    """Retrouve la page dont le texte contient le PLUS de valeurs de la
    grille STOCKÉE — par CONTENU plutôt que par titre de section. Nécessaire
    car la donnée peut provenir d'un tableau au titre tout différent de
    "Annexe 13" (ex. un tableau de raccordement "Annexe n°16" servant de
    repli quand la page Annexe 13 par branche n'existe pas/n'est pas
    exploitable dans ce document — constaté sur STAR 2025 : chercher une
    page titrée "Annexe 13" tombait sur une page de résumé sans rapport,
    dont seules les 2-3 premières valeurs coïncidaient par coïncidence).
    Rapide (texte pdfplumber seul, pas de camelot) : quelques secondes pour
    tout le document plutôt que plusieurs dizaines."""
    values = _grid_reference_values(grid)
    if not values:
        return None
    import pdfplumber
    best_page, best_score = None, 0
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages[:max_pages]):
            text = page.extract_text() or ""
            if not text:
                continue
            digits_blob = re.sub(r"[^0-9]", "", text)
            score = 0
            for v in values:
                s = str(v)
                if len(s) >= 4:
                    if s in digits_blob:
                        score += 1
                elif re.search(rf"(?<!\d){s}(?!\d)", text):
                    score += 1
            if score > best_score:
                best_score, best_page = score, i + 1
    # Exige une correspondance substantielle (pas juste 1-2 nombres communs
    # par coïncidence) — mieux vaut ne rien afficher qu'une page sans rapport.
    if best_page is None or best_score < max(3, len(values) // 3):
        return None
    return best_page


def locate_source_page(conn, code, annee, tableau):
    """Numéro de page du PDF source où se trouve le tableau demandé — pour
    l'afficher à côté de l'aperçu Excel dans la page de correction manuelle
    et aider l'utilisateur à repérer visuellement les fautes d'extraction.
    Retrouvée par CONTENU (voir `_find_page_matching_grid_values`) — la
    grille déjà stockée fait foi, jamais une ré-extraction indépendante qui
    pourrait diverger de ce qui est réellement affiché à l'écran. Mis en
    cache dans `tableau_pages` (voir schema.sql) dès le premier appel pour ce
    document : un document déjà publié ne change pas de pagination. None si
    le tableau n'a pas encore de pipeline de repérage dédié (bilan, pas
    encore construit), s'il n'y a aucune cellule stockée, ou si la page n'a
    pas pu être retrouvée."""
    if tableau not in (
        "annexe12", "annexe13", "bilan_actif", "bilan_passif",
        "takaful_surplus_familial", "takaful_surplus_general", "takaful_resultat_entreprise",
        "takaful_ventilation_familial", "takaful_ventilation_general",
    ):
        return None
    doc_id = get_document_id(conn, code, annee)
    if not doc_id:
        return None

    cached = get_cached_tableau_page(conn, doc_id, tableau)
    if cached is not TABLEAU_PAGE_MISS:
        return cached

    path = get_local_pdf_path_for_document(conn, doc_id)
    grid = get_document_grid(conn, code, annee, tableau)
    page_num = None
    if path and grid and grid["lignes"]:
        try:
            page_num = _find_page_matching_grid_values(path, grid)
        except Exception:
            page_num = None
    # Ne met en cache un échec (None) QUE si le PDF était réellement
    # disponible pour la recherche — sinon "introuvable" resterait figé
    # pour toujours (voir TABLEAU_PAGE_MISS) même une fois le PDF local
    # redevenu présent (ex: après un rattrapage — voir
    # api/app.py::_backfill_startup_loop). Découvert le 2026-09-17 :
    # STAR/2025/annexe12 était resté "introuvable" en cache depuis un
    # appel fait pendant que le cache PDF local avait été vidé par un
    # rebuild PyInstaller, bien après que le PDF ait été retéléchargé.
    if path:
        save_cached_tableau_page(conn, doc_id, tableau, page_num)
    return page_num


def page_source_info(conn, code, annee, tableau):
    """Numéro de page (voir `locate_source_page`) accompagné d'un indicateur
    "raccordement" — la page trouvée réconcilie le résultat technique avec
    le compte de résultat global (1 colonne "Total", ex. "Annexe n°16")
    plutôt que de ventiler par branche : un repli légitime, déjà vérifié à
    la main dans certains cas (voir extraction/annexe13_verified.py) quand
    la vraie page par branche est un scan illisible, mais qui a besoin
    d'être signalé explicitement — un utilisateur voyant "Annexe n°16"
    affiché sous l'onglet "Annexe 13" y voit à raison une incohérence s'il
    n'est pas prévenu que c'est délibéré."""
    page_num = locate_source_page(conn, code, annee, tableau)
    if page_num is None or tableau in (
        "bilan_actif", "bilan_passif",
        "takaful_surplus_familial", "takaful_surplus_general", "takaful_resultat_entreprise",
        "takaful_ventilation_familial", "takaful_ventilation_general",
    ):
        # Le concept de page "raccordement" (Annexe 16 substituée à
        # l'Annexe 13 par branche) n'existe pas côté Bilan ni côté Takaful
        # — jamais signalé.
        return {"page": page_num, "raccordement": False}
    raccordement_re = _ANNEXE13_RACCORDEMENT_RE if tableau == "annexe13" else _ANNEXE12_RACCORDEMENT_RE
    doc_id = get_document_id(conn, code, annee)
    path = get_local_pdf_path_for_document(conn, doc_id) if doc_id else None
    is_raccordement = False
    if path:
        try:
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                if 0 < page_num <= len(pdf.pages):
                    head = (pdf.pages[page_num - 1].extract_text() or "")[:200]
                    is_raccordement = bool(raccordement_re.search(head.lower()))
        except Exception:
            is_raccordement = False
    return {"page": page_num, "raccordement": is_raccordement}


def _raw_tableaux_for_groups(group_keys):
    if not group_keys:
        return None
    raws = set()
    for key in group_keys:
        raws.update(_TABLEAU_GROUP_TO_RAW.get(key, []))
    return sorted(raws)


# ── Export Excel flexible ───────────────────────────────────────────────────
DARK = "2E2E38"
YELLOW = "FFE600"
LIGHT = "F4F4F7"


def _thin_border():
    side = Side(style="thin", color="DDDDE3")
    return Border(left=side, right=side, top=side, bottom=side)


def _autosize_columns(ws, skip_rows=(1, 2), min_width=10, max_width=32, label_max_width=100):
    """Largeur de chaque colonne = le CONTENU RÉEL le plus large qu'elle
    porte (pas une valeur fixe devinée à l'avance, qui coupait le texte dès
    qu'un libellé ou un nombre dépassait la largeur supposée). Une seule
    passe sur toute la feuille une fois tout écrit, plutôt que de faire
    suivre une largeur à chaque site d'écriture séparé (plusieurs blocs
    différents écrivent dans la même feuille).

    Exclusions volontaires, pour ne pas gonfler une colonne à cause d'une
    ligne qui n'est de toute façon jamais coupée (déborde librement dans des
    cellules vides voisines, sans bordure ni contenu pour l'arrêter) :
    - `skip_rows` : le bandeau de titre (fusionné, largeur non pertinente).
    - toute ligne "titre" — UNE SEULE cellule remplie sur toute la ligne
      (titres de bloc/sous-titres, ex. "Annexe 13 — Résultat technique...",
      "2024 — tableau complet (...)") — une vraie ligne de donnée ou
      d'en-tête a toujours plusieurs cellules remplies (libellé + valeurs)."""
    widths = {}
    for row in ws.iter_rows():
        if row[0].row in skip_rows:
            continue
        populated = [c for c in row if c.value is not None]
        if len(populated) <= 1:
            continue
        for cell in populated:
            if isinstance(cell.value, (int, float)):
                text = f"{cell.value:,.0f}"
            else:
                text = str(cell.value)
            widths[cell.column] = max(widths.get(cell.column, 0), len(text))
    for col_idx, max_len in widths.items():
        cap = label_max_width if col_idx == 1 else max_width
        ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_len + 3, min_width), cap)


# Libellé "propre" affiché comme titre de section dans chaque feuille, à
# partir du libellé brut réellement stocké en base (voir la note sur
# l'hétérogénéité de `tableau` en tête de fichier). "Annexe 12/13" reste
# affiché tel quel (Vie + Non-Vie combinés) plutôt que rattaché arbitrairement
# à l'un des deux, pour ne pas laisser croire que la section "Annexe 12"
# d'une feuille est un Vie pur si une partie de ses lignes vient en fait de
# ce libellé combiné.
_RAW_TO_DISPLAY = {
    "Annexe12": "Annexe 12 — Résultat technique Vie",
    "Annexe 12 - Resultat technique Vie": "Annexe 12 — Résultat technique Vie",
    "Annexe13": "Annexe 13 — Résultat technique Non-Vie",
    "Annexe 13 - Resultat technique Non-Vie": "Annexe 13 — Résultat technique Non-Vie",
    "Annexe 12/13": "Annexe 12/13 — Résultat technique (Vie + Non-Vie combinés)",
    "Bilan": "Bilan (Actif / Passif)",
    "Etat de resultat (technique / global)": "État de résultat",
    "Calcul interne": "Ratios calculés (interne)",
    "Presentation de la societe": "Présentation de la société",
}


def _display_tableau(raw):
    return _RAW_TO_DISPLAY.get(raw, raw)


_GROUP_DISPLAY = {key: label for key, label, _raws in TABLEAU_GROUPS}


def _resolve_display_tableau(raw, active_group_keys):
    """Comme `_display_tableau`, mais résout l'ambiguïté du libellé combiné
    "Annexe 12/13" (voir commentaire sur TABLEAU_GROUPS) selon le contexte
    de LA sélection en cours plutôt que de toujours afficher le libellé
    combiné générique. Si `raw` n'appartient qu'à UN SEUL groupe parmi ceux
    réellement demandés dans cet export (ex. seul "annexe13" sélectionné),
    le libellé de CE groupe est utilisé — la donnée rejoint alors le même
    bloc que la grille complète Annexe 13 (voir build_flexible_export_xlsx)
    au lieu de créer une section à part, mal étiquetée. Si `raw` appartient
    à plusieurs groupes actifs à la fois (ex. export "tous les tableaux",
    Annexe 12 ET Annexe 13 tous deux actifs), l'ambiguïté est réelle — le
    libellé combiné reste affiché tel quel, honnête plutôt que de deviner."""
    owning = [k for k in active_group_keys if raw in _TABLEAU_GROUP_TO_RAW.get(k, [])]
    if len(owning) == 1:
        return _GROUP_DISPLAY[owning[0]]
    return _display_tableau(raw)


_INVALID_SHEET_CHARS = set('[]:*?/\\')


def _safe_sheet_name(code, used):
    name = "".join(c for c in (code or "?") if c not in _INVALID_SHEET_CHARS)[:31] or "Feuille"
    base, i = name, 2
    while name.lower() in used:
        suffix = f" ({i})"
        name = base[: 31 - len(suffix)] + suffix
        i += 1
    used.add(name.lower())
    return name


def _write_sheet_title(ws, last_col, title, subtitle):
    """Bandeau de titre — fond blanc, texte noir (retour utilisateur : "au
    lieu du gris foncé mettez le blanc et le texte en noir"), un seul bloc
    sur 2 lignes : nom de la société en noir gras, sous-titre en gris foncé
    discret en dessous (hiérarchie par le poids/la taille du texte)."""
    last_col = max(last_col, 2)
    for r in (1, 2):
        for col_idx in range(1, last_col + 1):
            ws.cell(row=r, column=col_idx).fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    ws.cell(row=1, column=1, value=title)
    ws.cell(row=1, column=1).font = Font(color="000000", bold=True, size=14, name="Calibri")
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="bottom")
    ws.row_dimensions[1].height = 34
    if subtitle:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
        ws.cell(row=2, column=1, value=subtitle)
        ws.cell(row=2, column=1).font = Font(color="595959", size=9.5, name="Calibri")
        ws.cell(row=2, column=1).alignment = Alignment(horizontal="center", vertical="top")
    ws.row_dimensions[2].height = 18
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "808080"


# ── Annexe 13 — tableau complet (toutes lignes × toutes colonnes) ──────────
# Contrairement aux autres tableaux ci-dessus (lus depuis kpi_values, donc
# limités aux 7 KPI déjà extraits pour les dashboards), l'Annexe 13 est
# ré-extraite directement depuis le PDF source via
# extraction/full_table_extractor.py — la grille réelle par branche, telle
# qu'elle apparaît dans le document. Couverture actuelle : ~68% des
# documents CMF Non-Vie sur 2016-2025 (voir
# extraction/CAS_PARTICULIERS_FULL_TABLE.md pour le détail par société/
# année) ; quand l'extraction complète échoue pour un document donné, le
# sous-ensemble à 7 KPI déjà utilisé par les dashboards est affiché à la
# place, clairement signalé comme tel plutôt que de faire disparaître
# l'année silencieusement.
def _extract_annexe13_full_grid(pdf_path):
    """Repli en direct sur le PDF pour un document pas encore traité par la
    pipeline de validation (extraction/annexe13_pipeline.py — voir
    api/services/tableau_pipeline_service.py) : mêmes localisation +
    extraction, ET même normalisation des libellés de ligne, pour que ce
    chemin de repli reste visuellement cohérent avec le chemin rapide
    (cellules déjà validées en base) plutôt que d'afficher des libellés
    bruts non normalisés selon que le document a déjà été traité ou pas."""
    try:
        _page_num, result = locate_and_extract_full_table(
            pdf_path, _is_annexe13_page, _ANNEXE13_KPI_PATTERNS, _ANNEXE13_RACCORDEMENT_RE,
            extra_page_predicate=relaxed_is_annexe13_page,
        )
    except Exception:
        return None
    if result is None:
        return None
    normalized = normalize_table(result)
    return {"colonnes": normalized["colonnes"], "lignes": normalized["lignes"]}


# ── Annexe 12 — tableau complet (même principe, voir Annexe 13 ci-dessus) ──
def _extract_annexe12_full_grid(pdf_path):
    """Symétrique de `_extract_annexe13_full_grid`, pour l'Annexe 12
    (Résultat technique Vie) — voir extraction/annexe12_pipeline.py."""
    try:
        _page_num, result = locate_and_extract_full_table(
            pdf_path, _is_annexe12_page, _ANNEXE12_KPI_PATTERNS, _ANNEXE12_RACCORDEMENT_RE,
            extra_page_predicate=relaxed_is_annexe12_page, use_notes_fallback=False,
        )
    except Exception:
        return None
    if result is None:
        return None
    normalized = normalize_table_vie(result)
    return {"colonnes": normalized["colonnes"], "lignes": normalized["lignes"]}


def _fetch_full_grid_by_doc(conn, document_ids, tableau):
    """Grilles déjà stockées (`tableau_cellules`) pour un ensemble de
    documents, une clé `tableau` donnée — {document_id: {"colonnes": [...],
    "lignes": {ligne: {colonne: valeur}}}}. Contrairement à
    `get_tableau_cellules` (triée par `colonne_ordre`, donc COLONNE-majeure
    — plusieurs lignes différentes se mélangent pour une même colonne),
    trie ici par `id` (ordre d'insertion réel = ordre d'apparition dans le
    PDF pour ces pipelines grille) pour que l'ordre des LIGNES du dict
    Python résultant (préservé, voir `_write_full_grid_block(...,
    preserve_order=True)`) reste celui du document source — utilisé pour
    Bilan/Takaful, qui n'ont pas de référentiel canonique de tri comme
    Annexe 12/13 (CANONICAL_ROWS)."""
    if not document_ids:
        return {}
    with conn.cursor() as cur:
        placeholders = ",".join(["%s"] * len(document_ids))
        cur.execute(
            f"""
            SELECT document_id, ligne, colonne, valeur
            FROM tableau_cellules
            WHERE tableau = %s AND document_id IN ({placeholders})
            ORDER BY id
            """,
            [tableau] + list(document_ids),
        )
        rows = cur.fetchall()
    grids = {}
    for doc_id, ligne, colonne, valeur in rows:
        grid = grids.setdefault(doc_id, {"colonnes": [], "lignes": {}})
        if colonne not in grid["colonnes"]:
            grid["colonnes"].append(colonne)
        grid["lignes"].setdefault(ligne, {})[colonne] = valeur
    return grids


# Position de chaque poste dans l'ordre naturel du tableau (ordre déjà
# significatif de CANONICAL_ROWS — annexe13_pipeline.py, celui d'un vrai
# relevé "Résultat technique" : Primes en premier, Résultat technique et
# provisions en dernier) — sans ça, l'ordre dépend de la source (DB triée
# par libellé le temps d'une requête sans ORDER BY explicite, ou ordre
# d'apparition PDF pour le repli live) et n'est jamais celui attendu.
_ROW_DISPLAY_ORDER = {label: i for i, label in enumerate(CANONICAL_ROWS)}
_ROW_DISPLAY_ORDER_VIE = {label: i for i, label in enumerate(CANONICAL_ROWS_VIE)}


def _sorted_grid_rows(lignes, order=_ROW_DISPLAY_ORDER, fallback=len(CANONICAL_ROWS)):
    return sorted(lignes.items(), key=lambda kv: (order.get(kv[0], fallback), kv[0]))


# Charte visuelle de ce bloc spécifiquement (grille complète Annexe 13) —
# police Arial alignée sur le script de référence de l'utilisatrice
# (FS_Market_Intelligence/B.py::export_to_excel). Couleur d'en-tête : bleu
# → gris → jaune foncé → sombre (couleur EY) → gris moyen → ce gris,
# légèrement plus foncé (retours utilisateur successifs). Lignes de données
# zébrées (alternance blanc/gris très clair), comme le tableau de référence
# "Classement des compagnies".
_REF_HEADER = "5B6472"
_REF_HEADER_TEXT = "FFFFFF"
_REF_ZEBRA = "F3F4F6"


def _write_full_grid_block(ws, row, annee, grid, row_order=_ROW_DISPLAY_ORDER, row_order_fallback=None, preserve_order=False):
    cols = grid["colonnes"]
    last_col = max(1 + len(cols), 2)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
    subtitle_cell = ws.cell(row=row, column=1, value=f"{annee} — tableau complet ({len(grid['lignes'])} lignes × {len(cols)} colonnes)")
    subtitle_cell.font = Font(italic=True, size=10, color=DARK, name="Calibri")
    subtitle_cell.alignment = Alignment(horizontal="center", vertical="center")
    row += 2  # ligne vide avant le début du tableau (retour utilisateur : espacement)
    # Libellés de ligne ET d'en-tête en MAJUSCULES — la casse du référentiel
    # canonique (CANONICAL_ROWS) sert au rattachement/à la validation, pas à
    # l'affichage ; convention réelle des tableaux source (et du dossier de
    # référence) pour les deux.
    headers = ["LIBELLÉ"] + [c.upper() for c in cols]

    # En-tête de GROUPE fusionné (ex. TUNIS_RE : "NON MARINES" au-dessus
    # d'Incendie/ARD/Risques techniques) — retour utilisateur du 2026-09-10 :
    # veut retrouver dans l'export la même structure de fusion de cellules
    # que le PDF source, pas seulement des noms de colonne individuellement
    # corrects. `derive_column_groups` (annexe13_pipeline.py) la retrouve à
    # partir des seuls noms de colonnes (généralisable à toute société ayant
    # ce gabarit, pas propre à TUNIS_RE) ; {} pour tout tableau sans ce
    # gabarit — comportement à une seule ligne d'en-tête inchangé pour eux.
    groups = derive_column_groups(cols)
    header_style = dict(
        fill=PatternFill(start_color=_REF_HEADER, end_color=_REF_HEADER, fill_type="solid"),
        font=Font(color=_REF_HEADER_TEXT, bold=True, name="Arial", size=10),
        alignment=Alignment(horizontal="center", vertical="center"),
    )
    if groups:
        grouped_col_idxs = {i for g in groups for i in range(g["debut"], g["fin"] + 1)}
        # Ligne 1 : "LIBELLÉ" + colonnes hors groupe fusionnées VERTICALEMENT
        # sur les 2 lignes d'en-tête (comme "RUBRIQUES" dans le PDF), noms de
        # groupe fusionnés HORIZONTALEMENT sur la portée de leurs colonnes
        # membres.
        ws.merge_cells(start_row=row, start_column=1, end_row=row + 1, end_column=1)
        cell = ws.cell(row=row, column=1, value=headers[0])
        cell.fill, cell.font, cell.alignment = header_style["fill"], header_style["font"], header_style["alignment"]
        cell.border = _thin_border()
        ws.cell(row=row + 1, column=1).border = _thin_border()
        group_by_start = {g["debut"]: g for g in groups}
        col_idx = 0
        while col_idx < len(cols):
            excel_col = col_idx + 2
            g = group_by_start.get(col_idx)
            if g:
                end_excel_col = g["fin"] + 2
                ws.merge_cells(start_row=row, start_column=excel_col, end_row=row, end_column=end_excel_col)
                for c in range(excel_col, end_excel_col + 1):
                    cell = ws.cell(row=row, column=c, value=g["libelle"].upper() if c == excel_col else None)
                    cell.fill, cell.font, cell.alignment = header_style["fill"], header_style["font"], header_style["alignment"]
                    cell.border = _thin_border()
                col_idx = g["fin"] + 1
            else:
                ws.merge_cells(start_row=row, start_column=excel_col, end_row=row + 1, end_column=excel_col)
                cell = ws.cell(row=row, column=excel_col, value=headers[col_idx + 1])
                cell.fill, cell.font, cell.alignment = header_style["fill"], header_style["font"], header_style["alignment"]
                cell.border = _thin_border()
                ws.cell(row=row + 1, column=excel_col).border = _thin_border()
                col_idx += 1
        # Ligne 2 : libellé propre de chaque colonne MEMBRE d'un groupe
        # uniquement (les colonnes hors groupe ont déjà leur nom fusionné
        # verticalement ci-dessus, rien à ré-écrire sur cette ligne pour elles).
        for i in grouped_col_idxs:
            excel_col = i + 2
            cell = ws.cell(row=row + 1, column=excel_col, value=headers[i + 1])
            cell.fill, cell.font, cell.alignment = header_style["fill"], header_style["font"], header_style["alignment"]
            cell.border = _thin_border()
        row += 2
    else:
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.fill, cell.font, cell.alignment = header_style["fill"], header_style["font"], header_style["alignment"]
            cell.border = _thin_border()
        row += 1
    fallback = row_order_fallback if row_order_fallback is not None else len(row_order)
    # `preserve_order=True` (Bilan/Takaful) : ces tableaux n'ont pas de
    # référentiel canonique (CANONICAL_ROWS n'existe que pour Annexe 12/13)
    # — trier par libellé (repli de `_sorted_grid_rows` quand `row_order`
    # est vide) mélangerait l'ordre réel du PDF (ex. PA2 après PA361).
    # `grid["lignes"]` est déjà dans l'ORDRE VOULU à ce stade (voir
    # `_fetch_full_grid_by_doc`, qui insère selon l'ordre d'insertion en
    # base = ordre d'apparition dans le PDF source) — un dict Python
    # préserve cet ordre, donc un simple `.items()` suffit.
    row_items = list(grid["lignes"].items()) if preserve_order else _sorted_grid_rows(grid["lignes"], order=row_order, fallback=fallback)
    for i, (label, values) in enumerate(row_items):
        fill = PatternFill(start_color=_REF_ZEBRA, end_color=_REF_ZEBRA, fill_type="solid") if i % 2 == 1 else None
        cell = ws.cell(row=row, column=1, value=(label or "").upper())
        cell.border = _thin_border()
        cell.font = Font(name="Arial", size=10, color=DARK)
        cell.alignment = Alignment(horizontal="left", vertical="center")
        if fill:
            cell.fill = fill
        for col_idx, col in enumerate(cols, start=2):
            val = values.get(col)
            c = ws.cell(row=row, column=col_idx, value=val)
            c.number_format = "#,##0"
            c.border = _thin_border()
            c.font = Font(name="Arial", size=10, color=DARK)
            c.alignment = Alignment(horizontal="center", vertical="center")
            if fill:
                c.fill = fill
        row += 1
    row += 2
    return row, len(headers)


def _write_multi_year_grid_block(ws, row, grids_by_annee, display, row_order=_ROW_DISPLAY_ORDER, row_order_fallback=None, preserve_order=False):
    """Grille complète FUSIONNANT toutes les années en un seul tableau —
    UNE ligne par poste, les années groupées en en-têtes de colonnes côte
    à côte (comme les blocs KPI simples), plutôt qu'un tableau complet
    répété une fois par année (empilé verticalement). Corrige la
    structuration jugée non lisible sur plusieurs années (retour
    utilisateur direct, 2026-09-17 : "la mise en place des tableaux comme
    ça pour beaucoup d'années n'est pas structuré" — comparer une ligne
    d'une année à l'autre imposait de faire défiler tout le tableau de
    l'année précédente).

    Chaque année garde ses PROPRES colonnes (elles varient réellement
    d'une année à l'autre pour un même tableau — ex. Bilan Actif de STAR :
    47 lignes en 2022, 19 en 2025) : une ligne absente une année donnée
    laisse simplement ses cellules vides pour cette année, sans décaler ni
    supprimer les colonnes des autres années."""
    grids = {a: g for a, g in grids_by_annee.items() if g and g.get("lignes")}
    if not grids:
        return row, 1
    annees = sorted(grids.keys())
    total_cols = 1 + sum(len(grids[a]["colonnes"]) for a in annees)

    # Titre du tableau, CENTRÉ SUR SA VRAIE LARGEUR (pas la largeur de la
    # feuille entière, qui peut être dictée par un autre bloc plus large —
    # retour utilisateur direct, 2026-09-17 : "le titre du tableau doit
    # être au centre, au-dessus du tableau et non pas juste à côté").
    # Une seule année : l'année rejoint le titre lui-même ("Bilan Actif —
    # 2024"), mise en valeur par sa propre taille/gras plutôt que fusionnée
    # sur toute la largeur des colonnes de l'en-tête (retour direct : "je
    # préfère que l'année [...] soit écrite mise en valeur [...] sans la
    # mettre en fusion sur toutes les colonnes. Et je préfère qu'elle soit
    # également avec le titre du tableau") — la ligne d'en-tête "année"
    # séparée ci-dessous ne s'affiche alors plus du tout, redondante.
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=max(total_cols, 2))
    titre = f"{display} — {annees[0]}" if len(annees) == 1 else display
    title_cell = ws.cell(row=row, column=1, value=titre)
    title_cell.font = Font(bold=True, size=12, color=DARK, name="Calibri")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    row += 1
    if len(annees) > 1:
        periode = f"{annees[0]}–{annees[-1]}"
        subtitle_cell = ws.cell(row=row, column=1, value=f"{periode} — tableau complet")
        subtitle_cell.font = Font(italic=True, size=10, color=DARK, name="Calibri")
        row += 1

    # Ordre des lignes : référentiel canonique si dispo (Annexe 12/13),
    # sinon ordre de PREMIÈRE apparition en balayant les années dans
    # l'ordre chronologique (préserve l'ordre réel du PDF le plus ancien
    # disponible, complété par les postes qui n'apparaissent que plus tard).
    fallback = row_order_fallback if row_order_fallback is not None else len(row_order)
    if preserve_order:
        all_labels = []
        seen = set()
        for a in annees:
            g = grids.get(a)
            if not g:
                continue
            for label in g["lignes"]:
                if label not in seen:
                    seen.add(label)
                    all_labels.append(label)
    else:
        all_labels_set = {label for g in grids.values() for label in g["lignes"]}
        all_labels = [label for label, _ in sorted(
            ((label, None) for label in all_labels_set),
            key=lambda kv: (row_order.get(kv[0], fallback), kv[0]),
        )]

    # Couleur des noms de colonnes en bleu (retour utilisateur direct,
    # 2026-09-17, précisé ensuite : "la couleur des CELLULES [...] pas du
    # texte") — le FOND des cellules d'en-tête de colonne passe en bleu
    # (texte blanc conservé pour le contraste), pas "LIBELLÉ" ni
    # l'éventuel bandeau année (repères visuels distincts entre eux).
    header_style = dict(
        fill=PatternFill(start_color=_REF_HEADER, end_color=_REF_HEADER, fill_type="solid"),
        font=Font(color=_REF_HEADER_TEXT, bold=True, name="Arial", size=10),
        alignment=Alignment(horizontal="center", vertical="center"),
    )
    col_header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    col_header_font = Font(color=_REF_HEADER_TEXT, bold=True, name="Arial", size=10)

    if len(annees) == 1:
        # Une seule année : le titre porte déjà l'année (voir plus haut) —
        # une seule ligne d'en-tête (LIBELLÉ + noms de colonnes), pas de
        # bandeau "année" fusionné en plus, redondant et jamais voulu ici.
        cell = ws.cell(row=row, column=1, value="LIBELLÉ")
        cell.fill, cell.font, cell.alignment = header_style["fill"], header_style["font"], header_style["alignment"]
        cell.border = _thin_border()
        a = annees[0]
        cols = grids[a]["colonnes"]
        year_col_span = {a: (2, cols)}
        for i, colname in enumerate(cols):
            cell = ws.cell(row=row, column=2 + i, value=colname.upper())
            cell.fill = col_header_fill
            cell.font = col_header_font
            cell.alignment = header_style["alignment"]
            cell.border = _thin_border()
        last_col = max(1 + len(cols), 2)
        row += 1
    else:
        # Plusieurs années : "LIBELLÉ" fusionné verticalement sur les 2
        # lignes d'en-tête + un groupe fusionné HORIZONTALEMENT par année,
        # sur la portée réelle de SES colonnes (ligne 1), puis le nom
        # propre de chaque colonne de chaque année (ligne 2).
        ws.merge_cells(start_row=row, start_column=1, end_row=row + 1, end_column=1)
        cell = ws.cell(row=row, column=1, value="LIBELLÉ")
        cell.fill, cell.font, cell.alignment = header_style["fill"], header_style["font"], header_style["alignment"]
        cell.border = _thin_border()
        ws.cell(row=row + 1, column=1).border = _thin_border()

        col = 2
        year_col_span = {}  # annee -> (col_debut, [colonnes])
        for a in annees:
            g = grids.get(a)
            cols = g["colonnes"] if g else []
            if not cols:
                continue
            year_col_span[a] = (col, cols)
            end_col = col + len(cols) - 1
            ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=end_col)
            for c in range(col, end_col + 1):
                cell = ws.cell(row=row, column=c, value=str(a) if c == col else None)
                cell.fill, cell.font, cell.alignment = header_style["fill"], header_style["font"], header_style["alignment"]
                cell.border = _thin_border()
            for i, colname in enumerate(cols):
                cell = ws.cell(row=row + 1, column=col + i, value=colname.upper())
                cell.fill = col_header_fill
                cell.font = col_header_font
                cell.alignment = header_style["alignment"]
                cell.border = _thin_border()
            col = end_col + 1
        last_col = max(col - 1, 2)
        row += 2

    for i, label in enumerate(all_labels):
        fill = PatternFill(start_color=_REF_ZEBRA, end_color=_REF_ZEBRA, fill_type="solid") if i % 2 == 1 else None
        cell = ws.cell(row=row, column=1, value=(label or "").upper())
        cell.border = _thin_border()
        cell.font = Font(name="Arial", size=10, color=DARK)
        cell.alignment = Alignment(horizontal="left", vertical="center")
        if fill:
            cell.fill = fill
        for a, (col_debut, cols) in year_col_span.items():
            values = grids[a]["lignes"].get(label, {}) if a in grids else {}
            for j, colname in enumerate(cols):
                val = values.get(colname)
                c = ws.cell(row=row, column=col_debut + j, value=val)
                c.number_format = "#,##0"
                c.border = _thin_border()
                c.font = Font(name="Arial", size=10, color=DARK)
                c.alignment = Alignment(horizontal="center", vertical="center")
                if fill:
                    c.fill = fill
        row += 1
    row += 2
    return row, last_col


def _write_narrow_fallback_block(ws, row, annee, narrow_annexe13):
    vals = {kpi: v[annee] for kpi, v in narrow_annexe13.items() if annee in v}
    ws.cell(
        row=row, column=1,
        value=f"{annee} — tableau complet non disponible pour ce document : "
              f"sous-ensemble utilisé par les dashboards affiché à la place",
    )
    ws.cell(row=row, column=1).font = Font(italic=True, size=10, color="B00020", name="Calibri")
    row += 1
    if not vals:
        ws.cell(row=row, column=1, value="(aucune donnée disponible)")
        ws.cell(row=row, column=1).font = Font(italic=True, size=10, color=DARK, name="Calibri")
        row += 2
        return row, 1
    headers = ["KPI", str(annee)]
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.fill = PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")
        cell.font = Font(color=YELLOW, bold=True, name="Calibri", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _thin_border()
    row += 1
    for i, kpi in enumerate(sorted(vals.keys())):
        fill = PatternFill(start_color=LIGHT, end_color=LIGHT, fill_type="solid") if i % 2 == 0 else None
        cell = ws.cell(row=row, column=1, value=kpi)
        cell.border = _thin_border()
        cell.font = Font(name="Calibri", size=10, color=DARK)
        if fill:
            cell.fill = fill
        c = ws.cell(row=row, column=2, value=vals[kpi])
        c.border = _thin_border()
        c.font = Font(name="Calibri", size=10, color=DARK)
        c.alignment = Alignment(horizontal="center", vertical="center")
        if fill:
            c.fill = fill
        row += 1
    row += 2
    return row, len(headers)


def build_flexible_export_xlsx(tableau_keys=None, codes=None, annees=None):
    """Génère un export Excel filtré sur n'importe quelle combinaison de
    tableaux/sociétés/années — chaque filtre vide/absent signifie "tous".

    Structuration des feuilles (retour utilisateur direct, 2026-09-17) :
      - Plus d'une société sélectionnée → une feuille PAR SOCIÉTÉ, chaque
        feuille regroupant tous les tableaux demandés en blocs successifs
        (comportement historique).
      - Une seule société sélectionnée mais plusieurs tableaux → une
        feuille PAR TABLEAU à la place (plus facile à partager/comparer
        qu'un unique classeur à rallonge pour une société donnée).
      - Une seule société ET un seul tableau → une seule feuille (design
        Annexe 13 tel qu'il existe déjà).
      - L'année n'est JAMAIS un axe de feuille séparée : toujours des
        colonnes côte à côte dans le même bloc/tableau, quel que soit le
        nombre d'années — une grille reste comparable en lecture d'une
        année à l'autre.

    Design UNIFORME pour tous les tableaux (retour utilisateur direct,
    2026-09-17 : "on doit avoir un design uniforme pour tous les tableaux,
    comme celui de annexe 13") : Annexe 12/13, Bilan Actif/Passif et les 5
    grilles Takaful (Surplus/Ventilation/État de résultat) sont TOUTES
    rendues comme une grille complète (`_write_full_grid_block` — toutes
    les lignes du tableau source, pas seulement le sous-ensemble de KPI
    utilisé par les dashboards), lue depuis `tableau_cellules`. Annexe
    12/13 gardent en plus un repli d'extraction LIVE sur le PDF (voir
    `_extract_annexe13_full_grid`/`_extract_annexe12_full_grid`) pour les
    quelques documents jamais repassés par la validation de fond — les
    7 autres tableaux n'ont pas cet extracteur dédié, ils affichent
    simplement "grille non disponible" pour l'année concernée si elle
    n'est pas encore en base."""
    raw_tableaux = _raw_tableaux_for_groups(tableau_keys)
    active_group_keys = tableau_keys if tableau_keys else [key for key, _label, _raws in TABLEAU_GROUPS]

    # ── Les 9 tableaux à grille complète (voir TABLEAU_GROUPS) — chacun
    # avec son display, son ordre de lignes (canonique pour Annexe 12/13,
    # préservé tel quel pour les 7 autres qui n'ont pas de référentiel) et
    # son éventuel extracteur live de repli (Annexe 12/13 seulement).
    _FULL_GRID_SPECS = {
        "annexe13": dict(
            display=_display_tableau("Annexe13"), row_order=_ROW_DISPLAY_ORDER,
            row_order_fallback=len(CANONICAL_ROWS), preserve_order=False,
            exclusions_module="extraction.annexe13_pipeline", exclusions_name="ANNEXE13_NON_VIE_EXCLUSIONS",
            live_extractor=_extract_annexe13_full_grid,
        ),
        "annexe12": dict(
            display=_display_tableau("Annexe12"), row_order=_ROW_DISPLAY_ORDER_VIE,
            row_order_fallback=len(CANONICAL_ROWS_VIE), preserve_order=False,
            exclusions_module="extraction.annexe12_pipeline", exclusions_name="ANNEXE12_VIE_EXCLUSIONS",
            live_extractor=_extract_annexe12_full_grid,
        ),
    }
    for key, label, _raws in TABLEAU_GROUPS:
        if key not in _FULL_GRID_SPECS:
            _FULL_GRID_SPECS[key] = dict(
                display=label, row_order={}, row_order_fallback=0, preserve_order=True,
                exclusions_module=None, exclusions_name=None, live_extractor=None,
            )
    active_full_grid_keys = [k for k in _FULL_GRID_SPECS if not tableau_keys or k in tableau_keys]
    # Libellés bruts (kpi_values.tableau) déjà couverts par une grille
    # complète ci-dessus — leur bloc "KPI narrow" (dashboards) ne doit
    # jamais s'afficher EN PLUS de la grille complète, sinon la même
    # donnée apparaîtrait deux fois, une fois résumée et une fois en
    # entier (source de confusion, retour utilisateur direct).
    superseded_raws = {raw for k in active_full_grid_keys for raw in _TABLEAU_GROUP_TO_RAW.get(k, [])}
    # "Presentation de la societe" (metadonnees scrapees : adresse,
    # effectif...) et "Calcul interne" (ratios que NOUS calculons, ROE/
    # ROA/combine...) ne sont PAS des tableaux du PDF source — jamais
    # demandes pour cet export, exclus definitivement (retour utilisateur
    # direct, 2026-09-17 : "je ne vous ai jamais demande de mettre la
    # presentation de la societe [...] et les ratios calcules en
    # interne"). "Etat de resultat" EST un vrai tableau PDF mais n'a pas
    # encore d'extracteur de grille complete (voir TODO plus haut) - en
    # attendant, exclu ici aussi plutot que d'afficher un sous-ensemble
    # KPI qui ferait croire, a tort, que c'est le tableau complet.
    superseded_raws |= {"Presentation de la societe", "Calcul interne", "Etat de resultat (technique / global)"}

    conn = get_connection()
    try:
        query = """
            SELECT c.code, c.nom_entreprise, d.annee, k.tableau, k.kpi,
                   k.valeur_nombre, k.valeur_texte
            FROM kpi_values k
            JOIN documents d ON d.id = k.document_id
            JOIN sources s ON s.id = d.source_id
            JOIN societes c ON c.id = d.cmf_id
            WHERE s.nom = 'CMF'
        """
        params = []
        if raw_tableaux:
            placeholders = ",".join(["%s"] * len(raw_tableaux))
            query += f" AND k.tableau IN ({placeholders})"
            params.extend(raw_tableaux)
        if codes:
            placeholders = ",".join(["%s"] * len(codes))
            query += f" AND c.code IN ({placeholders})"
            params.extend(codes)
        if annees:
            placeholders = ",".join(["%s"] * len(annees))
            query += f" AND d.annee IN ({placeholders})"
            params.extend(annees)
        query += " ORDER BY c.code, k.tableau, k.kpi, d.annee"

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        # Documents CMF candidats + cellules déjà stockées, POUR CHAQUE
        # tableau à grille complète actif — repose directement sur la
        # table `documents` (indépendant de ce que `kpi_values` contient
        # déjà), puisque Annexe 12/13 peuvent ré-extraire en direct depuis
        # le PDF, sans jamais dépendre du narrow KPI déjà en base.
        full_grid_docs = {}       # key -> [(doc_id, code, nom, annee, nom_pdf), ...]
        full_grid_cellules = {}   # key -> {doc_id: grid}
        for key in active_full_grid_keys:
            spec = _FULL_GRID_SPECS[key]
            qk = """
                SELECT d.id, c.code, c.nom_entreprise, d.annee, d.nom_pdf
                FROM documents d
                JOIN sources s ON s.id = d.source_id
                JOIN societes c ON c.id = d.cmf_id
                WHERE s.nom = 'CMF'
            """
            pk = []
            if spec["exclusions_module"]:
                import importlib
                exclusions = getattr(importlib.import_module(spec["exclusions_module"]), spec["exclusions_name"])
                if exclusions:
                    qk += f" AND c.code NOT IN ({','.join(['%s'] * len(exclusions))})"
                    pk.extend(sorted(exclusions))
            if codes:
                placeholders = ",".join(["%s"] * len(codes))
                qk += f" AND c.code IN ({placeholders})"
                pk.extend(codes)
            if annees:
                placeholders = ",".join(["%s"] * len(annees))
                qk += f" AND d.annee IN ({placeholders})"
                pk.extend(annees)
            qk += " ORDER BY c.code, d.annee"
            with conn.cursor() as cur:
                cur.execute(qk, pk)
                docs = cur.fetchall()
            full_grid_docs[key] = docs
            if spec["preserve_order"]:
                # Bilan/Takaful : ordre RÉEL des lignes du PDF (voir
                # `_fetch_full_grid_by_doc`), pas de référentiel canonique.
                full_grid_cellules[key] = _fetch_full_grid_by_doc(conn, [d[0] for d in docs], key)
            else:
                cellules = {}
                for doc_id, ligne, colonne, valeur in get_tableau_cellules(conn, [d[0] for d in docs], key):
                    grid = cellules.setdefault(doc_id, {"colonnes": [], "lignes": {}})
                    if colonne not in grid["colonnes"]:
                        grid["colonnes"].append(colonne)
                    grid["lignes"].setdefault(ligne, {})[colonne] = valeur
                full_grid_cellules[key] = cellules
    finally:
        conn.close()

    # ── Regroupement société → tableau affiché → kpi → année → valeur ──────
    par_societe = {}  # code -> {"nom": ..., "blocs": {display: {kpi: {annee: valeur}}}, "grids": {key: {annee: grille_ou_None}}}

    def _get_soc(code, nom_entreprise):
        return par_societe.setdefault(
            code, {"nom": nom_entreprise, "blocs": {}, "grids": {k: {} for k in active_full_grid_keys}},
        )

    for code, nom_entreprise, annee, tableau, kpi, valeur_nombre, valeur_texte in rows:
        if tableau in superseded_raws:
            continue  # remplacé par la grille complète du tableau correspondant
        valeur = valeur_nombre if valeur_nombre is not None else valeur_texte
        soc = _get_soc(code, nom_entreprise)
        display = _resolve_display_tableau(tableau, active_group_keys)
        bloc = soc["blocs"].setdefault(display, {})
        bloc.setdefault(kpi, {})[annee] = valeur

    # Repli d'extraction LIVE (camelot, plusieurs secondes par document) —
    # borné, Annexe 12/13 SEULEMENT (seuls tableaux avec un extracteur
    # dédié réutilisable ici) : sans plafond, une sélection large (ex.
    # "toutes sociétés, toutes années") pouvait retenter en direct chaque
    # document jamais validé avec succès (~110 sur 223, voir
    # statut-validation-annexe13), rendant une requête HTTP synchrone
    # unique de dizaines de minutes — constaté en usage réel (export resté
    # "en cours" sans jamais aboutir). Budget SÉPARÉ par tableau : un
    # export "tous les tableaux" doit pouvoir rafraîchir Annexe 12 ET 13
    # indépendamment, sans qu'ils se disputent le même quota.
    MAX_LIVE_EXTRACTIONS = 15
    for key in active_full_grid_keys:
        spec = _FULL_GRID_SPECS[key]
        live_done = 0
        for doc_id, code, nom_entreprise, annee, nom_pdf in full_grid_docs[key]:
            soc = _get_soc(code, nom_entreprise)
            cached = full_grid_cellules[key].get(doc_id)
            if cached is not None:
                soc["grids"][key][annee] = cached
                continue
            if not spec["live_extractor"] or live_done >= MAX_LIVE_EXTRACTIONS:
                continue
            pdf_path = local_pdf_path("CMF", code, nom_pdf)
            if not pdf_path or not os.path.isfile(pdf_path):
                continue
            soc["grids"][key][annee] = spec["live_extractor"](pdf_path)
            live_done += 1

    wb = Workbook()
    wb.remove(wb.active)  # une vraie feuille par société/tableau ci-dessous ; pas de feuille "Sheet" vide

    if not par_societe:
        ws = wb.create_sheet("Export données")
        _write_sheet_title(ws, 4, "FS Market Intelligence — Export de données", "Aucune donnée pour cette sélection.")
    else:
        used_names = set()

        def _sheet_n_cols(soc, blocs_a_rendre, grids_a_rendre):
            """Largeur du bandeau de titre = la plus large colonne de TOUS
            les blocs/grilles rendus SUR CETTE feuille (calculée AVANT
            d'écrire quoi que ce soit) — sans ce pré-calcul, le bandeau se
            limitait à une largeur fixe devinée à l'avance, trop étroite
            dès qu'un bloc (ex. Annexe 13, jusqu'à 16 colonnes par branche)
            la dépassait : le fond sombre du titre s'arrêtait au milieu du
            tableau, visible comme un trait/une cassure verticale entre
            zone sombre et zone blanche au-dessus des colonnes suivantes."""
            return max(
                [2] +
                [1 + len({a for kpi_annees in soc["blocs"][name].values() for a in kpi_annees.keys()})
                 for name in blocs_a_rendre] +
                [n for key in grids_a_rendre
                 for n in (1 + sum(len(g["colonnes"]) for g in soc["grids"].get(key, {}).values() if g and g.get("lignes")), 2)]
            )

        def _write_narrow_block(ws, row, display_tableau, bloc):
            annees_bloc = sorted({a for kpi_annees in bloc.values() for a in kpi_annees.keys()})
            cols = ["KPI"] + [str(a) for a in annees_bloc]
            ws.cell(row=row, column=1, value=display_tableau).font = Font(bold=True, size=12, color=DARK, name="Calibri")
            row += 1
            for col_idx, header in enumerate(cols, start=1):
                cell = ws.cell(row=row, column=col_idx, value=header)
                cell.fill = PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")
                cell.font = Font(color=YELLOW, bold=True, name="Calibri", size=10)
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = _thin_border()
            row += 1
            for i, kpi in enumerate(sorted(bloc.keys())):
                fill = PatternFill(start_color=LIGHT, end_color=LIGHT, fill_type="solid") if i % 2 == 0 else None
                cell = ws.cell(row=row, column=1, value=kpi)
                cell.border = _thin_border()
                cell.font = Font(name="Calibri", size=10, color=DARK)
                cell.alignment = Alignment(horizontal="left", vertical="center")
                if fill:
                    cell.fill = fill
                for col_idx, annee in enumerate(annees_bloc, start=2):
                    val = bloc[kpi].get(annee)
                    c = ws.cell(row=row, column=col_idx, value=val)
                    c.border = _thin_border()
                    c.font = Font(name="Calibri", size=10, color=DARK)
                    c.alignment = Alignment(horizontal="center", vertical="center")
                    if fill:
                        c.fill = fill
                row += 1
            row += 2
            return row, len(cols)

        def _write_grid_section(ws, row, n_cols, key, grids):
            """UNE seule grille fusionnant toutes les années disponibles
            (voir _write_multi_year_grid_block) — pas un tableau complet
            répété par année. Si UNE SEULE année est disponible, le
            résultat est visuellement identique à l'ancien rendu par
            année (aucune perte pour le cas le plus simple)."""
            spec = _FULL_GRID_SPECS[key]
            annees_a_rendre = sorted(a for a, g in grids.items() if g and g.get("lignes"))
            if not annees_a_rendre:
                return row, n_cols
            # Le titre (et l'année si une seule) est écrit PAR
            # _write_multi_year_grid_block elle-même, centré sur la
            # largeur RÉELLE de ce tableau plutôt que celle, potentiellement
            # plus large, de la feuille entière — voir son docstring.
            row, used_cols = _write_multi_year_grid_block(
                ws, row, grids, spec["display"],
                row_order=spec["row_order"], row_order_fallback=spec["row_order_fallback"],
                preserve_order=spec["preserve_order"],
            )
            n_cols = max(n_cols, used_cols)
            return row, n_cols

        def _write_logo_and_finish(ws, code, n_cols):
            _autosize_columns(ws)
            # Logo de la société (déjà disponible dans le projet, réutilisé
            # tel quel — voir _LOGO_FILES) — ajouté APRÈS l'auto-ajustement
            # des largeurs (ci-dessus), pour connaître la largeur réelle du
            # tableau (nécessaire pour le centrage). Placé sur la ligne 3,
            # le blanc entre le bandeau société (lignes 1-2) et le titre du
            # premier bloc (ligne 4) — retour utilisateur : "entre les deux
            # titres" — et centré horizontalement sur la largeur du tableau.
            logo_path = _logo_path(code)
            if logo_path:
                try:
                    logo_w, logo_h = _logo_dimensions(logo_path)
                    ws.row_dimensions[3].height = max(logo_h + 6, 20)
                    logo_img = XLImage(logo_path)
                    logo_img.width, logo_img.height = logo_w, logo_h
                    logo_img.anchor = _centered_anchor(ws, 3, n_cols, logo_w, logo_h)
                    ws.add_image(logo_img)
                except Exception:
                    pass  # image illisible/corrompue : ne doit jamais faire échouer l'export
            # Pas de freeze_panes : Excel dessine une ligne de démarcation
            # (souvent perçue comme un "trait" résiduel) à la limite d'un
            # volet figé, même une fois la sélection multi-volets corrigée
            # — supprimé entièrement plutôt que de continuer à chercher à
            # neutraliser un rendu natif d'Excel.
            ws.sheet_view.selection = [Selection(pane="topLeft", activeCell="A1", sqref="A1")]

        # TOUJOURS une feuille PAR SOCIÉTÉ, quel que soit le nombre de
        # tableaux sélectionnés — c'est la structure originale, confirmée
        # explicitement par l'utilisatrice (retour direct, 2026-09-17,
        # après une tentative de "feuille par tableau" non demandée et non
        # voulue) : "le fichier Excel réparti par sheet et chaque sheet
        # contient le traitement d'une société. Dans chaque sheet, on va
        # trouver l'annexe 13 et le bilan actif [...] de la société en
        # question."
        for code in sorted(par_societe.keys()):
            soc = par_societe[code]
            sheet_name = _safe_sheet_name(code, used_names)
            ws = wb.create_sheet(sheet_name)
            blocs_a_rendre = sorted(soc["blocs"].keys())
            grids_a_rendre = [k for k in active_full_grid_keys if soc["grids"].get(k)]
            n_cols = _sheet_n_cols(soc, blocs_a_rendre, grids_a_rendre)
            _write_sheet_title(ws, n_cols, f"{soc['nom'] or code} ({code})", "FS Market Intelligence — Export de données")
            row = 4
            for display_tableau in blocs_a_rendre:
                row, used_cols = _write_narrow_block(ws, row, display_tableau, soc["blocs"][display_tableau])
                n_cols = max(n_cols, used_cols)
            for key in grids_a_rendre:
                row, n_cols = _write_grid_section(ws, row, n_cols, key, soc["grids"][key])
            _write_logo_and_finish(ws, code, n_cols)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
