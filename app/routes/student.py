# app/routes/student.py

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy.orm import joinedload  # Wajib diimport untuk optimasi N+1
from app import db

from app.models import (
    UserRole, Student, TahfidzRecord, TahfidzSummary, TahfidzEvaluation,
    RecitationRecord,Schedule, Grade, Violation, AcademicYear, BehaviorReport,
    Attendance, ParticipantType, AttendanceStatus, BoardingAttendance, BoardingActivitySchedule
)
from app.decorators import role_required
from app.utils.announcements import get_announcements_for_dashboard, mark_announcements_as_read

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

    # [OPTIMASI DYNAMIC] Menggunakan relasi dynamic 'student.tahfidz_records'
    # Plus joinedload(teacher) agar nama ustadz tidak bikin query baru
    recent_tahfidz = student.tahfidz_records \
        .options(joinedload(TahfidzRecord.teacher)) \
        .order_by(TahfidzRecord.date.desc()) \
        .limit(5).all()

    recent_tahfidz_evaluations = student.tahfidz_evaluations \
        .options(joinedload(TahfidzEvaluation.teacher)) \
        .order_by(TahfidzEvaluation.date.desc()) \
        .limit(3).all()

    recent_recitations = student.recitation_records \
        .options(joinedload(RecitationRecord.teacher)) \
        .order_by(RecitationRecord.date.desc()) \
        .limit(5).all()

    top_tab = (request.args.get('top_tab') or 'main').strip().lower()
    show_all_announcements = (request.args.get('ann') or '').strip().lower() == 'all'
    class_program = student.current_class.program_type.name if student.current_class and student.current_class.program_type else None
    program_types = [class_program] if class_program else []

    announcements, unread_announcements_count = get_announcements_for_dashboard(
        current_user,
        class_ids=[student.current_class_id],
        user_ids=[current_user.id],
        program_types=program_types,
        show_all=show_all_announcements
    )
    if top_tab == 'ann':
        mark_announcements_as_read(current_user, announcements)
        unread_announcements_count = 0

    # --- BAGIAN 2: JADWAL PELAJARAN (OPTIMIZED N+1) ---
    today_name_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    today_idx = datetime.now().weekday()
    today_name = today_name_map[today_idx]

    # Jadwal Hari Ini
    # [OPTIMASI] Tambahkan joinedload untuk Subject & Teacher
    todays_schedules = Schedule.query \
        .options(
        joinedload(Schedule.subject),
        joinedload(Schedule.teacher)
    ) \
        .filter_by(
        class_id=student.current_class_id,
        day=today_name
    ).order_by(Schedule.start_time).all()

    # Jadwal Lengkap (Senin - Minggu)
    # [OPTIMASI] Tambahkan joinedload agar loop di HTML cepat
    all_schedules = Schedule.query \
        .options(
        joinedload(Schedule.subject),
        joinedload(Schedule.teacher)
    ) \
        .filter_by(class_id=student.current_class_id).all()

    # Logic pengelompokan Python (Tidak berubah, ini sudah oke)
    weekly_schedule = {day: [] for day in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']}
    for sch in all_schedules:
        if sch.day in weekly_schedule:
            weekly_schedule[sch.day].append(sch)

    for day in weekly_schedule:
        weekly_schedule[day].sort(key=lambda x: x.start_time)

    # --- BAGIAN 3: EVALUASI BELAJAR (NILAI) ---
    active_year = AcademicYear.query.filter_by(is_active=True).first()

    grades = []
    if active_year:
        # [OPTIMASI DYNAMIC + JOIN]
        # Menggunakan 'student.grades' (dynamic) lalu filter tahun ajaran
        # joinedload(subject) agar nama mapel langsung terambil
        grades = student.grades \
            .options(joinedload(Grade.subject)) \
            .filter_by(academic_year_id=active_year.id) \
            .order_by(Grade.subject_id, Grade.type) \
            .all()


    academic_recap = []
    if grades:
        by_subject = {}
        for g in grades:
            key = g.subject.name if g.subject else '-'
            by_subject.setdefault(key, {'subject': key, 'tugas_uh': [], 'uts': [], 'uas': []})
            if g.type.name in ('TUGAS', 'UH'):
                by_subject[key]['tugas_uh'].append(g.score)
            elif g.type.name == 'UTS':
                by_subject[key]['uts'].append(g.score)
            elif g.type.name == 'UAS':
                by_subject[key]['uas'].append(g.score)

        for item in by_subject.values():
            tugas = sum(item['tugas_uh']) / len(item['tugas_uh']) if item['tugas_uh'] else 0
            uts = sum(item['uts']) / len(item['uts']) if item['uts'] else 0
            uas = sum(item['uas']) / len(item['uas']) if item['uas'] else 0
            final = round((tugas * 0.3) + (uts * 0.3) + (uas * 0.4), 2)
            academic_recap.append({'subject': item['subject'], 'tugas_uh': round(tugas, 2), 'uts': round(uts, 2), 'uas': round(uas, 2),'final': final})

    # --- BAGIAN 4: CATATAN PERILAKU ---
    # [OPTIMASI DYNAMIC] Cukup panggil student.violations
    violations = student.violations \
        .order_by(Violation.date.desc()) \
        .all()

    total_points = sum(v.points for v in violations)
    behavior_reports = student.behavior_reports \
        .order_by(BehaviorReport.report_date.desc(), BehaviorReport.created_at.desc()) \
        .limit(30).all()

    attendances = student.attendances \
        .options(joinedload(Attendance.teacher)) \
        .filter(Attendance.participant_type == ParticipantType.STUDENT) \
        .order_by(Attendance.date.desc(), Attendance.created_at.desc()) \
        .limit(60).all()

    attendance_recap = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0}
    for att in attendances:
        if att.status == AttendanceStatus.HADIR:
            attendance_recap['hadir'] += 1
        elif att.status == AttendanceStatus.SAKIT:
            attendance_recap['sakit'] += 1
        elif att.status == AttendanceStatus.IZIN:
            attendance_recap['izin'] += 1
        elif att.status == AttendanceStatus.ALPA:
            attendance_recap['alpa'] += 1

    today = datetime.now().date()
    boarding_attendances = BoardingAttendance.query.join(
        BoardingActivitySchedule,
        BoardingAttendance.schedule_id == BoardingActivitySchedule.id
    ).filter(
        BoardingAttendance.student_id == student.id,
        BoardingAttendance.date >= today.replace(day=1)
    ).order_by(
        BoardingAttendance.date.desc(),
        BoardingActivitySchedule.start_time.asc()
    ).limit(100).all()

    boarding_today = [item for item in boarding_attendances if item.date == today]

    boarding_recap = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0}
    for record in boarding_attendances:
        if record.status == AttendanceStatus.HADIR:
            boarding_recap['hadir'] += 1
        elif record.status == AttendanceStatus.SAKIT:
            boarding_recap['sakit'] += 1
        elif record.status == AttendanceStatus.IZIN:
            boarding_recap['izin'] += 1
        elif record.status == AttendanceStatus.ALPA:
            boarding_recap['alpa'] += 1

    return render_template('student/dashboard.html',
                           student=student,
                           summary=summary,
                           recent_tahfidz=recent_tahfidz,
                           recent_tahfidz_evaluations=recent_tahfidz_evaluations,
                           recent_recitations=recent_recitations,
                           announcements=announcements,
                           top_tab=top_tab,
                           show_all_announcements=show_all_announcements,
                           unread_announcements_count=unread_announcements_count,
                           today_name=today_name,
                           todays_schedules=todays_schedules,
                           weekly_schedule=weekly_schedule,
                           grades=grades,
                           academic_recap=academic_recap,
                           violations=violations,
                           behavior_reports=behavior_reports,
                           attendances=attendances,
                           attendance_recap=attendance_recap,
                           boarding_attendances=boarding_attendances,
                           boarding_today=boarding_today,
                           boarding_recap=boarding_recap,
                           total_points=total_points)
