from app import create_app
from app.extensions import db
from app.services.staff_assignment_service import cleanup_rumah_quran_subject_data


def run_cleanup():
    app = create_app()
    with app.app_context():
        stats = cleanup_rumah_quran_subject_data()
        if stats["closed_assignments"] or stats["deleted_schedules"]:
            db.session.commit()

        print("Rumah Qur'an subject cleanup completed.")
        print(f"closed_assignments={stats['closed_assignments']}")
        print(f"deleted_schedules={stats['deleted_schedules']}")


if __name__ == "__main__":
    run_cleanup()
