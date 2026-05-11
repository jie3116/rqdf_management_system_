"""add finance accounting core

Revision ID: b1f2e3d4c5a6
Revises: aa6b7c8d9e0f
Create Date: 2026-05-10 11:40:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'b1f2e3d4c5a6'
down_revision = 'aa6b7c8d9e0f'
branch_labels = None
depends_on = None


finance_account_category = postgresql.ENUM(
    'ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE',
    name='financeaccountcategory',
    create_type=False,
)
finance_normal_balance = postgresql.ENUM('DEBIT', 'CREDIT', name='financenormalbalance', create_type=False)
finance_period_status = postgresql.ENUM('OPEN', 'CLOSED', 'LOCKED', name='financeperiodstatus', create_type=False)
finance_accounting_basis = postgresql.ENUM('CASH', 'ACCRUAL', name='financeaccountingbasis', create_type=False)
finance_journal_status = postgresql.ENUM('DRAFT', 'POSTED', 'VOID', name='financejournalstatus', create_type=False)
finance_entry_side = postgresql.ENUM('DEBIT', 'CREDIT', name='financeentryside', create_type=False)
finance_journal_source_type = postgresql.ENUM(
    'INVOICE_PAYMENT',
    'SAVINGS_DEPOSIT',
    'SAVINGS_WITHDRAWAL',
    'CASH_BANK_TRANSACTION',
    'ADJUSTMENT',
    'REVERSAL',
    'MANUAL',
    name='financejournalsourcetype',
    create_type=False,
)
finance_cash_bank_account_type = postgresql.ENUM('CASH', 'BANK', 'EWALLET', name='financecashbankaccounttype', create_type=False)
finance_cash_bank_transaction_type = postgresql.ENUM('IN', 'OUT', 'TRANSFER', name='financecashbanktransactiontype', create_type=False)
finance_cash_bank_transaction_status = postgresql.ENUM('DRAFT', 'POSTED', 'VOID', name='financecashbanktransactionstatus', create_type=False)


def upgrade():
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financeaccountcategory') THEN "
        "CREATE TYPE financeaccountcategory AS ENUM ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financenormalbalance') THEN "
        "CREATE TYPE financenormalbalance AS ENUM ('DEBIT', 'CREDIT'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financeperiodstatus') THEN "
        "CREATE TYPE financeperiodstatus AS ENUM ('OPEN', 'CLOSED', 'LOCKED'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financeaccountingbasis') THEN "
        "CREATE TYPE financeaccountingbasis AS ENUM ('CASH', 'ACCRUAL'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financejournalstatus') THEN "
        "CREATE TYPE financejournalstatus AS ENUM ('DRAFT', 'POSTED', 'VOID'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financeentryside') THEN "
        "CREATE TYPE financeentryside AS ENUM ('DEBIT', 'CREDIT'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financejournalsourcetype') THEN "
        "CREATE TYPE financejournalsourcetype AS ENUM "
        "('INVOICE_PAYMENT','SAVINGS_DEPOSIT','SAVINGS_WITHDRAWAL','CASH_BANK_TRANSACTION','ADJUSTMENT','REVERSAL','MANUAL'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financecashbankaccounttype') THEN "
        "CREATE TYPE financecashbankaccounttype AS ENUM ('CASH', 'BANK', 'EWALLET'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financecashbanktransactiontype') THEN "
        "CREATE TYPE financecashbanktransactiontype AS ENUM ('IN', 'OUT', 'TRANSFER'); "
        "END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'financecashbanktransactionstatus') THEN "
        "CREATE TYPE financecashbanktransactionstatus AS ENUM ('DRAFT', 'POSTED', 'VOID'); "
        "END IF; END $$;"
    )

    op.create_table(
        'finance_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('category', finance_account_category, nullable=False),
        sa.Column('normal_balance', finance_normal_balance, nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.ForeignKeyConstraint(['parent_id'], ['finance_accounts.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_finance_accounts_tenant_code'),
    )
    op.create_index('ix_finance_accounts_tenant_id', 'finance_accounts', ['tenant_id'], unique=False)
    op.create_index('ix_finance_accounts_parent_id', 'finance_accounts', ['parent_id'], unique=False)

    op.create_table(
        'finance_periods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=20), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', finance_period_status, nullable=False, server_default='OPEN'),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('closed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.ForeignKeyConstraint(['closed_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_finance_periods_tenant_name'),
    )
    op.create_index('ix_finance_periods_tenant_id', 'finance_periods', ['tenant_id'], unique=False)

    op.create_table(
        'finance_cash_bank_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('account_name', sa.String(length=120), nullable=False),
        sa.Column('account_type', finance_cash_bank_account_type, nullable=False),
        sa.Column('gl_account_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.ForeignKeyConstraint(['gl_account_id'], ['finance_accounts.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'account_name', name='uq_finance_cash_bank_accounts_tenant_name'),
    )
    op.create_index('ix_finance_cash_bank_accounts_tenant_id', 'finance_cash_bank_accounts', ['tenant_id'], unique=False)

    op.create_table(
        'finance_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('accounting_basis', finance_accounting_basis, nullable=False, server_default='CASH'),
        sa.Column('default_cash_bank_account_id', sa.Integer(), nullable=True),
        sa.Column('default_spp_revenue_account_id', sa.Integer(), nullable=True),
        sa.Column('default_registration_revenue_account_id', sa.Integer(), nullable=True),
        sa.Column('default_savings_liability_account_id', sa.Integer(), nullable=True),
        sa.Column('default_donation_revenue_account_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.ForeignKeyConstraint(['default_cash_bank_account_id'], ['finance_cash_bank_accounts.id']),
        sa.ForeignKeyConstraint(['default_donation_revenue_account_id'], ['finance_accounts.id']),
        sa.ForeignKeyConstraint(['default_registration_revenue_account_id'], ['finance_accounts.id']),
        sa.ForeignKeyConstraint(['default_savings_liability_account_id'], ['finance_accounts.id']),
        sa.ForeignKeyConstraint(['default_spp_revenue_account_id'], ['finance_accounts.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', name='uq_finance_settings_tenant'),
    )
    op.create_index('ix_finance_settings_tenant_id', 'finance_settings', ['tenant_id'], unique=False)

    op.create_table(
        'finance_journal_sequences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('year_month', sa.String(length=7), nullable=False),
        sa.Column('last_value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'year_month', name='uq_finance_journal_sequences_tenant_month'),
    )
    op.create_index('ix_finance_journal_sequences_tenant_id', 'finance_journal_sequences', ['tenant_id'], unique=False)

    op.create_table(
        'finance_journals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('journal_no', sa.String(length=30), nullable=False),
        sa.Column('journal_date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_type', finance_journal_source_type, nullable=True),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('status', finance_journal_status, nullable=False, server_default='DRAFT'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('posted_at', sa.DateTime(), nullable=True),
        sa.Column('voided_at', sa.DateTime(), nullable=True),
        sa.Column('void_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'journal_no', name='uq_finance_journals_tenant_journal_no'),
        sa.UniqueConstraint('tenant_id', 'source_type', 'source_id', name='uq_finance_journals_tenant_source'),
    )
    op.create_index('ix_finance_journals_tenant_id', 'finance_journals', ['tenant_id'], unique=False)

    op.create_table(
        'finance_journal_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('journal_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('entry_side', finance_entry_side, nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('memo', sa.Text(), nullable=True),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.CheckConstraint('amount > 0', name='ck_finance_journal_lines_amount_positive'),
        sa.ForeignKeyConstraint(['account_id'], ['finance_accounts.id']),
        sa.ForeignKeyConstraint(['journal_id'], ['finance_journals.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_finance_journal_lines_tenant_id', 'finance_journal_lines', ['tenant_id'], unique=False)
    op.create_index('ix_finance_journal_lines_journal_id', 'finance_journal_lines', ['journal_id'], unique=False)

    op.create_table(
        'finance_cash_bank_transactions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('cash_bank_account_id', sa.Integer(), nullable=False),
        sa.Column('trx_date', sa.Date(), nullable=False),
        sa.Column('trx_type', finance_cash_bank_transaction_type, nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('counterpart_account_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('journal_id', sa.Integer(), nullable=True),
        sa.Column('status', finance_cash_bank_transaction_status, nullable=False, server_default='DRAFT'),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('approved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.CheckConstraint('amount > 0', name='ck_finance_cash_bank_transactions_amount_positive'),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['cash_bank_account_id'], ['finance_cash_bank_accounts.id']),
        sa.ForeignKeyConstraint(['counterpart_account_id'], ['finance_accounts.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['journal_id'], ['finance_journals.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_finance_cash_bank_transactions_tenant_id', 'finance_cash_bank_transactions', ['tenant_id'], unique=False)


def downgrade():
    op.drop_index('ix_finance_cash_bank_transactions_tenant_id', table_name='finance_cash_bank_transactions')
    op.drop_table('finance_cash_bank_transactions')

    op.drop_index('ix_finance_journal_lines_journal_id', table_name='finance_journal_lines')
    op.drop_index('ix_finance_journal_lines_tenant_id', table_name='finance_journal_lines')
    op.drop_table('finance_journal_lines')

    op.drop_index('ix_finance_journals_tenant_id', table_name='finance_journals')
    op.drop_table('finance_journals')

    op.drop_index('ix_finance_journal_sequences_tenant_id', table_name='finance_journal_sequences')
    op.drop_table('finance_journal_sequences')

    op.drop_index('ix_finance_settings_tenant_id', table_name='finance_settings')
    op.drop_table('finance_settings')

    op.drop_index('ix_finance_cash_bank_accounts_tenant_id', table_name='finance_cash_bank_accounts')
    op.drop_table('finance_cash_bank_accounts')

    op.drop_index('ix_finance_periods_tenant_id', table_name='finance_periods')
    op.drop_table('finance_periods')

    op.drop_index('ix_finance_accounts_parent_id', table_name='finance_accounts')
    op.drop_index('ix_finance_accounts_tenant_id', table_name='finance_accounts')
    op.drop_table('finance_accounts')

    op.execute("DROP TYPE IF EXISTS financecashbanktransactionstatus")
    op.execute("DROP TYPE IF EXISTS financecashbanktransactiontype")
    op.execute("DROP TYPE IF EXISTS financecashbankaccounttype")
    op.execute("DROP TYPE IF EXISTS financejournalsourcetype")
    op.execute("DROP TYPE IF EXISTS financeentryside")
    op.execute("DROP TYPE IF EXISTS financejournalstatus")
    op.execute("DROP TYPE IF EXISTS financeaccountingbasis")
    op.execute("DROP TYPE IF EXISTS financeperiodstatus")
    op.execute("DROP TYPE IF EXISTS financenormalbalance")
    op.execute("DROP TYPE IF EXISTS financeaccountcategory")
