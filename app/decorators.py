from functools import wraps
from flask import abort, flash, redirect, request, url_for
from flask_login import current_user
from app.models import UserRole
from app.utils.roles import get_active_role

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
            active_role = get_active_role(current_user)
            if active_role and active_role not in roles and len(current_user.all_roles()) > 1:
                flash('Akses ditolak: role aktif Anda tidak sesuai halaman tujuan.', 'warning')
                return redirect(url_for('auth.select_role', next=request.url))
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper

def admin_required(fn):
    return role_required(UserRole.ADMIN)(fn)
