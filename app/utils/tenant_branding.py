from flask import request, url_for
from flask_login import current_user

from app.models import AppConfig, Tenant, TenantStatus
from app.utils.tenant import get_default_tenant


BRAND_NAME_KEY = "institution_name"
BRAND_LOGO_KEY = "institution_logo"
BRAND_ADDRESS_KEY = "institution_address"
BRAND_PHONE_KEY = "institution_phone"
BRAND_DOMAIN_KEY = "tenant_domain"
DEFAULT_BRAND_NAME = "RQDF Management System"
DEFAULT_LOGO_STATIC = "img/logo-rqdf-white.png"


def _clean_host(host):
    return (host or "").split(":", 1)[0].strip().lower()


def get_tenant_config_map(tenant_id, keys=None):
    if tenant_id is None:
        return {}
    query = AppConfig.query.filter(
        AppConfig.tenant_id == tenant_id,
        AppConfig.is_deleted.is_(False),
    )
    if keys:
        query = query.filter(AppConfig.key.in_(keys))
    return {row.key: (row.value or "").strip() for row in query.all()}


def resolve_tenant_from_request():
    if current_user.is_authenticated and getattr(current_user, "tenant_id", None):
        return current_user.tenant

    tenant_hint = (request.args.get("tenant") or "").strip()
    if tenant_hint:
        tenant = Tenant.query.filter(
            Tenant.is_deleted.is_(False),
            Tenant.status == TenantStatus.ACTIVE,
            (Tenant.code == tenant_hint) | (Tenant.slug == tenant_hint),
        ).first()
        if tenant:
            return tenant

    host = _clean_host(request.host)
    if host:
        domain_rows = AppConfig.query.filter(
            AppConfig.key == BRAND_DOMAIN_KEY,
            AppConfig.is_deleted.is_(False),
        ).all()
        for row in domain_rows:
            domains = [
                _clean_host(item)
                for item in (row.value or "").replace("\n", ",").split(",")
                if item.strip()
            ]
            if host in domains:
                tenant = Tenant.query.filter_by(id=row.tenant_id, is_deleted=False).first()
                if tenant and tenant.status == TenantStatus.ACTIVE:
                    return tenant

    return get_default_tenant()


def build_tenant_brand(tenant=None):
    tenant = tenant or resolve_tenant_from_request()
    if not tenant:
        return {
            "tenant": None,
            "name": DEFAULT_BRAND_NAME,
            "logo_static": DEFAULT_LOGO_STATIC,
            "logo_url": url_for("static", filename=DEFAULT_LOGO_STATIC),
            "address": "",
            "phone": "",
            "domain": "",
        }

    config = get_tenant_config_map(
        tenant.id,
        [BRAND_NAME_KEY, BRAND_LOGO_KEY, BRAND_ADDRESS_KEY, BRAND_PHONE_KEY, BRAND_DOMAIN_KEY],
    )
    logo_static = config.get(BRAND_LOGO_KEY) or DEFAULT_LOGO_STATIC
    return {
        "tenant": tenant,
        "name": config.get(BRAND_NAME_KEY) or tenant.name or DEFAULT_BRAND_NAME,
        "logo_static": logo_static,
        "logo_url": url_for("static", filename=logo_static),
        "address": config.get(BRAND_ADDRESS_KEY) or "",
        "phone": config.get(BRAND_PHONE_KEY) or "",
        "domain": config.get(BRAND_DOMAIN_KEY) or "",
    }
