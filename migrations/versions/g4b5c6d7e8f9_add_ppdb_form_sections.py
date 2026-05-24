"""add ppdb form sections

Revision ID: g4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-05-24 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "g4b5c6d7e8f9"
down_revision = "f3a4b5c6d7e8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ppdb_form_sections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("period_id", sa.Integer(), nullable=False),
        sa.Column("path_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["path_id"], ["ppdb_paths.id"]),
        sa.ForeignKeyConstraint(["period_id"], ["ppdb_periods.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "path_id", "title", name="uq_ppdb_form_sections_path_title"),
    )
    op.create_index("ix_ppdb_form_sections_path_id", "ppdb_form_sections", ["path_id"], unique=False)
    op.create_index("ix_ppdb_form_sections_period_id", "ppdb_form_sections", ["period_id"], unique=False)
    op.create_index("ix_ppdb_form_sections_tenant_id", "ppdb_form_sections", ["tenant_id"], unique=False)

    with op.batch_alter_table("ppdb_form_fields") as batch_op:
        batch_op.add_column(sa.Column("section_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_ppdb_form_fields_section_id",
            "ppdb_form_sections",
            ["section_id"],
            ["id"],
        )
        batch_op.create_index("ix_ppdb_form_fields_section_id", ["section_id"])


def downgrade():
    with op.batch_alter_table("ppdb_form_fields") as batch_op:
        batch_op.drop_index("ix_ppdb_form_fields_section_id")
        batch_op.drop_constraint("fk_ppdb_form_fields_section_id", type_="foreignkey")
        batch_op.drop_column("section_id")

    op.drop_index("ix_ppdb_form_sections_tenant_id", table_name="ppdb_form_sections")
    op.drop_index("ix_ppdb_form_sections_period_id", table_name="ppdb_form_sections")
    op.drop_index("ix_ppdb_form_sections_path_id", table_name="ppdb_form_sections")
    op.drop_table("ppdb_form_sections")
