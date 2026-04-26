from flask import g

from app.models import (
    BoardingAttendance,
    Schedule,
    TahfidzEvaluation,
    TahfidzRecord,
    RecitationRecord,
    Teacher,
    UserRole,
    AttendanceStatus,
)
from app.routes.teacher import (
    _classroom_visible_for_teacher,
    _collect_teacher_assignment_summary,
    _count_teacher_students,
    _get_class_participants,
    _get_teacher_classes,
    _get_teacher_homeroom_classes,
)
from app.utils.announcements import get_announcements_for_dashboard
from app.utils.timezone import local_day_bounds_utc_naive, local_today

from .common import (
    DAY_NAMES,
    announcement_payload,
    api_error,
    api_success,
    fmt_datetime,
    fmt_time,
    mobile_auth_required,
    participant_name_from_record,
    user_display_name,
)


def register_teacher_routes(api_bp):
    @api_bp.get("/teacher/dashboard")
    @mobile_auth_required(UserRole.GURU)
    def teacher_dashboard():
        user = g.mobile_user
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        if teacher is None:
            return api_error("not_found", "Profil guru tidak ditemukan.", 404)

        my_classes = _get_teacher_classes(teacher)
        homeroom_classes = _get_teacher_homeroom_classes(teacher)
        total_students = _count_teacher_students(my_classes) if my_classes else 0
        homeroom_class = homeroom_classes[0] if homeroom_classes else None
        _, teaching_assignments = _collect_teacher_assignment_summary(teacher)

        today = local_today()
        today_name = DAY_NAMES[today.weekday()]
        today_start_utc, today_end_utc = local_day_bounds_utc_naive(today)

        todays_schedules = (
            Schedule.query.filter_by(
                teacher_id=teacher.id,
                day=today_name,
                is_deleted=False,
            )
            .order_by(Schedule.start_time.asc())
            .all()
        )
        todays_schedules = [
            item
            for item in todays_schedules
            if _classroom_visible_for_teacher(teacher, item.class_room)
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
            students, _ = _get_class_participants(class_room.id, tenant_id=user.tenant_id)
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
            homeroom_students, homeroom_majlis = _get_class_participants(homeroom_class.id, tenant_id=user.tenant_id)
            homeroom_menu = [
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
            ]
            homeroom_payload = {
                "available": True,
                "class_id": homeroom_class.id,
                "class_name": homeroom_class.name or "-",
                "student_count": len(homeroom_students),
                "majlis_count": len(homeroom_majlis),
                "menu": homeroom_menu,
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
                            item.subject.name
                            if item.subject
                            else (item.majlis_subject.name if item.majlis_subject else "-")
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
                "class_options": [
                    {"id": item.id, "name": item.name or "-"}
                    for item in sorted(my_classes, key=lambda obj: obj.name or "")
                ],
                "input_menu": [
                    {"key": "nilai", "label": "Input Nilai", "description": "Input nilai mapel untuk kelas yang diajar."},
                    {"key": "absensi", "label": "Input Absensi", "description": "Catat kehadiran peserta per kelas."},
                    {"key": "perilaku", "label": "Laporan Perilaku", "description": "Input catatan perilaku siswa."},
                    {"key": "tahfidz", "label": "Input Tahfidz", "description": "Input setoran hafalan tahfidz."},
                    {"key": "bacaan", "label": "Input Bacaan", "description": "Input setoran bacaan Al-Qur'an/kitab."},
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
                    {
                        "key": "riwayat_nilai",
                        "label": "Riwayat Nilai",
                        "description": "Lihat histori input nilai per kelas.",
                    },
                    {
                        "key": "riwayat_absensi",
                        "label": "Riwayat Absensi",
                        "description": "Lihat histori absensi yang telah diinput.",
                    },
                ],
                "homeroom": homeroom_payload,
            }
        )
