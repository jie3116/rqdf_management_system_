"""add person_id bridge columns to legacy profiles

Revision ID: q7f8g9h0i1j2
Revises: p6e7f8g9h0i1
Create Date: 2026-04-01 09:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'q7f8g9h0i1j2'
down_revision = 'p6e7f8g9h0i1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('students', sa.Column('person_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_students_person_id'), 'students', ['person_id'], unique=True)
    op.create_foreign_key('fk_students_person_id_people', 'students', 'people', ['person_id'], ['id'])

    op.add_column('parents', sa.Column('person_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_parents_person_id'), 'parents', ['person_id'], unique=False)
    op.create_foreign_key('fk_parents_person_id_people', 'parents', 'people', ['person_id'], ['id'])

    op.add_column('majlis_participants', sa.Column('person_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_majlis_participants_person_id'), 'majlis_participants', ['person_id'], unique=False)
    op.create_foreign_key(
        'fk_majlis_participants_person_id_people',
        'majlis_participants',
        'people',
        ['person_id'],
        ['id'],
    )

    op.add_column('teachers', sa.Column('person_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_teachers_person_id'), 'teachers', ['person_id'], unique=True)
    op.create_foreign_key('fk_teachers_person_id_people', 'teachers', 'people', ['person_id'], ['id'])

    op.add_column('staff', sa.Column('person_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_staff_person_id'), 'staff', ['person_id'], unique=True)
    op.create_foreign_key('fk_staff_person_id_people', 'staff', 'people', ['person_id'], ['id'])

    op.add_column('boarding_guardians', sa.Column('person_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_boarding_guardians_person_id'), 'boarding_guardians', ['person_id'], unique=True)
    op.create_foreign_key(
        'fk_boarding_guardians_person_id_people',
        'boarding_guardians',
        'people',
        ['person_id'],
        ['id'],
    )


def downgrade():
    op.drop_constraint('fk_boarding_guardians_person_id_people', 'boarding_guardians', type_='foreignkey')
    op.drop_index(op.f('ix_boarding_guardians_person_id'), table_name='boarding_guardians')
    op.drop_column('boarding_guardians', 'person_id')

    op.drop_constraint('fk_staff_person_id_people', 'staff', type_='foreignkey')
    op.drop_index(op.f('ix_staff_person_id'), table_name='staff')
    op.drop_column('staff', 'person_id')

    op.drop_constraint('fk_teachers_person_id_people', 'teachers', type_='foreignkey')
    op.drop_index(op.f('ix_teachers_person_id'), table_name='teachers')
    op.drop_column('teachers', 'person_id')

    op.drop_constraint('fk_majlis_participants_person_id_people', 'majlis_participants', type_='foreignkey')
    op.drop_index(op.f('ix_majlis_participants_person_id'), table_name='majlis_participants')
    op.drop_column('majlis_participants', 'person_id')

    op.drop_constraint('fk_parents_person_id_people', 'parents', type_='foreignkey')
    op.drop_index(op.f('ix_parents_person_id'), table_name='parents')
    op.drop_column('parents', 'person_id')

    op.drop_constraint('fk_students_person_id_people', 'students', type_='foreignkey')
    op.drop_index(op.f('ix_students_person_id'), table_name='students')
    op.drop_column('students', 'person_id')
