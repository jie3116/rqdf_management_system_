from app.extensions import db
from app.models import (
    AcademicYear,
    ClassRoom,
    EnrollmentStatus,
    GroupMembership,
    MembershipStatus,
    Person,
    Program,
    ProgramEnrollment,
    Tenant,
    ProgramType,
    Student,
    local_today,
)


def apply_rumah_quran_student_filter(query, track=None):
    student_ids_query = (
        db.session.query(Student.id)
        .join(Person, Person.id == Student.person_id)
        .join(
            ProgramEnrollment,
            (ProgramEnrollment.person_id == Student.person_id)
            & (ProgramEnrollment.status == EnrollmentStatus.ACTIVE)
            & (ProgramEnrollment.is_deleted.is_(False)),
        )
        .join(
            Program,
            (Program.id == ProgramEnrollment.program_id)
            & (Program.code == "RUMAH_QURAN")
            & (Program.is_deleted.is_(False)),
        )
        .join(
            GroupMembership,
            (GroupMembership.enrollment_id == ProgramEnrollment.id)
            & (GroupMembership.status == MembershipStatus.ACTIVE)
            & (GroupMembership.is_deleted.is_(False)),
        )
        .join(
            ClassRoom,
            (ClassRoom.program_group_id == GroupMembership.group_id)
            & (ClassRoom.is_deleted.is_(False)),
        )
        .filter(
            Student.is_deleted.is_(False),
            Person.is_deleted.is_(False),
        )
    )

    if track == "reguler":
        student_ids_query = student_ids_query.filter(ClassRoom.program_type == ProgramType.RQDF_SORE)
    elif track == "takhosus":
        student_ids_query = student_ids_query.filter(ClassRoom.program_type == ProgramType.TAKHOSUS_TAHFIDZ)

    return query.filter(Student.id.in_(student_ids_query.distinct()))


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


def _active_rumah_quran_enrollment(tenant_id, person_id):
    if not tenant_id or not person_id:
        return None

    return (
        ProgramEnrollment.query.join(ProgramEnrollment.program)
        .filter(
            ProgramEnrollment.tenant_id == tenant_id,
            ProgramEnrollment.person_id == person_id,
            ProgramEnrollment.status == EnrollmentStatus.ACTIVE,
            ProgramEnrollment.is_deleted.is_(False),
            Program.code == "RUMAH_QURAN",
        )
        .order_by(ProgramEnrollment.join_date.desc(), ProgramEnrollment.id.desc())
        .first()
    )


def list_rumah_quran_classes():
    return (
        ClassRoom.query.filter(
            ClassRoom.is_deleted.is_(False),
            ClassRoom.program_type.in_([ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ]),
        )
        .order_by(ClassRoom.program_type.asc(), ClassRoom.name.asc())
        .all()
    )


def get_student_rumah_quran_classroom(student):
    tenant_id = _resolve_student_tenant_id(student)
    if not tenant_id or not student.person_id:
        return None

    enrollment = _active_rumah_quran_enrollment(tenant_id, student.person_id)
    if enrollment is None:
        return None

    membership = (
        GroupMembership.query.filter_by(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            status=MembershipStatus.ACTIVE,
            is_deleted=False,
        )
        .order_by(GroupMembership.is_primary.desc(), GroupMembership.start_date.desc(), GroupMembership.id.desc())
        .first()
    )
    if membership is None:
        return None

    return ClassRoom.query.filter_by(program_group_id=membership.group_id, is_deleted=False).first()


def assign_student_rumah_quran_class(student, class_id):
    tenant_id = _resolve_student_tenant_id(student)
    if not tenant_id or not student.person_id:
        return False

    enrollment = _active_rumah_quran_enrollment(tenant_id, student.person_id)
    target_class = None
    if class_id:
        target_class = ClassRoom.query.filter_by(id=class_id, is_deleted=False).first()

    is_rumah_quran_class = (
        target_class is not None
        and target_class.program_group_id is not None
        and target_class.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ)
    )

    if enrollment is None and is_rumah_quran_class:
        program = Program.query.filter_by(tenant_id=tenant_id, code="RUMAH_QURAN", is_deleted=False).first()
        if program is None:
            return False

        enrollment = ProgramEnrollment(
            tenant_id=tenant_id,
            person_id=student.person_id,
            program_id=program.id,
        )
        db.session.add(enrollment)

    if enrollment is None and not is_rumah_quran_class:
        return False

    active_year = _active_academic_year()
    enrollment.academic_year_id = (
        target_class.academic_year_id
        if target_class and target_class.academic_year_id
        else (active_year.id if active_year else None)
    )
    enrollment.status = EnrollmentStatus.ACTIVE
    enrollment.join_date = enrollment.join_date or local_today()
    enrollment.origin_type = enrollment.origin_type or "CLASS_ASSIGN"
    db.session.flush()

    membership = (
        GroupMembership.query.filter_by(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            status=MembershipStatus.ACTIVE,
            is_deleted=False,
        )
        .order_by(GroupMembership.is_primary.desc(), GroupMembership.start_date.desc(), GroupMembership.id.desc())
        .first()
    )

    if not is_rumah_quran_class:
        if membership is not None:
            membership.status = MembershipStatus.LEFT
            membership.end_date = local_today()
        return True

    if membership is None:
        membership = GroupMembership(
            tenant_id=tenant_id,
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


def sync_student_rumah_quran_membership(student):
    current_class = student.current_class
    target_class_id = (
        current_class.id
        if current_class
        and current_class.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ)
        else None
    )
    return assign_student_rumah_quran_class(student, target_class_id)
