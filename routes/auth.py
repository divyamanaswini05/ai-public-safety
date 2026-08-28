"""Authentication routes — register, login, logout, verify and reset."""

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user

from forms import ForgotPasswordForm, LoginForm, RegisterForm, ResetPasswordForm
from models import User
from services import auth_service
from services.audit_service import audit

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _safe_next_target(target: str | None) -> str | None:
    """Allow only same-origin relative redirects (open-redirect guard)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Sign in with email or username."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user, error = auth_service.authenticate(form.identity.data, form.password.data)
        if error is not None:
            flash(error, "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember.data)
        session.permanent = form.remember.data
        if not user.is_verified:
            flash(
                "Please verify your email address to enable full access.",
                "warning",
            )
        target = _safe_next_target(request.form.get("next"))
        return redirect(target or url_for("main.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Create a new account and sign the user in."""
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        user = auth_service.register_user(
            username=form.username.data,
            email=form.email.data,
            password=form.password.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
        )
        login_user(user)
        flash(
            "Account created. Check your inbox to verify your email address.",
            "success",
        )
        return redirect(url_for("main.index"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """End the signed-in session (CSRF-protected POST only)."""
    # Audit before logout_user() so the entry still resolves the identity.
    audit(
        action="auth.logout",
        module="auth",
        message=f"User signed out: {current_user.email}",
    )
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.index"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Request a password reset link."""
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if user is not None:
            auth_service.send_password_reset(user)
        # Generic response prevents user-account enumeration.
        flash("If that email exists, a password reset link has been sent.", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Set a new password using a signed reset token."""
    user = auth_service.validate_reset_token(token)
    if user is None:
        flash("This reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        auth_service.reset_password(user, form.password.data)
        flash("Your password has been reset. Please sign in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form, token=token)


@auth_bp.route("/verify-email/<token>")
def verify_email(token: str):
    """Confirm a user's email address from a verification link."""
    user = auth_service.verify_email_token(token)
    if user is None:
        flash("This verification link is invalid or has expired.", "danger")
        return render_template("auth/verify_email.html", success=False)

    if user.is_verified:
        flash("Your email address is already verified.", "info")
        return render_template("auth/verify_email.html", success=True)

    auth_service.confirm_user_email(user)
    flash("Email verified successfully.", "success")
    return render_template("auth/verify_email.html", success=True)


@auth_bp.route("/resend-verification")
@login_required
def resend_verification():
    """Re-send the verification email to the signed-in user."""
    if current_user.is_verified:
        flash("Your email address is already verified.", "info")
    else:
        auth_service.send_verification_email(current_user)
        flash("A new verification email has been sent.", "info")
    return redirect(url_for("main.index"))
