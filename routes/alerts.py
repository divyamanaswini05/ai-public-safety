"""Alert routes — list, review and acknowledge alerts."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from extensions import db
from models import Alert, Incident
from models.enums import AlertPriority, AlertStatus, AlertType, RoleSlug
from services import alert_service
from utils.decorators import role_required

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alerts")

MANAGE_ROLES = (RoleSlug.ADMIN.value, RoleSlug.OPERATOR.value)


@alerts_bp.get("/")
@login_required
def index():
    """List alerts with optional status/priority/type/incident filters."""
    filters = {
        "status": request.args.get("status") or None,
        "priority": request.args.get("priority") or None,
        "alert_type": request.args.get("type") or None,
        "incident_id": request.args.get("incident_id", type=int),
        "search": request.args.get("q") or None,
    }
    return render_template(
        "alerts/index.html",
        alerts=alert_service.list_alerts(**filters),
        filters=filters,
        counts=alert_service.get_alert_counts(),
        statuses=AlertStatus,
        priorities=AlertPriority,
        types=AlertType,
    )


@alerts_bp.get("/<int:alert_id>")
@login_required
def detail(alert_id: int):
    """Full view of a single alert."""
    alert = db.get_or_404(Alert, alert_id)
    return render_template("alerts/detail.html", alert=alert)


@alerts_bp.post("/<int:alert_id>/send")
@role_required(*MANAGE_ROLES)
def send(alert_id: int):
    """Mark a pending alert as sent."""
    alert = db.get_or_404(Alert, alert_id)
    if alert.status != AlertStatus.PENDING:
        flash("Only pending alerts can be marked as sent.", "warning")
        return redirect(url_for("alerts.detail", alert_id=alert_id))
    alert_service.mark_sent(alert)
    flash(f"Alert '{alert.title}' marked sent.", "success")
    return redirect(url_for("alerts.detail", alert_id=alert_id))


@alerts_bp.post("/<int:alert_id>/acknowledge")
@role_required(*MANAGE_ROLES)
def acknowledge(alert_id: int):
    """Acknowledge a sent alert."""
    alert = db.get_or_404(Alert, alert_id)
    if alert.status != AlertStatus.SENT:
        flash("Only sent alerts can be acknowledged.", "warning")
        return redirect(url_for("alerts.detail", alert_id=alert_id))
    alert_service.acknowledge(alert, current_user.id)
    flash(f"Alert '{alert.title}' acknowledged.", "success")
    return redirect(url_for("alerts.detail", alert_id=alert_id))


@alerts_bp.post("/<int:alert_id>/expire")
@role_required(RoleSlug.ADMIN.value)
def expire(alert_id: int):
    """Expire a pending or sent alert (admin only)."""
    alert = db.get_or_404(Alert, alert_id)
    if alert.status in (AlertStatus.ACKNOWLEDGED, AlertStatus.EXPIRED):
        flash("This alert is already closed.", "warning")
        return redirect(url_for("alerts.detail", alert_id=alert_id))
    alert_service.expire(alert)
    flash(f"Alert '{alert.title}' expired.", "info")
    return redirect(url_for("alerts.detail", alert_id=alert_id))
