from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from app.models import (
    UserRole, TahfidzRecord, TahfidzSummary, Announcement, TahfidzEvaluation,
    RecitationRecord, Schedule, Grade, Violation, AcademicYear, Invoice, PaymentStatus,
ParticipantType, StudentCandidate, ProgramType, EducationLevel, ScholarshipCategory, RegistrationStatus
)
from app.decorators import role_required
from app.extensions import db

parent_bp = Blueprint('parent', __name__)


def _get_majlis_announcements(limit=None):
    query = Announcement.query.filter_by(is_active=True).order_by(Announcement.created_at.desc())
    announcements = query.limit(limit).all() if limit else query.all()
    majlis_announcements = [
        item for item in announcements
        if 'majelis' in (item.title or '').lower() or 'majelis' in (item.content or '').lower()
    ]
    return announcements, majlis_announcements


@parent_bp.route('/join-majlis', methods=['GET'])
@login_required
@role_required(UserRole.WALI_MURID)
def join_majlis():
    parent = current_user.parent_profile
    if not parent:
        flash("Profil Wali Murid tidak ditemukan.", "danger")
        return redirect(url_for('parent.dashboard'))

    existing_candidate = StudentCandidate.query.filter(
        StudentCandidate.program_type == ProgramType.MAJLIS_TALIM,
        StudentCandidate.parent_phone == parent.phone,
        StudentCandidate.status.in_(
            [RegistrationStatus.PENDING, RegistrationStatus.INTERVIEW, RegistrationStatus.ACCEPTED])
    ).order_by(StudentCandidate.created_at.desc()).first()

    if existing_candidate and parent.is_majlis_participant:
        flash("Anda sudah terdaftar sebagai peserta Majelis Ta'lim.", "info")
        return redirect(url_for('parent.majlis_dashboard'))

    if not existing_candidate:
        candidate = StudentCandidate(
            status=RegistrationStatus.PENDING,
            program_type=ProgramType.MAJLIS_TALIM,
            education_level=EducationLevel.NON_FORMAL,
            scholarship_category=ScholarshipCategory.NON_BEASISWA,
            full_name=parent.full_name,
            address=parent.address,
            parent_phone=parent.phone,
            personal_phone=parent.phone,
            personal_job=parent.job,
        )
        db.session.add(candidate)
        db.session.flush()
        year = datetime.now().year
        candidate.registration_no = f"MAJ{year}{candidate.id:05d}"

    if not parent.is_majlis_participant:
        parent.is_majlis_participant = True
        parent.majlis_join_date = datetime.now().date()

    try:
        db.session.commit()
        if existing_candidate:
            flash("Data pendaftaran Majelis Anda sudah ada di daftar PPDB.", "info")
        else:
            flash("Pendaftaran Majelis berhasil dikirim ke daftar PPDB untuk verifikasi.", "success")
    except Exception:
        db.session.rollback()
        flash("Terjadi kesalahan saat mendaftarkan Majelis Ta'lim.", "danger")

    return redirect(url_for('parent.majlis_dashboard'))

@parent_bp.route('/dashboard')
@login_required
@role_required(UserRole.WALI_MURID)
def dashboard():
    parent = current_user.parent_profile
    if not parent:
        flash("Profil Wali Murid tidak ditemukan. Hubungi Admin.", "danger")
        return render_template('index.html')

    children = parent.children
    if not children:
        return render_template('parent/empty_state.html')

    selected_student_id = request.args.get('student_id', type=int)
    student = None

    if selected_student_id:
        student = next((child for child in children if child.id == selected_student_id), None)
        if not student:
            flash("Akses ditolak: Data siswa tidak terdaftar sebagai anak Anda.", "warning")

    if not student:
        student = children[0]

    summary = TahfidzSummary.query.filter_by(
        student_id=student.id,
        participant_type=ParticipantType.STUDENT
    ).first()

    recent_tahfidz = TahfidzRecord.query.filter_by(
        student_id=student.id,
        participant_type=ParticipantType.STUDENT
    ).order_by(TahfidzRecord.date.desc()).limit(5).all()

    recent_recitation = RecitationRecord.query.filter_by(
        student_id=student.id,
        participant_type=ParticipantType.STUDENT
    ).order_by(RecitationRecord.date.desc()).limit(5).all()

    recent_tahfidz_evaluations = TahfidzEvaluation.query.filter_by(
        student_id=student.id,
        participant_type=ParticipantType.STUDENT
    ).order_by(TahfidzEvaluation.date.desc()).limit(3).all()

    announcements, _ = _get_majlis_announcements(limit=3)

    today_name_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    today_name = today_name_map[datetime.now().weekday()]

    todays_schedules = []
    if student.current_class_id:
        todays_schedules = Schedule.query.filter_by(
            class_id=student.current_class_id, day=today_name
        ).order_by(Schedule.start_time).all()

    weekly_schedule = {day: [] for day in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']}
    if student.current_class_id:
        all_schedules = Schedule.query.filter_by(class_id=student.current_class_id).all()
        for sch in all_schedules:
            if sch.day in weekly_schedule:
                weekly_schedule[sch.day].append(sch)
        for day in weekly_schedule:
            weekly_schedule[day].sort(key=lambda x: x.start_time)

    active_year = AcademicYear.query.filter_by(is_active=True).first()
    grades = []
    if active_year:
        grades = Grade.query.filter_by(student_id=student.id, academic_year_id=active_year.id) \
            .order_by(Grade.subject_id, Grade.type).all()

    violations = Violation.query.filter_by(student_id=student.id).order_by(Violation.date.desc()).all()
    total_points = sum(v.points for v in violations)

    invoices = Invoice.query.filter_by(student_id=student.id).order_by(Invoice.created_at.desc()).all()
    total_tagihan = sum(inv.total_amount - inv.paid_amount for inv in invoices if inv.status != PaymentStatus.PAID)

    return render_template('parent/dashboard.html',
                           parent=parent,
                           children=children,
                           student=student,
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


@parent_bp.route('/dashboard/majlis')
@ login_required
@ role_required(UserRole.WALI_MURID)
def majlis_dashboard():
    parent = current_user.parent_profile
    if not parent:
        flash("Profil Wali Murid tidak ditemukan.", "danger")
        return redirect(url_for('parent.dashboard'))

    if not parent.is_majlis_participant:
        flash("Anda belum terdaftar sebagai peserta Majelis Ta'lim.", "info")
        return redirect(url_for('parent.dashboard'))

    announcements, majlis_announcements = _get_majlis_announcements()

    summary = TahfidzSummary.query.filter_by(
        parent_id=parent.id,
        participant_type=ParticipantType.PARENT_MAJLIS
    ).first()

    recent_tahfidz = TahfidzRecord.query.filter_by(
        parent_id=parent.id,
        participant_type=ParticipantType.PARENT_MAJLIS
    ).order_by(TahfidzRecord.date.desc()).limit(10).all()

    recent_recitation = RecitationRecord.query.filter_by(
        parent_id=parent.id,
        participant_type=ParticipantType.PARENT_MAJLIS
    ).order_by(RecitationRecord.date.desc()).limit(10).all()

    recent_evaluations = TahfidzEvaluation.query.filter_by(
        parent_id=parent.id,
        participant_type=ParticipantType.PARENT_MAJLIS
    ).order_by(TahfidzEvaluation.date.desc()).limit(10).all()

    weekly_schedule = {day: [] for day in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']}
    if parent.majlis_class_id:
        schedules = Schedule.query.filter_by(class_id=parent.majlis_class_id).order_by(Schedule.start_time).all()
        for sch in schedules:
            if sch.day in weekly_schedule:
                weekly_schedule[sch.day].append(sch)

    children = parent.children
    latest_child = children[0] if children else None

    return render_template('parent/dashboard_majlis.html',
                           parent=parent,
                           children=children,
                           latest_child=latest_child,
                           announcements=announcements,
                           majlis_announcements=majlis_announcements,
                           summary=summary,
                           recent_tahfidz=recent_tahfidz,
                           recent_recitation=recent_recitation,
                           recent_evaluations=recent_evaluations,
                           majlis_class=parent.majlis_class,
                           weekly_schedule=weekly_schedule)


@parent_bp.route('/majelis-kegiatan')
@login_required
@role_required(UserRole.WALI_MURID)
def majlis_activities():
    parent = current_user.parent_profile
    if not parent:
        flash("Profil Wali Murid tidak ditemukan.", "danger")
        return redirect(url_for('parent.dashboard'))

    announcements, majlis_announcements = _get_majlis_announcements()

    return render_template('parent/majlis_activities.html',
                           parent=parent,
                           majlis_announcements=majlis_announcements,
                           announcements=announcements)