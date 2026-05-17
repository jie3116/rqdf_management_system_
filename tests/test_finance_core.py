from datetime import date, datetime

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    FinanceAccount,
    FinanceAccountCategory,
    FinanceCashBankAccount,
    FinanceCashBankAccountType,
    FinanceCashBankTransaction,
    FinanceCashBankTransactionStatus,
    FinanceEntrySide,
    FinanceJournal,
    FinanceJournalLine,
    FinanceJournalSourceType,
    FinanceJournalStatus,
    FinanceNormalBalance,
    FinancePeriod,
    FinancePeriodStatus,
    FinanceSetting,
    Invoice,
    PaymentStatus,
    Student,
    Tenant,
    User,
    UserRole,
    Transaction,
)
from app.routes.admin import _financial_position_data
from app.services.finance_posting_service import (
    create_cash_bank_transaction,
    post_invoice_payment,
    reverse_journal,
)


class TestConfig:
    SECRET_KEY = "test-secret"
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def finance_context(app):
    tenant = Tenant(name="Tenant A", slug="tenant-a", code="TA", is_default=True)
    db.session.add(tenant)
    db.session.flush()

    actor = User(
        tenant_id=tenant.id,
        username="admin",
        email="admin@example.test",
        role=UserRole.ADMIN,
        must_change_password=False,
    )
    student_user = User(
        tenant_id=tenant.id,
        username="student",
        email="student@example.test",
        role=UserRole.SISWA,
        must_change_password=False,
    )
    student = Student(user=student_user, nis="S001", full_name="Student One")

    cash_account = FinanceAccount(
        tenant_id=tenant.id,
        code="1010",
        name="Kas Operasional",
        category=FinanceAccountCategory.ASSET,
        normal_balance=FinanceNormalBalance.DEBIT,
        is_active=True,
    )
    bank_account = FinanceAccount(
        tenant_id=tenant.id,
        code="1020",
        name="Bank Operasional",
        category=FinanceAccountCategory.ASSET,
        normal_balance=FinanceNormalBalance.DEBIT,
        is_active=True,
    )
    revenue_account = FinanceAccount(
        tenant_id=tenant.id,
        code="4100",
        name="Pendapatan SPP",
        category=FinanceAccountCategory.REVENUE,
        normal_balance=FinanceNormalBalance.CREDIT,
        is_active=True,
    )
    expense_account = FinanceAccount(
        tenant_id=tenant.id,
        code="5100",
        name="Beban ATK",
        category=FinanceAccountCategory.EXPENSE,
        normal_balance=FinanceNormalBalance.DEBIT,
        is_active=True,
    )
    db.session.add_all([actor, student_user, student, cash_account, bank_account, revenue_account, expense_account])
    db.session.flush()

    cash_bank = FinanceCashBankAccount(
        tenant_id=tenant.id,
        account_name="Kas Operasional",
        account_type=FinanceCashBankAccountType.CASH,
        gl_account_id=cash_account.id,
        is_active=True,
    )
    settings = FinanceSetting(
        tenant_id=tenant.id,
        default_cash_bank_account_id=None,
        default_spp_revenue_account_id=revenue_account.id,
    )
    db.session.add(cash_bank)
    db.session.flush()
    settings.default_cash_bank_account_id = cash_bank.id
    db.session.add(settings)
    db.session.add(
        FinancePeriod(
            tenant_id=tenant.id,
            name="2026-05",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            status=FinancePeriodStatus.OPEN,
        )
    )

    invoice = Invoice(
        student=student,
        invoice_number="INV-001",
        total_amount=100_000,
        paid_amount=100_000,
        status=PaymentStatus.PAID,
        due_date=date(2026, 5, 31),
    )
    trx = Transaction(
        invoice=invoice,
        amount=100_000,
        method="cash",
        date=datetime(2026, 5, 10, 9, 0, 0),
        pic_id=actor.id,
    )
    db.session.add_all([invoice, trx])
    db.session.commit()

    return {
        "tenant": tenant,
        "actor": actor,
        "student": student,
        "cash_account": cash_account,
        "bank_account": bank_account,
        "revenue_account": revenue_account,
        "expense_account": expense_account,
        "cash_bank": cash_bank,
        "invoice_transaction": trx,
    }


def _journal_amounts_by_side(journal):
    debit = sum(int(line.amount or 0) for line in journal.lines if line.entry_side == FinanceEntrySide.DEBIT)
    credit = sum(int(line.amount or 0) for line in journal.lines if line.entry_side == FinanceEntrySide.CREDIT)
    return debit, credit


def test_invoice_payment_posts_balanced_journal_and_is_idempotent(finance_context):
    tenant = finance_context["tenant"]
    actor = finance_context["actor"]
    trx = finance_context["invoice_transaction"]

    first_journal_id = post_invoice_payment(tenant_id=tenant.id, transaction_id=trx.id, actor_user_id=actor.id)
    second_journal_id = post_invoice_payment(tenant_id=tenant.id, transaction_id=trx.id, actor_user_id=actor.id)

    assert second_journal_id == first_journal_id
    assert FinanceJournal.query.count() == 1

    journal = db.session.get(FinanceJournal, first_journal_id)
    assert journal.status == FinanceJournalStatus.POSTED
    assert journal.source_type == FinanceJournalSourceType.INVOICE_PAYMENT
    assert _journal_amounts_by_side(journal) == (100_000, 100_000)


def test_invoice_payment_in_closed_period_stays_draft(finance_context):
    tenant = finance_context["tenant"]
    actor = finance_context["actor"]
    trx = finance_context["invoice_transaction"]
    period = FinancePeriod.query.filter_by(tenant_id=tenant.id, name="2026-05").one()
    period.status = FinancePeriodStatus.LOCKED
    db.session.commit()

    journal_id = post_invoice_payment(tenant_id=tenant.id, transaction_id=trx.id, actor_user_id=actor.id)

    journal = db.session.get(FinanceJournal, journal_id)
    assert journal.status == FinanceJournalStatus.DRAFT
    assert journal.posted_at is None
    assert _journal_amounts_by_side(journal) == (100_000, 100_000)


def test_cash_bank_out_creates_posted_journal_with_expected_sides(finance_context):
    tenant = finance_context["tenant"]
    actor = finance_context["actor"]
    cash_bank = finance_context["cash_bank"]
    cash_account = finance_context["cash_account"]
    expense_account = finance_context["expense_account"]

    cash_bank_trx_id = create_cash_bank_transaction(
        tenant_id=tenant.id,
        trx_date=date(2026, 5, 12),
        cash_bank_account_id=cash_bank.id,
        trx_type="OUT",
        amount=25_000,
        counterpart_account_id=expense_account.id,
        description="Beli ATK",
        actor_user_id=actor.id,
    )

    cash_bank_trx = db.session.get(FinanceCashBankTransaction, cash_bank_trx_id)
    journal = cash_bank_trx.journal
    assert cash_bank_trx.status == FinanceCashBankTransactionStatus.POSTED
    assert journal.status == FinanceJournalStatus.POSTED
    assert journal.source_type == FinanceJournalSourceType.CASH_BANK_TRANSACTION

    sides = {(line.account_id, line.entry_side): line.amount for line in journal.lines}
    assert sides[(expense_account.id, FinanceEntrySide.DEBIT)] == 25_000
    assert sides[(cash_account.id, FinanceEntrySide.CREDIT)] == 25_000


def test_transfer_requires_asset_counterpart(finance_context):
    tenant = finance_context["tenant"]
    actor = finance_context["actor"]
    cash_bank = finance_context["cash_bank"]
    expense_account = finance_context["expense_account"]

    with pytest.raises(ValueError, match="Akun lawan TRANSFER harus akun ASSET"):
        create_cash_bank_transaction(
            tenant_id=tenant.id,
            trx_date=date(2026, 5, 12),
            cash_bank_account_id=cash_bank.id,
            trx_type="TRANSFER",
            amount=25_000,
            counterpart_account_id=expense_account.id,
            description="Transfer salah akun",
            actor_user_id=actor.id,
        )


def test_reverse_journal_creates_opposite_lines_and_voids_cash_bank_source(finance_context):
    tenant = finance_context["tenant"]
    actor = finance_context["actor"]
    cash_bank = finance_context["cash_bank"]
    expense_account = finance_context["expense_account"]

    cash_bank_trx_id = create_cash_bank_transaction(
        tenant_id=tenant.id,
        trx_date=date(2026, 5, 12),
        cash_bank_account_id=cash_bank.id,
        trx_type="OUT",
        amount=25_000,
        counterpart_account_id=expense_account.id,
        description="Beli ATK",
        actor_user_id=actor.id,
    )
    cash_bank_trx = db.session.get(FinanceCashBankTransaction, cash_bank_trx_id)
    original_journal_id = cash_bank_trx.journal_id

    reversal_journal_id = reverse_journal(
        tenant_id=tenant.id,
        journal_id=original_journal_id,
        reason="Salah input",
        actor_user_id=actor.id,
    )

    original = db.session.get(FinanceJournal, original_journal_id)
    reversal = db.session.get(FinanceJournal, reversal_journal_id)
    db.session.refresh(cash_bank_trx)

    assert original.status == FinanceJournalStatus.VOID
    assert cash_bank_trx.status == FinanceCashBankTransactionStatus.VOID
    assert reversal.status == FinanceJournalStatus.POSTED
    assert reversal.source_type == FinanceJournalSourceType.REVERSAL
    assert _journal_amounts_by_side(reversal) == (25_000, 25_000)


def test_financial_position_balances_assets_with_liabilities_equity_and_net_income(finance_context):
    tenant = finance_context["tenant"]
    actor = finance_context["actor"]
    cash_account = finance_context["cash_account"]
    revenue_account = finance_context["revenue_account"]

    liability_account = FinanceAccount(
        tenant_id=tenant.id,
        code="2100",
        name="Utang Operasional",
        category=FinanceAccountCategory.LIABILITY,
        normal_balance=FinanceNormalBalance.CREDIT,
        is_active=True,
    )
    equity_account = FinanceAccount(
        tenant_id=tenant.id,
        code="3100",
        name="Modal Yayasan",
        category=FinanceAccountCategory.EQUITY,
        normal_balance=FinanceNormalBalance.CREDIT,
        is_active=True,
    )
    db.session.add_all([liability_account, equity_account])
    db.session.flush()

    opening = FinanceJournal(
        tenant_id=tenant.id,
        journal_no="JV-TEST-OPEN",
        journal_date=date(2026, 5, 1),
        description="Saldo awal",
        status=FinanceJournalStatus.POSTED,
        created_by_user_id=actor.id,
        approved_by_user_id=actor.id,
        posted_at=datetime(2026, 5, 1, 8, 0, 0),
    )
    income = FinanceJournal(
        tenant_id=tenant.id,
        journal_no="JV-TEST-INCOME",
        journal_date=date(2026, 5, 5),
        description="Pendapatan berjalan",
        status=FinanceJournalStatus.POSTED,
        created_by_user_id=actor.id,
        approved_by_user_id=actor.id,
        posted_at=datetime(2026, 5, 5, 8, 0, 0),
    )
    db.session.add_all([opening, income])
    db.session.flush()
    db.session.add_all([
        FinanceJournalLine(
            tenant_id=tenant.id,
            journal_id=opening.id,
            account_id=cash_account.id,
            entry_side=FinanceEntrySide.DEBIT,
            amount=200_000,
            memo="Saldo awal kas",
        ),
        FinanceJournalLine(
            tenant_id=tenant.id,
            journal_id=opening.id,
            account_id=liability_account.id,
            entry_side=FinanceEntrySide.CREDIT,
            amount=50_000,
            memo="Saldo awal utang",
        ),
        FinanceJournalLine(
            tenant_id=tenant.id,
            journal_id=opening.id,
            account_id=equity_account.id,
            entry_side=FinanceEntrySide.CREDIT,
            amount=150_000,
            memo="Saldo awal modal",
        ),
        FinanceJournalLine(
            tenant_id=tenant.id,
            journal_id=income.id,
            account_id=cash_account.id,
            entry_side=FinanceEntrySide.DEBIT,
            amount=100_000,
            memo="Kas pendapatan",
        ),
        FinanceJournalLine(
            tenant_id=tenant.id,
            journal_id=income.id,
            account_id=revenue_account.id,
            entry_side=FinanceEntrySide.CREDIT,
            amount=100_000,
            memo="Pendapatan",
        ),
    ])
    db.session.commit()

    report = _financial_position_data(tenant.id, date(2026, 5, 31))

    assert report["total_assets"] == 300_000
    assert report["total_liabilities"] == 50_000
    assert report["total_equity"] == 250_000
    assert report["net_income"] == 100_000
    assert report["total_assets"] == report["total_liabilities_equity"]
