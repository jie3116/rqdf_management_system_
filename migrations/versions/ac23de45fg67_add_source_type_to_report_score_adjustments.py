"""add source type to report score adjustments

Revision ID: ac23de45fg67
Revises: ab12cd34ef56
Create Date: 2026-06-01 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'ac23de45fg67'
down_revision = 'ab12cd34ef56'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('report_score_adjustments', schema=None) as batch_op:
        batch_op.drop_index('idx_report_score_adjustment_lookup')
        batch_op.add_column(sa.Column('source_type', sa.String(length=30), nullable=False, server_default='ACADEMIC'))
        batch_op.alter_column(
            'subject_id',
            existing_type=sa.Integer(),
            nullable=True,
            existing_nullable=False,
        )
        batch_op.create_index(
            'idx_report_score_adjustment_lookup',
            ['tenant_id', 'student_id', 'academic_year_id', 'subject_id', 'source_type', 'status'],
            unique=False,
        )
        batch_op.create_index('ix_report_score_adjustments_source_type', ['source_type'], unique=False)


def downgrade():
    with op.batch_alter_table('report_score_adjustments', schema=None) as batch_op:
        batch_op.drop_index('ix_report_score_adjustments_source_type')
        batch_op.drop_index('idx_report_score_adjustment_lookup')
        batch_op.alter_column(
            'subject_id',
            existing_type=sa.Integer(),
            nullable=False,
            existing_nullable=True,
        )
        batch_op.drop_column('source_type')
        batch_op.create_index(
            'idx_report_score_adjustment_lookup',
            ['tenant_id', 'student_id', 'academic_year_id', 'subject_id', 'status'],
            unique=False,
        )
