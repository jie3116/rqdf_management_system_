from app import create_app
from app.extensions import db
from app.models import (
    ClassRoom,
    EnrollmentStatus,
    GroupMembership,
    MembershipStatus,
    Program,
    ProgramEnrollment,
    ProgramType,
    Student,
    Tenant,
)
from app.services.bahasa_service import assign_student_bahasa_class, ensure_bahasa_program_group


def _default_tenant():
    return Tenant.query.filter_by(is_default=True, is_deleted=False).first()


def repair_bahasa_memberships():
    app = create_app()
    with app.app_context():
        tenant = _default_tenant()
        if tenant is None:
            raise RuntimeError("Default tenant tidak ditemukan.")

        bahasa_program = Program.query.filter_by(
            tenant_id=tenant.id,
            code="BAHASA",
            is_deleted=False,
        ).first()
        if bahasa_program is None:
            raise RuntimeError("Program BAHASA tidak ditemukan untuk tenant default.")

        bahasa_classes = (
            ClassRoom.query.filter(
                ClassRoom.program_type == ProgramType.BAHASA,
                ClassRoom.is_deleted.is_(False),
            )
            .order_by(ClassRoom.name.asc())
            .all()
        )

        stats = {
            "bahasa_classes": len(bahasa_classes),
            "relinked_classes": 0,
            "moved_active_memberships": 0,
            "assigned_from_current_class": 0,
            "classes_without_program_group": 0,
        }

        for class_room in bahasa_classes:
            old_group_id = class_room.program_group_id
            ensure_bahasa_program_group(class_room, tenant_id=tenant.id)
            db.session.flush()
            new_group_id = class_room.program_group_id

            if not new_group_id:
                stats["classes_without_program_group"] += 1
                continue

            if old_group_id and old_group_id != new_group_id:
                stats["relinked_classes"] += 1
                active_memberships = (
                    GroupMembership.query.join(
                        ProgramEnrollment,
                        ProgramEnrollment.id == GroupMembership.enrollment_id,
                    )
                    .filter(
                        GroupMembership.tenant_id == tenant.id,
                        GroupMembership.group_id == old_group_id,
                        GroupMembership.status == MembershipStatus.ACTIVE,
                        GroupMembership.is_deleted.is_(False),
                        ProgramEnrollment.program_id == bahasa_program.id,
                        ProgramEnrollment.status == EnrollmentStatus.ACTIVE,
                        ProgramEnrollment.is_deleted.is_(False),
                    )
                    .all()
                )
                for membership in active_memberships:
                    membership.group_id = new_group_id
                    membership.is_primary = True
                    membership.end_date = None
                    stats["moved_active_memberships"] += 1

        bahasa_current_class_students = (
            Student.query.join(ClassRoom, Student.current_class_id == ClassRoom.id)
            .filter(
                Student.is_deleted.is_(False),
                ClassRoom.program_type == ProgramType.BAHASA,
                ClassRoom.is_deleted.is_(False),
            )
            .all()
        )
        for student in bahasa_current_class_students:
            if assign_student_bahasa_class(student, student.current_class_id):
                stats["assigned_from_current_class"] += 1

        db.session.commit()

        print("Bahasa membership repair completed.")
        for key, value in stats.items():
            print(f"{key}={value}")


if __name__ == "__main__":
    repair_bahasa_memberships()
