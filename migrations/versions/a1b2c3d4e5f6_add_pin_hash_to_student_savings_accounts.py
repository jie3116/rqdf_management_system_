"""add pin hash to student savings accounts

Revision ID: a1b2c3d4e5f6
Revises: z9y8x7w6v5u4
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'z9y8x7w6v5u4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('student_savings_accounts', sa.Column('pin_hash', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('student_savings_accounts', 'pin_hash')
