from flask import Flask
from config import Config
from app.extensions import db, migrate, login_manager


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Init Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Import Models
    from app import models

    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    # --- REGISTRASI BLUEPRINT ---
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.academic import academic_bp
    from app.routes.admin import admin_bp
    from app.routes.staff import staff_bp


    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(academic_bp, url_prefix='/academic')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staff_bp, url_prefix='/staff')

    return app