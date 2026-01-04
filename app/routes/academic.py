from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Student, Grade, Subject, UserRole, TahfidzRecord, TahfidzType, TahfidzSummary
from app.decorators import role_required  # Custom decorator
from datetime import datetime

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



@academic_bp.route('/tahfidz/input', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz():
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        jenis_setoran = request.form.get('type')

        # Ambil data form yang baru
        start_surah = request.form.get('start_surah')
        end_surah = request.form.get('end_surah')
        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')

        # Ambil Juz yang dihitung otomatis oleh JS, atau input manual user
        juz_start = request.form.get('juz_start')

        quality = request.form.get('quality')
        notes = request.form.get('notes')

        # Logic Penamaan Surat di Database
        if start_surah == end_surah:
            final_surah_name = start_surah
        else:
            final_surah_name = f"{start_surah} (Ayat {ayat_start}) ⮕ {end_surah} (Ayat {ayat_end})"

        # Simpan Record
        new_record = TahfidzRecord(
            student_id=student_id,
            teacher_id=current_user.teacher_profile.id,
            type=TahfidzType[jenis_setoran],
            juz=int(juz_start),
            surah=final_surah_name,
            ayat_start=int(ayat_start),
            ayat_end=int(ayat_end),
            quality=quality,
            notes=notes,
            date=datetime.now()
        )
        db.session.add(new_record)

        # Logic Update Summary (Sederhana: Tambah poin jika Ziyadah)
        if jenis_setoran == 'ZIYADAH':
            summary = TahfidzSummary.query.filter_by(student_id=student_id).first()
            if not summary:
                summary = TahfidzSummary(student_id=student_id, total_juz=0)
                db.session.add(summary)

            # Update posisi terakhir santri
            summary.last_surah = end_surah
            summary.last_ayat = int(ayat_end)
            # Opsional: Anda bisa buat logic complex hitung total juz di sini

        db.session.commit()
        flash('Setoran hafalan berhasil dicatat!', 'success')
        return redirect(url_for('academic.input_tahfidz'))

    students = Student.query.filter_by(is_deleted=False).all()
    return render_template('admin/academic/input_tahfidz.html', students=students)


@academic_bp.route('/guru/dashboard')
@login_required
@role_required(UserRole.GURU)
def teacher_dashboard():
    return render_template('teacher/dashboard.html')