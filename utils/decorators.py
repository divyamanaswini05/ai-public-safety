"""Access-control decorators for route protection."""

from functools import wraps

from flask import abort, flash, redirect, request, url_for
from flask_login import current_user


def role_required(*roles: str):
    """Require an authenticated user holding at least one of the roles.

    Unauthenticated visitors are sent to the login page; authenticated
    users without the required role receive an HTTP 403 response.
    """

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please sign in to access this page.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            if not current_user.has_role(*roles):
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
