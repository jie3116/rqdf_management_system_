"""add user role assignments for multi role support

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-02-17 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'j0e1f2a3b4c5'
down_revision = 'i9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    userrole_enum = postgresql.ENUM(
        'ADMIN', 'GURU', 'SISWA', 'WALI_MURID', 'WALI_ASRAMA', 'TU', 'MAJLIS_PARTICIPANT',
        name='userrole',
        create_type=False
    )
    op.create_table(
        'user_role_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', userrole_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role', name='uq_user_role_assignment')
    )


def downgrade():
    op.drop_table('user_role_assignments')
