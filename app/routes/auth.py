from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from app.extensions import db
from app.models import User
from app.forms import LoginForm, ChangePasswordForm
from sqlalchemy import or_
from werkzeug.security import generate_password_hash

auth_bp = Blueprint('auth', __name__)


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


# --- ROUTE LOGIN (Sama seperti sebelumnya) ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(
            or_(
                User.email == form.login_id.data,
                User.username == form.login_id.data
            )
        ).first()

        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)

            # Cek status password di sini juga untuk redirect awal
            if user.must_change_password:
                return redirect(url_for('auth.change_password'))

            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.dashboard'))
        else:
            flash('Login gagal. Cek kembali Email/No HP dan password.', 'danger')

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
        return redirect(url_for('main.dashboard'))

    return render_template('auth/change_password.html', form=form)


@auth_bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))