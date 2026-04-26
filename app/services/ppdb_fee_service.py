import json

from app.extensions import db
from app.models import AppConfig, FeeType, ProgramType, ScholarshipCategory
from app.utils.money import to_rupiah_int
from app.utils.tenant import get_default_tenant_id


PPDB_FEE_TEMPLATE_DEFINITIONS = [
    {
        "key": "ppdb_fee_template.formal_non_beasiswa",
        "input_name": "ppdb_formal_non_beasiswa",
        "label": "Formal - Non Beasiswa",
        "help_text": "Satu baris satu nama biaya. Nama harus sama dengan Master Biaya.",
        "default_items": [
            "Biaya Pendaftaran",
            "Seragam Batik",
            "Infaq Bulanan (Juli)",
            "Wakaf Bangunan",
            "Fasilitas Kasur",
            "Orientasi Siswa",
            "Wakaf Perpustakaan",
            "Infaq Qurban",
            "Raport Pesantren",
            "Adm Sekolah Formal",
            "Infaq Kegiatan",
        ],
    },
    {
        "key": "ppdb_fee_template.formal_beasiswa",
        "input_name": "ppdb_formal_beasiswa",
        "label": "Formal - Beasiswa",
        "help_text": "Satu baris satu nama biaya. Nama harus sama dengan Master Biaya.",
        "default_items": [
            "Biaya Pendaftaran (Beasiswa)",
            "Infaq Bulanan (Beasiswa)",
            "Wakaf Bangunan (Beasiswa)",
            "Fasilitas Lemari (Beasiswa)",
            "Fasilitas Kasur (Beasiswa)",
            "Orientasi Siswa (Beasiswa)",
            "Raport",
            "Wakaf Perpustakaan (Beasiswa)",
            "Infaq Kegiatan (Beasiswa)",
            "Infaq Qurban (Beasiswa)",
            "Seragam Batik",
            "Adm Sekolah Formal",
        ],
    },
    {
        "key": "ppdb_fee_template.rqdf_sore",
        "input_name": "ppdb_rqdf_sore",
        "label": "Rumah Qur'an - Reguler",
        "help_text": "Satu baris satu nama biaya. Infaq pembangunan & seragam ukuran ditambahkan otomatis.",
        "default_items": [
            "Infaq Pendaftaran (RQDF)",
            "Uang Dana Semesteran",
            "Infaq Bulanan RQDF",
            "Atribut (Syal) & Buku",
            "Raport RQDF",
        ],
    },
    {
        "key": "ppdb_fee_template.takhosus_tahfidz",
        "input_name": "ppdb_takhosus_tahfidz",
        "label": "Rumah Qur'an - Takhosus Tahfidz",
        "help_text": "Satu baris satu nama biaya. Infaq pembangunan & seragam ukuran ditambahkan otomatis.",
        "default_items": [
            "Infaq Pendaftaran (RQDF)",
            "Uang Dana Semesteran",
            "Infaq Bulanan RQDF",
            "Atribut (Syal) & Buku",
            "Raport RQDF",
        ],
    },
]


DEFAULT_FEE_AMOUNTS = {
    "Biaya Pendaftaran": 200000,
    "Seragam Batik": 100000,
    "Infaq Bulanan (Juli)": 650000,
    "Wakaf Bangunan": 1000000,
    "Fasilitas Kasur": 500000,
    "Orientasi Siswa": 150000,
    "Wakaf Perpustakaan": 100000,
    "Infaq Qurban": 100000,
    "Raport Pesantren": 65000,
    "Adm Sekolah Formal": 500000,
    "Infaq Kegiatan": 100000,
    "Biaya Pendaftaran (Beasiswa)": 100000,
    "Infaq Bulanan (Beasiswa)": 325000,
    "Wakaf Bangunan (Beasiswa)": 500000,
    "Fasilitas Lemari (Beasiswa)": 250000,
    "Fasilitas Kasur (Beasiswa)": 250000,
    "Orientasi Siswa (Beasiswa)": 75000,
    "Raport": 65000,
    "Wakaf Perpustakaan (Beasiswa)": 50000,
    "Infaq Kegiatan (Beasiswa)": 50000,
    "Infaq Qurban (Beasiswa)": 50000,
    "Infaq Pendaftaran (RQDF)": 300000,
    "Uang Dana Semesteran": 50000,
    "Infaq Bulanan RQDF": 150000,
    "Atribut (Syal) & Buku": 100000,
    "Raport RQDF": 50000,
    "Seragam RQDF (S/M)": 345000,
    "Seragam RQDF (L/XL)": 355000,
    "Seragam RQDF (XXL)": 380000,
}


def _definition_map():
    return {item["key"]: item for item in PPDB_FEE_TEMPLATE_DEFINITIONS}


def _resolve_tenant_id(tenant_id=None):
    return tenant_id or get_default_tenant_id()


def _split_fee_names(raw_value):
    if not raw_value:
        return []
    lines = str(raw_value).replace(",", "\n").splitlines()
    names = []
    seen = set()
    for line in lines:
        name = line.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def _parse_template_value(raw_value, fallback_names):
    if raw_value is None:
        return list(fallback_names)
    try:
        loaded = json.loads(raw_value)
    except (TypeError, ValueError):
        return _split_fee_names(raw_value) or list(fallback_names)

    if isinstance(loaded, list):
        parsed = []
        seen = set()
        for item in loaded:
            name = str(item).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            parsed.append(name)
        return parsed
    return list(fallback_names)


def _template_names_by_key(config_key, tenant_id=None):
    definition = _definition_map().get(config_key)
    if definition is None:
        return []
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    if resolved_tenant_id is None:
        return list(definition["default_items"])

    config = AppConfig.query.filter_by(
        tenant_id=resolved_tenant_id,
        key=config_key,
        is_deleted=False,
    ).first()
    raw_value = config.value if config else None
    return _parse_template_value(raw_value, definition["default_items"])


def _fee_rows_from_template(config_key, tenant_id=None):
    return [
        {"item": name, "harga": _fee_nominal(name, tenant_id=tenant_id)}
        for name in _template_names_by_key(config_key, tenant_id=tenant_id)
    ]


def _program_template_key(program_type, scholarship_category):
    if program_type == ProgramType.SEKOLAH_FULLDAY:
        if scholarship_category in (None, ScholarshipCategory.NON_BEASISWA):
            return "ppdb_fee_template.formal_non_beasiswa"
        return "ppdb_fee_template.formal_beasiswa"
    if program_type == ProgramType.RQDF_SORE:
        return "ppdb_fee_template.rqdf_sore"
    if program_type == ProgramType.TAKHOSUS_TAHFIDZ:
        return "ppdb_fee_template.takhosus_tahfidz"
    return None


def _fee_nominal(name, tenant_id=None):
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    fee_type_query = FeeType.query.filter_by(name=name)
    if resolved_tenant_id is not None:
        fee_type_query = fee_type_query.filter(FeeType.tenant_id == resolved_tenant_id)
    fee_type = fee_type_query.order_by(FeeType.id.desc()).first()
    if fee_type:
        return to_rupiah_int(fee_type.amount)
    return to_rupiah_int(DEFAULT_FEE_AMOUNTS.get(name, 0))


def build_candidate_fee_drafts(candidate, tenant_id=None):
    if candidate is None or not candidate.program_type:
        return []

    resolved_tenant_id = _resolve_tenant_id(tenant_id or getattr(candidate, "tenant_id", None))
    template_key = _program_template_key(candidate.program_type, candidate.scholarship_category)
    if template_key is None:
        return []

    drafts = [
        {"nama": name, "nominal": _fee_nominal(name, tenant_id=resolved_tenant_id)}
        for name in _template_names_by_key(template_key, tenant_id=resolved_tenant_id)
    ]

    if candidate.program_type in (ProgramType.RQDF_SORE, ProgramType.TAKHOSUS_TAHFIDZ):
        if candidate.initial_pledge_amount and candidate.initial_pledge_amount > 0:
            drafts.append(
                {"nama": "Infaq Pembangunan Pesantren", "nominal": to_rupiah_int(candidate.initial_pledge_amount)}
            )

        uniform_size = candidate.uniform_size.name if candidate.uniform_size else ""
        if uniform_size in ("S", "M"):
            uniform_fee_name = "Seragam RQDF (S/M)"
        elif uniform_size in ("L", "XL"):
            uniform_fee_name = "Seragam RQDF (L/XL)"
        elif uniform_size == "XXL":
            uniform_fee_name = "Seragam RQDF (XXL)"
        else:
            uniform_fee_name = None

        if uniform_fee_name:
            uniform_amount = _fee_nominal(uniform_fee_name, tenant_id=resolved_tenant_id)
            if uniform_amount > 0:
                drafts.append({"nama": f"Seragam RQDF (Ukuran {uniform_size})", "nominal": uniform_amount})

    return drafts


def get_ppdb_fee_template_admin_fields(tenant_id=None):
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    fields = []
    for definition in PPDB_FEE_TEMPLATE_DEFINITIONS:
        names = _template_names_by_key(definition["key"], tenant_id=resolved_tenant_id)
        fields.append(
            {
                "key": definition["key"],
                "input_name": definition["input_name"],
                "label": definition["label"],
                "help_text": definition["help_text"],
                "value_text": "\n".join(names),
            }
        )
    return fields


def save_ppdb_fee_templates(form_data, tenant_id=None):
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    if resolved_tenant_id is None:
        return 0

    changed = 0
    for definition in PPDB_FEE_TEMPLATE_DEFINITIONS:
        input_name = definition["input_name"]
        raw_value = form_data.get(input_name, "")
        names = _split_fee_names(raw_value)
        value = json.dumps(names, ensure_ascii=False)
        config = AppConfig.query.filter_by(
            tenant_id=resolved_tenant_id,
            key=definition["key"],
            is_deleted=False,
        ).first()
        if config is None:
            config = AppConfig(
                tenant_id=resolved_tenant_id,
                key=definition["key"],
                value=value,
                description=f"Template komponen biaya PPDB - {definition['label']}",
            )
            db.session.add(config)
            changed += 1
            continue
        if config.value != value:
            config.value = value
            changed += 1
        if not config.description:
            config.description = f"Template komponen biaya PPDB - {definition['label']}"
    return changed


def get_public_ppdb_fee_preview(tenant_id=None):
    resolved_tenant_id = _resolve_tenant_id(tenant_id)
    return {
        "formal_non_beasiswa": _fee_rows_from_template(
            "ppdb_fee_template.formal_non_beasiswa",
            tenant_id=resolved_tenant_id,
        ),
        "formal_beasiswa": _fee_rows_from_template(
            "ppdb_fee_template.formal_beasiswa",
            tenant_id=resolved_tenant_id,
        ),
        "rqdf_sore_base": _fee_rows_from_template(
            "ppdb_fee_template.rqdf_sore",
            tenant_id=resolved_tenant_id,
        ),
        "takhosus_tahfidz": _fee_rows_from_template(
            "ppdb_fee_template.takhosus_tahfidz",
            tenant_id=resolved_tenant_id,
        ),
        "uniform_prices": {
            "S": _fee_nominal("Seragam RQDF (S/M)", tenant_id=resolved_tenant_id),
            "M": _fee_nominal("Seragam RQDF (S/M)", tenant_id=resolved_tenant_id),
            "L": _fee_nominal("Seragam RQDF (L/XL)", tenant_id=resolved_tenant_id),
            "XL": _fee_nominal("Seragam RQDF (L/XL)", tenant_id=resolved_tenant_id),
            "XXL": _fee_nominal("Seragam RQDF (XXL)", tenant_id=resolved_tenant_id),
        },
        "pledge_item_name": "Infaq Pembangunan Pesantren",
        "uniform_item_label_prefix": "Seragam RQDF (Ukuran",
    }
