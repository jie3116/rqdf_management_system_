from datetime import date
import json

from sqlalchemy import or_

from app.extensions import db
from app.models import (
    EducationLevel,
    PpdbDocumentRequirement,
    PpdbFeeItem,
    PpdbFormField,
    PpdbFormSection,
    PpdbPath,
    PpdbPeriod,
    PpdbPeriodStatus,
    ProgramType,
    ScholarshipCategory,
    TenantProgram,
)
from app.utils.programs import system_program_label
from app.utils.timezone import local_today


DEFAULT_PPDB_PATHS = (
    {
        "code": "SBQ-REG",
        "name": "Sekolah Bina Qur'an - Reguler",
        "program_type": ProgramType.SEKOLAH_FULLDAY,
        "education_level": None,
        "scholarship_category": ScholarshipCategory.NON_BEASISWA,
        "sort_order": 10,
    },
    {
        "code": "SBQ-BEA",
        "name": "Sekolah Bina Qur'an - Beasiswa",
        "program_type": ProgramType.SEKOLAH_FULLDAY,
        "education_level": None,
        "scholarship_category": None,
        "sort_order": 20,
    },
    {
        "code": "RQDF",
        "name": "Kelas Reguler RQDF",
        "program_type": ProgramType.RQDF_SORE,
        "education_level": EducationLevel.NON_FORMAL,
        "scholarship_category": ScholarshipCategory.NON_BEASISWA,
        "sort_order": 30,
    },
    {
        "code": "TAKHOSUS",
        "name": "Takhosus Tahfidz",
        "program_type": ProgramType.TAKHOSUS_TAHFIDZ,
        "education_level": EducationLevel.NON_FORMAL,
        "scholarship_category": ScholarshipCategory.NON_BEASISWA,
        "sort_order": 40,
    },
    {
        "code": "MAJLIS",
        "name": "Majelis Ta'lim",
        "program_type": ProgramType.MAJLIS_TALIM,
        "education_level": EducationLevel.NON_FORMAL,
        "scholarship_category": ScholarshipCategory.NON_BEASISWA,
        "sort_order": 50,
    },
)

DEFAULT_TENANT_PROGRAMS = (
    {
        "code": "SEKOLAH_FULLDAY",
        "name": "Sekolah Formal",
        "system_type": ProgramType.SEKOLAH_FULLDAY,
        "education_level": None,
        "category": "FORMAL",
        "sort_order": 10,
    },
    {
        "code": "RQDF_SORE",
        "name": "Rumah Qur'an",
        "system_type": ProgramType.RQDF_SORE,
        "education_level": EducationLevel.NON_FORMAL,
        "category": "NON_FORMAL",
        "sort_order": 20,
    },
    {
        "code": "TAKHOSUS_TAHFIDZ",
        "name": "Takhosus Tahfidz",
        "system_type": ProgramType.TAKHOSUS_TAHFIDZ,
        "education_level": EducationLevel.NON_FORMAL,
        "category": "NON_FORMAL",
        "sort_order": 30,
    },
    {
        "code": "MAJLIS_TALIM",
        "name": "Majelis Ta'lim",
        "system_type": ProgramType.MAJLIS_TALIM,
        "education_level": EducationLevel.NON_FORMAL,
        "category": "MAJLIS",
        "sort_order": 40,
    },
    {
        "code": "BAHASA",
        "name": "Program Bahasa",
        "system_type": ProgramType.BAHASA,
        "education_level": EducationLevel.NON_FORMAL,
        "category": "NON_FORMAL",
        "sort_order": 50,
    },
)


def list_active_tenant_programs(tenant_id):
    if tenant_id is None:
        return []
    return (
        TenantProgram.query.filter_by(
            tenant_id=tenant_id,
            is_active=True,
            is_deleted=False,
        )
        .order_by(TenantProgram.sort_order.asc(), TenantProgram.name.asc())
        .all()
    )


def get_or_create_tenant_program(tenant_id, code, name, system_type, education_level=None, category=None, sort_order=0):
    if tenant_id is None:
        return None
    normalized_code = (code or "").strip().upper()
    program = TenantProgram.query.filter_by(
        tenant_id=tenant_id,
        code=normalized_code,
        is_deleted=False,
    ).first()
    if program:
        return program
    program = TenantProgram(
        tenant_id=tenant_id,
        code=normalized_code,
        name=name,
        system_type=system_type,
        education_level=education_level,
        category=category,
        sort_order=sort_order,
        is_active=True,
    )
    db.session.add(program)
    db.session.flush()
    return program


def seed_default_tenant_programs(tenant_id):
    created = 0
    for item in DEFAULT_TENANT_PROGRAMS:
        before = TenantProgram.query.filter_by(
            tenant_id=tenant_id,
            code=item["code"],
            is_deleted=False,
        ).first()
        get_or_create_tenant_program(
            tenant_id=tenant_id,
            code=item["code"],
            name=item["name"],
            system_type=item["system_type"],
            education_level=item["education_level"],
            category=item["category"],
            sort_order=item["sort_order"],
        )
        if before is None:
            created += 1
    return created


def get_active_ppdb_period(tenant_id, today=None):
    if tenant_id is None:
        return None

    today = today or local_today()
    return (
        PpdbPeriod.query.filter(
            PpdbPeriod.tenant_id == tenant_id,
            PpdbPeriod.status == PpdbPeriodStatus.OPEN,
            PpdbPeriod.public_registration_enabled.is_(True),
            PpdbPeriod.start_date <= today,
            PpdbPeriod.end_date >= today,
        )
        .order_by(PpdbPeriod.start_date.desc(), PpdbPeriod.id.desc())
        .first()
    )


def list_active_ppdb_paths(tenant_id, period=None):
    if tenant_id is None or period is None:
        return []

    return (
        PpdbPath.query.filter_by(
            tenant_id=tenant_id,
            period_id=period.id,
            is_active=True,
            is_deleted=False,
        )
        .order_by(PpdbPath.sort_order.asc(), PpdbPath.name.asc())
        .all()
    )


def list_active_ppdb_form_fields(tenant_id, period=None, path=None):
    if tenant_id is None or period is None:
        return []

    query = PpdbFormField.query.filter(
        PpdbFormField.tenant_id == tenant_id,
        PpdbFormField.period_id == period.id,
        PpdbFormField.is_active.is_(True),
        PpdbFormField.is_deleted.is_(False),
    )
    if path is None:
        query = query.filter(PpdbFormField.path_id.is_(None))
    else:
        query = query.filter(or_(PpdbFormField.path_id.is_(None), PpdbFormField.path_id == path.id))

    return query.order_by(
        PpdbFormField.section_id.asc().nullsfirst(),
        PpdbFormField.sort_order.asc(),
        PpdbFormField.label.asc(),
    ).all()


def list_active_ppdb_form_sections(tenant_id, period=None, path=None):
    if tenant_id is None or period is None or path is None:
        return []
    return (
        PpdbFormSection.query.filter(
            PpdbFormSection.tenant_id == tenant_id,
            PpdbFormSection.period_id == period.id,
            PpdbFormSection.path_id == path.id,
            PpdbFormSection.is_active.is_(True),
            PpdbFormSection.is_deleted.is_(False),
        )
        .order_by(PpdbFormSection.sort_order.asc(), PpdbFormSection.title.asc())
        .all()
    )


def list_configured_ppdb_form_sections(tenant_id, period=None):
    if tenant_id is None or period is None:
        return []
    return (
        PpdbFormSection.query.filter(
            PpdbFormSection.tenant_id == tenant_id,
            PpdbFormSection.period_id == period.id,
            PpdbFormSection.is_deleted.is_(False),
        )
        .order_by(PpdbFormSection.path_id.asc(), PpdbFormSection.sort_order.asc(), PpdbFormSection.title.asc())
        .all()
    )


def list_configured_ppdb_form_fields(tenant_id, period=None):
    if tenant_id is None or period is None:
        return []
    return (
        PpdbFormField.query.filter(
            PpdbFormField.tenant_id == tenant_id,
            PpdbFormField.period_id == period.id,
            PpdbFormField.is_deleted.is_(False),
        )
        .order_by(PpdbFormField.sort_order.asc(), PpdbFormField.label.asc())
        .all()
    )


def list_active_ppdb_document_requirements(tenant_id, period=None, path=None):
    if tenant_id is None or period is None:
        return []

    query = PpdbDocumentRequirement.query.filter(
        PpdbDocumentRequirement.tenant_id == tenant_id,
        PpdbDocumentRequirement.period_id == period.id,
        PpdbDocumentRequirement.is_active.is_(True),
        PpdbDocumentRequirement.is_deleted.is_(False),
    )
    if path is None:
        query = query.filter(PpdbDocumentRequirement.path_id.is_(None))
    else:
        query = query.filter(
            or_(PpdbDocumentRequirement.path_id.is_(None), PpdbDocumentRequirement.path_id == path.id)
        )

    return query.order_by(
        PpdbDocumentRequirement.sort_order.asc(),
        PpdbDocumentRequirement.name.asc(),
    ).all()


def list_configured_ppdb_document_requirements(tenant_id, period=None):
    if tenant_id is None or period is None:
        return []
    return (
        PpdbDocumentRequirement.query.filter(
            PpdbDocumentRequirement.tenant_id == tenant_id,
            PpdbDocumentRequirement.period_id == period.id,
            PpdbDocumentRequirement.is_deleted.is_(False),
        )
        .order_by(PpdbDocumentRequirement.sort_order.asc(), PpdbDocumentRequirement.name.asc())
        .all()
    )


def list_active_ppdb_fee_items(tenant_id, period=None, path=None):
    if tenant_id is None or period is None or path is None:
        return []
    return (
        PpdbFeeItem.query.filter(
            PpdbFeeItem.tenant_id == tenant_id,
            PpdbFeeItem.period_id == period.id,
            PpdbFeeItem.path_id == path.id,
            PpdbFeeItem.is_active.is_(True),
            PpdbFeeItem.is_deleted.is_(False),
        )
        .order_by(PpdbFeeItem.sort_order.asc(), PpdbFeeItem.name.asc())
        .all()
    )


def ppdb_fee_preview_by_path(tenant_id, period=None):
    if tenant_id is None or period is None:
        return {}
    rows = (
        PpdbFeeItem.query.filter(
            PpdbFeeItem.tenant_id == tenant_id,
            PpdbFeeItem.period_id == period.id,
            PpdbFeeItem.is_active.is_(True),
            PpdbFeeItem.is_deleted.is_(False),
        )
        .order_by(PpdbFeeItem.sort_order.asc(), PpdbFeeItem.name.asc())
        .all()
    )
    preview = {}
    for row in rows:
        preview.setdefault(str(row.path_id), []).append(
            {
                "item": row.name,
                "harga": int(row.amount or 0),
            }
        )
    return preview


def ppdb_field_options(field):
    if not field or not field.options_json:
        return []
    try:
        parsed = json.loads(field.options_json)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item).strip() for item in parsed if str(item).strip()]


def find_matching_ppdb_path(tenant_id, period, program_type, education_level=None, scholarship_category=None):
    if tenant_id is None or period is None or program_type is None:
        return None

    query = PpdbPath.query.filter(
        PpdbPath.tenant_id == tenant_id,
        PpdbPath.period_id == period.id,
        PpdbPath.program_type == program_type,
        PpdbPath.is_active.is_(True),
        PpdbPath.is_deleted.is_(False),
        or_(PpdbPath.education_level.is_(None), PpdbPath.education_level == education_level),
        or_(PpdbPath.scholarship_category.is_(None), PpdbPath.scholarship_category == scholarship_category),
    )
    return query.order_by(PpdbPath.sort_order.asc(), PpdbPath.id.asc()).first()


def seed_default_ppdb_paths(tenant_id, period):
    if tenant_id is None or period is None:
        return 0

    seed_default_tenant_programs(tenant_id)
    existing_codes = {
        row.code
        for row in PpdbPath.query.filter_by(
            tenant_id=tenant_id,
            period_id=period.id,
            is_deleted=False,
        ).all()
    }
    created = 0
    for item in DEFAULT_PPDB_PATHS:
        if item["code"] in existing_codes:
            continue
        tenant_program = get_or_create_tenant_program(
            tenant_id=tenant_id,
            code=item["program_type"].name,
            name=system_program_label(item["program_type"]),
            system_type=item["program_type"],
            education_level=item["education_level"],
            category="PPDB",
            sort_order=item["sort_order"],
        )
        db.session.add(
            PpdbPath(
                tenant_id=tenant_id,
                period_id=period.id,
                tenant_program_id=tenant_program.id if tenant_program else None,
                code=item["code"],
                name=item["name"],
                program_type=item["program_type"],
                education_level=item["education_level"],
                scholarship_category=item["scholarship_category"],
                sort_order=item["sort_order"],
                is_active=True,
            )
        )
        created += 1
    return created


def create_default_ppdb_period(tenant_id):
    today = local_today()
    start = date(today.year, 1, 1)
    end = date(today.year, 12, 31)
    period = PpdbPeriod(
        tenant_id=tenant_id,
        name=f"PPDB {today.year}",
        academic_year_label=f"{today.year}/{today.year + 1}",
        start_date=start,
        end_date=end,
        status=PpdbPeriodStatus.OPEN,
        registration_no_prefix="REG",
        public_registration_enabled=True,
    )
    db.session.add(period)
    db.session.flush()
    seed_default_ppdb_paths(tenant_id, period)
    return period
