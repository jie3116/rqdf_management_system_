"""add question items to tahfidz evaluations

Revision ID: o5d6e7f8g9h0
Revises: n4c5d6e7f8g9
Create Date: 2026-03-26 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o5d6e7f8g9h0'
down_revision = 'n4c5d6e7f8g9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tahfidz_evaluations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('question_items', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('tahfidz_evaluations', schema=None) as batch_op:
        batch_op.drop_column('question_items')
