from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def to_rupiah_int(value, default=0):
    """Normalisasi nominal ke integer Rupiah agar konsisten lintas layer aplikasi."""
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value

    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default

    return int(number.quantize(Decimal('1'), rounding=ROUND_HALF_UP))
