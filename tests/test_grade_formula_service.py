import json

import pytest

from app import create_app
from app.extensions import db
from app.models import AppConfig, ReportScoreAdjustment, Tenant, User, UserRole
from app.services.grade_formula_service import (
    GRADE_FORMULA_CONFIG_KEY,
    calculate_weighted_final,
    resolve_grade_weights,
)


class TestConfig:
    SECRET_KEY = "test-secret"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def _tenant_with_formula(value):
    tenant = Tenant(name="Tenant Formula", slug="tenant-formula", code="TF", is_default=True)
    db.session.add(tenant)
    db.session.flush()
    db.session.add(
        AppConfig(
            tenant_id=tenant.id,
            key=GRADE_FORMULA_CONFIG_KEY,
            value=json.dumps(value),
            description="Formula nilai",
        )
    )
    db.session.commit()
    return tenant


def test_calculate_weighted_final_uses_default_formula_without_config():
    result = calculate_weighted_final({"TUGAS": 80, "UH": 70, "UTS": 90, "UAS": 100})

    assert result == 85.5


def test_calculate_weighted_final_uses_tenant_config(app):
    tenant = _tenant_with_formula({"TUGAS": 50, "UAS": 50})

    result = calculate_weighted_final(
        {"TUGAS": 80, "UH": 10, "UAS": 100},
        tenant_id=tenant.id,
    )

    assert result == 90


def test_resolve_grade_weights_prefers_subject_academic_year_scope(app):
    tenant = _tenant_with_formula(
        {
            "default": {"TUGAS": 100},
            "academic_years": {"7": {"UTS": 100}},
            "subjects": {"11": {"UH": 100}},
            "subject_academic_years": {"11:7": {"UAS": 100}},
        }
    )

    weights = resolve_grade_weights(
        tenant_id=tenant.id,
        academic_year_id=7,
        subject_id=11,
    )

    assert weights == {"UAS": 100.0}


def test_calculate_weighted_final_applies_active_report_adjustment(app):
    tenant = _tenant_with_formula({"TUGAS": 100})
    user = User(username="admin", email="admin@example.test", tenant_id=tenant.id, role=UserRole.ADMIN)
    db.session.add(user)
    db.session.flush()
    db.session.add(
        ReportScoreAdjustment(
            tenant_id=tenant.id,
            student_id=10,
            class_id=3,
            academic_year_id=7,
            subject_id=11,
            original_score=80,
            adjusted_score=88,
            reason="Berita acara koreksi nilai",
            approval_reference="BA-NILAI/001",
            approved_by_user_id=user.id,
            status="ACTIVE",
        )
    )
    db.session.commit()

    result = calculate_weighted_final(
        {"TUGAS": 80},
        tenant_id=tenant.id,
        student_id=10,
        class_id=3,
        academic_year_id=7,
        subject_id=11,
    )

    assert result == 88
