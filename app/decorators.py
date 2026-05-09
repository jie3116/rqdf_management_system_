from functools import wraps
from flask import abort
from flask_login import current_user
from app.models import UserRole

def role_required(*roles):
    """
    Decorator untuk membatasi akses berdasarkan Role.
    Penggunaan: @role_required(UserRole.ADMIN, UserRole.GURU)
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return abort(401)
            if not current_user.has_role(*roles):
                return abort(403) # Forbidden
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

def admin_required(fn):
    return role_required(UserRole.SUPER_ADMIN, UserRole.ADMIN)(fn)
