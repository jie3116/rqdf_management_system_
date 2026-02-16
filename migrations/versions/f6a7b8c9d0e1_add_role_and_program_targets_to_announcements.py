"""add role and program targets to announcements

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-16 14:05:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('announcements', sa.Column('target_role', sa.String(length=30), nullable=True))
    op.add_column('announcements', sa.Column('target_program_type', sa.String(length=50), nullable=True))


def downgrade():
    op.drop_column('announcements', 'target_program_type')
    op.drop_column('announcements', 'target_role')
