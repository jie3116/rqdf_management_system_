"""add assignment and multi tenant core tables

Revision ID: p6e7f8g9h0i1
Revises: o5d6e7f8g9h0
Create Date: 2026-03-27 10:15:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'p6e7f8g9h0i1'
down_revision = 'o5d6e7f8g9h0'
branch_labels = None
depends_on = None


def upgrade():
    tenant_status_enum = postgresql.ENUM(
        'ACTIVE', 'SUSPENDED', 'ARCHIVED',
        name='tenantstatus',
        create_type=False,
    )
    person_kind_enum = postgresql.ENUM(
        'STUDENT', 'PARENT', 'EXTERNAL', 'STAFF',
        name='personkind',
        create_type=False,
    )
    program_category_enum = postgresql.ENUM(
        'FORMAL', 'NON_FORMAL',
        name='programcategory',
        create_type=False,
    )
    enrollment_status_enum = postgresql.ENUM(
        'ACTIVE', 'INACTIVE', 'GRADUATED', 'LEFT', 'COMPLETED',
        name='enrollmentstatus',
        create_type=False,
    )
    group_type_enum = postgresql.ENUM(
        'CLASS', 'HALAQAH', 'MAJLIS_CLASS', 'DORMITORY', 'ACTIVITY_GROUP',
        name='grouptype',
        create_type=False,
    )
    membership_status_enum = postgresql.ENUM(
        'ACTIVE', 'LEFT', 'MOVED', 'COMPLETED',
        name='membershipstatus',
        create_type=False,
    )
    assignment_role_enum = postgresql.ENUM(
        'HOMEROOM', 'SUBJECT_TEACHER', 'MURABBI', 'MUSYRIF', 'PEMBINA',
        name='assignmentrole',
        create_type=False,
    )
    gender_enum = postgresql.ENUM('L', 'P', name='gender', create_type=False)
    education_level_enum = postgresql.ENUM('NON_FORMAL', 'SD', 'SMP', 'SMA', name='educationlevel', create_type=False)

    tenant_status_enum.create(op.get_bind(), checkfirst=True)
    person_kind_enum.create(op.get_bind(), checkfirst=True)
    program_category_enum.create(op.get_bind(), checkfirst=True)
    enrollment_status_enum.create(op.get_bind(), checkfirst=True)
    group_type_enum.create(op.get_bind(), checkfirst=True)
    membership_status_enum.create(op.get_bind(), checkfirst=True)
    assignment_role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('status', tenant_status_enum, nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
        sa.UniqueConstraint('slug')
    )
    op.create_index(op.f('ix_tenants_slug'), 'tenants', ['slug'], unique=True)
    op.create_index(op.f('ix_tenants_code'), 'tenants', ['code'], unique=True)

    op.execute(
        """
        INSERT INTO tenants (name, slug, code, status, timezone, is_default, created_at, updated_at, is_deleted)
        VALUES ('Default Tenant', 'default', 'DEFAULT', 'ACTIVE', 'Asia/Jakarta', true, NOW(), NOW(), false)
        """
    )

    op.add_column('users', sa.Column('tenant_id', sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE users
        SET tenant_id = (
            SELECT id FROM tenants WHERE code = 'DEFAULT' LIMIT 1
        )
        WHERE tenant_id IS NULL
        """
    )
    op.alter_column('users', 'tenant_id', nullable=False)
    op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)
    op.create_foreign_key(
        'fk_users_tenant_id_tenants',
        'users',
        'tenants',
        ['tenant_id'],
        ['id']
    )

    op.create_table(
        'people',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('person_code', sa.String(length=50), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=False),
        sa.Column('gender', gender_enum, nullable=True),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('person_kind', person_kind_enum, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'person_code', name='uq_people_tenant_person_code'),
        sa.UniqueConstraint('tenant_id', 'user_id', name='uq_people_tenant_user')
    )
    op.create_index(op.f('ix_people_tenant_id'), 'people', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_people_phone'), 'people', ['phone'], unique=False)

    op.create_table(
        'programs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('category', program_category_enum, nullable=False),
        sa.Column('education_level', education_level_enum, nullable=True),
        sa.Column('report_schema', sa.String(length=50), nullable=False),
        sa.Column('organization_unit', sa.String(length=100), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_programs_tenant_code'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_programs_tenant_name')
    )
    op.create_index(op.f('ix_programs_tenant_id'), 'programs', ['tenant_id'], unique=False)

    op.create_table(
        'program_enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('academic_year_id', sa.Integer(), nullable=True),
        sa.Column('status', enrollment_status_enum, nullable=False),
        sa.Column('join_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('origin_type', sa.String(length=30), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id']),
        sa.ForeignKeyConstraint(['person_id'], ['people.id']),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_program_enrollments_tenant_id'), 'program_enrollments', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_program_enrollments_person_id'), 'program_enrollments', ['person_id'], unique=False)
    op.create_index(op.f('ix_program_enrollments_program_id'), 'program_enrollments', ['program_id'], unique=False)
    op.create_index('idx_program_enrollment_active', 'program_enrollments', ['tenant_id', 'program_id', 'status'], unique=False)

    op.create_table(
        'program_groups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('academic_year_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('group_type', group_type_enum, nullable=False),
        sa.Column('level_label', sa.String(length=50), nullable=True),
        sa.Column('gender_scope', gender_enum, nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id']),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'program_id', 'academic_year_id', 'name', name='uq_program_groups_scope')
    )
    op.create_index(op.f('ix_program_groups_tenant_id'), 'program_groups', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_program_groups_program_id'), 'program_groups', ['program_id'], unique=False)

    op.create_table(
        'group_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('enrollment_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=False),
        sa.Column('status', membership_status_enum, nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['enrollment_id'], ['program_enrollments.id']),
        sa.ForeignKeyConstraint(['group_id'], ['program_groups.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_group_memberships_tenant_id'), 'group_memberships', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_group_memberships_enrollment_id'), 'group_memberships', ['enrollment_id'], unique=False)
    op.create_index(op.f('ix_group_memberships_group_id'), 'group_memberships', ['group_id'], unique=False)
    op.create_index('idx_group_membership_active', 'group_memberships', ['tenant_id', 'group_id', 'status'], unique=False)

    op.create_table(
        'staff_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('program_id', sa.Integer(), nullable=False),
        sa.Column('group_id', sa.Integer(), nullable=True),
        sa.Column('academic_year_id', sa.Integer(), nullable=True),
        sa.Column('assignment_role', assignment_role_enum, nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['academic_year_id'], ['academic_years.id']),
        sa.ForeignKeyConstraint(['group_id'], ['program_groups.id']),
        sa.ForeignKeyConstraint(['person_id'], ['people.id']),
        sa.ForeignKeyConstraint(['program_id'], ['programs.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_staff_assignments_tenant_id'), 'staff_assignments', ['tenant_id'], unique=False)
    op.create_index(op.f('ix_staff_assignments_person_id'), 'staff_assignments', ['person_id'], unique=False)
    op.create_index(op.f('ix_staff_assignments_program_id'), 'staff_assignments', ['program_id'], unique=False)
    op.create_index(op.f('ix_staff_assignments_group_id'), 'staff_assignments', ['group_id'], unique=False)
    op.create_index('idx_staff_assignment_active', 'staff_assignments', ['tenant_id', 'program_id', 'assignment_role'], unique=False)


def downgrade():
    op.drop_index('idx_staff_assignment_active', table_name='staff_assignments')
    op.drop_index(op.f('ix_staff_assignments_group_id'), table_name='staff_assignments')
    op.drop_index(op.f('ix_staff_assignments_program_id'), table_name='staff_assignments')
    op.drop_index(op.f('ix_staff_assignments_person_id'), table_name='staff_assignments')
    op.drop_index(op.f('ix_staff_assignments_tenant_id'), table_name='staff_assignments')
    op.drop_table('staff_assignments')

    op.drop_index('idx_group_membership_active', table_name='group_memberships')
    op.drop_index(op.f('ix_group_memberships_group_id'), table_name='group_memberships')
    op.drop_index(op.f('ix_group_memberships_enrollment_id'), table_name='group_memberships')
    op.drop_index(op.f('ix_group_memberships_tenant_id'), table_name='group_memberships')
    op.drop_table('group_memberships')

    op.drop_index(op.f('ix_program_groups_program_id'), table_name='program_groups')
    op.drop_index(op.f('ix_program_groups_tenant_id'), table_name='program_groups')
    op.drop_table('program_groups')

    op.drop_index('idx_program_enrollment_active', table_name='program_enrollments')
    op.drop_index(op.f('ix_program_enrollments_program_id'), table_name='program_enrollments')
    op.drop_index(op.f('ix_program_enrollments_person_id'), table_name='program_enrollments')
    op.drop_index(op.f('ix_program_enrollments_tenant_id'), table_name='program_enrollments')
    op.drop_table('program_enrollments')

    op.drop_index(op.f('ix_programs_tenant_id'), table_name='programs')
    op.drop_table('programs')

    op.drop_index(op.f('ix_people_phone'), table_name='people')
    op.drop_index(op.f('ix_people_tenant_id'), table_name='people')
    op.drop_table('people')

    op.drop_constraint('fk_users_tenant_id_tenants', 'users', type_='foreignkey')
    op.drop_index(op.f('ix_users_tenant_id'), table_name='users')
    op.drop_column('users', 'tenant_id')

    op.drop_index(op.f('ix_tenants_code'), table_name='tenants')
    op.drop_index(op.f('ix_tenants_slug'), table_name='tenants')
    op.drop_table('tenants')

    postgresql.ENUM(name='assignmentrole').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='membershipstatus').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='grouptype').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='enrollmentstatus').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='programcategory').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='personkind').drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name='tenantstatus').drop(op.get_bind(), checkfirst=True)
