"""add program fields to class room

Revision ID: c2d4e7a9f8b1
Revises: b7f4a2d91c33
Create Date: 2026-02-16 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c2d4e7a9f8b1'
down_revision = 'b7f4a2d91c33'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    is_postgresql = bind.dialect.name == 'postgresql'

    if is_postgresql:
        # Pastikan enum lama kompatibel dengan model terbaru
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE programtype ADD VALUE IF NOT EXISTS 'TAKHOSUS_TAHFIDZ'")
        op.add_column(
            'class_rooms',
            sa.Column('program_type', postgresql.ENUM(name='programtype', create_type=False), nullable=True)
        )
        op.add_column(
            'class_rooms',
            sa.Column('education_level', postgresql.ENUM(name='educationlevel', create_type=False), nullable=True)
        )
    else:
        op.add_column(
            'class_rooms',
            sa.Column(
                'program_type',
                sa.Enum('RQDF_SORE', 'SEKOLAH_FULLDAY', 'TAKHOSUS_TAHFIDZ', 'MAJLIS_TALIM', name='programtype'),
                nullable=True
            )
        )
        op.add_column(
            'class_rooms',
            sa.Column(
                'education_level',
                sa.Enum('NON_FORMAL', 'SD', 'SMP', 'SMA', name='educationlevel'),
                nullable=True
            )
        )

    # Backfill data lama berdasarkan nama kelas / tipe kelas agar tab list siswa langsung terisi
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'SEKOLAH_FULLDAY', education_level = 'SD'
        WHERE program_type IS NULL AND LOWER(name) LIKE '%sd%'
    """)
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'SEKOLAH_FULLDAY', education_level = 'SMP'
        WHERE program_type IS NULL AND LOWER(name) LIKE '%smp%'
    """)
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'SEKOLAH_FULLDAY', education_level = 'SMA'
        WHERE program_type IS NULL AND LOWER(name) LIKE '%sma%'
    """)
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'TAKHOSUS_TAHFIDZ'
        WHERE program_type IS NULL AND LOWER(name) LIKE '%takhosus%'
    """)
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'RQDF_SORE'
        WHERE program_type IS NULL AND (LOWER(name) LIKE '%reguler%' OR LOWER(name) LIKE '%rqdf%')
    """)
    op.execute("""
        UPDATE class_rooms
        SET program_type = 'MAJLIS_TALIM', education_level = COALESCE(education_level, 'NON_FORMAL')
        WHERE program_type IS NULL AND class_type = 'MAJLIS_TALIM'
    """)


def downgrade():
    op.drop_column('class_rooms', 'education_level')
    op.drop_column('class_rooms', 'program_type')
