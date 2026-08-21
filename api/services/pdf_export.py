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
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, HRFlowable,
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
    "assets", "EyForDarkBg.png",
)
# Copie locale (api/assets/) plutôt qu'un lien vers frontend/public/logos/ :
# Dockerfile.api ne copie pas le dossier frontend/ dans l'image, le logo
# serait introuvable (silencieusement omis, cf. le if os.path.exists ci-dessous).
#
# "EyForDarkBg.png" — PAS "EyDark.png" (utilisé jusqu'au 2026-08-19) : ce
# dernier s'est avéré être un WebP renommé .png, entièrement OPAQUE (aucun
# canal alpha — vérifié via PIL, `mode == "RGB"`, alpha uniforme à 255 sur
# toute l'image) avec un fond blanc plein ET des lettres "EY" elles-mêmes en
# gris quasi blanc (luminance > 230 partout hors du triangle jaune) —
# probablement un export raté (silhouette blanche destinée à un fond sombre,
# mais enregistrée sans transparence). `mask="auto"` de ReportLab masquait
# ce défaut par chance en PDF (d'où le "ça a l'air propre" des captures
# précédentes), mais openpyxl (export Excel) colle les pixels tels quels :
# un bloc blanc plein apparaissait sur le bandeau sombre — signalé par
# l'utilisateur comme "logo pas clair". Ce fichier est reconstruit à partir
# de "EYLight.png" (texte "EY"/tagline gris foncé ~(21,28,35), triangle
# jaune (255,230,0), VRAIE transparence alpha) en inversant le texte foncé
# en blanc pur (garde le jaune inchangé) — silhouette blanche+jaune correcte
# avec une vraie transparence, exploitable telle quelle en PDF ET en Excel.
_LOGO_ASPECT = 0.864  # largeur/hauteur du PNG source (768x889)

# Logos compagnies — copie locale de frontend/src/utils/logos.js (même
# raison que EyDark.png : api/assets/ est le seul dossier d'images accessible
# depuis l'image Docker api, voir commentaire ci-dessus). Utilisés pour
# afficher le logo de la compagnie à côté du logo EY dans l'en-tête de la
# fiche compagnie exportée — ajouté le 2026-08-19 sur demande explicite
# ("améliorer l'allure générale" des exports).
_LOGOS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets", "logos",
)
_COMPANY_LOGO_MAP = {
    "AL_AMANAH_TAKAFUL": "El Amana Takaful.png",
    "AMI":               "AMI.png",
    "ASTREE":            "astree.png",
    "ATTIJARI":          "Attijari.png",
    "AT_TAKAFULIA":      "At-Takafulia.png",
    "BH":                "BH.png",
    "BIAT":              "BIAT.png",
    "BNA":                "BNA.png",
    "CARTE":             "Carte.png",
    "CARTE_VIE":         "Carte-Vie.png",
    "COMAR":             "COMAR.png",
    "COTUNACE":          "COTUNACE.png",
    "CTAMA":             "CTAMA.png",
    "GAT":               "GAT.png",
    "GAT_VIE":           "GAT-vie.png",
    "HAYETT":            "hayett.png",
    "LLOYD_TUNISIEN":    "LLOYD.png",
    "LLOYD_VIE":         "LLOYD-Vie.png",
    "MAGHREBIA":         "Maghrebia.png",
    "MAGHREBIA_VIE":     "Maghrebia-Vie.png",
    "STAR":              "STAR.png",
    "TUNIS_RE":          "TunisRe.png",
    "UIB":               "UIB.png",
    "ZITOUNA_TAKAFUL":   "Zitouna-Takaful.png",
}


def _company_logo_path(code):
    filename = _COMPANY_LOGO_MAP.get((code or "").upper())
    if not filename:
        return None
    path = os.path.join(_LOGOS_DIR, filename)
    return path if os.path.exists(path) else None

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


def _header_footer(title, subtitle, company_logo_path=None):
    def _draw(cnv, doc):
        cnv.saveState()
        page_w, page_h = A4
        # Bandeau d'en-tête
        cnv.setFillColor(DARK)
        cnv.rect(0, page_h - 2.6 * cm, page_w, 2.6 * cm, fill=1, stroke=0)
        if os.path.exists(_LOGO_PATH):
            try:
                logo_h = 1.7 * cm  # agrandi le 2026-08-19 (retour utilisateur)
                logo_w = logo_h * _LOGO_ASPECT
                cnv.drawImage(_LOGO_PATH, 1.5 * cm, page_h - 2.25 * cm,
                               width=logo_w, height=logo_h, mask="auto")
            except Exception:
                pass
        # Logo compagnie (fiche compagnie uniquement), coin opposé du logo
        # EY. Historique du 2026-08-19, 2 essais avant celui-ci :
        #   1) médaillon blanc rond (Ø1,7cm) — carré ~1,3cm imposé aux
        #      logos, illisible pour les formats très en largeur (BH,
        #      BIAT : texte écrasé à l'illisibilité).
        #   2) posé à même le bandeau dark, sans fond (retour utilisateur
        #      explicite "mettre un fond foncé") — corrige bien la taille
        #      (boîte large 4,2cm au lieu d'un carré) mais CASSE la
        #      lisibilité des logos à texte sombre conçus pour un fond
        #      clair (BIAT : "ASSURANCES BIAT" en gris foncé devient quasi
        #      invisible sur le bandeau navy) — la plupart des logos
        #      compagnies ici sont dans ce cas, pas dans celui de STAR/BH
        #      qui s'en sortent car assez colorés/contrastés.
        # Solution retenue : garder le fond CLAIR (fonctionne pour la
        # quasi-totalité des logos, conçus pour un support clair comme
        # n'importe quel document imprimé) mais sur une carte LARGE
        # (4,2cm, pas un carré/rond) plutôt qu'un médaillon — corrige le
        # vrai problème (écrasement des logos en largeur), pas la couleur.
        if company_logo_path:
            try:
                badge_w, badge_h = 4.4 * cm, 1.55 * cm
                badge_x = page_w - 1.3 * cm - badge_w
                badge_y = page_h - 2.05 * cm
                cnv.setFillColor(WHITE)
                cnv.roundRect(badge_x, badge_y, badge_w, badge_h, 6, fill=1, stroke=0)
                logo_w = badge_w - 0.5 * cm
                logo_h = badge_h - 0.4 * cm
                cnv.drawImage(company_logo_path,
                               badge_x + (badge_w - logo_w) / 2, badge_y + (badge_h - logo_h) / 2,
                               width=logo_w, height=logo_h, mask="auto",
                               preserveAspectRatio=True, anchor="c")
            except Exception:
                pass
        cnv.setFillColor(WHITE)
        cnv.setFont("Helvetica-Bold", 15)
        cnv.drawString(4.2 * cm, page_h - 1.35 * cm, title)
        cnv.setFillColor(YELLOW)
        cnv.setFont("Helvetica", 10)
        cnv.drawString(4.2 * cm, page_h - 1.9 * cm, subtitle)
        # Pied de page
        cnv.setStrokeColor(colors.HexColor("#44444E"))
        cnv.setLineWidth(0.5)
        cnv.line(1.5 * cm, 1.55 * cm, page_w - 1.5 * cm, 1.55 * cm)
        cnv.setFillColor(GREY)
        cnv.setFont("Helvetica", 7.5)
        cnv.drawString(1.5 * cm, 1.2 * cm,
                        f"FS Market Intelligence · Confidentiel EY · Généré le "
                        f"{datetime.now().strftime('%d/%m/%Y à %H:%M')}")
        cnv.drawRightString(page_w - 1.5 * cm, 1.2 * cm, f"Page {doc.page}")
        cnv.restoreState()
    return _draw


def _doc(buffer, title, subtitle, company_logo_path=None):
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=3.2 * cm, bottomMargin=2 * cm,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    draw = _header_footer(title, subtitle, company_logo_path)
    doc.build_with_header = lambda flowables: doc.build(
        flowables, onFirstPage=draw, onLaterPages=draw
    )
    return doc


def _section_header(text):
    """Titre de section + filet jaune — remplace un simple Paragraph pour
    donner plus de repère visuel entre sections (ajouté le 2026-08-19,
    passe d'amélioration générale de l'allure des exports)."""
    return [
        Paragraph(text, STYLE_SECTION),
        HRFlowable(width="100%", thickness=1.4, color=YELLOW, spaceBefore=0, spaceAfter=8,
                   lineCap="round"),
    ]


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
    # Intercale label/valeur verticalement dans une même cellule via Table
    # imbriquée, avec un filet jaune en haut de chaque carte — même accent
    # que les cartes KPI de l'application (voir .kpi-card dans index.css) —
    # pour que l'export "ressemble" visuellement à l'écran d'origine.
    cells = []
    for row in rows:
        card_cells = []
        for c in row:
            card = Table([[c[0]], [c[1]]], colWidths=[4.0 * cm])
            card.setStyle(TableStyle([
                ("LINEABOVE", (0, 0), (-1, 0), 2.2, YELLOW),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
            ]))
            card_cells.append(card)
        cells.append(card_cells)
    t = Table(cells, colWidths=[4.3 * cm] * 4)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("BOX", (0, 0), (-1, -1), 0, WHITE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
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
               f"Exercice {profil.get('annee') or annee} · FS Market Intelligence",
               company_logo_path=_company_logo_path(code))

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

    flow.extend(_section_header("Bilan (MDT)"))
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
        flow.extend(_section_header("Évolution historique"))
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

    flow.extend(_section_header("Ratios techniques (%)"))
    header = ["Segment", "Ratio S/P", "Ratio de frais", "Ratio combiné"]
    rows = [header]
    for label, key in [("Vie", "vie"), ("Non-Vie", "non_vie"), ("Total", "total")]:
        seg = ratios.get(key, {})
        rows.append([label, _fmt(seg.get("ratio_sp_pct")), _fmt(seg.get("ratio_frais_pct")),
                     _fmt(seg.get("ratio_combine_pct"))])
    flow.append(_table(rows, col_widths=[3.5*cm, 3.5*cm, 3.5*cm, 3.5*cm]))

    classement = agences.get("classement", [])
    if classement:
        flow.extend(_section_header(
            f"Réseau d'agences — classement (année {agences.get('annee_cga', annee)})"
        ))
        header = ["Rang", "Compagnie", "Agences", "Part réseau (%)"]
        rows = [header] + [
            [c["rang"], c["code"], _fmt(c.get("n"), decimals=0), _fmt(c.get("pct"))]
            for c in classement[:15]
        ]
        flow.append(_table(rows, col_widths=[1.5*cm, 4*cm, 3*cm, 3*cm]))

    doc.build_with_header(flow)
    buffer.seek(0)
    return buffer
