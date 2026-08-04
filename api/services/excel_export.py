"""Génération de l'export Excel — Analyse Comparative — avec formules
recalculables pour les ratios simples (ROE, ROA, Ratio de frais, PDM).

Ratio combiné et Ratio de sinistralité restent des valeurs figées : leur
calcul réel (kpi_builder.py::build_company_row) enchaîne ~15 règles de
repli (agrégation Vie/Non-Vie, détection de valeurs non fiables,
invalidation croisée RC/RF...) — les reproduire comme formules tableur
risquerait de produire des chiffres qui divergent silencieusement de
l'application, la classe de bug precisement traquee dans Qualité Data
cette session."""

import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment

from api.utils.formatters import kpis_by_year
from database.repository import get_connection, list_documents_by_source, get_kpi_values_for_document

DARK = "2E2E38"
YELLOW = "FFE600"
LIGHT = "F4F4F7"

_RAW_KPIS = [
    "Primes émises par assurance", "Résultat Net", "Capitaux propres",
    "Total actif", "Charges d'acquisition et de gestion nettes",
]


def _header_fill():
    return PatternFill(start_color=DARK, end_color=DARK, fill_type="solid")


def _header_font():
    return Font(color=YELLOW, bold=True, name="Calibri", size=10)


def _thin_border():
    side = Side(style="thin", color="DDDDE3")
    return Border(left=side, right=side, top=side, bottom=side)


def build_analyse_comparative_xlsx(annee):
    conn = get_connection()
    try:
        raw_by_company = {}
        for doc_id, _cmf_id, code, doc_annee in list_documents_by_source(conn, "CMF"):
            if doc_annee != annee or not code:
                continue
            kpis = get_kpi_values_for_document(conn, doc_id)
            if any(kpis.get(k) is not None for k in _RAW_KPIS):
                raw_by_company[code] = kpis

        ftusa = kpis_by_year(conn, "FTUSA").get(annee, {})
        total_marche = ftusa.get("Total Primes émises")

        from api.app import app
        from api.routes.comparative import analyse_comparative
        with app.test_request_context(f"/x?annee={annee}"):
            comp_data = analyse_comparative().get_json()
    finally:
        conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = f"Analyse Comparative {annee}"

    headers = [
        "Compagnie", "Primes émises (MDT)", "Résultat net (MDT)",
        "Capitaux propres (MDT)", "Total actif (MDT)",
        "Charges d'acquisition et de gestion nettes (MDT)",
        "PDM (%)", "ROE (%)", "ROA (%)", "Ratio de frais de gestion (%)",
        "Ratio combiné (%)*", "Ratio de sinistralité (%)*",
    ]
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = _header_fill()
        cell.font = _header_font()
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _thin_border()
    ws.row_dimensions[1].height = 32

    # Cellule dédiée au total marché (référencée par les formules PDM)
    total_marche_row = 1
    total_marche_col = len(headers) + 2  # colonne isolée, à droite du tableau
    ws.cell(row=total_marche_row, column=total_marche_col, value="Total primes marché (MDT)").font = Font(bold=True, size=9)
    total_marche_cell = ws.cell(row=total_marche_row + 1, column=total_marche_col,
                                 value=round(total_marche / 1_000_000, 3) if total_marche else None)
    total_marche_ref = f"${get_column_letter(total_marche_col)}${total_marche_row + 1}"

    codes_sorted = sorted(
        comp_data.keys(),
        key=lambda c: (comp_data[c].get("pdm") if comp_data[c].get("pdm") is not None else -1),
        reverse=True,
    )

    row_idx = 2
    for code in codes_sorted:
        kpis = raw_by_company.get(code, {})
        comp = comp_data[code]

        def mdt(kpi_name):
            v = kpis.get(kpi_name)
            return round(v / 1_000_000, 3) if v is not None else None

        primes = mdt("Primes émises par assurance")
        resultat = mdt("Résultat Net")
        capitaux = mdt("Capitaux propres")
        actif = mdt("Total actif")
        charges_frais = mdt("Charges d'acquisition et de gestion nettes")

        c_primes    = f"B{row_idx}"
        c_resultat  = f"C{row_idx}"
        c_capitaux  = f"D{row_idx}"
        c_actif     = f"E{row_idx}"
        c_charges   = f"F{row_idx}"

        ws.append([
            code, primes, resultat, capitaux, actif, charges_frais,
            f"=IF(OR({c_primes}=\"\",{total_marche_ref}=\"\",{total_marche_ref}=0),\"\",{c_primes}/{total_marche_ref}*100)",
            f"=IF(OR({c_resultat}=\"\",{c_capitaux}=\"\",{c_capitaux}=0),\"\",{c_resultat}/{c_capitaux}*100)",
            f"=IF(OR({c_resultat}=\"\",{c_actif}=\"\",{c_actif}=0),\"\",{c_resultat}/{c_actif}*100)",
            f"=IF(OR({c_charges}=\"\",{c_primes}=\"\",{c_primes}=0),\"\",ABS({c_charges})/{c_primes}*100)",
            comp.get("ratio_combine"),
            comp.get("ratio_sp"),
        ])

        fill = PatternFill(start_color=LIGHT, end_color=LIGHT, fill_type="solid") if row_idx % 2 == 0 else None
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = _thin_border()
            if fill:
                cell.fill = fill
            if col_idx > 1:
                cell.number_format = "0.0"
        row_idx += 1

    note = ws.cell(row=1, column=11, value="Ratio combiné (%)*")
    note.comment = Comment(
        "Valeur figée, calculée côté serveur — identique à celle affichée dans "
        "l'application. Non recalculable ici : sa formule réelle enchaîne "
        "plusieurs règles de repli (agrégation Vie/Non-Vie, détection de "
        "valeurs non fiables) trop complexes pour une formule tableur fiable.",
        "FS Market Intelligence", height=140, width=260,
    )
    note2 = ws.cell(row=1, column=12, value="Ratio de sinistralité (%)*")
    note2.comment = Comment(
        "Valeur figée — même raison que Ratio combiné (voir commentaire de cette colonne).",
        "FS Market Intelligence", height=80, width=260,
    )
    ws.cell(row=1, column=6).comment = Comment(
        "Convention comptable : les charges sont stockées en négatif (sortie "
        "de trésorerie). Le Ratio de frais applique ABS() sur cette colonne.",
        "FS Market Intelligence", height=90, width=240,
    )

    for col_idx, width in enumerate([14, 16, 16, 18, 16, 30, 10, 10, 10, 16, 16, 18], start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    ws.column_dimensions[get_column_letter(total_marche_col)].width = 20

    ws.freeze_panes = "A2"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
