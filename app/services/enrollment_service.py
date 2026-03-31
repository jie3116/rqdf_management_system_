from app.models import EnrollmentStatus, GroupMembership, MembershipStatus, ProgramEnrollment


def get_active_enrollments(tenant_id, person_id, program_code=None):
    query = ProgramEnrollment.query.filter_by(
        tenant_id=tenant_id,
        person_id=person_id,
        status=EnrollmentStatus.ACTIVE,
        is_deleted=False,
    )

    if program_code:
        query = query.join(ProgramEnrollment.program).filter_by(code=program_code)

    return query.order_by(ProgramEnrollment.join_date.desc()).all()


def get_active_group_memberships(tenant_id, enrollment_id, group_type=None):
    query = GroupMembership.query.filter_by(
        tenant_id=tenant_id,
        enrollment_id=enrollment_id,
        status=MembershipStatus.ACTIVE,
        is_deleted=False,
    )

    if group_type:
        query = query.join(GroupMembership.group).filter_by(group_type=group_type)

    return query.order_by(GroupMembership.is_primary.desc(), GroupMembership.start_date.desc()).all()
