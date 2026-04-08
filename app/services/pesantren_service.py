from app.extensions import db
from app.models import (
    AcademicYear,
    BoardingDormitory,
    EnrollmentStatus,
    GroupMembership,
    MembershipStatus,
    Program,
    ProgramEnrollment,
    Student,
    Tenant,
    local_today,
)


def _default_tenant():
    return Tenant.query.filter_by(is_default=True).first()


def _active_academic_year():
    return AcademicYear.query.filter_by(is_active=True).first()


def _resolve_student_tenant_id(student):
    if student.user and student.user.tenant_id:
        return student.user.tenant_id
    if student.parent and student.parent.user and student.parent.user.tenant_id:
        return student.parent.user.tenant_id
    tenant = _default_tenant()
    return tenant.id if tenant else None


def _active_pesantren_enrollment(tenant_id, person_id):
    if not tenant_id or not person_id:
        return None

    return (
        ProgramEnrollment.query.join(ProgramEnrollment.program)
        .filter(
            ProgramEnrollment.tenant_id == tenant_id,
            ProgramEnrollment.person_id == person_id,
            ProgramEnrollment.status == EnrollmentStatus.ACTIVE,
            ProgramEnrollment.is_deleted.is_(False),
            Program.code == "PESANTREN",
        )
        .order_by(ProgramEnrollment.join_date.desc(), ProgramEnrollment.id.desc())
        .first()
    )


def list_students_for_dormitory(dormitory_id):
    return (
        Student.query.join(
            ProgramEnrollment,
            (ProgramEnrollment.person_id == Student.person_id)
            & (ProgramEnrollment.status == EnrollmentStatus.ACTIVE)
            & (ProgramEnrollment.is_deleted.is_(False)),
        )
        .join(
            Program,
            (Program.id == ProgramEnrollment.program_id)
            & (Program.code == "PESANTREN")
            & (Program.is_deleted.is_(False)),
        )
        .join(
            GroupMembership,
            (GroupMembership.enrollment_id == ProgramEnrollment.id)
            & (GroupMembership.status == MembershipStatus.ACTIVE)
            & (GroupMembership.is_deleted.is_(False)),
        )
        .join(
            BoardingDormitory,
            (BoardingDormitory.program_group_id == GroupMembership.group_id)
            & (BoardingDormitory.is_deleted.is_(False)),
        )
        .filter(
            BoardingDormitory.id == dormitory_id,
            Student.is_deleted.is_(False),
        )
        .order_by(Student.full_name.asc())
        .distinct()
        .all()
    )


def sync_student_dormitory_membership(student, dormitory_id):
    tenant_id = _resolve_student_tenant_id(student)
    if not tenant_id or not student.person_id:
        return False

    enrollment = _active_pesantren_enrollment(tenant_id, student.person_id)
    target_dormitory = None
    if dormitory_id:
        target_dormitory = BoardingDormitory.query.filter_by(id=dormitory_id, is_deleted=False).first()

    is_valid_dormitory = target_dormitory is not None and target_dormitory.program_group_id is not None

    if enrollment is None and is_valid_dormitory:
        program = Program.query.filter_by(tenant_id=tenant_id, code="PESANTREN", is_deleted=False).first()
        if program is None:
            return False

        enrollment = ProgramEnrollment(
            tenant_id=tenant_id,
            person_id=student.person_id,
            program_id=program.id,
        )
        db.session.add(enrollment)

    if enrollment is None and not is_valid_dormitory:
        return False

    active_year = _active_academic_year()
    enrollment.academic_year_id = active_year.id if active_year else None
    enrollment.status = EnrollmentStatus.ACTIVE
    enrollment.join_date = enrollment.join_date or local_today()
    enrollment.origin_type = enrollment.origin_type or "BOARDING_ASSIGN"
    db.session.flush()

    active_memberships = (
        GroupMembership.query.filter_by(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            status=MembershipStatus.ACTIVE,
            is_deleted=False,
        )
        .order_by(GroupMembership.id.asc())
        .all()
    )

    if not is_valid_dormitory:
        for membership in active_memberships:
            membership.status = MembershipStatus.LEFT
            membership.end_date = local_today()
        return True

    for membership in active_memberships:
        if membership.group_id != target_dormitory.program_group_id:
            membership.status = MembershipStatus.LEFT
            membership.end_date = local_today()

    target_membership = next((item for item in active_memberships if item.group_id == target_dormitory.program_group_id), None)
    if target_membership is None:
        target_membership = GroupMembership(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            group_id=target_dormitory.program_group_id,
        )
        db.session.add(target_membership)

    target_membership.status = MembershipStatus.ACTIVE
    target_membership.start_date = local_today()
    target_membership.end_date = None
    target_membership.is_primary = True
    return True
