from app import create_app
from app.models import StudentCandidate

app = create_app()

with app.app_context():
    print("\n--- MULAI PENGECEKAN DATABASE ---")

    # Ambil pendaftar terakhir berdasarkan ID paling besar
    calon = StudentCandidate.query.order_by(StudentCandidate.id.desc()).first()

    if calon:
        print(f"✅ DATA TERAKHIR DITEMUKAN!")
        print(f"--------------------------------")
        print(f"No Reg   : {calon.registration_no}")
        print(f"Nama     : {calon.full_name}")
        print(f"Jenjang  : {calon.education_level.value}")
        print(f"Jalur    : {calon.scholarship_category.value}")
        print(f"Program  : {calon.program_type.value}")
        print(f"--------------------------------")
    else:
        print("❌ Database StudentCandidate masih kosong.")

    print("--- SELESAI ---\n")