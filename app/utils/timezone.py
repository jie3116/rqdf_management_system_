from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Asia/Jakarta")


def utc_now():
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def utc_now_naive():
    """Return naive UTC datetime for DB columns without timezone metadata."""
    return utc_now().replace(tzinfo=None)


def _local_now_aware():
    """Return timezone-aware local datetime in app timezone."""
    return utc_now().astimezone(APP_TIMEZONE)


def local_now():
    """Return naive local datetime in app timezone."""
    return _local_now_aware().replace(tzinfo=None)


def local_today():
    """Return local date in app timezone."""
    return _local_now_aware().date()


def local_day_bounds_utc_naive(day=None):
    """
    Return naive UTC [start, end) bounds for a local-calendar day.
    """
    local_day = day or local_today()
    start_local = datetime.combine(local_day, time.min, tzinfo=APP_TIMEZONE)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc
