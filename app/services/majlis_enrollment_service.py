from app.models import (
    ClassRoom,
    EnrollmentStatus,
    GroupMembership,
    MembershipStatus,
    ProgramEnrollment,
)


def _active_majlis_enrollment_query(tenant_id, person_id):
    return (
        ProgramEnrollment.query.join(ProgramEnrollment.program)
        .filter(
            ProgramEnrollment.tenant_id == tenant_id,
            ProgramEnrollment.person_id == person_id,
            ProgramEnrollment.status == EnrollmentStatus.ACTIVE,
            ProgramEnrollment.is_deleted.is_(False),
        )
        .filter_by(code="MAJLIS_TALIM")
        .order_by(ProgramEnrollment.join_date.desc(), ProgramEnrollment.id.desc())
    )


def get_active_majlis_enrollment(tenant_id, person_id):
    if not tenant_id or not person_id:
        return None
    return _active_majlis_enrollment_query(tenant_id, person_id).first()


def get_active_majlis_membership(tenant_id, person_id):
    enrollment = get_active_majlis_enrollment(tenant_id, person_id)
    if enrollment is None:
        return None

    return (
        GroupMembership.query.filter_by(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            status=MembershipStatus.ACTIVE,
            is_deleted=False,
        )
        .order_by(GroupMembership.is_primary.desc(), GroupMembership.start_date.desc(), GroupMembership.id.desc())
        .first()
    )


def resolve_majlis_classroom(tenant_id, person_id):
    membership = get_active_majlis_membership(tenant_id, person_id)
    if membership is None:
        return None

    return (
        ClassRoom.query.filter_by(
            program_group_id=membership.group_id,
            is_deleted=False,
        )
        .order_by(ClassRoom.id.desc())
        .first()
    )
