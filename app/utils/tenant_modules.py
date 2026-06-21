from app.models import AppConfig, UserRole


TENANT_PACKAGE_KEY = "tenant.module_package"

PACKAGE_FULL = "full"
PACKAGE_RUMAH_QURAN = "rumah_quran"
PACKAGE_SEKOLAH = "sekolah"
PACKAGE_OPTIONS = (PACKAGE_FULL, PACKAGE_RUMAH_QURAN, PACKAGE_SEKOLAH)

CAPABILITY_QURAN = "quran"
CAPABILITY_SCHOOL_ACADEMIC = "school_academic"
CAPABILITY_TEACHER = "teacher"
CAPABILITY_STUDENT = "student"
CAPABILITY_PARENT = "parent"
CAPABILITY_BOARDING = "boarding"
CAPABILITY_MAJLIS = "majlis"
CAPABILITY_FINANCE = "finance"
CAPABILITY_PPDB = "ppdb"
CAPABILITY_ONLINE_CLASS = "online_class"
CAPABILITY_AI_ASSISTANT = "ai_assistant"
CAPABILITY_ANALYTICS = "analytics"
CAPABILITY_ANNOUNCEMENT = "announcement"

BASE_CAPABILITIES = frozenset(
    {
        CAPABILITY_QURAN,
        CAPABILITY_SCHOOL_ACADEMIC,
        CAPABILITY_TEACHER,
        CAPABILITY_STUDENT,
        CAPABILITY_PARENT,
        CAPABILITY_BOARDING,
        CAPABILITY_MAJLIS,
        CAPABILITY_ANALYTICS,
        CAPABILITY_ANNOUNCEMENT,
    }
)

ADD_ON_CAPABILITIES = frozenset(
    {
        CAPABILITY_FINANCE,
        CAPABILITY_PPDB,
        CAPABILITY_ONLINE_CLASS,
        CAPABILITY_AI_ASSISTANT,
    }
)

ALL_CAPABILITIES = BASE_CAPABILITIES | ADD_ON_CAPABILITIES

SCHOOL_CAPABILITIES = frozenset(
    {
        CAPABILITY_SCHOOL_ACADEMIC,
        CAPABILITY_TEACHER,
        CAPABILITY_STUDENT,
        CAPABILITY_PARENT,
        CAPABILITY_ANALYTICS,
        CAPABILITY_ANNOUNCEMENT,
    }
)

QURAN_CAPABILITIES = frozenset(
    {
        CAPABILITY_QURAN,
        CAPABILITY_PARENT,
        CAPABILITY_MAJLIS,
        CAPABILITY_ANALYTICS,
        CAPABILITY_ANNOUNCEMENT,
    }
)


_RUMAH_QURAN_BLOCKED_ADMIN_ENDPOINTS = {
    "admin.manage_academic_years",
    "admin.activate_academic_year",
    "admin.manage_subjects",
    "admin.edit_subject",
    "admin.manage_extracurriculars",
}

_SEKOLAH_ONLY_BLOCKED_ENDPOINTS = {
    "main.majlis_dashboard",
    "parent.join_majlis",
    "parent.majlis_dashboard",
    "parent.majlis_activities",
}


def normalize_tenant_package(raw_value):
    value = (raw_value or "").strip().lower()
    if value in PACKAGE_OPTIONS:
        return value
    return PACKAGE_FULL


def get_tenant_package(tenant_id):
    if tenant_id is None:
        return PACKAGE_FULL
    row = AppConfig.query.filter_by(
        tenant_id=tenant_id,
        key=TENANT_PACKAGE_KEY,
        is_deleted=False,
    ).first()
    return normalize_tenant_package(row.value if row else PACKAGE_FULL)


def capabilities_for_package(package):
    package = normalize_tenant_package(package)
    if package == PACKAGE_FULL:
        return ALL_CAPABILITIES
    if package == PACKAGE_SEKOLAH:
        return SCHOOL_CAPABILITIES
    if package == PACKAGE_RUMAH_QURAN:
        return QURAN_CAPABILITIES
    return frozenset()


def tenant_has_capability(tenant_id, capability):
    if not capability:
        return True
    if tenant_id is None:
        return False
    package = get_tenant_package(tenant_id)
    return capability in capabilities_for_package(package)


def role_allowed_for_package(role, package):
    if role is None:
        return True
    package = normalize_tenant_package(package)
    if package == PACKAGE_FULL:
        return True
    if role == UserRole.SUPER_ADMIN:
        return True
    if package == PACKAGE_SEKOLAH:
        return role in {
            UserRole.ADMIN,
            UserRole.PIMPINAN,
            UserRole.TU,
            UserRole.GURU,
            UserRole.SISWA,
            UserRole.WALI_MURID,
        }
    if package == PACKAGE_RUMAH_QURAN:
        return role in {
            UserRole.ADMIN,
            UserRole.PIMPINAN,
            UserRole.TU,
            UserRole.WALI_MURID,
            UserRole.MAJLIS_PARTICIPANT,
        }
    return True


def endpoint_allowed_for_package(endpoint, package):
    if not endpoint:
        return True

    package = normalize_tenant_package(package)
    if package == PACKAGE_FULL:
        return True

    if endpoint.startswith(("static", "auth.", "api.")):
        return True

    if package == PACKAGE_SEKOLAH:
        if endpoint.startswith("staff."):
            return False
        if endpoint.startswith("boarding."):
            return False
        if endpoint in _SEKOLAH_ONLY_BLOCKED_ENDPOINTS:
            return False
        return True

    if package == PACKAGE_RUMAH_QURAN:
        if endpoint.startswith(("teacher.", "student.", "boarding.")):
            return False
        if endpoint == "parent.dashboard":
            return False
        if endpoint in _RUMAH_QURAN_BLOCKED_ADMIN_ENDPOINTS:
            return False
        return True

    return True

