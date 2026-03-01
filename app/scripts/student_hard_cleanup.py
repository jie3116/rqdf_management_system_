import argparse
from typing import List, Optional

from app import create_app
from app.extensions import db
from app.models import (
    Announcement,
    AnnouncementRead,
    Attendance,
    AuditLog,
    BehaviorReport,
    BoardingAttendance,
    BoardingDormitory,
    Grade,
    Invoice,
    NotificationQueue,
    RecitationRecord,
    ReportCard,
    Student,
    StudentAttitude,
    StudentClassHistory,
    TahfidzEvaluation,
    TahfidzRecord,
    TahfidzSummary,
    Transaction,
    User,
    UserRole,
    UserRoleAssignment,
    Violation,
    student_extracurriculars,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hard cleanup siswa berdasarkan rentang NIS (gunakan dengan sangat hati-hati)."
    )
    parser.add_argument("--nis-start", required=True, help="NIS awal, contoh: 202600001")
    parser.add_argument("--nis-end", required=True, help="NIS akhir, contoh: 202600203")
    parser.add_argument(
        "--delete-users",
        action="store_true",
        help="Ikut hapus akun user siswa yang aman untuk dihapus (student-only).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Eksekusi hard cleanup. Tanpa ini hanya preview.",
    )
    return parser.parse_args()


def normalize_nis_to_int(nis: Optional[str]) -> Optional[int]:
    if not nis:
        return None
    digits = "".join(ch for ch in str(nis).strip() if ch.isdigit())
    if not digits:
        return None
    return int(digits)


def get_target_students(nis_start: str, nis_end: str) -> List[Student]:
    start_num = normalize_nis_to_int(nis_start)
    end_num = normalize_nis_to_int(nis_end)
    if start_num is None or end_num is None:
        return []
    if start_num > end_num:
        start_num, end_num = end_num, start_num

    candidates = (
        Student.query.execution_options(include_deleted=True)
        .filter(Student.nis.isnot(None))
        .all()
    )

    matched = []
    for student in candidates:
        nis_num = normalize_nis_to_int(student.nis)
        if nis_num is None:
            continue
        if start_num <= nis_num <= end_num:
            matched.append(student)

    matched.sort(key=lambda item: (normalize_nis_to_int(item.nis) or 0, item.id))
    return matched


def print_zero_result_debug(nis_start: str, nis_end: str) -> None:
    start_prefix = (nis_start or "").strip()[:4]
    total_all = Student.query.execution_options(include_deleted=True).count()
    total_active = Student.query.count()
    exact_start = (
        Student.query.execution_options(include_deleted=True)
        .filter(Student.nis == nis_start.strip())
        .count()
    )
    exact_end = (
        Student.query.execution_options(include_deleted=True)
        .filter(Student.nis == nis_end.strip())
        .count()
    )
    prefix_count = 0
    if start_prefix:
        prefix_count = (
            Student.query.execution_options(include_deleted=True)
            .filter(Student.nis.like(f"{start_prefix}%"))
            .count()
        )

    print("Diagnostik:")
    print(f"- total siswa (include soft-delete): {total_all}")
    print(f"- total siswa aktif (exclude soft-delete): {total_active}")
    print(f"- exact NIS start ({nis_start}): {exact_start}")
    print(f"- exact NIS end   ({nis_end}): {exact_end}")
    print(f"- jumlah NIS prefix {start_prefix}: {prefix_count}")


def print_preview(students: List[Student]) -> None:
    print(f"Total target siswa: {len(students)}")
    for s in students:
        user_info = s.user_id if s.user_id is not None else "-"
        print(f"- id={s.id} nis={s.nis} nama={s.full_name} user_id={user_info} is_deleted={s.is_deleted}")


def delete_student_data(student_ids: List[int]) -> None:
    if not student_ids:
        return

    invoice_ids = [
        row[0]
        for row in db.session.query(Invoice.id)
        .execution_options(include_deleted=True)
        .filter(Invoice.student_id.in_(student_ids))
        .all()
    ]
    if invoice_ids:
        Transaction.query.filter(Transaction.invoice_id.in_(invoice_ids)).delete(synchronize_session=False)

    Invoice.query.filter(Invoice.student_id.in_(student_ids)).delete(synchronize_session=False)
    Attendance.query.filter(Attendance.student_id.in_(student_ids)).delete(synchronize_session=False)
    BoardingAttendance.query.filter(BoardingAttendance.student_id.in_(student_ids)).delete(synchronize_session=False)
    Grade.query.filter(Grade.student_id.in_(student_ids)).delete(synchronize_session=False)
    ReportCard.query.filter(ReportCard.student_id.in_(student_ids)).delete(synchronize_session=False)
    StudentAttitude.query.filter(StudentAttitude.student_id.in_(student_ids)).delete(synchronize_session=False)
    Violation.query.filter(Violation.student_id.in_(student_ids)).delete(synchronize_session=False)
    BehaviorReport.query.filter(BehaviorReport.student_id.in_(student_ids)).delete(synchronize_session=False)
    TahfidzRecord.query.filter(TahfidzRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
    TahfidzSummary.query.filter(TahfidzSummary.student_id.in_(student_ids)).delete(synchronize_session=False)
    RecitationRecord.query.filter(RecitationRecord.student_id.in_(student_ids)).delete(synchronize_session=False)
    TahfidzEvaluation.query.filter(TahfidzEvaluation.student_id.in_(student_ids)).delete(synchronize_session=False)
    StudentClassHistory.query.filter(StudentClassHistory.student_id.in_(student_ids)).delete(synchronize_session=False)

    db.session.execute(
        student_extracurriculars.delete().where(student_extracurriculars.c.student_id.in_(student_ids))
    )
    Student.query.filter(Student.id.in_(student_ids)).delete(synchronize_session=False)


def delete_student_only_users(user_ids: List[int]) -> None:
    if not user_ids:
        print("Tidak ada user terkait untuk diproses.")
        return

    users = User.query.execution_options(include_deleted=True).filter(User.id.in_(user_ids)).all()
    deleted = 0
    skipped = 0

    for user in users:
        user_roles = user.all_roles()
        has_other_profiles = any(
            [
                user.teacher_profile is not None,
                user.parent_profile is not None,
                user.staff_profile is not None,
                user.majlis_profile is not None,
                user.boarding_guardian_profile is not None,
            ]
        )
        is_student_only = (UserRole.SISWA in user_roles) and (not has_other_profiles)
        if UserRole.ADMIN in user_roles or not is_student_only:
            skipped += 1
            continue

        Announcement.query.filter_by(target_user_id=user.id).update(
            {Announcement.target_user_id: None}, synchronize_session=False
        )
        Announcement.query.filter_by(user_id=user.id).update(
            {Announcement.user_id: None}, synchronize_session=False
        )
        BoardingDormitory.query.filter_by(guardian_user_id=user.id).update(
            {BoardingDormitory.guardian_user_id: None}, synchronize_session=False
        )
        Transaction.query.filter_by(pic_id=user.id).update(
            {Transaction.pic_id: None}, synchronize_session=False
        )

        AnnouncementRead.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        NotificationQueue.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        AuditLog.query.filter_by(user_id=user.id).delete(synchronize_session=False)
        UserRoleAssignment.query.filter_by(user_id=user.id).delete(synchronize_session=False)

        db.session.delete(user)
        deleted += 1

    print(f"User dihapus: {deleted}, dilewati: {skipped}")


def main() -> int:
    args = parse_args()
    app = create_app()

    with app.app_context():
        students = get_target_students(args.nis_start, args.nis_end)
        print_preview(students)

        if not students:
            print("Tidak ada data siswa pada rentang NIS tersebut.")
            print_zero_result_debug(args.nis_start, args.nis_end)
            return 0

        if not args.yes:
            print("Mode preview. Tambahkan --yes untuk eksekusi hard cleanup.")
            return 0

        student_ids = [s.id for s in students]
        user_ids = [s.user_id for s in students if s.user_id is not None]

        try:
            delete_student_data(student_ids)
            if args.delete_users:
                delete_student_only_users(user_ids)
            db.session.commit()
            print("Hard cleanup selesai.")
            return 0
        except Exception as exc:
            db.session.rollback()
            print(f"Gagal hard cleanup: {exc}")
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
