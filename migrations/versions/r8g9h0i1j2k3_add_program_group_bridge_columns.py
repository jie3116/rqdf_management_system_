"""add program_group_id bridge columns to legacy groups

Revision ID: r8g9h0i1j2k3
Revises: q7f8g9h0i1j2
Create Date: 2026-04-01 10:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r8g9h0i1j2k3'
down_revision = 'q7f8g9h0i1j2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('class_rooms', sa.Column('program_group_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_class_rooms_program_group_id'), 'class_rooms', ['program_group_id'], unique=True)
    op.create_foreign_key(
        'fk_class_rooms_program_group_id_program_groups',
        'class_rooms',
        'program_groups',
        ['program_group_id'],
        ['id'],
    )

    op.add_column('boarding_dormitories', sa.Column('program_group_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_boarding_dormitories_program_group_id'),
        'boarding_dormitories',
        ['program_group_id'],
        unique=True,
    )
    op.create_foreign_key(
        'fk_boarding_dormitories_program_group_id_program_groups',
        'boarding_dormitories',
        'program_groups',
        ['program_group_id'],
        ['id'],
    )


def downgrade():
    op.drop_constraint(
        'fk_boarding_dormitories_program_group_id_program_groups',
        'boarding_dormitories',
        type_='foreignkey',
    )
    op.drop_index(op.f('ix_boarding_dormitories_program_group_id'), table_name='boarding_dormitories')
    op.drop_column('boarding_dormitories', 'program_group_id')

    op.drop_constraint('fk_class_rooms_program_group_id_program_groups', 'class_rooms', type_='foreignkey')
    op.drop_index(op.f('ix_class_rooms_program_group_id'), table_name='class_rooms')
    op.drop_column('class_rooms', 'program_group_id')
