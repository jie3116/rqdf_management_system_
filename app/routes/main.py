from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
import datetime
from app.extensions import db
from app.forms import PPDBForm
from app.models import (
    UserRole, Student, Parent,
    StudentCandidate, ProgramType, EducationLevel,
    ScholarshipCategory, UniformSize, TahfidzSchedule,
    RegistrationStatus, Gender
)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # 1. ADMIN
    if current_user.role == UserRole.ADMIN:
        total_siswa = Student.query.count()
        # Nanti bisa diupdate mengambil total dari tabel Transaction
        total_uang = 0
        return render_template('admin/dashboard.html', total_siswa=total_siswa, total_uang=total_uang)

    # 2. SISWA
    elif current_user.role == UserRole.SISWA:
        student = current_user.student_profile
        return render_template('student/dashboard.html', student=student)

    # 3. WALI MURID
    elif current_user.role == UserRole.WALI_MURID:
        parent = current_user.parent_profile
        children = parent.children if parent else []
        return render_template('parent/dashboard.html', parent=parent, children=children)

    # 4. GURU
    elif current_user.role == UserRole.GURU:
        return render_template('teacher/dashboard.html')

    # 5. TATA USAHA
    elif current_user.role == UserRole.TU:
        return render_template('staff/dashboard.html')

    return "Role tidak dikenali", 403


@main_bp.route('/ppdb', methods=['GET', 'POST'])
def ppdb_register():
    form = PPDBForm()

    if form.validate_on_submit():
        try:
            # Generate No Register: REG-TAHUN-URUTAN
            # Contoh: REG2026005
            year = datetime.datetime.now().year
            count = StudentCandidate.query.count() + 1
            reg_no = f"REG{year}{str(count).zfill(3)}"

            # Buat Object Candidate
            candidate = StudentCandidate(
                registration_no=reg_no,

                # Dropdown Enums (Konversi String dari Form ke Enum Database)
                program_type=ProgramType[form.program_type.data],
                education_level=EducationLevel[form.education_level.data],
                scholarship_category=ScholarshipCategory[form.scholarship_category.data],
                status=RegistrationStatus.PENDING,

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

                # Khusus RQDF Sore / Pilihan Tambahan
                tahfidz_schedule=TahfidzSchedule[form.tahfidz_schedule.data],
                uniform_size=UniformSize[form.uniform_size.data],
                initial_pledge_amount=form.initial_pledge_amount.data
            )

            db.session.add(candidate)
            db.session.commit()

            flash('Pendaftaran Berhasil! Admin akan segera menghubungi via WhatsApp.', 'success')
            # Kita arahkan ke halaman sukses (perlu dibuat template html-nya)
            return render_template('public/ppdb_success.html', candidate=candidate)

        except Exception as e:
            db.session.rollback()
            print(f"Error PPDB: {e}")
            flash(f"Terjadi kesalahan saat menyimpan data: {e}", "danger")

    return render_template('public/ppdb_form.html', form=form)