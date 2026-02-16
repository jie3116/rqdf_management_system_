"""add behavior reports table

Revision ID: 8c1b9b4f2d11
Revises: 12a1e9060913
Create Date: 2026-02-16 10:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '8c1b9b4f2d11'
down_revision = '12a1e9060913'
branch_labels = None
depends_on = None


def upgrade():
    # Buat enum secara aman (tidak gagal jika enum sudah ada).
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE behaviorreporttype AS ENUM ('POSITIVE', 'DEVELOPMENT', 'CONCERN');
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )

    behaviorreporttype = postgresql.ENUM(
        'POSITIVE',
        'DEVELOPMENT',
        'CONCERN',
        name='behaviorreporttype',
        create_type=False
    )

    op.create_table(
        'behavior_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=False),
        sa.Column('report_type', behaviorreporttype, nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('action_plan', sa.Text(), nullable=True),
        sa.Column('follow_up_date', sa.Date(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_behavior_reports_report_date'), 'behavior_reports', ['report_date'], unique=False)
    op.create_index(op.f('ix_behavior_reports_student_id'), 'behavior_reports', ['student_id'], unique=False)
    op.create_index(op.f('ix_behavior_reports_teacher_id'), 'behavior_reports', ['teacher_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_behavior_reports_teacher_id'), table_name='behavior_reports')
    op.drop_index(op.f('ix_behavior_reports_student_id'), table_name='behavior_reports')
    op.drop_index(op.f('ix_behavior_reports_report_date'), table_name='behavior_reports')
    op.drop_table('behavior_reports')

    # Hapus enum jika tidak dipakai lagi.
    op.execute("DROP TYPE IF EXISTS behaviorreporttype")
