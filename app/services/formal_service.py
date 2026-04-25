from app.extensions import db
from app.models import (
    AcademicYear,
    ClassRoom,
    EducationLevel,
    EnrollmentStatus,
    Gender,
    GroupMembership,
    GroupType,
    MembershipStatus,
    Person,
    PersonKind,
    Program,
    ProgramEnrollment,
    ProgramGroup,
    ProgramType,
    Student,
    Tenant,
    local_today,
)


FORMAL_PROGRAM_CODES = ("SEKOLAH_SD", "SEKOLAH_SMP", "SEKOLAH_SMA")


def _default_tenant():
    return Tenant.query.filter_by(is_default=True).first()


def _active_academic_year():
    return AcademicYear.query.filter_by(is_active=True).first()


def _student_tenant_id(student):
    if student.user and student.user.tenant_id:
        return student.user.tenant_id
    if student.parent and student.parent.user and student.parent.user.tenant_id:
        return student.parent.user.tenant_id
    tenant = _default_tenant()
    return tenant.id if tenant else None


def _formal_program_code(class_room):
    if class_room is None:
        return None
    grade_level = class_room.grade_level
    if isinstance(grade_level, str):
        grade_level = grade_level.strip()
        grade_level = int(grade_level) if grade_level.isdigit() else None
    if class_room.education_level == EducationLevel.SD:
        return "SEKOLAH_SD"
    if class_room.education_level == EducationLevel.SMP:
        return "SEKOLAH_SMP"
    if class_room.education_level == EducationLevel.SMA:
        return "SEKOLAH_SMA"
    if grade_level is not None:
        if grade_level <= 6:
            return "SEKOLAH_SD"
        if grade_level <= 9:
            return "SEKOLAH_SMP"
        return "SEKOLAH_SMA"
    if class_room.program_type == ProgramType.SEKOLAH_FULLDAY:
        return "SEKOLAH_SD"
    return None


def is_formal_classroom(class_room):
    return _formal_program_code(class_room) is not None


def _formal_program(tenant_id, class_room):
    program_code = _formal_program_code(class_room)
    if not tenant_id or not program_code:
        return None
    return Program.query.filter_by(
        tenant_id=tenant_id,
        code=program_code,
        is_deleted=False,
    ).first()


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


def ensure_formal_program_group(class_room, tenant_id=None):
    if class_room is None or class_room.is_deleted or not is_formal_classroom(class_room):
        return None

    resolved_tenant_id = _resolve_classroom_tenant_id(class_room, tenant_id=tenant_id)
    if resolved_tenant_id is None:
        return None

    program = _formal_program(resolved_tenant_id, class_room)
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
    group.gender_scope = None
    group.is_active = True
    db.session.flush()

    class_room.program_group_id = group.id
    return group


def _ensure_student_person(student, tenant_id):
    if student.person_id:
        person = Person.query.filter_by(id=student.person_id, tenant_id=tenant_id).first()
        if person:
            person.full_name = student.full_name or person.full_name or "-"
            person.gender = student.gender or person.gender
            person.date_of_birth = student.date_of_birth or person.date_of_birth
            person.address = student.address or person.address
            person.person_kind = PersonKind.STUDENT
            person.is_active = True
            return person

    person = None
    if student.user_id:
        person = Person.query.filter_by(tenant_id=tenant_id, user_id=student.user_id, is_deleted=False).first()

    if person is None:
        if student.id is None:
            db.session.flush()
        person = Person(
            tenant_id=tenant_id,
            user_id=student.user_id,
            person_code=f"STUDENT-{student.id}",
            full_name=student.full_name or "-",
            gender=student.gender,
            date_of_birth=student.date_of_birth,
            address=student.address,
            person_kind=PersonKind.STUDENT,
            is_active=True,
        )
        db.session.add(person)
        db.session.flush()

    person.full_name = student.full_name or person.full_name or "-"
    person.gender = student.gender or person.gender
    person.date_of_birth = student.date_of_birth or person.date_of_birth
    person.address = student.address or person.address
    person.phone = None
    person.is_active = True
    student.person_id = person.id
    return person


def list_formal_students_for_class(class_id):
    students = (
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
            & (Program.code.in_(FORMAL_PROGRAM_CODES))
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
    if students:
        return students

    return (
        Student.query.filter_by(current_class_id=class_id, is_deleted=False)
        .order_by(Student.full_name.asc())
        .all()
    )


def _active_formal_enrollment(tenant_id, person_id, class_room):
    program = _formal_program(tenant_id, class_room)
    if not tenant_id or not person_id or program is None:
        return None

    return (
        ProgramEnrollment.query.filter_by(
            tenant_id=tenant_id,
            person_id=person_id,
            program_id=program.id,
            status=EnrollmentStatus.ACTIVE,
            is_deleted=False,
        )
        .order_by(ProgramEnrollment.join_date.desc(), ProgramEnrollment.id.desc())
        .first()
    )


def get_student_formal_classroom(student):
    if student is None:
        return None

    tenant_id = _student_tenant_id(student)
    person_id = student.person_id
    current_class = student.current_class

    if not tenant_id or not person_id:
        return current_class if is_formal_classroom(current_class) else None

    membership = (
        GroupMembership.query.join(GroupMembership.enrollment)
        .join(ProgramEnrollment.program)
        .filter(
            ProgramEnrollment.tenant_id == tenant_id,
            ProgramEnrollment.person_id == person_id,
            ProgramEnrollment.status == EnrollmentStatus.ACTIVE,
            ProgramEnrollment.is_deleted.is_(False),
            Program.code.in_(FORMAL_PROGRAM_CODES),
            Program.is_deleted.is_(False),
            GroupMembership.status == MembershipStatus.ACTIVE,
            GroupMembership.is_deleted.is_(False),
        )
        .order_by(
            GroupMembership.is_primary.desc(),
            GroupMembership.start_date.desc(),
            GroupMembership.id.desc(),
        )
        .first()
    )

    if membership is not None:
        class_room = ClassRoom.query.filter_by(
            program_group_id=membership.group_id,
            is_deleted=False,
        ).first()
        if class_room is not None:
            return class_room

    return current_class if is_formal_classroom(current_class) else None


def sync_student_formal_class_membership(student, class_id=None):
    if student is None:
        return False

    target_class_id = class_id if class_id is not None else student.current_class_id
    target_class = (
        ClassRoom.query.filter_by(id=target_class_id, is_deleted=False).first()
        if target_class_id
        else None
    )
    tenant_id = _student_tenant_id(student)
    if not tenant_id:
        return False

    if student.id is None:
        db.session.flush()
    person = _ensure_student_person(student, tenant_id)
    db.session.flush()

    # Close all active formal memberships when student leaves formal class context.
    active_formal_enrollments = (
        ProgramEnrollment.query.join(ProgramEnrollment.program)
        .filter(
            ProgramEnrollment.tenant_id == tenant_id,
            ProgramEnrollment.person_id == person.id,
            ProgramEnrollment.status == EnrollmentStatus.ACTIVE,
            ProgramEnrollment.is_deleted.is_(False),
            Program.code.in_(FORMAL_PROGRAM_CODES),
        )
        .all()
    )

    if target_class is None or not is_formal_classroom(target_class):
        for enrollment in active_formal_enrollments:
            memberships = GroupMembership.query.filter_by(
                tenant_id=tenant_id,
                enrollment_id=enrollment.id,
                status=MembershipStatus.ACTIVE,
                is_deleted=False,
            ).all()
            for membership in memberships:
                membership.status = MembershipStatus.LEFT
                membership.end_date = local_today()
        return True

    if target_class.program_group_id:
        target_group = ProgramGroup.query.filter_by(id=target_class.program_group_id, is_deleted=False).first()
        if target_group and target_group.tenant_id != tenant_id:
            return False

    ensure_formal_program_group(target_class, tenant_id=tenant_id)
    program = _formal_program(tenant_id, target_class)
    if program is None or target_class.program_group_id is None:
        return False

    active_year = _active_academic_year()
    enrollment = _active_formal_enrollment(tenant_id, person.id, target_class)
    if enrollment is None:
        enrollment = ProgramEnrollment(
            tenant_id=tenant_id,
            person_id=person.id,
            program_id=program.id,
        )
        db.session.add(enrollment)

    enrollment.academic_year_id = (
        target_class.academic_year_id
        if target_class.academic_year_id
        else (active_year.id if active_year else None)
    )
    enrollment.status = EnrollmentStatus.ACTIVE
    enrollment.join_date = enrollment.join_date or local_today()
    enrollment.origin_type = enrollment.origin_type or "CLASS_ASSIGN"
    db.session.flush()

    # Close active formal memberships from other groups/programs first.
    for active_enrollment in active_formal_enrollments:
        memberships = GroupMembership.query.filter_by(
            tenant_id=tenant_id,
            enrollment_id=active_enrollment.id,
            status=MembershipStatus.ACTIVE,
            is_deleted=False,
        ).all()
        for membership in memberships:
            if active_enrollment.id != enrollment.id or membership.group_id != target_class.program_group_id:
                membership.status = MembershipStatus.LEFT
                membership.end_date = local_today()

    membership = (
        GroupMembership.query.filter_by(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            group_id=target_class.program_group_id,
            is_deleted=False,
        )
        .order_by(GroupMembership.id.desc())
        .first()
    )
    if membership is None:
        membership = GroupMembership(
            tenant_id=tenant_id,
            enrollment_id=enrollment.id,
            group_id=target_class.program_group_id,
        )
        db.session.add(membership)

    membership.status = MembershipStatus.ACTIVE
    membership.start_date = local_today()
    membership.end_date = None
    membership.is_primary = True
    return True
