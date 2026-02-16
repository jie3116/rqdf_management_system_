from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import or_
from app.models import (
    UserRole, TahfidzRecord, TahfidzSummary, TahfidzEvaluation, ProgramType,
    RecitationRecord, Schedule, Grade, Violation, AcademicYear, Invoice, PaymentStatus,
ParticipantType, StudentCandidate, ProgramType, EducationLevel, ScholarshipCategory, RegistrationStatus,
MajlisParticipant, BehaviorReport
)
from app.decorators import role_required
from app.extensions import db
from app.utils.announcements import get_announcements_for_dashboard, mark_announcements_as_read

parent_bp = Blueprint('parent', __name__)


@parent_bp.route('/join-majlis', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.WALI_MURID)
def join_majlis():
    parent = current_user.parent_profile
    if not parent:
        flash("Profil Wali Murid tidak ditemukan.", "danger")
        return redirect(url_for('parent.dashboard'))

    participant_profile = current_user.majlis_profile

    if request.method == 'GET':
        return render_template('parent/join_majlis.html', parent=parent, participant_profile=participant_profile)

    participant_name = (request.form.get('participant_name') or '').strip()
    participant_phone = (request.form.get('participant_phone') or '').strip() or parent.phone
    participant_job = (request.form.get('job') or '').strip()
    participant_address = (request.form.get('address') or '').strip() or parent.address

    if not participant_name:
        flash("Nama peserta majelis wajib diisi.", "warning")
        return redirect(url_for('parent.join_majlis'))

    if not participant_phone:
        flash("Nomor WhatsApp peserta majelis wajib diisi.", "warning")
        return redirect(url_for('parent.join_majlis'))

    existing_candidate = StudentCandidate.query.filter(
        StudentCandidate.program_type == ProgramType.MAJLIS_TALIM,
        StudentCandidate.status.in_([RegistrationStatus.PENDING, RegistrationStatus.INTERVIEW, RegistrationStatus.ACCEPTED]),
        or_(
            StudentCandidate.parent_phone == participant_phone,
            StudentCandidate.personal_phone == participant_phone
        )
    ).order_by(StudentCandidate.created_at.desc()).first()

    if not existing_candidate:
        candidate = StudentCandidate(
            status=RegistrationStatus.PENDING,
            program_type=ProgramType.MAJLIS_TALIM,
            education_level=EducationLevel.NON_FORMAL,
            scholarship_category=ScholarshipCategory.NON_BEASISWA,
            full_name=participant_name,
            address=participant_address,
            parent_phone=participant_phone,
            personal_phone=participant_phone,
            personal_job=participant_job,
            father_name=parent.full_name,
            father_job=parent.job,
        )
        db.session.add(candidate)
        db.session.flush()
        year = datetime.now().year
        candidate.registration_no = f"MAJ{year}{candidate.id:05d}"

    if participant_profile:
        participant_profile.full_name = participant_name
        participant_profile.phone = participant_phone
        participant_profile.job = participant_job
        participant_profile.address = participant_address
    else:
        participant_profile = MajlisParticipant(
            user_id=current_user.id,
            full_name=participant_name,
            phone=participant_phone,
            job=participant_job,
            address=participant_address,
            join_date=datetime.now().date()
        )
        db.session.add(participant_profile)

    parent.is_majlis_participant = True
    if not parent.majlis_join_date:
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

    top_tab = (request.args.get('top_tab') or 'main').strip().lower()
    show_all_announcements = (request.args.get('ann') or '').strip().lower() == 'all'
    target_ids = [current_user.id]
    if student and student.user_id:
        target_ids.append(student.user_id)
    class_program = student.current_class.program_type.name if student and student.current_class and student.current_class.program_type else None
    announcements, unread_announcements_count = get_announcements_for_dashboard(
        current_user,
        class_ids=[student.current_class_id if student else None],
        user_ids=target_ids,
        program_types=[class_program] if class_program else [],
        show_all=show_all_announcements
    )
    if top_tab == 'ann':
        mark_announcements_as_read(current_user, announcements)
        unread_announcements_count = 0

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
    behavior_reports = BehaviorReport.query.filter_by(student_id=student.id).order_by(
        BehaviorReport.report_date.desc(),
        BehaviorReport.created_at.desc()
    ).limit(30).all()

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
                           top_tab=top_tab,
                           show_all_announcements=show_all_announcements,
                           unread_announcements_count=unread_announcements_count,
                           today_name=today_name,
                           todays_schedules=todays_schedules,
                           weekly_schedule=weekly_schedule,
                           grades=grades,
                           violations=violations,
                           behavior_reports=behavior_reports,
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

    participant_profile = current_user.majlis_profile

    if not parent.is_majlis_participant and not participant_profile:
        flash("Anda belum terdaftar sebagai peserta Majelis Ta'lim.", "info")
        return redirect(url_for('parent.dashboard'))

    if not participant_profile and parent.is_majlis_participant:
        participant_profile = MajlisParticipant(
            user_id=current_user.id,
            full_name=parent.full_name,
            phone=parent.phone,
            address=parent.address,
            job=parent.job,
            majlis_class_id=parent.majlis_class_id,
            join_date=parent.majlis_join_date or datetime.now().date()
        )
        db.session.add(participant_profile)
        db.session.commit()

    return redirect(url_for('main.majlis_dashboard'))


@parent_bp.route('/majelis-kegiatan')
@login_required
@role_required(UserRole.WALI_MURID)
def majlis_activities():
    return redirect(url_for('main.majlis_dashboard'))
