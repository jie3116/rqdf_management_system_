"""fix unknown grade class mapping

Revision ID: e5f6a7b8c9d0
Revises: d4a6b7c8e9f0
Create Date: 2026-02-16 13:25:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4a6b7c8e9f0'
branch_labels = None
depends_on = None


def upgrade():
    # Grade 20 dipakai sebagai placeholder '-', jangan dipaksa menjadi SMA
    op.execute("""
        UPDATE class_rooms
        SET program_type = NULL, education_level = NULL
        WHERE grade_level = 20
          AND program_type = 'SEKOLAH_FULLDAY'
          AND education_level = 'SMA'
          AND LOWER(name) NOT LIKE '%sma%'
    """)


def downgrade():
    pass
