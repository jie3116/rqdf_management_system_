from flask import Flask
from config import Config
from app.extensions import db, migrate, login_manager, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 1. Init Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # 2. Context Processor (Inject datetime agar tidak error di base.html)
    @app.context_processor
    def inject_helpers():
        from datetime import datetime
        import locale
        try:
            # Opsional: Set bahasa tanggal ke Indonesia
            locale.setlocale(locale.LC_TIME, 'id_ID.utf8')
        except:
            pass
        return {'datetime': datetime}

    # 3. Import Models (Penting agar db.create_all mendeteksi tabel)
    from app import models

    # 4. User Loader (Wajib untuk Flask-Login)
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    # 5. Registrasi Blueprint
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.staff import staff_bp
    from app.routes.student import student_bp
    from app.routes.parent import parent_bp
    from app.routes.teacher import teacher_bp


    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(parent_bp, url_prefix='/parent')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')

    return app