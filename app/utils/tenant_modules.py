from app.models import AppConfig, UserRole


TENANT_PACKAGE_KEY = "tenant.module_package"

PACKAGE_FULL = "full"
PACKAGE_RUMAH_QURAN = "rumah_quran"
PACKAGE_SEKOLAH = "sekolah"
PACKAGE_OPTIONS = (PACKAGE_FULL, PACKAGE_RUMAH_QURAN, PACKAGE_SEKOLAH)


_RUMAH_QURAN_BLOCKED_ADMIN_ENDPOINTS = {
    "admin.manage_academic_years",
    "admin.activate_academic_year",
    "admin.manage_classes",
    "admin.edit_class",
    "admin.delete_class",
    "admin.manage_subjects",
    "admin.edit_subject",
    "admin.manage_schedules",
    "admin.edit_schedule",
    "admin.delete_schedule",
    "admin.manage_teachers",
    "admin.edit_teacher",
    "admin.delete_teacher",
    "admin.teacher_assignments",
    "admin.upload_teachers",
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
            UserRole.GURU,
            UserRole.SISWA,
            UserRole.WALI_MURID,
            UserRole.WALI_ASRAMA,
        }
    if package == PACKAGE_RUMAH_QURAN:
        return role in {
            UserRole.ADMIN,
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

