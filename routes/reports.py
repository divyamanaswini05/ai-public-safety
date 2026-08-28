"""Report routes — generate and download PDF and Excel reports."""

from flask import Blueprint, render_template, request, send_file
from flask_login import login_required
import io

from services import report_service

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.get("/")
@login_required
def index():
    return render_template("reports/index.html")


@reports_bp.get("/incidents.pdf")
@login_required
def incidents_pdf():
    status = request.args.get("status") or None
    incident_type = request.args.get("type") or None
    pdf = report_service.incident_pdf(status=status, incident_type=incident_type)
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="incidents_report.pdf",
    )


@reports_bp.get("/incidents.xlsx")
@login_required
def incidents_excel():
    status = request.args.get("status") or None
    incident_type = request.args.get("type") or None
    xlsx = report_service.incident_excel(status=status, incident_type=incident_type)
    return send_file(
        io.BytesIO(xlsx),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="incidents_report.xlsx",
    )


@reports_bp.get("/cameras.pdf")
@login_required
def cameras_pdf():
    pdf = report_service.camera_report_pdf()
    return send_file(
        io.BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="cameras_report.pdf",
    )
