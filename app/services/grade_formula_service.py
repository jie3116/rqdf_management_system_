import json

from flask import current_app

from app.models import AppConfig, ReportScoreAdjustment


GRADE_FORMULA_CONFIG_KEY = "grade_formula_weights"
DEFAULT_GRADE_WEIGHTS = {
    "TUGAS": 30.0,
    "UH": 20.0,
    "UTS": 25.0,
    "UAS": 25.0,
}
REPORT_ADJUSTMENT_STATUS_ACTIVE = "ACTIVE"
REPORT_ADJUSTMENT_STATUS_VOID = "VOID"
REPORT_ADJUSTMENT_SOURCE_ACADEMIC = "ACADEMIC"
REPORT_ADJUSTMENT_SOURCE_TAHFIDZ = "TAHFIDZ"
REPORT_ADJUSTMENT_SOURCE_TAHFIDZ_EVALUATION = "TAHFIDZ_EVALUATION"


def normalize_report_adjustment_source(source_type):
    normalized = (source_type or REPORT_ADJUSTMENT_SOURCE_ACADEMIC).strip().upper()
    normalized = normalized.replace(" ", "_")
    aliases = {
        "AKADEMIK": REPORT_ADJUSTMENT_SOURCE_ACADEMIC,
        "ACADEMIC": REPORT_ADJUSTMENT_SOURCE_ACADEMIC,
        "TAHFIDZ": REPORT_ADJUSTMENT_SOURCE_TAHFIDZ,
        "EVALUASI_TAHFIDZ": REPORT_ADJUSTMENT_SOURCE_TAHFIDZ_EVALUATION,
        "TAHFIDZ_EVALUASI": REPORT_ADJUSTMENT_SOURCE_TAHFIDZ_EVALUATION,
        "TAHFIDZ_EVALUATION": REPORT_ADJUSTMENT_SOURCE_TAHFIDZ_EVALUATION,
    }
    normalized = aliases.get(normalized, normalized)
    allowed = {
        REPORT_ADJUSTMENT_SOURCE_ACADEMIC,
        REPORT_ADJUSTMENT_SOURCE_TAHFIDZ,
        REPORT_ADJUSTMENT_SOURCE_TAHFIDZ_EVALUATION,
    }
    return normalized if normalized in allowed else None


def calculate_weighted_final(
    type_averages,
    tenant_id=None,
    academic_year_id=None,
    subject_id=None,
    student_id=None,
    class_id=None,
):
    detail = calculate_report_final_detail(
        type_averages,
        tenant_id=tenant_id,
        academic_year_id=academic_year_id,
        subject_id=subject_id,
        student_id=student_id,
        class_id=class_id,
    )
    return detail["final_score"]


def calculate_report_final_detail(
    type_averages,
    tenant_id=None,
    academic_year_id=None,
    subject_id=None,
    student_id=None,
    class_id=None,
):
    weights = resolve_grade_weights(
        tenant_id=tenant_id,
        academic_year_id=academic_year_id,
        subject_id=subject_id,
    )
    total_weighted = 0.0
    total_weight = 0.0

    for type_name, average in (type_averages or {}).items():
        weight = float(weights.get(str(type_name).upper(), 0))
        if weight <= 0:
            continue
        total_weighted += float(average or 0) * weight
        total_weight += weight

    if total_weight <= 0:
        original_score = 0
    else:
        original_score = round(total_weighted / total_weight, 2)

    adjustment = resolve_report_score_adjustment(
        tenant_id=tenant_id,
        student_id=student_id,
        academic_year_id=academic_year_id,
        subject_id=subject_id,
        class_id=class_id,
        source_type=REPORT_ADJUSTMENT_SOURCE_ACADEMIC,
    )
    if not adjustment:
        return {
            "final_score": original_score,
            "original_score": original_score,
            "is_adjusted": False,
            "adjustment": None,
        }

    adjusted_score = round(float(adjustment.adjusted_score or 0), 2)
    return {
        "final_score": adjusted_score,
        "original_score": round(float(adjustment.original_score or original_score), 2),
        "is_adjusted": True,
        "adjustment": adjustment,
    }


def resolve_report_score_adjustment(
    tenant_id=None,
    student_id=None,
    academic_year_id=None,
    subject_id=None,
    class_id=None,
    source_type=REPORT_ADJUSTMENT_SOURCE_ACADEMIC,
):
    source_type = normalize_report_adjustment_source(source_type)
    if not source_type:
        return None
    if not all([tenant_id, student_id, academic_year_id]):
        return None
    if source_type == REPORT_ADJUSTMENT_SOURCE_ACADEMIC and not subject_id:
        return None

    query = ReportScoreAdjustment.query.filter(
        ReportScoreAdjustment.is_deleted.is_(False),
        ReportScoreAdjustment.status == REPORT_ADJUSTMENT_STATUS_ACTIVE,
        ReportScoreAdjustment.tenant_id == tenant_id,
        ReportScoreAdjustment.student_id == student_id,
        ReportScoreAdjustment.academic_year_id == academic_year_id,
        ReportScoreAdjustment.source_type == source_type,
    )
    if source_type == REPORT_ADJUSTMENT_SOURCE_ACADEMIC:
        query = query.filter(ReportScoreAdjustment.subject_id == subject_id)
    else:
        query = query.filter(ReportScoreAdjustment.subject_id.is_(None))
    if class_id is not None:
        query = query.filter(
            db_or_class_scope(ReportScoreAdjustment.class_id, class_id)
        )

    return query.order_by(
        ReportScoreAdjustment.approved_at.desc(),
        ReportScoreAdjustment.created_at.desc(),
        ReportScoreAdjustment.id.desc(),
    ).first()


def db_or_class_scope(column, class_id):
    from app.extensions import db

    return db.or_(column == class_id, column.is_(None))


def resolve_grade_weights(tenant_id=None, academic_year_id=None, subject_id=None):
    config = _load_grade_formula_config(tenant_id)
    if not config:
        return dict(DEFAULT_GRADE_WEIGHTS)

    selected = _select_weight_config(
        config,
        academic_year_id=academic_year_id,
        subject_id=subject_id,
    )
    normalized = _normalize_weights(selected)
    return normalized or dict(DEFAULT_GRADE_WEIGHTS)


def _load_grade_formula_config(tenant_id):
    if tenant_id is None:
        return None

    row = AppConfig.query.filter_by(
        tenant_id=tenant_id,
        key=GRADE_FORMULA_CONFIG_KEY,
        is_deleted=False,
    ).first()
    if row is None or not row.value:
        return None

    try:
        parsed = json.loads(row.value)
    except (TypeError, ValueError):
        current_app.logger.warning(
            "Invalid JSON in %s for tenant_id=%s",
            GRADE_FORMULA_CONFIG_KEY,
            tenant_id,
        )
        return None

    return parsed if isinstance(parsed, dict) else None


def _select_weight_config(config, academic_year_id=None, subject_id=None):
    if _looks_like_weight_map(config):
        return config

    subject_key = str(subject_id) if subject_id is not None else None
    year_key = str(academic_year_id) if academic_year_id is not None else None

    subject_years = config.get("subject_academic_years") or {}
    if subject_key and year_key:
        for key in (f"{subject_key}:{year_key}", f"{year_key}:{subject_key}"):
            selected = subject_years.get(key)
            if selected:
                return selected

    subjects = config.get("subjects") or {}
    if subject_key and subjects.get(subject_key):
        return subjects[subject_key]

    academic_years = config.get("academic_years") or {}
    if year_key and academic_years.get(year_key):
        return academic_years[year_key]

    return config.get("weights") or config.get("default") or config


def _looks_like_weight_map(value):
    if not isinstance(value, dict):
        return False
    return any(str(key).upper() in DEFAULT_GRADE_WEIGHTS for key in value)


def _normalize_weights(value):
    if not isinstance(value, dict):
        return {}

    source = value.get("weights") if isinstance(value.get("weights"), dict) else value
    weights = {}
    for key, raw_weight in source.items():
        normalized_key = str(key).strip().upper()
        if not normalized_key:
            continue
        try:
            weight = float(raw_weight)
        except (TypeError, ValueError):
            continue
        if weight > 0:
            weights[normalized_key] = weight
    return weights
