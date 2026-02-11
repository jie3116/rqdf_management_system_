from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from app.models import (
    UserRole, TahfidzRecord, TahfidzSummary, Announcement, TahfidzEvaluation,
    RecitationRecord, Schedule, Grade, Violation, AcademicYear, Invoice, PaymentStatus,
    ParticipantType
)
from app.decorators import role_required

parent_bp = Blueprint('parent', __name__)


@parent_bp.route('/dashboard')
@login_required
@role_required(UserRole.WALI_MURID)
def dashboard():
    # 1. Identifikasi Wali Murid
    parent = current_user.parent_profile
    if not parent:
        flash("Profil Wali Murid tidak ditemukan. Hubungi Admin.", "danger")
        return render_template('index.html')

    # 2. Ambil Semua Anak (Kakak & Adik)
    children = parent.children

    if not children:
        # Jika akun wali ada, tapi belum ditautkan ke siswa manapun
        return render_template('parent/empty_state.html')

    # 3. LOGIKA PILIH ANAK (SWITCH PROFILE)
    selected_student_id = request.args.get('student_id', type=int)
    student = None

    if selected_student_id:
        # SECURITY CHECK: Pastikan ID yang diminta adalah anak kandung user ini
        student = next((child for child in children if child.id == selected_student_id), None)

        if not student:
            flash("Akses ditolak: Data siswa tidak terdaftar sebagai anak Anda.", "warning")

    # 4. Fallback: Default ke Anak Pertama jika tidak memilih
    if not student:
        student = children[0]

    # =======================================================
    # QUERY DATA (Khusus untuk 'student' yang sedang dipilih)
    # =======================================================

    # A. Tahfidz
    summary = TahfidzSummary.query.filter_by(
        student_id=student.id, 
        participant_type=ParticipantType.STUDENT
    ).first()
    
    recent_tahfidz = TahfidzRecord.query.filter_by(
        student_id=student.id,
        participant_type=ParticipantType.STUDENT
    ).order_by(TahfidzRecord.date.desc()).limit(5).all()
    
    # B. Setoran Bacaan
    recent_recitation = RecitationRecord.query.filter_by(
        student_id=student.id,
        participant_type=ParticipantType.STUDENT
    ).order_by(RecitationRecord.date.desc()).limit(5).all()
    
    recent_tahfidz_evaluations = TahfidzEvaluation.query.filter_by(
        student_id=student.id,
        participant_type=ParticipantType.STUDENT
    ).order_by(TahfidzEvaluation.date.desc()).limit(3).all()

    # C. Pengumuman (Umum)
    announcements = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc()).limit(3).all()

    # D. Jadwal Hari Ini
    today_name_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    today_name = today_name_map[datetime.now().weekday()]

    todays_schedules = []
    if student.current_class_id:
        todays_schedules = Schedule.query.filter_by(
            class_id=student.current_class_id, day=today_name
        ).order_by(Schedule.start_time).all()

    # E. Jadwal Mingguan
    weekly_schedule = {day: [] for day in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']}
    if student.current_class_id:
        all_schedules = Schedule.query.filter_by(class_id=student.current_class_id).all()
        for sch in all_schedules:
            if sch.day in weekly_schedule:
                weekly_schedule[sch.day].append(sch)
        for day in weekly_schedule:
            weekly_schedule[day].sort(key=lambda x: x.start_time)

    # F. Nilai Akademik
    active_year = AcademicYear.query.filter_by(is_active=True).first()
    grades = []
    if active_year:
        grades = Grade.query.filter_by(student_id=student.id, academic_year_id=active_year.id) \
            .order_by(Grade.subject_id, Grade.type).all()

    # G. Pelanggaran
    violations = Violation.query.filter_by(student_id=student.id).order_by(Violation.date.desc()).all()
    total_points = sum(v.points for v in violations)

    # H. KEUANGAN / TAGIHAN (Penting bagi Ortu)
    invoices = Invoice.query.filter_by(student_id=student.id).order_by(Invoice.created_at.desc()).all()
    # Hitung total yang BELUM LUNAS saja
    total_tagihan = sum(inv.total_amount - inv.paid_amount for inv in invoices if inv.status != PaymentStatus.PAID)

    return render_template('parent/dashboard.html',
                           parent=parent,
                           children=children,  # Untuk Dropdown
                           student=student,  # Anak Aktif
                           summary=summary,
                           recent_tahfidz=recent_tahfidz,
                           recent_recitation=recent_recitation,
                           recent_tahfidz_evaluations=recent_tahfidz_evaluations,
                           announcements=announcements,
                           today_name=today_name,
                           todays_schedules=todays_schedules,
                           weekly_schedule=weekly_schedule,
                           grades=grades,
                           violations=violations,
                           total_points=total_points,
                           invoices=invoices,
                           total_tagihan=total_tagihan)