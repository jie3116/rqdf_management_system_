from app.extensions import db
from datetime import datetime
import enum
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.utils.timezone import local_today, utc_now_naive


# ==========================================
# 0. BASE MODEL (SCALABILITY FOUNDATION)
# ==========================================
class BaseModel(db.Model):
    """
    Kelas Abstract yang akan diwarisi oleh semua model.
    Menyediakan fitur Timestamp otomatis dan Soft Delete.
    """
    __abstract__ = True

    created_at = db.Column(db.DateTime, default=utc_now_naive)
    updated_at = db.Column(db.DateTime, default=utc_now_naive, onupdate=utc_now_naive)
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
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    PIMPINAN = "pimpinan"
    GURU = "teacher"
    SISWA = "student"
    WALI_MURID = "wali_murid"
    WALI_ASRAMA = "wali_asrama"
    TU = "tata_usaha"
    MAJLIS_PARTICIPANT = "majlis_participant"


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


class BehaviorReportType(enum.Enum):
    POSITIVE = "Apresiasi"
    DEVELOPMENT = "Pembinaan"
    CONCERN = "Perlu Perhatian"


class ProgramType(enum.Enum):
    RQDF_SORE = "RQDF Reguler (Sore)"
    SEKOLAH_FULLDAY = "Sekolah Bina Qur'an"
    TAKHOSUS_TAHFIDZ = "Takhosus Tahfidz"
    MAJLIS_TALIM = "Majelis Ta'lim"
    BAHASA = "Program Bahasa"


class EducationLevel(enum.Enum):
    NON_FORMAL = "Non Formal"
    SD = "SD"
    SMP = "SMP"
    SMA = "SMA"


class TenantStatus(enum.Enum):
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    ARCHIVED = "Archived"


class PersonKind(enum.Enum):
    STUDENT = "Student"
    PARENT = "Parent"
    EXTERNAL = "External"
    STAFF = "Staff"


class ProgramCategory(enum.Enum):
    FORMAL = "Formal"
    NON_FORMAL = "Non Formal"


class EnrollmentStatus(enum.Enum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    GRADUATED = "Graduated"
    LEFT = "Left"
    COMPLETED = "Completed"


class GroupType(enum.Enum):
    CLASS = "Class"
    HALAQAH = "Halaqah"
    MAJLIS_CLASS = "Majlis Class"
    DORMITORY = "Dormitory"
    ACTIVITY_GROUP = "Activity Group"


class MembershipStatus(enum.Enum):
    ACTIVE = "Active"
    LEFT = "Left"
    MOVED = "Moved"
    COMPLETED = "Completed"


class AssignmentRole(enum.Enum):
    HOMEROOM = "Homeroom"
    SUBJECT_TEACHER = "Subject Teacher"
    MURABBI = "Murabbi"
    MUSYRIF = "Musyrif"
    PEMBINA = "Pembina"


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


class PpdbPeriodStatus(enum.Enum):
    DRAFT = "Draft"
    OPEN = "Dibuka"
    CLOSED = "Ditutup"


class PpdbFieldType(enum.Enum):
    TEXT = "Text"
    TEXTAREA = "Textarea"
    NUMBER = "Number"
    DATE = "Date"
    SELECT = "Select"
    BOOLEAN = "Boolean"


class ClassType(enum.Enum):
    REGULAR = "Kelas Reguler"
    MAJLIS_TALIM = "Majelis Ta'lim"


class SavingsTransactionType(enum.Enum):
    DEPOSIT = "Setoran"
    WITHDRAWAL = "Penarikan"


class SavingsTransactionStatus(enum.Enum):
    PENDING = "Menunggu Verifikasi"
    APPROVED = "Disetujui"
    REJECTED = "Ditolak"


class FinanceAccountCategory(enum.Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"


class FinanceNormalBalance(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class FinancePeriodStatus(enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"


class FinanceAccountingBasis(enum.Enum):
    CASH = "CASH"
    ACCRUAL = "ACCRUAL"


class FinanceJournalStatus(enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    VOID = "VOID"


class FinanceEntrySide(enum.Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class FinanceJournalSourceType(enum.Enum):
    INVOICE_PAYMENT = "INVOICE_PAYMENT"
    SAVINGS_DEPOSIT = "SAVINGS_DEPOSIT"
    SAVINGS_WITHDRAWAL = "SAVINGS_WITHDRAWAL"
    CASH_BANK_TRANSACTION = "CASH_BANK_TRANSACTION"
    ADJUSTMENT = "ADJUSTMENT"
    REVERSAL = "REVERSAL"
    MANUAL = "MANUAL"


class FinanceCashBankAccountType(enum.Enum):
    CASH = "CASH"
    BANK = "BANK"
    EWALLET = "EWALLET"


class FinanceCashBankTransactionType(enum.Enum):
    IN = "IN"
    OUT = "OUT"
    TRANSFER = "TRANSFER"


class FinanceCashBankTransactionStatus(enum.Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    VOID = "VOID"


# ==========================================
# 2. ASSOCIATION TABLES
# ==========================================
student_extracurriculars = db.Table('student_extracurriculars',
                                    db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
                                    db.Column('extracurricular_id', db.Integer, db.ForeignKey('extracurriculars.id'),
                                              primary_key=True)
                                    )

boarding_schedule_dormitories = db.Table(
    'boarding_schedule_dormitories',
    db.Column('schedule_id', db.Integer, db.ForeignKey('boarding_activity_schedules.id'), primary_key=True),
    db.Column('dormitory_id', db.Integer, db.ForeignKey('boarding_dormitories.id'), primary_key=True),
)


# ==========================================
# 3. SYSTEM, CONFIG & KNOWLEDGE BASE
# ==========================================
class AppConfig(BaseModel):
    __tablename__ = 'app_configs'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    key = db.Column(db.String(50), nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'key', name='uq_app_configs_tenant_key'),
    )


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=utc_now_naive)


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
    target_scope = db.Column(db.String(20), default='ALL', nullable=False)  # ALL / CLASS / USER
    target_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    target_role = db.Column(db.String(30), nullable=True)
    target_program_type = db.Column(db.String(50), nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    author = db.relationship('User', foreign_keys=[user_id], backref='announcements')
    target_class = db.relationship('ClassRoom', foreign_keys=[target_class_id], backref='targeted_announcements')
    target_user = db.relationship('User', foreign_keys=[target_user_id], backref='targeted_announcements')


class AnnouncementRead(BaseModel):
    __tablename__ = 'announcement_reads'
    id = db.Column(db.Integer, primary_key=True)
    announcement_id = db.Column(db.Integer, db.ForeignKey('announcements.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    read_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)

    announcement = db.relationship('Announcement', backref='read_logs')
    user = db.relationship('User', backref='announcement_reads')

    __table_args__ = (
        db.UniqueConstraint('announcement_id', 'user_id', name='uq_announcement_read_user'),
    )


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


class AiAssistantDocument(BaseModel):
    __tablename__ = 'ai_assistant_documents'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    title = db.Column(db.String(150), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(20), nullable=False)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    extracted_text = db.Column(db.Text, nullable=True)
    extraction_status = db.Column(db.String(20), nullable=False, default='PENDING')
    extraction_error = db.Column(db.Text, nullable=True)

    tenant = db.relationship('Tenant', backref=db.backref('ai_assistant_documents', lazy='dynamic'))
    teacher = db.relationship('Teacher', backref=db.backref('ai_assistant_documents', lazy='dynamic'))

    __table_args__ = (
        db.Index('idx_ai_document_teacher_created', 'teacher_id', 'created_at'),
    )


class AiAssistantRequest(BaseModel):
    __tablename__ = 'ai_assistant_requests'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    document_id = db.Column(db.Integer, db.ForeignKey('ai_assistant_documents.id'), nullable=False, index=True)
    request_type = db.Column(db.String(30), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    parameters_json = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='COMPLETED')

    tenant = db.relationship('Tenant', backref=db.backref('ai_assistant_requests', lazy='dynamic'))
    teacher = db.relationship('Teacher', backref=db.backref('ai_assistant_requests', lazy='dynamic'))
    document = db.relationship('AiAssistantDocument', backref=db.backref('ai_requests', lazy='dynamic'))


class AiAssistantOutput(BaseModel):
    __tablename__ = 'ai_assistant_outputs'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('ai_assistant_requests.id'), nullable=False, index=True)
    output_text = db.Column(db.Text, nullable=False)
    output_format = db.Column(db.String(20), nullable=False, default='markdown')

    request = db.relationship('AiAssistantRequest', backref=db.backref('outputs', lazy='dynamic'))


class Tenant(BaseModel):
    __tablename__ = 'tenants'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(80), nullable=False, unique=True, index=True)
    code = db.Column(db.String(50), nullable=False, unique=True, index=True)
    status = db.Column(db.Enum(TenantStatus, name='tenantstatus'), default=TenantStatus.ACTIVE, nullable=False)
    timezone = db.Column(db.String(50), default='Asia/Jakarta', nullable=False)
    is_default = db.Column(db.Boolean, default=False, nullable=False)

    users = db.relationship('User', backref='tenant', lazy='dynamic')
    people = db.relationship('Person', backref='tenant', lazy='dynamic')
    programs = db.relationship('Program', backref='tenant', lazy='dynamic')


# ==========================================
# 4. USERS & PROFILES
# ==========================================
class User(UserMixin, BaseModel):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    username = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256))
    withdrawal_pin_hash = db.Column(db.String(255), nullable=True)
    withdrawal_pin_failed_attempts = db.Column(db.Integer, default=0, nullable=False)
    withdrawal_pin_locked_until = db.Column(db.DateTime, nullable=True)
    role = db.Column(db.Enum(UserRole, name='userrole'), default=UserRole.SISWA, nullable=False)
    last_login = db.Column(db.DateTime)
    must_change_password = db.Column(db.Boolean, default=True)
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'username', name='uq_users_tenant_username'),
        db.UniqueConstraint('tenant_id', 'email', name='uq_users_tenant_email'),
    )

    # Relationships
    student_profile = db.relationship('Student', backref='user', uselist=False, lazy='select')
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False, lazy='select')
    parent_profile = db.relationship('Parent', backref='user', uselist=False, lazy='select')
    staff_profile = db.relationship('Staff', backref='user', uselist=False, lazy='select')
    majlis_profile = db.relationship('MajlisParticipant', backref='user', uselist=False, lazy='select')
    boarding_guardian_profile = db.relationship('BoardingGuardian', backref='user', uselist=False, lazy='select')
    managed_dormitories = db.relationship('BoardingDormitory', backref='guardian_user', lazy='dynamic')
    role_assignments = db.relationship(
        'UserRoleAssignment',
        backref='user',
        lazy='select',
        cascade='all, delete-orphan'
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def set_withdrawal_pin(self, pin):
        self.withdrawal_pin_hash = generate_password_hash(pin)

    def check_withdrawal_pin(self, pin):
        if not self.withdrawal_pin_hash:
            return False
        return check_password_hash(self.withdrawal_pin_hash, pin)

    def all_roles(self):
        roles = set()
        if self.role:
            roles.add(self.role)
        for assignment in self.role_assignments or []:
            if assignment.role:
                roles.add(assignment.role)
        return roles

    def has_role(self, *roles):
        if not roles:
            return False

        owned_roles = self.all_roles()
        requested_roles = set()
        for role in roles:
            if isinstance(role, UserRole):
                requested_roles.add(role)
            elif isinstance(role, str):
                try:
                    requested_roles.add(UserRole(role))
                except ValueError:
                    continue
        return bool(owned_roles.intersection(requested_roles))

    def all_role_values(self):
        return {role.value for role in self.all_roles()}


class MobileRevokedToken(db.Model):
    __tablename__ = 'mobile_revoked_tokens'

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    token_type = db.Column(db.String(20), nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)


class MobileRateLimitBucket(db.Model):
    __tablename__ = 'mobile_rate_limit_buckets'

    id = db.Column(db.Integer, primary_key=True)
    bucket_key = db.Column(db.String(255), nullable=False, unique=True, index=True)
    action_name = db.Column(db.String(50), nullable=False, index=True)
    scope_key = db.Column(db.String(255), nullable=False, index=True)
    count = db.Column(db.Integer, nullable=False, default=0)
    window_ends_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


class MobileDeviceToken(BaseModel):
    __tablename__ = 'mobile_device_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(255), nullable=False, unique=True, index=True)
    platform = db.Column(db.String(20), nullable=False, default='unknown')
    device_name = db.Column(db.String(120), nullable=True)
    app_version = db.Column(db.String(40), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    last_seen_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False, index=True)

    user = db.relationship('User', backref=db.backref('mobile_device_tokens', lazy='dynamic'))


class Person(BaseModel):
    __tablename__ = 'people'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    person_code = db.Column(db.String(50), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.Enum(Gender, name='gender'), nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    phone = db.Column(db.String(20), nullable=True, index=True)
    address = db.Column(db.Text, nullable=True)
    person_kind = db.Column(db.Enum(PersonKind, name='personkind'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship('User', backref=db.backref('person', uselist=False))
    enrollments = db.relationship('ProgramEnrollment', backref='person', lazy='dynamic')
    staff_assignments = db.relationship('StaffAssignment', backref='person', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'person_code', name='uq_people_tenant_person_code'),
        db.UniqueConstraint('tenant_id', 'user_id', name='uq_people_tenant_user'),
    )


class UserRoleAssignment(BaseModel):
    __tablename__ = 'user_role_assignments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.Enum(UserRole, name='userrole'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'role', name='uq_user_role_assignment'),
    )


class Parent(BaseModel):
    __tablename__ = 'parents'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=True, index=True)
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
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=True, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False, index=True)
    address = db.Column(db.Text)
    job = db.Column(db.String(100))

    majlis_class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=True)
    join_date = db.Column(db.Date, default=local_today)

    majlis_class = db.relationship('ClassRoom', foreign_keys=[majlis_class_id], backref='majlis_external_participants')


class Teacher(BaseModel):
    __tablename__ = 'teachers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=True, unique=True, index=True)
    nip = db.Column(db.String(20), unique=True)
    full_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    specialty = db.Column(db.String(50))

    homeroom_class = db.relationship('ClassRoom', backref='homeroom_teacher', uselist=False)
    supervised_extracurriculars = db.relationship('Extracurricular', backref='supervisor', lazy=True)
    behavior_reports = db.relationship('BehaviorReport', backref='teacher', lazy='dynamic')


class Staff(BaseModel):
    __tablename__ = 'staff'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=True, unique=True, index=True)
    full_name = db.Column(db.String(100))
    position = db.Column(db.String(50))


class BoardingGuardian(BaseModel):
    __tablename__ = 'boarding_guardians'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=True, unique=True, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True, index=True)


class BoardingDormitory(BaseModel):
    __tablename__ = 'boarding_dormitories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    gender = db.Column(db.Enum(Gender, name='gender'), nullable=True)
    capacity = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text, nullable=True)
    guardian_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    program_group_id = db.Column(db.Integer, db.ForeignKey('program_groups.id'), nullable=True, unique=True, index=True)


class Student(BaseModel):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id'), nullable=True)
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=True, unique=True, index=True)
    current_class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'))
    nis = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nisn = db.Column(db.String(20), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.Enum(Gender, name='gender'))
    place_of_birth = db.Column(db.String(50))
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.Text)
    custom_spp_fee = db.Column(db.Integer, nullable=True, default=None)
    boarding_dormitory_id = db.Column(db.Integer, db.ForeignKey('boarding_dormitories.id'), nullable=True)

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
    behavior_reports = db.relationship('BehaviorReport', backref='student', lazy='dynamic')
    boarding_dormitory = db.relationship('BoardingDormitory', backref='students')

    __table_args__ = (
        db.Index('idx_student_class_academic', 'current_class_id', 'created_at'),
    )


class Program(BaseModel):
    __tablename__ = 'programs'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    category = db.Column(db.Enum(ProgramCategory, name='programcategory'), nullable=False)
    education_level = db.Column(db.Enum(EducationLevel, name='educationlevel'), nullable=True)
    report_schema = db.Column(db.String(50), nullable=False)
    organization_unit = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    enrollments = db.relationship('ProgramEnrollment', backref='program', lazy='dynamic')
    groups = db.relationship('ProgramGroup', backref='program', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'code', name='uq_programs_tenant_code'),
        db.UniqueConstraint('tenant_id', 'name', name='uq_programs_tenant_name'),
    )


class ProgramEnrollment(BaseModel):
    __tablename__ = 'program_enrollments'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=False, index=True)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False, index=True)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=True)
    status = db.Column(db.Enum(EnrollmentStatus, name='enrollmentstatus'), default=EnrollmentStatus.ACTIVE, nullable=False)
    join_date = db.Column(db.Date, default=local_today, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    origin_type = db.Column(db.String(30), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    tenant = db.relationship('Tenant', backref='program_enrollments')
    academic_year = db.relationship('AcademicYear', backref='program_enrollments')
    group_memberships = db.relationship('GroupMembership', backref='enrollment', lazy='dynamic')

    __table_args__ = (
        db.Index('idx_program_enrollment_active', 'tenant_id', 'program_id', 'status'),
    )


class ProgramGroup(BaseModel):
    __tablename__ = 'program_groups'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False, index=True)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    group_type = db.Column(db.Enum(GroupType, name='grouptype'), nullable=False)
    level_label = db.Column(db.String(50), nullable=True)
    gender_scope = db.Column(db.Enum(Gender, name='gender'), nullable=True)
    capacity = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    tenant = db.relationship('Tenant', backref='program_groups')
    academic_year = db.relationship('AcademicYear', backref='program_groups')
    memberships = db.relationship('GroupMembership', backref='group', lazy='dynamic')
    staff_assignments = db.relationship('StaffAssignment', backref='group', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'program_id', 'academic_year_id', 'name', name='uq_program_groups_scope'),
    )


class GroupMembership(BaseModel):
    __tablename__ = 'group_memberships'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey('program_enrollments.id'), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('program_groups.id'), nullable=False, index=True)
    status = db.Column(db.Enum(MembershipStatus, name='membershipstatus'), default=MembershipStatus.ACTIVE, nullable=False)
    start_date = db.Column(db.Date, default=local_today, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)

    tenant = db.relationship('Tenant', backref='group_memberships')

    __table_args__ = (
        db.Index('idx_group_membership_active', 'tenant_id', 'group_id', 'status'),
    )


class StaffAssignment(BaseModel):
    __tablename__ = 'staff_assignments'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    person_id = db.Column(db.Integer, db.ForeignKey('people.id'), nullable=False, index=True)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id'), nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey('program_groups.id'), nullable=True, index=True)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=True)
    assignment_role = db.Column(db.Enum(AssignmentRole, name='assignmentrole'), nullable=False)
    start_date = db.Column(db.Date, default=local_today, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    tenant = db.relationship('Tenant', backref='staff_assignments')
    program = db.relationship('Program', backref='staff_assignments')
    academic_year = db.relationship('AcademicYear', backref='staff_assignments')

    __table_args__ = (
        db.Index('idx_staff_assignment_active', 'tenant_id', 'program_id', 'assignment_role'),
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
    program_group_id = db.Column(db.Integer, db.ForeignKey('program_groups.id'), nullable=True, unique=True, index=True)

    # BARU: Tipe kelas
    class_type = db.Column(db.Enum(ClassType, name='classtype'), default=ClassType.REGULAR)
    program_type = db.Column(db.Enum(ProgramType, name='programtype'), nullable=True)
    education_level = db.Column(db.Enum(EducationLevel, name='educationlevel'), nullable=True)

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
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=True, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    title = db.Column(db.String(100))
    file_url = db.Column(db.String(255))
    description = db.Column(db.Text)
    material_type = db.Column(db.String(20), default='LINK', nullable=False)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    published_at = db.Column(db.DateTime, default=utc_now_naive, nullable=True)

    class_room = db.relationship('ClassRoom', backref='learning_materials')
    teacher = db.relationship('Teacher', backref='learning_materials')
    subject = db.relationship('Subject', backref='learning_materials')


class OnlineClassSession(BaseModel):
    __tablename__ = 'online_class_sessions'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    meeting_url = db.Column(db.String(255), nullable=False)
    meeting_provider = db.Column(db.String(30), nullable=True)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    class_room = db.relationship('ClassRoom', backref='online_sessions')
    teacher = db.relationship('Teacher', backref='online_sessions')
    subject = db.relationship('Subject', backref='online_sessions')

    __table_args__ = (
        db.Index('idx_online_class_session_class_time', 'class_id', 'starts_at'),
    )


class LearningAssignment(BaseModel):
    __tablename__ = 'learning_assignments'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    resource_url = db.Column(db.String(255), nullable=True)
    due_at = db.Column(db.DateTime, nullable=False, index=True)
    max_score = db.Column(db.Float, default=100.0, nullable=False)
    is_published = db.Column(db.Boolean, default=True, nullable=False)

    class_room = db.relationship('ClassRoom', backref='learning_assignments')
    teacher = db.relationship('Teacher', backref='learning_assignments')
    subject = db.relationship('Subject', backref='learning_assignments')

    __table_args__ = (
        db.Index('idx_learning_assignment_class_due', 'class_id', 'due_at'),
    )


class LearningAssignmentSubmission(BaseModel):
    __tablename__ = 'learning_assignment_submissions'
    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('learning_assignments.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)
    submission_text = db.Column(db.Text, nullable=True)
    submission_url = db.Column(db.String(255), nullable=True)
    submitted_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False, index=True)
    score = db.Column(db.Float, nullable=True)
    feedback = db.Column(db.Text, nullable=True)
    graded_at = db.Column(db.DateTime, nullable=True)
    graded_by_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=True)

    assignment = db.relationship('LearningAssignment', backref='submissions')
    student = db.relationship('Student', backref='learning_submissions')
    graded_by_teacher = db.relationship('Teacher', foreign_keys=[graded_by_teacher_id], backref='graded_submissions')

    __table_args__ = (
        db.UniqueConstraint('assignment_id', 'student_id', name='uq_assignment_submission_student'),
        db.Index('idx_assignment_submission_assignment_submitted', 'assignment_id', 'submitted_at'),
    )


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

    date = db.Column(db.Date, default=local_today, nullable=False)
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


class BoardingActivitySchedule(BaseModel):
    __tablename__ = 'boarding_activity_schedules'
    id = db.Column(db.Integer, primary_key=True)
    dormitory_id = db.Column(db.Integer, db.ForeignKey('boarding_dormitories.id'), nullable=True)  # legacy support
    activity_name = db.Column(db.String(100), nullable=False)
    day = db.Column(db.String(10), nullable=True)  # legacy support
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    applies_all_dormitories = db.Column(db.Boolean, default=True, nullable=False)
    applies_all_days = db.Column(db.Boolean, default=True, nullable=False)
    selected_days = db.Column(db.String(100), nullable=True)  # CSV hari: Senin,Selasa,...
    exclude_national_holidays = db.Column(db.Boolean, default=True, nullable=False)

    dormitory = db.relationship('BoardingDormitory', backref='activity_schedules')
    selected_dormitories = db.relationship(
        'BoardingDormitory',
        secondary=boarding_schedule_dormitories,
        backref='custom_activity_schedules'
    )


class BoardingAttendance(BaseModel):
    __tablename__ = 'boarding_attendances'
    id = db.Column(db.Integer, primary_key=True)
    dormitory_id = db.Column(db.Integer, db.ForeignKey('boarding_dormitories.id'), nullable=False)
    schedule_id = db.Column(db.Integer, db.ForeignKey('boarding_activity_schedules.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    attendance_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=local_today, nullable=False)
    status = db.Column(db.Enum(AttendanceStatus, name='attendancestatus'), default=AttendanceStatus.HADIR, nullable=False)
    notes = db.Column(db.String(150), nullable=True)

    dormitory = db.relationship('BoardingDormitory', backref='attendance_records')
    schedule = db.relationship('BoardingActivitySchedule', backref='attendance_records')
    attendance_by_user = db.relationship('User', backref='boarding_attendance_inputs')

    __table_args__ = (
        db.UniqueConstraint('date', 'schedule_id', 'student_id', name='uq_boarding_attendance_student_schedule_date'),
        db.Index('idx_boarding_attendance_dormitory_date', 'dormitory_id', 'date'),
    )


class BoardingHoliday(BaseModel):
    __tablename__ = 'boarding_holidays'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    is_national = db.Column(db.Boolean, default=True, nullable=False)


class Grade(BaseModel):
    """
    Menyimpan nilai harian (Raw Data) yang diinput Guru.
    """
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    majlis_participant_id = db.Column(db.Integer, db.ForeignKey('majlis_participants.id'), nullable=True)
    participant_type = db.Column(db.Enum(ParticipantType, name='participanttype'), default=ParticipantType.STUDENT, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=True)
    majlis_subject_id = db.Column(db.Integer, db.ForeignKey('majlis_subjects.id'), nullable=True)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))

    type = db.Column(db.Enum(GradeType, name='gradetype'))  # Tugas, UTS, UAS
    score = db.Column(db.Float)
    notes = db.Column(db.String(100))

    subject = db.relationship('Subject', backref='grades')
    majlis_subject = db.relationship('MajlisSubject', backref='grades')
    teacher = db.relationship('Teacher', backref='input_grades')
    academic_year = db.relationship('AcademicYear', backref='grades')
    majlis_participant = db.relationship('MajlisParticipant', backref='grades')


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


class ReportScoreAdjustment(BaseModel):
    """
    Adjustment resmi nilai akhir raport.
    Tidak mengubah nilai raw guru; hanya mengoreksi nilai final dengan jejak persetujuan.
    """
    __tablename__ = 'report_score_adjustments'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=True, index=True)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'), nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False, index=True)
    original_score = db.Column(db.Float, nullable=False)
    adjusted_score = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    approval_reference = db.Column(db.String(100), nullable=False)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    approved_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    status = db.Column(db.String(20), default='ACTIVE', nullable=False, index=True)
    void_reason = db.Column(db.Text, nullable=True)
    voided_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    voided_at = db.Column(db.DateTime, nullable=True)

    tenant = db.relationship('Tenant', backref='report_score_adjustments')
    student = db.relationship('Student', backref='report_score_adjustments')
    class_room = db.relationship('ClassRoom', backref='report_score_adjustments')
    academic_year = db.relationship('AcademicYear', backref='report_score_adjustments')
    subject = db.relationship('Subject', backref='report_score_adjustments')
    approved_by_user = db.relationship('User', foreign_keys=[approved_by_user_id], backref='approved_report_score_adjustments')
    voided_by_user = db.relationship('User', foreign_keys=[voided_by_user_id], backref='voided_report_score_adjustments')

    __table_args__ = (
        db.Index(
            'idx_report_score_adjustment_lookup',
            'tenant_id', 'student_id', 'academic_year_id', 'subject_id', 'status'
        ),
    )


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
    date = db.Column(db.Date, default=local_today)
    description = db.Column(db.Text)
    points = db.Column(db.Integer)
    sanction = db.Column(db.String(100))


class BehaviorReport(BaseModel):
    __tablename__ = 'behavior_reports'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'), nullable=False, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('class_rooms.id'), nullable=True, index=True)
    report_date = db.Column(db.Date, default=local_today, nullable=False, index=True)
    report_type = db.Column(db.Enum(BehaviorReportType, name='behaviorreporttype'), nullable=False)
    indicator_key = db.Column(db.String(50), nullable=True, index=True)
    indicator_group = db.Column(db.String(20), nullable=True)
    is_yes = db.Column(db.Boolean, nullable=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    action_plan = db.Column(db.Text, nullable=True)
    follow_up_date = db.Column(db.Date, nullable=True)
    is_resolved = db.Column(db.Boolean, default=False)

    class_room = db.relationship('ClassRoom', backref='behavior_reports')


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
    date = db.Column(db.DateTime, default=utc_now_naive)
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
    date = db.Column(db.DateTime, default=utc_now_naive)

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
    score = db.Column(db.Float)
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
    date = db.Column(db.DateTime, default=utc_now_naive)
    period_type = db.Column(db.Enum(EvaluationPeriod, name='evaluationperiod'))
    period_label = db.Column(db.String(30))
    evaluation_type = db.Column(db.String(30), default='SAMBUNG_AYAT')
    question_count = db.Column(db.Integer, default=0)
    question_details = db.Column(db.Text)
    question_items = db.Column(db.Text)
    surah = db.Column(db.String(50))
    ayat_start = db.Column(db.Integer)
    ayat_end = db.Column(db.Integer)
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
class FinanceAccount(BaseModel):
    __tablename__ = 'finance_accounts'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.Enum(FinanceAccountCategory, name='financeaccountcategory'), nullable=False)
    normal_balance = db.Column(db.Enum(FinanceNormalBalance, name='financenormalbalance'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('finance_accounts.id'), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    parent = db.relationship('FinanceAccount', remote_side=[id], backref=db.backref('children', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'code', name='uq_finance_accounts_tenant_code'),
    )


class FinancePeriod(BaseModel):
    __tablename__ = 'finance_periods'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    name = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(FinancePeriodStatus, name='financeperiodstatus'), default=FinancePeriodStatus.OPEN, nullable=False)
    closed_at = db.Column(db.DateTime, nullable=True)
    closed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    closed_by = db.relationship('User', foreign_keys=[closed_by_user_id], backref='closed_finance_periods')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_finance_periods_tenant_name'),
    )


class FinanceCashBankAccount(BaseModel):
    __tablename__ = 'finance_cash_bank_accounts'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    account_name = db.Column(db.String(120), nullable=False)
    account_type = db.Column(db.Enum(FinanceCashBankAccountType, name='financecashbankaccounttype'), nullable=False)
    gl_account_id = db.Column(db.Integer, db.ForeignKey('finance_accounts.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    gl_account = db.relationship('FinanceAccount', backref='cash_bank_accounts')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'account_name', name='uq_finance_cash_bank_accounts_tenant_name'),
    )


class FinanceSetting(BaseModel):
    __tablename__ = 'finance_settings'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    accounting_basis = db.Column(
        db.Enum(FinanceAccountingBasis, name='financeaccountingbasis'),
        default=FinanceAccountingBasis.CASH,
        nullable=False,
    )
    default_cash_bank_account_id = db.Column(db.Integer, db.ForeignKey('finance_cash_bank_accounts.id'), nullable=True)
    default_spp_revenue_account_id = db.Column(db.Integer, db.ForeignKey('finance_accounts.id'), nullable=True)
    default_registration_revenue_account_id = db.Column(db.Integer, db.ForeignKey('finance_accounts.id'), nullable=True)
    default_savings_liability_account_id = db.Column(db.Integer, db.ForeignKey('finance_accounts.id'), nullable=True)
    default_donation_revenue_account_id = db.Column(db.Integer, db.ForeignKey('finance_accounts.id'), nullable=True)

    default_cash_bank_account = db.relationship('FinanceCashBankAccount', foreign_keys=[default_cash_bank_account_id], backref='finance_settings_default')
    default_spp_revenue_account = db.relationship('FinanceAccount', foreign_keys=[default_spp_revenue_account_id], backref='finance_settings_spp_revenue')
    default_registration_revenue_account = db.relationship('FinanceAccount', foreign_keys=[default_registration_revenue_account_id], backref='finance_settings_registration_revenue')
    default_savings_liability_account = db.relationship('FinanceAccount', foreign_keys=[default_savings_liability_account_id], backref='finance_settings_savings_liability')
    default_donation_revenue_account = db.relationship('FinanceAccount', foreign_keys=[default_donation_revenue_account_id], backref='finance_settings_donation_revenue')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', name='uq_finance_settings_tenant'),
    )


class FinanceJournalSequence(BaseModel):
    __tablename__ = 'finance_journal_sequences'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    year_month = db.Column(db.String(7), nullable=False)
    last_value = db.Column(db.Integer, default=0, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'year_month', name='uq_finance_journal_sequences_tenant_month'),
    )


class FinanceJournal(BaseModel):
    __tablename__ = 'finance_journals'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    journal_no = db.Column(db.String(30), nullable=False)
    journal_date = db.Column(db.Date, nullable=False, default=local_today)
    description = db.Column(db.Text, nullable=True)
    source_type = db.Column(db.Enum(FinanceJournalSourceType, name='financejournalsourcetype'), nullable=True)
    source_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.Enum(FinanceJournalStatus, name='financejournalstatus'), default=FinanceJournalStatus.DRAFT, nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    posted_at = db.Column(db.DateTime, nullable=True)
    voided_at = db.Column(db.DateTime, nullable=True)
    void_reason = db.Column(db.Text, nullable=True)

    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='created_finance_journals')
    approved_by = db.relationship('User', foreign_keys=[approved_by_user_id], backref='approved_finance_journals')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'journal_no', name='uq_finance_journals_tenant_journal_no'),
        db.UniqueConstraint('tenant_id', 'source_type', 'source_id', name='uq_finance_journals_tenant_source'),
    )


class FinanceJournalLine(BaseModel):
    __tablename__ = 'finance_journal_lines'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('finance_journals.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('finance_accounts.id'), nullable=False)
    entry_side = db.Column(db.Enum(FinanceEntrySide, name='financeentryside'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    memo = db.Column(db.Text, nullable=True)
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)

    journal = db.relationship('FinanceJournal', backref='lines')
    account = db.relationship('FinanceAccount', backref='journal_lines')

    __table_args__ = (
        db.CheckConstraint('amount > 0', name='ck_finance_journal_lines_amount_positive'),
    )


class FinanceCashBankTransaction(BaseModel):
    __tablename__ = 'finance_cash_bank_transactions'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    cash_bank_account_id = db.Column(db.Integer, db.ForeignKey('finance_cash_bank_accounts.id'), nullable=False)
    trx_date = db.Column(db.Date, nullable=False, default=local_today)
    trx_type = db.Column(db.Enum(FinanceCashBankTransactionType, name='financecashbanktransactiontype'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    counterpart_account_id = db.Column(db.Integer, db.ForeignKey('finance_accounts.id'), nullable=True)
    description = db.Column(db.Text, nullable=True)
    journal_id = db.Column(db.Integer, db.ForeignKey('finance_journals.id'), nullable=True)
    status = db.Column(
        db.Enum(FinanceCashBankTransactionStatus, name='financecashbanktransactionstatus'),
        default=FinanceCashBankTransactionStatus.DRAFT,
        nullable=False,
    )
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    cash_bank_account = db.relationship('FinanceCashBankAccount', backref='transactions')
    counterpart_account = db.relationship('FinanceAccount', foreign_keys=[counterpart_account_id], backref='cash_bank_counterparts')
    journal = db.relationship('FinanceJournal', backref='cash_bank_transactions')
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], backref='created_cash_bank_transactions')
    approved_by = db.relationship('User', foreign_keys=[approved_by_user_id], backref='approved_cash_bank_transactions')

    __table_args__ = (
        db.CheckConstraint('amount > 0', name='ck_finance_cash_bank_transactions_amount_positive'),
    )


class FeeType(BaseModel):
    __tablename__ = 'fee_types'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    name = db.Column(db.String(50))
    amount = db.Column(db.Integer)
    academic_year_id = db.Column(db.Integer, db.ForeignKey('academic_years.id'))
    academic_year = db.relationship('AcademicYear', backref='fees')


class Invoice(BaseModel):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_types.id'))
    total_amount = db.Column(db.Integer)
    paid_amount = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum(PaymentStatus, name='paymentstatus'), default=PaymentStatus.UNPAID)
    due_date = db.Column(db.Date)

    fee_type = db.relationship('FeeType', backref='invoices')
    transactions = db.relationship('Transaction', backref='invoice', lazy=True)


class Transaction(BaseModel):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))
    amount = db.Column(db.Integer)
    method = db.Column(db.String(30))
    date = db.Column(db.DateTime, default=utc_now_naive)
    pic_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class StudentSavingsAccount(BaseModel):
    __tablename__ = 'student_savings_accounts'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, unique=True)
    balance = db.Column(db.Integer, default=0, nullable=False)
    pin_hash = db.Column(db.String(255), nullable=True)
    pin_failed_attempts = db.Column(db.Integer, default=0, nullable=False)
    pin_locked_until = db.Column(db.DateTime, nullable=True)

    student = db.relationship('Student', backref=db.backref('savings_account', uselist=False))

    def set_pin(self, pin):
        self.pin_hash = generate_password_hash(pin)

    def check_pin(self, pin):
        if not self.pin_hash:
            return False
        return check_password_hash(self.pin_hash, pin)


class StudentSavingsTransaction(BaseModel):
    __tablename__ = 'student_savings_transactions'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    account_id = db.Column(db.Integer, db.ForeignKey('student_savings_accounts.id'), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.Enum(SavingsTransactionType, name='savingstransactiontype'), nullable=False)
    status = db.Column(db.Enum(SavingsTransactionStatus, name='savingstransactionstatus'), default=SavingsTransactionStatus.PENDING, nullable=False)
    proof_image = db.Column(db.String(255), nullable=True)
    requested_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    account = db.relationship('StudentSavingsAccount', backref='transactions')
    student = db.relationship('Student', backref='savings_transactions')
    requested_by = db.relationship('User', foreign_keys=[requested_by_user_id], backref='requested_savings_transactions')
    approved_by = db.relationship('User', foreign_keys=[approved_by_user_id], backref='approved_savings_transactions')


# ==========================================
# 9. PPDB CANDIDATE (COMPLETED)
# ==========================================
class PpdbPeriod(BaseModel):
    __tablename__ = 'ppdb_periods'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    academic_year_label = db.Column(db.String(20), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum(PpdbPeriodStatus, name='ppdbperiodstatus'), default=PpdbPeriodStatus.DRAFT, nullable=False)
    registration_no_prefix = db.Column(db.String(10), default='REG', nullable=False)
    public_registration_enabled = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    tenant = db.relationship('Tenant', backref=db.backref('ppdb_periods', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'name', name='uq_ppdb_periods_tenant_name'),
        db.CheckConstraint('end_date >= start_date', name='ck_ppdb_periods_date_range'),
    )


class TenantProgram(BaseModel):
    __tablename__ = 'tenant_programs'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    code = db.Column(db.String(40), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    system_type = db.Column(db.Enum(ProgramType, name="programtype"), nullable=False)
    education_level = db.Column(db.Enum(EducationLevel), nullable=True)
    category = db.Column(db.String(40), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.Text, nullable=True)

    tenant = db.relationship('Tenant', backref=db.backref('tenant_programs', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'code', name='uq_tenant_programs_tenant_code'),
    )


class PpdbPath(BaseModel):
    __tablename__ = 'ppdb_paths'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    period_id = db.Column(db.Integer, db.ForeignKey('ppdb_periods.id'), nullable=False, index=True)
    tenant_program_id = db.Column(db.Integer, db.ForeignKey('tenant_programs.id'), nullable=True, index=True)
    code = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    program_type = db.Column(db.Enum(ProgramType, name="programtype"), nullable=False)
    education_level = db.Column(db.Enum(EducationLevel), nullable=True)
    scholarship_category = db.Column(db.Enum(ScholarshipCategory, name="scholarshipcategory"), nullable=True)
    quota = db.Column(db.Integer, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    rules_json = db.Column(db.Text, nullable=True)

    tenant = db.relationship('Tenant', backref=db.backref('ppdb_paths', lazy='dynamic'))
    period = db.relationship('PpdbPeriod', backref=db.backref('paths', lazy='dynamic'))
    tenant_program = db.relationship('TenantProgram', backref=db.backref('ppdb_paths', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'period_id', 'code', name='uq_ppdb_paths_period_code'),
        db.CheckConstraint('quota IS NULL OR quota >= 0', name='ck_ppdb_paths_quota_non_negative'),
    )


class PpdbFormSection(BaseModel):
    __tablename__ = 'ppdb_form_sections'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    period_id = db.Column(db.Integer, db.ForeignKey('ppdb_periods.id'), nullable=False, index=True)
    path_id = db.Column(db.Integer, db.ForeignKey('ppdb_paths.id'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    tenant = db.relationship('Tenant', backref=db.backref('ppdb_form_sections', lazy='dynamic'))
    period = db.relationship('PpdbPeriod', backref=db.backref('form_sections', lazy='dynamic'))
    path = db.relationship('PpdbPath', backref=db.backref('form_sections', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'path_id', 'title', name='uq_ppdb_form_sections_path_title'),
    )


class PpdbFormField(BaseModel):
    __tablename__ = 'ppdb_form_fields'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    period_id = db.Column(db.Integer, db.ForeignKey('ppdb_periods.id'), nullable=False, index=True)
    path_id = db.Column(db.Integer, db.ForeignKey('ppdb_paths.id'), nullable=True, index=True)
    section_id = db.Column(db.Integer, db.ForeignKey('ppdb_form_sections.id'), nullable=True, index=True)
    field_key = db.Column(db.String(80), nullable=False)
    label = db.Column(db.String(120), nullable=False)
    field_type = db.Column(db.Enum(PpdbFieldType, name='ppdbfieldtype'), default=PpdbFieldType.TEXT, nullable=False)
    is_required = db.Column(db.Boolean, default=False, nullable=False)
    options_json = db.Column(db.Text, nullable=True)
    validation_json = db.Column(db.Text, nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    tenant = db.relationship('Tenant', backref=db.backref('ppdb_form_fields', lazy='dynamic'))
    period = db.relationship('PpdbPeriod', backref=db.backref('form_fields', lazy='dynamic'))
    path = db.relationship('PpdbPath', backref=db.backref('form_fields', lazy='dynamic'))
    section = db.relationship('PpdbFormSection', backref=db.backref('fields', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'period_id', 'path_id', 'field_key', name='uq_ppdb_form_fields_scope_key'),
    )


class PpdbDocumentRequirement(BaseModel):
    __tablename__ = 'ppdb_document_requirements'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    period_id = db.Column(db.Integer, db.ForeignKey('ppdb_periods.id'), nullable=False, index=True)
    path_id = db.Column(db.Integer, db.ForeignKey('ppdb_paths.id'), nullable=True, index=True)
    code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    is_required = db.Column(db.Boolean, default=True, nullable=False)
    allowed_file_types = db.Column(db.String(120), nullable=True)
    max_file_size_kb = db.Column(db.Integer, nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    tenant = db.relationship('Tenant', backref=db.backref('ppdb_document_requirements', lazy='dynamic'))
    period = db.relationship('PpdbPeriod', backref=db.backref('document_requirements', lazy='dynamic'))
    path = db.relationship('PpdbPath', backref=db.backref('document_requirements', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'period_id', 'path_id', 'code', name='uq_ppdb_document_requirements_scope_code'),
    )


class PpdbFeeItem(BaseModel):
    __tablename__ = 'ppdb_fee_items'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    period_id = db.Column(db.Integer, db.ForeignKey('ppdb_periods.id'), nullable=False, index=True)
    path_id = db.Column(db.Integer, db.ForeignKey('ppdb_paths.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    notes = db.Column(db.String(200), nullable=True)

    tenant = db.relationship('Tenant', backref=db.backref('ppdb_fee_items', lazy='dynamic'))
    period = db.relationship('PpdbPeriod', backref=db.backref('fee_items', lazy='dynamic'))
    path = db.relationship('PpdbPath', backref=db.backref('fee_items', lazy='dynamic'))

    __table_args__ = (
        db.CheckConstraint('amount >= 0', name='ck_ppdb_fee_items_amount_non_negative'),
    )


class PpdbFeatureFlag(BaseModel):
    __tablename__ = 'ppdb_feature_flags'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    key = db.Column(db.String(80), nullable=False)
    is_enabled = db.Column(db.Boolean, default=False, nullable=False)
    value_json = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(200), nullable=True)

    tenant = db.relationship('Tenant', backref=db.backref('ppdb_feature_flags', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'key', name='uq_ppdb_feature_flags_tenant_key'),
    )


class StudentCandidate(BaseModel):
    __tablename__ = 'student_candidates'
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False, index=True)
    ppdb_period_id = db.Column(db.Integer, db.ForeignKey('ppdb_periods.id'), nullable=True, index=True)
    ppdb_path_id = db.Column(db.Integer, db.ForeignKey('ppdb_paths.id'), nullable=True, index=True)
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
    extra_answers_json = db.Column(db.Text, nullable=True)
    document_status_json = db.Column(db.Text, nullable=True)

    ppdb_period = db.relationship('PpdbPeriod', backref=db.backref('candidates', lazy='dynamic'))
    ppdb_path = db.relationship('PpdbPath', backref=db.backref('candidates', lazy='dynamic'))


class AdmissionFeeTemplate(BaseModel):
    __tablename__ = 'admission_fee_templates'
    id = db.Column(db.Integer, primary_key=True)
    program_type = db.Column(db.Enum(ProgramType, name="programtype"), nullable=False)
    scholarship_category = db.Column(db.Enum(ScholarshipCategory, name="scholarshipcategory"), nullable=True)

    fee_type_id = db.Column(db.Integer, db.ForeignKey('fee_types.id'), nullable=False)
    fee_type = db.relationship('FeeType')

    # Opsional: Jika harga di template beda dengan harga master FeeType
    custom_amount = db.Column(db.Float, nullable=True)


