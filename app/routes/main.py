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

# Kita hapus import model Student, Tahfidz, Schedule dll karena tidak dipakai lagi di sini
# Sisakan import yang dipakai untuk PPDB form saja
from app.models import (
    UserRole,
    StudentCandidate,
    ProgramType,
    EducationLevel,
    ScholarshipCategory,
    UniformSize,
    TahfidzSchedule,
    RegistrationStatus,
    Gender,
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
    Fungsi Dispatcher: Hanya mengarahkan user ke dashboard spesifik berdasarkan Role.
    """

    # 1. Admin
    if current_user.role == UserRole.ADMIN:
        return redirect(url_for('admin.dashboard'))

    # 2. Guru
    elif current_user.role == UserRole.GURU:
        return redirect(url_for('teacher.dashboard'))

    # 3. Staff TU
    elif current_user.role == UserRole.TU:
        return redirect(url_for('staff.dashboard'))

    # 4. SISWA
    elif current_user.role == UserRole.SISWA:
        return redirect(url_for('student.dashboard'))

    # 5. Wali Murid
    elif current_user.role == UserRole.WALI_MURID:
        return redirect(url_for('parent.dashboard'))

    # Fallback jika role tidak dikenali
    return render_template('index.html')


# ==========================================
# PPDB PUBLIC ROUTE (FORM PENDAFTARAN)
# ==========================================

@main_bp.route('/ppdb', methods=['GET', 'POST'])
def ppdb_register():
    form = PPDBForm()

    if form.validate_on_submit():
        try:
            # Logika berdasarkan program type
            try:
                program_type = ProgramType[form.program_type.data]
            except KeyError:
                flash('Pilihan program tidak valid.', 'danger')
                return render_template("public/ppdb_form.html", form=form)

            is_majlis = program_type == ProgramType.MAJLIS_TALIM
            is_rqdf = program_type == ProgramType.RQDF_SORE

            # Validasi kontak berdasarkan jenis program
            if is_majlis:
                contact_phone = form.personal_phone.data
                if not contact_phone:
                    flash("Nomor WhatsApp wajib diisi untuk Majelis Ta'lim", 'danger')
                    return render_template("public/ppdb_form.html", form=form)
            else:
                contact_phone = form.parent_phone.data
                if not contact_phone:
                    flash('Nomor Telepon Orang Tua wajib diisi', 'danger')
                    return render_template("public/ppdb_form.html", form=form)

            # Untuk Majelis, pakai default yang aman agar tidak tergantung field tersembunyi
            education_level = EducationLevel.NON_FORMAL if is_majlis else EducationLevel[form.education_level.data]
            scholarship_category = ScholarshipCategory.NON_BEASISWA if is_majlis else ScholarshipCategory[
                form.scholarship_category.data
            ]

            candidate = StudentCandidate(
                status=RegistrationStatus.PENDING,
                program_type=program_type,
                education_level=education_level,
                scholarship_category=scholarship_category,
                full_name=form.full_name.data,
                nickname=form.nickname.data,
                nik=form.nik.data,
                kk_number=form.kk_number.data,
                gender=Gender[form.gender.data],
                place_of_birth=form.place_of_birth.data,
                date_of_birth=form.date_of_birth.data,
                age=form.age.data,
                address=form.address.data,
                previous_school=form.previous_school.data,
                previous_school_class=form.previous_school_class.data,
                
                # Data Orang Tua (Optional untuk Majelis)
                father_name=form.father_name.data,
                father_job=form.father_job.data,
                father_income_range=form.father_income_range.data,
                mother_name=form.mother_name.data,
                mother_job=form.mother_job.data,
                mother_income_range=form.mother_income_range.data,
                
                # Phone logic berdasarkan program
                parent_phone=contact_phone,
                
                # BARU: Data khusus Majelis Ta'lim
                personal_phone=form.personal_phone.data if is_majlis else None,
                personal_job=form.personal_job.data if is_majlis else None,

                tahfidz_schedule=TahfidzSchedule[form.tahfidz_schedule.data] if is_rqdf else TahfidzSchedule.TIDAK_ADA,
                uniform_size=UniformSize[form.uniform_size.data] if is_rqdf else UniformSize.TIDAK_MEMILIH,
                initial_pledge_amount=form.initial_pledge_amount.data if is_rqdf else 0,
            )

            db.session.add(candidate)
            db.session.flush()

            year = datetime.now().year
            if program_type == ProgramType.MAJLIS_TALIM:
                candidate.registration_no = f"MAJ{year}{candidate.id:05d}"  # BARU: Prefix khusus Majelis
            else:
                candidate.registration_no = f"REG{year}{candidate.id:05d}"

            db.session.commit()

            flash(f"Pendaftaran berhasil. Nomor pendaftaran Anda: {candidate.registration_no}", "success")
            return render_template("public/ppdb_success.html", candidate=candidate)

        except Exception:
            db.session.rollback()
            current_app.logger.exception("PPDB registration failed")
            flash("Terjadi kesalahan sistem saat memproses pendaftaran.", "danger")

    return render_template("public/ppdb_form.html", form=form)