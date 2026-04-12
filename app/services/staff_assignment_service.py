from app.extensions import db
from app.models import (
    AcademicYear,
    AppConfig,
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

ASSIGNMENT_LABEL_DEFAULTS = {
    "assignment_label.formal_homeroom": ("Wali Kelas", "Label untuk penanggung jawab kelas program formal."),
    "assignment_label.nonformal_homeroom": ("Pembimbing Kelas", "Label untuk penanggung jawab kelas program non-formal."),
    "assignment_label.subject_teacher": ("Guru Mapel", "Label untuk assignment guru mata pelajaran."),
    "assignment_label.program_companion": ("Pendamping Program", "Label umum untuk pendamping atau pembina program."),
    "assignment_label.boarding_supervisor": ("Pembina Asrama", "Label untuk assignment pengasuhan/asrama."),
}


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


def _teacher_by_id(teacher_id):
    if not teacher_id:
        return None
    return Teacher.query.filter_by(id=teacher_id, is_deleted=False).first()


def get_assignable_teacher_classes():
    return (
        ClassRoom.query.filter(
            ClassRoom.is_deleted.is_(False),
            ClassRoom.program_group_id.isnot(None),
        )
        .order_by(ClassRoom.name.asc())
        .all()
    )


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


def create_teacher_staff_assignment(teacher, class_room, assignment_role, notes=None):
    tenant = _default_tenant()
    person_id = _teacher_person_id(teacher)
    if teacher is None or class_room is None or tenant is None or not person_id:
        return False, "Data guru atau kelas belum lengkap."

    if class_room.program_group_id is None:
        return False, "Kelas belum terhubung ke program group."

    program = _program_for_class(class_room, tenant.id)
    group = _group_for_class(class_room)
    if program is None or group is None:
        return False, "Program atau group kelas belum valid."

    existing = (
        StaffAssignment.query.filter_by(
            tenant_id=tenant.id,
            person_id=person_id,
            program_id=program.id,
            group_id=group.id,
            academic_year_id=class_room.academic_year_id,
            assignment_role=assignment_role,
            is_deleted=False,
        )
        .order_by(StaffAssignment.id.desc())
        .first()
    )
    if existing and existing.end_date is None:
        return False, "Assignment aktif yang sama sudah ada."

    if existing is None:
        existing = StaffAssignment(
            tenant_id=tenant.id,
            person_id=person_id,
            program_id=program.id,
            group_id=group.id,
            academic_year_id=class_room.academic_year_id,
            assignment_role=assignment_role,
        )
        db.session.add(existing)

    existing.start_date = local_today()
    existing.end_date = None
    existing.notes = notes or "Admin assignment"
    db.session.flush()
    return True, None


def sync_class_homeroom_assignment(class_room):
    tenant = _default_tenant()
    if class_room is None or tenant is None:
        return False, "Data kelas belum lengkap."

    program = _program_for_class(class_room, tenant.id)
    group = _group_for_class(class_room)
    if program is None or group is None:
        return False, None

    teacher = _teacher_by_id(class_room.homeroom_teacher_id)
    person_id = _teacher_person_id(teacher)

    active_assignments = (
        StaffAssignment.query.filter(
            StaffAssignment.tenant_id == tenant.id,
            StaffAssignment.program_id == program.id,
            StaffAssignment.group_id == group.id,
            StaffAssignment.assignment_role == AssignmentRole.HOMEROOM,
            StaffAssignment.is_deleted.is_(False),
            StaffAssignment.end_date.is_(None),
        )
        .order_by(StaffAssignment.id.asc())
        .all()
    )

    for assignment in active_assignments:
        if person_id is None or assignment.person_id != person_id:
            assignment.end_date = local_today()

    if teacher is None or person_id is None:
        return True, None

    _ensure_staff_assignment(
        person_id=person_id,
        tenant_id=tenant.id,
        program_id=program.id,
        group_id=group.id,
        academic_year_id=class_room.academic_year_id,
        assignment_role=AssignmentRole.HOMEROOM,
        notes="Class homeroom sync",
    )

    duplicate_assignments = (
        StaffAssignment.query.filter(
            StaffAssignment.tenant_id == tenant.id,
            StaffAssignment.person_id == person_id,
            StaffAssignment.program_id == program.id,
            StaffAssignment.group_id == group.id,
            StaffAssignment.assignment_role == AssignmentRole.HOMEROOM,
            StaffAssignment.is_deleted.is_(False),
            StaffAssignment.end_date.is_(None),
        )
        .order_by(StaffAssignment.id.desc())
        .all()
    )
    for assignment in duplicate_assignments[1:]:
        assignment.end_date = local_today()
    return True, None


def deactivate_teacher_staff_assignment(teacher, assignment_id):
    tenant = _default_tenant()
    person_id = _teacher_person_id(teacher)
    if teacher is None or tenant is None or not person_id:
        return False, "Data guru belum lengkap."

    assignment = StaffAssignment.query.filter_by(
        id=assignment_id,
        tenant_id=tenant.id,
        person_id=person_id,
        is_deleted=False,
    ).first()
    if assignment is None:
        return False, "Assignment tidak ditemukan."

    if assignment.end_date is None:
        assignment.end_date = local_today()
    return True, None


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


def ensure_assignment_label_configs():
    created = 0
    for key, (default_value, description) in ASSIGNMENT_LABEL_DEFAULTS.items():
        existing = AppConfig.query.filter_by(key=key, is_deleted=False).first()
        if existing is None:
            db.session.add(AppConfig(key=key, value=default_value, description=description))
            created += 1
    if created:
        db.session.commit()
    return created


def _assignment_label_config(key):
    config = AppConfig.query.filter_by(key=key, is_deleted=False).first()
    if config and config.value:
        return config.value.strip()
    return ASSIGNMENT_LABEL_DEFAULTS[key][0]


def display_assignment_role(assignment_role, program_code=None):
    """
    Keep UI labels generic for SaaS readiness.

    We retain richer internal enums such as MURABBI/PEMBINA so the domain can
    evolve later, but the default product vocabulary shown to users stays
    neutral and tenant-agnostic.
    """
    if assignment_role is None:
        return "-"

    if assignment_role == AssignmentRole.SUBJECT_TEACHER:
        return _assignment_label_config("assignment_label.subject_teacher")

    if assignment_role == AssignmentRole.HOMEROOM:
        if program_code and program_code.startswith("SEKOLAH_"):
            return _assignment_label_config("assignment_label.formal_homeroom")
        return _assignment_label_config("assignment_label.nonformal_homeroom")

    if assignment_role == AssignmentRole.MURABBI:
        return _assignment_label_config("assignment_label.program_companion")

    if assignment_role == AssignmentRole.MUSYRIF:
        return _assignment_label_config("assignment_label.boarding_supervisor")

    if assignment_role == AssignmentRole.PEMBINA:
        return _assignment_label_config("assignment_label.program_companion")

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
