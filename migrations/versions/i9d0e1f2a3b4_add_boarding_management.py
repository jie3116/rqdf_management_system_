"""add boarding management feature

Revision ID: i9d0e1f2a3b4
Revises: h8c9d0e1f2a3
Create Date: 2026-02-17 12:20:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'i9d0e1f2a3b4'
down_revision = 'h8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'WALI_ASRAMA'")

    op.create_table(
        'boarding_guardians',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_boarding_guardians_phone'), 'boarding_guardians', ['phone'], unique=False)

    op.create_table(
        'boarding_dormitories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('gender', postgresql.ENUM('L', 'P', name='gender', create_type=False), nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('guardian_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['guardian_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.add_column('students', sa.Column('boarding_dormitory_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_students_boarding_dormitory_id_boarding_dormitories',
        'students',
        'boarding_dormitories',
        ['boarding_dormitory_id'],
        ['id']
    )

    op.create_table(
        'boarding_activity_schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dormitory_id', sa.Integer(), nullable=False),
        sa.Column('activity_name', sa.String(length=100), nullable=False),
        sa.Column('day', sa.String(length=10), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['dormitory_id'], ['boarding_dormitories.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'boarding_attendances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dormitory_id', sa.Integer(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('attendance_by_user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('status', postgresql.ENUM(
            'HADIR', 'SAKIT', 'IZIN', 'ALPA',
            name='attendancestatus',
            create_type=False
        ), nullable=False),
        sa.Column('notes', sa.String(length=150), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['attendance_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['dormitory_id'], ['boarding_dormitories.id']),
        sa.ForeignKeyConstraint(['schedule_id'], ['boarding_activity_schedules.id']),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date', 'schedule_id', 'student_id', name='uq_boarding_attendance_student_schedule_date')
    )
    op.create_index('idx_boarding_attendance_dormitory_date', 'boarding_attendances', ['dormitory_id', 'date'], unique=False)


def downgrade():
    op.drop_index('idx_boarding_attendance_dormitory_date', table_name='boarding_attendances')
    op.drop_table('boarding_attendances')
    op.drop_table('boarding_activity_schedules')

    op.drop_constraint('fk_students_boarding_dormitory_id_boarding_dormitories', 'students', type_='foreignkey')
    op.drop_column('students', 'boarding_dormitory_id')

    op.drop_table('boarding_dormitories')
    op.drop_index(op.f('ix_boarding_guardians_phone'), table_name='boarding_guardians')
    op.drop_table('boarding_guardians')

    # PostgreSQL enum value userrole.WALI_ASRAMA tidak dihapus saat downgrade.
