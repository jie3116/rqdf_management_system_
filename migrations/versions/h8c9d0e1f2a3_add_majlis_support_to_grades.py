"""add majlis support to grades

Revision ID: h8c9d0e1f2a3
Revises: g7b8c9d0e1f2
Create Date: 2026-02-17 10:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h8c9d0e1f2a3'
down_revision = 'g7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('grades', schema=None) as batch_op:
        batch_op.add_column(sa.Column('majlis_participant_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('participant_type', sa.Enum('STUDENT', 'PARENT_MAJLIS', 'EXTERNAL_MAJLIS', name='participanttype'), nullable=True, server_default='STUDENT'))
        batch_op.add_column(sa.Column('majlis_subject_id', sa.Integer(), nullable=True))
        batch_op.alter_column('student_id', existing_type=sa.Integer(), nullable=True)
        batch_op.alter_column('subject_id', existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key('fk_grades_majlis_participant_id_majlis_participants', 'majlis_participants', ['majlis_participant_id'], ['id'])
        batch_op.create_foreign_key('fk_grades_majlis_subject_id_majlis_subjects', 'majlis_subjects', ['majlis_subject_id'], ['id'])
        batch_op.alter_column('participant_type', existing_type=sa.Enum('STUDENT', 'PARENT_MAJLIS', 'EXTERNAL_MAJLIS', name='participanttype'), nullable=False, server_default='STUDENT')


def downgrade():
    with op.batch_alter_table('grades', schema=None) as batch_op:
        batch_op.drop_constraint('fk_grades_majlis_subject_id_majlis_subjects', type_='foreignkey')
        batch_op.drop_constraint('fk_grades_majlis_participant_id_majlis_participants', type_='foreignkey')
        batch_op.drop_column('majlis_subject_id')
        batch_op.drop_column('participant_type')
        batch_op.drop_column('majlis_participant_id')
