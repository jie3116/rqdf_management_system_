from app import create_app
from app.extensions import db
from app.models import (
    AcademicYear,
    EnrollmentStatus,
    GroupMembership,
    MajlisParticipant,
    MembershipStatus,
    Parent,
    Program,
    ProgramEnrollment,
    ProgramType,
    Student,
    Tenant,
    local_today,
)


def _default_tenant():
    return Tenant.query.filter_by(is_default=True).first()


def _active_academic_year():
    return AcademicYear.query.filter_by(is_active=True).first()


def _program_map(tenant_id):
    programs = Program.query.filter_by(tenant_id=tenant_id, is_deleted=False).all()
    return {program.code: program for program in programs}


def _join_date(value):
    if value:
        return value
    return local_today()


def _ensure_enrollment(tenant_id, person_id, program_id, academic_year_id, join_date, notes):
    enrollment = (
        ProgramEnrollment.query.filter_by(
            tenant_id=tenant_id,
            person_id=person_id,
            program_id=program_id,
            is_deleted=False,
        )
        .order_by(ProgramEnrollment.id.asc())
        .first()
    )

    created = enrollment is None
    if enrollment is None:
        enrollment = ProgramEnrollment(
            tenant_id=tenant_id,
            person_id=person_id,
            program_id=program_id,
        )
        db.session.add(enrollment)

    enrollment.academic_year_id = academic_year_id
    enrollment.status = EnrollmentStatus.ACTIVE
    enrollment.join_date = _join_date(join_date)
    enrollment.origin_type = "MIGRATION"
    enrollment.notes = notes
    db.session.flush()
    return enrollment, created


def _ensure_membership(tenant_id, enrollment_id, group_id, start_date, is_primary=True):
    membership = (
        GroupMembership.query.filter_by(
            tenant_id=tenant_id,
            enrollment_id=enrollment_id,
            group_id=group_id,
            is_deleted=False,
        )
        .order_by(GroupMembership.id.asc())
        .first()
    )

    created = membership is None
    if membership is None:
        membership = GroupMembership(
            tenant_id=tenant_id,
            enrollment_id=enrollment_id,
            group_id=group_id,
        )
        db.session.add(membership)

    membership.status = MembershipStatus.ACTIVE
    membership.start_date = _join_date(start_date)
    membership.end_date = None
    membership.is_primary = is_primary
    db.session.flush()
    return membership, created


def backfill_nonformal_enrollments():
    app = create_app()
    with app.app_context():
        tenant = _default_tenant()
        if tenant is None:
            raise RuntimeError("Default tenant tidak ditemukan.")

        active_year = _active_academic_year()
        programs = _program_map(tenant.id)

        required_codes = {"MAJLIS_TALIM", "PESANTREN", "RUMAH_QURAN"}
        missing_codes = sorted(required_codes - set(programs.keys()))
        if missing_codes:
            raise RuntimeError(f"Program belum tersedia: {', '.join(missing_codes)}")

        stats = {
            "majlis_enrollments": 0,
            "majlis_memberships": 0,
            "pesantren_enrollments": 0,
            "pesantren_memberships": 0,
            "rumah_quran_enrollments": 0,
            "rumah_quran_memberships": 0,
            "skipped": 0,
        }

        def handle_record(person_id, program_code, academic_year_id, group_id, join_date, notes, enrollment_key, membership_key):
            if not person_id:
                stats["skipped"] += 1
                return

            enrollment, enrollment_created = _ensure_enrollment(
                tenant_id=tenant.id,
                person_id=person_id,
                program_id=programs[program_code].id,
                academic_year_id=academic_year_id,
                join_date=join_date,
                notes=notes,
            )
            if enrollment_created:
                stats[enrollment_key] += 1

            if group_id:
                _, membership_created = _ensure_membership(
                    tenant_id=tenant.id,
                    enrollment_id=enrollment.id,
                    group_id=group_id,
                    start_date=join_date,
                )
                if membership_created:
                    stats[membership_key] += 1

        parents = Parent.query.execution_options(include_deleted=True).all()
        for parent in parents:
            if not parent.is_majlis_participant:
                continue
            academic_year_id = parent.majlis_class.academic_year_id if parent.majlis_class else (active_year.id if active_year else None)
            group_id = parent.majlis_class.program_group_id if parent.majlis_class else None
            handle_record(
                person_id=parent.person_id,
                program_code="MAJLIS_TALIM",
                academic_year_id=academic_year_id,
                group_id=group_id,
                join_date=parent.majlis_join_date,
                notes="Backfill dari parent.is_majlis_participant",
                enrollment_key="majlis_enrollments",
                membership_key="majlis_memberships",
            )

        participants = MajlisParticipant.query.execution_options(include_deleted=True).all()
        for participant in participants:
            academic_year_id = participant.majlis_class.academic_year_id if participant.majlis_class else (active_year.id if active_year else None)
            group_id = participant.majlis_class.program_group_id if participant.majlis_class else None
            handle_record(
                person_id=participant.person_id,
                program_code="MAJLIS_TALIM",
                academic_year_id=academic_year_id,
                group_id=group_id,
                join_date=participant.join_date,
                notes="Backfill dari majlis_participants",
                enrollment_key="majlis_enrollments",
                membership_key="majlis_memberships",
            )

        students = Student.query.execution_options(include_deleted=True).all()
        for student in students:
            if student.boarding_dormitory_id and student.boarding_dormitory and student.boarding_dormitory.program_group_id:
                handle_record(
                    person_id=student.person_id,
                    program_code="PESANTREN",
                    academic_year_id=active_year.id if active_year else None,
                    group_id=student.boarding_dormitory.program_group_id,
                    join_date=student.created_at.date() if student.created_at else None,
                    notes="Backfill dari boarding_dormitory siswa",
                    enrollment_key="pesantren_enrollments",
                    membership_key="pesantren_memberships",
                )

            if (
                student.current_class
                and student.current_class.program_group_id
                and student.current_class.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ)
            ):
                handle_record(
                    person_id=student.person_id,
                    program_code="RUMAH_QURAN",
                    academic_year_id=student.current_class.academic_year_id or (active_year.id if active_year else None),
                    group_id=student.current_class.program_group_id,
                    join_date=student.created_at.date() if student.created_at else None,
                    notes="Backfill dari kelas program rumah quran",
                    enrollment_key="rumah_quran_enrollments",
                    membership_key="rumah_quran_memberships",
                )

        db.session.commit()
        print("Non-formal enrollment backfill completed.")
        for key, value in stats.items():
            print(f"{key}={value}")


if __name__ == "__main__":
    backfill_nonformal_enrollments()
