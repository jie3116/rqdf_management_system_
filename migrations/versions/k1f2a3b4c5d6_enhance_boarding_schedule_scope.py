"""enhance boarding schedule scope and holidays

Revision ID: k1f2a3b4c5d6
Revises: j0e1f2a3b4c5
Create Date: 2026-02-17 15:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k1f2a3b4c5d6'
down_revision = 'j0e1f2a3b4c5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'boarding_schedule_dormitories',
        sa.Column('schedule_id', sa.Integer(), nullable=False),
        sa.Column('dormitory_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['schedule_id'], ['boarding_activity_schedules.id']),
        sa.ForeignKeyConstraint(['dormitory_id'], ['boarding_dormitories.id']),
        sa.PrimaryKeyConstraint('schedule_id', 'dormitory_id')
    )

    with op.batch_alter_table('boarding_activity_schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('applies_all_dormitories', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('applies_all_days', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('selected_days', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('exclude_national_holidays', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.alter_column('dormitory_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('day', existing_type=sa.String(length=10), nullable=True)

    op.execute("""
        INSERT INTO boarding_schedule_dormitories (schedule_id, dormitory_id)
        SELECT id, dormitory_id
        FROM boarding_activity_schedules
        WHERE dormitory_id IS NOT NULL
        ON CONFLICT DO NOTHING
    """)

    op.execute("""
        UPDATE boarding_activity_schedules
        SET
            applies_all_dormitories = CASE WHEN dormitory_id IS NULL THEN TRUE ELSE FALSE END,
            applies_all_days = CASE WHEN day IS NULL THEN TRUE ELSE FALSE END,
            selected_days = CASE WHEN day IS NULL THEN NULL ELSE day END
    """)

    op.create_table(
        'boarding_holidays',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('is_national', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date')
    )
    op.create_index(op.f('ix_boarding_holidays_date'), 'boarding_holidays', ['date'], unique=True)


def downgrade():
    op.drop_index(op.f('ix_boarding_holidays_date'), table_name='boarding_holidays')
    op.drop_table('boarding_holidays')

    with op.batch_alter_table('boarding_activity_schedules', schema=None) as batch_op:
        batch_op.alter_column('day', existing_type=sa.String(length=10), nullable=False)
        batch_op.alter_column('dormitory_id', existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column('exclude_national_holidays')
        batch_op.drop_column('selected_days')
        batch_op.drop_column('applies_all_days')
        batch_op.drop_column('applies_all_dormitories')

    op.drop_table('boarding_schedule_dormitories')
