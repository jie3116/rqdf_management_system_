"""backfill class program mapping

Revision ID: d4a6b7c8e9f0
Revises: c2d4e7a9f8b1
Create Date: 2026-02-16 13:05:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'd4a6b7c8e9f0'
down_revision = 'c2d4e7a9f8b1'
branch_labels = None
depends_on = None


def upgrade():
    # Pola umum kelas RQDF/reguler
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'RQDF_SORE'
        WHERE program_type IS NULL
          AND (
            LOWER(name) LIKE '%td sore%'
            OR LOWER(name) LIKE '%sore%'
            OR LOWER(name) LIKE '%rqdf%'
            OR LOWER(name) LIKE '%reguler%'
          )
    """)

    # Fallback SBQ berdasarkan grade level
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'SEKOLAH_FULLDAY', education_level = COALESCE(education_level, 'SD')
        WHERE program_type IS NULL
          AND grade_level IN (1, 2, 3, 4, 5, 6)
    """)
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'SEKOLAH_FULLDAY', education_level = COALESCE(education_level, 'SMP')
        WHERE program_type IS NULL
          AND grade_level IN (7, 8, 9)
    """)
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'SEKOLAH_FULLDAY', education_level = COALESCE(education_level, 'SMA')
        WHERE program_type IS NULL
          AND grade_level IN (10, 11, 12)
    """)


def downgrade():
    # Data-only migration: tidak rollback untuk mencegah hilang klasifikasi manual
    pass
