from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app.extensions import db
from app.models import User, Teacher, Parent, MajlisParticipant, BoardingGuardian, Student
from app.forms import LoginForm, ChangePasswordForm
from sqlalchemy import or_
from werkzeug.security import generate_password_hash
from app.utils.security import is_safe_url
from app.utils.roles import get_active_role, set_active_role, role_label


auth_bp = Blueprint('auth', __name__)


def _resolve_user_for_login(login_id):
    identifier = (login_id or '').strip()
    if not identifier:
        return None, False

    # 1) Prioritas: username/email langsung pada tabel users
    direct_user = User.query.filter(
        or_(User.email == identifier, User.username == identifier)
    ).first()
    if direct_user:
        return direct_user, False

    # 2) Fallback: cari dari identifier profil lintas role
    candidate_ids = set()

    teacher_rows = db.session.query(Teacher.user_id).filter(
        or_(Teacher.nip == identifier, Teacher.phone == identifier)
    ).all()
    candidate_ids.update(row[0] for row in teacher_rows if row[0])

    parent_rows = db.session.query(Parent.user_id).filter(Parent.phone == identifier).all()
    candidate_ids.update(row[0] for row in parent_rows if row[0])

    majlis_rows = db.session.query(MajlisParticipant.user_id).filter(MajlisParticipant.phone == identifier).all()
    candidate_ids.update(row[0] for row in majlis_rows if row[0])

    guardian_rows = db.session.query(BoardingGuardian.user_id).filter(BoardingGuardian.phone == identifier).all()
    candidate_ids.update(row[0] for row in guardian_rows if row[0])

    student_rows = db.session.query(Student.user_id).filter(
        or_(Student.nis == identifier, Student.nisn == identifier)
    ).all()
    candidate_ids.update(row[0] for row in student_rows if row[0])

    if not candidate_ids:
        return None, False

    if len(candidate_ids) > 1:
        return None, True

    user = User.query.get(next(iter(candidate_ids)))
    return user, False


# --- THE BOUNCER (SATPAM) ---
@auth_bp.before_app_request
def check_force_password_change():
    """
    Cek setiap request:
    Jika user login DAN statusnya 'must_change_password' == True,
    Maka PAKSA dia ke halaman ganti password.
    Kecuali dia sedang mengakses halaman statis (css/js) atau halaman logout.
    """
    if current_user.is_authenticated and current_user.must_change_password:
        # Daftar endpoint yang BOLEH diakses meski belum ganti password
        allowed_endpoints = ['auth.change_password', 'auth.logout', 'static']

        if request.endpoint not in allowed_endpoints:
            flash('Demi keamanan, Anda wajib mengganti password default sebelum melanjutkan.', 'warning')
            return redirect(url_for('auth.change_password'))


# --- ROUTE LOGIN ----
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user, is_ambiguous = _resolve_user_for_login(form.login_id.data)

        if is_ambiguous:
            flash('Login gagal: identifier terhubung ke lebih dari satu akun. Hubungi admin untuk sinkronisasi data.', 'danger')
            return render_template('auth/login.html', title='Login', form=form)

        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)

            # Cek status password di sini juga untuk redirect awal
            if user.must_change_password:
                return redirect(url_for('auth.change_password'))

            roles = list(user.all_roles()) if hasattr(user, 'all_roles') else ([user.role] if user.role else [])
            if len(roles) > 1:
                return redirect(url_for('auth.select_role'))

            if roles:
                set_active_role(user, roles[0])

            next_page = request.args.get('next')
            if is_safe_url(next_page):
                return redirect(next_page)

            return redirect(url_for('main.dashboard'))
        else:
            flash('Login gagal. Cek kembali Username/Email/NIS/NIP/No HP dan password.', 'danger')

    return render_template('auth/login.html', title='Login', form=form)


# --- ROUTE GANTI PASSWORD (BARU) ---
@auth_bp.route('/ganti-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()

    if form.validate_on_submit():
        # 1. Cek Password Lama Benar tidak?
        if not current_user.check_password(form.old_password.data):
            flash('Password lama salah!', 'danger')
            return render_template('auth/change_password.html', form=form)

        # 2. Update Password
        current_user.password_hash = generate_password_hash(form.new_password.data)

        # 3. MATIKAN FLAG WAJIB GANTI
        current_user.must_change_password = False

        db.session.commit()

        flash('Password berhasil diperbarui! Silakan masuk ke dashboard.', 'success')
        roles = list(current_user.all_roles()) if hasattr(current_user, 'all_roles') else ([current_user.role] if current_user.role else [])
        if len(roles) > 1:
            return redirect(url_for('auth.select_role'))
        if roles:
            set_active_role(current_user, roles[0])
        return redirect(url_for('main.dashboard'))

    return render_template('auth/change_password.html', form=form)


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    from flask import session
    session.pop('active_role', None)
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/pilih-role', methods=['GET', 'POST'])
@login_required
def select_role():
    roles = sorted(
        list(current_user.all_roles()),
        key=lambda role: role.value
    )

    if request.method == 'POST':
        role_raw = request.form.get('active_role')
        next_page = request.form.get('next') or request.args.get('next')
        if set_active_role(current_user, role_raw):
            flash(f'Role aktif diubah ke {role_label(role_raw)}.', 'success')
            if is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('main.dashboard'))

        flash('Role yang dipilih tidak valid.', 'danger')
        return redirect(url_for('auth.select_role', next=next_page))

    current_active = get_active_role(current_user)
    next_page = request.args.get('next')
    return render_template(
        'auth/select_role.html',
        roles=roles,
        current_active=current_active,
        role_label=role_label,
        next_page=next_page
    )
