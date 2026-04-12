from app import create_app
from app.extensions import db
from app.services.staff_assignment_service import backfill_all_teacher_staff_assignments


def backfill_staff_assignments():
    result = backfill_all_teacher_staff_assignments()
    db.session.commit()
    print("Staff assignment backfill completed.")
    print(f"teachers={result['teachers']}")
    print(f"created={result['created']}")
    print(f"skipped={result['skipped']}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        backfill_staff_assignments()
