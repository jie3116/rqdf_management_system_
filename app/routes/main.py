from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    current_app,
)

from flask_login import (
    login_required,
    current_user,
)

from app.extensions import db
from app.forms import PPDBForm
from app.models import (
    UserRole,
    StudentCandidate,
    Student,
    ProgramType,
    EducationLevel,
    ScholarshipCategory,
    UniformSize,
    TahfidzSchedule,
    RegistrationStatus,
    Gender,
    TahfidzSummary,
    TahfidzRecord,
    Announcement,
    Schedule,
)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    # Halaman awal langsung arahkan ke Login
    return redirect(url_for('auth.login'))

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # 1. Redirect untuk Admin, Guru, Staff, Wali (Logic Lama)
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin.dashboard'))
    elif current_user.role == UserRole.GURU:
        return redirect(url_for('academic.teacher_dashboard'))  # Pastikan route ini ada di app/routes/academic.py atau main.py
    elif current_user.role == UserRole.TU:
        return redirect(url_for('staff.dashboard'))
    elif current_user.role == UserRole.WALI_MURID:
        return redirect(url_for('parent_dashboard'))  # Perlu dibuat nanti jika belum ada

    # 2. Logic Khusus Dashboard SISWA
    elif current_user.role == UserRole.SISWA:
        student = current_user.student_profile

        # --- DATA TAHFIDZ ---
        summary = TahfidzSummary.query.filter_by(student_id=student.id).first()
        recent_tahfidz = TahfidzRecord.query.filter_by(student_id=student.id) \
            .order_by(TahfidzRecord.date.desc()) \
            .limit(5).all()

        # --- PENGUMUMAN ---
        announcements = Announcement.query.filter_by(is_active=True) \
            .order_by(Announcement.created_at.desc()).limit(3).all()

        # --- [BARU] JADWAL HARI INI ---
        # 1. Dapatkan nama hari dalam Bahasa Indonesia
        days_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
        today_name = days_map[datetime.now().weekday()]

        # 2. Query Jadwal sesuai Kelas & Hari
        todays_schedules = []
        if student.current_class:
            todays_schedules = Schedule.query.filter_by(
                class_id=student.current_class.id,
                day=today_name
            ).order_by(Schedule.start_time).all()

        return render_template('student/dashboard.html',
                               student=student,
                               summary=summary,
                               recent_tahfidz=recent_tahfidz,
                               announcements=announcements,
                               todays_schedules=todays_schedules,  # Kirim ke HTML
                               today_name=today_name)

    return render_template('index.html')


# Route placeholder jika belum ada di tempat lain
@main_bp.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    return render_template('teacher/dashboard.html')


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
