"""add tenant_id to student_candidates

Revision ID: t0i1j2k3l4m5
Revises: s9h0i1j2k3l4
Create Date: 2026-04-26 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "t0i1j2k3l4m5"
down_revision = "s9h0i1j2k3l4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("student_candidates", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.create_index("ix_student_candidates_tenant_id", "student_candidates", ["tenant_id"], unique=False)
    op.create_foreign_key(
        "fk_student_candidates_tenant_id_tenants",
        "student_candidates",
        "tenants",
        ["tenant_id"],
        ["id"],
    )

    conn = op.get_bind()
    default_tenant_id = conn.execute(
        sa.text(
            "SELECT id FROM tenants "
            "WHERE is_default = true AND is_deleted = false "
            "ORDER BY id ASC LIMIT 1"
        )
    ).scalar()
    if default_tenant_id is None:
        raise RuntimeError("Default tenant tidak ditemukan. Tidak bisa backfill student_candidates.tenant_id.")

    conn.execute(
        sa.text("UPDATE student_candidates SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),
        {"tenant_id": default_tenant_id},
    )

    op.alter_column("student_candidates", "tenant_id", nullable=False)


def downgrade():
    op.drop_constraint("fk_student_candidates_tenant_id_tenants", "student_candidates", type_="foreignkey")
    op.drop_index("ix_student_candidates_tenant_id", table_name="student_candidates")
    op.drop_column("student_candidates", "tenant_id")
