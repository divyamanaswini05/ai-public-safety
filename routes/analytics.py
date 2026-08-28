"""Analytics routes — charts and statistics page."""

import json

from flask import Blueprint, render_template, jsonify
from flask_login import login_required

from services import analytics_service

analytics_bp = Blueprint("analytics", __name__, url_prefix="/analytics")


@analytics_bp.get("/")
@login_required
def index():
    return render_template("analytics/index.html")


@analytics_bp.get("/data.json")
@login_required
def data():
    return jsonify({
        "overview": analytics_service.overview(),
        "incidents_by_type": analytics_service.incidents_by_type(),
        "incidents_by_severity": analytics_service.incidents_by_severity(),
        "incidents_by_status": analytics_service.incidents_by_status(),
        "alerts_by_priority": analytics_service.alerts_by_priority(),
        "alerts_by_status": analytics_service.alerts_by_status(),
        "incidents_last_7_days": analytics_service.incidents_last_7_days(),
    })
