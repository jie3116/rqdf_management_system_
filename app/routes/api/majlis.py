from flask import g, request
from sqlalchemy import and_, or_

from app.models import (
    Attendance,
    AttendanceStatus,
    ClassRoom,
    Invoice,
    ParticipantType,
    PaymentStatus,
    ProgramType,
    RecitationRecord,
    Schedule,
    Student,
    TahfidzEvaluation,
    TahfidzRecord,
    TahfidzSummary,
    User,
    UserRole,
)
from app.services.majlis_enrollment_service import resolve_majlis_classroom
from app.utils.announcements import get_announcements_for_dashboard, mark_announcements_as_read
from app.utils.tenant import scoped_classrooms_query

from .common import (
    ORDERED_DAYS,
    announcement_payload,
    api_error,
    api_success,
    fmt_date,
    fmt_datetime,
    fmt_time,
    mobile_auth_required,
)


def resolve_majlis_context(user):
    profile = user.majlis_profile
    parent_profile = user.parent_profile if user.has_role(UserRole.WALI_MURID) else None
    if profile is None:
        return None, parent_profile, None

    majlis_class = profile.majlis_class
    if parent_profile and getattr(parent_profile, "person_id", None):
        resolved = resolve_majlis_classroom(user.tenant_id, parent_profile.person_id)
        majlis_class = resolved or majlis_class
    if getattr(profile, "person_id", None):
        resolved = resolve_majlis_classroom(user.tenant_id, profile.person_id)
        majlis_class = resolved or majlis_class

    if majlis_class and user.tenant_id:
        scoped = scoped_classrooms_query(user.tenant_id).filter(ClassRoom.id == majlis_class.id).first()
        majlis_class = scoped

    return profile, parent_profile, majlis_class


def majlis_announcements_query(user, profile, parent_profile, show_all=False):
    class_id = profile.majlis_class_id if profile else None
    if class_id is None and profile and getattr(profile, "person_id", None):
        majlis_class = resolve_majlis_classroom(user.tenant_id, profile.person_id)
        class_id = majlis_class.id if majlis_class else None
    if class_id is None and parent_profile and getattr(parent_profile, "person_id", None):
        majlis_class = resolve_majlis_classroom(user.tenant_id, parent_profile.person_id)
        class_id = majlis_class.id if majlis_class else None

    if class_id and user.tenant_id:
        scoped = scoped_classrooms_query(user.tenant_id).filter(ClassRoom.id == class_id).first()
        if scoped is None:
            class_id = None

    return get_announcements_for_dashboard(
        user,
        class_ids=[class_id] if class_id else [],
        user_ids=[user.id],
        program_types=[ProgramType.MAJLIS_TALIM.name],
        show_all=show_all,
    )


def register_majlis_routes(api_bp):
    @api_bp.get("/majlis/announcements")
    @mobile_auth_required(UserRole.MAJLIS_PARTICIPANT, UserRole.WALI_MURID)
    def majlis_announcements():
        user = g.mobile_user
        profile, parent_profile, _ = resolve_majlis_context(user)
        if profile is None:
            return api_error("not_found", "Profil peserta majlis tidak ditemukan.", 404)

        scope = (request.args.get("scope") or "all").strip().lower()
        mark_as_read = (request.args.get("mark_as_read") or "").strip() in {"1", "true", "yes"}
        show_all = scope == "all"
        announcements, unread_count = majlis_announcements_query(
            user,
            profile=profile,
            parent_profile=parent_profile,
            show_all=show_all,
        )
        if mark_as_read:
            mark_announcements_as_read(user, announcements)
            unread_count = 0

        return api_success(
            {
                "items": [announcement_payload(item) for item in announcements],
                "unread_announcements_count": unread_count,
            }
        )

    @api_bp.get("/majlis/dashboard")
    @mobile_auth_required(UserRole.MAJLIS_PARTICIPANT, UserRole.WALI_MURID)
    def majlis_dashboard():
        user = g.mobile_user
        profile, parent_profile, majlis_class = resolve_majlis_context(user)
        if profile is None:
            return api_error("not_found", "Profil peserta majlis tidak ditemukan.", 404)

        summary_filters = [
            and_(
                TahfidzSummary.majlis_participant_id == profile.id,
                TahfidzSummary.participant_type == ParticipantType.EXTERNAL_MAJLIS,
            )
        ]
        tahfidz_filters = [
            and_(
                TahfidzRecord.majlis_participant_id == profile.id,
                TahfidzRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS,
            )
        ]
        recitation_filters = [
            and_(
                RecitationRecord.majlis_participant_id == profile.id,
                RecitationRecord.participant_type == ParticipantType.EXTERNAL_MAJLIS,
            )
        ]
        evaluation_filters = [
            and_(
                TahfidzEvaluation.majlis_participant_id == profile.id,
                TahfidzEvaluation.participant_type == ParticipantType.EXTERNAL_MAJLIS,
            )
        ]
        attendance_filters = [
            and_(
                Attendance.majlis_participant_id == profile.id,
                Attendance.participant_type == ParticipantType.EXTERNAL_MAJLIS,
            )
        ]

        if parent_profile:
            summary_filters.append(
                and_(
                    TahfidzSummary.parent_id == parent_profile.id,
                    TahfidzSummary.participant_type == ParticipantType.PARENT_MAJLIS,
                )
            )
            tahfidz_filters.append(
                and_(
                    TahfidzRecord.parent_id == parent_profile.id,
                    TahfidzRecord.participant_type == ParticipantType.PARENT_MAJLIS,
                )
            )
            recitation_filters.append(
                and_(
                    RecitationRecord.parent_id == parent_profile.id,
                    RecitationRecord.participant_type == ParticipantType.PARENT_MAJLIS,
                )
            )
            evaluation_filters.append(
                and_(
                    TahfidzEvaluation.parent_id == parent_profile.id,
                    TahfidzEvaluation.participant_type == ParticipantType.PARENT_MAJLIS,
                )
            )
            attendance_filters.append(
                and_(
                    Attendance.parent_id == parent_profile.id,
                    Attendance.participant_type == ParticipantType.PARENT_MAJLIS,
                )
            )

        summary = TahfidzSummary.query.filter(or_(*summary_filters)).order_by(TahfidzSummary.updated_at.desc()).first()
        tahfidz_records = TahfidzRecord.query.filter(or_(*tahfidz_filters)).order_by(TahfidzRecord.date.desc()).limit(10).all()
        recitation_records = (
            RecitationRecord.query.filter(or_(*recitation_filters))
            .order_by(RecitationRecord.date.desc())
            .limit(10)
            .all()
        )
        evaluation_records = (
            TahfidzEvaluation.query.filter(or_(*evaluation_filters))
            .order_by(TahfidzEvaluation.date.desc())
            .limit(10)
            .all()
        )

        announcements, unread_count = majlis_announcements_query(
            user,
            profile=profile,
            parent_profile=parent_profile,
            show_all=False,
        )

        attendance_rows = (
            Attendance.query.filter(or_(*attendance_filters))
            .order_by(Attendance.date.desc(), Attendance.created_at.desc())
            .limit(30)
            .all()
        )
        attendance_recap = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0}
        for row in attendance_rows:
            if row.status == AttendanceStatus.HADIR:
                attendance_recap["hadir"] += 1
            elif row.status == AttendanceStatus.SAKIT:
                attendance_recap["sakit"] += 1
            elif row.status == AttendanceStatus.IZIN:
                attendance_recap["izin"] += 1
            elif row.status == AttendanceStatus.ALPA:
                attendance_recap["alpa"] += 1

        weekly_schedule = {day: [] for day in ORDERED_DAYS}
        if majlis_class:
            schedules = (
                Schedule.query.filter_by(class_id=majlis_class.id, is_deleted=False)
                .order_by(Schedule.start_time.asc())
                .all()
            )
            for item in schedules:
                if item.day in weekly_schedule:
                    weekly_schedule[item.day].append(item)

        schedule_days = []
        for day in ORDERED_DAYS:
            schedule_days.append(
                {
                    "day": day,
                    "items": [
                        {
                            "id": item.id,
                            "start_time": fmt_time(item.start_time),
                            "subject_name": (
                                item.majlis_subject.name
                                if item.majlis_subject
                                else (item.subject.name if item.subject else "-")
                            ),
                            "teacher_name": (
                                item.teacher.full_name if item.teacher and item.teacher.full_name else "-"
                            ),
                        }
                        for item in weekly_schedule[day]
                    ],
                }
            )

        finance_payload = {
            "applicable": False,
            "invoices": [],
            "summary": {
                "total_amount": 0,
                "paid_amount": 0,
                "remaining_amount": 0,
                "unpaid_count": 0,
            },
        }
        if parent_profile:
            parent_invoices = (
                Invoice.query.join(Student, Invoice.student_id == Student.id).join(User, Student.user_id == User.id)
                .filter(
                    Student.parent_id == parent_profile.id,
                    User.tenant_id == user.tenant_id,
                    Invoice.is_deleted.is_(False),
                )
                .order_by(Invoice.created_at.desc())
                .limit(25)
                .all()
            )
            total_amount = sum(item.total_amount or 0 for item in parent_invoices)
            paid_amount = sum(item.paid_amount or 0 for item in parent_invoices)
            remaining_amount = sum(max(0, (item.total_amount or 0) - (item.paid_amount or 0)) for item in parent_invoices)
            unpaid_count = sum(1 for item in parent_invoices if item.status != PaymentStatus.PAID)
            finance_payload = {
                "applicable": True,
                "invoices": [
                    {
                        "id": item.id,
                        "invoice_number": item.invoice_number or "-",
                        "student_name": item.student.full_name if item.student else "-",
                        "fee_type": item.fee_type.name if item.fee_type else "-",
                        "remaining_amount": max(0, (item.total_amount or 0) - (item.paid_amount or 0)),
                        "status_label": item.status.value if item.status else "-",
                    }
                    for item in parent_invoices
                ],
                "summary": {
                    "total_amount": total_amount,
                    "paid_amount": paid_amount,
                    "remaining_amount": remaining_amount,
                    "unpaid_count": unpaid_count,
                },
            }

        summary_target = "-"
        if summary:
            target_parts = []
            if summary.last_surah:
                target_parts.append(summary.last_surah)
            if summary.last_ayat:
                target_parts.append(str(summary.last_ayat))
            summary_target = " : ".join(target_parts) if target_parts else "-"

        return api_success(
            {
                "profile": {
                    "id": profile.id,
                    "full_name": profile.full_name or "-",
                    "phone": profile.phone or "-",
                    "address": profile.address or "-",
                    "job": profile.job or "-",
                    "majlis_class_id": majlis_class.id if majlis_class else 0,
                    "majlis_class_name": majlis_class.name if majlis_class else "-",
                    "join_date": fmt_date(profile.join_date),
                    "has_external_profile": bool(profile),
                    "has_parent_profile": bool(parent_profile),
                },
                "summary": {
                    "total_juz": summary.total_juz if summary else 0,
                    "last_target_text": summary_target,
                    "updated_at": fmt_datetime(summary.updated_at if summary else None),
                },
                "announcements": [announcement_payload(item) for item in announcements],
                "unread_announcements_count": unread_count,
                "tahfidz_records": [
                    {
                        "id": item.id,
                        "date": fmt_datetime(item.date),
                        "type_label": item.type.value if item.type else "-",
                        "surah": item.surah or "-",
                        "ayat_start": item.ayat_start or 0,
                        "ayat_end": item.ayat_end or 0,
                        "quality": item.quality or "-",
                        "score": item.score or 0,
                    }
                    for item in tahfidz_records
                ],
                "recitation_records": [
                    {
                        "id": item.id,
                        "date": fmt_datetime(item.date),
                        "recitation_source_label": item.recitation_source.value if item.recitation_source else "-",
                        "surah": item.surah or "-",
                        "ayat_start": item.ayat_start or 0,
                        "ayat_end": item.ayat_end or 0,
                        "book_name": item.book_name or "-",
                        "page_start": item.page_start or 0,
                        "page_end": item.page_end or 0,
                        "score": item.score or 0,
                    }
                    for item in recitation_records
                ],
                "evaluation_records": [
                    {
                        "id": item.id,
                        "date": fmt_datetime(item.date),
                        "period_type_label": item.period_type.value if item.period_type else "-",
                        "period_label": item.period_label or "-",
                        "score": item.score or 0,
                        "makhraj_errors": item.makhraj_errors or 0,
                        "tajwid_errors": item.tajwid_errors or 0,
                        "harakat_errors": item.harakat_errors or 0,
                    }
                    for item in evaluation_records
                ],
                "attendance": {
                    "records": [
                        {
                            "id": item.id,
                            "date": fmt_date(item.date),
                            "status": item.status.name if item.status else "-",
                            "status_label": item.status.value if item.status else "-",
                            "class_name": item.class_room.name if item.class_room else "-",
                            "teacher_name": item.teacher.full_name if item.teacher and item.teacher.full_name else "-",
                        }
                        for item in attendance_rows
                    ],
                    "recap": attendance_recap,
                },
                "schedule_days": schedule_days,
                "finance": finance_payload,
            }
        )
