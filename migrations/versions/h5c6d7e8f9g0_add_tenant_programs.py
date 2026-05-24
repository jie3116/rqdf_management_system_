"""add tenant programs

Revision ID: h5c6d7e8f9g0
Revises: g4b5c6d7e8f9
Create Date: 2026-05-24 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "h5c6d7e8f9g0"
down_revision = "g4b5c6d7e8f9"
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

    op.create_table(
        "tenant_programs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("system_type", programtype_enum, nullable=False),
        sa.Column("education_level", educationlevel_enum, nullable=True),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_tenant_programs_tenant_code"),
    )
    op.create_index("ix_tenant_programs_tenant_id", "tenant_programs", ["tenant_id"], unique=False)

    with op.batch_alter_table("ppdb_paths") as batch_op:
        batch_op.add_column(sa.Column("tenant_program_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_ppdb_paths_tenant_program_id",
            "tenant_programs",
            ["tenant_program_id"],
            ["id"],
        )
        batch_op.create_index("ix_ppdb_paths_tenant_program_id", ["tenant_program_id"])

    op.execute(
        """
        INSERT INTO tenant_programs (
            tenant_id, code, name, system_type, education_level, category,
            is_active, sort_order, created_at, updated_at, is_deleted
        )
        SELECT DISTINCT
            pp.tenant_id,
            pp.program_type::text AS code,
            CASE pp.program_type::text
                WHEN 'SEKOLAH_FULLDAY' THEN 'Sekolah Bina Qur''an'
                WHEN 'RQDF_SORE' THEN 'Kelas Reguler RQDF'
                WHEN 'TAKHOSUS_TAHFIDZ' THEN 'Takhosus Tahfidz'
                WHEN 'MAJLIS_TALIM' THEN 'Majelis Ta''lim'
                WHEN 'BAHASA' THEN 'Program Bahasa'
                ELSE pp.program_type::text
            END AS name,
            pp.program_type AS system_type,
            NULL::educationlevel AS education_level,
            'LEGACY' AS category,
            TRUE AS is_active,
            0 AS sort_order,
            NOW() AS created_at,
            NOW() AS updated_at,
            FALSE AS is_deleted
        FROM ppdb_paths pp
        WHERE pp.is_deleted IS NOT TRUE
        ON CONFLICT (tenant_id, code) DO NOTHING
        """
    )

    op.execute(
        """
        UPDATE ppdb_paths pp
        SET tenant_program_id = tp.id
        FROM tenant_programs tp
        WHERE tp.tenant_id = pp.tenant_id
          AND tp.code = pp.program_type::text
          AND pp.tenant_program_id IS NULL
        """
    )


def downgrade():
    with op.batch_alter_table("ppdb_paths") as batch_op:
        batch_op.drop_index("ix_ppdb_paths_tenant_program_id")
        batch_op.drop_constraint("fk_ppdb_paths_tenant_program_id", type_="foreignkey")
        batch_op.drop_column("tenant_program_id")

    op.drop_index("ix_tenant_programs_tenant_id", table_name="tenant_programs")
    op.drop_table("tenant_programs")
