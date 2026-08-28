"""Report generation — PDF incident summaries and Excel data exports."""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
)
from openpyxl import Workbook

from extensions import db
from models import Incident, Alert, Camera
from models.enums import IncidentStatus, IncidentType, SeverityLevel
from models.base import utcnow


def _incident_query(
    status: str | None = None,
    incident_type: str | None = None,
):
    query = Incident.query
    if status:
        try:
            query = query.filter(Incident.status == IncidentStatus(status))
        except ValueError:
            pass
    if incident_type:
        try:
            query = query.filter(Incident.incident_type == IncidentType(incident_type))
        except ValueError:
            pass
    return query.order_by(Incident.detected_at.desc()).all()


def incident_pdf(
    status: str | None = None,
    incident_type: str | None = None,
) -> bytes:
    """Generate a PDF report of incidents."""
    incidents = _incident_query(status, incident_type)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("SentinelAI — Incident Report", styles["Title"]))
    elements.append(Paragraph(
        f"Generated: {utcnow().strftime('%d %b %Y %H:%M')}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 12))

    data = [["ID", "Title", "Type", "Severity", "Status", "Detected"]]
    for inc in incidents:
        data.append([
            str(inc.id),
            inc.title[:40],
            inc.incident_type.value,
            inc.severity.value,
            inc.status.value,
            inc.detected_at.strftime("%d %b %y %H:%M"),
        ])

    if len(data) > 1:
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#334155")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#0f172a"), colors.HexColor("#1e293b")]),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No incidents match the selected filters.", styles["Normal"]))

    doc.build(elements)
    return buf.getvalue()


def incident_excel(
    status: str | None = None,
    incident_type: str | None = None,
) -> bytes:
    """Generate an Excel workbook of incidents."""
    incidents = _incident_query(status, incident_type)
    wb = Workbook()
    ws = wb.active
    ws.title = "Incidents"
    ws.append(["ID", "Title", "Type", "Severity", "Status", "Camera", "Confidence", "Detected", "Resolved"])
    for inc in incidents:
        ws.append([
            inc.id,
            inc.title,
            inc.incident_type.value,
            inc.severity.value,
            inc.status.value,
            inc.camera.name if inc.camera else "",
            inc.confidence,
            inc.detected_at.isoformat() if inc.detected_at else "",
            inc.resolved_at.isoformat() if inc.resolved_at else "",
        ])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def camera_report_pdf() -> bytes:
    """Generate a PDF listing all cameras with their status."""
    cameras = Camera.query.order_by(Camera.name).all()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("SentinelAI — Camera Report", styles["Title"]))
    elements.append(Paragraph(
        f"Generated: {utcnow().strftime('%d %b %Y %H:%M')}",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 12))

    data = [["Name", "Location", "Source", "Status", "Health"]]
    for cam in cameras:
        data.append([
            cam.name,
            cam.location or "—",
            cam.source_type.value.upper(),
            cam.status.value,
            f"{cam.health_score}%" if cam.health_score is not None else "—",
        ])

    if len(data) > 1:
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#334155")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#0f172a"), colors.HexColor("#1e293b")]),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No cameras registered.", styles["Normal"]))

    doc.build(elements)
    return buf.getvalue()
