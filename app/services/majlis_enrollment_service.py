from types import SimpleNamespace

from sqlalchemy import or_

from app.models import (
    ClassRoom,
    EnrollmentStatus,
    GroupMembership,
    MajlisParticipant,
    MembershipStatus,
    Person,
    PersonKind,
    Program,
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
            Program.code == "MAJLIS_TALIM",
        )
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


def list_active_majlis_participants(search=None):
    search = (search or "").strip()

    query = (
        ProgramEnrollment.query.join(ProgramEnrollment.program)
        .join(Person, Person.id == ProgramEnrollment.person_id)
        .outerjoin(
            MajlisParticipant,
            (MajlisParticipant.person_id == ProgramEnrollment.person_id)
            & (MajlisParticipant.is_deleted.is_(False)),
        )
        .filter(
            Program.code == "MAJLIS_TALIM",
            ProgramEnrollment.status == EnrollmentStatus.ACTIVE,
            ProgramEnrollment.is_deleted.is_(False),
            Person.is_deleted.is_(False),
            Person.person_kind == PersonKind.EXTERNAL,
        )
        .order_by(Person.full_name.asc(), ProgramEnrollment.id.asc())
    )

    if search:
        query = query.outerjoin(
            GroupMembership,
            (GroupMembership.enrollment_id == ProgramEnrollment.id)
            & (GroupMembership.status == MembershipStatus.ACTIVE)
            & (GroupMembership.is_deleted.is_(False)),
        ).outerjoin(
            ClassRoom,
            (ClassRoom.program_group_id == GroupMembership.group_id)
            & (ClassRoom.is_deleted.is_(False)),
        ).filter(
            or_(
                Person.full_name.ilike(f"%{search}%"),
                Person.phone.ilike(f"%{search}%"),
                ClassRoom.name.ilike(f"%{search}%"),
            )
        )

    enrollments = query.all()
    rows = []
    for enrollment in enrollments:
        majlis_class = resolve_majlis_classroom(enrollment.tenant_id, enrollment.person_id)
        rows.append(
            SimpleNamespace(
                id=enrollment.person.user.majlis_profile.id if enrollment.person.user and enrollment.person.user.majlis_profile else None,
                full_name=enrollment.person.full_name,
                phone=enrollment.person.phone,
                address=enrollment.person.address,
                majlis_class=majlis_class,
            )
        )

    return rows
