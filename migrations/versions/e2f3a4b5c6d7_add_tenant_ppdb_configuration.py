"""add tenant ppdb configuration

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-05-23 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    programtype_enum = postgresql.ENUM(
        "RQDF_SORE",
        "SEKOLAH_FULLDAY",
        "TAKHOSUS_TAHFIDZ",
        "MAJLIS_TALIM",
        "BAHASA",
        name="programtype",
        create_type=False,
    )
    educationlevel_enum = postgresql.ENUM(
        "NON_FORMAL",
        "SD",
        "SMP",
        "SMA",
        name="educationlevel",
        create_type=False,
    )
    scholarshipcategory_enum = postgresql.ENUM(
        "NON_BEASISWA",
        "TAHFIDZ_5_JUZ",
        "TAHFIDZ_10_30_JUZ",
        "YATIM_DHUAFA",
        name="scholarshipcategory",
        create_type=False,
    )

    op.create_table(
        "ppdb_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("academic_year_label", sa.String(length=20), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Enum("DRAFT", "OPEN", "CLOSED", name="ppdbperiodstatus"), nullable=False),
        sa.Column("registration_no_prefix", sa.String(length=10), nullable=False),
        sa.Column("public_registration_enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.CheckConstraint("end_date >= start_date", name="ck_ppdb_periods_date_range"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_ppdb_periods_tenant_name"),
    )
    op.create_index("ix_ppdb_periods_tenant_id", "ppdb_periods", ["tenant_id"], unique=False)

    op.create_table(
        "ppdb_paths",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("program_type", programtype_enum, nullable=False),
        sa.Column("education_level", educationlevel_enum, nullable=True),
        sa.Column("scholarship_category", scholarshipcategory_enum, nullable=True),
        sa.Column("quota", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.CheckConstraint("quota IS NULL OR quota >= 0", name="ck_ppdb_paths_quota_non_negative"),
        sa.ForeignKeyConstraint(["period_id"], ["ppdb_periods.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "period_id", "code", name="uq_ppdb_paths_period_code"),
    )
    op.create_index("ix_ppdb_paths_period_id", "ppdb_paths", ["period_id"], unique=False)
    op.create_index("ix_ppdb_paths_tenant_id", "ppdb_paths", ["tenant_id"], unique=False)

    op.create_table(
        "ppdb_feature_flags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=True),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "key", name="uq_ppdb_feature_flags_tenant_key"),
    )
    op.create_index("ix_ppdb_feature_flags_tenant_id", "ppdb_feature_flags", ["tenant_id"], unique=False)

    op.create_table(
        "ppdb_form_fields",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("path_id", sa.Integer(), nullable=True),
        sa.Column("field_key", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("field_type", sa.Enum("TEXT", "TEXTAREA", "NUMBER", "DATE", "SELECT", "BOOLEAN", name="ppdbfieldtype"), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("options_json", sa.Text(), nullable=True),
        sa.Column("validation_json", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["path_id"], ["ppdb_paths.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["ppdb_periods.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "period_id", "path_id", "field_key", name="uq_ppdb_form_fields_scope_key"),
    )
    op.create_index("ix_ppdb_form_fields_path_id", "ppdb_form_fields", ["path_id"], unique=False)
    op.create_index("ix_ppdb_form_fields_period_id", "ppdb_form_fields", ["period_id"], unique=False)
    op.create_index("ix_ppdb_form_fields_tenant_id", "ppdb_form_fields", ["tenant_id"], unique=False)

    op.create_table(
        "ppdb_document_requirements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("path_id", sa.Integer(), nullable=True),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("allowed_file_types", sa.String(length=120), nullable=True),
        sa.Column("max_file_size_kb", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["path_id"], ["ppdb_paths.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["ppdb_periods.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "period_id", "path_id", "code", name="uq_ppdb_document_requirements_scope_code"),
    )
    op.create_index("ix_ppdb_document_requirements_path_id", "ppdb_document_requirements", ["path_id"], unique=False)
    op.create_index("ix_ppdb_document_requirements_period_id", "ppdb_document_requirements", ["period_id"], unique=False)
    op.create_index("ix_ppdb_document_requirements_tenant_id", "ppdb_document_requirements", ["tenant_id"], unique=False)

    with op.batch_alter_table("student_candidates") as batch_op:
        batch_op.add_column(sa.Column("ppdb_period_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("ppdb_path_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("extra_answers_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("document_status_json", sa.Text(), nullable=True))
        batch_op.create_foreign_key("fk_student_candidates_ppdb_period_id", "ppdb_periods", ["ppdb_period_id"], ["id"])
        batch_op.create_foreign_key("fk_student_candidates_ppdb_path_id", "ppdb_paths", ["ppdb_path_id"], ["id"])
        batch_op.create_index("ix_student_candidates_ppdb_period_id", ["ppdb_period_id"])
        batch_op.create_index("ix_student_candidates_ppdb_path_id", ["ppdb_path_id"])


def downgrade():
    with op.batch_alter_table("student_candidates") as batch_op:
        batch_op.drop_index("ix_student_candidates_ppdb_path_id")
        batch_op.drop_index("ix_student_candidates_ppdb_period_id")
        batch_op.drop_constraint("fk_student_candidates_ppdb_path_id", type_="foreignkey")
        batch_op.drop_constraint("fk_student_candidates_ppdb_period_id", type_="foreignkey")
        batch_op.drop_column("document_status_json")
        batch_op.drop_column("extra_answers_json")
        batch_op.drop_column("ppdb_path_id")
        batch_op.drop_column("ppdb_period_id")

    op.drop_index("ix_ppdb_document_requirements_tenant_id", table_name="ppdb_document_requirements")
    op.drop_index("ix_ppdb_document_requirements_period_id", table_name="ppdb_document_requirements")
    op.drop_index("ix_ppdb_document_requirements_path_id", table_name="ppdb_document_requirements")
    op.drop_table("ppdb_document_requirements")
    op.drop_index("ix_ppdb_form_fields_tenant_id", table_name="ppdb_form_fields")
    op.drop_index("ix_ppdb_form_fields_period_id", table_name="ppdb_form_fields")
    op.drop_index("ix_ppdb_form_fields_path_id", table_name="ppdb_form_fields")
    op.drop_table("ppdb_form_fields")
    op.drop_index("ix_ppdb_feature_flags_tenant_id", table_name="ppdb_feature_flags")
    op.drop_table("ppdb_feature_flags")
    op.drop_index("ix_ppdb_paths_tenant_id", table_name="ppdb_paths")
    op.drop_index("ix_ppdb_paths_period_id", table_name="ppdb_paths")
    op.drop_table("ppdb_paths")
    op.drop_index("ix_ppdb_periods_tenant_id", table_name="ppdb_periods")
    op.drop_table("ppdb_periods")
