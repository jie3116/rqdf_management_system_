"""add surah fields to tahfidz evaluations

Revision ID: n4c5d6e7f8g9
Revises: m3b4c5d6e7f8
Create Date: 2026-03-26 10:30:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n4c5d6e7f8g9'
down_revision = 'm3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tahfidz_evaluations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('question_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('question_details', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('surah', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('ayat_start', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('ayat_end', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('tahfidz_evaluations', schema=None) as batch_op:
        batch_op.drop_column('ayat_end')
        batch_op.drop_column('ayat_start')
        batch_op.drop_column('surah')
        batch_op.drop_column('question_details')
        batch_op.drop_column('question_count')
