from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import or_
from app.models import (
    UserRole, TahfidzRecord, TahfidzSummary, TahfidzEvaluation, ProgramType,
    RecitationRecord, Schedule, Grade, Violation, AcademicYear, Invoice, PaymentStatus,
    ParticipantType, StudentCandidate, EducationLevel, ScholarshipCategory, RegistrationStatus,
    MajlisParticipant, BehaviorReport, Attendance, AttendanceStatus, ClassRoom,
    BoardingAttendance, BoardingActivitySchedule
)
from app.decorators import role_required
from app.services.formal_service import get_student_formal_classroom
from app.utils.tenant import resolve_tenant_id, scoped_classrooms_query
from app.utils.timezone import local_now, local_today
from app.extensions import db
from app.utils.announcements import get_announcements_for_dashboard, mark_announcements_as_read
from app.routes.teacher import _behavior_matrix_for_student

parent_bp = Blueprint('parent', __name__)


def _academic_year_date_bounds(academic_year):
    if academic_year is None:
        return None, None
    name = (academic_year.name or '').strip()
    semester = (academic_year.semester or '').strip().lower()
    parts = [item.strip() for item in name.split('/') if item.strip()]
    if not parts:
        return None, None
    try:
        start_year = int(parts[0])
        end_year = int(parts[1]) if len(parts) > 1 else start_year + 1
    except ValueError:
        return None, None

    start_date = datetime(start_year, 7, 1).date()
    end_date = datetime(end_year, 6, 30).date()
    if 'ganjil' in semester or semester.endswith('1'):
        return datetime(start_year, 7, 1).date(), datetime(start_year, 12, 31).date()
    if 'genap' in semester or semester.endswith('2'):
        return datetime(end_year, 1, 1).date(), datetime(end_year, 6, 30).date()
    return start_date, end_date


def _resolve_parent_report_period(period_type_raw, academic_year_id_raw, year_name_raw):
    period_type = (period_type_raw or 'SEMESTER').strip().upper()
    if period_type not in {'SEMESTER', 'YEAR'}:
        period_type = 'SEMESTER'

    all_years = (
        AcademicYear.query.filter(AcademicYear.is_deleted.is_(False))
        .order_by(AcademicYear.name.desc(), AcademicYear.id.desc())
        .all()
    )
    active_year = (
        AcademicYear.query.filter(
            AcademicYear.is_deleted.is_(False),
            AcademicYear.is_active.is_(True),
        )
        .order_by(AcademicYear.id.desc())
        .first()
    )

    selected_year = None
    selected_year_name = (year_name_raw or '').strip()
    selected_year_rows = []

    if period_type == 'SEMESTER':
        if academic_year_id_raw:
            selected_year = AcademicYear.query.filter(
                AcademicYear.is_deleted.is_(False),
                AcademicYear.id == academic_year_id_raw,
            ).first()
        if selected_year is None:
            selected_year = active_year or (all_years[0] if all_years else None)
        selected_year_name = selected_year.name if selected_year else ''
        year_ids = [selected_year.id] if selected_year else []
        start_date, end_date = _academic_year_date_bounds(selected_year) if selected_year else (None, None)
    else:
        if not selected_year_name:
            selected_year_name = active_year.name if active_year else ''
        if not selected_year_name and all_years:
            selected_year_name = all_years[0].name
        selected_year_rows = [row for row in all_years if (row.name or '') == selected_year_name]
        year_ids = [row.id for row in selected_year_rows]
        selected_year = selected_year_rows[0] if selected_year_rows else (active_year or None)

        bounds = [_academic_year_date_bounds(row) for row in selected_year_rows]
        valid_bounds = [(start, end) for start, end in bounds if start and end]
        if valid_bounds:
            start_date = min(item[0] for item in valid_bounds)
            end_date = max(item[1] for item in valid_bounds)
        else:
            start_date, end_date = None, None

    semester_options = [
        {
            'id': row.id,
            'label': f'{row.name or "-"} - {row.semester or "-"}',
            'name': row.name or '-',
            'semester': row.semester or '-',
        }
        for row in all_years
    ]
    seen_names = []
    for row in all_years:
        label = (row.name or '').strip()
        if label and label not in seen_names:
            seen_names.append(label)
    year_options = [{'key': label, 'label': label} for label in seen_names]

    return {
        'period_type': period_type,
        'academic_year_ids': year_ids,
        'selected_academic_year': selected_year,
        'selected_year_name': selected_year_name,
        'start_date': start_date,
        'end_date': end_date,
        'period_options': {
            'type_options': [
                {'key': 'SEMESTER', 'label': 'Per Semester'},
                {'key': 'YEAR', 'label': 'Per Tahun Ajaran'},
            ],
            'semester_options': semester_options,
            'year_options': year_options,
        },
    }


@parent_bp.route('/join-majlis', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.WALI_MURID)
def join_majlis():
    parent = current_user.parent_profile
    if not parent:
        flash("Profil Wali Murid tidak ditemukan.", "danger")
        return redirect(url_for('parent.dashboard'))
    tenant_id = resolve_tenant_id(current_user, fallback_default=False)
    if tenant_id is None:
        flash("Tenant akun tidak valid. Hubungi admin.", "danger")
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
        StudentCandidate.tenant_id == tenant_id,
        StudentCandidate.program_type == ProgramType.MAJLIS_TALIM,
        StudentCandidate.status.in_([RegistrationStatus.PENDING, RegistrationStatus.INTERVIEW, RegistrationStatus.ACCEPTED]),
        or_(
            StudentCandidate.parent_phone == participant_phone,
            StudentCandidate.personal_phone == participant_phone
        )
    ).order_by(StudentCandidate.created_at.desc()).first()

    if not existing_candidate:
        candidate = StudentCandidate(
            tenant_id=tenant_id,
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
        year = local_now().year
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
            join_date=local_today()
        )
        db.session.add(participant_profile)

    parent.is_majlis_participant = True
    if not parent.majlis_join_date:
        parent.majlis_join_date = local_today()

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
        flash("Profil Wali Murid tidak ditemukan atau belum lengkap. Hubungi Admin.", "danger")
        return render_template('parent/empty_state.html')

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

    selected_period_type = (request.args.get('period_type') or 'SEMESTER').strip().upper()
    selected_year_name = (request.args.get('year_name') or '').strip()
    selected_period_academic_year_id = request.args.get('academic_year_id', type=int)
    period_scope = _resolve_parent_report_period(
        period_type_raw=selected_period_type,
        academic_year_id_raw=selected_period_academic_year_id,
        year_name_raw=selected_year_name,
    )
    selected_period_type = period_scope['period_type']
    selected_academic_year = period_scope['selected_academic_year']
    selected_year_name = period_scope['selected_year_name']
    selected_year_ids = period_scope['academic_year_ids'] or []
    behavior_start_date = period_scope['start_date']
    behavior_end_date = period_scope['end_date']

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
    tenant_id = resolve_tenant_id(current_user, fallback_default=False)
    formal_class = get_student_formal_classroom(student)
    active_class_id = formal_class.id if formal_class else student.current_class_id
    if tenant_id and active_class_id:
        active_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == active_class_id).first()
        if active_class is None:
            active_class_id = None
        elif formal_class is None:
            formal_class = active_class

    class_program = formal_class.program_type.name if formal_class and formal_class.program_type else None
    announcements, unread_announcements_count = get_announcements_for_dashboard(
        current_user,
        class_ids=[active_class_id] if active_class_id else [],
        user_ids=target_ids,
        program_types=[class_program] if class_program else [],
        show_all=show_all_announcements
    )
    if top_tab == 'ann':
        mark_announcements_as_read(current_user, announcements)
        unread_announcements_count = 0

    today_name_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    today_name = today_name_map[local_now().weekday()]

    todays_schedules = []
    if active_class_id:
        todays_schedules = Schedule.query.filter_by(
            class_id=active_class_id, day=today_name, is_deleted=False
        ).order_by(Schedule.start_time).all()

    weekly_schedule = {day: [] for day in ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu']}
    if active_class_id:
        all_schedules = Schedule.query.filter_by(class_id=active_class_id, is_deleted=False).all()
        for sch in all_schedules:
            if sch.day in weekly_schedule:
                weekly_schedule[sch.day].append(sch)
        for day in weekly_schedule:
            weekly_schedule[day].sort(key=lambda x: x.start_time)

    active_year = selected_academic_year
    grade_query = Grade.query.filter(Grade.student_id == student.id)
    if selected_year_ids:
        grade_query = grade_query.filter(Grade.academic_year_id.in_(selected_year_ids))
    else:
        grade_query = grade_query.filter(False)
    grades = grade_query.order_by(Grade.subject_id, Grade.type).all()

    violations = Violation.query.filter_by(student_id=student.id).order_by(Violation.date.desc()).all()
    total_points = sum(v.points for v in violations)
    behavior_reports = BehaviorReport.query.filter_by(student_id=student.id).order_by(
        BehaviorReport.report_date.desc(),
        BehaviorReport.created_at.desc()
    ).limit(30).all()
    behavior_reports = [row for row in behavior_reports if row.indicator_key]
    if behavior_start_date:
        behavior_reports = [row for row in behavior_reports if row.report_date and row.report_date >= behavior_start_date]
    if behavior_end_date:
        behavior_reports = [row for row in behavior_reports if row.report_date and row.report_date <= behavior_end_date]

    behavior_academic_year_ids = selected_year_ids
    behavior_matrix = _behavior_matrix_for_student(
        student_id=student.id,
        class_id=active_class_id or 0,
        academic_year_ids=behavior_academic_year_ids,
        start_date=behavior_start_date,
        end_date=behavior_end_date,
        history_limit=120
    )
    latest_behavior_note = '-'
    for history_row in behavior_matrix.get('history_rows') or []:
        note = (history_row.get('notes') or '').strip()
        if note and note != '-':
            latest_behavior_note = note
            break

    attendances = Attendance.query.filter_by(
        student_id=student.id,
        participant_type=ParticipantType.STUDENT
    )
    if selected_year_ids:
        attendances = attendances.filter(Attendance.academic_year_id.in_(selected_year_ids))
    else:
        attendances = attendances.filter(False)
    attendances = attendances.order_by(Attendance.date.desc(), Attendance.created_at.desc()).limit(120).all()

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

    is_boarding_student = bool(student.boarding_dormitory_id)
    boarding_attendances = []
    boarding_recap = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0}
    if is_boarding_student:
        today = local_today()
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

        for record in boarding_attendances:
            if record.status == AttendanceStatus.HADIR:
                boarding_recap['hadir'] += 1
            elif record.status == AttendanceStatus.SAKIT:
                boarding_recap['sakit'] += 1
            elif record.status == AttendanceStatus.IZIN:
                boarding_recap['izin'] += 1
            elif record.status == AttendanceStatus.ALPA:
                boarding_recap['alpa'] += 1

    invoices = Invoice.query.filter_by(student_id=student.id, is_deleted=False).order_by(Invoice.created_at.desc()).all()
    total_tagihan = sum(inv.total_amount - inv.paid_amount for inv in invoices if inv.status != PaymentStatus.PAID)

    return render_template('parent/dashboard.html',
                           parent=parent,
                           children=children,
                           student=student,
                           formal_class=formal_class,
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
                           attendances=attendances,
                           attendance_recap=attendance_recap,
                           is_boarding_student=is_boarding_student,
                           boarding_attendances=boarding_attendances,
                           boarding_recap=boarding_recap,
                           violations=violations,
                           behavior_reports=behavior_reports,
                           behavior_matrix=behavior_matrix,
                           latest_behavior_note=latest_behavior_note,
                           selected_period_type=selected_period_type,
                           selected_academic_year=selected_academic_year,
                           selected_year_name=selected_year_name,
                           period_options=period_scope['period_options'],
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
            join_date=parent.majlis_join_date or local_today()
        )
        db.session.add(participant_profile)
        db.session.commit()

    return redirect(url_for('main.majlis_dashboard'))


@parent_bp.route('/majelis-kegiatan')
@login_required
@role_required(UserRole.WALI_MURID)
def majlis_activities():
    return redirect(url_for('main.majlis_dashboard'))

