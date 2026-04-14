from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, timedelta
from collections import defaultdict
import json
from app.models import (
    Teacher, Student, ClassRoom, TahfidzRecord, TahfidzSummary, RecitationRecord,
    TahfidzEvaluation, TahfidzType, RecitationSource, ParticipantType, Grade,
    EvaluationPeriod,
    GradeType, Subject, MajlisSubject, Attendance, AttendanceStatus, AcademicYear, Schedule, db, UserRole, MajlisParticipant,
    BehaviorReport, BehaviorReportType, Announcement, BoardingAttendance, ProgramType
)
from app.decorators import role_required
from app.services.rumah_quran_service import is_rumah_quran_classroom, list_rumah_quran_students_for_class
from app.services.bahasa_service import is_bahasa_classroom, list_bahasa_students_for_class
from app.services.formal_service import is_formal_classroom, list_formal_students_for_class
from app.services.staff_assignment_service import (
    list_teacher_homeroom_classes_from_assignments,
    list_teacher_subject_classes_from_assignments,
)
from app.utils.announcements import get_announcements_for_dashboard, mark_announcements_as_read
from app.utils.timezone import local_day_bounds_utc_naive, local_today, utc_now_naive

teacher_bp = Blueprint('teacher', __name__)


def _dedupe_classes(classes):
    deduped = {}
    for class_room in classes or []:
        if class_room and class_room.id not in deduped:
            deduped[class_room.id] = class_room
    return list(deduped.values())


def _get_teacher_homeroom_classes(teacher):
    classes = list_teacher_homeroom_classes_from_assignments(teacher)
    if classes:
        return sorted(_dedupe_classes(classes), key=lambda item: item.name or "")
    return (
        ClassRoom.query.filter_by(homeroom_teacher_id=teacher.id, is_deleted=False)
        .order_by(ClassRoom.name.asc())
        .all()
    )


def _class_program_group(class_room):
    if not class_room or not class_room.program_type:
        return 'formal'
    if class_room.program_type == ProgramType.BAHASA:
        return 'bahasa'
    if class_room.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ):
        return 'rumah_quran'
    if class_room.program_type == ProgramType.MAJLIS_TALIM:
        return 'majlis'
    return 'formal'


def _assignment_group_catalog():
    return {
        'formal': {
            'title': 'Sekolah Formal',
            'badge': 'Formal',
            'icon': 'fas fa-school',
            'description': 'Wali kelas dan pengampu mapel sekolah formal.',
        },
        'rumah_quran': {
            'title': "Rumah Qur'an",
            'badge': 'Rumah Qur\'an',
            'icon': 'fas fa-quran',
            'description': 'Halaqah reguler dan takhosus tahfidz.',
        },
        'bahasa': {
            'title': 'Program Bahasa',
            'badge': 'Bahasa',
            'icon': 'fas fa-language',
            'description': 'Kelas bahasa tambahan lintas program.',
        },
        'majlis': {
            'title': "Majlis Ta'lim",
            'badge': 'Majlis',
            'icon': 'fas fa-users',
            'description': 'Kelas pembinaan majlis ta\'lim.',
        },
    }


def _collect_teacher_assignment_summary(teacher):
    grouped_assignments = {}
    catalog = _assignment_group_catalog()
    for key, meta in catalog.items():
        grouped_assignments[key] = {
            'key': key,
            'title': meta['title'],
            'badge': meta['badge'],
            'icon': meta['icon'],
            'description': meta['description'],
            'homeroom_classes': [],
            'subject_assignments': [],
        }

    for class_room in _dedupe_classes(_get_teacher_homeroom_classes(teacher)):
        group_key = _class_program_group(class_room)
        grouped_assignments[group_key]['homeroom_classes'].append(class_room)

    teaching_assignments = []
    seen_assignments = set()
    all_teacher_schedules = Schedule.query.filter_by(teacher_id=teacher.id, is_deleted=False).all()
    for sch in all_teacher_schedules:
        if not sch.class_room:
            continue
        if not sch.subject and not sch.majlis_subject:
            continue

        assignment_type = 'SUBJECT' if sch.subject_id else 'MAJLIS_SUBJECT'
        assignment_id = sch.subject_id if sch.subject_id else sch.majlis_subject_id
        assignment_name = sch.subject.name if sch.subject else sch.majlis_subject.name
        key = (sch.class_id, assignment_type, assignment_id)
        if key in seen_assignments:
            continue
        seen_assignments.add(key)
        assignment_item = {
            'class_id': sch.class_id,
            'class_name': sch.class_room.name,
            'subject_id': sch.subject_id,
            'majlis_subject_id': sch.majlis_subject_id,
            'assignment_name': assignment_name,
        }
        teaching_assignments.append((
            sch.class_id,
            sch.class_room.name,
            sch.subject_id,
            sch.majlis_subject_id,
            assignment_name
        ))
        group_key = _class_program_group(sch.class_room)
        grouped_assignments[group_key]['subject_assignments'].append(assignment_item)

    assignment_groups = [
        group for group in grouped_assignments.values()
        if group['homeroom_classes'] or group['subject_assignments']
    ]
    return assignment_groups, teaching_assignments


def build_teacher_sidebar_groups(teacher):
    if not teacher:
        return []

    assignment_groups, _ = _collect_teacher_assignment_summary(teacher)
    group_items = {
        'formal': [
            {'endpoint': 'teacher.homeroom_students', 'label': 'Data Peserta Kelas', 'icon': 'fas fa-users'},
            {'endpoint': 'teacher.input_grades', 'label': 'Input Nilai', 'icon': 'fas fa-pen-alt'},
            {'endpoint': 'teacher.input_attendance', 'label': 'Input Absensi', 'icon': 'fas fa-clipboard-check'},
            {'endpoint': 'teacher.input_behavior_report', 'label': 'Laporan Perilaku', 'icon': 'fas fa-user-shield'},
            {'endpoint': 'teacher.class_announcements', 'label': 'Pengumuman Kelas', 'icon': 'fas fa-bullhorn'},
        ],
        'rumah_quran': [
            {'endpoint': 'teacher.input_tahfidz', 'label': 'Input Tahfidz', 'icon': 'fas fa-quran'},
            {'endpoint': 'teacher.input_recitation', 'label': 'Input Bacaan', 'icon': 'fas fa-book-reader'},
            {'endpoint': 'teacher.input_tahfidz_evaluation', 'label': 'Evaluasi Tahfidz', 'icon': 'fas fa-clipboard-check'},
            {'endpoint': 'teacher.input_attendance', 'label': 'Input Absensi', 'icon': 'fas fa-calendar-check'},
            {'endpoint': 'teacher.input_behavior_report', 'label': 'Laporan Perilaku', 'icon': 'fas fa-user-shield'},
            {'endpoint': 'teacher.class_announcements', 'label': 'Pengumuman Kelas', 'icon': 'fas fa-bullhorn'},
        ],
        'bahasa': [
            {'endpoint': 'teacher.input_attendance', 'label': 'Input Absensi', 'icon': 'fas fa-calendar-check'},
            {'endpoint': 'teacher.input_behavior_report', 'label': 'Laporan Perilaku', 'icon': 'fas fa-user-shield'},
            {'endpoint': 'teacher.class_announcements', 'label': 'Pengumuman Kelas', 'icon': 'fas fa-bullhorn'},
        ],
        'majlis': [
            {'endpoint': 'teacher.input_tahfidz', 'label': 'Input Tahfidz', 'icon': 'fas fa-quran'},
            {'endpoint': 'teacher.input_recitation', 'label': 'Input Bacaan', 'icon': 'fas fa-book-reader'},
            {'endpoint': 'teacher.input_tahfidz_evaluation', 'label': 'Evaluasi Tahfidz', 'icon': 'fas fa-clipboard-check'},
            {'endpoint': 'teacher.input_attendance', 'label': 'Input Absensi', 'icon': 'fas fa-calendar-check'},
            {'endpoint': 'teacher.input_behavior_report', 'label': 'Laporan Perilaku', 'icon': 'fas fa-user-shield'},
            {'endpoint': 'teacher.class_announcements', 'label': 'Pengumuman Kelas', 'icon': 'fas fa-bullhorn'},
        ],
    }

    sidebar_groups = []
    for group in assignment_groups:
        sidebar_groups.append({
            'key': group['key'],
            'title': group['title'],
            'icon': group['icon'],
            'description': group['description'],
            'class_count': len(group['homeroom_classes']),
            'subject_count': len(group['subject_assignments']),
            'items': group_items.get(group['key'], []),
        })
    return sidebar_groups


def _get_teacher_classes(teacher):
    """Helper: Ambil semua kelas yang diajar atau dibina guru ini."""
    classes_by_id = {}

    # 1. Kelas sebagai Wali Kelas/Pembimbing utama
    for homeroom_class in _get_teacher_homeroom_classes(teacher):
        classes_by_id[homeroom_class.id] = homeroom_class

    for assigned_class in list_teacher_subject_classes_from_assignments(teacher):
        classes_by_id[assigned_class.id] = assigned_class
    
    # 2. Kelas dari jadwal mengajar guru
    teaching_class_ids = db.session.query(Schedule.class_id).filter(
        Schedule.teacher_id == teacher.id,
        Schedule.is_deleted == False,
        Schedule.class_id.isnot(None)
    ).distinct().all()
    for row in teaching_class_ids:
        class_id = row[0]
        target_class = ClassRoom.query.get(class_id)
        if target_class and not target_class.is_deleted:
            classes_by_id[target_class.id] = target_class
    
    return list(classes_by_id.values())


def _is_tahfidz_related_schedule(schedule):
    labels = []
    if schedule.subject and schedule.subject.name:
        labels.append(schedule.subject.name)
    if schedule.majlis_subject and schedule.majlis_subject.name:
        labels.append(schedule.majlis_subject.name)
    haystack = ' '.join(labels).lower()
    keywords = [
        'tahfidz',
        'tahsin',
        'tajwid',
        'quran',
        "qur'an",
        'al-qur',
        'tilawah',
        'bacaan',
    ]
    return any(keyword in haystack for keyword in keywords)


def _get_teacher_tahfidz_classes(teacher):
    classes = []
    seen_ids = set()

    # Kelas non-formal yang memang diampu guru sebagai wali/homeroom tetap
    # harus bisa dioperasikan meski jadwalnya belum dibuat.
    for homeroom_class in _get_teacher_homeroom_classes(teacher):
        if (
            is_rumah_quran_classroom(homeroom_class)
            or is_bahasa_classroom(homeroom_class)
        ):
            seen_ids.add(homeroom_class.id)
            classes.append(homeroom_class)

    schedules = Schedule.query.filter_by(
        teacher_id=teacher.id,
        is_deleted=False,
    ).order_by(Schedule.day.asc(), Schedule.start_time.asc()).all()
    for schedule in schedules:
        if not schedule.class_room or schedule.class_room.is_deleted:
            continue
        if not _is_tahfidz_related_schedule(schedule):
            continue
        if schedule.class_id in seen_ids:
            continue
        seen_ids.add(schedule.class_id)
        classes.append(schedule.class_room)
    return classes


def _get_class_participants(class_id):
    class_room = ClassRoom.query.filter_by(id=class_id, is_deleted=False).first()
    if is_rumah_quran_classroom(class_room):
        students = list_rumah_quran_students_for_class(class_id)
    elif is_bahasa_classroom(class_room):
        students = list_bahasa_students_for_class(class_id)
    elif is_formal_classroom(class_room):
        students = list_formal_students_for_class(class_id)
    else:
        students = Student.query.filter_by(
            current_class_id=class_id,
            is_deleted=False
        ).order_by(Student.full_name).all()
    majlis_participants = MajlisParticipant.query.filter_by(
        majlis_class_id=class_id,
        is_deleted=False
    ).order_by(MajlisParticipant.full_name).all()
    return students, majlis_participants


def _student_belongs_to_class(student, class_id):
    if not student or not class_id:
        return False
    students, _ = _get_class_participants(class_id)
    return any(item.id == student.id for item in students)


def _count_teacher_students(classes):
    student_ids = set()
    for class_room in classes:
        students, _ = _get_class_participants(class_room.id)
        for student in students:
            student_ids.add(student.id)
    return len(student_ids)


def _parse_participant_key(participant_key):
    if not participant_key:
        return None, None

    if '-' in participant_key:
        prefix, raw_id = participant_key.split('-', 1)
        try:
            participant_id = int(raw_id)
        except ValueError:
            return None, None
        if prefix == 'S':
            return ParticipantType.STUDENT, participant_id
        if prefix == 'M':
            return ParticipantType.EXTERNAL_MAJLIS, participant_id
        return None, None

    try:
        return ParticipantType.STUDENT, int(participant_key)
    except (TypeError, ValueError):
        return None, None


def _evaluation_period_labels(period_type):
    mapping = {
        'BULANAN': [
            'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
            'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
        ],
        'TENGAH_SEMESTER': [
            'Tengah Semester 1',
            'Tengah Semester 2',
            'Tengah Semester 3',
            'Tengah Semester 4',
        ],
        'SEMESTER': ['Semester 1', 'Semester 2'],
    }
    return mapping.get((period_type or '').strip().upper(), [])


def _build_participant_rows(students, majlis_participants):
    rows = []
    for student in students:
        rows.append({
            'key': f'S-{student.id}',
            'participant_type': ParticipantType.STUDENT,
            'student_id': student.id,
            'majlis_participant_id': None,
            'display_name': student.full_name,
            'identifier': student.nis or '-',
            'identifier_label': 'NIS'
        })
    for participant in majlis_participants:
        rows.append({
            'key': f'M-{participant.id}',
            'participant_type': ParticipantType.EXTERNAL_MAJLIS,
            'student_id': None,
            'majlis_participant_id': participant.id,
            'display_name': participant.full_name,
            'identifier': participant.phone or '-',
            'identifier_label': 'Kontak'
        })
    return rows


def _calculate_weighted_final(type_averages):
    """Hitung nilai akhir berbobot dari rata-rata per tipe nilai."""
    weights = {'TUGAS': 0.3, 'UH': 0.2, 'UTS': 0.25, 'UAS': 0.25}
    total_weighted = 0
    total_weight = 0
    for type_name, avg_score in type_averages.items():
        weight = weights.get(type_name, 0)
        total_weighted += avg_score * weight
        total_weight += weight
    return round(total_weighted / total_weight, 2) if total_weight > 0 else 0


def _resolve_selected_participant(participants, participant_key):
    if not participant_key:
        return None
    return next((p for p in participants if p['key'] == participant_key), None)

@teacher_bp.route('/dashboard')
@login_required
@role_required(UserRole.GURU)
def dashboard():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()

    my_classes = _get_teacher_classes(teacher)
    homeroom_classes = _get_teacher_homeroom_classes(teacher)
    class_ids = [c.id for c in my_classes]
    nonformal_classes = [
        c for c in my_classes
        if c and c.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ, ProgramType.BAHASA, ProgramType.MAJLIS_TALIM)
    ]
    bahasa_classes = [c for c in nonformal_classes if c.program_type == ProgramType.BAHASA]
    rumah_quran_classes = [
        c for c in nonformal_classes
        if c.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ)
    ]

    total_students = _count_teacher_students(my_classes) if class_ids else 0
    homeroom_class = homeroom_classes[0] if homeroom_classes else None
    assignment_groups, teaching_assignments = _collect_teacher_assignment_summary(teacher)

    today = local_today()
    today_name_map = {0: 'Senin', 1: 'Selasa', 2: 'Rabu', 3: 'Kamis', 4: 'Jumat', 5: 'Sabtu', 6: 'Minggu'}
    today_name = today_name_map[today.weekday()]

    todays_schedules = Schedule.query.filter_by(
        teacher_id=teacher.id,
        day=today_name,
        is_deleted=False
    ).order_by(Schedule.start_time).all()

    all_teacher_schedules = Schedule.query.filter_by(teacher_id=teacher.id, is_deleted=False).all()
    for sch in all_teacher_schedules:
        if not sch.class_room:
            continue
        if not sch.subject and not sch.majlis_subject:
            continue

    top_tab = (request.args.get('top_tab') or 'main').strip().lower()
    main_tab = (request.args.get('main_tab') or 'ringkas').strip().lower()
    allowed_main_tabs = {'ringkas', 'input', 'riwayat', 'perwalian'}
    if main_tab not in allowed_main_tabs:
        main_tab = 'ringkas'
    show_all_announcements = (request.args.get('ann') or '').strip().lower() == 'all'

    start_utc, end_utc = local_day_bounds_utc_naive(today)

    today_tahfidz = TahfidzRecord.query.filter(
        TahfidzRecord.teacher_id == teacher.id,
        TahfidzRecord.date >= start_utc,
        TahfidzRecord.date < end_utc
    ).count()

    today_recitation = RecitationRecord.query.filter(
        RecitationRecord.teacher_id == teacher.id,
        RecitationRecord.date >= start_utc,
        RecitationRecord.date < end_utc
    ).count()

    recent_tahfidz = TahfidzRecord.query.filter_by(teacher_id=teacher.id)        .order_by(TahfidzRecord.date.desc()).limit(5).all()

    recent_recitation = RecitationRecord.query.filter_by(teacher_id=teacher.id)        .order_by(RecitationRecord.date.desc()).limit(5).all()
    boarding_student_ids = []
    if class_ids:
        boarding_student_ids = [row[0] for row in db.session.query(Student.id).filter(
            Student.current_class_id.in_(class_ids),
            Student.boarding_dormitory_id.isnot(None),
            Student.is_deleted == False
        ).all()]

    boarding_attendance_stats = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0, 'belum_input': 0}
    if boarding_student_ids:
        records = BoardingAttendance.query.filter(
            BoardingAttendance.date == today,
            BoardingAttendance.student_id.in_(boarding_student_ids)
        ).all()

        seen_students = set()
        for record in records:
            seen_students.add(record.student_id)
            if record.status == AttendanceStatus.HADIR:
                boarding_attendance_stats['hadir'] += 1
            elif record.status == AttendanceStatus.SAKIT:
                boarding_attendance_stats['sakit'] += 1
            elif record.status == AttendanceStatus.IZIN:
                boarding_attendance_stats['izin'] += 1
            elif record.status == AttendanceStatus.ALPA:
                boarding_attendance_stats['alpa'] += 1
        boarding_attendance_stats['belum_input'] = max(0, len(set(boarding_student_ids)) - len(seen_students))

    class_programs = []
    for c in my_classes:
        if c and c.program_type:
            class_programs.append(c.program_type.name)
    announcements, unread_announcements_count = get_announcements_for_dashboard(
        current_user,
        class_ids=class_ids,
        user_ids=[current_user.id],
        program_types=class_programs,
        show_all=show_all_announcements
    )
    if top_tab == 'ann':
        mark_announcements_as_read(current_user, announcements)
        unread_announcements_count = 0

    return render_template('teacher/dashboard.html',
                         teacher=teacher,
                         my_classes=my_classes,
                         homeroom_classes=homeroom_classes,
                         nonformal_classes=nonformal_classes,
                         bahasa_classes=bahasa_classes,
                         rumah_quran_classes=rumah_quran_classes,
                         assignment_groups=assignment_groups,
                         main_tab=main_tab,
                         total_students=total_students,
                         today_tahfidz=today_tahfidz,
                         today_recitation=today_recitation,
                         recent_tahfidz=recent_tahfidz,
                         recent_recitation=recent_recitation,
                         announcements=announcements,
                         top_tab=top_tab,
                         show_all_announcements=show_all_announcements,
                         unread_announcements_count=unread_announcements_count,
                         todays_schedules=todays_schedules,
                         homeroom_class=homeroom_class,
                         teaching_assignments=teaching_assignments,
                         boarding_attendance_stats=boarding_attendance_stats)


@teacher_bp.route('/input-nilai', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_grades():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_majlis_subject_id = request.args.get('majlis_subject_id', type=int)
    students = []
    majlis_participants = []
    participants = []
    target_class = None
    subject = Subject.query.get(selected_subject_id) if selected_subject_id else None
    majlis_subject = MajlisSubject.query.get(selected_majlis_subject_id) if selected_majlis_subject_id else None

    if selected_class_id:
        target_class = ClassRoom.query.get(selected_class_id)
        if target_class in my_classes:
            students, majlis_participants = _get_class_participants(selected_class_id)
            participants = _build_participant_rows(students, majlis_participants)
        else:
            flash('Anda tidak memiliki akses ke kelas tersebut.', 'danger')

    active_year = AcademicYear.query.filter_by(is_active=True).first()
    existing_grades = {}
    if active_year and participants and (selected_subject_id or selected_majlis_subject_id):
        student_ids = [p['student_id'] for p in participants if p['participant_type'] == ParticipantType.STUDENT]
        majlis_ids = [p['majlis_participant_id'] for p in participants if p['participant_type'] == ParticipantType.EXTERNAL_MAJLIS]
        grade_query = Grade.query.filter_by(academic_year_id=active_year.id, teacher_id=teacher.id)

        if selected_subject_id:
            grade_query = grade_query.filter(Grade.subject_id == selected_subject_id)
        else:
            grade_query = grade_query.filter(Grade.majlis_subject_id == selected_majlis_subject_id)

        participant_filters = []
        if student_ids:
            participant_filters.append(
                db.and_(Grade.participant_type == ParticipantType.STUDENT, Grade.student_id.in_(student_ids))
            )
        if majlis_ids:
            participant_filters.append(
                db.and_(Grade.participant_type == ParticipantType.EXTERNAL_MAJLIS, Grade.majlis_participant_id.in_(majlis_ids))
            )
        if participant_filters:
            grade_query = grade_query.filter(db.or_(*participant_filters))
        else:
            grade_query = grade_query.filter(False)

        grouped_scores = {}
        latest_scores = {}
        grade_rows = grade_query.order_by(Grade.created_at.asc(), Grade.id.asc()).all()
        for g in grade_rows:
            if g.participant_type == ParticipantType.EXTERNAL_MAJLIS and g.majlis_participant_id:
                key = f'M-{g.majlis_participant_id}'
            elif g.student_id:
                key = f'S-{g.student_id}'
            else:
                continue
            grouped_scores.setdefault(key, {}).setdefault(g.type.name, []).append(g.score)
            latest_scores.setdefault(key, {})[g.type.name] = g.score

        for participant_key, type_map in grouped_scores.items():
            for type_name, scores in type_map.items():
                existing_grades.setdefault(participant_key, {})[type_name] = {
                    'latest': latest_scores[participant_key][type_name],
                    'avg': round(sum(scores) / len(scores), 2),
                    'count': len(scores)
                }
    
    if request.method == 'POST':
        if not active_year:
            flash('Tahun ajaran aktif belum diatur.', 'warning')
            return redirect(url_for(
                'teacher.input_grades',
                class_id=selected_class_id,
                subject_id=selected_subject_id,
                majlis_subject_id=selected_majlis_subject_id
            ))

        grade_type = request.form.get('grade_type')
        notes = request.form.get('notes', '')
        subject_id = selected_subject_id or request.form.get('subject_id', type=int)
        majlis_subject_id = selected_majlis_subject_id or request.form.get('majlis_subject_id', type=int)
        if grade_type not in [t.name for t in GradeType]:
            flash('Tipe nilai tidak valid.', 'warning')
            return redirect(url_for(
                'teacher.input_grades',
                class_id=selected_class_id,
                subject_id=selected_subject_id,
                majlis_subject_id=selected_majlis_subject_id
            ))
        if not subject_id and not majlis_subject_id:
            flash('Mata pelajaran belum dipilih.', 'warning')
            return redirect(url_for(
                'teacher.input_grades',
                class_id=selected_class_id,
                subject_id=selected_subject_id,
                majlis_subject_id=selected_majlis_subject_id
            ))
        if not participants:
            flash('Belum ada peserta pada kelas ini.', 'warning')
            return redirect(url_for(
                'teacher.input_grades',
                class_id=selected_class_id,
                subject_id=selected_subject_id,
                majlis_subject_id=selected_majlis_subject_id
            ))
        
        success_count = 0
        for participant in participants:
            score = request.form.get(f"score_{participant['key']}")
            if not score or not score.strip():
                continue
            try:
                score_float = float(score)
            except ValueError:
                continue

            db.session.add(Grade(
                student_id=participant['student_id'],
                majlis_participant_id=participant['majlis_participant_id'],
                participant_type=participant['participant_type'],
                subject_id=subject_id,
                majlis_subject_id=majlis_subject_id,
                academic_year_id=active_year.id,
                teacher_id=teacher.id,
                type=GradeType[grade_type],
                score=score_float,
                notes=notes
            ))
            success_count += 1

        if success_count:
            db.session.commit()
            flash(f'Berhasil menyimpan {success_count} nilai!', 'success')
        else:
            flash('Tidak ada nilai yang berhasil disimpan.', 'warning')

        return redirect(url_for(
            'teacher.input_grades',
            class_id=selected_class_id,
            subject_id=selected_subject_id,
            majlis_subject_id=selected_majlis_subject_id
        ))
    
    return render_template('teacher/input_grades.html',
                           my_classes=my_classes,
                           participants=participants,
                           target_class=target_class,
                           subject=subject,
                           majlis_subject=majlis_subject,
                           existing_grades=existing_grades)


@teacher_bp.route('/riwayat-nilai')
@login_required
@role_required(UserRole.GURU)
def grade_history():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    selected_participant_key = (request.args.get('participant') or '').strip()

    selected_class = None
    participants = []
    selected_participant = None
    academic_grade_rows = []
    tahfidz_records = []
    recitation_records = []
    tahfidz_evaluations = []
    academic_summary_rows = []

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class not in my_classes:
            flash('Anda tidak memiliki akses ke kelas tersebut.', 'danger')
            return redirect(url_for('teacher.grade_history'))

        students, majlis_participants = _get_class_participants(selected_class_id)
        participants = _build_participant_rows(students, majlis_participants)
        selected_participant = _resolve_selected_participant(participants, selected_participant_key)

        if selected_participant:
            base_grade_query = Grade.query.filter(
                Grade.teacher_id == teacher.id
            )
            base_tahfidz_query = TahfidzRecord.query.filter(
                TahfidzRecord.teacher_id == teacher.id
            )
            base_recitation_query = RecitationRecord.query.filter(
                RecitationRecord.teacher_id == teacher.id
            )
            base_evaluation_query = TahfidzEvaluation.query.filter(
                TahfidzEvaluation.teacher_id == teacher.id
            )

            if selected_participant['participant_type'] == ParticipantType.STUDENT:
                participant_id = selected_participant['student_id']
                base_grade_query = base_grade_query.filter(
                    Grade.participant_type == ParticipantType.STUDENT,
                    Grade.student_id == participant_id
                )
                base_tahfidz_query = base_tahfidz_query.filter(
                    TahfidzRecord.participant_type == ParticipantType.STUDENT,
                    TahfidzRecord.student_id == participant_id
                )
                base_recitation_query = base_recitation_query.filter(
                    RecitationRecord.participant_type == ParticipantType.STUDENT,
                    RecitationRecord.student_id == participant_id
                )
                base_evaluation_query = base_evaluation_query.filter(
                    TahfidzEvaluation.participant_type == ParticipantType.STUDENT,
                    TahfidzEvaluation.student_id == participant_id
                )
            else:
                participant_id = selected_participant['majlis_participant_id']
                base_grade_query = base_grade_query.filter(
                    Grade.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                    Grade.majlis_participant_id == participant_id
                )
                base_tahfidz_query = base_tahfidz_query.filter(
                    TahfidzRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                    TahfidzRecord.majlis_participant_id == participant_id
                )
                base_recitation_query = base_recitation_query.filter(
                    RecitationRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                    RecitationRecord.majlis_participant_id == participant_id
                )
                base_evaluation_query = base_evaluation_query.filter(
                    TahfidzEvaluation.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                    TahfidzEvaluation.majlis_participant_id == participant_id
                )

            academic_grade_rows = base_grade_query.order_by(Grade.created_at.desc(), Grade.id.desc()).all()
            tahfidz_records = base_tahfidz_query.order_by(TahfidzRecord.date.desc(), TahfidzRecord.id.desc()).all()
            recitation_records = base_recitation_query.order_by(RecitationRecord.date.desc(), RecitationRecord.id.desc()).all()
            tahfidz_evaluations = base_evaluation_query.order_by(TahfidzEvaluation.date.desc(), TahfidzEvaluation.id.desc()).all()

            grouped = defaultdict(lambda: defaultdict(list))
            for row in academic_grade_rows:
                subject_name = row.subject.name if row.subject else (row.majlis_subject.name if row.majlis_subject else '-')
                grouped[subject_name][row.type.name].append(row.score)

            for subject_name, subject_data in grouped.items():
                type_averages = {}
                type_counts = {}
                for grade_type in ['TUGAS', 'UH', 'UTS', 'UAS']:
                    scores = subject_data.get(grade_type, [])
                    if scores:
                        type_averages[grade_type] = round(sum(scores) / len(scores), 2)
                        type_counts[grade_type] = len(scores)
                academic_summary_rows.append({
                    'subject_name': subject_name,
                    'type_averages': type_averages,
                    'type_counts': type_counts,
                    'final_score': _calculate_weighted_final(type_averages)
                })

            academic_summary_rows.sort(key=lambda row: row['subject_name'])

    return render_template(
        'teacher/grade_history.html',
        my_classes=my_classes,
        selected_class=selected_class,
        selected_participant_key=selected_participant_key,
        selected_participant=selected_participant,
        participants=participants,
        academic_grade_rows=academic_grade_rows,
        academic_summary_rows=academic_summary_rows,
        tahfidz_records=tahfidz_records,
        recitation_records=recitation_records,
        tahfidz_evaluations=tahfidz_evaluations
    )


@teacher_bp.route('/riwayat-absensi')
@login_required
@role_required(UserRole.GURU)
def attendance_history():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    selected_participant_key = (request.args.get('participant') or '').strip()

    selected_class = None
    participants = []
    selected_participant = None
    class_attendances = []
    participant_attendances = []
    class_recap = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0, 'total': 0}
    participant_recap = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0, 'total': 0}

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class not in my_classes:
            flash('Anda tidak memiliki akses ke kelas tersebut.', 'danger')
            return redirect(url_for('teacher.attendance_history'))

        students, majlis_participants = _get_class_participants(selected_class_id)
        participants = _build_participant_rows(students, majlis_participants)
        selected_participant = _resolve_selected_participant(participants, selected_participant_key)

        class_attendances = Attendance.query.filter(
            Attendance.class_id == selected_class_id,
            Attendance.participant_type.in_([ParticipantType.STUDENT, ParticipantType.EXTERNAL_MAJLIS])
        ).order_by(
            Attendance.date.desc(),
            Attendance.created_at.desc()
        ).limit(300).all()

        for row in class_attendances:
            class_recap['total'] += 1
            if row.status == AttendanceStatus.HADIR:
                class_recap['hadir'] += 1
            elif row.status == AttendanceStatus.SAKIT:
                class_recap['sakit'] += 1
            elif row.status == AttendanceStatus.IZIN:
                class_recap['izin'] += 1
            elif row.status == AttendanceStatus.ALPA:
                class_recap['alpa'] += 1

        if selected_participant:
            participant_query = Attendance.query.filter(
                Attendance.class_id == selected_class_id
            )
            if selected_participant['participant_type'] == ParticipantType.STUDENT:
                participant_query = participant_query.filter(
                    Attendance.participant_type == ParticipantType.STUDENT,
                    Attendance.student_id == selected_participant['student_id']
                )
            else:
                participant_query = participant_query.filter(
                    Attendance.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                    Attendance.majlis_participant_id == selected_participant['majlis_participant_id']
                )

            participant_attendances = participant_query.order_by(
                Attendance.date.desc(),
                Attendance.created_at.desc()
            ).all()

            for row in participant_attendances:
                participant_recap['total'] += 1
                if row.status == AttendanceStatus.HADIR:
                    participant_recap['hadir'] += 1
                elif row.status == AttendanceStatus.SAKIT:
                    participant_recap['sakit'] += 1
                elif row.status == AttendanceStatus.IZIN:
                    participant_recap['izin'] += 1
                elif row.status == AttendanceStatus.ALPA:
                    participant_recap['alpa'] += 1

    return render_template(
        'teacher/attendance_history.html',
        my_classes=my_classes,
        selected_class=selected_class,
        selected_participant_key=selected_participant_key,
        selected_participant=selected_participant,
        participants=participants,
        class_attendances=class_attendances,
        participant_attendances=participant_attendances,
        class_recap=class_recap,
        participant_recap=participant_recap
    )


@teacher_bp.route('/input-tahfidz', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_tahfidz_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students, majlis_participants = _get_class_participants(selected_class_id)
        else:
            flash("Anda tidak memiliki akses ke halaqoh tersebut.", "danger")

    if request.method == 'POST':
        participant_type, participant_id = _parse_participant_key(request.form.get('student_id'))
        jenis_setoran = request.form.get('jenis_setoran') or request.form.get('type')  # backward-compatible

        start_surah = request.form.get('start_surah_name')
        end_surah = request.form.get('end_surah_name')
        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')
        notes = request.form.get('notes')

        if not start_surah or not ayat_start or not ayat_end:
            flash("Surat dan ayat wajib diisi.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        try:
            final_ayat_start = int(ayat_start)
            final_ayat_end = int(ayat_end)
            tajwid_errors = int(request.form.get('tajwid_errors') or 0)
            makhraj_errors = int(request.form.get('makhraj_errors') or 0)
            tahfidz_errors = int(request.form.get('tahfidz_errors') or 0)
        except ValueError:
            flash("Ayat dan jumlah kesalahan harus berupa angka.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        if final_ayat_start < 1 or final_ayat_end < 1:
            flash("Ayat awal/akhir minimal bernilai 1.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        # Validasi urutan ayat hanya berlaku jika surat awal dan akhir sama.
        is_same_surah = (not end_surah) or (start_surah == end_surah)
        if is_same_surah and final_ayat_end < final_ayat_start:
            flash("Ayat akhir tidak boleh lebih kecil dari ayat awal jika suratnya sama.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        if not participant_id or not participant_type:
            flash("Silakan pilih peserta terlebih dahulu.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        student_id = participant_id if participant_type == ParticipantType.STUDENT else None
        majlis_participant_id = participant_id if participant_type == ParticipantType.EXTERNAL_MAJLIS else None

        if jenis_setoran not in [t.name for t in TahfidzType]:
            flash("Jenis setoran tidak valid.", "danger")
            return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

        final_surah_name = start_surah if(not end_surah or start_surah == end_surah) else f"{start_surah} - {end_surah}"

        total_errors = tajwid_errors + makhraj_errors + tahfidz_errors
        calculated_score = max(0, 100 - (total_errors * 2))
        score = int(request.form.get('score_preview') or calculated_score)
        quality = request.form.get('quality')

        new_record = TahfidzRecord(
            student_id=student_id,
            majlis_participant_id=majlis_participant_id,
            participant_type=participant_type,
            teacher_id=teacher.id,
            type=TahfidzType[jenis_setoran],
            juz=0,
            surah=final_surah_name,
            ayat_start=final_ayat_start,
            ayat_end=final_ayat_end,
            tajwid_errors=tajwid_errors,
            makhraj_errors=makhraj_errors,
            tahfidz_errors=tahfidz_errors,
            score=score,
            quality=quality,
            notes=notes,
            date=utc_now_naive()
        )
        db.session.add(new_record)

        summary = TahfidzSummary.query.filter_by(
            student_id=student_id,
            majlis_participant_id=majlis_participant_id,
            participant_type=participant_type
        ).first()
        if not summary:
            summary = TahfidzSummary(
                student_id=student_id,
                majlis_participant_id=majlis_participant_id,
                participant_type=participant_type
            )
            db.session.add(summary)

        if jenis_setoran == 'ZIYADAH':
            summary.last_surah = final_surah_name
            summary.last_ayat = final_ayat_end

        db.session.commit()
        flash('Setoran tahfidz berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_tahfidz', class_id=selected_class_id))

    return render_template('teacher/input_tahfidz.html',
                           my_classes=my_classes,
                           students=students,
                           majlis_participants=majlis_participants,
                           selected_class=selected_class,
                           tahfidz_types=TahfidzType)


@teacher_bp.route('/input-bacaan', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_recitation():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_tahfidz_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students, majlis_participants = _get_class_participants(selected_class_id)
        else:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            selected_class = None

    if request.method == 'POST':
        form_class_id = request.form.get('class_id', type=int)
        participant_type, participant_id = _parse_participant_key(request.form.get('student_id'))
        recitation_source = request.form.get('recitation_source', 'QURAN')

        active_class_id = form_class_id or selected_class_id

        if recitation_source not in [s.name for s in RecitationSource]:
            flash("Sumber bacaan tidak valid.", "danger")
            return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        if not participant_id or not participant_type:
            flash("Silakan pilih peserta terlebih dahulu.", "warning")
            return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        student_id = participant_id if participant_type == ParticipantType.STUDENT else None
        majlis_participant_id = participant_id if participant_type == ParticipantType.EXTERNAL_MAJLIS else None

        if participant_type == ParticipantType.STUDENT:
            student = Student.query.filter_by(id=student_id, is_deleted=False).first()
            if not student:
                flash("Data siswa tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))
            if active_class_id and not _student_belongs_to_class(student, active_class_id):
                flash("Siswa tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))
        else:
            participant = MajlisParticipant.query.filter_by(id=majlis_participant_id, is_deleted=False).first()
            if not participant:
                flash("Data peserta majlis tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))
            if active_class_id and participant.majlis_class_id != active_class_id:
                flash("Peserta majlis tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        start_surah = request.form.get('start_surah_name')
        end_surah = request.form.get('end_surah_name')
        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')
        book_name = request.form.get('book_name')
        page_start = request.form.get('page_start')
        page_end = request.form.get('page_end')
        notes = request.form.get('notes')

        try:
            tajwid_errors = int(request.form.get('tajwid_errors') or 0)
            makhraj_errors = int(request.form.get('makhraj_errors') or 0)
        except ValueError:
            flash("Input jumlah kesalahan harus berupa angka.", "danger")
            return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        final_surah_name = None
        final_ayat_start = None
        final_ayat_end = None
        final_page_start = None
        final_page_end = None

        if recitation_source == 'QURAN':
            if not start_surah or not ayat_start or not ayat_end:
                flash("Untuk setoran Al-Qur'an, surat dan ayat wajib diisi.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            try:
                final_ayat_start = int(ayat_start)
                final_ayat_end = int(ayat_end)
            except ValueError:
                flash("Ayat awal/akhir harus berupa angka.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            if final_ayat_start < 1 or final_ayat_end < 1:
                flash("Ayat awal/akhir minimal bernilai 1.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            # Validasi urutan ayat hanya jika surat awal dan akhir sama.
            is_same_surah = (not end_surah) or (start_surah == end_surah)
            if is_same_surah and final_ayat_end < final_ayat_start:
                flash("Ayat akhir tidak boleh lebih kecil dari ayat awal jika suratnya sama.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            final_surah_name = start_surah if (not end_surah or start_surah == end_surah) else f"{start_surah} - {end_surah}"

        else:
            if not book_name:
                flash("Nama kitab/buku wajib diisi untuk setoran jenis kitab.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            try:
                final_page_start = int(page_start) if page_start else None
                final_page_end = int(page_end) if page_end else None
            except ValueError:
                flash("Halaman awal/akhir harus berupa angka.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

            if final_page_start and final_page_end and final_page_end < final_page_start:
                flash("Halaman akhir tidak boleh lebih kecil dari halaman awal.", "warning")
                return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

        score = max(0, 100 - ((tajwid_errors + makhraj_errors) * 2))

        new_record = RecitationRecord(
            student_id=student_id,
            majlis_participant_id=majlis_participant_id,
            participant_type=participant_type,
            teacher_id=teacher.id,
            recitation_source=RecitationSource[recitation_source],
            surah=final_surah_name,
            ayat_start=final_ayat_start,
            ayat_end=final_ayat_end,
            book_name=book_name,
            page_start=final_page_start,
            page_end=final_page_end,
            tajwid_errors=tajwid_errors,
            makhraj_errors=makhraj_errors,
            score=score,
            notes=notes,
            date=utc_now_naive()
        )
        db.session.add(new_record)
        db.session.commit()
        flash('Setoran bacaan berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_recitation', class_id=active_class_id))

    return render_template('teacher/input_recitation.html',
                           my_classes=my_classes,
                           students=students,
                           majlis_participants=majlis_participants,
                           selected_class=selected_class,
                           recitation_sources=RecitationSource)


@teacher_bp.route('/input-evaluasi-tahfidz', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz_evaluation():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_tahfidz_classes(teacher)

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students, majlis_participants = _get_class_participants(selected_class_id)
        else:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            selected_class = None

    if request.method == 'POST':
        form_class_id = request.form.get('class_id', type=int)
        participant_type, participant_id = _parse_participant_key(request.form.get('student_id'))
        period_type = request.form.get('period_type')
        period_label = request.form.get('period_label')
        question_details = request.form.get('question_details')
        notes = request.form.get('notes')

        active_class_id = form_class_id or selected_class_id

        if not participant_id or not participant_type:
            flash("Silakan pilih peserta terlebih dahulu.", "warning")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        if period_type not in [p.name for p in EvaluationPeriod]:
            flash("Periode evaluasi tidak valid.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))
        if period_label not in _evaluation_period_labels(period_type):
            flash("Label periode evaluasi tidak valid.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        student_id = participant_id if participant_type == ParticipantType.STUDENT else None
        majlis_participant_id = participant_id if participant_type == ParticipantType.EXTERNAL_MAJLIS else None

        if participant_type == ParticipantType.STUDENT:
            student = Student.query.filter_by(id=student_id, is_deleted=False).first()
            if not student:
                flash("Data siswa tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))
            if active_class_id and not _student_belongs_to_class(student, active_class_id):
                flash("Siswa tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))
        else:
            participant = MajlisParticipant.query.filter_by(id=majlis_participant_id, is_deleted=False).first()
            if not participant:
                flash("Data peserta majlis tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))
            if active_class_id and participant.majlis_class_id != active_class_id:
                flash("Peserta majlis tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        try:
            makhraj_errors = int(request.form.get('makhraj_errors') or 0)
            tajwid_errors = int(request.form.get('tajwid_errors') or 0)
            harakat_errors = int(request.form.get('harakat_errors') or 0)
            tahfidz_errors = int(request.form.get('tahfidz_errors') or 0)
        except ValueError:
            flash("Input jumlah kesalahan harus berupa angka.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        question_surahs = request.form.getlist('question_surah[]')
        question_ayats = request.form.getlist('question_ayat[]')
        question_scores = request.form.getlist('question_score[]')
        if not (
            len(question_surahs) == len(question_ayats) == len(question_scores)
        ):
            flash("Setiap pertanyaan harus memiliki surah, ayat, dan nilai.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))
        normalized_questions = []
        try:
            for surah, ayat_raw, score_raw in zip(question_surahs, question_ayats, question_scores):
                surah = (surah or '').strip()
                ayat = int(ayat_raw or 0)
                score_value = float(score_raw or 0)
                if not surah or ayat < 1 or score_value < 0 or score_value > 100:
                    raise ValueError
                normalized_questions.append({
                    'surah': surah,
                    'ayat': ayat,
                    'score': round(score_value, 2),
                })
        except ValueError:
            flash("Setiap pertanyaan harus memiliki surah, ayat, dan nilai yang valid.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        if not normalized_questions:
            flash("Tambahkan minimal satu pertanyaan evaluasi.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

        question_count = len(normalized_questions)
        score = round(sum(item['score'] for item in normalized_questions) / question_count, 2)
        first_question = normalized_questions[0]
        last_question = normalized_questions[-1]
        summary_surah = first_question['surah']
        if any(item['surah'] != summary_surah for item in normalized_questions[1:]):
            summary_surah = f"{summary_surah} - {last_question['surah']}"

        new_evaluation = TahfidzEvaluation(
            student_id=student_id,
            majlis_participant_id=majlis_participant_id,
            participant_type=participant_type,
            teacher_id=teacher.id,
            period_type=EvaluationPeriod[period_type],
            period_label=period_label,
            question_count=question_count,
            question_details=question_details,
            question_items=json.dumps(normalized_questions),
            surah=summary_surah,
            ayat_start=first_question['ayat'],
            ayat_end=last_question['ayat'],
            makhraj_errors=makhraj_errors,
            tajwid_errors=tajwid_errors,
            harakat_errors=harakat_errors,
            tahfidz_errors=tahfidz_errors,
            score=score,
            notes=notes,
            date=utc_now_naive()
        )
        db.session.add(new_evaluation)
        db.session.commit()

        flash('Evaluasi tahfidz berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_tahfidz_evaluation', class_id=active_class_id))

    return render_template('teacher/input_tahfidz_evaluation.html',
                           my_classes=my_classes,
                           students=students,
                           majlis_participants=majlis_participants,
                           selected_class=selected_class,
                           EvaluationPeriod=EvaluationPeriod)


@teacher_bp.route('/input-perilaku', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_behavior_report():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)
    selected_class_id = request.args.get('class_id', type=int)
    query = (request.args.get('q') or '').strip()

    selected_class = None
    students = []
    recent_reports = []

    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            if is_rumah_quran_classroom(selected_class):
                students_query = Student.query.filter(
                    Student.id.in_([student.id for student in list_rumah_quran_students_for_class(selected_class_id)]),
                    Student.is_deleted == False,
                )
            elif is_bahasa_classroom(selected_class):
                students_query = Student.query.filter(
                    Student.id.in_([student.id for student in list_bahasa_students_for_class(selected_class_id)]),
                    Student.is_deleted == False,
                )
            else:
                students_query = Student.query.filter_by(current_class_id=selected_class_id, is_deleted=False)
            if query:
                students_query = students_query.filter(
                    db.or_(
                        Student.full_name.ilike(f'%{query}%'),
                        Student.nis.ilike(f'%{query}%')
                    )
                )
            students = students_query.order_by(Student.full_name).all()

            recent_reports = BehaviorReport.query.filter(BehaviorReport.student_id.in_([s.id for s in students])) \
                .order_by(BehaviorReport.report_date.desc(), BehaviorReport.created_at.desc()).limit(30).all() if students else []
        else:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            selected_class = None

    if request.method == 'POST':
        class_id = request.form.get('class_id', type=int)
        student_id = request.form.get('student_id', type=int)
        report_type = request.form.get('report_type')
        report_date_str = request.form.get('report_date')
        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip()
        action_plan = (request.form.get('action_plan') or '').strip()
        follow_up_date_str = (request.form.get('follow_up_date') or '').strip()
        is_resolved = request.form.get('is_resolved') == 'on'

        if not class_id or not student_id or not report_type or not title or not description:
            flash("Data laporan belum lengkap.", "warning")
            return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

        class_room = ClassRoom.query.get(class_id)
        if class_room not in my_classes:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            return redirect(url_for('teacher.input_behavior_report'))

        student = Student.query.filter_by(id=student_id, is_deleted=False).first()
        if not student or not _student_belongs_to_class(student, class_id):
            flash("Siswa tidak ditemukan pada kelas yang dipilih.", "danger")
            return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

        try:
            report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date() if report_date_str else local_today()
            follow_up_date = datetime.strptime(follow_up_date_str, '%Y-%m-%d').date() if follow_up_date_str else None
        except ValueError:
            flash("Format tanggal tidak valid.", "warning")
            return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

        if report_type not in [item.name for item in BehaviorReportType]:
            flash("Tipe laporan perilaku tidak valid.", "danger")
            return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

        new_report = BehaviorReport(
            student_id=student.id,
            teacher_id=teacher.id,
            report_date=report_date,
            report_type=BehaviorReportType[report_type],
            title=title,
            description=description,
            action_plan=action_plan or None,
            follow_up_date=follow_up_date,
            is_resolved=is_resolved
        )
        db.session.add(new_report)
        db.session.commit()
        flash("Laporan perilaku berhasil disimpan.", "success")
        return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

    return render_template(
        'teacher/input_behavior.html',
        my_classes=my_classes,
        selected_class=selected_class,
        students=students,
        recent_reports=recent_reports,
        behavior_types=BehaviorReportType,
        query=query
    )


@teacher_bp.route('/pengumuman-kelas', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def class_announcements():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)
    my_class_ids = {c.id for c in my_classes}
    selected_class_id = request.args.get('class_id', type=int)

    if request.method == 'POST':
        class_id = request.form.get('class_id', type=int)
        title = (request.form.get('title') or '').strip()
        content = (request.form.get('content') or '').strip()
        is_active = request.form.get('is_active') == 'on'

        target_class = ClassRoom.query.get(class_id) if class_id else None
        if not target_class or class_id not in my_class_ids:
            flash("Kelas target tidak valid.", "danger")
            return redirect(url_for('teacher.class_announcements'))
        if not title or not content:
            flash("Judul dan isi pengumuman wajib diisi.", "warning")
            return redirect(url_for('teacher.class_announcements', class_id=class_id))

        announcement = Announcement(
            title=title,
            content=content,
            is_active=is_active,
            target_scope='CLASS',
            target_class_id=class_id,
            user_id=current_user.id
        )
        db.session.add(announcement)
        db.session.commit()
        flash("Pengumuman kelas berhasil dibuat.", "success")
        return redirect(url_for('teacher.class_announcements', class_id=class_id))

    announcements_query = Announcement.query.filter_by(user_id=current_user.id).order_by(Announcement.created_at.desc())
    if selected_class_id:
        announcements_query = announcements_query.filter_by(target_class_id=selected_class_id)
    announcements = announcements_query.limit(30).all()

    return render_template(
        'teacher/class_announcements.html',
        my_classes=my_classes,
        selected_class_id=selected_class_id,
        announcements=announcements
    )


@teacher_bp.route('/pengumuman-kelas/hapus/<int:announcement_id>', methods=['POST'])
@login_required
@role_required(UserRole.GURU)
def delete_class_announcement(announcement_id):
    selected_class_id = request.form.get('class_id', type=int)
    announcement = Announcement.query.filter_by(id=announcement_id, user_id=current_user.id).first()
    if not announcement:
        flash("Pengumuman tidak ditemukan atau bukan milik Anda.", "danger")
        return redirect(url_for('teacher.class_announcements', class_id=selected_class_id))

    try:
        announcement.is_deleted = True
        db.session.commit()
        flash("Pengumuman berhasil dihapus.", "success")
    except Exception:
        db.session.rollback()
        flash("Gagal menghapus pengumuman.", "danger")

    return redirect(url_for('teacher.class_announcements', class_id=selected_class_id))


@teacher_bp.route('/siswa-wali-kelas')
@login_required
@role_required(UserRole.GURU)
def homeroom_students():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    homeroom_classes = ClassRoom.query.filter_by(homeroom_teacher_id=teacher.id, is_deleted=False).order_by(ClassRoom.name).all()

    if not homeroom_classes:
        flash("Anda belum ditugaskan sebagai wali kelas.", "warning")
        return redirect(url_for('teacher.dashboard'))

    selected_class_id = request.args.get('class_id', type=int) or homeroom_classes[0].id
    selected_class = next((c for c in homeroom_classes if c.id == selected_class_id), homeroom_classes[0])

    students, majlis_participants = _get_class_participants(selected_class.id)

    return render_template('teacher/homeroom_students.html',
                         teacher=teacher,
                         students=students,
                         majlis_participants=majlis_participants,
                         homeroom_class=selected_class,
                         homeroom_classes=homeroom_classes)


@teacher_bp.route('/hitung-nilai-siswa/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def calculate_student_grades(student_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    student = Student.query.get_or_404(student_id)
    
    # Cek akses
    my_classes = _get_teacher_classes(teacher)
    if student.current_class not in my_classes:
        flash("Anda tidak memiliki akses ke siswa tersebut.", "danger")
        return redirect(url_for('teacher.dashboard'))
    
    active_year = AcademicYear.query.filter_by(is_active=True).first()
    if not active_year:
        flash('Tahun ajaran aktif belum diatur.', 'warning')
        return redirect(url_for('teacher.dashboard'))
    
    # Ambil semua nilai siswa di tahun aktif
    grades = Grade.query.filter_by(
        student_id=student_id,
        academic_year_id=active_year.id
    ).all()
    
    # Group by subject
    grades_by_subject = defaultdict(list)
    for grade in grades:
        if not grade.subject:
            continue
        grades_by_subject[grade.subject].append(grade)
    
    # Hitung rata-rata per mapel
    subject_averages = {}
    for subject, subject_grades in grades_by_subject.items():
        type_scores = defaultdict(list)
        for grade in subject_grades:
            type_scores[grade.type].append(grade.score)
        
        # Rata-rata per tipe (berdasarkan enum name: TUGAS/UH/UTS/UAS)
        type_averages = {}
        for grade_type, scores in type_scores.items():
            type_averages[grade_type.name] = sum(scores) / len(scores)

        subject_averages[subject.name] = _calculate_weighted_final(type_averages)
    
    return render_template('teacher/student_grades_calculation.html',
                         student=student,
                         grades_by_subject=grades_by_subject,
                         subject_averages=subject_averages,
                         active_year=active_year)


@teacher_bp.route('/cetak-raport/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def print_report_card(student_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    homeroom_classes = ClassRoom.query.filter_by(homeroom_teacher_id=teacher.id, is_deleted=False).all()

    if not homeroom_classes:
        flash("Hanya wali kelas yang dapat mencetak raport.", "danger")
        return redirect(url_for('teacher.dashboard'))
    
    student = Student.query.get_or_404(student_id)
    if student.current_class_id not in [c.id for c in homeroom_classes]:
        flash("Siswa tidak ada di kelas perwalian Anda.", "danger")
        return redirect(url_for('teacher.homeroom_students'))

    active_year = AcademicYear.query.filter_by(is_active=True).first()
    final_report = []
    if active_year:
        grades = Grade.query.filter_by(student_id=student.id, academic_year_id=active_year.id).all()
        grouped = defaultdict(lambda: defaultdict(list))
        for g in grades:
            grouped[g.subject][g.type.name].append(g.score)

        for sub, data in grouped.items():
            type_averages = {}
            for grade_type in ['TUGAS', 'UH', 'UTS', 'UAS']:
                scores = data.get(grade_type, [])
                if scores:
                    type_averages[grade_type] = sum(scores) / len(scores)
            final_score = _calculate_weighted_final(type_averages)
            predikat = 'A' if final_score >= 85 else 'B' if final_score >= 75 else 'C' if final_score >= 65 else 'D'
            final_report.append({'subject': sub.name, 'kkm': sub.kkm or 70, 'final': final_score, 'predikat': predikat})

    attendance_stats = {'sakit': 0, 'izin': 0, 'alpa': 0}
    if active_year:
        attendances = Attendance.query.filter_by(student_id=student.id, academic_year_id=active_year.id).all()
        for a in attendances:
            if a.status.name == 'SAKIT':
                attendance_stats['sakit'] += 1
            elif a.status.name == 'IZIN':
                attendance_stats['izin'] += 1
            elif a.status.name == 'ALPHA':
                attendance_stats['alpa'] += 1

    return render_template('teacher/print_report.html',
                          student=student,
                          teacher=teacher,
                          academic_year=active_year,
                          final_report=final_report,
                          attendance_stats=attendance_stats)


@teacher_bp.route('/cetak-lampiran/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def print_attachment(student_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    student = Student.query.get_or_404(student_id)
    
    # Get tahfidz records for attachment
    tahfidz_records = TahfidzRecord.query.filter_by(
        student_id=student_id,
        participant_type=ParticipantType.STUDENT
    ).order_by(TahfidzRecord.date.desc()).all()
    
    # Get recitation records
    recitation_records = RecitationRecord.query.filter_by(
        student_id=student_id,
        participant_type=ParticipantType.STUDENT
    ).order_by(RecitationRecord.date.desc()).all()
    
    return render_template('teacher/print_attachment.html',
                         student=student,
                         teacher=teacher,
                         tahfidz_records=tahfidz_records,
                         recitation_records=recitation_records)


@teacher_bp.route('/input-absensi', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_attendance():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)
    
    selected_class_id = request.args.get('class_id', type=int)
    selected_date = request.args.get('date', local_today().strftime('%Y-%m-%d'))
    
    students = []
    majlis_participants = []
    participants = []
    selected_class = None
    existing_attendance = {}
    
    if selected_class_id:
        selected_class = ClassRoom.query.get(selected_class_id)
        if selected_class in my_classes:
            students, majlis_participants = _get_class_participants(selected_class_id)
            participants = _build_participant_rows(students, majlis_participants)
            
            # Cek absensi yang sudah ada
            date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
            attendances = Attendance.query.filter(
                Attendance.class_id == selected_class_id,
                Attendance.date == date_obj,
                Attendance.participant_type.in_([ParticipantType.STUDENT, ParticipantType.EXTERNAL_MAJLIS])
            ).all()

            for att in attendances:
                if att.participant_type == ParticipantType.EXTERNAL_MAJLIS and att.majlis_participant_id:
                    key = f"M-{att.majlis_participant_id}"
                elif att.student_id:
                    key = f"S-{att.student_id}"
                else:
                    continue
                existing_attendance[key] = {
                    'status': att.status.name,
                    'notes': att.notes or ''
                }
        else:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
    
    if request.method == 'POST':
        date_str = request.form.get('attendance_date') or selected_date
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Format tanggal absensi tidak valid.', 'warning')
            return redirect(url_for('teacher.input_attendance', class_id=selected_class_id, date=selected_date))
        
        active_year = AcademicYear.query.filter_by(is_active=True).first()
        
        for participant in participants:
            status_key = f"status_{participant['key']}"
            status = request.form.get(status_key)
            notes_key = f"notes_{participant['key']}"
            notes = request.form.get(notes_key, '')
            
            if status:
                # Cek apakah sudah ada record
                existing = Attendance.query.filter_by(
                    student_id=participant['student_id'],
                    majlis_participant_id=participant['majlis_participant_id'],
                    participant_type=participant['participant_type'],
                    class_id=selected_class_id,
                    date=date_obj,
                ).first()
                
                if existing:
                    existing.status = AttendanceStatus[status]
                    existing.notes = notes
                else:
                    new_attendance = Attendance(
                        student_id=participant['student_id'],
                        majlis_participant_id=participant['majlis_participant_id'],
                        participant_type=participant['participant_type'],
                        class_id=selected_class_id,
                        teacher_id=teacher.id,
                        academic_year_id=active_year.id if active_year else None,
                        date=date_obj,
                        status=AttendanceStatus[status],
                        notes=notes
                    )
                    db.session.add(new_attendance)
        
        db.session.commit()
        flash('Absensi berhasil disimpan!', 'success')
        return redirect(url_for('teacher.input_attendance', 
                              class_id=selected_class_id, 
                              date=date_str))
    
    return render_template('teacher/input_attendance.html',
                         my_classes=my_classes,
                         participants=participants,
                         selected_class=selected_class,
                         selected_class_id=selected_class_id,
                         selected_date=selected_date,
                         existing_attendance=existing_attendance,
                         attendance_statuses=AttendanceStatus)

