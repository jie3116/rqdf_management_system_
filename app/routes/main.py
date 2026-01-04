from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
import datetime
from app.extensions import db
from app.forms import PPDBForm
from app.models import (
    UserRole, StudentCandidate, ProgramType, EducationLevel,
    ScholarshipCategory, UniformSize, TahfidzSchedule,
    RegistrationStatus, Gender
)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    # Halaman awal langsung arahkan ke Login
    return redirect(url_for('auth.login'))


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Fungsi ini bertugas sebagai ROUTER PUSAT.
    Dia tidak menampilkan halaman, tapi melempar (redirect) user
    ke controller spesifik sesuai jabatannya.
    """

    # 1. ADMIN -> Lempar ke routes/admin.py
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin.dashboard'))

    # 2. TATA USAHA -> Lempar ke routes/staff.py (Solusi error tadi)
    elif current_user.role == UserRole.TU:
        return redirect(url_for('staff.dashboard'))

    # 3. WALI MURID -> Lempar ke routes/parent.py
    elif current_user.role == UserRole.WALI_MURID:
        return redirect(url_for('parent.dashboard'))

    # 4. SISWA -> Render langsung (karena simpel) atau buat routes/student.py nanti
    elif current_user.role == UserRole.SISWA:
        student = current_user.student_profile
        return render_template('student/dashboard.html', student=student)

    # 5. GURU -> Render placeholder
    elif current_user.role == UserRole.GURU:
        return render_template('teacher/dashboard.html')

    return "Role tidak dikenali atau Anda tidak memiliki akses.", 403


# ==========================================
# PPDB PUBLIC ROUTE (FORM PENDAFTARAN)
# ==========================================
@main_bp.route('/ppdb', methods=['GET', 'POST'])
def ppdb_register():
    form = PPDBForm()

    if form.validate_on_submit():
        try:
            # 1. Buat object candidate TANPA registration_no
            candidate = StudentCandidate(
                # Status awal pendaftaran
                status=RegistrationStatus.PENDING,

                # Dropdown Enums
                program_type=ProgramType[form.program_type.data],
                education_level=EducationLevel[form.education_level.data],
                scholarship_category=ScholarshipCategory[form.scholarship_category.data],

                # Data Diri
                full_name=form.full_name.data,
                nickname=form.nickname.data,
                nik=form.nik.data,
                kk_number=form.kk_number.data,
                gender=Gender[form.gender.data],
                place_of_birth=form.place_of_birth.data,
                date_of_birth=form.date_of_birth.data,
                age=form.age.data,
                address=form.address.data,

                # Sekolah Asal
                previous_school=form.previous_school.data,
                previous_school_class=form.previous_school_class.data,

                # Orang Tua
                father_name=form.father_name.data,
                father_job=form.father_job.data,
                father_income_range=form.father_income_range.data,
                mother_name=form.mother_name.data,
                mother_job=form.mother_job.data,
                mother_income_range=form.mother_income_range.data,
                parent_phone=form.parent_phone.data,

                # Tambahan
                tahfidz_schedule=TahfidzSchedule[form.tahfidz_schedule.data],
                uniform_size=UniformSize[form.uniform_size.data],
                initial_pledge_amount=form.initial_pledge_amount.data
            )

            # 2. Simpan sementara untuk mendapatkan ID (AMAN)
            db.session.add(candidate)
            db.session.flush()  # candidate.id tersedia di sini

            # 3. Generate nomor registrasi BERDASARKAN ID
            year = datetime.datetime.now().year
            candidate.registration_no = f"REG{year}{candidate.id:05d}"

            # 4. Commit final
            db.session.commit()

            flash(
                f"Pendaftaran berhasil. Nomor pendaftaran Anda: {candidate.registration_no}",
                "success"
            )

            return render_template(
                "public/ppdb_success.html",
                candidate=candidate
            )

        except Exception:
            db.session.rollback()
            current_app.logger.exception("PPDB registration failed")

            flash(
                "Terjadi kesalahan sistem saat memproses pendaftaran. "
                "Silakan coba kembali atau hubungi panitia.",
                "danger"
            )

    return render_template("public/ppdb_form.html", form=form)
