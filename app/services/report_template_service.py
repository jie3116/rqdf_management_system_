from app.models import AppConfig, Tenant


REPORT_TEMPLATE_PROFILE_KEY = "report_template_profile"
REPORT_MUDIR_NAME_KEY = "report_mudir_name"
GENERIC_REPORT_PROFILE = "generic"
RQDF_REPORT_PROFILE = "rqdf"
SUPPORTED_REPORT_PROFILES = {
    GENERIC_REPORT_PROFILE,
    RQDF_REPORT_PROFILE,
}


def resolve_report_template_profile(tenant_id):
    if tenant_id is None:
        return GENERIC_REPORT_PROFILE

    configured_profile = (
        AppConfig.query.filter(
            AppConfig.tenant_id == tenant_id,
            AppConfig.key == REPORT_TEMPLATE_PROFILE_KEY,
            AppConfig.is_deleted.is_(False),
        )
        .with_entities(AppConfig.value)
        .scalar()
    )
    normalized_profile = (configured_profile or "").strip().lower()
    if normalized_profile in SUPPORTED_REPORT_PROFILES:
        return normalized_profile

    tenant = Tenant.query.filter_by(id=tenant_id, is_deleted=False).first()
    if tenant and (tenant.name or "").strip().upper() == "RQDF" and (tenant.code or "").strip().upper() == "DEFAULT":
        return RQDF_REPORT_PROFILE
    return GENERIC_REPORT_PROFILE


def report_template_for(profile, report_type):
    normalized_profile = profile if profile in SUPPORTED_REPORT_PROFILES else GENERIC_REPORT_PROFILE
    templates = {
        GENERIC_REPORT_PROFILE: {
            "formal": "teacher/print_report_formal.html",
            "tahfidz": "teacher/print_report_tahfidz.html",
            "bahasa": "teacher/print_report_bahasa.html",
            "lampiran": "teacher/print_report_lampiran.html",
        },
        RQDF_REPORT_PROFILE: {
            "formal": "teacher/print_report_formal_rqdf.html",
            "tahfidz": "teacher/print_report_tahfidz_rqdf.html",
            "bahasa": "teacher/print_report_bahasa.html",
            "lampiran": "teacher/print_report_lampiran.html",
        },
    }
    return templates[normalized_profile].get(report_type, templates[GENERIC_REPORT_PROFILE][report_type])


def resolve_report_mudir_name(tenant_id, profile=None):
    if tenant_id is None:
        return "-"
    configured_name = (
        AppConfig.query.filter(
            AppConfig.tenant_id == tenant_id,
            AppConfig.key == REPORT_MUDIR_NAME_KEY,
            AppConfig.is_deleted.is_(False),
        )
        .with_entities(AppConfig.value)
        .scalar()
    )
    if (configured_name or "").strip():
        return configured_name.strip()
    if (profile or resolve_report_template_profile(tenant_id)) == RQDF_REPORT_PROFILE:
        return "Cecep Jamaludin, Lc., M.Pd."
    return "-"
