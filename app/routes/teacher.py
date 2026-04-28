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
from app.utils.tenant import classroom_in_tenant, resolve_tenant_id, scoped_classrooms_query
from app.utils.timezone import local_day_bounds_utc_naive, local_today, utc_now_naive

teacher_bp = Blueprint('teacher', __name__)


def _teacher_tenant_id(teacher):
    if teacher is None:
        return None
    return resolve_tenant_id(getattr(teacher, "user", None), fallback_default=False)


def _teacher_scoped_classrooms_query(teacher):
    tenant_id = _teacher_tenant_id(teacher)
    if tenant_id is None:
        return ClassRoom.query.filter(ClassRoom.id == -1)
    return scoped_classrooms_query(tenant_id)


def _teacher_classroom_by_id(teacher, class_id):
    if not class_id:
        return None
    return _teacher_scoped_classrooms_query(teacher).filter(ClassRoom.id == class_id).first()


def _classroom_visible_for_teacher(teacher, class_room):
    if class_room is None:
        return False
    tenant_id = _teacher_tenant_id(teacher)
    return classroom_in_tenant(class_room, tenant_id)


def _dedupe_classes(classes):
    deduped = {}
    for class_room in classes or []:
        if class_room and class_room.id not in deduped:
            deduped[class_room.id] = class_room
    return list(deduped.values())


def _get_teacher_homeroom_classes(teacher):
    classes = [
        class_room
        for class_room in list_teacher_homeroom_classes_from_assignments(teacher)
        if _classroom_visible_for_teacher(teacher, class_room)
    ]
    if classes:
        return sorted(_dedupe_classes(classes), key=lambda item: item.name or "")
    return (
        _teacher_scoped_classrooms_query(teacher)
        .filter(ClassRoom.homeroom_teacher_id == teacher.id)
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
        if not _classroom_visible_for_teacher(teacher, sch.class_room):
            continue
        if is_rumah_quran_classroom(sch.class_room):
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
            {'endpoint': 'teacher.homeroom_students', 'label': 'Raport Perwalian', 'icon': 'fas fa-users'},
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
            {'endpoint': 'teacher.input_grades', 'label': 'Input Nilai', 'icon': 'fas fa-pen-alt'},
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
        if not _classroom_visible_for_teacher(teacher, assigned_class):
            continue
        if is_rumah_quran_classroom(assigned_class):
            continue
        classes_by_id[assigned_class.id] = assigned_class
    
    # 2. Kelas dari jadwal mengajar guru
    teaching_class_ids = db.session.query(Schedule.class_id).filter(
        Schedule.teacher_id == teacher.id,
        Schedule.is_deleted == False,
        Schedule.class_id.isnot(None)
    ).distinct().all()
    for row in teaching_class_ids:
        class_id = row[0]
        target_class = _teacher_classroom_by_id(teacher, class_id)
        if target_class and not target_class.is_deleted:
            if is_rumah_quran_classroom(target_class):
                continue
            classes_by_id[target_class.id] = target_class
    
    return list(classes_by_id.values())


def _get_teacher_attendance_classes(teacher):
    """Kelas untuk akses absensi: hanya wali kelas atau guru mapel aktif."""
    classes_by_id = {}

    for homeroom_class in _get_teacher_homeroom_classes(teacher):
        classes_by_id[homeroom_class.id] = homeroom_class

    teaching_schedules = (
        Schedule.query.filter(
            Schedule.teacher_id == teacher.id,
            Schedule.is_deleted.is_(False),
            Schedule.class_id.isnot(None),
        )
        .order_by(Schedule.class_id.asc())
        .all()
    )
    for schedule in teaching_schedules:
        class_room = schedule.class_room
        if not class_room or class_room.is_deleted:
            continue
        if not _classroom_visible_for_teacher(teacher, class_room):
            continue
        if not schedule.subject_id and not schedule.majlis_subject_id:
            continue
        if is_rumah_quran_classroom(class_room):
            continue
        classes_by_id[class_room.id] = class_room

    return sorted(classes_by_id.values(), key=lambda item: item.name or "")


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

    # Rumah Qur'an: akses tahfidz hanya untuk pembimbing/wali kelas yang melekat
    # pada kelas tersebut (homeroom_teacher_id).
    strict_rumah_quran_classes = (
        _teacher_scoped_classrooms_query(teacher).filter(
            ClassRoom.homeroom_teacher_id == teacher.id,
            ClassRoom.program_type.in_([ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ]),
        )
        .order_by(ClassRoom.name.asc())
        .all()
    )
    for homeroom_class in strict_rumah_quran_classes:
        seen_ids.add(homeroom_class.id)
        classes.append(homeroom_class)

    # Kelas tahfidz non-RQ: ambil hanya dari assignment guru mapel yang masih aktif.
    # Ini mencegah akses dari jadwal lama/stale yang belum relevan.
    assigned_subject_class_ids = {
        class_room.id
        for class_room in _dedupe_classes(list_teacher_subject_classes_from_assignments(teacher))
        if class_room and not class_room.is_deleted and _classroom_visible_for_teacher(teacher, class_room)
    }
    schedules = []
    if assigned_subject_class_ids:
        schedules = (
            Schedule.query.filter(
                Schedule.teacher_id == teacher.id,
                Schedule.is_deleted.is_(False),
                Schedule.class_id.in_(assigned_subject_class_ids),
            )
            .order_by(Schedule.day.asc(), Schedule.start_time.asc())
            .all()
        )

    for schedule in schedules:
        if not schedule.class_room or schedule.class_room.is_deleted:
            continue
        if not _classroom_visible_for_teacher(teacher, schedule.class_room):
            continue
        if is_rumah_quran_classroom(schedule.class_room):
            # Rumah Qur'an tidak memakai akses berbasis jadwal mapel.
            continue
        if not _is_tahfidz_related_schedule(schedule):
            continue
        if schedule.class_id in seen_ids:
            continue
        seen_ids.add(schedule.class_id)
        classes.append(schedule.class_room)
    return classes


def _teacher_can_access_tahfidz_class(teacher, class_id):
    if not teacher or not class_id:
        return False

    class_room = _teacher_classroom_by_id(teacher, class_id)
    if class_room is None:
        return False

    if is_rumah_quran_classroom(class_room):
        # Hard rule: hanya pembimbing/wali kelas Rumah Qur'an yang boleh akses.
        return class_room.homeroom_teacher_id == teacher.id

    return any(item.id == class_id for item in _get_teacher_tahfidz_classes(teacher))


def _get_teacher_tahfidz_classes_legacy(teacher):
    classes = []
    seen_ids = set()

    for homeroom_class in _get_teacher_homeroom_classes(teacher):
        if is_rumah_quran_classroom(homeroom_class):
            seen_ids.add(homeroom_class.id)
            classes.append(homeroom_class)
    return classes


def _get_class_participants(class_id, tenant_id=None):
    if tenant_id is None:
        tenant_id = resolve_tenant_id(current_user, fallback_default=False)

    class_room = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == class_id).first() if tenant_id else None
    if class_room is None:
        return [], []

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


def _teacher_can_access_class(teacher, class_id):
    if not teacher or not class_id:
        return False
    return any(class_room.id == class_id for class_room in _get_teacher_classes(teacher))


def _teacher_can_access_attendance_class(teacher, class_id):
    if not teacher or not class_id:
        return False
    return any(class_room.id == class_id for class_room in _get_teacher_attendance_classes(teacher))


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


BEHAVIOR_INDICATORS = {
    'positive': [
        {'key': 'rajin', 'label': 'Rajin'},
        {'key': 'sopan', 'label': 'Sopan'},
        {'key': 'fokus', 'label': 'Fokus'},
        {'key': 'usaha_keras', 'label': 'Usaha Keras'},
        {'key': 'optimis', 'label': 'Optimis'},
        {'key': 'tanggung_jawab', 'label': 'Tanggung Jawab'},
        {'key': 'tolong_menolong', 'label': 'Tolong Menolong'},
    ],
    'negative': [
        {'key': 'bicara_kasar', 'label': 'Bicara Kasar'},
        {'key': 'gaduh_ganggu', 'label': 'Gaduh / Ganggu'},
        {'key': 'pergi_tanpa_izin', 'label': 'Pergi tanpa izin'},
        {'key': 'malas_menghafal', 'label': 'Malas menghafal'},
        {'key': 'membantah', 'label': 'Membantah'},
        {'key': 'ngobrol', 'label': 'Ngobrol'},
        {'key': 'bermusuhan', 'label': 'Bermusuhan'},
    ],
}


def _behavior_indicator_items():
    rows = []
    for group_name in ('positive', 'negative'):
        default_yes = group_name == 'positive'
        for row in BEHAVIOR_INDICATORS[group_name]:
            rows.append({
                'key': row['key'],
                'label': row['label'],
                'group': group_name,
                'default_yes': default_yes,
            })
    return rows


def _behavior_indicator_label_map():
    result = {}
    for row in _behavior_indicator_items():
        result[row['key']] = row['label']
    return result


def _behavior_frequency_category(yes_count, total_meetings):
    total = max(0, int(total_meetings or 0))
    yes = max(0, int(yes_count or 0))
    yes = min(yes, total) if total else 0
    percentage = round((float(yes) / float(total)) * 100, 2) if total else 0.0
    if percentage >= 75:
        key, label = 'SL', 'SELALU'
    elif percentage >= 30:
        key, label = 'SR', 'SERING'
    elif percentage > 0:
        key, label = 'K', 'KURANG/KADANG'
    else:
        key, label = 'TP', 'TIDAK PERNAH'
    return {'key': key, 'label': label, 'percentage': percentage}


def _class_meeting_dates(class_id, academic_year_ids=None, start_date=None, end_date=None):
    query = Attendance.query.filter(
        Attendance.is_deleted.is_(False),
        Attendance.class_id == class_id,
        Attendance.participant_type == ParticipantType.STUDENT,
    )
    if academic_year_ids:
        query = query.filter(Attendance.academic_year_id.in_(academic_year_ids))
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    rows = query.with_entities(Attendance.date).distinct().all()
    return sorted({row[0] for row in rows if row and row[0]})


def _behavior_matrix_for_student(
    student_id,
    class_id,
    academic_year_ids=None,
    start_date=None,
    end_date=None,
    history_limit=120,
):
    indicator_items = _behavior_indicator_items()
    indicator_map = {row['key']: row for row in indicator_items}
    meeting_dates = _class_meeting_dates(class_id, academic_year_ids=academic_year_ids, start_date=start_date, end_date=end_date)

    query = BehaviorReport.query.filter(
        BehaviorReport.is_deleted.is_(False),
        BehaviorReport.student_id == student_id,
    )
    if start_date:
        query = query.filter(BehaviorReport.report_date >= start_date)
    if end_date:
        query = query.filter(BehaviorReport.report_date <= end_date)
    behavior_rows = query.order_by(BehaviorReport.report_date.desc(), BehaviorReport.created_at.desc()).all()

    if not meeting_dates:
        meeting_dates = sorted({row.report_date for row in behavior_rows if row.report_date})
    meeting_set = set(meeting_dates)

    grouped_yes_by_day = defaultdict(lambda: defaultdict(bool))
    for row in behavior_rows:
        key = (row.indicator_key or '').strip().lower()
        if not key or key not in indicator_map or row.report_date is None:
            continue
        if meeting_set and row.report_date not in meeting_set:
            continue
        if row.is_yes is True:
            grouped_yes_by_day[key][row.report_date] = True
        elif row.report_date not in grouped_yes_by_day[key]:
            grouped_yes_by_day[key][row.report_date] = False

    matrix = {'positive': [], 'negative': []}
    total_meetings = len(meeting_dates)
    for row in indicator_items:
        key = row['key']
        group = row['group']
        day_values = grouped_yes_by_day.get(key, {})
        yes_count = len([flag for flag in day_values.values() if flag])
        no_count = max(0, total_meetings - yes_count)
        category = _behavior_frequency_category(yes_count, total_meetings)
        matrix[group].append({
            'key': key,
            'label': row['label'],
            'yes_count': yes_count,
            'no_count': no_count,
            'total_meetings': total_meetings,
            'yes_percentage': category['percentage'],
            'category_key': category['key'],
            'category_label': category['label'],
            'is_SL': category['key'] == 'SL',
            'is_SR': category['key'] == 'SR',
            'is_K': category['key'] == 'K',
            'is_TP': category['key'] == 'TP',
        })

    history_rows = []
    for row in behavior_rows[:max(1, history_limit)]:
        key = (row.indicator_key or '').strip().lower()
        label = indicator_map[key]['label'] if key in indicator_map else (row.title or '-')
        history_rows.append({
            'id': row.id,
            'report_date': _web_fmt_date(row.report_date),
            'indicator_key': key or '-',
            'indicator_label': label,
            'group': row.indicator_group or ('positive' if row.report_type == BehaviorReportType.POSITIVE else 'negative'),
            'is_yes': bool(row.is_yes),
            'teacher_name': row.teacher.full_name if row.teacher and row.teacher.full_name else '-',
            'notes': row.description or '-',
        })

    return {
        'total_meetings': total_meetings,
        'matrix': matrix,
        'history_rows': history_rows,
        'legend': {'SL': 'SELALU', 'SR': 'SERING', 'K': 'KURANG/KADANG', 'TP': 'TIDAK PERNAH'},
    }


def _web_fmt_date(value):
    return value.strftime('%d/%m/%Y') if value else '-'


def _web_fmt_datetime(value):
    return value.strftime('%d/%m/%Y %H:%M') if value else '-'


def _grade_subject_name(row):
    if row.subject and row.subject.name:
        return row.subject.name
    if row.majlis_subject and row.majlis_subject.name:
        return row.majlis_subject.name
    return '-'


def _academic_report_payload_for_homeroom(rows, include_history=False, history_limit=120):
    grouped = defaultdict(lambda: defaultdict(list))
    summary_rows = []
    history_rows = []

    for row in rows or []:
        subject_name = _grade_subject_name(row)
        if row.type:
            grouped[subject_name][row.type.name].append(float(row.score or 0))

        if include_history and len(history_rows) < max(1, history_limit):
            history_rows.append({
                'id': row.id,
                'created_at': _web_fmt_datetime(row.created_at),
                'subject_name': subject_name,
                'type': row.type.name if row.type else '-',
                'type_label': row.type.value if row.type else '-',
                'score': row.score or 0,
                'notes': row.notes or '-',
                'teacher_name': row.teacher.full_name if row.teacher and row.teacher.full_name else '-',
            })

    for subject_name, type_map in grouped.items():
        type_averages = {}
        type_counts = {}
        for type_name, scores in type_map.items():
            if scores:
                type_averages[type_name] = round(sum(scores) / len(scores), 2)
                type_counts[type_name] = len(scores)
        summary_rows.append({
            'subject_name': subject_name,
            'type_averages': type_averages,
            'type_counts': type_counts,
            'final_score': _calculate_weighted_final(type_averages),
        })

    summary_rows.sort(key=lambda row: (row.get('subject_name') or '').lower())
    final_scores = [float(item.get('final_score') or 0) for item in summary_rows]
    final_average = round(sum(final_scores) / len(final_scores), 2) if final_scores else 0

    return {
        'grade_count': len(rows or []),
        'subject_count': len(summary_rows),
        'final_average': final_average,
        'summary_rows': summary_rows,
        'history_rows': history_rows,
    }


def _attendance_report_payload_for_homeroom(rows, include_history=False, history_limit=120):
    recap = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0, 'total': 0}
    history_rows = []

    for row in rows or []:
        recap['total'] += 1
        if row.status == AttendanceStatus.HADIR:
            recap['hadir'] += 1
        elif row.status == AttendanceStatus.SAKIT:
            recap['sakit'] += 1
        elif row.status == AttendanceStatus.IZIN:
            recap['izin'] += 1
        elif row.status == AttendanceStatus.ALPA:
            recap['alpa'] += 1

        if include_history and len(history_rows) < max(1, history_limit):
            history_rows.append({
                'id': row.id,
                'date': _web_fmt_date(row.date),
                'status': row.status.name if row.status else '-',
                'status_label': row.status.value if row.status else '-',
                'notes': row.notes or '-',
                'teacher_name': row.teacher.full_name if row.teacher and row.teacher.full_name else '-',
                'class_name': row.class_room.name if row.class_room and row.class_room.name else '-',
            })

    attendance_rate = round((float(recap['hadir']) / float(recap['total'])) * 100, 2) if recap['total'] else 0
    return {
        'recap': recap,
        'attendance_rate': attendance_rate,
        'history_rows': history_rows,
    }


def _behavior_report_payload_for_homeroom(rows, include_history=False, history_limit=120):
    recap = {'positive': 0, 'development': 0, 'concern': 0, 'resolved': 0, 'unresolved': 0, 'total': 0}
    history_rows = []

    for row in rows or []:
        recap['total'] += 1
        if row.report_type == BehaviorReportType.POSITIVE:
            recap['positive'] += 1
        elif row.report_type == BehaviorReportType.DEVELOPMENT:
            recap['development'] += 1
        elif row.report_type == BehaviorReportType.CONCERN:
            recap['concern'] += 1

        if row.is_resolved:
            recap['resolved'] += 1
        else:
            recap['unresolved'] += 1

        if include_history and len(history_rows) < max(1, history_limit):
            history_rows.append({
                'id': row.id,
                'report_date': _web_fmt_date(row.report_date),
                'report_type': row.report_type.name if row.report_type else '-',
                'report_type_label': row.report_type.value if row.report_type else '-',
                'title': row.title or '-',
                'description': row.description or '-',
                'action_plan': row.action_plan or '-',
                'follow_up_date': _web_fmt_date(row.follow_up_date),
                'is_resolved': bool(row.is_resolved),
                'teacher_name': row.teacher.full_name if row.teacher and row.teacher.full_name else '-',
            })

    return {'recap': recap, 'history_rows': history_rows}


def _behavior_summary_from_indicator_rows(rows):
    total = 0
    positive_yes = 0
    negative_yes = 0
    for row in rows or []:
        key = (row.indicator_key or '').strip().lower()
        group = (row.indicator_group or '').strip().lower()
        if not key or group not in {'positive', 'negative'}:
            continue
        total += 1
        if bool(row.is_yes):
            if group == 'positive':
                positive_yes += 1
            else:
                negative_yes += 1
    return {
        'total_observations': total,
        'positive_yes': positive_yes,
        'negative_yes': negative_yes,
    }


def _quran_report_payload_for_homeroom(tahfidz_rows, recitation_rows, evaluation_rows):
    tahfidz_scores = [float(item.score or 0) for item in tahfidz_rows]
    recitation_scores = [float(item.score or 0) for item in recitation_rows]
    evaluation_scores = [float(item.score or 0) for item in evaluation_rows]

    tahfidz_history = []
    for row in tahfidz_rows:
        tahfidz_history.append({
            'id': row.id,
            'date': _web_fmt_datetime(row.date),
            'type': row.type.name if row.type else '-',
            'type_label': row.type.value if row.type else '-',
            'surah': row.surah or '-',
            'ayat_start': row.ayat_start or '-',
            'ayat_end': row.ayat_end or '-',
            'score': row.score or 0,
            'notes': row.notes or '-',
        })

    recitation_history = []
    for row in recitation_rows:
        recitation_history.append({
            'id': row.id,
            'date': _web_fmt_datetime(row.date),
            'recitation_source': row.recitation_source.name if row.recitation_source else '-',
            'recitation_source_label': row.recitation_source.value if row.recitation_source else '-',
            'surah': row.surah or '-',
            'ayat_start': row.ayat_start or '-',
            'ayat_end': row.ayat_end or '-',
            'book_name': row.book_name or '-',
            'page_start': row.page_start or '-',
            'page_end': row.page_end or '-',
            'score': row.score or 0,
            'notes': row.notes or '-',
        })

    evaluation_history = []
    for row in evaluation_rows:
        evaluation_history.append({
            'id': row.id,
            'date': _web_fmt_datetime(row.date),
            'period_type': row.period_type.name if row.period_type else '-',
            'period_type_label': row.period_type.value if row.period_type else '-',
            'period_label': row.period_label or '-',
            'question_count': row.question_count or 0,
            'question_details': row.question_details or '-',
            'score': row.score or 0,
            'notes': row.notes or '-',
        })

    return {
        'tahfidz_summary': {
            'count': len(tahfidz_rows),
            'average_score': round(sum(tahfidz_scores) / len(tahfidz_scores), 2) if tahfidz_scores else 0,
        },
        'recitation_summary': {
            'count': len(recitation_rows),
            'average_score': round(sum(recitation_scores) / len(recitation_scores), 2) if recitation_scores else 0,
        },
        'evaluation_summary': {
            'count': len(evaluation_rows),
            'average_score': round(sum(evaluation_scores) / len(evaluation_scores), 2) if evaluation_scores else 0,
        },
        'tahfidz_history': tahfidz_history,
        'recitation_history': recitation_history,
        'evaluation_history': evaluation_history,
    }


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


def _resolve_homeroom_report_period(period_type_raw, academic_year_id_raw, year_name_raw):
    period_type = (period_type_raw or 'SEMESTER').strip().upper()
    if period_type not in {'SEMESTER', 'YEAR'}:
        period_type = 'SEMESTER'

    all_years = (
        AcademicYear.query.filter_by(is_deleted=False)
        .order_by(AcademicYear.name.desc(), AcademicYear.id.desc())
        .all()
    )
    active_year = AcademicYear.query.filter_by(is_active=True, is_deleted=False).order_by(AcademicYear.id.desc()).first()

    selected_year = None
    selected_year_name = (year_name_raw or '').strip()
    selected_year_rows = []

    if period_type == 'SEMESTER':
        if academic_year_id_raw:
            selected_year = AcademicYear.query.filter_by(id=academic_year_id_raw, is_deleted=False).first()
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
        {'id': row.id, 'label': f'{row.name or "-"} - {row.semester or "-"}', 'name': row.name or '-', 'semester': row.semester or '-'}
        for row in all_years
    ]
    seen_names = []
    for row in all_years:
        label = (row.name or '').strip()
        if label and label not in seen_names:
            seen_names.append(label)
    year_options = [{'key': name, 'label': name} for name in seen_names]

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
    todays_schedules = [
        schedule
        for schedule in todays_schedules
        if _classroom_visible_for_teacher(teacher, schedule.class_room)
    ]

    all_teacher_schedules = Schedule.query.filter_by(teacher_id=teacher.id, is_deleted=False).all()
    for sch in all_teacher_schedules:
        if not sch.class_room:
            continue
        if not _classroom_visible_for_teacher(teacher, sch.class_room):
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
        for class_room in my_classes:
            students, _ = _get_class_participants(class_room.id)
            for student in students:
                if student.boarding_dormitory_id:
                    boarding_student_ids.append(student.id)
        boarding_student_ids = list(set(boarding_student_ids))

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
    my_class_ids = {class_room.id for class_room in my_classes}

    selected_class_id = request.args.get('class_id', type=int)
    selected_subject_id = request.args.get('subject_id', type=int)
    selected_majlis_subject_id = request.args.get('majlis_subject_id', type=int)
    students = []
    majlis_participants = []
    participants = []
    target_class = None
    class_subject_options = []
    class_majlis_subject_options = []

    if selected_class_id:
        target_class = _teacher_classroom_by_id(teacher, selected_class_id)
        if target_class and selected_class_id in my_class_ids:
            students, majlis_participants = _get_class_participants(selected_class_id)
            participants = _build_participant_rows(students, majlis_participants)

            class_schedules = (
                Schedule.query.filter(
                    Schedule.teacher_id == teacher.id,
                    Schedule.class_id == selected_class_id,
                    Schedule.is_deleted.is_(False),
                )
                .order_by(Schedule.day.asc(), Schedule.start_time.asc(), Schedule.id.asc())
                .all()
            )
            seen_subject_ids = set()
            seen_majlis_subject_ids = set()
            for schedule in class_schedules:
                if schedule.subject_id and schedule.subject and schedule.subject_id not in seen_subject_ids:
                    seen_subject_ids.add(schedule.subject_id)
                    class_subject_options.append(schedule.subject)
                if (
                    schedule.majlis_subject_id
                    and schedule.majlis_subject
                    and schedule.majlis_subject_id not in seen_majlis_subject_ids
                ):
                    seen_majlis_subject_ids.add(schedule.majlis_subject_id)
                    class_majlis_subject_options.append(schedule.majlis_subject)
        else:
            flash('Anda tidak memiliki akses ke kelas tersebut.', 'danger')
            target_class = None
            selected_class_id = None
            selected_subject_id = None
            selected_majlis_subject_id = None

    valid_subject_ids = {item.id for item in class_subject_options}
    valid_majlis_subject_ids = {item.id for item in class_majlis_subject_options}
    if selected_subject_id and selected_subject_id not in valid_subject_ids:
        selected_subject_id = None
    if selected_majlis_subject_id and selected_majlis_subject_id not in valid_majlis_subject_ids:
        selected_majlis_subject_id = None
    if selected_subject_id and selected_majlis_subject_id:
        selected_majlis_subject_id = None

    subject = Subject.query.get(selected_subject_id) if selected_subject_id else None
    majlis_subject = MajlisSubject.query.get(selected_majlis_subject_id) if selected_majlis_subject_id else None

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
        form_class_id = request.form.get('class_id', type=int)
        active_class_id = form_class_id or selected_class_id
        if not active_class_id or active_class_id not in my_class_ids:
            flash('Kelas tidak valid atau Anda tidak memiliki akses.', 'danger')
            return redirect(url_for('teacher.input_grades'))

        active_students, active_majlis_participants = _get_class_participants(active_class_id)
        active_participants = _build_participant_rows(active_students, active_majlis_participants)

        if not active_year:
            flash('Tahun ajaran aktif belum diatur.', 'warning')
            return redirect(url_for(
                'teacher.input_grades',
                class_id=active_class_id,
                subject_id=selected_subject_id,
                majlis_subject_id=selected_majlis_subject_id
            ))

        grade_type = request.form.get('grade_type')
        notes = request.form.get('notes', '')
        subject_id = request.form.get('subject_id', type=int) or selected_subject_id
        majlis_subject_id = request.form.get('majlis_subject_id', type=int) or selected_majlis_subject_id
        if subject_id and subject_id not in valid_subject_ids:
            subject_id = None
        if majlis_subject_id and majlis_subject_id not in valid_majlis_subject_ids:
            majlis_subject_id = None
        if subject_id and majlis_subject_id:
            majlis_subject_id = None

        if grade_type not in [t.name for t in GradeType]:
            flash('Tipe nilai tidak valid.', 'warning')
            return redirect(url_for(
                'teacher.input_grades',
                class_id=active_class_id,
                subject_id=selected_subject_id,
                majlis_subject_id=selected_majlis_subject_id
            ))
        if not subject_id and not majlis_subject_id:
            flash('Mata pelajaran belum dipilih.', 'warning')
            return redirect(url_for(
                'teacher.input_grades',
                class_id=active_class_id,
                subject_id=selected_subject_id,
                majlis_subject_id=selected_majlis_subject_id
            ))
        if not active_participants:
            flash('Belum ada peserta pada kelas ini.', 'warning')
            return redirect(url_for(
                'teacher.input_grades',
                class_id=active_class_id,
                subject_id=selected_subject_id,
                majlis_subject_id=selected_majlis_subject_id
            ))
        
        success_count = 0
        for participant in active_participants:
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
            class_id=active_class_id,
            subject_id=subject_id,
            majlis_subject_id=majlis_subject_id
        ))
    
    return render_template('teacher/input_grades.html',
                           my_classes=my_classes,
                           participants=participants,
                           target_class=target_class,
                           selected_class_id=selected_class_id,
                           subject=subject,
                           selected_subject_id=selected_subject_id,
                           class_subject_options=class_subject_options,
                           majlis_subject=majlis_subject,
                           selected_majlis_subject_id=selected_majlis_subject_id,
                           class_majlis_subject_options=class_majlis_subject_options,
                           existing_grades=existing_grades)


@teacher_bp.route('/riwayat-nilai')
@login_required
@role_required(UserRole.GURU)
def grade_history():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_classes(teacher)
    my_class_ids = {class_room.id for class_room in my_classes}

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
        selected_class = _teacher_classroom_by_id(teacher, selected_class_id)
        if selected_class is None or selected_class_id not in my_class_ids:
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
    my_classes = _get_teacher_attendance_classes(teacher)
    my_class_ids = {class_room.id for class_room in my_classes}

    selected_class_id = request.args.get('class_id', type=int)
    selected_participant_key = (request.args.get('participant') or '').strip()

    selected_class = None
    participants = []
    selected_participant = None
    class_attendances = []
    participant_attendances = []
    participant_summary_rows = []
    class_recap = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0, 'total': 0}
    participant_recap = {'hadir': 0, 'sakit': 0, 'izin': 0, 'alpa': 0, 'total': 0}

    if selected_class_id:
        selected_class = _teacher_classroom_by_id(teacher, selected_class_id)
        if selected_class is None or selected_class_id not in my_class_ids:
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

        participant_summary_map = {
            row['key']: {
                'key': row['key'],
                'display_name': row['display_name'],
                'identifier': row['identifier'],
                'identifier_label': row['identifier_label'],
                'hadir': 0,
                'sakit': 0,
                'izin': 0,
                'alpa': 0,
                'total': 0,
            }
            for row in participants
        }

        for row in class_attendances:
            class_recap['total'] += 1
            if row.participant_type == ParticipantType.EXTERNAL_MAJLIS and row.majlis_participant_id:
                key = f"M-{row.majlis_participant_id}"
                fallback_name = row.majlis_participant.full_name if row.majlis_participant else f"Peserta #{row.majlis_participant_id}"
                fallback_identifier = row.majlis_participant.phone if row.majlis_participant else '-'
                fallback_label = 'Kontak'
            elif row.student_id:
                key = f"S-{row.student_id}"
                fallback_name = row.student.full_name if row.student else f"Siswa #{row.student_id}"
                fallback_identifier = row.student.nis if row.student else '-'
                fallback_label = 'NIS'
            else:
                key = None
                fallback_name = None
                fallback_identifier = '-'
                fallback_label = '-'

            if key:
                bucket = participant_summary_map.get(key)
                if bucket is None:
                    bucket = {
                        'key': key,
                        'display_name': fallback_name,
                        'identifier': fallback_identifier,
                        'identifier_label': fallback_label,
                        'hadir': 0,
                        'sakit': 0,
                        'izin': 0,
                        'alpa': 0,
                        'total': 0,
                    }
                    participant_summary_map[key] = bucket
                bucket['total'] += 1

            if row.status == AttendanceStatus.HADIR:
                class_recap['hadir'] += 1
                if key:
                    participant_summary_map[key]['hadir'] += 1
            elif row.status == AttendanceStatus.SAKIT:
                class_recap['sakit'] += 1
                if key:
                    participant_summary_map[key]['sakit'] += 1
            elif row.status == AttendanceStatus.IZIN:
                class_recap['izin'] += 1
                if key:
                    participant_summary_map[key]['izin'] += 1
            elif row.status == AttendanceStatus.ALPA:
                class_recap['alpa'] += 1
                if key:
                    participant_summary_map[key]['alpa'] += 1

        participant_summary_rows = sorted(
            participant_summary_map.values(),
            key=lambda item: (item.get('display_name') or '').lower()
        )

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
        participant_summary_rows=participant_summary_rows,
        class_recap=class_recap,
        participant_recap=participant_recap
    )


@teacher_bp.route('/input-tahfidz', methods=['GET', 'POST'])
@login_required
@role_required(UserRole.GURU)
def input_tahfidz():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    my_classes = _get_teacher_tahfidz_classes(teacher)
    my_class_ids = {class_room.id for class_room in my_classes}

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = _teacher_classroom_by_id(teacher, selected_class_id)
        if (
            selected_class
            and selected_class_id in my_class_ids
            and _teacher_can_access_tahfidz_class(teacher, selected_class_id)
        ):
            students, majlis_participants = _get_class_participants(selected_class_id)
        else:
            flash("Anda tidak memiliki akses ke halaqoh tersebut.", "danger")
            selected_class = None

    if request.method == 'POST':
        form_class_id = request.form.get('class_id', type=int)
        active_class_id = form_class_id or selected_class_id
        if (
            not active_class_id
            or active_class_id not in my_class_ids
            or not _teacher_can_access_tahfidz_class(teacher, active_class_id)
        ):
            flash("Kelas tidak valid atau Anda tidak memiliki akses.", "danger")
            return redirect(url_for('teacher.input_tahfidz'))

        participant_type, participant_id = _parse_participant_key(request.form.get('student_id'))
        jenis_setoran = request.form.get('jenis_setoran') or request.form.get('type')  # backward-compatible

        start_surah = request.form.get('start_surah_name')
        end_surah = request.form.get('end_surah_name')
        ayat_start = request.form.get('ayat_start')
        ayat_end = request.form.get('ayat_end')
        notes = request.form.get('notes')

        if not start_surah or not ayat_start or not ayat_end:
            flash("Surat dan ayat wajib diisi.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))

        try:
            final_ayat_start = int(ayat_start)
            final_ayat_end = int(ayat_end)
            tajwid_errors = int(request.form.get('tajwid_errors') or 0)
            makhraj_errors = int(request.form.get('makhraj_errors') or 0)
            tahfidz_errors = int(request.form.get('tahfidz_errors') or 0)
        except ValueError:
            flash("Ayat dan jumlah kesalahan harus berupa angka.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))

        if final_ayat_start < 1 or final_ayat_end < 1:
            flash("Ayat awal/akhir minimal bernilai 1.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))

        # Validasi urutan ayat hanya berlaku jika surat awal dan akhir sama.
        is_same_surah = (not end_surah) or (start_surah == end_surah)
        if is_same_surah and final_ayat_end < final_ayat_start:
            flash("Ayat akhir tidak boleh lebih kecil dari ayat awal jika suratnya sama.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))

        if not participant_id or not participant_type:
            flash("Silakan pilih peserta terlebih dahulu.", "warning")
            return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))

        student_id = participant_id if participant_type == ParticipantType.STUDENT else None
        majlis_participant_id = participant_id if participant_type == ParticipantType.EXTERNAL_MAJLIS else None

        if jenis_setoran not in [t.name for t in TahfidzType]:
            flash("Jenis setoran tidak valid.", "danger")
            return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))

        if participant_type == ParticipantType.STUDENT:
            student = Student.query.filter_by(id=student_id, is_deleted=False).first()
            if not student:
                flash("Data siswa tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))
            if not _student_belongs_to_class(student, active_class_id):
                flash("Siswa tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))
        else:
            participant = MajlisParticipant.query.filter_by(id=majlis_participant_id, is_deleted=False).first()
            if not participant:
                flash("Data peserta majlis tidak ditemukan.", "danger")
                return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))
            if participant.majlis_class_id != active_class_id:
                flash("Peserta majlis tidak berada pada kelas yang dipilih.", "danger")
                return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))

        final_surah_name = start_surah if(not end_surah or start_surah == end_surah) else f"{start_surah} - {end_surah}"

        total_errors = tajwid_errors + makhraj_errors + tahfidz_errors
        calculated_score = max(0, 100 - (total_errors * 4))
        score = calculated_score
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
        return redirect(url_for('teacher.input_tahfidz', class_id=active_class_id))

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
    my_class_ids = {class_room.id for class_room in my_classes}

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = _teacher_classroom_by_id(teacher, selected_class_id)
        if (
            selected_class
            and selected_class_id in my_class_ids
            and _teacher_can_access_tahfidz_class(teacher, selected_class_id)
        ):
            students, majlis_participants = _get_class_participants(selected_class_id)
        else:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            selected_class = None

    if request.method == 'POST':
        form_class_id = request.form.get('class_id', type=int)
        participant_type, participant_id = _parse_participant_key(request.form.get('student_id'))
        recitation_source = request.form.get('recitation_source', 'QURAN')

        active_class_id = form_class_id or selected_class_id
        if (
            not active_class_id
            or active_class_id not in my_class_ids
            or not _teacher_can_access_tahfidz_class(teacher, active_class_id)
        ):
            flash("Kelas tidak valid atau Anda tidak memiliki akses.", "danger")
            return redirect(url_for('teacher.input_recitation'))

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

        score = max(0, 100 - ((tajwid_errors + makhraj_errors) * 4))

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
    my_class_ids = {class_room.id for class_room in my_classes}

    selected_class_id = request.args.get('class_id', type=int)
    students = []
    majlis_participants = []
    selected_class = None

    if selected_class_id:
        selected_class = _teacher_classroom_by_id(teacher, selected_class_id)
        if (
            selected_class
            and selected_class_id in my_class_ids
            and _teacher_can_access_tahfidz_class(teacher, selected_class_id)
        ):
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
        if (
            not active_class_id
            or active_class_id not in my_class_ids
            or not _teacher_can_access_tahfidz_class(teacher, active_class_id)
        ):
            flash("Kelas tidak valid atau Anda tidak memiliki akses.", "danger")
            return redirect(url_for('teacher.input_tahfidz_evaluation'))

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
        average_score = round(sum(item['score'] for item in normalized_questions) / question_count, 2)
        total_errors = makhraj_errors + tajwid_errors + harakat_errors + tahfidz_errors
        score = round(max(0, average_score - (total_errors * 4)), 2)
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
    my_class_ids = {class_room.id for class_room in my_classes}
    selected_class_id = request.args.get('class_id', type=int)
    query = (request.args.get('q') or '').strip()

    selected_class = None
    students = []
    recent_reports = []
    behavior_indicators = _behavior_indicator_items()

    if selected_class_id:
        selected_class = _teacher_classroom_by_id(teacher, selected_class_id)
        if selected_class and selected_class_id in my_class_ids:
            students, _ = _get_class_participants(selected_class_id)
            if query:
                normalized_query = query.lower()
                students = [
                    student for student in students
                    if normalized_query in (student.full_name or "").lower()
                    or normalized_query in (student.nis or "").lower()
                ]
            students = sorted(students, key=lambda student: (student.full_name or "").lower())

            recent_reports = BehaviorReport.query.filter(
                BehaviorReport.student_id.in_([s.id for s in students]),
                BehaviorReport.indicator_key.isnot(None)
            ) \
                .order_by(BehaviorReport.report_date.desc(), BehaviorReport.created_at.desc()).limit(30).all() if students else []
        else:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            selected_class = None

    if request.method == 'POST':
        class_id = request.form.get('class_id', type=int)
        student_id = request.form.get('student_id', type=int)
        report_date_str = request.form.get('report_date')
        notes = (request.form.get('notes') or '').strip()
        action_plan = (request.form.get('action_plan') or '').strip()

        if not class_id or not student_id:
            flash("Data laporan belum lengkap.", "warning")
            return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

        class_room = _teacher_classroom_by_id(teacher, class_id)
        if class_room is None or class_id not in my_class_ids:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            return redirect(url_for('teacher.input_behavior_report'))

        student = Student.query.filter_by(id=student_id, is_deleted=False).first()
        if not student or not _student_belongs_to_class(student, class_id):
            flash("Siswa tidak ditemukan pada kelas yang dipilih.", "danger")
            return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

        try:
            report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date() if report_date_str else local_today()
        except ValueError:
            flash("Format tanggal tidak valid.", "warning")
            return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

        created_count = 0
        for indicator in behavior_indicators:
            raw_choice = (request.form.get(f"ind_{indicator['key']}") or '').strip().lower()
            is_yes = raw_choice == 'yes'
            report_type = BehaviorReportType.POSITIVE if indicator['group'] == 'positive' else BehaviorReportType.CONCERN
            description = notes or (
                f"Observasi indikator sikap '{indicator['label']}': {'YA' if is_yes else 'TIDAK'}."
            )

            db.session.add(BehaviorReport(
                student_id=student.id,
                teacher_id=teacher.id,
                class_id=class_id,
                report_date=report_date,
                report_type=report_type,
                indicator_key=indicator['key'],
                indicator_group=indicator['group'],
                is_yes=is_yes,
                title=indicator['label'],
                description=description,
                action_plan=action_plan or None,
                follow_up_date=None,
                is_resolved=False
            ))
            created_count += 1
        db.session.commit()
        flash(f"Observasi perilaku berhasil disimpan ({created_count} indikator).", "success")
        return redirect(url_for('teacher.input_behavior_report', class_id=class_id))

    return render_template(
        'teacher/input_behavior.html',
        my_classes=my_classes,
        selected_class=selected_class,
        students=students,
        recent_reports=recent_reports,
        behavior_indicators=behavior_indicators,
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

        target_class = _teacher_classroom_by_id(teacher, class_id) if class_id else None
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
        if selected_class_id not in my_class_ids:
            flash("Anda tidak memiliki akses ke kelas tersebut.", "danger")
            return redirect(url_for('teacher.class_announcements'))
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
    homeroom_classes = _get_teacher_homeroom_classes(teacher)

    if not homeroom_classes:
        flash("Anda belum ditugaskan sebagai wali kelas.", "warning")
        return redirect(url_for('teacher.dashboard'))

    selected_class_id = request.args.get('class_id', type=int) or homeroom_classes[0].id
    selected_class = next((c for c in homeroom_classes if c.id == selected_class_id), homeroom_classes[0])
    selected_period_type = (request.args.get('period_type') or 'SEMESTER').strip().upper()
    selected_year_name = (request.args.get('year_name') or '').strip()
    selected_period_academic_year_id = request.args.get('academic_year_id', type=int)

    students, majlis_participants = _get_class_participants(selected_class.id)
    students = sorted(students, key=lambda row: row.full_name or '')
    student_ids = [row.id for row in students]

    period_scope = _resolve_homeroom_report_period(
        period_type_raw=selected_period_type,
        academic_year_id_raw=selected_period_academic_year_id,
        year_name_raw=selected_year_name
    )
    selected_academic_year = period_scope['selected_academic_year']
    selected_year_name = period_scope['selected_year_name']
    selected_period_type = period_scope['period_type']
    selected_year_ids = period_scope['academic_year_ids'] or []
    behavior_start_date = period_scope['start_date']
    behavior_end_date = period_scope['end_date']

    grade_rows_by_student = defaultdict(list)
    attendance_rows_by_student = defaultdict(list)
    behavior_rows_by_student = defaultdict(list)

    if student_ids:
        grade_query = Grade.query.filter(
            Grade.is_deleted.is_(False),
            Grade.participant_type == ParticipantType.STUDENT,
            Grade.student_id.in_(student_ids)
        )
        if selected_year_ids:
            grade_query = grade_query.filter(Grade.academic_year_id.in_(selected_year_ids))
        else:
            grade_query = grade_query.filter(False)
        for row in grade_query.order_by(Grade.created_at.desc(), Grade.id.desc()).all():
            grade_rows_by_student[row.student_id].append(row)

        attendance_query = Attendance.query.filter(
            Attendance.is_deleted.is_(False),
            Attendance.class_id == selected_class.id,
            Attendance.participant_type == ParticipantType.STUDENT,
            Attendance.student_id.in_(student_ids)
        )
        if selected_year_ids:
            attendance_query = attendance_query.filter(Attendance.academic_year_id.in_(selected_year_ids))
        else:
            attendance_query = attendance_query.filter(False)
        for row in attendance_query.order_by(Attendance.date.desc(), Attendance.created_at.desc()).all():
            attendance_rows_by_student[row.student_id].append(row)

        behavior_rows = (
            BehaviorReport.query.filter(
                BehaviorReport.is_deleted.is_(False),
                BehaviorReport.student_id.in_(student_ids)
            )
            .order_by(BehaviorReport.report_date.desc(), BehaviorReport.created_at.desc())
            .all()
        )
        if behavior_start_date:
            behavior_rows = [row for row in behavior_rows if row.report_date and row.report_date >= behavior_start_date]
        if behavior_end_date:
            behavior_rows = [row for row in behavior_rows if row.report_date and row.report_date <= behavior_end_date]
        for row in behavior_rows:
            behavior_rows_by_student[row.student_id].append(row)

    student_report_rows = []
    for row in students:
        academic_report = _academic_report_payload_for_homeroom(grade_rows_by_student.get(row.id, []), include_history=False)
        attendance_report = _attendance_report_payload_for_homeroom(
            attendance_rows_by_student.get(row.id, []),
            include_history=False
        )
        behavior_summary = _behavior_summary_from_indicator_rows(behavior_rows_by_student.get(row.id, []))
        student_report_rows.append({
            'id': row.id,
            'nis': row.nis or '-',
            'name': row.full_name or '-',
            'gender': row.gender.value if row.gender else '-',
            'parent_phone': row.parent.phone if row.parent and row.parent.phone else '-',
            'academic': {
                'grade_count': academic_report['grade_count'],
                'subject_count': academic_report['subject_count'],
                'final_average': academic_report['final_average'],
            },
            'attendance': {
                **attendance_report['recap'],
                'attendance_rate': attendance_report['attendance_rate'],
            },
            'behavior': behavior_summary,
        })

    return render_template('teacher/homeroom_students.html',
                         teacher=teacher,
                         students=students,
                         student_report_rows=student_report_rows,
                         selected_academic_year=selected_academic_year,
                         selected_period_type=selected_period_type,
                         selected_year_name=selected_year_name,
                         period_options=period_scope['period_options'],
                         majlis_participants=majlis_participants,
                         homeroom_class=selected_class,
                         homeroom_classes=homeroom_classes)


@teacher_bp.route('/siswa-wali-kelas/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def homeroom_student_detail(student_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    homeroom_classes = _get_teacher_homeroom_classes(teacher)

    if not homeroom_classes:
        flash("Anda belum ditugaskan sebagai wali kelas.", "warning")
        return redirect(url_for('teacher.dashboard'))

    selected_class_id = request.args.get('class_id', type=int) or homeroom_classes[0].id
    selected_class = next((c for c in homeroom_classes if c.id == selected_class_id), homeroom_classes[0])
    selected_period_type = (request.args.get('period_type') or 'SEMESTER').strip().upper()
    selected_year_name = (request.args.get('year_name') or '').strip()
    selected_period_academic_year_id = request.args.get('academic_year_id', type=int)
    history_limit = max(20, min(400, request.args.get('history_limit', type=int) or 120))

    students, _ = _get_class_participants(selected_class.id)
    students = sorted(students, key=lambda row: row.full_name or '')
    selected_student = next((row for row in students if row.id == student_id), None)
    if selected_student is None:
        flash("Siswa tidak berada pada kelas perwalian yang dipilih.", "danger")
        return redirect(url_for('teacher.homeroom_students', class_id=selected_class.id))

    period_scope = _resolve_homeroom_report_period(
        period_type_raw=selected_period_type,
        academic_year_id_raw=selected_period_academic_year_id,
        year_name_raw=selected_year_name
    )
    selected_academic_year = period_scope['selected_academic_year']
    selected_year_name = period_scope['selected_year_name']
    selected_period_type = period_scope['period_type']
    selected_year_ids = period_scope['academic_year_ids'] or []
    behavior_start_date = period_scope['start_date']
    behavior_end_date = period_scope['end_date']

    grade_query = Grade.query.filter(
        Grade.is_deleted.is_(False),
        Grade.participant_type == ParticipantType.STUDENT,
        Grade.student_id == selected_student.id
    )
    if selected_year_ids:
        grade_query = grade_query.filter(Grade.academic_year_id.in_(selected_year_ids))
    else:
        grade_query = grade_query.filter(False)
    selected_grade_rows = grade_query.order_by(Grade.created_at.desc(), Grade.id.desc()).all()

    attendance_query = Attendance.query.filter(
        Attendance.is_deleted.is_(False),
        Attendance.class_id == selected_class.id,
        Attendance.participant_type == ParticipantType.STUDENT,
        Attendance.student_id == selected_student.id
    )
    if selected_year_ids:
        attendance_query = attendance_query.filter(Attendance.academic_year_id.in_(selected_year_ids))
    else:
        attendance_query = attendance_query.filter(False)
    selected_attendance_rows = attendance_query.order_by(Attendance.date.desc(), Attendance.created_at.desc()).all()

    academic_report = _academic_report_payload_for_homeroom(
        selected_grade_rows,
        include_history=True,
        history_limit=history_limit
    )
    attendance_report = _attendance_report_payload_for_homeroom(
        selected_attendance_rows,
        include_history=True,
        history_limit=history_limit
    )
    behavior_report = _behavior_matrix_for_student(
        student_id=selected_student.id,
        class_id=selected_class.id,
        academic_year_ids=selected_year_ids,
        start_date=behavior_start_date,
        end_date=behavior_end_date,
        history_limit=history_limit
    )

    latest_behavior_note = '-'
    for history_row in behavior_report.get('history_rows') or []:
        note = (history_row.get('notes') or '').strip()
        if note and note != '-':
            latest_behavior_note = note
            break

    tahfidz_rows = (
        TahfidzRecord.query.filter(
            TahfidzRecord.is_deleted.is_(False),
            TahfidzRecord.participant_type == ParticipantType.STUDENT,
            TahfidzRecord.student_id == selected_student.id
        )
        .order_by(TahfidzRecord.date.desc(), TahfidzRecord.id.desc())
        .limit(history_limit)
        .all()
    )
    recitation_rows = (
        RecitationRecord.query.filter(
            RecitationRecord.is_deleted.is_(False),
            RecitationRecord.participant_type == ParticipantType.STUDENT,
            RecitationRecord.student_id == selected_student.id
        )
        .order_by(RecitationRecord.date.desc(), RecitationRecord.id.desc())
        .limit(history_limit)
        .all()
    )
    evaluation_rows = (
        TahfidzEvaluation.query.filter(
            TahfidzEvaluation.is_deleted.is_(False),
            TahfidzEvaluation.participant_type == ParticipantType.STUDENT,
            TahfidzEvaluation.student_id == selected_student.id
        )
        .order_by(TahfidzEvaluation.date.desc(), TahfidzEvaluation.id.desc())
        .limit(history_limit)
        .all()
    )
    quran_report = _quran_report_payload_for_homeroom(tahfidz_rows, recitation_rows, evaluation_rows)

    return render_template(
        'teacher/homeroom_student_detail.html',
        teacher=teacher,
        homeroom_class=selected_class,
        homeroom_classes=homeroom_classes,
        selected_period_type=selected_period_type,
        selected_academic_year=selected_academic_year,
        selected_year_name=selected_year_name,
        period_options=period_scope['period_options'],
        student={
            'id': selected_student.id,
            'nis': selected_student.nis or '-',
            'name': selected_student.full_name or '-',
            'gender': selected_student.gender.value if selected_student.gender else '-',
            'parent_phone': selected_student.parent.phone if selected_student.parent and selected_student.parent.phone else '-',
        },
        academic=academic_report,
        attendance=attendance_report,
        behavior=behavior_report,
        latest_behavior_note=latest_behavior_note,
        quran=quran_report
    )


@teacher_bp.route('/hitung-nilai-siswa/<int:student_id>')
@login_required
@role_required(UserRole.GURU)
def calculate_student_grades(student_id):
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    student = Student.query.filter_by(id=student_id, is_deleted=False).first_or_404()
    
    # Cek akses
    my_classes = _get_teacher_classes(teacher)
    if not any(_student_belongs_to_class(student, class_room.id) for class_room in my_classes):
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
    homeroom_classes = _get_teacher_homeroom_classes(teacher)

    if not homeroom_classes:
        flash("Hanya wali kelas yang dapat mencetak raport.", "danger")
        return redirect(url_for('teacher.dashboard'))
    
    student = Student.query.filter_by(id=student_id, is_deleted=False).first_or_404()
    if not any(_student_belongs_to_class(student, class_room.id) for class_room in homeroom_classes):
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
    student = Student.query.filter_by(id=student_id, is_deleted=False).first_or_404()

    my_classes = _get_teacher_classes(teacher)
    if not any(_student_belongs_to_class(student, class_room.id) for class_room in my_classes):
        flash("Anda tidak memiliki akses ke siswa tersebut.", "danger")
        return redirect(url_for('teacher.dashboard'))
    
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
    my_classes = _get_teacher_attendance_classes(teacher)
    my_class_ids = {class_room.id for class_room in my_classes}
    
    selected_class_id = request.args.get('class_id', type=int)
    selected_date = request.args.get('date', local_today().strftime('%Y-%m-%d'))
    
    students = []
    majlis_participants = []
    participants = []
    selected_class = None
    existing_attendance = {}
    
    if selected_class_id:
        selected_class = _teacher_classroom_by_id(teacher, selected_class_id)
        if selected_class and selected_class_id in my_class_ids:
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
        if (
            not selected_class_id
            or selected_class_id not in my_class_ids
            or not _teacher_can_access_attendance_class(teacher, selected_class_id)
        ):
            flash("Kelas tidak valid atau Anda tidak memiliki akses.", "danger")
            return redirect(url_for('teacher.input_attendance'))
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

