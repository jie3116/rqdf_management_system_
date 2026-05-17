"""add pimpinan to userrole enum

Revision ID: c6d7e8f9g0h1
Revises: b1f2e3d4c5a6
Create Date: 2026-05-17 00:00:00.000000
"""

from alembic import op


revision = "c6d7e8f9g0h1"
down_revision = "b1f2e3d4c5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'pimpinan'")
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'PIMPINAN'")


def downgrade():
    pass
