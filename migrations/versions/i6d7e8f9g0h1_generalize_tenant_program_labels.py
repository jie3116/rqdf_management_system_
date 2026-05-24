"""generalize tenant program labels

Revision ID: i6d7e8f9g0h1
Revises: h5c6d7e8f9g0
Create Date: 2026-05-24 12:00:00.000000
"""

from alembic import op


revision = "i6d7e8f9g0h1"
down_revision = "h5c6d7e8f9g0"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE tenant_programs
        SET name = 'Sekolah Formal'
        WHERE code = 'SEKOLAH_FULLDAY'
          AND name = 'Sekolah Bina Qur''an'
          AND category IN ('LEGACY', 'FORMAL', 'PPDB')
        """
    )
    op.execute(
        """
        UPDATE tenant_programs
        SET name = 'Rumah Qur''an'
        WHERE code = 'RQDF_SORE'
          AND name = 'Kelas Reguler RQDF'
          AND category IN ('LEGACY', 'NON_FORMAL', 'PPDB')
        """
    )
    op.execute(
        """
        UPDATE tenant_programs
        SET name = 'Tahfidz Intensif'
        WHERE code = 'TAKHOSUS_TAHFIDZ'
          AND name = 'Takhosus Tahfidz'
          AND category IN ('LEGACY', 'NON_FORMAL', 'PPDB')
        """
    )
    op.execute(
        """
        UPDATE tenant_programs
        SET name = 'Majelis / Kelas Dewasa'
        WHERE code = 'MAJLIS_TALIM'
          AND name = 'Majelis Ta''lim'
          AND category IN ('LEGACY', 'MAJLIS', 'PPDB')
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE tenant_programs
        SET name = 'Sekolah Bina Qur''an'
        WHERE code = 'SEKOLAH_FULLDAY'
          AND name = 'Sekolah Formal'
          AND category IN ('LEGACY', 'FORMAL', 'PPDB')
        """
    )
    op.execute(
        """
        UPDATE tenant_programs
        SET name = 'Kelas Reguler RQDF'
        WHERE code = 'RQDF_SORE'
          AND name = 'Rumah Qur''an'
          AND category IN ('LEGACY', 'NON_FORMAL', 'PPDB')
        """
    )
    op.execute(
        """
        UPDATE tenant_programs
        SET name = 'Takhosus Tahfidz'
        WHERE code = 'TAKHOSUS_TAHFIDZ'
          AND name = 'Tahfidz Intensif'
          AND category IN ('LEGACY', 'NON_FORMAL', 'PPDB')
        """
    )
    op.execute(
        """
        UPDATE tenant_programs
        SET name = 'Majelis Ta''lim'
        WHERE code = 'MAJLIS_TALIM'
          AND name = 'Majelis / Kelas Dewasa'
          AND category IN ('LEGACY', 'MAJLIS', 'PPDB')
        """
    )
