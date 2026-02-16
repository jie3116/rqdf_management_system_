"""add announcement target scope and user

Revision ID: b7f4a2d91c33
Revises: 8c1b9b4f2d11
Create Date: 2026-02-16 11:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f4a2d91c33'
down_revision = '8c1b9b4f2d11'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.add_column(sa.Column('target_scope', sa.String(length=20), nullable=False, server_default='ALL'))
        batch_op.add_column(sa.Column('target_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_announcements_target_user_id_users', 'users', ['target_user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('announcements', schema=None) as batch_op:
        batch_op.drop_constraint('fk_announcements_target_user_id_users', type_='foreignkey')
        batch_op.drop_column('target_user_id')
        batch_op.drop_column('target_scope')
