from app import create_app
from app.extensions import db
from werkzeug.security import generate_password_hash
from datetime import date, datetime
from app.models import (
    User, UserRole, Student, Teacher, Parent, ClassRoom,
    Gender, Subject, Staff, FeeType, AcademicYear,
    Invoice, Transaction, PaymentStatus, AppConfig
)

app = create_app()

with app.app_context():
    print("🧹 Menghapus database lama...")
    db.drop_all()

    print("🏗️ Membuat tabel database baru dengan struktur Scalable...")
    db.create_all()

    # ============================================
    # 1. MASTER DATA (CONFIG & ACADEMIC YEAR)
    # ============================================
    print("⚙️  Creating Master Data...")

    # Config Aplikasi
    conf1 = AppConfig(key="school_name", value="RQDF Boarding School", description="Nama Sekolah")
    conf2 = AppConfig(key="app_version", value="2.0", description="Versi Aplikasi")
    db.session.add_all([conf1, conf2])

    # Tahun Ajaran (PENTING: Harus ada sebelum buat Kelas/Biaya)
    ta_now = AcademicYear(name='2025/2026', semester='Ganjil', is_active=True)
    db.session.add(ta_now)
    db.session.commit()  # Commit dulu biar dpt ID untuk relasi

    # ============================================
    # 2. DATA KELAS & MAPEL
    # ============================================
    print("📚 Creating Classes & Subjects...")

    # Mapel
    mtk = Subject(code="MTK", name="Matematika", kkm=75)
    ipa = Subject(code="IPA", name="Ilmu Pengetahuan Alam", kkm=75)
    tahfidz = Subject(code="THF", name="Tahfidz Al-Quran", kkm=80)
    db.session.add_all([mtk, ipa, tahfidz])

    # Kelas
    cls7a = ClassRoom(name="X-Abu Bakar", grade_level=10)
    cls7b = ClassRoom(name="X-Umar", grade_level=10)
    db.session.add_all([cls7a, cls7b])
    db.session.commit()

    # ============================================
    # 3. USERS (ADMIN, GURU, TU)
    # ============================================
    print("👤 Creating Users (Admin, Guru, TU)...")

    # A. ADMIN
    admin_user = User(
        username='admin',
        email='admin@sekolah.id',
        password_hash=generate_password_hash('admin123'),
        role=UserRole.ADMIN,
        must_change_password=False
    )
    db.session.add(admin_user)

    # B. GURU (Ustadz Cecep)
    guru_user = User(
        username='guru01',
        email='teacher@sekolah.id',
        password_hash=generate_password_hash('guru123'),
        role=UserRole.GURU,
        must_change_password=False
    )
    db.session.add(guru_user)
    db.session.flush()  # Butuh ID user untuk profile

    guru_profile = Teacher(
        user_id=guru_user.id,
        nip="19900101",
        full_name="Ustadz Cecep Supriatna",
        specialty="Tahfidz & Fiqih"
    )
    db.session.add(guru_profile)

    # C. STAFF TU (Bu Siti)
    tu_user = User(
        username='tu01',
        email='tu@sekolah.id',
        password_hash=generate_password_hash('tu123'),
        role=UserRole.TU,
        must_change_password=False
    )
    db.session.add(tu_user)
    db.session.flush()

    tu_profile = Staff(
        user_id=tu_user.id,
        full_name="Nazelina, S.Pd",
        position="Bendahara"
    )
    db.session.add(tu_profile)

    # ============================================
    # 4. SISWA & WALI (Pak Aji & Arsyad)
    # ============================================
    print("👤 Creating Parents & Students...")

    # A. WALI (Pak Aji)
    wali_user = User(
        username='081916071882',  # Login pakai No HP
        email='aji@mail.com',
        password_hash=generate_password_hash('123456'),
        role=UserRole.WALI_MURID,
        must_change_password=True  # Wajib ganti pass
    )
    db.session.add(wali_user)
    db.session.flush()

    wali_profile = Parent(
        user_id=wali_user.id,
        full_name="Aji Abdul Aziz",
        phone="081916071882",
        job="Wiraswasta",
        address="Cianjur"
    )
    db.session.add(wali_profile)
    db.session.flush()

    # B. SISWA (Arsyad)
    siswa_user = User(
        username='20250001',  # NIS
        email='shafiya@sekolah.id',
        password_hash=generate_password_hash('20250001'),
        role=UserRole.SISWA,
        must_change_password=True
    )
    db.session.add(siswa_user)
    db.session.flush()

    siswa_profile = Student(
        user_id=siswa_user.id,
        parent_id=wali_profile.id,
        current_class_id=cls7a.id,  # Masuk kelas X-Abu Bakar
        nis="20250001",
        full_name="Shafiya Zakiya",
        gender=Gender.L,
        place_of_birth="Cirebon",
        date_of_birth=date(2008, 8, 8),
        address="Cirebon kota udang"
    )
    db.session.add(siswa_profile)

    # ============================================
    # 5. KEUANGAN (FEE TYPES)
    # ============================================
    print("💰 Creating Fee Types...")

    # Karena model baru, FeeType butuh academic_year_id
    spp = FeeType(
        name="SPP Juli 2025",
        amount=150000,
        academic_year_id=ta_now.id  # Relasi ke Tahun Ajaran (PENTING)
    )
    gedung = FeeType(
        name="Uang Gedung",
        amount=2000000,
        academic_year_id=ta_now.id
    )
    db.session.add_all([spp, gedung])

    # Final Commit
    db.session.commit()

    print("\n✅ Database Seeded Successfully (Version 2.0)!")
    print("   - Admin: admin / admin123")
    print("   - TU: tu01 / tu123")
    print("   - Wali: 081916071882 / 123456 (Must Change)")
    print("   - Siswa: 20250001 / 20250001 (Must Change)")