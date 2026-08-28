"""Admin routes — user management, settings and audit log viewer."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from extensions import db
from models import AuditLog, Role, Setting, User
from models.enums import RoleSlug
from services.audit_service import audit
from utils.decorators import role_required

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _require_admin():
    """Ensures the view is admin-only."""
    return role_required(RoleSlug.ADMIN.value)


@admin_bp.get("/")
@role_required(RoleSlug.ADMIN.value)
def index():
    return render_template(
        "admin/index.html",
        user_count=User.query.count(),
        setting_count=Setting.query.count(),
        log_count=AuditLog.query.count(),
        recent_logs=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all(),
    )


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
@admin_bp.get("/users/")
@role_required(RoleSlug.ADMIN.value)
def users():
    return render_template(
        "admin/users.html",
        users=User.query.order_by(User.created_at.desc()).all(),
        roles=Role.query.order_by(Role.name).all(),
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
@role_required(RoleSlug.ADMIN.value)
def user_new():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role_id = request.form.get("role_id", type=int)
        if not username or not email or not password:
            flash("Username, email and password are required.", "danger")
            return redirect(url_for("admin.user_new"))
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash("Username or email already exists.", "danger")
            return redirect(url_for("admin.user_new"))
        user = User(
            username=username,
            email=email,
            role_id=role_id,
            is_active=True,
            is_verified=True,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        audit(action="admin.user.create", module="admin", message=f"User '{username}' created")
        flash(f"User '{username}' created.", "success")
        return redirect(url_for("admin.users"))
    return render_template(
        "admin/user_form.html",
        roles=Role.query.order_by(Role.name).all(),
        user=None,
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@role_required(RoleSlug.ADMIN.value)
def user_edit(user_id: int):
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        user.first_name = request.form.get("first_name", "").strip() or None
        user.last_name = request.form.get("last_name", "").strip() or None
        user.role_id = request.form.get("role_id", type=int)
        user.is_active = request.form.get("is_active") == "on"
        user.is_verified = request.form.get("is_verified") == "on"
        new_password = request.form.get("password", "").strip()
        if new_password:
            user.set_password(new_password)
        db.session.commit()
        audit(action="admin.user.update", module="admin", message=f"User '{user.username}' updated")
        flash(f"User '{user.username}' updated.", "success")
        return redirect(url_for("admin.users"))
    return render_template(
        "admin/user_form.html",
        roles=Role.query.order_by(Role.name).all(),
        user=user,
    )


@admin_bp.post("/users/<int:user_id>/delete")
@role_required(RoleSlug.ADMIN.value)
def user_delete(user_id: int):
    user = db.get_or_404(User, user_id)
    if user.has_role(RoleSlug.ADMIN.value):
        flash("Cannot delete admin accounts.", "danger")
        return redirect(url_for("admin.users"))
    username = user.username
    db.session.delete(user)
    db.session.commit()
    audit(action="admin.user.delete", module="admin", message=f"User '{username}' deleted")
    flash(f"User '{username}' deleted.", "info")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
@admin_bp.get("/settings/")
@role_required(RoleSlug.ADMIN.value)
def settings():
    return render_template(
        "admin/settings.html",
        settings=Setting.query.order_by(Setting.group, Setting.key).all(),
    )


@admin_bp.route("/settings/<int:setting_id>/edit", methods=["GET", "POST"])
@role_required(RoleSlug.ADMIN.value)
def setting_edit(setting_id: int):
    setting = db.get_or_404(Setting, setting_id)
    if request.method == "POST":
        setting.value = request.form.get("value", "")
        setting.description = request.form.get("description", "").strip() or None
        db.session.commit()
        audit(action="admin.setting.update", module="admin", message=f"Setting '{setting.key}' updated")
        flash(f"Setting '{setting.key}' updated.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/setting_form.html", setting=setting)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
@admin_bp.get("/audit/")
@role_required(RoleSlug.ADMIN.value)
def audit_log():
    query = AuditLog.query
    module_filter = request.args.get("module") or None
    if module_filter:
        query = query.filter(AuditLog.module == module_filter)
    logs = query.order_by(AuditLog.created_at.desc()).limit(200).all()
    modules = (
        db.session.query(AuditLog.module)
        .distinct()
        .filter(AuditLog.module.isnot(None))
        .order_by(AuditLog.module)
        .all()
    )
    return render_template(
        "admin/audit.html",
        logs=logs,
        modules=[m for m, in modules],
        filters={"module": module_filter},
    )
