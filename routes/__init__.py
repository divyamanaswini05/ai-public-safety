"""Blueprint registration.

Every feature module exposes a :class:`~flask.Blueprint`. They are
collected in this package and attached to the application in a single
place inside the application factory.
"""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    """Attach every application blueprint to the app."""
    from routes.alerts import alerts_bp
    from routes.admin import admin_bp
    from routes.ai import ai_bp
    from routes.analytics import analytics_bp
    from routes.auth import auth_bp
    from routes.cameras import cameras_bp
    from routes.crowd import crowd_bp
    from routes.dashboard import dashboard_bp
    from routes.evidence import evidence_bp
    from routes.face import face_bp
    from routes.fire_smoke import fire_smoke_bp
    from routes.incidents import incidents_bp
    from routes.intrusion import intrusion_bp
    from routes.main import main_bp
    from routes.reports import reports_bp
    from routes.surveillance import surveillance_bp
    from routes.weapon import weapon_bp

    blueprints = (
        main_bp,
        auth_bp,
        dashboard_bp,
        cameras_bp,
        surveillance_bp,
        ai_bp,
        incidents_bp,
        alerts_bp,
        fire_smoke_bp,
        weapon_bp,
        crowd_bp,
        intrusion_bp,
        face_bp,
        evidence_bp,
        analytics_bp,
        reports_bp,
        admin_bp,
    )

    for blueprint in blueprints:
        app.register_blueprint(blueprint)
