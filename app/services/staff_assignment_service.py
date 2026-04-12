from app.extensions import db
from app.models import (
    AcademicYear,
    AssignmentRole,
    ClassRoom,
    EducationLevel,
    Program,
    ProgramGroup,
    ProgramType,
    Schedule,
    StaffAssignment,
    Teacher,
    Tenant,
    local_today,
)


def _default_tenant():
    return Tenant.query.filter_by(is_default=True, is_deleted=False).first()


def _active_academic_year():
    return AcademicYear.query.filter_by(is_active=True, is_deleted=False).first()


def _teacher_person_id(teacher):
    return teacher.person_id if teacher and teacher.person_id else None


def _program_code_for_class(class_room):
    if class_room is None:
        return None
    if class_room.program_type == ProgramType.BAHASA:
        return "BAHASA"
    if class_room.program_type == ProgramType.MAJLIS_TALIM:
        return "MAJLIS_TALIM"
    if class_room.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ):
        return "RUMAH_QURAN"
    if class_room.education_level == EducationLevel.SD:
        return "SEKOLAH_SD"
    if class_room.education_level == EducationLevel.SMP:
        return "SEKOLAH_SMP"
    if class_room.education_level == EducationLevel.SMA:
        return "SEKOLAH_SMA"
    if class_room.grade_level:
        if class_room.grade_level <= 6:
            return "SEKOLAH_SD"
        if class_room.grade_level <= 9:
            return "SEKOLAH_SMP"
        return "SEKOLAH_SMA"
    return None


def _program_for_class(class_room, tenant_id):
    code = _program_code_for_class(class_room)
    if not code or not tenant_id:
        return None
    return Program.query.filter_by(
        tenant_id=tenant_id,
        code=code,
        is_deleted=False,
    ).first()


def _group_for_class(class_room):
    if class_room is None or not class_room.program_group_id:
        return None
    return ProgramGroup.query.filter_by(
        id=class_room.program_group_id,
        is_deleted=False,
    ).first()


def _ensure_staff_assignment(person_id, tenant_id, program_id, group_id, academic_year_id, assignment_role, notes):
    if not (person_id and tenant_id and program_id):
        return False

    assignment = (
        StaffAssignment.query.filter_by(
            tenant_id=tenant_id,
            person_id=person_id,
            program_id=program_id,
            group_id=group_id,
            academic_year_id=academic_year_id,
            assignment_role=assignment_role,
            is_deleted=False,
        )
        .order_by(StaffAssignment.id.desc())
        .first()
    )

    if assignment is None:
        assignment = StaffAssignment(
            tenant_id=tenant_id,
            person_id=person_id,
            program_id=program_id,
            group_id=group_id,
            academic_year_id=academic_year_id,
            assignment_role=assignment_role,
        )
        db.session.add(assignment)

    assignment.start_date = assignment.start_date or local_today()
    assignment.end_date = None
    assignment.notes = notes
    return assignment.id is None


def sync_teacher_staff_assignments(teacher):
    if teacher is None:
        return {"created": 0, "skipped": 0}

    tenant = _default_tenant()
    person_id = _teacher_person_id(teacher)
    if tenant is None or not person_id:
        return {"created": 0, "skipped": 1}

    created = 0
    academic_year = _active_academic_year()

    homeroom_classes = (
        ClassRoom.query.filter_by(homeroom_teacher_id=teacher.id, is_deleted=False)
        .order_by(ClassRoom.id.asc())
        .all()
    )
    for class_room in homeroom_classes:
        program = _program_for_class(class_room, tenant.id)
        group = _group_for_class(class_room)
        if program is None:
            continue
        if _ensure_staff_assignment(
            person_id=person_id,
            tenant_id=tenant.id,
            program_id=program.id,
            group_id=group.id if group else None,
            academic_year_id=class_room.academic_year_id or (academic_year.id if academic_year else None),
            assignment_role=AssignmentRole.HOMEROOM,
            notes="Legacy homeroom backfill",
        ):
            created += 1

    schedules = (
        Schedule.query.filter_by(teacher_id=teacher.id, is_deleted=False)
        .order_by(Schedule.id.asc())
        .all()
    )
    seen_schedule_keys = set()
    for schedule in schedules:
        if not schedule.class_room:
            continue
        program = _program_for_class(schedule.class_room, tenant.id)
        group = _group_for_class(schedule.class_room)
        if program is None:
            continue
        key = (
            program.id,
            group.id if group else None,
            schedule.class_room.academic_year_id or (academic_year.id if academic_year else None),
            AssignmentRole.SUBJECT_TEACHER,
        )
        if key in seen_schedule_keys:
            continue
        seen_schedule_keys.add(key)
        if _ensure_staff_assignment(
            person_id=person_id,
            tenant_id=tenant.id,
            program_id=program.id,
            group_id=group.id if group else None,
            academic_year_id=schedule.class_room.academic_year_id or (academic_year.id if academic_year else None),
            assignment_role=AssignmentRole.SUBJECT_TEACHER,
            notes="Legacy schedule backfill",
        ):
            created += 1

    return {"created": created, "skipped": 0}


def _active_staff_assignments_for_teacher(teacher, assignment_role=None):
    tenant = _default_tenant()
    person_id = _teacher_person_id(teacher)
    if teacher is None or tenant is None or not person_id:
        return []

    query = StaffAssignment.query.filter(
        StaffAssignment.tenant_id == tenant.id,
        StaffAssignment.person_id == person_id,
        StaffAssignment.is_deleted.is_(False),
        StaffAssignment.end_date.is_(None),
    )
    if assignment_role is not None:
        query = query.filter(StaffAssignment.assignment_role == assignment_role)

    return query.order_by(StaffAssignment.id.asc()).all()


def list_teacher_homeroom_classes_from_assignments(teacher):
    classes = []
    seen_ids = set()
    for assignment in _active_staff_assignments_for_teacher(teacher, AssignmentRole.HOMEROOM):
        if not assignment.group_id:
            continue
        class_room = ClassRoom.query.filter_by(
            program_group_id=assignment.group_id,
            is_deleted=False,
        ).first()
        if class_room and class_room.id not in seen_ids:
            seen_ids.add(class_room.id)
            classes.append(class_room)
    return classes


def list_teacher_subject_classes_from_assignments(teacher):
    classes = []
    seen_ids = set()
    for assignment in _active_staff_assignments_for_teacher(teacher, AssignmentRole.SUBJECT_TEACHER):
        if not assignment.group_id:
            continue
        class_room = ClassRoom.query.filter_by(
            program_group_id=assignment.group_id,
            is_deleted=False,
        ).first()
        if class_room and class_room.id not in seen_ids:
            seen_ids.add(class_room.id)
            classes.append(class_room)
    return classes


def list_teacher_assignment_groups_from_assignments(teacher):
    groups = {}
    for assignment in _active_staff_assignments_for_teacher(teacher):
        if not assignment.program:
            continue
        code = assignment.program.code
        groups.setdefault(code, []).append(assignment)
    return groups


def display_assignment_role(assignment_role, program_code=None):
    if assignment_role is None:
        return "-"

    if assignment_role == AssignmentRole.SUBJECT_TEACHER:
        return "Guru Mapel"

    if assignment_role == AssignmentRole.HOMEROOM:
        if program_code and program_code.startswith("SEKOLAH_"):
            return "Wali Kelas"
        return "Penanggung Jawab Kelas"

    if assignment_role == AssignmentRole.MURABBI:
        return "Pendamping Program"

    if assignment_role == AssignmentRole.MUSYRIF:
        return "Pembina Asrama"

    if assignment_role == AssignmentRole.PEMBINA:
        return "Pendamping Program"

    return assignment_role.value


def backfill_all_teacher_staff_assignments():
    summary = {"teachers": 0, "created": 0, "skipped": 0}
    teachers = Teacher.query.filter_by(is_deleted=False).order_by(Teacher.id.asc()).all()
    for teacher in teachers:
        result = sync_teacher_staff_assignments(teacher)
        summary["teachers"] += 1
        summary["created"] += result["created"]
        summary["skipped"] += result["skipped"]
    return summary
