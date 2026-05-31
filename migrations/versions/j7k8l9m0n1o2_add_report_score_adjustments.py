"""add report score adjustments

Revision ID: j7k8l9m0n1o2
Revises: i6d7e8f9g0h1
Create Date: 2026-05-31 20:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "j7k8l9m0n1o2"
down_revision = "i6d7e8f9g0h1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "report_score_adjustments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=True),
        sa.Column("academic_year_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("original_score", sa.Float(), nullable=False),
        sa.Column("adjusted_score", sa.Float(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("approval_reference", sa.String(length=100), nullable=False),
        sa.Column("approved_by_user_id", sa.Integer(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("voided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("voided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["academic_year_id"], ["academic_years.id"]),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["class_id"], ["class_rooms.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["voided_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_score_adjustments_tenant_id", "report_score_adjustments", ["tenant_id"])
    op.create_index("ix_report_score_adjustments_student_id", "report_score_adjustments", ["student_id"])
    op.create_index("ix_report_score_adjustments_class_id", "report_score_adjustments", ["class_id"])
    op.create_index("ix_report_score_adjustments_academic_year_id", "report_score_adjustments", ["academic_year_id"])
    op.create_index("ix_report_score_adjustments_subject_id", "report_score_adjustments", ["subject_id"])
    op.create_index("ix_report_score_adjustments_approved_by_user_id", "report_score_adjustments", ["approved_by_user_id"])
    op.create_index("ix_report_score_adjustments_status", "report_score_adjustments", ["status"])
    op.create_index("ix_report_score_adjustments_voided_by_user_id", "report_score_adjustments", ["voided_by_user_id"])
    op.create_index(
        "idx_report_score_adjustment_lookup",
        "report_score_adjustments",
        ["tenant_id", "student_id", "academic_year_id", "subject_id", "status"],
    )


def downgrade():
    op.drop_index("idx_report_score_adjustment_lookup", table_name="report_score_adjustments")
    op.drop_index("ix_report_score_adjustments_voided_by_user_id", table_name="report_score_adjustments")
    op.drop_index("ix_report_score_adjustments_status", table_name="report_score_adjustments")
    op.drop_index("ix_report_score_adjustments_approved_by_user_id", table_name="report_score_adjustments")
    op.drop_index("ix_report_score_adjustments_subject_id", table_name="report_score_adjustments")
    op.drop_index("ix_report_score_adjustments_academic_year_id", table_name="report_score_adjustments")
    op.drop_index("ix_report_score_adjustments_class_id", table_name="report_score_adjustments")
    op.drop_index("ix_report_score_adjustments_student_id", table_name="report_score_adjustments")
    op.drop_index("ix_report_score_adjustments_tenant_id", table_name="report_score_adjustments")
    op.drop_table("report_score_adjustments")
