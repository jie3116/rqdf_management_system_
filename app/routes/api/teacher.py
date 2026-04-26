import json
from collections import defaultdict
from datetime import datetime

from flask import g, request

from app.extensions import db
from app.models import (
    AcademicYear,
    Announcement,
    Attendance,
    AttendanceStatus,
    BehaviorReport,
    BehaviorReportType,
    BoardingAttendance,
    EvaluationPeriod,
    Grade,
    GradeType,
    MajlisSubject,
    ParticipantType,
    RecitationRecord,
    RecitationSource,
    Schedule,
    Subject,
    TahfidzEvaluation,
    TahfidzRecord,
    TahfidzSummary,
    TahfidzType,
    Teacher,
    UserRole,
)
from app.routes.teacher import (
    _build_participant_rows,
    _classroom_visible_for_teacher,
    _collect_teacher_assignment_summary,
    _get_class_participants,
    _get_teacher_attendance_classes,
    _get_teacher_classes,
    _get_teacher_homeroom_classes,
    _get_teacher_tahfidz_classes,
    _resolve_selected_participant,
    _teacher_can_access_attendance_class,
    _teacher_can_access_class,
    _teacher_can_access_tahfidz_class,
)
from app.utils.announcements import get_announcements_for_dashboard
from app.utils.timezone import local_day_bounds_utc_naive, local_today, utc_now_naive

from .common import (
    DAY_NAMES,
    ORDERED_DAYS,
    announcement_payload,
    api_error,
    api_success,
    fmt_date,
    fmt_datetime,
    fmt_time,
    mobile_auth_required,
    participant_name_from_record,
    user_display_name,
)


def _teacher_from_mobile_user():
    user = g.mobile_user
    teacher = Teacher.query.filter_by(user_id=user.id).first()
    return user, teacher


def _class_payload(class_room):
    return {"id": class_room.id, "name": class_room.name or "-"}


def _classes_payload(classrooms):
    return [_class_payload(item) for item in sorted(classrooms, key=lambda row: row.name or "")]


def _selected_class(classrooms, class_id):
    if class_id:
        return next((row for row in classrooms if row.id == class_id), None)
    return classrooms[0] if classrooms else None


def _safe_parse_date(raw_value):
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _safe_parse_int(raw_value, default=0):
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def _safe_parse_float(raw_value, default=0.0):
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def _bool_value(raw_value):
    if isinstance(raw_value, bool):
        return raw_value
    return str(raw_value or "").strip().lower() in {"1", "true", "yes", "on"}


def _calculate_weighted_final(type_averages):
    weights = {"TUGAS": 0.3, "UH": 0.2, "UTS": 0.25, "UAS": 0.25}
    weighted = 0.0
    total_weight = 0.0
    for grade_type, average in (type_averages or {}).items():
        weight = float(weights.get(grade_type, 0))
        if weight <= 0:
            continue
        weighted += float(average) * weight
        total_weight += weight
    if total_weight <= 0:
        return 0
    return round(weighted / total_weight, 2)


def _participant_name_from_attendance(record):
    if record.participant_type == ParticipantType.EXTERNAL_MAJLIS and record.majlis_participant:
        return record.majlis_participant.full_name or "-"
    if record.student:
        return record.student.full_name or "-"
    return "-"


def _class_participants_for_api(user, class_id):
    students, majlis_participants = _get_class_participants(class_id, tenant_id=user.tenant_id)
    participants = _build_participant_rows(students, majlis_participants)
    return students, majlis_participants, participants


def _teacher_total_students(user, classes):
    student_ids = set()
    for class_room in classes:
        students, _, _ = _class_participants_for_api(user, class_room.id)
        for student in students:
            student_ids.add(student.id)
    return len(student_ids)


def _subject_options_for_class(teacher, class_id):
    subject_options = []
    majlis_subject_options = []
    class_schedules = (
        Schedule.query.filter(
            Schedule.teacher_id == teacher.id,
            Schedule.class_id == class_id,
        )
        .order_by(Schedule.day.asc(), Schedule.start_time.asc(), Schedule.id.asc())
        .all()
    )
    seen_subject_ids = set()
    seen_majlis_subject_ids = set()
    for schedule in class_schedules:
        if schedule.subject_id and schedule.subject and schedule.subject_id not in seen_subject_ids:
            seen_subject_ids.add(schedule.subject_id)
            subject_options.append(schedule.subject)
        if (
            schedule.majlis_subject_id
            and schedule.majlis_subject
            and schedule.majlis_subject_id not in seen_majlis_subject_ids
        ):
            seen_majlis_subject_ids.add(schedule.majlis_subject_id)
            majlis_subject_options.append(schedule.majlis_subject)
    return subject_options, majlis_subject_options


def _recent_tahfidz_payload(rows):
    return [
        {
            "id": row.id,
            "participant_name": participant_name_from_record(row),
            "surah": row.surah or "-",
            "ayat_start": row.ayat_start or "-",
            "ayat_end": row.ayat_end or "-",
            "type": row.type.name if row.type else "-",
            "type_label": row.type.value if row.type else "-",
            "score": row.score or 0,
            "date": fmt_datetime(row.date),
        }
        for row in rows
    ]


def _recent_recitation_payload(rows):
    return [
        {
            "id": row.id,
            "participant_name": participant_name_from_record(row),
            "recitation_source": row.recitation_source.name if row.recitation_source else "-",
            "recitation_source_label": row.recitation_source.value if row.recitation_source else "-",
            "surah": row.surah or "-",
            "ayat_start": row.ayat_start or "-",
            "ayat_end": row.ayat_end or "-",
            "book_name": row.book_name or "-",
            "page_start": row.page_start or "-",
            "page_end": row.page_end or "-",
            "score": row.score or 0,
            "date": fmt_datetime(row.date),
        }
        for row in rows
    ]


def _recent_evaluation_payload(rows):
    return [
        {
            "id": row.id,
            "participant_name": participant_name_from_record(row),
            "period_type": row.period_type.name if row.period_type else "-",
            "period_type_label": row.period_type.value if row.period_type else "-",
            "period_label": row.period_label or "-",
            "question_count": row.question_count or 0,
            "question_details": row.question_details or "-",
            "question_items": json.loads(row.question_items or "[]") if row.question_items else [],
            "score": row.score or 0,
            "notes": row.notes or "-",
            "date": fmt_datetime(row.date),
        }
        for row in rows
    ]


def register_teacher_routes(api_bp):
    @api_bp.get("/teacher/dashboard")
    @mobile_auth_required(UserRole.GURU)
    def teacher_dashboard():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        my_classes = _get_teacher_classes(teacher)
        homeroom_classes = _get_teacher_homeroom_classes(teacher)
        total_students = _teacher_total_students(user, my_classes) if my_classes else 0
        homeroom_class = homeroom_classes[0] if homeroom_classes else None
        _, teaching_assignments = _collect_teacher_assignment_summary(teacher)

        today = local_today()
        today_name = DAY_NAMES[today.weekday()]
        today_start_utc, today_end_utc = local_day_bounds_utc_naive(today)

        todays_schedules = (
            Schedule.query.filter_by(teacher_id=teacher.id, day=today_name)
            .order_by(Schedule.start_time.asc())
            .all()
        )
        todays_schedules = [
            item for item in todays_schedules if _classroom_visible_for_teacher(teacher, item.class_room)
        ]

        today_tahfidz_count = TahfidzRecord.query.filter(
            TahfidzRecord.teacher_id == teacher.id,
            TahfidzRecord.date >= today_start_utc,
            TahfidzRecord.date < today_end_utc,
        ).count()
        today_recitation_count = RecitationRecord.query.filter(
            RecitationRecord.teacher_id == teacher.id,
            RecitationRecord.date >= today_start_utc,
            RecitationRecord.date < today_end_utc,
        ).count()
        today_evaluation_count = TahfidzEvaluation.query.filter(
            TahfidzEvaluation.teacher_id == teacher.id,
            TahfidzEvaluation.date >= today_start_utc,
            TahfidzEvaluation.date < today_end_utc,
        ).count()

        recent_tahfidz = (
            TahfidzRecord.query.filter_by(teacher_id=teacher.id)
            .order_by(TahfidzRecord.date.desc())
            .limit(5)
            .all()
        )
        recent_recitation = (
            RecitationRecord.query.filter_by(teacher_id=teacher.id)
            .order_by(RecitationRecord.date.desc())
            .limit(5)
            .all()
        )

        boarding_student_ids = set()
        for class_room in my_classes:
            students, _, _ = _class_participants_for_api(user, class_room.id)
            for student in students:
                if student.boarding_dormitory_id:
                    boarding_student_ids.add(student.id)

        boarding_stats = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0, "belum_input": 0}
        if boarding_student_ids:
            records = BoardingAttendance.query.filter(
                BoardingAttendance.date == today,
                BoardingAttendance.student_id.in_(list(boarding_student_ids)),
            ).all()
            seen_student_ids = set()
            for record in records:
                seen_student_ids.add(record.student_id)
                if record.status == AttendanceStatus.HADIR:
                    boarding_stats["hadir"] += 1
                elif record.status == AttendanceStatus.SAKIT:
                    boarding_stats["sakit"] += 1
                elif record.status == AttendanceStatus.IZIN:
                    boarding_stats["izin"] += 1
                elif record.status == AttendanceStatus.ALPA:
                    boarding_stats["alpa"] += 1
            boarding_stats["belum_input"] = max(0, len(boarding_student_ids) - len(seen_student_ids))

        class_programs = [item.program_type.name for item in my_classes if item and item.program_type]
        announcements, unread_count = get_announcements_for_dashboard(
            user,
            class_ids=[item.id for item in my_classes],
            user_ids=[user.id],
            program_types=class_programs,
            show_all=False,
        )

        if homeroom_class:
            homeroom_students, homeroom_majlis, _ = _class_participants_for_api(user, homeroom_class.id)
            homeroom_payload = {
                "available": True,
                "class_id": homeroom_class.id,
                "class_name": homeroom_class.name or "-",
                "student_count": len(homeroom_students),
                "majlis_count": len(homeroom_majlis),
                "menu": [
                    {
                        "key": "homeroom_students",
                        "label": "Data Peserta",
                        "description": "Lihat data siswa dan peserta aktif kelas perwalian.",
                    },
                    {
                        "key": "class_announcements",
                        "label": "Pengumuman Kelas",
                        "description": "Kelola pengumuman khusus untuk kelas perwalian.",
                    },
                    {
                        "key": "behavior_reports",
                        "label": "Laporan Perilaku",
                        "description": "Catat perkembangan perilaku siswa kelas perwalian.",
                    },
                ],
            }
        else:
            homeroom_payload = {
                "available": False,
                "class_id": 0,
                "class_name": "-",
                "student_count": 0,
                "majlis_count": 0,
                "menu": [],
            }

        return api_success(
            {
                "profile": {
                    "id": teacher.id,
                    "full_name": teacher.full_name or user_display_name(user),
                    "nip": teacher.nip or "-",
                    "homeroom_class_name": homeroom_class.name if homeroom_class else "Tidak Menjabat",
                    "total_classes": len(my_classes),
                    "total_students": total_students,
                },
                "summary": {
                    "today_schedule_count": len(todays_schedules),
                    "homeroom_label": homeroom_class.name if homeroom_class else "Tidak Menjabat",
                    "today_tahfidz_count": today_tahfidz_count,
                    "today_recitation_count": today_recitation_count,
                    "today_evaluation_count": today_evaluation_count,
                    "boarding": boarding_stats,
                },
                "announcements": [announcement_payload(item) for item in announcements],
                "unread_announcements_count": unread_count,
                "today_name": today_name,
                "today_schedules": [
                    {
                        "id": item.id,
                        "class_id": item.class_id or 0,
                        "class_name": item.class_room.name if item.class_room else "-",
                        "subject_id": item.subject_id or 0,
                        "majlis_subject_id": item.majlis_subject_id or 0,
                        "subject_name": (
                            item.subject.name if item.subject else (item.majlis_subject.name if item.majlis_subject else "-")
                        ),
                        "start_time": fmt_time(item.start_time),
                        "end_time": fmt_time(item.end_time),
                    }
                    for item in todays_schedules
                ],
                "teaching_assignments": [
                    {
                        "class_id": class_id,
                        "class_name": class_name,
                        "subject_id": subject_id or 0,
                        "majlis_subject_id": majlis_subject_id or 0,
                        "subject_name": subject_name or "-",
                    }
                    for class_id, class_name, subject_id, majlis_subject_id, subject_name in teaching_assignments
                ],
                "class_options": _classes_payload(my_classes),
                "input_menu": [
                    {"key": "nilai", "label": "Input Nilai", "description": "Input nilai mapel untuk kelas yang diajar."},
                    {"key": "absensi", "label": "Input Absensi", "description": "Catat kehadiran peserta per kelas."},
                    {"key": "perilaku", "label": "Laporan Perilaku", "description": "Input catatan perilaku siswa."},
                    {"key": "tahfidz", "label": "Input Tahfidz", "description": "Input setoran hafalan tahfidz."},
                    {"key": "bacaan", "label": "Input Bacaan", "description": "Input setoran bacaan Al-Quran/kitab."},
                    {"key": "evaluasi", "label": "Evaluasi Tahfidz", "description": "Input evaluasi periodik tahfidz."},
                ],
                "recent_tahfidz": [
                    {
                        "id": item.id,
                        "participant_name": participant_name_from_record(item),
                        "date": fmt_datetime(item.date),
                        "detail": f"{item.surah or '-'} ({item.ayat_start or '-'}-{item.ayat_end or '-'})",
                        "score": item.score or 0,
                    }
                    for item in recent_tahfidz
                ],
                "recent_recitation": [
                    {
                        "id": item.id,
                        "participant_name": participant_name_from_record(item),
                        "date": fmt_datetime(item.date),
                        "detail": item.book_name or item.surah or "-",
                        "score": item.score or 0,
                    }
                    for item in recent_recitation
                ],
                "history_menu": [
                    {"key": "riwayat_nilai", "label": "Riwayat Nilai", "description": "Lihat histori input nilai per kelas."},
                    {"key": "riwayat_absensi", "label": "Riwayat Absensi", "description": "Lihat histori absensi yang telah diinput."},
                ],
                "homeroom": homeroom_payload,
            }
        )

    @api_bp.get("/teacher/input-grades")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_grades_form():
        _, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_classes(teacher)
        if not classes:
            return api_success(
                {
                    "classes": [],
                    "selected_class": {"id": 0, "name": "-"},
                    "participants": [],
                    "grade_types": [],
                    "subject": {},
                    "majlis_subject": {},
                    "subject_options": [],
                    "majlis_subject_options": [],
                }
            )

        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        user = g.mobile_user
        _, _, participants = _class_participants_for_api(user, selected_class.id)
        subject_options, majlis_subject_options = _subject_options_for_class(teacher, selected_class.id)
        valid_subject_ids = {item.id for item in subject_options}
        valid_majlis_subject_ids = {item.id for item in majlis_subject_options}

        selected_subject_id = request.args.get("subject_id", type=int)
        selected_majlis_subject_id = request.args.get("majlis_subject_id", type=int)
        if selected_subject_id not in valid_subject_ids:
            selected_subject_id = subject_options[0].id if subject_options else None
        if selected_majlis_subject_id not in valid_majlis_subject_ids:
            selected_majlis_subject_id = majlis_subject_options[0].id if majlis_subject_options else None
        if selected_subject_id and selected_majlis_subject_id:
            selected_majlis_subject_id = None

        subject = Subject.query.filter_by(id=selected_subject_id).first() if selected_subject_id else None
        majlis_subject = (
            MajlisSubject.query.filter_by(id=selected_majlis_subject_id).first()
            if selected_majlis_subject_id
            else None
        )

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class),
                "participants": participants,
                "grade_types": [
                    {"key": item.name, "label": item.value}
                    for item in GradeType
                    if item.name != "SIKAP"
                ],
                "subject": {"id": subject.id, "name": subject.name} if subject else {},
                "majlis_subject": (
                    {"id": majlis_subject.id, "name": majlis_subject.name} if majlis_subject else {}
                ),
                "subject_options": [{"id": item.id, "name": item.name} for item in subject_options],
                "majlis_subject_options": [{"id": item.id, "name": item.name} for item in majlis_subject_options],
            }
        )

    @api_bp.post("/teacher/input-grades")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_grades_submit():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        class_id = _safe_parse_int(payload.get("class_id"), default=0)
        if not class_id or not _teacher_can_access_class(teacher, class_id):
            return api_error("forbidden", "Kelas tidak valid atau tidak dapat diakses.", 403)

        _, _, participants = _class_participants_for_api(user, class_id)
        participant_map = {item["key"]: item for item in participants}
        if not participant_map:
            return api_error("invalid_request", "Belum ada peserta pada kelas tersebut.", 400)

        active_year = AcademicYear.query.filter_by(is_active=True).first()
        if active_year is None:
            return api_error("invalid_state", "Tahun ajaran aktif belum diatur.", 409)

        subject_options, majlis_subject_options = _subject_options_for_class(teacher, class_id)
        valid_subject_ids = {item.id for item in subject_options}
        valid_majlis_subject_ids = {item.id for item in majlis_subject_options}

        subject_id = _safe_parse_int(payload.get("subject_id"), default=0) or None
        majlis_subject_id = _safe_parse_int(payload.get("majlis_subject_id"), default=0) or None
        if subject_id and subject_id not in valid_subject_ids:
            subject_id = None
        if majlis_subject_id and majlis_subject_id not in valid_majlis_subject_ids:
            majlis_subject_id = None
        if subject_id and majlis_subject_id:
            majlis_subject_id = None
        if subject_id is None and majlis_subject_id is None:
            return api_error("invalid_request", "Mata pelajaran belum dipilih.", 400)

        grade_type = (payload.get("grade_type") or "").strip().upper()
        if grade_type not in {item.name for item in GradeType}:
            return api_error("invalid_request", "Tipe nilai tidak valid.", 400)
        if grade_type == "SIKAP":
            return api_error("invalid_request", "Tipe nilai SIKAP tidak didukung pada input mobile ini.", 400)

        raw_scores = payload.get("scores") or []
        if not isinstance(raw_scores, list) or not raw_scores:
            return api_error("invalid_request", "Data nilai belum diisi.", 400)

        notes = (payload.get("notes") or "").strip()
        created_count = 0
        for row in raw_scores:
            if not isinstance(row, dict):
                continue
            participant_key = (row.get("participant_key") or "").strip()
            if participant_key not in participant_map:
                continue
            score_value = _safe_parse_float(row.get("score"), default=-1)
            if score_value < 0:
                continue
            participant = participant_map[participant_key]
            db.session.add(
                Grade(
                    student_id=participant.get("student_id"),
                    majlis_participant_id=participant.get("majlis_participant_id"),
                    participant_type=participant.get("participant_type"),
                    subject_id=subject_id,
                    majlis_subject_id=majlis_subject_id,
                    academic_year_id=active_year.id,
                    teacher_id=teacher.id,
                    type=GradeType[grade_type],
                    score=score_value,
                    notes=notes,
                )
            )
            created_count += 1

        if created_count <= 0:
            return api_error("invalid_request", "Tidak ada nilai valid untuk disimpan.", 400)

        db.session.commit()
        return api_success({"saved_count": created_count}, message="Nilai berhasil disimpan.")

    @api_bp.get("/teacher/input-attendance")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_attendance_form():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_attendance_classes(teacher)
        if not classes:
            return api_success(
                {
                    "classes": [],
                    "selected_class": {"id": 0, "name": "-"},
                    "participants": [],
                    "attendance_statuses": [],
                    "existing_attendance": {},
                }
            )

        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        selected_date_raw = (request.args.get("date") or "").strip()
        selected_date = _safe_parse_date(selected_date_raw) or local_today()

        _, _, participants = _class_participants_for_api(user, selected_class.id)
        existing_rows = (
            Attendance.query.filter(
                Attendance.class_id == selected_class.id,
                Attendance.date == selected_date,
                Attendance.participant_type.in_([ParticipantType.STUDENT, ParticipantType.EXTERNAL_MAJLIS]),
            )
            .order_by(Attendance.id.asc())
            .all()
        )
        existing_attendance = {}
        for row in existing_rows:
            if row.participant_type == ParticipantType.EXTERNAL_MAJLIS and row.majlis_participant_id:
                key = f"M-{row.majlis_participant_id}"
            elif row.student_id:
                key = f"S-{row.student_id}"
            else:
                continue
            existing_attendance[key] = {
                "status": row.status.name if row.status else "-",
                "notes": row.notes or "",
            }

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class),
                "selected_date": selected_date.strftime("%Y-%m-%d"),
                "participants": participants,
                "attendance_statuses": [{"key": item.name, "label": item.value} for item in AttendanceStatus],
                "existing_attendance": existing_attendance,
            }
        )

    @api_bp.post("/teacher/input-attendance")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_attendance_submit():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        class_id = _safe_parse_int(payload.get("class_id"), default=0)
        if not class_id or not _teacher_can_access_attendance_class(teacher, class_id):
            return api_error("forbidden", "Kelas tidak valid atau tidak dapat diakses.", 403)

        attendance_date = _safe_parse_date(payload.get("attendance_date")) or local_today()
        raw_records = payload.get("records") or []
        if not isinstance(raw_records, list) or not raw_records:
            return api_error("invalid_request", "Data absensi belum diisi.", 400)

        _, _, participants = _class_participants_for_api(user, class_id)
        participant_map = {item["key"]: item for item in participants}
        active_year = AcademicYear.query.filter_by(is_active=True).first()
        saved_count = 0

        for row in raw_records:
            if not isinstance(row, dict):
                continue
            participant_key = (row.get("participant_key") or "").strip()
            if participant_key not in participant_map:
                continue
            status_key = (row.get("status") or "").strip().upper()
            if status_key not in {item.name for item in AttendanceStatus}:
                continue
            participant = participant_map[participant_key]
            existing = Attendance.query.filter_by(
                student_id=participant.get("student_id"),
                majlis_participant_id=participant.get("majlis_participant_id"),
                participant_type=participant.get("participant_type"),
                class_id=class_id,
                date=attendance_date,
            ).first()
            if existing:
                existing.status = AttendanceStatus[status_key]
                existing.notes = (row.get("notes") or "").strip()
                if active_year:
                    existing.academic_year_id = active_year.id
            else:
                db.session.add(
                    Attendance(
                        student_id=participant.get("student_id"),
                        majlis_participant_id=participant.get("majlis_participant_id"),
                        participant_type=participant.get("participant_type"),
                        class_id=class_id,
                        teacher_id=teacher.id,
                        academic_year_id=active_year.id if active_year else None,
                        date=attendance_date,
                        status=AttendanceStatus[status_key],
                        notes=(row.get("notes") or "").strip(),
                    )
                )
            saved_count += 1

        if saved_count <= 0:
            return api_error("invalid_request", "Tidak ada data absensi valid untuk disimpan.", 400)

        db.session.commit()
        return api_success({"saved_count": saved_count}, message="Absensi berhasil disimpan.")

    @api_bp.get("/teacher/input-tahfidz")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_tahfidz_form():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_tahfidz_classes(teacher)
        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if classes and selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        participants = []
        recent_records = []
        if selected_class:
            _, _, participants = _class_participants_for_api(user, selected_class.id)
            student_ids = [row.get("student_id") for row in participants if row.get("student_id")]
            majlis_ids = [row.get("majlis_participant_id") for row in participants if row.get("majlis_participant_id")]

            query = TahfidzRecord.query.filter(TahfidzRecord.teacher_id == teacher.id)
            filters = []
            if student_ids:
                filters.append(
                    db.and_(
                        TahfidzRecord.participant_type == ParticipantType.STUDENT,
                        TahfidzRecord.student_id.in_(student_ids),
                    )
                )
            if majlis_ids:
                filters.append(
                    db.and_(
                        TahfidzRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                        TahfidzRecord.majlis_participant_id.in_(majlis_ids),
                    )
                )
            if filters:
                query = query.filter(db.or_(*filters))
                recent_records = query.order_by(TahfidzRecord.date.desc(), TahfidzRecord.id.desc()).limit(30).all()
                recent_records = _recent_tahfidz_payload(recent_records)

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class) if selected_class else {"id": 0, "name": "-"},
                "participants": participants,
                "tahfidz_types": [{"key": item.name, "label": item.value} for item in TahfidzType],
                "recent_records": recent_records,
            }
        )

    @api_bp.post("/teacher/input-tahfidz")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_tahfidz_submit():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        class_id = _safe_parse_int(payload.get("class_id"), default=0)
        if not class_id or not _teacher_can_access_tahfidz_class(teacher, class_id):
            return api_error("forbidden", "Kelas tidak valid atau tidak dapat diakses.", 403)

        _, _, participants = _class_participants_for_api(user, class_id)
        participant_map = {row["key"]: row for row in participants}
        participant_key = (payload.get("participant_key") or "").strip()
        participant = participant_map.get(participant_key)
        if participant is None:
            return api_error("invalid_request", "Peserta tidak valid.", 400)

        tahfidz_type = (payload.get("type") or "").strip().upper()
        if tahfidz_type not in {item.name for item in TahfidzType}:
            return api_error("invalid_request", "Jenis setoran tidak valid.", 400)

        start_surah = (payload.get("start_surah_name") or "").strip()
        end_surah = (payload.get("end_surah_name") or "").strip()
        ayat_start = _safe_parse_int(payload.get("ayat_start"), default=0)
        ayat_end = _safe_parse_int(payload.get("ayat_end"), default=0)
        if not start_surah or ayat_start <= 0 or ayat_end <= 0:
            return api_error("invalid_request", "Surah dan ayat wajib diisi.", 400)
        if (not end_surah or end_surah == start_surah) and ayat_end < ayat_start:
            return api_error("invalid_request", "Ayat akhir tidak boleh lebih kecil dari ayat awal.", 400)

        final_surah_name = start_surah if (not end_surah or end_surah == start_surah) else f"{start_surah} - {end_surah}"
        tajwid_errors = max(0, _safe_parse_int(payload.get("tajwid_errors"), default=0))
        makhraj_errors = max(0, _safe_parse_int(payload.get("makhraj_errors"), default=0))
        tahfidz_errors = max(0, _safe_parse_int(payload.get("tahfidz_errors"), default=0))
        total_errors = tajwid_errors + makhraj_errors + tahfidz_errors
        score = max(0, 100 - (total_errors * 4))

        new_record = TahfidzRecord(
            student_id=participant.get("student_id"),
            majlis_participant_id=participant.get("majlis_participant_id"),
            participant_type=participant.get("participant_type"),
            teacher_id=teacher.id,
            type=TahfidzType[tahfidz_type],
            juz=0,
            surah=final_surah_name,
            ayat_start=ayat_start,
            ayat_end=ayat_end,
            tajwid_errors=tajwid_errors,
            makhraj_errors=makhraj_errors,
            tahfidz_errors=tahfidz_errors,
            score=score,
            quality=(payload.get("quality") or "").strip() or None,
            notes=(payload.get("notes") or "").strip() or None,
            date=utc_now_naive(),
        )
        db.session.add(new_record)

        summary = TahfidzSummary.query.filter_by(
            student_id=participant.get("student_id"),
            majlis_participant_id=participant.get("majlis_participant_id"),
            participant_type=participant.get("participant_type"),
        ).first()
        if summary is None:
            summary = TahfidzSummary(
                student_id=participant.get("student_id"),
                majlis_participant_id=participant.get("majlis_participant_id"),
                participant_type=participant.get("participant_type"),
            )
            db.session.add(summary)
        if tahfidz_type == "ZIYADAH":
            summary.last_surah = final_surah_name
            summary.last_ayat = ayat_end

        db.session.commit()
        return api_success({"record_id": new_record.id}, message="Setoran tahfidz berhasil disimpan.")

    @api_bp.get("/teacher/input-recitation")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_recitation_form():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_tahfidz_classes(teacher)
        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if classes and selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        participants = []
        recent_records = []
        if selected_class:
            _, _, participants = _class_participants_for_api(user, selected_class.id)
            student_ids = [row.get("student_id") for row in participants if row.get("student_id")]
            majlis_ids = [row.get("majlis_participant_id") for row in participants if row.get("majlis_participant_id")]
            query = RecitationRecord.query.filter(RecitationRecord.teacher_id == teacher.id)
            filters = []
            if student_ids:
                filters.append(
                    db.and_(
                        RecitationRecord.participant_type == ParticipantType.STUDENT,
                        RecitationRecord.student_id.in_(student_ids),
                    )
                )
            if majlis_ids:
                filters.append(
                    db.and_(
                        RecitationRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                        RecitationRecord.majlis_participant_id.in_(majlis_ids),
                    )
                )
            if filters:
                query = query.filter(db.or_(*filters))
                recent_records = query.order_by(RecitationRecord.date.desc(), RecitationRecord.id.desc()).limit(30).all()
                recent_records = _recent_recitation_payload(recent_records)

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class) if selected_class else {"id": 0, "name": "-"},
                "participants": participants,
                "recitation_sources": [{"key": item.name, "label": item.value} for item in RecitationSource],
                "recent_records": recent_records,
            }
        )

    @api_bp.post("/teacher/input-recitation")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_recitation_submit():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        class_id = _safe_parse_int(payload.get("class_id"), default=0)
        if not class_id or not _teacher_can_access_tahfidz_class(teacher, class_id):
            return api_error("forbidden", "Kelas tidak valid atau tidak dapat diakses.", 403)

        _, _, participants = _class_participants_for_api(user, class_id)
        participant_map = {row["key"]: row for row in participants}
        participant_key = (payload.get("participant_key") or "").strip()
        participant = participant_map.get(participant_key)
        if participant is None:
            return api_error("invalid_request", "Peserta tidak valid.", 400)

        source = (payload.get("recitation_source") or "").strip().upper()
        if source not in {item.name for item in RecitationSource}:
            return api_error("invalid_request", "Sumber bacaan tidak valid.", 400)

        tajwid_errors = max(0, _safe_parse_int(payload.get("tajwid_errors"), default=0))
        makhraj_errors = max(0, _safe_parse_int(payload.get("makhraj_errors"), default=0))
        score = max(0, 100 - ((tajwid_errors + makhraj_errors) * 4))

        start_surah = (payload.get("start_surah_name") or "").strip()
        end_surah = (payload.get("end_surah_name") or "").strip()
        ayat_start = _safe_parse_int(payload.get("ayat_start"), default=0)
        ayat_end = _safe_parse_int(payload.get("ayat_end"), default=0)
        book_name = (payload.get("book_name") or "").strip()
        page_start = _safe_parse_int(payload.get("page_start"), default=0)
        page_end = _safe_parse_int(payload.get("page_end"), default=0)

        final_surah = None
        final_ayat_start = None
        final_ayat_end = None
        final_page_start = None
        final_page_end = None
        final_book_name = None

        if source == "QURAN":
            if not start_surah or ayat_start <= 0 or ayat_end <= 0:
                return api_error("invalid_request", "Surah dan ayat untuk bacaan Al-Quran wajib diisi.", 400)
            if (not end_surah or end_surah == start_surah) and ayat_end < ayat_start:
                return api_error("invalid_request", "Ayat akhir tidak boleh lebih kecil dari ayat awal.", 400)
            final_surah = start_surah if (not end_surah or end_surah == start_surah) else f"{start_surah} - {end_surah}"
            final_ayat_start = ayat_start
            final_ayat_end = ayat_end
        else:
            if not book_name:
                return api_error("invalid_request", "Nama kitab/buku wajib diisi.", 400)
            if page_start > 0 and page_end > 0 and page_end < page_start:
                return api_error("invalid_request", "Halaman akhir tidak boleh lebih kecil dari halaman awal.", 400)
            final_book_name = book_name
            final_page_start = page_start if page_start > 0 else None
            final_page_end = page_end if page_end > 0 else None

        new_record = RecitationRecord(
            student_id=participant.get("student_id"),
            majlis_participant_id=participant.get("majlis_participant_id"),
            participant_type=participant.get("participant_type"),
            teacher_id=teacher.id,
            recitation_source=RecitationSource[source],
            surah=final_surah,
            ayat_start=final_ayat_start,
            ayat_end=final_ayat_end,
            book_name=final_book_name,
            page_start=final_page_start,
            page_end=final_page_end,
            tajwid_errors=tajwid_errors,
            makhraj_errors=makhraj_errors,
            score=score,
            notes=(payload.get("notes") or "").strip() or None,
            date=utc_now_naive(),
        )
        db.session.add(new_record)
        db.session.commit()
        return api_success({"record_id": new_record.id}, message="Setoran bacaan berhasil disimpan.")

    @api_bp.get("/teacher/input-evaluation")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_evaluation_form():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_tahfidz_classes(teacher)
        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if classes and selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        participants = []
        recent_records = []
        if selected_class:
            _, _, participants = _class_participants_for_api(user, selected_class.id)
            student_ids = [row.get("student_id") for row in participants if row.get("student_id")]
            majlis_ids = [row.get("majlis_participant_id") for row in participants if row.get("majlis_participant_id")]
            query = TahfidzEvaluation.query.filter(TahfidzEvaluation.teacher_id == teacher.id)
            filters = []
            if student_ids:
                filters.append(
                    db.and_(
                        TahfidzEvaluation.participant_type == ParticipantType.STUDENT,
                        TahfidzEvaluation.student_id.in_(student_ids),
                    )
                )
            if majlis_ids:
                filters.append(
                    db.and_(
                        TahfidzEvaluation.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                        TahfidzEvaluation.majlis_participant_id.in_(majlis_ids),
                    )
                )
            if filters:
                query = query.filter(db.or_(*filters))
                recent_records = query.order_by(TahfidzEvaluation.date.desc(), TahfidzEvaluation.id.desc()).limit(30).all()
                recent_records = _recent_evaluation_payload(recent_records)

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class) if selected_class else {"id": 0, "name": "-"},
                "participants": participants,
                "evaluation_periods": [{"key": item.name, "label": item.value} for item in EvaluationPeriod],
                "recent_records": recent_records,
            }
        )

    @api_bp.post("/teacher/input-evaluation")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_evaluation_submit():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        class_id = _safe_parse_int(payload.get("class_id"), default=0)
        if not class_id or not _teacher_can_access_tahfidz_class(teacher, class_id):
            return api_error("forbidden", "Kelas tidak valid atau tidak dapat diakses.", 403)

        _, _, participants = _class_participants_for_api(user, class_id)
        participant_map = {row["key"]: row for row in participants}
        participant_key = (payload.get("participant_key") or "").strip()
        participant = participant_map.get(participant_key)
        if participant is None:
            return api_error("invalid_request", "Peserta tidak valid.", 400)

        period_type = (payload.get("period_type") or "").strip().upper()
        if period_type not in {item.name for item in EvaluationPeriod}:
            return api_error("invalid_request", "Periode evaluasi tidak valid.", 400)

        raw_questions = payload.get("questions") or []
        if not isinstance(raw_questions, list) or not raw_questions:
            return api_error("invalid_request", "Data pertanyaan evaluasi wajib diisi.", 400)

        normalized_questions = []
        for row in raw_questions:
            if not isinstance(row, dict):
                continue
            surah = (row.get("surah") or "").strip()
            ayat = _safe_parse_int(row.get("ayat"), default=0)
            score = _safe_parse_float(row.get("score"), default=-1)
            if not surah or ayat <= 0 or score < 0:
                continue
            normalized_questions.append({"surah": surah, "ayat": ayat, "score": score})

        if not normalized_questions:
            return api_error("invalid_request", "Pertanyaan evaluasi belum valid.", 400)

        question_count = len(normalized_questions)
        score = round(
            sum(float(item["score"]) for item in normalized_questions) / float(question_count),
            2,
        )
        first_question = normalized_questions[0]
        last_question = normalized_questions[-1]
        summary_surah = (
            first_question["surah"]
            if first_question["surah"] == last_question["surah"]
            else f"{first_question['surah']} - {last_question['surah']}"
        )

        new_row = TahfidzEvaluation(
            student_id=participant.get("student_id"),
            majlis_participant_id=participant.get("majlis_participant_id"),
            participant_type=participant.get("participant_type"),
            teacher_id=teacher.id,
            period_type=EvaluationPeriod[period_type],
            period_label=(payload.get("period_label") or "").strip() or "-",
            question_count=question_count,
            question_details=(payload.get("question_details") or "").strip() or None,
            question_items=json.dumps(normalized_questions),
            surah=summary_surah,
            ayat_start=first_question["ayat"],
            ayat_end=last_question["ayat"],
            makhraj_errors=max(0, _safe_parse_int(payload.get("makhraj_errors"), default=0)),
            tajwid_errors=max(0, _safe_parse_int(payload.get("tajwid_errors"), default=0)),
            harakat_errors=max(0, _safe_parse_int(payload.get("harakat_errors"), default=0)),
            tahfidz_errors=max(0, _safe_parse_int(payload.get("tahfidz_errors"), default=0)),
            score=score,
            notes=(payload.get("notes") or "").strip() or None,
            date=utc_now_naive(),
        )
        db.session.add(new_row)
        db.session.commit()
        return api_success({"record_id": new_row.id}, message="Evaluasi tahfidz berhasil disimpan.")

    @api_bp.get("/teacher/input-behavior")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_behavior_form():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_classes(teacher)
        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if classes and selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        query_text = (request.args.get("q") or "").strip().lower()
        students = []
        recent_reports = []
        if selected_class:
            students, _, _ = _class_participants_for_api(user, selected_class.id)
            if query_text:
                students = [
                    item
                    for item in students
                    if query_text in (item.full_name or "").lower() or query_text in (item.nis or "").lower()
                ]
            students = sorted(students, key=lambda row: row.full_name or "")
            student_ids = [item.id for item in students]
            if student_ids:
                recent_rows = (
                    BehaviorReport.query.filter(BehaviorReport.student_id.in_(student_ids))
                    .order_by(BehaviorReport.report_date.desc(), BehaviorReport.created_at.desc())
                    .limit(30)
                    .all()
                )
                recent_reports = [
                    {
                        "id": row.id,
                        "student_id": row.student_id,
                        "student_name": row.student.full_name if row.student else "-",
                        "report_type": row.report_type.name if row.report_type else "-",
                        "report_type_label": row.report_type.value if row.report_type else "-",
                        "title": row.title or "-",
                        "description": row.description or "-",
                        "is_resolved": bool(row.is_resolved),
                        "report_date": fmt_date(row.report_date),
                    }
                    for row in recent_rows
                ]

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class) if selected_class else {"id": 0, "name": "-"},
                "students": [{"id": row.id, "name": row.full_name or "-", "nis": row.nis or "-"} for row in students],
                "behavior_types": [{"key": item.name, "label": item.value} for item in BehaviorReportType],
                "recent_reports": recent_reports,
            }
        )

    @api_bp.post("/teacher/input-behavior")
    @mobile_auth_required(UserRole.GURU)
    def teacher_input_behavior_submit():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        class_id = _safe_parse_int(payload.get("class_id"), default=0)
        if not class_id or not _teacher_can_access_class(teacher, class_id):
            return api_error("forbidden", "Kelas tidak valid atau tidak dapat diakses.", 403)

        student_id = _safe_parse_int(payload.get("student_id"), default=0)
        if not student_id:
            return api_error("invalid_request", "Siswa wajib dipilih.", 400)

        students, _, _ = _class_participants_for_api(user, class_id)
        student = next((item for item in students if item.id == student_id), None)
        if student is None:
            return api_error("forbidden", "Siswa tidak berada pada kelas yang dipilih.", 403)

        report_type = (payload.get("report_type") or "").strip().upper()
        if report_type not in {item.name for item in BehaviorReportType}:
            return api_error("invalid_request", "Tipe laporan perilaku tidak valid.", 400)

        title = (payload.get("title") or "").strip()
        description = (payload.get("description") or "").strip()
        if not title or not description:
            return api_error("invalid_request", "Judul dan deskripsi laporan wajib diisi.", 400)

        report_date = _safe_parse_date(payload.get("report_date")) or local_today()
        follow_up_date = _safe_parse_date(payload.get("follow_up_date"))

        new_row = BehaviorReport(
            student_id=student.id,
            teacher_id=teacher.id,
            report_date=report_date,
            report_type=BehaviorReportType[report_type],
            title=title,
            description=description,
            action_plan=(payload.get("action_plan") or "").strip() or None,
            follow_up_date=follow_up_date,
            is_resolved=_bool_value(payload.get("is_resolved")),
        )
        db.session.add(new_row)
        db.session.commit()
        return api_success({"report_id": new_row.id}, message="Laporan perilaku berhasil disimpan.")

    @api_bp.get("/teacher/grade-history")
    @mobile_auth_required(UserRole.GURU)
    def teacher_grade_history():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_classes(teacher)
        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if classes and selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        participants = []
        selected_participant_key = (request.args.get("participant") or "").strip()
        selected_participant = None
        academic_grade_rows = []
        academic_summary_rows = []

        if selected_class:
            _, _, participants = _class_participants_for_api(user, selected_class.id)
            if not selected_participant_key and participants:
                selected_participant_key = participants[0]["key"]
            selected_participant = _resolve_selected_participant(participants, selected_participant_key)
            if selected_participant:
                grade_query = Grade.query.filter(Grade.teacher_id == teacher.id)
                if selected_participant["participant_type"] == ParticipantType.STUDENT:
                    grade_query = grade_query.filter(
                        Grade.participant_type == ParticipantType.STUDENT,
                        Grade.student_id == selected_participant["student_id"],
                    )
                else:
                    grade_query = grade_query.filter(
                        Grade.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                        Grade.majlis_participant_id == selected_participant["majlis_participant_id"],
                    )
                grade_rows = grade_query.order_by(Grade.created_at.desc(), Grade.id.desc()).all()
                grouped = defaultdict(lambda: defaultdict(list))
                for row in grade_rows:
                    subject_name = row.subject.name if row.subject else (row.majlis_subject.name if row.majlis_subject else "-")
                    if row.type:
                        grouped[subject_name][row.type.name].append(float(row.score or 0))
                    academic_grade_rows.append(
                        {
                            "id": row.id,
                            "subject_name": subject_name,
                            "type": row.type.name if row.type else "-",
                            "type_label": row.type.value if row.type else "-",
                            "score": row.score or 0,
                            "notes": row.notes or "-",
                            "created_at": fmt_datetime(row.created_at),
                        }
                    )
                for subject_name, type_map in grouped.items():
                    type_averages = {}
                    for type_name, scores in type_map.items():
                        if scores:
                            type_averages[type_name] = round(sum(scores) / len(scores), 2)
                    academic_summary_rows.append(
                        {
                            "subject_name": subject_name,
                            "type_averages": type_averages,
                            "final_score": _calculate_weighted_final(type_averages),
                        }
                    )
                academic_summary_rows.sort(key=lambda row: (row.get("subject_name") or "").lower())

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class) if selected_class else {"id": 0, "name": "-"},
                "participants": participants,
                "selected_participant_key": selected_participant_key,
                "selected_participant": selected_participant or {},
                "academic_grade_rows": academic_grade_rows,
                "academic_summary_rows": academic_summary_rows,
            }
        )

    @api_bp.get("/teacher/attendance-history")
    @mobile_auth_required(UserRole.GURU)
    def teacher_attendance_history():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_attendance_classes(teacher)
        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if classes and selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        participants = []
        selected_participant_key = (request.args.get("participant") or "").strip()
        selected_participant = None
        class_attendances = []
        participant_attendances = []
        class_recap = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0, "total": 0}
        participant_recap = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0, "total": 0}

        if selected_class:
            _, _, participants = _class_participants_for_api(user, selected_class.id)
            if not selected_participant_key and participants:
                selected_participant_key = participants[0]["key"]
            selected_participant = _resolve_selected_participant(participants, selected_participant_key)

            attendance_rows = (
                Attendance.query.filter(
                    Attendance.class_id == selected_class.id,
                    Attendance.participant_type.in_([ParticipantType.STUDENT, ParticipantType.EXTERNAL_MAJLIS]),
                )
                .order_by(Attendance.date.desc(), Attendance.created_at.desc())
                .limit(500)
                .all()
            )
            for row in attendance_rows:
                class_recap["total"] += 1
                if row.status == AttendanceStatus.HADIR:
                    class_recap["hadir"] += 1
                elif row.status == AttendanceStatus.SAKIT:
                    class_recap["sakit"] += 1
                elif row.status == AttendanceStatus.IZIN:
                    class_recap["izin"] += 1
                elif row.status == AttendanceStatus.ALPA:
                    class_recap["alpa"] += 1
                class_attendances.append(
                    {
                        "id": row.id,
                        "participant_name": _participant_name_from_attendance(row),
                        "date": fmt_date(row.date),
                        "status": row.status.name if row.status else "-",
                        "status_label": row.status.value if row.status else "-",
                        "notes": row.notes or "-",
                    }
                )

            if selected_participant:
                participant_query = Attendance.query.filter(Attendance.class_id == selected_class.id)
                if selected_participant["participant_type"] == ParticipantType.STUDENT:
                    participant_query = participant_query.filter(
                        Attendance.participant_type == ParticipantType.STUDENT,
                        Attendance.student_id == selected_participant["student_id"],
                    )
                else:
                    participant_query = participant_query.filter(
                        Attendance.participant_type == ParticipantType.EXTERNAL_MAJLIS,
                        Attendance.majlis_participant_id == selected_participant["majlis_participant_id"],
                    )
                rows = participant_query.order_by(Attendance.date.desc(), Attendance.created_at.desc()).all()
                for row in rows:
                    participant_recap["total"] += 1
                    if row.status == AttendanceStatus.HADIR:
                        participant_recap["hadir"] += 1
                    elif row.status == AttendanceStatus.SAKIT:
                        participant_recap["sakit"] += 1
                    elif row.status == AttendanceStatus.IZIN:
                        participant_recap["izin"] += 1
                    elif row.status == AttendanceStatus.ALPA:
                        participant_recap["alpa"] += 1
                    participant_attendances.append(
                        {
                            "id": row.id,
                            "participant_name": _participant_name_from_attendance(row),
                            "date": fmt_date(row.date),
                            "status": row.status.name if row.status else "-",
                            "status_label": row.status.value if row.status else "-",
                            "notes": row.notes or "-",
                        }
                    )

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class) if selected_class else {"id": 0, "name": "-"},
                "participants": participants,
                "selected_participant_key": selected_participant_key,
                "selected_participant": selected_participant or {},
                "class_recap": class_recap,
                "participant_recap": participant_recap,
                "class_attendances": class_attendances,
                "participant_attendances": participant_attendances,
            }
        )

    @api_bp.get("/teacher/homeroom-students")
    @mobile_auth_required(UserRole.GURU)
    def teacher_homeroom_students():
        user, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        homeroom_classes = _get_teacher_homeroom_classes(teacher)
        if not homeroom_classes:
            return api_success(
                {
                    "homeroom_classes": [],
                    "selected_class": {"id": 0, "name": "-"},
                    "students": [],
                    "majlis_participants": [],
                }
            )

        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(homeroom_classes, class_id)
        if selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        students, majlis_participants, _ = _class_participants_for_api(user, selected_class.id)
        return api_success(
            {
                "homeroom_classes": _classes_payload(homeroom_classes),
                "selected_class": _class_payload(selected_class),
                "students": [
                    {
                        "id": row.id,
                        "name": row.full_name or "-",
                        "identifier_label": "NIS",
                        "identifier": row.nis or "-",
                    }
                    for row in students
                ],
                "majlis_participants": [
                    {
                        "id": row.id,
                        "name": row.full_name or "-",
                        "identifier_label": "Kontak",
                        "identifier": row.phone or "-",
                    }
                    for row in majlis_participants
                ],
            }
        )

    @api_bp.get("/teacher/class-announcements")
    @mobile_auth_required(UserRole.GURU)
    def teacher_class_announcements():
        _, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        classes = _get_teacher_classes(teacher)
        class_id = request.args.get("class_id", type=int)
        selected_class = _selected_class(classes, class_id)
        if classes and class_id and selected_class is None:
            return api_error("forbidden", "Akses kelas tidak diizinkan.", 403)

        query = Announcement.query.filter(Announcement.user_id == g.mobile_user.id).order_by(Announcement.created_at.desc())
        if selected_class:
            query = query.filter(Announcement.target_class_id == selected_class.id)
        rows = query.limit(50).all()

        return api_success(
            {
                "classes": _classes_payload(classes),
                "selected_class": _class_payload(selected_class) if selected_class else {"id": 0, "name": "-"},
                "announcements": [
                    {
                        "id": row.id,
                        "title": row.title or "-",
                        "content": row.content or "-",
                        "class_id": row.target_class_id or 0,
                        "class_name": row.target_class.name if row.target_class else "-",
                        "is_active": bool(row.is_active),
                        "created_at": fmt_datetime(row.created_at),
                    }
                    for row in rows
                ],
            }
        )

    @api_bp.post("/teacher/class-announcements")
    @mobile_auth_required(UserRole.GURU)
    def teacher_class_announcements_submit():
        _, teacher = _teacher_from_mobile_user()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        payload = request.get_json(silent=True) or {}
        class_id = _safe_parse_int(payload.get("class_id"), default=0)
        if not class_id or not _teacher_can_access_class(teacher, class_id):
            return api_error("forbidden", "Kelas target tidak valid.", 403)

        title = (payload.get("title") or "").strip()
        content = (payload.get("content") or "").strip()
        if not title or not content:
            return api_error("invalid_request", "Judul dan isi pengumuman wajib diisi.", 400)

        row = Announcement(
            title=title,
            content=content,
            is_active=_bool_value(payload.get("is_active")),
            target_scope="CLASS",
            target_class_id=class_id,
            user_id=g.mobile_user.id,
        )
        db.session.add(row)
        db.session.commit()
        return api_success({"announcement_id": row.id}, message="Pengumuman kelas berhasil dibuat.")
