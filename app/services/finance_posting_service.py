from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

from app.extensions import db
from app.models import (
    FinanceAccount,
    FinanceAccountCategory,
    FinanceCashBankAccount,
    FinanceEntrySide,
    FinanceJournal,
    FinanceJournalLine,
    FinanceJournalSequence,
    FinanceJournalSourceType,
    FinanceJournalStatus,
    FinancePeriod,
    FinancePeriodStatus,
    FinanceSetting,
    Invoice,
    SavingsTransactionStatus,
    SavingsTransactionType,
    Student,
    StudentSavingsTransaction,
    Transaction,
    User,
)
from app.utils.timezone import utc_now_naive


@dataclass(frozen=True)
class PostingContext:
    can_post: bool
    reason: Optional[str] = None


def generate_journal_no(*, tenant_id: int, journal_date: date) -> str:
    year_month = journal_date.strftime('%Y-%m')
    sequence = (
        FinanceJournalSequence.query
        .filter_by(tenant_id=tenant_id, year_month=year_month)
        .with_for_update()
        .first()
    )
    if not sequence:
        sequence = FinanceJournalSequence(tenant_id=tenant_id, year_month=year_month, last_value=0)
        db.session.add(sequence)
        db.session.flush()
        sequence = (
            FinanceJournalSequence.query
            .filter_by(id=sequence.id)
            .with_for_update()
            .first()
        )
    sequence.last_value = (sequence.last_value or 0) + 1
    db.session.flush()
    return f"JV-{year_month}-{sequence.last_value:04d}"


def post_invoice_payment(*, tenant_id: int, transaction_id: int, actor_user_id: int) -> int:
    existing = _find_existing_source_journal(
        tenant_id=tenant_id,
        source_type=FinanceJournalSourceType.INVOICE_PAYMENT,
        source_id=transaction_id,
    )
    if existing:
        return existing.id

    trx = (
        Transaction.query
        .join(Invoice, Invoice.id == Transaction.invoice_id)
        .join(Student, Student.id == Invoice.student_id)
        .join(User, User.id == Student.user_id)
        .filter(
            Transaction.id == transaction_id,
            User.tenant_id == tenant_id,
            Invoice.is_deleted.is_(False),
            Student.is_deleted.is_(False),
            User.is_deleted.is_(False),
        )
        .first()
    )
    if not trx:
        raise ValueError("Transaksi pembayaran tidak ditemukan untuk tenant ini.")

    invoice = trx.invoice
    amount = int(trx.amount or 0)
    if amount <= 0:
        raise ValueError("Nominal transaksi pembayaran harus lebih dari 0.")

    settings = _get_finance_settings(tenant_id)
    cash_gl_account_id = _resolve_cash_bank_gl_account_id(tenant_id, settings)
    revenue_account_id = getattr(settings, 'default_spp_revenue_account_id', None) if settings else None
    journal_date = _resolve_journal_date(trx.date)
    journal_description = (
        f"Pembayaran invoice {invoice.invoice_number or invoice.id} "
        f"(trx #{trx.id}, metode={trx.method or '-'})"
    )

    journal = _create_journal_with_lines(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        journal_date=journal_date,
        description=journal_description,
        source_type=FinanceJournalSourceType.INVOICE_PAYMENT,
        source_id=trx.id,
        line_specs=(
            (cash_gl_account_id, FinanceEntrySide.DEBIT, amount, 'Kas/Bank masuk'),
            (revenue_account_id, FinanceEntrySide.CREDIT, amount, 'Pendapatan pendidikan'),
        ),
        reference_type='transaction',
        reference_id=trx.id,
    )
    db.session.commit()
    return journal.id


def post_savings_transaction(*, tenant_id: int, savings_transaction_id: int, actor_user_id: int) -> int:
    source_deposit = FinanceJournalSourceType.SAVINGS_DEPOSIT
    source_withdrawal = FinanceJournalSourceType.SAVINGS_WITHDRAWAL

    savings_trx = (
        StudentSavingsTransaction.query
        .join(Student, Student.id == StudentSavingsTransaction.student_id)
        .join(User, User.id == Student.user_id)
        .filter(
            StudentSavingsTransaction.id == savings_transaction_id,
            StudentSavingsTransaction.tenant_id == tenant_id,
            User.tenant_id == tenant_id,
            Student.is_deleted.is_(False),
            User.is_deleted.is_(False),
        )
        .first()
    )
    if not savings_trx:
        raise ValueError("Transaksi tabungan tidak ditemukan untuk tenant ini.")
    if savings_trx.status != SavingsTransactionStatus.APPROVED:
        raise ValueError("Hanya transaksi tabungan APPROVED yang dapat diposting ke jurnal.")

    source_type = (
        source_deposit
        if savings_trx.transaction_type == SavingsTransactionType.DEPOSIT
        else source_withdrawal
    )
    existing = _find_existing_source_journal(
        tenant_id=tenant_id,
        source_type=source_type,
        source_id=savings_trx.id,
    )
    if existing:
        return existing.id

    amount = int(savings_trx.amount or 0)
    if amount <= 0:
        raise ValueError("Nominal transaksi tabungan harus lebih dari 0.")

    settings = _get_finance_settings(tenant_id)
    cash_gl_account_id = _resolve_cash_bank_gl_account_id(tenant_id, settings)
    savings_liability_account_id = getattr(settings, 'default_savings_liability_account_id', None) if settings else None
    journal_date = _resolve_journal_date(savings_trx.approved_at or savings_trx.updated_at or savings_trx.created_at)

    if savings_trx.transaction_type == SavingsTransactionType.DEPOSIT:
        line_specs = (
            (cash_gl_account_id, FinanceEntrySide.DEBIT, amount, 'Kas/Bank masuk'),
            (savings_liability_account_id, FinanceEntrySide.CREDIT, amount, 'Titipan tabungan santri'),
        )
        label = "Setoran tabungan"
    else:
        line_specs = (
            (savings_liability_account_id, FinanceEntrySide.DEBIT, amount, 'Pengurangan titipan tabungan'),
            (cash_gl_account_id, FinanceEntrySide.CREDIT, amount, 'Kas/Bank keluar'),
        )
        label = "Penarikan tabungan"

    journal = _create_journal_with_lines(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        journal_date=journal_date,
        description=f"{label} santri (trx tabungan #{savings_trx.id})",
        source_type=source_type,
        source_id=savings_trx.id,
        line_specs=line_specs,
        reference_type='student_savings_transaction',
        reference_id=savings_trx.id,
    )
    db.session.commit()
    return journal.id


def post_journal(*, tenant_id: int, journal_id: int, actor_user_id: int) -> None:
    journal = (
        FinanceJournal.query
        .filter_by(id=journal_id, tenant_id=tenant_id)
        .with_for_update()
        .first()
    )
    if not journal:
        raise ValueError("Jurnal tidak ditemukan.")
    if journal.status == FinanceJournalStatus.VOID:
        raise ValueError("Jurnal VOID tidak dapat diposting.")
    _validate_journal_balance(journal.lines)
    posting_context = _posting_context(tenant_id=tenant_id, journal_date=journal.journal_date)
    if not posting_context.can_post:
        raise ValueError(posting_context.reason or "Periode akuntansi tidak siap untuk posting.")

    journal.status = FinanceJournalStatus.POSTED
    journal.posted_at = utc_now_naive()
    journal.approved_by_user_id = actor_user_id
    db.session.flush()


def reverse_journal(*, tenant_id: int, journal_id: int, reason: str, actor_user_id: int) -> int:
    original = (
        FinanceJournal.query
        .filter_by(id=journal_id, tenant_id=tenant_id)
        .with_for_update()
        .first()
    )
    if not original:
        raise ValueError("Jurnal yang akan direversal tidak ditemukan.")
    if original.status != FinanceJournalStatus.POSTED:
        raise ValueError("Hanya jurnal POSTED yang dapat direversal.")

    posting_context = _posting_context(tenant_id=tenant_id, journal_date=date.today())
    if not posting_context.can_post:
        raise ValueError(posting_context.reason or "Periode akuntansi tidak siap untuk reversal.")

    reversal_journal = FinanceJournal(
        tenant_id=tenant_id,
        journal_no=generate_journal_no(tenant_id=tenant_id, journal_date=date.today()),
        journal_date=date.today(),
        description=f"Reversal jurnal #{original.id}: {reason}",
        source_type=FinanceJournalSourceType.REVERSAL,
        source_id=original.id,
        status=FinanceJournalStatus.DRAFT,
        created_by_user_id=actor_user_id,
    )
    db.session.add(reversal_journal)
    db.session.flush()

    for line in original.lines:
        reverse_side = FinanceEntrySide.CREDIT if line.entry_side == FinanceEntrySide.DEBIT else FinanceEntrySide.DEBIT
        db.session.add(
            FinanceJournalLine(
                tenant_id=tenant_id,
                journal_id=reversal_journal.id,
                account_id=line.account_id,
                entry_side=reverse_side,
                amount=line.amount,
                memo=f"Reversal dari jurnal #{original.id}",
                reference_type='finance_journal',
                reference_id=original.id,
            )
        )

    post_journal(tenant_id=tenant_id, journal_id=reversal_journal.id, actor_user_id=actor_user_id)
    original.status = FinanceJournalStatus.VOID
    original.voided_at = utc_now_naive()
    original.void_reason = reason
    db.session.commit()
    return reversal_journal.id


def _find_existing_source_journal(*, tenant_id: int, source_type: FinanceJournalSourceType, source_id: int) -> Optional[FinanceJournal]:
    return FinanceJournal.query.filter_by(
        tenant_id=tenant_id,
        source_type=source_type,
        source_id=source_id,
    ).first()


def _get_finance_settings(tenant_id: int) -> Optional[FinanceSetting]:
    return FinanceSetting.query.filter_by(tenant_id=tenant_id).first()


def _resolve_cash_bank_gl_account_id(tenant_id: int, settings: Optional[FinanceSetting]) -> Optional[int]:
    if not settings or not settings.default_cash_bank_account_id:
        return None
    cash_bank_account = FinanceCashBankAccount.query.filter_by(
        id=settings.default_cash_bank_account_id,
        tenant_id=tenant_id,
        is_active=True,
    ).first()
    if not cash_bank_account:
        return None

    gl_account = FinanceAccount.query.filter_by(
        id=cash_bank_account.gl_account_id,
        tenant_id=tenant_id,
        is_active=True,
    ).first()
    if not gl_account or gl_account.category != FinanceAccountCategory.ASSET:
        return None
    return gl_account.id


def _resolve_journal_date(raw_value: Optional[datetime]) -> date:
    if isinstance(raw_value, datetime):
        return raw_value.date()
    return date.today()


def _posting_context(*, tenant_id: int, journal_date: date) -> PostingContext:
    period = (
        FinancePeriod.query
        .filter(
            FinancePeriod.tenant_id == tenant_id,
            FinancePeriod.start_date <= journal_date,
            FinancePeriod.end_date >= journal_date,
        )
        .first()
    )
    if not period:
        return PostingContext(can_post=False, reason="Periode akuntansi belum dibuat.")
    if period.status != FinancePeriodStatus.OPEN:
        return PostingContext(can_post=False, reason="Periode akuntansi tidak dalam status OPEN.")
    return PostingContext(can_post=True)


def _validate_journal_balance(lines: Iterable[FinanceJournalLine]) -> None:
    debit = 0
    credit = 0
    line_count = 0
    for line in lines:
        line_count += 1
        amount = int(line.amount or 0)
        if amount <= 0:
            raise ValueError("Semua baris jurnal harus bernilai positif.")
        if line.entry_side == FinanceEntrySide.DEBIT:
            debit += amount
        elif line.entry_side == FinanceEntrySide.CREDIT:
            credit += amount
    if line_count < 2:
        raise ValueError("Jurnal minimal harus memiliki dua baris.")
    if debit != credit:
        raise ValueError("Jurnal tidak seimbang (debit != kredit).")


def _create_journal_with_lines(
    *,
    tenant_id: int,
    actor_user_id: int,
    journal_date: date,
    description: str,
    source_type: FinanceJournalSourceType,
    source_id: int,
    line_specs: Iterable[tuple[Optional[int], FinanceEntrySide, int, str]],
    reference_type: str,
    reference_id: int,
) -> FinanceJournal:
    posting_context = _posting_context(tenant_id=tenant_id, journal_date=journal_date)
    missing_accounts = [spec for spec in line_specs if not spec[0]]

    journal = FinanceJournal(
        tenant_id=tenant_id,
        journal_no=generate_journal_no(tenant_id=tenant_id, journal_date=journal_date),
        journal_date=journal_date,
        description=description,
        source_type=source_type,
        source_id=source_id,
        status=FinanceJournalStatus.DRAFT,
        created_by_user_id=actor_user_id,
    )
    db.session.add(journal)
    db.session.flush()

    for account_id, entry_side, amount, memo in line_specs:
        if not account_id:
            continue
        db.session.add(
            FinanceJournalLine(
                tenant_id=tenant_id,
                journal_id=journal.id,
                account_id=account_id,
                entry_side=entry_side,
                amount=amount,
                memo=memo,
                reference_type=reference_type,
                reference_id=reference_id,
            )
        )

    db.session.flush()
    if missing_accounts:
        return journal
    _validate_journal_balance(journal.lines)
    if posting_context.can_post:
        journal.status = FinanceJournalStatus.POSTED
        journal.posted_at = utc_now_naive()
        journal.approved_by_user_id = actor_user_id
    return journal
