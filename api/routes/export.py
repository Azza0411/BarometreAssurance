"""Routes /api/export/* — génération de rapports PDF téléchargeables."""

from flask import Blueprint, send_file
from api.utils.formatters import required_year_arg
from api.services.pdf_export import (
    build_fiche_compagnie_pdf, build_analyse_comparative_pdf, build_apercu_marche_pdf,
)

bp = Blueprint("export", __name__)


@bp.route("/api/export/fiche-compagnie")
def export_fiche_compagnie():
    from flask import request
    code = request.args.get("code", "")
    annee = required_year_arg()
    buffer = build_fiche_compagnie_pdf(code, annee)
    return send_file(
        buffer, mimetype="application/pdf", as_attachment=True,
        download_name=f"Fiche_{code}_{annee}.pdf",
    )


@bp.route("/api/export/analyse-comparative")
def export_analyse_comparative():
    annee = required_year_arg()
    buffer = build_analyse_comparative_pdf(annee)
    return send_file(
        buffer, mimetype="application/pdf", as_attachment=True,
        download_name=f"Analyse_Comparative_{annee}.pdf",
    )


@bp.route("/api/export/apercu-marche")
def export_apercu_marche():
    annee = required_year_arg()
    buffer = build_apercu_marche_pdf(annee)
    return send_file(
        buffer, mimetype="application/pdf", as_attachment=True,
        download_name=f"Apercu_Marche_{annee}.pdf",
    )
