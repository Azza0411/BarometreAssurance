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

from database.repository import get_connection, list_all_documents

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_DATA_DIR = os.path.join(_PROJECT_ROOT, "data")

# Sources dont chaque document correspond à un vrai fichier PDF stocké en
# local (téléchargé par le scraper), avec son schéma de chemin propre.
# BVMT/INS sont des scrapes de pages HTML (pas de PDF individuel) et ENQUETE
# vient d'un fichier Excel unique fourni par l'utilisateur — pour ces
# 3 sources, aucun fichier local par document : le lien externe reste la
# seule référence consultable.
def _local_pdf_path(source_nom, code, nom_pdf):
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
        local_path = _local_pdf_path(source_nom, code, nom_pdf)
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
    path = _local_pdf_path(source_nom, code, nom_pdf)
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


def build_flexible_export_xlsx(tableau_keys=None, codes=None, annees=None):
    """Génère un export Excel "brut" (format long : une ligne par valeur de
    KPI) filtré sur n'importe quelle combinaison de tableaux/sociétés/années
    — chaque filtre vide/absent signifie "tous". C'est la fonction derrière
    les cas d'usage : "tous les Annexe 12 de toutes les compagnies en 2024",
    "tous les tableaux financiers de COMAR", "tous les tableaux par années
    de toutes les entreprises", etc."""
    raw_tableaux = _raw_tableaux_for_groups(tableau_keys)

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
        query += " ORDER BY c.code, d.annee, k.tableau, k.kpi"

        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Export données"

    headers = ["Code compagnie", "Compagnie", "Année", "Tableau", "KPI", "Valeur (nombre)", "Valeur (texte)"]

    for r in (1,):
        for col_idx in range(1, len(headers) + 1):
            ws.cell(row=r, column=col_idx).fill = PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")
    ws.merge_cells(f"A1:{get_column_letter(len(headers))}1")
    ws["A1"] = f"FS Market Intelligence — Export de données ({len(rows)} valeurs)"
    ws["A1"].font = Font(color="FFFFFF", bold=True, size=13, name="Calibri")
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 6
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = DARK

    header_row = 3
    for col_idx, value in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=value)
        cell.fill = PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")
        cell.font = Font(color=YELLOW, bold=True, name="Calibri", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _thin_border()
    ws.row_dimensions[header_row].height = 22

    row_idx = header_row + 1
    for code, nom_entreprise, annee, tableau, kpi, valeur_nombre, valeur_texte in rows:
        values = [code, nom_entreprise, annee, tableau, kpi, valeur_nombre, valeur_texte]
        fill = PatternFill(start_color=LIGHT, end_color=LIGHT, fill_type="solid") if row_idx % 2 == 0 else None
        for col_idx, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = _thin_border()
            cell.font = Font(name="Calibri", size=10, color=DARK)
            cell.alignment = Alignment(horizontal="left" if col_idx in (2, 4, 5) else "center", vertical="center")
            if fill:
                cell.fill = fill
        row_idx += 1

    widths = [16, 32, 9, 26, 34, 15, 20]
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    ws.freeze_panes = f"A{header_row + 1}"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
