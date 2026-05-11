import os
import sys

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import (
    FinanceAccount,
    FinanceAccountCategory,
    FinanceCashBankAccount,
    FinanceCashBankAccountType,
    FinanceNormalBalance,
    FinanceSetting,
    Tenant,
)


DEFAULT_COA = (
    ("1010", "Kas Operasional", FinanceAccountCategory.ASSET, FinanceNormalBalance.DEBIT),
    ("1020", "Bank Operasional", FinanceAccountCategory.ASSET, FinanceNormalBalance.DEBIT),
    ("1100", "Piutang SPP", FinanceAccountCategory.ASSET, FinanceNormalBalance.DEBIT),
    ("2010", "Utang Titipan Tabungan Santri", FinanceAccountCategory.LIABILITY, FinanceNormalBalance.CREDIT),
    ("3100", "Modal / Saldo Awal", FinanceAccountCategory.EQUITY, FinanceNormalBalance.CREDIT),
    ("4100", "Pendapatan SPP", FinanceAccountCategory.REVENUE, FinanceNormalBalance.CREDIT),
    ("4200", "Pendapatan Pendaftaran", FinanceAccountCategory.REVENUE, FinanceNormalBalance.CREDIT),
    ("4300", "Pendapatan Donasi / Infaq", FinanceAccountCategory.REVENUE, FinanceNormalBalance.CREDIT),
    ("5100", "Beban Gaji", FinanceAccountCategory.EXPENSE, FinanceNormalBalance.DEBIT),
    ("5200", "Beban ATK", FinanceAccountCategory.EXPENSE, FinanceNormalBalance.DEBIT),
    ("5300", "Beban Utilitas", FinanceAccountCategory.EXPENSE, FinanceNormalBalance.DEBIT),
)


def _upsert_account(*, tenant_id, code, name, category, normal_balance):
    account = FinanceAccount.query.filter_by(tenant_id=tenant_id, code=code).first()
    if not account:
        account = FinanceAccount(
            tenant_id=tenant_id,
            code=code,
            name=name,
            category=category,
            normal_balance=normal_balance,
            is_active=True,
        )
        db.session.add(account)
        db.session.flush()
        return account, True

    account.name = name
    account.category = category
    account.normal_balance = normal_balance
    account.is_active = True
    db.session.flush()
    return account, False


def seed_finance_defaults():
    app = create_app()
    with app.app_context():
        tenants = Tenant.query.order_by(Tenant.id.asc()).all()
        total_created_accounts = 0
        total_updated_accounts = 0
        created_cash_bank = 0
        created_settings = 0

        for tenant in tenants:
            account_map = {}
            for code, name, category, normal_balance in DEFAULT_COA:
                account, created = _upsert_account(
                    tenant_id=tenant.id,
                    code=code,
                    name=name,
                    category=category,
                    normal_balance=normal_balance,
                )
                account_map[code] = account
                if created:
                    total_created_accounts += 1
                else:
                    total_updated_accounts += 1

            cash_account = account_map["1010"]
            cash_bank = FinanceCashBankAccount.query.filter_by(
                tenant_id=tenant.id,
                account_name="Kas Operasional",
            ).first()
            if not cash_bank:
                cash_bank = FinanceCashBankAccount(
                    tenant_id=tenant.id,
                    account_name="Kas Operasional",
                    account_type=FinanceCashBankAccountType.CASH,
                    gl_account_id=cash_account.id,
                    is_active=True,
                )
                db.session.add(cash_bank)
                db.session.flush()
                created_cash_bank += 1
            else:
                cash_bank.account_type = FinanceCashBankAccountType.CASH
                cash_bank.gl_account_id = cash_account.id
                cash_bank.is_active = True

            settings = FinanceSetting.query.filter_by(tenant_id=tenant.id).first()
            if not settings:
                settings = FinanceSetting(tenant_id=tenant.id)
                db.session.add(settings)
                created_settings += 1

            settings.default_cash_bank_account_id = cash_bank.id
            settings.default_spp_revenue_account_id = account_map["4100"].id
            settings.default_registration_revenue_account_id = account_map["4200"].id
            settings.default_savings_liability_account_id = account_map["2010"].id
            settings.default_donation_revenue_account_id = account_map["4300"].id

        db.session.commit()
        print(
            "Finance defaults seeded:",
            f"tenants={len(tenants)}",
            f"accounts_created={total_created_accounts}",
            f"accounts_updated={total_updated_accounts}",
            f"cash_bank_created={created_cash_bank}",
            f"settings_created={created_settings}",
        )


if __name__ == "__main__":
    seed_finance_defaults()
