from flask import g, request

from app.models import (
    Attendance,
    ClassRoom,
    Invoice,
    ParticipantType,
    PaymentStatus,
    RecitationRecord,
    TahfidzEvaluation,
    TahfidzRecord,
    TahfidzSummary,
    UserRole,
)
from app.services.formal_service import get_student_formal_classroom
from app.utils.announcements import get_announcements_for_dashboard
from app.utils.tenant import resolve_tenant_id, scoped_classrooms_query

from .common import (
    announcement_payload,
    api_error,
    api_success,
    fmt_datetime,
    mobile_auth_required,
    parent_children_for_tenant,
    serialize_child,
)


def register_parent_routes(api_bp):
    @api_bp.get("/parent/children")
    @mobile_auth_required(UserRole.WALI_MURID)
    def parent_children():
        user = g.mobile_user
        parent = user.parent_profile
        if parent is None:
            return api_error("not_found", "Profil wali murid tidak ditemukan.", 404)

        children = parent_children_for_tenant(user, parent)
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
        user = g.mobile_user
        parent = user.parent_profile
        if parent is None:
            return api_error("not_found", "Profil wali murid tidak ditemukan.", 404)

        children = parent_children_for_tenant(user, parent)
        if not children:
            return api_error("not_found", "Data anak belum tersedia.", 404)

        selected_student_id = request.args.get("student_id", type=int)
        selected_child = None
        if selected_student_id:
            selected_child = next((item for item in children if item.id == selected_student_id), None)
            if selected_child is None:
                return api_error("forbidden", "Akses data siswa tidak diizinkan.", 403)
        if selected_child is None:
            selected_child = children[0]

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

        active_class = get_student_formal_classroom(selected_child) or selected_child.current_class
        active_class_id = active_class.id if active_class else None
        tenant_id = resolve_tenant_id(user, fallback_default=False)
        if tenant_id and active_class_id:
            visible_class = scoped_classrooms_query(tenant_id).filter(ClassRoom.id == active_class_id).first()
            if visible_class is None:
                active_class_id = None
                active_class = None
            else:
                active_class = visible_class

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
