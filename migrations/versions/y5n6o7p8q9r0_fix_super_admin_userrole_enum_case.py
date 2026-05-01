"""fix super_admin userrole enum case

Revision ID: y5n6o7p8q9r0
Revises: x4m5n6o7p8q9
Create Date: 2026-05-01 00:00:00.000000
"""

from alembic import op


revision = "y5n6o7p8q9r0"
down_revision = "x4m5n6o7p8q9"
branch_labels = None
depends_on = None


def upgrade():
    # SQLAlchemy Enum(UserRole) menyimpan nama enum (uppercase), bukan value lowercase.
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SUPER_ADMIN'")


def downgrade():
    pass
