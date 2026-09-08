"""Logique de la page "Gestion de base de données" : liste des documents
scrapés (avec résolution du fichier PDF réellement stocké en local), listes
d'options pour les filtres d'export, et génération de l'export Excel
flexible (n'importe quelle combinaison Tableau × Société × Année).

Séparé de excel_export.py (dédié à l'export figé "Analyse Comparative") —
ici l'export est un extrait BRUT de kpi_values (format long : une ligne par
valeur de KPI), pas une mise en page métier avec formules recalculables.
"""

import os

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io

from database.repository import get_connection, list_all_documents, get_tableau_cellules
from extraction.annexe13_kpi_extractor import (
    _is_target_page as _is_annexe13_page,
    RACCORDEMENT_RE as _ANNEXE13_RACCORDEMENT_RE,
    KPI_PATTERNS as _ANNEXE13_KPI_PATTERNS,
)
from extraction.full_table_extractor import locate_and_extract_full_table, relaxed_is_annexe13_page
from extraction.annexe13_pipeline import normalize_table, CANONICAL_ROWS

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")

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
    ("bilan", "Bilan (Actif / Passif)", ["Bilan"]),
    ("resultat", "État de résultat", ["Etat de resultat (technique / global)"]),
    ("calcul", "Ratios calculés (interne)", ["Calcul interne"]),
    ("presentation", "Présentation de la société", ["Presentation de la societe"]),
]
_TABLEAU_GROUP_TO_RAW = {key: raws for key, _label, raws in TABLEAU_GROUPS}


def get_filter_options(conn):
    """Options disponibles pour les 3 filtres de l'export flexible :
    sociétés CMF (code + nom), années CMF disponibles, groupes de tableaux."""
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
    tableaux = [{"key": key, "label": label} for key, label, _raws in TABLEAU_GROUPS]
    return {"societes": societes, "annees": annees, "tableaux": tableaux}


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
    last_col = max(last_col, 2)
    for col_idx in range(1, last_col + 1):
        ws.cell(row=1, column=col_idx).fill = PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=last_col)
    ws.cell(row=1, column=1, value=title)
    ws.cell(row=1, column=1).font = Font(color="FFFFFF", bold=True, size=13, name="Calibri")
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 26
    if subtitle:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=last_col)
        ws.cell(row=2, column=1, value=subtitle)
        ws.cell(row=2, column=1).font = Font(color=YELLOW, size=10, name="Calibri")
        ws.cell(row=2, column=1).alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 18
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = DARK


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


# Position de chaque poste dans l'ordre naturel du tableau (ordre déjà
# significatif de CANONICAL_ROWS — annexe13_pipeline.py, celui d'un vrai
# relevé "Résultat technique" : Primes en premier, Résultat technique et
# provisions en dernier) — sans ça, l'ordre dépend de la source (DB triée
# par libellé le temps d'une requête sans ORDER BY explicite, ou ordre
# d'apparition PDF pour le repli live) et n'est jamais celui attendu.
_ROW_DISPLAY_ORDER = {label: i for i, label in enumerate(CANONICAL_ROWS)}


def _sorted_grid_rows(lignes):
    return sorted(lignes.items(), key=lambda kv: (_ROW_DISPLAY_ORDER.get(kv[0], len(CANONICAL_ROWS)), kv[0]))


def _write_full_grid_block(ws, row, annee, grid):
    cols = grid["colonnes"]
    ws.cell(row=row, column=1, value=f"{annee} — tableau complet ({len(grid['lignes'])} lignes × {len(cols)} colonnes)")
    ws.cell(row=row, column=1).font = Font(italic=True, size=10, color=DARK, name="Calibri")
    row += 1
    # En majuscules à l'affichage (ex. "A.TRAVAIL", "INCENDIE", "TOTAL") —
    # c'est la convention réelle des en-têtes de branche dans les documents
    # source, cohérente avec ce que produit le libellé de ligne (poste
    # comptable canonique, lui en casse normale).
    headers = ["Libellé"] + [c.upper() for c in cols]
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col_idx, value=header)
        cell.fill = PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")
        cell.font = Font(color=YELLOW, bold=True, name="Calibri", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _thin_border()
    row += 1
    for i, (label, values) in enumerate(_sorted_grid_rows(grid["lignes"])):
        fill = PatternFill(start_color=LIGHT, end_color=LIGHT, fill_type="solid") if i % 2 == 0 else None
        cell = ws.cell(row=row, column=1, value=label or "")
        cell.border = _thin_border()
        cell.font = Font(name="Calibri", size=10, color=DARK)
        cell.alignment = Alignment(horizontal="left", vertical="center")
        if fill:
            cell.fill = fill
        for col_idx, col in enumerate(cols, start=2):
            val = values.get(col)
            c = ws.cell(row=row, column=col_idx, value=val)
            c.border = _thin_border()
            c.font = Font(name="Calibri", size=10, color=DARK)
            c.alignment = Alignment(horizontal="center", vertical="center")
            if fill:
                c.fill = fill
        row += 1
    row += 2
    return row, len(headers)


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
    Une feuille par société, et dans chaque feuille, un vrai tableau
    (KPI en lignes, année en colonnes) par tableau source demandé — pas une
    liste plate. C'est la fonction derrière les cas d'usage : "tous les
    Annexe 12 de toutes les compagnies en 2024" (une feuille par société,
    chacune avec son Annexe 12 2024), "tous les tableaux financiers de
    COMAR" (une feuille COMAR avec un bloc par tableau), "tous les tableaux
    par années de toutes les entreprises" (une feuille par société, un bloc
    par tableau, une colonne par année)."""
    raw_tableaux = _raw_tableaux_for_groups(tableau_keys)
    # Annexe 13 est ré-extraite en grille complète directement depuis le PDF
    # (voir _extract_annexe13_full_grid) dès qu'elle fait partie de la
    # sélection — y compris quand tableau_keys est vide/absent ("tous les
    # tableaux"). Le sous-ensemble à 7 KPI reste quand même récupéré via
    # kpi_values ci-dessous : il sert de repli pour les documents où la
    # grille complète échoue (voir extraction/CAS_PARTICULIERS_FULL_TABLE.md).
    include_annexe13_full = not tableau_keys or "annexe13" in tableau_keys
    _ANNEXE13_DISPLAY = _display_tableau("Annexe13")

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

        # Documents CMF candidats pour la grille complète Annexe 13 — repose
        # directement sur la table documents (indépendant de ce que
        # kpi_values contient déjà) puisque l'extraction complète relit le
        # PDF elle-même plutôt que de réutiliser les KPI déjà stockés.
        annexe13_docs = []
        annexe13_cellules_by_doc = {}
        if include_annexe13_full:
            q2 = """
                SELECT d.id, c.code, c.nom_entreprise, d.annee, d.nom_pdf
                FROM documents d
                JOIN sources s ON s.id = d.source_id
                JOIN societes c ON c.id = d.cmf_id
                WHERE s.nom = 'CMF'
            """
            p2 = []
            if codes:
                placeholders = ",".join(["%s"] * len(codes))
                q2 += f" AND c.code IN ({placeholders})"
                p2.extend(codes)
            if annees:
                placeholders = ",".join(["%s"] * len(annees))
                q2 += f" AND d.annee IN ({placeholders})"
                p2.extend(annees)
            q2 += " ORDER BY c.code, d.annee"
            with conn.cursor() as cur:
                cur.execute(q2, p2)
                annexe13_docs = cur.fetchall()
            # Cellules déjà validées en base (extraction/annexe13_pipeline.py
            # via api/services/tableau_pipeline_service.py) : chemin rapide,
            # évite de re-parser le PDF pour les documents déjà traités.
            # Repli sur l'extraction live (ci-dessous) pour les autres —
            # jamais d'export vide simplement parce que la validation n'a
            # pas encore tourné pour ce document.
            doc_ids = [doc_id for doc_id, *_ in annexe13_docs]
            for doc_id, ligne, colonne, valeur in get_tableau_cellules(conn, doc_ids, "annexe13"):
                grid = annexe13_cellules_by_doc.setdefault(doc_id, {"colonnes": [], "lignes": {}})
                if colonne not in grid["colonnes"]:
                    grid["colonnes"].append(colonne)
                grid["lignes"].setdefault(ligne, {})[colonne] = valeur
    finally:
        conn.close()

    # ── Regroupement société → tableau affiché → kpi → année → valeur ──────
    par_societe = {}  # code -> {"nom": ..., "blocs": {display_tableau: {kpi: {annee: valeur}}}, "annexe13_grids": {annee: grille_ou_None}}
    for code, nom_entreprise, annee, tableau, kpi, valeur_nombre, valeur_texte in rows:
        valeur = valeur_nombre if valeur_nombre is not None else valeur_texte
        soc = par_societe.setdefault(code, {"nom": nom_entreprise, "blocs": {}, "annexe13_grids": {}})
        display = _display_tableau(tableau)
        bloc = soc["blocs"].setdefault(display, {})
        bloc.setdefault(kpi, {})[annee] = valeur

    for doc_id, code, nom_entreprise, annee, nom_pdf in annexe13_docs:
        soc = par_societe.setdefault(code, {"nom": nom_entreprise, "blocs": {}, "annexe13_grids": {}})
        cached = annexe13_cellules_by_doc.get(doc_id)
        if cached is not None:
            soc["annexe13_grids"][annee] = cached
            continue
        pdf_path = local_pdf_path("CMF", code, nom_pdf)
        if not pdf_path or not os.path.isfile(pdf_path):
            continue
        soc["annexe13_grids"][annee] = _extract_annexe13_full_grid(pdf_path)

    wb = Workbook()
    wb.remove(wb.active)  # une vraie feuille par société ci-dessous ; pas de feuille "Sheet" vide

    if not par_societe:
        ws = wb.create_sheet("Export données")
        _write_sheet_title(ws, 4, "FS Market Intelligence — Export de données", "Aucune donnée pour cette sélection.")
    else:
        used_names = set()
        for code in sorted(par_societe.keys()):
            soc = par_societe[code]
            sheet_name = _safe_sheet_name(code, used_names)
            ws = wb.create_sheet(sheet_name)

            # Largeur du bandeau de titre = la plus large colonne de TOUS les
            # blocs de la feuille (calculée AVANT d'écrire quoi que ce soit) —
            # sans ce pré-calcul, le bandeau se limitait à une largeur fixe
            # devinée à l'avance (6), trop étroite dès qu'un bloc (ex. Annexe
            # 13, jusqu'à 16 colonnes par branche) la dépassait : le fond
            # sombre du titre s'arrêtait au milieu du tableau, visible comme
            # un trait/une cassure verticale entre zone sombre et zone
            # blanche au-dessus des colonnes suivantes.
            n_cols = max(
                [2] +
                [1 + len({a for kpi_annees in bloc.values() for a in kpi_annees.keys()})
                 for name, bloc in soc["blocs"].items() if not (name == _ANNEXE13_DISPLAY and include_annexe13_full)] +
                ([1 + max((len(g["colonnes"]) for g in soc.get("annexe13_grids", {}).values() if g and g.get("lignes")), default=0),
                  2] if include_annexe13_full else [])
            )
            _write_sheet_title(ws, n_cols, f"{soc['nom'] or code} ({code})", "FS Market Intelligence — Export de données")

            row = 4
            for display_tableau in sorted(soc["blocs"].keys()):
                if display_tableau == _ANNEXE13_DISPLAY and include_annexe13_full:
                    continue  # remplacé par la grille complète ci-dessous
                bloc = soc["blocs"][display_tableau]
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
                header_row_idx = row
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

                row += 2  # espacement avant le bloc suivant
                n_cols = max(n_cols, len(cols))

            if include_annexe13_full:
                grids = soc.get("annexe13_grids", {})
                narrow_annexe13 = soc["blocs"].get(_ANNEXE13_DISPLAY, {})
                annees_a_rendre = sorted(grids.keys())
                if annees_a_rendre:
                    ws.cell(row=row, column=1, value=f"{_ANNEXE13_DISPLAY} (tableau complet, toutes branches)")
                    ws.cell(row=row, column=1).font = Font(bold=True, size=12, color=DARK, name="Calibri")
                    row += 1
                    for annee in annees_a_rendre:
                        grid = grids[annee]
                        if grid and grid.get("lignes"):
                            row, used_cols = _write_full_grid_block(ws, row, annee, grid)
                        else:
                            row, used_cols = _write_narrow_fallback_block(ws, row, annee, narrow_annexe13)
                        n_cols = max(n_cols, used_cols)

            ws.column_dimensions["A"].width = 42
            for col_idx in range(2, n_cols + 1):
                ws.column_dimensions[get_column_letter(col_idx)].width = 14
            ws.freeze_panes = "B4"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
