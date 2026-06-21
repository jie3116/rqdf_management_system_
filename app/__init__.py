from flask import Flask
from sqlalchemy import event
from sqlalchemy.orm import with_loader_criteria
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
        from flask_login import current_user
        from app.models import Teacher, FinanceJournal, FinanceJournalStatus, FinancePeriod
        from app.routes.teacher import build_teacher_sidebar_groups
        from app.utils.roles import get_active_role, role_label
        from app.utils.tenant import resolve_tenant_id
        from app.utils.tenant_branding import build_tenant_brand
        from app.utils.tenant_modules import (
            PACKAGE_FULL,
            PACKAGE_RUMAH_QURAN,
            PACKAGE_SEKOLAH,
            get_tenant_package,
        )
        from app.utils.timezone import local_now, local_today
        try:
            # Opsional: Set bahasa tanggal ke Indonesia
            locale.setlocale(locale.LC_TIME, 'id_ID.utf8')
        except:
            pass
        active_role = get_active_role(current_user) if current_user.is_authenticated else None
        teacher_sidebar_groups = []
        user_role_labels = []
        tenant_package = PACKAGE_FULL
        finance_draft_journal_count = 0
        finance_has_open_period_today = True
        finance_current_period_status = None
        if current_user.is_authenticated:
            tenant_id = resolve_tenant_id(current_user, fallback_default=False)
            tenant_package = get_tenant_package(tenant_id)
            user_roles = sorted(list(current_user.all_roles()), key=lambda role: role.value)
            user_role_labels = [role_label(role) for role in user_roles]
            if current_user.has_role('tata_usaha') and tenant_id is not None:
                finance_draft_journal_count = FinanceJournal.query.filter_by(
                    tenant_id=tenant_id,
                    status=FinanceJournalStatus.DRAFT,
                ).count()
                period_today = FinancePeriod.query.filter(
                    FinancePeriod.tenant_id == tenant_id,
                    FinancePeriod.start_date <= local_today(),
                    FinancePeriod.end_date >= local_today(),
                ).first()
                finance_current_period_status = period_today.status.value if period_today else None
                finance_has_open_period_today = bool(
                    period_today and period_today.status.value == "OPEN"
                )
        if current_user.is_authenticated and current_user.has_role('teacher'):
            teacher = Teacher.query.filter_by(user_id=current_user.id, is_deleted=False).first()
            teacher_sidebar_groups = build_teacher_sidebar_groups(teacher)
        tenant_brand = build_tenant_brand()
        return {
            'datetime': datetime,
            'local_now': local_now,
            'local_today': local_today,
            'tenant_brand': tenant_brand,
            'tenant_brand_name': tenant_brand['name'],
            'tenant_logo_url': tenant_brand['logo_url'],
            'active_role': active_role,
            'active_role_value': active_role.value if active_role else None,
            'active_role_label': role_label(active_role) if active_role else '-',
            'user_role_labels': user_role_labels,
            'tenant_package': tenant_package,
            'module_school_enabled': tenant_package in (PACKAGE_FULL, PACKAGE_SEKOLAH),
            'module_rumah_quran_enabled': tenant_package in (PACKAGE_FULL, PACKAGE_RUMAH_QURAN),
            'module_boarding_enabled': tenant_package == PACKAGE_FULL,
            'teacher_sidebar_groups': teacher_sidebar_groups,
            'finance_draft_journal_count': finance_draft_journal_count,
            'finance_has_open_period_today': finance_has_open_period_today,
            'finance_current_period_status': finance_current_period_status,
        }

    # 3. Import Models (Penting agar db.create_all mendeteksi tabel)
    from app import models

    # 4. User Loader (Wajib untuk Flask-Login)
    @login_manager.user_loader
    def load_user(user_id):
        return models.User.query.get(int(user_id))

    # 4b. Global Soft Delete Filter (hindari data is_deleted muncul tanpa sengaja)

    @event.listens_for(db.session, "do_orm_execute")
    def _add_soft_delete_filter(execute_state):
        if not execute_state.is_select:
            return
        if execute_state.execution_options.get("include_deleted", False):
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                models.BaseModel,
                lambda cls: cls.is_deleted.is_(False),
                include_aliases=True,
            )
        )

    @app.before_request
    def _enforce_tenant_module_access():
        from flask import request, flash, redirect, url_for, session
        from flask_login import current_user, logout_user
        from app.utils.tenant import is_user_tenant_active, resolve_tenant_id
        from app.utils.tenant_modules import (
            endpoint_allowed_for_package,
            get_tenant_package,
            role_allowed_for_package,
        )

        if not current_user.is_authenticated:
            return None

        if current_user.has_role("super_admin"):
            return None

        if not is_user_tenant_active(current_user):
            flash('Tenant akun ini tidak aktif. Silakan hubungi admin.', 'danger')
            session.pop('active_role', None)
            logout_user()
            return redirect(url_for('auth.login'))

        tenant_id = resolve_tenant_id(current_user, fallback_default=False)
        package = get_tenant_package(tenant_id)

        user_roles = list(current_user.all_roles())
        has_allowed_role = not user_roles or any(
            role_allowed_for_package(role, package) for role in user_roles
        )
        if not has_allowed_role:
            flash('Role akun ini tidak tersedia untuk paket modul tenant ini.', 'warning')
            session.pop('active_role', None)
            logout_user()
            return redirect(url_for('auth.login'))

        endpoint = request.endpoint or ""
        if not endpoint_allowed_for_package(endpoint, package):
            flash('Modul ini tidak aktif untuk tenant Anda.', 'warning')
            return redirect(url_for('main.dashboard'))

        return None

    # 5. Registrasi Blueprint
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.staff import staff_bp
    from app.routes.student import student_bp
    from app.routes.parent import parent_bp
    from app.routes.teacher import teacher_bp
    from app.routes.boarding import boarding_bp
    from app.routes.api import api_bp


    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(parent_bp, url_prefix='/parent')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(boarding_bp)
    app.register_blueprint(api_bp, url_prefix='/api/v1')

    return app
