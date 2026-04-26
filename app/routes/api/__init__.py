from flask import Blueprint

from app.extensions import csrf

from .auth import register_auth_routes
from .majlis import register_majlis_routes
from .parent import register_parent_routes
from .teacher import register_teacher_routes


api_bp = Blueprint("api", __name__)
csrf.exempt(api_bp)

register_auth_routes(api_bp)
register_parent_routes(api_bp)
register_teacher_routes(api_bp)
register_majlis_routes(api_bp)
