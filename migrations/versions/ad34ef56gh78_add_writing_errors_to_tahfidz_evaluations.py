"""add writing errors to tahfidz evaluations

Revision ID: ad34ef56gh78
Revises: ac23de45fg67
Create Date: 2026-06-15 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ad34ef56gh78'
down_revision = 'ac23de45fg67'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tahfidz_evaluations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('writing_errors', sa.Integer(), nullable=True))

    op.execute(
        "UPDATE tahfidz_evaluations "
        "SET writing_errors = 0 "
        "WHERE writing_errors IS NULL"
    )


def downgrade():
    with op.batch_alter_table('tahfidz_evaluations', schema=None) as batch_op:
        batch_op.drop_column('writing_errors')
