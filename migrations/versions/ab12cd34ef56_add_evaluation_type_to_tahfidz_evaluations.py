"""add evaluation type to tahfidz evaluations

Revision ID: ab12cd34ef56
Revises: j7k8l9m0n1o2
Create Date: 2026-05-31 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab12cd34ef56'
down_revision = 'j7k8l9m0n1o2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tahfidz_evaluations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('evaluation_type', sa.String(length=30), nullable=True))
        batch_op.alter_column(
            'score',
            existing_type=sa.Integer(),
            type_=sa.Float(),
            existing_nullable=True,
        )

    op.execute(
        "UPDATE tahfidz_evaluations "
        "SET evaluation_type = 'SAMBUNG_AYAT' "
        "WHERE evaluation_type IS NULL"
    )


def downgrade():
    with op.batch_alter_table('tahfidz_evaluations', schema=None) as batch_op:
        batch_op.alter_column(
            'score',
            existing_type=sa.Float(),
            type_=sa.Integer(),
            existing_nullable=True,
        )
        batch_op.drop_column('evaluation_type')
