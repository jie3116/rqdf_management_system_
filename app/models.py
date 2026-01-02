from app.extensions import db
from datetime import datetime
import enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash



# ==========================================
# 0. BASE MODEL (SCALABILITY FOUNDATION)
# ==========================================
class BaseModel(db.Model):
    """
    Kelas Abstract yang akan diwarisi oleh semua model.
    Menyediakan fitur Timestamp otomatis dan Soft Delete.
    """
    __abstract__ = True

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)  # Soft Delete flag

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        """Soft delete: data tidak hilang, hanya disembunyikan."""
        self.is_deleted = True
        db.session.commit()


# ==========================================
# 1. ENUMS
# ==========================================
class UserRole(enum.Enum):
    ADMIN = "admin"
    GURU = "teacher"
    SISWA = "student"
    WALI_MURID = "wali_murid"
    TU = "tata_usaha"


class Gender(enum.Enum):
    L = "Laki-laki"
    P = "Perempuan"


class AttendanceStatus(enum.Enum):
    HADIR = "Hadir"
    SAKIT = "Sakit"
    IZIN = "Izin"
    ALPA = "Alpa"


class PaymentStatus(enum.Enum):
    UNPAID = "Belum Lunas"
    PAID = "Lunas"
    PARTIAL = "Cicilan"


class TahfidzType(enum.Enum):
    ZIYADAH = "Ziyadah"
    MURAJAAH = "Murajaah"


class GradeType(enum.Enum):
    TUGAS = "Tugas"
    UH = "Ulangan Harian"
    UTS = "UTS"
    UAS = "UAS"
    SIKAP = "Sikap"

class ProgramType(enum.Enum):
    RQDF_SORE = "RQDF Reguler (Sore)"            # Formulir A
    SEKOLAH_FULLDAY = "Sekolah Bina Qur'an"      # Formulir B & C


class EducationLevel(enum.Enum):
    NON_FORMAL = "Non Formal" # Untuk RQDF Sore
    SD = "SD"
    SMP = "SMP"
    SMA = "SMA"

class ScholarshipCategory(enum.Enum):
    NON_BEASISWA = "Non Beasiswa / Reguler"
    TAHFIDZ_5_JUZ = "Beasiswa 5 Juz"
    TAHFIDZ_10_30_JUZ = "Beasiswa 10-30 Juz"
    YATIM_DHUAFA = "Beasiswa Yatim Dhuafa"

class UniformSize(enum.Enum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"
    XXL = "XXL"
    TIDAK_MEMILIH = "Tidak Memilih" # Untuk yang tidak beli seragam

class TahfidzSchedule(enum.Enum):
    SHIFT_1 = "14.00 s.d 15.30"
    SHIFT_2 = "16.00 s.d 17.30"
    TIDAK_ADA = "-" # Untuk Sekolah Formal

class RegistrationStatus(enum.Enum):
    PENDING = "Menunggu Verifikasi"
    INTERVIEW = "Tahap Wawancara"
    ACCEPTED = "Diterima"
    REJECTED = "Tidak Diterima"


# ==========================================
# 2. ASSOCIATION TABLES
# ==========================================
student_extracurriculars = db.Table('student_extracurriculars',
                                    db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
                                    db.Column('extracurricular_id', db.Integer, db.ForeignKey('extracurriculars.id'),
                                              primary_key=True)
                                    )


# ==========================================
# 3. SYSTEM & CONFIG (NEW)
# ==========================================
class AppConfig(BaseModel):
    """Menyimpan setting dinamis (misal: Tahun Ajaran Aktif, Denda Keterlambatan)"""
    __tablename__ = 'app_configs'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255))
    description = db.Column(db.String(200))


class AuditLog(db.Model):
    """Mencatat siapa melakukan apa (Security)"""
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50))  # LOGIN, UPDATE_NILAI, DELETE_SISWA
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class NotificationQueue(BaseModel):
    """Antrian pesan WA/Email (Scalability)"""
    __tablename__ = 'notification_queues'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    target_contact = db.Column(db.String(50))  # No WA / Email
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDING')  # PENDING, SENT, FAILED


# ==========================================
# 4. USERS & PROFILES
# ==========================================

class User(UserMixin, BaseModel):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.Enum(UserRole), default=UserRole.SISWA, nullable=False)
    last_login = db.Column(db.DateTime)

    # Jika True = User akan dialihkan ke halaman ganti password saat login
    must_change_password = db.Column(db.Boolean, default=True)

    # Relationships
    student_profile = db.relationship('Student', backref='user', uselist=False)
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False)
    parent_profile = db.relationship('Parent', backref='user', uselist=False)
    staff_profile = db.relationship('Staff', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Parent(BaseModel):
    __tablename__ = 'parents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, index=True)  # Index untuk pencarian cepat
    address = db.Column(db.Text)
    job = db.Column(db.String(100))
    children = db.relationship('Student', backref='parent', lazy=True)


class Teacher(BaseModel):
    __tablename__ = 'teachers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    nip = db.Column(db.String(20), unique=True)
    full_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    specialty = db.Column(db.String(50))

    homeroom_class = db.relationship('ClassRoom', backref='homeroom_teacher', uselist=False)
    supervised_extracurriculars = db.relationship('Extracurricular', backref='supervisor', lazy=True)


class Staff(BaseModel):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(100))
    position = db.Column(db.String(50))


class Student(BaseModel):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=True)
    current_class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'))
    nis = db.Column(db.String(20), unique=True, nullable=False)
    nisn = db.Column(db.String(20), unique=True, nullable=True)
    full_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.Enum(Gender))
    place_of_birth = db.Column(db.String(50))
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.Text)
    custom_spp_fee = db.Column(db.Integer, nullable=True, default=None)

    # Relations
    class_history = db.relationship('StudentClassHistory', backref='student', lazy=True)
    attendances = db.relationship('Attendance', backref='student', lazy=True)
    grades = db.relationship('Grade', backref='student', lazy=True)
    violations = db.relationship('Violation', backref='student', lazy=True)  # BK
    invoices = db.relationship('Invoice', backref='student', lazy=True)
    tahfidz_records = db.relationship('TahfidzRecord', backref='student', lazy=True)
    tahfidz_summary = db.relationship('TahfidzSummary', backref='student', uselist=False)
    extracurriculars = db.relationship('Extracurricular', secondary=student_extracurriculars, back_populates='students')


# ==========================================
# 5. ACADEMIC CORE
# ==========================================
class AcademicYear(BaseModel):
    __tablename__ = 'academic_years'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)  # 2024/2025
    semester = db.Column(db.String(10), nullable=False)  # Ganjil/Genap
    is_active = db.Column(db.Boolean, default=False)


class ClassRoom(BaseModel):
    __tablename__ = 'class_rooms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=False)
    grade_level = db.Column(db.Integer)
    homeroom_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))

    students = db.relationship('Student', backref='current_class', lazy=True)
    schedules = db.relationship('Schedule', backref='class_room', lazy=True)


class Subject(BaseModel):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True)
    name = db.Column(db.String(50), nullable=False)
    kkm = db.Column(db.Float, default=75.0)


class StudentClassHistory(BaseModel):
    """Mencatat riwayat kenaikan kelas student"""
    __tablename__ = 'student_class_history'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    status = db.Column(db.String(20))  # Active, Promoted, Graduated


class LearningMaterial(BaseModel):
    """E-Learning: Upload Materi"""
    __tablename__ = 'learning_materials'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    title = db.Column(db.String(100))
    file_url = db.Column(db.String(255))
    description = db.Column(db.Text)


# ==========================================
# 6. ACTIVITIES & RECORDS
# ==========================================
class Schedule(BaseModel):
    __tablename__ = 'schedules'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    day = db.Column(db.String(10))
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)


class Attendance(BaseModel):
    __tablename__ = 'attendances'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))  # Penting utk rekap per semester
    date = db.Column(db.Date, default=datetime.utcnow)
    status = db.Column(db.Enum(AttendanceStatus))
    notes = db.Column(db.String(100))


class Grade(BaseModel):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    type = db.Column(db.Enum(GradeType))
    score = db.Column(db.Float)
    notes = db.Column(db.String(100))


class Violation(BaseModel):
    """Bimbingan Konseling (BK)"""
    __tablename__ = 'violations'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    date = db.Column(db.Date, default=datetime.utcnow)
    description = db.Column(db.Text)
    points = db.Column(db.Integer)  # Poin pelanggaran
    sanction = db.Column(db.String(100))  # Sanksi yang diberikan


class Extracurricular(BaseModel):
    __tablename__ = 'extracurriculars'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    supervisor_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    students = db.relationship('Student', secondary=student_extracurriculars, back_populates='extracurriculars')


# ==========================================
# 7. TAHFIDZ PROGRAM
# ==========================================
class TahfidzRecord(BaseModel):
    __tablename__ = 'tahfidz_records'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.Column(db.Enum(TahfidzType))
    juz = db.Column(db.Integer)
    surah = db.Column(db.String(50))
    ayat_start = db.Column(db.Integer)
    ayat_end = db.Column(db.Integer)
    quality = db.Column(db.String(20))
    notes = db.Column(db.Text)


class TahfidzSummary(BaseModel):
    __tablename__ = 'tahfidz_summaries'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), unique=True)
    total_juz = db.Column(db.Float, default=0)
    last_surah = db.Column(db.String(50))
    last_ayat = db.Column(db.Integer)


# ==========================================
# 8. FINANCE
# ==========================================
class FeeType(BaseModel):
    __tablename__ = 'fee_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))  # SPP Juli, Uang Gedung
    amount = db.Column(db.Float)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))  # Biaya bisa beda tiap tahun
    academic_year = db.relationship('AcademicYear', backref='fees')


class Invoice(BaseModel):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)

    # Format: INV/202408/1/25
    invoice_number = db.Column(db.String(50), unique=True)

    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_types.id'))

    total_amount = db.Column(db.Float)
    paid_amount = db.Column(db.Float, default=0)
    status = db.Column(db.Enum(PaymentStatus), default=PaymentStatus.UNPAID)
    due_date = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relasi
    # Relasi 'student' dan 'fee_type' sudah otomatis terbuat lewat backref dari model lain,
    # atau bisa didefinisikan eksplisit jika perlu, tapi biasanya SQLAlchemy cukup pintar.
    # Namun untuk keamanan, kita definisikan ulang relasi untuk akses objek langsung:
    fee_type = db.relationship('FeeType', backref='invoices')
    # Student relasi sudah ada di backref di model Student (invoices = db.relationship...)

    transactions = db.relationship('Transaction', backref='invoice', lazy=True)


class Transaction(BaseModel):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    amount = db.Column(db.Float)
    method = db.Column(db.String(30))  # Tunai, Transfer
    date = db.Column(db.DateTime, default=datetime.utcnow)

    # Staff/Admin yang menginput (optional)
    pic_id = db.Column(db.Integer, db.ForeignKey('users.id'))


# ==========================================
# 8. MODEL CANDIDATE (SUPERSET)
# ==========================================

class StudentCandidate(BaseModel):
    __tablename__ = 'student_candidates'
    id = db.Column(db.Integer, primary_key=True)

    # --- 1. INFO PENDAFTARAN UTAMA ---
    registration_no = db.Column(db.String(20), unique=True)
    program_type = db.Column(db.Enum(ProgramType), default=ProgramType.SEKOLAH_FULLDAY)
    education_level = db.Column(db.Enum(EducationLevel))  # SMP / SMA / Non Formal
    scholarship_category = db.Column(db.Enum(ScholarshipCategory), default=ScholarshipCategory.NON_BEASISWA)
    status = db.Column(db.Enum(RegistrationStatus), default=RegistrationStatus.PENDING)

    # --- 2. DATA PRIBADI (Gabungan Form A, B, C) ---
    full_name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(50))  # Form B & C minta nama panggilan
    nik = db.Column(db.String(20))  # Form B minta NIK
    kk_number = db.Column(db.String(20))  # Form B minta No KK
    gender = db.Column(db.Enum(Gender))
    place_of_birth = db.Column(db.String(50))
    date_of_birth = db.Column(db.Date)
    age = db.Column(db.Integer)  # Form A minta Umur
    address = db.Column(db.Text)

    # --- 3. DATA SEKOLAH ASAL ---
    previous_school = db.Column(db.String(100))  # Form A, B, C butuh ini
    previous_school_class = db.Column(db.String(20))  # Form A: "Sekolah/Kelas"

    # --- 4. DATA ORANG TUA & EKONOMI ---
    father_name = db.Column(db.String(100))
    father_job = db.Column(db.String(100))
    mother_name = db.Column(db.String(100))
    mother_job = db.Column(db.String(100))
    parent_phone = db.Column(db.String(20))  # WA Orang Tua

    # Penghasilan (Penting untuk Beasiswa Yatim Dhuafa)
    father_income_range = db.Column(db.String(50))  # < 1jt, 1-2.5jt, dll
    mother_income_range = db.Column(db.String(50))

    # --- 5. PILIHAN FASILITAS & BIAYA (CUSTOM FIELDS) ---
    # Khusus RQDF Sore
    tahfidz_schedule = db.Column(db.Enum(TahfidzSchedule), default=TahfidzSchedule.TIDAK_ADA)

    # Seragam (RQDF Sore minta ukuran spesifik)
    uniform_size = db.Column(db.Enum(UniformSize), default=UniformSize.TIDAK_MEMILIH)

    # Komitmen Wakaf/Infaq (Pilihan nominal di Form A)
    initial_pledge_amount = db.Column(db.Float, default=0)

    # Opsi Pembiayaan (Normal / 50% untuk Beasiswa)
    finance_option = db.Column(db.String(50))  # "Normal", "Beasiswa 50%"

    created_at = db.Column(db.DateTime, default=datetime.utcnow)