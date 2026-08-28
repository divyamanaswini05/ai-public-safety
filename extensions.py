"""Central registry of third-party Flask extensions.

Extensions are instantiated exactly once in this module and are bound to
the application inside ``app.create_app``. Keeping them here allows the
application factory to be called multiple times (tests, scripts) without
double-binding any extension.
"""

from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

# Database ORM
db = SQLAlchemy()

# Schema migrations (alembic)
migrate = Migrate()

# Password hashing
bcrypt = Bcrypt()

# CSRF token protection for every form
csrf = CSRFProtect()

# Email dispatch (forgot password, alert notifications)
mail = Mail()

# Realtime channel for live surveillance and alert streaming
socketio = SocketIO()

# Session / user authentication
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please sign in to access this page."
login_manager.login_message_category = "warning"
