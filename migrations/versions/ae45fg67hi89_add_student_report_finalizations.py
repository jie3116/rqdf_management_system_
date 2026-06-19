"""add student report finalizations

Revision ID: ae45fg67hi89
Revises: ad34ef56gh78
Create Date: 2026-06-19
"""

from alembic import op
import sqlalchemy as sa


revision = 'ae45fg67hi89'
down_revision = 'ad34ef56gh78'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'student_report_finalizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=True),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('period_key', sa.String(length=100), nullable=False),
        sa.Column('homeroom_note', sa.Text(), nullable=True),
        sa.Column('behavior_overrides', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['class_id'], ['class_rooms.id']),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'tenant_id',
            'student_id',
            'period_key',
            name='uq_student_report_finalization_period',
        ),
    )
    op.create_index(
        op.f('ix_student_report_finalizations_tenant_id'),
        'student_report_finalizations',
        ['tenant_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_student_report_finalizations_student_id'),
        'student_report_finalizations',
        ['student_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_student_report_finalizations_class_id'),
        'student_report_finalizations',
        ['class_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_student_report_finalizations_teacher_id'),
        'student_report_finalizations',
        ['teacher_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_student_report_finalizations_period_key'),
        'student_report_finalizations',
        ['period_key'],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f('ix_student_report_finalizations_period_key'), table_name='student_report_finalizations')
    op.drop_index(op.f('ix_student_report_finalizations_teacher_id'), table_name='student_report_finalizations')
    op.drop_index(op.f('ix_student_report_finalizations_class_id'), table_name='student_report_finalizations')
    op.drop_index(op.f('ix_student_report_finalizations_student_id'), table_name='student_report_finalizations')
    op.drop_index(op.f('ix_student_report_finalizations_tenant_id'), table_name='student_report_finalizations')
    op.drop_table('student_report_finalizations')
