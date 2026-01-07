# app/routes/student.py

from flask import Blueprint, render_template
from flask_login import login_required, current_user
from datetime import datetime
from app.models import (
    UserRole, Student, TahfidzRecord, TahfidzSummary, Announcement,
    Schedule, Grade, Violation, AcademicYear
)
from app.decorators import role_required

student_bp = Blueprint('student', __name__)


@student_bp.route('/dashboard')
@login_required
@role_required(UserRole.SISWA)
def dashboard():
    # 1. Identifikasi Santri
    student = current_user.student_profile
    if not student:
        return "Data profil siswa tidak ditemukan", 404

    # --- BAGIAN 1: DATA TAHFIDZ & PENGUMUMAN ---
    summary = TahfidzSummary.query.filter_by(student_id=student.id).first()
    recent_tahfidz = TahfidzRecord.query.filter_by(student_id=student.id) \
        .order_by(TahfidzRecord.date.desc()).limit(5).all()
    announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).limit(3).all()

    # --- BAGIAN 2: JADWAL PELAJARAN (Hari Ini & Lengkap) ---
    today_name_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    today_idx = datetime.now().weekday()
    today_name = today_name_map[today_idx]

    # Jadwal Hari Ini
    todays_schedules = Schedule.query.filter_by(
        class_id=student.current_class_id,
        day=today_name
    ).order_by(Schedule.start_time).all()

    # Jadwal Lengkap (Senin - Minggu)
    # Kita ambil semua jadwal kelas ini, lalu urutkan di Python atau Template
    all_schedules = Schedule.query.filter_by(class_id=student.current_class_id).all()

    # Kelompokkan jadwal per hari untuk memudahkan loop di HTML
    # Format: {'Senin': [obj_jadwal, obj_jadwal], 'Selasa': [...]}
    weekly_schedule = {day: [] for day in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']}
    for sch in all_schedules:
        if sch.day in weekly_schedule:
            weekly_schedule[sch.day].append(sch)

    # Sortir jam per hari
    for day in weekly_schedule:
        weekly_schedule[day].sort(key=lambda x: x.start_time)

    # --- BAGIAN 3: EVALUASI BELAJAR (NILAI) ---
    # Ambil Tahun Ajaran Aktif (Asumsi ada flag is_active di model AcademicYear)
    active_year = AcademicYear.query.filter_by(is_active=True).first()

    grades = []
    if active_year:
        grades = Grade.query.filter_by(
            student_id=student.id,
            academic_year_id=active_year.id
        ).order_by(Grade.subject_id, Grade.type).all()

    # Kelompokkan Nilai berdasarkan Mata Pelajaran agar rapi
    # Structure: {'Matematika': {'Tugas': [80, 90], 'UTS': 85}, 'IPA': {...}}
    # (Untuk simplifikasi tampilan awal, kita kirim raw object 'grades' dulu, nanti filter di HTML)

    # --- BAGIAN 4: CATATAN PERILAKU ---
    violations = Violation.query.filter_by(student_id=student.id).order_by(Violation.date.desc()).all()
    total_points = sum(v.points for v in violations)

    return render_template('student/dashboard.html',
                           student=student,
                           summary=summary,
                           recent_tahfidz=recent_tahfidz,
                           announcements=announcements,
                           today_name=today_name,
                           todays_schedules=todays_schedules,
                           weekly_schedule=weekly_schedule,  # Baru
                           grades=grades,  # Baru
                           violations=violations,  # Baru
                           total_points=total_points)  # Baru