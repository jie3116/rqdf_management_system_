"""add student savings management

Revision ID: z9y8x7w6v5u4
Revises: f6a7b8c9d0e1
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'z9y8x7w6v5u4'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('student_savings_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('balance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('student_id')
    )
    op.create_index('ix_student_savings_accounts_tenant_id', 'student_savings_accounts', ['tenant_id'])

    op.create_table('student_savings_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.Enum('DEPOSIT','WITHDRAWAL', name='savingstransactiontype'), nullable=False),
        sa.Column('status', sa.Enum('PENDING','APPROVED','REJECTED', name='savingstransactionstatus'), nullable=False),
        sa.Column('proof_image', sa.String(length=255), nullable=True),
        sa.Column('requested_by_user_id', sa.Integer(), nullable=False),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['student_savings_accounts.id']),
        sa.ForeignKeyConstraint(['student_id'], ['students.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_student_savings_transactions_tenant_id', 'student_savings_transactions', ['tenant_id'])

def downgrade():
    op.drop_index('ix_student_savings_transactions_tenant_id', table_name='student_savings_transactions')
    op.drop_table('student_savings_transactions')
    op.drop_index('ix_student_savings_accounts_tenant_id', table_name='student_savings_accounts')
    op.drop_table('student_savings_accounts')
    sa.Enum(name='savingstransactiontype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='savingstransactionstatus').drop(op.get_bind(), checkfirst=True)
