from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Student, Grade, Subject, UserRole
from app.decorators import role_required  # Custom decorator yang kita buat

academic_bp = Blueprint('academic', __name__)


# 1. Halaman Input Nilai (Hanya Guru)
@academic_bp.route('/input-nilai', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)  # Hanya Guru yang boleh akses
def input_grade():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        subject_id = request.form.get('subject_id')
        score = request.form.get('score')
        type = request.form.get('type')  # UTS/UAS/TUGAS

        # Simpan ke Database
        new_grade = Grade(
            student_id=student_id,
            subject_id=subject_id,
            teacher_id=current_user.teacher_profile.id,  # Ambil ID teacher yang sedang login
            score=float(score),
            type=type
        )
        new_grade.save()  # Menggunakan method save() dari BaseModel
        flash('Nilai berhasil disimpan!', 'success')
        return redirect(url_for('academic.input_grade'))

    # GET: Tampilkan Form
    students = Student.query.all()  # Nanti filter by kelas ajar teacher
    subjects = Subject.query.all()
    return render_template('academic/input_grade.html', students=students, subjects=subjects)


# 2. Halaman Lihat Rapor (Siswa & Orang Tua)
@academic_bp.route('/rapor-saya')
@login_required
def my_report():
    if current_user.role == UserRole.SISWA:
        grades = current_user.student_profile.grades
    elif current_user.role == UserRole.WALI_MURID:
        # Jika ortu, tampilkan anak-anaknya (Logic sederhana ambil anak pertama dulu)
        grades = current_user.parent_profile.children[0].grades
    else:
        flash("Akses ditolak", "danger")
        return redirect(url_for('main.dashboard'))

    return render_template('academic/report_card.html', grades=grades)