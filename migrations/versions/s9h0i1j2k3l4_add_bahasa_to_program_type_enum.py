"""add BAHASA to program_type enum

Revision ID: s9h0i1j2k3l4
Revises: r8g9h0i1j2k3
Create Date: 2026-04-12 00:00:00.000000
"""

from alembic import op


revision = "s9h0i1j2k3l4"
down_revision = "r8g9h0i1j2k3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE programtype ADD VALUE IF NOT EXISTS 'BAHASA'")


def downgrade():
    pass
