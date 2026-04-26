from app import create_app
from app.extensions import db
from app.models import (
    BoardingDormitory,
    ClassRoom,
    GroupType,
    Program,
    ProgramGroup,
    ProgramType,
    Tenant,
)


def _default_tenant():
    return Tenant.query.filter_by(is_default=True).first()


def _program_code_for_classroom(class_room):
    if class_room.class_type and class_room.class_type.name == "MAJLIS_TALIM":
        return "MAJLIS_TALIM"

    if class_room.program_type == ProgramType.SEKOLAH_FULLDAY:
        if class_room.education_level and class_room.education_level.name == "SD":
            return "SEKOLAH_SD"
        if class_room.education_level and class_room.education_level.name == "SMP":
            return "SEKOLAH_SMP"
        if class_room.education_level and class_room.education_level.name == "SMA":
            return "SEKOLAH_SMA"

    if class_room.program_type == ProgramType.RQDF_SORE:
        return "RUMAH_QURAN"

    if class_room.program_type == ProgramType.TAKHOSUS_TAHFIDZ:
        return "RUMAH_QURAN"

    if class_room.program_type == ProgramType.BAHASA:
        return "BAHASA"

    return "SEKOLAH_SD"


def _group_type_for_classroom(class_room):
    if class_room.class_type and class_room.class_type.name == "MAJLIS_TALIM":
        return GroupType.MAJLIS_CLASS

    if class_room.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ):
        return GroupType.HALAQAH

    return GroupType.CLASS


def _ensure_program_group(tenant_id, program_id, academic_year_id, name, group_type, level_label=None, gender_scope=None, capacity=None):
    program_group = ProgramGroup.query.filter_by(
        tenant_id=tenant_id,
        program_id=program_id,
        academic_year_id=academic_year_id,
        name=name,
    ).first()

    if program_group is None:
        program_group = ProgramGroup(
            tenant_id=tenant_id,
            program_id=program_id,
            academic_year_id=academic_year_id,
            name=name,
        )
        db.session.add(program_group)

    program_group.group_type = group_type
    program_group.level_label = level_label
    program_group.gender_scope = gender_scope
    program_group.capacity = capacity
    program_group.is_active = True
    db.session.flush()
    return program_group


def backfill_program_groups():
    app = create_app()
    with app.app_context():
        tenant = _default_tenant()
        if tenant is None:
            raise RuntimeError("Default tenant tidak ditemukan.")

        created = 0
        linked_classrooms = 0
        linked_dormitories = 0

        classrooms = ClassRoom.query.execution_options(include_deleted=True).all()
        for class_room in classrooms:
            program_code = _program_code_for_classroom(class_room)
            program = Program.query.filter_by(tenant_id=tenant.id, code=program_code).first()
            if program is None:
                continue

            existing = ProgramGroup.query.filter_by(
                tenant_id=tenant.id,
                program_id=program.id,
                academic_year_id=class_room.academic_year_id,
                name=class_room.name,
            ).first()

            group = _ensure_program_group(
                tenant_id=tenant.id,
                program_id=program.id,
                academic_year_id=class_room.academic_year_id,
                name=class_room.name,
                group_type=_group_type_for_classroom(class_room),
                level_label=str(class_room.grade_level) if class_room.grade_level else None,
            )

            if existing is None:
                created += 1

            class_room.program_group_id = group.id
            linked_classrooms += 1

        dormitories = BoardingDormitory.query.execution_options(include_deleted=True).all()
        pesantren = Program.query.filter_by(tenant_id=tenant.id, code="PESANTREN").first()
        for dormitory in dormitories:
            if pesantren is None:
                continue

            existing = ProgramGroup.query.filter_by(
                tenant_id=tenant.id,
                program_id=pesantren.id,
                academic_year_id=None,
                name=dormitory.name,
            ).first()

            group = _ensure_program_group(
                tenant_id=tenant.id,
                program_id=pesantren.id,
                academic_year_id=None,
                name=dormitory.name,
                group_type=GroupType.DORMITORY,
                gender_scope=dormitory.gender,
                capacity=dormitory.capacity,
            )

            if existing is None:
                created += 1

            dormitory.program_group_id = group.id
            linked_dormitories += 1

        db.session.commit()
        print(
            f"Program groups backfill completed. created={created} "
            f"classrooms={linked_classrooms} dormitories={linked_dormitories}"
        )


if __name__ == "__main__":
    backfill_program_groups()
