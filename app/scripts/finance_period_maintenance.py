import argparse
import os
import sys
from datetime import date
from calendar import monthrange

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import create_app
from app.extensions import db
from app.models import FinancePeriod, FinancePeriodStatus, Tenant
from app.utils.timezone import local_today, local_now


def _month_bounds(year: int, month: int):
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def _resolve_target_month(month_value: str | None):
    if month_value:
        parts = month_value.split("-", 1)
        if len(parts) != 2:
            raise ValueError("Format bulan harus YYYY-MM")
        year = int(parts[0])
        month = int(parts[1])
        if month < 1 or month > 12:
            raise ValueError("Bulan harus 01..12")
        return year, month
    today = local_today()
    return today.year, today.month


def _select_tenants(tenant_ids: list[int] | None):
    if tenant_ids:
        return Tenant.query.filter(Tenant.id.in_(tenant_ids), Tenant.is_deleted.is_(False)).order_by(Tenant.id.asc()).all()
    return Tenant.query.filter(Tenant.is_deleted.is_(False)).order_by(Tenant.id.asc()).all()


def _create_open_period_if_missing(tenant_id: int, period_name: str, start_date: date, end_date: date):
    existing = FinancePeriod.query.filter_by(tenant_id=tenant_id, name=period_name).first()
    if existing:
        return False
    db.session.add(
        FinancePeriod(
            tenant_id=tenant_id,
            name=period_name,
            start_date=start_date,
            end_date=end_date,
            status=FinancePeriodStatus.OPEN,
        )
    )
    return True


def _lock_old_periods(tenant_id: int, before_date: date, actor_user_id: int | None = None):
    candidates = FinancePeriod.query.filter(
        FinancePeriod.tenant_id == tenant_id,
        FinancePeriod.end_date < before_date,
        FinancePeriod.status.in_([FinancePeriodStatus.OPEN, FinancePeriodStatus.CLOSED]),
    ).all()
    changed = 0
    for period in candidates:
        period.status = FinancePeriodStatus.LOCKED
        period.closed_at = local_now()
        period.closed_by_user_id = actor_user_id
        changed += 1
    return changed


def run(month_value: str | None = None, tenant_ids: list[int] | None = None, lock_old_periods: bool = False):
    app = create_app()
    with app.app_context():
        year, month = _resolve_target_month(month_value)
        period_name = f"{year:04d}-{month:02d}"
        start_date, end_date = _month_bounds(year, month)
        cutoff = start_date

        created_count = 0
        locked_count = 0
        tenants = _select_tenants(tenant_ids)
        for tenant in tenants:
            if _create_open_period_if_missing(tenant.id, period_name, start_date, end_date):
                created_count += 1
            if lock_old_periods:
                locked_count += _lock_old_periods(tenant.id, cutoff)

        db.session.commit()
        print(
            "Finance period maintenance done:",
            f"target_period={period_name}",
            f"tenants={len(tenants)}",
            f"created_open_periods={created_count}",
            f"locked_old_periods={locked_count}",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Finance monthly maintenance (period creation + optional lock old periods)")
    parser.add_argument("--month", dest="month_value", help="Target month format YYYY-MM. Default: current local month.")
    parser.add_argument("--tenant-id", dest="tenant_ids", action="append", type=int, help="Optional tenant id (can repeat).")
    parser.add_argument("--lock-old-periods", action="store_true", help="Lock periods that ended before target month.")
    args = parser.parse_args()
    run(
        month_value=args.month_value,
        tenant_ids=args.tenant_ids,
        lock_old_periods=args.lock_old_periods,
    )
