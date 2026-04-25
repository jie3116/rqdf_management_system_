from app.extensions import db
from app.models import (
    AcademicYear,
    ClassRoom,
    EnrollmentStatus,
    GroupMembership,
    GroupType,
    MembershipStatus,
    Person,
    Program,
    ProgramEnrollment,
    ProgramGroup,
    ProgramType,
    Student,
    Tenant,
    local_today,
)


def apply_bahasa_student_filter(query):
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
            & (Program.code == "BAHASA")
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
            ClassRoom.program_type == ProgramType.BAHASA,
            Student.is_deleted.is_(False),
            Person.is_deleted.is_(False),
        )
    )
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


def _active_bahasa_enrollment(tenant_id, person_id):
    if not tenant_id or not person_id:
        return None

    return (
        ProgramEnrollment.query.join(ProgramEnrollment.program)
        .filter(
            ProgramEnrollment.tenant_id == tenant_id,
            ProgramEnrollment.person_id == person_id,
            ProgramEnrollment.status == EnrollmentStatus.ACTIVE,
            ProgramEnrollment.is_deleted.is_(False),
            Program.code == "BAHASA",
        )
        .order_by(ProgramEnrollment.join_date.desc(), ProgramEnrollment.id.desc())
        .first()
    )


def _resolve_classroom_tenant_id(class_room, tenant_id=None):
    if tenant_id:
        return tenant_id

    if class_room and class_room.program_group_id:
        group = ProgramGroup.query.filter_by(id=class_room.program_group_id, is_deleted=False).first()
        if group:
            return group.tenant_id

    if class_room and class_room.homeroom_teacher and class_room.homeroom_teacher.user:
        if class_room.homeroom_teacher.user.tenant_id:
            return class_room.homeroom_teacher.user.tenant_id

    tenant = _default_tenant()
    return tenant.id if tenant else None


def list_bahasa_classes():
    classes = (
        ClassRoom.query.outerjoin(ProgramGroup, ProgramGroup.id == ClassRoom.program_group_id)
        .outerjoin(Program, Program.id == ProgramGroup.program_id)
        .filter(
            ClassRoom.is_deleted.is_(False),
            Program.is_deleted.is_(False),
            Program.code == "BAHASA",
        )
        .order_by(ClassRoom.name.asc())
        .all()
    )
    if classes:
        return classes

    return [
        class_room
        for class_room in ClassRoom.query.filter(ClassRoom.is_deleted.is_(False)).order_by(ClassRoom.name.asc()).all()
        if class_room.program_type == ProgramType.BAHASA
    ]


def is_bahasa_classroom(class_room):
    return class_room is not None and class_room.program_type == ProgramType.BAHASA


def ensure_bahasa_program_group(class_room, tenant_id=None):
    if class_room is None or class_room.is_deleted or class_room.program_type != ProgramType.BAHASA:
        return None

    resolved_tenant_id = _resolve_classroom_tenant_id(class_room, tenant_id=tenant_id)
    if resolved_tenant_id is None:
        return None

    program = Program.query.filter_by(
        tenant_id=resolved_tenant_id,
        code="BAHASA",
        is_deleted=False,
    ).first()
    if program is None:
        return None

    group = None
    if class_room.program_group_id:
        group = ProgramGroup.query.filter_by(
            id=class_room.program_group_id,
            tenant_id=resolved_tenant_id,
            is_deleted=False,
        ).first()
        if group is not None and group.program_id != program.id:
            group = None

    if group is None:
        group = ProgramGroup.query.filter_by(
            tenant_id=resolved_tenant_id,
            program_id=program.id,
            academic_year_id=class_room.academic_year_id,
            name=class_room.name,
            is_deleted=False,
        ).first()

    if group is None:
        group = ProgramGroup(
            tenant_id=resolved_tenant_id,
            program_id=program.id,
            academic_year_id=class_room.academic_year_id,
            name=class_room.name,
        )
        db.session.add(group)

    group.name = class_room.name
    group.group_type = GroupType.CLASS
    group.academic_year_id = class_room.academic_year_id
    group.level_label = str(class_room.grade_level) if class_room.grade_level else None
    group.is_active = True
    db.session.flush()

    class_room.program_group_id = group.id
    return group


def list_bahasa_students_for_class(class_id):
    return (
        Student.query.join(Person, Person.id == Student.person_id)
        .join(
            ProgramEnrollment,
            (ProgramEnrollment.person_id == Student.person_id)
            & (ProgramEnrollment.status == EnrollmentStatus.ACTIVE)
            & (ProgramEnrollment.is_deleted.is_(False)),
        )
        .join(
            Program,
            (Program.id == ProgramEnrollment.program_id)
            & (Program.code == "BAHASA")
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
            ClassRoom.id == class_id,
            Student.is_deleted.is_(False),
            Person.is_deleted.is_(False),
        )
        .order_by(Student.full_name.asc())
        .distinct()
        .all()
    )


def get_student_bahasa_classroom(student):
    tenant_id = _resolve_student_tenant_id(student)
    if not tenant_id or not student.person_id:
        return None

    enrollment = _active_bahasa_enrollment(tenant_id, student.person_id)
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


def assign_student_bahasa_class(student, class_id):
    tenant_id = _resolve_student_tenant_id(student)
    if not tenant_id or not student.person_id:
        return False

    enrollment = _active_bahasa_enrollment(tenant_id, student.person_id)
    target_class = None
    if class_id:
        target_class = ClassRoom.query.filter_by(id=class_id, is_deleted=False).first()
        if target_class and target_class.program_group_id:
            target_group = ProgramGroup.query.filter_by(id=target_class.program_group_id, is_deleted=False).first()
            if target_group and target_group.tenant_id != tenant_id:
                return False
        ensure_bahasa_program_group(target_class, tenant_id=tenant_id)

    is_bahasa_class = (
        target_class is not None
        and target_class.program_group_id is not None
        and target_class.program_type == ProgramType.BAHASA
    )

    if enrollment is None and is_bahasa_class:
        program = Program.query.filter_by(tenant_id=tenant_id, code="BAHASA", is_deleted=False).first()
        if program is None:
            return False

        enrollment = ProgramEnrollment(
            tenant_id=tenant_id,
            person_id=student.person_id,
            program_id=program.id,
        )
        db.session.add(enrollment)

    if enrollment is None and not is_bahasa_class:
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

    if not is_bahasa_class:
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
