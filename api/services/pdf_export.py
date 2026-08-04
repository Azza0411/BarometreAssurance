"""Génération de rapports PDF (Export PDF) : Fiche compagnie, Analyse
Comparative, Aperçu Marché. Réutilise directement les vues Flask existantes
(via test_request_context) pour ne dupliquer aucune règle métier — la même
donnée que celle affichée à l'écran est celle exportée."""

import io
import os
from datetime import datetime

from flask import current_app
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

DARK   = colors.HexColor("#2E2E38")
YELLOW = colors.HexColor("#FFE600")
BLUE   = colors.HexColor("#3A6EA8")
GREY   = colors.HexColor("#9A9AA8")
LIGHT  = colors.HexColor("#F4F4F7")
WHITE  = colors.white

_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "EyDark.png",
)
# Copie locale (api/assets/) plutôt qu'un lien vers frontend/public/logos/ :
# Dockerfile.api ne copie pas le dossier frontend/ dans l'image, le logo
# serait introuvable (silencieusement omis, cf. le if os.path.exists ci-dessous).
_LOGO_ASPECT = 0.836  # largeur/hauteur du PNG source (474x567) — évite un
                      # étirement/débordement si drawImage() ne préserve pas
                      # le ratio comme attendu quand une seule dimension est fournie.

_styles = getSampleStyleSheet()
STYLE_TITLE = ParagraphStyle("EYTitle", parent=_styles["Title"], textColor=WHITE,
                              fontSize=18, leading=22, alignment=TA_LEFT)
STYLE_SUBTITLE = ParagraphStyle("EYSubtitle", parent=_styles["Normal"], textColor=YELLOW,
                                 fontSize=11, leading=14, alignment=TA_LEFT)
STYLE_SECTION = ParagraphStyle("EYSection", parent=_styles["Heading2"], textColor=DARK,
                                fontSize=13, spaceBefore=14, spaceAfter=6)
STYLE_BODY = ParagraphStyle("EYBody", parent=_styles["Normal"], fontSize=9, leading=12)
STYLE_KPI_LABEL = ParagraphStyle("EYKpiLabel", parent=_styles["Normal"], fontSize=8,
                                  textColor=GREY, alignment=TA_LEFT)
STYLE_KPI_VALUE = ParagraphStyle("EYKpiValue", parent=_styles["Normal"], fontSize=15,
                                  textColor=DARK, leading=18, alignment=TA_LEFT)


def _route_json(view_func, query_string=""):
    """Appelle une vue Flask existante hors contexte de requête HTTP réel et
    renvoie son JSON — même donnée que celle affichée à l'écran, sans
    dupliquer la logique métier (calculs, filter_reliable, fallbacks)."""
    app = current_app._get_current_object()
    with app.test_request_context(query_string and f"/x?{query_string}" or "/x"):
        resp = view_func()
        return resp.get_json()


def _fmt(value, unit="", decimals=1, na="—"):
    if value is None:
        return na
    if isinstance(value, (int, float)):
        s = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
        return f"{s} {unit}".strip()
    return str(value)


def _header_footer(title, subtitle):
    def _draw(cnv, doc):
        cnv.saveState()
        page_w, page_h = A4
        # Bandeau d'en-tête
        cnv.setFillColor(DARK)
        cnv.rect(0, page_h - 2.6 * cm, page_w, 2.6 * cm, fill=1, stroke=0)
        if os.path.exists(_LOGO_PATH):
            try:
                logo_h = 1.1 * cm
                logo_w = logo_h * _LOGO_ASPECT
                cnv.drawImage(_LOGO_PATH, 1.5 * cm, page_h - 2.05 * cm,
                               width=logo_w, height=logo_h, mask="auto")
            except Exception:
                pass
        cnv.setFillColor(WHITE)
        cnv.setFont("Helvetica-Bold", 15)
        cnv.drawString(4.2 * cm, page_h - 1.35 * cm, title)
        cnv.setFillColor(YELLOW)
        cnv.setFont("Helvetica", 10)
        cnv.drawString(4.2 * cm, page_h - 1.9 * cm, subtitle)
        # Pied de page
        cnv.setFillColor(GREY)
        cnv.setFont("Helvetica", 7.5)
        cnv.drawString(1.5 * cm, 1.2 * cm,
                        f"FS Market Intelligence · Confidentiel EY · Généré le "
                        f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}")
        cnv.drawRightString(page_w - 1.5 * cm, 1.2 * cm, f"Page {doc.page}")
        cnv.restoreState()
    return _draw


def _doc(buffer, title, subtitle):
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=3.2 * cm, bottomMargin=2 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    draw = _header_footer(title, subtitle)
    doc.build_with_header = lambda flowables: doc.build(
        flowables, onFirstPage=draw, onLaterPages=draw
    )
    return doc


def _table(data, col_widths=None, align_right_from=1):
    """Table stylée EY : en-tête sombre/jaune, lignes alternées."""
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), YELLOW),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDE3")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    if align_right_from is not None:
        style.append(("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"))
    t.setStyle(TableStyle(style))
    return t


def _kpi_row(items):
    """items: [(label, value), ...] — grille de 4 cartes KPI par ligne."""
    rows, cur = [], []
    for label, value in items:
        cur.append([Paragraph(label, STYLE_KPI_LABEL), Paragraph(value, STYLE_KPI_VALUE)])
        if len(cur) == 4:
            rows.append(cur)
            cur = []
    if cur:
        while len(cur) < 4:
            cur.append(["", ""])
        rows.append(cur)
    flat = [[c[1] for c in row] for row in rows]  # valeurs
    labels = [[c[0] for c in row] for row in rows]
    # Intercale label/valeur verticalement dans une même cellule via Table imbriquée
    cells = []
    for row in rows:
        cells.append([
            Table([[c[0]], [c[1]]], colWidths=[4.1 * cm])
            for c in row
        ])
    t = Table(cells, colWidths=[4.3 * cm] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0, WHITE),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


# ─────────────────────────────────────────────────────────────────────────
#  1. Fiche compagnie (Vue par Assurance)
# ─────────────────────────────────────────────────────────────────────────

def build_fiche_compagnie_pdf(code, annee):
    from api.routes.vue_assurance import (
        vue_assurance_profil, vue_assurance_bilan, vue_assurance_evolution,
    )

    profil = _route_json(vue_assurance_profil, f"code={code}&annee={annee}")
    bilan = _route_json(vue_assurance_bilan, f"code={code}&annee={annee}")
    evolution = _route_json(vue_assurance_evolution, f"code={code}")

    buffer = io.BytesIO()
    doc = _doc(buffer, f"Fiche compagnie — {code}",
               f"Exercice {profil.get('annee') or annee} · FS Market Intelligence")

    flow = [Spacer(1, 0.2 * cm)]
    flow.append(_kpi_row([
        ("Primes émises (MDT)", _fmt(profil.get("primes_emises"))),
        ("Résultat net (MDT)", _fmt(profil.get("resultat_net"))),
        ("Total actif (MDT)", _fmt(profil.get("total_actif"))),
        ("Part de marché", _fmt(profil.get("pdm"), "%")),
        ("ROE", _fmt(profil.get("roe"), "%")),
        ("ROA", _fmt(profil.get("roa"), "%")),
        ("Ratio combiné", _fmt(profil.get("ratio_combine"), "%")),
        ("Ratio de sinistralité", _fmt(profil.get("ratio_sp"), "%")),
    ]))

    if profil.get("siege_social"):
        flow.append(Spacer(1, 0.3 * cm))
        flow.append(Paragraph(f"Siège social : {profil['siege_social']}", STYLE_BODY))

    flow.append(Paragraph("Bilan (MDT)", STYLE_SECTION))
    if bilan.get("actif") or bilan.get("passif"):
        actif_rows = [["Actif", "Valeur (MDT)"]] + [
            [it["label"], _fmt(it["value"], decimals=1)] for it in bilan.get("actif", [])
        ]
        passif_rows = [["Passif", "Valeur (MDT)"]] + [
            [it["label"], _fmt(it["value"], decimals=1)] for it in bilan.get("passif", [])
        ]
        two_col = Table([[
            _table(actif_rows, col_widths=[5.5 * cm, 3 * cm]),
            _table(passif_rows, col_widths=[5.5 * cm, 3 * cm]),
        ]], colWidths=[9 * cm, 9 * cm])
        two_col.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        flow.append(two_col)
    else:
        flow.append(Paragraph(
            f"Bilan non disponible pour {code} sur l'exercice {bilan.get('annee') or annee}.",
            STYLE_BODY,
        ))

    if evolution:
        flow.append(Paragraph("Évolution historique", STYLE_SECTION))
        years = sorted(evolution.keys())
        header = ["Année", "Primes (MDT)", "Résultat net (MDT)", "Total actif (MDT)",
                  "ROE (%)", "Ratio combiné (%)", "PDM (%)"]
        rows = [header]
        for y in years:
            d = evolution[y]
            rows.append([
                y, _fmt(d.get("primes_emises")), _fmt(d.get("resultat_net")),
                _fmt(d.get("total_actif")), _fmt(d.get("roe")),
                _fmt(d.get("ratio_combine")), _fmt(d.get("pdm")),
            ])
        flow.append(_table(rows, col_widths=[1.8 * cm, 2.7 * cm, 3 * cm, 2.8 * cm, 2.2 * cm, 2.8 * cm, 2.2 * cm]))

    doc.build_with_header(flow)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────────────────────────────────
#  2. Analyse Comparative
# ─────────────────────────────────────────────────────────────────────────

def build_analyse_comparative_pdf(annee):
    from api.routes.comparative import analyse_comparative

    data = _route_json(analyse_comparative, f"annee={annee}")

    buffer = io.BytesIO()
    doc = _doc(buffer, "Analyse Comparative", f"Exercice {annee} · FS Market Intelligence")

    rows_sorted = sorted(
        data.items(), key=lambda kv: (kv[1].get("pdm") or -1), reverse=True
    )
    header = ["Compagnie", "PDM (%)", "Primes (MDT)", "Ratio combiné (%)",
              "Ratio S/P (%)", "Ratio frais (%)", "ROE (%)", "ROA (%)"]
    rows = [header]
    for code, row in rows_sorted:
        rows.append([
            code, _fmt(row.get("pdm")), _fmt(row.get("primes")),
            _fmt(row.get("ratio_combine")), _fmt(row.get("ratio_sp")),
            _fmt(row.get("ratio_frais")), _fmt(row.get("roe")), _fmt(row.get("roa")),
        ])

    flow = [Spacer(1, 0.2 * cm),
            Paragraph(f"{len(rows_sorted)} compagnie(s) — triées par part de marché décroissante", STYLE_BODY),
            Spacer(1, 0.3 * cm),
            _table(rows, col_widths=[2.6*cm, 1.8*cm, 2.4*cm, 2.6*cm, 2.2*cm, 2.2*cm, 1.8*cm, 1.8*cm])]

    doc.build_with_header(flow)
    buffer.seek(0)
    return buffer


# ─────────────────────────────────────────────────────────────────────────
#  3. Aperçu Marché
# ─────────────────────────────────────────────────────────────────────────

def build_apercu_marche_pdf(annee):
    from api.routes.apercu_marche import (
        apercu_marche_profil_pays, apercu_marche_ratios, apercu_marche_distribution_agences,
    )

    profil = _route_json(apercu_marche_profil_pays, f"annee={annee}")
    ratios = _route_json(apercu_marche_ratios, f"annee={annee}")
    agences = _route_json(apercu_marche_distribution_agences, f"annee={annee}")

    buffer = io.BytesIO()
    doc = _doc(buffer, "Aperçu Marché", f"Exercice {annee} · Marché tunisien de l'assurance")

    flow = [Spacer(1, 0.2 * cm)]
    flow.append(_kpi_row([
        ("Population (hab.)", _fmt(profil.get("population"), decimals=0)),
        ("PIB (MDT)", _fmt(profil.get("pib_mdt"), decimals=0)),
        ("Taux de pénétration", _fmt(profil.get("taux_penetration_pct"), "%")),
        ("Densité (DT/hab.)", _fmt(profil.get("densite_assurance_dt"))),
        ("Primes totales (MDT)", _fmt(profil.get("total_primes_emises_mdt"))),
        ("Primes Vie (MDT)", _fmt(profil.get("primes_vie_mdt"))),
        ("Primes Non-Vie (MDT)", _fmt(profil.get("primes_non_vie_mdt"))),
        ("Nombre d'assureurs", _fmt(profil.get("nb_assureurs"), decimals=0)),
    ]))

    flow.append(Paragraph("Ratios techniques (%)", STYLE_SECTION))
    header = ["Segment", "Ratio S/P", "Ratio de frais", "Ratio combiné"]
    rows = [header]
    for label, key in [("Vie", "vie"), ("Non-Vie", "non_vie"), ("Total", "total")]:
        seg = ratios.get(key, {})
        rows.append([label, _fmt(seg.get("ratio_sp_pct")), _fmt(seg.get("ratio_frais_pct")),
                     _fmt(seg.get("ratio_combine_pct"))])
    flow.append(_table(rows, col_widths=[3.5*cm, 3.5*cm, 3.5*cm, 3.5*cm]))

    classement = agences.get("classement", [])
    if classement:
        flow.append(Paragraph(f"Réseau d'agences — classement (année {agences.get('annee_cga', annee)})",
                               STYLE_SECTION))
        header = ["Rang", "Compagnie", "Agences", "Part réseau (%)"]
        rows = [header] + [
            [c["rang"], c["code"], _fmt(c.get("n"), decimals=0), _fmt(c.get("pct"))]
            for c in classement[:15]
        ]
        flow.append(_table(rows, col_widths=[1.5*cm, 4*cm, 3*cm, 3*cm]))

    doc.build_with_header(flow)
    buffer.seek(0)
    return buffer
