"""Dashboard routes — command-centre overview of the whole system."""

from flask import Blueprint, render_template
from flask_login import login_required

from services import dashboard_service

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.get("/")
@login_required
def index():
    """Render the analytics dashboard for signed-in users."""
    chart_data = {
        "incident_trend": dashboard_service.get_incident_trend(),
        "alert_trend": dashboard_service.get_alert_trend(),
        "incidents_by_type": dashboard_service.get_incidents_by_type(),
        "incidents_by_severity": dashboard_service.get_incidents_by_severity(),
        "camera_status_split": dashboard_service.get_camera_status_split(),
    }
    return render_template(
        "dashboard/index.html",
        kpis=dashboard_service.get_kpis(),
        chart_data=chart_data,
        recent_incidents=dashboard_service.get_recent_incidents(6),
        recent_alerts=dashboard_service.get_recent_alerts(6),
        recent_activity=dashboard_service.get_recent_activity(8),
    )
