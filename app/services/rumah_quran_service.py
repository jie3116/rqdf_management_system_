from app.extensions import db
from app.models import (
    ClassRoom,
    EnrollmentStatus,
    GroupMembership,
    MembershipStatus,
    Person,
    Program,
    ProgramEnrollment,
    ProgramType,
    Student,
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
