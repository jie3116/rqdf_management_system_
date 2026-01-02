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
            if current_user.role not in roles:
                return abort(403) # Forbidden
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

def admin_required(fn):
    return role_required(UserRole.ADMIN)(fn)