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
    is_deleted = db.Column(db.Boolean, default=False)

    def save(self):
        db.session.add(self)
        db.session.commit()

    def delete(self):
        """Soft delete: data tidak hilang, hanya disembunyikan."""
        self.is_deleted = True
        db.session.commit()

    # TAMBAHAN: Method helper
    def update(self, **kwargs):
        """Update multiple fields at once"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()

    def to_dict(self):
        """Convert model to dictionary"""
        return {column.name: getattr(self, column.name)
                for column in self.__table__.columns}


# ==========================================
# 1. ENUMS
# ==========================================
class UserRole(enum.Enum):
    ADMIN = "admin"
    GURU = "teacher"
    SISWA = "student"
    WALI_MURID = "wali_murid"
    TU = "tata_usaha"
    MAJLIS_PARTICIPANT = "majlis_participant"  # BARU: Role untuk peserta majlis non-parent


class ParticipantType(enum.Enum):
    STUDENT = "Siswa"
    PARENT_MAJLIS = "Orang Tua (Majelis Ta'lim)"
    EXTERNAL_MAJLIS = "Peserta Majelis Ta'lim"


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
    # SETORAN_BACAAN dihapus karena terpisah di RecitationRecord


class RecitationSource(enum.Enum):
    """
    BARU: Enum untuk sumber bacaan di setoran bacaan
    """
    QURAN = "Al-Qur'an"
    BOOK = "Kitab/Buku"


class GradeType(enum.Enum):
    TUGAS = "Tugas"
    UH = "Ulangan Harian"
    UTS = "UTS"
    UAS = "UAS"
    SIKAP = "Sikap"


class EvaluationPeriod(enum.Enum):
    BULANAN = "Bulanan"
    TENGAH_SEMESTER = "Tengah Semester"
    SEMESTER = "Semester"


class ProgramType(enum.Enum):
    RQDF_SORE = "RQDF Reguler (Sore)"
    SEKOLAH_FULLDAY = "Sekolah Bina Qur'an"
    TAKHOSUS_TAHFIDZ = "Takhosus Tahfidz"
    MAJLIS_TALIM = "Majelis Ta'lim"  # BARU


class EducationLevel(enum.Enum):
    NON_FORMAL = "Non Formal"
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
    TIDAK_MEMILIH = "Tidak Memilih"


class TahfidzSchedule(enum.Enum):
    SHIFT_1 = "14.00 s.d 15.30"
    SHIFT_2 = "16.00 s.d 17.30"
    TIDAK_ADA = "-"


class RegistrationStatus(enum.Enum):
    PENDING = "Menunggu Verifikasi"
    INTERVIEW = "Tahap Wawancara"
    ACCEPTED = "Diterima"
    REJECTED = "Tidak Diterima"


class ClassType(enum.Enum):
    REGULAR = "Kelas Reguler"
    MAJLIS_TALIM = "Majelis Ta'lim"


# ==========================================
# 2. ASSOCIATION TABLES
# ==========================================
student_extracurriculars = db.Table('student_extracurriculars',
                                    db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
                                    db.Column('extracurricular_id', db.Integer, db.ForeignKey('extracurriculars.id'),
                                              primary_key=True)
                                    )


# ==========================================
# 3. SYSTEM, CONFIG & KNOWLEDGE BASE
# ==========================================
class AppConfig(BaseModel):
    __tablename__ = 'app_configs'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(255))
    description = db.Column(db.String(200))


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class NotificationQueue(BaseModel):
    __tablename__ = 'notification_queues'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    target_contact = db.Column(db.String(50))
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='PENDING')


class Announcement(BaseModel):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    # Target spesifik (opsional)
    target_class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    author = db.relationship('User', backref='announcements')


class SchoolDocument(BaseModel):
    """
    Menyimpan dokumen sekolah untuk Knowledge Base AI (RAG).
    Contoh: 'Panduan Akademik', 'Peraturan Asrama', 'Silabus'.
    """
    __tablename__ = 'school_documents'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(50))  # Kurikulum, Peraturan, SK
    file_path = db.Column(db.String(255))  # Path di server
    description = db.Column(db.Text)

    # Status Indexing Vector DB (Untuk fitur AI nanti)
    is_indexed = db.Column(db.Boolean, default=False)
    vector_id = db.Column(db.String(100), nullable=True)


# ==========================================
# 4. USERS & PROFILES
# ==========================================
class User(UserMixin, BaseModel):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.Enum(UserRole, name='userrole'), default=UserRole.SISWA, nullable=False)
    last_login = db.Column(db.DateTime)
    must_change_password = db.Column(db.Boolean, default=True)

    # Relationships
    student_profile = db.relationship('Student', backref='user', uselist=False, lazy='select')
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False, lazy='select')
    parent_profile = db.relationship('Parent', backref='user', uselist=False, lazy='select')
    staff_profile = db.relationship('Staff', backref='user', uselist=False, lazy='select')
    majlis_profile = db.relationship('MajlisParticipant', backref='user', uselist=False, lazy='select')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Parent(BaseModel):
    __tablename__ = 'parents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, index=True)
    address = db.Column(db.Text)
    job = db.Column(db.String(100))

    # FITUR BARU: Majelis Ta'lim
    is_majlis_participant = db.Column(db.Boolean, default=False)
    majlis_class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=True)
    majlis_join_date = db.Column(db.Date, nullable=True)

    children = db.relationship('Student', backref='parent', lazy=True)
    majlis_class = db.relationship('ClassRoom', foreign_keys=[majlis_class_id], backref='majlis_parents')


class MajlisParticipant(BaseModel):
    """
    Model untuk peserta majelis ta'lim yang bukan orang tua siswa
    """
    __tablename__ = 'majlis_participants'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, index=True)
    address = db.Column(db.Text)
    job = db.Column(db.String(100))

    majlis_class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=True)
    join_date = db.Column(db.Date, default=datetime.utcnow)

    majlis_class = db.relationship('ClassRoom', foreign_keys=[majlis_class_id], backref='majlis_external_participants')


class Teacher(BaseModel):
    __tablename__ = 'teachers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
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
    nis = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nisn = db.Column(db.String(20), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.Enum(Gender, name='gender'))
    place_of_birth = db.Column(db.String(50))
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.Text)
    custom_spp_fee = db.Column(db.Integer, nullable=True, default=None)

    # Relations
    class_history = db.relationship('StudentClassHistory', backref='student', lazy=True)
    attendances = db.relationship('Attendance', backref='student', lazy='dynamic')
    grades = db.relationship('Grade', backref='student', lazy='dynamic')
    report_cards = db.relationship('ReportCard', backref='student', lazy=True)
    student_attitudes = db.relationship('StudentAttitude', backref='student', lazy=True)
    violations = db.relationship('Violation', backref='student', lazy='dynamic')
    invoices = db.relationship('Invoice', backref='student', lazy='dynamic')
    tahfidz_records = db.relationship('TahfidzRecord', foreign_keys='TahfidzRecord.student_id', backref='student',
                                      lazy='dynamic')
    tahfidz_summary = db.relationship('TahfidzSummary', foreign_keys='TahfidzSummary.student_id', backref='student',
                                      uselist=False)
    recitation_records = db.relationship('RecitationRecord', foreign_keys='RecitationRecord.student_id',
                                         backref='student', lazy='dynamic')
    tahfidz_evaluations = db.relationship('TahfidzEvaluation', foreign_keys='TahfidzEvaluation.student_id',
                                          backref='student', lazy='dynamic')
    extracurriculars = db.relationship('Extracurricular', secondary=student_extracurriculars, back_populates='students')

    __table_args__ = (
        db.Index('idx_student_class_academic', 'current_class_id', 'created_at'),
    )


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
    name = db.Column(db.String(50), nullable=False)
    grade_level = db.Column(db.Integer, nullable=True)
    homeroom_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))

    # BARU: Tipe kelas
    class_type = db.Column(db.Enum(ClassType, name='classtype'), default=ClassType.REGULAR)

    # Menambahkan Tahun Ajaran agar History Kelas Rapi
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=True)
    academic_year = db.relationship('AcademicYear')

    students = db.relationship('Student', backref='current_class', lazy=True)
    schedules = db.relationship('Schedule', backref='class_room', lazy=True)


class Subject(BaseModel):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True)
    name = db.Column(db.String(50), nullable=False)
    kkm = db.Column(db.Float, default=75.0)


class MajlisSubject(BaseModel):
    """
    Subject khusus untuk Majelis Ta'lim
    """
    __tablename__ = 'majlis_subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # Tajwid, Tahfidz, Fiqh Wanita, dll
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)


class StudentClassHistory(BaseModel):
    __tablename__ = 'student_class_history'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    status = db.Column(db.String(20))


class LearningMaterial(BaseModel):
    __tablename__ = 'learning_materials'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    title = db.Column(db.String(100))
    file_url = db.Column(db.String(255))
    description = db.Column(db.Text)


# ==========================================
# 6. ACTIVITIES, GRADES & RECORDS
# ==========================================
class Schedule(BaseModel):
    __tablename__ = 'schedules'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    majlis_subject_id = db.Column(db.Integer, db.ForeignKey('majlis_subjects.id'), nullable=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    day = db.Column(db.String(10))
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)

    subject = db.relationship('Subject', backref='schedules')
    majlis_subject = db.relationship('MajlisSubject', backref='schedules')
    teacher = db.relationship('Teacher', backref='teaching_schedules')


class Attendance(BaseModel):
    __tablename__ = 'attendances'
    id = db.Column(db.Integer, primary_key=True)

    # Foreign Keys - Support untuk majlis ta'lim
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=True)
    majlis_participant_id = db.Column(db.Integer, db.ForeignKey('majlis_participants.id'), nullable=True)

    participant_type = db.Column(db.Enum(ParticipantType, name='participanttype'), default=ParticipantType.STUDENT)

    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=True)

    date = db.Column(db.Date, default=datetime.utcnow, nullable=False)
    status = db.Column(db.Enum(AttendanceStatus, name='attendancestatus'), default=AttendanceStatus.HADIR)
    notes = db.Column(db.String(100))

    class_room = db.relationship('ClassRoom', backref='attendance_records')
    teacher = db.relationship('Teacher', backref='inputted_attendances')
    parent_participant = db.relationship('Parent', foreign_keys=[parent_id], backref='attendances')
    majlis_participant = db.relationship('MajlisParticipant', backref='attendances')

    __table_args__ = (
        db.Index('idx_attendance_date_class', 'date', 'class_id'),
        db.Index('idx_attendance_participant_date', 'participant_type', 'date'),
    )


class Grade(BaseModel):
    """
    Menyimpan nilai harian (Raw Data) yang diinput Guru.
    """
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))

    type = db.Column(db.Enum(GradeType, name='gradetype'))  # Tugas, UTS, UAS
    score = db.Column(db.Float)
    notes = db.Column(db.String(100))

    subject = db.relationship('Subject', backref='grades')
    teacher = db.relationship('Teacher', backref='input_grades')
    academic_year = db.relationship('AcademicYear', backref='grades')


class GradeWeight(BaseModel):
    """
    Menyimpan bobot penilaian.
    Contoh: UTS=30%, UAS=40%, Tugas=30%.
    """
    __tablename__ = 'grade_weights'
    id = db.Column(db.Integer, primary_key=True)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))

    grade_type = db.Column(db.Enum(GradeType, name='gradetype'))
    weight_percentage = db.Column(db.Float)  # Misal: 30.0


class ReportCard(BaseModel):
    """
    Menyimpan Nilai Akhir Raport (Snapshot).
    Ini yang akan dicetak di PDF agar tidak perlu hitung ulang terus menerus.
    """
    __tablename__ = 'report_cards'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))

    knowledge_score = db.Column(db.Float)  # Nilai Angka
    knowledge_predikat = db.Column(db.String(2))  # A, B, C
    skill_score = db.Column(db.Float)
    skill_predikat = db.Column(db.String(2))
    description = db.Column(db.Text)  # Catatan Guru Mapel


class StudentAttitude(BaseModel):
    """
    Menyimpan Nilai Sikap & Absensi Semester (Inputan Wali Kelas).
    """
    __tablename__ = 'student_attitudes'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))

    spiritual_predikat = db.Column(db.String(20))  # Baik/Sangat Baik
    spiritual_desc = db.Column(db.Text)
    social_predikat = db.Column(db.String(20))
    social_desc = db.Column(db.Text)

    sick_count = db.Column(db.Integer, default=0)
    permit_count = db.Column(db.Integer, default=0)
    alpha_count = db.Column(db.Integer, default=0)


class Violation(BaseModel):
    __tablename__ = 'violations'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    date = db.Column(db.Date, default=datetime.utcnow)
    description = db.Column(db.Text)
    points = db.Column(db.Integer)
    sanction = db.Column(db.String(100))


class Extracurricular(BaseModel):
    __tablename__ = 'extracurriculars'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)
    supervisor_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    students = db.relationship('Student', secondary=student_extracurriculars, back_populates='extracurriculars')


# ==========================================
# 7. TAHFIDZ & RECITATION PROGRAMS
# ==========================================
class TahfidzRecord(BaseModel):
    """
    Khusus untuk Tahfidz (Ziyadah & Murajaah) - TERPISAH dari Setoran Bacaan
    """
    __tablename__ = 'tahfidz_records'
    id = db.Column(db.Integer, primary_key=True)

    # MODIFIED: Bisa untuk siswa atau peserta majelis
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=True)
    majlis_participant_id = db.Column(db.Integer, db.ForeignKey('majlis_participants.id'), nullable=True)

    participant_type = db.Column(db.Enum(ParticipantType, name='participanttype'), default=ParticipantType.STUDENT)

    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    teacher = db.relationship('Teacher', backref='tahfidz_history')
    date = db.Column(db.DateTime, default=datetime.utcnow)
    type = db.Column(db.Enum(TahfidzType, name='tahfidztype'))  # Hanya ZIYADAH/MURAJAAH
    juz = db.Column(db.Integer)
    surah = db.Column(db.String(50))
    ayat_start = db.Column(db.Integer)
    ayat_end = db.Column(db.Integer)
    quality = db.Column(db.String(20))
    tajwid_errors = db.Column(db.Integer, default=0)
    makhraj_errors = db.Column(db.Integer, default=0)
    tahfidz_errors = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer)
    notes = db.Column(db.Text)

    # Relationships
    parent_participant = db.relationship('Parent', foreign_keys=[parent_id], backref='tahfidz_records')
    majlis_participant = db.relationship('MajlisParticipant', backref='tahfidz_records')


class TahfidzSummary(BaseModel):
    __tablename__ = 'tahfidz_summaries'
    id = db.Column(db.Integer, primary_key=True)

    # MODIFIED: Bisa untuk siswa atau peserta majelis
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=True)
    majlis_participant_id = db.Column(db.Integer, db.ForeignKey('majlis_participants.id'), nullable=True)

    participant_type = db.Column(db.Enum(ParticipantType, name='participanttype'), default=ParticipantType.STUDENT)

    total_juz = db.Column(db.Float, default=0)
    last_surah = db.Column(db.String(50))
    last_ayat = db.Column(db.Integer)

    # Relationships
    parent_participant = db.relationship('Parent', foreign_keys=[parent_id], backref='tahfidz_summary')
    majlis_participant = db.relationship('MajlisParticipant', backref='tahfidz_summary')


class RecitationRecord(BaseModel):
    """
    TERPISAH: Record setoran bacaan (Al-Qur'an / Kitab lainnya)
    Ini yang digunakan di input_recitation.html
    """
    __tablename__ = 'recitation_records'
    id = db.Column(db.Integer, primary_key=True)

    # Support untuk siswa dan peserta majlis
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=True)
    majlis_participant_id = db.Column(db.Integer, db.ForeignKey('majlis_participants.id'), nullable=True)

    participant_type = db.Column(db.Enum(ParticipantType, name='participanttype'), default=ParticipantType.STUDENT)

    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    teacher = db.relationship('Teacher', backref='recitation_history')
    date = db.Column(db.DateTime, default=datetime.utcnow)

    # BARU: Menggunakan RecitationSource enum
    recitation_source = db.Column(db.Enum(RecitationSource, name='recitationsource'), default=RecitationSource.QURAN)

    # Fields untuk Al-Qur'an
    surah = db.Column(db.String(50))
    ayat_start = db.Column(db.Integer)
    ayat_end = db.Column(db.Integer)

    # Fields untuk Kitab/Buku
    book_name = db.Column(db.String(100))
    page_start = db.Column(db.Integer)
    page_end = db.Column(db.Integer)

    # Penilaian
    tajwid_errors = db.Column(db.Integer, default=0)
    makhraj_errors = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer)
    notes = db.Column(db.Text)

    # Relationships
    parent_participant = db.relationship('Parent', foreign_keys=[parent_id], backref='recitation_records')
    majlis_participant = db.relationship('MajlisParticipant', backref='recitation_records')


class TahfidzEvaluation(BaseModel):
    __tablename__ = 'tahfidz_evaluations'
    id = db.Column(db.Integer, primary_key=True)

    # Support untuk siswa dan peserta majlis
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=True)
    majlis_participant_id = db.Column(db.Integer, db.ForeignKey('majlis_participants.id'), nullable=True)

    participant_type = db.Column(db.Enum(ParticipantType, name='participanttype'), default=ParticipantType.STUDENT)

    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    teacher = db.relationship('Teacher', backref='tahfidz_evaluations')
    date = db.Column(db.DateTime, default=datetime.utcnow)
    period_type = db.Column(db.Enum(EvaluationPeriod, name='evaluationperiod'))
    period_label = db.Column(db.String(30))
    makhraj_errors = db.Column(db.Integer, default=0)
    tajwid_errors = db.Column(db.Integer, default=0)
    harakat_errors = db.Column(db.Integer, default=0)
    tahfidz_errors = db.Column(db.Integer, default=0)
    score = db.Column(db.Integer)
    notes = db.Column(db.Text)

    # Relationships
    parent_participant = db.relationship('Parent', foreign_keys=[parent_id], backref='tahfidz_evaluations')
    majlis_participant = db.relationship('MajlisParticipant', backref='tahfidz_evaluations')


# ==========================================
# 8. FINANCE
# ==========================================
class FeeType(BaseModel):
    __tablename__ = 'fee_types'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    amount = db.Column(db.Float)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    academic_year = db.relationship('AcademicYear', backref='fees')


class Invoice(BaseModel):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_types.id'))
    total_amount = db.Column(db.Float)
    paid_amount = db.Column(db.Float, default=0)
    status = db.Column(db.Enum(PaymentStatus, name='paymentstatus'), default=PaymentStatus.UNPAID)
    due_date = db.Column(db.Date)

    fee_type = db.relationship('FeeType', backref='invoices')
    transactions = db.relationship('Transaction', backref='invoice', lazy=True)


class Transaction(BaseModel):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    amount = db.Column(db.Float)
    method = db.Column(db.String(30))
    date = db.Column(db.DateTime, default=datetime.utcnow)
    pic_id = db.Column(db.Integer, db.ForeignKey('users.id'))


# ==========================================
# 9. PPDB CANDIDATE (COMPLETED)
# ==========================================
class StudentCandidate(BaseModel):
    __tablename__ = 'student_candidates'
    id = db.Column(db.Integer, primary_key=True)
    registration_no = db.Column(db.String(20), unique=True)
    program_type = db.Column(db.Enum(ProgramType, name="programtype"), default=ProgramType.SEKOLAH_FULLDAY)
    education_level = db.Column(db.Enum(EducationLevel))
    scholarship_category = db.Column(db.Enum(ScholarshipCategory, name="scholarshipcategory"),
                                     default=ScholarshipCategory.NON_BEASISWA)
    status = db.Column(db.Enum(RegistrationStatus), default=RegistrationStatus.PENDING)

    full_name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(50))
    nik = db.Column(db.String(20))
    kk_number = db.Column(db.String(20))
    gender = db.Column(db.Enum(Gender))
    place_of_birth = db.Column(db.String(50))
    date_of_birth = db.Column(db.Date)
    age = db.Column(db.Integer)
    address = db.Column(db.Text)

    previous_school = db.Column(db.String(100))
    previous_school_class = db.Column(db.String(20))

    # Data Orang Tua (Optional untuk Majelis Ta'lim)
    father_name = db.Column(db.String(100))
    father_job = db.Column(db.String(100))
    mother_name = db.Column(db.String(100))
    mother_job = db.Column(db.String(100))
    parent_phone = db.Column(db.String(20))
    father_income_range = db.Column(db.String(50))
    mother_income_range = db.Column(db.String(50))

    # BARU: Data khusus untuk Majelis Ta'lim
    personal_phone = db.Column(db.String(20), nullable=True)  # WhatsApp pribadi untuk peserta majlis
    personal_job = db.Column(db.String(100), nullable=True)   # Pekerjaan peserta majlis

    tahfidz_schedule = db.Column(db.Enum(TahfidzSchedule), default=TahfidzSchedule.TIDAK_ADA)
    uniform_size = db.Column(db.Enum(UniformSize), default=UniformSize.TIDAK_MEMILIH)
    initial_pledge_amount = db.Column(db.Float, default=0)
    finance_option = db.Column(db.String(50))


class AdmissionFeeTemplate(BaseModel):
    __tablename__ = 'admission_fee_templates'
    id = db.Column(db.Integer, primary_key=True)
    program_type = db.Column(db.Enum(ProgramType, name="programtype"), nullable=False)
    scholarship_category = db.Column(db.Enum(ScholarshipCategory, name="scholarshipcategory"), nullable=True)

    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_types.id'), nullable=False)
    fee_type = db.relationship('FeeType')

    # Opsional: Jika harga di template beda dengan harga master FeeType
    custom_amount = db.Column(db.Float, nullable=True)