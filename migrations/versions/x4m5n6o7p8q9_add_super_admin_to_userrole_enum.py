"""add super_admin to userrole enum

Revision ID: x4m5n6o7p8q9
Revises: w3l4m5n6o7p8
Create Date: 2026-05-01 00:00:00.000000
"""

from alembic import op


revision = "x4m5n6o7p8q9"
down_revision = "w3l4m5n6o7p8"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'super_admin'")


def downgrade():
    pass
