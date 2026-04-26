from collections import defaultdict

from flask import g, request

from app.models import (
    AcademicYear,
    Attendance,
    AttendanceStatus,
    BehaviorReport,
    BoardingAttendance,
    ClassRoom,
    Grade,
    Invoice,
    ParticipantType,
    PaymentStatus,
    RecitationRecord,
    Schedule,
    TahfidzEvaluation,
    TahfidzRecord,
    TahfidzSummary,
    UserRole,
    Violation,
)
from app.services.formal_service import get_student_formal_classroom
from app.utils.announcements import get_announcements_for_dashboard
from app.utils.tenant import resolve_tenant_id, scoped_classrooms_query
from app.utils.timezone import local_today

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
    parent_children_for_tenant,
    serialize_child,
)


def _student_payload(user, student):
    payload = dict(serialize_child(user, student))
    payload["nis"] = student.nis or "-"
    return payload


def _resolve_parent_children_context():
    user = g.mobile_user
    parent = user.parent_profile
    if parent is None:
        return None, None, None, api_error("not_found", "Profil wali murid tidak ditemukan.", 404)

    children = parent_children_for_tenant(user, parent)
    return user, parent, children, None


def _resolve_selected_child(children, selected_student_id):
    if not children:
        return None
    if selected_student_id:
        return next((item for item in children if item.id == selected_student_id), None)
    return children[0]


def _resolve_child_class(user, student):
    active_class = get_student_formal_classroom(student) or student.current_class
    active_class_id = active_class.id if active_class else None
    tenant_id = resolve_tenant_id(user, fallback_default=False)
    if tenant_id and active_class_id:
        visible_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == active_class_id).first()
        if visible_class is None:
            active_class = None
            active_class_id = None
        else:
            active_class = visible_class
    return active_class, active_class_id


def _calculate_weighted_final(type_averages):
    weights = {"TUGAS": 0.3, "UH": 0.2, "UTS": 0.25, "UAS": 0.25}
    total_weighted = 0.0
    total_weight = 0.0
    for type_name, score in (type_averages or {}).items():
        weight = float(weights.get(type_name, 0))
        if weight <= 0:
            continue
        total_weighted += float(score) * weight
        total_weight += weight
    if total_weight <= 0:
        return 0
    return round(total_weighted / total_weight, 2)


def register_parent_routes(api_bp):
    @api_bp.get("/parent/children")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_children():
        user, parent, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response

        return api_success(
            {
                "parent": {
                    "id": parent.id,
                    "full_name": parent.full_name or "-",
                    "phone": parent.phone or "-",
                    "is_majlis_participant": bool(parent.is_majlis_participant),
                },
                "children": [serialize_child(user, child) for child in children],
            }
        )

    @api_bp.get("/parent/dashboard")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_dashboard():
        user, parent, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response
        if not children:
            return api_error("not_found", "Data anak belum tersedia.", 404)

        selected_student_id = request.args.get("student_id", type=int)
        selected_child = _resolve_selected_child(children, selected_student_id)
        if selected_child is None:
            return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)

        summary = TahfidzSummary.query.filter_by(
            student_id=selected_child.id,
            participant_type=ParticipantType.STUDENT,
        ).first()
        memorization_progress = "-"
        if summary:
            target = []
            if summary.last_surah:
                target.append(summary.last_surah)
            if summary.last_ayat:
                target.append(str(summary.last_ayat))
            target_text = " : ".join(target) if target else "-"
            memorization_progress = f"{summary.total_juz or 0:.1f} Juz | {target_text}"

        latest_attendance = (
            Attendance.query.filter_by(
                student_id=selected_child.id,
                participant_type=ParticipantType.STUDENT,
            )
            .order_by(Attendance.date.desc(), Attendance.created_at.desc())
            .first()
        )
        attendance_status = latest_attendance.status.value if latest_attendance and latest_attendance.status else "-"

        invoices = (
            Invoice.query.filter_by(student_id=selected_child.id, is_deleted=False)
            .order_by(Invoice.created_at.desc())
            .all()
        )
        billing_total = float(
            sum(
                max(0, (invoice.total_amount or 0) - (invoice.paid_amount or 0))
                for invoice in invoices
                if invoice.status != PaymentStatus.PAID
            )
        )

        violations = selected_child.violations.all() if hasattr(selected_child.violations, "all") else []
        violation_points = sum(item.points or 0 for item in violations)

        recent_tahfidz = (
            TahfidzRecord.query.filter_by(
                student_id=selected_child.id,
                participant_type=ParticipantType.STUDENT,
            )
            .order_by(TahfidzRecord.date.desc())
            .limit(3)
            .all()
        )
        recent_recitation = (
            RecitationRecord.query.filter_by(
                student_id=selected_child.id,
                participant_type=ParticipantType.STUDENT,
            )
            .order_by(RecitationRecord.date.desc())
            .limit(3)
            .all()
        )
        recent_evaluations = (
            TahfidzEvaluation.query.filter_by(
                student_id=selected_child.id,
                participant_type=ParticipantType.STUDENT,
            )
            .order_by(TahfidzEvaluation.date.desc())
            .limit(3)
            .all()
        )

        activities = []
        for row in recent_tahfidz:
            activities.append(
                {
                    "type": "tahfidz",
                    "message": f"Setoran {row.type.value if row.type else 'Tahfidz'} - {row.surah or '-'}",
                    "created_at": fmt_datetime(row.date),
                }
            )
        for row in recent_recitation:
            material = row.book_name or row.surah or "Bacaan"
            activities.append(
                {
                    "type": "recitation",
                    "message": f"Setoran Bacaan - {material}",
                    "created_at": fmt_datetime(row.date),
                }
            )
        for row in recent_evaluations:
            activities.append(
                {
                    "type": "evaluation",
                    "message": f"Evaluasi Tahfidz - Nilai {row.score or 0}",
                    "created_at": fmt_datetime(row.date),
                }
            )
        activities = sorted(activities, key=lambda item: item["created_at"], reverse=True)[:8]

        target_ids = [user.id]
        if selected_child.user_id:
            target_ids.append(selected_child.user_id)

        active_class, active_class_id = _resolve_child_class(user, selected_child)

        class_program = active_class.program_type.name if active_class and active_class.program_type else None
        announcements, unread_count = get_announcements_for_dashboard(
            user,
            class_ids=[active_class_id] if active_class_id else [],
            user_ids=target_ids,
            program_types=[class_program] if class_program else [],
            show_all=False,
        )

        return api_success(
            {
                "guardian_name": parent.full_name or "-",
                "children": [serialize_child(user, item) for item in children],
                "selected_child": serialize_child(user, selected_child),
                "summary": {
                    "billing_total": billing_total,
                    "violation_points": violation_points,
                    "memorization_progress": memorization_progress,
                    "attendance_status": attendance_status,
                },
                "quick_actions": [
                    {"key": "pengumuman", "label": "Pengumuman"},
                    {"key": "keuangan", "label": "Keuangan"},
                    {"key": "tahfidz", "label": "Tahfidz"},
                    {"key": "jadwal", "label": "Jadwal"},
                    {"key": "nilai", "label": "Nilai"},
                    {"key": "absensi", "label": "Absensi"},
                    {"key": "perilaku", "label": "Perilaku"},
                ],
                "recent_activities": activities,
                "announcements": [announcement_payload(item) for item in announcements],
                "unread_announcements_count": unread_count,
                "is_majlis_participant": bool(parent.is_majlis_participant),
            }
        )

    @api_bp.get("/parent/children/<int:child_id>/announcements")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_child_announcements(child_id):
        user, _, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response

        selected_child = _resolve_selected_child(children, child_id)
        if selected_child is None:
            return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)

        active_class, active_class_id = _resolve_child_class(user, selected_child)
        class_program = active_class.program_type.name if active_class and active_class.program_type else None

        target_user_ids = [user.id]
        if selected_child.user_id:
            target_user_ids.append(selected_child.user_id)

        announcements, unread_count = get_announcements_for_dashboard(
            user,
            class_ids=[active_class_id] if active_class_id else [],
            user_ids=target_user_ids,
            program_types=[class_program] if class_program else [],
            show_all=True,
        )

        return api_success(
            {
                "student": _student_payload(user, selected_child),
                "unread_count": unread_count,
                "items": [announcement_payload(item) for item in announcements],
            }
        )

    @api_bp.get("/parent/children/<int:child_id>/finance")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_child_finance(child_id):
        user, _, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response

        selected_child = _resolve_selected_child(children, child_id)
        if selected_child is None:
            return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)

        invoices = (
            Invoice.query.filter_by(student_id=selected_child.id)
            .order_by(Invoice.created_at.desc(), Invoice.id.desc())
            .all()
        )

        invoice_rows = []
        total_amount = 0
        paid_amount = 0
        remaining_amount = 0
        unpaid_count = 0
        for row in invoices:
            total = int(row.total_amount or 0)
            paid = int(row.paid_amount or 0)
            remaining = max(0, total - paid)
            total_amount += total
            paid_amount += paid
            remaining_amount += remaining
            if row.status != PaymentStatus.PAID:
                unpaid_count += 1

            invoice_rows.append(
                {
                    "id": row.id,
                    "invoice_number": row.invoice_number or f"INV-{row.id}",
                    "fee_type": row.fee_type.name if row.fee_type else "-",
                    "total_amount": total,
                    "paid_amount": paid,
                    "remaining_amount": remaining,
                    "status": row.status.name if row.status else "-",
                    "status_label": row.status.value if row.status else "-",
                    "due_date": fmt_date(row.due_date),
                    "created_at": fmt_datetime(row.created_at),
                }
            )

        return api_success(
            {
                "student": _student_payload(user, selected_child),
                "summary": {
                    "total_amount": total_amount,
                    "paid_amount": paid_amount,
                    "remaining_amount": remaining_amount,
                    "unpaid_count": unpaid_count,
                },
                "invoices": invoice_rows,
            }
        )

    @api_bp.get("/parent/children/<int:child_id>/memorization-report")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_child_memorization_report(child_id):
        user, _, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response

        selected_child = _resolve_selected_child(children, child_id)
        if selected_child is None:
            return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)

        summary = TahfidzSummary.query.filter_by(
            student_id=selected_child.id,
            participant_type=ParticipantType.STUDENT,
        ).first()
        last_target_parts = []
        if summary and summary.last_surah:
            last_target_parts.append(summary.last_surah)
        if summary and summary.last_ayat:
            last_target_parts.append(str(summary.last_ayat))
        last_target_text = " : ".join(last_target_parts) if last_target_parts else "-"

        tahfidz_records = (
            TahfidzRecord.query.filter_by(
                student_id=selected_child.id,
                participant_type=ParticipantType.STUDENT,
            )
            .order_by(TahfidzRecord.date.desc(), TahfidzRecord.id.desc())
            .limit(50)
            .all()
        )
        recitation_records = (
            RecitationRecord.query.filter_by(
                student_id=selected_child.id,
                participant_type=ParticipantType.STUDENT,
            )
            .order_by(RecitationRecord.date.desc(), RecitationRecord.id.desc())
            .limit(50)
            .all()
        )
        evaluations = (
            TahfidzEvaluation.query.filter_by(
                student_id=selected_child.id,
                participant_type=ParticipantType.STUDENT,
            )
            .order_by(TahfidzEvaluation.date.desc(), TahfidzEvaluation.id.desc())
            .limit(50)
            .all()
        )

        return api_success(
            {
                "student": _student_payload(user, selected_child),
                "summary": {
                    "total_juz": int(summary.total_juz or 0) if summary else 0,
                    "last_surah": summary.last_surah if summary and summary.last_surah else "-",
                    "last_ayat": summary.last_ayat if summary and summary.last_ayat else "-",
                    "last_target_text": last_target_text,
                },
                "records": [
                    {
                        "id": row.id,
                        "surah": row.surah or "-",
                        "ayat_start": row.ayat_start or "-",
                        "ayat_end": row.ayat_end or "-",
                        "date": fmt_datetime(row.date),
                        "type": row.type.name if row.type else "-",
                        "type_label": row.type.value if row.type else "-",
                        "score": row.score or 0,
                    }
                    for row in tahfidz_records
                ],
                "recitation_records": [
                    {
                        "id": row.id,
                        "material_text": (
                            f"{row.book_name} ({row.page_start or '-'}-{row.page_end or '-'})"
                            if row.book_name
                            else f"{row.surah or '-'} ({row.ayat_start or '-'}-{row.ayat_end or '-'})"
                        ),
                        "recitation_source": row.recitation_source.name if row.recitation_source else "-",
                        "recitation_source_label": (
                            row.recitation_source.value if row.recitation_source else "-"
                        ),
                        "date": fmt_datetime(row.date),
                        "surah": row.surah or "-",
                        "ayat_start": row.ayat_start or "-",
                        "ayat_end": row.ayat_end or "-",
                        "book_name": row.book_name or "-",
                        "page_start": row.page_start or "-",
                        "page_end": row.page_end or "-",
                        "score": row.score or 0,
                    }
                    for row in recitation_records
                ],
                "evaluations": [
                    {
                        "id": row.id,
                        "period_type": row.period_type.name if row.period_type else "-",
                        "period_type_label": row.period_type.value if row.period_type else "-",
                        "period_label": row.period_label or "-",
                        "date": fmt_datetime(row.date),
                        "notes": row.notes or "-",
                        "score": row.score or 0,
                    }
                    for row in evaluations
                ],
            }
        )

    @api_bp.get("/parent/children/<int:child_id>/weekly-schedule")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_child_weekly_schedule(child_id):
        user, _, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response

        selected_child = _resolve_selected_child(children, child_id)
        if selected_child is None:
            return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)

        active_class, active_class_id = _resolve_child_class(user, selected_child)
        day_buckets = {day: [] for day in ORDERED_DAYS}

        if active_class_id:
            schedules = (
                Schedule.query.filter(Schedule.class_id == active_class_id)
                .order_by(Schedule.day.asc(), Schedule.start_time.asc(), Schedule.id.asc())
                .all()
            )
            for row in schedules:
                if row.day not in day_buckets:
                    continue
                subject_name = row.subject.name if row.subject else (row.majlis_subject.name if row.majlis_subject else "-")
                day_buckets[row.day].append(
                    {
                        "schedule_id": row.id,
                        "subject_name": subject_name,
                        "start_time": fmt_time(row.start_time),
                        "end_time": fmt_time(row.end_time),
                        "text": f"{fmt_time(row.start_time)}-{fmt_time(row.end_time)} • {subject_name}",
                    }
                )

        today_name = DAY_NAMES[local_today().weekday()]
        return api_success(
            {
                "student": _student_payload(user, selected_child),
                "class": {
                    "id": active_class.id if active_class else 0,
                    "name": active_class.name if active_class else "-",
                },
                "today_name": today_name,
                "today_items": day_buckets.get(today_name, []),
                "days": [{"day": day, "items": day_buckets.get(day, [])} for day in ORDERED_DAYS],
            }
        )

    @api_bp.get("/parent/children/<int:child_id>/academic-grades")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_child_academic_grades(child_id):
        user, _, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response

        selected_child = _resolve_selected_child(children, child_id)
        if selected_child is None:
            return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)

        active_year = AcademicYear.query.filter_by(is_active=True).first()
        grade_query = Grade.query.filter(
            Grade.participant_type == ParticipantType.STUDENT,
            Grade.student_id == selected_child.id,
        )
        if active_year:
            grade_query = grade_query.filter(Grade.academic_year_id == active_year.id)

        grade_rows = grade_query.order_by(Grade.created_at.desc(), Grade.id.desc()).all()
        grouped = defaultdict(lambda: defaultdict(list))
        for row in grade_rows:
            subject_name = row.subject.name if row.subject else (row.majlis_subject.name if row.majlis_subject else "-")
            if row.type:
                grouped[subject_name][row.type.name].append(float(row.score or 0))

        summary_rows = []
        for subject_name, type_map in grouped.items():
            type_averages = {}
            for grade_type, scores in type_map.items():
                if scores:
                    type_averages[grade_type] = round(sum(scores) / len(scores), 2)
            summary_rows.append(
                {
                    "subject_name": subject_name,
                    "type_averages": type_averages,
                    "final_score": _calculate_weighted_final(type_averages),
                }
            )
        summary_rows.sort(key=lambda item: (item.get("subject_name") or "").lower())

        return api_success(
            {
                "student": _student_payload(user, selected_child),
                "academic_year": {
                    "id": active_year.id if active_year else 0,
                    "name": active_year.name if active_year else "-",
                    "semester": active_year.semester if active_year else "-",
                },
                "summary": summary_rows,
                "grades": [
                    {
                        "id": row.id,
                        "subject_name": (
                            row.subject.name
                            if row.subject
                            else (row.majlis_subject.name if row.majlis_subject else "-")
                        ),
                        "type": row.type.name if row.type else "-",
                        "type_label": row.type.value if row.type else "-",
                        "score": row.score or 0,
                        "notes": row.notes or "-",
                        "created_at": fmt_datetime(row.created_at),
                    }
                    for row in grade_rows
                ],
            }
        )

    @api_bp.get("/parent/children/<int:child_id>/attendance")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_child_attendance(child_id):
        user, _, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response

        selected_child = _resolve_selected_child(children, child_id)
        if selected_child is None:
            return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)

        attendance_rows = (
            Attendance.query.filter(
                Attendance.participant_type == ParticipantType.STUDENT,
                Attendance.student_id == selected_child.id,
            )
            .order_by(Attendance.date.desc(), Attendance.created_at.desc())
            .limit(120)
            .all()
        )

        recap = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0, "total": 0}
        for row in attendance_rows:
            recap["total"] += 1
            if row.status == AttendanceStatus.HADIR:
                recap["hadir"] += 1
            elif row.status == AttendanceStatus.SAKIT:
                recap["sakit"] += 1
            elif row.status == AttendanceStatus.IZIN:
                recap["izin"] += 1
            elif row.status == AttendanceStatus.ALPA:
                recap["alpa"] += 1

        boarding_rows = []
        boarding_recap = {"hadir": 0, "sakit": 0, "izin": 0, "alpa": 0, "total": 0}
        is_boarding_student = bool(selected_child.boarding_dormitory_id)
        if is_boarding_student:
            boarding_rows = (
                BoardingAttendance.query.filter(BoardingAttendance.student_id == selected_child.id)
                .order_by(BoardingAttendance.date.desc(), BoardingAttendance.created_at.desc())
                .limit(120)
                .all()
            )
            for row in boarding_rows:
                boarding_recap["total"] += 1
                if row.status == AttendanceStatus.HADIR:
                    boarding_recap["hadir"] += 1
                elif row.status == AttendanceStatus.SAKIT:
                    boarding_recap["sakit"] += 1
                elif row.status == AttendanceStatus.IZIN:
                    boarding_recap["izin"] += 1
                elif row.status == AttendanceStatus.ALPA:
                    boarding_recap["alpa"] += 1

        return api_success(
            {
                "student": _student_payload(user, selected_child),
                "recap": recap,
                "records": [
                    {
                        "id": row.id,
                        "date": fmt_date(row.date),
                        "status": row.status.name if row.status else "-",
                        "status_label": row.status.value if row.status else "-",
                        "teacher_name": (
                            row.teacher.full_name if row.teacher and row.teacher.full_name else "-"
                        ),
                        "notes": row.notes or "-",
                    }
                    for row in attendance_rows
                ],
                "is_boarding_student": is_boarding_student,
                "boarding_recap": boarding_recap,
                "boarding_records": [
                    {
                        "id": row.id,
                        "date": fmt_date(row.date),
                        "activity_name": (
                            row.schedule.activity_name if row.schedule and row.schedule.activity_name else "-"
                        ),
                        "status": row.status.name if row.status else "-",
                        "status_label": row.status.value if row.status else "-",
                        "notes": row.notes or "-",
                    }
                    for row in boarding_rows
                ],
            }
        )

    @api_bp.get("/parent/children/<int:child_id>/behavior")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_child_behavior(child_id):
        user, _, children, error_response = _resolve_parent_children_context()
        if error_response is not None:
            return error_response

        selected_child = _resolve_selected_child(children, child_id)
        if selected_child is None:
            return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)

        reports = (
            BehaviorReport.query.filter(BehaviorReport.student_id == selected_child.id)
            .order_by(BehaviorReport.report_date.desc(), BehaviorReport.created_at.desc())
            .limit(120)
            .all()
        )
        violations = (
            selected_child.violations.order_by(Violation.date.desc(), Violation.created_at.desc()).limit(120).all()
            if hasattr(selected_child, "violations")
            else []
        )
        point_total = sum(int(item.points or 0) for item in violations)

        return api_success(
            {
                "student": _student_payload(user, selected_child),
                "summary": {
                    "point_total": point_total,
                    "violation_count": len(violations),
                    "behavior_report_count": len(reports),
                },
                "reports": [
                    {
                        "id": row.id,
                        "date": fmt_date(row.report_date),
                        "report_type": row.report_type.name if row.report_type else "-",
                        "report_type_label": row.report_type.value if row.report_type else "-",
                        "teacher_name": (
                            row.teacher.full_name if row.teacher and row.teacher.full_name else "-"
                        ),
                        "title": row.title or "-",
                        "description": row.description or "-",
                        "is_resolved": bool(row.is_resolved),
                    }
                    for row in reports
                ],
                "violations": [
                    {
                        "id": row.id,
                        "date": fmt_date(row.date),
                        "description": row.description or "-",
                        "points": row.points or 0,
                        "sanction": row.sanction or "-",
                    }
                    for row in violations
                ],
            }
        )
