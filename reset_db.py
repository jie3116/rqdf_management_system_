from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Sedang menghapus semua tabel di PostgreSQL...")

    # 1. Hapus tabel tracking migrasi (alembic_version)
    try:
        db.session.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        db.session.commit()
    except Exception as e:
        print(f"Warning alembic: {e}")

    # 2. Hapus semua tabel aplikasi (User, Student, dll)
    db.drop_all()

    print("✅ SUKSES! Database sekarang sudah kosong melompong.")