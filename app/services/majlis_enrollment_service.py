from types import SimpleNamespace

from sqlalchemy import or_

from app.extensions import db
from app.models import (
    AcademicYear,
    ClassRoom,
    EnrollmentStatus,
    GroupMembership,
    MajlisParticipant,
    MembershipStatus,
    Person,
    PersonKind,
    Program,
    ProgramEnrollment,
    Tenant,
    User,
    local_today,
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
                majlis_class_id=majlis_class.id if majlis_class else None,
                majlis_class=majlis_class,
            )
        )

    return rows


def assign_majlis_class(participant_id, class_id):
    participant = MajlisParticipant.query.filter_by(id=participant_id, is_deleted=False).first()
    if participant is None:
        return False

    target_class = None
    if class_id:
        target_class = ClassRoom.query.filter_by(id=class_id, is_deleted=False).first()

    participant.majlis_class_id = class_id

    if not participant.person_id:
        return True

    enrollment = get_active_majlis_enrollment(participant.user.tenant_id if participant.user else None, participant.person_id)
    if enrollment is None:
        return True

    membership = get_active_majlis_membership(enrollment.tenant_id, enrollment.person_id)

    if target_class is None or not target_class.program_group_id:
        if membership is not None:
            membership.status = MembershipStatus.LEFT
            membership.end_date = local_today()
        return True

    if membership is None:
        membership = GroupMembership(
            tenant_id=enrollment.tenant_id,
            enrollment_id=enrollment.id,
            group_id=target_class.program_group_id,
        )
        db.session.add(membership)

    membership.group_id = target_class.program_group_id
    membership.status = MembershipStatus.ACTIVE
    membership.start_date = local_today()
    membership.end_date = None
    membership.is_primary = True
    return True


def sync_majlis_participant_profile(participant, full_name, phone, address):
    participant.full_name = full_name
    participant.phone = phone
    participant.address = address or None

    person = None
    if participant.person_id:
        person = Person.query.filter_by(id=participant.person_id, is_deleted=False).first()
    elif participant.user and participant.user.person:
        person = participant.user.person

    if person:
        person.full_name = full_name
        person.phone = phone
        person.address = address or None

    return participant


def _default_tenant():
    return Tenant.query.filter_by(is_default=True).first()


def _active_academic_year():
    return AcademicYear.query.filter_by(is_active=True).first()


def _majlis_program(tenant_id):
    return Program.query.filter_by(tenant_id=tenant_id, code="MAJLIS_TALIM", is_deleted=False).first()


def _ensure_person_for_majlis_user(user, full_name, phone, address):
    person = user.person
    tenant_id = user.tenant_id
    if tenant_id is None:
        tenant = _default_tenant()
        tenant_id = tenant.id if tenant else None
        user.tenant_id = tenant_id

    if tenant_id is None:
        raise RuntimeError("Tenant default tidak ditemukan untuk peserta majlis.")

    if person is None:
        person = Person.query.filter_by(tenant_id=tenant_id, user_id=user.id, is_deleted=False).first()

    if person is None:
        person = Person(
            tenant_id=tenant_id,
            user_id=user.id,
            person_code=f"EXTERNAL-{user.id}",
            person_kind=PersonKind.EXTERNAL,
        )
        db.session.add(person)

    person.full_name = full_name
    person.phone = phone
    person.address = address or None
    person.is_active = True
    db.session.flush()
    return person


def ensure_majlis_participant_acceptance(user, full_name, phone, address, job=None, class_id=None, join_date=None):
    participant = user.majlis_profile
    if participant is None:
        participant = MajlisParticipant(user_id=user.id)
        db.session.add(participant)

    participant.full_name = full_name
    participant.phone = phone
    participant.address = address or None
    participant.job = job or None
    participant.join_date = join_date or participant.join_date or local_today()
    participant.majlis_class_id = class_id

    person = _ensure_person_for_majlis_user(user, full_name, phone, address)
    participant.person_id = person.id

    program = _majlis_program(user.tenant_id)
    if program is None:
        raise RuntimeError("Program MAJLIS_TALIM belum tersedia.")

    enrollment = get_active_majlis_enrollment(user.tenant_id, person.id)
    if enrollment is None:
        enrollment = ProgramEnrollment(
            tenant_id=user.tenant_id,
            person_id=person.id,
            program_id=program.id,
        )
        db.session.add(enrollment)

    target_class = None
    if class_id:
        target_class = ClassRoom.query.filter_by(id=class_id, is_deleted=False).first()

    active_year = _active_academic_year()
    enrollment.academic_year_id = (
        target_class.academic_year_id
        if target_class and target_class.academic_year_id
        else (active_year.id if active_year else None)
    )
    enrollment.status = EnrollmentStatus.ACTIVE
    enrollment.join_date = join_date or participant.join_date or local_today()
    enrollment.origin_type = "PPDB_ACCEPT"
    enrollment.notes = "Sinkron dari penerimaan PPDB majlis"
    db.session.flush()

    assign_majlis_class(participant.id, class_id)
    return participant
