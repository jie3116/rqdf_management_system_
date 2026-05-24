"""add ppdb fee items

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-05-24 09:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ppdb_fee_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("path_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.CheckConstraint("amount >= 0", name="ck_ppdb_fee_items_amount_non_negative"),
        sa.ForeignKeyConstraint(["path_id"], ["ppdb_paths.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["ppdb_periods.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ppdb_fee_items_path_id", "ppdb_fee_items", ["path_id"], unique=False)
    op.create_index("ix_ppdb_fee_items_period_id", "ppdb_fee_items", ["period_id"], unique=False)
    op.create_index("ix_ppdb_fee_items_tenant_id", "ppdb_fee_items", ["tenant_id"], unique=False)


def downgrade():
    op.drop_index("ix_ppdb_fee_items_tenant_id", table_name="ppdb_fee_items")
    op.drop_index("ix_ppdb_fee_items_period_id", table_name="ppdb_fee_items")
    op.drop_index("ix_ppdb_fee_items_path_id", table_name="ppdb_fee_items")
    op.drop_table("ppdb_fee_items")
